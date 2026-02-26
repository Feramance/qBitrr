from __future__ import annotations

import atexit
import contextlib
import glob
import logging
import os
import signal
import sys
import time
from multiprocessing import Event, freeze_support
from queue import SimpleQueue
from threading import Event as ThreadEvent
from threading import Thread
from time import monotonic

import pathos
import qbittorrentapi
import requests
from packaging import version as version_parser
from packaging.version import Version as VersionClass
from qbittorrentapi import APINames

from qBitrr.auto_update import AutoUpdater, perform_self_update
from qBitrr.bundled_data import patched_version
from qBitrr.config import (
    CONFIG,
    CONFIG_EXISTS,
    QBIT_DISABLED,
    SEARCH_ONLY,
    get_auto_update_settings,
    process_flags,
)
from qBitrr.env_config import ENVIRO_CONFIG
from qBitrr.ffprobe import FFprobeDownloader
from qBitrr.home_path import APPDATA_FOLDER
from qBitrr.logger import run_logs
from qBitrr.qbit_category_manager import qBitCategoryManager
from qBitrr.utils import ExpiringSet
from qBitrr.versioning import fetch_latest_release
from qBitrr.webui import WebUI

if CONFIG_EXISTS:
    from qBitrr.arss import ArrManager
else:
    sys.exit(0)

logger = logging.getLogger("qBitrr")
run_logs(logger, "Main")


def _mask_secret(value: str | None) -> str:
    return "[redacted]" if value else ""


def _delete_all_databases() -> None:
    """
    Delete old per-instance database files from the APPDATA_FOLDER on startup.

    Preserves the consolidated database (qbitrr.db) and Torrents.db.
    Deletes old per-instance databases and their WAL/SHM files.
    """
    db_patterns = ["*.db", "*.db-wal", "*.db-shm"]
    deleted_files = []
    # Files to preserve (consolidated database)
    preserve_files = {"qbitrr.db", "Torrents.db"}

    for pattern in db_patterns:
        for db_file in glob.glob(str(APPDATA_FOLDER.joinpath(pattern))):
            base_name = os.path.basename(db_file)
            # Preserve consolidated database and its WAL/SHM files
            should_preserve = any(base_name.startswith(f) for f in preserve_files)
            if should_preserve:
                continue

            try:
                os.remove(db_file)
                deleted_files.append(base_name)
            except Exception as e:
                logger.error("Failed to delete database file %s: %s", db_file, e)

    if deleted_files:
        logger.info("Deleted old database files on startup: %s", ", ".join(deleted_files))
    else:
        logger.debug("No old database files found to delete on startup")


class qBitManager:
    min_supported_version = VersionClass("4.3.9")
    soft_not_supported_supported_version = VersionClass("4.4.4")
    # max_supported_version = VersionClass("5.1.2")
    _head_less_mode = False

    def __init__(self):
        self._name = "Manager"
        self.shutdown_event = Event()
        self.database_restart_event = Event()  # Signal for coordinated database recovery restart
        self.qBit_Host = CONFIG.get("qBit.Host", fallback="localhost")
        self.qBit_Port = CONFIG.get("qBit.Port", fallback=8105)
        self.qBit_UserName = CONFIG.get("qBit.UserName", fallback=None)
        self.qBit_Password = CONFIG.get("qBit.Password", fallback=None)
        self.logger = logging.getLogger(f"qBitrr.{self._name}")
        run_logs(self.logger, self._name)
        self.logger.debug(
            "qBitTorrent Config: Host: %s Port: %s, Username: %s, Password: %s",
            self.qBit_Host,
            self.qBit_Port,
            self.qBit_UserName,
            _mask_secret(self.qBit_Password),
        )
        self._validated_version = False
        self.current_qbit_version = None
        # Multi-instance support
        self.clients: dict[str, qbittorrentapi.Client] = {}
        self.qbit_versions: dict[str, VersionClass] = {}
        self.instance_metadata: dict[str, dict] = {}
        self.instance_health: dict[str, bool] = {}
        # qBit category management
        self.qbit_category_configs: dict[str, dict] = {}
        self.qbit_category_managers: dict[str, qBitCategoryManager] = {}
        self.expiring_bool = ExpiringSet(max_age_seconds=10)
        self.cache = {}
        self.name_cache = {}
        self.should_delay_torrent_scan = False  # If true torrent scan is delayed by 5 minutes.
        self.child_processes: list[pathos.helpers.mp.Process] = []
        self._process_registry: dict[pathos.helpers.mp.Process, dict[str, str]] = {}
        self.auto_updater = None
        self.arr_manager = None
        self._bootstrap_ready = ThreadEvent()
        self._startup_thread: Thread | None = None
        self._restart_requested = False
        self._restart_thread: Thread | None = None
        self.ffprobe_downloader = FFprobeDownloader()
        # Process auto-restart tracking
        self._process_restart_counts: dict[tuple[str, str], list[float]] = (
            {}
        )  # (category, role) -> [timestamps]
        # Database checkpoint thread
        self._db_checkpoint_thread: Thread | None = None
        self._db_checkpoint_event = ThreadEvent()
        self._failed_spawn_attempts: dict[tuple[str, str], int] = {}  # Track failed spawn attempts
        self._pending_spawns: list[tuple] = []  # (arr_instance, meta) tuples to retry
        self.auto_restart_enabled = CONFIG.get("Settings.AutoRestartProcesses", fallback=True)
        self.max_process_restarts = CONFIG.get("Settings.MaxProcessRestarts", fallback=5)
        self.process_restart_window = CONFIG.get("Settings.ProcessRestartWindow", fallback=300)
        self.process_restart_delay = CONFIG.get("Settings.ProcessRestartDelay", fallback=5)
        # Start WebUI immediately, before any blocking network calls
        try:
            web_port = int(CONFIG.get("WebUI.Port", fallback=6969) or 6969)
        except Exception:
            web_port = 6969
        web_host = CONFIG.get("WebUI.Host", fallback="127.0.0.1") or "127.0.0.1"
        if os.environ.get("QBITRR_DOCKER_RUNNING") == "69420" and web_host in {
            "127.0.0.1",
            "localhost",
        }:
            web_host = "0.0.0.0"
        if web_host in {"0.0.0.0", "::"}:
            self.logger.warning(
                "WebUI host configured for %s; ensure exposure is intentional and protected.",
                web_host,
            )
        self.webui = WebUI(self, host=web_host, port=web_port)
        self.webui.start()

        # Finish bootstrap tasks (qBit connection, Arr manager, workers, auto-update) in background
        self._startup_thread = Thread(
            target=self._complete_startup, name="qBitrr-Startup", daemon=True
        )
        self._startup_thread.start()

    @property
    def client(self) -> qbittorrentapi.Client | None:
        """Return the first available qBit client, or None if none configured."""
        for c in self.clients.values():
            if c is not None:
                return c
        return None

    def configure_auto_update(self) -> None:
        enabled, cron = get_auto_update_settings()
        if self.auto_updater:
            self.auto_updater.stop()
            self.auto_updater = None
        if not enabled:
            self.logger.debug("Auto update is disabled")
            return
        updater = AutoUpdater(cron, self._perform_auto_update, self.logger)
        if updater.start():
            self.auto_updater = updater
        else:
            self.logger.error("Auto update could not be scheduled; leaving it disabled")

    def _perform_auto_update(self) -> None:
        """Check for updates and apply if available."""
        self.logger.notice("Checking for updates...")

        # Fetch latest release info from GitHub
        release_info = fetch_latest_release()

        if release_info.get("error"):
            self.logger.error("Auto update skipped: %s", release_info["error"])
            return

        # Use normalized version for comparison, raw tag for display
        target_version = release_info.get("normalized")
        raw_tag = release_info.get("raw_tag")

        if not release_info.get("update_available"):
            if target_version:
                self.logger.info(
                    "Auto update skipped: already running the latest release (%s).",
                    raw_tag or target_version,
                )
            else:
                self.logger.info("Auto update skipped: no new release detected.")
            return

        # Detect installation type
        from qBitrr.auto_update import get_installation_type

        install_type = get_installation_type()

        self.logger.notice(
            "Update available: %s -> %s (installation: %s)",
            patched_version,
            raw_tag or target_version,
            install_type,
        )

        # Perform the update with specific version
        updated = perform_self_update(self.logger, target_version=target_version)

        if not updated:
            if install_type == "binary":
                # Binary installations require manual update, this is expected
                self.logger.info("Manual update required for binary installation")
            else:
                self.logger.error("Auto update failed; manual intervention may be required.")
            return

        # Verify update success (git/pip only)
        if target_version and install_type != "binary":
            from qBitrr.auto_update import verify_update_success

            if verify_update_success(target_version, self.logger):
                self.logger.notice("Update verified successfully")
            else:
                self.logger.warning(
                    "Update completed but version verification failed. "
                    "The system may not be running the expected version."
                )
                # Continue with restart anyway (Phase 1 approach)

        self.logger.notice("Update applied successfully; restarting to load the new version.")
        self.request_restart()

    def request_restart(self, delay: float = 3.0) -> None:
        if self._restart_requested:
            return
        self._restart_requested = True

        def _restart():
            if delay > 0:
                time.sleep(delay)
            self.logger.notice("Restarting qBitrr...")

            # Set shutdown event to signal all loops to stop
            try:
                self.shutdown_event.set()
            except Exception:
                pass

            # Wait for child processes to exit gracefully
            for proc in list(self.child_processes):
                with contextlib.suppress(Exception):
                    proc.join(timeout=5)

            # Force kill any remaining child processes
            for proc in list(self.child_processes):
                with contextlib.suppress(Exception):
                    proc.kill()
                with contextlib.suppress(Exception):
                    proc.terminate()

            # Close database connections explicitly
            try:
                if hasattr(self, "arr_manager") and self.arr_manager:
                    for arr in self.arr_manager.managed_objects.values():
                        if hasattr(arr, "db") and arr.db:
                            with contextlib.suppress(Exception):
                                arr.db.close()
            except Exception:
                pass

            # Flush all log handlers
            try:
                for handler in logging.root.handlers[:]:
                    with contextlib.suppress(Exception):
                        handler.flush()
                        handler.close()
            except Exception:
                pass

            # Prepare restart arguments
            python = sys.executable
            args = [python] + sys.argv

            self.logger.notice("Executing restart: %s", " ".join(args))

            # Flush logs one final time before exec
            try:
                for handler in self.logger.handlers[:]:
                    with contextlib.suppress(Exception):
                        handler.flush()
            except Exception:
                pass

            # Replace current process with new instance
            # This works in Docker, native installs, and systemd
            try:
                os.execv(python, args)
            except Exception as e:
                # If execv fails, fall back to exit and hope external supervisor restarts us
                self.logger.critical("Failed to restart via execv: %s. Exiting instead.", e)
                os._exit(1)

        self._restart_thread = Thread(target=_restart, name="qBitrr-Restart", daemon=True)
        self._restart_thread.start()

    def _prepare_arr_processes(self, arr, timeout_seconds: int = 30) -> None:
        timeout = max(
            1, int(CONFIG.get("Settings.ProcessSpawnTimeoutSeconds", fallback=timeout_seconds))
        )
        result_queue: SimpleQueue = SimpleQueue()

        def _stage():
            try:
                result_queue.put((True, arr.spawn_child_processes()))
            except Exception as exc:  # pragma: no cover - defensive logging
                result_queue.put((False, exc))

        spawn_thread = Thread(
            target=_stage,
            name=f"spawn-{getattr(arr, 'category', getattr(arr, '_name', 'arr'))}",
            daemon=True,
        )
        spawn_thread.start()
        spawn_thread.join(timeout)
        if spawn_thread.is_alive():
            self.logger.error(
                "Timed out initialising worker processes for %s after %ss; skipping this instance.",
                getattr(arr, "_name", getattr(arr, "category", "unknown")),
                timeout,
            )
            return
        if result_queue.empty():
            self.logger.error(
                "No startup result returned for %s; skipping this instance.",
                getattr(arr, "_name", getattr(arr, "category", "unknown")),
            )
            return
        success, payload = result_queue.get()
        if not success:
            self.logger.exception(
                "Failed to initialise worker processes for %s",
                getattr(arr, "_name", getattr(arr, "category", "unknown")),
                exc_info=payload,
            )
            return
        worker_count, processes = payload
        if not worker_count:
            return
        for proc in processes:
            role = "search" if getattr(arr, "process_search_loop", None) is proc else "torrent"
            self._process_registry[proc] = {
                "category": getattr(arr, "category", ""),
                "name": getattr(arr, "_name", getattr(arr, "category", "")),
                "role": role or "worker",
            }
        self.logger.debug(
            "Prepared %s worker(s) for %s",
            worker_count,
            getattr(arr, "_name", getattr(arr, "category", "unknown")),
        )

    def _complete_startup(self) -> None:
        started_at = monotonic()
        try:
            # FFprobe update (deferred from __init__ to avoid blocking WebUI start)
            try:
                self.ffprobe_downloader.update()
            except Exception as e:
                self.logger.error(
                    "FFprobe manager error: %s while attempting to download/update FFprobe", e
                )
            # Initialize all qBit instances before Arr managers
            self._initialize_qbit_instances()
            arr_manager = ArrManager(self)
            self.arr_manager = arr_manager
            arr_manager.build_arr_instances()

            # Initialize qBit category managers after Arr instances (for category validation)
            self._initialize_qbit_category_managers()

            run_logs(self.logger)
            for arr in arr_manager.managed_objects.values():
                self._prepare_arr_processes(arr)

            # Spawn qBit category workers after Arr workers
            self._spawn_qbit_category_workers()

            # Start periodic database checkpoint thread
            self._start_db_checkpoint_thread()

            self.configure_auto_update()
            elapsed = monotonic() - started_at
            self.logger.info("Background startup completed in %.1fs", elapsed)
        except Exception:
            self.logger.exception(
                "Background startup encountered an error; continuing with partial functionality."
            )
        finally:
            self._bootstrap_ready.set()

    def _version_validator(self):
        validated = False
        if (
            self.min_supported_version
            <= self.current_qbit_version
            # <= self.max_supported_version
        ):
            validated = True

        if self._validated_version and validated:
            self.logger.info(
                "Current qBitTorrent version is supported: %s", self.current_qbit_version
            )
        elif not self._validated_version and validated:
            self.logger.warning(
                "Could not validate current qBitTorrent version, assuming: %s",
                self.current_qbit_version,
            )
        else:
            self.logger.critical(
                "You are currently running qBitTorrent version %s which is not supported by qBitrr.",
                # "Supported version range is %s to < %s",
                self.current_qbit_version,
                # self.min_supported_version,
                # self.max_supported_version,
            )
            sys.exit(1)

    def _initialize_qbit_instances(self) -> None:
        """
        Initialize all qBittorrent instances from config.

        Scans config for [qBit] and [qBit-XXX] sections and initializes each as
        an equal instance using the section name as the key (e.g. "qBit", "qBit-Seedbox").
        No instance is treated as "default".
        """
        if QBIT_DISABLED or SEARCH_ONLY:
            self.logger.debug("qBit disabled or search-only mode; skipping instance init")
            return

        for section in CONFIG.sections():
            if section == "qBit" or section.startswith("qBit-"):
                try:
                    self._init_instance(section, section)
                    self.logger.info("Initialized qBit instance: %s", section)
                except Exception as e:
                    self.logger.error("Failed to initialize qBit instance '%s': %s", section, e)
                    self.instance_health[section] = False

        # Set current_qbit_version from the first initialized instance (for legacy compatibility)
        if self.qbit_versions:
            self.current_qbit_version = next(iter(self.qbit_versions.values()))
            self._validated_version = True

        self.logger.info("Total qBit instances initialized: %d", len(self.clients))

    def _init_instance(self, section_name: str, instance_name: str) -> None:
        """
        Initialize a single qBittorrent instance.

        Args:
            section_name: Config section name (e.g., "qBit-Seedbox")
            instance_name: Short instance identifier (e.g., "Seedbox")

        Raises:
            Exception: If connection fails or version is unsupported
        """
        host = CONFIG.get(f"{section_name}.Host", fallback="localhost")
        port = CONFIG.get(f"{section_name}.Port", fallback=8105)
        username = CONFIG.get(f"{section_name}.UserName", fallback=None)
        password = CONFIG.get(f"{section_name}.Password", fallback=None)

        self.logger.debug(
            "Connecting to qBit instance '%s': %s:%s (user: %s)",
            instance_name,
            host,
            port,
            username,
        )

        client = qbittorrentapi.Client(
            host=host,
            port=port,
            username=username,
            password=password,
            SIMPLE_RESPONSES=False,
        )

        # Test connection and get version
        try:
            version = version_parser.parse(client.app_version())
            self.logger.debug("Instance '%s' version: %s", instance_name, version)
        except Exception as e:
            self.logger.error(
                "Could not connect to qBit instance '%s' at %s:%s: %s",
                instance_name,
                host,
                port,
                e,
            )
            raise

        # Validate version
        if version < self.min_supported_version:
            self.logger.critical(
                "Instance '%s' version %s is below minimum supported %s",
                instance_name,
                version,
                self.min_supported_version,
            )
            raise ValueError(
                f"Unsupported qBittorrent version {version} for instance {instance_name}"
            )

        # Register instance
        self.clients[instance_name] = client
        self.qbit_versions[instance_name] = version
        self.instance_metadata[instance_name] = {
            "host": host,
            "port": port,
            "username": username,
        }
        self.instance_health[instance_name] = True

        # Load qBit category management config for this instance
        managed_categories = CONFIG.get(f"{section_name}.ManagedCategories", fallback=[])
        if managed_categories:
            # Load default seeding settings
            default_seeding = {}
            seeding_keys = [
                "DownloadRateLimitPerTorrent",
                "UploadRateLimitPerTorrent",
                "MaxUploadRatio",
                "MaxSeedingTime",
                "RemoveTorrent",
            ]
            for key in seeding_keys:
                value = CONFIG.get(f"{section_name}.CategorySeeding.{key}", fallback=-1)
                default_seeding[key] = value

            # Load HnR protection settings
            hnr_keys = {
                "HitAndRunMode": "disabled",
                "MinSeedRatio": 1.0,
                "MinSeedingTimeDays": 0,
                "HitAndRunPartialSeedRatio": 1.0,
                "TrackerUpdateBuffer": 0,
            }
            for key, fallback in hnr_keys.items():
                default_seeding[key] = CONFIG.get(
                    f"{section_name}.CategorySeeding.{key}", fallback=fallback
                )

            # Load per-category overrides
            category_overrides = {}
            categories_list = CONFIG.get(f"{section_name}.CategorySeeding.Categories", fallback=[])
            for cat_config in categories_list:
                if isinstance(cat_config, dict) and "Name" in cat_config:
                    cat_name = cat_config["Name"]
                    category_overrides[cat_name] = cat_config

            # Load qBit-level shared trackers
            instance_trackers = CONFIG.get(f"{section_name}.Trackers", fallback=[])

            # Stalled handling for qBit-managed categories (same semantics as Arr)
            stalled_delay = CONFIG.get(f"{section_name}.CategorySeeding.StalledDelay", fallback=-1)
            ignore_younger = CONFIG.get(
                f"{section_name}.CategorySeeding.IgnoreTorrentsYoungerThan",
                fallback=CONFIG.get("Settings.IgnoreTorrentsYoungerThan", fallback=600),
            )

            # Store config for later initialization
            self.qbit_category_configs[instance_name] = {
                "managed_categories": managed_categories,
                "default_seeding": default_seeding,
                "category_overrides": category_overrides,
                "trackers": instance_trackers,
                "stalled_delay": stalled_delay,
                "ignore_torrents_younger_than": ignore_younger,
            }
            self.logger.debug(
                "Loaded qBit category config for '%s': %d managed categories",
                instance_name,
                len(managed_categories),
            )

    def is_instance_alive(self, instance_name: str) -> bool:
        """
        Check if a specific qBittorrent instance is alive and responding.

        Args:
            instance_name: The instance identifier (e.g. "qBit" or "qBit-Seedbox")

        Returns:
            bool: True if instance is healthy and responding, False otherwise
        """
        if instance_name not in self.clients:
            self.logger.warning("Instance '%s' not found in clients", instance_name)
            return False

        client = self.clients[instance_name]
        if client is None:
            return False

        try:
            # Quick health check - just get app version
            client.app_version()
            self.instance_health[instance_name] = True
            return True
        except Exception as e:
            self.logger.debug("Instance '%s' health check failed: %s", instance_name, e)
            self.instance_health[instance_name] = False
            return False

    def get_all_instances(self) -> list[str]:
        """
        Get list of all configured qBittorrent instance names.

        Returns:
            list[str]: List of instance identifiers (e.g., ["qBit", "qBit-Seedbox"])
        """
        return list(self.clients.keys())

    def get_healthy_instances(self) -> list[str]:
        """
        Get list of all healthy (responding) qBittorrent instances.

        Returns:
            list[str]: List of healthy instance identifiers
        """
        return [name for name in self.clients.keys() if self.is_instance_alive(name)]

    def get_instance_info(self, instance_name: str) -> dict:
        """
        Get metadata about a specific qBittorrent instance.

        Args:
            instance_name: The instance identifier (e.g. "qBit" or "qBit-Seedbox")

        Returns:
            dict: Instance metadata including host, port, version, health status
        """
        if instance_name not in self.clients:
            return {"error": f"Instance '{instance_name}' not found"}

        metadata = self.instance_metadata.get(instance_name, {})
        return {
            "name": instance_name,
            "host": metadata.get("host"),
            "port": metadata.get("port"),
            "version": str(self.qbit_versions.get(instance_name, "unknown")),
            "healthy": self.instance_health.get(instance_name, False),
        }

    def get_client(self, instance_name: str) -> qbittorrentapi.Client | None:
        """
        Get qBittorrent client for a specific instance.

        Args:
            instance_name: The instance identifier (e.g. "qBit" or "qBit-Seedbox")

        Returns:
            qbittorrentapi.Client | None: Client instance, or None if not found/unhealthy
        """
        if instance_name not in self.clients:
            self.logger.warning("Instance '%s' not found in clients", instance_name)
            return None
        return self.clients[instance_name]

    def _reload_qbit_category_configs(self) -> None:
        """Reload qBit category configs from the current CONFIG without re-creating clients."""
        if QBIT_DISABLED or SEARCH_ONLY:
            return

        seeding_keys = [
            "DownloadRateLimitPerTorrent",
            "UploadRateLimitPerTorrent",
            "MaxUploadRatio",
            "MaxSeedingTime",
            "RemoveTorrent",
        ]
        hnr_keys = {
            "HitAndRunMode": "disabled",
            "MinSeedRatio": 1.0,
            "MinSeedingTimeDays": 0,
            "HitAndRunPartialSeedRatio": 1.0,
            "TrackerUpdateBuffer": 0,
        }

        def _load_category_config(section_name: str, instance_name: str):
            managed_categories = CONFIG.get(f"{section_name}.ManagedCategories", fallback=[])
            if not managed_categories:
                return
            default_seeding = {}
            for key in seeding_keys:
                default_seeding[key] = CONFIG.get(
                    f"{section_name}.CategorySeeding.{key}", fallback=-1
                )
            for key, fallback in hnr_keys.items():
                default_seeding[key] = CONFIG.get(
                    f"{section_name}.CategorySeeding.{key}", fallback=fallback
                )
            category_overrides = {}
            for cat_config in CONFIG.get(
                f"{section_name}.CategorySeeding.Categories", fallback=[]
            ):
                if isinstance(cat_config, dict) and "Name" in cat_config:
                    category_overrides[cat_config["Name"]] = cat_config
            trackers = CONFIG.get(f"{section_name}.Trackers", fallback=[])
            stalled_delay = CONFIG.get(f"{section_name}.CategorySeeding.StalledDelay", fallback=-1)
            ignore_younger = CONFIG.get(
                f"{section_name}.CategorySeeding.IgnoreTorrentsYoungerThan",
                fallback=CONFIG.get("Settings.IgnoreTorrentsYoungerThan", fallback=600),
            )
            self.qbit_category_configs[instance_name] = {
                "managed_categories": managed_categories,
                "default_seeding": default_seeding,
                "category_overrides": category_overrides,
                "trackers": trackers,
                "stalled_delay": stalled_delay,
                "ignore_torrents_younger_than": ignore_younger,
            }

        for section in CONFIG.sections():
            if section == "qBit" or section.startswith("qBit-"):
                _load_category_config(section, section)

        self.logger.info(
            "Reloaded qBit category configs: %d instances", len(self.qbit_category_configs)
        )

    def _initialize_qbit_category_managers(self) -> None:
        """
        Initialize qBit category managers for instances with managed categories.

        Creates qBitCategoryManager instances for each qBit instance that has
        ManagedCategories configured. Managers handle seeding settings and
        removal logic for qBit-managed torrents.
        """
        if not self.qbit_category_configs:
            self.logger.debug("No qBit category managers to initialize")
            return

        for instance_name, config in self.qbit_category_configs.items():
            try:
                manager = qBitCategoryManager(instance_name, self, config)
                self.qbit_category_managers[instance_name] = manager
                self.logger.info(
                    "Initialized qBit category manager for instance '%s'", instance_name
                )
            except Exception as e:
                self.logger.error(
                    "Failed to initialize qBit category manager for '%s': %s",
                    instance_name,
                    e,
                    exc_info=True,
                )

        self.logger.info(
            "Total qBit category managers initialized: %d", len(self.qbit_category_managers)
        )

    def _spawn_qbit_category_workers(self) -> None:
        """
        Spawn worker processes for qBit category managers.

        Creates a worker process for each qBit category manager to handle
        continuous processing of managed torrents (applying seeding settings,
        checking removal conditions).
        """
        if not self.qbit_category_managers:
            self.logger.debug("No qBit category workers to spawn")
            return

        for instance_name, manager in self.qbit_category_managers.items():
            try:
                process = pathos.helpers.mp.Process(
                    target=manager.run_processing_loop,
                    name=f"qBitCategory-{instance_name}",
                )
                process.start()
                self.child_processes.append(process)
                self._process_registry[process] = {
                    "category": f"qbit-{instance_name}",
                    "role": "category_manager",
                    "instance": instance_name,
                }
                self.logger.info(
                    "Spawned qBit category worker for instance '%s' (PID: %d)",
                    instance_name,
                    process.pid,
                )
            except Exception as e:
                self.logger.error(
                    "Failed to spawn qBit category worker for '%s': %s",
                    instance_name,
                    e,
                    exc_info=True,
                )

        self.logger.info(
            "Total qBit category workers spawned: %d", len(self.qbit_category_managers)
        )

    def _periodic_db_checkpoint(self) -> None:
        """
        Background thread that periodically checkpoints the database WAL.

        This runs every 5 minutes during normal operation to ensure WAL entries
        are regularly flushed to the main database file, minimizing data loss
        risk in case of sudden crashes or power loss.
        """
        from qBitrr.database import checkpoint_database

        self.logger.info("Starting periodic database checkpoint thread (interval: 5 minutes)")

        while not self.shutdown_event.is_set():
            # Wait 5 minutes or until shutdown
            if self._db_checkpoint_event.wait(timeout=300):  # 300 seconds = 5 minutes
                break  # Shutdown requested

            if self.shutdown_event.is_set():
                break

            try:
                checkpoint_database()
            except Exception as e:
                self.logger.error("Periodic database checkpoint failed: %s", e)

        self.logger.info("Periodic database checkpoint thread stopped")

    def _start_db_checkpoint_thread(self) -> None:
        """Start the periodic database checkpoint background thread."""
        if self._db_checkpoint_thread is None or not self._db_checkpoint_thread.is_alive():
            self._db_checkpoint_thread = Thread(
                target=self._periodic_db_checkpoint,
                name="DBCheckpoint",
                daemon=True,
            )
            self._db_checkpoint_thread.start()
            self.logger.info("Started periodic database checkpoint thread")

    # @response_text(str)
    # @login_required
    def app_version(self, instance_name: str = "default", **kwargs):
        """Get qBittorrent app version for a specific instance."""
        client = self.get_client(instance_name)
        if client is None:
            return None
        return client._get(
            _name=APINames.Application,
            _method="version",
            _retries=0,
            _retry_backoff_factor=0,
            **kwargs,
        )

    def transfer_info(self, instance_name: str = "default", **kwargs):
        """
        Proxy transfer info requests to a specific qBittorrent instance.

        Args:
            instance_name: The instance identifier (default: "default")
            **kwargs: Additional arguments to pass to transfer_info

        Returns:
            dict: Transfer info or connection status
        """
        client = self.get_client(instance_name)
        if client is None:
            return {"connection_status": "disconnected"}
        return client.transfer_info(**kwargs)

    @property
    def is_alive(self) -> bool:
        """
        Check if any configured qBittorrent instance is alive.

        Uses caching via expiring_bool to avoid excessive health checks.
        """
        try:
            if not self.clients:
                return False
            if 1 in self.expiring_bool:
                return True
            for name in self.clients:
                if self.is_instance_alive(name):
                    self.expiring_bool.add(1)
                    return True
            self.logger.warning("Could not connect to any qBittorrent instance")
        except requests.RequestException:
            self.logger.warning("Could not connect to any qBittorrent instance")
        self.should_delay_torrent_scan = True
        return False

    def get_child_processes(self, timeout: float = 60.0) -> list[pathos.helpers.mp.Process]:
        if not self._bootstrap_ready.wait(timeout):
            self.logger.warning(
                "Background startup did not finish within %.1fs. Continuing with the services currently available.",
                timeout,
            )
        return list(self.child_processes)

    def run(self) -> None:
        try:
            if not self._bootstrap_ready.wait(60.0):
                self.logger.warning(
                    "Startup thread still running after 60s; managing available workers."
                )
            started_processes = []
            failed_processes = []
            for proc in list(self.child_processes):
                try:
                    # Check if process has already been started
                    if proc.is_alive() or proc.exitcode is not None:
                        meta = self._process_registry.get(proc, {})
                        self.logger.warning(
                            "Skipping start of already-started %s worker for category '%s' (alive=%s, exitcode=%s)",
                            meta.get("role", "worker"),
                            meta.get("category", "unknown"),
                            proc.is_alive(),
                            proc.exitcode,
                        )
                        continue

                    meta = self._process_registry.get(proc, {})
                    self.logger.info(
                        "Starting %s worker for category '%s'...",
                        meta.get("role", "worker"),
                        meta.get("category", "unknown"),
                    )
                    proc.start()

                    # Verify process actually started (give it a moment)
                    time.sleep(0.1)
                    if proc.is_alive():
                        self.logger.info(
                            "Successfully started %s worker for category '%s' (PID: %s)",
                            meta.get("role", "worker"),
                            meta.get("category", "unknown"),
                            proc.pid,
                        )
                        started_processes.append((meta.get("role"), meta.get("category")))
                    else:
                        self.logger.error(
                            "Process %s worker for category '%s' started but immediately died (exitcode: %s)",
                            meta.get("role", "worker"),
                            meta.get("category", "unknown"),
                            proc.exitcode,
                        )
                        failed_processes.append((meta.get("role"), meta.get("category")))
                except Exception as exc:
                    meta = self._process_registry.get(proc, {})
                    self.logger.critical(
                        "FAILED to start %s worker for category '%s': %s",
                        meta.get("role", "worker"),
                        meta.get("category", "unknown"),
                        exc,
                        exc_info=exc,
                    )
                    failed_processes.append((meta.get("role"), meta.get("category")))

            # Log summary
            if started_processes:
                self.logger.info(
                    "Started %d worker process(es): %s",
                    len(started_processes),
                    ", ".join(f"{role}({cat})" for role, cat in started_processes),
                )
            if failed_processes:
                self.logger.critical(
                    "FAILED to start %d worker process(es): %s - Will retry periodically",
                    len(failed_processes),
                    ", ".join(f"{role}({cat})" for role, cat in failed_processes),
                )
                # Track failed processes for retry
                for role, category in failed_processes:
                    key = (category, role)
                    self._failed_spawn_attempts[key] = self._failed_spawn_attempts.get(key, 0) + 1
                    # Add to retry queue if not already there
                    if hasattr(self, "arr_manager") and self.arr_manager:
                        for arr in self.arr_manager.managed_objects.values():
                            if arr.category == category:
                                # Check if already in pending spawns (avoid duplicates)
                                meta = {"category": category, "role": role, "name": arr._name}
                                already_pending = any(
                                    m.get("category") == category and m.get("role") == role
                                    for _, m in self._pending_spawns
                                )
                                if not already_pending:
                                    self._pending_spawns.append((arr, meta))
                                break
            while not self.shutdown_event.is_set():
                # Check for database restart signal
                if self.database_restart_event.is_set():
                    self.logger.critical(
                        "Database restart signal detected - terminating ALL processes for coordinated restart..."
                    )
                    # Terminate all child processes
                    for proc in list(self.child_processes):
                        if proc.is_alive():
                            self.logger.warning(
                                "Terminating %s process for database recovery",
                                self._process_registry.get(proc, {}).get("role", "worker"),
                            )
                            proc.terminate()
                    # Wait for processes to terminate
                    time.sleep(2)
                    # Force kill any that didn't terminate
                    for proc in list(self.child_processes):
                        if proc.is_alive():
                            self.logger.error(
                                "Force killing %s process",
                                self._process_registry.get(proc, {}).get("role", "worker"),
                            )
                            proc.kill()
                    # Clear all processes
                    self.child_processes.clear()
                    self._process_registry.clear()
                    # Clear the event
                    self.database_restart_event.clear()
                    # Restart all Arr instances
                    self.logger.critical("Restarting all Arr instances after database recovery...")
                    if hasattr(self, "arr_manager") and self.arr_manager:
                        for arr in self.arr_manager.managed_objects.values():
                            try:
                                worker_count, procs = arr.spawn_child_processes()
                                for proc in procs:
                                    role = (
                                        "search"
                                        if getattr(arr, "process_search_loop", None) is proc
                                        else "torrent"
                                    )
                                    self._process_registry[proc] = {
                                        "category": getattr(arr, "category", ""),
                                        "name": getattr(arr, "_name", ""),
                                        "role": role,
                                    }
                                    # CRITICAL: Actually start the process!
                                    try:
                                        proc.start()
                                        time.sleep(0.1)  # Brief pause to let process initialize
                                        if proc.is_alive():
                                            self.logger.info(
                                                "Started %s worker for %s (PID: %s)",
                                                role,
                                                arr._name,
                                                proc.pid,
                                            )
                                        else:
                                            self.logger.error(
                                                "Respawned %s worker for %s died immediately (exitcode: %s)",
                                                role,
                                                arr._name,
                                                proc.exitcode,
                                            )
                                    except Exception as start_exc:
                                        self.logger.error(
                                            "Failed to start respawned %s worker for %s: %s",
                                            role,
                                            arr._name,
                                            start_exc,
                                        )
                                self.logger.info(
                                    "Respawned %d process(es) for %s", worker_count, arr._name
                                )
                            except Exception as e:
                                self.logger.exception(
                                    "Failed to respawn processes for %s: %s", arr._name, e
                                )
                    continue

                any_alive = False
                for proc in list(self.child_processes):
                    if proc.is_alive():
                        any_alive = True
                        continue
                    exit_code = proc.exitcode
                    if exit_code is None:
                        continue

                    meta = self._process_registry.get(proc, {})
                    category = meta.get("category", "unknown")
                    role = meta.get("role", "unknown")

                    self.logger.warning(
                        "Worker process exited (role=%s, category=%s, code=%s)",
                        role,
                        category,
                        exit_code,
                    )

                    # Attempt auto-restart if enabled and process crashed (non-zero exit)
                    if self.auto_restart_enabled and exit_code != 0:
                        if self._should_restart_process(category, role):
                            self.logger.info(
                                "Attempting to restart %s worker for category '%s'",
                                role,
                                category,
                            )
                            if self._restart_process(proc, meta):
                                continue  # Keep process in list, skip removal
                            else:
                                self.logger.error(
                                    "Failed to restart %s worker for category '%s'",
                                    role,
                                    category,
                                )

                    # Remove process if not restarted
                    self._process_registry.pop(proc, None)
                    with contextlib.suppress(ValueError):
                        self.child_processes.remove(proc)

                # Retry failed process spawns
                if self._pending_spawns and self.auto_restart_enabled:
                    retry_spawns = []
                    for arr, meta in self._pending_spawns:
                        category = meta.get("category", "")
                        role = meta.get("role", "")
                        key = (category, role)
                        attempts = self._failed_spawn_attempts.get(key, 0)

                        # Exponential backoff: 30s, 60s, 120s, 240s, 480s (max 8min)
                        # Retry indefinitely but with increasing delays
                        self.logger.info(
                            "Retrying spawn of %s worker for '%s' (attempt #%d)...",
                            role,
                            category,
                            attempts + 1,
                        )

                        try:
                            worker_count, procs = arr.spawn_child_processes()
                            if worker_count > 0:
                                for proc in procs:
                                    proc_role = (
                                        "search"
                                        if getattr(arr, "process_search_loop", None) is proc
                                        else "torrent"
                                    )
                                    if proc_role == role:  # Only start the one we're retrying
                                        try:
                                            proc.start()
                                            time.sleep(0.1)
                                            if proc.is_alive():
                                                self.logger.info(
                                                    "Successfully spawned %s worker for '%s' on retry (PID: %s)",
                                                    role,
                                                    category,
                                                    proc.pid,
                                                )
                                                self._process_registry[proc] = meta
                                                # CRITICAL: Add to child_processes so it's monitored
                                                if proc not in self.child_processes:
                                                    self.child_processes.append(proc)
                                                # Clear failed attempts on success
                                                self._failed_spawn_attempts.pop(key, None)
                                            else:
                                                self.logger.error(
                                                    "Retry spawn failed: %s worker for '%s' died immediately",
                                                    role,
                                                    category,
                                                )
                                                retry_spawns.append((arr, meta))
                                                self._failed_spawn_attempts[key] = attempts + 1
                                        except Exception as exc:
                                            self.logger.error(
                                                "Retry spawn failed for %s worker '%s': %s",
                                                role,
                                                category,
                                                exc,
                                            )
                                            retry_spawns.append((arr, meta))
                                            self._failed_spawn_attempts[key] = attempts + 1
                        except Exception as exc:
                            self.logger.error(
                                "Failed to respawn processes for retry: %s",
                                exc,
                            )
                            retry_spawns.append((arr, meta))
                            self._failed_spawn_attempts[key] = attempts + 1

                    # Update pending spawns list
                    self._pending_spawns = retry_spawns

                if not self.child_processes:
                    if not any_alive:
                        break
                self.shutdown_event.wait(timeout=5)
                if not any(proc.is_alive() for proc in self.child_processes):
                    if self.child_processes:
                        continue
                    break
        except KeyboardInterrupt:
            self.logger.info("Detected Ctrl+C - Terminating process")
            sys.exit(0)
        except BaseException as e:
            self.logger.info("Detected unexpected error, shutting down: %r", e)
            sys.exit(1)
        finally:
            for proc in list(self.child_processes):
                if proc.is_alive():
                    proc.join(timeout=1)

    def _should_restart_process(self, category: str, role: str) -> bool:
        """
        Determine if a process should be restarted based on restart count and window.

        Tracks restart attempts per (category, role) combination and prevents
        crash loops by enforcing maximum restart limits within a time window.

        Args:
            category: The Arr category (e.g., "radarr", "sonarr")
            role: The process role ("search" or "torrent")

        Returns:
            bool: True if process should be restarted, False otherwise
        """
        key = (category, role)
        now = time.time()

        # Get restart history for this process type
        if key not in self._process_restart_counts:
            self._process_restart_counts[key] = []

        restart_times = self._process_restart_counts[key]

        # Remove timestamps outside the restart window
        restart_times[:] = [t for t in restart_times if now - t < self.process_restart_window]

        # Check if we've exceeded max restarts
        if len(restart_times) >= self.max_process_restarts:
            self.logger.error(
                "Process %s/%s has failed %d times in %d seconds. Auto-restart disabled for this process.",
                category,
                role,
                len(restart_times),
                self.process_restart_window,
            )
            return False

        return True

    def _restart_process(
        self, failed_proc: pathos.helpers.mp.Process, meta: dict[str, str]
    ) -> bool:
        """
        Restart a failed worker process.

        Creates a new process instance with the same target function, starts it,
        and updates all tracking structures to reference the new process.

        Args:
            failed_proc: The failed process object
            meta: Process metadata dict with keys: category, name, role

        Returns:
            bool: True if restart successful, False otherwise
        """
        category = meta.get("category", "")
        role = meta.get("role", "worker")
        meta.get("name", "")

        try:
            # Wait before restarting
            if self.process_restart_delay > 0:
                self.logger.debug(
                    "Waiting %ds before restarting %s worker for '%s'",
                    self.process_restart_delay,
                    role,
                    category,
                )
                time.sleep(self.process_restart_delay)

            # Find the corresponding Arr instance
            if not self.arr_manager:
                self.logger.error("ArrManager not available for process restart")
                return False

            arr = self.arr_manager.managed_objects.get(category)
            if not arr:
                self.logger.error("Cannot find Arr instance for category '%s'", category)
                return False

            # Recreate the process based on role
            new_proc = None
            if role == "search" and hasattr(arr, "run_search_loop"):
                new_proc = pathos.helpers.mp.Process(target=arr.run_search_loop, daemon=False)
                if hasattr(arr, "process_search_loop"):
                    arr.process_search_loop = new_proc
            elif role == "torrent" and hasattr(arr, "run_torrent_loop"):
                new_proc = pathos.helpers.mp.Process(target=arr.run_torrent_loop, daemon=False)
                if hasattr(arr, "process_torrent_loop"):
                    arr.process_torrent_loop = new_proc
            else:
                self.logger.error(
                    "Unknown role '%s' for category '%s' or target method not found",
                    role,
                    category,
                )
                return False

            if not new_proc:
                return False

            # Start the new process
            new_proc.start()

            # Update restart tracking
            key = (category, role)
            self._process_restart_counts.setdefault(key, []).append(time.time())

            # Replace in child_processes list
            with contextlib.suppress(ValueError):
                self.child_processes.remove(failed_proc)
            self.child_processes.append(new_proc)

            # Update registry
            self._process_registry.pop(failed_proc, None)
            self._process_registry[new_proc] = meta

            self.logger.notice(
                "Successfully restarted %s worker for category '%s' (restarts in window: %d/%d)",
                role,
                category,
                len(self._process_restart_counts[key]),
                self.max_process_restarts,
            )

            return True

        except Exception as e:
            self.logger.exception(
                "Failed to restart %s worker for category '%s': %s", role, category, e
            )
            return False


def _report_config_issues():
    try:
        issues = []
        # Check required settings
        from qBitrr.config import COMPLETED_DOWNLOAD_FOLDER, CONFIG, FREE_SPACE, FREE_SPACE_FOLDER

        if not COMPLETED_DOWNLOAD_FOLDER or str(COMPLETED_DOWNLOAD_FOLDER).upper() == "CHANGE_ME":
            issues.append("Settings.CompletedDownloadFolder is missing or set to CHANGE_ME")
        if FREE_SPACE != "-1":
            if not FREE_SPACE_FOLDER or str(FREE_SPACE_FOLDER).upper() == "CHANGE_ME":
                issues.append("Settings.FreeSpaceFolder must be set when FreeSpace is enabled")
        # Check Arr sections
        for key in CONFIG.sections():
            import re

            m = re.match(r"radarr.*", key, re.IGNORECASE)
            if not m:
                continue
            managed = CONFIG.get(f"{key}.Managed", fallback=False)
            if not managed:
                continue
            uri = CONFIG.get(f"{key}.URI", fallback=None)
            apikey = CONFIG.get(f"{key}.APIKey", fallback=None)
            if not uri or str(uri).upper() == "CHANGE_ME":
                issues.append(f"{key}.URI is missing or set to CHANGE_ME")
            if not apikey or str(apikey).upper() == "CHANGE_ME":
                issues.append(f"{key}.APIKey is missing or set to CHANGE_ME")
        if issues:
            logger.error("Configuration issues detected:")
            for i in issues:
                logger.error(" - %s", i)
    except Exception as e:
        logger.debug("Config validation skipped due to error: %s", e)


def run():
    early_exit = process_flags()
    if early_exit is True:
        sys.exit(0)
    logger.info("Starting qBitrr: Version: %s.", patched_version)

    # Delete all databases on startup
    _delete_all_databases()

    try:
        manager = qBitManager()
    except NameError:
        sys.exit(0)
    run_logs(logger)
    # Early consolidated config validation feedback
    _report_config_issues()
    logger.debug("Environment variables: %r", ENVIRO_CONFIG)

    # Flag to track if shutdown has been initiated
    shutdown_initiated = False

    try:
        manager.get_child_processes()

        # Register cleanup for child processes when the main process exits
        def _cleanup():
            nonlocal shutdown_initiated
            if shutdown_initiated:
                return  # Already cleaned up
            shutdown_initiated = True

            # Checkpoint database WAL before shutdown
            try:
                from qBitrr.database import checkpoint_database

                checkpoint_database()
            except Exception as e:
                logger.error("Failed to checkpoint database on shutdown: %s", e)

            # Signal loops to shutdown gracefully
            try:
                manager.shutdown_event.set()
            except Exception:
                pass
            # Give processes a chance to exit
            for p in manager.child_processes:
                with contextlib.suppress(Exception):
                    p.join(timeout=5)
            for p in manager.child_processes:
                with contextlib.suppress(Exception):
                    p.kill()
                with contextlib.suppress(Exception):
                    p.terminate()

        # Register signal handlers for graceful shutdown
        def _signal_handler(signum, frame):
            logger.info("Received signal %s - initiating graceful shutdown", signum)
            _cleanup()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        atexit.register(_cleanup)
        if manager.child_processes:
            manager.run()
        else:
            logger.warning(
                "No tasks to perform — qBit may be unreachable or no Arr instances are configured."
            )
            logger.info(
                "Configure qBitrr via the WebUI or config.toml and restart to begin managing downloads."
            )
            # Keep the process alive so the WebUI daemon thread stays up
            while not manager.shutdown_event.is_set():
                manager.shutdown_event.wait(timeout=5)
    except KeyboardInterrupt:
        logger.info("Detected Ctrl+C - Terminating process")
        _cleanup()
        sys.exit(0)
    except Exception:
        logger.info("Attempting to terminate child processes, please wait a moment.")
        _cleanup()
        for child in manager.child_processes:
            child.kill()


if __name__ == "__main__":
    freeze_support()
    run()
