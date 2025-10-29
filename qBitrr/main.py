from __future__ import annotations

import atexit
import contextlib
import logging
import sys
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
from qBitrr.logger import run_logs
from qBitrr.tables import ensure_core_tables, get_database
from qBitrr.utils import ExpiringSet
from qBitrr.webui import WebUI

if CONFIG_EXISTS:
    from qBitrr.arss import ArrManager
else:
    sys.exit(0)

logger = logging.getLogger("qBitrr")
run_logs(logger, "Main")


def _mask_secret(value: str | None) -> str:
    return "[redacted]" if value else ""


class qBitManager:
    min_supported_version = VersionClass("4.3.9")
    soft_not_supported_supported_version = VersionClass("4.4.4")
    # max_supported_version = VersionClass("5.1.2")
    _head_less_mode = False

    def __init__(self):
        self._name = "Manager"
        self.shutdown_event = Event()
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
        self.client = None
        self.current_qbit_version = None
        if not (QBIT_DISABLED or SEARCH_ONLY):
            self.client = qbittorrentapi.Client(
                host=self.qBit_Host,
                port=self.qBit_Port,
                username=self.qBit_UserName,
                password=self.qBit_Password,
                SIMPLE_RESPONSES=False,
            )
            try:
                self.current_qbit_version = version_parser.parse(self.client.app_version())
                self._validated_version = True
            except Exception as e:
                self.current_qbit_version = self.min_supported_version
                self.logger.error(
                    "Could not establish qBitTorrent version (%s). You may experience errors; please report this.",
                    e,
                )
            self._version_validator()
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
        self.ffprobe_downloader = FFprobeDownloader()
        try:
            if not (QBIT_DISABLED or SEARCH_ONLY):
                self.ffprobe_downloader.update()
        except Exception as e:
            self.logger.error(
                "FFprobe manager error: %s while attempting to download/update FFprobe", e
            )
        # Start WebUI as early as possible
        try:
            web_port = int(CONFIG.get("Settings.WebUIPort", fallback=6969) or 6969)
        except Exception:
            web_port = 6969
        web_host = CONFIG.get("Settings.WebUIHost", fallback="127.0.0.1") or "127.0.0.1"
        if web_host in {"0.0.0.0", "::"}:
            self.logger.warning(
                "WebUI host configured for %s; ensure exposure is intentional and protected.",
                web_host,
            )
        self.webui = WebUI(self, host=web_host, port=web_port)
        self.webui.start()

        # Finish bootstrap tasks (Arr manager, workers, auto-update) in the background
        self._startup_thread = Thread(
            target=self._complete_startup, name="qBitrr-Startup", daemon=True
        )
        self._startup_thread.start()

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
        self.logger.notice("Performing auto update...")
        perform_self_update(self.logger)
        self.logger.notice(
            "Auto update cycle complete. A restart may be required if files were updated."
        )

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
            arr_manager = ArrManager(self)
            self.arr_manager = arr_manager
            arr_manager.build_arr_instances()
            run_logs(self.logger)
            for arr in arr_manager.managed_objects.values():
                self._prepare_arr_processes(arr)
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

    # @response_text(str)
    # @login_required
    def app_version(self, **kwargs):
        return self.client._get(
            _name=APINames.Application,
            _method="version",
            _retries=0,
            _retry_backoff_factor=0,
            **kwargs,
        )

    def transfer_info(self, **kwargs):
        """Proxy transfer info requests to the underlying qBittorrent client."""
        if self.client is None:
            return {"connection_status": "disconnected"}
        return self.client.transfer_info(**kwargs)

    @property
    def is_alive(self) -> bool:
        try:
            if self.client is None:
                return False
            if 1 in self.expiring_bool:
                return True
            self.client.app_version()
            self.logger.trace("Successfully connected to %s:%s", self.qBit_Host, self.qBit_Port)
            self.expiring_bool.add(1)
            return True
        except requests.RequestException:
            self.logger.warning("Could not connect to %s:%s", self.qBit_Host, self.qBit_Port)
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
            for proc in list(self.child_processes):
                try:
                    proc.start()
                    meta = self._process_registry.get(proc, {})
                    self.logger.debug(
                        "Started %s worker for category '%s'",
                        meta.get("role", "worker"),
                        meta.get("category", "unknown"),
                    )
                except Exception as exc:
                    self.logger.exception(
                        "Failed to start worker process %s",
                        getattr(proc, "name", repr(proc)),
                        exc_info=exc,
                    )
            while not self.shutdown_event.is_set():
                any_alive = False
                for proc in list(self.child_processes):
                    if proc.is_alive():
                        any_alive = True
                        continue
                    exit_code = proc.exitcode
                    if exit_code is None:
                        continue
                    meta = self._process_registry.pop(proc, {})
                    with contextlib.suppress(ValueError):
                        self.child_processes.remove(proc)
                    self.logger.warning(
                        "Worker process exited (role=%s, category=%s, code=%s)",
                        meta.get("role", "unknown"),
                        meta.get("category", "unknown"),
                        exit_code,
                    )
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

            m = re.match(r"(rad|son|anim)arr.*", key, re.IGNORECASE)
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
    try:
        manager = qBitManager()
    except NameError:
        sys.exit(0)
    run_logs(logger)
    # Early consolidated config validation feedback
    _report_config_issues()
    logger.debug("Environment variables: %r", ENVIRO_CONFIG)
    try:
        manager.get_child_processes()

        # Register cleanup for child processes when the main process exits
        def _cleanup():
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

        atexit.register(_cleanup)
        if manager.child_processes:
            manager.run()
        else:
            logger.warning(
                "No tasks to perform, if this is unintended double check your config file."
            )
    except KeyboardInterrupt:
        logger.info("Detected Ctrl+C - Terminating process")
        sys.exit(0)
    except Exception:
        logger.info("Attempting to terminate child processes, please wait a moment.")
        for child in manager.child_processes:
            child.kill()


def initialize_database() -> None:
    try:
        get_database()
        ensure_core_tables()
    except Exception:
        logger.exception("Failed to initialize database schema")
        raise


if __name__ == "__main__":
    freeze_support()
    initialize_database()
    run()
