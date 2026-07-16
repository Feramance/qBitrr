from __future__ import annotations

from typing import Any, TypeVar

from tomlkit import inline_table, table

from qBitrr.utils import normalize_url_base

T = TypeVar("T")

from qBitrr.gen_config.config_class import MyConfig
from qBitrr.gen_config.sections import iter_arr_sections


def _normalize_enum(value: Any, allowed: dict[str, str], default: str) -> str:
    """Normalize a config enum to one of the allowed canonical values."""
    if value is None:
        return default
    value_str = str(value).strip().lower()
    return allowed.get(value_str, default)


def _normalize_theme_value(value: Any) -> str:
    """Normalize theme value to always be 'Light' or 'Dark' (case insensitive input)."""
    return _normalize_enum(value, {"light": "Light", "dark": "Dark"}, "Dark")


def _normalize_view_density_value(value: Any) -> str:
    """Normalize view density to 'Comfortable' or 'Compact' (case insensitive input)."""
    return _normalize_enum(
        value, {"comfortable": "Comfortable", "compact": "Compact"}, "Comfortable"
    )


def _normalize_url_base_value(value: Any) -> str:
    """Normalize WebUI.UrlBase to '' or a leading-slash path without trailing slash."""
    return normalize_url_base(str(value) if value is not None else None)


def _validate_and_fill_config(config: MyConfig) -> bool:
    """
    Validate configuration and fill in missing values with defaults.
    Returns True if any changes were made, False otherwise.
    """
    changed = False
    defaults = config.defaults_config

    # Helper function to ensure a config section exists
    def ensure_section(section_name: str) -> None:
        """Ensure a config section exists."""
        if section_name not in config.config:
            config.config[section_name] = table()

    # Helper function to check and fill config values
    def ensure_value(config_section: str, key: str, default_value: Any) -> bool:
        """Ensure a config value exists, setting to default if missing."""
        ensure_section(config_section)
        section = config.config[config_section]

        if key not in section or section[key] is None:
            # Get the value from defaults if available
            default_section = defaults.get(config_section, {})
            if default_section and key in default_section:
                default = default_section[key]
            else:
                default = default_value
            section[key] = default
            return True
        return False

    # Validate Settings section
    settings_defaults = [
        ("ConfigVersion", "0.0.1"),  # Internal version, DO NOT expose to WebUI
        ("ConsoleLevel", "INFO"),
        ("Logging", True),
        ("CompletedDownloadFolder", "CHANGE_ME"),
        ("FreeSpace", "-1"),
        ("FreeSpaceFolder", "CHANGE_ME"),
        ("AutoPauseResume", True),
        ("NoInternetSleepTimer", 15),
        ("LoopSleepTimer", 5),
        ("SearchLoopDelay", -1),
        ("FailedCategory", "failed"),
        ("RecheckCategory", "recheck"),
        ("Tagless", False),
        ("IgnoreTorrentsYoungerThan", 180),
        ("PingURLS", ["one.one.one.one", "dns.google.com"]),
        ("FFprobeAutoUpdate", True),
        ("AutoUpdateEnabled", False),
        ("AutoUpdateCron", "0 3 * * 0"),
        ("AutoRestartProcesses", True),
        ("MaxProcessRestarts", 5),
        ("ProcessRestartWindow", 300),
        ("ProcessRestartDelay", 5),
    ]

    for key, default in settings_defaults:
        if ensure_value("Settings", key, default):
            changed = True

    # Validate WebUI section
    webui_defaults = [
        ("Host", "0.0.0.0"),
        ("Port", 6969),
        ("Token", ""),
        ("BehindHttpsProxy", False),
        ("UrlBase", ""),
        ("LiveArr", True),
        ("Theme", "Dark"),
        ("ViewDensity", "Comfortable"),
    ]

    for key, default in webui_defaults:
        if ensure_value("WebUI", key, default):
            changed = True

    # Normalize Theme value to always be capitalized (Light or Dark)
    ensure_section("WebUI")
    webui_section = config.config["WebUI"]
    if "Theme" in webui_section:
        current_theme = webui_section["Theme"]
        normalized_theme = _normalize_theme_value(current_theme)
        if current_theme != normalized_theme:
            webui_section["Theme"] = normalized_theme
            changed = True

    # Normalize ViewDensity value to always be capitalized (Comfortable or Compact)
    if "ViewDensity" in webui_section:
        current_density = webui_section["ViewDensity"]
        normalized_density = _normalize_view_density_value(current_density)
        if current_density != normalized_density:
            webui_section["ViewDensity"] = normalized_density
            changed = True

    if "UrlBase" in webui_section:
        current_url_base = webui_section["UrlBase"]
        normalized_url_base = _normalize_url_base_value(current_url_base)
        if current_url_base != normalized_url_base:
            webui_section["UrlBase"] = normalized_url_base
            changed = True

    # Validate qBit section
    qbit_defaults = [
        ("Disabled", False),
        ("Host", "localhost"),
        ("Port", 8105),
        ("UserName", ""),
        ("Password", ""),
    ]

    for key, default in qbit_defaults:
        if ensure_value("qBit", key, default):
            changed = True

    # Validate EntrySearch sections for all Arr instances
    entry_search_defaults = {
        "QualityProfileMappings": inline_table(),
        "ForceResetTempProfiles": False,
        "TempProfileResetTimeoutMinutes": 0,
        "ProfileSwitchRetryAttempts": 3,
    }

    for key in iter_arr_sections(config):
        # Check if this Arr instance has an EntrySearch section
        if "EntrySearch" in config.config[str(key)]:
            entry_search = config.config[str(key)]["EntrySearch"]

            # Add missing fields directly to the existing section
            for field, default in entry_search_defaults.items():
                if field not in entry_search:
                    if field == "QualityProfileMappings":
                        # Create as inline table (inline dict) not a section
                        entry_search[field] = inline_table()
                    else:
                        # Add as a simple value
                        entry_search[field] = default
                    changed = True

    # Validate HnR fields on CategorySeeding and Tracker sections
    hnr_category_defaults = {
        "HitAndRunMode": "disabled",
        "MinSeedRatio": 1.0,
        "MinSeedingTimeDays": 0,
        "HitAndRunMinimumDownloadPercent": 10,
        "HitAndRunPartialSeedRatio": 1.0,
        "TrackerUpdateBuffer": 0,
    }
    hnr_tracker_defaults = {
        "HitAndRunMode": "disabled",
        "MinSeedRatio": 1.0,
        "MinSeedingTimeDays": 0,
        "HitAndRunMinimumDownloadPercent": 10,
        "HitAndRunPartialSeedRatio": 1.0,
        "TrackerUpdateBuffer": 0,
    }

    # Fill missing HnR fields in qBit.CategorySeeding
    for key in list(config.config.keys()):
        if str(key) == "qBit" or str(key).startswith("qBit-"):
            qbit_section = config.config[str(key)]
            if "CategorySeeding" in qbit_section:
                cat_seeding = qbit_section["CategorySeeding"]
                for field, default in hnr_category_defaults.items():
                    if field not in cat_seeding:
                        cat_seeding[field] = default
                        changed = True

    # Fill missing HnR fields in all tracker entries (qBit + Arr level)
    all_sections = list(config.config.keys())
    for key in all_sections:
        section = config.config[str(key)]
        if not isinstance(section, dict):
            continue
        # qBit.Trackers
        if "Trackers" in section and isinstance(section["Trackers"], list):
            for tracker in section["Trackers"]:
                if isinstance(tracker, dict):
                    for field, default in hnr_tracker_defaults.items():
                        if field not in tracker:
                            tracker[field] = default
                            changed = True
        # Arr.Torrent.Trackers
        if "Torrent" in section and isinstance(section["Torrent"], dict):
            torrent_section = section["Torrent"]
            if "Trackers" in torrent_section and isinstance(torrent_section["Trackers"], list):
                for tracker in torrent_section["Trackers"]:
                    if isinstance(tracker, dict):
                        for field, default in hnr_tracker_defaults.items():
                            if field not in tracker:
                                tracker[field] = default
                                changed = True

    return changed
