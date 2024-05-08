from __future__ import annotations

import pathlib
from functools import reduce
from typing import Any, TypeVar

from tomlkit import comment, document, nl, parse, table
from tomlkit.items import Table
from tomlkit.toml_document import TOMLDocument

from qBitrr.env_config import ENVIRO_CONFIG
from qBitrr.home_path import APPDATA_FOLDER, HOME_PATH

T = TypeVar("T")


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
    _add_qbit_section(config)
    _add_category_sections(config)
    return config


def _add_settings_section(config: TOMLDocument):
    settings = table()
    _gen_default_line(
        settings,
        "Level of logging; One of CRITICAL, ERROR, WARNING, NOTICE, INFO, DEBUG, TRACE",
        "ConsoleLevel",
        ENVIRO_CONFIG.settings.console_level or "INFO",
    )
    _gen_default_line(
        settings,
        "Enable logging to files",
        "Logging",
        ENVIRO_CONFIG.settings.logging or True,
    )
    _gen_default_line(
        settings,
        "Folder where your completed downloads are put into. Can be found in qBitTorrent -> Options -> Downloads -> Default Save Path (Please note, replace all '\\' with '/')",
        "CompletedDownloadFolder",
        ENVIRO_CONFIG.settings.completed_download_folder or "CHANGE_ME",
    )
    _gen_default_line(
        settings,
        "The desired amount of free space in the downloads directory [K=kilobytes, M=megabytes, G=gigabytes, T=terabytes] (set to -1 to disable)",
        "FreeSpace",
        ENVIRO_CONFIG.settings.free_space or "-1",
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
        True if ENVIRO_CONFIG.settings.ping_urls is None else ENVIRO_CONFIG.settings.ping_urls,
    )
    config.add("Settings", settings)


def _add_qbit_section(config: TOMLDocument):
    qbit = table()
    _gen_default_line(
        qbit,
        [
            "If this is enable qBitrr can run in a headless mode where it will only process searches.",
            "If media search is enabled in their individual categories",
            "This is useful if you use for example Sabnzbd/NZBGet for downloading content but still want the faster media searches provided by qbit",
        ],
        "Disabled",
        False if ENVIRO_CONFIG.qbit.disabled is None else ENVIRO_CONFIG.qbit.disabled,
    )
    _gen_default_line(
        qbit,
        'qBit WebUI Port - Can be found in Options > Web UI (called "IP Address")',
        "Host",
        ENVIRO_CONFIG.qbit.host or "CHANGE_ME",
    )
    _gen_default_line(
        qbit,
        'qBit WebUI Port - Can be found in Options > Web UI (called "Port" on top right corner of the window)',
        "Port",
        ENVIRO_CONFIG.qbit.port or 8080,
    )
    _gen_default_line(
        qbit,
        "qBit WebUI Authentication - Can be found in Options > Web UI > Authentication",
        "UserName",
        ENVIRO_CONFIG.qbit.username or "CHANGE_ME",
    )
    _gen_default_line(
        qbit,
        'If you set "Bypass authentication on localhost or whitelisted IPs" remove this field.',
        "Password",
        ENVIRO_CONFIG.qbit.password or "CHANGE_ME",
    )
    config.add("qBit", qbit)


def _add_category_sections(config: TOMLDocument):
    for c in ["Sonarr-TV", "Sonarr-Anime", "Radarr-1080", "Radarr-4K"]:
        _gen_default_cat(c, config)


def _gen_default_cat(category: str, config: TOMLDocument):
    cat_default = table()
    cat_default.add(nl())
    _gen_default_line(
        cat_default, "Toggle whether to manage the Servarr instance torrents.", "Managed", True
    )
    _gen_default_line(
        cat_default,
        "The URL used to access Servarr interface "
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
        cat_default,
        "The Servarr's Import Mode(one of Move, Copy or Auto)",
        "importMode",
        "Auto",
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
    if "anime" not in category.lower():
        _gen_default_line(
            torrent_table,
            [
                "These regex values will match any folder where the full name matches the specified values here, comma separated strings.",
                "These regex need to be escaped, that's why you see so many backslashes.",
            ],
            "FolderExclusionRegex",
            [
                r"\bextras?\b",
                r"\bfeaturettes?\b",
                r"\bsamples?\b",
                r"\bscreens?\b",
                r"\bnc(ed|op)?(\\d+)?\b",
            ],
        )
    else:
        _gen_default_line(
            torrent_table,
            [
                "These regex values will match any folder where the full name matches the specified values here, comma separated strings.",
                "These regex need to be escaped, that's why you see so many backslashes.",
            ],
            "FolderExclusionRegex",
            [
                r"\bextras?\b",
                r"\bfeaturettes?\b",
                r"\bsamples?\b",
                r"\bscreens?\b",
                r"\bspecials?\b",
                r"\bova\b",
                r"\bnc(ed|op)?(\\d+)?\b",
            ],
        )
    _gen_default_line(
        torrent_table,
        [
            "These regex values will match any folder where the full name matches the specified values here, comma separated strings.",
            "These regex need to be escaped, that's why you see so many backslashes.",
        ],
        "FileNameExclusionRegex",
        [
            r"\bncop\\d+?\b",
            r"\bnced\\d+?\b",
            r"\bsample\b",
            r"brarbg.com\b",
            r"\btrailer\b",
            r"music video",
            r"comandotorrents.com",
        ],
    )
    _gen_default_line(
        torrent_table,
        "Only files with these extensions will be allowed to be downloaded, comma separated strings or regex, leave it empty to allow all extensions",
        "FileExtensionAllowlist",
        [".mp4", ".mkv", ".sub", ".ass", ".srt", ".!qB", ".parts"],
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
            tracker_table,
            "Set this value to -1 to disabled it",
            "DownloadRateLimit",
            -1,
        )
        tracker_table.add(comment("Set the maximum allowed upload rate for torrents"))
        _gen_default_line(
            tracker_table,
            "Set this value to -1 to disabled it",
            "UploadRateLimit",
            -1,
        )
        tracker_table.add(comment("Set the maximum allowed download rate for torrents"))
        _gen_default_line(
            tracker_table,
            "Set this value to -1 to disabled it",
            "MaxUploadRatio",
            -1,
        )
        tracker_table.add(comment("Set the maximum allowed download rate for torrents"))
        _gen_default_line(
            tracker_table,
            "Set this value to -1 to disabled it",
            "MaxSeedingTime",
            -1,
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
    _gen_default_line(
        search_table,
        "Should search for specials episodes? (Season 00)",
        "AlsoSearchSpecials",
        False,
    )
    if "sonarr" in category.lower():
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
            [
                "Radarr has a default of 3 simultaneous tasks, which can be increased up to 10 tasks",
                'If you set the environment variable of "THREAD_LIMIT" to a number between and including 2-10',
                "Radarr devs have stated that this is an unsupported feature so you will not get any support for doing so from them.",
                "That being said I've been daily driving 10 simultaneous tasks for quite a while now with no issues.",
            ],
            "SearchLimit",
            5,
        )
    _gen_default_line(
        search_table,
        "It will order searches by the year the EPISODE was first aired",
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
        search_table, "Delay between request searches in seconds", "SearchRequestsEvery", 300
    )
    _gen_default_line(
        search_table,
        "Search movies which already have a file in the database in hopes of finding a "
        "better quality version.",
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
    if "sonarr" in category.lower():
        _gen_default_line(
            search_table,
            "Search by series instead of by episode (This ignored the QualityUnmetSearch and CustomFormatUnmetSearch setting)",
            "SearchBySeries",
            True,
        )
        _gen_default_line(
            search_table,
            "Prioritize Today's releases (Similar effect as RSS Sync, where it searches "
            "today's release episodes first, only works on Sonarr).",
            "PrioritizeTodaysReleases",
            True,
        )
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
        "Ombi URI (Note that this has to be the instance of Ombi which manage the Arr instance request (If you have multiple Ombi instances)",
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
    _gen_default_line(overseerr_table, "Overseerr's URI", "OverseerrURI", "CHANGE_ME")
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
                    err,
                    "Possible permissions while attempting to read the config file.\n",
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


def _write_config_file(docker=False) -> pathlib.Path:
    doc = generate_doc()
    file_name = "config.rename_me.toml" if docker else "config.toml"
    CONFIG_FILE = HOME_PATH.joinpath(file_name)
    if CONFIG_FILE.exists() and not docker:
        print(f"{CONFIG_FILE} already exists, File is not being replaced.")
        CONFIG_FILE = pathlib.Path.cwd().joinpath("config_new.toml")
    config = MyConfig(CONFIG_FILE, config=doc)
    config.save()
    print(f'New config file has been saved to "{CONFIG_FILE}"')
    return CONFIG_FILE
