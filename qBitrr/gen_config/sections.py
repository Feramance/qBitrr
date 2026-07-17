from __future__ import annotations

from typing import Any, TypeVar

from tomlkit import comment, document, inline_table, nl, table
from tomlkit.items import Table
from tomlkit.toml_document import TOMLDocument

from qBitrr.env_config import ENVIRO_CONFIG
from qBitrr.home_path import APPDATA_FOLDER, HOME_PATH

T = TypeVar("T")

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


def _add_web_settings_section(config: TOMLDocument):
    web_settings = table()
    _gen_default_line(
        web_settings,
        "WebUI listen host (default 0.0.0.0; use 127.0.0.1 for localhost-only)",
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
        "Require login on new installs; user is prompted to create credentials. Set to true to disable auth (backward compat for configs without this key).",
        "AuthDisabled",
        False,
    )
    _gen_default_line(
        web_settings,
        [
            "Set to true when the WebUI is reached over HTTPS (e.g. behind a reverse proxy).",
            "When true, the app trusts X-Forwarded-Proto and sets the session cookie as Secure.",
            "Leave false for plain HTTP.",
        ],
        "BehindHttpsProxy",
        False,
    )
    _gen_default_line(
        web_settings,
        [
            "Public URL path prefix when served behind a reverse proxy (no trailing slash).",
            'Example: "/qbitrr" serves the UI at https://host/qbitrr/ui. Leave empty for site root.',
        ],
        "UrlBase",
        "",
    )
    _gen_default_line(
        web_settings,
        "Enable username/password login",
        "LocalAuthEnabled",
        False,
    )
    _gen_default_line(
        web_settings,
        "Enable OIDC login",
        "OIDCEnabled",
        False,
    )
    _gen_default_line(
        web_settings,
        "Username for local auth",
        "Username",
        "",
    )
    _gen_default_line(
        web_settings,
        "BCrypt password hash — set via the WebUI 'Set Password' button, never plain text",
        "PasswordHash",
        "",
    )
    oidc_settings = table()
    _gen_default_line(
        oidc_settings,
        "OIDC issuer/authority URL (e.g. https://auth.example.com/application/o/qbitrr)",
        "Authority",
        "",
    )
    _gen_default_line(
        oidc_settings,
        "OAuth2 client ID",
        "ClientId",
        "",
    )
    _gen_default_line(
        oidc_settings,
        "OAuth2 client secret",
        "ClientSecret",
        "",
    )
    _gen_default_line(
        oidc_settings,
        "Space-separated OIDC scopes",
        "Scopes",
        "openid profile",
    )
    _gen_default_line(
        oidc_settings,
        "OIDC callback path (must match IdP redirect URI)",
        "CallbackPath",
        "/signin-oidc",
    )
    _gen_default_line(
        oidc_settings,
        "Require HTTPS for IdP metadata (set false only for local dev OIDC)",
        "RequireHttpsMetadata",
        True,
    )
    web_settings.add("OIDC", oidc_settings)
    _gen_default_line(
        web_settings,
        "Enable live updates for Arr views",
        "LiveArr",
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
        "5.12.12",
    )
    _gen_default_line(
        settings,
        "Level of logging; One of CRITICAL, ERROR, WARNING, NOTICE, INFO, DEBUG, TRACE",
        "ConsoleLevel",
        _default(ENVIRO_CONFIG.settings.console_level, "INFO"),
    )
    _gen_default_line(
        settings,
        "Enable logging to files",
        "Logging",
        _default(ENVIRO_CONFIG.settings.logging, True),
    )
    _gen_default_line(
        settings,
        "Folder where your completed downloads are put into. Can be found in qBitTorrent -> Options -> Downloads -> Default Save Path (Please note, replace all '\\' with '/')",
        "CompletedDownloadFolder",
        _default(ENVIRO_CONFIG.settings.completed_download_folder, "CHANGE_ME"),
    )
    _gen_default_line(
        settings,
        "The desired amount of free space in the downloads directory [K=kilobytes, M=megabytes, G=gigabytes, T=terabytes] (set to -1 to disable, this bypasses AutoPauseResume)",
        "FreeSpace",
        _default(ENVIRO_CONFIG.settings.free_space, "-1"),
    )
    _gen_default_line(
        settings,
        "Folder where the free space handler will check for free space (Please note, replace all '' with '/')",
        "FreeSpaceFolder",
        _default(ENVIRO_CONFIG.settings.free_space_folder, "CHANGE_ME"),
    )
    _gen_default_line(
        settings,
        "Enable automation of pausing and resuming torrents as needed (Required enabled for the FreeSpace logic to function)",
        "AutoPauseResume",
        _default(ENVIRO_CONFIG.settings.auto_pause_resume, True),
    )
    _gen_default_line(
        settings,
        "Time to sleep for if there is no internet (in seconds: 600 = 10 Minutes)",
        "NoInternetSleepTimer",
        _default(ENVIRO_CONFIG.settings.no_internet_sleep_timer, 15),
    )
    _gen_default_line(
        settings,
        "Time to sleep between reprocessing torrents (in seconds: 600 = 10 Minutes)",
        "LoopSleepTimer",
        _default(ENVIRO_CONFIG.settings.loop_sleep_timer, 5),
    )
    _gen_default_line(
        settings,
        "Time to sleep between posting search commands (in seconds: 600 = 10 Minutes)",
        "SearchLoopDelay",
        _default(ENVIRO_CONFIG.settings.search_loop_delay, -1),
    )
    _gen_default_line(
        settings,
        "Add torrents to this category to mark them as failed",
        "FailedCategory",
        _default(ENVIRO_CONFIG.settings.failed_category, "failed"),
    )
    _gen_default_line(
        settings,
        "Add torrents to this category to trigger them to be rechecked properly",
        "RecheckCategory",
        _default(ENVIRO_CONFIG.settings.recheck_category, "recheck"),
    )
    _gen_default_line(
        settings, "Tagless operation", "Tagless", _default(ENVIRO_CONFIG.settings.tagless, False)
    )
    _gen_default_line(
        settings,
        [
            "Ignore Torrents which are younger than this value (in seconds: 600 = 10 Minutes)",
            "Only applicable to Re-check and failed categories",
        ],
        "IgnoreTorrentsYoungerThan",
        _default(ENVIRO_CONFIG.settings.ignore_torrents_younger_than, 180),
    )
    _gen_default_line(
        settings,
        [
            "URL to be pinged to check if you have a valid internet connection",
            "These will be pinged a **LOT** make sure the service is okay with you sending all the continuous pings.",
        ],
        "PingURLS",
        _default(ENVIRO_CONFIG.settings.ping_urls, ["one.one.one.one", "dns.google.com"]),
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
        _default(ENVIRO_CONFIG.settings.auto_update_cron, "0 3 * * 0"),
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
        _default(ENVIRO_CONFIG.qbit.host, "CHANGE_ME"),
    )
    _gen_default_line(
        qbit,
        'qbittorrent WebUI Port - Can be found in Options > Web UI (called "Port" on top right corner of the window)',
        "Port",
        _default(ENVIRO_CONFIG.qbit.port, 8080),
    )
    _gen_default_line(
        qbit,
        "qbittorrent WebUI Authentication - Can be found in Options > Web UI > Authentication",
        "UserName",
        _default(ENVIRO_CONFIG.qbit.username, "CHANGE_ME"),
    )
    _gen_default_line(
        qbit,
        'If you set "Bypass authentication on localhost or whitelisted IPs" remove this field.',
        "Password",
        _default(ENVIRO_CONFIG.qbit.password, "CHANGE_ME"),
    )
    _gen_default_line(
        qbit,
        [
            "If true, do not verify TLS certificates for HTTPS WebUI (self-signed certs). "
            "Disables MITM protection for that connection.",
        ],
        "SkipTLSVerify",
        False,
    )
    _gen_default_line(
        qbit,
        [
            "Categories managed directly by this qBit instance (not managed by Arr instances).",
            "These categories will have seeding settings applied according to CategorySeeding configuration.",
            "Subcategory paths use '/' to match qBittorrent (for example 'seed/tleech').",
            "Example: ['downloads', 'private-tracker', 'long-term-seed']",
        ],
        "ManagedCategories",
        [],
    )
    _gen_default_line(
        qbit,
        [
            "When true, configured categories ALSO match torrents in any subcategory beneath them.",
            "Example: setting MatchSubcategories=true with ManagedCategories=['seed'] manages",
            "torrents whose qBit category is 'seed', 'seed/tleech', 'seed/longterm', etc.",
            "When false (default) the qBit category string must match exactly.",
        ],
        "MatchSubcategories",
        False,
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
        [
            "Hit and Run mode: and = require both ratio and time; or = either clears; disabled = no HnR.",
        ],
        "HitAndRunMode",
        "disabled",
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
        "Minimum download percentage before a torrent is considered for HnR (0-100, default 10)",
        "HitAndRunMinimumDownloadPercent",
        10,
    )
    _gen_default_line(
        category_seeding,
        "Minimum ratio for partial downloads (>=HitAndRunMinimumDownloadPercent% but <100% complete)",
        "HitAndRunPartialSeedRatio",
        1.0,
    )
    _gen_default_line(
        category_seeding,
        "Extra seconds buffer for tracker stats lag (0 = disabled)",
        "TrackerUpdateBuffer",
        0,
    )
    _gen_default_line(
        category_seeding,
        "Maximum time stalled downloads can sit before removal, in minutes (-1 = disabled, 0 = infinite).",
        "StalledDelay",
        -1,
    )
    _gen_default_line(
        category_seeding,
        "Ignore torrents younger than this (seconds). Stalled removal also requires last_activity older than this.",
        "IgnoreTorrentsYoungerThan",
        180,
    )
    _gen_qbit_tracker_tables(qbit)

    qbit.add("CategorySeeding", category_seeding)

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
        [
            "If true, do not verify TLS for this Servarr API (HTTPS). Does not affect Overseerr/Ombi.",
            "Disables MITM protection for that connection.",
        ],
        "SkipTLSVerify",
        False,
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
    _gen_default_tracker_tables(category, torrent_table)
    _gen_default_seeding_table(category, torrent_table)

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

    torrent_table.add("SeedingMode", seeding_table)


def _gen_default_tracker_tables(category: str, torrent_table: Table):
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
    _gen_default_line(
        ombi_table,
        [
            "If true, do not verify TLS for Ombi HTTPS (self-signed). Disables MITM protection.",
        ],
        "SkipTLSVerify",
        False,
    )
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
    _gen_default_line(
        overseerr_table,
        [
            "If true, do not verify TLS for Overseerr HTTPS (self-signed). Disables MITM protection.",
        ],
        "SkipTLSVerify",
        False,
    )
    overseerr_table.add(comment("Only for 4K Instances"))
    if "radarr-4k" in category.lower():
        _gen_default_line(overseerr_table, "Only for 4K Instances", "Is4K", True)
    else:
        _gen_default_line(overseerr_table, "Only for 4K Instances", "Is4K", False)
    search_table.add("Overseerr", overseerr_table)
