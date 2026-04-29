"""Denormalized catalog counts and Arr WebUI rollup refresh.

Search loops run in child processes writing to the shared qBitrr SQLite catalog. The WebUI
runs in the main process. Because process-local Python state (``arr._webui_catalog_rollups``)
cannot observe writes from other processes, the WebUI re-aggregates directly from SQLite on
every read via :func:`ensure_arr_webui_rollups`. To keep that affordable, each Arr type is
serviced by a **single aggregate SELECT** (H-3) that uses ``SUM(CASE WHEN ... END)`` to
compute available / monitored / missing / quality-met / requests in one round-trip.

A short in-process TTL on top of the aggregate keeps back-to-back Flask handlers in the WebUI
from re-running the same query (M-5). The TTL is intentionally tiny (a few seconds) so cross-
process catalogue updates surface promptly.

Helpers like :func:`update_album_total_tracks` and :func:`update_series_season_episode_totals`
maintain denormalized columns on the catalog rows themselves so individual row payloads stay
cheap; those run inside worker processes whenever the worker writes a row.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import TYPE_CHECKING, Any

from peewee import Case, Value, fn

from qBitrr.db_lock import database_lock

if TYPE_CHECKING:
    from qBitrr.arss import Arr

_ZERO_COUNTS_EP3 = {"available": 0, "monitored": 0, "missing": 0}
_ZERO_COUNTS_RAD = {
    "available": 0,
    "monitored": 0,
    "missing": 0,
    "quality_met": 0,
    "requests": 0,
}

# Per-process rollup cache: WebUI re-aggregates on each read but back-to-back Flask handlers
# (e.g. ``/api/<arr>/<cat>/X`` followed immediately by ``/api/<arr>/<cat>/Y``) within ``_TTL``
# seconds reuse the previous aggregate.  Keyed by ``(arr_id, _name)`` so multiple Arr instances
# do not share state.  Locked because Flask serves requests from a thread pool.
_ROLLUP_CACHE_TTL_SECONDS = 5.0
_rollup_cache: dict[tuple[int, str], tuple[float, dict[str, Any]]] = {}
_rollup_cache_lock = Lock()


def _count_entry_rows(model: Any, where_clause: Any) -> int:
    """Scalar COUNT(*) for catalog file models keyed by ``EntryId``.

    Kept for callers that still need a one-off COUNT (it is no longer used by the rollup
    aggregator itself, which is now a single ``SUM(CASE...)`` SELECT per Arr type).

    Definition note (M-4): rollup *availability* is **not** the same metric as a row-level
    ``hasFile``.  Rollups define ``available = (Monitored == True) AND (file_id IS NOT NULL
    AND file_id != 0)`` so an unmonitored row that has a file does not count toward the
    catalogue's "available" total.  Per-row payloads (``movies[].hasFile``, etc.) expose
    the underlying ``has_file`` regardless of monitoring; consumers that want the rollup
    semantics should ``and`` it with ``monitored``.
    """
    return model.select(fn.COUNT(model.EntryId)).where(where_clause).scalar() or 0


def _sum_case_int(condition: Any, name: str) -> Any:
    """Build a ``SUM(CASE WHEN <condition> THEN 1 ELSE 0 END) AS <name>`` expression.

    The WHEN is a peewee expression (returns 0/1 booleans in SQLite); SUM aggregates them.
    Used to pack multiple boolean ``COUNT`` queries into a single round-trip.
    """
    return fn.SUM(Case(None, ((condition, Value(1)),), Value(0))).alias(name)


def _radarr_aggregate(arr: Any, name: str) -> dict[str, Any] | None:
    """Single-pass aggregate for the Radarr movies catalog (H-3)."""
    model = getattr(arr, "model_file", None)
    if model is None:
        return None
    inst = model.ArrInstance == name
    has_file = (model.MovieFileId.is_null(False)) & (model.MovieFileId != 0)
    monitored = model.Monitored == True  # noqa: E712
    row = (
        model.select(
            fn.COUNT(model.EntryId).alias("total"),
            _sum_case_int(monitored, "monitored"),
            _sum_case_int(monitored & has_file, "available"),
            _sum_case_int(model.QualityMet == True, "quality_met"),  # noqa: E712
            _sum_case_int(model.IsRequest == True, "requests"),  # noqa: E712
        )
        .where(inst)
        .dicts()
        .get()
    )
    monitored_count = int(row.get("monitored") or 0)
    available_count = int(row.get("available") or 0)
    return {
        "movies": {
            "counts": {
                "available": available_count,
                "monitored": monitored_count,
                "missing": max(monitored_count - available_count, 0),
                "quality_met": int(row.get("quality_met") or 0),
                "requests": int(row.get("requests") or 0),
            },
            "total": int(row.get("total") or 0),
        }
    }


def _sonarr_aggregate(arr: Any, name: str) -> dict[str, Any] | None:
    """Single-pass aggregate for Sonarr episodes plus a separate cheap series total."""
    ep = getattr(arr, "model_file", None)
    if ep is None:
        return None
    inst_ep = ep.ArrInstance == name
    has_file = (ep.EpisodeFileId.is_null(False)) & (ep.EpisodeFileId != 0)
    monitored = ep.Monitored == True  # noqa: E712
    row = (
        ep.select(
            _sum_case_int(monitored, "monitored"),
            _sum_case_int(monitored & has_file, "available"),
        )
        .where(inst_ep)
        .dicts()
        .get()
    )
    monitored_count = int(row.get("monitored") or 0)
    available_count = int(row.get("available") or 0)

    sm = getattr(arr, "series_file_model", None)
    total_series = 0
    if sm is not None:
        total_series = sm.select(fn.COUNT(sm.EntryId)).where(sm.ArrInstance == name).scalar() or 0
    return {
        "sonarr_episodes": {
            "counts": {
                "available": available_count,
                "monitored": monitored_count,
                "missing": max(monitored_count - available_count, 0),
            },
            "total_series": int(total_series),
        }
    }


def _lidarr_aggregate(arr: Any, name: str) -> dict[str, Any] | None:
    """Single-pass aggregates for Lidarr albums + (joined) tracks (H-3 + L-1)."""
    album_m = getattr(arr, "model_file", None)
    track_m = getattr(arr, "track_file_model", None)
    if album_m is None:
        return None
    inst_al = album_m.ArrInstance == name
    has_album_file = (album_m.AlbumFileId.is_null(False)) & (album_m.AlbumFileId != 0)
    album_monitored = album_m.Monitored == True  # noqa: E712
    album_row = (
        album_m.select(
            fn.COUNT(album_m.EntryId).alias("total"),
            _sum_case_int(album_monitored, "monitored"),
            _sum_case_int(album_monitored & has_album_file, "available"),
            _sum_case_int(album_m.QualityMet == True, "quality_met"),  # noqa: E712
            _sum_case_int(album_m.IsRequest == True, "requests"),  # noqa: E712
        )
        .where(inst_al)
        .dicts()
        .get()
    )
    monitored_count = int(album_row.get("monitored") or 0)
    available_count = int(album_row.get("available") or 0)
    out: dict[str, Any] = {
        "lidarr_albums": {
            "counts": {
                "available": available_count,
                "monitored": monitored_count,
                "missing": max(monitored_count - available_count, 0),
                "quality_met": int(album_row.get("quality_met") or 0),
                "requests": int(album_row.get("requests") or 0),
            },
            "total": int(album_row.get("total") or 0),
        }
    }

    if track_m is not None:
        # JOIN tracks to albums once and aggregate everything in the same SELECT.
        track_row = (
            track_m.select(
                fn.COUNT(track_m.EntryId).alias("total"),
                _sum_case_int(track_m.HasFile == True, "available"),  # noqa: E712
                _sum_case_int(track_m.Monitored == True, "monitored"),  # noqa: E712
                _sum_case_int(track_m.HasFile == False, "missing"),  # noqa: E712
            )
            .join(album_m, on=(track_m.AlbumId == album_m.EntryId))
            .where((track_m.ArrInstance == name) & (album_m.ArrInstance == name))
            .dicts()
            .get()
        )
        out["lidarr_tracks"] = {
            "counts": {
                "available": int(track_row.get("available") or 0),
                "monitored": int(track_row.get("monitored") or 0),
                # Row-level absence (not the album-level "missing").
                "missing": int(track_row.get("missing") or 0),
            },
            "total": int(track_row.get("total") or 0),
        }
    return out


def refresh_arr_webui_rollups(arr: Arr) -> None:
    """
    Read aggregate counts from SQLite into ``arr._webui_catalog_rollups`` for this Arr instance.

    Each Arr type uses a single SELECT with ``SUM(CASE WHEN ...)`` so the lock is held for one
    round-trip even when the catalog has hundreds of thousands of rows.  Callers should use
    :func:`ensure_arr_webui_rollups` (which adds the per-process TTL).
    """
    db = getattr(arr, "db", None)
    if db is None:
        return
    name = getattr(arr, "_name", "")
    t = getattr(arr, "type", None)
    if t not in ("radarr", "sonarr", "lidarr"):
        arr._webui_catalog_rollups = {}  # type: ignore[attr-defined]
        return
    aggregator = {
        "radarr": _radarr_aggregate,
        "sonarr": _sonarr_aggregate,
        "lidarr": _lidarr_aggregate,
    }[t]
    with database_lock():
        with db.connection_context():
            roll = aggregator(arr, name)
    arr._webui_catalog_rollups = roll or {}  # type: ignore[attr-defined]


def ensure_arr_webui_rollups(arr: Arr) -> None:
    """Refresh rollups from SQLite, with a short per-process TTL (M-5).

    The TTL is intentionally tiny (``_ROLLUP_CACHE_TTL_SECONDS``) so successive Flask handlers
    within the same WebUI tick reuse the previous aggregate; cross-process worker writes still
    surface within a few seconds.
    """
    if getattr(arr, "db", None) is None:
        return
    cache_key = (id(arr), getattr(arr, "_name", ""))
    now = time.monotonic()
    with _rollup_cache_lock:
        cached = _rollup_cache.get(cache_key)
        if cached is not None and (now - cached[0]) < _ROLLUP_CACHE_TTL_SECONDS:
            arr._webui_catalog_rollups = cached[1]  # type: ignore[attr-defined]
            return
    refresh_arr_webui_rollups(arr)
    snapshot = getattr(arr, "_webui_catalog_rollups", None) or {}
    with _rollup_cache_lock:
        _rollup_cache[cache_key] = (now, snapshot)


def invalidate_arr_webui_rollups_cache(arr: Arr | None = None) -> None:
    """Drop the in-process TTL cache for one Arr (or all when ``None``).

    Workers should call this with their own ``arr`` after a write; it is the equivalent of
    the previous ``mark_arr_webui_rollups_stale`` flag but it works across the WebUI cache
    rather than a per-Arr attribute.
    """
    with _rollup_cache_lock:
        if arr is None:
            _rollup_cache.clear()
            return
        cache_key = (id(arr), getattr(arr, "_name", ""))
        _rollup_cache.pop(cache_key, None)


# --- Backwards-compatible shims: workers still call these names, but the worker-side cache
#     is now a no-op stale flag (the WebUI's TTL cache is the only one that matters). ----
def mark_arr_webui_rollups_stale(arr: Arr) -> None:  # noqa: D401 - retained for external callers
    """Compatibility shim: clear the WebUI's TTL cache for this Arr.

    The previous worker-process ``_webui_rollups_stale`` flag is no longer consulted because
    the WebUI runs in a different process and never observed it.  Callers (workers) keep
    using this name so we just forward to :func:`invalidate_arr_webui_rollups_cache`.
    """
    invalidate_arr_webui_rollups_cache(arr)


def flush_pending_arr_webui_rollups(
    arr: Arr,
) -> None:  # noqa: D401 - retained for external callers
    """Compatibility shim: alias of :func:`invalidate_arr_webui_rollups_cache`.

    Kept so existing call sites in :mod:`qBitrr.arss` continue to compile without renames.
    """
    invalidate_arr_webui_rollups_cache(arr)


def get_radarr_counts_total(arr: Arr) -> tuple[dict[str, int], int]:
    ensure_arr_webui_rollups(arr)
    r = getattr(arr, "_webui_catalog_rollups", None) or {}
    m = r.get("movies") or {}
    return (dict(m.get("counts") or _ZERO_COUNTS_RAD), int(m.get("total") or 0))


def get_sonarr_episode_instance_counts_total(arr: Arr) -> tuple[dict[str, int], int]:
    ensure_arr_webui_rollups(arr)
    r = getattr(arr, "_webui_catalog_rollups", None) or {}
    s = r.get("sonarr_episodes") or {}
    return (dict(s.get("counts") or _ZERO_COUNTS_EP3), int(s.get("total_series") or 0))


def get_lidarr_album_counts_total(arr: Arr) -> tuple[dict[str, int], int]:
    ensure_arr_webui_rollups(arr)
    r = getattr(arr, "_webui_catalog_rollups", None) or {}
    a = r.get("lidarr_albums") or {}
    return (dict(a.get("counts") or _ZERO_COUNTS_RAD), int(a.get("total") or 0))


def get_lidarr_track_counts_total(arr: Arr) -> tuple[dict[str, int], int]:
    ensure_arr_webui_rollups(arr)
    r = getattr(arr, "_webui_catalog_rollups", None) or {}
    t = r.get("lidarr_tracks") or {}
    return (dict(t.get("counts") or _ZERO_COUNTS_EP3), int(t.get("total") or 0))


def get_lidarr_album_and_track_rollups(arr: Arr) -> tuple[
    tuple[dict[str, int], int],
    tuple[dict[str, int], int],
]:
    """Return album + track rollup tuples after a single SQLite aggregation pass."""
    ensure_arr_webui_rollups(arr)
    r = getattr(arr, "_webui_catalog_rollups", None) or {}
    a = r.get("lidarr_albums") or {}
    t = r.get("lidarr_tracks") or {}
    return (
        (dict(a.get("counts") or _ZERO_COUNTS_RAD), int(a.get("total") or 0)),
        (dict(t.get("counts") or _ZERO_COUNTS_EP3), int(t.get("total") or 0)),
    )


def update_album_total_tracks(
    arr: Arr, album_entry_id: int, album_model: Any, track_model: Any
) -> Any | None:
    """Set AlbumFilesModel.TotalTracks from TrackFilesModel rows; return the album row."""
    db = getattr(arr, "db", None)
    if db is None:
        return None
    name = getattr(arr, "_name", "")
    with database_lock():
        with db.connection_context():
            n = (
                track_model.select()
                .where((track_model.AlbumId == album_entry_id) & (track_model.ArrInstance == name))
                .count()
            )
            album_model.update(TotalTracks=n).where(
                (album_model.EntryId == album_entry_id) & (album_model.ArrInstance == name)
            ).execute()
            return album_model.get_or_none(
                (album_model.EntryId == album_entry_id) & (album_model.ArrInstance == name)
            )


def update_series_season_episode_totals(
    arr: Arr, series_id: int, ep_model: Any, series_model: Any
) -> None:
    """Recompute SeriesFilesModel.SeasonCount and EpisodeTotalCount for one series."""
    db = getattr(arr, "db", None)
    if db is None:
        return
    name = getattr(arr, "_name", "")
    with database_lock():
        with db.connection_context():
            ep_q = ep_model.select().where(
                (ep_model.ArrInstance == name) & (ep_model.SeriesId == series_id)
            )
            ep_total = ep_q.count()
            season_count = (
                ep_model.select(ep_model.SeasonNumber)
                .where((ep_model.ArrInstance == name) & (ep_model.SeriesId == series_id))
                .distinct()
                .count()
            )
            series_model.update(SeasonCount=int(season_count), EpisodeTotalCount=ep_total).where(
                (series_model.EntryId == series_id) & (series_model.ArrInstance == name)
            ).execute()


def update_artist_album_track_totals(
    arr: Arr, artist_id: int, album_model: Any, track_model: Any, artist_model: Any
) -> None:
    """Recompute ArtistFilesModel.AlbumCount and TrackTotalCount."""
    db = getattr(arr, "db", None)
    if db is None:
        return
    name = getattr(arr, "_name", "")
    with database_lock():
        with db.connection_context():
            alb_n = (
                album_model.select()
                .where((album_model.ArtistId == artist_id) & (album_model.ArrInstance == name))
                .count()
            )
            tr_n = (
                track_model.select()
                .join(
                    album_model,
                    on=(track_model.AlbumId == album_model.EntryId),
                )
                .where(
                    (track_model.ArrInstance == name)
                    & (album_model.ArrInstance == name)
                    & (album_model.ArtistId == artist_id)
                )
                .count()
            )
            artist_model.update(AlbumCount=alb_n, TrackTotalCount=tr_n).where(
                (artist_model.EntryId == artist_id) & (artist_model.ArrInstance == name)
            ).execute()


def refresh_rollups_after_db_update(
    arr: Arr,
    db_entry: dict[str, Any] | None,
    *,
    series: bool,
    artist: bool,
) -> None:
    """Update denormalized columns; defer heavy WebUI rollup to flush_pending_arr_webui_rollups."""
    if not getattr(arr, "db", None) or not db_entry:
        return
    t = getattr(arr, "type", None)
    try:
        if t == "radarr":
            mark_arr_webui_rollups_stale(arr)
        elif t == "sonarr":
            ep = getattr(arr, "model_file", None)
            sm = getattr(arr, "series_file_model", None)
            if ep is not None and sm is not None:
                if series:
                    sid = int(db_entry.get("id") or 0)
                    if sid:
                        update_series_season_episode_totals(arr, sid, ep, sm)
                else:
                    sid = int(db_entry.get("seriesId") or db_entry.get("series_id") or 0)
                    if sid:
                        update_series_season_episode_totals(arr, sid, ep, sm)
            mark_arr_webui_rollups_stale(arr)
        elif t == "lidarr":
            am = getattr(arr, "model_file", None)
            tm = getattr(arr, "track_file_model", None)
            arm = getattr(arr, "artists_file_model", None)
            if artist and arm is not None:
                aid = int(db_entry.get("id") or 0)
                if aid and am is not None and tm is not None:
                    update_artist_album_track_totals(arr, aid, am, tm, arm)
            elif not artist and am is not None and tm is not None:
                aeid = int(db_entry.get("id") or 0)
                if aeid:
                    arow = update_album_total_tracks(arr, aeid, am, tm)
                    if arow and getattr(arow, "ArtistId", None) is not None and arm is not None:
                        update_artist_album_track_totals(arr, int(arow.ArtistId), am, tm, arm)
            mark_arr_webui_rollups_stale(arr)
    except Exception:
        arr.logger.debug("refresh_rollups_after_db_update failed", exc_info=True)
