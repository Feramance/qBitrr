from __future__ import annotations

from typing import TYPE_CHECKING, Any

import qbittorrentapi
import qbittorrentapi.exceptions
import requests
from ujson import JSONDecodeError

from qBitrr.arr_client import (
    JsonObject,
    Lidarr,
    PyarrConnectionError,
    PyarrResourceNotFound,
    PyarrServerError,
    Radarr,
    Sonarr,
    build_lidarr_client,
    build_radarr_client,
    build_sonarr_client,
    execute_command,
)
from qBitrr.arr_tracker_index import (
    TrackerIndex,
    build_tracker_index,
)
from qBitrr.arr_tracker_index import extract_tracker_host as _extract_tracker_host
from qBitrr.catalog_rollups import refresh_rollups_after_db_update
from qBitrr.category_paths import (
    category_parents,
    find_overlap_conflicts,
    has_subcategory_separator,
    matches_configured,
    normalize_category,
)
from qBitrr.config import (
    APPDATA_FOLDER,
    AUTO_PAUSE_RESUME,
    CONFIG,
    PROCESS_ONLY,
    QBIT_DISABLED,
    SEARCH_ONLY,
    TAGLESS,
    get_auto_pause_resume_effective,
    get_completed_download_folder_effective,
    get_effective_qbit_disabled,
    get_failed_category_effective,
    get_free_space_guard_settings,
    get_ignore_torrents_younger_than_effective,
    get_loop_sleep_timer_effective,
    get_no_internet_sleep_timer_effective,
    get_recheck_category_effective,
    get_search_loop_delay_effective,
    sync_config_from_disk,
)
from qBitrr.db_lock import database_lock, with_database_retry
from qBitrr.errors import (
    DelayLoopException,
    NoConnectionrException,
    RestartLoopException,
    SkipException,
    UnhandledError,
)
from qBitrr.logger import run_logs
from qBitrr.qbit_seeding_config import load_qbit_seeding_config
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
    has_internet,
    parse_size,
    qbit_sections,
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
    PyarrConnectionError,
)

_QBIT_WRITE_RETRY_EXCEPTIONS = (
    qbittorrentapi.exceptions.APIError,
    qbittorrentapi.exceptions.APIConnectionError,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ContentDecodingError,
    requests.exceptions.RequestException,
)

_QBIT_READ_RETRY_EXCEPTIONS = (
    *_QBIT_WRITE_RETRY_EXCEPTIONS,
    JSONDecodeError,
    ValueError,
)

# Backward-compatible alias for destructive qBit write operations.
_QBIT_TORRENT_DELETE_EXCEPTIONS = _QBIT_WRITE_RETRY_EXCEPTIONS


class _TrackerDataUnavailable(Exception):
    """Raised when qBittorrent cannot provide reliable tracker metadata."""


def _lidarr_track_duration_seconds(raw: Any) -> int:
    """Convert Lidarr track ``duration`` from API milliseconds to whole seconds for SQLite.

    Lidarr's track resource reports duration in milliseconds; values below one second
    become ``0`` after integer division (sub-second interludes/transitions).
    """

    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 0
    if v <= 0:
        return 0
    return v // 1000


def _parse_qbittorrent_tag_list(tags_str: str | None) -> set[str]:
    """Split qBittorrent's comma-separated ``tags`` string into non-empty labels."""
    if not tags_str or not isinstance(tags_str, str):
        return set()
    return {p.strip() for p in tags_str.split(",") if p.strip()}


def _prune_instance_hash_map(mapping: dict[str, set[str]], hashes: set[str]) -> None:
    """Remove hashes from a per-instance map, dropping empty instance buckets."""
    if not hashes:
        return
    for inst_name in list(mapping):
        mapping[inst_name] -= hashes
        if not mapping[inst_name]:
            del mapping[inst_name]


def _collect_instance_hash_map_hashes(*maps: dict[str, set[str]]) -> set[str]:
    """Return all hashes still queued across one or more per-instance maps."""
    pending: set[str] = set()
    for mapping in maps:
        for hashes in mapping.values():
            pending.update(hashes)
    return pending


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
    pass


__all__ = [
    "_ARR_RETRY_EXCEPTIONS",
    "_ARR_RETRY_EXCEPTIONS_EXTENDED",
    "_QBIT_READ_RETRY_EXCEPTIONS",
    "_QBIT_TORRENT_DELETE_EXCEPTIONS",
    "_QBIT_WRITE_RETRY_EXCEPTIONS",
    "_TrackerDataUnavailable",
    "_collect_instance_hash_map_hashes",
    "_extract_tracker_host",
    "_is_media_available",
    "_is_media_processing",
    "_lidarr_track_duration_seconds",
    "_normalize_media_status",
    "_parse_qbittorrent_tag_list",
    "_prune_instance_hash_map",
    "APPDATA_FOLDER",
    "AUTO_PAUSE_RESUME",
    "AlbumFilesModel",
    "AlbumQueueModel",
    "ArtistFilesModel",
    "CONFIG",
    "DelayLoopException",
    "EpisodeFilesModel",
    "EpisodeQueueModel",
    "ExpiringSet",
    "FilesQueued",
    "JsonObject",
    "Lidarr",
    "MovieQueueModel",
    "MoviesFilesModel",
    "NoConnectionrException",
    "PROCESS_ONLY",
    "PyarrConnectionError",
    "PyarrResourceNotFound",
    "PyarrServerError",
    "QBIT_DISABLED",
    "Radarr",
    "RestartLoopException",
    "SEARCH_ONLY",
    "SeriesFilesModel",
    "SkipException",
    "Sonarr",
    "sync_config_from_disk",
    "TAGLESS",
    "TorrentLibrary",
    "TrackFilesModel",
    "TrackerIndex",
    "UnhandledError",
    "absolute_file_paths",
    "build_lidarr_client",
    "build_radarr_client",
    "build_sonarr_client",
    "build_tracker_index",
    "category_parents",
    "clear_search_activity",
    "database_lock",
    "execute_command",
    "fetch_search_activities",
    "find_overlap_conflicts",
    "get_auto_pause_resume_effective",
    "get_completed_download_folder_effective",
    "get_effective_qbit_disabled",
    "get_failed_category_effective",
    "get_free_space_guard_settings",
    "get_ignore_torrents_younger_than_effective",
    "get_loop_sleep_timer_effective",
    "get_no_internet_sleep_timer_effective",
    "get_recheck_category_effective",
    "get_search_loop_delay_effective",
    "has_internet",
    "has_subcategory_separator",
    "load_qbit_seeding_config",
    "matches_configured",
    "normalize_category",
    "parse_size",
    "qbit_sections",
    "record_search_activity",
    "refresh_rollups_after_db_update",
    "run_logs",
    "validate_and_return_torrent_file",
    "with_database_retry",
    "with_retry",
]
