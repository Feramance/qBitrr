from __future__ import annotations

import atexit
import contextlib
import itertools
import logging
import sys
from multiprocessing import Event, Manager, freeze_support

import pathos
import qbittorrentapi
import requests
from packaging import version as version_parser
from packaging.version import Version as VersionClass
from qbittorrentapi import APINames

from qBitrr.auto_update import AutoUpdater, perform_self_update
from qBitrr.bundled_data import patched_version
from qBitrr.config import (
    APPDATA_FOLDER,
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
from qBitrr.utils import ExpiringSet, absolute_file_paths
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
        self.child_processes = []
        self.auto_updater = None
        self._ipc_manager = Manager()
        atexit.register(self._ipc_manager.shutdown)
        self.shared_search_activity = self._ipc_manager.dict()
        self.shared_search_queue = self._ipc_manager.Queue()
        self.ffprobe_downloader = FFprobeDownloader()
        try:
            if not (QBIT_DISABLED or SEARCH_ONLY):
                self.ffprobe_downloader.update()
        except Exception as e:
            self.logger.error(
                "FFprobe manager error: %s while attempting to download/update FFprobe", e
            )
        self.arr_manager = ArrManager(
            self,
            search_activity_store=self.shared_search_activity,
            search_queue=self.shared_search_queue,
        ).build_arr_instances()
        run_logs(self.logger)
        # Start WebUI
        try:
            web_port = int(CONFIG.get("Settings.WebUIPort", fallback=6969) or 6969)
        except Exception:
            web_port = 6969
        web_host = CONFIG.get("Settings.WebUIHost", fallback="0.0.0.0") or "0.0.0.0"
        self.webui = WebUI(self, host=web_host, port=web_port)
        self.webui.start()
        self.configure_auto_update()

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

    def get_child_processes(self) -> list[pathos.helpers.mp.Process]:
        run_logs(self.logger)
        self.logger.debug("Managing %s categories", len(self.arr_manager.managed_objects))
        count = 0
        for arr in self.arr_manager.managed_objects.values():
            numb, processes = arr.spawn_child_processes()
            count += numb
        return self.child_processes

    def run(self):
        try:
            self.logger.debug("Starting %s child processes", len(self.child_processes))
            [p.start() for p in self.child_processes]
            [p.join() for p in self.child_processes]
        except KeyboardInterrupt:
            self.logger.info("Detected Ctrl+C - Terminating process")
            sys.exit(0)
        except BaseException as e:
            self.logger.info("Detected Ctrl+C - Terminating process: %r", e)
            sys.exit(1)


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


def file_cleanup():
    extensions = [".db", ".db-shm", ".db-wal"]
    all_files_in_folder = list(absolute_file_paths(APPDATA_FOLDER))
    for file, ext in itertools.product(all_files_in_folder, extensions):
        if file.name.endswith(ext):
            file.unlink(missing_ok=True)


if __name__ == "__main__":
    freeze_support()
    file_cleanup()
    run()
