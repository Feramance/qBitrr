from __future__ import annotations

import argparse
import contextlib
import pathlib
import shutil
import sys

from qBitrr.bundled_data import license_text, patched_version
from qBitrr.env_config import ENVIRO_CONFIG
from qBitrr.gen_config import MyConfig, _write_config_file, generate_doc
from qBitrr.home_path import APPDATA_FOLDER, HOME_PATH


def process_flags() -> argparse.Namespace | bool:
    parser = argparse.ArgumentParser(description="An interface to interact with qBit and *arrs.")
    parser.add_argument(
        "--gen-config",
        "-gc",
        dest="gen_config",
        help="Generate a config file in the current working directory",
        action="store_true",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"qBitrr version: {patched_version}"
    )

    parser.add_argument(
        "-l",
        "--license",
        dest="license",
        action="store_const",
        const=license_text,
        help="Show the qBitrr's licence",
    )
    parser.add_argument(
        "-s",
        "--source",
        action="store_const",
        dest="source",
        const="Source code can be found on: https://github.com/Feramance/qBitrr",
        help="Shows a link to qBitrr's source",
    )

    args = parser.parse_args()

    if args.gen_config:
        from qBitrr.gen_config import _write_config_file

        _write_config_file()
        return True
    elif args.license:
        print(args.license)
        return True
    elif args.source:
        print(args.source)
        return True
    return args


COPIED_TO_NEW_DIR = False
file = "config.toml"
CONFIG_EXISTS = True
CONFIG_FILE = HOME_PATH.joinpath(file)
CONFIG_PATH = pathlib.Path(f"./{file}")
if any(
    a in sys.argv
    for a in [
        "--gen-config",
        "-gc",
        "--version",
        "-v",
        "--license",
        "-l",
        "--source",
        "-s",
        "-h",
        "--help",
    ]
):
    CONFIG = MyConfig(CONFIG_FILE, config=generate_doc())
    COPIED_TO_NEW_DIR = None
elif (not CONFIG_FILE.exists()) and (not CONFIG_PATH.exists()):
    print(f"{file} has not been found")

    CONFIG_FILE = _write_config_file(docker=True)
    print(f"'{CONFIG_FILE.name}' has been generated")
    print('Rename it to "config.toml" then edit it and restart the container')

    CONFIG_EXISTS = False

elif CONFIG_FILE.exists():
    CONFIG = MyConfig(CONFIG_FILE)
else:
    with contextlib.suppress(
        Exception
    ):  # If file already exist or can't copy to APPDATA_FOLDER ignore the exception
        shutil.copy(CONFIG_PATH, CONFIG_FILE)
        COPIED_TO_NEW_DIR = True
    CONFIG = MyConfig("./config.toml")

if COPIED_TO_NEW_DIR is not None:
    # print(f"STARTING QBITRR | {CONFIG.path} |\n{CONFIG}")
    print("STARTING QBITRR")
else:
    print(f"STARTING QBITRR |  CONFIG_FILE={CONFIG_FILE} | CONFIG_PATH={CONFIG_PATH}")

FFPROBE_AUTO_UPDATE = (
    CONFIG.get("Settings.FFprobeAutoUpdate", fallback=True)
    if ENVIRO_CONFIG.settings.ffprobe_auto_update is None
    else ENVIRO_CONFIG.settings.ffprobe_auto_update
)
FAILED_CATEGORY = ENVIRO_CONFIG.settings.failed_category or CONFIG.get(
    "Settings.FailedCategory", fallback="failed"
)
RECHECK_CATEGORY = ENVIRO_CONFIG.settings.recheck_category or CONFIG.get(
    "Settings.RecheckCategory", fallback="recheck"
)
TAGLESS = ENVIRO_CONFIG.settings.tagless or CONFIG.get("Settings.Tagless", fallback=False)
CONSOLE_LOGGING_LEVEL_STRING = ENVIRO_CONFIG.settings.console_level or CONFIG.get(
    "Settings.ConsoleLevel", fallback="INFO"
)
ENABLE_LOGS = ENVIRO_CONFIG.settings.logging or CONFIG.get("Settings.Logging", fallback=True)
COMPLETED_DOWNLOAD_FOLDER = (
    ENVIRO_CONFIG.settings.completed_download_folder
    or CONFIG.get_or_raise("Settings.CompletedDownloadFolder")
)
FREE_SPACE = ENVIRO_CONFIG.settings.free_space or CONFIG.get("Settings.FreeSpace", fallback="-1")
FREE_SPACE_FOLDER = (
    (ENVIRO_CONFIG.settings.free_space_folder or CONFIG.get_or_raise("Settings.FreeSpaceFolder"))
    if FREE_SPACE != "-1"
    else None
)
NO_INTERNET_SLEEP_TIMER = ENVIRO_CONFIG.settings.no_internet_sleep_timer or CONFIG.get(
    "Settings.NoInternetSleepTimer", fallback=60
)
LOOP_SLEEP_TIMER = ENVIRO_CONFIG.settings.loop_sleep_timer or CONFIG.get(
    "Settings.LoopSleepTimer", fallback=5
)
SEARCH_LOOP_DELAY = ENVIRO_CONFIG.settings.search_loop_delay or CONFIG.get(
    "Settings.SearchLoopDelay", fallback=-1
)
AUTO_PAUSE_RESUME = ENVIRO_CONFIG.settings.auto_pause_resume or CONFIG.get(
    "Settings.AutoPauseResume", fallback=True
)
PING_URLS = ENVIRO_CONFIG.settings.ping_urls or CONFIG.get(
    "Settings.PingURLS", fallback=["one.one.one.one", "dns.google.com"]
)
IGNORE_TORRENTS_YOUNGER_THAN = ENVIRO_CONFIG.settings.ignore_torrents_younger_than or CONFIG.get(
    "Settings.IgnoreTorrentsYoungerThan", fallback=600
)
QBIT_DISABLED = (
    CONFIG.get("qBit.Disabled", fallback=False)
    if ENVIRO_CONFIG.qbit.disabled is None
    else ENVIRO_CONFIG.qbit.disabled
)
SEARCH_ONLY = ENVIRO_CONFIG.overrides.search_only
PROCESS_ONLY = ENVIRO_CONFIG.overrides.processing_only

if QBIT_DISABLED and PROCESS_ONLY:
    print("qBittorrent is disabled yet QBITRR_OVERRIDES_PROCESSING_ONLY is enabled")
    print(
        "Processing monitors qBitTorrents downloads "
        "therefore it depends on a health qBitTorrent connection"
    )
    print("Exiting...")
    sys.exit(1)

if SEARCH_ONLY and QBIT_DISABLED is False:
    QBIT_DISABLED = True
    print("QBITRR_OVERRIDES_SEARCH_ONLY is enabled, forcing qBitTorrent setting off")

# Settings Config Values
FF_VERSION = APPDATA_FOLDER.joinpath("ffprobe_info.json")
FF_PROBE = APPDATA_FOLDER.joinpath("ffprobe")
