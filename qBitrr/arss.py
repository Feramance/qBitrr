from __future__ import annotations

import contextlib
import itertools
import logging
import pathlib
import re
import shutil
import sys
import time
from collections import defaultdict
from copy import copy
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable, Iterable, Iterator, NoReturn

import ffmpeg
import pathos
import qbittorrentapi
import qbittorrentapi.exceptions
import requests
from packaging import version as version_parser
from peewee import SqliteDatabase
from pyarr import RadarrAPI, SonarrAPI
from pyarr.exceptions import PyarrResourceNotFound
from pyarr.types import JsonObject
from qbittorrentapi import TorrentDictionary, TorrentStates
from ujson import JSONDecodeError

from qBitrr.config import (
    APPDATA_FOLDER,
    AUTO_PAUSE_RESUME,
    COMPLETED_DOWNLOAD_FOLDER,
    CONFIG,
    FAILED_CATEGORY,
    FREE_SPACE,
    FREE_SPACE_FOLDER,
    LOOP_SLEEP_TIMER,
    NO_INTERNET_SLEEP_TIMER,
    PROCESS_ONLY,
    QBIT_DISABLED,
    RECHECK_CATEGORY,
    SEARCH_LOOP_DELAY,
    SEARCH_ONLY,
    TAGLESS,
)
from qBitrr.errors import (
    DelayLoopException,
    NoConnectionrException,
    RestartLoopException,
    SkipException,
    UnhandledError,
)
from qBitrr.logger import run_logs
from qBitrr.tables import (
    EpisodeFilesModel,
    EpisodeQueueModel,
    FilesQueued,
    MovieQueueModel,
    MoviesFilesModel,
    SeriesFilesModel,
    TorrentLibrary,
)
from qBitrr.utils import (
    ExpiringSet,
    absolute_file_paths,
    has_internet,
    parse_size,
    validate_and_return_torrent_file,
)

if TYPE_CHECKING:
    from qBitrr.main import qBitManager


class Arr:
    def __init__(
        self, name: str, manager: ArrManager, client_cls: type[Callable | RadarrAPI | SonarrAPI]
    ):
        if name in manager.groups:
            raise OSError(f"Group '{name}' has already been registered.")
        self._name = name
        self.managed = CONFIG.get(f"{name}.Managed", fallback=False)
        if not self.managed:
            raise SkipException
        self.uri = CONFIG.get_or_raise(f"{name}.URI")
        if self.uri in manager.uris:
            raise OSError(
                f"Group '{self._name}' is trying to manage Arr instance: "
                f"'{self.uri}' which has already been registered."
            )
        self.category = CONFIG.get(f"{name}.Category", fallback=self._name)
        self.manager = manager
        self._LOG_LEVEL = self.manager.qbit_manager.logger.level
        self.logger = logging.getLogger(f"qBitrr.{self._name}")
        run_logs(self.logger, self._name)

        if not QBIT_DISABLED:
            categories = self.manager.qbit_manager.client.torrent_categories.categories
            try:
                categ = categories[self.category]
                path = categ["savePath"]
                if path:
                    self.logger.trace("Category exists with save path [%s]", path)
                    self.completed_folder = pathlib.Path(path)
                else:
                    self.logger.trace("Category exists without save path")
                    self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(
                        self.category
                    )
            except KeyError:
                self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(
                    self.category
                )
                self.manager.qbit_manager.client.torrent_categories.create_category(
                    self.category, save_path=self.completed_folder
                )
        else:
            self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(self.category)

        if not self.completed_folder.exists() and not SEARCH_ONLY:
            try:
                self.completed_folder.mkdir(parents=True, exist_ok=True)
                self.completed_folder.chmod(mode=0o777)
            except BaseException:
                self.logger.warning(
                    "%s completed folder is a soft requirement. The specified folder does not exist %s and cannot be created. This will disable all file monitoring.",
                    self._name,
                    self.completed_folder,
                )
        self.apikey = CONFIG.get_or_raise(f"{name}.APIKey")
        self.re_search = CONFIG.get(f"{name}.ReSearch", fallback=False)
        self.import_mode = CONFIG.get(f"{name}.importMode", fallback="Auto")
        if self.import_mode == "Hardlink":
            self.import_mode = "Auto"
        self.refresh_downloads_timer = CONFIG.get(f"{name}.RefreshDownloadsTimer", fallback=1)
        self.arr_error_codes_to_blocklist = CONFIG.get(
            f"{name}.ArrErrorCodesToBlocklist", fallback=[]
        )
        self.rss_sync_timer = CONFIG.get(f"{name}.RssSyncTimer", fallback=15)

        self.case_sensitive_matches = CONFIG.get(
            f"{name}.Torrent.CaseSensitiveMatches", fallback=False
        )
        self.folder_exclusion_regex = CONFIG.get(
            f"{name}.Torrent.FolderExclusionRegex", fallback=None
        )
        self.file_name_exclusion_regex = CONFIG.get(
            f"{name}.Torrent.FileNameExclusionRegex", fallback=None
        )
        self.file_extension_allowlist = CONFIG.get(
            f"{name}.Torrent.FileExtensionAllowlist", fallback=None
        )
        if self.file_extension_allowlist:
            self.file_extension_allowlist = [
                rf"\{ext}" if ext[:1] != "\\" else ext for ext in self.file_extension_allowlist
            ]
        self.auto_delete = CONFIG.get(f"{name}.Torrent.AutoDelete", fallback=False)

        self.remove_dead_trackers = CONFIG.get(
            f"{name}.Torrent.SeedingMode.RemoveDeadTrackers", fallback=False
        )
        self.seeding_mode_global_download_limit = CONFIG.get(
            f"{name}.Torrent.SeedingMode.DownloadRateLimitPerTorrent", fallback=-1
        )
        self.seeding_mode_global_upload_limit = CONFIG.get(
            f"{name}.Torrent.SeedingMode.UploadRateLimitPerTorrent", fallback=-1
        )
        self.seeding_mode_global_max_upload_ratio = CONFIG.get(
            f"{name}.Torrent.SeedingMode.MaxUploadRatio", fallback=-1
        )
        self.seeding_mode_global_max_seeding_time = CONFIG.get(
            f"{name}.Torrent.SeedingMode.MaxSeedingTime", fallback=-1
        )
        self.seeding_mode_global_remove_torrent = CONFIG.get(
            f"{name}.Torrent.SeedingMode.RemoveTorrent", fallback=-1
        )
        self.seeding_mode_global_bad_tracker_msg = CONFIG.get(
            f"{name}.Torrent.SeedingMode.RemoveTrackerWithMessage", fallback=[]
        )

        self.monitored_trackers = CONFIG.get(f"{name}.Torrent.Trackers", fallback=[])
        self._remove_trackers_if_exists: set[str] = {
            i.get("URI") for i in self.monitored_trackers if i.get("RemoveIfExists") is True
        }
        self._monitored_tracker_urls: set[str] = {
            r
            for i in self.monitored_trackers
            if (r := i.get("URI")) not in self._remove_trackers_if_exists
        }
        self._add_trackers_if_missing: set[str] = {
            i.get("URI") for i in self.monitored_trackers if i.get("AddTrackerIfMissing") is True
        }
        if (
            self.auto_delete is True
            and not self.completed_folder.parent.exists()
            and not SEARCH_ONLY
        ):
            self.auto_delete = False
            self.logger.critical(
                "AutoDelete disabled due to missing folder: '%s'", self.completed_folder.parent
            )

        self.reset_on_completion = CONFIG.get(
            f"{name}.EntrySearch.SearchAgainOnSearchCompletion", fallback=False
        )
        self.do_upgrade_search = CONFIG.get(f"{name}.EntrySearch.DoUpgradeSearch", fallback=False)
        self.quality_unmet_search = CONFIG.get(
            f"{name}.EntrySearch.QualityUnmetSearch", fallback=False
        )
        self.custom_format_unmet_search = CONFIG.get(
            f"{name}.EntrySearch.CustomFormatUnmetSearch", fallback=False
        )
        self.force_minimum_custom_format = CONFIG.get(
            f"{name}.EntrySearch.ForceMinimumCustomFormat", fallback=False
        )

        self.ignore_torrents_younger_than = CONFIG.get(
            f"{name}.Torrent.IgnoreTorrentsYoungerThan", fallback=600
        )
        self.maximum_eta = CONFIG.get(f"{name}.Torrent.MaximumETA", fallback=86400)
        self.maximum_deletable_percentage = CONFIG.get(
            f"{name}.Torrent.MaximumDeletablePercentage", fallback=0.95
        )
        self.search_missing = CONFIG.get(f"{name}.EntrySearch.SearchMissing", fallback=False)
        if PROCESS_ONLY:
            self.search_missing = False
        self.search_specials = CONFIG.get(f"{name}.EntrySearch.AlsoSearchSpecials", fallback=False)
        self.search_unmonitored = CONFIG.get(f"{name}.EntrySearch.Unmonitored", fallback=False)
        self.search_by_year = CONFIG.get(f"{name}.EntrySearch.SearchByYear", fallback=True)
        self.search_in_reverse = CONFIG.get(f"{name}.EntrySearch.SearchInReverse", fallback=False)

        self.search_command_limit = CONFIG.get(f"{name}.EntrySearch.SearchLimit", fallback=5)
        self.prioritize_todays_release = CONFIG.get(
            f"{name}.EntrySearch.PrioritizeTodaysReleases", fallback=True
        )

        self.do_not_remove_slow = CONFIG.get(f"{name}.Torrent.DoNotRemoveSlow", fallback=False)
        self.re_search_stalled = CONFIG.get(f"{name}.Torrent.ReSearchStalled", fallback=False)
        self.stalled_delay = CONFIG.get(f"{name}.Torrent.StalledDelay", fallback=15)
        self.allowed_stalled = True if self.stalled_delay != -1 else False

        self.search_current_year = None
        if self.search_in_reverse:
            self._delta = 1
        else:
            self._delta = -1
        self._app_data_folder = APPDATA_FOLDER
        self.search_db_file = self._app_data_folder.joinpath(f"{self._name}.db")

        self.ombi_search_requests = CONFIG.get(
            f"{name}.EntrySearch.Ombi.SearchOmbiRequests", fallback=False
        )
        self.overseerr_requests = CONFIG.get(
            f"{name}.EntrySearch.Overseerr.SearchOverseerrRequests", fallback=False
        )
        self.series_search = CONFIG.get(f"{name}.EntrySearch.SearchBySeries", fallback=False)
        if self.ombi_search_requests:
            self.ombi_uri = CONFIG.get_or_raise(f"{name}.EntrySearch.Ombi.OmbiURI")
            self.ombi_api_key = CONFIG.get_or_raise(f"{name}.EntrySearch.Ombi.OmbiAPIKey")
        else:
            self.ombi_uri = CONFIG.get(f"{name}.EntrySearch.Ombi.OmbiURI", fallback=None)
            self.ombi_api_key = CONFIG.get(f"{name}.EntrySearch.Ombi.OmbiAPIKey", fallback=None)
        if self.overseerr_requests:
            self.overseerr_uri = CONFIG.get_or_raise(f"{name}.EntrySearch.Overseerr.OverseerrURI")
            self.overseerr_api_key = CONFIG.get_or_raise(
                f"{name}.EntrySearch.Overseerr.OverseerrAPIKey"
            )
        else:
            self.overseerr_uri = CONFIG.get(
                f"{name}.EntrySearch.Overseerr.OverseerrURI", fallback=None
            )
            self.overseerr_api_key = CONFIG.get(
                f"{name}.EntrySearch.Overseerr.OverseerrAPIKey", fallback=None
            )
        self.overseerr_is_4k = CONFIG.get(f"{name}.EntrySearch.Overseerr.Is4K", fallback=False)
        self.ombi_approved_only = CONFIG.get(
            f"{name}.EntrySearch.Ombi.ApprovedOnly", fallback=True
        )
        self.overseerr_approved_only = CONFIG.get(
            f"{name}.EntrySearch.Overseerr.ApprovedOnly", fallback=True
        )
        self.search_requests_every_x_seconds = CONFIG.get(
            f"{name}.EntrySearch.SearchRequestsEvery", fallback=1800
        )
        self._temp_overseer_request_cache: dict[str, set[int | str]] = defaultdict(set)
        if self.ombi_search_requests or self.overseerr_requests:
            self.request_search_timer = 0
        else:
            self.request_search_timer = None

        if self.case_sensitive_matches:
            self.folder_exclusion_regex_re = (
                re.compile("|".join(self.folder_exclusion_regex), re.DOTALL)
                if self.folder_exclusion_regex
                else None
            )
            self.file_name_exclusion_regex_re = (
                re.compile("|".join(self.file_name_exclusion_regex), re.DOTALL)
                if self.file_name_exclusion_regex
                else None
            )
            self.file_extension_allowlist_re = (
                re.compile("|".join(self.file_extension_allowlist), re.DOTALL)
                if self.file_extension_allowlist
                else None
            )
        else:
            self.folder_exclusion_regex_re = (
                re.compile("|".join(self.folder_exclusion_regex), re.IGNORECASE | re.DOTALL)
                if self.folder_exclusion_regex
                else None
            )
            self.file_name_exclusion_regex_re = (
                re.compile("|".join(self.file_name_exclusion_regex), re.IGNORECASE | re.DOTALL)
                if self.file_name_exclusion_regex
                else None
            )
            self.file_extension_allowlist_re = (
                re.compile("|".join(self.file_extension_allowlist), re.IGNORECASE | re.DOTALL)
                if self.file_extension_allowlist
                else None
            )
        self.client = client_cls(host_url=self.uri, api_key=self.apikey)
        if isinstance(self.client, SonarrAPI):
            self.type = "sonarr"
        elif isinstance(self.client, RadarrAPI):
            self.type = "radarr"

        try:
            version_info = self.client.get_update()
            self.version = version_parser.parse(version_info[0].get("version"))
            self.logger.debug("%s version: %s", self._name, self.version.__str__())
        except Exception:
            self.logger.debug("Failed to get version")

        self.main_quality_profiles = CONFIG.get(
            f"{self._name}.EntrySearch.MainQualityProfile", fallback=None
        )
        if not isinstance(self.main_quality_profiles, list):
            self.main_quality_profiles = [self.main_quality_profiles]
        self.temp_quality_profiles = CONFIG.get(
            f"{self._name}.EntrySearch.TempQualityProfile", fallback=None
        )
        if not isinstance(self.temp_quality_profiles, list):
            self.temp_quality_profiles = [self.temp_quality_profiles]

        self.use_temp_for_missing = (
            CONFIG.get(f"{name}.EntrySearch.UseTempForMissing", fallback=False)
            and self.main_quality_profiles
            and self.temp_quality_profiles
        )
        self.keep_temp_profile = CONFIG.get(f"{name}.EntrySearch.KeepTempProfile", fallback=False)

        if self.use_temp_for_missing:
            self.temp_quality_profile_ids = self.parse_quality_profiles()

        if self.rss_sync_timer > 0:
            self.rss_sync_timer_last_checked = datetime(1970, 1, 1)
        else:
            self.rss_sync_timer_last_checked = None
        if self.refresh_downloads_timer > 0:
            self.refresh_downloads_timer_last_checked = datetime(1970, 1, 1)
        else:
            self.refresh_downloads_timer_last_checked = None

        self.loop_completed = False
        self.queue = []
        self.cache = {}
        self.requeue_cache = {}
        self.queue_file_ids = set()
        self.sent_to_scan = set()
        self.sent_to_scan_hashes = set()
        self.files_probed = set()
        self.import_torrents = []
        self.change_priority = {}
        self.recheck = set()
        self.pause = set()
        self.skip_blacklist = set()
        self.delete = set()
        self.resume = set()
        self.remove_from_qbit = set()
        self.overseerr_requests_release_cache = {}
        self.files_to_explicitly_delete: Iterator = iter([])
        self.files_to_cleanup = set()
        self.missing_files_post_delete = set()
        self.downloads_with_bad_error_message_blocklist = set()
        self.needs_cleanup = False

        self.timed_ignore_cache = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.timed_ignore_cache_2 = ExpiringSet(
            max_age_seconds=self.ignore_torrents_younger_than * 2
        )
        self.timed_skip = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.tracker_delay = ExpiringSet(max_age_seconds=600)
        self.special_casing_file_check = ExpiringSet(max_age_seconds=10)
        self.expiring_bool = ExpiringSet(max_age_seconds=10)
        self.session = requests.Session()
        self.cleaned_torrents = set()
        self.search_api_command = None

        self.manager.completed_folders.add(self.completed_folder)
        self.manager.category_allowlist.add(self.category)

        self.logger.debug(
            "%s Config: "
            "Managed: %s, "
            "Re-search: %s, "
            "ImportMode: %s, "
            "Category: %s, "
            "URI: %s, "
            "API Key: %s, "
            "RefreshDownloadsTimer=%s, "
            "RssSyncTimer=%s",
            self._name,
            self.import_mode,
            self.managed,
            self.re_search,
            self.category,
            self.uri,
            self.apikey,
            self.refresh_downloads_timer,
            self.rss_sync_timer,
        )
        self.logger.debug("Script Config:  CaseSensitiveMatches=%s", self.case_sensitive_matches)
        self.logger.debug("Script Config:  FolderExclusionRegex=%s", self.folder_exclusion_regex)
        self.logger.debug(
            "Script Config:  FileNameExclusionRegex=%s", self.file_name_exclusion_regex
        )
        self.logger.debug(
            "Script Config:  FileExtensionAllowlist=%s", self.file_extension_allowlist
        )
        self.logger.debug("Script Config:  AutoDelete=%s", self.auto_delete)
        self.logger.debug(
            "Script Config:  IgnoreTorrentsYoungerThan=%s", self.ignore_torrents_younger_than
        )
        self.logger.debug("Script Config:  MaximumETA=%s", self.maximum_eta)
        self.logger.debug(
            "Script Config:  MaximumDeletablePercentage=%s", self.maximum_deletable_percentage
        )
        self.logger.debug("Script Config:  StalledDelay=%s", self.stalled_delay)
        self.logger.debug("Script Config:  AllowedStalled=%s", self.allowed_stalled)
        self.logger.debug("Script Config:  ReSearchStalled=%s", self.re_search_stalled)
        self.logger.debug("Script Config:  StalledDelay=%s", self.stalled_delay)

        if self.search_missing:
            self.logger.debug("Script Config:  SearchMissing=%s", self.search_missing)
            self.logger.debug("Script Config:  AlsoSearchSpecials=%s", self.search_specials)
            self.logger.debug("Script Config:  SearchUnmoniored=%s", self.search_unmonitored)
            self.logger.debug("Script Config:  SearchByYear=%s", self.search_by_year)
            self.logger.debug("Script Config:  SearchInReverse=%s", self.search_in_reverse)
            self.logger.debug("Script Config:  CommandLimit=%s", self.search_command_limit)
            self.logger.debug(
                "Script Config:  MaximumDeletablePercentage=%s", self.maximum_deletable_percentage
            )
            self.logger.debug("Script Config:  DoUpgradeSearch=%s", self.do_upgrade_search)
            self.logger.debug(
                "Script Config:  CustomFormatUnmetSearch=%s", self.custom_format_unmet_search
            )
            self.logger.debug(
                "Script Config:  PrioritizeTodaysReleases=%s", self.prioritize_todays_release
            )
            self.logger.debug("Script Config:  SearchBySeries=%s", self.series_search)
            self.logger.debug("Script Config:  SearchOmbiRequests=%s", self.ombi_search_requests)
            if self.ombi_search_requests:
                self.logger.debug("Script Config:  OmbiURI=%s", self.ombi_uri)
                self.logger.debug("Script Config:  OmbiAPIKey=%s", self.ombi_api_key)
                self.logger.debug("Script Config:  ApprovedOnly=%s", self.ombi_approved_only)
            self.logger.debug(
                "Script Config:  SearchOverseerrRequests=%s", self.overseerr_requests
            )
            if self.overseerr_requests:
                self.logger.debug("Script Config:  OverseerrURI=%s", self.overseerr_uri)
                self.logger.debug("Script Config:  OverseerrAPIKey=%s", self.overseerr_api_key)
            if self.ombi_search_requests or self.overseerr_requests:
                self.logger.debug(
                    "Script Config:  SearchRequestsEvery=%s", self.search_requests_every_x_seconds
                )

        if self.type == "sonarr":
            if (
                self.quality_unmet_search
                or self.do_upgrade_search
                or self.custom_format_unmet_search
                or self.series_search
            ):
                self.search_api_command = "SeriesSearch"
            else:
                self.search_api_command = "MissingEpisodeSearch"

        if not QBIT_DISABLED and not TAGLESS:
            self.manager.qbit_manager.client.torrents_create_tags(
                [
                    "qBitrr-allowed_seeding",
                    "qBitrr-ignored",
                    "qBitrr-imported",
                    "qBitrr-allowed_stalled",
                ]
            )
        elif not QBIT_DISABLED and TAGLESS:
            self.manager.qbit_manager.client.torrents_create_tags(["qBitrr-ignored"])
        self.search_setup_completed = False
        self.model_file: EpisodeFilesModel | MoviesFilesModel = None
        self.series_file_model: SeriesFilesModel = None
        self.model_queue: EpisodeQueueModel | MovieQueueModel = None
        self.persistent_queue: FilesQueued = None
        self.torrents: TorrentLibrary = None
        self.logger.hnotice("Starting %s monitor", self._name)

    @property
    def is_alive(self) -> bool:
        try:
            if 1 in self.expiring_bool:
                return True
            if self.session is None:
                self.expiring_bool.add(1)
                return True
            req = self.session.get(
                f"{self.uri}/api/v3/system/status", timeout=10, params={"apikey": self.apikey}
            )
            req.raise_for_status()
            self.logger.trace("Successfully connected to %s", self.uri)
            self.expiring_bool.add(1)
            return True
        except requests.HTTPError:
            self.expiring_bool.add(1)
            return True
        except requests.RequestException:
            self.logger.warning("Could not connect to %s", self.uri)
        return False

    @staticmethod
    def is_ignored_state(torrent: TorrentDictionary) -> bool:
        return torrent.state_enum in (
            TorrentStates.FORCED_DOWNLOAD,
            TorrentStates.FORCED_UPLOAD,
            TorrentStates.CHECKING_UPLOAD,
            TorrentStates.CHECKING_DOWNLOAD,
            TorrentStates.CHECKING_RESUME_DATA,
            TorrentStates.ALLOCATING,
            TorrentStates.MOVING,
            TorrentStates.QUEUED_DOWNLOAD,
        )

    @staticmethod
    def is_uploading_state(torrent: TorrentDictionary) -> bool:
        return torrent.state_enum in (
            TorrentStates.UPLOADING,
            TorrentStates.STALLED_UPLOAD,
            TorrentStates.QUEUED_UPLOAD,
        )

    @staticmethod
    def is_complete_state(torrent: TorrentDictionary) -> bool:
        """Returns True if the State is categorized as Complete."""
        return torrent.state_enum in (
            TorrentStates.UPLOADING,
            TorrentStates.STALLED_UPLOAD,
            TorrentStates.PAUSED_UPLOAD,
            TorrentStates.QUEUED_UPLOAD,
        )

    @staticmethod
    def is_downloading_state(torrent: TorrentDictionary) -> bool:
        """Returns True if the State is categorized as Downloading."""
        return torrent.state_enum in (TorrentStates.DOWNLOADING, TorrentStates.PAUSED_DOWNLOAD)

    def in_tags(self, torrent: TorrentDictionary, tag: str) -> bool:
        return_value = False
        if TAGLESS:
            if tag == "qBitrr-ignored":
                return_value = "qBitrr-ignored" in torrent.tags
            else:
                condition = (
                    self.torrents.Hash == torrent.hash & self.torrents.Category == torrent.category
                )
                if tag == "qBitrr-allowed_seeding":
                    condition &= self.torrents.AllowedSeeding is True
                elif tag == "qBitrr-imported":
                    condition &= self.torrents.Imported is True
                elif tag == "qBitrr-allowed_stalled":
                    condition &= self.torrents.AllowedStalled is True
                elif tag == "qBitrr-free_space_paused":
                    condition &= self.torrents.FreeSpacePaused is True
                query = self.torrents.select().where(condition).execute()
                if query:
                    return_value = True
                else:
                    return_value = False
        else:
            if tag in torrent.tags:
                return_value = True
            else:
                return_value = False

        if return_value:
            self.logger.trace("Tag %s in %s", tag, torrent.name)
            return True
        else:
            self.logger.trace("Tag %s not in %s", tag, torrent.name)
            return False

    def remove_tags(self, torrent: TorrentDictionary, tags: list) -> None:
        for tag in tags:
            self.logger.trace("Removing tag %s from %s", tag, torrent.name)
        if TAGLESS:
            for tag in tags:
                query = (
                    self.torrents.select()
                    .where(
                        self.torrents.Hash
                        == torrent.hash & self.torrents.Category
                        == torrent.category
                    )
                    .execute()
                )
                if not query:
                    self.torrents.insert(
                        Hash=torrent.hash, Category=torrent.category
                    ).on_conflict_ignore().execute()
                if tag == "qBitrr-allowed_seeding":
                    self.torrents.update(AllowedSeeding=False).where(
                        self.torrents.Hash
                        == torrent.hash & self.torrents.Category
                        == torrent.category
                    )
                elif tag == "qBitrr-imported":
                    self.torrents.update(Imported=False).where(
                        self.torrents.Hash
                        == torrent.hash & self.torrents.Category
                        == torrent.category
                    )
                elif tag == "qBitrr-allowed_stalled":
                    self.torrents.update(AllowedStalled=False).where(
                        self.torrents.Hash
                        == torrent.hash & self.torrents.Category
                        == torrent.category
                    )
                elif tag == "qBitrr-free_space_paused":
                    self.torrents.update(FreeSpacePaused=False).where(
                        self.torrents.Hash
                        == torrent.hash & self.torrents.Category
                        == torrent.category
                    )
        else:
            torrent.remove_tags(tags)

    def add_tags(self, torrent: TorrentDictionary, tags: list) -> None:
        for tag in tags:
            self.logger.trace("Adding tag %s from %s", tag, torrent.name)
        if TAGLESS:
            for tag in tags:
                query = (
                    self.torrents.select()
                    .where(
                        self.torrents.Hash
                        == torrent.hash & self.torrents.Category
                        == torrent.category
                    )
                    .execute()
                )
                if not query:
                    self.torrents.insert(
                        Hash=torrent.hash, Category=torrent.category
                    ).on_conflict_ignore().execute()
                if tag == "qBitrr-allowed_seeding":
                    self.torrents.update(AllowedSeeding=True).where(
                        self.torrents.Hash
                        == torrent.hash & self.torrents.Category
                        == torrent.category
                    )
                elif tag == "qBitrr-imported":
                    self.torrents.update(Imported=True).where(
                        self.torrents.Hash
                        == torrent.hash & self.torrents.Category
                        == torrent.category
                    )
                elif tag == "qBitrr-allowed_stalled":
                    self.torrents.update(AllowedStalled=True).where(
                        self.torrents.Hash
                        == torrent.hash & self.torrents.Category
                        == torrent.category
                    )
                elif tag == "qBitrr-free_space_paused":
                    self.torrents.update(FreeSpacePaused=True).where(
                        self.torrents.Hash
                        == torrent.hash & self.torrents.Category
                        == torrent.category
                    )
        else:
            torrent.add_tags(tags)

    def _get_models(
        self,
    ) -> tuple[
        type[EpisodeFilesModel] | type[MoviesFilesModel],
        type[EpisodeQueueModel] | type[MovieQueueModel],
        type[SeriesFilesModel] | None,
        type[TorrentLibrary] | None,
    ]:
        if self.type == "sonarr":
            if self.series_search:
                return (
                    EpisodeFilesModel,
                    EpisodeQueueModel,
                    SeriesFilesModel,
                    TorrentLibrary if TAGLESS else None,
                )
            return EpisodeFilesModel, EpisodeQueueModel, None, TorrentLibrary if TAGLESS else None
        elif self.type == "radarr":
            return MoviesFilesModel, MovieQueueModel, None, TorrentLibrary if TAGLESS else None
        else:
            raise UnhandledError(f"Well you shouldn't have reached here, Arr.type={self.type}")

    def _get_oversee_requests_all(self) -> dict[str, set]:
        try:
            key = "approved" if self.overseerr_approved_only else "unavailable"
            data = defaultdict(set)
            response = self.session.get(
                url=f"{self.overseerr_uri}/api/v1/request",
                headers={"X-Api-Key": self.overseerr_api_key},
                params={"take": 100, "skip": 0, "sort": "added", "filter": key},
                timeout=2,
            )
            response = response.json().get("results", [])
            type_ = None
            if self.type == "radarr":
                type_ = "movie"
            elif self.type == "sonarr":
                type_ = "tv"
            _now = datetime.now()
            for entry in response:
                type__ = entry.get("type")
                if type__ == "movie":
                    id__ = entry.get("media", {}).get("tmdbId")
                elif type__ == "tv":
                    id__ = entry.get("media", {}).get("tvdbId")
                if type_ != type__:
                    continue
                if self.overseerr_is_4k and entry.get("is4k"):
                    if self.overseerr_approved_only:
                        if entry.get("media", {}).get("status4k") != 3:
                            continue
                    elif entry.get("media", {}).get("status4k") == 5:
                        continue
                elif not self.overseerr_is_4k and not entry.get("is4k"):
                    if self.overseerr_approved_only:
                        if entry.get("media", {}).get("status") != 3:
                            continue
                    elif entry.get("media", {}).get("status") == 5:
                        continue
                else:
                    continue
                if id__ in self.overseerr_requests_release_cache:
                    date = self.overseerr_requests_release_cache[id__]
                else:
                    date = datetime(day=1, month=1, year=1970)
                    date_string_backup = f"{_now.year}-{_now.month:02}-{_now.day:02}"
                    date_string = None
                    try:
                        if type_ == "movie":
                            _entry_data = self.session.get(
                                url=f"{self.overseerr_uri}/api/v1/movies/{id__}",
                                headers={"X-Api-Key": self.overseerr_api_key},
                                timeout=2,
                            )
                            date_string = _entry_data.json().get("releaseDate")
                        elif type__ == "tv":
                            _entry_data = self.session.get(
                                url=f"{self.overseerr_uri}/api/v1/tv/{id__}",
                                headers={"X-Api-Key": self.overseerr_api_key},
                                timeout=2,
                            )
                            # We don't do granular (episode/season) searched here so no need to
                            # suppose them
                            date_string = _entry_data.json().get("firstAirDate")
                        if not date_string:
                            date_string = date_string_backup
                        date = datetime.strptime(date_string, "%Y-%m-%d")
                        if date > _now:
                            continue
                        self.overseerr_requests_release_cache[id__] = date
                    except Exception as e:
                        self.logger.warning("Failed to query release date from Overseerr: %s", e)
                if media := entry.get("media"):
                    if imdbId := media.get("imdbId"):
                        data["ImdbId"].add(imdbId)
                    if self.type == "sonarr" and (tvdbId := media.get("tvdbId")):
                        data["TvdbId"].add(tvdbId)
                    elif self.type == "radarr" and (tmdbId := media.get("tmdbId")):
                        data["TmdbId"].add(tmdbId)
            self._temp_overseer_request_cache = data
        except requests.exceptions.ConnectionError:
            self.logger.warning("Couldn't connect to Overseerr")
            self._temp_overseer_request_cache = defaultdict(set)
            return self._temp_overseer_request_cache
        except requests.exceptions.ReadTimeout:
            self.logger.warning("Connection to Overseerr timed out")
            self._temp_overseer_request_cache = defaultdict(set)
            return self._temp_overseer_request_cache
        except Exception as e:
            self.logger.exception(e, exc_info=sys.exc_info())
            self._temp_overseer_request_cache = defaultdict(set)
            return self._temp_overseer_request_cache
        else:
            return self._temp_overseer_request_cache

    def _get_overseerr_requests_count(self) -> int:
        self._get_oversee_requests_all()
        if self.type == "sonarr":
            return len(
                self._temp_overseer_request_cache.get("TvdbId", [])
                or self._temp_overseer_request_cache.get("ImdbId", [])
            )
        elif self.type == "radarr":
            return len(
                self._temp_overseer_request_cache.get("ImdbId", [])
                or self._temp_overseer_request_cache.get("TmdbId", [])
            )
        return 0

    def _get_ombi_request_count(self) -> int:
        if self.type == "sonarr":
            extras = "/api/v1/Request/tv/total"
        elif self.type == "radarr":
            extras = "/api/v1/Request/movie/total"
        else:
            raise UnhandledError(f"Well you shouldn't have reached here, Arr.type={self.type}")
        try:
            response = self.session.get(
                url=f"{self.ombi_uri}{extras}", headers={"ApiKey": self.ombi_api_key}
            )
        except Exception as e:
            self.logger.exception(e, exc_info=sys.exc_info())
            return 0
        else:
            return response.json()

    def _get_ombi_requests(self) -> list[dict]:
        if self.type == "sonarr":
            extras = "/api/v1/Request/tvlite"
        elif self.type == "radarr":
            extras = "/api/v1/Request/movie"
        else:
            raise UnhandledError(f"Well you shouldn't have reached here, Arr.type={self.type}")
        try:
            response = self.session.get(
                url=f"{self.ombi_uri}{extras}", headers={"ApiKey": self.ombi_api_key}
            )
            return response.json()
        except Exception as e:
            self.logger.exception(e, exc_info=sys.exc_info())
            return []

    def _process_ombi_requests(self) -> dict[str, set[str, int]]:
        requests = self._get_ombi_requests()
        data = defaultdict(set)
        for request in requests:
            if self.type == "radarr" and self.ombi_approved_only and request.get("denied") is True:
                continue
            elif self.type == "sonarr" and self.ombi_approved_only:
                # This is me being lazy and not wanting to deal with partially approved requests.
                if any(child.get("denied") is True for child in request.get("childRequests", [])):
                    continue
            if imdbId := request.get("imdbId"):
                data["ImdbId"].add(imdbId)
            if self.type == "radarr" and (theMovieDbId := request.get("theMovieDbId")):
                data["TmdbId"].add(theMovieDbId)
            if self.type == "sonarr" and (tvDbId := request.get("tvDbId")):
                data["TvdbId"].add(tvDbId)
        return data

    def _process_paused(self) -> None:
        # Bulks pause all torrents flagged for pausing.
        if self.pause and AUTO_PAUSE_RESUME:
            self.needs_cleanup = True
            self.logger.debug("Pausing %s torrents", len(self.pause))
            for i in self.pause:
                self.logger.debug(
                    "Pausing %s (%s)", i, self.manager.qbit_manager.name_cache.get(i)
                )
            self.manager.qbit.torrents_pause(torrent_hashes=self.pause)
            self.pause.clear()

    def _process_imports(self) -> None:
        if self.import_torrents:
            self.needs_cleanup = True
            for torrent in self.import_torrents:
                if torrent.hash in self.sent_to_scan:
                    continue
                path = validate_and_return_torrent_file(torrent.content_path)
                if not path.exists():
                    self.timed_ignore_cache.add(torrent.hash)
                    self.logger.warning(
                        "Missing Torrent: [%s] %s (%s) - File does not seem to exist: %s",
                        torrent.state_enum,
                        torrent.name,
                        torrent.hash,
                        path,
                    )
                    continue
                if path in self.sent_to_scan:
                    continue
                self.sent_to_scan_hashes.add(torrent.hash)
                try:
                    if self.type == "sonarr":
                        while True:
                            try:
                                self.client.post_command(
                                    "DownloadedEpisodesScan",
                                    path=str(path),
                                    downloadClientId=torrent.hash.upper(),
                                    importMode=self.import_mode,
                                )
                                break
                            except (
                                requests.exceptions.ChunkedEncodingError,
                                requests.exceptions.ContentDecodingError,
                                requests.exceptions.ConnectionError,
                                JSONDecodeError,
                            ):
                                continue
                        self.logger.success("DownloadedEpisodesScan: %s", path)
                    elif self.type == "radarr":
                        while True:
                            try:
                                self.client.post_command(
                                    "DownloadedMoviesScan",
                                    path=str(path),
                                    downloadClientId=torrent.hash.upper(),
                                    importMode=self.import_mode,
                                )
                                break
                            except (
                                requests.exceptions.ChunkedEncodingError,
                                requests.exceptions.ContentDecodingError,
                                requests.exceptions.ConnectionError,
                                JSONDecodeError,
                            ):
                                continue
                        self.logger.success("DownloadedMoviesScan: %s", path)
                except Exception as ex:
                    self.logger.error(
                        "Downloaded scan error: [%s][%s][%s][%s]",
                        path,
                        torrent.hash.upper(),
                        self.import_mode,
                        ex,
                    )
                self.add_tags(torrent, ["qBitrr-imported"])
                self.sent_to_scan.add(path)
            self.import_torrents.clear()

    def _process_failed_individual(
        self, hash_: str, entry: int, skip_blacklist: set[str], remove_from_client: bool = True
    ) -> None:
        self.logger.debug(
            "Deleting from queue: %s, [%s][Blocklisting:%s][Remove from client:%s]",
            hash_,
            self.manager.qbit_manager.name_cache.get(hash_, "Blocklisted"),
            True if hash_ not in skip_blacklist else False,
            remove_from_client,
        )
        if hash_ not in skip_blacklist:
            self.delete_from_queue(
                id_=entry, remove_from_client=remove_from_client, blacklist=True
            )
        else:
            self.delete_from_queue(
                id_=entry, remove_from_client=remove_from_client, blacklist=False
            )
        object_id = self.requeue_cache.get(entry)
        if self.re_search and object_id:
            if self.type == "sonarr":
                object_ids = list(object_id)
                self.logger.trace("Requeue cache entry list: %s", object_ids)
                if self.series_search:
                    while True:
                        try:
                            data = self.client.get_series(object_ids[0])
                            name = data["title"]
                            series_id = data["id"]
                            if name:
                                year = data.get("year", 0)
                                tvdbId = data.get("tvdbId", 0)
                                self.logger.notice(
                                    "Re-Searching series: %s (%s) | [tvdbId=%s|id=%s]",
                                    name,
                                    year,
                                    tvdbId,
                                    series_id,
                                )
                            else:
                                self.logger.notice("Re-Searching series: %s", series_id)
                            break
                        except (
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                        ):
                            continue
                        except PyarrResourceNotFound as e:
                            self.logger.debug(e)
                            self.logger.error("PyarrResourceNotFound: %s", object_ids[0])
                    for object_id in object_ids:
                        if object_id in self.queue_file_ids:
                            self.queue_file_ids.remove(object_id)
                    self.logger.trace("Research series id: %s", series_id)
                    while True:
                        try:
                            self.client.post_command(self.search_api_command, seriesId=series_id)
                            break
                        except (
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                        ):
                            continue
                    if self.persistent_queue and series_id:
                        self.persistent_queue.insert(EntryId=series_id).on_conflict_ignore()
                else:
                    for object_id in object_ids:
                        while True:
                            try:
                                data = self.client.get_episode(object_id)
                                name = data.get("title")
                                series_id = data.get("series", {}).get("id")
                                if name:
                                    episodeNumber = data.get("episodeNumber", 0)
                                    absoluteEpisodeNumber = data.get("absoluteEpisodeNumber", 0)
                                    seasonNumber = data.get("seasonNumber", 0)
                                    seriesTitle = data.get("series", {}).get("title")
                                    year = data.get("series", {}).get("year", 0)
                                    tvdbId = data.get("series", {}).get("tvdbId", 0)
                                    self.logger.notice(
                                        "Re-Searching episode: %s (%s) | "
                                        "S%02dE%03d "
                                        "(E%04d) | "
                                        "%s | "
                                        "[tvdbId=%s|id=%s]",
                                        seriesTitle,
                                        year,
                                        seasonNumber,
                                        episodeNumber,
                                        absoluteEpisodeNumber,
                                        name,
                                        tvdbId,
                                        object_id,
                                    )
                                else:
                                    self.logger.notice("Re-Searching episode: %s", object_id)
                                break
                            except (
                                requests.exceptions.ChunkedEncodingError,
                                requests.exceptions.ContentDecodingError,
                                requests.exceptions.ConnectionError,
                                JSONDecodeError,
                                AttributeError,
                            ):
                                continue

                        if object_id in self.queue_file_ids:
                            self.queue_file_ids.remove(object_id)
                        while True:
                            try:
                                self.client.post_command("EpisodeSearch", episodeIds=[object_id])
                                break
                            except (
                                requests.exceptions.ChunkedEncodingError,
                                requests.exceptions.ContentDecodingError,
                                requests.exceptions.ConnectionError,
                                JSONDecodeError,
                            ):
                                continue
                        if self.persistent_queue:
                            self.persistent_queue.insert(EntryId=object_id).on_conflict_ignore()
            elif self.type == "radarr":
                self.logger.trace("Requeue cache entry: %s", object_id)
                while True:
                    try:
                        data = self.client.get_movie(object_id)
                        name = data.get("title")
                        if name:
                            year = data.get("year", 0)
                            tmdbId = data.get("tmdbId", 0)
                            self.logger.notice(
                                "Re-Searching movie: %s (%s) | [tmdbId=%s|id=%s]",
                                name,
                                year,
                                tmdbId,
                                object_id,
                            )
                        else:
                            self.logger.notice("Re-Searching movie: %s", object_id)
                        break
                    except (
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ConnectionError,
                        JSONDecodeError,
                        AttributeError,
                    ):
                        continue
                if object_id in self.queue_file_ids:
                    self.queue_file_ids.remove(object_id)
                while True:
                    try:
                        self.client.post_command("MoviesSearch", movieIds=[object_id])
                        break
                    except (
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ConnectionError,
                        JSONDecodeError,
                    ):
                        continue
                if self.persistent_queue:
                    self.persistent_queue.insert(EntryId=object_id).on_conflict_ignore()

    def _process_errored(self) -> None:
        # Recheck all torrents marked for rechecking.
        if self.recheck:
            self.needs_cleanup = True
            updated_recheck = list(self.recheck)
            self.manager.qbit.torrents_recheck(torrent_hashes=updated_recheck)
            for k in updated_recheck:
                if k not in self.timed_ignore_cache_2:
                    self.timed_ignore_cache_2.add(k)
                    self.timed_ignore_cache.add(k)
            self.recheck.clear()

    def _process_failed(self) -> None:
        to_delete_all = self.delete.union(
            self.missing_files_post_delete, self.downloads_with_bad_error_message_blocklist
        )
        if self.missing_files_post_delete or self.downloads_with_bad_error_message_blocklist:
            delete_ = True
        else:
            delete_ = False
        skip_blacklist = {
            i.upper() for i in self.skip_blacklist.union(self.missing_files_post_delete)
        }
        if to_delete_all:
            self.needs_cleanup = True
            payload = self.process_entries(to_delete_all)
            if payload:
                for entry, hash_ in payload:
                    self._process_failed_individual(
                        hash_=hash_, entry=entry, skip_blacklist=skip_blacklist
                    )
        if self.remove_from_qbit or self.skip_blacklist or to_delete_all:
            # Remove all bad torrents from the Client.
            temp_to_delete = set()
            if to_delete_all:
                self.manager.qbit.torrents_delete(hashes=to_delete_all, delete_files=True)
            if self.remove_from_qbit or self.skip_blacklist:
                temp_to_delete = self.remove_from_qbit.union(self.skip_blacklist)
                self.manager.qbit.torrents_delete(hashes=temp_to_delete, delete_files=True)

            to_delete_all = to_delete_all.union(temp_to_delete)
            for h in to_delete_all:
                self.cleaned_torrents.discard(h)
                self.sent_to_scan_hashes.discard(h)
                if h in self.manager.qbit_manager.name_cache:
                    del self.manager.qbit_manager.name_cache[h]
                if h in self.manager.qbit_manager.cache:
                    del self.manager.qbit_manager.cache[h]
        if delete_:
            self.missing_files_post_delete.clear()
            self.downloads_with_bad_error_message_blocklist.clear()
        self.skip_blacklist.clear()
        self.remove_from_qbit.clear()
        self.delete.clear()

    def _process_file_priority(self) -> None:
        # Set all files marked as "Do not download" to not download.
        for hash_, files in self.change_priority.copy().items():
            self.needs_cleanup = True
            name = self.manager.qbit_manager.name_cache.get(hash_)
            if name:
                self.logger.debug("Updating file priority on torrent: %s (%s)", name, hash_)
                self.manager.qbit.torrents_file_priority(
                    torrent_hash=hash_, file_ids=files, priority=0
                )
            else:
                self.logger.error("Torrent does not exist? %s", hash_)
            del self.change_priority[hash_]

    def _process_resume(self) -> None:
        if self.resume and AUTO_PAUSE_RESUME:
            self.needs_cleanup = True
            self.manager.qbit.torrents_resume(torrent_hashes=self.resume)
            for k in self.resume:
                self.timed_ignore_cache.add(k)
            self.resume.clear()

    def _remove_empty_folders(self) -> None:
        new_sent_to_scan = set()
        if not self.completed_folder.exists():
            return
        for path in absolute_file_paths(self.completed_folder):
            if path.is_dir() and not len(list(absolute_file_paths(path))):
                with contextlib.suppress(FileNotFoundError):
                    path.rmdir()
                self.logger.trace("Removing empty folder: %s", path)
                if path in self.sent_to_scan:
                    self.sent_to_scan.discard(path)
                else:
                    new_sent_to_scan.add(path)
        self.sent_to_scan = new_sent_to_scan
        if not len(list(absolute_file_paths(self.completed_folder))):
            self.sent_to_scan = set()
            self.sent_to_scan_hashes = set()

    def api_calls(self) -> None:
        if not self.is_alive:
            raise NoConnectionrException(
                f"Service: {self._name} did not respond on {self.uri}", type="arr"
            )
        now = datetime.now()
        if (
            self.rss_sync_timer_last_checked is not None
            and self.rss_sync_timer_last_checked < now - timedelta(minutes=self.rss_sync_timer)
        ):
            while True:
                try:
                    self.client.post_command("RssSync")
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ):
                    continue
            self.rss_sync_timer_last_checked = now

        if (
            self.refresh_downloads_timer_last_checked is not None
            and self.refresh_downloads_timer_last_checked
            < now - timedelta(minutes=self.refresh_downloads_timer)
        ):
            while True:
                try:
                    self.client.post_command("RefreshMonitoredDownloads")
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ):
                    continue
            self.refresh_downloads_timer_last_checked = now

    def arr_db_query_commands_count(self) -> int:
        search_commands = 0
        if not self.search_missing:
            return 0
        while True:
            try:
                commands = self.client.get_command()
                for command in commands:
                    if (
                        command["name"].endswith("Search")
                        and command["status"] != "completed"
                        and "Missing" not in command["name"]
                    ):
                        search_commands = search_commands + 1
                break
            except (
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ContentDecodingError,
                requests.exceptions.ConnectionError,
                JSONDecodeError,
            ):
                continue

        return search_commands

    def _search_todays(self, condition):
        if self.prioritize_todays_release:
            for entry in (
                self.model_file.select()
                .where(condition)
                .order_by(
                    self.model_file.SeriesTitle,
                    self.model_file.SeasonNumber.desc(),
                    self.model_file.AirDateUtc.desc(),
                )
                .execute()
            ):
                yield entry, True, True
        else:
            yield None, None, None

    def db_get_files(
        self,
    ) -> Iterable[
        tuple[MoviesFilesModel | EpisodeFilesModel | SeriesFilesModel, bool, bool, bool, int]
    ]:
        if self.type == "sonarr" and self.series_search:
            serieslist = self.db_get_files_series()
            for series in serieslist:
                yield series[0], series[1], series[2], series[2] is not True, len(serieslist)
        elif self.type == "sonarr" and not self.series_search:
            episodelist = self.db_get_files_episodes()
            for episodes in episodelist:
                yield episodes[0], episodes[1], episodes[2], False, len(episodelist)
        elif self.type == "radarr":
            movielist = self.db_get_files_movies()
            for movies in movielist:
                yield movies[0], movies[1], movies[2], False, len(movielist)

    def db_maybe_reset_entry_searched_state(self):
        if self.type == "sonarr":
            self.db_reset__series_searched_state()
            self.db_reset__episode_searched_state()
        elif self.type == "radarr":
            self.db_reset__movie_searched_state()
        self.loop_completed = False

    def db_reset__series_searched_state(self):
        ids = []
        self.series_file_model: SeriesFilesModel
        self.model_file: EpisodeFilesModel
        if (
            self.loop_completed and self.reset_on_completion and self.series_search
        ):  # Only wipe if a loop completed was tagged
            self.series_file_model.update(Searched=False, Upgrade=False).where(
                self.series_file_model.Searched is True
            ).execute()
            while True:
                try:
                    series = self.client.get_series()
                    for s in series:
                        ids.append(s["id"])
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ):
                    continue
            self.series_file_model.delete().where(
                self.series_file_model.EntryId.not_in(ids)
            ).execute()
            self.loop_completed = False

    def db_reset__episode_searched_state(self):
        ids = []
        self.model_file: EpisodeFilesModel
        if (
            self.loop_completed is True and self.reset_on_completion
        ):  # Only wipe if a loop completed was tagged
            self.model_file.update(Searched=False, Upgrade=False).where(
                self.model_file.Searched is True
            ).execute()
            while True:
                try:
                    series = self.client.get_series()
                    for s in series:
                        episodes = self.client.get_episode(s["id"], True)
                        for e in episodes:
                            ids.append(e["id"])
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ) as e:
                    continue
            self.model_file.delete().where(self.model_file.EntryId.not_in(ids)).execute()
            self.loop_completed = False

    def db_reset__movie_searched_state(self):
        ids = []
        self.model_file: MoviesFilesModel
        if (
            self.loop_completed is True and self.reset_on_completion
        ):  # Only wipe if a loop completed was tagged
            self.model_file.update(Searched=False, Upgrade=False).where(
                self.model_file.Searched is True
            ).execute()
            while True:
                try:
                    movies = self.client.get_movie()
                    for m in movies:
                        ids.append(m["id"])
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ):
                    continue
            self.model_file.delete().where(self.model_file.EntryId.not_in(ids)).execute()
            self.loop_completed = False

    def db_get_files_series(self) -> list[list[SeriesFilesModel, bool, bool]] | None:
        entries = []
        if not self.search_missing:
            return None
        elif not self.series_search:
            return None
        elif self.type == "sonarr":
            condition = self.model_file.AirDateUtc.is_null(False)
            if not self.search_specials:
                condition &= self.model_file.SeasonNumber != 0
            if self.do_upgrade_search:
                condition &= self.model_file.Upgrade == False
            else:
                if self.quality_unmet_search and not self.custom_format_unmet_search:
                    condition &= (
                        self.model_file.Searched == False | self.model_file.QualityMet == False
                    )
                elif not self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (
                        self.model_file.Searched
                        == False | self.model_file.CustomFormatMet
                        == False
                    )
                elif self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (
                        self.model_file.Searched
                        == False | self.model_file.QualityMet
                        == False | self.model_file.CustomFormatMet
                        == False
                    )
                else:
                    condition &= self.model_file.EpisodeFileId == 0
                    condition &= self.model_file.Searched == False
            todays_condition = copy(condition)
            todays_condition &= self.model_file.AirDateUtc > (
                datetime.now(timezone.utc) - timedelta(days=1)
            )
            todays_condition &= self.model_file.AirDateUtc < (
                datetime.now(timezone.utc) - timedelta(hours=1)
            )
            condition &= self.model_file.AirDateUtc < (
                datetime.now(timezone.utc) - timedelta(days=1)
            )
            if self.search_by_year:
                condition &= (
                    self.model_file.AirDateUtc
                    >= datetime(month=1, day=1, year=int(self.search_current_year)).date()
                )
                condition &= (
                    self.model_file.AirDateUtc
                    <= datetime(month=12, day=31, year=int(self.search_current_year)).date()
                )
            for i1, i2, i3 in self._search_todays(condition):
                if i1 is not None:
                    entries.append([i1, i2, i3])
            if not self.do_upgrade_search:
                condition = self.series_file_model.Searched == False
            else:
                condition = self.series_file_model.Upgrade == False
            for entry_ in (
                self.series_file_model.select()
                .where(condition)
                .order_by(self.series_file_model.EntryId.asc())
                .execute()
            ):
                self.logger.trace("Adding %s to search list", entry_.Title)
                entries.append([entry_, False, False])
            return entries

    def db_get_files_episodes(self) -> list[list[EpisodeFilesModel, bool, bool]] | None:
        entries = []
        if not self.search_missing:
            return None
        elif self.type == "sonarr":
            condition = self.model_file.AirDateUtc.is_null(False)
            if not self.search_specials:
                condition &= self.model_file.SeasonNumber != 0
            if self.do_upgrade_search:
                condition &= self.model_file.Upgrade == False
            else:
                if self.quality_unmet_search and not self.custom_format_unmet_search:
                    condition &= (
                        self.model_file.Searched == False | self.model_file.QualityMet == False
                    )
                elif not self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (
                        self.model_file.Searched
                        == False | self.model_file.CustomFormatMet
                        == False
                    )
                elif self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (
                        self.model_file.Searched
                        == False | self.model_file.QualityMet
                        == False | self.model_file.CustomFormatMet
                        == False
                    )
                else:
                    condition &= self.model_file.EpisodeFileId == 0
                    condition &= self.model_file.Searched == False
            today_condition = copy(condition)
            today_condition &= self.model_file.AirDateUtc > (
                datetime.now(timezone.utc) - timedelta(days=1)
            )
            today_condition &= self.model_file.AirDateUtc < (
                datetime.now(timezone.utc) - timedelta(hours=1)
            )
            condition &= self.model_file.AirDateUtc < (
                datetime.now(timezone.utc) - timedelta(days=1)
            )
            if self.search_by_year:
                condition &= (
                    self.model_file.AirDateUtc
                    >= datetime(month=1, day=1, year=int(self.search_current_year)).date()
                )
                condition &= (
                    self.model_file.AirDateUtc
                    <= datetime(month=12, day=31, year=int(self.search_current_year)).date()
                )
            for entry in (
                self.model_file.select()
                .where(condition)
                .order_by(
                    self.model_file.SeriesTitle,
                    self.model_file.SeasonNumber.desc(),
                    self.model_file.AirDateUtc.desc(),
                )
                .group_by(self.model_file.SeriesId)
                .order_by(self.model_file.EpisodeFileId.asc())
                .execute()
            ):
                entries.append([entry, False, False])
            for i1, i2, i3 in self._search_todays(today_condition):
                if i1 is not None:
                    entries.append([i1, i2, i3])
            return entries

    def db_get_files_movies(self) -> list[list[MoviesFilesModel, bool, bool]] | None:
        entries = []
        if not self.search_missing:
            return None
        if self.type == "radarr":
            condition = self.model_file.Year.is_null(False)
            if self.do_upgrade_search:
                condition &= self.model_file.Upgrade == False
            else:
                if self.quality_unmet_search and not self.custom_format_unmet_search:
                    condition &= (
                        self.model_file.Searched == False | self.model_file.QualityMet == False
                    )
                elif not self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (
                        self.model_file.Searched
                        == False | self.model_file.CustomFormatMet
                        == False
                    )
                elif self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (
                        self.model_file.Searched
                        == False | self.model_file.QualityMet
                        == False | self.model_file.CustomFormatMet
                        == False
                    )
                else:
                    condition &= self.model_file.MovieFileId == 0
                    condition &= self.model_file.Searched == False
            if self.search_by_year:
                condition &= self.model_file.Year == self.search_current_year
            for entry in (
                self.model_file.select()
                .where(condition)
                .order_by(self.model_file.MovieFileId.asc())
                .execute()
            ):
                entries.append([entry, False, False])
            return entries

    def db_get_request_files(self) -> Iterable[tuple[MoviesFilesModel | EpisodeFilesModel, int]]:
        entries = []
        self.logger.trace("Getting request files")
        if self.type == "sonarr":
            condition = self.model_file.IsRequest == True
            condition &= self.model_file.AirDateUtc.is_null(False)
            condition &= self.model_file.EpisodeFileId == 0
            condition &= self.model_file.Searched == False
            condition &= self.model_file.AirDateUtc < (
                datetime.now(timezone.utc) - timedelta(days=1)
            )
            entries = list(
                self.model_file.select()
                .where(condition)
                .order_by(
                    self.model_file.SeriesTitle,
                    self.model_file.SeasonNumber.desc(),
                    self.model_file.AirDateUtc.desc(),
                )
                .execute()
            )
        elif self.type == "radarr":
            condition = self.model_file.IsRequest == True
            condition &= self.model_file.Year.is_null(False)
            condition &= self.model_file.MovieFileId == 0
            condition &= self.model_file.Searched == False
            entries = list(
                self.model_file.select()
                .where(condition)
                .order_by(self.model_file.Title.asc())
                .execute()
            )
        for entry in entries:
            yield entry, len(entries)

    def db_request_update(self):
        if self.overseerr_requests:
            self.db_overseerr_update()
        else:
            self.db_ombi_update()

    def _db_request_update(self, request_ids: dict[str, set[int | str]]):
        if self.type == "sonarr" and any(i in request_ids for i in ["ImdbId", "TvdbId"]):
            TvdbIds = request_ids.get("TvdbId")
            ImdbIds = request_ids.get("ImdbId")
            while True:
                try:
                    series = self.client.get_series()
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ):
                    continue
            for s in series:
                episodes = self.client.get_episode(s["id"], True)
                for e in episodes:
                    if "airDateUtc" in e:
                        if datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                            tzinfo=timezone.utc
                        ) > datetime.now(timezone.utc):
                            continue
                        if not self.search_specials and e["seasonNumber"] == 0:
                            continue
                        if TvdbIds and ImdbIds and "tvdbId" in e and "imdbId" in e:
                            if s["tvdbId"] not in TvdbIds or s["imdbId"] not in ImdbIds:
                                continue
                        if ImdbIds and "imdbId" in e:
                            if s["imdbId"] not in ImdbIds:
                                continue
                        if TvdbIds and "tvdbId" in e:
                            if s["tvdbId"] not in TvdbIds:
                                continue
                        if not e["monitored"]:
                            continue
                        if e["episodeFileId"] != 0:
                            continue
                        self.db_update_single_series(db_entry=e, request=True)
        elif self.type == "radarr" and any(i in request_ids for i in ["ImdbId", "TmdbId"]):
            ImdbIds = request_ids.get("ImdbId")
            TmdbIds = request_ids.get("TmdbId")
            while True:
                try:
                    movies = self.client.get_movie()
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ):
                    continue
            for m in movies:
                if m["year"] > datetime.now().year and m["year"] == 0:
                    continue
                if TmdbIds and ImdbIds and "tmdbId" in m and "imdbId" in m:
                    if m["tmdbId"] not in TmdbIds or m["imdbId"] not in ImdbIds:
                        continue
                if ImdbIds and "imdbId" in m:
                    if m["imdbId"] not in ImdbIds:
                        continue
                if TmdbIds and "tmdbId" in m:
                    if m["tmdbId"] not in TmdbIds:
                        continue
                if not m["monitored"]:
                    continue
                if m["hasFile"]:
                    continue
                self.db_update_single_series(db_entry=m, request=True)

    def db_overseerr_update(self):
        if (not self.search_missing) or (not self.overseerr_requests):
            return
        if self._get_overseerr_requests_count() == 0:
            return
        request_ids = self._temp_overseer_request_cache
        if not any(i in request_ids for i in ["ImdbId", "TmdbId", "TvdbId"]):
            return
        self.logger.notice("Started updating database with Overseerr request entries.")
        self._db_request_update(request_ids)
        self.logger.notice("Finished updating database with Overseerr request entries")

    def db_ombi_update(self):
        if (not self.search_missing) or (not self.ombi_search_requests):
            return
        if self._get_ombi_request_count() == 0:
            return
        request_ids = self._process_ombi_requests()
        if not any(i in request_ids for i in ["ImdbId", "TmdbId", "TvdbId"]):
            return
        self.logger.notice("Started updating database with Ombi request entries.")
        self._db_request_update(request_ids)
        self.logger.notice("Finished updating database with Ombi request entries")

    def db_update_todays_releases(self):
        if not self.prioritize_todays_release:
            return
        if self.type == "sonarr":
            try:
                while True:
                    try:
                        series = self.client.get_series()
                        break
                    except (
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ConnectionError,
                        JSONDecodeError,
                    ):
                        continue
                for s in series:
                    episodes = self.client.get_episode(s["id"], True)
                    for e in episodes:
                        if "airDateUtc" in e:
                            if (
                                datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ")
                                .replace(tzinfo=timezone.utc)
                                .date()
                                > datetime.now(timezone.utc).date()
                                or datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ")
                                .replace(tzinfo=timezone.utc)
                                .date()
                                < datetime.now(timezone.utc).date()
                            ):
                                continue
                            if not self.search_specials and e["seasonNumber"] == 0:
                                continue
                            if not e["monitored"]:
                                continue
                            if e["episodeFileId"] != 0:
                                continue
                            self.logger.trace("Updating todays releases")
                            self.db_update_single_series(db_entry=e)
            except BaseException:
                self.logger.debug("No episode releases found for today")

    def db_update(self):
        if not self.search_missing:
            return
        self.db_update_todays_releases()
        if self.db_update_processed and not self.search_by_year:
            return
        if self.search_by_year:
            self.logger.info("Started updating database for %s", self.search_current_year)
        else:
            self.logger.info("Started updating database")
        if self.type == "sonarr":
            if not self.series_search:
                while True:
                    try:
                        series = self.client.get_series()
                        break
                    except (
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ConnectionError,
                        JSONDecodeError,
                    ):
                        continue
                if self.search_by_year:
                    for s in series:
                        if isinstance(s, str):
                            continue
                        episodes = self.client.get_episode(s["id"], True)
                        for e in episodes:
                            if isinstance(e, str):
                                continue
                            if "airDateUtc" in e:
                                if datetime.strptime(
                                    e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ"
                                ).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                                    continue
                                if (
                                    datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ")
                                    .replace(tzinfo=timezone.utc)
                                    .date()
                                    < datetime(
                                        month=1, day=1, year=int(self.search_current_year)
                                    ).date()
                                ):
                                    continue
                                if (
                                    datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ")
                                    .replace(tzinfo=timezone.utc)
                                    .date()
                                    > datetime(
                                        month=12, day=31, year=int(self.search_current_year)
                                    ).date()
                                ):
                                    continue
                                if not self.search_specials and e["seasonNumber"] == 0:
                                    continue
                                self.db_update_single_series(db_entry=e)

                else:
                    for s in series:
                        if isinstance(s, str):
                            continue
                        episodes = self.client.get_episode(s["id"], True)
                        for e in episodes:
                            if isinstance(e, str):
                                continue
                            if "airDateUtc" in e:
                                if datetime.strptime(
                                    e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ"
                                ).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                                    continue
                                if not self.search_specials and e["seasonNumber"] == 0:
                                    continue
                                self.db_update_single_series(db_entry=e)
                self.db_update_processed = True
            else:
                while True:
                    try:
                        series = self.client.get_series()
                        break
                    except (
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ConnectionError,
                        JSONDecodeError,
                    ):
                        continue
                if self.search_by_year:
                    for s in series:
                        if isinstance(s, str):
                            continue
                        if s["year"] < self.search_current_year:
                            continue
                        if s["year"] > self.search_current_year:
                            continue
                        self.db_update_single_series(db_entry=s, series=True)
                else:
                    for s in series:
                        if isinstance(s, str):
                            continue
                        self.db_update_single_series(db_entry=s, series=True)
                self.db_update_processed = True
        elif self.type == "radarr":
            while True:
                try:
                    movies = self.client.get_movie()
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ):
                    continue
            if self.search_by_year:
                for m in movies:
                    if isinstance(m, str):
                        continue
                    if m["year"] < self.search_current_year:
                        continue
                    if m["year"] > self.search_current_year:
                        continue
                    self.db_update_single_series(db_entry=m)
            else:
                for m in movies:
                    if isinstance(m, str):
                        continue
                    self.db_update_single_series(db_entry=m)
            self.db_update_processed = True
        self.logger.trace("Finished updating database")

    def minimum_availability_check(self, db_entry: JsonObject) -> bool:
        inCinemas = (
            datetime.strptime(db_entry["inCinemas"], "%Y-%m-%dT%H:%M:%SZ")
            if "inCinemas" in db_entry
            else None
        )
        digitalRelease = (
            datetime.strptime(db_entry["digitalRelease"], "%Y-%m-%dT%H:%M:%SZ")
            if "digitalRelease" in db_entry
            else None
        )
        physicalRelease = (
            datetime.strptime(db_entry["physicalRelease"], "%Y-%m-%dT%H:%M:%SZ")
            if "physicalRelease" in db_entry
            else None
        )
        now = datetime.now()
        if db_entry["year"] > now.year or db_entry["year"] == 0:
            self.logger.trace(
                "Skipping 1 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                db_entry["title"],
                db_entry["minimumAvailability"],
                inCinemas,
                digitalRelease,
                physicalRelease,
            )
            return False
        elif db_entry["year"] < now.year - 1 and db_entry["year"] != 0:
            self.logger.trace(
                "Grabbing 2 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                db_entry["title"],
                db_entry["minimumAvailability"],
                inCinemas,
                digitalRelease,
                physicalRelease,
            )
            return True
        elif (
            "inCinemas" not in db_entry
            and "digitalRelease" not in db_entry
            and "physicalRelease" not in db_entry
            and db_entry["minimumAvailability"] == "released"
        ):
            self.logger.trace(
                "Grabbing 3 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                db_entry["title"],
                db_entry["minimumAvailability"],
                inCinemas,
                digitalRelease,
                physicalRelease,
            )
            return True
        elif (
            "digitalRelease" in db_entry
            and "physicalRelease" in db_entry
            and db_entry["minimumAvailability"] == "released"
        ):
            if digitalRelease <= now or physicalRelease <= now:
                self.logger.trace(
                    "Grabbing 4 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return True
            else:
                self.logger.trace(
                    "Skipping 5 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return False
        elif ("digitalRelease" in db_entry or "physicalRelease" in db_entry) and db_entry[
            "minimumAvailability"
        ] == "released":
            if "digitalRelease" in db_entry:
                if digitalRelease <= now:
                    self.logger.trace(
                        "Grabbing 6 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                        db_entry["title"],
                        db_entry["minimumAvailability"],
                        inCinemas,
                        digitalRelease,
                        physicalRelease,
                    )
                    return True
                else:
                    self.logger.trace(
                        "Skipping 7 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                        db_entry["title"],
                        db_entry["minimumAvailability"],
                        inCinemas,
                        digitalRelease,
                        physicalRelease,
                    )
                    return False
            elif "physicalRelease" in db_entry:
                if physicalRelease <= now:
                    self.logger.trace(
                        "Grabbing 8 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                        db_entry["title"],
                        db_entry["minimumAvailability"],
                        inCinemas,
                        digitalRelease,
                        physicalRelease,
                    )
                    return True
                else:
                    self.logger.trace(
                        "Skipping 9 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                        db_entry["title"],
                        db_entry["minimumAvailability"],
                        inCinemas,
                        digitalRelease,
                        physicalRelease,
                    )
                    return False
        elif (
            "inCinemas" not in db_entry
            and "digitalRelease" not in db_entry
            and "physicalRelease" not in db_entry
            and db_entry["minimumAvailability"] == "inCinemas"
        ):
            self.logger.trace(
                "Grabbing 10 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                db_entry["title"],
                db_entry["minimumAvailability"],
                inCinemas,
                digitalRelease,
                physicalRelease,
            )
            return True
        elif "inCinemas" in db_entry and db_entry["minimumAvailability"] == "inCinemas":
            if inCinemas <= now:
                self.logger.trace(
                    "Grabbing 11 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return True
            else:
                self.logger.trace(
                    "Skipping 12 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return False
        elif "inCinemas" not in db_entry and db_entry["minimumAvailability"] == "inCinemas":
            if "digitalRelease" in db_entry:
                if digitalRelease <= now:
                    self.logger.trace(
                        "Grabbing 13 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                        db_entry["title"],
                        db_entry["minimumAvailability"],
                        inCinemas,
                        digitalRelease,
                        physicalRelease,
                    )
                    return True
                else:
                    self.logger.trace(
                        "Skipping 14 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                        db_entry["title"],
                        db_entry["minimumAvailability"],
                        inCinemas,
                        digitalRelease,
                        physicalRelease,
                    )
                    return False
            elif "physicalRelease" in db_entry:
                if physicalRelease <= now:
                    self.logger.trace(
                        "Grabbing 15 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                        db_entry["title"],
                        db_entry["minimumAvailability"],
                        inCinemas,
                        digitalRelease,
                        physicalRelease,
                    )
                    return True
                else:
                    self.logger.trace(
                        "Skipping 16 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                        db_entry["title"],
                        db_entry["minimumAvailability"],
                        inCinemas,
                        digitalRelease,
                        physicalRelease,
                    )
                    return False
            else:
                self.logger.trace(
                    "Skipping 17 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                    db_entry["title"],
                    db_entry["minimumAvailability"],
                    inCinemas,
                    digitalRelease,
                    physicalRelease,
                )
                return False
        elif db_entry["minimumAvailability"] == "announced":
            self.logger.trace(
                "Grabbing 18 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                db_entry["title"],
                db_entry["minimumAvailability"],
                inCinemas,
                digitalRelease,
                physicalRelease,
            )
            return True
        else:
            self.logger.trace(
                "Skipping 19 %s - Minimum Availability: %s, Dates Cinema:%s, Digital:%s, Physical:%s",
                db_entry["title"],
                db_entry["minimumAvailability"],
                inCinemas,
                digitalRelease,
                physicalRelease,
            )
            return False

    def db_update_single_series(
        self, db_entry: JsonObject = None, request: bool = False, series: bool = False
    ):
        if not self.search_missing:
            return
        try:
            searched = False
            if self.type == "sonarr":
                if not series:
                    self.model_file: EpisodeFilesModel
                    episodeData = self.model_file.get_or_none(
                        self.model_file.EntryId == db_entry["id"]
                    )
                    while True:
                        try:
                            episode = self.client.get_episode(db_entry["id"])
                            break
                        except (
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                        ):
                            continue
                    if episode["monitored"] or self.search_unmonitored:
                        while True:
                            try:
                                if episodeData:
                                    if not episodeData.MinCustomFormatScore:
                                        minCustomFormat = self.client.get_quality_profile(
                                            episode["series"]["qualityProfileId"]
                                        )["minFormatScore"]
                                    else:
                                        minCustomFormat = episodeData.MinCustomFormatScore
                                    if episode["hasFile"]:
                                        if (
                                            episode["episodeFile"]["id"]
                                            != episodeData.EpisodeFileId
                                        ):
                                            customFormat = self.client.get_episode_file(
                                                episode["episodeFile"]["id"]
                                            )["customFormatScore"]
                                        else:
                                            customFormat = episodeData.CustomFormatScore
                                    else:
                                        customFormat = 0
                                else:
                                    minCustomFormat = self.client.get_quality_profile(
                                        episode["series"]["qualityProfileId"]
                                    )["minFormatScore"]
                                    if episode["hasFile"]:
                                        customFormat = self.client.get_episode_file(
                                            episode["episodeFile"]["id"]
                                        )["customFormatScore"]
                                    else:
                                        customFormat = 0
                                break
                            except (
                                requests.exceptions.ChunkedEncodingError,
                                requests.exceptions.ContentDecodingError,
                                requests.exceptions.ConnectionError,
                                JSONDecodeError,
                            ):
                                continue
                            except KeyError:
                                self.logger.warning("Key Error [%s]", db_entry["id"])
                                continue

                        QualityUnmet = (
                            episode["episodeFile"]["qualityCutoffNotMet"]
                            if "episodeFile" in episode
                            else False
                        )
                        if (
                            episode["hasFile"]
                            and not (self.quality_unmet_search and QualityUnmet)
                            and not (
                                self.custom_format_unmet_search and customFormat <= minCustomFormat
                            )
                        ):
                            searched = True
                            self.model_queue.update(Completed=True).where(
                                self.model_queue.EntryId == episode["id"]
                            ).execute()

                        if self.use_temp_for_missing:
                            try:
                                self.logger.trace(
                                    "Temp quality profile [%s][%s]",
                                    searched,
                                    db_entry["qualityProfileId"],
                                )
                                if (
                                    searched
                                    and db_entry["qualityProfileId"]
                                    in self.temp_quality_profile_ids.values()
                                    and not self.keep_temp_profile
                                ):
                                    data: JsonObject = {
                                        "qualityProfileId": list(
                                            self.temp_quality_profile_ids.keys()
                                        )[
                                            list(self.temp_quality_profile_ids.values()).index(
                                                db_entry["qualityProfileId"]
                                            )
                                        ]
                                    }
                                    self.logger.debug(
                                        "Upgrading quality profile for %s to %s",
                                        db_entry["title"],
                                        list(self.temp_quality_profile_ids.keys())[
                                            list(self.temp_quality_profile_ids.values()).index(
                                                db_entry["qualityProfileId"]
                                            )
                                        ],
                                    )
                                elif (
                                    not searched
                                    and db_entry["qualityProfileId"]
                                    in self.temp_quality_profile_ids.keys()
                                ):
                                    data: JsonObject = {
                                        "qualityProfileId": self.temp_quality_profile_ids[
                                            db_entry["qualityProfileId"]
                                        ]
                                    }
                                    self.logger.debug(
                                        "Downgrading quality profile for %s to %s",
                                        db_entry["title"],
                                        self.temp_quality_profile_ids[
                                            db_entry["qualityProfileId"]
                                        ],
                                    )
                            except KeyError:
                                self.logger.warning(
                                    "Check quality profile settings for %s", db_entry["title"]
                                )
                            try:
                                if data:
                                    while True:
                                        try:
                                            self.client.upd_episode(episode["id"], data)
                                            break
                                        except (
                                            requests.exceptions.ChunkedEncodingError,
                                            requests.exceptions.ContentDecodingError,
                                            requests.exceptions.ConnectionError,
                                            JSONDecodeError,
                                        ):
                                            continue
                            except UnboundLocalError:
                                pass

                        EntryId = episode["id"]
                        SeriesTitle = episode.get("series", {}).get("title")
                        SeasonNumber = episode["seasonNumber"]
                        Title = episode["title"]
                        SeriesId = episode["seriesId"]
                        EpisodeFileId = episode["episodeFileId"]
                        EpisodeNumber = episode["episodeNumber"]
                        AbsoluteEpisodeNumber = (
                            episode["absoluteEpisodeNumber"]
                            if "absoluteEpisodeNumber" in episode
                            else None
                        )
                        SceneAbsoluteEpisodeNumber = (
                            episode["sceneAbsoluteEpisodeNumber"]
                            if "sceneAbsoluteEpisodeNumber" in episode
                            else None
                        )
                        AirDateUtc = episode["airDateUtc"]
                        Monitored = episode["monitored"]
                        QualityMet = not QualityUnmet if db_entry["hasFile"] else False
                        customFormatMet = customFormat >= minCustomFormat

                        if not episode["hasFile"]:
                            reason = "Missing"
                        elif self.quality_unmet_search and QualityUnmet:
                            reason = "Quality"
                        elif self.custom_format_unmet_search and not customFormatMet:
                            reason = "CustomFormat"
                        elif self.do_upgrade_search:
                            reason = "Upgrade"
                        else:
                            reason = None

                        to_update = {
                            self.model_file.Monitored: Monitored,
                            self.model_file.Title: Title,
                            self.model_file.AirDateUtc: AirDateUtc,
                            self.model_file.SceneAbsoluteEpisodeNumber: SceneAbsoluteEpisodeNumber,
                            self.model_file.AbsoluteEpisodeNumber: AbsoluteEpisodeNumber,
                            self.model_file.EpisodeNumber: EpisodeNumber,
                            self.model_file.EpisodeFileId: EpisodeFileId,
                            self.model_file.SeriesId: SeriesId,
                            self.model_file.SeriesTitle: SeriesTitle,
                            self.model_file.SeasonNumber: SeasonNumber,
                            self.model_file.QualityMet: QualityMet,
                            self.model_file.Upgrade: False,
                            self.model_file.Searched: searched,
                            self.model_file.MinCustomFormatScore: minCustomFormat,
                            self.model_file.CustomFormatScore: customFormat,
                            self.model_file.CustomFormatMet: customFormatMet,
                            self.model_file.Reason: reason,
                        }

                        self.logger.debug(
                            "Updating database entry | %s | S%02dE%03d [Searched:%s][Upgrade:%s][QualityMet:%s][CustomFormatMet:%s]",
                            SeriesTitle.ljust(60, "."),
                            SeasonNumber,
                            EpisodeNumber,
                            str(searched).ljust(5),
                            str(False).ljust(5),
                            str(QualityMet).ljust(5),
                            str(customFormatMet).ljust(5),
                        )

                        if request:
                            to_update[self.model_file.IsRequest] = request

                        db_commands = self.model_file.insert(
                            EntryId=EntryId,
                            Title=Title,
                            SeriesId=SeriesId,
                            EpisodeFileId=EpisodeFileId,
                            EpisodeNumber=EpisodeNumber,
                            AbsoluteEpisodeNumber=AbsoluteEpisodeNumber,
                            SceneAbsoluteEpisodeNumber=SceneAbsoluteEpisodeNumber,
                            AirDateUtc=AirDateUtc,
                            Monitored=Monitored,
                            SeriesTitle=SeriesTitle,
                            SeasonNumber=SeasonNumber,
                            Searched=searched,
                            IsRequest=request,
                            QualityMet=QualityMet,
                            Upgrade=False,
                            MinCustomFormatScore=minCustomFormat,
                            CustomFormatScore=customFormat,
                            CustomFormatMet=customFormatMet,
                            Reason=reason,
                        ).on_conflict(conflict_target=[self.model_file.EntryId], update=to_update)
                        db_commands.execute()
                    else:
                        db_commands = self.model_file.delete().where(
                            self.model_file.EntryId == episode["id"]
                        )
                        db_commands.execute()
                else:
                    self.series_file_model: SeriesFilesModel
                    EntryId = db_entry["id"]
                    seriesData = self.model_file.get_or_none(self.model_file.EntryId == EntryId)
                    if db_entry["monitored"] or self.search_unmonitored:
                        while True:
                            try:
                                seriesMetadata = self.client.get_series(id_=EntryId)
                                if not seriesData:
                                    minCustomFormat = self.client.get_quality_profile(
                                        seriesMetadata["qualityProfileId"]
                                    )["minFormatScore"]
                                else:
                                    minCustomFormat = seriesMetadata.MinCustomFormatScore
                                break
                            except (
                                requests.exceptions.ChunkedEncodingError,
                                requests.exceptions.ContentDecodingError,
                                requests.exceptions.ConnectionError,
                                JSONDecodeError,
                            ):
                                continue
                            except KeyError:
                                self.logger.warning(
                                    "Key Error [%s][%s]", db_entry["id"], seriesMetadata
                                )
                                continue
                        episodeCount = 0
                        episodeFileCount = 0
                        totalEpisodeCount = 0
                        monitoredEpisodeCount = 0
                        seasons = seriesMetadata.get("seasons")
                        for season in seasons:
                            sdict = dict(season)
                            if sdict.get("seasonNumber") == 0:
                                statistics = sdict.get("statistics")
                                monitoredEpisodeCount = monitoredEpisodeCount + statistics.get(
                                    "episodeCount", 0
                                )
                                totalEpisodeCount = totalEpisodeCount + statistics.get(
                                    "totalEpisodeCount", 0
                                )
                                episodeFileCount = episodeFileCount + statistics.get(
                                    "episodeFileCount", 0
                                )
                            else:
                                statistics = sdict.get("statistics")
                                episodeCount = episodeCount + statistics.get("episodeCount")
                                totalEpisodeCount = totalEpisodeCount + statistics.get(
                                    "totalEpisodeCount"
                                )
                                episodeFileCount = episodeFileCount + statistics.get(
                                    "episodeFileCount"
                                )
                        if self.search_specials:
                            searched = totalEpisodeCount == episodeFileCount
                        else:
                            searched = (episodeCount + monitoredEpisodeCount) == episodeFileCount
                        if self.use_temp_for_missing:
                            try:
                                if (
                                    searched
                                    and db_entry["qualityProfileId"]
                                    in self.temp_quality_profile_ids.values()
                                    and not self.keep_temp_profile
                                ):
                                    db_entry["qualityProfileId"] = list(
                                        self.temp_quality_profile_ids.keys()
                                    )[
                                        list(self.temp_quality_profile_ids.values()).index(
                                            db_entry["qualityProfileId"]
                                        )
                                    ]
                                    self.logger.debug(
                                        "Updating quality profile for %s to %s",
                                        db_entry["title"],
                                        db_entry["qualityProfileId"],
                                    )
                                elif (
                                    not searched
                                    and db_entry["qualityProfileId"]
                                    in self.temp_quality_profile_ids.keys()
                                ):
                                    db_entry["qualityProfileId"] = self.temp_quality_profile_ids[
                                        db_entry["qualityProfileId"]
                                    ]
                                    self.logger.debug(
                                        "Updating quality profile for %s to %s",
                                        db_entry["title"],
                                        self.temp_quality_profile_ids[
                                            db_entry["qualityProfileId"]
                                        ],
                                    )
                            except KeyError:
                                self.logger.warning(
                                    "Check quality profile settings for %s", db_entry["title"]
                                )
                            while True:
                                try:
                                    self.client.upd_series(db_entry)
                                    break
                                except (
                                    requests.exceptions.ChunkedEncodingError,
                                    requests.exceptions.ContentDecodingError,
                                    requests.exceptions.ConnectionError,
                                    JSONDecodeError,
                                ):
                                    continue

                        Title = seriesMetadata.get("title")
                        Monitored = db_entry["monitored"]

                        to_update = {
                            self.series_file_model.Monitored: Monitored,
                            self.series_file_model.Title: Title,
                            self.series_file_model.Searched: searched,
                            self.series_file_model.Upgrade: False,
                            self.series_file_model.MinCustomFormatScore: minCustomFormat,
                        }

                        self.logger.debug(
                            "Updating database entry | %s [Searched:%s][Upgrade:%s]",
                            Title.ljust(60, "."),
                            str(searched).ljust(5),
                            str(False).ljust(5),
                        )

                        db_commands = self.series_file_model.insert(
                            EntryId=EntryId,
                            Title=Title,
                            Searched=searched,
                            Monitored=Monitored,
                            Upgrade=False,
                            MinCustomFormatScore=minCustomFormat,
                        ).on_conflict(
                            conflict_target=[self.series_file_model.EntryId], update=to_update
                        )
                        db_commands.execute()
                    else:
                        db_commands = self.series_file_model.delete().where(
                            self.series_file_model.EntryId == EntryId
                        )
                        db_commands.execute()

            elif self.type == "radarr":
                self.model_file: MoviesFilesModel
                searched = False
                movieData = self.model_file.get_or_none(self.model_file.EntryId == db_entry["id"])
                if self.minimum_availability_check(db_entry) and (
                    db_entry["monitored"] or self.search_unmonitored
                ):
                    while True:
                        try:
                            if movieData:
                                if not movieData.MinCustomFormatScore:
                                    minCustomFormat = self.client.get_quality_profile(
                                        db_entry["qualityProfileId"]
                                    )["minFormatScore"]
                                else:
                                    minCustomFormat = movieData.MinCustomFormatScore
                                if db_entry["hasFile"]:
                                    if db_entry["movieFile"]["id"] != movieData.MovieFileId:
                                        customFormat = self.client.get_movie_file(
                                            db_entry["movieFile"]["id"]
                                        )["customFormatScore"]
                                    else:
                                        customFormat = movieData.CustomFormatScore
                                else:
                                    customFormat = 0
                            else:
                                minCustomFormat = self.client.get_quality_profile(
                                    db_entry["qualityProfileId"]
                                )["minFormatScore"]
                                if db_entry["hasFile"]:
                                    customFormat = self.client.get_movie_file(
                                        db_entry["movieFile"]["id"]
                                    )["customFormatScore"]
                                else:
                                    customFormat = 0
                            break
                        except (
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                            KeyError,
                        ):
                            continue
                        # except KeyError:
                        #     self.logger.warning("Key Error [%s]", db_entry["id"])
                    QualityUnmet = (
                        db_entry["episodeFile"]["qualityCutoffNotMet"]
                        if "episodeFile" in db_entry
                        else False
                    )
                    if (
                        db_entry["hasFile"]
                        and not (self.quality_unmet_search and QualityUnmet)
                        and not (
                            self.custom_format_unmet_search and customFormat <= minCustomFormat
                        )
                    ):
                        searched = True
                        self.model_queue.update(Completed=True).where(
                            self.model_queue.EntryId == db_entry["id"]
                        ).execute()

                    if self.use_temp_for_missing:
                        try:
                            if (
                                searched
                                and db_entry["qualityProfileId"]
                                in self.temp_quality_profile_ids.values()
                                and not self.keep_temp_profile
                            ):
                                db_entry["qualityProfileId"] = list(
                                    self.temp_quality_profile_ids.keys()
                                )[
                                    list(self.temp_quality_profile_ids.values()).index(
                                        db_entry["qualityProfileId"]
                                    )
                                ]
                                self.logger.debug(
                                    "Updating quality profile for %s to %s",
                                    db_entry["title"],
                                    db_entry["qualityProfileId"],
                                )
                            elif (
                                not searched
                                and db_entry["qualityProfileId"]
                                in self.temp_quality_profile_ids.keys()
                            ):
                                db_entry["qualityProfileId"] = self.temp_quality_profile_ids[
                                    db_entry["qualityProfileId"]
                                ]
                                self.logger.debug(
                                    "Updating quality profile for %s to %s",
                                    db_entry["title"],
                                    self.temp_quality_profile_ids[db_entry["qualityProfileId"]],
                                )
                        except KeyError:
                            self.logger.warning(
                                "Check quality profile settings for %s", db_entry["title"]
                            )
                        while True:
                            try:
                                self.client.upd_movie(db_entry)
                                break
                            except (
                                requests.exceptions.ChunkedEncodingError,
                                requests.exceptions.ContentDecodingError,
                                requests.exceptions.ConnectionError,
                                JSONDecodeError,
                            ):
                                continue

                    title = db_entry["title"]
                    monitored = db_entry["monitored"]
                    tmdbId = db_entry["tmdbId"]
                    year = db_entry["year"]
                    entryId = db_entry["id"]
                    movieFileId = db_entry["movieFileId"]
                    qualityMet = not QualityUnmet if db_entry["hasFile"] else False
                    customFormatMet = customFormat >= minCustomFormat

                    if not db_entry["hasFile"]:
                        reason = "Missing"
                    elif self.quality_unmet_search and QualityUnmet:
                        reason = "Quality"
                    elif self.custom_format_unmet_search and not customFormatMet:
                        reason = "CustomFormat"
                    elif self.do_upgrade_search:
                        reason = "Upgrade"
                    else:
                        reason = None

                    to_update = {
                        self.model_file.MovieFileId: movieFileId,
                        self.model_file.Monitored: monitored,
                        self.model_file.QualityMet: qualityMet,
                        self.model_file.Searched: searched,
                        self.model_file.Upgrade: False,
                        self.model_file.MinCustomFormatScore: minCustomFormat,
                        self.model_file.CustomFormatScore: customFormat,
                        self.model_file.CustomFormatMet: customFormatMet,
                        self.model_file.Reason: reason,
                    }

                    if request:
                        to_update[self.model_file.IsRequest] = request

                    self.logger.debug(
                        "Updating database entry | %s [Searched:%s][Upgrade:%s][QualityMet:%s][CustomFormatMet:%s]",
                        title.ljust(60, "."),
                        str(searched).ljust(5),
                        str(False).ljust(5),
                        str(qualityMet).ljust(5),
                        str(customFormatMet).ljust(5),
                    )

                    db_commands = self.model_file.insert(
                        Title=title,
                        Monitored=monitored,
                        TmdbId=tmdbId,
                        Year=year,
                        EntryId=entryId,
                        Searched=searched,
                        MovieFileId=movieFileId,
                        IsRequest=request,
                        QualityMet=qualityMet,
                        Upgrade=False,
                        MinCustomFormatScore=minCustomFormat,
                        CustomFormatScore=customFormat,
                        CustomFormatMet=customFormatMet,
                        Reason=reason,
                    ).on_conflict(conflict_target=[self.model_file.EntryId], update=to_update)
                    db_commands.execute()
                else:
                    db_commands = self.model_file.delete().where(
                        self.model_file.EntryId == db_entry["id"]
                    )
                    db_commands.execute()

        except requests.exceptions.ConnectionError as e:
            self.logger.debug(
                "Max retries exceeded for %s [%s][%s]",
                self._name,
                db_entry["id"],
                db_entry["title"],
                exc_info=e,
            )
            raise DelayLoopException(length=300, type=self._name)
        except JSONDecodeError:
            if self.type == "sonarr":
                if self.series_search:
                    self.logger.warning(
                        "Error getting series info: [%s][%s]", db_entry["id"], db_entry["title"]
                    )
                else:
                    self.logger.warning(
                        "Error getting episode info: [%s][%s]", db_entry["id"], db_entry["title"]
                    )
            elif self.type == "radarr":
                self.logger.warning(
                    "Error getting movie info: [%s][%s]", db_entry["id"], db_entry["path"]
                )
        except Exception as e:
            self.logger.error(e, exc_info=sys.exc_info())

    def delete_from_queue(self, id_, remove_from_client=True, blacklist=True):
        try:
            while True:
                try:
                    res = self.client.del_queue(id_, remove_from_client, blacklist)
                    # res = self.client._delete(
                    #     f"queue/{id_}?removeFromClient={remove_from_client}&blocklist={blacklist}",
                    #     self.client.ver_uri,
                    # )
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ):
                    continue
        except PyarrResourceNotFound as e:
            self.logger.error("Connection Error: " + e.message)
            raise DelayLoopException(length=300, type=self._name)
        return res

    def file_is_probeable(self, file: pathlib.Path) -> bool:
        if not self.manager.ffprobe_available:
            return True  # ffprobe is not found, so we say every file is acceptable.
        try:
            if file in self.files_probed:
                self.logger.trace("Probeable: File has already been probed: %s", file)
                return True
            if file.is_dir():
                self.logger.trace("Not probeable: File is a directory: %s", file)
                return False
            output = ffmpeg.probe(
                str(file.absolute()), cmd=self.manager.qbit_manager.ffprobe_downloader.probe_path
            )
            if not output:
                self.logger.trace("Not probeable: Probe returned no output: %s", file)
                return False
            self.files_probed.add(file)
            return True
        except BaseException as e:
            error = e.stderr.decode()
            self.logger.trace(
                "Not probeable: Probe returned an error: %s:\n%s",
                file,
                e.stderr,
                exc_info=sys.exc_info(),
            )
            if "Invalid data found when processing input" in error:
                return False
            return False

    def folder_cleanup(self, downloads_id: str | None, folder: pathlib.Path):
        if not self.auto_delete:
            return
        self.logger.debug("Folder Cleanup: %s", folder)
        all_files_in_folder = list(absolute_file_paths(folder))
        invalid_files = set()
        probeable = 0
        for file in all_files_in_folder:
            if file.name in {"desktop.ini", ".DS_Store"}:
                continue
            elif file.suffix.lower() == ".parts":
                continue
            if not file.exists():
                continue
            if file.is_dir():
                self.logger.trace("Folder Cleanup: File is a folder: %s", file)
                continue
            if self.file_extension_allowlist and (
                (match := self.file_extension_allowlist_re.search(file.suffix)) and match.group()
            ):
                self.logger.trace("Folder Cleanup: File has an allowed extension: %s", file)
                if self.file_is_probeable(file):
                    self.logger.trace("Folder Cleanup: File is a valid media type: %s", file)
                    probeable += 1
            elif not self.file_extension_allowlist:
                self.logger.trace("Folder Cleanup: File has an allowed extension: %s", file)
                if self.file_is_probeable(file):
                    self.logger.trace("Folder Cleanup: File is a valid media type: %s", file)
                    probeable += 1
            else:
                invalid_files.add(file)

        if not probeable:
            self.downloads_with_bad_error_message_blocklist.discard(downloads_id)
            self.delete.discard(downloads_id)
            self.remove_and_maybe_blocklist(downloads_id, folder)
        elif invalid_files:
            for file in invalid_files:
                self.remove_and_maybe_blocklist(None, file)

    def post_file_cleanup(self):
        for downloads_id, file in self.files_to_cleanup:
            self.folder_cleanup(downloads_id, file)
        self.files_to_cleanup = set()

    def post_download_error_cleanup(self):
        for downloads_id, file in self.files_to_explicitly_delete:
            self.remove_and_maybe_blocklist(downloads_id, file)

    def remove_and_maybe_blocklist(self, downloads_id: str | None, file_or_folder: pathlib.Path):
        if downloads_id is not None:
            self.delete_from_queue(id_=downloads_id, blacklist=True)
            self.logger.debug(
                "Torrent removed and blocklisted: File was marked as failed by Arr " "| %s",
                file_or_folder,
            )
        if file_or_folder != self.completed_folder:
            if file_or_folder.is_dir():
                try:
                    shutil.rmtree(file_or_folder, ignore_errors=True)
                    self.logger.debug(
                        "Folder removed: Folder was marked as failed by Arr, "
                        "manually removing it | %s",
                        file_or_folder,
                    )
                except (PermissionError, OSError):
                    self.logger.debug(
                        "Folder in use: Failed to remove Folder: Folder was marked as failed by Ar "
                        "| %s",
                        file_or_folder,
                    )
            else:
                try:
                    file_or_folder.unlink(missing_ok=True)
                    self.logger.debug(
                        "File removed: File was marked as failed by Arr, "
                        "manually removing it | %s",
                        file_or_folder,
                    )
                except (PermissionError, OSError):
                    self.logger.debug(
                        "File in use: Failed to remove file: File was marked as failed by Ar | %s",
                        file_or_folder,
                    )

    def all_folder_cleanup(self) -> None:
        if not self.auto_delete:
            return
        self._update_bad_queue_items()
        self.post_file_cleanup()
        if not self.needs_cleanup:
            return
        folder = self.completed_folder
        self.folder_cleanup(None, folder)
        self.files_to_explicitly_delete = iter([])
        self.post_download_error_cleanup()
        self._remove_empty_folders()
        self.needs_cleanup = False

    def maybe_do_search(
        self,
        file_model: EpisodeFilesModel | MoviesFilesModel | SeriesFilesModel,
        request: bool = False,
        todays: bool = False,
        bypass_limit: bool = False,
        series_search: bool = False,
        commands: int = 0,
    ):
        request_tag = (
            "[OVERSEERR REQUEST]: "
            if request and self.overseerr_requests
            else "[OMBI REQUEST]: "
            if request and self.ombi_search_requests
            else "[PRIORITY SEARCH - TODAY]: "
            if todays
            else ""
        )
        self.refresh_download_queue()
        if request or todays:
            bypass_limit = True
        if (not self.search_missing) or (file_model is None):
            return None
        elif not self.is_alive:
            raise NoConnectionrException(f"Could not connect to {self.uri}", type="arr")
        elif self.type == "sonarr":
            if not series_search:
                file_model: EpisodeFilesModel
                if not (request or todays):
                    (
                        self.model_queue.select(self.model_queue.Completed)
                        .where(self.model_queue.EntryId == file_model.EntryId)
                        .execute()
                    )
                else:
                    pass
                if file_model.EntryId in self.queue_file_ids:
                    self.logger.debug(
                        "%sSkipping: Already Searched: %s | "
                        "S%02dE%03d | "
                        "%s | [id=%s|AirDateUTC=%s]",
                        request_tag,
                        file_model.SeriesTitle,
                        file_model.SeasonNumber,
                        file_model.EpisodeNumber,
                        file_model.Title,
                        file_model.EntryId,
                        file_model.AirDateUtc,
                    )
                    self.model_file.update(Searched=True, Upgrade=True).where(
                        file_model.EntryId == file_model.EntryId
                    ).execute()
                    return True
                active_commands = self.arr_db_query_commands_count()
                self.logger.info(
                    "%s active search commands, %s remaining",
                    active_commands,
                    commands,
                )
                if not bypass_limit and active_commands >= self.search_command_limit:
                    self.logger.trace(
                        "Idle: Too many commands in queue: %s | "
                        "S%02dE%03d | "
                        "%s | [id=%s|AirDateUTC=%s]",
                        file_model.SeriesTitle,
                        file_model.SeasonNumber,
                        file_model.EpisodeNumber,
                        file_model.Title,
                        file_model.EntryId,
                        file_model.AirDateUtc,
                    )
                    return False
                self.persistent_queue.insert(
                    EntryId=file_model.EntryId
                ).on_conflict_ignore().execute()
                self.model_queue.insert(
                    Completed=False, EntryId=file_model.EntryId
                ).on_conflict_replace().execute()
                if file_model.EntryId not in self.queue_file_ids:
                    while True:
                        try:
                            self.client.post_command(
                                "EpisodeSearch", episodeIds=[file_model.EntryId]
                            )
                            break
                        except (
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                        ):
                            continue
                self.model_file.update(Searched=True, Upgrade=True).where(
                    file_model.EntryId == file_model.EntryId
                ).execute()
                if file_model.Reason:
                    self.logger.hnotice(
                        "%sSearching for: %s | S%02dE%03d | %s | [id=%s|AirDateUTC=%s][%s]",
                        request_tag,
                        file_model.SeriesTitle,
                        file_model.SeasonNumber,
                        file_model.EpisodeNumber,
                        file_model.Title,
                        file_model.EntryId,
                        file_model.AirDateUtc,
                        file_model.Reason,
                    )
                else:
                    self.logger.hnotice(
                        "%sSearching for: %s | S%02dE%03d | %s | [id=%s|AirDateUTC=%s]",
                        request_tag,
                        file_model.SeriesTitle,
                        file_model.SeasonNumber,
                        file_model.EpisodeNumber,
                        file_model.Title,
                        file_model.EntryId,
                        file_model.AirDateUtc,
                    )
                return True
            else:
                file_model: SeriesFilesModel
                active_commands = self.arr_db_query_commands_count()
                self.logger.info(
                    "%s active search commands, %s remaining",
                    active_commands,
                    commands,
                )
                if not bypass_limit and active_commands >= self.search_command_limit:
                    self.logger.trace(
                        "Idle: Too many commands in queue: %s | [id=%s]",
                        file_model.Title,
                        file_model.EntryId,
                    )
                    return False
                self.persistent_queue.insert(
                    EntryId=file_model.EntryId
                ).on_conflict_ignore().execute()
                self.model_queue.insert(
                    Completed=False, EntryId=file_model.EntryId
                ).on_conflict_replace().execute()
                while True:
                    try:
                        self.client.post_command(
                            self.search_api_command, seriesId=file_model.EntryId
                        )
                        break
                    except (
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ConnectionError,
                        JSONDecodeError,
                    ):
                        continue
                self.model_file.update(Searched=True, Upgrade=True).where(
                    file_model.EntryId == file_model.EntryId
                ).execute()
                self.logger.hnotice(
                    "%sSearching for: %s | %s | [id=%s]",
                    request_tag,
                    "Missing episodes in"
                    if "Missing" in self.search_api_command
                    else "All episodes in",
                    file_model.Title,
                    file_model.EntryId,
                )
                return True
        elif self.type == "radarr":
            file_model: MoviesFilesModel
            if not (request or todays):
                (
                    self.model_queue.select(self.model_queue.Completed)
                    .where(self.model_queue.EntryId == file_model.EntryId)
                    .execute()
                )
            else:
                pass
            if file_model.EntryId in self.queue_file_ids:
                self.logger.debug(
                    "%sSkipping: Already Searched: %s (%s)",
                    request_tag,
                    file_model.Title,
                    file_model.EntryId,
                )
                self.model_file.update(Searched=True, Upgrade=True).where(
                    file_model.EntryId == file_model.EntryId
                ).execute()
                return True
            active_commands = self.arr_db_query_commands_count()
            self.logger.info("%s active search commands, %s remaining", active_commands, commands)
            if not bypass_limit and active_commands >= self.search_command_limit:
                self.logger.trace(
                    "Idle: Too many commands in queue: %s | [id=%s]",
                    file_model.Title,
                    file_model.EntryId,
                )
                return False
            self.persistent_queue.insert(EntryId=file_model.EntryId).on_conflict_ignore().execute()

            self.model_queue.insert(
                Completed=False, EntryId=file_model.EntryId
            ).on_conflict_replace().execute()
            if file_model.EntryId:
                while True:
                    try:
                        self.client.post_command("MoviesSearch", movieIds=[file_model.EntryId])
                        break
                    except (
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ConnectionError,
                        JSONDecodeError,
                    ):
                        continue
            self.model_file.update(Searched=True, Upgrade=True).where(
                file_model.EntryId == file_model.EntryId
            ).execute()
            if file_model.Reason:
                self.logger.hnotice(
                    "%sSearching for: %s (%s) [tmdbId=%s|id=%s][%s]",
                    request_tag,
                    file_model.Title,
                    file_model.Year,
                    file_model.TmdbId,
                    file_model.EntryId,
                    file_model.Reason,
                )
            else:
                self.logger.hnotice(
                    "%sSearching for: %s (%s) [tmdbId=%s|id=%s]",
                    request_tag,
                    file_model.Title,
                    file_model.Year,
                    file_model.TmdbId,
                    file_model.EntryId,
                )
            return True

    def process(self):
        self._process_resume()
        self._process_paused()
        self._process_errored()
        self._process_file_priority()
        self._process_imports()
        self._process_failed()
        self.all_folder_cleanup()

    def process_entries(
        self, hashes: set[str]
    ) -> tuple[list[tuple[int, str]]]:  # tuple[list[tuple[int, str]], set[str]]:
        payload = [
            (_id, h.upper()) for h in hashes if (_id := self.cache.get(h.upper())) is not None
        ]

        return payload

    def process_torrents(self):
        try:
            try:
                while True:
                    try:
                        torrents = self.manager.qbit_manager.client.torrents.info(
                            status_filter="all",
                            category=self.category,
                            sort="added_on",
                            reverse=False,
                        )
                        break
                    except (qbittorrentapi.exceptions.APIError, JSONDecodeError) as e:
                        if "JSONDecodeError" in str(e):
                            continue
                        else:
                            raise qbittorrentapi.exceptions.APIError
                torrents = [t for t in torrents if hasattr(t, "category")]
                if not len(torrents):
                    raise DelayLoopException(length=LOOP_SLEEP_TIMER, type="no_downloads")
                if not has_internet(self.manager.qbit_manager.client):
                    self.manager.qbit_manager.should_delay_torrent_scan = True
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="internet")
                if self.manager.qbit_manager.should_delay_torrent_scan:
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="delay")
                self.api_calls()
                self.refresh_download_queue()
                for torrent in torrents:
                    with contextlib.suppress(qbittorrentapi.NotFound404Error):
                        self._process_single_torrent(torrent)
                self.process()
            except NoConnectionrException as e:
                self.logger.error(e.message)
            except requests.exceptions.ConnectionError:
                self.logger.warning("Couldn't connect to %s", self.type)
                self._temp_overseer_request_cache = defaultdict(set)
                return self._temp_overseer_request_cache
            except qbittorrentapi.exceptions.APIError:
                self.logger.error("The qBittorrent API returned an unexpected error")
                self.logger.debug("Unexpected APIError from qBitTorrent")  # , exc_info=e)
                raise DelayLoopException(length=300, type="qbit")
            except DelayLoopException:
                raise
            except KeyboardInterrupt:
                self.logger.hnotice("Detected Ctrl+C - Terminating process")
                sys.exit(0)
            except Exception as e:
                self.logger.error(e, exc_info=sys.exc_info())
        except KeyboardInterrupt:
            self.logger.hnotice("Detected Ctrl+C - Terminating process")
            sys.exit(0)
        except DelayLoopException:
            raise

    def _process_single_torrent_failed_cat(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.notice(
            "Deleting manually failed torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        self.delete.add(torrent.hash)

    def _process_single_torrent_recheck_cat(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.notice(
            "Re-checking manually set torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        self.recheck.add(torrent.hash)

    def _process_single_torrent_ignored(self, torrent: qbittorrentapi.TorrentDictionary):
        # Do not touch torrents that are currently being ignored.
        self.logger.trace(
            "Skipping torrent: Ignored state | "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _process_single_torrent_added_to_ignore_cache(
        self, torrent: qbittorrentapi.TorrentDictionary
    ):
        self.logger.trace(
            "Skipping torrent: Marked for skipping | "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _process_single_torrent_queued_upload(
        self, torrent: qbittorrentapi.TorrentDictionary, leave_alone: bool
    ):
        if leave_alone or torrent.state_enum == TorrentStates.FORCED_UPLOAD:
            self.logger.trace(
                "Torrent State: Queued Upload | Allowing Seeding | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
        else:
            self.pause.add(torrent.hash)
            self.logger.trace(
                "Pausing torrent: Queued Upload | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )

    def _process_single_torrent_stalled_torrent(
        self, torrent: qbittorrentapi.TorrentDictionary, extra: str
    ):
        # Process torrents who have stalled at this point, only mark for
        # deletion if they have been added more than "IgnoreTorrentsYoungerThan"
        # seconds ago
        if (
            torrent.added_on < time.time() - self.ignore_torrents_younger_than
            and torrent.last_activity < (time.time() - self.ignore_torrents_younger_than)
        ):
            self.logger.info(
                "Deleting Stale torrent: %s | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                extra,
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
            self.delete.add(torrent.hash)
        else:
            self.logger.trace(
                "Ignoring Stale torrent: "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )

    def _process_single_torrent_percentage_threshold(
        self, torrent: qbittorrentapi.TorrentDictionary, maximum_eta: int
    ):
        # Ignore torrents who have reached maximum percentage as long as
        # the last activity is within the MaximumETA set for this category
        # For example if you set MaximumETA to 5 mines, this will ignore all
        # torrents that have stalled at a higher percentage as long as there is activity
        # And the window of activity is determined by the current time - MaximumETA,
        # if the last active was after this value ignore this torrent
        # the idea here is that if a torrent isn't completely dead some leecher/seeder
        # may contribute towards your progress.
        # However if its completely dead and no activity is observed, then lets
        # remove it and requeue a new torrent.
        if maximum_eta > 0 and torrent.last_activity < (time.time() - maximum_eta):
            self.logger.info(
                "Deleting Stale torrent: Last activity is older than Maximum ETA "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
            self.delete.add(torrent.hash)
        else:
            self.logger.trace(
                "Skipping torrent: Reached Maximum completed "
                "percentage and is active | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )

    def _process_single_torrent_paused(self, torrent: qbittorrentapi.TorrentDictionary):
        self.timed_ignore_cache.add(torrent.hash)
        self.resume.add(torrent.hash)
        self.logger.debug(
            "Resuming incomplete paused torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _process_single_torrent_already_sent_to_scan(
        self, torrent: qbittorrentapi.TorrentDictionary
    ):
        self.logger.trace(
            "Skipping torrent: Already sent for import | "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _process_single_torrent_errored(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.trace(
            "Rechecking Errored torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        self.recheck.add(torrent.hash)

    def _process_single_torrent_fully_completed_torrent(
        self, torrent: qbittorrentapi.TorrentDictionary, leave_alone: bool
    ):
        if leave_alone or torrent.state_enum == TorrentStates.FORCED_UPLOAD:
            self.logger.trace(
                "Torrent State: Completed | Allowing Seeding | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
        elif not self.in_tags(torrent, "qBitrr-imported"):
            self.logger.info(
                "Importing Completed torrent: "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
            content_path = pathlib.Path(torrent.content_path)
            if content_path.is_dir() and content_path.name == torrent.name:
                torrent_folder = content_path
            else:
                if content_path.is_file() and content_path.parent.name == torrent.name:
                    torrent_folder = content_path.parent
                else:
                    torrent_folder = content_path
            self.files_to_cleanup.add((torrent.hash, torrent_folder))
            self.import_torrents.append(torrent)

    def _process_single_torrent_missing_files(self, torrent: qbittorrentapi.TorrentDictionary):
        # Sometimes Sonarr/Radarr does not automatically remove the
        # torrent for some reason,
        # this ensures that we can safely remove it if the client is reporting
        # the status of the client as "Missing files"
        self.logger.info(
            "Deleting torrent with missing files: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        # We do not want to blacklist these!!
        self.remove_from_qbit.add(torrent.hash)

    def _process_single_torrent_uploading(
        self, torrent: qbittorrentapi.TorrentDictionary, leave_alone: bool
    ):
        if leave_alone or torrent.state_enum == TorrentStates.FORCED_UPLOAD:
            self.logger.trace(
                "Torrent State: Queued Upload | Allowing Seeding | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
        else:
            self.logger.info(
                "Pausing uploading torrent: "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
            self.pause.add(torrent.hash)

    def _process_single_torrent_already_cleaned_up(
        self, torrent: qbittorrentapi.TorrentDictionary
    ):
        self.logger.trace(
            "Skipping file check: Already been cleaned up | "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _process_single_torrent_delete_slow(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.trace(
            "Deleting slow torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        self.delete.add(torrent.hash)

    def _process_single_torrent_delete_cfunmet(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.info(
            "Removing CF unmet torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Ratio: %s%%][Seeding time: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            torrent.ratio,
            timedelta(seconds=torrent.seeding_time),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        self.delete.add(torrent.hash)

    def _process_single_torrent_delete_ratio_seed(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.info(
            "Removing completed torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Ratio: %s%%][Seeding time: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            torrent.ratio,
            timedelta(seconds=torrent.seeding_time),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        self.delete.add(torrent.hash)

    def _process_single_torrent_process_files(
        self, torrent: qbittorrentapi.TorrentDictionary, special_case: bool = False
    ):
        _remove_files = set()
        total = len(torrent.files)
        if total == 0:
            return
        elif special_case:
            self.special_casing_file_check.add(torrent.hash)
        for file in torrent.files:
            if not hasattr(file, "name"):
                continue
            file_path = pathlib.Path(file.name)
            # Acknowledge files that already been marked as "Don't download"
            if file.priority == 0:
                total -= 1
                continue
            # A folder within the folder tree matched the terms
            # in FolderExclusionRegex, mark it for exclusion.
            if self.folder_exclusion_regex and any(
                self.folder_exclusion_regex_re.search(p.name.lower())
                for p in file_path.parents
                if (folder_match := p.name)
            ):
                self.logger.debug(
                    "Removing File: Not allowed | Parent: %s  | %s (%s) | %s ",
                    folder_match,
                    torrent.name,
                    torrent.hash,
                    file.name,
                )
                _remove_files.add(file.id)
                total -= 1
            # A file matched and entry in FileNameExclusionRegex, mark it for
            # exclusion.
            elif self.file_name_exclusion_regex and (
                (match := self.file_name_exclusion_regex_re.search(file_path.name))
                and match.group()
            ):
                self.logger.debug(
                    "Removing File: Not allowed | Name: %s  | %s (%s) | %s ",
                    match.group(),
                    torrent.name,
                    torrent.hash,
                    file.name,
                )
                _remove_files.add(file.id)
                total -= 1
            elif self.file_extension_allowlist and not (
                (match := self.file_extension_allowlist_re.search(file_path.suffix))
                and match.group()
            ):
                self.logger.debug(
                    "Removing File: Not allowed | Extension: %s  | %s (%s) | %s ",
                    file_path.suffix,
                    torrent.name,
                    torrent.hash,
                    file.name,
                )
                _remove_files.add(file.id)
                total -= 1
            # If all files in the torrent are marked for exclusion then delete the
            # torrent.
            if total == 0:
                self.logger.info(
                    "Deleting All files ignored: "
                    "[Progress: %s%%][Added On: %s]"
                    "[Availability: %s%%][Time Left: %s]"
                    "[Last active: %s] "
                    "| [%s] | %s (%s)",
                    round(torrent.progress * 100, 2),
                    datetime.fromtimestamp(torrent.added_on),
                    round(torrent.availability * 100, 2),
                    timedelta(seconds=torrent.eta),
                    datetime.fromtimestamp(torrent.last_activity),
                    torrent.state_enum,
                    torrent.name,
                    torrent.hash,
                )
                self.delete.add(torrent.hash)
            # Mark all bad files and folder for exclusion.
            elif _remove_files and torrent.hash not in self.change_priority:
                self.change_priority[torrent.hash] = list(_remove_files)
            elif _remove_files and torrent.hash in self.change_priority:
                self.change_priority[torrent.hash] = list(_remove_files)

        self.cleaned_torrents.add(torrent.hash)

    def _process_single_completed_paused_torrent(
        self, torrent: qbittorrentapi.TorrentDictionary, leave_alone: bool
    ):
        if leave_alone:
            self.resume.add(torrent.hash)
            self.logger.trace(
                "Resuming torrent: "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
        else:
            self.logger.trace(
                "Skipping torrent: "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(torrent.added_on),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )

    def _process_single_torrent_unprocessed(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.trace(
            "Skipping torrent: Unresolved state: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _get_torrent_important_trackers(
        self, torrent: qbittorrentapi.TorrentDictionary
    ) -> tuple[set[str], set[str]]:
        try:
            current_trackers = {i.url for i in torrent.trackers if hasattr(i, "url")}
        except qbittorrentapi.exceptions.APIError as e:
            self.logger.error("The qBittorrent API returned an unexpected error")
            self.logger.debug("Unexpected APIError from qBitTorrent", exc_info=e)
            raise DelayLoopException(length=300, type="qbit")
        monitored_trackers = self._monitored_tracker_urls.intersection(current_trackers)
        need_to_be_added = self._add_trackers_if_missing.difference(current_trackers)
        monitored_trackers = monitored_trackers.union(need_to_be_added)
        return need_to_be_added, monitored_trackers

    @staticmethod
    def __return_max(x: dict):
        return x.get("Priority", -100)

    def _get_most_important_tracker_and_tags(
        self, monitored_trackers, removed
    ) -> tuple[dict, set[str]]:
        new_list = [
            i
            for i in self.monitored_trackers
            if (i.get("URI") in monitored_trackers) and i.get("RemoveIfExists") is not True
        ]
        _list_of_tags = [i.get("AddTags", []) for i in new_list if i.get("URI") not in removed]
        max_item = max(new_list, key=self.__return_max) if new_list else {}
        return max_item, set(itertools.chain.from_iterable(_list_of_tags))

    def _get_torrent_limit_meta(self, torrent: qbittorrentapi.TorrentDictionary):
        _, monitored_trackers = self._get_torrent_important_trackers(torrent)
        most_important_tracker, _unique_tags = self._get_most_important_tracker_and_tags(
            monitored_trackers, {}
        )

        data_settings = {
            "ratio_limit": r
            if (
                r := most_important_tracker.get(
                    "MaxUploadRatio", self.seeding_mode_global_max_upload_ratio
                )
            )
            > 0
            else -5,
            "seeding_time_limit": r
            if (
                r := most_important_tracker.get(
                    "MaxSeedingTime", self.seeding_mode_global_max_seeding_time
                )
            )
            > 0
            else -5,
            "dl_limit": r
            if (
                r := most_important_tracker.get(
                    "DownloadRateLimit", self.seeding_mode_global_download_limit
                )
            )
            > 0
            else -5,
            "up_limit": r
            if (
                r := most_important_tracker.get(
                    "UploadRateLimit", self.seeding_mode_global_upload_limit
                )
            )
            > 0
            else -5,
            "super_seeding": most_important_tracker.get("SuperSeedMode", torrent.super_seeding),
            "max_eta": most_important_tracker.get("MaximumETA", self.maximum_eta),
        }

        data_torrent = {
            "ratio_limit": r if (r := torrent.ratio_limit) > 0 else -5,
            "seeding_time_limit": r if (r := torrent.seeding_time_limit) > 0 else -5,
            "dl_limit": r if (r := torrent.dl_limit) > 0 else -5,
            "up_limit": r if (r := torrent.up_limit) > 0 else -5,
            "super_seeding": torrent.super_seeding,
        }
        return data_settings, data_torrent

    def _should_leave_alone(
        self, torrent: qbittorrentapi.TorrentDictionary
    ) -> tuple[bool, int, bool]:
        return_value = True
        remove_torrent = False
        if torrent.super_seeding or torrent.state_enum == TorrentStates.FORCED_UPLOAD:
            return return_value, -1, remove_torrent  # Do not touch super seeding torrents.
        data_settings, data_torrent = self._get_torrent_limit_meta(torrent)
        self.logger.trace("Config Settings for torrent [%s]: %r", torrent.name, data_settings)
        self.logger.trace("Torrent Settings for torrent [%s]: %r", torrent.name, data_torrent)
        # self.logger.trace("%r", torrent)

        ratio_limit_dat = data_settings.get("ratio_limit", -5)
        ratio_limit_tor = data_torrent.get("ratio_limit", -5)
        seeding_time_limit_dat = data_settings.get("seeding_time_limit", -5)
        seeding_time_limit_tor = data_torrent.get("seeding_time_limit", -5)

        seeding_time_limit = max(seeding_time_limit_dat, seeding_time_limit_tor)
        ratio_limit = max(ratio_limit_dat, ratio_limit_tor)

        if self.seeding_mode_global_remove_torrent != -1:
            remove_torrent = self.torrent_limit_check(torrent, seeding_time_limit, ratio_limit)
        else:
            remove_torrent = False
        return_value = not self.torrent_limit_check(torrent, seeding_time_limit, ratio_limit)
        if data_settings.get("super_seeding", False) or data_torrent.get("super_seeding", False):
            return_value = True
        if self.in_tags(torrent, "qBitrr-free_space_paused"):
            return_value = True
        if (
            return_value
            and not self.in_tags(torrent, "qBitrr-allowed_seeding")
            and not self.in_tags(torrent, "qBitrr-free_space_paused")
        ):
            self.add_tags(torrent, ["qBitrr-allowed_seeding"])
        elif (
            not return_value and self.in_tags(torrent, "qBitrr-allowed_seeding")
        ) or self.in_tags(torrent, "qBitrr-free_space_paused"):
            self.remove_tags(torrent, ["qBitrr-allowed_seeding"])

        self.logger.trace("Config Settings returned [%s]: %r", torrent.name, data_settings)
        return (
            return_value,
            data_settings.get("max_eta", self.maximum_eta),
            remove_torrent,
        )  # Seeding is not complete needs more time

    def _process_single_torrent_trackers(self, torrent: qbittorrentapi.TorrentDictionary):
        if torrent.hash in self.tracker_delay:
            return
        self.tracker_delay.add(torrent.hash)
        _remove_urls = set()
        need_to_be_added, monitored_trackers = self._get_torrent_important_trackers(torrent)
        if need_to_be_added:
            torrent.add_trackers(need_to_be_added)
        with contextlib.suppress(BaseException):
            for tracker in torrent.trackers:
                if (
                    self.remove_dead_trackers
                    and (
                        any(tracker.msg == m for m in self.seeding_mode_global_bad_tracker_msg)
                    )  # TODO: Add more messages
                ) or tracker.url in self._remove_trackers_if_exists:
                    _remove_urls.add(tracker.url)
        if _remove_urls:
            self.logger.trace(
                "Removing trackers from torrent: %s (%s) - %s",
                torrent.name,
                torrent.hash,
                _remove_urls,
            )
            with contextlib.suppress(qbittorrentapi.Conflict409Error):
                torrent.remove_trackers(_remove_urls)
        most_important_tracker, unique_tags = self._get_most_important_tracker_and_tags(
            monitored_trackers, _remove_urls
        )
        if monitored_trackers and most_important_tracker:
            # Only use globals if there is not a configured equivalent value on the
            # highest priority tracker
            data = {
                "ratio_limit": r
                if (
                    r := most_important_tracker.get(
                        "MaxUploadRatio", self.seeding_mode_global_max_upload_ratio
                    )
                )
                > 0
                else None,
                "seeding_time_limit": r
                if (
                    r := most_important_tracker.get(
                        "MaxSeedingTime", self.seeding_mode_global_max_seeding_time
                    )
                )
                > 0
                else None,
            }
            if any(r is not None for r in data):
                if (
                    (_l1 := data.get("seeding_time_limit"))
                    and _l1 > 0
                    and torrent.seeding_time_limit != data.get("seeding_time_limit")
                ):
                    data.pop("seeding_time_limit")
                if (
                    (_l2 := data.get("ratio_limit"))
                    and _l2 > 0
                    and torrent.seeding_time_limit != data.get("ratio_limit")
                ):
                    data.pop("ratio_limit")

                if not _l1:
                    data["seeding_time_limit"] = None
                elif _l1 < 0:
                    data["seeding_time_limit"] = None
                if not _l2:
                    data["ratio_limit"] = None
                elif _l2 < 0:
                    data["ratio_limit"] = None

                if any(v is not None for v in data.values()) and data:
                    with contextlib.suppress(Exception):
                        torrent.set_share_limits(**data)
            if (
                r := most_important_tracker.get(
                    "DownloadRateLimit", self.seeding_mode_global_download_limit
                )
                != 0
                and torrent.dl_limit != r
            ):
                torrent.set_download_limit(limit=r)
            elif r < 0:
                torrent.set_upload_limit(limit=-1)
            if (
                r := most_important_tracker.get(
                    "UploadRateLimit", self.seeding_mode_global_upload_limit
                )
                != 0
                and torrent.up_limit != r
            ):
                torrent.set_upload_limit(limit=r)
            elif r < 0:
                torrent.set_upload_limit(limit=-1)
            if (
                r := most_important_tracker.get("SuperSeedMode", False)
                and torrent.super_seeding != r
            ):
                torrent.set_super_seeding(enabled=r)

        else:
            data = {
                "ratio_limit": r if (r := self.seeding_mode_global_max_upload_ratio) > 0 else None,
                "seeding_time_limit": r
                if (r := self.seeding_mode_global_max_seeding_time) > 0
                else None,
            }
            if any(r is not None for r in data):
                if (
                    (_l1 := data.get("seeding_time_limit"))
                    and _l1 > 0
                    and torrent.seeding_time_limit != data.get("seeding_time_limit")
                ):
                    data.pop("seeding_time_limit")
                if (
                    (_l2 := data.get("ratio_limit"))
                    and _l2 > 0
                    and torrent.seeding_time_limit != data.get("ratio_limit")
                ):
                    data.pop("ratio_limit")
                if not _l1:
                    data["seeding_time_limit"] = None
                elif _l1 < 0:
                    data["seeding_time_limit"] = None
                if not _l2:
                    data["ratio_limit"] = None
                elif _l2 < 0:
                    data["ratio_limit"] = None
                if any(v is not None for v in data.values()) and data:
                    with contextlib.suppress(Exception):
                        torrent.set_share_limits(**data)

            if r := self.seeding_mode_global_download_limit != 0 and torrent.dl_limit != r:
                torrent.set_download_limit(limit=r)
            elif r < 0:
                torrent.set_download_limit(limit=-1)
            if r := self.seeding_mode_global_upload_limit != 0 and torrent.up_limit != r:
                torrent.set_upload_limit(limit=r)
            elif r < 0:
                torrent.set_upload_limit(limit=-1)

        if unique_tags:
            current_tags = set(torrent.tags.split(", "))
            add_tags = unique_tags.difference(current_tags)
            if add_tags:
                self.add_tags(torrent, add_tags)

    def _stalled_check(self, torrent: qbittorrentapi.TorrentDictionary, time_now: float) -> bool:
        stalled_ignore = True
        if not self.allowed_stalled:
            self.logger.trace("Stalled check: Stalled delay disabled")
            return False
        if time_now < torrent.added_on + self.ignore_torrents_younger_than:
            self.logger.trace(
                "Stalled check: In recent queue %s [Current:%s][Added:%s][Starting:%s]",
                torrent.name,
                datetime.fromtimestamp(time_now),
                datetime.fromtimestamp(torrent.added_on),
                datetime.fromtimestamp(
                    torrent.added_on + timedelta(minutes=self.stalled_delay).seconds
                ),
            )
            return True
        if self.stalled_delay == 0:
            self.logger.trace(
                "Stalled check: %s [Current:%s][Last Activity:%s][Limit:No Limit]",
                torrent.name,
                datetime.fromtimestamp(time_now),
                datetime.fromtimestamp(torrent.last_activity),
            )
        else:
            self.logger.trace(
                "Stalled check: %s [Current:%s][Last Activity:%s][Limit:%s]",
                torrent.name,
                datetime.fromtimestamp(time_now),
                datetime.fromtimestamp(torrent.last_activity),
                datetime.fromtimestamp(
                    torrent.last_activity + timedelta(minutes=self.stalled_delay).seconds
                ),
            )
        if (
            (
                torrent.state_enum
                in (TorrentStates.METADATA_DOWNLOAD, TorrentStates.STALLED_DOWNLOAD)
                and not self.in_tags(torrent, "qBitrr-ignored")
                and not self.in_tags(torrent, "qBitrr-free_space_paused")
            )
            or (
                torrent.availability < 1
                and torrent.hash in self.cleaned_torrents
                and torrent.state_enum in (TorrentStates.DOWNLOADING)
                and not self.in_tags(torrent, "qBitrr-ignored")
                and not self.in_tags(torrent, "qBitrr-free_space_paused")
            )
        ) and self.allowed_stalled:
            if (
                self.stalled_delay > 0
                and time_now
                >= torrent.last_activity + timedelta(minutes=self.stalled_delay).seconds
            ):
                stalled_ignore = False
                self.logger.trace("Process stalled, delay expired: %s", torrent.name)
            elif not self.in_tags(torrent, "qBitrr-allowed_stalled"):
                self.add_tags(torrent, ["qBitrr-allowed_stalled"])
                if self.re_search_stalled:
                    self.logger.trace(
                        "Stalled, adding tag, blocklosting and re-searching: %s", torrent.name
                    )
                    skip_blacklist = set()
                    payload = self.process_entries([torrent.hash])
                    if payload:
                        for entry, hash_ in payload:
                            self._process_failed_individual(
                                hash_=hash_,
                                entry=entry,
                                skip_blacklist=skip_blacklist,
                                remove_from_client=False,
                            )
                else:
                    self.logger.trace("Stalled, adding tag: %s", torrent.name)
            elif self.in_tags(torrent, "qBitrr-allowed_stalled"):
                self.logger.trace(
                    "Stalled: %s [Current:%s][Last Activity:%s][Limit:%s]",
                    torrent.name,
                    datetime.fromtimestamp(time_now),
                    datetime.fromtimestamp(torrent.last_activity),
                    datetime.fromtimestamp(
                        torrent.last_activity + timedelta(minutes=self.stalled_delay).seconds
                    ),
                )

        elif self.in_tags(torrent, "qBitrr-allowed_stalled"):
            self.remove_tags(torrent, ["qBitrr-allowed_stalled"])
            stalled_ignore = False
            self.logger.trace("Not stalled, removing tag: %s", torrent.name)
        else:
            stalled_ignore = False
            self.logger.trace("Not stalled: %s", torrent.name)
        return stalled_ignore

    def _process_single_torrent(self, torrent: qbittorrentapi.TorrentDictionary):
        if torrent.category != RECHECK_CATEGORY:
            self.manager.qbit_manager.cache[torrent.hash] = torrent.category
        self._process_single_torrent_trackers(torrent)
        self.manager.qbit_manager.name_cache[torrent.hash] = torrent.name
        time_now = time.time()
        leave_alone, _tracker_max_eta, remove_torrent = self._should_leave_alone(torrent)
        self.logger.trace(
            "Torrent [%s]: Leave Alone (allow seeding): %s, Max ETA: %s, State[%s]",
            torrent.name,
            leave_alone,
            _tracker_max_eta,
            torrent.state_enum,
        )
        maximum_eta = _tracker_max_eta

        if torrent.state_enum in (
            TorrentStates.METADATA_DOWNLOAD,
            TorrentStates.STALLED_DOWNLOAD,
            TorrentStates.DOWNLOADING,
        ):
            stalled_ignore = self._stalled_check(torrent, time_now)
        else:
            stalled_ignore = False

        if self.in_tags(torrent, "qBitrr-ignored"):
            self.remove_tags(torrent, ["qBitrr-allowed_seeding", "qBitrr-free_space_paused"])

        if (
            self.custom_format_unmet_search
            and self.custom_format_unmet_check(torrent)
            and not self.in_tags(torrent, "qBitrr-ignored")
            and not self.in_tags(torrent, "qBitrr-free_space_paused")
        ):
            self._process_single_torrent_delete_cfunmet(torrent)
        elif remove_torrent and not leave_alone and torrent.amount_left == 0:
            self._process_single_torrent_delete_ratio_seed(torrent)
        elif torrent.category == FAILED_CATEGORY:
            # Bypass everything if manually marked as failed
            self._process_single_torrent_failed_cat(torrent)
        elif torrent.category == RECHECK_CATEGORY:
            # Bypass everything else if manually marked for rechecking
            self._process_single_torrent_recheck_cat(torrent)
        elif self.is_ignored_state(torrent):
            self._process_single_torrent_ignored(torrent)
        elif (
            torrent.state_enum in (TorrentStates.METADATA_DOWNLOAD, TorrentStates.STALLED_DOWNLOAD)
            and not self.in_tags(torrent, "qBitrr-ignored")
            and not self.in_tags(torrent, "qBitrr-free_space_paused")
            and not stalled_ignore
        ):
            self._process_single_torrent_stalled_torrent(torrent, "Stalled State")
        elif (
            torrent.state_enum.is_downloading
            and torrent.state_enum != TorrentStates.METADATA_DOWNLOAD
            and torrent.hash not in self.special_casing_file_check
            and torrent.hash not in self.cleaned_torrents
        ):
            self._process_single_torrent_process_files(torrent, True)
        elif torrent.hash in self.timed_ignore_cache:
            # Do not touch torrents recently resumed/reached (A torrent can temporarily
            # stall after being resumed from a paused state).
            self._process_single_torrent_added_to_ignore_cache(torrent)
        elif torrent.state_enum == TorrentStates.QUEUED_UPLOAD:
            self._process_single_torrent_queued_upload(torrent, leave_alone)
        # Resume monitored downloads which have been paused.
        elif (
            torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD
            and torrent.amount_left != 0
            and not self.in_tags(torrent, "qBitrr-free_space_paused")
            and not self.in_tags(torrent, "qBitrr-ignored")
        ):
            self._process_single_torrent_paused(torrent)
        elif (
            torrent.progress <= self.maximum_deletable_percentage
            and not self.is_complete_state(torrent)
            and not self.in_tags(torrent, "qBitrr-ignored")
            and not self.in_tags(torrent, "qBitrr-free_space_paused")
            and not stalled_ignore
        ) and torrent.hash in self.cleaned_torrents:
            self._process_single_torrent_percentage_threshold(torrent, maximum_eta)
        # Ignore torrents which have been submitted to their respective Arr
        # instance for import.
        elif (
            torrent.hash in self.manager.managed_objects[torrent.category].sent_to_scan_hashes
        ) and torrent.hash in self.cleaned_torrents:
            self._process_single_torrent_already_sent_to_scan(torrent)

        # Sometimes torrents will error, this causes them to be rechecked so they
        # complete downloading.
        elif torrent.state_enum == TorrentStates.ERROR:
            self._process_single_torrent_errored(torrent)
        # If a torrent was not just added,
        # and the amount left to download is 0 and the torrent
        # is Paused tell the Arr tools to process it.
        elif (
            torrent.added_on > 0
            and torrent.completion_on
            and torrent.amount_left == 0
            and torrent.state_enum != TorrentStates.PAUSED_UPLOAD
            and self.is_complete_state(torrent)
            and torrent.content_path
            and torrent.completion_on < time_now - 60
        ):
            self._process_single_torrent_fully_completed_torrent(torrent, leave_alone)
        elif torrent.state_enum == TorrentStates.MISSING_FILES:
            self._process_single_torrent_missing_files(torrent)
        # If a torrent is Uploading Pause it, as long as its not being Forced Uploaded.
        elif (
            self.is_uploading_state(torrent)
            and torrent.seeding_time > 1
            and torrent.amount_left == 0
            and torrent.added_on > 0
            and torrent.content_path
            and self.seeding_mode_global_remove_torrent != -1
        ) and torrent.hash in self.cleaned_torrents:
            self._process_single_torrent_uploading(torrent, leave_alone)
        # Mark a torrent for deletion
        elif (
            torrent.state_enum != TorrentStates.PAUSED_DOWNLOAD
            and torrent.state_enum.is_downloading
            and time_now > torrent.added_on + self.ignore_torrents_younger_than
            and 0 < maximum_eta < torrent.eta
            and not self.do_not_remove_slow
            and not self.in_tags(torrent, "qBitrr-ignored")
            and not self.in_tags(torrent, "qBitrr-free_space_paused")
            and not stalled_ignore
        ):
            self._process_single_torrent_delete_slow(torrent)
        # Process uncompleted torrents
        elif torrent.state_enum.is_downloading:
            # If a torrent availability hasn't reached 100% or more within the configurable
            # "IgnoreTorrentsYoungerThan" variable, mark it for deletion.
            if (
                (
                    time_now > torrent.added_on + self.ignore_torrents_younger_than
                    and torrent.availability < 1
                )
                and torrent.hash in self.cleaned_torrents
                and self.is_downloading_state(torrent)
                and not self.in_tags(torrent, "qBitrr-ignored")
                and not self.in_tags(torrent, "qBitrr-free_space_paused")
                and not stalled_ignore
            ):
                self._process_single_torrent_stalled_torrent(torrent, "Unavailable")
            else:
                if torrent.hash in self.cleaned_torrents:
                    self._process_single_torrent_already_cleaned_up(torrent)
                    return
                # A downloading torrent is not stalled, parse its contents.
                self._process_single_torrent_process_files(torrent)
        elif self.is_complete_state(torrent) and leave_alone:
            self._process_single_completed_paused_torrent(torrent, leave_alone)
        else:
            self._process_single_torrent_unprocessed(torrent)

    def custom_format_unmet_check(self, torrent: qbittorrentapi.TorrentDictionary) -> bool:
        try:
            # Retry getting the queue until it succeeds
            while True:
                try:
                    queue = self.client.get_queue()
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ):
                    continue  # Retry on exceptions

            if not queue.get("records"):
                return False

            download_id = torrent.hash.upper()
            record = next(
                (r for r in queue["records"] if r.get("downloadId") == download_id), None
            )

            if not record:
                return False

            custom_format_score = record.get("customFormatScore")
            if custom_format_score is None:
                return False

            # Default assumption: custom format requirements are met
            cf_unmet = False

            if self.type == "sonarr":
                entry_id_field = "seriesId" if self.series_search else "episodeId"
                file_id_field = None if self.series_search else "EpisodeFileId"
            elif self.type == "radarr":
                entry_id_field = "movieId"
                file_id_field = "MovieFileId"
            else:
                return False  # Unknown type

            entry_id = record.get(entry_id_field)
            if not entry_id:
                return False

            # Retrieve the model entry from the database
            model_entry = (
                self.model_file.select().where(self.model_file.EntryId == entry_id).first()
            )
            if not model_entry:
                return False

            if self.type == "sonarr" and self.series_search:
                if self.force_minimum_custom_format:
                    min_score = getattr(model_entry, "MinCustomFormatScore", 0)
                    cf_unmet = custom_format_score < min_score
            else:
                file_id = getattr(model_entry, file_id_field, 0) if file_id_field else 0
                if file_id != 0:
                    model_cf_score = getattr(model_entry, "CustomFormatScore", 0)
                    cf_unmet = custom_format_score < model_cf_score
                    if self.force_minimum_custom_format:
                        min_score = getattr(model_entry, "MinCustomFormatScore", 0)
                        cf_unmet = cf_unmet and custom_format_score < min_score

            return cf_unmet

        except Exception:
            return False

    def torrent_limit_check(
        self, torrent: qbittorrentapi.TorrentDictionary, seeding_time_limit, ratio_limit
    ) -> bool:
        if (
            self.seeding_mode_global_remove_torrent == 4
            and torrent.ratio >= ratio_limit
            and torrent.seeding_time >= seeding_time_limit
        ):
            return True
        if self.seeding_mode_global_remove_torrent == 3 and (
            torrent.ratio >= ratio_limit or torrent.seeding_time >= seeding_time_limit
        ):
            return True
        elif (
            self.seeding_mode_global_remove_torrent == 2
            and torrent.seeding_time >= seeding_time_limit
        ):
            return True
        elif self.seeding_mode_global_remove_torrent == 1 and torrent.ratio >= ratio_limit:
            return True
        elif self.seeding_mode_global_remove_torrent == -1 and (
            torrent.ratio >= ratio_limit and torrent.seeding_time >= seeding_time_limit
        ):
            return True
        else:
            return False

    def refresh_download_queue(self):
        self.queue = self.get_queue()
        self.requeue_cache = defaultdict(set)
        if self.queue:
            self.cache = {
                entry["downloadId"]: entry["id"] for entry in self.queue if entry.get("downloadId")
            }
            if self.type == "sonarr":
                if not self.series_search:
                    for entry in self.queue:
                        if r := entry.get("episodeId"):
                            self.requeue_cache[entry["id"]].add(r)
                    self.queue_file_ids = {
                        entry["episodeId"] for entry in self.queue if entry.get("episodeId")
                    }
                    if self.model_queue:
                        self.model_queue.delete().where(
                            self.model_queue.EntryId.not_in(list(self.queue_file_ids))
                        ).execute()
                else:
                    for entry in self.queue:
                        if r := entry.get("seriesId"):
                            self.requeue_cache[entry["id"]].add(r)
                    self.queue_file_ids = {
                        entry["seriesId"] for entry in self.queue if entry.get("seriesId")
                    }
                    if self.model_queue:
                        self.model_queue.delete().where(
                            self.model_queue.EntryId.not_in(list(self.queue_file_ids))
                        ).execute()
            elif self.type == "radarr":
                self.requeue_cache = {
                    entry["id"]: entry["movieId"] for entry in self.queue if entry.get("movieId")
                }
                self.queue_file_ids = {
                    entry["movieId"] for entry in self.queue if entry.get("movieId")
                }
                if self.model_queue:
                    self.model_queue.delete().where(
                        self.model_queue.EntryId.not_in(list(self.queue_file_ids))
                    ).execute()

        self._update_bad_queue_items()

    def get_queue(self, page=1, page_size=1000, sort_direction="ascending", sort_key="timeLeft"):
        while True:
            try:
                res = self.client.get_queue(
                    page=page, page_size=page_size, sort_key=sort_key, sort_dir=sort_direction
                )
                break
            except (
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ContentDecodingError,
                requests.exceptions.ConnectionError,
                JSONDecodeError,
            ):
                continue
        try:
            res = res.get("records", [])
        except AttributeError:
            res = None
        return res

    def _update_bad_queue_items(self):
        if not self.arr_error_codes_to_blocklist:
            return
        _temp = self.get_queue()
        if _temp:
            _temp = filter(
                lambda x: x.get("status") == "completed"
                and x.get("trackedDownloadState") == "importPending"
                and x.get("trackedDownloadStatus") == "warning",
                _temp,
            )
            _path_filter = set()
            _temp = list(_temp)
            for entry in _temp:
                messages = entry.get("statusMessages", [])
                output_path = entry.get("outputPath")
                for m in messages:
                    title = m.get("title")
                    if not title:
                        continue
                    for _m in m.get("messages", []):
                        if _m in self.arr_error_codes_to_blocklist:
                            e = entry.get("downloadId")
                            _path_filter.add((e, pathlib.Path(output_path).joinpath(title)))
                            self.downloads_with_bad_error_message_blocklist.add(e)
            if len(_path_filter):
                self.needs_cleanup = True
            self.files_to_explicitly_delete = iter(_path_filter.copy())

    def parse_quality_profiles(self) -> dict[int, int]:
        temp_quality_profile_ids = {}

        while True:
            try:
                profiles = self.client.get_quality_profile()
                break
            except (
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ContentDecodingError,
                requests.exceptions.ConnectionError,
                JSONDecodeError,
            ):
                continue

        for n in self.main_quality_profiles:
            pair = [n, self.temp_quality_profiles[self.main_quality_profiles.index(n)]]

            for p in profiles:
                if p["name"] == pair[0]:
                    pair[0] = p["id"]
                    self.logger.trace("Quality profile %s:%s", p["name"], p["id"])
                if p["name"] == pair[1]:
                    pair[1] = p["id"]
                    self.logger.trace("Quality profile %s:%s", p["name"], p["id"])
            temp_quality_profile_ids[pair[0]] = pair[1]

        return temp_quality_profile_ids

    def register_search_mode(self):
        if self.search_setup_completed:
            return
        if not self.search_missing:
            self.search_setup_completed = True
            return

        self.db = SqliteDatabase(None)
        self.db.init(
            str(self.search_db_file),
            pragmas={
                "journal_mode": "wal",
                "cache_size": -1 * 64000,  # 64MB
                "foreign_keys": 1,
                "ignore_check_constraints": 0,
                "synchronous": 0,
            },
        )

        db1, db2, db3, db4 = self._get_models()

        class Files(db1):
            class Meta:
                database = self.db

        class Queue(db2):
            class Meta:
                database = self.db

        class PersistingQueue(FilesQueued):
            class Meta:
                database = self.db

        self.db.connect()
        if db3:

            class Series(db3):
                class Meta:
                    database = self.db

            self.db.create_tables([Files, Queue, PersistingQueue, Series])
            self.series_file_model = Series
        else:
            self.db.create_tables([Files, Queue, PersistingQueue])

        if db4:
            self.torrent_db = SqliteDatabase(None)
            self.torrent_db.init(
                str(self._app_data_folder.joinpath("Torrents.db")),
                pragmas={
                    "journal_mode": "wal",
                    "cache_size": -1 * 64000,  # 64MB
                    "foreign_keys": 1,
                    "ignore_check_constraints": 0,
                    "synchronous": 0,
                },
            )

            class Torrents(db4):
                class Meta:
                    database = self.torrent_db

            self.torrent_db.connect()
            self.torrent_db.create_tables([Torrents])
            self.torrents = Torrents

        self.model_file = Files
        self.model_queue = Queue
        self.persistent_queue = PersistingQueue
        self.search_setup_completed = True

    def run_request_search(self):
        if (
            (
                (not self.ombi_search_requests and not self.overseerr_requests)
                or not self.search_missing
            )
            or self.request_search_timer is None
            or (self.request_search_timer > time.time() - self.search_requests_every_x_seconds)
        ):
            return None
        self.register_search_mode()
        totcommands = -1
        if SEARCH_LOOP_DELAY == -1:
            loop_delay = 30
        else:
            loop_delay = SEARCH_LOOP_DELAY
        try:
            self.db_request_update()
            try:
                for entry, commands in self.db_get_request_files():
                    if totcommands == -1:
                        totcommands = commands
                        self.logger.info("Starting request search for %s items", totcommands)
                    else:
                        totcommands -= 1
                    if SEARCH_LOOP_DELAY == -1:
                        loop_delay = 30
                    else:
                        loop_delay = SEARCH_LOOP_DELAY
                    while not self.maybe_do_search(
                        entry,
                        request=True,
                        commands=totcommands,
                    ):
                        self.logger.debug("Waiting for active request search commands")
                        time.sleep(loop_delay)
                    self.logger.info("Delaying request search loop by %s seconds", loop_delay)
                    time.sleep(loop_delay)
                    if totcommands == 0:
                        self.logger.info("All request searches completed")
                    else:
                        self.logger.info(
                            "Request searches not completed, %s remaining", totcommands
                        )
                self.request_search_timer = time.time()
            except NoConnectionrException as e:
                self.logger.error(e.message)
                raise DelayLoopException(length=300, type=e.type)
            except DelayLoopException:
                raise
            except Exception as e:
                self.logger.exception(e, exc_info=sys.exc_info())
        except DelayLoopException as e:
            if e.type == "qbit":
                self.logger.critical(
                    "Failed to connected to qBit client, sleeping for %s",
                    timedelta(seconds=e.length),
                )
            elif e.type == "internet":
                self.logger.critical(
                    "Failed to connected to the internet, sleeping for %s",
                    timedelta(seconds=e.length),
                )
            elif e.type == "arr":
                self.logger.critical(
                    "Failed to connected to the Arr instance, sleeping for %s",
                    timedelta(seconds=e.length),
                )
            elif e.type == "delay":
                self.logger.critical(
                    "Forced delay due to temporary issue with environment, sleeping for %s",
                    timedelta(seconds=e.length),
                )
            elif e.type == "no_downloads":
                self.logger.debug(
                    "No downloads in category, sleeping for %s", timedelta(seconds=e.length)
                )
            time.sleep(e.length)

    def get_year_search(self) -> tuple[list[int], int]:
        years_list = set()
        years = []
        if self.type == "radarr":
            while True:
                try:
                    movies = self.client.get_movie()
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ):
                    continue

            for m in movies:
                if not m["monitored"]:
                    continue
                if m["year"] != 0 and m["year"] <= datetime.now(timezone.utc).year:
                    years_list.add(m["year"])

        elif self.type == "sonarr":
            while True:
                try:
                    series = self.client.get_series()
                    break
                except (
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                ):
                    continue

            for s in series:
                episodes = self.client.get_episode(s["id"], True)
                for e in episodes:
                    if "airDateUtc" in e:
                        if not self.search_specials and e["seasonNumber"] == 0:
                            continue
                        if not e["monitored"]:
                            continue
                        years_list.add(
                            datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ")
                            .replace(tzinfo=timezone.utc)
                            .year
                        )

        years_list = dict.fromkeys(years_list)
        if self.search_in_reverse:
            for key, _null in sorted(years_list.items(), key=lambda x: x[0], reverse=True):
                years.append(key)

        else:
            for key, _null in sorted(years_list.items(), key=lambda x: x[0], reverse=False):
                years.append(key)
        self.logger.trace("Years: %s", years)
        years_count = len(years)
        self.logger.trace("Years count: %s", years_count)
        return years, years_count

    def run_search_loop(self) -> NoReturn:
        run_logs(self.logger)
        try:
            self.register_search_mode()
            if not self.search_missing:
                return None
            loop_timer = timedelta(minutes=15)
            timer = datetime.now()
            years_index = 0
            totcommands = -1
            self.db_update_processed = False
            while True:
                if self.loop_completed:
                    years_index = 0
                    totcommands = -1
                    timer = datetime.now()
                if self.search_by_year:
                    totcommands = -1
                    if years_index == 0:
                        years, years_count = self.get_year_search()
                        try:
                            self.search_current_year = years[years_index]
                        except BaseException:
                            self.search_current_year = years[: years_index + 1]
                    self.logger.debug("Current year %s", self.search_current_year)
                try:
                    self.db_maybe_reset_entry_searched_state()
                    self.refresh_download_queue()
                    self.db_update()
                    # self.run_request_search()
                    try:
                        if self.search_by_year:
                            if years.index(self.search_current_year) != years_count - 1:
                                years_index += 1
                                self.search_current_year = years[years_index]
                            elif datetime.now() >= (timer + loop_timer):
                                self.refresh_download_queue()
                                time.sleep(((timer + loop_timer) - datetime.now()).total_seconds())
                                self.logger.trace("Restarting loop testing")
                                raise RestartLoopException
                        elif datetime.now() >= (timer + loop_timer):
                            self.refresh_download_queue()
                            self.logger.trace("Restarting loop testing")
                            raise RestartLoopException
                        for (
                            entry,
                            todays,
                            limit_bypass,
                            series_search,
                            commands,
                        ) in self.db_get_files():
                            if totcommands == -1:
                                totcommands = commands
                                self.logger.info("Starting search for %s items", totcommands)
                            if SEARCH_LOOP_DELAY == -1:
                                loop_delay = 30
                            else:
                                loop_delay = SEARCH_LOOP_DELAY
                            while not self.maybe_do_search(
                                entry,
                                todays=todays,
                                bypass_limit=limit_bypass,
                                series_search=series_search,
                                commands=totcommands,
                            ):
                                self.logger.debug("Waiting for active search commands")
                                time.sleep(loop_delay)
                            totcommands -= 1
                            self.logger.info("Delaying search loop by %s seconds", loop_delay)
                            time.sleep(loop_delay)
                            if totcommands == 0:
                                self.logger.info("All searches completed")
                            elif datetime.now() >= (timer + loop_timer):
                                timer = datetime.now()
                                self.logger.info(
                                    "Searches not completed, %s remaining", totcommands
                                )
                    except RestartLoopException:
                        self.loop_completed = True
                        self.db_update_processed = False
                        self.logger.info("Loop timer elapsed, restarting it.")
                    except NoConnectionrException as e:
                        self.logger.error(e.message)
                        self.manager.qbit_manager.should_delay_torrent_scan = True
                        raise DelayLoopException(length=300, type=e.type)
                    except DelayLoopException:
                        raise
                    except ValueError:
                        self.logger.info("Loop completed, restarting it.")
                        self.loop_completed = True
                    except qbittorrentapi.exceptions.APIConnectionError as e:
                        self.logger.warning(e)
                        raise DelayLoopException(length=300, type="qbit")
                    except Exception as e:
                        self.logger.exception(e, exc_info=sys.exc_info())
                    time.sleep(LOOP_SLEEP_TIMER)
                except DelayLoopException as e:
                    if e.type == "qbit":
                        self.logger.critical(
                            "Failed to connected to qBit client, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.type == "internet":
                        self.logger.critical(
                            "Failed to connected to the internet, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.type == "arr":
                        self.logger.critical(
                            "Failed to connected to the Arr instance, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.type == "delay":
                        self.logger.critical(
                            "Forced delay due to temporary issue with environment, "
                            "sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    time.sleep(e.length)
                    self.manager.qbit_manager.should_delay_torrent_scan = False
                except KeyboardInterrupt:
                    self.logger.hnotice("Detected Ctrl+C - Terminating process")
                    sys.exit(0)
                else:
                    time.sleep(5)
        except KeyboardInterrupt:
            self.logger.hnotice("Detected Ctrl+C - Terminating process")
            sys.exit(0)

    def run_torrent_loop(self) -> NoReturn:
        run_logs(self.logger)
        self.register_search_mode()
        self.logger.hnotice("Starting torrent monitoring for %s", self._name)
        while True:
            try:
                try:
                    try:
                        if not self.manager.qbit_manager.is_alive:
                            raise NoConnectionrException(
                                "Could not connect to qBit client.", type="qbit"
                            )
                        if not self.is_alive:
                            raise NoConnectionrException(
                                f"Could not connect to {self.uri}", type="arr"
                            )
                        self.process_torrents()
                    except NoConnectionrException as e:
                        self.logger.error(e.message)
                        self.manager.qbit_manager.should_delay_torrent_scan = True
                        raise DelayLoopException(length=300, type="arr")
                    except qbittorrentapi.exceptions.APIConnectionError as e:
                        self.logger.warning(e)
                        raise DelayLoopException(length=300, type="qbit")
                    except qbittorrentapi.exceptions.APIError as e:
                        self.logger.warning(e)
                        raise DelayLoopException(length=300, type="qbit")
                    except DelayLoopException:
                        raise
                    except KeyboardInterrupt:
                        self.logger.hnotice("Detected Ctrl+C - Terminating process")
                        sys.exit(0)
                    except Exception as e:
                        self.logger.error(e, exc_info=sys.exc_info())
                    time.sleep(LOOP_SLEEP_TIMER)
                except DelayLoopException as e:
                    if e.type == "qbit":
                        self.logger.critical(
                            "Failed to connected to qBit client, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.type == "internet":
                        self.logger.critical(
                            "Failed to connected to the internet, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.type == "arr":
                        self.logger.critical(
                            "Failed to connected to the Arr instance, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.type == "delay":
                        self.logger.critical(
                            "Forced delay due to temporary issue with environment, "
                            "sleeping for %s.",
                            timedelta(seconds=e.length),
                        )
                    elif e.type == "no_downloads":
                        self.logger.debug(
                            "No downloads in category, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    time.sleep(e.length)
                    self.manager.qbit_manager.should_delay_torrent_scan = False
                except KeyboardInterrupt:
                    self.logger.hnotice("Detected Ctrl+C - Terminating process")
                    sys.exit(0)
            except KeyboardInterrupt:
                self.logger.hnotice("Detected Ctrl+C - Terminating process")
                sys.exit(0)

    def spawn_child_processes(self):
        _temp = []
        if self.search_missing:
            self.process_search_loop = pathos.helpers.mp.Process(
                target=self.run_search_loop, daemon=True
            )
            self.manager.qbit_manager.child_processes.append(self.process_search_loop)
            _temp.append(self.process_search_loop)
        if not any([QBIT_DISABLED, SEARCH_ONLY]):
            self.process_torrent_loop = pathos.helpers.mp.Process(
                target=self.run_torrent_loop, daemon=True
            )
            self.manager.qbit_manager.child_processes.append(self.process_torrent_loop)
            _temp.append(self.process_torrent_loop)

        return len(_temp), _temp


class PlaceHolderArr(Arr):
    def __init__(self, name: str, manager: ArrManager):
        if name in manager.groups:
            raise OSError(f"Group '{name}' has already been registered.")
        self._name = name.title()
        self.category = name
        self.manager = manager
        self.queue = []
        self.cache = {}
        self.requeue_cache = {}
        self.sent_to_scan = set()
        self.sent_to_scan_hashes = set()
        self.files_probed = set()
        self.import_torrents = []
        self.change_priority = {}
        self.recheck = set()
        self.pause = set()
        self.skip_blacklist = set()
        self.remove_from_qbit = set()
        self.delete = set()
        self.resume = set()
        self.expiring_bool = ExpiringSet(max_age_seconds=10)
        self.ignore_torrents_younger_than = CONFIG.get(
            "Settings.IgnoreTorrentsYoungerThan", fallback=600
        )
        self.timed_ignore_cache = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.timed_skip = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.tracker_delay = ExpiringSet(max_age_seconds=600)
        self._LOG_LEVEL = self.manager.qbit_manager.logger.level
        self.logger = logging.getLogger(f"qBitrr.{self._name}")
        run_logs(self.logger, self._name)
        self.search_missing = False
        self.session = None
        self.search_setup_completed = False
        self.logger.hnotice("Starting %s monitor", self._name)

    def _process_errored(self):
        # Recheck all torrents marked for rechecking.
        if not self.recheck:
            return
        temp = defaultdict(list)
        updated_recheck = []
        for h in self.recheck:
            updated_recheck.append(h)
            if c := self.manager.qbit_manager.cache.get(h):
                temp[c].append(h)
        self.manager.qbit.torrents_recheck(torrent_hashes=updated_recheck)
        for k, v in temp.items():
            self.manager.qbit.torrents_set_category(torrent_hashes=v, category=k)

        for k in updated_recheck:
            self.timed_ignore_cache.add(k)
        self.recheck.clear()

    def _process_failed(self):
        if not (self.delete or self.skip_blacklist):
            return
        to_delete_all = self.delete
        skip_blacklist = {i.upper() for i in self.skip_blacklist}
        if to_delete_all:
            for arr in self.manager.managed_objects.values():
                if payload := arr.process_entries(to_delete_all):
                    for entry, hash_ in payload:
                        if hash_ in arr.cache:
                            arr._process_failed_individual(
                                hash_=hash_, entry=entry, skip_blacklist=skip_blacklist
                            )
        if self.remove_from_qbit or self.skip_blacklist or to_delete_all:
            # Remove all bad torrents from the Client.
            temp_to_delete = set()
            if to_delete_all:
                self.manager.qbit.torrents_delete(hashes=to_delete_all, delete_files=True)
            if self.remove_from_qbit or self.skip_blacklist:
                temp_to_delete = self.remove_from_qbit.union(self.skip_blacklist)
                self.manager.qbit.torrents_delete(hashes=temp_to_delete, delete_files=True)
            to_delete_all = to_delete_all.union(temp_to_delete)
            for h in to_delete_all:
                if h in self.manager.qbit_manager.name_cache:
                    del self.manager.qbit_manager.name_cache[h]
                if h in self.manager.qbit_manager.cache:
                    del self.manager.qbit_manager.cache[h]
        self.skip_blacklist.clear()
        self.remove_from_qbit.clear()
        self.delete.clear()

    def process(self):
        self._process_errored()
        self._process_failed()

    def process_torrents(self):
        try:
            try:
                while True:
                    try:
                        torrents = self.manager.qbit_manager.client.torrents.info(
                            status_filter="all",
                            category=self.category,
                            sort="added_on",
                            reverse=False,
                        )
                        break
                    except qbittorrentapi.exceptions.APIError:
                        continue
                torrents = [t for t in torrents if hasattr(t, "category")]
                if not len(torrents):
                    raise DelayLoopException(length=LOOP_SLEEP_TIMER, type="no_downloads")
                if not has_internet(self.manager.qbit_manager):
                    self.manager.qbit_manager.should_delay_torrent_scan = True
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="internet")
                if self.manager.qbit_manager.should_delay_torrent_scan:
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="delay")
                for torrent in torrents:
                    if torrent.category != RECHECK_CATEGORY:
                        self.manager.qbit_manager.cache[torrent.hash] = torrent.category
                    self.manager.qbit_manager.name_cache[torrent.hash] = torrent.name
                    if torrent.category == FAILED_CATEGORY:
                        # Bypass everything if manually marked as failed
                        self._process_single_torrent_failed_cat(torrent)
                    elif torrent.category == RECHECK_CATEGORY:
                        # Bypass everything else if manually marked for rechecking
                        self._process_single_torrent_recheck_cat(torrent)
                self.process()
            except NoConnectionrException as e:
                self.logger.error(e.message)
            except qbittorrentapi.exceptions.APIError as e:
                self.logger.error("The qBittorrent API returned an unexpected error")
                self.logger.debug("Unexpected APIError from qBitTorrent", exc_info=e)
                raise DelayLoopException(length=300, type="qbit")
            except qbittorrentapi.exceptions.APIConnectionError:
                self.logger.warning("Max retries exceeded")
                raise DelayLoopException(length=300, type="qbit")
            except DelayLoopException:
                raise
            except KeyboardInterrupt:
                self.logger.hnotice("Detected Ctrl+C - Terminating process")
                sys.exit(0)
            except Exception as e:
                self.logger.error(e, exc_info=sys.exc_info())
        except KeyboardInterrupt:
            self.logger.hnotice("Detected Ctrl+C - Terminating process")
            sys.exit(0)
        except DelayLoopException:
            raise

    def run_search_loop(self):
        return


class FreeSpaceManager(Arr):
    def __init__(self, categories: set[str], manager: ArrManager):
        self._name = "FreeSpaceManager"
        self.manager = manager
        self.logger = logging.getLogger(f"qBitrr.{self._name}")
        self._LOG_LEVEL = self.manager.qbit_manager.logger.level
        run_logs(self.logger, self._name)
        self.categories = categories
        self.logger.trace("Categories: %s", self.categories)
        self.pause = set()
        self.resume = set()
        self.expiring_bool = ExpiringSet(max_age_seconds=10)
        self.ignore_torrents_younger_than = CONFIG.get(
            "Settings.IgnoreTorrentsYoungerThan", fallback=600
        )
        self.timed_ignore_cache = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.needs_cleanup = False
        if FREE_SPACE_FOLDER == "CHANGE_ME":
            self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(
                next(iter(self.categories))
            )
        else:
            self.completed_folder = pathlib.Path(FREE_SPACE_FOLDER)
        self.min_free_space = FREE_SPACE
        self.current_free_space = shutil.disk_usage(self.completed_folder).free - parse_size(
            self.min_free_space
        )
        self.logger.trace("Current free space: %s", self.current_free_space)
        self.manager.qbit_manager.client.torrents_create_tags(["qBitrr-free_space_paused"])
        self.search_missing = False
        self.session = None
        self.register_torrent_database()
        self.logger.hnotice("Starting %s monitor", self._name)
        self.search_setup_completed = False

    def register_torrent_database(self):
        self.torrent_db = SqliteDatabase(None)
        self.torrent_db.init(
            str(APPDATA_FOLDER.joinpath("Torrents.db")),
            pragmas={
                "journal_mode": "wal",
                "cache_size": -1 * 64000,  # 64MB
                "foreign_keys": 1,
                "ignore_check_constraints": 0,
                "synchronous": 0,
            },
        )

        class Torrents(TorrentLibrary):
            class Meta:
                database = self.torrent_db

        self.torrent_db.connect()
        self.torrent_db.create_tables([Torrents])
        self.torrents = Torrents

    def _process_single_torrent_pause_disk_space(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.info(
            "Pausing torrent for disk space: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(torrent.added_on),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        self.pause.add(torrent.hash)

    def _process_single_torrent(self, torrent):
        if self.is_downloading_state(torrent):
            free_space_test = self.current_free_space
            free_space_test -= torrent["amount_left"]
            self.logger.trace(
                "Result [%s]: Free space %s -> %s",
                torrent.name,
                self.current_free_space,
                free_space_test,
            )
            if torrent.state_enum != TorrentStates.PAUSED_DOWNLOAD and free_space_test < 0:
                self.logger.info(
                    "Pause download [%s]: Free space %s -> %s",
                    torrent.name,
                    self.current_free_space,
                    free_space_test,
                )
                self.add_tags(torrent, ["qBitrr-free_space_paused"])
                self.remove_tags(torrent, ["qBitrr-allowed_seeding"])
                self._process_single_torrent_pause_disk_space(torrent)
            elif torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD and free_space_test < 0:
                self.logger.info(
                    "Leave paused [%s]: Free space %s -> %s",
                    torrent.name,
                    self.current_free_space,
                    free_space_test,
                )
                self.add_tags(torrent, ["qBitrr-free_space_paused"])
                self.remove_tags(torrent, ["qBitrr-allowed_seeding"])
            elif torrent.state_enum != TorrentStates.PAUSED_DOWNLOAD and free_space_test > 0:
                self.logger.info(
                    "Continue downloading [%s]: Free space %s -> %s",
                    torrent.name,
                    self.current_free_space,
                    free_space_test,
                )
                self.current_free_space = free_space_test
                self.remove_tags(torrent, ["qBitrr-free_space_paused"])
            elif torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD and free_space_test > 0:
                self.logger.info(
                    "Unpause download [%s]: Free space %s -> %s",
                    torrent.name,
                    self.current_free_space,
                    free_space_test,
                )
                self.current_free_space = free_space_test
                self.remove_tags(torrent, ["qBitrr-free_space_paused"])
        elif not self.is_downloading_state(torrent) and self.in_tags(
            torrent, "qBitrr-free_space_paused"
        ):
            self.logger.info(
                "Removing tag [%s] for completed torrent[%s]: Free space %s",
                "qBitrr-free_space_paused",
                torrent.name,
                self.current_free_space,
            )
            self.remove_tags(torrent, ["qBitrr-free_space_paused"])

    def process(self):
        self._process_paused()

    def process_torrents(self):
        try:
            try:
                while True:
                    try:
                        torrents = self.manager.qbit_manager.client.torrents.info(
                            status_filter="all", sort="added_on", reverse=False
                        )
                        break
                    except qbittorrentapi.exceptions.APIError:
                        continue
                torrents = [t for t in torrents if hasattr(t, "category")]
                torrents = [t for t in torrents if t.category in self.categories]
                torrents = [t for t in torrents if "qBitrr-ignored" not in t.tags]
                if not len(torrents):
                    raise DelayLoopException(length=LOOP_SLEEP_TIMER, type="no_downloads")
                if not has_internet(self.manager.qbit_manager):
                    self.manager.qbit_manager.should_delay_torrent_scan = True
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="internet")
                if self.manager.qbit_manager.should_delay_torrent_scan:
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="delay")
                self.current_free_space = shutil.disk_usage(
                    self.completed_folder
                ).free - parse_size(self.min_free_space)
                self.logger.trace("Current free space: %s", self.current_free_space)
                sorted_torrents = sorted(torrents, key=lambda t: t["priority"])
                for torrent in sorted_torrents:
                    with contextlib.suppress(qbittorrentapi.NotFound404Error):
                        self._process_single_torrent(torrent)
                if len(self.pause) == 0:
                    self.logger.trace("No torrents to pause")
                self.process()
            except NoConnectionrException as e:
                self.logger.error(e.message)
            except qbittorrentapi.exceptions.APIError as e:
                self.logger.error("The qBittorrent API returned an unexpected error")
                self.logger.debug("Unexpected APIError from qBitTorrent", exc_info=e)
                raise DelayLoopException(length=300, type="qbit")
            except qbittorrentapi.exceptions.APIConnectionError:
                self.logger.warning("Max retries exceeded")
                raise DelayLoopException(length=300, type="qbit")
            except DelayLoopException:
                raise
            except KeyboardInterrupt:
                self.logger.hnotice("Detected Ctrl+C - Terminating process")
                sys.exit(0)
            except Exception as e:
                self.logger.error(e, exc_info=sys.exc_info())
        except KeyboardInterrupt:
            self.logger.hnotice("Detected Ctrl+C - Terminating process")
            sys.exit(0)
        except DelayLoopException:
            raise

    def run_search_loop(self):
        return


class ArrManager:
    def __init__(self, qbitmanager: qBitManager):
        self.groups: set[str] = set()
        self.uris: set[str] = set()
        self.special_categories: set[str] = {FAILED_CATEGORY, RECHECK_CATEGORY}
        self.arr_categories: set[str] = set()
        self.category_allowlist: set[str] = self.special_categories.copy()
        self.completed_folders: set[pathlib.Path] = set()
        self.managed_objects: dict[str, Arr] = {}
        self.qbit: qbittorrentapi.Client = qbitmanager.client
        self.qbit_manager: qBitManager = qbitmanager
        self.ffprobe_available: bool = self.qbit_manager.ffprobe_downloader.probe_path.exists()
        self.logger = logging.getLogger("qBitrr.ArrManager")
        run_logs(self.logger)
        if not self.ffprobe_available and not any([QBIT_DISABLED, SEARCH_ONLY]):
            self.logger.error(
                "'%s' was not found, disabling all functionality dependant on it",
                self.qbit_manager.ffprobe_downloader.probe_path,
            )

    def build_arr_instances(self):
        for key in CONFIG.sections():
            if search := re.match("(rad|son|anim)arr.*", key, re.IGNORECASE):
                name = search.group(0)
                match = search.group(1)
                if match.lower() == "son":
                    call_cls = SonarrAPI
                elif match.lower() == "anim":
                    call_cls = SonarrAPI
                elif match.lower() == "rad":
                    call_cls = RadarrAPI
                else:
                    call_cls = None
                try:
                    managed_object = Arr(name, self, client_cls=call_cls)
                    self.groups.add(name)
                    self.uris.add(managed_object.uri)
                    self.managed_objects[managed_object.category] = managed_object
                    self.arr_categories.add(managed_object.category)
                except ValueError as e:
                    self.logger.exception("Value Error: %s", e)
                except SkipException:
                    continue
                except (OSError, TypeError) as e:
                    self.logger.exception(e)
        if FREE_SPACE != "-1" and AUTO_PAUSE_RESUME:
            managed_object = FreeSpaceManager(self.arr_categories, self)
            self.managed_objects["FreeSpaceManager"] = managed_object
        for cat in self.special_categories:
            managed_object = PlaceHolderArr(cat, self)
            self.managed_objects[cat] = managed_object
        return self
