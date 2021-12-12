from __future__ import annotations

import contextlib
import pathlib
import re
import shutil
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from configparser import NoOptionError, NoSectionError
from copy import copy
from datetime import datetime, timedelta, timezone
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    NoReturn,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

import ffmpeg
import logbook
import pathos
import qbittorrentapi
import requests
from peewee import JOIN, SqliteDatabase
from pyarr import RadarrAPI, SonarrAPI
from qbittorrentapi import TorrentDictionary, TorrentStates

from .arr_tables import CommandsModel, EpisodesModel, MoviesModel, SeriesModel
from .config import (
    APPDATA_FOLDER,
    COMPLETED_DOWNLOAD_FOLDER,
    CONFIG,
    FAILED_CATEGORY,
    LOOP_SLEEP_TIMER,
    NO_INTERNET_SLEEP_TIMER,
    RECHECK_CATEGORY,
)
from .errors import (
    DelayLoopException,
    NoConnectionrException,
    RestartLoopException,
    SkipException,
    UnhandledError,
)
from .tables import (
    EpisodeFilesModel,
    EpisodeQueueModel,
    FilesQueued,
    MovieQueueModel,
    MoviesFilesModel,
    SeriesFilesModel,
)
from .utils import ExpiringSet, absolute_file_paths, has_internet, validate_and_return_torrent_file

if TYPE_CHECKING:
    from .main import qBitManager

logger = logbook.Logger("ArrManager")


class Arr:
    def __init__(
        self,
        name: str,
        manager: ArrManager,
        client_cls: Type[Callable | RadarrAPI | SonarrAPI],
    ):
        if name in manager.groups:
            raise EnvironmentError("Group '{name}' has already been registered.")
        self._name = name
        self.managed = CONFIG.getboolean(name, "Managed")
        if not self.managed:
            raise SkipException
        self.uri = CONFIG.get(name, "URI")
        if self.uri in manager.uris:
            raise EnvironmentError(
                "Group '{name}' is trying to manage Arr instance: '{uri}' which has already been registered."
            )

        self.category = CONFIG.get(name, "Category", fallback=self._name)
        self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(self.category)
        if not self.completed_folder.exists():
            raise EnvironmentError(
                f"{self._name} completed folder is a requirement, The specified folder does not exist '{self.completed_folder}'"
            )
        self.apikey = CONFIG.get(name, "APIKey")

        self.re_search = CONFIG.getboolean(name, "Research")
        self.import_mode = CONFIG.get(name, "importMode", fallback="Move")
        self.refresh_downloads_timer = CONFIG.getint(name, "RefreshDownloadsTimer", fallback=1)
        self.rss_sync_timer = CONFIG.getint(name, "RssSyncTimer", fallback=15)

        self.case_sensitive_matches = CONFIG.getboolean(name, "CaseSensitiveMatches")
        self.folder_exclusion_regex = CONFIG.getlist(name, "FolderExclusionRegex")
        self.file_name_exclusion_regex = CONFIG.getlist(name, "FileNameExclusionRegex")
        self.file_extension_allowlist = CONFIG.getlist(name, "FileExtensionAllowlist")
        self.auto_delete = CONFIG.getboolean(name, "AutoDelete", fallback=False)
        self.do_upgrade_search = CONFIG.getboolean(name, "DoUpgradeSearch", fallback=False)
        self.quality_unmet_search = CONFIG.getboolean(name, "QualityUnmetSearch", fallback=False)
        self.ignore_torrents_younger_than = CONFIG.getint(
            name, "IgnoreTorrentsYoungerThan", fallback=600
        )
        self.maximum_eta = CONFIG.getint(name, "MaximumETA", fallback=86400)
        self.maximum_deletable_percentage = CONFIG.getfloat(
            name, "MaximumDeletablePercentage", fallback=0.95
        )

        self.search_missing = CONFIG.getboolean(name, "SearchMissing")
        self.search_specials = CONFIG.getboolean(name, "AlsoSearchSpecials")
        self.search_by_year = CONFIG.getboolean(name, "SearchByYear")
        self.search_in_reverse = CONFIG.getboolean(name, "SearchInReverse")

        self.search_starting_year = CONFIG.getyear(name, "StartYear")
        self.search_ending_year = CONFIG.getyear(name, "LastYear")
        self.search_command_limit = CONFIG.getint(name, "SearchLimit", fallback=5)
        self.prioritize_todays_release = CONFIG.getboolean(
            name, "PrioritizeTodaysReleases", fallback=False
        )

        self.donotremoveslow = CONFIG.getboolean(name, "DoNotRemoveSlow", fallback=False)

        if self.search_in_reverse:
            self.search_current_year = self.search_ending_year
            self._delta = 1
        else:
            self.search_current_year = self.search_starting_year
            self._delta = -1

        self.arr_db_file = pathlib.Path(CONFIG.get(name, "DatabaseFile"))
        self._app_data_folder = APPDATA_FOLDER
        self.search_db_file = self._app_data_folder.joinpath(f"{self._name}.db")

        self.ombi_search_requests = CONFIG.getboolean(name, "SearchOmbiRequests")
        self.overseerr_requests = CONFIG.getboolean(name, "SearchOverseerrRequests")
        self.series_search = CONFIG.getboolean(name, "SearchBySeries", fallback=False)
        self.ombi_uri = CONFIG.get(name, "OmbiURI")
        self.overseerr_uri = CONFIG.get(name, "OverseerrURI")

        self.ombi_api_key = CONFIG.get(name, "OmbiAPIKey")
        self.overseerr_api_key = CONFIG.get(name, "OverseerrAPIKey")

        self.ombi_approved_only = CONFIG.getboolean(name, "ApprovedOnly")
        self.search_requests_every_x_seconds = CONFIG.getint(name, "SearchRequestsEvery")
        self._temp_overseer_request_cache: Dict[str, Set[Union[int, str]]] = defaultdict(set)
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

        self.manager = manager
        if self.rss_sync_timer > 0:
            self.rss_sync_timer_last_checked = datetime(1970, 1, 1)
        else:
            self.rss_sync_timer_last_checked = None
        if self.refresh_downloads_timer > 0:
            self.refresh_downloads_timer_last_checked = datetime(1970, 1, 1)
        else:
            self.refresh_downloads_timer_last_checked = None

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

        self.session = requests.Session()
        self.cleaned_torrents = set()

        self.manager.completed_folders.add(self.completed_folder)
        self.manager.category_allowlist.add(self.category)
        self.logger = logbook.Logger(self._name)
        self.logger.debug(
            "{group} Config: "
            "Managed: {managed}, "
            "Re-search: {search}, "
            "ImportMode: {import_mode}, "
            "Category: {category}, "
            "URI: {uri}, "
            "API Key: {apikey}, "
            "RefreshDownloadsTimer={refresh_downloads_timer}, "
            "RssSyncTimer={rss_sync_timer}",
            group=self._name,
            import_mode=self.import_mode,
            managed=self.managed,
            search=self.re_search,
            category=self.category,
            uri=self.uri,
            apikey=self.apikey,
            refresh_downloads_timer=self.refresh_downloads_timer,
            rss_sync_timer=self.rss_sync_timer,
        )
        self.logger.info(
            "Script Config:  CaseSensitiveMatches={CaseSensitiveMatches}",
            CaseSensitiveMatches=self.case_sensitive_matches,
        )
        self.logger.info(
            "Script Config:  FolderExclusionRegex={FolderExclusionRegex}",
            FolderExclusionRegex=self.folder_exclusion_regex,
        )
        self.logger.info(
            "Script Config:  FileNameExclusionRegex={FileNameExclusionRegex}",
            FileNameExclusionRegex=self.file_name_exclusion_regex,
        )
        self.logger.info(
            "Script Config:  FileExtensionAllowlist={FileExtensionAllowlist}",
            FileExtensionAllowlist=self.file_extension_allowlist,
        )
        self.logger.info("Script Config:  AutoDelete={AutoDelete}", AutoDelete=self.auto_delete)

        self.logger.info(
            "Script Config:  IgnoreTorrentsYoungerThan={IgnoreTorrentsYoungerThan}",
            IgnoreTorrentsYoungerThan=self.ignore_torrents_younger_than,
        )
        self.logger.info("Script Config:  MaximumETA={MaximumETA}", MaximumETA=self.maximum_eta)
        self.logger.info(
            "Script Config:  MaximumDeletablePercentage={MaximumDeletablePercentage}",
            MaximumDeletablePercentage=self.maximum_deletable_percentage,
        )
        self.logger.info(
            "Script Config:  DoUpgradeSearch={DoUpgradeSearch}",
            DoUpgradeSearch=self.do_upgrade_search,
        )
        self.logger.info(
            "Script Config:  PrioritizeTodaysReleases={PrioritizeTodaysReleases}",
            PrioritizeTodaysReleases=self.prioritize_todays_release,
        )
        self.logger.info(
            "Script Config:  SearchBySeries={SearchBySeries}",
            SearchBySeries=self.series_search,
        )
        self.logger.info(
            "Script Config:  SearchOverseerrRequests={SearchOverseerrRequests}",
            SearchOverseerrRequests=self.overseerr_requests,
        )
        if self.overseerr_requests:
            self.logger.info(
                "Script Config:  OverseerrURI={OverseerrURI}",
                OverseerrURI=self.overseerr_uri,
            )
            self.logger.debug(
                "Script Config:  OverseerrAPIKey={OverseerrAPIKey}",
                OverseerrAPIKey=self.overseerr_api_key,
            )
        self.logger.info(
            "Script Config:  SearchOmbiRequests={SearchOmbiRequests}",
            SearchOmbiRequests=self.ombi_search_requests,
        )
        if self.ombi_search_requests:
            self.logger.info(
                "Script Config:  OmbiURI={OmbiURI}",
                OmbiURI=self.ombi_uri,
            )
            self.logger.debug(
                "Script Config:  OmbiAPIKey={OmbiAPIKey}",
                OmbiAPIKey=self.ombi_api_key,
            )
            self.logger.info(
                "Script Config:  ApprovedOnly={ApprovedOnly}",
                ApprovedOnly=self.ombi_approved_only,
            )
        if self.ombi_search_requests or self.overseerr_requests:
            self.logger.info(
                "Script Config:  SearchRequestsEvery={SearchRequestsEvery}",
                SearchRequestsEvery=self.search_requests_every_x_seconds,
            )

        if self.search_missing:
            self.logger.info(
                "Script Config:  SearchMissing={SearchMissing}",
                SearchMissing=self.search_missing,
            )
            self.logger.info(
                "Script Config:  AlsoSearchSpecials={AlsoSearchSpecials}",
                AlsoSearchSpecials=self.search_specials,
            )
            self.logger.info(
                "Script Config:  SearchByYear={SearchByYear}",
                SearchByYear=self.search_by_year,
            )
            self.logger.info(
                "Script Config:  SearchInReverse={SearchInReverse}",
                SearchInReverse=self.search_in_reverse,
            )
            self.logger.info(
                "Script Config:  StartYear={StartYear}",
                StartYear=self.search_starting_year,
            )
            self.logger.info(
                "Script Config:  LastYear={LastYear}",
                LastYear=self.search_ending_year,
            )
            self.logger.info(
                "Script Config:  CommandLimit={search_command_limit}",
                search_command_limit=self.search_command_limit,
            )
            self.logger.info(
                "Script Config:  DatabaseFile={DatabaseFile}",
                DatabaseFile=self.arr_db_file,
            )
        self.search_setup_completed = False
        self.model_arr_file: Union[EpisodesModel, MoviesModel] = None
        self.model_arr_series_file: SeriesModel = None

        self.model_arr_command: CommandsModel = None
        self.model_file: Union[EpisodeFilesModel, MoviesFilesModel] = None
        self.series_file_model: SeriesFilesModel = None
        self.model_queue: Union[EpisodeQueueModel, MovieQueueModel] = None
        self.persistent_queue: FilesQueued = None

    @property
    def is_alive(self) -> bool:
        try:
            if self.session is None:
                return True
            req = self.session.get(f"{self.uri}/api/v3/system/status", timeout=2)
            req.raise_for_status()
            self.logger.trace("Successfully connected to {url}", url=self.uri)
            return True
        except requests.HTTPError:
            return True
        except requests.RequestException:
            self.logger.warning("Could not connect to {url}", url=self.uri)
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
    ) -> Tuple[
        Union[Type[EpisodesModel], Type[MoviesModel]],
        Type[CommandsModel],
        Union[Type[SeriesModel], None],
    ]:
        if self.type == "sonarr":
            return EpisodesModel, CommandsModel, SeriesModel
        elif self.type == "radarr":
            return MoviesModel, CommandsModel, None

    def _get_models(
        self,
    ) -> Tuple[Type[EpisodeFilesModel], Type[EpisodeQueueModel], Optional[Type[SeriesFilesModel]]]:
        if self.type == "sonarr":
            if self.series_search:
                return EpisodeFilesModel, EpisodeQueueModel, SeriesFilesModel
            return EpisodeFilesModel, EpisodeQueueModel, None
        elif self.type == "radarr":
            return MoviesFilesModel, MovieQueueModel, None
        else:
            raise UnhandledError("Well you shouldn't have reached here, Arr.type=%s" % self.type)

    def _get_oversee_requests_all(self) -> Dict[str, Set]:
        try:
            data = defaultdict(set)
            response = self.session.get(
                url=f"{self.overseerr_uri}/api/v1/request?take=100&skip=0&sort=added&filter=unavailable",
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

    def _get_ombi_requests(self) -> List[Dict]:
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

    def _process_ombi_requests(self) -> Dict[str, Set[str, int]]:
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
            self.logger.debug("Pausing {count} completed torrents", count=len(self.pause))
            for i in self.pause:
                self.logger.debug(
                    "Pausing {name} ({hash})",
                    hash=i,
                    name=self.manager.qbit_manager.name_cache.get(i),
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
                        "Missing Torrent: [{torrent.state_enum}] {torrent.name} ({torrent.hash}) - "
                        "File does not seem to exist: {path}",
                        torrent=torrent,
                        path=path,
                    )
                    continue
                if path in self.sent_to_scan:
                    continue
                self.sent_to_scan_hashes.add(torrent.hash)
                if self.type == "sonarr":
                    self.logger.log(
                        16,
                        "DownloadedEpisodesScan: {path}",
                        path=path,
                    )
                    self.post_command(
                        "DownloadedEpisodesScan",
                        path=str(path),
                        downloadClientId=torrent.hash.upper(),
                        importMode=self.import_mode,
                    )
                elif self.type == "radarr":
                    self.logger.log(16, "DownloadedMoviesScan: {path}", path=path)
                    self.post_command(
                        "DownloadedMoviesScan",
                        path=str(path),
                        downloadClientId=torrent.hash.upper(),
                        importMode=self.import_mode,
                    )
                self.sent_to_scan.add(path)
            self.import_torrents.clear()

    def _process_failed_individual(self, hash_: str, entry: int, skip_blacklist: Set[str]) -> None:
        with contextlib.suppress(Exception):
            if hash_ not in skip_blacklist:
                self.logger.debug(
                    "Blocklisting: {name} ({hash})",
                    hash=hash_,
                    name=self.manager.qbit_manager.name_cache.get(hash_, "Deleted"),
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
                            "Re-Searching episode: {seriesTitle} ({year}) | "
                            "S{seasonNumber:02d}E{episodeNumber:03d} "
                            "({absoluteEpisodeNumber:04d}) | "
                            "{title} | "
                            "[tvdbId={tvdbId}|id={episode_id}]",
                            episode_id=object_id,
                            title=name,
                            year=year,
                            tvdbId=tvdbId,
                            seriesTitle=seriesTitle,
                            seasonNumber=seasonNumber,
                            absoluteEpisodeNumber=absoluteEpisodeNumber,
                            episodeNumber=episodeNumber,
                        )
                    else:
                        self.logger.notice(
                            "Re-Searching episode: {id}",
                            id=object_id,
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
                        "Re-Searching movie: {name} ({year}) | [tmdbId={tmdbId}|id={movie_id}]",
                        movie_id=object_id,
                        name=name,
                        year=year,
                        tmdbId=tmdbId,
                    )
                else:
                    self.logger.notice(
                        "Re-Searching movie: {movie_id}",
                        movie_id=object_id,
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
                    "Updating file priority on torrent: {name} ({hash})",
                    name=name,
                    hash=hash_,
                )
                self.manager.qbit.torrents_file_priority(
                    torrent_hash=hash_, file_ids=files, priority=0
                )
            else:
                self.logger.error("Torrent does not exist? {hash}", hash=hash_)
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
        for path in absolute_file_paths(self.completed_folder):
            if path.is_dir() and not len(list(absolute_file_paths(path))):
                path.rmdir()
                self.logger.trace("Removing empty folder: {path}", path=path)
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
                "Service: %s did not respond on %s" % (self._name, self.uri)
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
        Tuple[Union[MoviesFilesModel, EpisodeFilesModel, SeriesFilesModel], bool, bool, bool]
    ]:
        if self.type == "sonarr" and self.series_search:
            for i1, i2, i3 in self.db_get_files_series():
                yield i1, i2, i3, i3 is not True
        else:
            for i1, i2, i3 in self.db_get_files_episodes():
                yield i1, i2, i3, False

    def db_get_files_series(
        self,
    ) -> Iterable[Tuple[Union[MoviesFilesModel, SeriesFilesModel, EpisodeFilesModel], bool, bool]]:
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
    ) -> Iterable[Tuple[Union[MoviesFilesModel, EpisodeFilesModel], bool, bool]]:
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

    def db_get_request_files(self) -> Iterable[Union[MoviesFilesModel, EpisodeFilesModel]]:
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
                yield entry
        elif self.type == "radarr":
            condition = self.model_file.Year <= datetime.now(timezone.utc).year
            condition &= self.model_file.Year > 0
            if not self.do_upgrade_search:
                if self.quality_unmet_search:
                    condition &= self.model_file.QualityMet == False
                else:
                    condition &= self.model_file.MovieFileId == 0
                    condition &= self.model_file.IsRequest == True
            for entry in (
                self.model_file.select()
                .where(condition)
                .order_by(self.model_file.Title.asc())
                .execute()
            ):
                yield entry

    def db_request_update(self):
        if self.overseerr_requests:
            self.db_overseerr_update()
        else:
            self.db_ombi_update()

    def _db_request_update(self, request_ids: Dict[str, Set[Union[int, str]]]):
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
                    .where((self.model_arr_file.Year == self.search_current_year))
                    .order_by(self.model_arr_file.Added.desc())
                ):
                    self.db_update_single_series(db_entry=series)
        self.logger.trace(f"Finished updating database")

    def db_update_single_series(
        self,
        db_entry: Union[EpisodesModel, SeriesModel, MoviesModel] = None,
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
                            (self.model_queue.EntryId == db_entry.Id)
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
                            "Quality Met | {SeriesTitle} | "
                            "S{SeasonNumber:02d}E{EpisodeNumber:03d}",
                            SeriesTitle=SeriesTitle,
                            SeasonNumber=SeasonNumber,
                            EpisodeNumber=EpisodeNumber,
                        )

                    self.logger.trace(
                        "Updating database entry | {SeriesTitle} | "
                        "S{SeasonNumber:02d}E{EpisodeNumber:03d} | {Title}",
                        SeriesTitle=SeriesTitle,
                        SeasonNumber=SeasonNumber,
                        EpisodeNumber=EpisodeNumber,
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
                        "Updating database entry | {SeriesTitle}",
                        SeriesTitle=Title,
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
                        (self.model_queue.EntryId == db_entry.Id)
                    ).execute()

                title = db_entry.Title
                monitored = db_entry.Monitored
                tmdbId = db_entry.TmdbId
                year = db_entry.Year
                EntryId = db_entry.Id
                MovieFileId = db_entry.MovieFileId

                QualityMet = db_entry.MovieFileId != 0 and not QualityUnmet

                self.logger.trace(
                    "Updating database entry | {title} ({tmdbId})", title=title, tmdbId=tmdbId
                )
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
            return True  # ffprobe is not in PATH, so we say every file is acceptable.
        try:
            if file in self.files_probed:
                self.logger.trace("Probeable: File has already been probed: {file}", file=file)
                return True
            if file.is_dir():
                self.logger.trace("Not Probeable: File is a directory: {file}", file=file)
                return False
            output = ffmpeg.probe(str(file.absolute()))
            if not output:
                self.logger.trace("Not Probeable: Probe returned no output: {file}", file=file)
                return False
            self.files_probed.add(file)
            return True
        except ffmpeg.Error as e:
            error = e.stderr.decode()
            self.logger.trace(
                "Not Probeable: Probe returned an error: {file}:\n{e.stderr}",
                e=e,
                file=file,
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
        self.logger.debug("Folder Cleanup: {folder}", folder=folder)
        for file in absolute_file_paths(folder):
            if file.name in {"desktop.ini", ".DS_Store"}:
                continue
            elif file.suffix.lower() == ".parts":
                continue
            if not file.exists():
                continue
            if file.is_dir():
                self.logger.trace("Folder Cleanup: File is a folder:  {file}", file=file)
                continue
            if file.suffix.lower() in self.file_extension_allowlist:
                self.logger.trace(
                    "Folder Cleanup: File has an allowed extension: {file}", file=file
                )
                if self.file_is_probeable(file):
                    self.logger.trace(
                        "Folder Cleanup: File is a valid media type: {file}", file=file
                    )
                    continue
            try:
                file.unlink(missing_ok=True)
                self.logger.debug("File removed: {path}", path=file)
            except PermissionError:
                self.logger.debug("File in use: Failed to remove file: {path}", path=file)
        for file in self.files_to_explicitly_delete:
            if not file.exists():
                continue
            try:
                file.unlink(missing_ok=True)
                self.logger.debug(
                    "File removed: File was marked as failed by Arr | {path}", path=file
                )
            except PermissionError:
                self.logger.debug(
                    "File in use: Failed to remove file: File was marked as failed by Ar | {path}",
                    path=file,
                )

        self.files_to_explicitly_delete = iter([])
        self._remove_empty_folders()
        self.needs_cleanup = False

    def maybe_do_search(
        self,
        file_model: Union[EpisodeFilesModel, MoviesFilesModel, SeriesFilesModel],
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
            raise NoConnectionrException("Could not connect to %s" % self.uri, type="arr")
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
                        "{request_tag}Skipping: Already Searched: {model.SeriesTitle} | "
                        "S{model.SeasonNumber:02d}E{model.EpisodeNumber:03d} | "
                        "{model.Title} | [id={model.EntryId}|AirDateUTC={model.AirDateUtc}]",
                        model=file_model,
                        request_tag=request_tag,
                    )
                    file_model.Searched = True
                    file_model.save()
                    return True
                active_commands = self.arr_db_query_commands_count()
                self.logger.debug(
                    "{request_tag}{active_commands} active search commands",
                    active_commands=active_commands,
                    request_tag=request_tag,
                )
                if not bypass_limit and active_commands >= self.search_command_limit:
                    self.logger.trace(
                        "{request_tag}Idle: Too many commands in queue: {model.SeriesTitle} | "
                        "S{model.SeasonNumber:02d}E{model.EpisodeNumber:03d} | "
                        "{model.Title} | [id={model.EntryId}|AirDateUTC={model.AirDateUtc}]",
                        model=file_model,
                        request_tag=request_tag,
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
                self.logger.log(
                    17,
                    "{request_tag}Searching for: {model.SeriesTitle} | "
                    "S{model.SeasonNumber:02d}E{model.EpisodeNumber:03d} | "
                    "{model.Title} | [id={model.EntryId}|AirDateUTC={model.AirDateUtc}]",
                    model=file_model,
                    request_tag=request_tag,
                )
                return True
            else:
                file_model: SeriesFilesModel
                active_commands = self.arr_db_query_commands_count()
                self.logger.debug(
                    "{request_tag}{active_commands} active search commands",
                    active_commands=active_commands,
                    request_tag=request_tag,
                )
                if not bypass_limit and active_commands >= self.search_command_limit:
                    self.logger.trace(
                        "{request_tag}Idle: Too many commands in queue: {model.Title} | "
                        "[id={model.EntryId}",
                        model=file_model,
                        request_tag=request_tag,
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
                self.logger.log(
                    17,
                    "{request_tag}Searching for: " "{model.Title} | [id={model.EntryId}]",
                    model=file_model,
                    request_tag=request_tag,
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
                    "{request_tag}Skipping: Already Searched: {model.Title} ({model.Year}) "
                    "[tmdbId={model.TmdbId}|id={model.EntryId}]",
                    model=file_model,
                    request_tag=request_tag,
                )
                file_model.Searched = True
                file_model.save()
                return True
            active_commands = self.arr_db_query_commands_count()
            self.logger.debug(
                "{request_tag}{active_commands} active search commands",
                active_commands=active_commands,
                request_tag=request_tag,
            )
            if not bypass_limit and active_commands >= self.search_command_limit:
                self.logger.trace(
                    "{request_tag}Skipping: Too many in queue: {model.Title} ({model.Year}) "
                    "[tmdbId={model.TmdbId}|id={model.EntryId}]",
                    model=file_model,
                    request_tag=request_tag,
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
            self.logger.log(
                17,
                "{request_tag}Searching for: {model.Title} ({model.Year}) "
                "[tmdbId={model.TmdbId}|id={model.EntryId}]",
                model=file_model,
                request_tag=request_tag,
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

    def process_entries(self, hashes: Set[str]) -> Tuple[List[Tuple[int, str]], Set[str]]:
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
            self.api_calls()
            self.refresh_download_queue()
            time_now = time.time()
            torrents = self.manager.qbit_manager.client.torrents.info.all(
                category=self.category, sort="added_on", reverse=False
            )
            for torrent in torrents:
                if torrent.category != RECHECK_CATEGORY:
                    self.manager.qbit_manager.cache[torrent.hash] = torrent.category
                self.manager.qbit_manager.name_cache[torrent.hash] = torrent.name
                # Bypass everything if manually marked as failed
                if torrent.category == FAILED_CATEGORY:
                    self.logger.notice(
                        "Deleting manually failed torrent: "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    self.delete.add(torrent.hash)
                # Bypass everything else if manually marked for rechecking
                elif torrent.category == RECHECK_CATEGORY:
                    self.logger.notice(
                        "Re-cheking manually set torrent: "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    self.recheck.add(torrent.hash)
                # Do not touch torrents that are currently "Checking".
                elif self.is_ignored_state(torrent):
                    self.logger.trace(
                        "Skipping torrent: Ignored state | "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    if torrent.state_enum == TorrentStates.QUEUED_DOWNLOAD:
                        self.recently_queue[torrent.hash] = time.time()
                    continue
                # Do not touch torrents recently resumed/reched (A torrent can temporarely stall after being resumed from a paused state).
                elif torrent.hash in self.timed_ignore_cache:
                    self.logger.trace(
                        "Skipping torrent: Marked for skipping | "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    continue
                elif torrent.state_enum == TorrentStates.QUEUED_UPLOAD:
                    self.pause.add(torrent.hash)
                    self.skip_blacklist.add(torrent.hash)
                    self.logger.trace(
                        "Pausing torrent: Queued Upload | "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                # Process torrents who have stalled at this point, only mark from for deletion if they have been added more than "IgnoreTorrentsYoungerThan" seconds ago
                elif torrent.state_enum in (
                    TorrentStates.METADATA_DOWNLOAD,
                    TorrentStates.STALLED_DOWNLOAD,
                ):
                    if (
                        self.recently_queue.get(torrent.hash, torrent.added_on)
                        < time_now - self.ignore_torrents_younger_than
                    ):
                        self.logger.info(
                            "Deleting Stale torrent: "
                            "[Progress: {progress}%][Added On: {added}]"
                            "[Availability: {availability}%][Time Left: {timedelta}]"
                            "[Last active: {last_activity}] "
                            "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                            torrent=torrent,
                            progress=round(torrent.progress * 100, 2),
                            availability=round(torrent.availability * 100, 2),
                            added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                            timedelta=timedelta(seconds=torrent.eta),
                            last_activity=datetime.fromtimestamp(torrent.last_activity),
                        )
                        self.delete.add(torrent.hash)
                # Ignore torrents who have reached maximum percentage as long as the last activity is within the MaximumETA set for this category
                # For example if you set MaximumETA to 5 mines, this will ignore all torrets that have stalled at a higher percentage as long as there is activity
                # And the window of activity is determined by the current time - MaximumETA, if the last active was after this value ignore this torrent
                # the idea here is that if a torrent isn't completely dead some leecher/seeder may contribute towards your progress.
                # However if its completely dead and no activity is observed, then lets remove it and requeue a new torrent.
                elif (
                    torrent.progress >= self.maximum_deletable_percentage
                    and self.is_complete_state(torrent) is False
                ) and torrent.hash in self.cleaned_torrents:
                    if torrent.last_activity < time_now - self.maximum_eta:
                        self.logger.info(
                            "Deleting Stale torrent: "
                            "[Progress: {progress}%][Added On: {added}]"
                            "[Availability: {availability}%][Time Left: {timedelta}]"
                            "[Last active: {last_activity}] "
                            "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                            torrent=torrent,
                            progress=round(torrent.progress * 100, 2),
                            availability=round(torrent.availability * 100, 2),
                            added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                            timedelta=timedelta(seconds=torrent.eta),
                            last_activity=datetime.fromtimestamp(torrent.last_activity),
                        )
                        self.delete.add(torrent.hash)
                    else:
                        self.logger.trace(
                            "Skipping torrent: Reached Maximum completed percentage and is active | "
                            "[Progress: {progress}%][Added On: {added}]"
                            "[Availability: {availability}%][Time Left: {timedelta}]"
                            "[Last active: {last_activity}] "
                            "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                            torrent=torrent,
                            progress=round(torrent.progress * 100, 2),
                            availability=round(torrent.availability * 100, 2),
                            added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                            timedelta=timedelta(seconds=torrent.eta),
                            last_activity=datetime.fromtimestamp(torrent.last_activity),
                        )
                        continue
                # Resume monitored downloads which have been paused.
                elif (
                    torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD
                    and torrent.amount_left != 0
                ):
                    self.timed_ignore_cache.add(torrent.hash)
                    self.resume.add(torrent.hash)
                    self.logger.debug(
                        "Resuming incomplete paused torrent: "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                # Ignore torrents which have been submitted to their respective Arr instance for import.
                elif (
                    torrent.hash
                    in self.manager.managed_objects[torrent.category].sent_to_scan_hashes
                ) and torrent.hash in self.cleaned_torrents:
                    self.logger.trace(
                        "Skipping torrent: Already sent for import | "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    continue
                # Some times torrents will error, this causes them to be rechecked so they complete downloading.
                elif torrent.state_enum == TorrentStates.ERROR:
                    self.logger.trace(
                        "Rechecking Erroed torrent: "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    self.recheck.add(torrent.hash)
                # If a torrent was not just added, and the amount left to download is 0 and the torrent
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
                    self.logger.info(
                        "Pausing Completed torrent: "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(torrent.added_on),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    self.pause.add(torrent.hash)
                    self.skip_blacklist.add(torrent.hash)
                    self.import_torrents.append(torrent)
                # Sometimes Sonarr/Radarr does not automatically remove the torrent for some reason,
                # this ensures that we can safelly remove it if the client is reporting the status of the client as "Missing files"
                elif torrent.state_enum == TorrentStates.MISSING_FILES:
                    self.logger.info(
                        "Deleting torrent with missing files: "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(torrent.added_on),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    # We do not want to blacklist these!!
                    self.skip_blacklist.add(torrent.hash)
                # If a torrent is Uploading Pause it, as long as its for being Forced Uploaded.
                elif (
                    self.is_uploading_state(torrent)
                    and torrent.seeding_time > 1
                    and torrent.amount_left == 0
                    and torrent.added_on > 0
                    and torrent.content_path
                    and torrent.amount_left == 0
                ) and torrent.hash in self.cleaned_torrents:
                    self.logger.info(
                        "Pausing uploading torrent: "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(torrent.added_on),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    self.pause.add(torrent.hash)
                    self.skip_blacklist.add(torrent.hash)
                # Mark a torrent for deletion
                elif (
                    torrent.state_enum != TorrentStates.PAUSED_DOWNLOAD
                    and torrent.state_enum.is_downloading
                    and self.recently_queue.get(torrent.hash, torrent.added_on)
                    < time_now - self.ignore_torrents_younger_than
                    and torrent.eta > self.maximum_eta
                    and not self.donotremoveslow
                ):
                    self.logger.trace(
                        "Deleting slow torrent: "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    self.delete.add(torrent.hash)
                # Process uncompleted torrents
                elif torrent.state_enum.is_downloading:
                    # If a torrent availability hasn't reached 100% or more within the configurable
                    # "IgnoreTorrentsYoungerThan" variable, mark it for deletion.
                    if (
                        self.recently_queue.get(torrent.hash, torrent.added_on)
                        < time_now - self.ignore_torrents_younger_than
                        and torrent.availability < 1
                    ) and torrent.hash in self.cleaned_torrents:
                        self.logger.trace(
                            "Deleting stale torrent: "
                            "[Progress: {progress}%][Added On: {added}]"
                            "[Availability: {availability}%][Time Left: {timedelta}]"
                            "[Last active: {last_activity}] "
                            "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                            torrent=torrent,
                            progress=round(torrent.progress * 100, 2),
                            availability=round(torrent.availability * 100, 2),
                            added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                            timedelta=timedelta(seconds=torrent.eta),
                            last_activity=datetime.fromtimestamp(torrent.last_activity),
                        )
                        self.delete.add(torrent.hash)
                    else:
                        if torrent.hash in self.cleaned_torrents:
                            self.logger.trace(
                                "Skipping file check: Already been cleaned up | "
                                "[Progress: {progress}%][Added On: {added}]"
                                "[Availability: {availability}%][Time Left: {timedelta}]"
                                "[Last active: {last_activity}] "
                                "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                                torrent=torrent,
                                progress=round(torrent.progress * 100, 2),
                                availability=round(torrent.availability * 100, 2),
                                added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                                timedelta=timedelta(seconds=torrent.eta),
                                last_activity=datetime.fromtimestamp(torrent.last_activity),
                            )
                            continue
                        # A downloading torrent is not stalled, parse its contents.
                        _remove_files = set()
                        total = len(torrent.files)
                        if total == 0:
                            self.cleaned_torrents.add(torrent.hash)
                            continue
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
                                    "Removing File: Not allowed | Parent: "
                                    "{folder_match} | {torrent.name} ({torrent.hash}) | {file.name} ",
                                    torrent=torrent,
                                    file=file,
                                    folder_match=folder_match,
                                )
                                _remove_files.add(file.id)
                                total -= 1
                            # A file matched and entry in FileNameExclusionRegex, mark it for exclusion.
                            elif (
                                match := self.file_name_exclusion_regex_re.search(file_path.name)
                            ) and match.group():
                                self.logger.debug(
                                    "Removing File: Not allowed | Name: "
                                    "{match} | {torrent.name} ({torrent.hash}) | {file.name}",
                                    torrent=torrent,
                                    file=file,
                                    match=match.group(),
                                )
                                _remove_files.add(file.id)
                                total -= 1
                            elif file_path.suffix.lower() not in self.file_extension_allowlist:
                                self.logger.debug(
                                    "Removing File: Not allowed | Extension: "
                                    "{suffix}  | {torrent.name} ({torrent.hash}) | {file.name} ",
                                    torrent=torrent,
                                    file=file,
                                    suffix=file_path.suffix,
                                )
                                _remove_files.add(file.id)
                                total -= 1
                            # If all files in the torrent are marked for exlusion then delete the torrent.
                            if total == 0:
                                self.logger.info(
                                    "Deleting All files ignored: "
                                    "[Progress: {progress}%][Added On: {added}]"
                                    "[Availability: {availability}%][Time Left: {timedelta}]"
                                    "[Last active: {last_activity}] "
                                    "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                                    torrent=torrent,
                                    progress=round(torrent.progress * 100, 2),
                                    availability=round(torrent.availability * 100, 2),
                                    added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                                    timedelta=timedelta(seconds=torrent.eta),
                                    last_activity=datetime.fromtimestamp(torrent.last_activity),
                                )
                                self.delete.add(torrent.hash)
                            # Mark all bad files and folder for exclusion.
                            elif _remove_files and torrent.hash not in self.change_priority:
                                self.change_priority[torrent.hash] = list(_remove_files)
                            elif _remove_files and torrent.hash in self.change_priority:
                                self.change_priority[torrent.hash] = list(_remove_files)
                        self.cleaned_torrents.add(torrent.hash)

                else:
                    self.logger.trace(
                        "Skipping torrent: Unresolved state: "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(self.recently_queue.get(torrent.hash, torrent.added_on)),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
            self.process()
        except NoConnectionrException as e:
            self.logger.error(e.message)
        except Exception as e:
            self.logger.error(e, exc_info=sys.exc_info())

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
                self.logger.notice(
                    "Attempting to force grab: {id_} =  {entry}", id_=id_, entry=entry.get("title")
                )
        if ids:
            with ThreadPoolExecutor(max_workers=16) as executor:
                executor.map(self._force_grab, ids)

    def _force_grab(self, id_):
        try:
            path = f"/api/v3/queue/grab/{id_}"
            res = self.client.request_post(path, data={})
            self.logger.trace("Successful Grab: {id_}", id_=id_)
            return res
        except Exception:
            self.logger.error("Exception when trying to force grab - {id_}.", id_=id_)

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
                        "Failed to connected to qBit client, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                elif e.type == "internet":
                    self.logger.critical(
                        "Failed to connected to the internet, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                elif e.type == "arr":
                    self.logger.critical(
                        "Failed to connected to the Arr instance, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                elif e.type == "delay":
                    self.logger.critical(
                        "Forced delay due to temporary issue with environment, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                time.sleep(e.length)

    def run_search_loop(self) -> NoReturn:
        self.register_search_mode()
        if not self.search_missing:
            return None
        count_start = self.search_current_year
        stopping_year = datetime.now().year if self.search_in_reverse else 1900
        loop_timer = timedelta(minutes=15)
        while True:
            timer = datetime.now(timezone.utc)
            try:
                self.run_request_search()
                self.db_update()
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
                    else:
                        if self.search_current_year < stopping_year:
                            self.search_current_year = copy(count_start)
                except RestartLoopException:
                    self.logger.debug("Loop timer elapsed, restarting it.")
                except NoConnectionrException as e:
                    self.logger.error(e.message)
                    self.manager.qbit_manager.should_delay_torrent_scan = True
                    raise DelayLoopException(length=300, type=e.type)
                except DelayLoopException:
                    raise
                except ValueError:
                    self.logger.debug(
                        "Loop completed, restarting it."
                    )  # TODO: Clean so that entries can be researched.
                except Exception as e:
                    self.logger.exception(e, exc_info=sys.exc_info())
                time.sleep(LOOP_SLEEP_TIMER)
            except DelayLoopException as e:
                if e.type == "qbit":
                    self.logger.critical(
                        "Failed to connected to qBit client, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                elif e.type == "internet":
                    self.logger.critical(
                        "Failed to connected to the internet, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                elif e.type == "arr":
                    self.logger.critical(
                        "Failed to connected to the Arr instance, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                elif e.type == "delay":
                    self.logger.critical(
                        "Forced delay due to temporary issue with environment, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                time.sleep(e.length)
                self.manager.qbit_manager.should_delay_torrent_scan = False
            else:
                time.sleep(5)

    def run_torrent_loop(self) -> NoReturn:
        while True:
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
                except Exception as e:
                    self.logger.error(e, exc_info=sys.exc_info())
                time.sleep(LOOP_SLEEP_TIMER)
            except DelayLoopException as e:
                if e.type == "qbit":
                    self.logger.critical(
                        "Failed to connected to qBit client, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                elif e.type == "internet":
                    self.logger.critical(
                        "Failed to connected to the internet, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                elif e.type == "arr":
                    self.logger.critical(
                        "Failed to connected to the Arr instance, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                elif e.type == "delay":
                    self.logger.critical(
                        "Forced delay due to temporary issue with environment, sleeping for {time}.",
                        time=timedelta(seconds=e.length),
                    )
                time.sleep(e.length)
                self.manager.qbit_manager.should_delay_torrent_scan = False

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

        [p.start() for p in _temp]


class PlaceHolderArr(Arr):
    def __init__(
        self,
        name: str,
        manager: ArrManager,
    ):
        if name in manager.groups:
            raise EnvironmentError("Group '{name}' has already been registered.")
        self._name = name
        self.category = name
        self.manager = manager
        self.queue = []
        self.cache = {}
        self.requeue_cache = {}
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
        self.IGNORE_TORRENTS_YOUNGER_THAN = CONFIG.getint(
            "Settings", "IgnoreTorrentsYoungerThan", fallback=600
        )
        self.timed_ignore_cache = ExpiringSet(max_age_seconds=self.IGNORE_TORRENTS_YOUNGER_THAN)
        self.timed_skip = ExpiringSet(max_age_seconds=self.IGNORE_TORRENTS_YOUNGER_THAN)
        self.logger = logbook.Logger(self._name)
        self.search_missing = False
        self.session = None

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
            torrents = self.manager.qbit_manager.client.torrents.info.all(
                category=self.category, sort="added_on", reverse=False
            )
            for torrent in torrents:
                if torrent.category != RECHECK_CATEGORY:
                    self.manager.qbit_manager.cache[torrent.hash] = torrent.category
                self.manager.qbit_manager.name_cache[torrent.hash] = torrent.name
                # Bypass everything if manually marked as failed
                if torrent.category == FAILED_CATEGORY:
                    self.logger.notice(
                        "Deleting manually failed torrent: "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(torrent.added_on),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    self.delete.add(torrent.hash)
                # Bypass everything else if manually marked for rechecking
                elif torrent.category == RECHECK_CATEGORY:
                    self.logger.notice(
                        "Re-cheking manually set torrent: "
                        "[Progress: {progress}%][Added On: {added}]"
                        "[Availability: {availability}%][Time Left: {timedelta}]"
                        "[Last active: {last_activity}] "
                        "| [{torrent.state_enum}] | {torrent.name} ({torrent.hash})",
                        torrent=torrent,
                        progress=round(torrent.progress * 100, 2),
                        availability=round(torrent.availability * 100, 2),
                        added=datetime.fromtimestamp(torrent.added_on),
                        timedelta=timedelta(seconds=torrent.eta),
                        last_activity=datetime.fromtimestamp(torrent.last_activity),
                    )
                    self.recheck.add(torrent.hash)
            self.process()
        except NoConnectionrException as e:
            self.logger.error(e.message)
        except Exception as e:
            self.logger.error(e, exc_info=sys.exc_info())

    def run_search_loop(self):
        return


class ArrManager:
    def __init__(self, qbitmanager: qBitManager):
        self.groups: Set[str] = set()
        self.uris: Set[str] = set()
        self.special_categories: Set[str] = {FAILED_CATEGORY, RECHECK_CATEGORY}
        self.category_allowlist: Set[str] = self.special_categories.copy()

        self.completed_folders: Set[pathlib.Path] = set()
        self.managed_objects: Dict[str, Arr] = {}
        self.ffprobe_available: bool = bool(shutil.which("ffprobe"))
        self.qbit: qbittorrentapi.Client = qbitmanager.client
        self.qbit_manager: qBitManager = qbitmanager
        self.logger = logger
        if not self.ffprobe_available:
            self.logger.error(
                "ffprobe was not found in your PATH, disabling all functionality dependant on it."
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
                except (NoSectionError, NoOptionError) as e:
                    self.logger.exception(e.message)
                except SkipException:
                    continue
                except EnvironmentError as e:
                    self.logger.exception(e)
        for cat in self.special_categories:
            managed_object = PlaceHolderArr(cat, self)
            self.managed_objects[cat] = managed_object
        return self
