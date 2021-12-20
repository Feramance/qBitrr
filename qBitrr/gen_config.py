from __future__ import annotations

import pathlib
import sys
from datetime import datetime
from functools import reduce
from typing import Any, TypeVar

from tomlkit import comment, document, nl, parse, table
from tomlkit.items import Table
from tomlkit.toml_document import TOMLDocument

T = TypeVar("T")


def generate_doc() -> TOMLDocument:
    config = document()
    config.add(
        comment(
            'This is a config file for the qBitrr Script - Make sure to change all entries of "CHANGE_ME".'
        )
    )
    config.add(
        comment(
            f"This is a config file should be moved to \"{pathlib.Path().home().joinpath('.config', 'qBitManager', 'config.toml')}\"."
        )
    )
    config.add(nl())
    _add_settings_section(config)
    _add_qbit_section(config)
    _add_category_sections(config)
    return config


def _add_settings_section(config: TOMLDocument):
    settings = table()
    settings.add(
        comment("Level of logging; One of CRITICAL, ERROR, WARNING, NOTICE, INFO, DEBUG, TRACE")
    )
    settings.add("ConsoleLevel", "INFO")
    settings.add(nl())
    settings.add(
        comment(
            "Folder where your completed downloads are put into. Can be found in qBitTorrent -> Options -> Downloads -> Default Save Path"
        )
    )
    settings.add("CompletedDownloadFolder", "CHANGE_ME")
    settings.add(nl())
    settings.add(
        comment("Time to sleep for if there is no internet (in seconds: 600 = 10 Minutes)")
    )
    settings.add("NoInternetSleepTimer", 15)
    settings.add(nl())
    settings.add(
        comment("Time to sleep between reprocessing torrents (in seconds: 600 = 10 Minutes)")
    )
    settings.add("LoopSleepTimer", 5)
    settings.add(nl())
    settings.add(comment("Add torrents to this category to mark them as failed"))
    settings.add("FailedCategory", "failed")
    settings.add(nl())
    settings.add(comment("Add torrents to this category to trigger them to be rechecked properly"))
    settings.add("RecheckCategory", "recheck")
    settings.add(nl())
    settings.add(
        comment("Ignore Torrents which are younger than this value (in seconds: 600 = 10 Minutes)")
    )
    settings.add(comment("Only applicable to Re-check and failed categories"))
    settings.add("IgnoreTorrentsYoungerThan", 180)
    settings.add(nl())
    settings.add(comment("URL to be pinged to check if you have a valid internet connection"))
    settings.add(
        comment(
            "These will be pinged a **LOT** make sure the service is okay with you sending all the continuous pings."
        )
    )
    settings.add("PingURLS", ["one.one.one.one", "dns.google.com"])
    settings.add(nl())
    settings.add(
        comment(
            "FFprobe auto updates, binaries are downloaded from https://ffbinaries.com/downloads"
        )
    )
    settings.add(comment("If this is disabled and you want ffprobe to work"))
    settings.add(
        comment(
            f"Ensure that you add the binary for your platform into ~/.config/qBitManager i.e \"{pathlib.Path().home().joinpath('.config', 'qBitManager', 'ffprobe.exe')}\""
        )
    )
    settings.add(
        comment(
            "If no `ffprobe` binary is found in the folder above all ffprobe functionality will be disabled."
        )
    )
    settings.add(
        comment(
            "By default this will always be on even if config does not have these key - to disable you need to explicitly set it to `False`"
        )
    )
    settings.add("FFprobeAutoUpdate", True)
    config.add("Settings", settings)


def _add_qbit_section(config: TOMLDocument):
    qbit = table()
    qbit.add(comment('Qbit WebUI Port - Can be found in Options > Web UI (called "IP Address")'))
    qbit.add("Host", "localhost")
    qbit.add(nl())
    qbit.add(
        comment(
            'Qbit WebUI Port - Can be found in Options > Web UI (called "Port" on top right corner of the window)'
        )
    )
    qbit.add("Port", 8105)
    qbit.add(nl())
    qbit.add(
        comment("Qbit WebUI Authentication - Can be found in Options > Web UI > Authentication")
    )
    qbit.add("UserName", "CHANGE_ME")
    qbit.add(nl())
    qbit.add(
        comment(
            'If you set "Bypass authentication on localhost or whitelisted IPs" remove this field.'
        )
    )
    qbit.add("Password", "CHANGE_ME")
    qbit.add(nl())
    config.add("QBit", qbit)


def _add_category_sections(config: TOMLDocument):
    for c in ["Sonarr-TV", "Sonarr-Anime", "Radarr-1080", "Radarr-4K"]:
        _gen_default_cat(c, config)


def _gen_default_cat(category: str, config: TOMLDocument):
    cat_default = table()
    cat_default.add(comment("Toggle whether to manage the Servarr instance torrents."))
    cat_default.add("Managed", True)
    cat_default.add(nl())
    cat_default.add(
        comment(
            "The URL used to access Servarr interface (if you use a domain enter the domain without a port)"
        )
    )
    cat_default.add("URI", "CHANGE_ME")
    cat_default.add(nl())
    cat_default.add(comment("The Servarr API Key, Can be found it Settings > General > Security"))
    cat_default.add("APIKey", "CHANGE_ME")
    cat_default.add(nl())
    cat_default.add(
        comment(
            "Category applied by Servarr to torrents in qBitTorrent, can be found in Settings > Download Clients > qBit > Category"
        )
    )
    cat_default.add("Category", category.lower())
    cat_default.add(nl())
    cat_default.add(
        comment("Toggle whether to send a query to Servarr to search any failed torrents")
    )
    cat_default.add("ReSearch", True)
    cat_default.add(nl())
    cat_default.add(comment("The Servarr's Import Mode(one of Move, Copy or Hardlink)"))
    cat_default.add("importMode", "Move")
    cat_default.add(nl())
    cat_default.add(comment("Timer to call RSSSync (In minutes) - Set to 0 to disable"))
    cat_default.add("RssSyncTimer", 0)
    cat_default.add(nl())
    cat_default.add(
        comment(
            "Timer to call RefreshDownloads tp update the queue. (In minutes) - Set to 0 to disable"
        )
    )
    cat_default.add("RefreshDownloadsTimer", 0)
    cat_default.add(nl())

    _gen_default_search_table(category, cat_default)
    _gen_default_torrent_table(category, cat_default)
    config.add(category, cat_default)


def _gen_default_torrent_table(category: str, cat_default: Table):
    torrent_table = table()
    torrent_table.add(comment("Set it to regex matches to respect/ignore case."))
    torrent_table.add("CaseSensitiveMatches", False)
    torrent_table.add(nl())
    torrent_table.add(
        comment(
            "These regex values will match any folder where the full name matches the specified values here, comma separated strings."
        )
    )
    torrent_table.add(
        comment("These regex need to be escaped, that's why you see so many backslashes.")
    )
    if "anime" in category.lower():
        torrent_table.add(
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
        torrent_table.add(
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
    torrent_table.add(nl())
    torrent_table.add(
        comment(
            "These regex values will match any folder where the full name matches the specified values here, comma separated strings."
        )
    )
    torrent_table.add(
        comment("These regex need to be escaped, that's why you see so many backslashes.")
    )
    torrent_table.add(
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
    torrent_table.add(nl())
    torrent_table.add(
        comment(
            "Only files with these extensions will be allowed to be downloaded, comma separated strings."
        )
    )
    torrent_table.add(
        "FileExtensionAllowlist", [".mp4", ".mkv", ".sub", ".ass", ".srt", ".!qB", ".parts"]
    )
    torrent_table.add(nl())
    torrent_table.add(comment("Auto delete files that can't be playable (i.e .exe, .png)"))
    torrent_table.add("AutoDelete", False)
    torrent_table.add(nl())
    torrent_table.add(
        comment("Ignore Torrents which are younger than this value (in seconds: 600 = 10 Minutes)")
    )
    torrent_table.add("IgnoreTorrentsYoungerThan", 180)
    torrent_table.add(nl())
    torrent_table.add(
        comment("Maximum allowed remaining ETA for torrent completion (in seconds: 3600 = 1 Hour)")
    )
    torrent_table.add(
        comment(
            "Note that if you set the MaximumETA on a tracker basis that value is favoured over this value"
        )
    )
    torrent_table.add("MaximumETA", 18000)
    torrent_table.add(nl())
    torrent_table.add(
        comment(
            "Do not delete torrents with higher completion percentage than this setting (0.5 = 50%, 1.0 = 100%)"
        )
    )
    torrent_table.add("MaximumDeletablePercentage", 0.99)
    torrent_table.add(nl())
    torrent_table.add(comment("Ignore slow torrents."))
    torrent_table.add("DoNotRemoveSlow", False)
    torrent_table.add(nl())
    _gen_default_seeding_table(category, torrent_table)
    _gen_default_tracker_tables(category, torrent_table)

    cat_default.add("Torrent", torrent_table)


def _gen_default_seeding_table(category: str, torrent_table: Table):
    seeding_table = table()
    seeding_table.add(comment("Set the maximum allowed download rate for torrents"))
    seeding_table.add(comment("Set this value to -1 to disabled it"))
    seeding_table.add(
        comment(
            "Note that if you set the DownloadRateLimit on a tracker basis that value is favoured over this value"
        )
    )
    seeding_table.add("DownloadRateLimitPerTorrent", -1)
    seeding_table.add(nl())
    seeding_table.add(comment("Set the maximum allowed upload rate for torrents"))
    seeding_table.add(comment("Set this value to -1 to disabled it"))
    seeding_table.add(
        comment(
            "Note that if you set the UploadRateLimit on a tracker basis that value is favoured over this value"
        )
    )
    seeding_table.add("UploadRateLimitPerTorrent", -1)
    seeding_table.add(nl())
    seeding_table.add(comment("Set the maximum allowed download rate for torrents"))
    seeding_table.add(comment("Set this value to -1 to disabled it"))
    seeding_table.add(
        comment(
            "Note that if you set the MaxUploadRatio on a tracker basis that value is favoured over this value"
        )
    )
    seeding_table.add("MaxUploadRatio", -1)
    seeding_table.add(nl())
    seeding_table.add(comment("Set the maximum allowed download rate for torrents"))
    seeding_table.add(comment("Set this value to -1 to disabled it"))
    seeding_table.add(
        comment(
            "Note that if you set the MaxSeedingTime on a tracker basis that value is favoured over this value"
        )
    )
    seeding_table.add("MaxSeedingTime", -1)
    seeding_table.add(nl())
    seeding_table.add(comment("Set the Maximum allowed download rate for torrents"))
    seeding_table.add("RemoveDeadTrackers", False)
    seeding_table.add(nl())
    seeding_table.add(
        comment(
            'If "RemoveDeadTrackers" is set to true then remove trackers with the following messages'
        )
    )
    seeding_table.add(
        "RemoveTrackerWithMessage",
        [
            "skipping tracker announce (unreachable)",
            "No such host is known",
            "unsupported URL protocol",
            "info hash is not authorized with this tracker",
        ],
    )
    seeding_table.add(nl())

    torrent_table.add("SeedingMode", seeding_table)


def _gen_default_tracker_tables(category: str, torrent_table: Table):
    tracker_table_list = []
    tracker_list = []
    if "anime" in category.lower():
        tracker_list.append(("Nyaa", "http://nyaa.tracker.wf:7777/announce", ["qbitrr-anime"], 10))
    elif "radarr" in category.lower():
        t = ["qbitrr-Rarbg", "Movies and TV"]
        t2 = []
        if "4k" in category.lower():
            t.append("4K")
            t2.append("4K")
        tracker_list.append(("Rarbg-2810", "udp://9.rarbg.com:2810/announce", t, 1))
        tracker_list.append(("Rarbg-2740", "udp://9.rarbg.to:2740/announce", t2, 2))

    for name, url, tags, priority in tracker_list:
        tracker_table = table()
        tracker_table.add(
            comment(
                "This is only for your own benefit, it is not currently used anywhere, but one day it may be."
            )
        )
        tracker_table.add("Name", name)
        tracker_table.add(nl())
        tracker_table.add(
            comment("This is used when multiple trackers are in one single torrent.")
        )
        tracker_table.add(
            comment(
                "the tracker with the highest priority will have all its settings applied to the torrent."
            )
        )
        tracker_table.add("Priority", priority)
        tracker_table.add(nl())
        tracker_table.add(comment("The tracker URI used by qBit."))
        tracker_table.add("URI", url)
        tracker_table.add(nl())
        tracker_table.add(
            comment(
                "Maximum allowed remaining ETA for torrent completion (in seconds: 3600 = 1 Hour)."
            )
        )
        tracker_table.add("MaximumETA", 18000)
        tracker_table.add(nl())

        tracker_table.add(comment("Set the maximum allowed download rate for torrents"))
        tracker_table.add(comment("Set this value to -1 to disabled it"))
        tracker_table.add("DownloadRateLimit", -1)
        tracker_table.add(nl())
        tracker_table.add(comment("Set the maximum allowed upload rate for torrents"))
        tracker_table.add(comment("Set this value to -1 to disabled it"))
        tracker_table.add("UploadRateLimit", -1)
        tracker_table.add(nl())
        tracker_table.add(comment("Set the maximum allowed download rate for torrents"))
        tracker_table.add(comment("Set this value to -1 to disabled it"))
        tracker_table.add("MaxUploadRatio", -1)
        tracker_table.add(nl())
        tracker_table.add(comment("Set the maximum allowed download rate for torrents"))
        tracker_table.add(comment("Set this value to -1 to disabled it"))
        tracker_table.add("MaxSeedingTime", -1)
        tracker_table.add(nl())

        tracker_table.add(comment("Add this tracker from any torrent that does not contains it."))
        tracker_table.add(comment("This setting does not respect priority."))
        tracker_table.add(comment("Meaning it always be applies."))
        tracker_table.add("AddTrackerIfMissing", False)
        tracker_table.add(nl())
        tracker_table.add(comment("Remove this tracker from any torrent that contains it."))
        tracker_table.add(comment("This setting does not respect priority."))
        tracker_table.add(comment("Meaning it always be applies."))
        tracker_table.add("RemoveIfExists", False)
        tracker_table.add(nl())
        tracker_table.add(comment("Enable Super Seeding setting for torrents with this tracker."))
        tracker_table.add("SuperSeedMode", False)
        tracker_table.add(nl())
        if tags:
            tracker_table.add(comment("Adds these tags to any torrents containing this tracker."))
            tracker_table.add(comment("This setting does not respect priority."))
            tracker_table.add(comment("Meaning it always be applies."))
            tracker_table.add("AddTags", tags)
            tracker_table.add(nl())

        tracker_table_list.append(tracker_table)
    torrent_table.add(
        comment("You can have multiple trackers set here or none just add more subsections.")
    )
    torrent_table.add("Trackers", tracker_table_list)


def _gen_default_search_table(category: str, cat_default: Table):
    search_table = table()
    search_table.add(
        comment(
            "All these settings depends on SearchMissing being True and access to the Servarr database file."
        )
    )
    search_table.add(nl())
    search_table.add(comment("Should search for Missing files?"))
    search_table.add("SearchMissing", False)
    search_table.add(nl())
    search_table.add(comment("Should search for specials episodes? (Season 00)"))
    search_table.add("AlsoSearchSpecials", False)
    search_table.add(nl())
    search_table.add(
        comment(
            "Maximum allowed Searches at any one points (I wouldn't recommend settings this too high)"
        )
    )
    if "sonarr" in category.lower():
        search_table.add(comment("Sonarr has a hardcoded cap of 3 simultaneous tasks"))
    elif "radarr" in category.lower():
        search_table.add(
            comment(
                "Radarr has a default of 3 simultaneous tasks, which can be increased up to 10 tasks"
            )
        )
        search_table.add(
            comment(
                'If you set the environment variable of "THREAD_LIMIT" to a number between and including 2-10'
            )
        )
        search_table.add(
            comment(
                "Radarr devs have stated that this is an unsupported feature so you will not get any support for doing so from them."
            )
        )
        search_table.add(
            comment(
                "That being said I've been daily driving 10 simultaneous tasks for quite a while now with no issues."
            )
        )
    search_table.add("SearchLimit", 5)
    search_table.add(nl())
    search_table.add(comment("Servarr Datapath file path"))
    search_table.add(comment("This is required for any of the search functionality to work"))
    search_table.add(
        comment(
            'The only exception for this is the "ReSearch" setting as that is done via an API call.'
        )
    )
    if "sonarr" in category.lower():
        search_table.add("DatabaseFile", "CHANGE_ME/sonarr.db")
    elif "radarr" in category.lower():
        search_table.add("DatabaseFile", "CHANGE_ME/radarr.db")
    search_table.add(nl())
    search_table.add(comment("It will order searches by the year the EPISODE was first aired"))
    search_table.add("SearchByYear", True)
    search_table.add(nl())
    search_table.add(
        comment("First year to search; Remove this field to set it to the current year.")
    )
    search_table.add("StartYear", datetime.now().year)
    search_table.add(nl())
    search_table.add(comment("Last Year to Search"))
    search_table.add("LastYear", 1990)
    search_table.add(nl())
    search_table.add(
        comment('Reverse search order (Start searching in "LastYear" and finish in "StartYear")')
    )
    search_table.add("SearchInReverse", False)
    search_table.add(nl())
    search_table.add(comment("Delay between request searches in seconds"))
    search_table.add("SearchRequestsEvery", 1800)
    search_table.add(nl())
    search_table.add(
        comment(
            "Search movies which already have a file in the database in hopes of finding a better quality version."
        )
    )
    search_table.add("DoUpgradeSearch", False)
    search_table.add(nl())
    search_table.add(comment("Do a quality unmet search for existing entries."))
    search_table.add("QualityUnmetSearch", False)
    search_table.add(nl())
    search_table.add(
        comment(
            "Once you have search all files on your specified year range restart the loop and search again."
        )
    )
    search_table.add("SearchAgainOnSearchCompletion", False)
    search_table.add(nl())

    if "sonarr" in category.lower():
        search_table.add(comment("Search by series instead of by episode"))
        search_table.add("SearchBySeries", True)
        search_table.add(nl())

        search_table.add(
            comment(
                "Prioritize Today's releases (Similar effect as RSS Sync, where it searches today's release episodes first, only works on Sonarr)."
            )
        )
        search_table.add("PrioritizeTodaysReleases", True)
        search_table.add(nl())
    _gen_default_ombi_table(category, search_table)
    _gen_default_overseerr_table(category, search_table)
    cat_default.add("EntrySearch", search_table)


def _gen_default_ombi_table(category: str, search_table: Table):
    ombi_table = table()
    ombi_table.add(
        comment("Search Ombi for pending requests (Will only work if 'SearchMissing' is enabled.)")
    )
    ombi_table.add("SearchOmbiRequests", False)
    ombi_table.add(nl())
    ombi_table.add(
        comment(
            "Ombi URI (Note that this has to be the instance of Ombi which manage the Arr instance request (If you have multiple Ombi instances)"
        )
    )
    ombi_table.add("OmbiURI", "http://localhost:5000")
    ombi_table.add(nl())
    ombi_table.add(comment("Ombi's API Key"))
    ombi_table.add("OmbiAPIKey", "CHANGE_ME")
    ombi_table.add(nl())
    ombi_table.add(comment("Only process approved requests"))
    ombi_table.add("ApprovedOnly", True)
    ombi_table.add(nl())

    search_table.add("Ombi", ombi_table)


def _gen_default_overseerr_table(category: str, search_table: Table):
    overseerr_table = table()
    overseerr_table.add(
        comment(
            "Search Overseerr for pending requests (Will only work if 'SearchMissing' is enabled.)"
        )
    )
    overseerr_table.add(comment("If this and Ombi are both enable, Ombi will be ignored"))
    overseerr_table.add("SearchOverseerrRequests", False)
    overseerr_table.add(nl())
    overseerr_table.add(comment("Overseerr's URI"))
    overseerr_table.add("OverseerrURI", "http://localhost:5055")
    overseerr_table.add(nl())
    overseerr_table.add(comment("Overseerr's API Key"))
    overseerr_table.add("OverseerrAPIKey", "CHANGE_ME")
    overseerr_table.add(nl())
    overseerr_table.add(comment("Only process approved requests"))
    overseerr_table.add("ApprovedOnly", True)
    overseerr_table.add(nl())
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
                if not self.path.exists():
                    self.path.touch()
                with self.path.open() as file:
                    self.config = parse(file.read())
                    return self
            except OSError as err:
                self.state = False
                self.err = err
            except TypeError as err:
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
                self.state = False
                self.err = err
            except TypeError as err:
                self.state = False
                self.err = err
        return self

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


def _write_config_file():
    doc = generate_doc()
    CONFIG_FILE = pathlib.Path().home().joinpath(".config", "qBitManager", "config.toml")
    if CONFIG_FILE.exists():
        print(f"{CONFIG_FILE} already exists.")
        print("If you want to generate a new config file first manually delete it or move it.")
        sys.exit(1)
    config = MyConfig(CONFIG_FILE, config=doc)
    config.save()
    print(f'New config file has been saved to "{CONFIG_FILE}"')
