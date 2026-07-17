"""Arr-type helpers for queue caches and year-search (used by ArrBase hooks)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class ArrTypeConfig:
    """Lightweight per-Arr-type wiring used by shared Arr orchestration."""

    queue_id_field: str
    queue_requeue_as_set: bool


ARR_TYPE_CONFIG: dict[str, ArrTypeConfig] = {
    "sonarr": ArrTypeConfig(queue_id_field="episodeId", queue_requeue_as_set=True),
    "radarr": ArrTypeConfig(queue_id_field="movieId", queue_requeue_as_set=False),
    "lidarr": ArrTypeConfig(queue_id_field="albumId", queue_requeue_as_set=False),
}


def get_arr_type_config(arr_type: str) -> ArrTypeConfig | None:
    """Return ArrTypeConfig for a known Arr type, or None."""
    return ARR_TYPE_CONFIG.get(arr_type)


def sonarr_queue_id_field(*, series_search: bool) -> str:
    """Sonarr queue media id field depends on series vs episode search mode."""
    return "seriesId" if series_search else "episodeId"


def build_queue_caches(
    arr_type: str,
    queue: list[dict[str, Any]],
    *,
    series_search: bool = False,
) -> tuple[dict[Any, Any], set[Any]]:
    """Build ``(requeue_cache, queue_file_ids)`` for a refreshed download queue."""
    if arr_type == "sonarr":
        field = sonarr_queue_id_field(series_search=bool(series_search))
        requeue: dict[Any, set[Any]] = defaultdict(set)
        for entry in queue:
            if media_id := entry.get(field):
                requeue[entry["id"]].add(media_id)
        file_ids = {entry[field] for entry in queue if entry.get(field)}
        return requeue, file_ids

    cfg = ARR_TYPE_CONFIG.get(arr_type)
    if cfg is None:
        return {}, set()
    field = cfg.queue_id_field
    requeue_map = {entry["id"]: entry[field] for entry in queue if entry.get(field)}
    file_ids = {entry[field] for entry in queue if entry.get(field)}
    return requeue_map, file_ids


def collect_years_for_search(arr: Any) -> list[int]:
    """Collect years eligible for year-based search (Radarr movies / Sonarr episodes)."""
    from qBitrr.arss._shared import _ARR_RETRY_EXCEPTIONS_EXTENDED, with_retry

    years_list: set[int] = set()
    if arr.type == "radarr":
        movies = with_retry(
            lambda: arr.client.movie.get(),
            retries=3,
            backoff=0.5,
            max_backoff=3,
            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
        )
        for movie in movies:
            if not movie["monitored"]:
                continue
            year = movie.get("year", 0)
            if year != 0 and year <= datetime.now(timezone.utc).year:
                years_list.add(year)
    elif arr.type == "sonarr":
        series = with_retry(
            lambda: arr.client.series.get(),
            retries=3,
            backoff=0.5,
            max_backoff=3,
            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
        )
        for show in series:
            episodes = with_retry(
                lambda s=show: arr.client.episode.get(series_id=s["id"]),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
            )
            for episode in episodes:
                if "airDateUtc" not in episode:
                    continue
                if not arr.search_specials and episode["seasonNumber"] == 0:
                    continue
                if not episode["monitored"]:
                    continue
                years_list.add(
                    datetime.strptime(episode["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ")
                    .replace(tzinfo=timezone.utc)
                    .year
                )
    ordered = dict.fromkeys(years_list)
    reverse = bool(getattr(arr, "search_in_reverse", False))
    return [key for key, _ in sorted(ordered.items(), key=lambda item: item[0], reverse=reverse)]


# Optional extension point for type-specific re-search fetch callables.
RESEARCH_FETCHERS: dict[str, Callable[[Any, Any], Any]] = {}
