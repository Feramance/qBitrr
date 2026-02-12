from __future__ import annotations

import pathlib
from functools import reduce
from typing import Any, TypeVar

from tomlkit import comment, document, inline_table, nl, parse, table
from tomlkit.items import Table
from tomlkit.toml_document import TOMLDocument

from qBitrr.env_config import ENVIRO_CONFIG
from qBitrr.home_path import APPDATA_FOLDER, HOME_PATH

T = TypeVar("T")


def _add_web_settings_section(config: TOMLDocument):
    web_settings = table()
    _gen_default_line(
        web_settings,
        "WebUI listen host (default 0.0.0.0)",
        "Host",
        "0.0.0.0",
    )
    _gen_default_line(
        web_settings,
        "WebUI listen port (default 6969)",
        "Port",
        6969,
    )
    _gen_default_line(
        web_settings,
        [
            "Optional bearer token to secure WebUI/API.",
            "Set a non-empty value to require Authorization: Bearer <token>.",
        ],
        "Token",
        "",
    )
    _gen_default_line(
        web_settings,
        "Enable live updates for Arr views",
        "LiveArr",
        True,
    )
    _gen_default_line(
        web_settings,
        "Group Sonarr episodes by series in views",
        "GroupSonarr",
        True,
    )
    _gen_default_line(
        web_settings,
        "Group Lidarr albums by artist in views",
        "GroupLidarr",
        True,
    )
    _gen_default_line(
        web_settings,
        "WebUI theme (Light or Dark)",
        "Theme",
        "Dark",
    )
    _gen_default_line(
        web_settings,
        "WebUI view density (Comfortable or Compact)",
        "ViewDensity",
        "Comfortable",
    )
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
    _gen_default_line(
        settings,
        [
            "Internal config schema version - DO NOT MODIFY",
            "This is managed automatically by qBitrr for config migrations",
        ],
        "ConfigVersion",
        "5.8.8",
    )
    _gen_default_line(
        settings,
        "Level of logging; One of CRITICAL, ERROR, WARNING, NOTICE, INFO, DEBUG, TRACE",
        "ConsoleLevel",
        ENVIRO_CONFIG.settings.console_level or "INFO",
    )
    _gen_default_line(
        settings, "Enable logging to files", "Logging", ENVIRO_CONFIG.settings.logging or True
    )
    _gen_default_line(
        settings,
        "Folder where your completed downloads are put into. Can be found in qBitTorrent -> Options -> Downloads -> Default Save Path (Please note, replace all '\\' with '/')",
        "CompletedDownloadFolder",
        ENVIRO_CONFIG.settings.completed_download_folder or "CHANGE_ME",
    )
    _gen_default_line(
        settings,
        "The desired amount of free space in the downloads directory [K=kilobytes, M=megabytes, G=gigabytes, T=terabytes] (set to -1 to disable, this bypasses AutoPauseResume)",
        "FreeSpace",
        ENVIRO_CONFIG.settings.free_space or "-1",
    )
    _gen_default_line(
        settings,
        "Folder where the free space handler will check for free space (Please note, replace all '' with '/')",
        "FreeSpaceFolder",
        ENVIRO_CONFIG.settings.free_space_folder or "CHANGE_ME",
    )
    _gen_default_line(
        settings,
        "Enable automation of pausing and resuming torrents as needed (Required enabled for the FreeSpace logic to function)",
        "AutoPauseResume",
        ENVIRO_CONFIG.settings.auto_pause_resume or True,
    )
    _gen_default_line(
        settings,
        "Time to sleep for if there is no internet (in seconds: 600 = 10 Minutes)",
        "NoInternetSleepTimer",
        ENVIRO_CONFIG.settings.no_internet_sleep_timer or 15,
    )
    _gen_default_line(
        settings,
        "Time to sleep between reprocessing torrents (in seconds: 600 = 10 Minutes)",
        "LoopSleepTimer",
        ENVIRO_CONFIG.settings.loop_sleep_timer or 5,
    )
    _gen_default_line(
        settings,
        "Time to sleep between posting search commands (in seconds: 600 = 10 Minutes)",
        "SearchLoopDelay",
        ENVIRO_CONFIG.settings.search_loop_delay or -1,
    )
    _gen_default_line(
        settings,
        "Add torrents to this category to mark them as failed",
        "FailedCategory",
        ENVIRO_CONFIG.settings.failed_category or "failed",
    )
    _gen_default_line(
        settings,
        "Add torrents to this category to trigger them to be rechecked properly",
        "RecheckCategory",
        ENVIRO_CONFIG.settings.recheck_category or "recheck",
    )
    _gen_default_line(
        settings, "Tagless operation", "Tagless", ENVIRO_CONFIG.settings.tagless or False
    )
    _gen_default_line(
        settings,
        [
            "Ignore Torrents which are younger than this value (in seconds: 600 = 10 Minutes)",
            "Only applicable to Re-check and failed categories",
        ],
        "IgnoreTorrentsYoungerThan",
        ENVIRO_CONFIG.settings.ignore_torrents_younger_than or 180,
    )
    _gen_default_line(
        settings,
        [
            "URL to be pinged to check if you have a valid internet connection",
            "These will be pinged a **LOT** make sure the service is okay with you sending all the continuous pings.",
        ],
        "PingURLS",
        ENVIRO_CONFIG.settings.ping_urls or ["one.one.one.one", "dns.google.com"],
    )
    _gen_default_line(
        settings,
        [
            "FFprobe auto updates, binaries are downloaded from https://ffbinaries.com/downloads",
            "If this is disabled and you want ffprobe to work",
            "Ensure that you add the ffprobe binary to the folder"
            f"\"{APPDATA_FOLDER.joinpath('ffprobe.exe')}\"",
            "If no `ffprobe` binary is found in the folder above all ffprobe functionality will be disabled.",
            "By default this will always be on even if config does not have these key - to disable you need to explicitly set it to `False`",
        ],
        "FFprobeAutoUpdate",
        (
            True
            if ENVIRO_CONFIG.settings.ffprobe_auto_update is None
            else ENVIRO_CONFIG.settings.ffprobe_auto_update
        ),
    )
    _gen_default_line(
        settings,
        [
            "Automatically attempt to update qBitrr on a schedule",
            "Set to true to enable the auto-update worker.",
        ],
        "AutoUpdateEnabled",
        (
            ENVIRO_CONFIG.settings.auto_update_enabled
            if ENVIRO_CONFIG.settings.auto_update_enabled is not None
            else False
        ),
    )
    _gen_default_line(
        settings,
        [
            "Cron expression describing when to check for updates",
            "Default is weekly Sunday at 03:00 (0 3 * * 0).",
        ],
        "AutoUpdateCron",
        ENVIRO_CONFIG.settings.auto_update_cron or "0 3 * * 0",
    )
    _gen_default_line(
        settings,
        [
            "Automatically restart worker processes that fail or crash",
            "Set to false to disable auto-restart (processes will only log failures)",
        ],
        "AutoRestartProcesses",
        True,
    )
    _gen_default_line(
        settings,
        [
            "Maximum number of restart attempts per process within the restart window",
            "Prevents infinite restart loops for processes that crash immediately",
        ],
        "MaxProcessRestarts",
        5,
    )
    _gen_default_line(
        settings,
        [
            "Time window (seconds) for tracking restart attempts",
            "If a process restarts MaxProcessRestarts times within this window, auto-restart is disabled for that process",
        ],
        "ProcessRestartWindow",
        300,
    )
    _gen_default_line(
        settings,
        "Delay (seconds) before attempting to restart a failed process",
        "ProcessRestartDelay",
        5,
    )
    config.add("Settings", settings)


def _add_qbit_section(config: TOMLDocument):
    qbit = table()
    _gen_default_line(
        qbit,
        [
            "If this is enabled qBitrr can run in headless mode where it will only process searches.",
            "If media search is enabled in their individual categories",
            "This is useful if you use for example Sabnzbd/NZBGet for downloading content but still want the faster media searches provided by qbit",
        ],
        "Disabled",
        False if ENVIRO_CONFIG.qbit.disabled is None else ENVIRO_CONFIG.qbit.disabled,
    )
    _gen_default_line(
        qbit,
        'qbittorrent WebUI URL/IP - Can be found in Options > Web UI (called "IP Address")',
        "Host",
        ENVIRO_CONFIG.qbit.host or "CHANGE_ME",
    )
    _gen_default_line(
        qbit,
        'qbittorrent WebUI Port - Can be found in Options > Web UI (called "Port" on top right corner of the window)',
        "Port",
        ENVIRO_CONFIG.qbit.port or 8080,
    )
    _gen_default_line(
        qbit,
        "qbittorrent WebUI Authentication - Can be found in Options > Web UI > Authentication",
        "UserName",
        ENVIRO_CONFIG.qbit.username or "CHANGE_ME",
    )
    _gen_default_line(
        qbit,
        'If you set "Bypass authentication on localhost or whitelisted IPs" remove this field.',
        "Password",
        ENVIRO_CONFIG.qbit.password or "CHANGE_ME",
    )
    _gen_default_line(
        qbit,
        [
            "Categories managed directly by this qBit instance (not managed by Arr instances).",
            "These categories will have seeding settings applied according to CategorySeeding configuration.",
            "Example: ['downloads', 'private-tracker', 'long-term-seed']",
        ],
        "ManagedCategories",
        [],
    )

    # Add CategorySeeding subsection
    category_seeding = table()
    _gen_default_line(
        category_seeding,
        "Download rate limit per torrent in KB/s (-1 = disabled)",
        "DownloadRateLimitPerTorrent",
        -1,
    )
    _gen_default_line(
        category_seeding,
        "Upload rate limit per torrent in KB/s (-1 = disabled)",
        "UploadRateLimitPerTorrent",
        -1,
    )
    _gen_default_line(
        category_seeding,
        "Maximum upload ratio (-1 = disabled, e.g. 2.0 for 200%)",
        "MaxUploadRatio",
        -1,
    )
    _gen_default_line(
        category_seeding,
        "Maximum seeding time in seconds (-1 = disabled, e.g. 604800 for 7 days)",
        "MaxSeedingTime",
        -1,
    )
    _gen_default_line(
        category_seeding,
        [
            "When to remove torrents from qBittorrent:",
            "  -1 = Never remove",
            "   1 = Remove when MaxUploadRatio is reached",
            "   2 = Remove when MaxSeedingTime is reached",
            "   3 = Remove when either condition is met (OR)",
            "   4 = Remove when both conditions are met (AND)",
        ],
        "RemoveTorrent",
        -1,
    )
    _gen_default_line(
        category_seeding,
        "Enable Hit and Run protection for managed category torrents",
        "HitAndRunMode",
        False,
    )
    _gen_default_line(
        category_seeding,
        "Minimum seed ratio before removal allowed (HnR protection)",
        "MinSeedRatio",
        1.0,
    )
    _gen_default_line(
        category_seeding,
        "Minimum seeding time in days before removal allowed (HnR protection, 0 = ratio only)",
        "MinSeedingTimeDays",
        0,
    )
    _gen_default_line(
        category_seeding,
        "Minimum ratio for partial downloads (>=10% but <100% complete)",
        "HitAndRunPartialSeedRatio",
        1.0,
    )
    _gen_default_line(
        category_seeding,
        "Extra seconds buffer for tracker stats lag (0 = disabled)",
        "TrackerUpdateBuffer",
        0,
    )
    qbit.add("CategorySeeding", category_seeding)

    config.add("qBit", qbit)


def _add_category_sections(config: TOMLDocument):
    for c in ["Sonarr-TV", "Sonarr-Anime", "Radarr-1080", "Radarr-4K", "Lidarr-Music"]:
        _gen_default_cat(c, config)


def _gen_default_cat(category: str, config: TOMLDocument):
    cat_default = table()
    cat_default.add(nl())
    _gen_default_line(
        cat_default, "Toggle whether to manage the Servarr instance torrents.", "Managed", True
    )
    _gen_default_line(
        cat_default,
        "The URL used to access Servarr interface eg. http://ip:port"
        "(if you use a domain enter the domain without a port)",
        "URI",
        "CHANGE_ME",
    )
    _gen_default_line(
        cat_default,
        "The Servarr API Key, Can be found it Settings > General > Security",
        "APIKey",
        "CHANGE_ME",
    )
    _gen_default_line(
        cat_default,
        "Category applied by Servarr to torrents in qBitTorrent, can be found in Settings > Download Clients > qBit > Category",
        "Category",
        category.lower(),
    )
    _gen_default_line(
        cat_default,
        "Toggle whether to send a query to Servarr to search any failed torrents",
        "ReSearch",
        True,
    )
    _gen_default_line(
        cat_default, "The Servarr's Import Mode(one of Move, Copy or Auto)", "importMode", "Auto"
    )
    _gen_default_line(
        cat_default,
        "Timer to call RSSSync (In minutes) - Set to 0 to disable (Values below 5 can cause errors for maximum retires)",
        "RssSyncTimer",
        1,
    )
    _gen_default_line(
        cat_default,
        "Timer to call RefreshDownloads to update the queue. (In minutes) - Set to 0 to disable (Values below 5 can cause errors for maximum retires)",
        "RefreshDownloadsTimer",
        1,
    )
    messages = []
    if "radarr" in category.lower():
        messages.extend(
            [
                "Not a preferred word upgrade for existing movie file(s)",
                "Not an upgrade for existing movie file(s)",
                "Unable to determine if file is a sample",
            ]
        )
    elif "sonarr" in category.lower():
        messages.extend(
            [
                "Not a preferred word upgrade for existing episode file(s)",
                "Not an upgrade for existing episode file(s)",
                "Unable to determine if file is a sample",
            ]
        )
    elif "lidarr" in category.lower():
        messages.extend(
            [
                "Not a preferred word upgrade for existing track file(s)",
                "Not an upgrade for existing track file(s)",
                "Unable to determine if file is a sample",
            ]
        )
    _gen_default_line(
        cat_default,
        [
            "Error messages shown my the Arr instance which should be considered failures.",
            "This entry should be a list, leave it empty if you want to disable this error handling.",
            "If enabled qBitrr will remove the failed files and tell the Arr instance the download failed",
        ],
        "ArrErrorCodesToBlocklist",
        list(set(messages)),
    )
    _gen_default_search_table(category, cat_default)
    _gen_default_torrent_table(category, cat_default)
    config.add(category, cat_default)


def _gen_default_torrent_table(category: str, cat_default: Table):
    torrent_table = table()
    _gen_default_line(
        torrent_table,
        "Set it to regex matches to respect/ignore case.",
        "CaseSensitiveMatches",
        False,
    )
    # Set folder exclusions based on category type
    if "anime" in category.lower():
        # Anime-specific exclusions (includes OVA, specials, NCOP/NCED)
        folder_exclusions = [
            r"\bextras?\b",
            r"\bfeaturettes?\b",
            r"\bsamples?\b",
            r"\bscreens?\b",
            r"\bspecials?\b",
            r"\bova\b",
            r"\bnc(ed|op)?(\\d+)?\b",
        ]
    elif "lidarr" in category.lower():
        # Music-specific exclusions (no NCOP/NCED, no featurettes)
        folder_exclusions = [
            r"\bextras?\b",
            r"\bsamples?\b",
            r"\bscreens?\b",
        ]
    else:
        # Standard video exclusions (movies/TV shows)
        folder_exclusions = [
            r"\bextras?\b",
            r"\bfeaturettes?\b",
            r"\bsamples?\b",
            r"\bscreens?\b",
            r"\bnc(ed|op)?(\\d+)?\b",
        ]

    _gen_default_line(
        torrent_table,
        [
            "These regex values will match any folder where the full name matches the specified values here, comma separated strings.",
            "These regex need to be escaped, that's why you see so many backslashes.",
        ],
        "FolderExclusionRegex",
        folder_exclusions,
    )
    # Set filename exclusions based on category type
    if "lidarr" in category.lower():
        # Music-specific exclusions (no NCOP/NCED, no "music video" since that's actual music content)
        filename_exclusions = [
            r"\bsample\b",
            r"brarbg.com\b",
            r"\btrailer\b",
            r"comandotorrents.com",
        ]
    else:
        # Video exclusions (movies/TV/anime)
        filename_exclusions = [
            r"\bncop\\d+?\b",
            r"\bnced\\d+?\b",
            r"\bsample\b",
            r"brarbg.com\b",
            r"\btrailer\b",
            r"music video",
            r"comandotorrents.com",
        ]

    _gen_default_line(
        torrent_table,
        [
            "These regex values will match any folder where the full name matches the specified values here, comma separated strings.",
            "These regex need to be escaped, that's why you see so many backslashes.",
        ],
        "FileNameExclusionRegex",
        filename_exclusions,
    )
    # Set appropriate file extensions based on category type
    if "lidarr" in category.lower():
        file_extensions = [
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
    else:
        file_extensions = [".mp4", ".mkv", ".sub", ".ass", ".srt", ".!qB", ".parts"]

    _gen_default_line(
        torrent_table,
        "Only files with these extensions will be allowed to be downloaded, comma separated strings or regex, leave it empty to allow all extensions",
        "FileExtensionAllowlist",
        file_extensions,
    )
    _gen_default_line(
        torrent_table,
        "Auto delete files that can't be playable (i.e .exe, .png)",
        "AutoDelete",
        False,
    )
    _gen_default_line(
        torrent_table,
        "Ignore Torrents which are younger than this value (in seconds: 600 = 10 Minutes)",
        "IgnoreTorrentsYoungerThan",
        180,
    )
    _gen_default_line(
        torrent_table,
        [
            "Maximum allowed remaining ETA for torrent completion (in seconds: 3600 = 1 Hour)",
            "Note that if you set the MaximumETA on a tracker basis that value is favoured over this value",
        ],
        "MaximumETA",
        -1,
    )
    _gen_default_line(
        torrent_table,
        "Do not delete torrents with higher completion percentage than this setting (0.5 = 50%, 1.0 = 100%)",
        "MaximumDeletablePercentage",
        0.99,
    )
    _gen_default_line(torrent_table, "Ignore slow torrents.", "DoNotRemoveSlow", True)
    _gen_default_line(
        torrent_table,
        "Maximum allowed time for allowed stalled torrents in minutes (-1 = Disabled, 0 = Infinite)",
        "StalledDelay",
        15,
    )
    _gen_default_line(
        torrent_table,
        "Re-search stalled torrents when StalledDelay is enabled and you want to re-search before removing the stalled torrent, or only after the torrent is removed.",
        "ReSearchStalled",
        False,
    )
    _gen_default_seeding_table(category, torrent_table)
    _gen_default_tracker_tables(category, torrent_table)

    cat_default.add("Torrent", torrent_table)


def _gen_default_seeding_table(category: str, torrent_table: Table):
    seeding_table = table()
    _gen_default_line(
        seeding_table,
        [
            "Set the maximum allowed download rate for torrents",
            "Set this value to -1 to disabled it",
            "Note that if you set the DownloadRateLimit on a tracker basis that value is favoured over this value",
        ],
        "DownloadRateLimitPerTorrent",
        -1,
    )
    _gen_default_line(
        seeding_table,
        [
            "Set the maximum allowed upload rate for torrents",
            "Set this value to -1 to disabled it",
            "Note that if you set the UploadRateLimit on a tracker basis that value is favoured over this value",
        ],
        "UploadRateLimitPerTorrent",
        -1,
    )
    _gen_default_line(
        seeding_table,
        [
            "Set the maximum allowed upload ratio for torrents",
            "Set this value to -1 to disabled it",
            "Note that if you set the MaxUploadRatio on a tracker basis that value is favoured over this value",
        ],
        "MaxUploadRatio",
        -1,
    )
    _gen_default_line(
        seeding_table,
        [
            "Set the maximum seeding time in seconds for torrents",
            "Set this value to -1 to disabled it",
            "Note that if you set the MaxSeedingTime on a tracker basis that value is favoured over this value",
        ],
        "MaxSeedingTime",
        -1,
    )
    _gen_default_line(
        seeding_table,
        "Remove torrent condition (-1=Do not remove, 1=Remove on MaxUploadRatio, 2=Remove on MaxSeedingTime, 3=Remove on MaxUploadRatio or MaxSeedingTime, 4=Remove on MaxUploadRatio and MaxSeedingTime)",
        "RemoveTorrent",
        -1,
    )
    _gen_default_line(
        seeding_table, "Enable if you want to remove dead trackers", "RemoveDeadTrackers", False
    )
    _gen_default_line(
        seeding_table,
        'If "RemoveDeadTrackers" is set to true then remove trackers with the following messages',
        "RemoveTrackerWithMessage",
        [
            "skipping tracker announce (unreachable)",
            "No such host is known",
            "unsupported URL protocol",
            "info hash is not authorized with this tracker",
        ],
    )

    _gen_default_line(
        seeding_table,
        [
            "Enable Hit and Run (HnR) protection.",
            "When enabled, torrents will not be removed until HnR obligations are met.",
            "Private trackers often require seeding to a minimum ratio or for a minimum time.",
        ],
        "HitAndRunMode",
        False,
    )
    _gen_default_line(
        seeding_table,
        [
            "Minimum seed ratio before a torrent can be removed (HnR protection).",
            "Set to 1.0 for typical private tracker requirements.",
        ],
        "MinSeedRatio",
        1.0,
    )
    _gen_default_line(
        seeding_table,
        [
            "Minimum seeding time in days before a torrent can be removed (HnR protection).",
            "Set to 0 to use ratio-only protection.",
            "For full downloads: either ratio OR time clears the HnR obligation.",
        ],
        "MinSeedingTimeDays",
        0,
    )
    _gen_default_line(
        seeding_table,
        [
            "Minimum ratio for partial downloads (>=10% but <100% complete).",
            "Partial downloads typically must reach this ratio (time does not apply).",
        ],
        "HitAndRunPartialSeedRatio",
        1.0,
    )
    _gen_default_line(
        seeding_table,
        [
            "Extra seconds to wait after meeting HnR criteria before allowing removal.",
            "Accounts for tracker stats lag (trackers can be ~30 min behind the client).",
            "Set to 0 to disable.",
        ],
        "TrackerUpdateBuffer",
        0,
    )

    torrent_table.add("SeedingMode", seeding_table)


def _gen_default_tracker_tables(category: str, torrent_table: Table):
    tracker_table_list = []
    tracker_list = []
    if "anime" in category.lower():
        tracker_list.append(("Nyaa", "http://nyaa.tracker.wf:7777/announce", ["qBitrr-anime"], 10))
    elif "radarr" in category.lower():
        t = ["qBitrr-Rarbg", "Movies and TV"]
        t2 = []
        if "4k" in category.lower():
            t.append("4K")
            t2.append("4K")
        tracker_list.extend(
            (
                ("Rarbg-2810", "udp://9.rarbg.com:2810/announce", t, 1),
                ("Rarbg-2740", "udp://9.rarbg.to:2740/announce", t2, 2),
            )
        )
    for name, url, tags, priority in tracker_list:
        tracker_table = table()
        _gen_default_line(
            tracker_table,
            "This is only for your own benefit, it is not currently used anywhere, but one day it may be.",
            "Name",
            name,
        )
        tracker_table.add(
            comment("This is used when multiple trackers are in one single torrent.")
        )
        _gen_default_line(
            tracker_table,
            "the tracker with the highest priority will have all its settings applied to the torrent.",
            "Priority",
            priority,
        )
        _gen_default_line(tracker_table, "The tracker URI used by qBit.", "URI", url)
        _gen_default_line(
            tracker_table,
            "Maximum allowed remaining ETA for torrent completion (in seconds: 3600 = 1 Hour).",
            "MaximumETA",
            18000,
        )
        tracker_table.add(comment("Set the maximum allowed download rate for torrents"))
        _gen_default_line(
            tracker_table, "Set this value to -1 to disabled it", "DownloadRateLimit", -1
        )
        tracker_table.add(comment("Set the maximum allowed upload rate for torrents"))
        _gen_default_line(
            tracker_table, "Set this value to -1 to disabled it", "UploadRateLimit", -1
        )
        tracker_table.add(comment("Set the maximum allowed download rate for torrents"))
        _gen_default_line(
            tracker_table, "Set this value to -1 to disabled it", "MaxUploadRatio", -1
        )
        tracker_table.add(comment("Set the maximum allowed download rate for torrents"))
        _gen_default_line(
            tracker_table, "Set this value to -1 to disabled it", "MaxSeedingTime", -1
        )
        _gen_default_line(
            tracker_table,
            "Add this tracker from any torrent that does not contains it.",
            "AddTrackerIfMissing",
            False,
        )
        _gen_default_line(
            tracker_table,
            "Remove this tracker from any torrent that contains it.",
            "RemoveIfExists",
            False,
        )
        _gen_default_line(
            tracker_table,
            "Enable Super Seeding setting for torrents with this tracker.",
            "SuperSeedMode",
            False,
        )
        _gen_default_line(
            tracker_table,
            "Enable Hit and Run protection for this tracker (overrides global).",
            "HitAndRunMode",
            False,
        )
        _gen_default_line(
            tracker_table,
            "Minimum seed ratio for HnR protection (overrides global).",
            "MinSeedRatio",
            1.0,
        )
        _gen_default_line(
            tracker_table,
            "Minimum seeding time in days for HnR protection (overrides global, 0 = ratio only).",
            "MinSeedingTimeDays",
            0,
        )
        _gen_default_line(
            tracker_table,
            "Minimum ratio for partial downloads for HnR protection (overrides global).",
            "HitAndRunPartialSeedRatio",
            1.0,
        )
        _gen_default_line(
            tracker_table,
            "Extra seconds buffer for tracker stats lag (overrides global).",
            "TrackerUpdateBuffer",
            0,
        )
        if tags:
            _gen_default_line(
                tracker_table,
                "Adds these tags to any torrents containing this tracker.",
                "AddTags",
                tags,
            )
        tracker_table_list.append(tracker_table)
    torrent_table.add(
        comment("You can have multiple trackers set here or none just add more subsections.")
    )
    torrent_table.add("Trackers", tracker_table_list)


def _gen_default_line(table, comments, field, value):
    if isinstance(comments, list):
        for c in comments:
            table.add(comment(c))
    else:
        table.add(comment(comments))
    table.add(field, value)
    table.add(nl())


def _gen_default_search_table(category: str, cat_default: Table):
    search_table = table()
    _gen_default_line(search_table, "Should search for Missing files?", "SearchMissing", True)
    if "sonarr" in category.lower():
        _gen_default_line(
            search_table,
            "Should search for specials episodes? (Season 00)",
            "AlsoSearchSpecials",
            False,
        )
        _gen_default_line(
            search_table,
            "Should search for unmonitored episodes/series?",
            "Unmonitored",
            False,
        )
        _gen_default_line(
            search_table,
            [
                "Maximum allowed Searches at any one points (I wouldn't recommend settings this too high)",
                "Sonarr has a hardcoded cap of 3 simultaneous tasks",
            ],
            "SearchLimit",
            5,
        )
    elif "radarr" in category.lower():
        _gen_default_line(
            search_table,
            "Should search for unmonitored movies?",
            "Unmonitored",
            False,
        )
        _gen_default_line(
            search_table,
            [
                "Radarr has a default of 3 simultaneous tasks, which can be increased up to 10 tasks",
                'If you set the environment variable of "THREAD_LIMIT" to a number between and including 2-10',
                "Radarr devs have stated that this is an unsupported feature so you will not get any support for doing so from them.",
                "That being said I've been daily driving 10 simultaneous tasks for quite a while now with no issues.",
            ],
            "SearchLimit",
            5,
        )
    # SearchByYear doesn't apply to Lidarr (music albums)
    if "lidarr" not in category.lower():
        if "sonarr" in category.lower():
            search_by_year_comment = (
                "It will order searches by the year the episode was first aired"
            )
        else:
            search_by_year_comment = "It will order searches by the year the movie was released"
        _gen_default_line(
            search_table,
            search_by_year_comment,
            "SearchByYear",
            True,
        )
    _gen_default_line(
        search_table,
        "Reverse search order (Start searching oldest to newest)",
        "SearchInReverse",
        False,
    )
    _gen_default_line(
        search_table,
        "Delay (in seconds) between checking for new Overseerr/Ombi requests. Does NOT affect delay between individual search commands (use Settings.SearchLoopDelay for that).",
        "SearchRequestsEvery",
        300,
    )
    _gen_default_line(
        search_table,
        "Search media which already have a file in hopes of finding a better quality version.",
        "DoUpgradeSearch",
        False,
    )
    _gen_default_line(
        search_table,
        "Do a quality unmet search for existing entries.",
        "QualityUnmetSearch",
        False,
    )
    _gen_default_line(
        search_table,
        "Do a minimum custom format score unmet search for existing entries.",
        "CustomFormatUnmetSearch",
        False,
    )
    _gen_default_line(
        search_table,
        "Automatically remove torrents that do not mee the minimum custom format score.",
        "ForceMinimumCustomFormat",
        False,
    )
    _gen_default_line(
        search_table,
        "Once you have search all files on your specified year range restart the loop and "
        "search again.",
        "SearchAgainOnSearchCompletion",
        True,
    )
    _gen_default_line(search_table, "Use Temp profile for missing", "UseTempForMissing", False)
    _gen_default_line(search_table, "Don't change back to main profile", "KeepTempProfile", False)
    _gen_default_line(
        search_table,
        [
            "Quality profile mappings for temp profile switching (Main Profile Name -> Temp Profile Name)",
            "Profile names must match exactly as they appear in your Arr instance",
            'Example: QualityProfileMappings = {"HD-1080p" = "SD", "HD-720p" = "SD"}',
        ],
        "QualityProfileMappings",
        inline_table(),
    )
    _gen_default_line(
        search_table,
        "Reset all items using temp profiles to their original main profile on qBitrr startup",
        "ForceResetTempProfiles",
        False,
    )
    _gen_default_line(
        search_table,
        "Timeout in minutes after which items with temp profiles are automatically reset to main profile (0 = disabled)",
        "TempProfileResetTimeoutMinutes",
        0,
    )
    _gen_default_line(
        search_table,
        "Number of retry attempts for profile switch API calls (default: 3)",
        "ProfileSwitchRetryAttempts",
        3,
    )
    _gen_default_line(
        search_table,
        "Main quality profile (To pair quality profiles, ensure they are in the same order as in the temp profiles)",
        "MainQualityProfile",
        [],
    )
    _gen_default_line(
        search_table,
        "Temp quality profile (To pair quality profiles, ensure they are in the same order as in the main profiles)",
        "TempQualityProfile",
        [],
    )
    if "sonarr" in category.lower():
        _gen_default_line(
            search_table,
            [
                "Search mode: true (always series search), false (always episode search), or 'smart' (automatic)",
                "Smart mode: uses series search for entire seasons/series, episode search for single episodes",
                "(Series search ignores QualityUnmetSearch and CustomFormatUnmetSearch settings)",
            ],
            "SearchBySeries",
            "smart",
        )
        _gen_default_line(
            search_table,
            "Prioritize Today's releases (Similar effect as RSS Sync, where it searches "
            "today's release episodes first, only works on Sonarr).",
            "PrioritizeTodaysReleases",
            True,
        )
    # Ombi and Overseerr don't support music requests
    if "lidarr" not in category.lower():
        _gen_default_ombi_table(category, search_table)
        _gen_default_overseerr_table(category, search_table)
    cat_default.add("EntrySearch", search_table)


def _gen_default_ombi_table(category: str, search_table: Table):
    ombi_table = table()
    _gen_default_line(
        ombi_table,
        "Search Ombi for pending requests (Will only work if 'SearchMissing' is enabled.)",
        "SearchOmbiRequests",
        False,
    )
    _gen_default_line(
        ombi_table,
        "Ombi URI eg. http://ip:port (Note that this has to be the instance of Ombi which manage the Arr instance request (If you have multiple Ombi instances)",
        "OmbiURI",
        "CHANGE_ME",
    )
    _gen_default_line(ombi_table, "Ombi's API Key", "OmbiAPIKey", "CHANGE_ME")
    _gen_default_line(ombi_table, "Only process approved requests", "ApprovedOnly", True)
    search_table.add("Ombi", ombi_table)


def _gen_default_overseerr_table(category: str, search_table: Table):
    overseerr_table = table()
    _gen_default_line(
        overseerr_table,
        [
            "Search Overseerr for pending requests (Will only work if 'SearchMissing' is enabled.)",
            "If this and Ombi are both enable, Ombi will be ignored",
        ],
        "SearchOverseerrRequests",
        False,
    )
    _gen_default_line(
        overseerr_table, "Overseerr's URI eg. http://ip:port", "OverseerrURI", "CHANGE_ME"
    )
    _gen_default_line(overseerr_table, "Overseerr's API Key", "OverseerrAPIKey", "CHANGE_ME")
    _gen_default_line(overseerr_table, "Only process approved requests", "ApprovedOnly", True)
    overseerr_table.add(comment("Only for 4K Instances"))
    if "radarr-4k" in category.lower():
        _gen_default_line(overseerr_table, "Only for 4K Instances", "Is4K", True)
    else:
        _gen_default_line(overseerr_table, "Only for 4K Instances", "Is4K", False)
    search_table.add("Overseerr", overseerr_table)


class MyConfig:
    # Original code taken from https://github.com/SemenovAV/toml_config
    # Licence is MIT, can be located at
    # https://github.com/SemenovAV/toml_config/blob/master/LICENSE.txt

    path: pathlib.Path
    config: TOMLDocument
    defaults_config: TOMLDocument

    def __init__(self, path: pathlib.Path | str, config: TOMLDocument | None = None):
        self.path = pathlib.Path(path)
        self._giving_data = bool(config)
        self.config = config or document()
        self.defaults_config = generate_doc()
        self.err = None
        self.state = True
        self.load()

    def __str__(self):
        return self.config.as_string()

    def load(self) -> MyConfig:
        if self.state:
            try:
                if self._giving_data:
                    return self
                with self.path.open() as file:
                    self.config = parse(file.read())
                    return self
            except (OSError, TypeError) as err:
                self.state = False
                self.err = err
        return self

    def save(self) -> MyConfig:
        if self.state:
            try:
                with open(self.path, "w", encoding="utf8") as file:
                    file.write(self.config.as_string())
                    return self
            except OSError as err:
                self._value_error(
                    err, "Possible permissions while attempting to read the config file.\n"
                )
            except TypeError as err:
                self._value_error(err, "While attempting to read the config file.\n")
        return self

    def _value_error(self, err, arg1):
        self.state = False
        self.err = err
        raise ValueError(f"{arg1}{err}")

    def get(self, section: str, fallback: Any = None) -> T:
        return self._deep_get(section, default=fallback)

    def get_or_raise(self, section: str) -> T:
        if (r := self._deep_get(section, default=KeyError)) is KeyError:
            raise KeyError(f"{section} does not exist")
        return r

    def sections(self):
        return self.config.keys()

    def _deep_get(self, keys, default=...):
        values = reduce(
            lambda d, key: d.get(key, ...) if isinstance(d, dict) else ...,
            keys.split("."),
            self.config,
        )

        return values if values is not ... else default


def _migrate_webui_config(config: MyConfig) -> bool:
    """
    Migrate WebUI configuration from old location (Settings section) to new location (WebUI section).
    Returns True if any migration was performed, False otherwise.
    """
    migrated = False

    # Check if WebUI section exists, if not create it
    if "WebUI" not in config.config:
        config.config["WebUI"] = table()

    webui_section = config.config.get("WebUI", {})

    # Migrate Host from Settings to WebUI
    if "Host" not in webui_section:
        old_host = config.get("Settings.Host", fallback=None)
        if old_host is not None:
            webui_section["Host"] = old_host
            migrated = True
            print(f"Migrated WebUI Host from Settings to WebUI section: {old_host}")

    # Migrate Port from Settings to WebUI
    if "Port" not in webui_section:
        old_port = config.get("Settings.Port", fallback=None)
        if old_port is not None:
            webui_section["Port"] = old_port
            migrated = True
            print(f"Migrated WebUI Port from Settings to WebUI section: {old_port}")

    # Migrate Token from Settings to WebUI
    if "Token" not in webui_section:
        old_token = config.get("Settings.Token", fallback=None)
        if old_token is not None:
            webui_section["Token"] = old_token
            migrated = True
            print(f"Migrated WebUI Token from Settings to WebUI section")

    return migrated


def _migrate_process_restart_settings(config: MyConfig) -> bool:
    """
    Add process auto-restart settings to existing configs.

    Migration runs if:
    - ConfigVersion < "0.0.3"

    After migration, ConfigVersion will be set by apply_config_migrations().

    Returns:
        True if changes were made, False otherwise
    """
    import logging

    from qBitrr.config_version import _parse_version, get_config_version

    logger = logging.getLogger(__name__)

    # Check if migration already applied
    current_version = _parse_version(get_config_version(config))
    if current_version >= _parse_version("0.0.3"):
        return False  # Already migrated

    # Ensure Settings section exists
    if "Settings" not in config.config:
        config.config["Settings"] = table()

    settings = config.config["Settings"]
    changes_made = False

    # Add AutoRestartProcesses if missing
    if "AutoRestartProcesses" not in settings:
        settings["AutoRestartProcesses"] = True
        changes_made = True
        logger.info("Added AutoRestartProcesses = true (default: enabled)")

    # Add MaxProcessRestarts if missing
    if "MaxProcessRestarts" not in settings:
        settings["MaxProcessRestarts"] = 5
        changes_made = True
        logger.info("Added MaxProcessRestarts = 5 (default)")

    # Add ProcessRestartWindow if missing
    if "ProcessRestartWindow" not in settings:
        settings["ProcessRestartWindow"] = 300
        changes_made = True
        logger.info("Added ProcessRestartWindow = 300 seconds (5 minutes)")

    # Add ProcessRestartDelay if missing
    if "ProcessRestartDelay" not in settings:
        settings["ProcessRestartDelay"] = 5
        changes_made = True
        logger.info("Added ProcessRestartDelay = 5 seconds")

    if changes_made:
        print("Migration v2→v3: Added process auto-restart configuration settings")

    return changes_made


def _migrate_quality_profile_mappings(config: MyConfig) -> bool:
    """
    Migrate from list-based profile config to dict-based mappings.

    Migration runs if:
    - ConfigVersion < "0.0.2"

    After migration, ConfigVersion will be set by apply_config_migrations().

    Returns:
        True if changes were made, False otherwise
    """
    import logging

    from qBitrr.config_version import _parse_version, get_config_version

    logger = logging.getLogger(__name__)

    # Check if migration already applied
    current_version = _parse_version(get_config_version(config))
    if current_version >= _parse_version("0.0.2"):
        return False  # Already migrated

    changes_made = False
    arr_types = ["Radarr", "Sonarr", "Lidarr", "Animarr"]

    for arr_type in arr_types:
        # Find all Arr instances (e.g., "Radarr-Movies", "Sonarr-TV")
        for key in list(config.config.keys()):
            if not str(key).startswith(arr_type):
                continue

            entry_search_key = f"{key}.EntrySearch"
            entry_search_section = config.get(entry_search_key, fallback=None)
            if not entry_search_section:
                continue

            # Check for old format
            main_profiles = config.get(f"{entry_search_key}.MainQualityProfile", fallback=None)
            temp_profiles = config.get(f"{entry_search_key}.TempQualityProfile", fallback=None)

            # Skip if no old format found
            if not main_profiles or not temp_profiles:
                continue

            # Validate list lengths match
            if len(main_profiles) != len(temp_profiles):
                logger.error(
                    f"Cannot migrate {key}: MainQualityProfile ({len(main_profiles)}) "
                    f"and TempQualityProfile ({len(temp_profiles)}) have different lengths"
                )
                continue

            # Create mappings dict, filtering out empty/None values
            mappings = {
                str(main).strip(): str(temp).strip()
                for main, temp in zip(main_profiles, temp_profiles)
                if main and temp and str(main).strip() and str(temp).strip()
            }

            if mappings:
                # Set new format - use tomlkit's inline_table to ensure it's rendered as inline dict
                inline_mappings = inline_table()
                inline_mappings.update(mappings)
                config.config[str(key)]["EntrySearch"]["QualityProfileMappings"] = inline_mappings
                changes_made = True
                logger.info(f"Migrated {key} to QualityProfileMappings: {mappings}")

                # Remove old format
                del config.config[str(key)]["EntrySearch"]["MainQualityProfile"]
                del config.config[str(key)]["EntrySearch"]["TempQualityProfile"]
                logger.debug(f"Removed legacy profile lists from {key}")

    return changes_made


def _migrate_qbit_category_settings(config: MyConfig) -> bool:
    """
    Add qBit category management settings to existing configs.

    Migration runs if:
    - ConfigVersion < "0.0.4"

    Adds ManagedCategories and CategorySeeding configuration to all qBit sections.

    After migration, ConfigVersion will be set by apply_config_migrations().

    Returns:
        True if changes were made, False otherwise
    """
    import logging

    from qBitrr.config_version import _parse_version, get_config_version

    logger = logging.getLogger(__name__)

    # Check if migration already applied
    current_version = _parse_version(get_config_version(config))
    if current_version >= _parse_version("0.0.4"):
        return False  # Already migrated

    changes_made = False

    # Migrate default qBit section
    if "qBit" in config.config:
        qbit_section = config.config["qBit"]
        if "ManagedCategories" not in qbit_section:
            qbit_section["ManagedCategories"] = []
            changes_made = True
            logger.info("Added ManagedCategories = [] to [qBit]")

        # Add CategorySeeding subsection
        if "CategorySeeding" not in qbit_section:
            seeding = table()
            seeding["DownloadRateLimitPerTorrent"] = -1
            seeding["UploadRateLimitPerTorrent"] = -1
            seeding["MaxUploadRatio"] = -1
            seeding["MaxSeedingTime"] = -1
            seeding["RemoveTorrent"] = -1
            seeding["HitAndRunMode"] = False
            seeding["MinSeedRatio"] = 1.0
            seeding["MinSeedingTimeDays"] = 0
            seeding["HitAndRunPartialSeedRatio"] = 1.0
            seeding["TrackerUpdateBuffer"] = 0
            qbit_section["CategorySeeding"] = seeding
            changes_made = True
            logger.info("Added CategorySeeding configuration to [qBit]")

    # Migrate additional qBit instances (qBit-XXX)
    for section in config.config.keys():
        if str(section).startswith("qBit-"):
            qbit_section = config.config[str(section)]
            if "ManagedCategories" not in qbit_section:
                qbit_section["ManagedCategories"] = []
                changes_made = True
                logger.info(f"Added ManagedCategories = [] to [{section}]")

            if "CategorySeeding" not in qbit_section:
                seeding = table()
                seeding["DownloadRateLimitPerTorrent"] = -1
                seeding["UploadRateLimitPerTorrent"] = -1
                seeding["MaxUploadRatio"] = -1
                seeding["MaxSeedingTime"] = -1
                seeding["RemoveTorrent"] = -1
                seeding["HitAndRunMode"] = False
                seeding["MinSeedRatio"] = 1.0
                seeding["MinSeedingTimeDays"] = 0
                seeding["HitAndRunPartialSeedRatio"] = 1.0
                seeding["TrackerUpdateBuffer"] = 0
                qbit_section["CategorySeeding"] = seeding
                changes_made = True
                logger.info(f"Added CategorySeeding configuration to [{section}]")

    if changes_made:
        print("Migration v3→v4: Added qBit category management settings")

    return changes_made


def _migrate_hnr_settings(config: MyConfig) -> bool:
    """
    Add Hit and Run protection settings to existing configs.

    Migration runs if:
    - ConfigVersion < "5.8.8"

    Adds HnR fields to SeedingMode, Trackers, and CategorySeeding sections for all Arr and qBit instances.

    Returns:
        True if changes were made, False otherwise
    """
    import logging

    from qBitrr.config_version import _parse_version, get_config_version

    logger = logging.getLogger(__name__)

    current_version = _parse_version(get_config_version(config))
    if current_version >= _parse_version("5.8.8"):
        return False  # Already migrated

    changes_made = False
    arr_types = ["Radarr", "Sonarr", "Lidarr", "Animarr"]
    hnr_seeding_defaults = {
        "HitAndRunMode": False,
        "MinSeedRatio": 1.0,
        "MinSeedingTimeDays": 0,
        "HitAndRunPartialSeedRatio": 1.0,
        "TrackerUpdateBuffer": 0,
    }

    # Add HnR fields to Arr SeedingMode and Tracker sections
    for arr_type in arr_types:
        for key in list(config.config.keys()):
            if not str(key).startswith(arr_type):
                continue

            if "Torrent" in config.config.get(str(key), {}):
                torrent_section = config.config[str(key)]["Torrent"]

                if "SeedingMode" in torrent_section:
                    seeding = torrent_section["SeedingMode"]
                    for field, default in hnr_seeding_defaults.items():
                        if field not in seeding:
                            seeding[field] = default
                            changes_made = True

                # Add HnR fields to each tracker
                if "Trackers" in torrent_section:
                    trackers = torrent_section["Trackers"]
                    if isinstance(trackers, list):
                        for tracker in trackers:
                            for field, default in hnr_seeding_defaults.items():
                                if field not in tracker:
                                    tracker[field] = default
                                    changes_made = True

    # Add HnR fields to qBit CategorySeeding sections
    for key in list(config.config.keys()):
        if str(key) == "qBit" or str(key).startswith("qBit-"):
            qbit_section = config.config[str(key)]
            if "CategorySeeding" in qbit_section:
                cat_seeding = qbit_section["CategorySeeding"]
                for field, default in hnr_seeding_defaults.items():
                    if field not in cat_seeding:
                        cat_seeding[field] = default
                        changes_made = True

    if changes_made:
        print("Migration: Added Hit and Run protection settings")
        logger.info("Added Hit and Run protection settings to config")

    return changes_made


def _normalize_theme_value(value: Any) -> str:
    """
    Normalize theme value to always be 'Light' or 'Dark' (case insensitive input).
    """
    if value is None:
        return "Dark"
    value_str = str(value).strip().lower()
    if value_str == "light":
        return "Light"
    elif value_str == "dark":
        return "Dark"
    else:
        # Default to Dark if invalid value
        return "Dark"


def _normalize_view_density_value(value: Any) -> str:
    """
    Normalize view density value to always be 'Comfortable' or 'Compact' (case insensitive input).
    """
    if value is None:
        return "Comfortable"
    value_str = str(value).strip().lower()
    if value_str == "comfortable":
        return "Comfortable"
    elif value_str == "compact":
        return "Compact"
    else:
        # Default to Comfortable if invalid value
        return "Comfortable"


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
        ("IgnoreTorrentsYoungerThan", 600),
        ("PingURLS", ["one.one.one.one", "dns.google.com"]),
        ("FFprobeAutoUpdate", True),
        ("AutoUpdateEnabled", False),
        ("AutoUpdateCron", "0 3 * * 0"),
    ]

    for key, default in settings_defaults:
        if ensure_value("Settings", key, default):
            changed = True

    # Validate WebUI section
    webui_defaults = [
        ("Host", "0.0.0.0"),
        ("Port", 6969),
        ("Token", ""),
        ("LiveArr", True),
        ("GroupSonarr", True),
        ("GroupLidarr", True),
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
    arr_types = ["Radarr", "Sonarr", "Lidarr", "Animarr"]
    entry_search_defaults = {
        "QualityProfileMappings": inline_table(),
        "ForceResetTempProfiles": False,
        "TempProfileResetTimeoutMinutes": 0,
        "ProfileSwitchRetryAttempts": 3,
    }

    for arr_type in arr_types:
        for key in list(config.config.keys()):
            if not str(key).startswith(arr_type):
                continue

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

    return changed


def apply_config_migrations(config: MyConfig) -> None:
    """
    Apply all configuration migrations and validations.
    Saves the config if any changes were made.
    """
    from qBitrr.config_version import (
        EXPECTED_CONFIG_VERSION,
        _parse_version,
        backup_config,
        get_config_version,
        set_config_version,
        validate_config_version,
    )

    changes_made = False

    # Validate config version
    is_valid, validation_result = validate_config_version(config)

    if not is_valid:
        # Config version is newer than expected - log error but continue
        print(f"WARNING: {validation_result}")
        print("Continuing with potentially incompatible config...")

    # Check if migration is needed
    current_version = _parse_version(get_config_version(config))
    expected_version = _parse_version(EXPECTED_CONFIG_VERSION)
    needs_migration = current_version < expected_version

    if needs_migration:
        print(f"Config schema upgrade needed ({current_version} -> {expected_version})")
        # Create backup before migration
        backup_path = backup_config(config.path)
        if backup_path:
            print(f"Config backup created: {backup_path}")
        else:
            print("WARNING: Could not create config backup, proceeding with migration anyway")

    # Apply migrations in order
    if _migrate_webui_config(config):
        changes_made = True

    # Migrate quality profile mappings from list to dict format (< 0.0.2)
    if _migrate_quality_profile_mappings(config):
        changes_made = True

    # Add process auto-restart settings (< 0.0.3)
    if _migrate_process_restart_settings(config):
        changes_made = True

    # Add qBit category management settings (< 0.0.4)
    if _migrate_qbit_category_settings(config):
        changes_made = True

    # Add Hit and Run protection settings (< 5.9.0)
    if _migrate_hnr_settings(config):
        changes_made = True

    # Validate and fill config (this also ensures ConfigVersion field exists)
    if _validate_and_fill_config(config):
        changes_made = True

    # Update config version if migration was needed
    if needs_migration and current_version < expected_version:
        set_config_version(config, EXPECTED_CONFIG_VERSION)
        changes_made = True

    # Save if changes were made
    if changes_made:
        config.save()
        print("Configuration has been updated with migrations and defaults.")


def _write_config_file(docker: bool = False) -> pathlib.Path:
    doc = generate_doc()
    config_file = HOME_PATH.joinpath("config.toml")
    if docker:
        if config_file.exists():
            print(f"{config_file} already exists, keeping current configuration.")
            return config_file
    elif config_file.exists():
        print(f"{config_file} already exists, File is not being replaced.")
        config_file = pathlib.Path.cwd().joinpath("config_new.toml")
    config = MyConfig(config_file, config=doc)
    config.save()
    print(f'New config file has been saved to "{config_file}"')
    return config_file
