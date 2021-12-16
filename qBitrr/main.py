from __future__ import annotations

import argparse
from typing import NoReturn

import logbook
import qbittorrentapi
import requests
from qbittorrentapi import APINames, login_required, response_text

from qBitrr.arss import ArrManager
from qBitrr.config import CONFIG, update_config
from qBitrr.ffprobe import FFmpegDownloader

logger = logbook.Logger("qBitManager")


class qBitManager:
    def __init__(self):
        self.qBit_Host = CONFIG.get("QBit.Host", fallback="localhost")
        self.qBit_Port = CONFIG.get("QBit.Port", fallback=8105)
        self.qBit_UserName = CONFIG.get("QBit.UserName", fallback=None)
        self.qBit_Password = CONFIG.get("QBit.Password", fallback=None)
        logger.debug(
            "QBitTorrent Config: Host: {qBit_Host}, Port: {qBit_Port}, Username: {qBit_UserName}, "
            "Password: {qBit_Password}",
            qBit_Host=self.qBit_Host,
            qBit_Port=self.qBit_Port,
            qBit_UserName=self.qBit_UserName,
            qBit_Password=self.qBit_Password,
        )
        self.client = qbittorrentapi.Client(
            host=self.qBit_Host,
            port=self.qBit_Port,
            username=self.qBit_UserName,
            password=self.qBit_Password,
            SIMPLE_RESPONSES=False,
        )
        self.logger = logger
        self.cache = dict()
        self.name_cache = dict()
        self.should_delay_torrent_scan = False  # If true torrent scan is delayed by 5 minutes.
        self.child_processes = []
        self.ffprobe_downloader = FFmpegDownloader()
        try:
            self.ffprobe_downloader.update()
        except Exception as e:
            self.logger.error(
                "FFprobe manager error: {e} while attempting to download/update FFprobe", e=e
            )
        self.arr_manager = ArrManager(self).build_arr_instances()

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
                "Successfully connected to {url}:{port}", url=self.qBit_Host, port=self.qBit_Port
            )
            return True
        except requests.RequestException:

            self.logger.warning(
                "Could not connect to {url}:{port}", url=self.qBit_Host, port=self.qBit_Port
            )
        self.should_delay_torrent_scan = True
        return False

    def run(self) -> NoReturn:
        for arr in self.arr_manager.managed_objects.values():
            arr.spawn_child_processes()

        for p in self.child_processes:
            p.join()


def process_flags() -> bool | None:
    parser = argparse.ArgumentParser(description="An interface to interact with qBit and *arrs.")
    parser.add_argument(
        "--config",
        "-c",
        dest="config",
        help="Specify a config file to be used.",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--gen-config",
        "-gc",
        dest="gen_config",
        help="Generate a config file in the current working directory.",
        action="store_true",
    )
    args = parser.parse_args()

    if args.gen_config:
        from qBitrr.gen_config import _write_config_file

        _write_config_file()
        return True

    update_config(args.config)

    return


def run():
    early_exist = process_flags()
    if early_exist:
        return

    manager = qBitManager()
    try:
        manager.run()
    finally:
        logger.notice("Terminating child processed, please wait a moment.")
        for child in manager.child_processes:
            child.terminate()


if __name__ == "__main__":
    run()
