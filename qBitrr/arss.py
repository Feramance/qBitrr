from __future__ import annotations

import atexit
import contextlib
import itertools
import logging
import pathlib
import re
import shutil
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from copy import copy
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, NoReturn
from urllib.parse import urlparse

import ffmpeg
import pathos
import qbittorrentapi
import qbittorrentapi.exceptions
import requests
from jaraco.docker import is_docker
from packaging import version as version_parser
from peewee import DatabaseError, Model, OperationalError, SqliteDatabase
from pyarr import LidarrAPI, RadarrAPI, SonarrAPI
from pyarr.exceptions import PyarrResourceNotFound, PyarrServerError
from pyarr.types import JsonObject
from qbittorrentapi import TorrentDictionary, TorrentStates
from ujson import JSONDecodeError

from qBitrr.config import (
    APPDATA_FOLDER,
    AUTO_PAUSE_RESUME,
    CHANGE_ME_SENTINEL,
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
from qBitrr.db_lock import with_database_retry
from qBitrr.errors import (
    DelayLoopException,
    NoConnectionrException,
    RestartLoopException,
    SkipException,
    UnhandledError,
)
from qBitrr.logger import run_logs
from qBitrr.search_activity_store import (
    clear_search_activity,
    fetch_search_activities,
    record_search_activity,
)
from qBitrr.tables import (
    AlbumFilesModel,
    AlbumQueueModel,
    ArtistFilesModel,
    EpisodeFilesModel,
    EpisodeQueueModel,
    FilesQueued,
    MovieQueueModel,
    MoviesFilesModel,
    SeriesFilesModel,
    TorrentLibrary,
    TrackFilesModel,
)
from qBitrr.utils import (
    ExpiringSet,
    absolute_file_paths,
    format_bytes,
    has_internet,
    mask_secret,
    parse_size,
    validate_and_return_torrent_file,
    with_retry,
)

_ARR_RETRY_EXCEPTIONS = (
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ContentDecodingError,
    requests.exceptions.ConnectionError,
    JSONDecodeError,
)

_ARR_RETRY_EXCEPTIONS_EXTENDED = (
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ContentDecodingError,
    requests.exceptions.ConnectionError,
    JSONDecodeError,
    requests.exceptions.RequestException,
)


def _extract_tracker_host(uri: str) -> str:
    """Extract the hostname from a tracker URI for matching purposes.

    Handles bare domains (``tracker.example.org``), full announce URLs
    (``https://tracker.example.org/a/key/announce``), and scheme-less paths
    (``tracker.example.org/announce``).  Returns the lowercased hostname so
    that a config URI ``tracker.example.org`` will match the qBit announce
    URL ``https://tracker.example.org/a/passkey/announce``.
    """
    uri = uri.strip().rstrip("/")
    if not uri:
        return ""
    # If no scheme, urlparse puts everything in `path` — add a scheme so it
    # can extract the hostname properly.
    if "://" not in uri:
        uri = "https://" + uri
    try:
        parsed = urlparse(uri)
        return (parsed.hostname or "").lower()
    except ValueError:
        # Python 3.14+ raises ValueError for malformed IPv6 URLs
        return ""


def _tracker_host_matches(config_uri: str, tracker_url: str) -> bool:
    """Return True if *config_uri* and *tracker_url* refer to the same tracker host."""
    return bool(
        (h := _extract_tracker_host(config_uri)) and h == _extract_tracker_host(tracker_url)
    )


def _normalize_media_status(value: int | str | None) -> str:
    """Normalise Overseerr media status values across API versions."""
    int_mapping = {
        1: "UNKNOWN",
        2: "PENDING",
        3: "PROCESSING",
        4: "PARTIALLY_AVAILABLE",
        5: "AVAILABLE",
        6: "DELETED",
    }
    if value is None:
        return "UNKNOWN"
    if isinstance(value, str):
        token = value.strip().upper().replace("-", "_").replace(" ", "_")
        # Newer Overseerr builds can return strings such as "PARTIALLY_AVAILABLE"
        return token or "UNKNOWN"
    try:
        return int_mapping.get(int(value), "UNKNOWN")
    except (TypeError, ValueError):
        return "UNKNOWN"


def _is_media_available(status: str) -> bool:
    return status in {"AVAILABLE", "DELETED"}


def _is_media_processing(status: str) -> bool:
    return status in {"PROCESSING", "PARTIALLY_AVAILABLE"}


if TYPE_CHECKING:
    from qBitrr.main import qBitManager


class Arr:
    def __init__(
        self,
        name: str,
        manager: ArrManager,
        client_cls: type[Callable | RadarrAPI | SonarrAPI | LidarrAPI],
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

        # Set completed_folder path (used for category creation and file monitoring)
        if not QBIT_DISABLED:
            try:
                # Check default instance for existing category configuration
                categories = self.manager.qbit_manager.client.torrent_categories.categories
                categ = categories.get(self.category)
                if categ and categ.get("savePath"):
                    self.logger.trace("Category exists with save path [%s]", categ["savePath"])
                    self.completed_folder = pathlib.Path(categ["savePath"])
                else:
                    self.logger.trace("Category does not exist or lacks save path")
                    self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(
                        self.category
                    )
            except Exception as e:
                self.logger.warning(
                    "Could not connect to qBittorrent during initialization for %s: %s. Using default path.",
                    self._name,
                    str(e).split("\n")[0] if "\n" in str(e) else str(e),
                )
                self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(
                    self.category
                )
            # Ensure category exists on ALL instances (deferred to avoid __init__ failures)
            try:
                self._ensure_category_on_all_instances()
            except Exception as e:
                self.logger.warning(
                    "Could not ensure category on all instances during init: %s", e
                )
        else:
            self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(self.category)

        if not self.completed_folder.exists() and not SEARCH_ONLY:
            try:
                self.completed_folder.mkdir(parents=True, exist_ok=True)
                self.completed_folder.chmod(mode=0o755)
            except Exception:
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
        self.refresh_downloads_timer = CONFIG.get_duration(
            f"{name}.RefreshDownloadsTimer", fallback=1, unit="minutes"
        )
        self.arr_error_codes_to_blocklist = CONFIG.get(
            f"{name}.ArrErrorCodesToBlocklist", fallback=[]
        )
        self.rss_sync_timer = CONFIG.get_duration(
            f"{name}.RssSyncTimer", fallback=15, unit="minutes"
        )

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
        self.seeding_mode_global_max_seeding_time = CONFIG.get_duration(
            f"{name}.Torrent.SeedingMode.MaxSeedingTime", fallback=-1
        )
        self.seeding_mode_global_remove_torrent = CONFIG.get(
            f"{name}.Torrent.SeedingMode.RemoveTorrent", fallback=-1
        )
        self.seeding_mode_global_bad_tracker_msg = CONFIG.get(
            f"{name}.Torrent.SeedingMode.RemoveTrackerWithMessage", fallback=[]
        )
        if isinstance(self.seeding_mode_global_bad_tracker_msg, str):
            self.seeding_mode_global_bad_tracker_msg = [self.seeding_mode_global_bad_tracker_msg]
        else:
            self.seeding_mode_global_bad_tracker_msg = list(
                self.seeding_mode_global_bad_tracker_msg
            )

        qbit_trackers = CONFIG.get("qBit.Trackers", fallback=[])
        arr_trackers = CONFIG.get(f"{name}.Torrent.Trackers", fallback=[])
        self.monitored_trackers = self._merge_trackers(qbit_trackers, arr_trackers)
        self._remove_trackers_if_exists: set[str] = {
            uri
            for i in self.monitored_trackers
            if i.get("RemoveIfExists") is True
            and (uri := (i.get("URI") or "").strip().rstrip("/"))
        }
        self._monitored_tracker_urls: set[str] = {
            uri
            for i in self.monitored_trackers
            if (uri := (i.get("URI") or "").strip().rstrip("/"))
            and uri not in self._remove_trackers_if_exists
        }
        self._add_trackers_if_missing: set[str] = {
            uri
            for i in self.monitored_trackers
            if i.get("AddTrackerIfMissing") is True
            and (uri := (i.get("URI") or "").strip().rstrip("/"))
        }
        # Host-based lookup: maps extracted hostname → config URI for matching
        # qBit announce URLs (e.g. "https://host/a/key/announce") against config
        # URIs that may be bare domains (e.g. "host") or partial paths.
        self._host_to_config_uri: dict[str, str] = {}
        for _uri in self._monitored_tracker_urls:
            _host = _extract_tracker_host(_uri)
            if _host:
                self._host_to_config_uri[_host] = _uri
        self._remove_tracker_hosts: set[str] = {
            h for u in self._remove_trackers_if_exists if (h := _extract_tracker_host(u))
        }
        self._normalized_bad_tracker_msgs: set[str] = {
            msg.lower() for msg in self.seeding_mode_global_bad_tracker_msg if isinstance(msg, str)
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

        self.ignore_torrents_younger_than = CONFIG.get_duration(
            f"{name}.Torrent.IgnoreTorrentsYoungerThan", fallback=600
        )
        self.maximum_eta = CONFIG.get_duration(f"{name}.Torrent.MaximumETA", fallback=86400)
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
        self.stalled_delay = CONFIG.get_duration(
            f"{name}.Torrent.StalledDelay", fallback=15, unit="minutes"
        )
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
        # SearchBySeries can be: True (always series), False (always episode), or "smart" (automatic)
        series_search_config = CONFIG.get(f"{name}.EntrySearch.SearchBySeries", fallback=False)
        if isinstance(series_search_config, str) and series_search_config.lower() == "smart":
            self.series_search = "smart"
        elif series_search_config in (True, "true", "True", "TRUE", 1):
            self.series_search = True
        else:
            self.series_search = False
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
        self.search_requests_every_x_seconds = CONFIG.get_duration(
            f"{name}.EntrySearch.SearchRequestsEvery", fallback=300
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
        elif isinstance(self.client, LidarrAPI):
            self.type = "lidarr"

        # Disable unsupported features for Lidarr
        if self.type == "lidarr":
            self.search_by_year = False
            self.ombi_search_requests = False
            self.overseerr_requests = False
            self.ombi_uri = None
            self.ombi_api_key = None
            self.overseerr_uri = None
            self.overseerr_api_key = None

        try:
            version_info = self.client.get_update()
            self.version = version_parser.parse(version_info[0].get("version"))
            self.logger.debug("%s version: %s", self._name, self.version.__str__())
        except Exception:
            self.logger.debug("Failed to get version")

        # Try new QualityProfileMappings format first (dict), then fall back to old format (lists)
        self.quality_profile_mappings = CONFIG.get(
            f"{self._name}.EntrySearch.QualityProfileMappings", fallback={}
        )

        if not self.quality_profile_mappings:
            # Old format: separate lists - convert to dict
            main_profiles = CONFIG.get(
                f"{self._name}.EntrySearch.MainQualityProfile", fallback=None
            )
            if not isinstance(main_profiles, list):
                main_profiles = [main_profiles] if main_profiles else []
            temp_profiles = CONFIG.get(
                f"{self._name}.EntrySearch.TempQualityProfile", fallback=None
            )
            if not isinstance(temp_profiles, list):
                temp_profiles = [temp_profiles] if temp_profiles else []

            # Convert lists to dictionary
            if main_profiles and temp_profiles and len(main_profiles) == len(temp_profiles):
                self.quality_profile_mappings = dict(zip(main_profiles, temp_profiles))

        self.use_temp_for_missing = (
            CONFIG.get(f"{name}.EntrySearch.UseTempForMissing", fallback=False)
            and self.quality_profile_mappings
        )
        self.keep_temp_profile = CONFIG.get(f"{name}.EntrySearch.KeepTempProfile", fallback=False)

        if self.use_temp_for_missing:
            self.logger.info(
                "Temp quality profile mode enabled: Mappings=%s, Keep temp=%s",
                self.quality_profile_mappings,
                self.keep_temp_profile,
            )
            self.temp_quality_profile_ids = self.parse_quality_profiles()
            # Create reverse mapping (temp_id → main_id) for O(1) lookups
            self.main_quality_profile_ids = {
                v: k for k, v in self.temp_quality_profile_ids.items()
            }
            self.profile_switch_retry_attempts = CONFIG.get(
                f"{name}.EntrySearch.ProfileSwitchRetryAttempts", fallback=3
            )
            self.temp_profile_timeout_minutes = CONFIG.get_duration(
                f"{name}.EntrySearch.TempProfileResetTimeoutMinutes", fallback=0, unit="minutes"
            )
            self.logger.info(
                "Parsed quality profile mappings: %s",
                {f"{k}→{v}": f"(main→temp)" for k, v in self.temp_quality_profile_ids.items()},
            )
            if self.temp_profile_timeout_minutes > 0:
                self.logger.info(
                    f"Temp profile timeout enabled: {self.temp_profile_timeout_minutes} minutes"
                )

            # Check if we should reset all temp profiles on startup
            force_reset = CONFIG.get(f"{name}.EntrySearch.ForceResetTempProfiles", fallback=False)
            if force_reset:
                self.logger.info(
                    "ForceResetTempProfiles enabled - resetting all temp profiles on startup"
                )
                self._reset_all_temp_profiles()

        # Cache for valid quality profile IDs to avoid repeated API calls and warnings
        self._quality_profile_cache: dict[int, dict] = {}
        self._invalid_quality_profiles: set[int] = set()

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
        self.remove_from_qbit_by_instance: dict[str, set[str]] = {}
        self.overseerr_requests_release_cache = {}
        self.files_to_explicitly_delete: Iterator = iter([])
        self.files_to_cleanup = set()
        self.missing_files_post_delete = set()
        self.downloads_with_bad_error_message_blocklist = set()
        self.needs_cleanup = False
        self._warned_no_seeding_limits = False

        self.last_search_description: str | None = None
        self.last_search_timestamp: str | None = None
        self.queue_active_count: int = 0
        self.category_torrent_count: int = 0
        self.free_space_tagged_count: int = 0

        self.timed_ignore_cache = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.timed_ignore_cache_2 = ExpiringSet(
            max_age_seconds=self.ignore_torrents_younger_than * 2
        )
        self.timed_skip = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.tracker_delay = ExpiringSet(max_age_seconds=600)
        self.special_casing_file_check = ExpiringSet(max_age_seconds=10)
        self.expiring_bool = ExpiringSet(max_age_seconds=10)
        self.session = requests.Session()
        atexit.register(self.session.close)
        self.cleaned_torrents = set()
        self.search_api_command = None

        self._webui_db_loaded = False
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
            mask_secret(self.apikey),
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
                self.logger.debug("Script Config:  OmbiAPIKey=%s", mask_secret(self.ombi_api_key))
                self.logger.debug("Script Config:  ApprovedOnly=%s", self.ombi_approved_only)
            self.logger.debug(
                "Script Config:  SearchOverseerrRequests=%s", self.overseerr_requests
            )
            if self.overseerr_requests:
                self.logger.debug("Script Config:  OverseerrURI=%s", self.overseerr_uri)
                self.logger.debug(
                    "Script Config:  OverseerrAPIKey=%s", mask_secret(self.overseerr_api_key)
                )
            if self.ombi_search_requests or self.overseerr_requests:
                self.logger.debug(
                    "Script Config:  SearchRequestsEvery=%s", self.search_requests_every_x_seconds
                )

        if self.type == "sonarr":
            if (
                self.quality_unmet_search
                or self.do_upgrade_search
                or self.custom_format_unmet_search
                or self.series_search is True
            ):
                self.search_api_command = "SeriesSearch"
            elif self.series_search == "smart":
                # In smart mode, the command will be determined dynamically
                self.search_api_command = "SeriesSearch"  # Default, will be overridden per search
            else:
                self.search_api_command = "MissingEpisodeSearch"

        if not QBIT_DISABLED and not TAGLESS:
            try:
                _client = self.manager.qbit_manager.client
                if _client is not None:
                    _client.torrents_create_tags(
                        [
                            "qBitrr-allowed_seeding",
                            "qBitrr-ignored",
                            "qBitrr-imported",
                            "qBitrr-allowed_stalled",
                        ]
                    )
            except qbittorrentapi.exceptions.APIConnectionError as e:
                self.logger.warning(
                    "Could not connect to qBittorrent during initialization for %s: %s. "
                    "Will retry when process starts.",
                    self._name,
                    str(e).split("\n")[0],  # Only log first line of error
                )
        elif not QBIT_DISABLED and TAGLESS:
            try:
                _client = self.manager.qbit_manager.client
                if _client is not None:
                    _client.torrents_create_tags(["qBitrr-ignored"])
            except qbittorrentapi.exceptions.APIConnectionError as e:
                self.logger.warning(
                    "Could not connect to qBittorrent during initialization for %s: %s. "
                    "Will retry when process starts.",
                    self._name,
                    str(e).split("\n")[0],  # Only log first line of error
                )
        self.search_setup_completed = False
        self.model_file: Model | None = None
        self.series_file_model: Model | None = None
        self.model_queue: Model | None = None
        self.persistent_queue: Model | None = None
        self.track_file_model: Model | None = None
        self.torrents: TorrentLibrary | None = None
        self.torrent_db: SqliteDatabase | None = None
        self.db: SqliteDatabase | None = None
        # Initialize search mode (and torrent tag-emulation DB in TAGLESS)
        # early and fail fast if it cannot be set up.
        self.register_search_mode()
        atexit.register(
            lambda: (
                hasattr(self, "db") and self.db and not self.db.is_closed() and self.db.close()
            )
        )
        atexit.register(
            lambda: (
                hasattr(self, "torrent_db")
                and self.torrent_db
                and not self.torrent_db.is_closed()
                and self.torrent_db.close()
            )
        )
        self.logger.hnotice("Starting %s monitor", self._name)

    @staticmethod
    def _merge_trackers(qbit_trackers: list, arr_trackers: list) -> list:
        """Merge qBit-level and Arr-level trackers. Arr overrides qBit by URI."""
        merged: dict[str, dict] = {}
        for tracker in qbit_trackers:
            if isinstance(tracker, dict):
                uri = (tracker.get("URI") or "").strip().rstrip("/")
                if uri:
                    merged[uri] = dict(tracker)
        for tracker in arr_trackers:
            if isinstance(tracker, dict):
                uri = (tracker.get("URI") or "").strip().rstrip("/")
                if uri:
                    merged[uri] = dict(tracker)
        return list(merged.values())

    def _ensure_category_on_all_instances(self) -> None:
        """
        Ensure the Arr category exists on ALL qBittorrent instances.

        Creates the category with the completed_folder save path on each instance.
        Logs errors but continues if individual instances fail.
        """
        if QBIT_DISABLED:
            return

        qbit_manager = self.manager.qbit_manager
        all_instances = qbit_manager.get_all_instances()

        self.logger.debug(
            "Ensuring category '%s' exists on %d qBit instance(s)",
            self.category,
            len(all_instances),
        )

        for instance_name in all_instances:
            try:
                client = qbit_manager.get_client(instance_name)
                if client is None:
                    self.logger.warning(
                        "Skipping category creation on instance '%s' (client unavailable)",
                        instance_name,
                    )
                    continue

                categories = client.torrent_categories.categories
                if self.category not in categories:
                    client.torrent_categories.create_category(
                        self.category, save_path=str(self.completed_folder)
                    )
                    self.logger.info(
                        "Created category '%s' on instance '%s'", self.category, instance_name
                    )
                else:
                    self.logger.debug(
                        "Category '%s' already exists on instance '%s'",
                        self.category,
                        instance_name,
                    )
            except Exception as e:
                self.logger.error(
                    "Failed to ensure category '%s' on instance '%s': %s",
                    self.category,
                    instance_name,
                    str(e).split("\n")[0] if "\n" in str(e) else str(e),
                )

    @staticmethod
    def _humanize_request_tag(tag: str) -> str | None:
        if not tag:
            return None
        cleaned = tag.strip().strip(": ")
        cleaned = cleaned.strip("[]")
        upper = cleaned.upper()
        if "OVERSEERR" in upper:
            return "Overseerr request"
        if "OMBI" in upper:
            return "Ombi request"
        if "PRIORITY SEARCH - TODAY" in upper:
            return "Today's releases"
        return cleaned or None

    def _record_search_activity(
        self,
        description: str | None,
        *,
        context: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.last_search_description = description
        self.last_search_timestamp = datetime.now(timezone.utc).isoformat()
        if detail == "loop-complete":
            detail = "Searches completed, waiting till next loop"
        elif detail == "no-pending-searches":
            detail = "No pending searches"
            self.last_search_description = None if description is None else description
        segments = [
            segment for segment in (context, self.last_search_description, detail) if segment
        ]
        if segments and segments.count("No pending searches") > 1:
            seen = set()
            deduped = []
            for segment in segments:
                key = segment.strip().lower()
                if key == "no pending searches" and key in seen:
                    continue
                seen.add(key)
                deduped.append(segment)
            segments = deduped
        if not segments:
            return
        self.last_search_description = " · ".join(segments)
        record_search_activity(
            str(self.category),
            self.last_search_description,
            self.last_search_timestamp,
        )

    @property
    def is_alive(self) -> bool:
        try:
            if 1 in self.expiring_bool:
                return True
            if self.session is None:
                self.expiring_bool.add(1)
                return True
            req = self.session.get(
                f"{self.uri}/api/v3/system/status",
                timeout=10,
                headers={"X-Api-Key": self.apikey},
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
            # Clear the cache to ensure we retry on next check
            with contextlib.suppress(KeyError):
                self.expiring_bool.remove(1)
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
    def _is_missing_files_torrent(torrent: TorrentDictionary) -> bool:
        """True if torrent is in missing-files state (delete from client, no blacklist)."""
        if torrent.state_enum == TorrentStates.MISSING_FILES:
            return True
        if torrent.state_enum == TorrentStates.ERROR:
            raw = getattr(torrent, "state", None)
            if raw is None and hasattr(torrent, "get"):
                raw = torrent.get("state")
            if isinstance(raw, str):
                return raw == "missingFiles" or "missing" in raw.lower()
        return False

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

    _TAGLESS_FIELD_MAP = {
        "qBitrr-allowed_seeding": "AllowedSeeding",
        "qBitrr-imported": "Imported",
        "qBitrr-allowed_stalled": "AllowedStalled",
        "qBitrr-free_space_paused": "FreeSpacePaused",
    }

    def _ensure_torrent_row(
        self, torrent: TorrentDictionary, instance_name: str = "default"
    ) -> None:
        """Ensure a TorrentLibrary row exists for the given torrent."""
        query = (
            self.torrents.select()
            .where(
                (self.torrents.Hash == torrent.hash)
                & (self.torrents.Category == torrent.category)
                & (self.torrents.QbitInstance == instance_name)
            )
            .execute()
        )
        if not query:
            self.torrents.insert(
                Hash=torrent.hash,
                Category=torrent.category,
                QbitInstance=instance_name,
            ).on_conflict_ignore().execute()

    def _torrent_condition(self, torrent: TorrentDictionary, instance_name: str = "default"):
        """Return the base WHERE condition for a torrent row."""
        return (
            (self.torrents.Hash == torrent.hash)
            & (self.torrents.Category == torrent.category)
            & (self.torrents.QbitInstance == instance_name)
        )

    def in_tags(
        self, torrent: TorrentDictionary, tag: str, instance_name: str = "default"
    ) -> bool:
        return_value = False
        if TAGLESS:
            if tag == "qBitrr-ignored":
                return_value = "qBitrr-ignored" in torrent.tags
            else:
                self._ensure_torrent_row(torrent, instance_name)
                condition = self._torrent_condition(torrent, instance_name)
                field_name = self._TAGLESS_FIELD_MAP.get(tag)
                if field_name:
                    condition &= getattr(self.torrents, field_name) == True
                return_value = bool(self.torrents.select().where(condition).execute())
        else:
            return_value = tag in torrent.tags

        if return_value:
            self.logger.trace("Tag %s in %s", tag, torrent.name)
        else:
            self.logger.trace("Tag %s not in %s", tag, torrent.name)
        return return_value

    def remove_tags(
        self, torrent: TorrentDictionary, tags: list, instance_name: str = "default"
    ) -> None:
        for tag in tags:
            self.logger.trace("Removing tag %s from %s", tag, torrent.name)
        if TAGLESS:
            self._ensure_torrent_row(torrent, instance_name)
            condition = self._torrent_condition(torrent, instance_name)
            for tag in tags:
                field_name = self._TAGLESS_FIELD_MAP.get(tag)
                if field_name:
                    self.torrents.update({getattr(self.torrents, field_name): False}).where(
                        condition
                    ).execute()
        else:
            with contextlib.suppress(Exception):
                with_retry(
                    lambda: torrent.remove_tags(tags),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=(
                        qbittorrentapi.exceptions.APIError,
                        qbittorrentapi.exceptions.APIConnectionError,
                        requests.exceptions.RequestException,
                    ),
                )

    def add_tags(
        self, torrent: TorrentDictionary, tags: list, instance_name: str = "default"
    ) -> None:
        for tag in tags:
            self.logger.trace("Adding tag %s from %s", tag, torrent.name)
        if TAGLESS:
            self._ensure_torrent_row(torrent, instance_name)
            condition = self._torrent_condition(torrent, instance_name)
            for tag in tags:
                field_name = self._TAGLESS_FIELD_MAP.get(tag)
                if field_name:
                    self.torrents.update({getattr(self.torrents, field_name): True}).where(
                        condition
                    ).execute()
        else:
            with contextlib.suppress(Exception):
                with_retry(
                    lambda: torrent.add_tags(tags),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=(
                        qbittorrentapi.exceptions.APIError,
                        qbittorrentapi.exceptions.APIConnectionError,
                        requests.exceptions.RequestException,
                    ),
                )

    def _get_oversee_requests_all(self) -> dict[str, set]:
        try:
            data = defaultdict(set)
            key = "approved" if self.overseerr_approved_only else "unavailable"
            take = 100
            skip = 0
            type_ = None
            if self.type == "radarr":
                type_ = "movie"
            elif self.type == "sonarr":
                type_ = "tv"
            _now = datetime.now()
            while True:
                response = self.session.get(
                    url=f"{self.overseerr_uri}/api/v1/request",
                    headers={"X-Api-Key": self.overseerr_api_key},
                    params={"take": take, "skip": skip, "sort": "added", "filter": key},
                    timeout=5,
                )
                response.raise_for_status()
                payload = response.json()
                results = []
                if isinstance(payload, list):
                    results = payload
                elif isinstance(payload, dict):
                    if isinstance(payload.get("results"), list):
                        results = payload["results"]
                    elif isinstance(payload.get("data"), list):
                        results = payload["data"]
                if not results:
                    break
                for entry in results:
                    # NOTE: 'type' field is not documented in official Overseerr API spec
                    # but exists in practice. May break if Overseerr changes API.
                    type__ = entry.get("type")
                    if not type__:
                        self.logger.debug(
                            "Overseerr request missing 'type' field (entry ID: %s). "
                            "This may indicate an API change.",
                            entry.get("id", "unknown"),
                        )
                        continue
                    if type__ == "movie":
                        id__ = entry.get("media", {}).get("tmdbId")
                    elif type__ == "tv":
                        id__ = entry.get("media", {}).get("tvdbId")
                    else:
                        id__ = None
                    if not id__ or type_ != type__:
                        continue
                    media = entry.get("media") or {}
                    # NOTE: 'status4k' field is not documented in official Overseerr API spec
                    # but exists for 4K request tracking. Falls back to 'status' for non-4K.
                    status_key = "status4k" if entry.get("is4k") else "status"
                    status_value = _normalize_media_status(media.get(status_key))
                    if entry.get("is4k"):
                        if not self.overseerr_is_4k:
                            continue
                    elif self.overseerr_is_4k:
                        continue
                    if self.overseerr_approved_only:
                        if not _is_media_processing(status_value):
                            continue
                    else:
                        if _is_media_available(status_value):
                            continue
                    if id__ in self.overseerr_requests_release_cache:
                        date = self.overseerr_requests_release_cache[id__]
                    else:
                        date = datetime(day=1, month=1, year=1970)
                        date_string_backup = f"{_now.year}-{_now.month:02}-{_now.day:02}"
                        date_string = None
                        try:
                            if type_ == "movie":
                                _entry = self.session.get(
                                    url=f"{self.overseerr_uri}/api/v1/movie/{id__}",
                                    headers={"X-Api-Key": self.overseerr_api_key},
                                    timeout=5,
                                )
                                _entry.raise_for_status()
                                date_string = _entry.json().get("releaseDate")
                            elif type__ == "tv":
                                _entry = self.session.get(
                                    url=f"{self.overseerr_uri}/api/v1/tv/{id__}",
                                    headers={"X-Api-Key": self.overseerr_api_key},
                                    timeout=5,
                                )
                                _entry.raise_for_status()
                                # We don't do granular (episode/season) searched here so no need to
                                # suppose them
                                date_string = _entry.json().get("firstAirDate")
                            if not date_string:
                                date_string = date_string_backup
                            date = datetime.strptime(date_string[:10], "%Y-%m-%d")
                            if date > _now:
                                continue
                            self.overseerr_requests_release_cache[id__] = date
                        except Exception as e:
                            self.logger.warning(
                                "Failed to query release date from Overseerr: %s", e
                            )
                    if media:
                        if imdbId := media.get("imdbId"):
                            data["ImdbId"].add(imdbId)
                        if self.type == "sonarr" and (tvdbId := media.get("tvdbId")):
                            data["TvdbId"].add(tvdbId)
                        elif self.type == "radarr" and (tmdbId := media.get("tmdbId")):
                            data["TmdbId"].add(tmdbId)
                if len(results) < take:
                    break
                skip += take
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
        total = 0
        try:
            response = self.session.get(
                url=f"{self.ombi_uri}{extras}", headers={"ApiKey": self.ombi_api_key}, timeout=5
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                for key in ("total", "count", "totalCount", "totalRecords", "pending", "value"):
                    value = payload.get(key)
                    if isinstance(value, int):
                        total = value
                        break
            elif isinstance(payload, list):
                total = len(payload)
        except Exception as e:
            self.logger.exception(e, exc_info=sys.exc_info())
        return total

    def _get_ombi_requests(self) -> list[dict]:
        if self.type == "sonarr":
            extras = "/api/v1/Request/tvlite"
        elif self.type == "radarr":
            extras = "/api/v1/Request/movie"
        else:
            raise UnhandledError(f"Well you shouldn't have reached here, Arr.type={self.type}")
        try:
            response = self.session.get(
                url=f"{self.ombi_uri}{extras}", headers={"ApiKey": self.ombi_api_key}, timeout=5
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict):
                for key in ("result", "results", "requests", "data", "items"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        return value
            return []
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
            with contextlib.suppress(Exception):
                with_retry(
                    lambda: self.manager.qbit.torrents_pause(torrent_hashes=self.pause),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=(
                        qbittorrentapi.exceptions.APIError,
                        qbittorrentapi.exceptions.APIConnectionError,
                        requests.exceptions.RequestException,
                    ),
                )
            self.pause.clear()

    def _process_imports(self) -> None:
        if self.import_torrents:
            self.needs_cleanup = True
            for torrent, instance_name in self.import_torrents:
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
                    scan_commands = {
                        "sonarr": "DownloadedEpisodesScan",
                        "radarr": "DownloadedMoviesScan",
                        "lidarr": "DownloadedAlbumsScan",
                    }
                    scan_cmd = scan_commands.get(self.type)
                    if scan_cmd:
                        _path = str(path)
                        _hash = torrent.hash.upper()
                        _mode = self.import_mode
                        with_retry(
                            lambda: self.client.post_command(
                                scan_cmd,
                                path=_path,
                                downloadClientId=_hash,
                                importMode=_mode,
                            ),
                            retries=3,
                            backoff=0.5,
                            max_backoff=3,
                            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
                        )
                        self.logger.success("%s: %s", scan_cmd, path)
                except Exception as ex:
                    self.logger.error(
                        "Downloaded scan error: [%s][%s][%s][%s]",
                        path,
                        torrent.hash.upper(),
                        self.import_mode,
                        ex,
                    )
                self.add_tags(torrent, ["qBitrr-imported"], instance_name)
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
                    series_id = None
                    try:
                        data = with_retry(
                            lambda: self.client.get_series(object_ids[0]),
                            retries=5,
                            backoff=0.5,
                            max_backoff=5,
                            exceptions=_ARR_RETRY_EXCEPTIONS,
                        )
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
                    except PyarrResourceNotFound as e:
                        self.logger.warning(
                            "Series %s not found in Sonarr (likely removed): %s",
                            object_ids[0],
                            str(e),
                        )
                    for object_id in object_ids:
                        if object_id in self.queue_file_ids:
                            self.queue_file_ids.remove(object_id)
                    if series_id:
                        self.logger.trace("Research series id: %s", series_id)
                        with_retry(
                            lambda: self.client.post_command(
                                self.search_api_command, seriesId=series_id
                            ),
                            retries=5,
                            backoff=0.5,
                            max_backoff=5,
                            exceptions=_ARR_RETRY_EXCEPTIONS,
                        )
                        if self.persistent_queue:
                            self.persistent_queue.insert(
                                EntryId=series_id, ArrInstance=self._name
                            ).on_conflict_ignore()
                else:
                    for object_id in object_ids:
                        episode_found = False
                        try:
                            data = with_retry(
                                lambda oid=object_id: self.client.get_episode(oid),
                                retries=5,
                                backoff=0.5,
                                max_backoff=5,
                                exceptions=(
                                    requests.exceptions.ChunkedEncodingError,
                                    requests.exceptions.ContentDecodingError,
                                    requests.exceptions.ConnectionError,
                                    JSONDecodeError,
                                    AttributeError,
                                ),
                            )
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
                            episode_found = True
                        except PyarrResourceNotFound as e:
                            self.logger.warning(
                                "Episode %s not found in Sonarr (likely removed): %s",
                                object_id,
                                str(e),
                            )

                        if object_id in self.queue_file_ids:
                            self.queue_file_ids.remove(object_id)
                        if episode_found:
                            with_retry(
                                lambda oid=object_id: self.client.post_command(
                                    "EpisodeSearch", episodeIds=[oid]
                                ),
                                retries=5,
                                backoff=0.5,
                                max_backoff=5,
                                exceptions=_ARR_RETRY_EXCEPTIONS,
                            )
                            if self.persistent_queue:
                                self.persistent_queue.insert(
                                    EntryId=object_id, ArrInstance=self._name
                                ).on_conflict_ignore()
            elif self.type == "radarr":
                self.logger.trace("Requeue cache entry: %s", object_id)
                movie_found = False
                try:
                    data = with_retry(
                        lambda: self.client.get_movie(object_id),
                        retries=5,
                        backoff=0.5,
                        max_backoff=5,
                        exceptions=(
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                            AttributeError,
                        ),
                    )
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
                    movie_found = True
                except PyarrResourceNotFound as e:
                    self.logger.warning(
                        "Movie %s not found in Radarr (likely removed): %s", object_id, str(e)
                    )
                if object_id in self.queue_file_ids:
                    self.queue_file_ids.remove(object_id)
                if movie_found:
                    with_retry(
                        lambda: self.client.post_command("MoviesSearch", movieIds=[object_id]),
                        retries=5,
                        backoff=0.5,
                        max_backoff=5,
                        exceptions=_ARR_RETRY_EXCEPTIONS,
                    )
                    if self.persistent_queue:
                        self.persistent_queue.insert(
                            EntryId=object_id, ArrInstance=self._name
                        ).on_conflict_ignore()
            elif self.type == "lidarr":
                self.logger.trace("Requeue cache entry: %s", object_id)
                album_found = False
                try:
                    data = with_retry(
                        lambda: self.client.get_album(object_id),
                        retries=5,
                        backoff=0.5,
                        max_backoff=5,
                        exceptions=(
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                            AttributeError,
                        ),
                    )
                    name = data.get("title")
                    if name:
                        artist_title = data.get("artist", {}).get("artistName", "")
                        foreign_album_id = data.get("foreignAlbumId", "")
                        self.logger.notice(
                            "Re-Searching album: %s - %s | [foreignAlbumId=%s|id=%s]",
                            artist_title,
                            name,
                            foreign_album_id,
                            object_id,
                        )
                    else:
                        self.logger.notice("Re-Searching album: %s", object_id)
                    album_found = True
                except PyarrResourceNotFound as e:
                    self.logger.warning(
                        "Album %s not found in Lidarr (likely removed): %s", object_id, str(e)
                    )
                if object_id in self.queue_file_ids:
                    self.queue_file_ids.remove(object_id)
                if album_found:
                    with_retry(
                        lambda: self.client.post_command("AlbumSearch", albumIds=[object_id]),
                        retries=5,
                        backoff=0.5,
                        max_backoff=5,
                        exceptions=_ARR_RETRY_EXCEPTIONS,
                    )
                    if self.persistent_queue:
                        self.persistent_queue.insert(
                            EntryId=object_id, ArrInstance=self._name
                        ).on_conflict_ignore()

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
        skip_blacklist = {
            i.upper() for i in self.skip_blacklist.union(self.missing_files_post_delete)
        }
        if (
            to_delete_all
            or self.remove_from_qbit
            or self.skip_blacklist
            or self.remove_from_qbit_by_instance
        ):
            n_delete = len(self.delete)
            n_missing = len(self.missing_files_post_delete)
            n_bad_msg = len(self.downloads_with_bad_error_message_blocklist)
            n_remove = len(self.remove_from_qbit)
            n_remove_by_inst = sum(len(s) for s in self.remove_from_qbit_by_instance.values())
            n_skip = len(self.skip_blacklist)
            self.logger.info(
                "Deletion summary: delete=%d, missing_files=%d, bad_error_blocklist=%d, "
                "remove_from_qbit=%d, remove_by_instance=%d, skip_blacklist=%d",
                n_delete,
                n_missing,
                n_bad_msg,
                n_remove,
                n_remove_by_inst,
                n_skip,
            )
            if to_delete_all and self.logger.isEnabledFor(10):  # DEBUG
                sample = list(to_delete_all)[:5]
                names = [self.manager.qbit_manager.name_cache.get(h, h) for h in sample]
                self.logger.debug(
                    "Deletion sample (first 5): %s",
                    list(zip(sample, names)),
                )
        if to_delete_all:
            self.needs_cleanup = True
            payload = self.process_entries(to_delete_all)
            if payload:
                for entry, hash_ in payload:
                    self._process_failed_individual(
                        hash_=hash_, entry=entry, skip_blacklist=skip_blacklist
                    )
        # Delete missing-files torrents from the correct qBit instance (multi-instance).
        per_instance_hashes = set()
        for hashes in self.remove_from_qbit_by_instance.values():
            per_instance_hashes.update(hashes)
        qbit_manager = self.manager.qbit_manager
        for inst_name, hashes in self.remove_from_qbit_by_instance.items():
            client = qbit_manager.get_client(inst_name)
            if client is None:
                self.logger.warning(
                    "Cannot delete %d torrent(s) from qBit instance '%s': no client",
                    len(hashes),
                    inst_name,
                )
                continue
            try:
                with_retry(
                    lambda c=client, h=list(hashes): c.torrents_delete(
                        hashes=h, delete_files=True
                    ),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=(
                        qbittorrentapi.exceptions.APIError,
                        qbittorrentapi.exceptions.APIConnectionError,
                        requests.exceptions.RequestException,
                    ),
                )
                for h in hashes:
                    self.cleaned_torrents.discard(h)
                    self.sent_to_scan_hashes.discard(h)
                    if h in qbit_manager.name_cache:
                        del qbit_manager.name_cache[h]
                    if h in qbit_manager.cache:
                        del qbit_manager.cache[h]
            except (
                qbittorrentapi.exceptions.APIError,
                qbittorrentapi.exceptions.APIConnectionError,
                requests.exceptions.RequestException,
            ) as e:
                self.logger.error(
                    "Failed to delete %d torrent(s) from qBit instance '%s': %s",
                    len(hashes),
                    inst_name,
                    e,
                )
        self.remove_from_qbit_by_instance.clear()
        to_delete_all = to_delete_all - per_instance_hashes
        if self.remove_from_qbit or self.skip_blacklist or to_delete_all:
            # Remove all bad torrents from the Client.
            deleted_hashes: set[str] = set()
            if to_delete_all:
                try:
                    with_retry(
                        lambda: self.manager.qbit.torrents_delete(
                            hashes=to_delete_all, delete_files=True
                        ),
                        retries=3,
                        backoff=0.5,
                        max_backoff=3,
                        exceptions=(
                            qbittorrentapi.exceptions.APIError,
                            qbittorrentapi.exceptions.APIConnectionError,
                            requests.exceptions.RequestException,
                        ),
                    )
                except (
                    qbittorrentapi.exceptions.APIError,
                    qbittorrentapi.exceptions.APIConnectionError,
                    requests.exceptions.RequestException,
                ) as e:
                    self.logger.error(
                        "Failed to delete %d torrent(s) from qBit: %s",
                        len(to_delete_all),
                        e,
                    )
                else:
                    deleted_hashes.update(to_delete_all)
            if self.remove_from_qbit or self.skip_blacklist:
                temp_to_delete = self.remove_from_qbit.union(self.skip_blacklist)
                try:
                    with_retry(
                        lambda: self.manager.qbit.torrents_delete(
                            hashes=temp_to_delete, delete_files=True
                        ),
                        retries=3,
                        backoff=0.5,
                        max_backoff=3,
                        exceptions=(
                            qbittorrentapi.exceptions.APIError,
                            qbittorrentapi.exceptions.APIConnectionError,
                            requests.exceptions.RequestException,
                        ),
                    )
                except (
                    qbittorrentapi.exceptions.APIError,
                    qbittorrentapi.exceptions.APIConnectionError,
                    requests.exceptions.RequestException,
                ) as e:
                    self.logger.error(
                        "Failed to delete %d torrent(s) from qBit: %s",
                        len(temp_to_delete),
                        e,
                    )
                else:
                    deleted_hashes.update(temp_to_delete)
            for h in deleted_hashes:
                self.cleaned_torrents.discard(h)
                self.sent_to_scan_hashes.discard(h)
                if h in self.manager.qbit_manager.name_cache:
                    del self.manager.qbit_manager.name_cache[h]
                if h in self.manager.qbit_manager.cache:
                    del self.manager.qbit_manager.cache[h]
        if self.missing_files_post_delete or self.downloads_with_bad_error_message_blocklist:
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
            with_retry(
                lambda: self.client.post_command("RssSync"),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
            )
            self.rss_sync_timer_last_checked = now

        if (
            self.refresh_downloads_timer_last_checked is not None
            and self.refresh_downloads_timer_last_checked
            < now - timedelta(minutes=self.refresh_downloads_timer)
        ):
            with_retry(
                lambda: self.client.post_command("RefreshMonitoredDownloads"),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
            )
            self.refresh_downloads_timer_last_checked = now

    def arr_db_query_commands_count(self) -> int:
        search_commands = 0
        if not (self.search_missing or self.do_upgrade_search):
            return 0
        commands = with_retry(
            lambda: self.client.get_command(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
        for command in commands:
            if command["name"].endswith("Search") and command["status"] != "completed":
                search_commands = search_commands + 1

        return search_commands

    def _search_todays(self, condition):
        if self.prioritize_todays_release:
            # Order searches by priority: Missing > CustomFormat > Quality > Upgrade
            from peewee import Case

            reason_priority = Case(
                None,
                (
                    (self.model_file.Reason == "Missing", 1),
                    (self.model_file.Reason == "CustomFormat", 2),
                    (self.model_file.Reason == "Quality", 3),
                    (self.model_file.Reason == "Upgrade", 4),
                ),
                5,  # Default priority for other reasons
            )

            for entry in (
                self.model_file.select()
                .where(condition)
                .order_by(
                    reason_priority.asc(),  # Primary: order by reason priority
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
        if self.type == "sonarr" and self.series_search is True:
            serieslist = self.db_get_files_series()
            for series in serieslist:
                yield series[0], series[1], series[2], series[2] is not True, len(serieslist)
        elif self.type == "sonarr" and self.series_search == "smart":
            # Smart mode: decide dynamically based on what needs to be searched
            episodelist = self.db_get_files_episodes()
            if episodelist:
                # Group episodes by series to determine if we should search by series or episode
                series_episodes_map = {}
                for episode_entry in episodelist:
                    episode = episode_entry[0]
                    series_id = episode.SeriesId
                    if series_id not in series_episodes_map:
                        series_episodes_map[series_id] = []
                    series_episodes_map[series_id].append(episode_entry)

                # Process each series
                for series_id, episodes in series_episodes_map.items():
                    if len(episodes) > 1:
                        # Multiple episodes from same series - use series search (smart decision)
                        self.logger.info(
                            "[SMART MODE] Using series search for %s episodes from series ID %s",
                            len(episodes),
                            series_id,
                        )
                        # Create a series entry for searching
                        series_model = (
                            self.series_file_model.select()
                            .where(
                                (self.series_file_model.EntryId == series_id)
                                & (self.series_file_model.ArrInstance == self._name)
                            )
                            .first()
                        )
                        if series_model:
                            yield series_model, episodes[0][1], episodes[0][2], True, len(
                                episodelist
                            )
                    else:
                        # Single episode - use episode search (smart decision)
                        episode = episodes[0][0]
                        self.logger.info(
                            "[SMART MODE] Using episode search for single episode: %s S%02dE%03d",
                            episode.SeriesTitle,
                            episode.SeasonNumber,
                            episode.EpisodeNumber,
                        )
                        yield episodes[0][0], episodes[0][1], episodes[0][2], False, len(
                            episodelist
                        )
        elif self.type == "sonarr" and self.series_search == False:
            episodelist = self.db_get_files_episodes()
            for episodes in episodelist:
                yield episodes[0], episodes[1], episodes[2], False, len(episodelist)
        elif self.type == "radarr":
            movielist = self.db_get_files_movies()
            for movies in movielist:
                yield movies[0], movies[1], movies[2], False, len(movielist)
        elif self.type == "lidarr":
            albumlist = self.db_get_files_movies()  # This calls the lidarr section we added
            for albums in albumlist:
                yield albums[0], albums[1], albums[2], False, len(albumlist)

    def db_maybe_reset_entry_searched_state(self):
        if self.type == "sonarr":
            self.db_reset__series_searched_state()
            self.db_reset__episode_searched_state()
        elif self.type == "radarr":
            self.db_reset__movie_searched_state()
        elif self.type == "lidarr":
            self.db_reset__album_searched_state()
        self.loop_completed = False

    def db_reset__series_searched_state(self):
        ids = []
        self.series_file_model: SeriesFilesModel
        self.model_file: EpisodeFilesModel
        if (
            self.loop_completed and self.reset_on_completion and self.series_search
        ):  # Only wipe if a loop completed was tagged
            self.series_file_model.update(Searched=False, Upgrade=False).where(
                (self.series_file_model.Searched == True)
                & (self.series_file_model.ArrInstance == self._name)
            ).execute()
            series = with_retry(
                lambda: self.client.get_series(),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
            for s in series:
                ids.append(s["id"])
            self.series_file_model.delete().where(
                (self.series_file_model.EntryId.not_in(ids))
                & (self.series_file_model.ArrInstance == self._name)
            ).execute()
            self.loop_completed = False

    def db_reset__episode_searched_state(self):
        ids = []
        self.model_file: EpisodeFilesModel
        if (
            self.loop_completed is True and self.reset_on_completion
        ):  # Only wipe if a loop completed was tagged
            self.model_file.update(Searched=False, Upgrade=False).where(
                (self.model_file.Searched == True) & (self.model_file.ArrInstance == self._name)
            ).execute()
            series = with_retry(
                lambda: self.client.get_series(),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
            for s in series:
                episodes = with_retry(
                    lambda s=s: self.client.get_episode(s["id"], True),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )
                for e in episodes:
                    ids.append(e["id"])
            self.model_file.delete().where(
                (self.model_file.EntryId.not_in(ids)) & (self.model_file.ArrInstance == self._name)
            ).execute()
            self.loop_completed = False

    def db_reset__movie_searched_state(self):
        ids = []
        self.model_file: MoviesFilesModel
        if (
            self.loop_completed is True and self.reset_on_completion
        ):  # Only wipe if a loop completed was tagged
            self.model_file.update(Searched=False, Upgrade=False).where(
                (self.model_file.Searched == True) & (self.model_file.ArrInstance == self._name)
            ).execute()
            movies = with_retry(
                lambda: self.client.get_movie(),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
            for m in movies:
                ids.append(m["id"])
            self.model_file.delete().where(
                (self.model_file.EntryId.not_in(ids)) & (self.model_file.ArrInstance == self._name)
            ).execute()
            self.loop_completed = False

    def db_reset__album_searched_state(self):
        ids = []
        self.model_file: AlbumFilesModel
        if (
            self.loop_completed is True and self.reset_on_completion
        ):  # Only wipe if a loop completed was tagged
            self.model_file.update(Searched=False, Upgrade=False).where(
                (self.model_file.Searched == True) & (self.model_file.ArrInstance == self._name)
            ).execute()
            artists = with_retry(
                lambda: self.client.get_artist(),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
            for artist in artists:
                albums = with_retry(
                    lambda a=artist: self.client.get_album(artistId=a["id"]),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )
                for album in albums:
                    ids.append(album["id"])
            self.model_file.delete().where(
                (self.model_file.EntryId.not_in(ids)) & (self.model_file.ArrInstance == self._name)
            ).execute()
            self.loop_completed = False

    def db_get_files_series(self) -> list[list[SeriesFilesModel, bool, bool]] | None:
        entries = []
        if not (self.search_missing or self.do_upgrade_search):
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
                    condition &= (self.model_file.Searched == False) | (
                        self.model_file.QualityMet == False
                    )
                elif not self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (self.model_file.Searched == False) | (
                        self.model_file.CustomFormatMet == False
                    )
                elif self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (
                        (self.model_file.Searched == False)
                        | (self.model_file.QualityMet == False)
                        | (self.model_file.CustomFormatMet == False)
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
                condition = (self.series_file_model.Searched == False) & (
                    self.series_file_model.ArrInstance == self._name
                )
            else:
                condition = (self.series_file_model.Upgrade == False) & (
                    self.series_file_model.ArrInstance == self._name
                )

            # Collect series entries with their priority based on episode reasons
            # Missing > CustomFormat > Quality > Upgrade
            series_entries = []
            for entry_ in self.series_file_model.select().where(condition).execute():
                # Get the highest priority reason from this series' episodes
                reason_priority_map = {
                    "Missing": 1,
                    "CustomFormat": 2,
                    "Quality": 3,
                    "Upgrade": 4,
                }
                # Find the minimum priority (highest importance) reason for this series
                min_priority = 5  # Default
                episode_reasons = (
                    self.model_file.select(self.model_file.Reason)
                    .where(self.model_file.SeriesId == entry_.EntryId)
                    .execute()
                )
                for ep in episode_reasons:
                    if ep.Reason:
                        priority = reason_priority_map.get(ep.Reason, 5)
                        min_priority = min(min_priority, priority)

                series_entries.append((entry_, min_priority))

            # Sort by priority, then by EntryId
            series_entries.sort(key=lambda x: (x[1], x[0].EntryId))

            for entry_, _ in series_entries:
                self.logger.trace("Adding %s to search list", entry_.Title)
                entries.append([entry_, False, False])
            return entries

    def db_get_files_episodes(self) -> list[list[EpisodeFilesModel, bool, bool]] | None:
        entries = []
        if not (self.search_missing or self.do_upgrade_search):
            return None
        elif self.type == "sonarr":
            condition = (self.model_file.AirDateUtc.is_null(False)) & (
                self.model_file.ArrInstance == self._name
            )
            if not self.search_specials:
                condition &= self.model_file.SeasonNumber != 0
            if self.do_upgrade_search:
                condition &= self.model_file.Upgrade == False
            else:
                if self.quality_unmet_search and not self.custom_format_unmet_search:
                    condition &= (self.model_file.Searched == False) | (
                        self.model_file.QualityMet == False
                    )
                elif not self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (self.model_file.Searched == False) | (
                        self.model_file.CustomFormatMet == False
                    )
                elif self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (
                        (self.model_file.Searched == False)
                        | (self.model_file.QualityMet == False)
                        | (self.model_file.CustomFormatMet == False)
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
            # Order searches by priority: Missing > CustomFormat > Quality > Upgrade
            # Use CASE to assign priority values to each reason
            from peewee import Case

            reason_priority = Case(
                None,
                (
                    (self.model_file.Reason == "Missing", 1),
                    (self.model_file.Reason == "CustomFormat", 2),
                    (self.model_file.Reason == "Quality", 3),
                    (self.model_file.Reason == "Upgrade", 4),
                ),
                5,  # Default priority for other reasons
            )

            for entry in (
                self.model_file.select()
                .where(condition)
                .group_by(self.model_file.SeriesId)
                .order_by(
                    reason_priority.asc(),
                    self.model_file.EpisodeFileId.asc(),
                    self.model_file.SeriesTitle,
                    self.model_file.SeasonNumber.desc(),
                    self.model_file.AirDateUtc.desc(),
                )
                .execute()
            ):
                entries.append([entry, False, False])
            for i1, i2, i3 in self._search_todays(today_condition):
                if i1 is not None:
                    entries.append([i1, i2, i3])
            return entries

    def db_get_files_movies(self) -> list[list[MoviesFilesModel, bool, bool]] | None:
        entries = []
        if not (self.search_missing or self.do_upgrade_search):
            return None
        if self.type == "radarr":
            condition = (self.model_file.Year.is_null(False)) & (
                self.model_file.ArrInstance == self._name
            )
            if self.do_upgrade_search:
                condition &= self.model_file.Upgrade == False
            else:
                if self.quality_unmet_search and not self.custom_format_unmet_search:
                    condition &= (self.model_file.Searched == False) | (
                        self.model_file.QualityMet == False
                    )
                elif not self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (self.model_file.Searched == False) | (
                        self.model_file.CustomFormatMet == False
                    )
                elif self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (
                        (self.model_file.Searched == False)
                        | (self.model_file.QualityMet == False)
                        | (self.model_file.CustomFormatMet == False)
                    )
                else:
                    condition &= self.model_file.MovieFileId == 0
                    condition &= self.model_file.Searched == False
            if self.search_by_year:
                condition &= self.model_file.Year == self.search_current_year

            # Order searches by priority: Missing > CustomFormat > Quality > Upgrade
            # Use CASE to assign priority values to each reason
            from peewee import Case

            reason_priority = Case(
                None,
                (
                    (self.model_file.Reason == "Missing", 1),
                    (self.model_file.Reason == "CustomFormat", 2),
                    (self.model_file.Reason == "Quality", 3),
                    (self.model_file.Reason == "Upgrade", 4),
                ),
                5,  # Default priority for other reasons
            )

            for entry in (
                self.model_file.select()
                .where(condition)
                .order_by(
                    reason_priority.asc(),  # Primary: order by reason priority
                    self.model_file.MovieFileId.asc(),
                )
                .execute()
            ):
                entries.append([entry, False, False])
            return entries
        elif self.type == "lidarr":
            condition = self.model_file.ArrInstance == self._name
            if self.do_upgrade_search:
                condition &= self.model_file.Upgrade == False
            else:
                if self.quality_unmet_search and not self.custom_format_unmet_search:
                    condition &= (self.model_file.Searched == False) | (
                        self.model_file.QualityMet == False
                    )
                elif not self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (self.model_file.Searched == False) | (
                        self.model_file.CustomFormatMet == False
                    )
                elif self.quality_unmet_search and self.custom_format_unmet_search:
                    condition &= (
                        (self.model_file.Searched == False)
                        | (self.model_file.QualityMet == False)
                        | (self.model_file.CustomFormatMet == False)
                    )
                else:
                    condition &= self.model_file.AlbumFileId == 0
                    condition &= self.model_file.Searched == False

            # Order searches by priority: Missing > CustomFormat > Quality > Upgrade
            # Use CASE to assign priority values to each reason
            from peewee import Case

            reason_priority = Case(
                None,
                (
                    (self.model_file.Reason == "Missing", 1),
                    (self.model_file.Reason == "CustomFormat", 2),
                    (self.model_file.Reason == "Quality", 3),
                    (self.model_file.Reason == "Upgrade", 4),
                ),
                5,  # Default priority for other reasons
            )

            for entry in (
                self.model_file.select()
                .where(condition)
                .order_by(
                    reason_priority.asc(),  # Primary: order by reason priority
                    self.model_file.AlbumFileId.asc(),
                )
                .execute()
            ):
                entries.append([entry, False, False])
            return entries

    def db_get_request_files(self) -> Iterable[tuple[MoviesFilesModel | EpisodeFilesModel, int]]:
        entries = []
        self.logger.trace("Getting request files")
        if self.type == "sonarr":
            condition = (self.model_file.IsRequest == True) & (
                self.model_file.ArrInstance == self._name
            )
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
            condition = (self.model_file.IsRequest == True) & (
                self.model_file.ArrInstance == self._name
            )
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
            series = with_retry(
                lambda: self.client.get_series(),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
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
            movies = with_retry(
                lambda: self.client.get_movie(),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
            for m in movies:
                if m["year"] > datetime.now().year or m["year"] == 0:
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
                series = with_retry(
                    lambda: self.client.get_series(),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )
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
            except Exception:
                self.logger.debug("No episode releases found for today")

    def db_update(self):
        if not (
            self.search_missing
            or self.do_upgrade_search
            or self.quality_unmet_search
            or self.custom_format_unmet_search
        ):
            return
        placeholder_summary = "Updating database"
        placeholder_set = False
        try:
            self._webui_db_loaded = False
            try:
                self._record_search_activity(placeholder_summary)
                placeholder_set = True
            except Exception:
                pass
            self.db_update_todays_releases()
            if self.db_update_processed:
                return
            self.logger.info("Started updating database")
            if self.type == "sonarr":
                # Always fetch series list for both episode and series-level tracking
                series = with_retry(
                    lambda: self.client.get_series(),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )

                # Process episodes for episode-level tracking (all episodes)
                for s in series:
                    if isinstance(s, str):
                        continue
                    episodes = self.client.get_episode(s["id"], True)
                    for e in episodes:
                        if isinstance(e, str):
                            continue
                        if "airDateUtc" in e:
                            if datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                                tzinfo=timezone.utc
                            ) > datetime.now(timezone.utc):
                                continue
                            if not self.search_specials and e["seasonNumber"] == 0:
                                continue
                            self.db_update_single_series(db_entry=e, series=False)

                # Process series for series-level tracking (all series)
                for s in series:
                    if isinstance(s, str):
                        continue
                    self.db_update_single_series(db_entry=s, series=True)

                self.db_update_processed = True
            elif self.type == "radarr":
                movies = with_retry(
                    lambda: self.client.get_movie(),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )
                # Process all movies
                for m in movies:
                    if isinstance(m, str):
                        continue
                    self.db_update_single_series(db_entry=m)
                self.db_update_processed = True
            elif self.type == "lidarr":
                artists = with_retry(
                    lambda: self.client.get_artist(),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )
                for artist in artists:
                    if isinstance(artist, str):
                        continue
                    albums = with_retry(
                        lambda a=artist: self.client.get_album(
                            artistId=a["id"], allArtistAlbums=True
                        ),
                        retries=5,
                        backoff=0.5,
                        max_backoff=5,
                        exceptions=_ARR_RETRY_EXCEPTIONS,
                    )
                    for album in albums:
                        if isinstance(album, str):
                            continue
                        # For Lidarr, we don't have a specific releaseDate field
                        # Check if album has been released
                        if "releaseDate" in album:
                            release_date = datetime.strptime(
                                album["releaseDate"], "%Y-%m-%dT%H:%M:%SZ"
                            )
                            if release_date > datetime.now():
                                continue
                        self.db_update_single_series(db_entry=album)
                # Process artists for artist-level tracking
                for artist in artists:
                    if isinstance(artist, str):
                        continue
                    self.db_update_single_series(db_entry=artist, artist=True)
                self.db_update_processed = True
            self.logger.trace("Finished updating database")
        finally:
            if placeholder_set:
                try:
                    activities = fetch_search_activities()
                    entry = activities.get(str(self.category))
                    if entry and entry.get("summary") == placeholder_summary:
                        clear_search_activity(str(self.category))
                except Exception:
                    pass
            self._webui_db_loaded = True

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
        self,
        db_entry: JsonObject = None,
        request: bool = False,
        series: bool = False,
        artist: bool = False,
    ):
        if not (
            self.search_missing
            or self.do_upgrade_search
            or self.quality_unmet_search
            or self.custom_format_unmet_search
        ):
            return
        try:
            searched = False
            if self.type == "sonarr":
                if not series:
                    self.model_file: EpisodeFilesModel
                    episodeData = self.model_file.get_or_none(
                        (self.model_file.EntryId == db_entry["id"])
                        & (self.model_file.ArrInstance == self._name)
                    )
                    episode = with_retry(
                        lambda: self.client.get_episode(db_entry["id"]),
                        retries=5,
                        backoff=0.5,
                        max_backoff=5,
                        exceptions=_ARR_RETRY_EXCEPTIONS,
                    )

                    # Validate episode object has required fields
                    if not episode or not isinstance(episode, dict):
                        self.logger.warning(
                            "Invalid episode object returned from API for episode ID %s: %s",
                            db_entry.get("id"),
                            type(episode).__name__,
                        )
                        return

                    required_fields = [
                        "id",
                        "seriesId",
                        "seasonNumber",
                        "episodeNumber",
                        "title",
                        "airDateUtc",
                        "episodeFileId",
                    ]
                    missing_fields = [field for field in required_fields if field not in episode]
                    if missing_fields:
                        self.logger.warning(
                            "Episode %s missing required fields %s. Episode data: %s",
                            db_entry.get("id"),
                            missing_fields,
                            episode,
                        )
                        return

                    if episode.get("monitored", True) or self.search_unmonitored:
                        series_info = episode.get("series") or {}
                        if isinstance(series_info, dict):
                            quality_profile_id = series_info.get("qualityProfileId")
                        else:
                            quality_profile_id = getattr(series_info, "qualityProfileId", None)
                        if not quality_profile_id:
                            quality_profile_id = db_entry.get("qualityProfileId")
                        minCustomFormat = (
                            getattr(episodeData, "MinCustomFormatScore", 0) if episodeData else 0
                        )
                        if not minCustomFormat:
                            if quality_profile_id:
                                profile = (
                                    with_retry(
                                        lambda qpid=quality_profile_id: self.client.get_quality_profile(
                                            qpid
                                        ),
                                        retries=5,
                                        backoff=0.5,
                                        max_backoff=5,
                                        exceptions=_ARR_RETRY_EXCEPTIONS,
                                    )
                                    or {}
                                )
                                minCustomFormat = profile.get("minFormatScore") or 0
                            else:
                                self.logger.warning(
                                    "Episode %s missing qualityProfileId; defaulting custom format threshold to 0",
                                    episode.get("id"),
                                )
                                minCustomFormat = 0
                        episode_file = episode.get("episodeFile") or {}
                        if isinstance(episode_file, dict):
                            episode_file_id = episode_file.get("id")
                        else:
                            episode_file_id = getattr(episode_file, "id", None)
                        has_file = bool(episode.get("hasFile"))
                        episode_data_file_id = (
                            getattr(episodeData, "EpisodeFileId", None) if episodeData else None
                        )
                        if has_file and episode_file_id:
                            if episode_data_file_id and episode_file_id == episode_data_file_id:
                                customFormat = getattr(episodeData, "CustomFormatScore", 0)
                            else:
                                file_info = (
                                    with_retry(
                                        lambda efid=episode_file_id: self.client.get_episode_file(
                                            efid
                                        ),
                                        retries=5,
                                        backoff=0.5,
                                        max_backoff=5,
                                        exceptions=_ARR_RETRY_EXCEPTIONS,
                                    )
                                    or {}
                                )
                                customFormat = file_info.get("customFormatScore") or 0
                        else:
                            customFormat = 0

                        QualityUnmet = (
                            episode["episodeFile"]["qualityCutoffNotMet"]
                            if "episodeFile" in episode
                            else False
                        )
                        if (
                            episode.get("hasFile", False)
                            and not (self.quality_unmet_search and QualityUnmet)
                            and not (
                                self.custom_format_unmet_search and customFormat < minCustomFormat
                            )
                        ):
                            searched = True
                            self.model_queue.update(Completed=True).where(
                                (self.model_queue.EntryId == episode["id"])
                                & (self.model_queue.ArrInstance == self._name)
                            ).execute()

                        if self.use_temp_for_missing:
                            data = None
                            quality_profile_id = db_entry.get("qualityProfileId")
                            # Only apply temp profiles for truly missing content (no file)
                            # Do NOT apply for quality/custom format unmet or upgrade searches
                            has_file = episode.get("hasFile", False)
                            profile_switch_timestamp = None
                            original_profile_for_db = None
                            current_profile_for_db = None

                            self.logger.trace(
                                "Temp quality profile check for '%s': searched=%s, has_file=%s, current_profile_id=%s, keep_temp=%s",
                                db_entry.get("title", "Unknown"),
                                searched,
                                has_file,
                                quality_profile_id,
                                self.keep_temp_profile,
                            )
                            if (
                                searched
                                and quality_profile_id in self.main_quality_profile_ids.keys()
                                and not self.keep_temp_profile
                            ):
                                new_profile_id = self.main_quality_profile_ids.get(
                                    quality_profile_id
                                )
                                if new_profile_id is None:
                                    self.logger.warning(
                                        f"Profile ID {quality_profile_id} not found in current temp→main mappings. "
                                        "Config may have changed. Skipping profile upgrade."
                                    )
                                else:
                                    data: JsonObject = {"qualityProfileId": new_profile_id}
                                    self.logger.info(
                                        "Upgrading quality profile for '%s': temp profile (ID:%s) → main profile (ID:%s) [Episode searched, reverting to main]",
                                        db_entry.get("title", "Unknown"),
                                        quality_profile_id,
                                        new_profile_id,
                                    )
                                # Reverting to main - clear tracking fields
                                profile_switch_timestamp = datetime.now()
                                original_profile_for_db = None
                                current_profile_for_db = None
                            elif (
                                not searched
                                and not has_file
                                and quality_profile_id in self.temp_quality_profile_ids.keys()
                            ):
                                new_profile_id = self.temp_quality_profile_ids[quality_profile_id]
                                data: JsonObject = {"qualityProfileId": new_profile_id}
                                self.logger.info(
                                    "Downgrading quality profile for '%s': main profile (ID:%s) → temp profile (ID:%s) [Episode not searched yet]",
                                    db_entry.get("title", "Unknown"),
                                    quality_profile_id,
                                    new_profile_id,
                                )
                                # Downgrading to temp - track original and switch time
                                profile_switch_timestamp = datetime.now()
                                original_profile_for_db = quality_profile_id
                                current_profile_for_db = new_profile_id
                            else:
                                self.logger.trace(
                                    "No quality profile change for '%s': searched=%s, profile_id=%s (in_temps=%s, in_mains=%s)",
                                    db_entry.get("title", "Unknown"),
                                    searched,
                                    quality_profile_id,
                                    quality_profile_id in self.temp_quality_profile_ids.values(),
                                    quality_profile_id in self.temp_quality_profile_ids.keys(),
                                )
                            if data:
                                profile_update_success = False
                                for attempt in range(self.profile_switch_retry_attempts):
                                    try:
                                        self.client.upd_episode(episode["id"], data)
                                        profile_update_success = True
                                        break
                                    except (
                                        requests.exceptions.ChunkedEncodingError,
                                        requests.exceptions.ContentDecodingError,
                                        requests.exceptions.ConnectionError,
                                        JSONDecodeError,
                                    ) as e:
                                        if attempt == self.profile_switch_retry_attempts - 1:
                                            self.logger.error(
                                                "Failed to update episode profile after %d attempts: %s",
                                                self.profile_switch_retry_attempts,
                                                e,
                                            )
                                            break
                                        time.sleep(1)
                                        continue

                                # If profile update failed, don't track the change
                                if not profile_update_success:
                                    profile_switch_timestamp = None
                                    original_profile_for_db = None
                                    current_profile_for_db = None

                        EntryId = episode.get("id")
                        SeriesTitle = episode.get("series", {}).get("title")
                        SeasonNumber = episode.get("seasonNumber")
                        Title = episode.get("title")
                        SeriesId = episode.get("seriesId")
                        EpisodeFileId = episode.get("episodeFileId")
                        EpisodeNumber = episode.get("episodeNumber")
                        AbsoluteEpisodeNumber = (
                            episode.get("absoluteEpisodeNumber")
                            if "absoluteEpisodeNumber" in episode
                            else None
                        )
                        SceneAbsoluteEpisodeNumber = (
                            episode.get("sceneAbsoluteEpisodeNumber")
                            if "sceneAbsoluteEpisodeNumber" in episode
                            else None
                        )
                        AirDateUtc = episode.get("airDateUtc")
                        Monitored = episode.get("monitored", True)
                        QualityMet = not QualityUnmet if db_entry["hasFile"] else False
                        customFormatMet = customFormat >= minCustomFormat

                        if not episode.get("hasFile", False):
                            # Episode is missing a file - always mark as Missing
                            reason = "Missing"
                        elif self.quality_unmet_search and QualityUnmet:
                            reason = "Quality"
                        elif self.custom_format_unmet_search and not customFormatMet:
                            reason = "CustomFormat"
                        elif self.do_upgrade_search:
                            reason = "Upgrade"
                        elif searched:
                            # Episode has file and search is complete
                            reason = "Not being searched"
                        else:
                            reason = "Not being searched"

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

                        # Add profile tracking fields if temp profile feature is enabled
                        if self.use_temp_for_missing and profile_switch_timestamp is not None:
                            to_update[self.model_file.LastProfileSwitchTime] = (
                                profile_switch_timestamp
                            )
                            to_update[self.model_file.OriginalProfileId] = original_profile_for_db
                            to_update[self.model_file.CurrentProfileId] = current_profile_for_db

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
                            ArrInstance=self._name,
                        ).on_conflict(conflict_target=[self.model_file.EntryId], update=to_update)
                        db_commands.execute()
                    else:
                        db_commands = self.model_file.delete().where(
                            (self.model_file.EntryId == episode["id"])
                            & (self.model_file.ArrInstance == self._name)
                        )
                        db_commands.execute()
                else:
                    self.series_file_model: SeriesFilesModel
                    EntryId = db_entry["id"]
                    seriesData = self.series_file_model.get_or_none(
                        (self.series_file_model.EntryId == EntryId)
                        & (self.series_file_model.ArrInstance == self._name)
                    )
                    if db_entry["monitored"] or self.search_unmonitored:
                        seriesMetadata = (
                            with_retry(
                                lambda eid=EntryId: self.client.get_series(id_=eid),
                                retries=5,
                                backoff=0.5,
                                max_backoff=5,
                                exceptions=_ARR_RETRY_EXCEPTIONS,
                            )
                            or {}
                        )
                        quality_profile_id = None
                        if isinstance(seriesMetadata, dict):
                            quality_profile_id = seriesMetadata.get("qualityProfileId")
                        else:
                            quality_profile_id = getattr(seriesMetadata, "qualityProfileId", None)
                        if not seriesData:
                            if quality_profile_id:
                                profile = (
                                    with_retry(
                                        lambda qpid=quality_profile_id: self.client.get_quality_profile(
                                            qpid
                                        ),
                                        retries=5,
                                        backoff=0.5,
                                        max_backoff=5,
                                        exceptions=_ARR_RETRY_EXCEPTIONS,
                                    )
                                    or {}
                                )
                                minCustomFormat = profile.get("minFormatScore") or 0
                            else:
                                self.logger.warning(
                                    "Series %s (%s) missing qualityProfileId; "
                                    "defaulting custom format score to 0",
                                    db_entry.get("title"),
                                    EntryId,
                                )
                                minCustomFormat = 0
                        else:
                            minCustomFormat = getattr(seriesData, "MinCustomFormatScore", 0)
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
                        # Sonarr series-level temp profile logic
                        # NOTE: Sonarr only supports quality profiles at the series level (not episode level).
                        # Individual episodes inherit the series profile. This is intentional and correct.
                        # If ANY episodes are missing, the entire series uses temp profile to maximize
                        # the chance of finding missing content (priority #1).
                        if self.use_temp_for_missing:
                            try:
                                quality_profile_id = db_entry.get("qualityProfileId")
                                if (
                                    searched
                                    and quality_profile_id in self.main_quality_profile_ids.keys()
                                    and not self.keep_temp_profile
                                ):
                                    new_main_id = self.main_quality_profile_ids[quality_profile_id]
                                    db_entry["qualityProfileId"] = new_main_id
                                    self.logger.debug(
                                        "Updating quality profile for %s to %s",
                                        db_entry["title"],
                                        new_main_id,
                                    )
                                elif (
                                    not searched
                                    and quality_profile_id in self.temp_quality_profile_ids.keys()
                                ):
                                    new_temp_id = self.temp_quality_profile_ids[quality_profile_id]
                                    db_entry["qualityProfileId"] = new_temp_id
                                    self.logger.debug(
                                        "Updating quality profile for %s to %s",
                                        db_entry["title"],
                                        new_temp_id,
                                    )
                            except KeyError:
                                self.logger.warning(
                                    "Check quality profile settings for %s", db_entry["title"]
                                )
                            for attempt in range(self.profile_switch_retry_attempts):
                                try:
                                    self.client.upd_series(db_entry)
                                    break
                                except (
                                    requests.exceptions.ChunkedEncodingError,
                                    requests.exceptions.ContentDecodingError,
                                    requests.exceptions.ConnectionError,
                                    JSONDecodeError,
                                ) as e:
                                    if attempt == self.profile_switch_retry_attempts - 1:
                                        self.logger.error(
                                            "Failed to update series profile after %d attempts: %s",
                                            self.profile_switch_retry_attempts,
                                            e,
                                        )
                                        break
                                    time.sleep(1)
                                    continue

                        Title = seriesMetadata.get("title")
                        Monitored = db_entry["monitored"]

                        # Get quality profile info
                        qualityProfileName = None
                        if quality_profile_id:
                            try:
                                if quality_profile_id not in self._quality_profile_cache:
                                    profile = self.client.get_quality_profile(quality_profile_id)
                                    self._quality_profile_cache[quality_profile_id] = profile
                                qualityProfileName = self._quality_profile_cache[
                                    quality_profile_id
                                ].get("name")
                            except Exception:
                                pass

                        to_update = {
                            self.series_file_model.Monitored: Monitored,
                            self.series_file_model.Title: Title,
                            self.series_file_model.Searched: searched,
                            self.series_file_model.Upgrade: False,
                            self.series_file_model.MinCustomFormatScore: minCustomFormat,
                            self.series_file_model.QualityProfileId: quality_profile_id,
                            self.series_file_model.QualityProfileName: qualityProfileName,
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
                            QualityProfileId=quality_profile_id,
                            QualityProfileName=qualityProfileName,
                            ArrInstance=self._name,
                        ).on_conflict(
                            conflict_target=[self.series_file_model.EntryId], update=to_update
                        )
                        db_commands.execute()

                        # Note: Episodes are now handled separately in db_update()
                        # No need to recursively process episodes here to avoid duplication
                    else:
                        db_commands = self.series_file_model.delete().where(
                            (self.series_file_model.EntryId == EntryId)
                            & (self.series_file_model.ArrInstance == self._name)
                        )
                        db_commands.execute()

            elif self.type == "radarr":
                self.model_file: MoviesFilesModel
                searched = False
                movieData = self.model_file.get_or_none(
                    (self.model_file.EntryId == db_entry["id"])
                    & (self.model_file.ArrInstance == self._name)
                )
                if self.minimum_availability_check(db_entry) and (
                    db_entry["monitored"] or self.search_unmonitored
                ):
                    _retry_exc = (
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ConnectionError,
                        JSONDecodeError,
                    )
                    if movieData:
                        if not movieData.MinCustomFormatScore:
                            profile = (
                                with_retry(
                                    lambda: self.client.get_quality_profile(
                                        db_entry["qualityProfileId"]
                                    ),
                                    retries=5,
                                    backoff=0.5,
                                    max_backoff=5,
                                    exceptions=_retry_exc,
                                )
                                or {}
                            )
                            minCustomFormat = profile.get("minFormatScore", 0)
                        else:
                            minCustomFormat = movieData.MinCustomFormatScore
                        if db_entry["hasFile"]:
                            if db_entry["movieFile"]["id"] != movieData.MovieFileId:
                                customFormat = with_retry(
                                    lambda: self.client.get_movie_file(
                                        db_entry["movieFile"]["id"]
                                    ),
                                    retries=5,
                                    backoff=0.5,
                                    max_backoff=5,
                                    exceptions=_retry_exc,
                                )["customFormatScore"]
                            else:
                                customFormat = movieData.CustomFormatScore
                        else:
                            customFormat = 0
                    else:
                        profile = (
                            with_retry(
                                lambda: self.client.get_quality_profile(
                                    db_entry["qualityProfileId"]
                                ),
                                retries=5,
                                backoff=0.5,
                                max_backoff=5,
                                exceptions=_retry_exc,
                            )
                            or {}
                        )
                        minCustomFormat = profile.get("minFormatScore", 0)
                        if db_entry["hasFile"]:
                            customFormat = with_retry(
                                lambda: self.client.get_movie_file(db_entry["movieFile"]["id"]),
                                retries=5,
                                backoff=0.5,
                                max_backoff=5,
                                exceptions=_retry_exc,
                            ).get("customFormatScore", 0)
                        else:
                            customFormat = 0
                    QualityUnmet = (
                        db_entry["movieFile"]["qualityCutoffNotMet"]
                        if "movieFile" in db_entry
                        else False
                    )
                    if (
                        db_entry["hasFile"]
                        and not (self.quality_unmet_search and QualityUnmet)
                        and not (
                            self.custom_format_unmet_search and customFormat < minCustomFormat
                        )
                    ):
                        searched = True
                        self.model_queue.update(Completed=True).where(
                            (self.model_queue.EntryId == db_entry["id"])
                            & (self.model_queue.ArrInstance == self._name)
                        ).execute()

                    profile_switch_timestamp = None
                    original_profile_for_db = None
                    current_profile_for_db = None

                    if self.use_temp_for_missing:
                        quality_profile_id = db_entry.get("qualityProfileId")
                        # Only apply temp profiles for truly missing content (no file)
                        # Do NOT apply for quality/custom format unmet or upgrade searches
                        has_file = db_entry.get("hasFile", False)
                        if (
                            searched
                            and quality_profile_id in self.main_quality_profile_ids.keys()
                            and not self.keep_temp_profile
                        ):
                            new_main_id = self.main_quality_profile_ids[quality_profile_id]
                            db_entry["qualityProfileId"] = new_main_id
                            self.logger.debug(
                                "Updating quality profile for %s to %s",
                                db_entry["title"],
                                new_main_id,
                            )
                            # Reverting to main - clear tracking fields
                            profile_switch_timestamp = datetime.now()
                            original_profile_for_db = None
                            current_profile_for_db = None
                        elif (
                            not searched
                            and not has_file
                            and quality_profile_id in self.temp_quality_profile_ids.keys()
                        ):
                            new_temp_id = self.temp_quality_profile_ids[quality_profile_id]
                            db_entry["qualityProfileId"] = new_temp_id
                            self.logger.debug(
                                "Updating quality profile for %s to %s",
                                db_entry["title"],
                                new_temp_id,
                            )
                            # Downgrading to temp - track original and switch time
                            profile_switch_timestamp = datetime.now()
                            original_profile_for_db = quality_profile_id
                            current_profile_for_db = new_temp_id

                        profile_update_success = False
                        for attempt in range(self.profile_switch_retry_attempts):
                            try:
                                self.client.upd_movie(db_entry)
                                profile_update_success = True
                                break
                            except (
                                requests.exceptions.ChunkedEncodingError,
                                requests.exceptions.ContentDecodingError,
                                requests.exceptions.ConnectionError,
                                JSONDecodeError,
                            ) as e:
                                if attempt == self.profile_switch_retry_attempts - 1:
                                    self.logger.error(
                                        "Failed to update movie profile after %d attempts: %s",
                                        self.profile_switch_retry_attempts,
                                        e,
                                    )
                                    break
                                time.sleep(1)
                                continue

                        # If profile update failed, don't track the change
                        if not profile_update_success:
                            profile_switch_timestamp = None
                            original_profile_for_db = None
                            current_profile_for_db = None

                    title = db_entry["title"]
                    monitored = db_entry["monitored"]
                    tmdbId = db_entry["tmdbId"]
                    year = db_entry["year"]
                    entryId = db_entry["id"]
                    movieFileId = db_entry["movieFileId"]
                    qualityMet = not QualityUnmet if db_entry["hasFile"] else False
                    customFormatMet = customFormat >= minCustomFormat

                    # Get quality profile info
                    qualityProfileId = db_entry.get("qualityProfileId")
                    qualityProfileName = None
                    if qualityProfileId:
                        try:
                            if qualityProfileId not in self._quality_profile_cache:
                                profile = self.client.get_quality_profile(qualityProfileId)
                                self._quality_profile_cache[qualityProfileId] = profile
                            qualityProfileName = self._quality_profile_cache[qualityProfileId].get(
                                "name"
                            )
                        except Exception:
                            pass

                    if not db_entry["hasFile"]:
                        # Movie is missing a file - always mark as Missing
                        reason = "Missing"
                    elif self.quality_unmet_search and QualityUnmet:
                        reason = "Quality"
                    elif self.custom_format_unmet_search and not customFormatMet:
                        reason = "CustomFormat"
                    elif self.do_upgrade_search:
                        reason = "Upgrade"
                    elif searched:
                        # Movie has file and search is complete
                        reason = "Not being searched"
                    else:
                        reason = "Not being searched"

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
                        self.model_file.QualityProfileId: qualityProfileId,
                        self.model_file.QualityProfileName: qualityProfileName,
                    }

                    # Add profile tracking fields if temp profile feature is enabled
                    if self.use_temp_for_missing and profile_switch_timestamp is not None:
                        to_update[self.model_file.LastProfileSwitchTime] = profile_switch_timestamp
                        to_update[self.model_file.OriginalProfileId] = original_profile_for_db
                        to_update[self.model_file.CurrentProfileId] = current_profile_for_db

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
                        QualityProfileId=qualityProfileId,
                        QualityProfileName=qualityProfileName,
                        ArrInstance=self._name,
                    ).on_conflict(conflict_target=[self.model_file.EntryId], update=to_update)
                    db_commands.execute()
                else:
                    db_commands = self.model_file.delete().where(
                        (self.model_file.EntryId == db_entry["id"])
                        & (self.model_file.ArrInstance == self._name)
                    )
                    db_commands.execute()
            elif self.type == "lidarr":
                if not artist:
                    # Album handling
                    self.model_file: AlbumFilesModel
                    searched = False
                    albumData = self.model_file.get_or_none(
                        (self.model_file.EntryId == db_entry["id"])
                        & (self.model_file.ArrInstance == self._name)
                    )
                    if db_entry["monitored"] or self.search_unmonitored:
                        _retry_exc = (
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                        )
                        if albumData:
                            if not albumData.MinCustomFormatScore:
                                try:
                                    profile_id = db_entry["profileId"]
                                    if profile_id in self._invalid_quality_profiles:
                                        minCustomFormat = 0
                                    elif profile_id in self._quality_profile_cache:
                                        minCustomFormat = self._quality_profile_cache[
                                            profile_id
                                        ].get("minFormatScore", 0)
                                    else:
                                        try:
                                            profile = with_retry(
                                                lambda pid=profile_id: self.client.get_quality_profile(
                                                    pid
                                                ),
                                                retries=5,
                                                backoff=0.5,
                                                max_backoff=5,
                                                exceptions=_retry_exc,
                                            )
                                            self._quality_profile_cache[profile_id] = profile
                                            minCustomFormat = profile.get("minFormatScore", 0)
                                        except PyarrResourceNotFound:
                                            self._invalid_quality_profiles.add(profile_id)
                                            self.logger.warning(
                                                "Quality profile %s not found for album %s, defaulting to 0",
                                                db_entry.get("profileId"),
                                                db_entry.get("title", "Unknown"),
                                            )
                                            minCustomFormat = 0
                                except Exception:
                                    minCustomFormat = 0
                            else:
                                minCustomFormat = albumData.MinCustomFormatScore
                            if db_entry.get("statistics", {}).get("percentOfTracks", 0) == 100:
                                albumFileId = db_entry.get("statistics", {}).get("sizeOnDisk", 0)
                                if albumFileId != albumData.AlbumFileId:
                                    customFormat = 0  # Lidarr may not have customFormatScore
                                else:
                                    customFormat = albumData.CustomFormatScore
                            else:
                                customFormat = 0
                        else:
                            try:
                                profile_id = db_entry["profileId"]
                                if profile_id in self._invalid_quality_profiles:
                                    minCustomFormat = 0
                                elif profile_id in self._quality_profile_cache:
                                    minCustomFormat = self._quality_profile_cache[profile_id].get(
                                        "minFormatScore", 0
                                    )
                                else:
                                    try:
                                        profile = with_retry(
                                            lambda pid=profile_id: self.client.get_quality_profile(
                                                pid
                                            ),
                                            retries=5,
                                            backoff=0.5,
                                            max_backoff=5,
                                            exceptions=_retry_exc,
                                        )
                                        self._quality_profile_cache[profile_id] = profile
                                        minCustomFormat = profile.get("minFormatScore", 0)
                                    except PyarrResourceNotFound:
                                        self._invalid_quality_profiles.add(profile_id)
                                        self.logger.warning(
                                            "Quality profile %s not found for album %s, defaulting to 0",
                                            db_entry.get("profileId"),
                                            db_entry.get("title", "Unknown"),
                                        )
                                        minCustomFormat = 0
                            except Exception:
                                minCustomFormat = 0
                            if db_entry.get("statistics", {}).get("percentOfTracks", 0) == 100:
                                customFormat = 0  # Lidarr may not have customFormatScore
                            else:
                                customFormat = 0

                        # Determine if album has all tracks
                        hasAllTracks = (
                            db_entry.get("statistics", {}).get("percentOfTracks", 0) == 100
                        )

                        # Check if quality cutoff is met for Lidarr
                        # Unlike Sonarr/Radarr which have a qualityCutoffNotMet boolean field,
                        # Lidarr requires us to check the track file quality against the profile cutoff
                        QualityUnmet = False
                        if hasAllTracks:
                            try:
                                # Get the artist's quality profile to find the cutoff
                                artist_id = db_entry.get("artistId")
                                artist_data = self.client.get_artist(artist_id)
                                profile_id = artist_data.get("qualityProfileId")

                                if profile_id:
                                    # Get or use cached profile
                                    if profile_id in self._quality_profile_cache:
                                        profile = self._quality_profile_cache[profile_id]
                                    else:
                                        profile = self.client.get_quality_profile(profile_id)
                                        self._quality_profile_cache[profile_id] = profile

                                    cutoff_quality_id = profile.get("cutoff")
                                    upgrade_allowed = profile.get("upgradeAllowed", False)

                                    if cutoff_quality_id and upgrade_allowed:
                                        # Get track files for this album to check their quality
                                        album_id = db_entry.get("id")
                                        track_files = self.client.get_track_file(
                                            albumId=[album_id]
                                        )

                                        if track_files:
                                            # Check if any track file's quality is below the cutoff
                                            for track_file in track_files:
                                                file_quality = track_file.get("quality", {}).get(
                                                    "quality", {}
                                                )
                                                file_quality_id = file_quality.get("id", 0)

                                                if file_quality_id < cutoff_quality_id:
                                                    QualityUnmet = True
                                                    self.logger.trace(
                                                        "Album '%s' has quality below cutoff: %s (ID: %d) < cutoff (ID: %d)",
                                                        db_entry.get("title", "Unknown"),
                                                        file_quality.get("name", "Unknown"),
                                                        file_quality_id,
                                                        cutoff_quality_id,
                                                    )
                                                    break
                            except Exception as e:
                                self.logger.trace(
                                    "Could not determine quality cutoff status for album '%s': %s",
                                    db_entry.get("title", "Unknown"),
                                    str(e),
                                )
                                # Default to False if we can't determine
                                QualityUnmet = False

                        if (
                            hasAllTracks
                            and not (self.quality_unmet_search and QualityUnmet)
                            and not (
                                self.custom_format_unmet_search and customFormat < minCustomFormat
                            )
                        ):
                            searched = True
                            self.model_queue.update(Completed=True).where(
                                self.model_queue.EntryId == db_entry["id"]
                            ).execute()

                        # Note: Lidarr quality profiles are set at artist level, not album level.
                        # Temp profile logic for Lidarr is handled in artist processing below.

                        title = db_entry.get("title", "Unknown Album")
                        monitored = db_entry.get("monitored", False)
                        # Handle artist field which can be an object or might not exist
                        artist_obj = db_entry.get("artist", {})
                        if isinstance(artist_obj, dict):
                            # Try multiple possible field names for artist name
                            artistName = (
                                artist_obj.get("artistName")
                                or artist_obj.get("name")
                                or artist_obj.get("title")
                                or "Unknown Artist"
                            )
                        else:
                            artistName = "Unknown Artist"
                        artistId = db_entry.get("artistId", 0)
                        foreignAlbumId = db_entry.get("foreignAlbumId", "")
                        releaseDate = db_entry.get("releaseDate")
                        entryId = db_entry.get("id", 0)
                        albumFileId = 1 if hasAllTracks else 0  # Use 1/0 to indicate presence
                        qualityMet = not QualityUnmet if hasAllTracks else False
                        customFormatMet = customFormat >= minCustomFormat

                        # Get quality profile info from artist (Lidarr albums inherit from artist)
                        qualityProfileId = None
                        qualityProfileName = None
                        try:
                            artist_id = db_entry.get("artistId")
                            if artist_id:
                                # Try to get from already-fetched artist data if available
                                artist_data = self.client.get_artist(artist_id)
                                qualityProfileId = artist_data.get("qualityProfileId")
                                if qualityProfileId:
                                    # Fetch quality profile from cache or API
                                    if qualityProfileId not in self._quality_profile_cache:
                                        profile = self.client.get_quality_profile(qualityProfileId)
                                        self._quality_profile_cache[qualityProfileId] = profile
                                    qualityProfileName = self._quality_profile_cache[
                                        qualityProfileId
                                    ].get("name")
                        except Exception:
                            pass

                        if not hasAllTracks:
                            # Album is missing tracks - always mark as Missing
                            reason = "Missing"
                        elif self.quality_unmet_search and QualityUnmet:
                            reason = "Quality"
                        elif self.custom_format_unmet_search and not customFormatMet:
                            reason = "CustomFormat"
                        elif self.do_upgrade_search:
                            reason = "Upgrade"
                        elif searched:
                            # Album is complete and not being searched
                            reason = "Not being searched"
                        else:
                            reason = "Not being searched"

                        to_update = {
                            self.model_file.AlbumFileId: albumFileId,
                            self.model_file.Monitored: monitored,
                            self.model_file.QualityMet: qualityMet,
                            self.model_file.Searched: searched,
                            self.model_file.Upgrade: False,
                            self.model_file.MinCustomFormatScore: minCustomFormat,
                            self.model_file.CustomFormatScore: customFormat,
                            self.model_file.CustomFormatMet: customFormatMet,
                            self.model_file.Reason: reason,
                            self.model_file.ArtistTitle: artistName,
                            self.model_file.ArtistId: artistId,
                            self.model_file.ForeignAlbumId: foreignAlbumId,
                            self.model_file.ReleaseDate: releaseDate,
                            self.model_file.QualityProfileId: qualityProfileId,
                            self.model_file.QualityProfileName: qualityProfileName,
                        }

                        if request:
                            to_update[self.model_file.IsRequest] = request

                        self.logger.debug(
                            "Updating database entry | %s - %s [Searched:%s][Upgrade:%s][QualityMet:%s][CustomFormatMet:%s]",
                            artistName.ljust(30, "."),
                            title.ljust(30, "."),
                            str(searched).ljust(5),
                            str(False).ljust(5),
                            str(qualityMet).ljust(5),
                            str(customFormatMet).ljust(5),
                        )

                        db_commands = self.model_file.insert(
                            Title=title,
                            Monitored=monitored,
                            ArtistTitle=artistName,
                            ArtistId=artistId,
                            ForeignAlbumId=foreignAlbumId,
                            ReleaseDate=releaseDate,
                            EntryId=entryId,
                            Searched=searched,
                            AlbumFileId=albumFileId,
                            IsRequest=request,
                            QualityMet=qualityMet,
                            Upgrade=False,
                            MinCustomFormatScore=minCustomFormat,
                            CustomFormatScore=customFormat,
                            CustomFormatMet=customFormatMet,
                            Reason=reason,
                            QualityProfileId=qualityProfileId,
                            QualityProfileName=qualityProfileName,
                            ArrInstance=self._name,
                        ).on_conflict(conflict_target=[self.model_file.EntryId], update=to_update)
                        db_commands.execute()

                        # Store tracks for this album (Lidarr only)
                        if self.track_file_model:
                            try:
                                # Fetch tracks for this album via the track API
                                # Tracks are NOT in the media field, they're a separate endpoint
                                tracks = self.client.get_tracks(albumId=entryId)
                                self.logger.debug(
                                    f"Fetched {len(tracks) if isinstance(tracks, list) else 0} tracks for album {entryId}"
                                )

                                if tracks and isinstance(tracks, list):
                                    # First, delete existing tracks for this album
                                    self.track_file_model.delete().where(
                                        self.track_file_model.AlbumId == entryId
                                    ).execute()

                                    # Insert new tracks
                                    track_insert_count = 0
                                    for track in tracks:
                                        # Get monitored status from track or default to album's monitored status
                                        track_monitored = track.get(
                                            "monitored", db_entry.get("monitored", False)
                                        )

                                        self.track_file_model.insert(
                                            EntryId=track.get("id"),
                                            AlbumId=entryId,
                                            TrackNumber=track.get("trackNumber", ""),
                                            Title=track.get("title", ""),
                                            Duration=track.get("duration", 0),
                                            HasFile=track.get("hasFile", False),
                                            TrackFileId=track.get("trackFileId", 0),
                                            Monitored=track_monitored,
                                            ArrInstance=self._name,
                                        ).execute()
                                        track_insert_count += 1

                                    if track_insert_count > 0:
                                        self.logger.info(
                                            f"Stored {track_insert_count} tracks for album {entryId} ({title})"
                                        )
                                else:
                                    self.logger.debug(
                                        f"No tracks found for album {entryId} ({title})"
                                    )
                            except Exception as e:
                                self.logger.warning(
                                    f"Could not fetch tracks for album {entryId} ({title}): {e}"
                                )
                    else:
                        db_commands = self.model_file.delete().where(
                            (self.model_file.EntryId == db_entry["id"])
                            & (self.model_file.ArrInstance == self._name)
                        )
                        db_commands.execute()
                        # Also delete tracks for this album (Lidarr only)
                        if self.track_file_model:
                            self.track_file_model.delete().where(
                                (self.track_file_model.AlbumId == db_entry["id"])
                                & (self.track_file_model.ArrInstance == self._name)
                            ).execute()
                else:
                    # Artist handling
                    self.artists_file_model: ArtistFilesModel
                    EntryId = db_entry["id"]
                    artistData = self.artists_file_model.get_or_none(
                        (self.artists_file_model.EntryId == EntryId)
                        & (self.artists_file_model.ArrInstance == self._name)
                    )
                    if db_entry["monitored"] or self.search_unmonitored:
                        _retry_exc = (
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                        )
                        artistMetadata = (
                            with_retry(
                                lambda eid=EntryId: self.client.get_artist(id_=eid),
                                retries=5,
                                backoff=0.5,
                                max_backoff=5,
                                exceptions=_retry_exc,
                            )
                            or {}
                        )
                        quality_profile_id = None
                        if isinstance(artistMetadata, dict):
                            quality_profile_id = artistMetadata.get("qualityProfileId")
                        else:
                            quality_profile_id = getattr(artistMetadata, "qualityProfileId", None)
                        if not artistData:
                            if quality_profile_id:
                                profile = (
                                    with_retry(
                                        lambda qpid=quality_profile_id: self.client.get_quality_profile(
                                            qpid
                                        ),
                                        retries=5,
                                        backoff=0.5,
                                        max_backoff=5,
                                        exceptions=_retry_exc,
                                    )
                                    or {}
                                )
                                minCustomFormat = profile.get("minFormatScore") or 0
                            else:
                                self.logger.warning(
                                    "Artist %s (%s) missing qualityProfileId; "
                                    "defaulting custom format score to 0",
                                    db_entry.get("artistName"),
                                    EntryId,
                                )
                                minCustomFormat = 0
                        else:
                            minCustomFormat = getattr(artistData, "MinCustomFormatScore", 0)
                        # Calculate if artist is fully searched based on album statistics
                        statistics = artistMetadata.get("statistics", {})
                        albumCount = statistics.get("albumCount", 0)
                        statistics.get("totalAlbumCount", 0)
                        # Check if there's any album with files (sizeOnDisk > 0)
                        sizeOnDisk = statistics.get("sizeOnDisk", 0)
                        # Artist is considered searched if it has albums and at least some have files
                        searched = albumCount > 0 and sizeOnDisk > 0

                        # Temp profile management for Lidarr artists
                        # Quality profiles in Lidarr are set at artist level, not album level
                        # NOTE: Lidarr uses sizeOnDisk instead of hasFile because the Lidarr API
                        # doesn't provide a hasFile boolean at artist level. sizeOnDisk > 0 is
                        # equivalent to hasFile=True for Lidarr.
                        if self.use_temp_for_missing and quality_profile_id:
                            if (
                                searched
                                and quality_profile_id in self.main_quality_profile_ids.keys()
                                and not self.keep_temp_profile
                            ):
                                # Artist has files, switch from temp back to main profile
                                main_profile_id = self.main_quality_profile_ids[quality_profile_id]
                                artistMetadata["qualityProfileId"] = main_profile_id
                                self.client.upd_artist(artistMetadata)
                                quality_profile_id = main_profile_id
                                self.logger.debug(
                                    "Upgrading artist '%s' from temp profile (ID:%s) to main profile (ID:%s) [Has files]",
                                    artistMetadata.get("artistName", "Unknown"),
                                    quality_profile_id,
                                    main_profile_id,
                                )
                            elif (
                                not searched
                                and sizeOnDisk == 0
                                and quality_profile_id in self.temp_quality_profile_ids.keys()
                            ):
                                # Artist has no files yet, apply temp profile
                                temp_profile_id = self.temp_quality_profile_ids[quality_profile_id]
                                artistMetadata["qualityProfileId"] = temp_profile_id
                                self.client.upd_artist(artistMetadata)
                                quality_profile_id = temp_profile_id
                                self.logger.debug(
                                    "Downgrading artist '%s' from main profile (ID:%s) to temp profile (ID:%s) [No files yet]",
                                    artistMetadata.get("artistName", "Unknown"),
                                    quality_profile_id,
                                    temp_profile_id,
                                )

                        Title = artistMetadata.get("artistName")
                        Monitored = db_entry["monitored"]

                        to_update = {
                            self.artists_file_model.Monitored: Monitored,
                            self.artists_file_model.Title: Title,
                            self.artists_file_model.Searched: searched,
                            self.artists_file_model.Upgrade: False,
                            self.artists_file_model.MinCustomFormatScore: minCustomFormat,
                        }

                        self.logger.debug(
                            "Updating database entry | %s [Searched:%s][Upgrade:%s]",
                            Title.ljust(60, "."),
                            str(searched).ljust(5),
                            str(False).ljust(5),
                        )

                        db_commands = self.artists_file_model.insert(
                            EntryId=EntryId,
                            Title=Title,
                            Searched=searched,
                            Monitored=Monitored,
                            Upgrade=False,
                            MinCustomFormatScore=minCustomFormat,
                            ArrInstance=self._name,
                        ).on_conflict(
                            conflict_target=[self.artists_file_model.EntryId], update=to_update
                        )
                        db_commands.execute()

                        # Note: Albums are now handled separately in db_update()
                        # No need to recursively process albums here to avoid duplication
                    else:
                        db_commands = self.artists_file_model.delete().where(
                            self.artists_file_model.EntryId == EntryId
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
            raise DelayLoopException(length=300, error_type=self._name)
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
            res = with_retry(
                lambda: self.client.del_queue(id_, remove_from_client, blacklist),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
        except PyarrResourceNotFound as e:
            # Queue item not found - this is expected when Arr has already auto-imported
            # and removed the item, or if it was manually removed. Clean up internal tracking.
            self.logger.warning(
                "Queue item %s not found in Arr (likely already imported/removed): %s",
                id_,
                str(e),
            )
            # Clean up internal tracking data for this queue entry
            if id_ in self.requeue_cache:
                # Remove associated media IDs from queue_file_ids
                media_ids = self.requeue_cache[id_]
                if isinstance(media_ids, set):
                    self.queue_file_ids.difference_update(media_ids)
                elif media_ids in self.queue_file_ids:
                    self.queue_file_ids.discard(media_ids)
                # Remove from requeue_cache
                del self.requeue_cache[id_]
            # Remove from cache (downloadId -> queue entry ID mapping)
            # We need to find and remove the cache entry by value (queue ID)
            cache_keys_to_remove = [k for k, v in self.cache.items() if v == id_]
            for key in cache_keys_to_remove:
                del self.cache[key]
            return None
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
            if file.name.endswith(".!qB"):
                self.logger.trace("Not probeable: File is still downloading: %s", file)
                return False
            output = ffmpeg.probe(
                str(file.absolute()), cmd=self.manager.qbit_manager.ffprobe_downloader.probe_path
            )
            if not output:
                self.logger.trace("Not probeable: Probe returned no output: %s", file)
                return False
            self.files_probed.add(file)
            return True
        except Exception as e:
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
            else (
                "[OMBI REQUEST]: "
                if request and self.ombi_search_requests
                else "[PRIORITY SEARCH - TODAY]: " if todays else ""
            )
        )
        self.refresh_download_queue()
        if request or todays:
            bypass_limit = True
        if file_model is None:
            return None
        features_enabled = (
            self.search_missing
            or self.do_upgrade_search
            or self.quality_unmet_search
            or self.custom_format_unmet_search
            or self.ombi_search_requests
            or self.overseerr_requests
        )
        if not features_enabled and not (request or todays):
            return None
        elif not self.is_alive:
            raise NoConnectionrException(f"Could not connect to {self.uri}", error_type="arr")
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
                        (self.model_file.EntryId == file_model.EntryId)
                        & (self.model_file.ArrInstance == self._name)
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
                    EntryId=file_model.EntryId, ArrInstance=self._name
                ).on_conflict_ignore().execute()
                self.model_queue.insert(
                    Completed=False, EntryId=file_model.EntryId, ArrInstance=self._name
                ).on_conflict_replace().execute()
                if file_model.EntryId not in self.queue_file_ids:
                    with_retry(
                        lambda: self.client.post_command(
                            "EpisodeSearch", episodeIds=[file_model.EntryId]
                        ),
                        retries=5,
                        backoff=0.5,
                        max_backoff=5,
                        exceptions=_ARR_RETRY_EXCEPTIONS,
                    )
                self.model_file.update(Searched=True, Upgrade=True).where(
                    (self.model_file.EntryId == file_model.EntryId)
                    & (self.model_file.ArrInstance == self._name)
                ).execute()
                reason_text = getattr(file_model, "Reason", None) or None
                if reason_text:
                    self.logger.hnotice(
                        "%sSearching for: %s | S%02dE%03d | %s | [id=%s|AirDateUTC=%s][%s]",
                        request_tag,
                        file_model.SeriesTitle,
                        file_model.SeasonNumber,
                        file_model.EpisodeNumber,
                        file_model.Title,
                        file_model.EntryId,
                        file_model.AirDateUtc,
                        reason_text,
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
                description = f"{file_model.SeriesTitle} S{file_model.SeasonNumber:02d}E{file_model.EpisodeNumber:02d}"
                if getattr(file_model, "Title", None):
                    description = f"{description} · {file_model.Title}"
                context_label = self._humanize_request_tag(request_tag)
                self._record_search_activity(
                    description,
                    context=context_label,
                    detail=str(reason_text) if reason_text else None,
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
                    EntryId=file_model.EntryId, ArrInstance=self._name
                ).on_conflict_ignore().execute()
                self.model_queue.insert(
                    Completed=False, EntryId=file_model.EntryId, ArrInstance=self._name
                ).on_conflict_replace().execute()
                with_retry(
                    lambda: self.client.post_command(
                        self.search_api_command, seriesId=file_model.EntryId
                    ),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )
                self.model_file.update(Searched=True, Upgrade=True).where(
                    (self.model_file.EntryId == file_model.EntryId)
                    & (self.model_file.ArrInstance == self._name)
                ).execute()
                self.logger.hnotice(
                    "%sSearching for: %s | %s | [id=%s]",
                    request_tag,
                    (
                        "Missing episodes in"
                        if "Missing" in self.search_api_command
                        else "All episodes in"
                    ),
                    file_model.Title,
                    file_model.EntryId,
                )
                context_label = self._humanize_request_tag(request_tag)
                scope = (
                    "Missing episodes in"
                    if "Missing" in self.search_api_command
                    else "All episodes in"
                )
                description = f"{scope} {file_model.Title}"
                self._record_search_activity(description, context=context_label)
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
                    (self.model_file.EntryId == file_model.EntryId)
                    & (self.model_file.ArrInstance == self._name)
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
            self.persistent_queue.insert(
                EntryId=file_model.EntryId, ArrInstance=self._name
            ).on_conflict_ignore().execute()

            self.model_queue.insert(
                Completed=False, EntryId=file_model.EntryId, ArrInstance=self._name
            ).on_conflict_replace().execute()
            if file_model.EntryId:
                with_retry(
                    lambda: self.client.post_command(
                        "MoviesSearch", movieIds=[file_model.EntryId]
                    ),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )
            self.model_file.update(Searched=True, Upgrade=True).where(
                (self.model_file.EntryId == file_model.EntryId)
                & (self.model_file.ArrInstance == self._name)
            ).execute()
            reason_text = getattr(file_model, "Reason", None)
            if reason_text:
                self.logger.hnotice(
                    "%sSearching for: %s (%s) [tmdbId=%s|id=%s][%s]",
                    request_tag,
                    file_model.Title,
                    file_model.Year,
                    file_model.TmdbId,
                    file_model.EntryId,
                    reason_text,
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
            context_label = self._humanize_request_tag(request_tag)
            description = (
                f"{file_model.Title} ({file_model.Year})"
                if getattr(file_model, "Year", None)
                else f"{file_model.Title}"
            )
            self._record_search_activity(
                description,
                context=context_label,
                detail=str(reason_text) if reason_text else None,
            )
            return True
        elif self.type == "lidarr":
            file_model: AlbumFilesModel
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
                    "%sSkipping: Already Searched: %s - %s (%s)",
                    request_tag,
                    file_model.ArtistTitle,
                    file_model.Title,
                    file_model.EntryId,
                )
                self.model_file.update(Searched=True, Upgrade=True).where(
                    (self.model_file.EntryId == file_model.EntryId)
                    & (self.model_file.ArrInstance == self._name)
                ).execute()
                return True
            active_commands = self.arr_db_query_commands_count()
            self.logger.info("%s active search commands, %s remaining", active_commands, commands)
            if not bypass_limit and active_commands >= self.search_command_limit:
                self.logger.trace(
                    "Idle: Too many commands in queue: %s - %s | [id=%s]",
                    file_model.ArtistTitle,
                    file_model.Title,
                    file_model.EntryId,
                )
                return False
            self.persistent_queue.insert(
                EntryId=file_model.EntryId, ArrInstance=self._name
            ).on_conflict_ignore().execute()

            self.model_queue.insert(
                Completed=False, EntryId=file_model.EntryId, ArrInstance=self._name
            ).on_conflict_replace().execute()
            if file_model.EntryId:
                with_retry(
                    lambda: self.client.post_command("AlbumSearch", albumIds=[file_model.EntryId]),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )
            self.model_file.update(Searched=True, Upgrade=True).where(
                (self.model_file.EntryId == file_model.EntryId)
                & (self.model_file.ArrInstance == self._name)
            ).execute()
            reason_text = getattr(file_model, "Reason", None)
            if reason_text:
                self.logger.hnotice(
                    "%sSearching for: %s - %s [foreignAlbumId=%s|id=%s][%s]",
                    request_tag,
                    file_model.ArtistTitle,
                    file_model.Title,
                    file_model.ForeignAlbumId,
                    file_model.EntryId,
                    reason_text,
                )
            else:
                self.logger.hnotice(
                    "%sSearching for: %s - %s [foreignAlbumId=%s|id=%s]",
                    request_tag,
                    file_model.ArtistTitle,
                    file_model.Title,
                    file_model.ForeignAlbumId,
                    file_model.EntryId,
                )
            context_label = self._humanize_request_tag(request_tag)
            description = f"{file_model.ArtistTitle} - {file_model.Title}"
            self._record_search_activity(
                description,
                context=context_label,
                detail=str(reason_text) if reason_text else None,
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

    def _get_torrents_from_all_instances(
        self,
    ) -> list[tuple[str, qbittorrentapi.TorrentDictionary]]:
        """
        Get torrents from ALL qBittorrent instances for this Arr's category.

        Returns:
            list[tuple[str, TorrentDictionary]]: List of (instance_name, torrent) tuples
        """
        all_torrents = []
        qbit_manager = self.manager.qbit_manager

        for instance_name in qbit_manager.get_all_instances():
            if not qbit_manager.is_instance_alive(instance_name):
                self.logger.debug(
                    "Skipping unhealthy instance '%s' during torrent scan", instance_name
                )
                continue

            client = qbit_manager.get_client(instance_name)
            if client is None:
                continue

            try:
                torrents = client.torrents.info(
                    status_filter="all",
                    category=self.category,
                    sort="added_on",
                    reverse=False,
                )
                # Tag each torrent with its instance name
                for torrent in torrents:
                    if hasattr(torrent, "category"):
                        all_torrents.append((instance_name, torrent))

                self.logger.trace(
                    "Retrieved %d torrents from instance '%s' for category '%s'",
                    len(torrents),
                    instance_name,
                    self.category,
                )
            except (qbittorrentapi.exceptions.APIError, JSONDecodeError) as e:
                self.logger.warning(
                    "Failed to get torrents from instance '%s': %s", instance_name, e
                )
                continue

        self.logger.debug(
            "Total torrents across %d instances: %d",
            len(qbit_manager.get_all_instances()),
            len(all_torrents),
        )
        return all_torrents

    def process_torrents(self):
        try:
            try:
                torrents_with_instances = with_retry(
                    lambda: self._get_torrents_from_all_instances(),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=(JSONDecodeError,),
                )

                # Filter torrents that have category attribute
                torrents_with_instances = [
                    (instance, t)
                    for instance, t in torrents_with_instances
                    if hasattr(t, "category")
                ]
                self._warned_no_seeding_limits = False
                self.category_torrent_count = len(torrents_with_instances)
                if not len(torrents_with_instances):
                    raise DelayLoopException(length=LOOP_SLEEP_TIMER, error_type="no_downloads")

                # Internet check: use the first available qBit client
                if not has_internet(self.manager.qbit_manager.client):
                    self.manager.qbit_manager.should_delay_torrent_scan = True
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, error_type="internet")
                if self.manager.qbit_manager.should_delay_torrent_scan:
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, error_type="delay")

                # Initialize database error tracking for exponential backoff
                if not hasattr(self, "_db_error_count"):
                    self._db_error_count = 0
                    self._db_last_error_time = 0

                # Periodic database health check (every 10th iteration)
                if not hasattr(self, "_health_check_counter"):
                    self._health_check_counter = 0

                self._health_check_counter += 1
                if self._health_check_counter >= 10:
                    from qBitrr.db_lock import check_database_health
                    from qBitrr.home_path import APPDATA_FOLDER

                    db_path = APPDATA_FOLDER / "qbitrr.db"
                    healthy, msg = check_database_health(db_path, self.logger)

                    if not healthy:
                        self.logger.error("Database health check failed: %s", msg)
                        self.logger.warning("Attempting database recovery...")
                        try:
                            self._recover_database()
                        except Exception as recovery_error:
                            self.logger.error(
                                "Database recovery failed: %s. Continuing with caution...",
                                recovery_error,
                            )

                    self._health_check_counter = 0

                self.api_calls()
                self.refresh_download_queue()
                # Multi-instance: Process torrents from all instances
                for instance_name, torrent in torrents_with_instances:
                    with contextlib.suppress(qbittorrentapi.NotFound404Error):
                        self._process_single_torrent(torrent, instance_name=instance_name)
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
                raise DelayLoopException(length=300, error_type="qbit")
            except (OperationalError, DatabaseError) as e:
                # Database errors after retry exhaustion - implement automatic recovery with backoff
                error_msg = str(e).lower()
                current_time = time.time()

                # Track consecutive database errors for exponential backoff
                # Initialize tracking on first error ever
                if not hasattr(self, "_db_first_error_time"):
                    self._db_first_error_time = current_time

                # Reset if >5min since last error (new error sequence)
                if (
                    current_time - self._db_last_error_time > 300
                ):  # Reset if >5min since last error
                    self._db_error_count = 0
                    self._db_first_error_time = current_time

                self._db_error_count += 1
                self._db_last_error_time = current_time

                # Check if errors have persisted for more than 5 minutes
                time_since_first_error = current_time - self._db_first_error_time
                if time_since_first_error > 300:  # 5 minutes
                    self.logger.critical(
                        "Database errors have persisted for %.1f minutes. "
                        "Signaling coordinated restart of ALL processes for database recovery...",
                        time_since_first_error / 60,
                    )
                    # Signal all processes to restart (shared database affects everyone)
                    self.manager.qbit_manager.database_restart_event.set()
                    # Exit this process - main will restart all
                    sys.exit(1)

                # Calculate exponential backoff: 2min, 5min, 10min, 20min, 30min (max)
                delay_seconds = min(120 * (2 ** (self._db_error_count - 1)), 1800)

                # Log detailed error information based on error type
                # Use escalating severity: WARNING (1-2 errors), ERROR (3-4), CRITICAL (5+)
                if self._db_error_count <= 2:
                    log_func = self.logger.warning
                elif self._db_error_count <= 4:
                    log_func = self.logger.error
                else:
                    log_func = self.logger.critical

                if "disk i/o error" in error_msg:
                    log_func(
                        "Database I/O error detected (consecutive error #%d). "
                        "This may indicate disk issues, filesystem corruption, or resource exhaustion. "
                        "Attempting automatic recovery and retrying in %d seconds...",
                        self._db_error_count,
                        delay_seconds,
                    )
                elif "database is locked" in error_msg:
                    log_func(
                        "Database locked error (consecutive error #%d). "
                        "Retrying in %d seconds...",
                        self._db_error_count,
                        delay_seconds,
                    )
                elif "disk image is malformed" in error_msg:
                    log_func(
                        "Database corruption detected (consecutive error #%d). "
                        "Attempting automatic recovery and retrying in %d seconds...",
                        self._db_error_count,
                        delay_seconds,
                    )
                else:
                    log_func(
                        "Database error (consecutive error #%d): %s. Retrying in %d seconds...",
                        self._db_error_count,
                        error_msg,
                        delay_seconds,
                    )

                # Attempt automatic recovery for critical errors
                if "disk i/o error" in error_msg or "disk image is malformed" in error_msg:
                    try:
                        self.logger.warning(
                            "Attempting enhanced database recovery (WAL checkpoint, repair, and verification)..."
                        )
                        self._enhanced_database_recovery()
                        self.logger.info(
                            "Database recovery completed successfully - will retry operation after delay"
                        )
                        # Reduce error count on successful recovery (but don't reset completely)
                        self._db_error_count = max(0, self._db_error_count - 1)
                    except Exception as recovery_error:
                        self.logger.critical(
                            "Automatic database recovery failed: %s. "
                            "MANUAL INTERVENTION REQUIRED: Check disk health (smartctl), "
                            "filesystem integrity (fsck), available space (df -h), "
                            "Docker volume mounts, permissions, and system logs (dmesg).",
                            recovery_error,
                        )

                # Delay processing to avoid hammering failing database
                raise DelayLoopException(length=delay_seconds, error_type="database")
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

    def _recover_database(self):
        """
        Attempt automatic database recovery when health check fails.

        This method implements a progressive recovery strategy:
        1. Try WAL checkpoint (least invasive)
        2. Try full database repair if checkpoint fails
        3. Log critical error if all recovery methods fail
        """
        from qBitrr.db_recovery import DatabaseRecoveryError, checkpoint_wal, repair_database
        from qBitrr.home_path import APPDATA_FOLDER

        db_path = APPDATA_FOLDER / "qbitrr.db"

        # Step 1: Try WAL checkpoint (least invasive)
        self.logger.info("Attempting WAL checkpoint...")
        if checkpoint_wal(db_path, self.logger):
            self.logger.info("WAL checkpoint successful - database recovered")
            return

        # Step 2: Try full repair (more invasive)
        self.logger.warning("WAL checkpoint failed - attempting full database repair...")
        try:
            if repair_database(db_path, backup=True, logger_override=self.logger):
                self.logger.info("Database repair successful")
                return
        except DatabaseRecoveryError as e:
            self.logger.error("Database repair failed: %s", e)
        except Exception as e:
            self.logger.error("Unexpected error during database repair: %s", e)

        # Step 3: All recovery methods failed
        self.logger.critical(
            "Database recovery failed - database may be corrupted. "
            "Manual intervention may be required. Continuing with caution..."
        )

    def _enhanced_database_recovery(self):
        """
        Enhanced automatic database recovery with additional filesystem checks.

        This method is called when disk I/O errors persist after retry logic has been exhausted.
        It implements a comprehensive recovery strategy:
        1. Try WAL checkpoint (least invasive)
        2. Try VACUUM to reclaim space and fix minor corruption
        3. Try full database repair (dump/restore) if needed
        4. Verify database integrity after recovery
        """
        from qBitrr.db_recovery import (
            DatabaseRecoveryError,
            checkpoint_wal,
            repair_database,
            vacuum_database,
        )
        from qBitrr.home_path import APPDATA_FOLDER

        db_path = APPDATA_FOLDER / "qbitrr.db"

        self.logger.info("Starting enhanced database recovery procedure...")

        # Step 1: Try WAL checkpoint
        self.logger.info("Step 1/3: Attempting WAL checkpoint...")
        if checkpoint_wal(db_path, self.logger):
            self.logger.info("WAL checkpoint successful")
            # Try a quick health check
            from qBitrr.db_lock import check_database_health

            healthy, msg = check_database_health(db_path, self.logger)
            if healthy:
                self.logger.info("Database health verified - recovery complete")
                return
            else:
                self.logger.warning(
                    "WAL checkpoint completed but database still unhealthy: %s", msg
                )

        # Step 2: Try VACUUM (only if WAL didn't fully fix it)
        self.logger.info("Step 2/3: Attempting VACUUM to reclaim space and fix minor issues...")
        if vacuum_database(db_path, self.logger):
            self.logger.info("VACUUM completed successfully")
            from qBitrr.db_lock import check_database_health

            healthy, msg = check_database_health(db_path, self.logger)
            if healthy:
                self.logger.info("Database health verified after VACUUM - recovery complete")
                return
            else:
                self.logger.warning("VACUUM completed but database still unhealthy: %s", msg)

        # Step 3: Try full repair (most invasive)
        self.logger.warning("Step 3/3: Attempting full database repair (dump/restore)...")
        try:
            if repair_database(db_path, backup=True, logger_override=self.logger):
                self.logger.info("Database repair successful")
                # Final health check
                from qBitrr.db_lock import check_database_health

                healthy, msg = check_database_health(db_path, self.logger)
                if healthy:
                    self.logger.info("Database health verified after repair - recovery complete")
                    return
                else:
                    self.logger.error("Repair completed but database still unhealthy: %s", msg)
                    raise DatabaseRecoveryError(f"Database unhealthy after repair: {msg}")
        except DatabaseRecoveryError as e:
            self.logger.error("Database repair failed: %s", e)
            raise
        except Exception as e:
            self.logger.error("Unexpected error during database repair: %s", e)
            raise

        # If we reach here, all recovery methods failed
        raise DatabaseRecoveryError("All automatic recovery methods failed")

    def _process_single_torrent_failed_cat(self, torrent: qbittorrentapi.TorrentDictionary):
        self._mark_for_deletion(torrent, "manually failed")

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

    def _mark_for_deletion(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        reason: str,
        ratio_limit=None,
        seeding_time_limit=None,
    ) -> None:
        """Mark torrent for deletion and log reason with current stats and effective limits."""
        extra = ""
        if ratio_limit is not None or seeding_time_limit is not None:
            parts = []
            if ratio_limit is not None:
                parts.append("ratio_limit=%s" % (ratio_limit if ratio_limit > 0 else "unset"))
            if seeding_time_limit is not None:
                parts.append(
                    "seeding_time_limit=%s"
                    % (seeding_time_limit if seeding_time_limit > 0 else "unset")
                )
            extra = " [%s]" % ", ".join(parts)
        self.logger.info(
            "Marking for deletion (%s): [Progress: %s%%][Ratio: %s][Seeding time: %s] | %s (%s)%s",
            reason,
            round(torrent.progress * 100, 2),
            torrent.ratio,
            timedelta(seconds=torrent.seeding_time),
            torrent.name,
            torrent.hash,
            extra,
        )
        self.delete.add(torrent.hash)

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
            if self._hnr_allows_delete(torrent, extra):
                self._mark_for_deletion(torrent, extra)
        else:
            self.logger.trace(
                "Ignoring Stale torrent (%s): "
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
            if self._hnr_allows_delete(torrent, "stale high-percentage deletion"):
                self._mark_for_deletion(torrent, "stale high-percentage deletion")
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
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        leave_alone: bool,
        instance_name: str = "default",
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
        elif not self.in_tags(torrent, "qBitrr-imported", instance_name):
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
            self.import_torrents.append((torrent, instance_name))

    def _process_single_torrent_missing_files(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        instance_name: str = "default",
    ):
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
        self.remove_from_qbit_by_instance.setdefault(instance_name, set()).add(torrent.hash)

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
        if self._hnr_allows_delete(torrent, "slow torrent deletion"):
            self._mark_for_deletion(torrent, "slow torrent deletion")

    def _process_single_torrent_delete_cfunmet(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = ""
    ):
        if self._hnr_allows_delete(torrent, "CF unmet deletion"):
            self._mark_for_deletion(torrent, "CF unmet deletion")

    def _process_single_torrent_delete_ratio_seed(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        limit_meta: tuple[dict, dict] | None = None,
    ):
        if limit_meta is not None:
            data_settings, data_torrent = limit_meta
        else:
            data_settings, data_torrent = self._get_torrent_limit_meta(torrent)
        r_dat = data_settings.get("ratio_limit", -5)
        r_tor = data_torrent.get("ratio_limit", -5)
        t_dat = data_settings.get("seeding_time_limit", -5)
        t_tor = data_torrent.get("seeding_time_limit", -5)
        ratio_limit = max(r_dat, r_tor) if (r_dat > 0 or r_tor > 0) else -5
        seeding_time_limit = max(t_dat, t_tor) if (t_dat > 0 or t_tor > 0) else -5
        if self._hnr_allows_delete(
            torrent, "ratio/seed limit deletion", data_settings=data_settings
        ):
            self._mark_for_deletion(
                torrent,
                "ratio/seed limit deletion",
                ratio_limit=ratio_limit,
                seeding_time_limit=seeding_time_limit,
            )

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
                if self._hnr_allows_delete(torrent, "all-files-excluded deletion"):
                    self._mark_for_deletion(torrent, "all-files-excluded deletion")
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
            current_tracker_urls = {
                i.url.rstrip("/") for i in torrent.trackers if hasattr(i, "url")
            }
        except qbittorrentapi.exceptions.APIError as e:
            self.logger.error("The qBittorrent API returned an unexpected error")
            self.logger.debug("Unexpected APIError from qBitTorrent", exc_info=e)
            raise DelayLoopException(length=300, error_type="qbit")
        # Host-based matching: resolve qBit announce URLs to their config URIs.
        # Supports apex/suffix matching so that an announce URL using a subdomain
        # (e.g. "tracker.torrentleech.org") matches a config URI that is the apex
        # domain (e.g. "torrentleech.org").
        current_hosts = {_extract_tracker_host(u) for u in current_tracker_urls} - {""}
        monitored_trackers: set[str] = set()
        for h in current_hosts:
            if h in self._host_to_config_uri:
                monitored_trackers.add(self._host_to_config_uri[h])
            else:
                for config_host, config_uri in self._host_to_config_uri.items():
                    if h.endswith("." + config_host):
                        monitored_trackers.add(config_uri)
                        break
        # For AddTrackerIfMissing, check by host whether tracker is already present
        need_to_be_added = {
            uri
            for uri in self._add_trackers_if_missing
            if _extract_tracker_host(uri) not in current_hosts
        }
        monitored_trackers = monitored_trackers.union(need_to_be_added)
        return need_to_be_added, monitored_trackers

    @staticmethod
    def __return_max(x: dict):
        return x.get("Priority", -100)

    def _get_most_important_tracker_and_tags(
        self, monitored_trackers, removed
    ) -> tuple[dict, set[str]]:
        removed_hosts = {_extract_tracker_host(u) for u in removed} - {""}
        new_list = [
            i
            for i in self.monitored_trackers
            if (i.get("URI") in monitored_trackers) and i.get("RemoveIfExists") is not True
        ]
        _list_of_tags = [
            i.get("AddTags", [])
            for i in new_list
            if _extract_tracker_host(i.get("URI") or "") not in removed_hosts
        ]
        max_item = max(new_list, key=self.__return_max) if new_list else {}
        return max_item, set(itertools.chain.from_iterable(_list_of_tags))

    def _resolve_hnr_clear_mode(self, tracker_or_config: dict) -> str:
        """Resolve HnR mode from single HitAndRunMode key: 'and' | 'or' | 'disabled'."""
        raw = tracker_or_config.get("HitAndRunMode")
        if isinstance(raw, str) and raw.strip().lower() in ("and", "or", "disabled"):
            return raw.strip().lower()
        # Legacy: boolean HitAndRunMode (pre-migration)
        if raw is True:
            return "and"
        return "disabled"

    def _get_torrent_limit_meta(self, torrent: qbittorrentapi.TorrentDictionary):
        _, monitored_trackers = self._get_torrent_important_trackers(torrent)
        most_important_tracker, _unique_tags = self._get_most_important_tracker_and_tags(
            monitored_trackers, {}
        )

        data_settings = {
            "ratio_limit": (
                r
                if (
                    r := most_important_tracker.get(
                        "MaxUploadRatio", self.seeding_mode_global_max_upload_ratio
                    )
                )
                > 0
                else -5
            ),
            "seeding_time_limit": (
                r
                if (
                    r := most_important_tracker.get(
                        "MaxSeedingTime", self.seeding_mode_global_max_seeding_time
                    )
                )
                > 0
                else -5
            ),
            "dl_limit": (
                r
                if (
                    r := most_important_tracker.get(
                        "DownloadRateLimit", self.seeding_mode_global_download_limit
                    )
                )
                > 0
                else -5
            ),
            "up_limit": (
                r
                if (
                    r := most_important_tracker.get(
                        "UploadRateLimit", self.seeding_mode_global_upload_limit
                    )
                )
                > 0
                else -5
            ),
            "super_seeding": most_important_tracker.get("SuperSeedMode", torrent.super_seeding),
            "max_eta": most_important_tracker.get("MaximumETA", self.maximum_eta),
            "hnr_clear_mode": self._resolve_hnr_clear_mode(most_important_tracker),
            "hnr_min_seed_ratio": most_important_tracker.get("MinSeedRatio", 1.0),
            "hnr_min_seeding_time_days": most_important_tracker.get("MinSeedingTimeDays", 0),
            "hnr_min_download_percent": most_important_tracker.get(
                "HitAndRunMinimumDownloadPercent", 10
            ),
            "hnr_partial_seed_ratio": most_important_tracker.get("HitAndRunPartialSeedRatio", 1.0),
            "hnr_tracker_update_buffer": most_important_tracker.get("TrackerUpdateBuffer", 0),
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
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = "default"
    ) -> tuple[bool, int, bool, dict | None, dict | None]:
        return_value = True
        remove_torrent = False
        if torrent.super_seeding or torrent.state_enum == TorrentStates.FORCED_UPLOAD:
            return return_value, -1, remove_torrent, None, None

        is_uploading = torrent.state_enum in (
            TorrentStates.UPLOADING,
            TorrentStates.STALLED_UPLOAD,
            TorrentStates.QUEUED_UPLOAD,
            TorrentStates.PAUSED_UPLOAD,
        )
        is_downloading = torrent.state_enum in (
            TorrentStates.DOWNLOADING,
            TorrentStates.STALLED_DOWNLOAD,
            TorrentStates.QUEUED_DOWNLOAD,
            TorrentStates.PAUSED_DOWNLOAD,
            TorrentStates.FORCED_DOWNLOAD,
            TorrentStates.METADATA_DOWNLOAD,
        )

        data_settings, data_torrent = self._get_torrent_limit_meta(torrent)
        self.logger.trace("Config Settings for torrent [%s]: %r", torrent.name, data_settings)
        self.logger.trace("Torrent Settings for torrent [%s]: %r", torrent.name, data_torrent)

        ratio_limit_dat = data_settings.get("ratio_limit", -5)
        ratio_limit_tor = data_torrent.get("ratio_limit", -5)
        seeding_time_limit_dat = data_settings.get("seeding_time_limit", -5)
        seeding_time_limit_tor = data_torrent.get("seeding_time_limit", -5)

        seeding_time_limit = max(seeding_time_limit_dat, seeding_time_limit_tor)
        ratio_limit = max(ratio_limit_dat, ratio_limit_tor)

        if is_uploading and self.seeding_mode_global_remove_torrent != -1:
            remove_torrent = self.torrent_limit_check(torrent, seeding_time_limit, ratio_limit)
        else:
            remove_torrent = False

        hnr_override = False
        if (
            is_downloading
            and remove_torrent
            and not self._hnr_safe_to_remove(torrent, data_settings)
        ):
            self.logger.debug(
                "HnR protection: keeping downloading torrent [%s] (ratio=%.2f, seeding=%s)",
                torrent.name,
                torrent.ratio,
                timedelta(seconds=torrent.seeding_time),
            )
            remove_torrent = False
            hnr_override = True

        if hnr_override:
            return_value = True
        else:
            return_value = not (
                is_uploading and self.torrent_limit_check(torrent, seeding_time_limit, ratio_limit)
            )
        if data_settings.get("super_seeding", False) or data_torrent.get("super_seeding", False):
            return_value = True
        if self.in_tags(torrent, "qBitrr-free_space_paused", instance_name):
            return_value = True
        if (
            return_value
            and not self.in_tags(torrent, "qBitrr-allowed_seeding", instance_name)
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
        ):
            self.add_tags(torrent, ["qBitrr-allowed_seeding"], instance_name)
        elif (
            not return_value and self.in_tags(torrent, "qBitrr-allowed_seeding", instance_name)
        ) or self.in_tags(torrent, "qBitrr-free_space_paused", instance_name):
            self.remove_tags(torrent, ["qBitrr-allowed_seeding"], instance_name)

        if hnr_override and not self.in_tags(torrent, "qBitrr-hnr_active", instance_name):
            self.add_tags(torrent, ["qBitrr-hnr_active"], instance_name)
        elif not hnr_override and self.in_tags(torrent, "qBitrr-hnr_active", instance_name):
            self.remove_tags(torrent, ["qBitrr-hnr_active"], instance_name)

        self.logger.trace("Config Settings returned [%s]: %r", torrent.name, data_settings)
        return (
            return_value,
            data_settings.get("max_eta", self.maximum_eta),
            remove_torrent,
            data_settings,
            data_torrent,
        )

    def _process_single_torrent_trackers(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = "default"
    ):
        if torrent.hash in self.tracker_delay:
            return
        self.tracker_delay.add(torrent.hash)
        _remove_urls = set()
        need_to_be_added, monitored_trackers = self._get_torrent_important_trackers(torrent)
        if need_to_be_added:
            torrent.add_trackers(need_to_be_added)
        with contextlib.suppress(BaseException):
            for tracker in torrent.trackers:
                tracker_url = getattr(tracker, "url", None)
                message_text = (getattr(tracker, "msg", "") or "").lower()
                remove_for_message = (
                    self.remove_dead_trackers
                    and self._normalized_bad_tracker_msgs
                    and any(
                        keyword in message_text for keyword in self._normalized_bad_tracker_msgs
                    )
                )
                if not tracker_url:
                    continue
                if (
                    remove_for_message
                    or _extract_tracker_host(tracker_url) in self._remove_tracker_hosts
                ):
                    _remove_urls.add(tracker_url)
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
            dl_r = most_important_tracker.get(
                "DownloadRateLimit", self.seeding_mode_global_download_limit
            )
            if dl_r != 0 and torrent.dl_limit != dl_r:
                torrent.set_download_limit(limit=dl_r)
            elif dl_r < 0:
                torrent.set_download_limit(limit=-1)
            ul_r = most_important_tracker.get(
                "UploadRateLimit", self.seeding_mode_global_upload_limit
            )
            if ul_r != 0 and torrent.up_limit != ul_r:
                torrent.set_upload_limit(limit=ul_r)
            elif ul_r < 0:
                torrent.set_upload_limit(limit=-1)
            if (
                r := most_important_tracker.get("SuperSeedMode", False)
                and torrent.super_seeding != r
            ):
                torrent.set_super_seeding(enabled=r)

        else:
            dl_r = self.seeding_mode_global_download_limit
            if dl_r != 0 and torrent.dl_limit != dl_r:
                torrent.set_download_limit(limit=dl_r)
            elif dl_r < 0:
                torrent.set_download_limit(limit=-1)
            ul_r = self.seeding_mode_global_upload_limit
            if ul_r != 0 and torrent.up_limit != ul_r:
                torrent.set_upload_limit(limit=ul_r)
            elif ul_r < 0:
                torrent.set_upload_limit(limit=-1)

        if unique_tags:
            current_tags = set(torrent.tags.split(", "))
            add_tags = unique_tags.difference(current_tags)
            if add_tags:
                self.add_tags(torrent, add_tags, instance_name)

    def _stalled_check(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        time_now: float,
        instance_name: str = "default",
    ) -> bool:
        stalled_ignore = True
        if not self.allowed_stalled:
            self.logger.trace("Stalled check: Stalled delay disabled")
            return False
        stalled_delay_seconds = int(timedelta(minutes=self.stalled_delay).total_seconds())
        if time_now < torrent.added_on + self.ignore_torrents_younger_than:
            self.logger.trace(
                "Stalled check: In recent queue %s [Current:%s][Added:%s][Starting:%s]",
                torrent.name,
                datetime.fromtimestamp(time_now),
                datetime.fromtimestamp(torrent.added_on),
                datetime.fromtimestamp(torrent.added_on + self.ignore_torrents_younger_than),
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
                datetime.fromtimestamp(torrent.last_activity + stalled_delay_seconds),
            )
        if (
            (
                torrent.state_enum
                in (TorrentStates.METADATA_DOWNLOAD, TorrentStates.STALLED_DOWNLOAD)
                and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
                and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
            )
            or (
                torrent.availability < 1
                and torrent.hash in self.cleaned_torrents
                and torrent.state_enum in (TorrentStates.DOWNLOADING)
                and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
                and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
            )
        ) and self.allowed_stalled:
            if (
                self.stalled_delay > 0
                and time_now >= torrent.last_activity + stalled_delay_seconds
            ):
                stalled_ignore = False
                self.logger.trace("Process stalled, delay expired: %s", torrent.name)
            elif not self.in_tags(torrent, "qBitrr-allowed_stalled", instance_name):
                self.add_tags(torrent, ["qBitrr-allowed_stalled"], instance_name)
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
            elif self.in_tags(torrent, "qBitrr-allowed_stalled", instance_name):
                self.logger.trace(
                    "Stalled: %s [Current:%s][Last Activity:%s][Limit:%s]",
                    torrent.name,
                    datetime.fromtimestamp(time_now),
                    datetime.fromtimestamp(torrent.last_activity),
                    datetime.fromtimestamp(torrent.last_activity + stalled_delay_seconds),
                )

        elif self.in_tags(torrent, "qBitrr-allowed_stalled", instance_name):
            self.remove_tags(torrent, ["qBitrr-allowed_stalled"], instance_name)
            stalled_ignore = False
            self.logger.trace("Not stalled, removing tag: %s", torrent.name)
        else:
            stalled_ignore = False
            self.logger.trace("Not stalled: %s", torrent.name)
        return stalled_ignore

    def _process_single_torrent(
        self, torrent: qbittorrentapi.TorrentDictionary, instance_name: str = "default"
    ):
        if torrent.category != RECHECK_CATEGORY:
            self.manager.qbit_manager.cache[torrent.hash] = torrent.category
        self._process_single_torrent_trackers(torrent, instance_name)
        self.manager.qbit_manager.name_cache[torrent.hash] = torrent.name
        time_now = time.time()
        leave_alone, _tracker_max_eta, remove_torrent, _data_settings, _data_torrent = (
            self._should_leave_alone(torrent, instance_name)
        )
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
            stalled_ignore = self._stalled_check(torrent, time_now, instance_name)
        else:
            stalled_ignore = False

        if self.in_tags(torrent, "qBitrr-ignored", instance_name):
            self.remove_tags(
                torrent, ["qBitrr-allowed_seeding", "qBitrr-free_space_paused"], instance_name
            )

        if (
            self.custom_format_unmet_search
            and self.custom_format_unmet_check(torrent)
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
        ):
            self._process_single_torrent_delete_cfunmet(torrent, instance_name)
        elif remove_torrent and not leave_alone and torrent.amount_left == 0:
            self._process_single_torrent_delete_ratio_seed(
                torrent, limit_meta=(_data_settings, _data_torrent)
            )
        elif torrent.category == FAILED_CATEGORY:
            # Bypass everything if manually marked as failed
            self._process_single_torrent_failed_cat(torrent)
        elif torrent.category == RECHECK_CATEGORY:
            # Bypass everything else if manually marked for rechecking
            self._process_single_torrent_recheck_cat(torrent)
        elif self._is_missing_files_torrent(torrent):
            # Missing-files (and ERROR+missingFiles): bypass all other processing, delete from client.
            self._process_single_torrent_missing_files(torrent, instance_name)
        elif self.is_ignored_state(torrent):
            self._process_single_torrent_ignored(torrent)
        elif (
            torrent.state_enum in (TorrentStates.STOPPED_DOWNLOAD, TorrentStates.STOPPED_UPLOAD)
            and leave_alone
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
        ):
            self.resume.add(torrent.hash)
            self.logger.debug(
                "Resuming stopped torrent: %s (%s) - State[%s]",
                torrent.name,
                torrent.hash,
                torrent.state_enum,
            )
        elif (
            torrent.state_enum in (TorrentStates.METADATA_DOWNLOAD, TorrentStates.STALLED_DOWNLOAD)
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
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
            if (
                torrent.state_enum
                in (TorrentStates.STOPPED_DOWNLOAD, TorrentStates.STOPPED_UPLOAD)
                and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
                and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
            ):
                self.resume.add(torrent.hash)
                self.logger.debug(
                    "Resuming stopped torrent (in ignore cache): %s (%s) - State[%s]",
                    torrent.name,
                    torrent.hash,
                    torrent.state_enum,
                )
            else:
                self._process_single_torrent_added_to_ignore_cache(torrent)
        elif torrent.state_enum == TorrentStates.QUEUED_UPLOAD:
            self._process_single_torrent_queued_upload(torrent, leave_alone)
        # Resume monitored downloads which have been paused.
        elif (
            torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD
            and torrent.amount_left != 0
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
        ):
            self._process_single_torrent_paused(torrent)
        elif (
            torrent.progress <= self.maximum_deletable_percentage
            and not self.is_complete_state(torrent)
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
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
            and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
            and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
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
                and not self.in_tags(torrent, "qBitrr-ignored", instance_name)
                and not self.in_tags(torrent, "qBitrr-free_space_paused", instance_name)
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
            queue = with_retry(
                lambda: self.client.get_queue(),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )

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
            elif self.type == "lidarr":
                entry_id_field = "albumId"
                file_id_field = "AlbumFileId"
            else:
                return False  # Unknown type

            entry_id = record.get(entry_id_field)
            if not entry_id:
                return False

            # Retrieve the model entry from the database
            model_entry = (
                self.model_file.select()
                .where(
                    (self.model_file.EntryId == entry_id)
                    & (self.model_file.ArrInstance == self._name)
                )
                .first()
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

    def _hnr_allows_delete(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        reason: str,
        *,
        data_settings: dict | None = None,
    ) -> bool:
        """Check if HnR obligations allow deleting this torrent.

        Fetches tracker metadata and checks HnR. Returns True if deletion
        is allowed, False if HnR protection blocks it.
        """
        if not any(self._resolve_hnr_clear_mode(t) != "disabled" for t in self.monitored_trackers):
            return True  # Fast path: no HnR on any tracker

        # If the HnR-enabled tracker reports the torrent as unregistered/dead,
        # HnR no longer applies (tracker has removed the torrent).
        if self._hnr_tracker_is_dead(torrent):
            self.logger.debug(
                "HnR bypass: tracker reports torrent as unregistered/dead [%s]",
                torrent.name,
            )
            return True

        if data_settings is None:
            data_settings, _ = self._get_torrent_limit_meta(torrent)
        if self._hnr_safe_to_remove(torrent, data_settings):
            return True
        self.logger.info(
            "HnR protection: blocking %s of [%s] (ratio=%.2f, seeding=%s, progress=%.1f%%)",
            reason,
            torrent.name,
            torrent.ratio,
            timedelta(seconds=torrent.seeding_time),
            torrent.progress * 100,
        )
        return False

    def _hnr_tracker_is_dead(self, torrent: qbittorrentapi.TorrentDictionary) -> bool:
        """Check if the HnR-enabled tracker reports the torrent as unregistered or dead.

        If a tracker says the torrent is unregistered/unauthorized, the torrent
        no longer exists on the tracker and HnR obligations cannot apply.
        """
        _dead_keywords = {
            "unregistered torrent",
            "torrent not registered",
            "info hash is not authorized",
            "torrent is not authorized",
            "not found",
            "torrent not found",
        }
        # Build set of HnR-enabled tracker hostnames
        hnr_hosts = {
            _extract_tracker_host(t.get("URI") or "")
            for t in self.monitored_trackers
            if self._resolve_hnr_clear_mode(t) != "disabled"
        } - {""}
        if not hnr_hosts:
            return False
        try:
            for tracker in torrent.trackers:
                tracker_url = (getattr(tracker, "url", None) or "").rstrip("/")
                if not tracker_url or _extract_tracker_host(tracker_url) not in hnr_hosts:
                    continue
                message_text = (getattr(tracker, "msg", "") or "").lower()
                if any(keyword in message_text for keyword in _dead_keywords):
                    return True
        except Exception:
            pass
        return False

    def _hnr_safe_to_remove(
        self, torrent: qbittorrentapi.TorrentDictionary, tracker_meta: dict
    ) -> bool:
        """Returns True only if Hit and Run obligations are met."""
        clear_mode = (tracker_meta.get("hnr_clear_mode") or "disabled").strip().lower()
        if clear_mode == "disabled":
            return True

        min_ratio = tracker_meta.get("hnr_min_seed_ratio", 1.0)
        min_time_secs = tracker_meta.get("hnr_min_seeding_time_days", 0) * 86400
        min_dl_pct = tracker_meta.get("hnr_min_download_percent", 10) / 100.0
        partial_ratio = tracker_meta.get("hnr_partial_seed_ratio", 1.0)
        buffer_secs = tracker_meta.get("hnr_tracker_update_buffer", 0)

        is_partial = torrent.progress < 1.0 and torrent.progress >= min_dl_pct
        effective_seeding_time = torrent.seeding_time - buffer_secs

        if torrent.progress < min_dl_pct:
            return True  # Below minimum download threshold, no HnR obligation
        if is_partial:
            return torrent.ratio >= partial_ratio  # Partial: ratio only

        ratio_met = torrent.ratio >= min_ratio if min_ratio > 0 else False
        time_met = effective_seeding_time >= min_time_secs if min_time_secs > 0 else False

        if clear_mode == "and":
            if min_ratio > 0 and min_time_secs > 0:
                return ratio_met and time_met
            if min_ratio > 0:
                return ratio_met
            if min_time_secs > 0:
                return time_met
            return True
        if clear_mode == "or":
            if min_ratio > 0 and min_time_secs > 0:
                return ratio_met or time_met
            if min_ratio > 0:
                return ratio_met
            if min_time_secs > 0:
                return time_met
            return True
        return True

    def torrent_limit_check(
        self, torrent: qbittorrentapi.TorrentDictionary, seeding_time_limit, ratio_limit
    ) -> bool:
        # -1 = Never remove (regardless of ratio/time limits)
        if self.seeding_mode_global_remove_torrent == -1:
            return False

        # Treat limits <= 0 as unset; only consider a limit "met" when it is set (>0) and satisfied
        ratio_limit_valid = ratio_limit is not None and ratio_limit > 0
        time_limit_valid = seeding_time_limit is not None and seeding_time_limit > 0
        ratio_met = ratio_limit_valid and torrent.ratio >= ratio_limit
        time_met = time_limit_valid and torrent.seeding_time >= seeding_time_limit

        mode = self.seeding_mode_global_remove_torrent
        if mode in (1, 2, 3, 4) and not ratio_limit_valid and not time_limit_valid:
            if not self._warned_no_seeding_limits:
                self.logger.warning(
                    "RemoveTorrent=%s but neither MaxUploadRatio nor MaxSeedingTime is set; "
                    "skipping seeding-based removal until at least one limit is configured",
                    mode,
                )
                self._warned_no_seeding_limits = True
            return False

        if mode == 4:
            return ratio_met and time_met
        if mode == 3:
            return ratio_met or time_met
        if mode == 2:
            return time_met
        if mode == 1:
            return ratio_met
        return False

    def refresh_download_queue(self):
        self.queue = self.get_queue() or []
        self.queue_active_count = len(self.queue)
        self.category_torrent_count = 0
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
                        with_database_retry(
                            lambda: self.model_queue.delete()
                            .where(
                                (self.model_queue.EntryId.not_in(list(self.queue_file_ids)))
                                & (self.model_queue.ArrInstance == self._name)
                            )
                            .execute(),
                            logger=self.logger,
                        )
                else:
                    for entry in self.queue:
                        if r := entry.get("seriesId"):
                            self.requeue_cache[entry["id"]].add(r)
                    self.queue_file_ids = {
                        entry["seriesId"] for entry in self.queue if entry.get("seriesId")
                    }
                    if self.model_queue:
                        with_database_retry(
                            lambda: self.model_queue.delete()
                            .where(
                                (self.model_queue.EntryId.not_in(list(self.queue_file_ids)))
                                & (self.model_queue.ArrInstance == self._name)
                            )
                            .execute(),
                            logger=self.logger,
                        )
            elif self.type == "radarr":
                self.requeue_cache = {
                    entry["id"]: entry["movieId"] for entry in self.queue if entry.get("movieId")
                }
                self.queue_file_ids = {
                    entry["movieId"] for entry in self.queue if entry.get("movieId")
                }
                if self.model_queue:
                    with_database_retry(
                        lambda: self.model_queue.delete()
                        .where(self.model_queue.EntryId.not_in(list(self.queue_file_ids)))
                        .execute(),
                        logger=self.logger,
                    )
            elif self.type == "lidarr":
                self.requeue_cache = {
                    entry["id"]: entry["albumId"] for entry in self.queue if entry.get("albumId")
                }
                self.queue_file_ids = {
                    entry["albumId"] for entry in self.queue if entry.get("albumId")
                }
                if self.model_queue:
                    with_database_retry(
                        lambda: self.model_queue.delete()
                        .where(self.model_queue.EntryId.not_in(list(self.queue_file_ids)))
                        .execute(),
                        logger=self.logger,
                    )

        self._update_bad_queue_items()

    def get_queue(self, page=1, page_size=1000, sort_direction="ascending", sort_key="timeLeft"):
        res = with_retry(
            lambda: self.client.get_queue(
                page=page, page_size=page_size, sort_key=sort_key, sort_dir=sort_direction
            ),
            retries=3,
            backoff=0.5,
            max_backoff=3,
            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
        )
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
        """
        Parse quality profile name mappings into ID mappings.

        Converts the configured profile name mappings (e.g., {"HD-1080p": "SD"})
        into ID mappings (e.g., {2: 1}) for faster lookups during profile switching.

        Returns:
            dict[int, int]: Mapping of main_profile_id → temp_profile_id
        """
        temp_quality_profile_ids: dict[int, int] = {}

        self.logger.debug(
            "Parsing quality profile mappings: %s",
            self.quality_profile_mappings,
        )

        try:
            profiles = with_retry(
                lambda: self.client.get_quality_profile(),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=(
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                    PyarrServerError,
                ),
            )
            self.logger.debug("Fetched %d quality profiles from API", len(profiles))
        except Exception as e:
            self.logger.error("Unexpected error getting quality profiles: %s", e)
            profiles = []

        # Build a lookup dict for profile name -> ID
        profile_name_to_id = {p["name"]: p["id"] for p in profiles}
        self.logger.trace("Available profiles: %s", profile_name_to_id)

        # Convert name mappings to ID mappings
        for main_name, temp_name in self.quality_profile_mappings.items():
            main_id = profile_name_to_id.get(main_name)
            temp_id = profile_name_to_id.get(temp_name)

            if main_id is None:
                self.logger.error(
                    "Main quality profile '%s' not found in available profiles. Available: %s",
                    main_name,
                    list(profile_name_to_id.keys()),
                )
            if temp_id is None:
                self.logger.error(
                    "Temp quality profile '%s' not found in available profiles. Available: %s",
                    temp_name,
                    list(profile_name_to_id.keys()),
                )

            if main_id is not None and temp_id is not None:
                temp_quality_profile_ids[main_id] = temp_id
                self.logger.info(
                    "Quality profile mapping: '%s' (ID:%d) → '%s' (ID:%d)",
                    main_name,
                    main_id,
                    temp_name,
                    temp_id,
                )
            else:
                self.logger.warning(
                    "Skipping quality profile mapping for '%s' → '%s' due to missing profile(s)",
                    main_name,
                    temp_name,
                )

        if not temp_quality_profile_ids:
            self.logger.error(
                "No valid quality profile mappings created! Check your configuration."
            )

        return temp_quality_profile_ids

    def _reset_all_temp_profiles(self):
        """Reset all items using temp profiles back to their original main profiles on startup."""
        reset_count = 0

        try:
            # Get all items from Arr instance
            if self._name.lower().startswith("radarr"):
                items = self.client.get_movie()
                item_type = "movie"
            elif self._name.lower().startswith("sonarr") or self._name.lower().startswith(
                "animarr"
            ):
                items = self.client.get_series()
                item_type = "series"
            elif self._name.lower().startswith("lidarr"):
                items = self.client.get_artist()
                item_type = "artist"
            else:
                self.logger.warning("Unknown Arr type for temp profile reset: %s", self._name)
                return

            self.logger.info("Checking %d %ss for temp profile resets...", len(items), item_type)

            for item in items:
                profile_id = item.get("qualityProfileId")

                # Check if item is currently using a temp profile
                if profile_id in self.main_quality_profile_ids.keys():
                    # This is a temp profile - get the original main profile
                    original_id = self.main_quality_profile_ids[profile_id]
                    item["qualityProfileId"] = original_id

                    # Update via API with retry logic
                    for attempt in range(self.profile_switch_retry_attempts):
                        try:
                            if item_type == "movie":
                                self.client.upd_movie(item)
                            elif item_type == "series":
                                self.client.upd_series(item)
                            elif item_type == "artist":
                                self.client.upd_artist(item)

                            reset_count += 1
                            self.logger.info(
                                f"Reset {item_type} '{item.get('title', item.get('artistName', 'Unknown'))}' "
                                f"from temp profile (ID:{profile_id}) to main profile (ID:{original_id})"
                            )
                            break
                        except (
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                        ) as e:
                            if attempt == self.profile_switch_retry_attempts - 1:
                                self.logger.error(
                                    f"Failed to reset {item_type} profile after {self.profile_switch_retry_attempts} attempts: {e}"
                                )
                            else:
                                time.sleep(1)
                                continue

            if reset_count > 0:
                self.logger.info(
                    f"ForceResetTempProfiles: Reset {reset_count} {item_type}s from temp to main profiles"
                )
            else:
                self.logger.info(
                    f"ForceResetTempProfiles: No {item_type}s found using temp profiles"
                )

        except Exception as e:
            self.logger.error("Error during temp profile reset: %s", e, exc_info=True)

    def _check_temp_profile_timeouts(self):
        """Check for items with temp profiles that have exceeded the timeout and reset them."""
        if self.temp_profile_timeout_minutes == 0:
            return  # Feature disabled

        timeout_threshold = datetime.now() - timedelta(minutes=self.temp_profile_timeout_minutes)
        reset_count = 0

        try:
            # Query database for items with expired temp profiles
            db1, db2, db3, db4, db5 = self._get_models()

            # Determine which model to use
            if self._name.lower().startswith("radarr"):
                model = self.movies_file_model
                item_type = "movie"
            elif self._name.lower().startswith("sonarr") or self._name.lower().startswith(
                "animarr"
            ):
                model = self.model_file  # episodes
                item_type = "episode"
            elif self._name.lower().startswith("lidarr"):
                model = self.artists_file_model
                item_type = "artist"
            else:
                return

            # Find items with temp profiles that have exceeded timeout
            expired_items = model.select().where(
                (model.ArrInstance == self._name)
                & (model.LastProfileSwitchTime.is_null(False))
                & (model.LastProfileSwitchTime < timeout_threshold)
                & (model.CurrentProfileId.is_null(False))
                & (model.OriginalProfileId.is_null(False))
            )

            for db_item in expired_items:
                entry_id = db_item.EntryId
                current_profile = db_item.CurrentProfileId
                original_profile = db_item.OriginalProfileId

                # Verify current profile is still a temp profile in our mappings
                if current_profile not in self.main_quality_profile_ids.keys():
                    # Not a temp profile anymore, clear tracking
                    model.update(
                        LastProfileSwitchTime=None, CurrentProfileId=None, OriginalProfileId=None
                    ).where(
                        (model.EntryId == entry_id) & (model.ArrInstance == self._name)
                    ).execute()
                    continue

                # Reset to original profile via Arr API
                try:
                    if item_type == "movie":
                        item = self.client.get_movie(entry_id)
                        item["qualityProfileId"] = original_profile
                        self.client.upd_movie(item)
                    elif item_type == "episode":
                        # For episodes, we need to update the series
                        series_id = db_item.SeriesId
                        series = self.client.get_series(series_id)
                        series["qualityProfileId"] = original_profile
                        self.client.upd_series(series)
                    elif item_type == "artist":
                        artist = self.client.get_artist(entry_id)
                        artist["qualityProfileId"] = original_profile
                        self.client.upd_artist(artist)

                    # Clear tracking fields in database
                    model.update(
                        LastProfileSwitchTime=None, CurrentProfileId=None, OriginalProfileId=None
                    ).where(
                        (model.EntryId == entry_id) & (model.ArrInstance == self._name)
                    ).execute()

                    reset_count += 1
                    self.logger.info(
                        f"Timeout reset: {item_type} ID {entry_id} from temp profile (ID:{current_profile}) "
                        f"to main profile (ID:{original_profile}) after {self.temp_profile_timeout_minutes} minutes"
                    )

                except Exception as e:
                    self.logger.error(
                        f"Failed to reset {item_type} ID {entry_id} after timeout: {e}"
                    )

            if reset_count > 0:
                self.logger.info(
                    f"TempProfileTimeout: Reset {reset_count} {item_type}s from temp to main profiles"
                )

        except Exception as e:
            self.logger.error("Error checking temp profile timeouts: %s", e, exc_info=True)

    def register_search_mode(self):
        """Initialize database models using the single shared database."""
        if self.search_setup_completed:
            return

        # Import the shared database
        from qBitrr.database import get_database

        self.db = get_database()

        # Get the appropriate model classes for this Arr type
        file_model, queue_model, series_or_artist_model, track_model, torrent_model = (
            self._get_models()
        )

        # Set model references for this instance
        self.model_file = file_model
        self.model_queue = queue_model
        self.persistent_queue = FilesQueued

        # Set type-specific models
        if self.type == "sonarr":
            self.series_file_model = series_or_artist_model
            self.artists_file_model = None
            self.track_file_model = None
        elif self.type == "lidarr":
            self.series_file_model = None
            self.artists_file_model = series_or_artist_model
            self.track_file_model = track_model
        else:  # radarr
            self.series_file_model = None
            self.artists_file_model = None
            self.track_file_model = None

        # Set torrents model if TAGLESS is enabled
        self.torrents = torrent_model if TAGLESS else None

        self.logger.debug("Database initialization completed for %s", self._name)
        self.search_setup_completed = True

    def _get_models(
        self,
    ) -> tuple[
        type[EpisodeFilesModel] | type[MoviesFilesModel] | type[AlbumFilesModel],
        type[EpisodeQueueModel] | type[MovieQueueModel] | type[AlbumQueueModel],
        type[SeriesFilesModel] | type[ArtistFilesModel] | None,
        type[TrackFilesModel] | None,
        type[TorrentLibrary] | None,
    ]:
        if self.type == "sonarr":
            return (
                EpisodeFilesModel,
                EpisodeQueueModel,
                SeriesFilesModel,
                None,
                TorrentLibrary if TAGLESS else None,
            )
        if self.type == "radarr":
            return (
                MoviesFilesModel,
                MovieQueueModel,
                None,
                None,
                TorrentLibrary if TAGLESS else None,
            )
        if self.type == "lidarr":
            return (
                AlbumFilesModel,
                AlbumQueueModel,
                ArtistFilesModel,
                TrackFilesModel,
                TorrentLibrary if TAGLESS else None,
            )
        raise UnhandledError(f"Well you shouldn't have reached here, Arr.type={self.type}")

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
        totcommands = -1
        if SEARCH_LOOP_DELAY == -1:
            loop_delay = 30
        else:
            loop_delay = SEARCH_LOOP_DELAY
        try:
            event = self.manager.qbit_manager.shutdown_event
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
                    while (not event.is_set()) and (
                        not self.maybe_do_search(
                            entry,
                            request=True,
                            commands=totcommands,
                        )
                    ):
                        self.logger.debug("Waiting for active request search commands")
                        event.wait(loop_delay)
                    self.logger.info("Delaying request search loop by %s seconds", loop_delay)
                    event.wait(loop_delay)
                    if totcommands == 0:
                        self.logger.info("All request searches completed")
                    else:
                        self.logger.info(
                            "Request searches not completed, %s remaining", totcommands
                        )
                self.request_search_timer = time.time()
            except NoConnectionrException as e:
                self.logger.error(e.message)
                raise DelayLoopException(length=300, error_type=e.error_type)
            except DelayLoopException:
                raise
            except Exception as e:
                self.logger.exception(e, exc_info=sys.exc_info())
        except DelayLoopException as e:
            if e.error_type == "qbit":
                self.logger.critical(
                    "Failed to connected to qBit client, sleeping for %s",
                    timedelta(seconds=e.length),
                )
            elif e.error_type == "internet":
                self.logger.critical(
                    "Failed to connected to the internet, sleeping for %s",
                    timedelta(seconds=e.length),
                )
            elif e.error_type == "arr":
                self.logger.critical(
                    "Failed to connected to the Arr instance, sleeping for %s",
                    timedelta(seconds=e.length),
                )
            elif e.error_type == "delay":
                self.logger.critical(
                    "Forced delay due to temporary issue with environment, sleeping for %s",
                    timedelta(seconds=e.length),
                )
            elif e.error_type == "no_downloads":
                self.logger.debug(
                    "No downloads in category, sleeping for %s", timedelta(seconds=e.length)
                )
            # Respect shutdown signal
            self.manager.qbit_manager.shutdown_event.wait(e.length)

    def get_year_search(self) -> tuple[list[int], int]:
        years_list = set()
        years = []
        if self.type == "radarr":
            movies = with_retry(
                lambda: self.client.get_movie(),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
            )

            for m in movies:
                if not m["monitored"]:
                    continue
                if m["year"] != 0 and m["year"] <= datetime.now(timezone.utc).year:
                    years_list.add(m["year"])

        elif self.type == "sonarr":
            series = with_retry(
                lambda: self.client.get_series(),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
            )

            for s in series:
                episodes = with_retry(
                    lambda s=s: self.client.get_episode(s["id"], True),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
                )
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
        self.logger.info(
            "Search loop starting for %s (SearchMissing=%s, DoUpgradeSearch=%s, "
            "QualityUnmetSearch=%s, CustomFormatUnmetSearch=%s, "
            "Overseerr=%s, Ombi=%s)",
            self._name,
            self.search_missing,
            self.do_upgrade_search,
            self.quality_unmet_search,
            self.custom_format_unmet_search,
            self.overseerr_requests,
            self.ombi_search_requests,
        )
        try:
            if not (
                self.search_missing
                or self.do_upgrade_search
                or self.quality_unmet_search
                or self.custom_format_unmet_search
                or self.ombi_search_requests
                or self.overseerr_requests
            ):
                return None
            loop_timer = timedelta(minutes=15)
            timer = datetime.now()
            years_index = 0
            totcommands = -1
            self.db_update_processed = False
            event = self.manager.qbit_manager.shutdown_event
            self.logger.info("Search loop initialized successfully, entering main loop")
            while not event.is_set():
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
                        except Exception:
                            self.search_current_year = years[: years_index + 1]
                    self.logger.debug("Current year %s", self.search_current_year)
                try:
                    self.db_maybe_reset_entry_searched_state()
                    self.refresh_download_queue()
                    self.db_update()

                    # Check for expired temp profiles if feature is enabled
                    if self.use_temp_for_missing and self.temp_profile_timeout_minutes > 0:
                        self._check_temp_profile_timeouts()

                    # Check for new Overseerr/Ombi requests and trigger searches
                    self.run_request_search()
                    try:
                        if self.search_by_year:
                            if years.index(self.search_current_year) != years_count - 1:
                                years_index += 1
                                self.search_current_year = years[years_index]
                            elif datetime.now() >= (timer + loop_timer):
                                self.refresh_download_queue()
                                event.wait(((timer + loop_timer) - datetime.now()).total_seconds())
                                self.logger.trace("Restarting loop testing")
                                try:
                                    self._record_search_activity(None, detail="loop-complete")
                                except Exception:
                                    pass
                                raise RestartLoopException
                        elif datetime.now() >= (timer + loop_timer):
                            self.refresh_download_queue()
                            self.logger.trace("Restarting loop testing")
                            try:
                                self._record_search_activity(None, detail="loop-complete")
                            except Exception:
                                pass
                            raise RestartLoopException
                        any_commands = False
                        for (
                            entry,
                            todays,
                            limit_bypass,
                            series_search,
                            commands,
                        ) in self.db_get_files():
                            any_commands = True
                            if totcommands == -1:
                                totcommands = commands
                                self.logger.info("Starting search for %s items", totcommands)
                            if SEARCH_LOOP_DELAY == -1:
                                loop_delay = 30
                            else:
                                loop_delay = SEARCH_LOOP_DELAY
                            while (not event.is_set()) and (
                                not self.maybe_do_search(
                                    entry,
                                    todays=todays,
                                    bypass_limit=limit_bypass,
                                    series_search=series_search,
                                    commands=totcommands,
                                )
                            ):
                                self.logger.debug("Waiting for active search commands")
                                event.wait(loop_delay)
                            totcommands -= 1
                            self.logger.info("Delaying search loop by %s seconds", loop_delay)
                            event.wait(loop_delay)
                            if totcommands == 0:
                                self.logger.info("All searches completed")
                                try:
                                    self._record_search_activity(
                                        None, detail="no-pending-searches"
                                    )
                                except Exception:
                                    pass
                            elif datetime.now() >= (timer + loop_timer):
                                timer = datetime.now()
                                self.logger.info(
                                    "Searches not completed, %s remaining", totcommands
                                )
                        if not any_commands:
                            self.logger.debug("No pending searches for %s", self._name)
                            try:
                                self._record_search_activity(None, detail="no-pending-searches")
                            except Exception:
                                pass
                    except RestartLoopException:
                        self.loop_completed = True
                        self.db_update_processed = False
                        self.logger.info("Loop timer elapsed, restarting it.")
                    except NoConnectionrException as e:
                        self.logger.error(e.message)
                        self.manager.qbit_manager.should_delay_torrent_scan = True
                        raise DelayLoopException(length=300, error_type=e.error_type)
                    except DelayLoopException:
                        raise
                    except ValueError:
                        self.logger.info("Loop completed, restarting it.")
                        self.loop_completed = True
                    except qbittorrentapi.exceptions.APIConnectionError as e:
                        self.logger.warning(e)
                        raise DelayLoopException(length=300, error_type="qbit")
                    except Exception as e:
                        self.logger.exception(e, exc_info=sys.exc_info())
                    event.wait(LOOP_SLEEP_TIMER)
                except DelayLoopException as e:
                    if e.error_type == "qbit":
                        self.logger.critical(
                            "Failed to connected to qBit client, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.error_type == "internet":
                        self.logger.critical(
                            "Failed to connected to the internet, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.error_type == "arr":
                        self.logger.critical(
                            "Failed to connected to the Arr instance, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.error_type == "delay":
                        self.logger.critical(
                            "Forced delay due to temporary issue with environment, "
                            "sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    event.wait(e.length)
                    self.manager.qbit_manager.should_delay_torrent_scan = False
                except KeyboardInterrupt:
                    self.logger.hnotice("Detected Ctrl+C - Terminating process")
                    sys.exit(0)
                else:
                    event.wait(5)
        except KeyboardInterrupt:
            self.logger.hnotice("Detected Ctrl+C - Terminating process")
            sys.exit(0)
        except Exception as e:
            self.logger.critical(
                "Search loop crashed unexpectedly for %s: %s",
                self._name,
                e,
                exc_info=True,
            )
            raise
        finally:
            self.logger.warning("Search loop terminated for %s", self._name)

    def run_torrent_loop(self) -> NoReturn:
        run_logs(self.logger)
        self.logger.hnotice("Starting torrent monitoring for %s", self._name)
        event = self.manager.qbit_manager.shutdown_event
        while not event.is_set():
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
                        raise DelayLoopException(length=300, error_type="arr")
                    except qbittorrentapi.exceptions.APIConnectionError as e:
                        self.logger.warning(e)
                        raise DelayLoopException(length=300, error_type="qbit")
                    except qbittorrentapi.exceptions.APIError as e:
                        self.logger.warning(e)
                        raise DelayLoopException(length=300, error_type="qbit")
                    except DelayLoopException:
                        raise
                    except KeyboardInterrupt:
                        self.logger.hnotice("Detected Ctrl+C - Terminating process")
                        sys.exit(0)
                    except Exception as e:
                        self.logger.error(e, exc_info=sys.exc_info())
                    event.wait(LOOP_SLEEP_TIMER)
                except DelayLoopException as e:
                    if e.error_type == "qbit":
                        self.logger.critical(
                            "Failed to connected to qBit client, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.error_type == "internet":
                        self.logger.critical(
                            "Failed to connected to the internet, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.error_type == "arr":
                        self.logger.critical(
                            "Failed to connected to the Arr instance, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    elif e.error_type == "delay":
                        self.logger.critical(
                            "Forced delay due to temporary issue with environment, "
                            "sleeping for %s.",
                            timedelta(seconds=e.length),
                        )
                    elif e.error_type == "no_downloads":
                        self.logger.debug(
                            "No downloads in category, sleeping for %s",
                            timedelta(seconds=e.length),
                        )
                    event.wait(e.length)
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
                target=self.run_search_loop, daemon=False
            )
            self.manager.qbit_manager.child_processes.append(self.process_search_loop)
            _temp.append(self.process_search_loop)
        if not (QBIT_DISABLED or SEARCH_ONLY):
            self.process_torrent_loop = pathos.helpers.mp.Process(
                target=self.run_torrent_loop, daemon=False
            )
            self.manager.qbit_manager.child_processes.append(self.process_torrent_loop)
            _temp.append(self.process_torrent_loop)

        return len(_temp), _temp


class PlaceHolderArr(Arr):
    def __init__(self, name: str, manager: ArrManager):
        if name in manager.groups:
            raise OSError(f"Group '{name}' has already been registered.")
        self.type = "placeholder"
        self._name = name.title()
        self.category = name
        self.manager = manager
        self.queue = []
        self.cache = {}
        self.requeue_cache = {}
        self.sent_to_scan = set()
        self.sent_to_scan_hashes = set()
        self.files_probed = set()
        self.files_to_cleanup = set()
        self.import_torrents = []
        self.change_priority = {}
        self.recheck = set()
        self.pause = set()
        self.skip_blacklist = set()
        self.remove_from_qbit = set()
        self.remove_from_qbit_by_instance: dict[str, set[str]] = {}
        self.delete = set()
        self.resume = set()
        self.expiring_bool = ExpiringSet(max_age_seconds=10)
        self.ignore_torrents_younger_than = CONFIG.get_duration(
            "Settings.IgnoreTorrentsYoungerThan", fallback=180
        )
        self.timed_ignore_cache = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.timed_ignore_cache_2 = ExpiringSet(
            max_age_seconds=self.ignore_torrents_younger_than * 2
        )
        self.timed_skip = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.tracker_delay = ExpiringSet(max_age_seconds=600)
        self.special_casing_file_check = ExpiringSet(max_age_seconds=10)
        self.cleaned_torrents = set()
        self.missing_files_post_delete = set()
        self.downloads_with_bad_error_message_blocklist = set()
        self.needs_cleanup = False
        self._warned_no_seeding_limits = False
        self.custom_format_unmet_search = False
        self.do_not_remove_slow = False
        self.maximum_eta = CONFIG.get_duration("Settings.Torrent.MaximumETA", fallback=86400)
        self.maximum_deletable_percentage = CONFIG.get(
            "Settings.Torrent.MaximumDeletablePercentage", fallback=0.95
        )
        self.folder_exclusion_regex = None
        self.file_name_exclusion_regex = None
        self.file_extension_allowlist = None
        self.folder_exclusion_regex_re = None
        self.file_name_exclusion_regex_re = None
        self.file_extension_allowlist_re = None
        self.re_search_stalled = False
        self.monitored_trackers = []
        self._host_to_config_uri = {}
        self._add_trackers_if_missing = set()
        self._remove_trackers_if_exists = set()
        self._monitored_tracker_urls = set()
        self.remove_dead_trackers = False
        self._remove_tracker_hosts = set()
        self._normalized_bad_tracker_msgs = set()
        self.seeding_mode_global_remove_torrent = -1
        self.seeding_mode_global_max_upload_ratio = -1
        self.seeding_mode_global_max_seeding_time = -1
        self.seeding_mode_global_download_limit = -1
        self.seeding_mode_global_upload_limit = -1
        self.seeding_mode_global_bad_tracker_msg = []
        self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(self.category)
        self._LOG_LEVEL = self.manager.qbit_manager.logger.level
        self.logger = logging.getLogger(f"qBitrr.{self._name}")
        run_logs(self.logger, self._name)
        self.manager.completed_folders.add(self.completed_folder)
        self.manager.category_allowlist.add(self.category)
        self.stalled_delay = -1
        self.allowed_stalled = False
        if self.category in self.manager.qbit_managed_categories:
            self._apply_qbit_seeding_config()
        self.search_missing = False
        self.session = None
        self.search_setup_completed = False
        self.last_search_description: str | None = None
        self.last_search_timestamp: str | None = None
        self.queue_active_count: int = 0
        self.category_torrent_count: int = 0
        self.free_space_tagged_count: int = 0
        if TAGLESS:
            self.register_search_mode()
        else:
            self.torrents = None
            self.db = None
            self.search_setup_completed = True
        self.logger.hnotice("Starting %s monitor", self._name)

    def _get_models(
        self,
    ) -> tuple[
        None,
        None,
        None,
        None,
        type[TorrentLibrary] | None,
    ]:
        """PlaceHolderArr has no file/queue models; only TorrentLibrary when TAGLESS."""
        return None, None, None, None, (TorrentLibrary if TAGLESS else None)

    def _process_single_torrent_missing_files(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        instance_name: str = "default",
    ) -> None:
        """Track which qBit instance the torrent is on so we delete from the correct client."""
        super()._process_single_torrent_missing_files(torrent, instance_name)

    def custom_format_unmet_check(self, torrent: qbittorrentapi.TorrentDictionary) -> bool:
        """PlaceHolderArr does not use Arr queue; never trigger custom-format branch."""
        return False

    def _apply_qbit_seeding_config(self) -> None:
        """Load qBit CategorySeeding/Trackers for this category's owning qBit section."""
        section = self.manager.qbit_managed_category_sections.get(self.category, "qBit")
        seeding_keys = [
            "DownloadRateLimitPerTorrent",
            "UploadRateLimitPerTorrent",
            "MaxUploadRatio",
            "MaxSeedingTime",
            "RemoveTorrent",
        ]
        default_seeding = {}
        for key in seeding_keys:
            if key == "MaxSeedingTime":
                default_seeding[key] = CONFIG.get_duration(
                    f"{section}.CategorySeeding.{key}", fallback=-1
                )
            else:
                default_seeding[key] = CONFIG.get(f"{section}.CategorySeeding.{key}", fallback=-1)
        for key, fallback in (
            ("HitAndRunMode", "disabled"),
            ("MinSeedRatio", 1.0),
            ("MinSeedingTimeDays", 0),
            ("HitAndRunPartialSeedRatio", 1.0),
            ("TrackerUpdateBuffer", 0),
        ):
            if key == "TrackerUpdateBuffer":
                default_seeding[key] = CONFIG.get_duration(
                    f"{section}.CategorySeeding.{key}", fallback=fallback
                )
            else:
                default_seeding[key] = CONFIG.get(
                    f"{section}.CategorySeeding.{key}", fallback=fallback
                )
        category_overrides = {}
        for cat_config in CONFIG.get(f"{section}.CategorySeeding.Categories", fallback=[]):
            if isinstance(cat_config, dict) and "Name" in cat_config:
                category_overrides[cat_config["Name"]] = cat_config
        effective = dict(default_seeding)
        if self.category in category_overrides:
            effective.update(category_overrides[self.category])
        self.seeding_mode_global_remove_torrent = effective.get("RemoveTorrent", -1)
        self.seeding_mode_global_max_upload_ratio = effective.get("MaxUploadRatio", -1)
        self.seeding_mode_global_max_seeding_time = effective.get("MaxSeedingTime", -1)
        self.seeding_mode_global_download_limit = effective.get("DownloadRateLimitPerTorrent", -1)
        self.seeding_mode_global_upload_limit = effective.get("UploadRateLimitPerTorrent", -1)
        self.stalled_delay = CONFIG.get_duration(
            f"{section}.CategorySeeding.StalledDelay", fallback=-1, unit="minutes"
        )
        self.allowed_stalled = self.stalled_delay != -1
        self.monitored_trackers = CONFIG.get(f"{section}.Trackers", fallback=[])
        self._remove_trackers_if_exists = {
            uri
            for i in self.monitored_trackers
            if i.get("RemoveIfExists") is True
            and (uri := (i.get("URI") or "").strip().rstrip("/"))
        }
        self._monitored_tracker_urls = {
            uri
            for i in self.monitored_trackers
            if (uri := (i.get("URI") or "").strip().rstrip("/"))
            and uri not in self._remove_trackers_if_exists
        }
        self._add_trackers_if_missing = {
            uri
            for i in self.monitored_trackers
            if i.get("AddTrackerIfMissing") is True
            and (uri := (i.get("URI") or "").strip().rstrip("/"))
        }
        self._host_to_config_uri = {}
        for _uri in self._monitored_tracker_urls:
            _host = _extract_tracker_host(_uri)
            if _host:
                self._host_to_config_uri[_host] = _uri
        self._remove_tracker_hosts = {
            h for u in self._remove_trackers_if_exists if (h := _extract_tracker_host(u))
        }
        self.logger.debug(
            "Applied qBit seeding config from section '%s' for category '%s': "
            "RemoveTorrent=%s, StalledDelay=%s",
            section,
            self.category,
            self.seeding_mode_global_remove_torrent,
            self.stalled_delay,
        )

    def _process_failed(self) -> None:
        """Delete torrents from the correct qBit instance and log any delete failures."""
        to_delete_all = self.delete.union(
            self.missing_files_post_delete, self.downloads_with_bad_error_message_blocklist
        )
        skip_blacklist = {
            i.upper() for i in self.skip_blacklist.union(self.missing_files_post_delete)
        }
        if not (
            to_delete_all
            or self.remove_from_qbit
            or self.skip_blacklist
            or self.remove_from_qbit_by_instance
        ):
            return
        n_delete = len(self.delete)
        n_missing = len(self.missing_files_post_delete)
        n_bad_msg = len(self.downloads_with_bad_error_message_blocklist)
        n_remove = len(self.remove_from_qbit)
        n_remove_by_inst = sum(len(s) for s in self.remove_from_qbit_by_instance.values())
        n_skip = len(self.skip_blacklist)
        self.logger.info(
            "Deletion summary: delete=%d, missing_files=%d, bad_error_blocklist=%d, "
            "remove_from_qbit=%d, remove_by_instance=%d, skip_blacklist=%d",
            n_delete,
            n_missing,
            n_bad_msg,
            n_remove,
            n_remove_by_inst,
            n_skip,
        )
        if to_delete_all:
            for arr in self.manager.managed_objects.values():
                if payload := arr.process_entries(to_delete_all):
                    for entry, hash_ in payload:
                        if hash_ in arr.cache:
                            arr._process_failed_individual(
                                hash_=hash_, entry=entry, skip_blacklist=skip_blacklist
                            )
        deleted_hashes: set[str] = set()
        qbit_manager = self.manager.qbit_manager
        # Delete per-instance (e.g. missing-files) so we use the correct qBit client.
        for instance_name, hashes in self.remove_from_qbit_by_instance.items():
            client = qbit_manager.get_client(instance_name)
            if client is None:
                self.logger.warning(
                    "Cannot delete %d torrent(s) from qBit instance '%s': no client",
                    len(hashes),
                    instance_name,
                )
                continue
            try:
                with_retry(
                    lambda c=client, h=hashes: c.torrents_delete(hashes=h, delete_files=True),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=(
                        qbittorrentapi.exceptions.APIError,
                        qbittorrentapi.exceptions.APIConnectionError,
                        requests.exceptions.RequestException,
                    ),
                )
                deleted_hashes.update(hashes)
            except (
                qbittorrentapi.exceptions.APIError,
                qbittorrentapi.exceptions.APIConnectionError,
                requests.exceptions.RequestException,
            ) as e:
                self.logger.error(
                    "Failed to delete %d torrent(s) from qBit instance '%s': %s",
                    len(hashes),
                    instance_name,
                    e,
                )
        # Remaining remove_from_qbit/skip_blacklist and to_delete_all via default client.
        if self.remove_from_qbit or self.skip_blacklist or to_delete_all:
            temp_to_delete = set()
            if to_delete_all:
                if self.manager.qbit:
                    try:
                        with_retry(
                            lambda: self.manager.qbit.torrents_delete(
                                hashes=to_delete_all, delete_files=True
                            ),
                            retries=3,
                            backoff=0.5,
                            max_backoff=3,
                            exceptions=(
                                qbittorrentapi.exceptions.APIError,
                                qbittorrentapi.exceptions.APIConnectionError,
                                requests.exceptions.RequestException,
                            ),
                        )
                        temp_to_delete.update(to_delete_all)
                    except (
                        qbittorrentapi.exceptions.APIError,
                        qbittorrentapi.exceptions.APIConnectionError,
                        requests.exceptions.RequestException,
                    ) as e:
                        self.logger.error(
                            "Failed to delete %d torrent(s) from qBit (to_delete_all): %s",
                            len(to_delete_all),
                            e,
                        )
                else:
                    self.logger.warning(
                        "Cannot delete to_delete_all: no qBit client (manager.qbit is None)"
                    )
            if self.remove_from_qbit or self.skip_blacklist:
                rest = (self.remove_from_qbit.union(self.skip_blacklist)) - deleted_hashes
                if rest and self.manager.qbit:
                    try:
                        with_retry(
                            lambda: self.manager.qbit.torrents_delete(
                                hashes=rest, delete_files=True
                            ),
                            retries=3,
                            backoff=0.5,
                            max_backoff=3,
                            exceptions=(
                                qbittorrentapi.exceptions.APIError,
                                qbittorrentapi.exceptions.APIConnectionError,
                                requests.exceptions.RequestException,
                            ),
                        )
                        temp_to_delete.update(rest)
                    except (
                        qbittorrentapi.exceptions.APIError,
                        qbittorrentapi.exceptions.APIConnectionError,
                        requests.exceptions.RequestException,
                    ) as e:
                        self.logger.error(
                            "Failed to delete %d torrent(s) from qBit (remove/blacklist): %s",
                            len(rest),
                            e,
                        )
                elif rest:
                    self.logger.warning(
                        "Cannot delete %d torrent(s): no qBit client (manager.qbit is None)",
                        len(rest),
                    )
            to_delete_all = to_delete_all.union(temp_to_delete).union(deleted_hashes)
            for h in to_delete_all:
                self.cleaned_torrents.discard(h)
                self.sent_to_scan_hashes.discard(h)
                if h in self.manager.qbit_manager.name_cache:
                    del self.manager.qbit_manager.name_cache[h]
                if h in self.manager.qbit_manager.cache:
                    del self.manager.qbit_manager.cache[h]
        if self.missing_files_post_delete or self.downloads_with_bad_error_message_blocklist:
            self.missing_files_post_delete.clear()
            self.downloads_with_bad_error_message_blocklist.clear()
        self.skip_blacklist.clear()
        self.remove_from_qbit.clear()
        self.remove_from_qbit_by_instance.clear()
        self.delete.clear()

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
        with contextlib.suppress(Exception):
            with_retry(
                lambda: self.manager.qbit.torrents_recheck(torrent_hashes=updated_recheck),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=(
                    qbittorrentapi.exceptions.APIError,
                    qbittorrentapi.exceptions.APIConnectionError,
                    requests.exceptions.RequestException,
                ),
            )
        for k, v in temp.items():
            with contextlib.suppress(Exception):
                with_retry(
                    lambda: self.manager.qbit.torrents_set_category(torrent_hashes=v, category=k),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=(
                        qbittorrentapi.exceptions.APIError,
                        qbittorrentapi.exceptions.APIConnectionError,
                        requests.exceptions.RequestException,
                    ),
                )

        for k in updated_recheck:
            self.timed_ignore_cache.add(k)
        self.recheck.clear()

    def process(self):
        self._process_resume()
        self._process_paused()
        self._process_errored()
        self._process_file_priority()
        self._process_failed()
        self.import_torrents.clear()
        with contextlib.suppress(AttributeError):
            self.files_to_cleanup.clear()

    def process_torrents(self):
        try:
            try:
                torrents_with_instances = with_retry(
                    lambda: self._get_torrents_from_all_instances(),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=(JSONDecodeError,),
                )

                torrents_with_instances = [
                    (instance, t)
                    for instance, t in torrents_with_instances
                    if getattr(t, "category", None) == self.category
                ]
                self._warned_no_seeding_limits = False
                self.category_torrent_count = len(torrents_with_instances)
                if not torrents_with_instances:
                    raise DelayLoopException(length=LOOP_SLEEP_TIMER, error_type="no_downloads")

                if not has_internet(self.manager.qbit_manager.client):
                    self.manager.qbit_manager.should_delay_torrent_scan = True
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, error_type="internet")
                if self.manager.qbit_manager.should_delay_torrent_scan:
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, error_type="delay")

                for instance_name, torrent in torrents_with_instances:
                    with contextlib.suppress(qbittorrentapi.NotFound404Error):
                        self._process_single_torrent(torrent, instance_name=instance_name)
                self.process()
            except NoConnectionrException as e:
                self.logger.error(e.message)
            except qbittorrentapi.exceptions.APIError as e:
                self.logger.error("The qBittorrent API returned an unexpected error")
                self.logger.debug("Unexpected APIError from qBitTorrent", exc_info=e)
                raise DelayLoopException(length=300, error_type="qbit")
            except qbittorrentapi.exceptions.APIConnectionError:
                self.logger.warning("Max retries exceeded")
                raise DelayLoopException(length=300, error_type="qbit")
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


class FreeSpaceManager(Arr):
    def __init__(self, categories: set[str], manager: ArrManager):
        self._name = "FreeSpaceManager"
        self.type = "FreeSpaceManager"
        self.manager = manager
        self.logger = logging.getLogger(f"qBitrr.{self._name}")
        self._LOG_LEVEL = self.manager.qbit_manager.logger.level
        run_logs(self.logger, self._name)
        self.cache = {}
        self.categories = categories
        self.logger.trace("Categories: %s", self.categories)
        self.pause = set()
        self.resume = set()
        self.expiring_bool = ExpiringSet(max_age_seconds=10)
        self.ignore_torrents_younger_than = CONFIG.get_duration(
            "Settings.IgnoreTorrentsYoungerThan", fallback=180
        )
        self.timed_ignore_cache = ExpiringSet(max_age_seconds=self.ignore_torrents_younger_than)
        self.needs_cleanup = False
        self._app_data_folder = APPDATA_FOLDER
        # Track search setup state to cooperate with Arr.register_search_mode
        self.search_setup_completed = False
        if FREE_SPACE_FOLDER == CHANGE_ME_SENTINEL:
            # Prefer an Arr-managed category so the path exists (Arr uses category subdirs).
            # qBit-managed-only categories may have no subdir under COMPLETED_DOWNLOAD_FOLDER.
            arr_cats = self.categories & self.manager.arr_categories
            chosen = next(iter(arr_cats), None) or next(iter(self.categories))
            self.completed_folder = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).joinpath(chosen)
            # Use the main completed-download folder for disk usage so we report the same
            # filesystem the user expects (doc default: "Same as CompletedDownloadFolder").
            # A category subdir may be a different mount and report much less free space.
            self._disk_usage_path = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER).resolve()
        else:
            self.completed_folder = pathlib.Path(FREE_SPACE_FOLDER)
            self._disk_usage_path = pathlib.Path(FREE_SPACE_FOLDER).resolve()
        self._free_space_folder_is_auto = FREE_SPACE_FOLDER == CHANGE_ME_SENTINEL
        self.min_free_space = FREE_SPACE
        # Parse once to avoid repeated conversions
        self._min_free_space_bytes = (
            parse_size(self.min_free_space) if self.min_free_space != "-1" else 0
        )
        if FREE_SPACE_FOLDER == CHANGE_ME_SENTINEL and not self.completed_folder.exists():
            # Fallback to parent when chosen category subdir doesn't exist (e.g. qBit-only).
            parent = pathlib.Path(COMPLETED_DOWNLOAD_FOLDER)
            if parent.exists():
                self.completed_folder = parent
            # else: keep completed_folder and let disk_usage raise so the user sees the error
        # Path for disk usage: use resolved path. Only when path was auto-chosen (CHANGE_ME),
        # allow falling back to first existing parent so we still report the correct volume;
        # when the user explicitly set FreeSpaceFolder, do not substitute—missing path should
        # error so they fix typo/mount instead of monitoring the wrong filesystem.
        self._path_for_disk_usage = self._disk_usage_path
        if self._free_space_folder_is_auto:
            _p = self._first_existing_parent(self._disk_usage_path)
            if _p:
                self._path_for_disk_usage = _p
                if self._path_for_disk_usage != self._disk_usage_path:
                    self.logger.warning(
                        "FreeSpaceFolder path does not exist, using parent for disk space check | "
                        "Configured: %s | Using: %s%s",
                        self._disk_usage_path,
                        self._path_for_disk_usage,
                        (
                            " | In Docker: ensure the host volume is mounted at the configured path (e.g. -v /host/torrents:/torrents)"
                            if is_docker()
                            else ""
                        ),
                    )
        self.current_free_space = (
            shutil.disk_usage(self._path_for_disk_usage).free - self._min_free_space_bytes
        )
        self.logger.trace(
            "Free space monitor initialized | Path: %s | Available: %s | Threshold: %s",
            self._path_for_disk_usage,
            format_bytes(self.current_free_space + self._min_free_space_bytes),
            format_bytes(self._min_free_space_bytes),
        )
        _client = self.manager.qbit_manager.client
        if _client is not None:
            _client.torrents_create_tags(["qBitrr-free_space_paused"])
        self.search_missing = False
        self.do_upgrade_search = False
        self.quality_unmet_search = False
        self.custom_format_unmet_search = False
        self.ombi_search_requests = False
        self.overseerr_requests = False
        self.session = None
        # Ensure torrent tag-emulation tables exist when needed.
        self.torrents = None
        self.torrent_db: SqliteDatabase | None = None
        self.last_search_description: str | None = None
        self.last_search_timestamp: str | None = None
        self.queue_active_count: int = 0
        self.category_torrent_count: int = 0
        self.free_space_tagged_count: int = 0
        self.register_search_mode()
        self.logger.hnotice("Starting %s monitor", self._name)
        atexit.register(
            lambda: (
                hasattr(self, "torrent_db")
                and self.torrent_db
                and not self.torrent_db.is_closed()
                and self.torrent_db.close()
            )
        )

    @staticmethod
    def _first_existing_parent(path: pathlib.Path) -> pathlib.Path | None:
        """Return the nearest existing parent path, or None if none exist (e.g. path below root)."""
        current = path
        while not current.exists():
            parent = current.parent
            if parent == current:
                return None
            current = parent
        return current

    def _get_models(
        self,
    ) -> tuple[
        None,
        None,
        None,
        None,
        type[TorrentLibrary] | None,
    ]:
        return None, None, None, None, (TorrentLibrary if TAGLESS else None)

    def _process_single_torrent_pause_disk_space(self, torrent: qbittorrentapi.TorrentDictionary):
        self.logger.info(
            "Pausing torrent due to insufficient disk space | "
            "Name: %s | Progress: %s%% | Size remaining: %s | "
            "Availability: %s%% | ETA: %s | State: %s | Hash: %s",
            torrent.name,
            round(torrent.progress * 100, 2),
            format_bytes(torrent.amount_left),
            round(torrent.availability * 100, 2),
            timedelta(seconds=torrent.eta),
            torrent.state_enum,
            torrent.hash[:8],  # Shortened hash for readability
        )
        self.pause.add(torrent.hash)

    def _process_single_torrent(self, torrent, instance_name: str = "default"):
        if self.is_downloading_state(torrent):
            free_space_test = self.current_free_space
            free_space_test -= torrent["amount_left"]
            self.logger.trace(
                "Evaluating torrent: %s | Current space: %s | Space after download: %s | Remaining: %s",
                torrent.name,
                format_bytes(self.current_free_space + self._min_free_space_bytes),
                format_bytes(free_space_test + self._min_free_space_bytes),
                format_bytes(torrent.amount_left),
            )
            if torrent.state_enum != TorrentStates.PAUSED_DOWNLOAD and free_space_test < 0:
                self.logger.info(
                    "Pausing download (insufficient space) | Torrent: %s | Available: %s | Needed: %s | Deficit: %s",
                    torrent.name,
                    format_bytes(self.current_free_space + self._min_free_space_bytes),
                    format_bytes(torrent.amount_left),
                    format_bytes(-free_space_test),
                )
                self.add_tags(torrent, ["qBitrr-free_space_paused"], instance_name)
                self.remove_tags(torrent, ["qBitrr-allowed_seeding"], instance_name)
                self._process_single_torrent_pause_disk_space(torrent)
            elif torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD and free_space_test < 0:
                self.logger.info(
                    "Keeping paused (insufficient space) | Torrent: %s | Available: %s | Needed: %s | Deficit: %s",
                    torrent.name,
                    format_bytes(self.current_free_space + self._min_free_space_bytes),
                    format_bytes(torrent.amount_left),
                    format_bytes(-free_space_test),
                )
                self.add_tags(torrent, ["qBitrr-free_space_paused"], instance_name)
                self.remove_tags(torrent, ["qBitrr-allowed_seeding"], instance_name)
            elif torrent.state_enum != TorrentStates.PAUSED_DOWNLOAD and free_space_test > 0:
                self.logger.info(
                    "Continuing download (sufficient space) | Torrent: %s | Available: %s | Space after: %s",
                    torrent.name,
                    format_bytes(self.current_free_space + self._min_free_space_bytes),
                    format_bytes(free_space_test + self._min_free_space_bytes),
                )
                self.current_free_space = free_space_test
                self.remove_tags(torrent, ["qBitrr-free_space_paused"], instance_name)
            elif torrent.state_enum == TorrentStates.PAUSED_DOWNLOAD and free_space_test > 0:
                self.logger.info(
                    "Resuming download (space available) | Torrent: %s | Available: %s | Space after: %s",
                    torrent.name,
                    format_bytes(self.current_free_space + self._min_free_space_bytes),
                    format_bytes(free_space_test + self._min_free_space_bytes),
                )
                self.current_free_space = free_space_test
                self.remove_tags(torrent, ["qBitrr-free_space_paused"], instance_name)
        elif not self.is_downloading_state(torrent) and self.in_tags(
            torrent, "qBitrr-free_space_paused", instance_name
        ):
            self.logger.info(
                "Torrent completed, removing free space tag | Torrent: %s | Available: %s",
                torrent.name,
                format_bytes(self.current_free_space + self._min_free_space_bytes),
            )
            self.remove_tags(torrent, ["qBitrr-free_space_paused"], instance_name)

    def process(self):
        self._process_paused()

    def process_torrents(self):
        try:
            try:
                _client = self.manager.qbit_manager.client
                if _client is None:
                    raise DelayLoopException(length=LOOP_SLEEP_TIMER, error_type="no_downloads")

                def _fetch_free_space_torrents():
                    result = []
                    for cat in self.categories:
                        with contextlib.suppress(qbittorrentapi.exceptions.APIError):
                            result.extend(
                                _client.torrents.info(
                                    status_filter="all",
                                    category=cat,
                                    sort="added_on",
                                    reverse=False,
                                )
                            )
                    return result

                torrents = with_retry(
                    _fetch_free_space_torrents,
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=(qbittorrentapi.exceptions.APIError,),
                )
                torrents = [t for t in torrents if hasattr(t, "category")]
                torrents = [t for t in torrents if t.category in self.categories]
                torrents = [t for t in torrents if "qBitrr-ignored" not in t.tags]
                self.category_torrent_count = len(torrents)
                _first_instance = next(iter(self.manager.qbit_manager.clients), "qBit")
                self.free_space_tagged_count = sum(
                    1
                    for t in torrents
                    if self.in_tags(t, "qBitrr-free_space_paused", _first_instance)
                )
                if not len(torrents):
                    raise DelayLoopException(length=LOOP_SLEEP_TIMER, error_type="no_downloads")
                if not has_internet(self.manager.qbit_manager.client):
                    self.manager.qbit_manager.should_delay_torrent_scan = True
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, error_type="internet")
                if self.manager.qbit_manager.should_delay_torrent_scan:
                    raise DelayLoopException(length=NO_INTERNET_SLEEP_TIMER, error_type="delay")
                # Re-resolve path each loop so we use the configured path once it appears
                # (e.g. Docker volume mounted after process start). Only when path was
                # auto-chosen (CHANGE_ME); explicit FreeSpaceFolder must exist or we error.
                if self._free_space_folder_is_auto:
                    _p = self._first_existing_parent(self._disk_usage_path)
                    if _p:
                        self._path_for_disk_usage = _p
                self.current_free_space = (
                    shutil.disk_usage(self._path_for_disk_usage).free - self._min_free_space_bytes
                )
                self.logger.trace(
                    "Processing torrents | Available: %s | Threshold: %s | Usable: %s | Torrents: %d | Paused for space: %d",
                    format_bytes(self.current_free_space + self._min_free_space_bytes),
                    format_bytes(self._min_free_space_bytes),
                    format_bytes(self.current_free_space),
                    self.category_torrent_count,
                    self.free_space_tagged_count,
                )
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
                raise DelayLoopException(length=300, error_type="qbit")
            except qbittorrentapi.exceptions.APIConnectionError:
                self.logger.warning("Max retries exceeded")
                raise DelayLoopException(length=300, error_type="qbit")
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
        self.qbit_managed_categories: set[str] = set()
        self.qbit_managed_category_sections: dict[str, str] = {}
        self.category_allowlist: set[str] = self.special_categories.copy()
        self.completed_folders: set[pathlib.Path] = set()
        self.managed_objects: dict[str, Arr] = {}
        self.qbit: qbittorrentapi.Client | None = qbitmanager.client
        self.qbit_manager: qBitManager = qbitmanager
        self.ffprobe_available: bool = self.qbit_manager.ffprobe_downloader.probe_path.exists()
        self.logger = logging.getLogger("qBitrr.ArrManager")
        run_logs(self.logger)
        if not self.ffprobe_available and not (QBIT_DISABLED or SEARCH_ONLY):
            self.logger.error(
                "'%s' was not found, disabling all functionality dependant on it",
                self.qbit_manager.ffprobe_downloader.probe_path,
            )

    def _validate_category_assignments(self):
        """
        Validate that no category is managed by both Arr and qBit instances.

        Collects all qBit-managed categories from all qBit instances and checks
        for conflicts with Arr-managed categories. Allows same category on
        multiple qBit instances (acceptable).

        Raises:
            ValueError: If any category is managed by both Arr and qBit
        """
        # Collect qBit-managed categories from all instances
        self.qbit_managed_categories.clear()
        self.qbit_managed_category_sections.clear()
        for section in CONFIG.sections():
            # Check default qBit section
            if section == "qBit":
                managed_cats = CONFIG.get("qBit.ManagedCategories", fallback=[])
                if managed_cats:
                    self.qbit_managed_categories.update(managed_cats)
                    for category in managed_cats:
                        owner = self.qbit_managed_category_sections.setdefault(category, section)
                        if owner != section:
                            self.logger.warning(
                                "Category '%s' is managed by both '%s' and '%s'; "
                                "PlaceHolderArr will use '%s' seeding config",
                                category,
                                owner,
                                section,
                                owner,
                            )
                    self.logger.debug(
                        "qBit instance 'default' manages categories: %s",
                        ", ".join(managed_cats),
                    )
            # Check additional qBit-XXX sections
            elif section.startswith("qBit-"):
                instance_name = section.replace("qBit-", "", 1)
                managed_cats = CONFIG.get(f"{section}.ManagedCategories", fallback=[])
                if managed_cats:
                    self.qbit_managed_categories.update(managed_cats)
                    for category in managed_cats:
                        owner = self.qbit_managed_category_sections.setdefault(category, section)
                        if owner != section:
                            self.logger.warning(
                                "Category '%s' is managed by both '%s' and '%s'; "
                                "PlaceHolderArr will use '%s' seeding config",
                                category,
                                owner,
                                section,
                                owner,
                            )
                    self.logger.debug(
                        "qBit instance '%s' manages categories: %s",
                        instance_name,
                        ", ".join(managed_cats),
                    )

        # Check for conflicts between Arr and qBit categories
        conflicts = self.arr_categories & self.qbit_managed_categories
        if conflicts:
            conflict_list = ", ".join(sorted(conflicts))
            error_msg = (
                f"Category conflict detected: {conflict_list} "
                f"cannot be managed by both Arr instances and qBit instances. "
                f"Please assign each category to either Arr OR qBit management, not both."
            )
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        # Update category allowlist to include qBit-managed categories
        self.category_allowlist.update(self.qbit_managed_categories)

        if self.qbit_managed_categories:
            self.logger.info(
                "qBit-managed categories registered: %s",
                ", ".join(sorted(self.qbit_managed_categories)),
            )
        self.logger.debug("Category validation passed - no conflicts detected")

    def build_arr_instances(self):
        for key in CONFIG.sections():
            if search := re.match("(rad|son|anim|lid)arr.*", key, re.IGNORECASE):
                name = search.group(0)
                match = search.group(1)
                if match.lower() == "son":
                    call_cls = SonarrAPI
                elif match.lower() == "anim":
                    call_cls = SonarrAPI
                elif match.lower() == "rad":
                    call_cls = RadarrAPI
                elif match.lower() == "lid":
                    call_cls = LidarrAPI
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

        # Validate category assignments after all Arr instances are initialized
        self._validate_category_assignments()

        # FreeSpaceManager monitors both Arr-managed and qBit-managed categories
        all_monitored_categories = self.arr_categories | self.qbit_managed_categories
        if (
            FREE_SPACE != "-1"
            and AUTO_PAUSE_RESUME
            and not QBIT_DISABLED
            and len(all_monitored_categories) > 0
        ):
            managed_object = FreeSpaceManager(all_monitored_categories, self)
            self.managed_objects["FreeSpaceManager"] = managed_object
        for cat in self.special_categories:
            managed_object = PlaceHolderArr(cat, self)
            self.managed_objects[cat] = managed_object
        # qBit-managed categories get the same torrent behaviour (recheck, missing files,
        # stalled, etc.) via PlaceHolderArr when not already an Arr category.
        for cat in self.qbit_managed_categories:
            if cat not in self.managed_objects:
                managed_object = PlaceHolderArr(cat, self)
                self.managed_objects[cat] = managed_object
        return self
