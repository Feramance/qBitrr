from __future__ import annotations

from typing import Any

from tomlkit import comment, document, nl, table
from tomlkit.items import Table
from tomlkit.toml_document import TOMLDocument

from qBitrr.env_config import ENVIRO_CONFIG
from qBitrr.gen_config.fields import (
    QBIT_FIELDS,
    SETTINGS_FIELDS,
    WEBUI_FIELDS,
    apply_fields,
    filter_arr_fields,
)
from qBitrr.gen_config.fields_arr import ARR_FIELDS
from qBitrr.home_path import HOME_PATH

ARR_SECTION_PREFIXES = ("Radarr", "Sonarr", "Lidarr", "Animarr")


def iter_arr_sections(config: Any):
    """Yield config section names for Radarr/Sonarr/Lidarr/Animarr instances."""
    keys = config.sections() if hasattr(config, "sections") else config.config.keys()
    for section in keys:
        name = str(section)
        if name.startswith(ARR_SECTION_PREFIXES):
            yield name


def _default(value, fallback):
    """Return value if not None, otherwise fallback. Unlike ``or``, preserves falsy values like False and 0."""
    return value if value is not None else fallback


def _fields_with_overrides(fields, overrides: dict[str, Any]):
    """Return registry fields with per-dotted-path default and/or comment overrides."""
    from dataclasses import replace

    out = []
    for cfg in fields:
        override = overrides.get(cfg.dotted)
        if override is None:
            out.append(cfg)
            continue
        if isinstance(override, dict):
            kwargs = {}
            if "default" in override:
                kwargs["default"] = override["default"]
            if "comments" in override:
                kwargs["comments"] = override["comments"]
            out.append(replace(cfg, **kwargs) if kwargs else cfg)
        else:
            out.append(replace(cfg, default=override))
    return out


def _add_web_settings_section(config: TOMLDocument):
    web_settings = table()
    apply_fields(web_settings, WEBUI_FIELDS)
    config.add("WebUI", web_settings)


def generate_doc() -> TOMLDocument:
    config = document()
    config.add(
        comment(
            "This is a config file for the qBitrr Script - "
            'Make sure to change all entries of "CHANGE_ME".'
        )
    )
    config.add(comment('This is a config file should be moved to "' f'{HOME_PATH}".'))
    config.add(nl())
    _add_settings_section(config)
    _add_web_settings_section(config)
    _add_qbit_section(config)
    _add_category_sections(config)
    return config


def _add_settings_section(config: TOMLDocument):
    settings = table()
    overrides = {
        "ConsoleLevel": _default(ENVIRO_CONFIG.settings.console_level, "INFO"),
        "Logging": _default(ENVIRO_CONFIG.settings.logging, True),
        "CompletedDownloadFolder": _default(
            ENVIRO_CONFIG.settings.completed_download_folder, "CHANGE_ME"
        ),
        "FreeSpace": _default(ENVIRO_CONFIG.settings.free_space, "-1"),
        "FreeSpaceFolder": _default(ENVIRO_CONFIG.settings.free_space_folder, "CHANGE_ME"),
        "AutoPauseResume": _default(ENVIRO_CONFIG.settings.auto_pause_resume, True),
        "NoInternetSleepTimer": _default(ENVIRO_CONFIG.settings.no_internet_sleep_timer, 15),
        "LoopSleepTimer": _default(ENVIRO_CONFIG.settings.loop_sleep_timer, 5),
        "SearchLoopDelay": _default(ENVIRO_CONFIG.settings.search_loop_delay, -1),
        "FailedCategory": _default(ENVIRO_CONFIG.settings.failed_category, "failed"),
        "RecheckCategory": _default(ENVIRO_CONFIG.settings.recheck_category, "recheck"),
        "Tagless": _default(ENVIRO_CONFIG.settings.tagless, False),
        "IgnoreTorrentsYoungerThan": _default(
            ENVIRO_CONFIG.settings.ignore_torrents_younger_than, 180
        ),
        "PingURLS": _default(
            ENVIRO_CONFIG.settings.ping_urls, ["one.one.one.one", "dns.google.com"]
        ),
        "FFprobeAutoUpdate": (
            True
            if ENVIRO_CONFIG.settings.ffprobe_auto_update is None
            else ENVIRO_CONFIG.settings.ffprobe_auto_update
        ),
        "AutoUpdateEnabled": (
            ENVIRO_CONFIG.settings.auto_update_enabled
            if ENVIRO_CONFIG.settings.auto_update_enabled is not None
            else False
        ),
        "AutoUpdateCron": _default(ENVIRO_CONFIG.settings.auto_update_cron, "0 3 * * 0"),
    }
    apply_fields(settings, _fields_with_overrides(SETTINGS_FIELDS, overrides))
    config.add("Settings", settings)


def _add_qbit_section(config: TOMLDocument):
    qbit = table()
    overrides = {
        "Disabled": (
            False if ENVIRO_CONFIG.qbit.disabled is None else ENVIRO_CONFIG.qbit.disabled
        ),
        "Host": _default(ENVIRO_CONFIG.qbit.host, "CHANGE_ME"),
        "Port": _default(ENVIRO_CONFIG.qbit.port, 8080),
        "UserName": _default(ENVIRO_CONFIG.qbit.username, "CHANGE_ME"),
        "Password": _default(ENVIRO_CONFIG.qbit.password, "CHANGE_ME"),
    }
    apply_fields(qbit, _fields_with_overrides(QBIT_FIELDS, overrides))
    _gen_qbit_tracker_tables(qbit)
    config.add("qBit", qbit)


def _gen_qbit_tracker_tables(qbit_table: Table):
    """Generate shared tracker config for the qBit instance level."""
    qbit_table.add(
        comment("Shared tracker configs inherited by all Arr instances on this qBit instance.")
    )
    qbit_table.add(
        comment("Define tracker-specific rate limits, HnR protection, and management rules here.")
    )
    qbit_table.add(
        comment(
            "Arr instances can optionally override per-tracker settings in their own Trackers section."
        )
    )

    tracker_table_list = []
    qbit_table.add("Trackers", tracker_table_list)


def _add_category_sections(config: TOMLDocument):
    for c in ["Sonarr-TV", "Sonarr-Anime", "Radarr-1080", "Radarr-4K", "Lidarr-Music"]:
        _gen_default_cat(c, config)


def _arr_blocklist_messages(category: str) -> list[str]:
    """Default ArrErrorCodesToBlocklist messages for a category (stable order)."""
    lower = category.lower()
    if "radarr" in lower:
        return [
            "Not a preferred word upgrade for existing movie file(s)",
            "Not an upgrade for existing movie file(s)",
            "Unable to determine if file is a sample",
        ]
    if "sonarr" in lower:
        return [
            "Not a preferred word upgrade for existing episode file(s)",
            "Not an upgrade for existing episode file(s)",
            "Unable to determine if file is a sample",
        ]
    if "lidarr" in lower:
        return [
            "Not a preferred word upgrade for existing track file(s)",
            "Not an upgrade for existing track file(s)",
            "Unable to determine if file is a sample",
        ]
    return []


def _arr_folder_exclusions(category: str) -> list[str]:
    lower = category.lower()
    if "anime" in lower:
        return [
            r"\bextras?\b",
            r"\bfeaturettes?\b",
            r"\bsamples?\b",
            r"\bscreens?\b",
            r"\bspecials?\b",
            r"\bova\b",
            r"\bnc(ed|op)?(\\d+)?\b",
        ]
    if "lidarr" in lower:
        return [
            r"\bextras?\b",
            r"\bsamples?\b",
            r"\bscreens?\b",
        ]
    return [
        r"\bextras?\b",
        r"\bfeaturettes?\b",
        r"\bsamples?\b",
        r"\bscreens?\b",
        r"\bnc(ed|op)?(\\d+)?\b",
    ]


def _arr_filename_exclusions(category: str) -> list[str]:
    if "lidarr" in category.lower():
        return [
            r"\bsample\b",
            r"brarbg.com\b",
            r"\btrailer\b",
            r"comandotorrents.com",
        ]
    return [
        r"\bncop\\d+?\b",
        r"\bnced\\d+?\b",
        r"\bsample\b",
        r"brarbg.com\b",
        r"\btrailer\b",
        r"music video",
        r"comandotorrents.com",
    ]


def _arr_file_extensions(category: str) -> list[str]:
    if "lidarr" in category.lower():
        return [
            ".mp3",
            ".flac",
            ".m4a",
            ".aac",
            ".ogg",
            ".opus",
            ".wav",
            ".ape",
            ".wma",
            ".!qB",
            ".parts",
        ]
    return [".mp4", ".mkv", ".sub", ".ass", ".srt", ".!qB", ".parts"]


def _arr_category_overrides(category: str) -> dict[str, Any]:
    """Category-specific defaults/comments layered on :data:`ARR_FIELDS`."""
    lower = category.lower()
    overrides: dict[str, Any] = {
        "Category": category.lower(),
        "ArrErrorCodesToBlocklist": _arr_blocklist_messages(category),
        "Torrent.FolderExclusionRegex": _arr_folder_exclusions(category),
        "Torrent.FileNameExclusionRegex": _arr_filename_exclusions(category),
        "Torrent.FileExtensionAllowlist": _arr_file_extensions(category),
        "EntrySearch.Overseerr.Is4K": "radarr-4k" in lower,
    }
    if "sonarr" in lower:
        overrides["EntrySearch.Unmonitored"] = {
            "default": False,
            "comments": "Should search for unmonitored episodes/series?",
        }
        overrides["EntrySearch.SearchLimit"] = {
            "default": 5,
            "comments": (
                "Maximum allowed Searches at any one points (I wouldn't recommend settings this too high)",
                "Sonarr has a hardcoded cap of 3 simultaneous tasks",
            ),
        }
        overrides["EntrySearch.SearchByYear"] = {
            "default": True,
            "comments": "It will order searches by the year the episode was first aired",
        }
    elif "radarr" in lower:
        overrides["EntrySearch.Unmonitored"] = {
            "default": False,
            "comments": "Should search for unmonitored movies?",
        }
        overrides["EntrySearch.SearchLimit"] = {
            "default": 5,
            "comments": (
                "Radarr has a default of 3 simultaneous tasks, which can be increased up to 10 tasks",
                'If you set the environment variable of "THREAD_LIMIT" to a number between and including 2-10',
                "Radarr devs have stated that this is an unsupported feature so you will not get any support for doing so from them.",
                "That being said I've been daily driving 10 simultaneous tasks for quite a while now with no issues.",
            ),
        }
        overrides["EntrySearch.SearchByYear"] = {
            "default": True,
            "comments": "It will order searches by the year the movie was released",
        }
    return overrides


def _gen_default_cat(category: str, config: TOMLDocument):
    """Emit one Arr category section from :data:`ARR_FIELDS` + category overrides."""
    cat_default = table()
    cat_default.add(nl())
    fields = filter_arr_fields(ARR_FIELDS, category)
    overrides = _arr_category_overrides(category)
    # Match historical key order: torrent leaves → Trackers → SeedingMode.
    non_seeding = [
        f
        for f in fields
        if not (len(f.path) >= 2 and f.path[0] == "Torrent" and f.path[1] == "SeedingMode")
    ]
    seeding = [
        f
        for f in fields
        if len(f.path) >= 2 and f.path[0] == "Torrent" and f.path[1] == "SeedingMode"
    ]
    apply_fields(cat_default, _fields_with_overrides(non_seeding, overrides))
    _gen_default_tracker_tables(category, cat_default["Torrent"])
    apply_fields(cat_default, _fields_with_overrides(seeding, overrides))
    config.add(category, cat_default)


def _gen_default_tracker_tables(category: str, torrent_table: Table):
    """Append empty Trackers list (AoT schema lives in FE overlays / allowlist)."""
    del category  # reserved for future per-Arr tracker templates
    torrent_table.add(
        comment(
            "Optional per-Arr tracker overrides. Trackers are inherited from qBit.Trackers by default."
        )
    )
    torrent_table.add(
        comment(
            "Add entries here only if this Arr instance needs different settings for a tracker (matched by URI)."
        )
    )
    torrent_table.add("Trackers", [])
