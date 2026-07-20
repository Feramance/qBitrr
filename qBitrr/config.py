from __future__ import annotations

import argparse
import contextlib
import logging
import pathlib
import shutil
import sys

from qBitrr.bundled_data import license_text, patched_version
from qBitrr.category_paths import normalize_category
from qBitrr.env_config import ENVIRO_CONFIG
from qBitrr.gen_config import MyConfig, _write_config_file, apply_config_migrations, generate_doc
from qBitrr.home_path import APPDATA_FOLDER, HOME_PATH

CHANGE_ME_SENTINEL = "CHANGE_ME"


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
    print(f'"{CONFIG_FILE.name}" has been generated with default values.')
    print("Update the file to match your environment, then restart the container.")
    # Load generated defaults so imports (logger, PyInstaller analysis) do not NameError.
    # Do not sys.exit here: freeze tooling imports this module; runtime exit is in main.run().
    CONFIG_EXISTS = False
    CONFIG = MyConfig(CONFIG_FILE)

elif CONFIG_FILE.exists():
    CONFIG = MyConfig(CONFIG_FILE)
else:
    with contextlib.suppress(
        Exception
    ):  # If file already exist or can't copy to APPDATA_FOLDER ignore the exception
        shutil.copy(CONFIG_PATH, CONFIG_FILE)
        COPIED_TO_NEW_DIR = True
    # Load from CONFIG_FILE after copy so we use the same path regardless of cwd
    CONFIG = MyConfig(CONFIG_FILE if CONFIG_FILE.exists() else CONFIG_PATH.resolve())

if COPIED_TO_NEW_DIR is not None:
    # print(f"STARTING QBITRR | {CONFIG.path} |\n{CONFIG}")
    print("STARTING QBITRR")
else:
    print(f"STARTING QBITRR |  CONFIG_FILE={CONFIG_FILE} | CONFIG_PATH={CONFIG_PATH}")

# Apply configuration migrations and validations
if CONFIG_EXISTS:
    apply_config_migrations(CONFIG)

_CFG_LOGGER = logging.getLogger("qBitrr.config")


def _normalize_special_category(raw: object, *, settings_key: str, default: str) -> str:
    """Normalise ``Settings.FailedCategory`` / ``Settings.RecheckCategory`` like other category paths."""
    if raw is None:
        coerced = ""
    else:
        coerced = str(raw)
    if "\\" in coerced:
        _CFG_LOGGER.warning(
            "%s contains backslashes (%r); qBittorrent uses '/' for hierarchical categories.",
            settings_key,
            coerced,
        )
    normalized = normalize_category(coerced)
    return normalized or (coerced.strip() if coerced.strip() else default)


FFPROBE_AUTO_UPDATE = (
    CONFIG.get("Settings.FFprobeAutoUpdate", fallback=True)
    if ENVIRO_CONFIG.settings.ffprobe_auto_update is None
    else ENVIRO_CONFIG.settings.ffprobe_auto_update
)
FAILED_CATEGORY = _normalize_special_category(
    ENVIRO_CONFIG.settings.failed_category
    or CONFIG.get("Settings.FailedCategory", fallback="failed"),
    settings_key="Settings.FailedCategory",
    default="failed",
)
RECHECK_CATEGORY = _normalize_special_category(
    ENVIRO_CONFIG.settings.recheck_category
    or CONFIG.get("Settings.RecheckCategory", fallback="recheck"),
    settings_key="Settings.RecheckCategory",
    default="recheck",
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
NO_INTERNET_SLEEP_TIMER = ENVIRO_CONFIG.settings.no_internet_sleep_timer or CONFIG.get_duration(
    "Settings.NoInternetSleepTimer", fallback=15
)
LOOP_SLEEP_TIMER = ENVIRO_CONFIG.settings.loop_sleep_timer or CONFIG.get_duration(
    "Settings.LoopSleepTimer", fallback=5
)
# Process-start snapshots above. Long-lived loops should call get_*_effective() below
# so live config reload can update values without a full restart.
SEARCH_LOOP_DELAY = ENVIRO_CONFIG.settings.search_loop_delay or CONFIG.get_duration(
    "Settings.SearchLoopDelay", fallback=-1
)
AUTO_PAUSE_RESUME = (
    CONFIG.get("Settings.AutoPauseResume", fallback=True)
    if ENVIRO_CONFIG.settings.auto_pause_resume is None
    else ENVIRO_CONFIG.settings.auto_pause_resume
)
PING_URLS = ENVIRO_CONFIG.settings.ping_urls or CONFIG.get(
    "Settings.PingURLS", fallback=["one.one.one.one", "dns.google.com"]
)
IGNORE_TORRENTS_YOUNGER_THAN = (
    ENVIRO_CONFIG.settings.ignore_torrents_younger_than
    or CONFIG.get_duration("Settings.IgnoreTorrentsYoungerThan", fallback=180)
)


def _has_any_qbit_section() -> bool:
    return any(s == "qBit" or s.startswith("qBit-") for s in CONFIG.sections())


# qBit is enabled when any [qBit] / [qBit-*] section exists; absence means disabled.
# Per-instance Disabled is handled at init time, not via this global flag.
QBIT_DISABLED = (
    (not _has_any_qbit_section())
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

if SEARCH_ONLY and not QBIT_DISABLED:
    QBIT_DISABLED = True
    print("QBITRR_OVERRIDES_SEARCH_ONLY is enabled, forcing qBitTorrent setting off")

# Settings Config Values
FF_VERSION = APPDATA_FOLDER.joinpath("ffprobe_info.json")
FF_PROBE = APPDATA_FOLDER.joinpath("ffprobe")


def get_auto_update_settings() -> tuple[bool, str, str]:
    """Return ``(enabled, cron, channel)`` for the auto-update worker."""
    from qBitrr.versioning import DEFAULT_UPDATE_CHANNEL, normalize_update_channel

    enabled_env = ENVIRO_CONFIG.settings.auto_update_enabled
    cron_env = ENVIRO_CONFIG.settings.auto_update_cron
    channel_env = ENVIRO_CONFIG.settings.auto_update_channel
    enabled = (
        enabled_env
        if enabled_env is not None
        else CONFIG.get("Settings.AutoUpdateEnabled", fallback=False)
    )
    cron = cron_env or CONFIG.get("Settings.AutoUpdateCron", fallback="0 3 * * 0")
    cron = str(cron or "0 3 * * 0")
    channel = normalize_update_channel(
        channel_env
        if channel_env is not None
        else CONFIG.get("Settings.AutoUpdateChannel", fallback=DEFAULT_UPDATE_CHANNEL)
    )
    return bool(enabled), cron, channel


def get_auto_pause_resume_effective() -> bool:
    """Return AutoPauseResume from env override or current CONFIG (for live reload).

    Loop-read settings should use ``get_*_effective()`` helpers, not the process-start
    module constants (e.g. ``AUTO_PAUSE_RESUME``), so config saves can take effect
    without a full restart.
    """
    if ENVIRO_CONFIG.settings.auto_pause_resume is not None:
        return ENVIRO_CONFIG.settings.auto_pause_resume
    return CONFIG.get("Settings.AutoPauseResume", fallback=True)


def get_effective_qbit_disabled() -> bool:
    """Return whether qBit processing is disabled, matching startup QBIT_DISABLED semantics.

    Globally disabled when no ``[qBit]`` / ``[qBit-*]`` section exists (or via env /
    SEARCH_ONLY). Per-instance ``Disabled`` does not flip this flag.
    """
    if ENVIRO_CONFIG.qbit.disabled is not None:
        qbit_disabled = ENVIRO_CONFIG.qbit.disabled
    else:
        qbit_disabled = not _has_any_qbit_section()
    if SEARCH_ONLY and not qbit_disabled:
        return True
    return qbit_disabled


def get_free_space_guard_settings() -> tuple[str, str]:
    """Return (FreeSpace, FreeSpaceFolder) from env + current CONFIG; folder unused when FreeSpace is -1."""
    free_space = ENVIRO_CONFIG.settings.free_space or CONFIG.get(
        "Settings.FreeSpace", fallback="-1"
    )
    if free_space == "-1":
        return "-1", ""
    folder = ENVIRO_CONFIG.settings.free_space_folder or CONFIG.get_or_raise(
        "Settings.FreeSpaceFolder"
    )
    return free_space, folder


def get_ffprobe_auto_update_effective() -> bool:
    """Return FFprobeAutoUpdate from env override or current CONFIG (for live reload)."""
    if ENVIRO_CONFIG.settings.ffprobe_auto_update is not None:
        return ENVIRO_CONFIG.settings.ffprobe_auto_update
    return CONFIG.get("Settings.FFprobeAutoUpdate", fallback=True)


def get_failed_category_effective() -> str:
    """Return FailedCategory from env override or current CONFIG (for live reload)."""
    return _normalize_special_category(
        ENVIRO_CONFIG.settings.failed_category
        or CONFIG.get("Settings.FailedCategory", fallback="failed"),
        settings_key="Settings.FailedCategory",
        default="failed",
    )


def get_recheck_category_effective() -> str:
    """Return RecheckCategory from env override or current CONFIG (for live reload)."""
    return _normalize_special_category(
        ENVIRO_CONFIG.settings.recheck_category
        or CONFIG.get("Settings.RecheckCategory", fallback="recheck"),
        settings_key="Settings.RecheckCategory",
        default="recheck",
    )


def get_completed_download_folder_effective() -> str:
    """Return CompletedDownloadFolder from env override or current CONFIG (for live reload)."""
    return ENVIRO_CONFIG.settings.completed_download_folder or CONFIG.get_or_raise(
        "Settings.CompletedDownloadFolder"
    )


def get_no_internet_sleep_timer_effective() -> int:
    """Return NoInternetSleepTimer from env override or current CONFIG (for live reload)."""
    return ENVIRO_CONFIG.settings.no_internet_sleep_timer or CONFIG.get_duration(
        "Settings.NoInternetSleepTimer", fallback=15
    )


def get_loop_sleep_timer_effective() -> int:
    """Return LoopSleepTimer from env override or current CONFIG (for live reload)."""
    return ENVIRO_CONFIG.settings.loop_sleep_timer or CONFIG.get_duration(
        "Settings.LoopSleepTimer", fallback=5
    )


def get_search_loop_delay_effective() -> int:
    """Return SearchLoopDelay from env override or current CONFIG (for live reload)."""
    return ENVIRO_CONFIG.settings.search_loop_delay or CONFIG.get_duration(
        "Settings.SearchLoopDelay", fallback=-1
    )


def get_ping_urls_effective() -> list[str]:
    """Return PingURLS from env override or current CONFIG (for live reload)."""
    return ENVIRO_CONFIG.settings.ping_urls or CONFIG.get(
        "Settings.PingURLS", fallback=["one.one.one.one", "dns.google.com"]
    )


def get_ignore_torrents_younger_than_effective() -> int:
    """Return global Settings.IgnoreTorrentsYoungerThan (for PlaceHolderArr live reload)."""
    return ENVIRO_CONFIG.settings.ignore_torrents_younger_than or CONFIG.get_duration(
        "Settings.IgnoreTorrentsYoungerThan", fallback=180
    )


def sync_config_from_disk() -> None:
    """Reload ``config.toml`` into the process-local CONFIG singleton (worker live reload)."""
    try:
        CONFIG.load()
    except Exception:
        _CFG_LOGGER.debug("sync_config_from_disk failed", exc_info=True)
