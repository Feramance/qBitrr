from __future__ import annotations

import contextlib
import pathlib
import shutil
import sys

import logbook

from qBitrr.gen_config import MyConfig

APPDATA_FOLDER = pathlib.Path().home().joinpath(".config", "qBitManager")
APPDATA_FOLDER.mkdir(parents=True, exist_ok=True)
COPIED_TO_NEW_DIR = False
CONFIG: MyConfig | None = None
CONFIG_FILE = None
FFPROBE_AUTO_UPDATE = True
FAILED_CATEGORY = "failed"
RECHECK_CATEGORY = "recheck"
CONSOLE_LOGGING_LEVEL_STRING = "NOTICE"
COMPLETED_DOWNLOAD_FOLDER = None
NO_INTERNET_SLEEP_TIMER = 60
LOOP_SLEEP_TIMER = 5
PING_URLS = ["one.one.one.one"]
IGNORE_TORRENTS_YOUNGER_THAN = 600


def update_config(file: str | None = None):
    global CONFIG, CONFIG_FILE, COPIED_TO_NEW_DIR, FFPROBE_AUTO_UPDATE, FAILED_CATEGORY, RECHECK_CATEGORY, CONSOLE_LOGGING_LEVEL_STRING, COMPLETED_DOWNLOAD_FOLDER, NO_INTERNET_SLEEP_TIMER, LOOP_SLEEP_TIMER, PING_URLS, IGNORE_TORRENTS_YOUNGER_THAN

    if file is None:
        file = "config.toml"
        CONFIG_FILE = APPDATA_FOLDER.joinpath(file)
        if (
            not (CONFIG_PATH := APPDATA_FOLDER.joinpath(file)).exists()
            and not pathlib.Path(f"./{file}").exists()
        ):
            logbook.critical("config.ini has not been found - exiting...")
            sys.exit(1)

        if CONFIG_PATH.exists():
            CONFIG = MyConfig(str(CONFIG_FILE))
        else:
            with contextlib.suppress(
                Exception
            ):  # If file already exist or can't copy to APPDATA_FOLDER ignore the exception
                CONFIG_FILE = pathlib.Path(f"./{file}")
                shutil.copy(CONFIG_FILE, CONFIG_PATH)
                COPIED_TO_NEW_DIR = True
            CONFIG = MyConfig("./config.toml")
    else:
        CONFIG_FILE = pathlib.Path(file)
        COPIED_TO_NEW_DIR = None
        if not (CONFIG_PATH := CONFIG_FILE).exists():
            logbook.critical(f"{CONFIG_PATH} has not been found - exiting...")
            sys.exit(1)
        else:
            CONFIG = MyConfig(str(CONFIG_PATH))

    FFPROBE_AUTO_UPDATE = CONFIG.get_section("Settings").get("FFprobeAutoUpdate", fallback=True)
    FAILED_CATEGORY = CONFIG.get_section("Settings").get("FailedCategory", fallback="failed")
    RECHECK_CATEGORY = CONFIG.get_section("Settings").get("RecheckCategory", fallback="recheck")
    CONSOLE_LOGGING_LEVEL_STRING = CONFIG.get_section("Settings").get(
        "ConsoleLevel", fallback="NOTICE"
    )
    COMPLETED_DOWNLOAD_FOLDER = CONFIG.get_section("Settings").get("CompletedDownloadFolder")
    NO_INTERNET_SLEEP_TIMER = CONFIG.get_section("Settings").get(
        "NoInternetSleepTimer", fallback=60
    )
    LOOP_SLEEP_TIMER = CONFIG.get_section("Settings").get("LoopSleepTimer", fallback=5)
    PING_URLS = CONFIG.get_section("Settings").get(
        "PingURLS", fallback=["one.one.one.one", "dns.google"]
    )
    IGNORE_TORRENTS_YOUNGER_THAN = CONFIG.get_section("Settings").get(
        "IgnoreTorrentsYoungerThan", fallback=600
    )

    from qBitrr.logger import _update_logger_level

    _update_logger_level()


# Settings Config Values
FF_VERSION = APPDATA_FOLDER.joinpath("ffprobe_info.json")
FF_PROBE = APPDATA_FOLDER.joinpath("ffprobe")
