from typing import NoReturn

import logbook
import qbittorrentapi
import requests
from qbittorrentapi import APINames, login_required, response_text

from .arss import ArrManager
from .config import CONFIG
from .logger import *

logger = logbook.Logger("qBitManager")

# QBitTorrent Config Values
qBit_Host = CONFIG.get("QBit", "Host", fallback="localhost")
qBit_Port = CONFIG.getint("QBit", "Port")
qBit_UserName = CONFIG.get("QBit", "UserName")
qBit_Password = CONFIG.get("QBit", "Password", fallback=None)
logger.debug(
    "QBitTorrent Config: Host: {qBit_Host}, Port: {qBit_Port}, Username: {qBit_UserName}, "
    "Password: {qBit_Password}",
    qBit_Host=qBit_Host,
    qBit_Port=qBit_Port,
    qBit_UserName=qBit_UserName,
    qBit_Password=qBit_Password,
)


class qBitManager:
    def __init__(self):
        self.client = qbittorrentapi.Client(
            host=qBit_Host,
            port=qBit_Port,
            username=qBit_UserName,
            password=qBit_Password,
            SIMPLE_RESPONSES=False,
        )
        self.arr_manager = ArrManager(self).build_arr_instances()
        self.logger = logger
        self.cache = dict()
        self.name_cache = dict()
        self.should_delay_torrent_scan = False  # If true torrent scan is delayed by 5 minutes.
        self.child_processes = []

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
            self.client.app_version()
            self.logger.trace(
                "Successfully connected to {url}:{port}", url=qBit_Host, port=qBit_Port
            )
            return True
        except requests.RequestException:

            self.logger.warning("Could not connect to {url}:{port}", url=qBit_Host, port=qBit_Port)
        self.should_delay_torrent_scan = True
        return False

    def run(self) -> NoReturn:
        for arr in self.arr_manager.managed_objects.values():
            arr.spawn_child_processes()

        for p in self.child_processes:
            p.join()


def run():
    manager = qBitManager()
    try:
        manager.run()
    finally:
        logger.notice("Terminating child processed, please wait a moment.")
        for child in manager.child_processes:
            child.terminate()


if __name__ == "__main__":
    run()
