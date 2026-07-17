"""Arr section template fields for the shared config field registry.

Category-specific defaults (exclusion regexes, error messages, ``Is4K``,
``Category``) are applied in :mod:`qBitrr.gen_config.sections` via
``filter_arr_fields`` + overrides so emitted TOML stays identical.
``arr_kinds`` encodes Sonarr/Radarr/Lidarr conditionals declaratively.
"""

from __future__ import annotations

from tomlkit import inline_table

from qBitrr.gen_config.fields import ConfigField

_SONARR = frozenset({"sonarr"})
_RADARR = frozenset({"radarr"})
_NOT_LIDARR = frozenset({"sonarr", "radarr"})


def _empty_quality_profile_mappings():
    """Empty inline table matching historical ``generate_doc`` emission."""
    return inline_table()


_REMOVE_TRACKER_MESSAGES = (
    "skipping tracker announce (unreachable)",
    "No such host is known",
    "unsupported URL protocol",
    "info hash is not authorized with this tracker",
)


def _default_remove_tracker_messages() -> list[str]:
    return list(_REMOVE_TRACKER_MESSAGES)


ARR_FIELDS: tuple[ConfigField, ...] = (
    ConfigField(
        ("Managed",),
        True,
        "Toggle whether to manage the Servarr instance torrents.",
        label="Managed",
        kind="checkbox",
    ),
    ConfigField(
        ("URI",),
        "CHANGE_ME",
        "The URL used to access Servarr interface eg. http://ip:port"
        "(if you use a domain enter the domain without a port)",
        label="URI",
        required=True,
    ),
    ConfigField(
        ("APIKey",),
        "CHANGE_ME",
        "The Servarr API Key, Can be found it Settings > General > Security",
        label="API Key",
        kind="password",
        secure=True,
        required=True,
    ),
    ConfigField(
        ("SkipTLSVerify",),
        False,
        (
            "If true, do not verify TLS for this Servarr API (HTTPS). Does not affect Overseerr/Ombi.",
            "Disables MITM protection for that connection.",
        ),
        label="Skip TLS Verify",
        kind="checkbox",
        ui_expose=False,
    ),
    ConfigField(
        ("Category",),
        "CHANGE_ME",
        "Category applied by Servarr to torrents in qBitTorrent, can be found in Settings > Download Clients > qBit > Category",
        label="Category",
        required=True,
    ),
    ConfigField(
        ("ReSearch",),
        True,
        "Toggle whether to send a query to Servarr to search any failed torrents",
        label="Re-search",
        kind="checkbox",
    ),
    ConfigField(
        ("importMode",),
        "Auto",
        "The Servarr's Import Mode(one of Move, Copy or Auto)",
        label="Import Mode",
        kind="select",
        options=("Move", "Copy", "Auto"),
    ),
    ConfigField(
        ("RssSyncTimer",),
        1,
        "Timer to call RSSSync (In minutes) - Set to 0 to disable (Values below 5 can cause errors for maximum retires)",
        label="RSS Sync Timer",
        kind="duration",
        native_unit="minutes",
    ),
    ConfigField(
        ("RefreshDownloadsTimer",),
        1,
        "Timer to call RefreshDownloads to update the queue. (In minutes) - Set to 0 to disable (Values below 5 can cause errors for maximum retires)",
        label="Refresh Downloads Timer",
        kind="duration",
        native_unit="minutes",
    ),
    ConfigField(
        ("ArrErrorCodesToBlocklist",),
        [],
        (
            "Error messages shown my the Arr instance which should be considered failures.",
            "This entry should be a list, leave it empty if you want to disable this error handling.",
            "If enabled qBitrr will remove the failed files and tell the Arr instance the download failed",
        ),
        label="Arr Error Codes To Blocklist",
        kind="tags",
    ),
    # EntrySearch
    ConfigField(
        ("EntrySearch", "SearchMissing"),
        True,
        "Should search for Missing files?",
        label="Search Missing",
        kind="checkbox",
    ),
    ConfigField(
        ("EntrySearch", "AlsoSearchSpecials"),
        False,
        "Should search for specials episodes? (Season 00)",
        label="Also Search Specials",
        kind="checkbox",
        arr_kinds=_SONARR,
    ),
    ConfigField(
        ("EntrySearch", "Unmonitored"),
        False,
        "Should search for unmonitored media?",
        label="Unmonitored",
        kind="checkbox",
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "SearchLimit"),
        5,
        "Maximum allowed Searches at any one point",
        label="Search Limit",
        kind="number",
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "SearchByYear"),
        True,
        "Order searches by year",
        label="Search By Year",
        kind="checkbox",
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "SearchInReverse"),
        False,
        "Reverse search order (Start searching oldest to newest)",
        label="Search In Reverse",
        kind="checkbox",
    ),
    ConfigField(
        ("EntrySearch", "SearchRequestsEvery"),
        300,
        "Delay (in seconds) between checking for new Overseerr/Ombi requests. Does NOT affect delay between individual search commands (use Settings.SearchLoopDelay for that).",
        label="Search Requests Every",
        kind="duration",
        native_unit="seconds",
    ),
    ConfigField(
        ("EntrySearch", "DoUpgradeSearch"),
        False,
        "Search media which already have a file in hopes of finding a better quality version.",
        label="Do Upgrade Search",
        kind="checkbox",
    ),
    ConfigField(
        ("EntrySearch", "QualityUnmetSearch"),
        False,
        "Do a quality unmet search for existing entries.",
        label="Quality Unmet Search",
        kind="checkbox",
    ),
    ConfigField(
        ("EntrySearch", "CustomFormatUnmetSearch"),
        False,
        "Do a minimum custom format score unmet search for existing entries.",
        label="Custom Format Unmet Search",
        kind="checkbox",
    ),
    ConfigField(
        ("EntrySearch", "ForceMinimumCustomFormat"),
        False,
        "Automatically remove torrents that do not mee the minimum custom format score.",
        label="Force Minimum Custom Format",
        kind="checkbox",
    ),
    ConfigField(
        ("EntrySearch", "SearchAgainOnSearchCompletion"),
        True,
        "Once you have search all files on your specified year range restart the loop and search again.",
        label="Search Again On Search Completion",
        kind="checkbox",
    ),
    ConfigField(
        ("EntrySearch", "UseTempForMissing"),
        False,
        "Use Temp profile for missing",
        label="Use Temp For Missing",
        kind="checkbox",
    ),
    ConfigField(
        ("EntrySearch", "KeepTempProfile"),
        False,
        "Don't change back to main profile",
        label="Keep Temp Profile",
        kind="checkbox",
    ),
    ConfigField(
        ("EntrySearch", "QualityProfileMappings"),
        _empty_quality_profile_mappings,
        (
            "Quality profile mappings for temp profile switching (Main Profile Name -> Temp Profile Name)",
            "Profile names must match exactly as they appear in your Arr instance",
            'Example: QualityProfileMappings = {"HD-1080p" = "SD", "HD-720p" = "SD"}',
        ),
        label="Quality Profile Mappings",
        kind="mapping",
        ui_expose=False,
    ),
    ConfigField(
        ("EntrySearch", "ForceResetTempProfiles"),
        False,
        "Reset all items using temp profiles to their original main profile on qBitrr startup",
        label="Force Reset Temp Profiles",
        kind="checkbox",
    ),
    ConfigField(
        ("EntrySearch", "TempProfileResetTimeoutMinutes"),
        0,
        "Timeout in minutes after which items with temp profiles are automatically reset to main profile (0 = disabled)",
        label="Temp Profile Reset Timeout Minutes",
        kind="number",
    ),
    ConfigField(
        ("EntrySearch", "ProfileSwitchRetryAttempts"),
        3,
        "Number of retry attempts for profile switch API calls (default: 3)",
        label="Profile Switch Retry Attempts",
        kind="number",
    ),
    ConfigField(
        ("EntrySearch", "SearchBySeries"),
        "smart",
        (
            "Search mode: true (always series search), false (always episode search), or 'smart' (automatic)",
            "Smart mode: uses series search for entire seasons/series, episode search for single episodes",
            "(Series search ignores QualityUnmetSearch and CustomFormatUnmetSearch settings)",
        ),
        label="Search By Series",
        kind="select",
        options=("smart", "true", "false"),
        arr_kinds=_SONARR,
    ),
    ConfigField(
        ("EntrySearch", "PrioritizeTodaysReleases"),
        True,
        "Prioritize Today's releases (Similar effect as RSS Sync, where it searches "
        "today's release episodes first, only works on Sonarr).",
        label="Prioritize Todays Releases",
        kind="checkbox",
        arr_kinds=_SONARR,
    ),
    # Ombi / Overseerr
    ConfigField(
        ("EntrySearch", "Ombi", "SearchOmbiRequests"),
        False,
        "Search Ombi for pending requests (Will only work if 'SearchMissing' is enabled.)",
        label="Search Ombi Requests",
        kind="checkbox",
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "Ombi", "OmbiURI"),
        "CHANGE_ME",
        "Ombi URI eg. http://ip:port (Note that this has to be the instance of Ombi which manage the Arr instance request (If you have multiple Ombi instances)",
        label="Ombi URI",
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "Ombi", "OmbiAPIKey"),
        "CHANGE_ME",
        "Ombi's API Key",
        label="Ombi API Key",
        kind="password",
        secure=True,
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "Ombi", "ApprovedOnly"),
        True,
        "Only process approved requests",
        label="Ombi Approved Only",
        kind="checkbox",
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "Ombi", "SkipTLSVerify"),
        False,
        ("If true, do not verify TLS for Ombi HTTPS (self-signed). Disables MITM protection.",),
        label="Ombi Skip TLS Verify",
        kind="checkbox",
        ui_expose=False,
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "Overseerr", "SearchOverseerrRequests"),
        False,
        (
            "Search Overseerr for pending requests (Will only work if 'SearchMissing' is enabled.)",
            "If this and Ombi are both enable, Ombi will be ignored",
        ),
        label="Search Overseerr Requests",
        kind="checkbox",
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "Overseerr", "OverseerrURI"),
        "CHANGE_ME",
        "Overseerr's URI eg. http://ip:port",
        label="Overseerr URI",
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "Overseerr", "OverseerrAPIKey"),
        "CHANGE_ME",
        "Overseerr's API Key",
        label="Overseerr API Key",
        kind="password",
        secure=True,
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "Overseerr", "ApprovedOnly"),
        True,
        "Only process approved requests",
        label="Overseerr Approved Only",
        kind="checkbox",
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "Overseerr", "SkipTLSVerify"),
        False,
        (
            "If true, do not verify TLS for Overseerr HTTPS (self-signed). Disables MITM protection.",
        ),
        label="Overseerr Skip TLS Verify",
        kind="checkbox",
        ui_expose=False,
        arr_kinds=_NOT_LIDARR,
    ),
    ConfigField(
        ("EntrySearch", "Overseerr", "Is4K"),
        False,
        "Only for 4K Instances",
        label="Is 4K",
        kind="checkbox",
        arr_kinds=_NOT_LIDARR,
    ),
    # Torrent
    ConfigField(
        ("Torrent", "CaseSensitiveMatches"),
        False,
        "Set it to regex matches to respect/ignore case.",
        label="Case Sensitive Matches",
        kind="checkbox",
    ),
    ConfigField(
        ("Torrent", "FolderExclusionRegex"),
        [],
        (
            "These regex values will match any folder where the full name matches the specified values here, comma separated strings.",
            "These regex need to be escaped, that's why you see so many backslashes.",
        ),
        label="Folder Exclusion Regex",
        kind="tags",
    ),
    ConfigField(
        ("Torrent", "FileNameExclusionRegex"),
        [],
        (
            "These regex values will match any folder where the full name matches the specified values here, comma separated strings.",
            "These regex need to be escaped, that's why you see so many backslashes.",
        ),
        label="File Name Exclusion Regex",
        kind="tags",
    ),
    ConfigField(
        ("Torrent", "FileExtensionAllowlist"),
        [],
        "Only files with these extensions will be allowed to be downloaded, comma separated strings or regex, leave it empty to allow all extensions",
        label="File Extension Allowlist",
        kind="tags",
    ),
    ConfigField(
        ("Torrent", "AutoDelete"),
        False,
        "Auto delete files that can't be playable (i.e .exe, .png)",
        label="Auto Delete",
        kind="checkbox",
    ),
    ConfigField(
        ("Torrent", "IgnoreTorrentsYoungerThan"),
        180,
        "Ignore Torrents which are younger than this value (in seconds: 600 = 10 Minutes)",
        label="Ignore Torrents Younger Than",
        kind="duration",
        native_unit="seconds",
    ),
    ConfigField(
        ("Torrent", "MaximumETA"),
        -1,
        (
            "Maximum allowed remaining ETA for torrent completion (in seconds: 3600 = 1 Hour)",
            "Note that if you set the MaximumETA on a tracker basis that value is favoured over this value",
        ),
        label="Maximum ETA",
        kind="duration",
        native_unit="seconds",
        allow_negative=True,
    ),
    ConfigField(
        ("Torrent", "MaximumDeletablePercentage"),
        0.99,
        "Do not delete torrents with higher completion percentage than this setting (0.5 = 50%, 1.0 = 100%)",
        label="Maximum Deletable Percentage",
        kind="number",
    ),
    ConfigField(
        ("Torrent", "DoNotRemoveSlow"),
        True,
        "Ignore slow torrents.",
        label="Do Not Remove Slow",
        kind="checkbox",
    ),
    ConfigField(
        ("Torrent", "StalledDelay"),
        15,
        "Maximum allowed time for allowed stalled torrents in minutes (-1 = Disabled, 0 = Infinite)",
        label="Stalled Delay",
        kind="duration",
        native_unit="minutes",
        allow_negative=True,
    ),
    ConfigField(
        ("Torrent", "ReSearchStalled"),
        False,
        "Re-search stalled torrents when StalledDelay is enabled and you want to re-search before removing the stalled torrent, or only after the torrent is removed.",
        label="Re-Search Stalled",
        kind="checkbox",
    ),
    # SeedingMode
    ConfigField(
        ("Torrent", "SeedingMode", "DownloadRateLimitPerTorrent"),
        -1,
        (
            "Set the maximum allowed download rate for torrents",
            "Set this value to -1 to disabled it",
            "Note that if you set the DownloadRateLimit on a tracker basis that value is favoured over this value",
        ),
        label="Download Rate Limit",
        kind="number",
    ),
    ConfigField(
        ("Torrent", "SeedingMode", "UploadRateLimitPerTorrent"),
        -1,
        (
            "Set the maximum allowed upload rate for torrents",
            "Set this value to -1 to disabled it",
            "Note that if you set the UploadRateLimit on a tracker basis that value is favoured over this value",
        ),
        label="Upload Rate Limit",
        kind="number",
    ),
    ConfigField(
        ("Torrent", "SeedingMode", "MaxUploadRatio"),
        -1,
        (
            "Set the maximum allowed upload ratio for torrents",
            "Set this value to -1 to disabled it",
            "Note that if you set the MaxUploadRatio on a tracker basis that value is favoured over this value",
        ),
        label="Max Upload Ratio",
        kind="number",
    ),
    ConfigField(
        ("Torrent", "SeedingMode", "MaxSeedingTime"),
        -1,
        (
            "Set the maximum seeding time in seconds for torrents",
            "Set this value to -1 to disabled it",
            "Note that if you set the MaxSeedingTime on a tracker basis that value is favoured over this value",
        ),
        label="Max Seeding Time",
        kind="duration",
        native_unit="seconds",
        allow_negative=True,
    ),
    ConfigField(
        ("Torrent", "SeedingMode", "RemoveTorrent"),
        -1,
        "Remove torrent condition (-1=Do not remove, 1=Remove on MaxUploadRatio, 2=Remove on MaxSeedingTime, 3=Remove on MaxUploadRatio or MaxSeedingTime, 4=Remove on MaxUploadRatio and MaxSeedingTime)",
        label="Remove Torrent",
        kind="select",
    ),
    ConfigField(
        ("Torrent", "SeedingMode", "RemoveDeadTrackers"),
        False,
        "Enable if you want to remove dead trackers",
        label="Remove Dead Trackers",
        kind="checkbox",
    ),
    ConfigField(
        ("Torrent", "SeedingMode", "RemoveTrackerWithMessage"),
        _default_remove_tracker_messages,
        'If "RemoveDeadTrackers" is set to true then remove trackers with the following messages',
        label="Remove Tracker With Message",
        kind="tags",
    ),
)

__all__ = ["ARR_FIELDS"]
