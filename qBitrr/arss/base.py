from __future__ import annotations

import atexit
import contextlib
import logging
import pathlib
import re
import shutil
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime, timedelta, timezone
from multiprocessing import current_process
from typing import TYPE_CHECKING, Any, ClassVar, NoReturn

import ffmpeg
import pathos
import qbittorrentapi
import qbittorrentapi.exceptions
import requests
from packaging import version as version_parser
from peewee import DatabaseError, Model, OperationalError, SqliteDatabase
from qbittorrentapi import TorrentDictionary
from ujson import JSONDecodeError

from qBitrr.arss._shared import (
    _ARR_RETRY_EXCEPTIONS,
    _ARR_RETRY_EXCEPTIONS_EXTENDED,
    _QBIT_READ_RETRY_EXCEPTIONS,
    _QBIT_WRITE_RETRY_EXCEPTIONS,
    APPDATA_FOLDER,
    CONFIG,
    PROCESS_ONLY,
    QBIT_DISABLED,
    SEARCH_ONLY,
    TAGLESS,
    AlbumFilesModel,
    AlbumQueueModel,
    ArtistFilesModel,
    DelayLoopException,
    EpisodeFilesModel,
    EpisodeQueueModel,
    ExpiringSet,
    FilesQueued,
    JsonObject,
    Lidarr,
    MovieQueueModel,
    MoviesFilesModel,
    NoConnectionrException,
    PyarrConnectionError,
    PyarrResourceNotFound,
    PyarrServerError,
    Radarr,
    RestartLoopException,
    SeriesFilesModel,
    SkipException,
    Sonarr,
    TorrentLibrary,
    TrackerIndex,
    TrackFilesModel,
    UnhandledError,
    _extract_tracker_host,
    _parse_qbittorrent_tag_list,
    _TrackerDataUnavailable,
    absolute_file_paths,
    build_tracker_index,
    category_parents,
    clear_search_activity,
    database_lock,
    execute_command,
    fetch_search_activities,
    get_completed_download_folder_effective,
    get_ignore_torrents_younger_than_effective,
    get_loop_sleep_timer_effective,
    get_no_internet_sleep_timer_effective,
    get_search_loop_delay_effective,
    has_internet,
    normalize_category,
    record_search_activity,
    run_logs,
    sync_config_from_disk,
    with_database_retry,
    with_retry,
)
from qBitrr.arss.db_queries import db_get_files as _db_get_files_fn
from qBitrr.arss.db_queries import db_get_request_files as _db_get_request_files_fn
from qBitrr.arss.db_queries import (
    db_maybe_reset_entry_searched_state as _db_maybe_reset_entry_searched_state_fn,
)
from qBitrr.arss.request_providers import db_request_update as _db_request_update_fn
from qBitrr.arss.search_handlers import maybe_do_search as _maybe_do_search_fn
from qBitrr.arss.torrent_batch_mixin import TorrentBatchMixin
from qBitrr.arss.torrent_dispatcher_mixin import TorrentDispatcherMixin
from qBitrr.arss.torrent_inspector_mixin import TorrentInspectorMixin
from qBitrr.arss.torrent_limits_mixin import TorrentLimitsMixin

if TYPE_CHECKING:
    from qBitrr.arss.manager import ArrManager


class ArrBase(
    TorrentBatchMixin, TorrentInspectorMixin, TorrentDispatcherMixin, TorrentLimitsMixin
):
    """Shared Arr worker pipeline; prefer RadarrArr / SonarrArr / LidarrArr concretes."""

    arr_type: ClassVar[str] = ""

    def __init__(
        self,
        name: str,
        manager: ArrManager,
        client_builder: Callable[..., Radarr | Sonarr | Lidarr],
    ):
        """Load Arr identity, settings, client, and DB; fail fast if unmanaged."""
        self._client_builder = client_builder
        self._init_identity(name, manager)
        self._init_completed_folder()
        self._init_arr_connection_settings(name)
        self._init_torrent_settings(name)
        self._init_tracker_and_seeding(name)
        self._init_search_settings(name)
        self._init_request_providers(name)
        self._init_exclusion_regexes()
        self._init_client_and_type(client_builder)
        self._init_quality_profiles(name)
        self._init_runtime_state()
        self._log_init_config()
        self._init_search_api_command()
        self._init_qbit_tags()
        self._init_models_and_db()

    def _init_identity(self, name: str, manager: ArrManager):
        """Register name/category with the manager and create the Arr logger."""
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
        raw_category = CONFIG.get(f"{name}.Category", fallback=self._name)
        normalised_category = normalize_category(raw_category)
        if normalised_category and normalised_category != str(raw_category).strip():
            logging.getLogger(f"qBitrr.{self._name}").info(
                "Normalised %s.Category %r → %r", name, str(raw_category), normalised_category
            )
        self.category = normalised_category or str(raw_category).strip() or self._name
        self.manager = manager
        self._LOG_LEVEL = self.manager.qbit_manager.logger.level
        self.logger = logging.getLogger(f"qBitrr.{self._name}")
        run_logs(self.logger, self._name)
        self._dedicated_qbit_clients: dict[str, qbittorrentapi.Client] = {}

    def _init_completed_folder(self):
        """Resolve completed_folder from qBit category save path or defaults."""
        # Set completed_folder path (used for category creation and file monitoring)
        if not QBIT_DISABLED:
            try:
                # Check default instance for existing category configuration
                primary_client = self._get_primary_qbit_client()
                if primary_client is None:
                    raise qbittorrentapi.exceptions.APIConnectionError(
                        "No qBit clients configured"
                    )
                categories = primary_client.torrent_categories.categories
                categ = categories.get(self.category)
                if categ and categ.get("savePath"):
                    self.logger.trace("Category exists with save path [%s]", categ["savePath"])
                    self.completed_folder = pathlib.Path(categ["savePath"])
                else:
                    self.logger.trace("Category does not exist or lacks save path")
                    self.completed_folder = pathlib.Path(
                        get_completed_download_folder_effective()
                    ).joinpath(self.category)
            except Exception as e:
                self.logger.warning(
                    "Could not connect to qBittorrent during initialization for %s: %s. Using default path.",
                    self._name,
                    str(e).split("\n")[0] if "\n" in str(e) else str(e),
                )
                self.completed_folder = pathlib.Path(
                    get_completed_download_folder_effective()
                ).joinpath(self.category)
            # Ensure category exists on ALL instances (deferred to avoid __init__ failures)
            try:
                self._ensure_category_on_all_instances()
            except Exception as e:
                self.logger.warning(
                    "Could not ensure category on all instances during init: %s", e
                )
        else:
            self.completed_folder = pathlib.Path(
                get_completed_download_folder_effective()
            ).joinpath(self.category)

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

    def _init_arr_connection_settings(self, name: str):
        """Load Arr API key, import mode, and sync timers."""
        self.apikey = CONFIG.get_or_raise(f"{name}.APIKey")
        self.skip_tls_verify_servarr = CONFIG.get(f"{name}.SkipTLSVerify", fallback=False)
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

    def _init_torrent_settings(self, name: str):
        """Load torrent match/exclusion/allowlist and AutoDelete settings."""
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

    def _init_tracker_and_seeding(self, name: str):
        """Load seeding limits and merge global/Arr tracker configs."""
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
        self._install_tracker_index(
            build_tracker_index(
                self.monitored_trackers,
                bad_tracker_messages=self.seeding_mode_global_bad_tracker_msg,
            )
        )

        if (
            self.auto_delete is True
            and not self.completed_folder.parent.exists()
            and not SEARCH_ONLY
        ):
            self.auto_delete = False
            self.logger.critical(
                "AutoDelete disabled due to missing folder: '%s'", self.completed_folder.parent
            )

    def _init_search_settings(self, name: str):
        """Load EntrySearch flags, stalls, and search DB path."""
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

    def _init_request_providers(self, name: str):
        """Load Ombi/Overseerr request-search settings."""
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
        self.skip_tls_verify_overseerr = CONFIG.get(
            f"{name}.EntrySearch.Overseerr.SkipTLSVerify", fallback=False
        )
        self.skip_tls_verify_ombi = CONFIG.get(
            f"{name}.EntrySearch.Ombi.SkipTLSVerify", fallback=False
        )
        self.search_requests_every_x_seconds = CONFIG.get_duration(
            f"{name}.EntrySearch.SearchRequestsEvery", fallback=300
        )
        self._temp_overseer_request_cache: dict[str, set[int | str]] = defaultdict(set)
        if self.ombi_search_requests or self.overseerr_requests:
            self.request_search_timer = 0
        else:
            self.request_search_timer = None

    def _init_exclusion_regexes(self):
        """Compile folder/file exclusion and extension allowlist regexes."""
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

    def _init_client_and_type(self, client_builder: Callable[..., Radarr | Sonarr | Lidarr]):
        """Build the pyarr client; ``self.type`` comes from the concrete subclass."""
        if not self.arr_type:
            raise UnhandledError(f"{type(self).__name__} must set ClassVar arr_type")
        self.type = self.arr_type
        self.client = client_builder(
            self.uri,
            self.apikey,
            verify_ssl=not self.skip_tls_verify_servarr,
        )
        self._apply_type_feature_gates()

        try:
            version_info = self.client.update.get()
            self.version = version_parser.parse(version_info[0].get("version"))
            self.logger.debug("%s version: %s", self._name, self.version.__str__())
        except Exception:
            self.logger.debug("Failed to get version")

    def _apply_type_feature_gates(self) -> None:
        """Disable features unsupported by this Arr type (Lidarr overrides)."""
        return

    def _init_quality_profiles(self, name: str):
        """Load temp/main quality profile mappings and optional startup reset."""
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

    def _init_runtime_state(self):
        """Initialize per-loop caches, queues, and HTTP session."""
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
        self.change_priority_by_instance: dict[str, dict[str, list]] = defaultdict(dict)
        self._init_qbit_action_buckets(include_recheck=True, include_delete=True)
        self.overseerr_requests_release_cache = {}
        self.files_to_explicitly_delete: Iterator = iter([])
        self.files_to_cleanup = set()
        self.missing_files_post_delete = set()
        self.downloads_with_bad_error_message_blocklist = set()
        self.needs_cleanup = False
        self._warned_no_seeding_limits = False
        self._torrent_important_trackers_cache: dict[str, tuple[set[str], set[str]]] = {}

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
        self.db_update_processed = False
        self.manager.completed_folders.add(self.completed_folder)
        self.manager.category_allowlist.add(self.category)

    def _log_init_config(self):
        """Emit startup debug lines summarizing loaded config."""
        # Never pass secret values into logging args (CodeQL clear-text logging).
        self.logger.debug(
            "%s Config: "
            "Managed: %s, "
            "Re-search: %s, "
            "ImportMode: %s, "
            "Category: %s, "
            "URI: %s, "
            "API Key: [redacted], "
            "RefreshDownloadsTimer=%s, "
            "RssSyncTimer=%s",
            self._name,
            self.managed,
            self.re_search,
            self.import_mode,
            self.category,
            self.uri,
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
                self.logger.debug("Script Config:  OmbiAPIKey=[redacted]")
                self.logger.debug("Script Config:  ApprovedOnly=%s", self.ombi_approved_only)
            self.logger.debug(
                "Script Config:  SearchOverseerrRequests=%s", self.overseerr_requests
            )
            if self.overseerr_requests:
                self.logger.debug("Script Config:  OverseerrURI=%s", self.overseerr_uri)
                self.logger.debug("Script Config:  OverseerrAPIKey=[redacted]")
            if self.ombi_search_requests or self.overseerr_requests:
                self.logger.debug(
                    "Script Config:  SearchRequestsEvery=%s", self.search_requests_every_x_seconds
                )

    def _init_search_api_command(self):
        """Pick the Arr search command; SonarrArr overrides for episode/series modes."""
        return

    def _init_qbit_tags(self):
        """Ensure required qBittorrent tags exist on the primary client."""
        if not QBIT_DISABLED and not TAGLESS:
            try:
                _client = self._get_primary_qbit_client()
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
                _client = self._get_primary_qbit_client()
                if _client is not None:
                    _client.torrents_create_tags(["qBitrr-ignored"])
            except qbittorrentapi.exceptions.APIConnectionError as e:
                self.logger.warning(
                    "Could not connect to qBittorrent during initialization for %s: %s. "
                    "Will retry when process starts.",
                    self._name,
                    str(e).split("\n")[0],  # Only log first line of error
                )

    def _init_models_and_db(self):
        """Register search/torrent models and SQLite atexit cleanup."""
        self.search_setup_completed = False
        self.model_file: Model | None = None
        self.series_file_model: Model | None = None
        self.model_queue: Model | None = None
        self.persistent_queue: Model | None = None
        self.track_file_model: Model | None = None
        self.torrents: TorrentLibrary | None = None
        self.torrent_db: SqliteDatabase | None = None
        self.db: SqliteDatabase | None = None
        self._webui_catalog_rollups: dict[str, Any] | None = None
        # Catalog header rollups for API responses are built in the WebUI process from SQLite
        # with a short TTL (:mod:`qBitrr.catalog_rollups`); worker Arr instances cannot clear
        # that process-local cache after DB writes.
        # Initialize search mode (and torrent tag-emulation DB in TAGLESS)
        # early and fail fast if it cannot be set up.
        self.register_search_mode()
        self._register_sqlite_db_atexit("db")
        self._register_sqlite_db_atexit("torrent_db")
        self.logger.hnotice("Starting %s monitor", self._name)

    def _install_tracker_index(self, idx: TrackerIndex) -> None:
        """Apply :class:`TrackerIndex` to instance tracker-derived fields."""
        self._remove_trackers_if_exists = set(idx.remove_trackers_if_exists)
        self._monitored_tracker_urls = set(idx.monitored_tracker_urls)
        self._add_trackers_if_missing = set(idx.add_trackers_if_missing)
        self._host_to_config_uri = dict(idx.host_to_config_uri)
        self._remove_tracker_hosts = set(idx.remove_tracker_hosts)
        self._normalized_bad_tracker_msgs = set(idx.normalized_bad_tracker_msgs)

    def _qbit_retry(
        self,
        fn: Callable,
        *,
        retries: int = 3,
        backoff: float = 0.5,
        max_backoff: float = 3,
    ):
        """Execute a qBittorrent API call with the standard retry policy."""
        return with_retry(
            fn,
            retries=retries,
            backoff=backoff,
            max_backoff=max_backoff,
            exceptions=_QBIT_WRITE_RETRY_EXCEPTIONS,
        )

    def _should_use_dedicated_qbit_client(self) -> bool:
        """Return True when running inside a child worker process."""
        return current_process().name != "MainProcess"

    def _get_qbit_client(self, instance_name: str = "qBit") -> qbittorrentapi.Client | None:
        """Get a qBit client, creating a dedicated per-process session when needed."""
        qbit_manager = self.manager.qbit_manager
        if not self._should_use_dedicated_qbit_client():
            return qbit_manager.get_client(instance_name)
        client = self._dedicated_qbit_clients.get(instance_name)
        if client is None:
            client = qbit_manager.create_client_for_instance(instance_name)
            self._dedicated_qbit_clients[instance_name] = client
            self.logger.debug(
                "Created dedicated qBit client for worker '%s' instance '%s'",
                self._name,
                instance_name,
            )
        return client

    def _get_primary_qbit_client(self) -> qbittorrentapi.Client | None:
        """Get the first configured qBit client, preferring a dedicated child session."""
        qbit_manager = self.manager.qbit_manager
        for instance_name in qbit_manager.get_all_instances():
            client = self._get_qbit_client(instance_name)
            if client is not None:
                return client
        return None

    def _is_qbit_instance_reachable(self, instance_name: str) -> bool:
        """Probe qBit reachability using this worker's dedicated or shared client."""
        client = self._get_qbit_client(instance_name)
        if client is None:
            return False
        try:
            client.app_version()
            return True
        except Exception as exc:
            self.logger.debug(
                "qBit instance '%s' unreachable in worker '%s': %s",
                instance_name,
                self._name,
                exc,
            )
            return False

    def _is_any_qbit_instance_reachable(self) -> bool:
        """Return True when any configured qBit instance responds in this worker."""
        qbit_manager = self.manager.qbit_manager
        instances = qbit_manager.get_all_instances()
        if not instances:
            # No instances registered means initialisation failed at startup -- for
            # example when qBitrr and qBittorrent are restarted together and the
            # WebUI is not accepting connections yet. `_initialize_qbit_instances()`
            # only ever runs from `_complete_startup()`, and nothing else populates
            # `clients`, so without this retry the worker keeps reporting "Could not
            # connect to qBit client" for the entire lifetime of the process even
            # after qBittorrent becomes reachable again. Retry here so the loop can
            # recover on its own; the caller already backs off 5 minutes on failure.
            qbit_manager._initialize_qbit_instances()
            instances = qbit_manager.get_all_instances()
            if not instances:
                return False
        return any(self._is_qbit_instance_reachable(name) for name in instances)

    def _retry_profile_switch_update(self, update_fn: Callable, kind: str) -> bool:
        """Retry Arr quality-profile updates using the configured switch-attempt count."""
        from qBitrr.quality_profile_helpers import retry_profile_switch_update

        return retry_profile_switch_update(
            update_fn,
            attempts=self.profile_switch_retry_attempts,
            kind=kind,
            logger=self.logger,
        )

    def _handle_delay_loop_exception(
        self,
        delay_exc: DelayLoopException,
        wait_fn: Callable[[float], None],
        *,
        reset_torrent_scan_delay: bool = False,
    ) -> None:
        """Standardized DelayLoopException logging and backoff wait."""
        if delay_exc.error_type == "qbit":
            self.logger.critical(
                "Failed to connected to qBit client, sleeping for %s",
                timedelta(seconds=delay_exc.length),
            )
        elif delay_exc.error_type == "internet":
            self.logger.critical(
                "Failed to connected to the internet, sleeping for %s",
                timedelta(seconds=delay_exc.length),
            )
        elif delay_exc.error_type == "arr":
            self.logger.critical(
                "Failed to connected to the Arr instance, sleeping for %s",
                timedelta(seconds=delay_exc.length),
            )
        elif delay_exc.error_type == "delay":
            self.logger.critical(
                "Forced delay due to temporary issue with environment, sleeping for %s",
                timedelta(seconds=delay_exc.length),
            )
        elif delay_exc.error_type == "no_downloads":
            self.logger.debug(
                "No downloads in category, sleeping for %s",
                timedelta(seconds=delay_exc.length),
            )
        wait_fn(delay_exc.length)
        if reset_torrent_scan_delay:
            self.manager.qbit_manager.should_delay_torrent_scan = False

    @staticmethod
    def _merge_trackers(qbit_trackers: list, arr_trackers: list) -> list:
        """Merge qBit-level and Arr-level trackers. Arr overrides qBit by URI."""
        from qBitrr.arr_tracker_index import merge_tracker_configs

        return merge_tracker_configs(qbit_trackers, arr_trackers)

    @staticmethod
    def merge_global_tracker_blocks() -> list[dict]:
        """
        Merge ``[[qBit.Trackers]]`` with every ``[[<Arr>.Torrent.Trackers]]`` section.

        URI-keyed merge: qBit entries are loaded first; each Arr section in config file
        order overwrites earlier entries for the same URI (including qBit).
        """
        from qBitrr.arr_tracker_index import merge_tracker_configs

        qbit_trackers = [
            tracker
            for tracker in CONFIG.get("qBit.Trackers", fallback=[])
            if isinstance(tracker, dict)
        ]
        arr_trackers: list[dict] = []
        for section in CONFIG.sections():
            if not re.match(r"(rad|son|anim|lid)arr.*", section, re.IGNORECASE):
                continue
            for tracker in CONFIG.get(f"{section}.Torrent.Trackers", fallback=[]):
                if isinstance(tracker, dict):
                    arr_trackers.append(tracker)
        return merge_tracker_configs(qbit_trackers, arr_trackers)

    @staticmethod
    def merge_global_tracker_configured_add_tags() -> frozenset[str]:
        """
        All tag names that may be applied via merged tracker ``AddTags`` (qBit + Arr).

        Used to remove stale qBitrr-applied tags without stripping user-added labels.
        """
        tags: set[str] = set()
        for row in ArrBase.merge_global_tracker_blocks():
            raw = row.get("AddTags") or []
            if isinstance(raw, str):
                items = [raw]
            else:
                items = list(raw) if raw else []
            for tag in items:
                if isinstance(tag, str) and tag.strip():
                    tags.add(tag.strip())
        return frozenset(tags)

    @staticmethod
    def merge_global_tracker_tag_to_priority_max() -> dict[str, int]:
        """
        Map each ``AddTags`` label to the maximum ``Priority`` among merged tracker rows.

        Used when ``SortTorrents`` orders the queue so order matches visible tags.
        """
        out: dict[str, int] = {}
        for row in ArrBase.merge_global_tracker_blocks():
            pri_raw = row.get("Priority", -100)
            try:
                pri_int = int(pri_raw) if not isinstance(pri_raw, bool) else -100
            except (TypeError, ValueError):
                pri_int = -100
            raw = row.get("AddTags") or []
            if isinstance(raw, str):
                items = [raw]
            else:
                items = list(raw) if raw else []
            for tag in items:
                if isinstance(tag, str) and tag.strip():
                    t = tag.strip()
                    out[t] = max(out.get(t, -100), pri_int)
        return out

    @staticmethod
    def global_sort_torrents_enabled() -> bool:
        """True if any merged tracker (qBit + all Arr) has ``SortTorrents`` set."""
        return any(i.get("SortTorrents", False) for i in ArrBase.merge_global_tracker_blocks())

    @staticmethod
    def global_remove_dead_trackers_union() -> bool:
        """True if any Arr section enables ``RemoveDeadTrackers`` (for priority sorting)."""
        for section in CONFIG.sections():
            if not re.match(r"(rad|son|anim|lid)arr.*", section, re.IGNORECASE):
                continue
            if CONFIG.get(f"{section}.Torrent.SeedingMode.RemoveDeadTrackers", fallback=False):
                return True
        return False

    @staticmethod
    def global_bad_tracker_messages_union() -> list[str]:
        """Union of ``RemoveTrackerWithMessage`` strings from all Arr sections (deduped)."""
        seen: set[str] = set()
        out: list[str] = []
        for section in CONFIG.sections():
            if not re.match(r"(rad|son|anim|lid)arr.*", section, re.IGNORECASE):
                continue
            raw = CONFIG.get(
                f"{section}.Torrent.SeedingMode.RemoveTrackerWithMessage", fallback=[]
            )
            if isinstance(raw, str):
                items = [raw]
            else:
                items = list(raw) if raw else []
            for msg in items:
                if isinstance(msg, str) and msg not in seen:
                    seen.add(msg)
                    out.append(msg)
        return out

    def _ensure_category_on_all_instances(self) -> None:
        """
        Ensure the Arr category exists on ALL qBittorrent instances.

        For subcategory paths (``parent/child``) every parent prefix is created
        before the leaf so qBittorrent does not silently treat the value as a
        flat name. Each parent is created with a save path derived from its
        parent's ``savePath`` (or :data:`COMPLETED_DOWNLOAD_FOLDER` for the root)
        so the resulting tree mirrors what the user expects on disk.
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

        leaf_category = self.category
        prefix_paths = category_parents(leaf_category)
        completed_root = pathlib.Path(get_completed_download_folder_effective())

        for instance_name in all_instances:
            try:
                client = self._get_qbit_client(instance_name)
                if client is None:
                    self.logger.warning(
                        "Skipping category creation on instance '%s' (client unavailable)",
                        instance_name,
                    )
                    continue

                categories = client.torrent_categories.categories
                # Walk parent chain first so qBittorrent stores a real hierarchy.
                for parent in prefix_paths:
                    if parent in categories:
                        continue
                    parents_of_parent = category_parents(parent)
                    parent_of_parent = parents_of_parent[-1] if parents_of_parent else None
                    if parent_of_parent and parent_of_parent in categories:
                        parent_save = categories[parent_of_parent].get("savePath") or str(
                            completed_root.joinpath(parent_of_parent)
                        )
                        save_path = str(pathlib.Path(parent_save).joinpath(parent.split("/")[-1]))
                    else:
                        save_path = str(completed_root.joinpath(parent))
                    try:
                        client.torrent_categories.create_category(parent, save_path=save_path)
                        self.logger.info(
                            "Created parent category '%s' on instance '%s' (save_path=%s)",
                            parent,
                            instance_name,
                            save_path,
                        )
                        # Refresh local view so subsequent siblings see this parent.
                        categories = client.torrent_categories.categories
                    except Exception as e:
                        self.logger.warning(
                            "Failed to create parent category '%s' on '%s': %s",
                            parent,
                            instance_name,
                            str(e).split("\n")[0] if "\n" in str(e) else str(e),
                        )

                if leaf_category not in categories:
                    client.torrent_categories.create_category(
                        leaf_category, save_path=str(self.completed_folder)
                    )
                    self.logger.info(
                        "Created category '%s' on instance '%s'",
                        leaf_category,
                        instance_name,
                    )
                else:
                    self.logger.debug(
                        "Category '%s' already exists on instance '%s'",
                        leaf_category,
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

    def _configure_worker_logging(self, worker_name: str) -> None:
        """Initialize a worker logger compatible with Arr helper paths."""
        self.logger = logging.getLogger(f"qBitrr.{worker_name}")
        run_logs(self.logger, worker_name)

    def _register_sqlite_db_atexit(self, attr_name: str) -> None:
        """Register a safe close handler for optional sqlite attributes."""

        def _close() -> None:
            db = getattr(self, attr_name, None)
            if db is None:
                return
            with contextlib.suppress(Exception):
                if hasattr(db, "is_closed"):
                    if not db.is_closed():
                        db.close()
                elif hasattr(db, "close"):
                    db.close()

        atexit.register(_close)

    def _init_qbit_action_buckets(
        self,
        *,
        include_recheck: bool = True,
        include_delete: bool = True,
    ) -> None:
        """Initialize pause/resume/(optional) delete/recheck hash buckets."""
        self.pause = set()
        self.pause_by_instance: dict[str, set[str]] = defaultdict(set)
        self.resume = set()
        self.resume_by_instance: dict[str, set[str]] = defaultdict(set)
        if include_recheck:
            self.recheck_by_instance: dict[str, set[str]] = {}
        if include_delete:
            self.skip_blacklist = set()
            self.delete = set()
            self.remove_from_qbit = set()
            self.remove_from_qbit_by_instance: dict[str, set[str]] = {}
            self.delete_by_instance: dict[str, set[str]] = {}

    def _init_worker_expiring_timeouts(self) -> None:
        """Initialize expiring caches used by lightweight worker classes."""
        ignore_seconds = self._get_ignore_torrents_younger_than()
        self.ignore_torrents_younger_than = ignore_seconds
        self.timed_ignore_cache = ExpiringSet(max_age_seconds=ignore_seconds)
        self.timed_ignore_cache_2 = ExpiringSet(max_age_seconds=ignore_seconds * 2)
        self.timed_skip = ExpiringSet(max_age_seconds=ignore_seconds)
        self.tracker_delay = ExpiringSet(max_age_seconds=600)
        self.special_casing_file_check = ExpiringSet(max_age_seconds=10)
        self.expiring_bool = ExpiringSet(max_age_seconds=10)

    def _get_ignore_torrents_younger_than(self) -> int:
        """Per-Arr ignore-younger threshold with global Settings fallback (live reload)."""
        return CONFIG.get_duration(
            f"{self._name}.Torrent.IgnoreTorrentsYoungerThan",
            fallback=get_ignore_torrents_younger_than_effective(),
        )

    def _get_maximum_eta(self) -> int:
        """Return MaximumETA from current CONFIG (live reload)."""
        return CONFIG.get_duration(f"{self._name}.Torrent.MaximumETA", fallback=86400)

    def _get_search_command_limit(self) -> int:
        """Return EntrySearch.SearchLimit from current CONFIG (live reload)."""
        return CONFIG.get(f"{self._name}.EntrySearch.SearchLimit", fallback=5)

    def _get_rss_sync_timer(self) -> int:
        """Return RssSyncTimer from current CONFIG (live reload)."""
        return CONFIG.get_duration(f"{self._name}.RssSyncTimer", fallback=15, unit="minutes")

    def _get_refresh_downloads_timer(self) -> int:
        """Return RefreshDownloadsTimer from current CONFIG (live reload)."""
        return CONFIG.get_duration(
            f"{self._name}.RefreshDownloadsTimer", fallback=1, unit="minutes"
        )

    def _sync_loop_settings_from_config(self) -> None:
        """Refresh Arr LIVE settings from CONFIG (call from worker loops each iteration).

        Covers timers/ETA/stalled delay and Arr LIVE attrs such as ``search_missing``,
        ``auto_delete``, tracker indexes, and related EntrySearch/Torrent flags so
        child processes pick up WebUI live saves without a respawn.
        """
        sync_config_from_disk()
        self._apply_arr_live_attrs_from_config()

    def _apply_arr_live_attrs_from_config(self) -> None:
        """Apply Arr LIVE in-memory attrs from the current CONFIG snapshot."""
        name = self._name
        ignore_seconds = self._get_ignore_torrents_younger_than()
        if ignore_seconds != self.ignore_torrents_younger_than:
            self.ignore_torrents_younger_than = ignore_seconds
            self.timed_ignore_cache = ExpiringSet(max_age_seconds=ignore_seconds)
            self.timed_ignore_cache_2 = ExpiringSet(max_age_seconds=ignore_seconds * 2)
            self.timed_skip = ExpiringSet(max_age_seconds=ignore_seconds)
        self.maximum_eta = self._get_maximum_eta()
        self.search_command_limit = self._get_search_command_limit()
        self.rss_sync_timer = self._get_rss_sync_timer()
        self.refresh_downloads_timer = self._get_refresh_downloads_timer()
        self.stalled_delay = CONFIG.get_duration(
            f"{name}.Torrent.StalledDelay", fallback=15, unit="minutes"
        )
        self.allowed_stalled = self.stalled_delay != -1
        self.managed = CONFIG.get(f"{name}.Managed", fallback=False)
        self.skip_tls_verify_servarr = CONFIG.get(f"{name}.SkipTLSVerify", fallback=False)
        self.re_search = CONFIG.get(f"{name}.ReSearch", fallback=False)
        self.import_mode = CONFIG.get(f"{name}.importMode", fallback="Auto")
        if self.import_mode == "Hardlink":
            self.import_mode = "Auto"
        self.arr_error_codes_to_blocklist = CONFIG.get(
            f"{name}.ArrErrorCodesToBlocklist", fallback=[]
        )
        self.case_sensitive_matches = CONFIG.get(
            f"{name}.Torrent.CaseSensitiveMatches", fallback=False
        )
        self.auto_delete = CONFIG.get(f"{name}.Torrent.AutoDelete", fallback=False)
        self.search_missing = CONFIG.get(f"{name}.EntrySearch.SearchMissing", fallback=False)
        if PROCESS_ONLY:
            self.search_missing = False
        qbit_trackers = CONFIG.get("qBit.Trackers", fallback=[])
        arr_trackers = CONFIG.get(f"{name}.Torrent.Trackers", fallback=[])
        self.monitored_trackers = self._merge_trackers(qbit_trackers, arr_trackers)
        self._install_tracker_index(
            build_tracker_index(
                self.monitored_trackers,
                bad_tracker_messages=self.seeding_mode_global_bad_tracker_msg,
            )
        )

    def apply_config_refresh(self, preserve_db: bool = True) -> None:
        """Refresh in-memory Arr settings from CONFIG without deleting the search DB.

        Main-process managed objects call this on Arr LIVE saves. Worker processes
        apply the same LIVE attrs each loop via ``_sync_loop_settings_from_config``.
        When ``preserve_db`` is False the caller must reset the search DB and respawn workers.
        """
        name = self._name
        new_uri = CONFIG.get_or_raise(f"{name}.URI")
        new_apikey = CONFIG.get_or_raise(f"{name}.APIKey")
        self.skip_tls_verify_servarr = CONFIG.get(f"{name}.SkipTLSVerify", fallback=False)
        if new_uri != self.uri or new_apikey != self.apikey:
            self.uri = new_uri
            self.apikey = new_apikey
            self.client = self._client_builder(
                self.uri,
                self.apikey,
                verify_ssl=not self.skip_tls_verify_servarr,
            )
        sync_config_from_disk()
        self._apply_arr_live_attrs_from_config()
        self.logger.info(
            "Applied in-place config refresh for %s (preserve_db=%s)", name, preserve_db
        )

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
        with database_lock():
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
                with database_lock():
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
            with database_lock():
                self._ensure_torrent_row(torrent, instance_name)
                condition = self._torrent_condition(torrent, instance_name)
                for tag in tags:
                    field_name = self._TAGLESS_FIELD_MAP.get(tag)
                    if field_name:
                        self.torrents.update({getattr(self.torrents, field_name): False}).where(
                            condition
                        ).execute()
        else:
            try:
                with_retry(
                    lambda t=torrent, tg=tags: t.remove_tags(tg),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=_QBIT_READ_RETRY_EXCEPTIONS,
                )
            except Exception as e:
                self.logger.warning("Failed to remove tags %s from %s: %s", tags, torrent.name, e)

    def add_tags(
        self, torrent: TorrentDictionary, tags: list, instance_name: str = "default"
    ) -> None:
        for tag in tags:
            self.logger.trace("Adding tag %s to %s", tag, torrent.name)
        if TAGLESS:
            with database_lock():
                self._ensure_torrent_row(torrent, instance_name)
                condition = self._torrent_condition(torrent, instance_name)
                for tag in tags:
                    field_name = self._TAGLESS_FIELD_MAP.get(tag)
                    if field_name:
                        self.torrents.update({getattr(self.torrents, field_name): True}).where(
                            condition
                        ).execute()
        else:
            try:
                with_retry(
                    lambda t=torrent, tg=tags: t.add_tags(tg),
                    retries=3,
                    backoff=0.5,
                    max_backoff=3,
                    exceptions=_QBIT_READ_RETRY_EXCEPTIONS,
                )
            except Exception as e:
                self.logger.warning("Failed to add tags %s to %s: %s", tags, torrent.name, e)

    def _remove_empty_folders(self) -> None:
        new_sent_to_scan = set()
        if not self.completed_folder.exists():
            return
        for path in absolute_file_paths(self.completed_folder):
            if not path.is_dir():
                continue
            try:
                is_empty_dir = next(path.iterdir(), None) is None
            except FileNotFoundError:
                continue
            if is_empty_dir:
                with contextlib.suppress(FileNotFoundError):
                    path.rmdir()
                self.logger.trace("Removing empty folder: %s", path)
                if path in self.sent_to_scan:
                    self.sent_to_scan.discard(path)
                else:
                    new_sent_to_scan.add(path)
        self.sent_to_scan = new_sent_to_scan
        try:
            is_completed_folder_empty = next(self.completed_folder.iterdir(), None) is None
        except FileNotFoundError:
            is_completed_folder_empty = True
        if is_completed_folder_empty:
            self.sent_to_scan = set()
            self.sent_to_scan_hashes = set()

    def api_calls(self) -> None:
        if not self.is_alive:
            raise NoConnectionrException(
                f"Service: {self._name} did not respond on {self.uri}", error_type="arr"
            )
        now = datetime.now()
        if (
            self.rss_sync_timer_last_checked is not None
            and self.rss_sync_timer_last_checked
            < now - timedelta(minutes=self._get_rss_sync_timer())
        ):
            if self._run_periodic_command("RssSync"):
                self.rss_sync_timer_last_checked = now

        if (
            self.refresh_downloads_timer_last_checked is not None
            and self.refresh_downloads_timer_last_checked
            < now - timedelta(minutes=self._get_refresh_downloads_timer())
        ):
            if self._run_periodic_command(
                "RefreshMonitoredDownloads", supported_types={"radarr", "sonarr"}
            ):
                self.refresh_downloads_timer_last_checked = now

    def _run_periodic_command(
        self,
        command: str,
        *,
        supported_types: set[str] | None = None,
    ) -> bool:
        """Run a background Arr maintenance command without failing the worker loop.

        Returns:
            True when the command succeeded or was intentionally skipped for this Arr type.
            False when the command was attempted and failed.
        """
        if supported_types is not None and self.type not in supported_types:
            self.logger.trace(
                "Skipping unsupported periodic command '%s' for %s type '%s'",
                command,
                self._name,
                self.type,
            )
            return True
        try:
            with_retry(
                lambda: execute_command(self.client, command),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
            )
            return True
        except (PyarrServerError, PyarrResourceNotFound) as exc:
            self.logger.warning(
                "Periodic command '%s' is unavailable for %s: %s",
                command,
                self._name,
                exc,
            )
        except ValueError as exc:
            self.logger.warning(
                "Periodic command '%s' failed for %s: %s",
                command,
                self._name,
                exc,
            )
        except _ARR_RETRY_EXCEPTIONS_EXTENDED as exc:
            self.logger.warning(
                "Periodic command '%s' failed for %s after retries: %s",
                command,
                self._name,
                exc,
            )
        except Exception as exc:
            self.logger.warning(
                "Periodic command '%s' failed for %s: %s",
                command,
                self._name,
                exc,
            )
        return False

    def arr_db_query_commands_count(self) -> int:
        search_commands = 0
        if not (self.search_missing or self.do_upgrade_search):
            return 0
        commands = with_retry(
            lambda: self.client.command.get(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
        for command in commands:
            if command["name"].endswith("Search") and command["status"] != "completed":
                search_commands = search_commands + 1

        return search_commands

    def _get_oversee_requests_all(self) -> dict[str, set]:
        from qBitrr.arss.request_providers import (
            _get_oversee_requests_all as __get_oversee_requests_all,
        )

        return __get_oversee_requests_all(self)

    def _get_overseerr_requests_count(self) -> int:
        from qBitrr.arss.request_providers import (
            _get_overseerr_requests_count as __get_overseerr_requests_count,
        )

        return __get_overseerr_requests_count(self)

    def _get_ombi_request_count(self) -> int:
        from qBitrr.arss.request_providers import (
            _get_ombi_request_count as __get_ombi_request_count,
        )

        return __get_ombi_request_count(self)

    def _get_ombi_requests(self) -> list[dict]:
        from qBitrr.arss.request_providers import _get_ombi_requests as __get_ombi_requests

        return __get_ombi_requests(self)

    def _process_ombi_requests(self) -> dict[str, set[str, int]]:
        from qBitrr.arss.request_providers import _process_ombi_requests as __process_ombi_requests

        return __process_ombi_requests(self)

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
        return _db_get_files_fn(self)

    def db_maybe_reset_entry_searched_state(self):
        return _db_maybe_reset_entry_searched_state_fn(self)

    def db_reset__series_searched_state(self):
        from qBitrr.arss.db_queries import (
            db_reset__series_searched_state as _db_reset__series_searched_state,
        )

        return _db_reset__series_searched_state(self)

    def db_reset__episode_searched_state(self):
        from qBitrr.arss.db_queries import (
            db_reset__episode_searched_state as _db_reset__episode_searched_state,
        )

        return _db_reset__episode_searched_state(self)

    def db_reset__movie_searched_state(self):
        from qBitrr.arss.db_queries import (
            db_reset__movie_searched_state as _db_reset__movie_searched_state,
        )

        return _db_reset__movie_searched_state(self)

    def db_reset__album_searched_state(self):
        from qBitrr.arss.db_queries import (
            db_reset__album_searched_state as _db_reset__album_searched_state,
        )

        return _db_reset__album_searched_state(self)

    def _db_search_quality_cf_condition(self, *, missing_file_field):
        from qBitrr.arss.db_queries import (
            _db_search_quality_cf_condition as __db_search_quality_cf_condition,
        )

        return __db_search_quality_cf_condition(self, missing_file_field=missing_file_field)

    def db_get_files_series(self) -> list[list[SeriesFilesModel, bool, bool]] | None:
        from qBitrr.arss.db_queries import db_get_files_series as _db_get_files_series

        return _db_get_files_series(self)

    def db_get_files_episodes(self) -> list[list[EpisodeFilesModel, bool, bool]] | None:
        from qBitrr.arss.db_queries import db_get_files_episodes as _db_get_files_episodes

        return _db_get_files_episodes(self)

    def db_get_files_movies(self) -> list[list[MoviesFilesModel, bool, bool]] | None:
        from qBitrr.arss.db_queries import db_get_files_movies as _db_get_files_movies

        return _db_get_files_movies(self)

    def db_get_request_files(self) -> Iterable[tuple[MoviesFilesModel | EpisodeFilesModel, int]]:
        return _db_get_request_files_fn(self)

    def db_request_update(self):
        return _db_request_update_fn(self)

    def _db_request_update(self, request_ids: dict[str, set[int | str]]):
        from qBitrr.arss.request_providers import _db_request_update as __db_request_update

        return __db_request_update(self, request_ids)

    def db_overseerr_update(self):
        from qBitrr.arss.request_providers import db_overseerr_update as _db_overseerr_update

        return _db_overseerr_update(self)

    def db_ombi_update(self):
        from qBitrr.arss.request_providers import db_ombi_update as _db_ombi_update

        return _db_ombi_update(self)

    def db_update_todays_releases(self):
        if not self.prioritize_todays_release:
            return
        self._db_update_todays_releases()

    def _db_update_todays_releases(self) -> None:
        """SonarrArr overrides to prioritize today's unaired episodes."""
        return

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
            self._db_update_media()
            self.logger.trace("Finished updating database")
        except Exception:
            raise
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

    def _db_update_media(self) -> None:
        """Fetch media from Arr API into the search DB. Concrete subclasses implement."""
        raise UnhandledError(f"{type(self).__name__} must implement _db_update_media")

    def minimum_availability_check(self, db_entry: JsonObject) -> bool:
        from qBitrr.radarr_availability import (
            minimum_availability_check as _minimum_availability_check,
        )

        return _minimum_availability_check(self, db_entry)

    def db_update_single_series(
        self,
        db_entry: JsonObject = None,
        request: bool = False,
        series: bool = False,
        artist: bool = False,
    ):
        from qBitrr.arss.db_update_handlers import (
            db_update_single_series as _db_update_single_series,
        )

        return _db_update_single_series(self, db_entry, request, series, artist)

    def _db_update_single_entry(
        self,
        db_entry: JsonObject,
        *,
        request: bool = False,
        series: bool = False,
        artist: bool = False,
    ) -> None:
        """Type-specific DB row update; implemented on RadarrArr / SonarrArr / LidarrArr."""
        raise UnhandledError(f"{type(self).__name__} must implement _db_update_single_entry")

    def _log_db_update_json_error(
        self, db_entry: JsonObject, *, series: bool = False, artist: bool = False
    ) -> None:
        """Log a JSONDecodeError during DB update (overridden per Arr type)."""
        self.logger.warning(
            "Error getting media info: [%s][%s]",
            db_entry.get("id"),
            db_entry.get("title", db_entry.get("path", "?")),
        )

    def _maybe_do_search_impl(
        self,
        file_model: EpisodeFilesModel | MoviesFilesModel | SeriesFilesModel,
        *,
        request_tag: str,
        request: bool,
        todays: bool,
        bypass_limit: bool,
        series_search: bool,
        commands: int,
    ):
        """Type-specific search command path; implemented on concrete Arr classes."""
        raise UnhandledError(f"{type(self).__name__} must implement _maybe_do_search_impl")

    def delete_from_queue(self, id_, remove_from_client=True, blacklist=True):
        try:
            res = with_retry(
                lambda: self.client.queue.delete(
                    item_id=id_, remove_from_client=remove_from_client, blocklist=blacklist
                ),
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
            stderr_raw = getattr(e, "stderr", b"")
            if isinstance(stderr_raw, bytes):
                error = stderr_raw.decode(errors="ignore")
            else:
                error = str(stderr_raw or "")
            invalid_data = "Invalid data found when processing input" in error
            self.logger.trace(
                "Not probeable: Probe returned an error: %s:\n%s",
                file,
                stderr_raw,
                exc_info=None if invalid_data else sys.exc_info(),
            )
            if invalid_data:
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

    def process(self):
        """Apply queued torrent side-effects (batch mixin), then folder cleanup.

        Preceded by :meth:`process_torrents`, which classifies each torrent via
        the dispatcher/inspector mixins before this method runs the batch queue.
        """
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

        With ``MatchSubcategories`` disabled (default) this uses qBittorrent's
        ``torrents/info?category=`` filter, which is exact-match — see
        :mod:`qBitrr.category_paths`.

        When enabled at the qBit level, the full torrent list for each instance is
        fetched and torrents under ``self.category`` are candidates; those whose
        category resolves to a **more specific** configured owner (another Arr or
        qBit-managed path, same rules as :meth:`ArrManager.resolve_owning_category`)
        are dropped so only this instance's ``Category`` key processes each torrent.

        Returns:
            list[tuple[str, TorrentDictionary]]: List of (instance_name, torrent) tuples
        """
        all_torrents = []
        qbit_manager = self.manager.qbit_manager
        target_category = normalize_category(self.category) or self.category
        instance_failures = 0
        last_error: Exception | None = None

        for instance_name in qbit_manager.get_all_instances():
            if not self._is_qbit_instance_reachable(instance_name):
                self.logger.debug(
                    "Skipping unhealthy instance '%s' during torrent scan", instance_name
                )
                continue

            client = self._get_qbit_client(instance_name)
            if client is None:
                continue

            # ``get_all_instances()`` returns config section keys: ``qBit`` or ``qBit-Seedbox``.
            section = instance_name
            instance_subcat_match = self.manager.arr_match_subcategories_effective(
                self._name, section
            )

            try:
                if instance_subcat_match:
                    torrents = client.torrents.info(
                        status_filter="all",
                        sort="added_on",
                        reverse=False,
                    )
                else:
                    torrents = client.torrents.info(
                        status_filter="all",
                        category=target_category,
                        sort="added_on",
                        reverse=False,
                    )
                kept = 0
                for torrent in torrents:
                    if not hasattr(torrent, "category"):
                        continue
                    cat = normalize_category(getattr(torrent, "category", "") or "")
                    if not cat:
                        continue
                    if instance_subcat_match:
                        if cat != target_category and not cat.startswith(target_category + "/"):
                            continue
                    owner = self.manager.resolve_owning_category(cat, qbit_section=instance_name)
                    if owner != self.category:
                        continue
                    all_torrents.append((instance_name, torrent))
                    kept += 1

                self.logger.trace(
                    "Retrieved %d torrents from instance '%s' for category '%s' "
                    "(MatchSubcategories=%s)",
                    kept,
                    instance_name,
                    target_category,
                    instance_subcat_match,
                )
            except _QBIT_READ_RETRY_EXCEPTIONS as e:
                self.logger.warning(
                    "Failed to get torrents from instance '%s': %s", instance_name, e
                )
                instance_failures += 1
                last_error = e
                continue

        if instance_failures and not all_torrents:
            if last_error is not None:
                raise last_error
            raise qbittorrentapi.exceptions.APIError(
                "Failed to fetch torrents from all qBit instances"
            )

        self.logger.debug(
            "Total torrents across %d instances: %d",
            len(qbit_manager.get_all_instances()),
            len(all_torrents),
        )
        return all_torrents

    def _sort_torrents_by_tracker_priority(self) -> None:
        """
        Reorder torrents in each qBittorrent instance by tracker priority (highest first).

        When any merged tracker defines ``AddTags``, queue order prefers the maximum
        ``Priority`` among those labels present on the torrent (visible in the client);
        otherwise order uses announce URL matching as before.

        When :attr:`categories` is set (e.g. :class:`TorrentPolicyManager`), only torrents
        in those qBitrr-monitored categories are reordered (Arr + qBit ``ManagedCategories``),
        excluding torrents tagged ``qBitrr-ignored`` — matching
        :meth:`TorrentPolicyManager._collect_monitored_torrents`.
        Otherwise all torrents from ``torrents.info`` are considered.

        Invoked by a global torrent-policy worker (single dedicated process).

        Requires qBittorrent Torrent Queuing to be enabled.
        """
        tag_to_priority = ArrBase.merge_global_tracker_tag_to_priority_max()
        qbit_manager = self.manager.qbit_manager
        for instance_name in qbit_manager.get_all_instances():
            if not self._is_qbit_instance_reachable(instance_name):
                continue
            client = self._get_qbit_client(instance_name)
            if client is None:
                continue
            try:
                try:
                    torrents = client.torrents.info(
                        status_filter="all",
                        sort="priority",
                        reverse=False,
                    )
                except (qbittorrentapi.exceptions.APIError, TypeError, ValueError):
                    torrents = client.torrents.info(
                        status_filter="all",
                        sort="added_on",
                        reverse=False,
                    )
                torrent_list = [t for t in torrents if hasattr(t, "category")]
                monitored = getattr(self, "categories", None)
                if monitored:
                    torrent_list = [
                        t
                        for t in torrent_list
                        if (
                            (
                                own := self.manager.resolve_owning_category(
                                    getattr(t, "category", None),
                                    qbit_section=instance_name,
                                )
                            )
                            and own in monitored
                            and "qBitrr-ignored" not in getattr(t, "tags", ())
                        )
                    ]
                sort_priorities = {
                    torrent.hash: self._get_torrent_queue_sort_priority(torrent, tag_to_priority)
                    for torrent in torrent_list
                }
                sorted_torrents = sorted(
                    torrent_list,
                    key=lambda t: (
                        -sort_priorities.get(t.hash, -100),
                        -ArrBase._normalize_torrent_added_on_value(t),
                        getattr(t, "name", "") or "",
                        getattr(t, "hash", "") or "",
                    ),
                )
                if len(sorted_torrents) > 1:
                    # Skip queue updates when the current queue order already matches
                    # desired tracker-priority ordering for this instance.
                    queue_membership = {
                        torrent.hash: self.is_queue_seeding_for_sort(torrent)
                        for torrent in torrent_list
                    }
                    current_order_by_qbit_priority = sorted(
                        torrent_list,
                        key=ArrBase._torrent_queue_position_sort_key,
                    )
                    current_downloading_order = [
                        torrent.hash
                        for torrent in current_order_by_qbit_priority
                        if not queue_membership.get(torrent.hash, False)
                    ]
                    current_seeding_order = [
                        torrent.hash
                        for torrent in current_order_by_qbit_priority
                        if queue_membership.get(torrent.hash, False)
                    ]
                    desired_downloading_order = [
                        torrent.hash
                        for torrent in sorted_torrents
                        if not queue_membership.get(torrent.hash, False)
                    ]
                    desired_seeding_order = [
                        torrent.hash
                        for torrent in sorted_torrents
                        if queue_membership.get(torrent.hash, False)
                    ]
                    if (
                        current_downloading_order == desired_downloading_order
                        and current_seeding_order == desired_seeding_order
                    ):
                        continue
                    # qBittorrent may ignore hash input ordering in batch topPrio calls.
                    # Move torrents one-by-one (lowest first) to enforce tracker-priority
                    # order within each queue, since qBittorrent keeps download/upload
                    # queues separate. Process seeding first so download promotions
                    # happen last and remain effectively higher priority.
                    for queue_is_seeding in (True, False):
                        queue_torrents = [
                            torrent
                            for torrent in sorted_torrents
                            if queue_membership.get(torrent.hash, False) == queue_is_seeding
                        ]
                        if queue_torrents and self.logger.isEnabledFor(logging.DEBUG):
                            queue_name = "seeding" if queue_is_seeding else "downloading"
                            preview = [
                                (
                                    t.hash[:8],
                                    sort_priorities.get(t.hash, -100),
                                    ArrBase._normalize_torrent_added_on_value(t),
                                )
                                for t in queue_torrents[:3]
                            ]
                            tail_preview = [
                                (
                                    t.hash[:8],
                                    sort_priorities.get(t.hash, -100),
                                    ArrBase._normalize_torrent_added_on_value(t),
                                )
                                for t in queue_torrents[-3:]
                            ]
                            self.logger.debug(
                                "Queue sort target for instance '%s' (%s): count=%d head=%s tail=%s",
                                instance_name,
                                queue_name,
                                len(queue_torrents),
                                preview,
                                tail_preview,
                            )
                        for torrent in reversed(queue_torrents):
                            try:
                                client.torrents_top_priority(torrent_hashes=[torrent.hash])
                            except (
                                qbittorrentapi.exceptions.APIError,
                                qbittorrentapi.exceptions.APIConnectionError,
                            ) as e:
                                self.logger.warning(
                                    "Failed to change torrent priority for hash '%s' on instance '%s': %s",
                                    torrent.hash,
                                    instance_name,
                                    e,
                                )
            except (
                qbittorrentapi.exceptions.APIError,
                qbittorrentapi.exceptions.APIConnectionError,
            ) as e:
                self.logger.warning(
                    "Failed to sort torrents by tracker priority on instance '%s': %s",
                    instance_name,
                    e,
                )

    def process_torrents(self):
        """Fetch torrents, classify each via dispatcher/inspector, then :meth:`process`.

        Call graph: ``process_torrents`` → ``_process_single_torrent`` (dispatcher)
        → ``_process_single_torrent_*`` (inspector) → ``process`` → ``_process_*`` (batch).
        """
        self._sync_loop_settings_from_config()
        try:
            try:
                self._ensure_database_error_tracking()
                torrents_with_instances = with_retry(
                    lambda: self._get_torrents_from_all_instances(),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_QBIT_READ_RETRY_EXCEPTIONS,
                )

                # Filter torrents that have category attribute
                torrents_with_instances = [
                    (instance, t)
                    for instance, t in torrents_with_instances
                    if hasattr(t, "category")
                ]
                self._warned_no_seeding_limits = False
                self.category_torrent_count = len(torrents_with_instances)
                self._torrent_important_trackers_cache.clear()
                if not len(torrents_with_instances):
                    raise DelayLoopException(
                        length=get_loop_sleep_timer_effective(), error_type="no_downloads"
                    )

                # Internet check: use the first available qBit client
                if not has_internet(self._get_primary_qbit_client()):
                    self.manager.qbit_manager.should_delay_torrent_scan = True
                    raise DelayLoopException(
                        length=get_no_internet_sleep_timer_effective(), error_type="internet"
                    )
                if self.manager.qbit_manager.should_delay_torrent_scan:
                    raise DelayLoopException(
                        length=get_no_internet_sleep_timer_effective(), error_type="delay"
                    )

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
                    else:
                        self._reset_database_error_tracking()

                    self._health_check_counter = 0

                self.api_calls()
                self.refresh_download_queue()
                managed_tag_pool = ArrBase.merge_global_tracker_configured_add_tags()
                # Multi-instance: Process torrents from all instances
                for instance_name, torrent in torrents_with_instances:
                    with contextlib.suppress(qbittorrentapi.NotFound404Error):
                        self._process_single_torrent(
                            torrent,
                            instance_name=instance_name,
                            managed_tag_pool=managed_tag_pool,
                        )
                self.process()
                self._reset_database_error_tracking()
            except NoConnectionrException as e:
                self.logger.error(e.message)
            except PyarrConnectionError as e:
                self.logger.warning("Couldn't connect to %s: %s", self.type, e)
                self._temp_overseer_request_cache = defaultdict(set)
                raise DelayLoopException(length=300, error_type="arr") from e
            except requests.exceptions.ConnectionError:
                self.logger.warning("Couldn't connect to %s", self.type)
                self._temp_overseer_request_cache = defaultdict(set)
                return self._temp_overseer_request_cache
            except qbittorrentapi.exceptions.APIError as e:
                self.logger.error("The qBittorrent API returned an unexpected error")
                self.logger.debug(
                    "Unexpected APIError from qBitTorrent: %s", str(e)
                )  # , exc_info=e)
                raise DelayLoopException(length=300, error_type="qbit")
            except (OperationalError, DatabaseError) as e:
                # Database errors after retry exhaustion - implement automatic recovery with backoff
                error_msg = str(e).lower()
                current_time = time.time()

                self._ensure_database_error_tracking()

                # Reset if >5min since last error (new error sequence)
                if (
                    current_time - self._db_last_error_time > 300
                ):  # Reset if >5min since last error
                    self._db_error_count = 0
                    self._db_first_error_time = current_time

                self._db_error_count += 1
                self._db_last_error_time = current_time

                self.logger.error(
                    "Database operation failed after retry exhaustion: %s (%s)",
                    e.__class__.__name__,
                    e,
                )

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
                        self._reset_database_error_tracking()
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

    def _ensure_database_error_tracking(self) -> None:
        """Initialize database error counters if not yet created."""
        if not hasattr(self, "_db_error_count"):
            self._db_error_count = 0
            self._db_first_error_time = 0
            self._db_last_error_time = 0

    def _reset_database_error_tracking(self) -> None:
        """Clear consecutive database error state after a healthy iteration."""
        self._db_error_count = 0
        self._db_first_error_time = 0
        self._db_last_error_time = 0

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
            self._reset_database_error_tracking()
            return

        # Step 2: Try full repair (more invasive)
        self.logger.warning("WAL checkpoint failed - attempting full database repair...")
        try:
            if repair_database(db_path, backup=True, logger_override=self.logger):
                self.logger.info("Database repair successful")
                self._reset_database_error_tracking()
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
                self._reset_database_error_tracking()
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
                self._reset_database_error_tracking()
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
                    self._reset_database_error_tracking()
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

    def _get_torrent_important_trackers(
        self,
        torrent: qbittorrentapi.TorrentDictionary,
        *,
        use_cache: bool = True,
        for_queue_sort_priority: bool = False,
    ) -> tuple[set[str], set[str]]:
        torrent_hash = getattr(torrent, "hash", "")
        if use_cache and torrent_hash and not for_queue_sort_priority:
            if cached := self._torrent_important_trackers_cache.get(torrent_hash):
                return cached
        try:
            current_tracker_urls = {
                i.url.rstrip("/") for i in torrent.trackers if hasattr(i, "url")
            }
        except qbittorrentapi.exceptions.APIError as e:
            message = str(e)
            # Some qBittorrent builds intermittently return non-JSON/empty tracker payloads.
            # Skip tracker-based logic for this torrent instead of delaying the entire loop.
            if "JSONDecodeError" in message or "response parsing" in message.lower():
                self.logger.warning(
                    "Skipping tracker processing for torrent '%s' (%s): %s",
                    getattr(torrent, "name", "<unknown>"),
                    getattr(torrent, "hash", "<unknown>"),
                    message,
                )
                raise _TrackerDataUnavailable(message) from e
            # Tracker lookup can race with torrent removal and briefly return 404.
            # Treat this as transient/unavailable metadata for this pass.
            if (
                isinstance(e, qbittorrentapi.exceptions.NotFound404Error)
                or "Torrent hash(es):" in message
            ):
                self.logger.warning(
                    "Skipping tracker processing for missing torrent '%s' (%s): %s",
                    getattr(torrent, "name", "<unknown>"),
                    getattr(torrent, "hash", "<unknown>"),
                    message,
                )
                raise _TrackerDataUnavailable(message) from e
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
        if not for_queue_sort_priority:
            monitored_trackers = monitored_trackers.union(need_to_be_added)
        result = (need_to_be_added, monitored_trackers)
        if use_cache and torrent_hash and not for_queue_sort_priority:
            self._torrent_important_trackers_cache[torrent_hash] = result
        return result

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
        _list_of_tags: list[list[str]] = []
        for i in new_list:
            if _extract_tracker_host(i.get("URI") or "") not in removed_hosts:
                raw = i.get("AddTags", [])
                if isinstance(raw, str):
                    _list_of_tags.append([raw] if raw.strip() else [])
                elif raw:
                    _list_of_tags.append([x for x in raw if isinstance(x, str)])
        max_item = max(new_list, key=self.__return_max) if new_list else {}
        return max_item, {t for row in _list_of_tags for t in row if t.strip()}

    def _get_torrent_tracker_priority(
        self, torrent: qbittorrentapi.TorrentDictionary, *, for_queue_sort: bool = False
    ) -> int:
        """Return the tracker Priority for this torrent's most important monitored tracker."""
        try:
            _, monitored_trackers = self._get_torrent_important_trackers(
                torrent, for_queue_sort_priority=for_queue_sort
            )
        except _TrackerDataUnavailable:
            return -100
        remove_urls = set()
        try:
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
                    remove_urls.add(tracker_url)
        except (
            qbittorrentapi.exceptions.APIError,
            qbittorrentapi.exceptions.APIConnectionError,
            AttributeError,
            TypeError,
            ValueError,
        ) as e:
            self.logger.debug(
                "Failed to inspect tracker metadata for torrent '%s' while calculating priority",
                getattr(torrent, "hash", "<unknown>"),
                exc_info=e,
            )
        most_important_tracker, _ = self._get_most_important_tracker_and_tags(
            monitored_trackers, remove_urls
        )
        return most_important_tracker.get("Priority", -100)

    def _get_torrent_queue_sort_priority(
        self, torrent: qbittorrentapi.TorrentDictionary, tag_to_priority: dict[str, int]
    ) -> int:
        """
        Priority for ``SortTorrents`` ordering: blends tag-derived and announce-based
        priority. Announce-based resolution (excluding ``AddTrackerIfMissing``-only URIs)
        is always computed; when configured ``AddTags`` match the torrent, the
        effective priority is the higher of tag-tier and announce-tier so stale or
        misleading labels cannot override a stronger announce match.
        """
        announce_pri = self._get_torrent_tracker_priority(torrent, for_queue_sort=True)
        if not tag_to_priority:
            return announce_pri
        present = _parse_qbittorrent_tag_list(getattr(torrent, "tags", None))
        matched = [tag_to_priority[t] for t in present if t in tag_to_priority]
        if not matched:
            return announce_pri
        tag_pri = max(matched)
        if tag_pri <= -100:
            return announce_pri
        return max(tag_pri, announce_pri)

    def refresh_download_queue(self):
        self.queue = self.get_queue() or []
        self.queue_active_count = len(self.queue)
        self.category_torrent_count = 0
        self.requeue_cache = defaultdict(set)
        if self.queue:
            self.cache = {
                entry["downloadId"]: entry["id"] for entry in self.queue if entry.get("downloadId")
            }
            self.requeue_cache, self.queue_file_ids = self.build_queue_caches_from_queue(
                self.queue
            )
            if self.model_queue:
                with database_lock():
                    with_database_retry(
                        lambda: self.model_queue.delete()
                        .where(
                            (self.model_queue.EntryId.not_in(list(self.queue_file_ids)))
                            & (self.model_queue.ArrInstance == self._name)
                        )
                        .execute(),
                        logger=self.logger,
                    )

        self._update_bad_queue_items()

    def get_queue(self, page=1, page_size=1000, sort_direction="ascending", sort_key="timeLeft"):
        res = with_retry(
            lambda: self.client.queue.get(
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
                lambda: self.client.quality_profile.get(),
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
            # Get all items from Arr instance (use arr_type, not section-name prefix)
            if self.type == "radarr":
                items = self.client.movie.get()
                item_type = "movie"
            elif self.type == "sonarr":
                items = self.client.series.get()
                item_type = "series"
            elif self.type == "lidarr":
                items = self.client.artist.get()
                item_type = "artist"
            else:
                self.logger.warning("Unknown Arr type for temp profile reset: %s", self.type)
                return

            self.logger.info("Checking %d %ss for temp profile resets...", len(items), item_type)

            for item in items:
                profile_id = item.get("qualityProfileId")

                # Check if item is currently using a temp profile
                if profile_id in self.main_quality_profile_ids.keys():
                    # This is a temp profile - get the original main profile
                    original_id = self.main_quality_profile_ids[profile_id]
                    item["qualityProfileId"] = original_id
                    item_name = item.get("title", item.get("artistName", "Unknown"))
                    from_profile_id = profile_id
                    to_profile_id = original_id

                    if item_type == "movie":
                        update_fn = lambda item=item: self.client.movie.update(data=item)
                    elif item_type == "series":
                        update_fn = lambda item=item: self.client.series.update(data=item)
                    else:
                        update_fn = lambda item=item: self.client.artist.update(data=item)
                    if self._retry_profile_switch_update(update_fn, item_type):
                        reset_count += 1
                        self.logger.info(
                            f"Reset {item_type} '{item_name}' "
                            f"from temp profile (ID:{from_profile_id}) to main profile (ID:{to_profile_id})"
                        )

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

            # Determine which model to use (arr_type, not section-name prefix)
            if self.type == "radarr":
                model = self.movies_file_model
                item_type = "movie"
            elif self.type == "sonarr":
                model = self.model_file  # episodes
                item_type = "episode"
            elif self.type == "lidarr":
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
                        item = self.client.movie.get(item_id=entry_id)
                        item["qualityProfileId"] = original_profile
                        self.client.movie.update(data=item)
                    elif item_type == "episode":
                        # For episodes, we need to update the series
                        series_id = db_item.SeriesId
                        series = self.client.series.get(item_id=series_id)
                        series["qualityProfileId"] = original_profile
                        self.client.series.update(data=series)
                    elif item_type == "artist":
                        artist = self.client.artist.get(item_id=entry_id)
                        artist["qualityProfileId"] = original_profile
                        self.client.artist.update(data=artist)

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

        self._bind_type_specific_models(series_or_artist_model, track_model)

        # Set torrents model if TAGLESS is enabled
        self.torrents = torrent_model if TAGLESS else None

        self.logger.debug("Database initialization completed for %s", self._name)
        self.search_setup_completed = True

    def _bind_type_specific_models(
        self,
        series_or_artist_model: type[SeriesFilesModel] | type[ArtistFilesModel] | None,
        track_model: type[TrackFilesModel] | None,
    ) -> None:
        """Wire series/artist/track model attributes; subclasses override."""
        self.series_file_model = None
        self.artists_file_model = None
        self.track_file_model = None

    def _get_models(
        self,
    ) -> tuple[
        type[EpisodeFilesModel] | type[MoviesFilesModel] | type[AlbumFilesModel],
        type[EpisodeQueueModel] | type[MovieQueueModel] | type[AlbumQueueModel],
        type[SeriesFilesModel] | type[ArtistFilesModel] | None,
        type[TrackFilesModel] | None,
        type[TorrentLibrary] | None,
    ]:
        raise UnhandledError(f"{type(self).__name__} must implement _get_models")

    def _re_search_failed_media(self, object_id: Any) -> None:
        """Re-trigger Arr search after a failed download; subclasses implement."""
        return

    def _custom_format_queue_fields(self) -> tuple[str, str | None] | None:
        """Return ``(entry_id_field, file_id_field)`` for CF unmet checks, or None."""
        return None

    def collect_years_for_search(self) -> list[int]:
        """Years eligible for year-based search; Radarr/Sonarr override."""
        return []

    def build_queue_caches_from_queue(
        self, queue: list[dict[str, Any]]
    ) -> tuple[dict[Any, Any], set[Any]]:
        """Build requeue/file-id caches from a refreshed download queue."""
        from qBitrr.arss.arr_type_config import build_queue_caches

        return build_queue_caches(
            self.type, queue, series_search=bool(getattr(self, "series_search", False))
        )

    def maybe_do_search(
        self,
        file_model: EpisodeFilesModel | MoviesFilesModel | SeriesFilesModel,
        request: bool = False,
        todays: bool = False,
        bypass_limit: bool = False,
        series_search: bool = False,
        commands: int = 0,
    ):
        return _maybe_do_search_fn(
            self,
            file_model,
            request=request,
            todays=todays,
            bypass_limit=bypass_limit,
            series_search=series_search,
            commands=commands,
        )

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
        if get_search_loop_delay_effective() == -1:
            loop_delay = 30
        else:
            loop_delay = get_search_loop_delay_effective()
        try:
            event = self.manager.qbit_manager.shutdown_event
            _db_request_update_fn(self)
            try:
                for entry, commands in _db_get_request_files_fn(self):
                    if totcommands == -1:
                        totcommands = commands
                        self.logger.info("Starting request search for %s items", totcommands)
                    else:
                        totcommands -= 1
                    if get_search_loop_delay_effective() == -1:
                        loop_delay = 30
                    else:
                        loop_delay = get_search_loop_delay_effective()
                    while (not event.is_set()) and (
                        not _maybe_do_search_fn(
                            self,
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
            self._handle_delay_loop_exception(
                e,
                self.manager.qbit_manager.shutdown_event.wait,
                reset_torrent_scan_delay=False,
            )

    def get_year_search(self) -> tuple[list[int], int]:
        years = self.collect_years_for_search()
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
                self._sync_loop_settings_from_config()
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
                    _db_maybe_reset_entry_searched_state_fn(self)
                    self.refresh_download_queue()
                    self.db_update()
                    # Reset the loop timer after db_update() so that the time
                    # spent ingesting the library does not count toward
                    # loop_timer. For large libraries (e.g. a big Lidarr music
                    # library) db_update() can take much longer than loop_timer,
                    # in which case ``now >= timer + loop_timer`` is already true
                    # by the time ingestion finishes and RestartLoopException is
                    # raised before db_get_files()/maybe_do_search() ever runs --
                    # starving missing-search entirely for that instance.
                    timer = datetime.now()

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
                        ) in _db_get_files_fn(self):
                            any_commands = True
                            if totcommands == -1:
                                totcommands = commands
                                self.logger.info("Starting search for %s items", totcommands)
                            if get_search_loop_delay_effective() == -1:
                                loop_delay = 30
                            else:
                                loop_delay = get_search_loop_delay_effective()
                            while (not event.is_set()) and (
                                not _maybe_do_search_fn(
                                    self,
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
                    except PyarrConnectionError as e:
                        self.logger.warning(
                            "Could not reach %s Arr API during search loop: %s",
                            self._name,
                            e,
                        )
                        raise DelayLoopException(length=300, error_type="arr") from e
                    except Exception as e:
                        self.logger.exception(e, exc_info=sys.exc_info())
                    event.wait(get_loop_sleep_timer_effective())
                except DelayLoopException as delay_exc:
                    self._handle_delay_loop_exception(
                        delay_exc,
                        event.wait,
                        reset_torrent_scan_delay=True,
                    )
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
                        if not self._is_any_qbit_instance_reachable():
                            raise NoConnectionrException(
                                "Could not connect to qBit client.", error_type="qbit"
                            )
                        if not self.is_alive:
                            raise NoConnectionrException(
                                f"Could not connect to {self.uri}", error_type="arr"
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
                    event.wait(get_loop_sleep_timer_effective())
                except DelayLoopException as e:
                    self._handle_delay_loop_exception(
                        e,
                        event.wait,
                        reset_torrent_scan_delay=True,
                    )
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
