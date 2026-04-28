"""Denormalized catalog counts and Arr WebUI rollup refresh (SQLite + in-memory caches)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from peewee import fn

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


def mark_arr_webui_rollups_stale(arr: Arr) -> None:
    """Mark in-memory rollup dict as needing a rebuild (cheap; heavy work runs in flush)."""
    if getattr(arr, "db", None) is None:
        return
    arr._webui_rollups_stale = True  # type: ignore[attr-defined]


def flush_pending_arr_webui_rollups(arr: Arr) -> None:
    """Recompute aggregates once after batched writes (single lock + COUNT pass)."""
    if getattr(arr, "db", None) is None:
        return
    if getattr(arr, "_webui_rollups_stale", False):
        refresh_arr_webui_rollups(arr)


def refresh_arr_webui_rollups(arr: Arr) -> None:
    """
    Refresh in-memory WebUI rollup dict for this Arr instance (radarr / sonarr / lidarr).
    Uses aggregate queries here (not inside Flask list handlers): call after DB mutations and
    optionally when WebUI first needs data before any sync has run.
    """
    db = getattr(arr, "db", None)
    if db is None:
        return
    name = getattr(arr, "_name", "")
    t = getattr(arr, "type", None)
    if t not in ("radarr", "sonarr", "lidarr"):
        arr._webui_catalog_rollups = {}
        arr._webui_rollups_stale = False  # type: ignore[attr-defined]
        return
    roll: dict[str, Any] = {}
    with database_lock():
        with db.connection_context():
            if t == "radarr":
                model = getattr(arr, "model_file", None)
                if model is None:
                    arr._webui_catalog_rollups = {}
                    arr._webui_rollups_stale = False  # type: ignore[attr-defined]
                    return
                base = model.select().where(model.ArrInstance == name)
                monitored_count = (
                    model.select(fn.COUNT(model.EntryId))
                    .where((model.ArrInstance == name) & (model.Monitored == True))  # noqa: E712
                    .scalar()
                    or 0
                )
                available_count = (
                    model.select(fn.COUNT(model.EntryId))
                    .where(
                        (model.ArrInstance == name)
                        & (model.Monitored == True)  # noqa: E712
                        & (model.MovieFileId.is_null(False))
                        & (model.MovieFileId != 0)
                    )
                    .scalar()
                    or 0
                )
                missing_count = max(monitored_count - available_count, 0)
                quality_met_count = (
                    model.select(fn.COUNT(model.EntryId))
                    .where((model.ArrInstance == name) & (model.QualityMet == True))  # noqa: E712
                    .scalar()
                    or 0
                )
                request_count = (
                    model.select(fn.COUNT(model.EntryId))
                    .where((model.ArrInstance == name) & (model.IsRequest == True))  # noqa: E712
                    .scalar()
                    or 0
                )
                total = base.count()
                roll["movies"] = {
                    "counts": {
                        "available": available_count,
                        "monitored": monitored_count,
                        "missing": missing_count,
                        "quality_met": quality_met_count,
                        "requests": request_count,
                    },
                    "total": total,
                }
            elif t == "sonarr":
                ep = getattr(arr, "model_file", None)
                if ep is None:
                    arr._webui_catalog_rollups = {}
                    arr._webui_rollups_stale = False  # type: ignore[attr-defined]
                    return
                monitored_count = (
                    ep.select(fn.COUNT(ep.EntryId))
                    .where((ep.ArrInstance == name) & (ep.Monitored == True))  # noqa: E712
                    .scalar()
                    or 0
                )
                available_count = (
                    ep.select(fn.COUNT(ep.EntryId))
                    .where(
                        (ep.ArrInstance == name)
                        & (ep.Monitored == True)  # noqa: E712
                        & (ep.EpisodeFileId.is_null(False))
                        & (ep.EpisodeFileId != 0)
                    )
                    .scalar()
                    or 0
                )
                missing_count = max(monitored_count - available_count, 0)
                sm = getattr(arr, "series_file_model", None)
                total_series = 0
                if sm is not None:
                    total_series = sm.select().where(sm.ArrInstance == name).count()
                roll["sonarr_episodes"] = {
                    "counts": {
                        "available": available_count,
                        "monitored": monitored_count,
                        "missing": missing_count,
                    },
                    "total_series": total_series,
                }
            elif t == "lidarr":
                album_m = getattr(arr, "model_file", None)
                track_m = getattr(arr, "track_file_model", None)
                if album_m is None:
                    arr._webui_catalog_rollups = {}
                    arr._webui_rollups_stale = False  # type: ignore[attr-defined]
                    return
                monitored_count = (
                    album_m.select(fn.COUNT(album_m.EntryId))
                    .where(
                        (album_m.ArrInstance == name) & (album_m.Monitored == True)
                    )  # noqa: E712
                    .scalar()
                    or 0
                )
                available_count = (
                    album_m.select(fn.COUNT(album_m.EntryId))
                    .where(
                        (album_m.ArrInstance == name)
                        & (album_m.Monitored == True)  # noqa: E712
                        & (album_m.AlbumFileId.is_null(False))
                        & (album_m.AlbumFileId != 0)
                    )
                    .scalar()
                    or 0
                )
                missing_count = max(monitored_count - available_count, 0)
                quality_met_count = (
                    album_m.select(fn.COUNT(album_m.EntryId))
                    .where(
                        (album_m.ArrInstance == name) & (album_m.QualityMet == True)
                    )  # noqa: E712
                    .scalar()
                    or 0
                )
                request_count = (
                    album_m.select(fn.COUNT(album_m.EntryId))
                    .where(
                        (album_m.ArrInstance == name) & (album_m.IsRequest == True)
                    )  # noqa: E712
                    .scalar()
                    or 0
                )
                total_albums = album_m.select().where(album_m.ArrInstance == name).count()
                roll["lidarr_albums"] = {
                    "counts": {
                        "available": available_count,
                        "monitored": monitored_count,
                        "missing": missing_count,
                        "quality_met": quality_met_count,
                        "requests": request_count,
                    },
                    "total": total_albums,
                }
                if track_m is not None:
                    qjoin = (
                        track_m.select()
                        .join(album_m, on=(track_m.AlbumId == album_m.EntryId))
                        .where((track_m.ArrInstance == name) & (album_m.ArrInstance == name))
                    )
                    available_t = (
                        track_m.select()
                        .join(album_m, on=(track_m.AlbumId == album_m.EntryId))
                        .where(
                            (track_m.ArrInstance == name)
                            & (album_m.ArrInstance == name)
                            & (track_m.HasFile == True)  # noqa: E712
                        )
                        .count()
                    )
                    monitored_t = (
                        track_m.select()
                        .join(album_m, on=(track_m.AlbumId == album_m.EntryId))
                        .where(
                            (track_m.ArrInstance == name)
                            & (album_m.ArrInstance == name)
                            & (track_m.Monitored == True)  # noqa: E712
                        )
                        .count()
                    )
                    missing_t = (
                        track_m.select()
                        .join(album_m, on=(track_m.AlbumId == album_m.EntryId))
                        .where(
                            (track_m.ArrInstance == name)
                            & (album_m.ArrInstance == name)
                            & (track_m.HasFile == False)  # noqa: E712
                        )
                        .count()
                    )
                    total_t = qjoin.count()
                    roll["lidarr_tracks"] = {
                        "counts": {
                            "available": available_t,
                            "monitored": monitored_t,
                            "missing": missing_t,
                        },
                        "total": total_t,
                    }
    arr._webui_catalog_rollups = roll  # type: ignore[attr-defined]
    arr._webui_rollups_stale = False  # type: ignore[attr-defined]


def ensure_arr_webui_rollups(arr: Arr) -> None:
    """Populate WebUI rollups if missing, stale, or empty while models are now available."""
    stale = getattr(arr, "_webui_rollups_stale", False)
    roll = getattr(arr, "_webui_catalog_rollups", None)
    if stale:
        refresh_arr_webui_rollups(arr)
        return
    if roll is None:
        refresh_arr_webui_rollups(arr)
        return
    if roll == {} and getattr(arr, "model_file", None) is not None:
        refresh_arr_webui_rollups(arr)


def get_radarr_counts_total(arr: Arr) -> tuple[dict[str, int], int]:
    ensure_arr_webui_rollups(arr)
    r = getattr(arr, "_webui_catalog_rollups", None) or {}
    m = r.get("movies") or {}
    return (m.get("counts") or dict(_ZERO_COUNTS_RAD), int(m.get("total") or 0))


def get_sonarr_episode_instance_counts_total(arr: Arr) -> tuple[dict[str, int], int]:
    ensure_arr_webui_rollups(arr)
    r = getattr(arr, "_webui_catalog_rollups", None) or {}
    s = r.get("sonarr_episodes") or {}
    return (s.get("counts") or dict(_ZERO_COUNTS_EP3), int(s.get("total_series") or 0))


def get_lidarr_album_counts_total(arr: Arr) -> tuple[dict[str, int], int]:
    ensure_arr_webui_rollups(arr)
    r = getattr(arr, "_webui_catalog_rollups", None) or {}
    a = r.get("lidarr_albums") or {}
    counts = a.get("counts") or dict(_ZERO_COUNTS_RAD)
    return (counts, int(a.get("total") or 0))


def get_lidarr_track_counts_total(arr: Arr) -> tuple[dict[str, int], int]:
    ensure_arr_webui_rollups(arr)
    r = getattr(arr, "_webui_catalog_rollups", None) or {}
    t = r.get("lidarr_tracks") or {}
    return (t.get("counts") or dict(_ZERO_COUNTS_EP3), int(t.get("total") or 0))


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
