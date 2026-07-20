"""Arr-type wiring helpers (queue id fields); type-specific logic lives on concretes.

``build_queue_caches`` / ``collect_years_for_search`` type switches were moved onto
:class:`~qBitrr.arss.radarr.RadarrArr`, :class:`~qBitrr.arss.sonarr.SonarrArr`, and
:class:`~qBitrr.arss.lidarr.LidarrArr` (``build_queue_caches_from_queue`` /
``collect_years_for_search``). This module keeps lightweight shared constants and
Sonarr's series-vs-episode queue field helper for call sites that need them without
an Arr instance.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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


# Optional extension point for type-specific re-search fetch callables.
RESEARCH_FETCHERS: dict[str, Callable[[Any, Any], Any]] = {}
