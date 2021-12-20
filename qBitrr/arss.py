from __future__ import annotations

import contextlib
import itertools
import logging
import pathlib
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Callable, Iterable, Iterator, NoReturn

import ffmpeg
import pathos
import qbittorrentapi
import requests
from peewee import JOIN, SqliteDatabase
from pyarr import RadarrAPI, SonarrAPI
from qbittorrentapi import TorrentDictionary, TorrentStates

from qBitrr.arr_tables import CommandsModel, EpisodesModel, MoviesModel, SeriesModel
from qBitrr.config import (
    APPDATA_FOLDER,
    COMPLETED_DOWNLOAD_FOLDER,
    CONFIG,
    FAILED_CATEGORY,
    LOOP_SLEEP_TIMER,
    NO_INTERNET_SLEEP_TIMER,
    RECHECK_CATEGORY,
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
)
from qBitrr.utils import (
    ExpiringSet,
    absolute_file_paths,
    has_internet,
    validate_and_return_torrent_file,
)

if TYPE_CHECKING:
    from qBitrr.main import qBitManager


class Arr:
    def __init__(
        self,
        name: str,
        manager: ArrManager,
        client_cls: type[Callable | RadarrAPI | SonarrAPI],
    ):
        if name in manager.groups:
            raise OSError("Group '{name}' has already been registered.")
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
        self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(self.category)
        if not self.completed_folder.exists():
            try:
                self.completed_folder.mkdir(parents=True)
            except Exception:
                raise OSError(
                    f"{self._name} completed folder is a requirement, "
                    f"The specified folder does not exist '{self.completed_folder}'"
                )
        self.manager = manager
        self._LOG_LEVEL = self.manager.qbit_manager.logger.level
        self.logger = logging.getLogger(f"qBitrr.{self._name}")
        run_logs(self.logger)
        self.apikey = CONFIG.get_or_raise(f"{name}.APIKey")
        self.re_search = CONFIG.get(f"{name}.ReSearch", fallback=False)
        self.import_mode = CONFIG.get(f"{name}.importMode", fallback="Move")
        self.refresh_downloads_timer = CONFIG.get(f"{name}.RefreshDownloadsTimer", fallback=1)
        self.rss_sync_timer = CONFIG.get(f"{name}.RssSyncTimer", fallback=15)

        self.case_sensitive_matches = CONFIG.get(
            f"{name}.Torrent.CaseSensitiveMatches", fallback=[]
        )
        self.folder_exclusion_regex = CONFIG.get(
            f"{name}.Torrent.FolderExclusionRegex", fallback=[]
        )
        self.file_name_exclusion_regex = CONFIG.get(
            f"{name}.Torrent.FileNameExclusionRegex", fallback=[]
        )
        self.file_extension_allowlist = CONFIG.get(
            f"{name}.Torrent.FileExtensionAllowlist", fallback=[]
        )
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
            if not (r := i.get("URI")) not in self._remove_trackers_if_exists
        }
        self._add_trackers_if_missing: set[str] = {
            i.get("URI") for i in self.monitored_trackers if i.get("AddTrackerIfMissing") is True
        }
        if self.auto_delete is True and not self.completed_folder.parent.exists():
            self.auto_delete = False
            self.logger.critical(
                "AutoDelete disabled due to missing folder: '%s'",
                self.completed_folder.parent,
            )

        self.reset_on_completion = CONFIG.get(
            f"{name}.EntrySearch.SearchAgainOnSearchCompletion", fallback=False
        )
        self.do_upgrade_search = CONFIG.get(f"{name}.EntrySearch.DoUpgradeSearch", fallback=False)
        self.quality_unmet_search = CONFIG.get(
            f"{name}.EntrySearch.QualityUnmetSearch", fallback=False
        )

        self.ignore_torrents_younger_than = CONFIG.get(
            f"{name}.Torrent.IgnoreTorrentsYoungerThan", fallback=600
        )
        self.maximum_eta = CONFIG.get(f"{name}.Torrent.MaximumETA", fallback=86400)
        self.maximum_deletable_percentage = CONFIG.get(
            f"{name}.Torrent.MaximumDeletablePercentage", fallback=0.95
        )
        self.search_missing = CONFIG.get(f"{name}.EntrySearch.SearchMissing", fallback=False)
        self.search_specials = CONFIG.get(f"{name}.EntrySearch.AlsoSearchSpecials", fallback=False)
        self.search_by_year = CONFIG.get(f"{name}.EntrySearch.SearchByYear", fallback=True)
        self.search_in_reverse = CONFIG.get(f"{name}.EntrySearch.SearchInReverse", fallback=False)

        self.search_starting_year = CONFIG.get(
            f"{name}.EntrySearch.StartYear", fallback=datetime.now().year
        )
        self.search_ending_year = CONFIG.get(f"{name}.EntrySearch.LastYear", fallback=1990)
        self.search_command_limit = CONFIG.get(f"{name}.EntrySearch.SearchLimit", fallback=5)
        self.prioritize_todays_release = CONFIG.get(
            f"{name}.EntrySearch.PrioritizeTodaysReleases", fallback=True
        )

        self.do_not_remove_slow = CONFIG.get(f"{name}.Torrent.DoNotRemoveSlow", fallback=False)

        if self.search_in_reverse:
            self.search_current_year = self.search_ending_year
            self._delta = 1
        else:
            self.search_current_year = self.search_starting_year
            self._delta = -1
        arr_db_file = CONFIG.get(f"{name}.EntrySearch.DatabaseFile", fallback=None)

        if self.search_missing and arr_db_file is None:
            self.logger.critical("Arr DB file not specified setting SearchMissing to False")
            self.search_missing = False
        self.arr_db_file = pathlib.Path(arr_db_file)
        self._app_data_folder = APPDATA_FOLDER
        self.search_db_file = self._app_data_folder.joinpath(f"{self._name}.db")
        if self.search_missing and not self.arr_db_file.exists():
            self.logger.critical(
                "Arr DB file cannot be located setting SearchMissing to False: %s",
                self.arr_db_file,
            )
            self.search_missing = False

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
            self.folder_exclusion_regex_re = re.compile(
                "|".join(self.folder_exclusion_regex), re.DOTALL
            )
            self.file_name_exclusion_regex_re = re.compile(
                "|".join(self.file_name_exclusion_regex), re.DOTALL
            )
        else:
            self.folder_exclusion_regex_re = re.compile(
                "|".join(self.folder_exclusion_regex), re.IGNORECASE | re.DOTALL
            )
            self.file_name_exclusion_regex_re = re.compile(
                "|".join(self.file_name_exclusion_regex), re.IGNORECASE | re.DOTALL
            )
        self.client = client_cls(host_url=self.uri, api_key=self.apikey)
        if isinstance(self.client, SonarrAPI):
            self.type = "sonarr"
        elif isinstance(self.client, RadarrAPI):
            self.type = "radarr"

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
        self.change_priority = dict()
        self.recheck = set()
        self.pause = set()
        self.skip_blacklist = set()
        self.delete = set()
        self.resume = set()
        self.files_to_explicitly_delete: Iterator = iter([])
        self.missing_files_post_delete = set()
        self.missing_files_post_delete_blacklist = set()
        self.needs_cleanup = False
        self.recently_queue = dict()

        self.timed_ignore_cache = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.timed_skip = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.tracker_delay = ExpiringSet(max_age_seconds=600)
        self.special_casing_file_check = ExpiringSet(max_age_seconds=10)
        self.expiring_bool = ExpiringSet(max_age_seconds=10)
        self.session = requests.Session()
        self.cleaned_torrents = set()

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
        self.logger.debug(
            "Script Config:  CaseSensitiveMatches=%s",
            self.case_sensitive_matches,
        )
        self.logger.debug(
            "Script Config:  FolderExclusionRegex=%s",
            self.folder_exclusion_regex,
        )
        self.logger.debug(
            "Script Config:  FileNameExclusionRegex=%s",
            self.file_name_exclusion_regex,
        )
        self.logger.debug(
            "Script Config:  FileExtensionAllowlist=%s",
            self.file_extension_allowlist,
        )
        self.logger.debug("Script Config:  AutoDelete=%s", self.auto_delete)

        self.logger.debug(
            "Script Config:  IgnoreTorrentsYoungerThan=%s",
            self.ignore_torrents_younger_than,
        )
        self.logger.debug("Script Config:  MaximumETA=%s", self.maximum_eta)

        if self.search_missing:
            self.logger.debug(
                "Script Config:  SearchMissing=%s",
                self.search_missing,
            )
            self.logger.debug(
                "Script Config:  AlsoSearchSpecials=%s",
                self.search_specials,
            )
            self.logger.debug(
                "Script Config:  SearchByYear=%s",
                self.search_by_year,
            )
            self.logger.debug(
                "Script Config:  SearchInReverse=%s",
                self.search_in_reverse,
            )
            self.logger.debug(
                "Script Config:  StartYear=%s",
                self.search_starting_year,
            )
            self.logger.debug(
                "Script Config:  LastYear=%s",
                self.search_ending_year,
            )
            self.logger.debug(
                "Script Config:  CommandLimit=%s",
                self.search_command_limit,
            )
            self.logger.debug(
                "Script Config:  DatabaseFile=%s",
                self.arr_db_file,
            )
            self.logger.debug(
                "Script Config:  MaximumDeletablePercentage=%s",
                self.maximum_deletable_percentage,
            )
            self.logger.debug(
                "Script Config:  DoUpgradeSearch=%s",
                self.do_upgrade_search,
            )
            self.logger.debug(
                "Script Config:  PrioritizeTodaysReleases=%s",
                self.prioritize_todays_release,
            )
            self.logger.debug(
                "Script Config:  SearchBySeries=%s",
                self.series_search,
            )
            self.logger.debug(
                "Script Config:  SearchOmbiRequests=%s",
                self.ombi_search_requests,
            )
            if self.ombi_search_requests:
                self.logger.debug(
                    "Script Config:  OmbiURI=%s",
                    self.ombi_uri,
                )
                self.logger.debug(
                    "Script Config:  OmbiAPIKey=%s",
                    self.ombi_api_key,
                )
                self.logger.debug(
                    "Script Config:  ApprovedOnly=%s",
                    self.ombi_approved_only,
                )
            self.logger.debug(
                "Script Config:  SearchOverseerrRequests=%s",
                self.overseerr_requests,
            )
            if self.overseerr_requests:
                self.logger.debug(
                    "Script Config:  OverseerrURI=%s",
                    self.overseerr_uri,
                )
                self.logger.debug(
                    "Script Config:  OverseerrAPIKey=%s",
                    self.overseerr_api_key,
                )
            if self.ombi_search_requests or self.overseerr_requests:
                self.logger.debug(
                    "Script Config:  SearchRequestsEvery=%s",
                    self.search_requests_every_x_seconds,
                )
        self.search_setup_completed = False
        self.model_arr_file: EpisodesModel | MoviesModel = None
        self.model_arr_series_file: SeriesModel = None

        self.model_arr_command: CommandsModel = None
        self.model_file: EpisodeFilesModel | MoviesFilesModel = None
        self.series_file_model: SeriesFilesModel = None
        self.model_queue: EpisodeQueueModel | MovieQueueModel = None
        self.persistent_queue: FilesQueued = None
        self.logger.hnotice("Starting %s monitor", self._name)

    @property
    def is_alive(self) -> bool:
        try:
            if 1 in self.expiring_bool:
                return True
            if self.session is None:
                self.expiring_bool.add(1)
                return True
            req = self.session.get(f"{self.uri}/api/v3/system/status", timeout=2)
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
        return torrent.state_enum in (
            TorrentStates.DOWNLOADING,
            TorrentStates.PAUSED_DOWNLOAD,
        )

    def _get_arr_modes(
        self,
    ) -> tuple[
        type[EpisodesModel] | type[MoviesModel],
        type[CommandsModel],
        type[SeriesModel] | None,
    ]:
        if self.type == "sonarr":
            return EpisodesModel, CommandsModel, SeriesModel
        elif self.type == "radarr":
            return MoviesModel, CommandsModel, None

    def _get_models(
        self,
    ) -> tuple[type[EpisodeFilesModel], type[EpisodeQueueModel], type[SeriesFilesModel] | None]:
        if self.type == "sonarr":
            if self.series_search:
                return EpisodeFilesModel, EpisodeQueueModel, SeriesFilesModel
            return EpisodeFilesModel, EpisodeQueueModel, None
        elif self.type == "radarr":
            return MoviesFilesModel, MovieQueueModel, None
        else:
            raise UnhandledError("Well you shouldn't have reached here, Arr.type=%s" % self.type)

    def _get_oversee_requests_all(self) -> dict[str, set]:
        try:
            if self.overseerr_approved_only:
                key = "approved"
            else:
                key = "unavailable"
            if self.overseerr_is_4k:
                status_key = "status4k"
            else:
                status_key = "status"
            data = defaultdict(set)
            response = self.session.get(
                url=f"{self.overseerr_uri}/api/v1/"
                f"request?take=100&skip=0&sort=added&filter={key}",
                headers={"X-Api-Key": self.overseerr_api_key},
                timeout=2,
            )
            response = response.json().get("results", [])
            type_ = None
            if self.type == "sonarr":
                type_ = "tv"
            elif self.type == "radarr":
                type_ = "movie"
            for entry in response:
                type__ = entry.get("type")
                if type_ != type__:
                    continue
                if self.overseerr_approved_only and entry.get("media", {}).get(status_key) == 5:
                    continue
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
            raise UnhandledError("Well you shouldn't have reached here, Arr.type=%s" % self.type)
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
            raise UnhandledError("Well you shouldn't have reached here, Arr.type=%s" % self.type)
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
        if self.pause:
            self.needs_cleanup = True
            self.logger.debug("Pausing %s completed torrents", len(self.pause))
            for i in self.pause:
                self.logger.debug(
                    "Pausing %s (%s)",
                    i,
                    self.manager.qbit_manager.name_cache.get(i),
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
                if self.type == "sonarr":
                    self.logger.success(
                        "DownloadedEpisodesScan: %s",
                        path,
                    )
                    self.post_command(
                        "DownloadedEpisodesScan",
                        path=str(path),
                        downloadClientId=torrent.hash.upper(),
                        importMode=self.import_mode,
                    )
                elif self.type == "radarr":
                    self.logger.success("DownloadedMoviesScan: %s", path)
                    self.post_command(
                        "DownloadedMoviesScan",
                        path=str(path),
                        downloadClientId=torrent.hash.upper(),
                        importMode=self.import_mode,
                    )
                self.sent_to_scan.add(path)
            self.import_torrents.clear()

    def _process_failed_individual(self, hash_: str, entry: int, skip_blacklist: set[str]) -> None:
        with contextlib.suppress(Exception):
            if hash_ not in skip_blacklist:
                self.logger.debug(
                    "Blocklisting: %s (%s)",
                    hash_,
                    self.manager.qbit_manager.name_cache.get(hash_, "Deleted"),
                )
                self.delete_from_queue(id_=entry, blacklist=True)
            else:
                self.delete_from_queue(id_=entry, blacklist=False)
        if hash_ in self.recently_queue:
            del self.recently_queue[hash_]
        object_id = self.requeue_cache.get(entry)
        if self.re_search and object_id:
            if self.type == "sonarr":
                object_ids = object_id
                for object_id in object_ids:
                    data = self.client.get_episode_by_episode_id(object_id)
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
                        self.logger.notice(
                            "Re-Searching episode: %s",
                            object_id,
                        )
                    self.post_command("EpisodeSearch", episodeIds=[object_id])
                    if self.persistent_queue and series_id:
                        self.persistent_queue.insert(EntryId=series_id).on_conflict_ignore()
            elif self.type == "radarr":
                data = self.client.get_movie_by_movie_id(object_id)
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
                    self.logger.notice(
                        "Re-Searching movie: %s",
                        object_id,
                    )
                self.post_command("MoviesSearch", movieIds=[object_id])
                if self.persistent_queue:
                    self.persistent_queue.insert(EntryId=object_id).on_conflict_ignore()

    def _process_errored(self) -> None:
        # Recheck all torrents marked for rechecking.
        if self.recheck:
            self.needs_cleanup = True
            updated_recheck = [r for r in self.recheck]
            self.manager.qbit.torrents_recheck(torrent_hashes=updated_recheck)
            for k in updated_recheck:
                self.timed_ignore_cache.add(k)
            self.recheck.clear()

    def _process_failed(self) -> None:
        to_delete_all = self.delete.union(self.skip_blacklist).union(
            self.missing_files_post_delete, self.missing_files_post_delete_blacklist
        )
        if self.missing_files_post_delete or self.missing_files_post_delete_blacklist:
            delete_ = True
        else:
            delete_ = False
        skip_blacklist = {
            i.upper() for i in self.skip_blacklist.union(self.missing_files_post_delete)
        }
        if to_delete_all:
            self.needs_cleanup = True
            payload, hashes = self.process_entries(to_delete_all)
            if payload:
                for entry, hash_ in payload:
                    self._process_failed_individual(
                        hash_=hash_, entry=entry, skip_blacklist=skip_blacklist
                    )
            # Remove all bad torrents from the Client.
            self.manager.qbit.torrents_delete(hashes=to_delete_all, delete_files=True)
            for h in to_delete_all:
                self.cleaned_torrents.discard(h)
                self.sent_to_scan_hashes.discard(h)

                if h in self.manager.qbit_manager.name_cache:
                    del self.manager.qbit_manager.name_cache[h]
                if h in self.manager.qbit_manager.cache:
                    del self.manager.qbit_manager.cache[h]
        if delete_:
            self.missing_files_post_delete.clear()
            self.missing_files_post_delete_blacklist.clear()
        self.skip_blacklist.clear()
        self.delete.clear()

    def _process_file_priority(self) -> None:
        # Set all files marked as "Do not download" to not download.
        for hash_, files in self.change_priority.copy().items():
            self.needs_cleanup = True
            name = self.manager.qbit_manager.name_cache.get(hash_)
            if name:
                self.logger.debug(
                    "Updating file priority on torrent: %s (%s)",
                    name,
                    hash_,
                )
                self.manager.qbit.torrents_file_priority(
                    torrent_hash=hash_, file_ids=files, priority=0
                )
            else:
                self.logger.error("Torrent does not exist? %s", hash_)
            del self.change_priority[hash_]

    def _process_resume(self) -> None:
        if self.resume:
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
            self.post_command("RssSync")
            self.rss_sync_timer_last_checked = now

        if (
            self.refresh_downloads_timer_last_checked is not None
            and self.refresh_downloads_timer_last_checked
            < now - timedelta(minutes=self.refresh_downloads_timer)
        ):
            self.post_command("RefreshMonitoredDownloads")
            self.refresh_downloads_timer_last_checked = now

    def arr_db_query_commands_count(self) -> int:
        if not self.search_missing:
            return 0
        search_commands = (
            self.model_arr_command.select()
            .where(
                (self.model_arr_command.EndedAt.is_null(True))
                & (self.model_arr_command.Name.endswith("Search"))
            )
            .execute()
        )
        return len(list(search_commands))

    def _search_todays(self, condition):
        if self.prioritize_todays_release:
            condition_today = copy(condition)
            condition_today &= self.model_file.AirDateUtc >= datetime.now(timezone.utc).date()
            for entry in (
                self.model_file.select()
                .where(condition_today)
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
        tuple[MoviesFilesModel | EpisodeFilesModel | SeriesFilesModel, bool, bool, bool]
    ]:
        if self.type == "sonarr" and self.series_search:
            for i1, i2, i3 in self.db_get_files_series():
                yield i1, i2, i3, i3 is not True
        else:
            for i1, i2, i3 in self.db_get_files_episodes():
                yield i1, i2, i3, False

    def db_maybe_reset_entry_searched_state(self):
        if self.type == "sonarr":
            self.db_reset__series_searched_state()
            self.db_reset__episode_searched_state()
        elif self.type == "radarr":
            self.db_reset__movie_searched_state()

    def db_reset__series_searched_state(self):
        if (
            self.loop_completed is True and self.reset_on_completion
        ):  # Only wipe if a loop completed was tagged
            self.series_file_model.update(Searched=False).where(
                self.model_file.Searched == True & self.model_file.EpisodeFileId == 0
            ).execute()

    def db_reset__episode_searched_state(self):
        if (
            self.loop_completed is True and self.reset_on_completion
        ):  # Only wipe if a loop completed was tagged
            self.model_file.update(Searched=False).where(
                self.model_file.Searched == True & self.model_file.EpisodeFileId == 0
            ).execute()

    def db_reset__movie_searched_state(self):
        if (
            self.loop_completed is True and self.reset_on_completion
        ):  # Only wipe if a loop completed was tagged
            self.model_file.update(Searched=False).where(
                self.model_file.Searched == True & self.model_file.MovieFileId == 0
            ).execute()

    def db_get_files_series(
        self,
    ) -> Iterable[tuple[MoviesFilesModel | SeriesFilesModel | EpisodeFilesModel, bool, bool]]:
        if not self.search_missing:
            yield None, False, False
        elif not self.series_search:
            yield None, False, False
        elif self.type == "sonarr":
            condition = self.model_file.AirDateUtc.is_null(False)
            if not self.search_specials:
                condition &= self.model_file.SeasonNumber != 0
            if not self.do_upgrade_search:
                condition &= self.model_file.Searched == False
                condition &= self.model_file.EpisodeFileId == 0
            condition &= self.model_file.AirDateUtc < (
                datetime.now(timezone.utc) - timedelta(hours=2)
            )
            condition &= self.model_file.AbsoluteEpisodeNumber.is_null(
                False
            ) | self.model_file.SceneAbsoluteEpisodeNumber.is_null(False)
            for i1, i2, i3 in self._search_todays(condition):
                if i1 is not None:
                    yield i1, i2, i3
            if not self.do_upgrade_search:
                condition = self.series_file_model.Searched == False
            else:
                condition = self.series_file_model.Searched.is_null(False)
            for entry_ in (
                self.series_file_model.select()
                .where(condition)
                .order_by(self.series_file_model.EntryId.asc())
                .execute()
            ):
                yield entry_, False, False
        elif self.type == "radarr":
            condition = self.model_file.Year == self.search_current_year
            if not self.do_upgrade_search:
                condition &= self.model_file.Searched == False
                condition &= self.model_file.MovieFileId == 0
            for entry in (
                self.model_file.select()
                .where(condition)
                .order_by(self.model_file.Title.asc())
                .execute()
            ):
                yield entry, False, False

    def db_get_files_episodes(
        self,
    ) -> Iterable[tuple[MoviesFilesModel | EpisodeFilesModel, bool, bool]]:
        if not self.search_missing:
            yield None, False, False
        elif self.type == "sonarr":
            condition = self.model_file.AirDateUtc.is_null(False)

            if not self.search_specials:
                condition &= self.model_file.SeasonNumber != 0
            condition &= self.model_file.AirDateUtc.is_null(False)
            if not self.do_upgrade_search:
                if self.quality_unmet_search:
                    condition &= self.model_file.QualityMet == False
                else:
                    condition &= self.model_file.Searched == False
                    condition &= self.model_file.EpisodeFileId == 0
            condition &= self.model_file.AirDateUtc < (
                datetime.now(timezone.utc) - timedelta(hours=2)
            )
            condition &= self.model_file.AbsoluteEpisodeNumber.is_null(
                False
            ) | self.model_file.SceneAbsoluteEpisodeNumber.is_null(False)
            today_condition = copy(condition)
            for entry_ in (
                self.model_file.select()
                .where(condition)
                .order_by(
                    self.model_file.SeriesTitle,
                    self.model_file.SeasonNumber.desc(),
                    self.model_file.AirDateUtc.desc(),
                )
                .group_by(self.model_file.SeriesId)
                .execute()
            ):
                condition_series = copy(condition)
                condition_series &= self.model_file.SeriesId == entry_.SeriesId
                has_been_queried = (
                    self.persistent_queue.get_or_none(
                        self.persistent_queue.EntryId == entry_.SeriesId
                    )
                    is not None
                )
                for entry in (
                    self.model_file.select()
                    .where(condition_series)
                    .order_by(
                        self.model_file.SeasonNumber.desc(),
                        self.model_file.AirDateUtc.desc(),
                    )
                    .execute()
                ):
                    yield entry, False, has_been_queried
                    has_been_queried = True
                for i1, i2, i3 in self._search_todays(today_condition):
                    if i1 is not None:
                        yield i1, i2, i3
        elif self.type == "radarr":
            condition = self.model_file.Year == self.search_current_year
            if not self.do_upgrade_search:
                if self.quality_unmet_search:
                    condition &= self.model_file.QualityMet == False
                else:
                    condition &= self.model_file.Searched == False
                    condition &= self.model_file.MovieFileId == 0
            for entry in (
                self.model_file.select()
                .where(condition)
                .order_by(self.model_file.Title.asc())
                .execute()
            ):
                yield entry, False, False

    def db_get_request_files(self) -> Iterable[MoviesFilesModel | EpisodeFilesModel]:
        if (not self.ombi_search_requests) or (not self.overseerr_requests):
            yield None
        if not self.search_missing:
            yield None
        elif self.type == "sonarr":
            condition = self.model_file.IsRequest == True
            if not self.do_upgrade_search:
                if self.quality_unmet_search:
                    condition &= self.model_file.QualityMet == False
                else:
                    condition &= self.model_file.EpisodeFileId == 0
            if not self.search_specials:
                condition &= self.model_file.SeasonNumber != 0
            condition &= self.model_file.AbsoluteEpisodeNumber.is_null(
                False
            ) | self.model_file.SceneAbsoluteEpisodeNumber.is_null(False)
            condition &= self.model_file.AirDateUtc.is_null(False)
            condition &= self.model_file.AirDateUtc < (
                datetime.now(timezone.utc) - timedelta(hours=2)
            )
            yield from (
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
            condition = self.model_file.Year <= datetime.now(timezone.utc).year
            condition &= self.model_file.Year > 0
            if not self.do_upgrade_search:
                if self.quality_unmet_search:
                    condition &= self.model_file.QualityMet == False
                else:
                    condition &= self.model_file.MovieFileId == 0
                    condition &= self.model_file.IsRequest == True
            yield from (
                self.model_file.select()
                .where(condition)
                .order_by(self.model_file.Title.asc())
                .execute()
            )

    def db_request_update(self):
        if self.overseerr_requests:
            self.db_overseerr_update()
        else:
            self.db_ombi_update()

    def _db_request_update(self, request_ids: dict[str, set[int | str]]):
        with self.db.atomic():
            if self.type == "sonarr" and any(i in request_ids for i in ["ImdbId", "TvdbId"]):
                self.model_arr_file: EpisodesModel
                self.model_arr_series_file: SeriesModel
                condition = self.model_arr_file.AirDateUtc.is_null(False)
                if not self.search_specials:
                    condition &= self.model_arr_file.SeasonNumber != 0
                condition &= self.model_arr_file.AbsoluteEpisodeNumber.is_null(
                    False
                ) | self.model_arr_file.SceneAbsoluteEpisodeNumber.is_null(False)
                condition &= self.model_arr_file.AirDateUtc < datetime.now(timezone.utc)
                imdb_con = None
                tvdb_con = None
                if ImdbIds := request_ids.get("ImdbId"):
                    imdb_con = self.model_arr_series_file.ImdbId.in_(ImdbIds)
                if tvDbIds := request_ids.get("TvdbId"):
                    tvdb_con = self.model_arr_series_file.TvdbId.in_(tvDbIds)
                if imdb_con and tvdb_con:
                    condition &= imdb_con | tvdb_con
                elif imdb_con:
                    condition &= imdb_con
                elif tvdb_con:
                    condition &= tvdb_con
                for db_entry in (
                    self.model_arr_file.select()
                    .join(
                        self.model_arr_series_file,
                        on=(self.model_arr_file.SeriesId == self.model_arr_series_file.Id),
                        join_type=JOIN.LEFT_OUTER,
                    )
                    .switch(self.model_arr_file)
                    .where(condition)
                ):
                    self.db_update_single_series(db_entry=db_entry, request=True)
            elif self.type == "radarr" and any(i in request_ids for i in ["ImdbId", "TmdbId"]):
                self.model_arr_file: MoviesModel
                condition = self.model_arr_file.Year <= datetime.now().year
                condition &= self.model_arr_file.Year > 0
                tmdb_con = None
                imdb_con = None
                if ImdbIds := request_ids.get("ImdbId"):
                    imdb_con = self.model_arr_file.ImdbId.in_(ImdbIds)
                if TmdbIds := request_ids.get("TmdbId"):
                    tmdb_con = self.model_arr_file.TmdbId.in_(TmdbIds)
                if tmdb_con and imdb_con:
                    condition &= tmdb_con | imdb_con
                elif tmdb_con:
                    condition &= tmdb_con
                elif imdb_con:
                    condition &= imdb_con
                for db_entry in (
                    self.model_arr_file.select()
                    .where(condition)
                    .order_by(self.model_arr_file.Added.desc())
                ):
                    self.db_update_single_series(db_entry=db_entry, request=True)

    def db_overseerr_update(self):
        if (not self.search_missing) or (not self.overseerr_requests):
            return
        if self._get_overseerr_requests_count() == 0:
            return
        request_ids = self._temp_overseer_request_cache
        if not any(i in request_ids for i in ["ImdbId", "TmdbId", "TvdbId"]):
            return
        self.logger.notice(f"Started updating database with Overseerr request entries.")
        self._db_request_update(request_ids)
        self.logger.notice(f"Finished updating database with Overseerr request entries")

    def db_ombi_update(self):
        if (not self.search_missing) or (not self.ombi_search_requests):
            return
        if self._get_ombi_request_count() == 0:
            return
        request_ids = self._process_ombi_requests()
        if not any(i in request_ids for i in ["ImdbId", "TmdbId", "TvdbId"]):
            return
        self.logger.notice(f"Started updating database with Ombi request entries.")
        self._db_request_update(request_ids)
        self.logger.notice(f"Finished updating database with Ombi request entries")

    def db_update_todays_releases(self):
        if not self.prioritize_todays_release:
            return
        with self.db.atomic():
            if self.type == "sonarr":
                for series in self.model_arr_file.select().where(
                    (self.model_arr_file.AirDateUtc.is_null(False))
                    & (self.model_arr_file.AirDateUtc < datetime.now(timezone.utc))
                    & (self.model_arr_file.AirDateUtc >= datetime.now(timezone.utc).date())
                    & (
                        self.model_arr_file.AbsoluteEpisodeNumber.is_null(False)
                        | self.model_arr_file.SceneAbsoluteEpisodeNumber.is_null(False)
                    )
                ):
                    self.db_update_single_series(db_entry=series)

    def db_update(self):
        if not self.search_missing:
            return
        self.logger.trace(f"Started updating database")
        self.db_update_todays_releases()
        with self.db.atomic():

            if self.type == "sonarr":
                if not self.series_search:
                    _series = set()
                    for series in self.model_arr_file.select().where(
                        (self.model_arr_file.AirDateUtc.is_null(False))
                        & (self.model_arr_file.AirDateUtc < datetime.now(timezone.utc))
                        & (
                            self.model_arr_file.AbsoluteEpisodeNumber.is_null(False)
                            | self.model_arr_file.SceneAbsoluteEpisodeNumber.is_null(False)
                        )
                        & (
                            self.model_arr_file.AirDateUtc
                            >= datetime(month=1, day=1, year=self.search_current_year)
                        )
                        & (
                            self.model_arr_file.AirDateUtc
                            <= datetime(month=12, day=31, year=self.search_current_year)
                        )
                    ):
                        series: EpisodesModel
                        _series.add(series.SeriesId)
                        self.db_update_single_series(db_entry=series)
                    for series in self.model_arr_file.select().where(
                        self.model_arr_file.SeriesId.in_(_series)
                    ):
                        self.db_update_single_series(db_entry=series)
                else:
                    for series in self.model_arr_series_file.select().order_by(
                        self.model_arr_series_file.Added.desc()
                    ):

                        self.db_update_single_series(db_entry=series, series=True)
            elif self.type == "radarr":
                for series in (
                    self.model_arr_file.select()
                    .where(self.model_arr_file.Year == self.search_current_year)
                    .order_by(self.model_arr_file.Added.desc())
                ):
                    self.db_update_single_series(db_entry=series)
        self.logger.trace(f"Finished updating database")

    def db_update_single_series(
        self,
        db_entry: EpisodesModel | SeriesModel | MoviesModel = None,
        request: bool = False,
        series: bool = False,
    ):
        if self.search_missing is False:
            return
        try:
            searched = False
            if self.type == "sonarr":
                if not series:
                    db_entry: EpisodesModel
                    QualityUnmet = False
                    if self.quality_unmet_search:
                        QualityUnmet = self.client.get_episode_file(db_entry.Id).get(
                            "qualityCutoffNotMet", False
                        )
                    if db_entry.EpisodeFileId != 0 and not QualityUnmet:
                        searched = True
                        self.model_queue.update(Completed=True).where(
                            self.model_queue.EntryId == db_entry.Id
                        ).execute()
                    EntryId = db_entry.Id
                    metadata = self.client.get_episode_by_episode_id(EntryId)
                    SeriesTitle = metadata.get("series", {}).get("title")
                    SeasonNumber = db_entry.SeasonNumber
                    Title = db_entry.Title
                    SeriesId = db_entry.SeriesId
                    EpisodeFileId = db_entry.EpisodeFileId
                    EpisodeNumber = db_entry.EpisodeNumber
                    AbsoluteEpisodeNumber = db_entry.AbsoluteEpisodeNumber
                    SceneAbsoluteEpisodeNumber = db_entry.SceneAbsoluteEpisodeNumber
                    LastSearchTime = db_entry.LastSearchTime
                    AirDateUtc = db_entry.AirDateUtc
                    Monitored = db_entry.Monitored
                    searched = searched
                    QualityMet = db_entry.EpisodeFileId != 0 and not QualityUnmet

                    if self.quality_unmet_search and QualityMet:
                        self.logger.trace(
                            "Quality Met | %s | S%02dE%03d",
                            SeriesTitle,
                            SeasonNumber,
                            EpisodeNumber,
                        )

                    self.logger.trace(
                        "Updating database entry | %s | S%02dE%03d",
                        SeriesTitle,
                        SeasonNumber,
                        EpisodeNumber,
                    )
                    to_update = {
                        self.model_file.Monitored: Monitored,
                        self.model_file.Title: Title,
                        self.model_file.AirDateUtc: AirDateUtc,
                        self.model_file.LastSearchTime: LastSearchTime,
                        self.model_file.SceneAbsoluteEpisodeNumber: SceneAbsoluteEpisodeNumber,
                        self.model_file.AbsoluteEpisodeNumber: AbsoluteEpisodeNumber,
                        self.model_file.EpisodeNumber: EpisodeNumber,
                        self.model_file.EpisodeFileId: EpisodeFileId,
                        self.model_file.SeriesId: SeriesId,
                        self.model_file.SeriesTitle: SeriesTitle,
                        self.model_file.SeasonNumber: SeasonNumber,
                        self.model_file.QualityMet: QualityMet,
                    }
                    if searched:
                        to_update[self.model_file.Searched] = searched

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
                        LastSearchTime=LastSearchTime,
                        AirDateUtc=AirDateUtc,
                        Monitored=Monitored,
                        SeriesTitle=SeriesTitle,
                        SeasonNumber=SeasonNumber,
                        Searched=searched,
                        IsRequest=request,
                        QualityMet=QualityMet,
                    ).on_conflict(
                        conflict_target=[self.model_file.EntryId],
                        update=to_update,
                    )
                else:
                    db_entry: SeriesModel
                    EntryId = db_entry.Id
                    metadata = self.client.get_series(id_=EntryId)
                    episode_count = metadata.get("episodeCount", -2)
                    searched = episode_count == metadata.get("episodeFileCount", -1)
                    if episode_count == 0:
                        searched = True
                    Title = metadata.get("title")
                    Monitored = db_entry.Monitored
                    self.logger.trace(
                        "Updating database entry | %s",
                        Title,
                    )
                    to_update = {
                        self.series_file_model.Monitored: Monitored,
                        self.series_file_model.Title: Title,
                    }
                    if searched:
                        to_update[self.series_file_model.Searched] = searched

                    db_commands = self.series_file_model.insert(
                        EntryId=EntryId, Title=Title, Searched=searched, Monitored=Monitored
                    ).on_conflict(
                        conflict_target=[self.series_file_model.EntryId],
                        update=to_update,
                    )

            elif self.type == "radarr":
                db_entry: MoviesModel
                searched = False
                QualityUnmet = False
                if self.quality_unmet_search:
                    QualityUnmet = any(
                        i["qualityCutoffNotMet"]
                        for i in self.client.get_movie_files_by_movie_id(db_entry.Id)
                        if "qualityCutoffNotMet" in i
                    )
                if db_entry.MovieFileId != 0 and not QualityUnmet:
                    searched = True
                    self.model_queue.update(Completed=True).where(
                        self.model_queue.EntryId == db_entry.Id
                    ).execute()

                title = db_entry.Title
                monitored = db_entry.Monitored
                tmdbId = db_entry.TmdbId
                year = db_entry.Year
                EntryId = db_entry.Id
                MovieFileId = db_entry.MovieFileId

                QualityMet = db_entry.MovieFileId != 0 and not QualityUnmet

                self.logger.trace("Updating database entry | %s (%s)", title, tmdbId)
                to_update = {
                    self.model_file.MovieFileId: MovieFileId,
                    self.model_file.Monitored: monitored,
                    self.model_file.QualityMet: QualityMet,
                }
                if searched:
                    to_update[self.model_file.Searched] = searched
                if request:
                    to_update[self.model_file.IsRequest] = request
                db_commands = self.model_file.insert(
                    Title=title,
                    Monitored=monitored,
                    TmdbId=tmdbId,
                    Year=year,
                    EntryId=EntryId,
                    Searched=searched,
                    MovieFileId=MovieFileId,
                    IsRequest=request,
                    QualityMet=QualityMet,
                ).on_conflict(
                    conflict_target=[self.model_file.EntryId],
                    update=to_update,
                )
            db_commands.execute()

        except Exception as e:
            self.logger.error(e, exc_info=sys.exc_info())

    def delete_from_queue(self, id_, remove_from_client=True, blacklist=True):
        params = {
            "removeFromClient": remove_from_client,
            "blocklist": blacklist,
            "blacklist": blacklist,
        }
        path = f"/api/v3/queue/{id_}"
        res = self.client.request_del(path, params=params)
        return res

    def file_is_probeable(self, file: pathlib.Path) -> bool:
        if not self.manager.ffprobe_available:
            return True  # ffprobe is not found, so we say every file is acceptable.
        try:
            if file in self.files_probed:
                self.logger.trace("Probeable: File has already been probed: %s", file)
                return True
            if file.is_dir():
                self.logger.trace("Not Probeable: File is a directory: %s", file)
                return False
            output = ffmpeg.probe(
                str(file.absolute()), cmd=self.manager.qbit_manager.ffprobe_downloader.probe_path
            )
            if not output:
                self.logger.trace("Not Probeable: Probe returned no output: %s", file)
                return False
            self.files_probed.add(file)
            return True
        except ffmpeg.Error as e:
            error = e.stderr.decode()
            self.logger.trace(
                "Not Probeable: Probe returned an error: %s:\n%s",
                file,
                e.stderr,
                exc_info=sys.exc_info(),
            )
            if "Invalid data found when processing input" in error:
                return False
            return False

    def folder_cleanup(self) -> None:
        if self.auto_delete is False:
            return
        self._update_bad_queue_items()
        if self.needs_cleanup is False:
            return
        folder = self.completed_folder
        self.logger.debug("Folder Cleanup: %s", folder)
        for file in absolute_file_paths(folder):
            if file.name in {"desktop.ini", ".DS_Store"}:
                continue
            elif file.suffix.lower() == ".parts":
                continue
            if not file.exists():
                continue
            if file.is_dir():
                self.logger.trace("Folder Cleanup: File is a folder: %s", file)
                continue
            if file.suffix.lower() in self.file_extension_allowlist:
                self.logger.trace("Folder Cleanup: File has an allowed extension: %s", file)
                if self.file_is_probeable(file):
                    self.logger.trace("Folder Cleanup: File is a valid media type: %s", file)
                    continue
            try:
                file.unlink(missing_ok=True)
                self.logger.debug("File removed: %s", file)
            except PermissionError:
                self.logger.debug("File in use: Failed to remove file: %s", file)
        for file in self.files_to_explicitly_delete:
            if not file.exists():
                continue
            try:
                file.unlink(missing_ok=True)
                self.logger.debug("File removed: File was marked as failed by Arr | %s", file)
            except PermissionError:
                self.logger.debug(
                    "File in use: Failed to remove file: File was marked as failed by Ar | %s",
                    file,
                )

        self.files_to_explicitly_delete = iter([])
        self._remove_empty_folders()
        self.needs_cleanup = False

    def maybe_do_search(
        self,
        file_model: EpisodeFilesModel | MoviesFilesModel | SeriesFilesModel,
        request: bool = False,
        todays: bool = False,
        bypass_limit: bool = False,
        series_search: bool = False,
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
                    queue = (
                        self.model_queue.select()
                        .where(self.model_queue.EntryId == file_model.EntryId)
                        .execute()
                    )
                else:
                    queue = False
                if queue:
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
                    file_model.Searched = True
                    file_model.save()
                    return True
                active_commands = self.arr_db_query_commands_count()
                self.logger.debug(
                    "%s%s active search commands",
                    request_tag,
                    active_commands,
                )
                if not bypass_limit and active_commands >= self.search_command_limit:
                    self.logger.trace(
                        "%sIdle: Too many commands in queue: %s | "
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
                    return False
                self.persistent_queue.insert(
                    EntryId=file_model.SeriesId
                ).on_conflict_ignore().execute()
                self.model_queue.insert(
                    Completed=False,
                    EntryId=file_model.EntryId,
                ).on_conflict_replace().execute()
                if file_model.EntryId not in self.queue_file_ids:
                    self.client.post_command("EpisodeSearch", episodeIds=[file_model.EntryId])
                file_model.Searched = True
                file_model.save()
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
                self.logger.debug(
                    "%s%s active search commands",
                    request_tag,
                    active_commands,
                )
                if not bypass_limit and active_commands >= self.search_command_limit:
                    self.logger.trace(
                        "%sIdle: Too many commands in queue: %s | %[id=%s]",
                        request_tag,
                        file_model.Title,
                        file_model.EntryId,
                    )
                    return False
                self.persistent_queue.insert(
                    EntryId=file_model.EntryId
                ).on_conflict_ignore().execute()
                self.model_queue.insert(
                    Completed=False,
                    EntryId=file_model.EntryId,
                ).on_conflict_replace().execute()
                self.client.post_command("SeriesSearch", seriesId=file_model.EntryId)
                file_model.Searched = True
                file_model.save()
                self.logger.hnotice(
                    "%sSearching for: %s | [id=%s]",
                    request_tag,
                    file_model.Title,
                    file_model.EntryId,
                )

                return True
        elif self.type == "radarr":
            if not (request or todays):
                queue = (
                    self.model_queue.select()
                    .where(self.model_queue.EntryId == file_model.EntryId)
                    .execute()
                )
            else:
                queue = False
            if queue:
                self.logger.debug(
                    "%sSkipping: Already Searched: %s (%s) [tmdbId=%s|id=%s]",
                    request_tag,
                    file_model.Title,
                    file_model.Year,
                    file_model.TmdbId,
                    file_model.EntryId,
                )
                file_model.Searched = True
                file_model.save()
                return True
            active_commands = self.arr_db_query_commands_count()
            self.logger.debug(
                "%s%s active search commands",
                request_tag,
                active_commands,
            )
            if not bypass_limit and active_commands >= self.search_command_limit:
                self.logger.trace(
                    "%sSkipping: Too many in queue: %s (%s) [tmdbId=%s|id=%s]",
                    request_tag,
                    file_model.Title,
                    file_model.Year,
                    file_model.TmdbId,
                    file_model.EntryId,
                )
                return False
            self.persistent_queue.insert(EntryId=file_model.EntryId).on_conflict_ignore().execute()

            self.model_queue.insert(
                Completed=False,
                EntryId=file_model.EntryId,
            ).on_conflict_replace().execute()
            if file_model.EntryId not in self.queue_file_ids:
                self.client.post_command("MoviesSearch", movieIds=[file_model.EntryId])
            file_model.Searched = True
            file_model.save()
            self.logger.hnotice(
                "%sSkipping: Searching for: %s (%s) [tmdbId=%s|id=%s]",
                request_tag,
                file_model.Title,
                file_model.Year,
                file_model.TmdbId,
                file_model.EntryId,
            )
            return True

    def post_command(self, name, **kwargs):
        data = {
            "name": name,
            **kwargs,
        }
        path = "/api/v3/command"
        res = self.client.request_post(path, data=data)
        return res

    def process(self):
        self._process_resume()
        self._process_paused()
        self._process_errored()
        self._process_file_priority()
        self._process_imports()
        self._process_failed()
        self.folder_cleanup()

    def process_entries(self, hashes: set[str]) -> tuple[list[tuple[int, str]], set[str]]:
        payload = [
            (_id, h.upper()) for h in hashes if (_id := self.cache.get(h.upper())) is not None
        ]
        hashes = {h for h in hashes if (_id := self.cache.get(h.upper())) is not None}

        return payload, hashes

    def process_torrents(self):
        if has_internet() is False:
            self.manager.qbit_manager.should_delay_torrent_scan = True
            raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="internet")
        if self.manager.qbit_manager.should_delay_torrent_scan:
            raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="delay")
        try:
            try:
                self.api_calls()
                self.refresh_download_queue()
                torrents = self.manager.qbit_manager.client.torrents.info.all(
                    category=self.category, sort="added_on", reverse=False
                )
                for torrent in torrents:
                    with contextlib.suppress(qbittorrentapi.exceptions.NotFound404Error):
                        self._process_single_torrent(torrent)
                self.process()
            except NoConnectionrException as e:
                self.logger.error(e.message)
            except KeyboardInterrupt:
                self.logger.hnotice("Detected Ctrl+C - Terminating process")
                sys.exit(0)
            except Exception as e:
                self.logger.error(e, exc_info=sys.exc_info())
        except KeyboardInterrupt:
            self.logger.hnotice("Detected Ctrl+C - Terminating process")
            sys.exit(0)

    def _process_single_torrent_failed_cat(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.notice(
            "Deleting manually failed torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
            datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
            datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        if torrent.state_enum == TorrentStates.QUEUED_DOWNLOAD:
            self.recently_queue[torrent.hash] = time.time()

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
            datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
                datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
        else:
            self.pause.add(torrent.hash)
            self.skip_blacklist.add(torrent.hash)
            self.logger.trace(
                "Pausing torrent: Queued Upload | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
            self.recently_queue.get(torrent.hash, torrent.added_on)
            < time.time() - self.ignore_torrents_younger_than
        ):
            self.logger.info(
                "Deleting Stale torrent: %s | "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                extra,
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
                datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
                datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
                datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
            return

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
            datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
            datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )

    def _process_single_torrent_errored(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.trace(
            "Rechecking Erroed torrent: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
                datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
        else:
            self.logger.info(
                "Pausing Completed torrent: "
                "[Progress: %s%%][Added On: %s]"
                "[Availability: %s%%][Time Left: %s]"
                "[Last active: %s] "
                "| [%s] | %s (%s)",
                round(torrent.progress * 100, 2),
                datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                round(torrent.availability * 100, 2),
                timedelta(seconds=torrent.eta),
                datetime.fromtimestamp(torrent.last_activity),
                torrent.state_enum,
                torrent.name,
                torrent.hash,
            )
            self.pause.add(torrent.hash)
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
            datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            datetime.fromtimestamp(torrent.last_activity),
            torrent.state_enum,
            torrent.name,
            torrent.hash,
        )
        # We do not want to blacklist these!!
        self.skip_blacklist.add(torrent.hash)

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
                datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
                datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
            datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
            datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
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
            file_path = pathlib.Path(file.name)
            # Acknowledge files that already been marked as "Don't download"
            if file.priority == 0:
                total -= 1
                continue
            # A folder within the folder tree matched the terms
            # in FolderExclusionRegex, mark it for exclusion.
            if any(
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
            elif (
                match := self.file_name_exclusion_regex_re.search(file_path.name)
            ) and match.group():
                self.logger.debug(
                    "Removing File: Not allowed | Name: %s  | %s (%s) | %s ",
                    match.group(),
                    torrent.name,
                    torrent.hash,
                    file.name,
                )
                _remove_files.add(file.id)
                total -= 1
            elif file_path.suffix.lower() not in self.file_extension_allowlist:
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
                    datetime.fromtimestamp(
                        self.recently_queue.get(torrent.hash, torrent.added_on)
                    ),
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

    def _process_single_torrent_unprocessed(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.trace(
            "Skipping torrent: Unresolved state: "
            "[Progress: %s%%][Added On: %s]"
            "[Availability: %s%%][Time Left: %s]"
            "[Last active: %s] "
            "| [%s] | %s (%s)",
            round(torrent.progress * 100, 2),
            datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
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
        current_trackers = {i.url for i in torrent.trackers}
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
            if (i.get("URI") in monitored_trackers) and not i.get("RemoveIfExists") is True
        ]
        _list_of_tags = [i.get("AddTags", []) for i in new_list if i.get("URI") not in removed]
        if new_list:
            max_item = max(new_list, key=self.__return_max)
        else:
            max_item = {}
        return max_item, set(itertools.chain.from_iterable(_list_of_tags))

    def _get_torrent_limit_meta(self, torrent: qbittorrentapi.TorrentDictionary):
        _, monitored_trackers = self._get_torrent_important_trackers(torrent)
        most_important_tracker, unique_tags = self._get_most_important_tracker_and_tags(
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
            else None,
            "seeding_time_limit": r
            if (
                r := most_important_tracker.get(
                    "MaxSeedingTime", self.seeding_mode_global_max_seeding_time
                )
            )
            > 0
            else None,
            "dl_limit": r
            if (
                r := most_important_tracker.get(
                    "DownloadRateLimit", self.seeding_mode_global_download_limit
                )
            )
            > 0
            else None,
            "up_limit": r
            if (
                r := most_important_tracker.get(
                    "UploadRateLimit", self.seeding_mode_global_upload_limit
                )
            )
            > 0
            else None,
            "super_seeding": most_important_tracker.get("SuperSeedMode", torrent.super_seeding),
            "max_eta": most_important_tracker.get("MaximumETA", self.maximum_eta),
        }

        data_torrent = {
            "ratio_limit": r if (r := torrent.ratio_limit) > 0 else -1,
            "seeding_time_limit": r if (r := torrent.seeding_time_limit) > 0 else -1,
            "dl_limit": r if (r := torrent.dl_limit) > 0 else -1,
            "up_limit": r if (r := torrent.up_limit) > 0 else -1,
            "super_seeding": torrent.super_seeding,
        }
        return data_settings, data_torrent

    def _should_leave_alone(self, torrent: qbittorrentapi.TorrentDictionary) -> tuple[bool, int]:
        return_value = True
        if torrent.super_seeding or torrent.state_enum == TorrentStates.FORCED_UPLOAD:
            return return_value, -1  # Do not touch super seeding torrents.
        data_settings, data_torrent = self._get_torrent_limit_meta(torrent)
        if torrent.ratio >= data_torrent.get(
            "ratio_limit", -1
        ) or torrent.ratio >= data_settings.get("ratio_limit", -1):
            return_value = False  # Seeding ratio met - Can be cleaned up.
        if torrent.seeding_time >= data_torrent.get(
            "seeding_time_limit", -1
        ) or torrent.seeding_time >= data_settings.get("seeding_time_limit", -1):
            return_value = False  # Seeding time met - Can be cleaned up.
        if return_value is True and "qbitrr-allowed_seeding" not in torrent.tags:
            torrent.add_tags(tags=["qbitrr-allowed_seeding"])
        elif return_value is False and "qbitrr-allowed_seeding" in torrent.tags:
            torrent.remove_tags(tags=["qbitrr-allowed_seeding"])
        return return_value, data_settings.get(
            "max_eta", self.maximum_eta
        )  # Seeding is not complete needs more time

    def _process_single_torrent_trackers(self, torrent: qbittorrentapi.TorrentDictionary):
        if torrent.hash in self.tracker_delay:
            return
        self.tracker_delay.add(torrent.hash)
        _remove_urls = set()
        need_to_be_added, monitored_trackers = self._get_torrent_important_trackers(torrent)
        if need_to_be_added:
            torrent.add_trackers(need_to_be_added)
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
            with contextlib.suppress(qbittorrentapi.exceptions.Conflict409Error):
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

                if any(v is not None for v in data.values()):
                    if any(v is not None for v in data.values()):
                        if data:
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
                if any(v is not None for v in data.values()):
                    if data:
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
                torrent.add_tags(add_tags)

    def _process_single_torrent(self, torrent: qbittorrentapi.TorrentDictionary):
        if torrent.category != RECHECK_CATEGORY:
            self.manager.qbit_manager.cache[torrent.hash] = torrent.category
        self._process_single_torrent_trackers(torrent)
        self.manager.qbit_manager.name_cache[torrent.hash] = torrent.name
        time_now = time.time()
        leave_alone, _tracker_max_eta = self._should_leave_alone(torrent)
        maximum_eta = _tracker_max_eta
        if torrent.category == FAILED_CATEGORY:
            # Bypass everything if manually marked as failed
            self._process_single_torrent_failed_cat(torrent)
        elif torrent.category == RECHECK_CATEGORY:
            # Bypass everything else if manually marked for rechecking
            self._process_single_torrent_recheck_cat(torrent)
        elif self.is_ignored_state(torrent):
            self._process_single_torrent_ignored(torrent)
            return  # Since to torrent is being ignored early exit here
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
            return
        elif torrent.state_enum == TorrentStates.QUEUED_UPLOAD:
            self._process_single_torrent_queued_upload(torrent, leave_alone)
        elif torrent.state_enum in (
            TorrentStates.METADATA_DOWNLOAD,
            TorrentStates.STALLED_DOWNLOAD,
        ):
            self._process_single_torrent_stalled_torrent(torrent, "Stalled State")
        elif (
            torrent.progress >= self.maximum_deletable_percentage
            and self.is_complete_state(torrent) is False
        ) and torrent.hash in self.cleaned_torrents:
            self._process_single_torrent_percentage_threshold(torrent, maximum_eta)
        # Resume monitored downloads which have been paused.
        elif torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD and torrent.amount_left != 0:
            self._process_single_torrent_paused(torrent)
        # Ignore torrents which have been submitted to their respective Arr
        # instance for import.
        elif (
            torrent.hash in self.manager.managed_objects[torrent.category].sent_to_scan_hashes
        ) and torrent.hash in self.cleaned_torrents:
            self._process_single_torrent_already_sent_to_scan(torrent)
            return
        # Some times torrents will error, this causes them to be rechecked so they
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
        # If a torrent is Uploading Pause it, as long as its for being Forced Uploaded.
        elif (
            self.is_uploading_state(torrent)
            and torrent.seeding_time > 1
            and torrent.amount_left == 0
            and torrent.added_on > 0
            and torrent.content_path
            and torrent.amount_left == 0
        ) and torrent.hash in self.cleaned_torrents:
            self._process_single_torrent_uploading(torrent, leave_alone)
        # Mark a torrent for deletion
        elif (
            torrent.state_enum != TorrentStates.PAUSED_DOWNLOAD
            and torrent.state_enum.is_downloading
            and self.recently_queue.get(torrent.hash, torrent.added_on)
            < time_now - self.ignore_torrents_younger_than
            and 0 < maximum_eta < torrent.eta
            and not self.do_not_remove_slow
        ):
            self._process_single_torrent_delete_slow(torrent)
        # Process uncompleted torrents
        elif torrent.state_enum.is_downloading:
            # If a torrent availability hasn't reached 100% or more within the configurable
            # "IgnoreTorrentsYoungerThan" variable, mark it for deletion.
            if (
                self.recently_queue.get(torrent.hash, torrent.added_on)
                < time_now - self.ignore_torrents_younger_than
                and torrent.availability < 1
            ) and torrent.hash in self.cleaned_torrents:
                self._process_single_torrent_stalled_torrent(torrent, "Unavailable")
            else:
                if torrent.hash in self.cleaned_torrents:
                    self._process_single_torrent_already_cleaned_up(torrent)
                    return
                # A downloading torrent is not stalled, parse its contents.
                self._process_single_torrent_process_files(torrent)

        else:
            self._process_single_torrent_unprocessed(torrent)

    def refresh_download_queue(self):
        if self.type == "sonarr":
            self.queue = self.get_queue()
        elif self.type == "radarr":
            self.queue = self.get_queue()
        self.cache = {
            entry["downloadId"]: entry["id"] for entry in self.queue if entry.get("downloadId")
        }
        if self.type == "sonarr":
            self.requeue_cache = defaultdict(set)
            for entry in self.queue:
                if r := entry.get("episodeId"):
                    self.requeue_cache[entry["id"]].add(r)
            self.queue_file_ids = {
                entry["episodeId"] for entry in self.queue if entry.get("episodeId")
            }
        elif self.type == "radarr":
            self.requeue_cache = {
                entry["id"]: entry["movieId"] for entry in self.queue if entry.get("movieId")
            }
            self.queue_file_ids = {
                entry["movieId"] for entry in self.queue if entry.get("movieId")
            }
        self._update_bad_queue_items()

    def get_queue(
        self,
        page=1,
        page_size=10000,
        sort_direction="ascending",
        sort_key="timeLeft",
        messages: bool = True,
    ):
        params = {
            "page": page,
            "pageSize": page_size,
            "sortDirection": sort_direction,
            "sortKey": sort_key,
        }
        if messages:
            path = "/api/v3/queue"
        else:
            path = "/api/queue"
        res = self.client.request_get(path, params=params)
        try:
            res = res.get("records", [])
        except AttributeError:
            pass
        return res

    def _update_bad_queue_items(self):
        _temp = self.get_queue()
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
                    if _m in {
                        "Not a preferred word upgrade for existing episode file(s)",
                        "Not a preferred word upgrade for existing movie file(s)",
                        "Not an upgrade for existing episode file(s)",
                        "Not an upgrade for existing movie file(s)",
                        "Unable to determine if file is a sample",
                    }:  # TODO: Add more error codes
                        _path_filter.add(pathlib.Path(output_path).joinpath(title))
                        e = entry.get("downloadId")
                        self.missing_files_post_delete_blacklist.add(e)
                    elif "No files found are eligible for import in" in _m:
                        if e := entry.get("downloadId"):
                            self.missing_files_post_delete.add(e)

        if len(_path_filter):
            self.needs_cleanup = True
        self.files_to_explicitly_delete = iter(_path_filter.copy())

    def force_grab(self):
        _temp = self.get_queue()
        _temp = filter(
            lambda x: x.get("status") == "delay",
            _temp,
        )
        ids = set()
        for entry in _temp:
            if id_ := entry.get("id"):
                ids.add(id_)
                self.logger.notice("Attempting to force grab: %s =  %s", id_, entry.get("title"))
        if ids:
            with ThreadPoolExecutor(max_workers=16) as executor:
                executor.map(self._force_grab, ids)

    def _force_grab(self, id_):
        try:
            path = f"/api/v3/queue/grab/{id_}"
            res = self.client.request_post(path, data={})
            self.logger.trace("Successful Grab: %s", id_)
            return res
        except Exception:
            self.logger.error("Exception when trying to force grab - %s", id_)

    def register_search_mode(self):
        if self.search_setup_completed:
            return
        if self.search_missing is False:
            self.search_setup_completed = True
            return
        if not self.arr_db_file.exists():
            self.search_missing = False
            return
        else:
            self.arr_db = SqliteDatabase(None)
            self.arr_db.init(f"file:{self.arr_db_file}?mode=ro", uri=True)
            self.arr_db.connect()

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

        db1, db2, db3 = self._get_models()

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

        self.model_file = Files
        self.model_queue = Queue
        self.persistent_queue = PersistingQueue

        db1, db2, db3 = self._get_arr_modes()

        class Files(db1):
            class Meta:
                database = self.arr_db
                if self.type == "sonarr":
                    table_name = "Episodes"
                elif self.type == "radarr":
                    table_name = "Movies"

        class Commands(db2):
            class Meta:
                database = self.arr_db
                table_name = "Commands"

        if db3:

            class Series(db3):
                class Meta:
                    database = self.arr_db
                    table_name = "Series"

            self.model_arr_series_file = Series

        self.model_arr_file = Files
        self.model_arr_command = Commands
        self.search_setup_completed = True

    def run_request_search(self):
        if self.request_search_timer is None or (
            self.request_search_timer > time.time() - self.search_requests_every_x_seconds
        ):
            return None
        self.register_search_mode()
        if not self.search_missing:
            return None
        self.logger.notice("Starting Request search")

        while True:
            try:
                self.db_request_update()
                try:
                    for entry in self.db_get_request_files():
                        while self.maybe_do_search(entry, request=True) is False:
                            time.sleep(30)
                    self.request_search_timer = time.time()
                    return
                except NoConnectionrException as e:
                    self.logger.error(e.message)
                    raise DelayLoopException(length=300, type=e.type)
                except DelayLoopException:
                    raise
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
                        "Forced delay due to temporary issue with environment, sleeping for %s",
                        timedelta(seconds=e.length),
                    )
                time.sleep(e.length)

    def run_search_loop(self) -> NoReturn:
        run_logs(self.logger)
        self.logger.hnotice("Starting missing search for %s", self._name)
        try:
            self.register_search_mode()
            if not self.search_missing:
                return None
            count_start = self.search_current_year
            stopping_year = datetime.now().year if self.search_in_reverse else 1900
            loop_timer = timedelta(minutes=15)
            while True:
                timer = datetime.now(timezone.utc)
                try:
                    self.db_maybe_reset_entry_searched_state()
                    self.db_update()
                    self.run_request_search()
                    self.force_grab()
                    try:
                        for entry, todays, limit_bypass, series_search in self.db_get_files():
                            if timer < (datetime.now(timezone.utc) - loop_timer):
                                self.force_grab()
                                raise RestartLoopException
                            while (
                                self.maybe_do_search(
                                    entry,
                                    todays=todays,
                                    bypass_limit=limit_bypass,
                                    series_search=series_search,
                                )
                                is False
                            ):
                                time.sleep(30)
                        self.search_current_year += self._delta
                        if self.search_in_reverse:
                            if self.search_current_year > stopping_year:
                                self.search_current_year = copy(count_start)
                                self.loop_completed = True
                        else:
                            if self.search_current_year < stopping_year:
                                self.search_current_year = copy(count_start)
                                self.loop_completed = True
                    except RestartLoopException:
                        self.logger.debug("Loop timer elapsed, restarting it.")
                    except NoConnectionrException as e:
                        self.logger.error(e.message)
                        self.manager.qbit_manager.should_delay_torrent_scan = True
                        raise DelayLoopException(length=300, type=e.type)
                    except DelayLoopException:
                        raise
                    except ValueError:
                        self.logger.debug("Loop completed, restarting it.")
                        self.loop_completed = True
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
                                "Could not connect to %s" % self.uri, type="arr"
                            )
                        self.process_torrents()
                    except NoConnectionrException as e:
                        self.logger.error(e.message)
                        self.manager.qbit_manager.should_delay_torrent_scan = True
                        raise DelayLoopException(length=300, type=e.type)
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
        self.process_torrent_loop = pathos.helpers.mp.Process(
            target=self.run_torrent_loop, daemon=True
        )
        self.manager.qbit_manager.child_processes.append(self.process_torrent_loop)
        _temp.append(self.process_torrent_loop)

        return len(_temp), _temp


class PlaceHolderArr(Arr):
    def __init__(
        self,
        name: str,
        manager: ArrManager,
    ):
        if name in manager.groups:
            raise OSError("Group '{name}' has already been registered.")
        self._name = name.title()
        self.category = name
        self.manager = manager
        self.queue = []
        self.cache = {}
        self.requeue_cache = {}
        self.recently_queue = {}
        self.sent_to_scan = set()
        self.sent_to_scan_hashes = set()
        self.files_probed = set()
        self.import_torrents = []
        self.change_priority = dict()
        self.recheck = set()
        self.pause = set()
        self.skip_blacklist = set()
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
        run_logs(self.logger)
        self.search_missing = False
        self.session = None
        self.logger.hnotice("Starting %s monitor", self._name)

    def _process_errored(self):
        # Recheck all torrents marked for rechecking.
        if self.recheck:
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
        to_delete_all = self.delete.union(self.skip_blacklist)
        skip_blacklist = {i.upper() for i in self.skip_blacklist}
        if to_delete_all:
            for arr in self.manager.managed_objects.values():
                payload, hashes = arr.process_entries(to_delete_all)
                if payload:
                    for entry, hash_ in payload:
                        if hash_ in arr.cache:
                            arr._process_failed_individual(
                                hash_=hash_, entry=entry, skip_blacklist=skip_blacklist
                            )

            # Remove all bad torrents from the Client.
            self.manager.qbit.torrents_delete(hashes=to_delete_all, delete_files=True)
            for h in to_delete_all:
                if h in self.manager.qbit_manager.name_cache:
                    del self.manager.qbit_manager.name_cache[h]
                if h in self.manager.qbit_manager.cache:
                    del self.manager.qbit_manager.cache[h]
        self.skip_blacklist.clear()
        self.delete.clear()

    def process(self):
        self._process_errored()
        self._process_failed()

    def process_torrents(self):
        if has_internet() is False:
            self.manager.qbit_manager.should_delay_torrent_scan = True
            raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="internet")
        if self.manager.qbit_manager.should_delay_torrent_scan:
            raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, type="delay")
        try:
            try:
                torrents = self.manager.qbit_manager.client.torrents.info.all(
                    category=self.category, sort="added_on", reverse=False
                )
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
            except KeyboardInterrupt:
                self.logger.hnotice("Detected Ctrl+C - Terminating process")
                sys.exit(0)
            except Exception as e:
                self.logger.error(e, exc_info=sys.exc_info())
        except KeyboardInterrupt:
            self.logger.hnotice("Detected Ctrl+C - Terminating process")
            sys.exit(0)

    def run_search_loop(self):
        return


class ArrManager:
    def __init__(self, qbitmanager: qBitManager):
        self.groups: set[str] = set()
        self.uris: set[str] = set()
        self.special_categories: set[str] = {FAILED_CATEGORY, RECHECK_CATEGORY}
        self.category_allowlist: set[str] = self.special_categories.copy()
        self.completed_folders: set[pathlib.Path] = set()
        self.managed_objects: dict[str, Arr] = {}
        self.qbit: qbittorrentapi.Client = qbitmanager.client
        self.qbit_manager: qBitManager = qbitmanager
        self.ffprobe_available: bool = self.qbit_manager.ffprobe_downloader.probe_path.exists()
        self.logger = logging.getLogger(
            "qBitrr.ArrManager",
        )
        run_logs(self.logger)
        if not self.ffprobe_available:
            self.logger.error(
                "'%s' was not found, disabling all functionality dependant on it",
                self.qbit_manager.ffprobe_downloader.probe_path,
            )

    def build_arr_instances(self):
        for key in CONFIG.sections():
            if search := re.match("(rad|son)arr.*", key, re.IGNORECASE):
                name = search.group(0)
                match = search.group(1)
                if match.lower() == "son":
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
                except ValueError as e:
                    self.logger.exception(e)
                except SkipException:
                    continue
                except OSError as e:
                    self.logger.exception(e)
        for cat in self.special_categories:
            managed_object = PlaceHolderArr(cat, self)
            self.managed_objects[cat] = managed_object
        return self
