from __future__ import annotations

import atexit
import logging
import sys
from multiprocessing import freeze_support

import pathos
import qbittorrentapi
import requests
from qbittorrentapi import APINames, login_required, response_text

from qBitrr.arss import ArrManager
from qBitrr.config import CONFIG, process_flags
from qBitrr.ffprobe import FFprobeDownloader
from qBitrr.logger import run_logs
from qBitrr.utils import ExpiringSet

CHILD_PROCESSES = []

logger = logging.getLogger("qBitrr")
run_logs(logger)


class qBitManager:
    def __init__(self):
        self.qBit_Host = CONFIG.get("QBit.Host", fallback="localhost")
        self.qBit_Port = CONFIG.get("QBit.Port", fallback=8105)
        self.qBit_UserName = CONFIG.get("QBit.UserName", fallback=None)
        self.qBit_Password = CONFIG.get("QBit.Password", fallback=None)
        self.logger = logging.getLogger(
            "qBitrr.Manager",
        )
        run_logs(self.logger)
        self.logger.debug(
            "QBitTorrent Config: Host: %s Port: %s, Username: %s, Password: %s",
            self.qBit_Host,
            self.qBit_Port,
            self.qBit_UserName,
            self.qBit_Password,
        )
        self.client = qbittorrentapi.Client(
            host=self.qBit_Host,
            port=self.qBit_Port,
            username=self.qBit_UserName,
            password=self.qBit_Password,
            SIMPLE_RESPONSES=False,
        )
        self.expiring_bool = ExpiringSet(max_age_seconds=10)
        self.cache = dict()
        self.name_cache = dict()
        self.should_delay_torrent_scan = False  # If true torrent scan is delayed by 5 minutes.
        self.child_processes = []
        self.ffprobe_downloader = FFprobeDownloader()
        try:
            self.ffprobe_downloader.update()
        except Exception as e:
            self.logger.error(
                "FFprobe manager error: %s while attempting to download/update FFprobe", e
            )
        self.arr_manager = ArrManager(self).build_arr_instances()
        run_logs(self.logger)

    @response_text(str)
    @login_required
    def app_version(self, **kwargs):
        return self.client._get(
            _name=APINames.Application,
            _method="version",
            _retries=0,
            _retry_backoff_factor=0,
            **kwargs,
        )

    @property
    def is_alive(self) -> bool:
        try:
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
        self.logger.hnotice("Managing %s categories", len(self.arr_manager.managed_objects))
        count = 0
        procs = []
        for arr in self.arr_manager.managed_objects.values():
            numb, processes = arr.spawn_child_processes()
            count += numb
            procs.extend(processes)
        return procs

    def run(self):
        try:
            self.logger.notice("Starting %s child processes", len(self.child_processes))
            [p.start() for p in self.child_processes]
            [p.join() for p in self.child_processes]
        except KeyboardInterrupt:
            self.logger.hnotice("Detected Ctrl+C - Terminating process")
            sys.exit(0)
        except BaseException as e:
            self.logger.hnotice("Detected Ctrl+C - Terminating process: %r", e)
            sys.exit(1)


def run():
    global CHILD_PROCESSES
    early_exit = process_flags()
    if early_exit.gen_config:
        return
    logger.notice("Starting qBitrr.")
    manager = qBitManager()
    run_logs(logger)
    try:
        CHILD_PROCESSES = manager.get_child_processes()
        manager.run()
    except KeyboardInterrupt:
        logger.hnotice("Detected Ctrl+C - Terminating process")
        sys.exit(0)
    except Exception:
        logger.notice("Attempting to terminate child processes, please wait a moment.")
        for child in manager.child_processes:
            child.kill()


def cleanup():
    for p in CHILD_PROCESSES:
        p.kill()
        p.terminate()


atexit.register(cleanup)


if __name__ == "__main__":
    freeze_support()
    run()
