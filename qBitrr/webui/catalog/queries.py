from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from peewee import SQL, fn

from qBitrr.catalog_rollups import (
    _sum_case_int,
    get_lidarr_album_and_track_rollups,
    get_lidarr_track_counts_total,
    get_radarr_counts_total,
    get_readarr_book_counts_total,
    get_sonarr_series_counts_total,
)
from qBitrr.db_lock import database_lock
from qBitrr.utils import coerce_bool
from qBitrr.webui.catalog.common import empty_catalog_payload


class Catalog:
    def _safe_str(value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    def _ensure_arr_db(self, arr) -> bool:
        """Ensure catalog models/DB are ready for read-only browse; do not run full Arr API sync here.

        Bulk ``db_update()`` runs in the Arr manager search loop (and related paths), not on HTTP requests.
        """
        if not getattr(arr, "search_setup_completed", False):
            try:
                arr.register_search_mode()
            except Exception:
                self.logger.debug(
                    "register_search_mode failed for %s", getattr(arr, "_name", arr), exc_info=True
                )
                return False
        if not getattr(arr, "search_setup_completed", False):
            return False
        return True

    def _radarr_movies_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        year_min: int | None = None,
        year_max: int | None = None,
        monitored: bool | None = None,
        has_file: bool | None = None,
        quality_met: bool | None = None,
        is_request: bool | None = None,
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return empty_catalog_payload("radarr", page=page, page_size=page_size)
        model = getattr(arr, "model_file", None)
        db = getattr(arr, "db", None)
        if model is None or db is None:
            return empty_catalog_payload("radarr", page=page, page_size=page_size)
        page = max(page, 0)
        page_size = max(page_size, 1)
        arr_instance = getattr(arr, "_name", "")
        # Standardised order across all ``*_from_db`` helpers (M-2):
        #   1. Compute rollups (refresh from SQLite under its own short lock).
        #   2. Acquire database_lock for the page-read.
        #   3. Drain rows under the lock.
        #   4. Release lock; build payload from snapshots.
        rollup_counts, total = get_radarr_counts_total(arr)

        page_rows: list[Any] = []
        has_quality_profile_id = hasattr(model, "QualityProfileId")
        has_quality_profile_name = hasattr(model, "QualityProfileName")

        with database_lock():
            with db.connection_context():
                base_query = model.select().where(model.ArrInstance == arr_instance)

                # Build filtered query
                query = base_query
                if search:
                    query = query.where(model.Title.contains(search))
                if year_min is not None:
                    query = query.where(model.Year >= year_min)
                if year_max is not None:
                    query = query.where(model.Year <= year_max)
                if monitored is not None:
                    query = query.where(model.Monitored == monitored)
                if has_file is not None:
                    if has_file:
                        query = query.where(
                            (model.MovieFileId.is_null(False)) & (model.MovieFileId != 0)
                        )
                    else:
                        query = query.where(
                            (model.MovieFileId.is_null(True)) | (model.MovieFileId == 0)
                        )
                if quality_met is not None:
                    query = query.where(model.QualityMet == quality_met)
                if is_request is not None:
                    query = query.where(model.IsRequest == is_request)

                # Drain into a list so the lock is released before we serialise the payload.
                page_rows = list(query.order_by(model.Title.asc()).paginate(page + 1, page_size))

        # Lock released — build the per-row payloads now (B-3).
        movies = []
        for movie in page_rows:
            quality_profile_id = (
                getattr(movie, "QualityProfileId", None) if has_quality_profile_id else None
            )
            quality_profile_name = (
                getattr(movie, "QualityProfileName", None) if has_quality_profile_name else None
            )

            movies.append(
                {
                    "id": movie.EntryId,
                    "title": movie.Title or "",
                    "year": movie.Year,
                    "monitored": coerce_bool(movie.Monitored),
                    "hasFile": coerce_bool(movie.MovieFileId),
                    "qualityMet": coerce_bool(movie.QualityMet),
                    "isRequest": coerce_bool(movie.IsRequest),
                    "upgrade": coerce_bool(movie.Upgrade),
                    "customFormatScore": movie.CustomFormatScore,
                    "minCustomFormatScore": movie.MinCustomFormatScore,
                    "customFormatMet": coerce_bool(movie.CustomFormatMet),
                    "reason": movie.Reason,
                    "qualityProfileId": quality_profile_id,
                    "qualityProfileName": quality_profile_name,
                }
            )
        return {
            "counts": dict(rollup_counts),
            "total": total,
            "page": page,
            "page_size": page_size,
            "movies": movies,
        }

    @staticmethod
    def _lidarr_track_row_reason(
        *,
        track_monitored: bool,
        track_has_file: bool,
        album_reason: Any,
    ) -> str:
        """Derive a per-track search reason for the WebUI (SQLite tracks have no Reason column)."""
        ar = str(album_reason).strip() if album_reason is not None else ""
        if not track_monitored:
            return "Unmonitored"
        if not track_has_file:
            return "Missing"
        if ar and ar != "Missing":
            return ar
        return "Not being searched"

    def _lidarr_album_row_payload(
        self,
        arr,
        album: Any,
        prefetched_tracks: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Build one ``{album, totals, tracks}`` entry from an AlbumFiles row.

        When ``prefetched_tracks`` is supplied the helper does not issue any extra DB query
        (used by :meth:`_lidarr_artist_detail_from_db` to avoid N+1). When ``None`` we fall
        back to the per-album lookup for callers that have not adopted the JOIN-bucket flow.
        """
        track_model = getattr(arr, "track_file_model", None)
        tracks_list: list[dict[str, Any]] = []
        track_monitored_count = 0
        track_available_count = 0

        track_iterable: list[Any] = []
        if prefetched_tracks is not None:
            track_iterable = prefetched_tracks
        elif track_model:
            try:
                track_iterable = list(
                    track_model.select()
                    .where(track_model.AlbumId == album.EntryId)
                    .order_by(track_model.TrackNumber)
                )
            except Exception as e:
                self.logger.warning(
                    "Failed to fetch tracks for album %s (%s): %s",
                    album.EntryId,
                    album.Title,
                    e,
                )
                track_iterable = []

        album_reason_raw = getattr(album, "Reason", None)

        for track in track_iterable:
            is_monitored = coerce_bool(getattr(track, "Monitored", False))
            has_file = coerce_bool(getattr(track, "HasFile", False))

            if is_monitored:
                track_monitored_count += 1
            if has_file:
                track_available_count += 1

            track_reason = self._lidarr_track_row_reason(
                track_monitored=is_monitored,
                track_has_file=has_file,
                album_reason=album_reason_raw,
            )

            tracks_list.append(
                {
                    "id": getattr(track, "EntryId", None),
                    "trackNumber": getattr(track, "TrackNumber", None),
                    "title": getattr(track, "Title", None),
                    "duration": getattr(track, "Duration", None),
                    "hasFile": has_file,
                    "trackFileId": getattr(track, "TrackFileId", None),
                    "monitored": is_monitored,
                    "reason": track_reason,
                }
            )

        track_missing_count = max(track_monitored_count - track_available_count, 0)

        quality_profile_id = getattr(album, "QualityProfileId", None)
        quality_profile_name = getattr(album, "QualityProfileName", None)

        return {
            "album": {
                "id": album.EntryId,
                "title": album.Title,
                "artistId": album.ArtistId,
                "artistName": album.ArtistTitle,
                "monitored": coerce_bool(album.Monitored),
                "hasFile": bool(album.AlbumFileId and album.AlbumFileId != 0),
                "foreignAlbumId": album.ForeignAlbumId,
                "releaseDate": (
                    album.ReleaseDate.isoformat()
                    if album.ReleaseDate and hasattr(album.ReleaseDate, "isoformat")
                    else (album.ReleaseDate if isinstance(album.ReleaseDate, str) else None)
                ),
                "qualityMet": coerce_bool(album.QualityMet),
                "isRequest": coerce_bool(album.IsRequest),
                "upgrade": coerce_bool(album.Upgrade),
                "customFormatScore": album.CustomFormatScore,
                "minCustomFormatScore": album.MinCustomFormatScore,
                "customFormatMet": coerce_bool(album.CustomFormatMet),
                "reason": album.Reason,
                "qualityProfileId": quality_profile_id,
                "qualityProfileName": quality_profile_name,
            },
            "totals": {
                "available": track_available_count,
                "monitored": track_monitored_count,
                "missing": track_missing_count,
            },
            "tracks": tracks_list,
        }

    @staticmethod
    def _lidarr_instance_keys(arr: Any) -> list[str]:
        """Return distinct non-empty ``ArrInstance`` keys to query for one Lidarr ``Arr``.

        Workers stamp ``ArtistFilesModel.ArrInstance`` with ``Arr._name``, but older or
        manually repaired databases may still carry ``Arr.category``. Matching only
        ``_name`` yields an empty browse with non-zero rollups.
        """
        name = (getattr(arr, "_name", None) or "").strip()
        cat = (getattr(arr, "category", None) or "").strip()
        keys: list[str] = []
        for k in (name, cat):
            if k and k not in keys:
                keys.append(k)
        if not keys:
            keys = [name] if name else [""]
        return keys

    @staticmethod
    def _lidarr_artist_browse_progress_maps(
        album_m: Any,
        track_m: Any,
        arr_instance_keys: list[str],
        artist_ids: list[int],
    ) -> tuple[dict[int, tuple[int, int]], dict[int, tuple[int, int]]]:
        """Return per-artist (monitored, on-disk) counts for albums and tracks.

        Album "available" matches catalog rules: monitored row with non-zero ``AlbumFileId``.
        Track "available": monitored with ``HasFile`` true.
        """
        alb_out: dict[int, tuple[int, int]] = {}
        trk_out: dict[int, tuple[int, int]] = {}
        if not artist_ids or not arr_instance_keys:
            return alb_out, trk_out

        artist_id_col = album_m.ArtistId.alias("artist_id")
        mon_alb = album_m.Monitored == True  # noqa: E712
        alb_file = (album_m.AlbumFileId.is_null(False)) & (album_m.AlbumFileId != 0)
        aq = (
            album_m.select(
                artist_id_col,
                _sum_case_int(mon_alb, "mon_n"),
                _sum_case_int(mon_alb & alb_file, "avail_n"),
            )
            .where(
                (album_m.ArrInstance.in_(arr_instance_keys)) & (album_m.ArtistId.in_(artist_ids))
            )
            .group_by(artist_id_col)
        )
        for row in aq.dicts():
            raw_aid = row.get("artist_id")
            if raw_aid is None:
                continue
            aid = int(raw_aid)
            alb_out[aid] = (int(row.get("mon_n") or 0), int(row.get("avail_n") or 0))

        if track_m is not None:
            mon_tr = track_m.Monitored == True  # noqa: E712
            tr_ok = track_m.HasFile == True  # noqa: E712
            tq = (
                track_m.select(
                    artist_id_col,
                    _sum_case_int(mon_tr, "mon_n"),
                    _sum_case_int(mon_tr & tr_ok, "avail_n"),
                )
                .join(album_m, on=(track_m.AlbumId == album_m.EntryId))
                .where(
                    (track_m.ArrInstance.in_(arr_instance_keys))
                    & (album_m.ArrInstance.in_(arr_instance_keys))
                    & (album_m.ArtistId.in_(artist_ids))
                )
                .group_by(artist_id_col)
            )
            # Joined aggregate is rooted at ``track_m``; model rows omit ``artist_id`` alias.
            for row in tq.dicts():
                raw_aid = row.get("artist_id")
                if raw_aid is None:
                    continue
                aid = int(raw_aid)
                trk_out[aid] = (int(row.get("mon_n") or 0), int(row.get("avail_n") or 0))

        return alb_out, trk_out

    def _lidarr_artists_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        monitored: bool | None = None,
        missing_only: bool = False,
        reason_filter: str | None = None,
    ) -> dict[str, Any]:
        empty = {
            "counts": {
                "available": 0,
                "monitored": 0,
                "missing": 0,
                "quality_met": 0,
                "requests": 0,
            },
            "counts_tracks": {"available": 0, "monitored": 0, "missing": 0},
            "total": 0,
            "page": max(page, 0),
            "page_size": max(page_size, 1),
            "artists": [],
        }

        if not self._ensure_arr_db(arr):
            return empty
        arm = getattr(arr, "artists_file_model", None)
        db = getattr(arr, "db", None)
        if arm is None or db is None:
            return empty

        page = max(page, 0)
        page_size = max(page_size, 1)
        arr_keys = self._lidarr_instance_keys(arr)

        (rollup_album_counts, album_total_inst), (rollup_track_counts, _) = (
            get_lidarr_album_and_track_rollups(arr)
        )

        slice_rows: list[Any] = []
        total = 0
        alb_maps: dict[int, tuple[int, int]] = {}
        trk_maps: dict[int, tuple[int, int]] = {}

        # Build the optional album-row predicate that maps Status / Search Reason filters to
        # the underlying ``AlbumFilesModel`` rows. ``Not being searched`` matches NULL too,
        # since older album rows may have left ``Reason`` unset.
        def _album_filter_extra(album_m: Any) -> Any | None:
            cond: Any | None = None
            if missing_only and album_m is not None:
                miss = (album_m.Monitored == True) & (  # noqa: E712
                    album_m.AlbumFileId.is_null() | (album_m.AlbumFileId == 0)
                )
                cond = miss if cond is None else cond & miss
            if reason_filter and album_m is not None:
                if reason_filter == "Not being searched":
                    rcond = (album_m.Reason == "Not being searched") | album_m.Reason.is_null()
                else:
                    rcond = album_m.Reason == reason_filter
                cond = rcond if cond is None else cond & rcond
            return cond

        with database_lock():
            with db.connection_context():
                album_m = getattr(arr, "model_file", None)
                track_m = getattr(arr, "track_file_model", None)

                album_filter_extra = _album_filter_extra(album_m)

                base = arm.select().where(arm.ArrInstance.in_(arr_keys))
                q_art = base
                if search:
                    q_art = q_art.where(arm.Title.contains(search))
                if monitored is not None:
                    q_art = q_art.where(arm.Monitored == monitored)
                if album_filter_extra is not None and album_m is not None:
                    artist_ids_subq = album_m.select(album_m.ArtistId).where(
                        album_m.ArrInstance.in_(arr_keys) & album_filter_extra
                    )
                    q_art = q_art.where(arm.EntryId.in_(artist_ids_subq))

                total = int(q_art.count() or 0)
                slice_rows = list(q_art.order_by(arm.Title.asc()).paginate(page + 1, page_size))

                # Album rows can be populated while ArtistFilesModel has no rows (e.g. artist
                # ingest skipped or legacy DB). Rollups then show album totals but browse was empty.
                if total == 0 and int(album_total_inst or 0) > 0 and album_m is not None:
                    conds: list[Any] = [album_m.ArrInstance.in_(arr_keys)]
                    if search:
                        conds.append(album_m.ArtistTitle.contains(search))
                    if album_filter_extra is not None:
                        conds.append(album_filter_extra)
                    grouped_artists = (
                        album_m.select(
                            album_m.ArtistId,
                            fn.MIN(album_m.ArtistTitle).alias("disp_title"),
                            fn.MAX(album_m.Monitored).alias("mx_mon"),
                        )
                        .where(*conds)
                        .group_by(album_m.ArtistId)
                    )
                    if monitored is True:
                        grouped_artists = grouped_artists.having(
                            fn.MAX(album_m.Monitored) == True  # noqa: E712
                        )
                    elif monitored is False:
                        grouped_artists = grouped_artists.having(
                            fn.MAX(album_m.Monitored) == False  # noqa: E712
                        )
                    count_wrap = grouped_artists.alias("lidarr_artists_fb")
                    total = int(album_m.select(fn.COUNT(SQL("*"))).from_(count_wrap).scalar() or 0)
                    slice_rows = []
                    for row in grouped_artists.order_by(
                        fn.MIN(album_m.ArtistTitle).asc(),
                        album_m.ArtistId.asc(),
                    ).paginate(page + 1, page_size):
                        aid = int(row.ArtistId)
                        ar_rec = arm.get_or_none(
                            (arm.EntryId == aid) & (arm.ArrInstance.in_(arr_keys))
                        )
                        if ar_rec is not None:
                            slice_rows.append(ar_rec)
                        else:
                            disp = getattr(row, "disp_title", None) or ""
                            mx = getattr(row, "mx_mon", None)
                            slice_rows.append(
                                SimpleNamespace(
                                    EntryId=aid,
                                    Title=disp,
                                    Monitored=mx,
                                    AlbumCount=0,
                                    TrackTotalCount=0,
                                    QualityProfileName=None,
                                    Searched=False,
                                )
                            )

                ids = [int(ar.EntryId) for ar in slice_rows]
                alb_maps, trk_maps = {}, {}
                if ids and album_m is not None:
                    alb_maps, trk_maps = Catalog._lidarr_artist_browse_progress_maps(
                        album_m, track_m, arr_keys, ids
                    )

        artists_out: list[dict[str, Any]] = []
        for ar in slice_rows:
            aid = int(ar.EntryId)
            am, aa = alb_maps.get(aid, (0, 0))
            tm, ta = trk_maps.get(aid, (0, 0))
            miss_a = max(am - aa, 0)
            miss_t = max(tm - ta, 0)
            artists_out.append(
                {
                    "artist": {
                        "id": ar.EntryId,
                        "name": ar.Title or "",
                        "monitored": coerce_bool(ar.Monitored),
                        "albumCount": int(getattr(ar, "AlbumCount", None) or 0),
                        "trackTotalCount": int(getattr(ar, "TrackTotalCount", None) or 0),
                        "qualityProfileName": getattr(ar, "QualityProfileName", None),
                        "searched": coerce_bool(ar.Searched),
                        "albumsMonitored": am,
                        "albumsAvailable": aa,
                        "albumsMissing": miss_a,
                        "tracksMonitored": tm,
                        "tracksAvailable": ta,
                        "tracksMissing": miss_t,
                    }
                }
            )

        return {
            "counts": dict(rollup_album_counts),
            "counts_tracks": dict(rollup_track_counts),
            "album_total": int(album_total_inst),
            "total": total,
            "page": page,
            "page_size": page_size,
            "artists": artists_out,
        }

    def _lidarr_artist_detail_from_db(self, arr, artist_id: int) -> dict[str, Any] | None:
        """Return a single artist with all albums and tracks in one DB visit.

        Lock scope is intentionally narrow: the SQLite ``database_lock`` only spans the read
        queries (B-3); rollups are gathered before the lock (M-2) and Python payload
        construction happens after release. Track lookup is a single JOIN query (H-2) bucketed
        per album in Python — replaces the prior N+1 ``select per album`` pattern.
        """
        arm = getattr(arr, "artists_file_model", None)
        album_m = getattr(arr, "model_file", None)
        track_m = getattr(arr, "track_file_model", None)
        db = getattr(arr, "db", None)

        if not self._ensure_arr_db(arr) or arm is None or album_m is None or db is None:
            return None

        arr_keys = self._lidarr_instance_keys(arr)

        # Compute rollups before acquiring the DB lock. Standardised ordering across all
        # ``*_from_db`` helpers (M-2): rollup -> lock -> read -> release -> build payload.
        (rollup_album_counts, _), (rollup_track_counts, _) = get_lidarr_album_and_track_rollups(
            arr
        )

        artist_row = None
        album_rows: list[Any] = []
        tracks_by_album: dict[int, list[Any]] = {}

        with database_lock():
            with db.connection_context():
                artist_row = arm.get_or_none(
                    (arm.EntryId == artist_id) & (arm.ArrInstance.in_(arr_keys))
                )
                if artist_row is None:
                    return None

                aq = album_m.select().where(
                    (album_m.ArtistId == artist_id) & (album_m.ArrInstance.in_(arr_keys))
                )
                try:
                    aq = aq.order_by(album_m.ReleaseDate, album_m.Title)
                except Exception:
                    aq = aq.order_by(album_m.Title)
                album_rows = list(aq)

                if track_m is not None and album_rows:
                    # Single JOIN: tracks for every album of this artist in one round-trip.
                    track_query = (
                        track_m.select(
                            track_m,
                            album_m.EntryId.alias("AlbumEntryId"),
                        )
                        .join(album_m, on=(track_m.AlbumId == album_m.EntryId))
                        .where(
                            (track_m.ArrInstance.in_(arr_keys))
                            & (album_m.ArrInstance.in_(arr_keys))
                            & (album_m.ArtistId == artist_id)
                        )
                        .order_by(album_m.EntryId, track_m.TrackNumber)
                    )
                    for trow in track_query:
                        album_id_for_track = int(getattr(trow, "AlbumId", 0) or 0)
                        tracks_by_album.setdefault(album_id_for_track, []).append(trow)

        # Lock released — build the response payload from the snapshots we just collected.
        album_items = [
            self._lidarr_album_row_payload(
                arr, al, prefetched_tracks=tracks_by_album.get(al.EntryId)
            )
            for al in album_rows
        ]

        artist_payload = {
            "id": artist_row.EntryId,
            "name": artist_row.Title or "",
            "monitored": coerce_bool(artist_row.Monitored),
            "albumCount": int(getattr(artist_row, "AlbumCount", None) or 0),
            "trackTotalCount": int(getattr(artist_row, "TrackTotalCount", None) or 0),
            "qualityProfileName": getattr(artist_row, "QualityProfileName", None),
            "searched": coerce_bool(artist_row.Searched),
        }

        return {
            "counts": dict(rollup_album_counts),
            "counts_tracks": dict(rollup_track_counts),
            "artist": artist_payload,
            "albums": album_items,
        }

    def _lidarr_albums_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        monitored: bool | None = None,
        has_file: bool | None = None,
        quality_met: bool | None = None,
        is_request: bool | None = None,
        group_by_artist: bool = True,
    ) -> dict[str, Any]:
        empty_albums_payload = empty_catalog_payload(
            "lidarr_albums", page=page, page_size=page_size
        )
        if not self._ensure_arr_db(arr):
            return dict(empty_albums_payload)
        model = getattr(arr, "model_file", None)
        db = getattr(arr, "db", None)
        if model is None or db is None:
            return dict(empty_albums_payload)
        page = max(page, 0)
        page_size = max(page_size, 1)
        arr_instance = getattr(arr, "_name", "")

        # M-2: rollups (which take their own short lock) before the page-read lock.
        # Aggregate album+track rollups together so the "Tracks" header matches the artist
        # list shape; one SQLite refresh services both rollup readers.
        (rollup_counts, album_total_inst), (rollup_track_counts, _) = (
            get_lidarr_album_and_track_rollups(arr)
        )

        album_results: list[Any] = []
        track_m = getattr(arr, "track_file_model", None)
        tracks_by_album: dict[int, list[Any]] = {}
        total = int(album_total_inst or 0)

        with database_lock():
            with db.connection_context():
                base_query = model.select().where(model.ArrInstance == arr_instance)

                # Build filtered query
                query = base_query
                if search:
                    query = query.where(model.Title.contains(search))
                if monitored is not None:
                    query = query.where(model.Monitored == monitored)
                if has_file is not None:
                    if has_file:
                        query = query.where(
                            (model.AlbumFileId.is_null(False)) & (model.AlbumFileId != 0)
                        )
                    else:
                        query = query.where(
                            (model.AlbumFileId.is_null(True)) | (model.AlbumFileId == 0)
                        )
                if quality_met is not None:
                    query = query.where(model.QualityMet == quality_met)
                if is_request is not None:
                    query = query.where(model.IsRequest == is_request)

                # ``total`` for pagination must match the unit we paginate by. Grouped
                # mode pages by distinct artists; flat mode pages by albums. Using the
                # album rollup count while grouping by artist made clients plan hundreds
                # of mostly-empty pages (spinner hung for minutes on large libraries).
                if group_by_artist:
                    # Paginate by artists: Two-pass approach with Peewee
                    # First, get all distinct artist names from the filtered query
                    # Use a subquery to get distinct artists efficiently
                    artists_subquery = (
                        query.select(model.ArtistTitle).distinct().order_by(model.ArtistTitle)
                    )

                    all_artists = [row.ArtistTitle for row in artists_subquery]
                    total = len(all_artists)

                    start_idx = page * page_size
                    end_idx = start_idx + page_size
                    paginated_artists = all_artists[start_idx:end_idx]

                    if paginated_artists:
                        album_results = list(
                            query.where(model.ArtistTitle.in_(paginated_artists)).order_by(
                                model.ArtistTitle, model.ReleaseDate
                            )
                        )
                else:
                    # Flat mode: paginate by albums.
                    total = int(query.count() or 0)
                    album_results = list(query.order_by(model.Title).paginate(page + 1, page_size))

                # Single JOIN of tracks for the page rather than N+1 per-album lookups (H-2).
                if track_m is not None and album_results:
                    album_ids = [int(getattr(a, "EntryId", 0) or 0) for a in album_results]
                    track_query = (
                        track_m.select()
                        .where(
                            (track_m.ArrInstance == arr_instance)
                            & (track_m.AlbumId.in_(album_ids))
                        )
                        .order_by(track_m.AlbumId, track_m.TrackNumber)
                    )
                    for trow in track_query:
                        bucket = tracks_by_album.setdefault(int(trow.AlbumId or 0), [])
                        bucket.append(trow)

        # Lock released — build payloads outside (B-3).
        albums = [
            self._lidarr_album_row_payload(
                arr, album, prefetched_tracks=tracks_by_album.get(int(album.EntryId or 0))
            )
            for album in album_results
        ]
        return {
            "counts": dict(rollup_counts),
            "counts_tracks": dict(rollup_track_counts),
            "album_total": int(album_total_inst),
            "total": total,
            "page": page,
            "page_size": page_size,
            "albums": albums,
        }

    def _lidarr_tracks_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        monitored: bool | None = None,
        has_file: bool | None = None,
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                },
                "total": 0,
                "page": page,
                "page_size": page_size,
                "tracks": [],
            }

        track_model = getattr(arr, "track_file_model", None)
        album_model = getattr(arr, "model_file", None)
        db = getattr(arr, "db", None)

        if not track_model or not album_model or db is None:
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                },
                "total": 0,
                "page": page,
                "page_size": page_size,
                "tracks": [],
            }

        arr_instance = getattr(arr, "_name", "")

        rollup_tracks, _inst_track_total = get_lidarr_track_counts_total(arr)

        try:
            track_rows: list[Any] = []
            total = 0
            with database_lock():
                with db.connection_context():
                    query = (
                        track_model.select(
                            track_model,
                            album_model.Title.alias("AlbumTitle"),
                            album_model.ArtistTitle,
                            album_model.ArtistId,
                        )
                        .join(album_model, on=(track_model.AlbumId == album_model.EntryId))
                        .where(
                            (track_model.ArrInstance == arr_instance)
                            & (album_model.ArrInstance == arr_instance)
                        )
                    )

                    if monitored is not None:
                        query = query.where(track_model.Monitored == monitored)
                    if has_file is not None:
                        query = query.where(track_model.HasFile == has_file)
                    if search:
                        query = query.where(
                            (track_model.Title.contains(search))
                            | (album_model.Title.contains(search))
                            | (album_model.ArtistTitle.contains(search))
                        )

                    total = query.count()
                    track_rows = list(
                        query.order_by(
                            album_model.ArtistTitle,
                            album_model.Title,
                            track_model.TrackNumber,
                        ).paginate(page + 1, page_size)
                    )

            # Lock released — build payload outside (B-3).
            tracks = [
                {
                    "id": track.EntryId,
                    "trackNumber": track.TrackNumber,
                    "title": track.Title,
                    "duration": track.Duration,
                    "hasFile": track.HasFile,
                    "trackFileId": track.TrackFileId,
                    "monitored": track.Monitored,
                    "albumId": track.AlbumId,
                    "albumTitle": track.AlbumTitle,
                    "artistTitle": track.ArtistTitle,
                    "artistId": track.ArtistId,
                }
                for track in track_rows
            ]

            return {
                "counts": dict(rollup_tracks),
                "total": total,
                "page": page,
                "page_size": page_size,
                "tracks": tracks,
            }
        except Exception as e:
            self.logger.error("Error fetching Lidarr tracks: %s", e)
            return {
                "counts": {"available": 0, "monitored": 0, "missing": 0},
                "total": 0,
                "page": page,
                "page_size": page_size,
                "tracks": [],
            }

    @staticmethod
    def _readarr_instance_keys(arr: Any) -> list[str]:
        """Return distinct non-empty ``ArrInstance`` keys to query for one Readarr ``Arr``."""
        return Catalog._lidarr_instance_keys(arr)

    @staticmethod
    def _readarr_author_browse_progress_maps(
        book_m: Any,
        arr_instance_keys: list[str],
        author_ids: list[int],
    ) -> dict[int, tuple[int, int]]:
        """Return per-author (monitored, on-disk) book counts.

        Book "available" matches catalog rules: monitored row with non-zero ``BookFileId``.
        """
        out: dict[int, tuple[int, int]] = {}
        if not author_ids or not arr_instance_keys or book_m is None:
            return out

        author_id_col = book_m.AuthorId.alias("author_id")
        mon_book = book_m.Monitored == True  # noqa: E712
        book_file = (book_m.BookFileId.is_null(False)) & (book_m.BookFileId != 0)
        bq = (
            book_m.select(
                author_id_col,
                _sum_case_int(mon_book, "mon_n"),
                _sum_case_int(mon_book & book_file, "avail_n"),
            )
            .where((book_m.ArrInstance.in_(arr_instance_keys)) & (book_m.AuthorId.in_(author_ids)))
            .group_by(author_id_col)
        )
        for row in bq.dicts():
            raw_aid = row.get("author_id")
            if raw_aid is None:
                continue
            aid = int(raw_aid)
            out[aid] = (int(row.get("mon_n") or 0), int(row.get("avail_n") or 0))
        return out

    def _readarr_book_row_payload(self, book: Any) -> dict[str, Any]:
        """Build one ``{book}`` entry from a ``BookFilesModel`` row."""
        quality_profile_id = getattr(book, "QualityProfileId", None)
        quality_profile_name = getattr(book, "QualityProfileName", None)
        return {
            "book": {
                "id": book.EntryId,
                "title": book.Title,
                "authorId": book.AuthorId,
                "authorName": book.AuthorTitle,
                "monitored": coerce_bool(book.Monitored),
                "hasFile": bool(book.BookFileId and book.BookFileId != 0),
                "foreignBookId": book.ForeignBookId,
                "releaseDate": (
                    book.ReleaseDate.isoformat()
                    if book.ReleaseDate and hasattr(book.ReleaseDate, "isoformat")
                    else (book.ReleaseDate if isinstance(book.ReleaseDate, str) else None)
                ),
                "qualityMet": coerce_bool(book.QualityMet),
                "isRequest": coerce_bool(book.IsRequest),
                "upgrade": coerce_bool(book.Upgrade),
                "customFormatScore": book.CustomFormatScore,
                "minCustomFormatScore": book.MinCustomFormatScore,
                "customFormatMet": coerce_bool(book.CustomFormatMet),
                "reason": book.Reason,
                "qualityProfileId": quality_profile_id,
                "qualityProfileName": quality_profile_name,
            }
        }

    def _readarr_authors_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        monitored: bool | None = None,
        missing_only: bool = False,
        reason_filter: str | None = None,
    ) -> dict[str, Any]:
        empty = empty_catalog_payload("readarr_authors", page=page, page_size=page_size)

        if not self._ensure_arr_db(arr):
            return empty
        arm = getattr(arr, "artists_file_model", None)
        db = getattr(arr, "db", None)
        if arm is None or db is None:
            return empty

        page = max(page, 0)
        page_size = max(page_size, 1)
        arr_keys = self._readarr_instance_keys(arr)

        rollup_book_counts, book_total_inst = get_readarr_book_counts_total(arr)

        slice_rows: list[Any] = []
        total = 0
        book_maps: dict[int, tuple[int, int]] = {}

        def _book_filter_extra(book_m: Any) -> Any | None:
            cond: Any | None = None
            if missing_only and book_m is not None:
                miss = (book_m.Monitored == True) & (  # noqa: E712
                    book_m.BookFileId.is_null() | (book_m.BookFileId == 0)
                )
                cond = miss if cond is None else cond & miss
            if reason_filter and book_m is not None:
                if reason_filter == "Not being searched":
                    rcond = (book_m.Reason == "Not being searched") | book_m.Reason.is_null()
                else:
                    rcond = book_m.Reason == reason_filter
                cond = rcond if cond is None else cond & rcond
            return cond

        with database_lock():
            with db.connection_context():
                book_m = getattr(arr, "model_file", None)
                book_filter_extra = _book_filter_extra(book_m)

                base = arm.select().where(arm.ArrInstance.in_(arr_keys))
                q_auth = base
                if search:
                    q_auth = q_auth.where(arm.Title.contains(search))
                if monitored is not None:
                    q_auth = q_auth.where(arm.Monitored == monitored)
                if book_filter_extra is not None and book_m is not None:
                    author_ids_subq = book_m.select(book_m.AuthorId).where(
                        book_m.ArrInstance.in_(arr_keys) & book_filter_extra
                    )
                    q_auth = q_auth.where(arm.EntryId.in_(author_ids_subq))

                total = int(q_auth.count() or 0)
                slice_rows = list(q_auth.order_by(arm.Title.asc()).paginate(page + 1, page_size))

                # Book rows can be populated while AuthorFilesModel has no rows.
                if total == 0 and int(book_total_inst or 0) > 0 and book_m is not None:
                    conds: list[Any] = [book_m.ArrInstance.in_(arr_keys)]
                    if search:
                        conds.append(book_m.AuthorTitle.contains(search))
                    if book_filter_extra is not None:
                        conds.append(book_filter_extra)
                    grouped_authors = (
                        book_m.select(
                            book_m.AuthorId,
                            fn.MIN(book_m.AuthorTitle).alias("disp_title"),
                            fn.MAX(book_m.Monitored).alias("mx_mon"),
                        )
                        .where(*conds)
                        .group_by(book_m.AuthorId)
                    )
                    if monitored is True:
                        grouped_authors = grouped_authors.having(
                            fn.MAX(book_m.Monitored) == True  # noqa: E712
                        )
                    elif monitored is False:
                        grouped_authors = grouped_authors.having(
                            fn.MAX(book_m.Monitored) == False  # noqa: E712
                        )
                    count_wrap = grouped_authors.alias("readarr_authors_fb")
                    total = int(book_m.select(fn.COUNT(SQL("*"))).from_(count_wrap).scalar() or 0)
                    slice_rows = []
                    for row in grouped_authors.order_by(
                        fn.MIN(book_m.AuthorTitle).asc(),
                        book_m.AuthorId.asc(),
                    ).paginate(page + 1, page_size):
                        aid = int(row.AuthorId)
                        ar_rec = arm.get_or_none(
                            (arm.EntryId == aid) & (arm.ArrInstance.in_(arr_keys))
                        )
                        if ar_rec is not None:
                            slice_rows.append(ar_rec)
                        else:
                            disp = getattr(row, "disp_title", None) or ""
                            mx = getattr(row, "mx_mon", None)
                            slice_rows.append(
                                SimpleNamespace(
                                    EntryId=aid,
                                    Title=disp,
                                    Monitored=mx,
                                    BookCount=0,
                                    QualityProfileName=None,
                                    Searched=False,
                                )
                            )

                ids = [int(ar.EntryId) for ar in slice_rows]
                book_maps = {}
                if ids and book_m is not None:
                    book_maps = Catalog._readarr_author_browse_progress_maps(book_m, arr_keys, ids)

        authors_out: list[dict[str, Any]] = []
        for ar in slice_rows:
            aid = int(ar.EntryId)
            bm, ba = book_maps.get(aid, (0, 0))
            miss_b = max(bm - ba, 0)
            authors_out.append(
                {
                    "author": {
                        "id": ar.EntryId,
                        "name": ar.Title or "",
                        "monitored": coerce_bool(ar.Monitored),
                        "bookCount": int(getattr(ar, "BookCount", None) or 0),
                        "qualityProfileName": getattr(ar, "QualityProfileName", None),
                        "searched": coerce_bool(ar.Searched),
                        "booksMonitored": bm,
                        "booksAvailable": ba,
                        "booksMissing": miss_b,
                    }
                }
            )

        return {
            "counts": dict(rollup_book_counts),
            "book_total": int(book_total_inst),
            "total": total,
            "page": page,
            "page_size": page_size,
            "authors": authors_out,
        }

    def _readarr_author_detail_from_db(self, arr, author_id: int) -> dict[str, Any] | None:
        """Return a single author with all books in one DB visit."""
        arm = getattr(arr, "artists_file_model", None)
        book_m = getattr(arr, "model_file", None)
        db = getattr(arr, "db", None)

        if not self._ensure_arr_db(arr) or arm is None or book_m is None or db is None:
            return None

        arr_keys = self._readarr_instance_keys(arr)
        rollup_book_counts, _ = get_readarr_book_counts_total(arr)

        author_row = None
        book_rows: list[Any] = []

        with database_lock():
            with db.connection_context():
                author_row = arm.get_or_none(
                    (arm.EntryId == author_id) & (arm.ArrInstance.in_(arr_keys))
                )

                bq = book_m.select().where(
                    (book_m.AuthorId == author_id) & (book_m.ArrInstance.in_(arr_keys))
                )
                try:
                    bq = bq.order_by(book_m.ReleaseDate, book_m.Title)
                except Exception:
                    bq = bq.order_by(book_m.Title)
                book_rows = list(bq)

                if author_row is None and not book_rows:
                    return None

        book_items = [self._readarr_book_row_payload(bk) for bk in book_rows]

        if author_row is not None:
            author_payload = {
                "id": author_row.EntryId,
                "name": author_row.Title or "",
                "monitored": coerce_bool(author_row.Monitored),
                "bookCount": int(getattr(author_row, "BookCount", None) or 0),
                "qualityProfileName": getattr(author_row, "QualityProfileName", None),
                "searched": coerce_bool(author_row.Searched),
            }
        else:
            first_book = book_rows[0]
            monitored_books = [bk for bk in book_rows if bk.Monitored]
            author_payload = {
                "id": author_id,
                "name": getattr(first_book, "AuthorTitle", None) or "",
                "monitored": any(coerce_bool(bk.Monitored) for bk in book_rows),
                "bookCount": len(book_rows),
                "qualityProfileName": None,
                "searched": bool(monitored_books)
                and all(coerce_bool(bk.Searched) for bk in monitored_books),
            }

        return {
            "counts": dict(rollup_book_counts),
            "author": author_payload,
            "books": book_items,
        }

    def _enrich_sonarr_series_payload_quality_from_api(
        self,
        arr: Any,
        payload: list[dict[str, Any]],
        pending: list[tuple[int, int]],
    ) -> None:
        """Fill quality profile from Sonarr HTTP API for episode-mode rows (after DB work).

        Run outside Peewee ``connection_context`` and outside :func:`~qBitrr.db_lock.database_lock`
        so no DB connection or cross-process DB lock is held during network I/O.
        """
        if not pending:
            return
        client = getattr(arr, "client", None)
        series_api = getattr(client, "series", None) if client else None
        if not client or not series_api or not hasattr(series_api, "get"):
            return
        for idx, series_id in pending:
            if not (0 <= idx < len(payload)):
                continue
            try:
                series_data = series_api.get(item_id=series_id)
                if not series_data:
                    continue
                quality_profile_id = series_data.get("qualityProfileId")
                quality_profile_name = None
                if quality_profile_id:
                    quality_cache = getattr(arr, "_quality_profile_cache", {})
                    if quality_profile_id in quality_cache:
                        quality_profile_name = quality_cache[quality_profile_id].get("name")
                    elif hasattr(client, "quality_profile") and hasattr(
                        client.quality_profile, "get"
                    ):
                        try:
                            profile = client.quality_profile.get(item_id=quality_profile_id)
                            quality_profile_name = profile.get("name") if profile else None
                        except Exception:
                            self.logger.debug(
                                "Sonarr quality profile lookup failed",
                                exc_info=True,
                            )
                series_obj = payload[idx].setdefault("series", {})
                if quality_profile_id is not None:
                    series_obj["qualityProfileId"] = quality_profile_id
                if quality_profile_name is not None:
                    series_obj["qualityProfileName"] = quality_profile_name
            except Exception:
                self.logger.debug("Sonarr series payload build failed", exc_info=True)

    def _sonarr_series_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        *,
        missing_only: bool = False,
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return empty_catalog_payload("sonarr", page=page, page_size=page_size)
        episodes_model = getattr(arr, "model_file", None)
        series_model = getattr(arr, "series_file_model", None)
        db = getattr(arr, "db", None)
        if episodes_model is None or db is None:
            return empty_catalog_payload("sonarr", page=page, page_size=page_size)
        page = max(page, 0)
        page_size = max(page_size, 1)
        resolved_page = page
        arr_instance = getattr(arr, "_name", "")
        missing_condition = episodes_model.EpisodeFileId.is_null(True) | (
            episodes_model.EpisodeFileId == 0
        )

        ep_instance_counts, rollup_total_series = get_sonarr_series_counts_total(arr)
        monitored_count = ep_instance_counts.get("monitored", 0)
        available_count = ep_instance_counts.get("available", 0)
        missing_count = ep_instance_counts.get("missing", 0)

        sonarr_api_quality_pending: list[tuple[int, int]] = []
        payload: list[dict[str, Any]] = []
        total_series = 0
        # Materialise raw rows inside the DB lock; build Python payloads after release (B-3).
        # Each tuple holds the bare data we need so payload assembly cannot touch the cursor.
        collected_series: list[tuple[Any, list[Any]]] = []  # (series_row, episodes_list)
        has_qp_id_field = bool(series_model) and hasattr(series_model, "QualityProfileId")
        has_qp_name_field = bool(series_model) and hasattr(series_model, "QualityProfileName")
        with database_lock():
            with db.connection_context():
                missing_series_ids: list[int] = []
                if missing_only:
                    missing_series_ids = [
                        row.SeriesId
                        for row in episodes_model.select(episodes_model.SeriesId)
                        .where(
                            (episodes_model.ArrInstance == arr_instance)
                            & (episodes_model.Monitored == True)  # noqa: E712
                            & missing_condition
                        )
                        .distinct()
                        if getattr(row, "SeriesId", None) is not None
                    ]
                    if not missing_series_ids:
                        return {
                            "counts": {
                                "available": available_count,
                                "monitored": monitored_count,
                                "missing": missing_count,
                            },
                            "total": 0,
                            "page": resolved_page,
                            "page_size": page_size,
                            "series": [],
                        }

                if series_model is not None:
                    base_series_query = series_model.select().where(
                        series_model.ArrInstance == arr_instance
                    )
                    total_series = rollup_total_series

                    series_query = base_series_query
                    if search:
                        series_query = series_query.where(series_model.Title.contains(search))
                    if missing_only and missing_series_ids:
                        series_query = series_query.where(
                            series_model.EntryId.in_(missing_series_ids)
                        )
                    filtered_series_count = series_query.count()
                    if filtered_series_count:
                        max_pages = (filtered_series_count + page_size - 1) // page_size
                        if max_pages:
                            resolved_page = min(resolved_page, max_pages - 1)
                        resolved_page = max(resolved_page, 0)
                        series_page = list(
                            series_query.order_by(series_model.Title.asc()).paginate(
                                resolved_page + 1, page_size
                            )
                        )
                        for series in series_page:
                            episodes_query = episodes_model.select().where(
                                (episodes_model.ArrInstance == arr_instance)
                                & (episodes_model.SeriesId == series.EntryId)
                            )
                            if missing_only:
                                episodes_query = episodes_query.where(missing_condition)
                            episodes_query = episodes_query.order_by(
                                episodes_model.SeasonNumber.asc(),
                                episodes_model.EpisodeNumber.asc(),
                            )
                            collected_series.append((series, list(episodes_query)))

        # ---- Lock released; build payloads from materialised rows ---------------------
        for series, episodes_list in collected_series:
            self.logger.debug(
                "[Sonarr Series] Series %s (ID %s) has %d episodes (missing_only=%s)",
                getattr(series, "Title", "unknown"),
                getattr(series, "EntryId", "?"),
                len(episodes_list),
                missing_only,
            )
            seasons: dict[str, dict[str, Any]] = {}
            series_monitored = 0
            series_available = 0
            for ep in episodes_list:
                season_value = getattr(ep, "SeasonNumber", None)
                season_key = str(season_value) if season_value is not None else "unknown"
                season_bucket = seasons.setdefault(
                    season_key,
                    {"monitored": 0, "available": 0, "episodes": []},
                )
                is_monitored = coerce_bool(getattr(ep, "Monitored", None))
                has_file = coerce_bool(getattr(ep, "EpisodeFileId", None))
                if is_monitored:
                    season_bucket["monitored"] += 1
                    series_monitored += 1
                if has_file:
                    season_bucket["available"] += 1
                    if is_monitored:
                        series_available += 1
                air_date = getattr(ep, "AirDateUtc", None)
                if hasattr(air_date, "isoformat"):
                    try:
                        air_value = air_date.isoformat()
                    except Exception:
                        air_value = str(air_date)
                elif isinstance(air_date, str):
                    air_value = air_date
                else:
                    air_value = ""
                if (not missing_only) or (not has_file):
                    season_bucket["episodes"].append(
                        {
                            "episodeNumber": getattr(ep, "EpisodeNumber", None),
                            "title": getattr(ep, "Title", "") or "",
                            "monitored": is_monitored,
                            "hasFile": has_file,
                            "airDateUtc": air_value,
                            "reason": getattr(ep, "Reason", None),
                        }
                    )
            for bucket in seasons.values():
                monitored_eps = int(bucket.get("monitored", 0) or 0)
                available_eps = int(bucket.get("available", 0) or 0)
                bucket["missing"] = max(monitored_eps - min(available_eps, monitored_eps), 0)
            series_missing = max(series_monitored - series_available, 0)
            if missing_only:
                seasons = {key: data for key, data in seasons.items() if data["episodes"]}
                if not seasons:
                    continue

            series_id = getattr(series, "EntryId", None)
            quality_profile_id = (
                getattr(series, "QualityProfileId", None) if has_qp_id_field else None
            )
            quality_profile_name = (
                getattr(series, "QualityProfileName", None) if has_qp_name_field else None
            )

            payload.append(
                {
                    "series": {
                        "id": series_id,
                        "title": getattr(series, "Title", "") or "",
                        "qualityProfileId": quality_profile_id,
                        "qualityProfileName": quality_profile_name,
                    },
                    "totals": {
                        "available": series_available,
                        "monitored": series_monitored,
                        "missing": series_missing,
                    },
                    "seasons": seasons,
                }
            )

        if not payload:
            # Episode-mode fallback: collect (series_id, series_title, episodes_list) tuples
            # inside the lock, then build the payload outside it.
            collected_fallback: list[tuple[Any, Any, list[Any]]] = []
            page_keys: list[tuple[Any, ...]] = []
            field_names: list[str] = []
            with database_lock():
                with db.connection_context():
                    base_episode_query = episodes_model.select().where(
                        episodes_model.ArrInstance == arr_instance
                    )
                    if search:
                        search_filters = []
                        if hasattr(episodes_model, "SeriesTitle"):
                            search_filters.append(episodes_model.SeriesTitle.contains(search))
                        search_filters.append(episodes_model.Title.contains(search))
                        expr = search_filters[0]
                        for extra in search_filters[1:]:
                            expr |= extra
                        base_episode_query = base_episode_query.where(expr)
                    if missing_only:
                        base_episode_query = base_episode_query.where(missing_condition)

                    series_id_field = (
                        getattr(episodes_model, "SeriesId", None)
                        if hasattr(episodes_model, "SeriesId")
                        else None
                    )
                    series_title_field = (
                        getattr(episodes_model, "SeriesTitle", None)
                        if hasattr(episodes_model, "SeriesTitle")
                        else None
                    )

                    distinct_fields = []
                    if series_id_field is not None:
                        distinct_fields.append(series_id_field)
                        field_names.append("SeriesId")
                    if series_title_field is not None:
                        distinct_fields.append(series_title_field)
                        field_names.append("SeriesTitle")
                    if not distinct_fields:
                        distinct_fields.append(episodes_model.Title.alias("SeriesTitle"))
                        field_names.append("SeriesTitle")

                    distinct_query = (
                        base_episode_query.select(*distinct_fields)
                        .distinct()
                        .order_by(
                            series_title_field.asc()
                            if series_title_field is not None
                            else episodes_model.Title.asc()
                        )
                    )
                    series_key_rows = list(distinct_query.tuples())
                    total_series = len(series_key_rows)
                    if total_series:
                        max_pages = (total_series + page_size - 1) // page_size
                        resolved_page = min(resolved_page, max_pages - 1)
                        resolved_page = max(resolved_page, 0)
                        start = resolved_page * page_size
                        end = start + page_size
                        page_keys = series_key_rows[start:end]
                    else:
                        resolved_page = 0
                        page_keys = []

                    for key in page_keys:
                        key_data = dict(zip(field_names, key))
                        fk_series_id = key_data.get("SeriesId")
                        fk_series_title = key_data.get("SeriesTitle")
                        episode_conditions = []
                        if fk_series_id is not None:
                            episode_conditions.append(episodes_model.SeriesId == fk_series_id)
                        if fk_series_title is not None:
                            episode_conditions.append(
                                episodes_model.SeriesTitle == fk_series_title
                            )
                        episodes_query = episodes_model.select().where(
                            episodes_model.ArrInstance == arr_instance
                        )
                        if episode_conditions:
                            condition = episode_conditions[0]
                            for extra in episode_conditions[1:]:
                                condition &= extra
                            episodes_query = episodes_query.where(condition)
                        if missing_only:
                            episodes_query = episodes_query.where(missing_condition)
                        episodes_query = episodes_query.order_by(
                            episodes_model.SeasonNumber.asc(),
                            episodes_model.EpisodeNumber.asc(),
                        )
                        collected_fallback.append(
                            (fk_series_id, fk_series_title, list(episodes_query))
                        )

            # Lock released — build payload from materialised rows (B-3).
            payload = []
            for fk_series_id, fk_series_title, episodes_list in collected_fallback:
                seasons: dict[str, dict[str, Any]] = {}
                series_monitored = 0
                series_available = 0
                # Track quality profile from first episode (all episodes share the same profile).
                quality_profile_id = None
                quality_profile_name = None
                for ep in episodes_list:
                    if quality_profile_id is None and hasattr(ep, "QualityProfileId"):
                        quality_profile_id = getattr(ep, "QualityProfileId", None)
                    if quality_profile_name is None and hasattr(ep, "QualityProfileName"):
                        quality_profile_name = getattr(ep, "QualityProfileName", None)
                    season_value = getattr(ep, "SeasonNumber", None)
                    season_key = str(season_value) if season_value is not None else "unknown"
                    season_bucket = seasons.setdefault(
                        season_key,
                        {"monitored": 0, "available": 0, "episodes": []},
                    )
                    is_monitored = coerce_bool(getattr(ep, "Monitored", None))
                    has_file = coerce_bool(getattr(ep, "EpisodeFileId", None))
                    if is_monitored:
                        season_bucket["monitored"] += 1
                        series_monitored += 1
                    if has_file:
                        season_bucket["available"] += 1
                        if is_monitored:
                            series_available += 1
                    air_date = getattr(ep, "AirDateUtc", None)
                    if hasattr(air_date, "isoformat"):
                        try:
                            air_value = air_date.isoformat()
                        except Exception:
                            air_value = str(air_date)
                    elif isinstance(air_date, str):
                        air_value = air_date
                    else:
                        air_value = ""
                    season_bucket["episodes"].append(
                        {
                            "episodeNumber": getattr(ep, "EpisodeNumber", None),
                            "title": getattr(ep, "Title", "") or "",
                            "monitored": is_monitored,
                            "hasFile": has_file,
                            "airDateUtc": air_value,
                            "reason": getattr(ep, "Reason", None),
                        }
                    )
                for bucket in seasons.values():
                    monitored_eps = int(bucket.get("monitored", 0) or 0)
                    available_eps = int(bucket.get("available", 0) or 0)
                    bucket["missing"] = max(monitored_eps - min(available_eps, monitored_eps), 0)
                series_missing = max(series_monitored - series_available, 0)
                if missing_only:
                    seasons = {key: data for key, data in seasons.items() if data["episodes"]}
                    if not seasons:
                        continue

                append_idx = len(payload)
                if quality_profile_id is None and fk_series_id is not None:
                    sonarr_api_quality_pending.append((append_idx, fk_series_id))

                payload.append(
                    {
                        "series": {
                            "id": fk_series_id,
                            "title": (
                                fk_series_title
                                or (
                                    f"Series {len(payload) + 1}"
                                    if fk_series_id is None
                                    else str(fk_series_id)
                                )
                            ),
                            "qualityProfileId": quality_profile_id,
                            "qualityProfileName": quality_profile_name,
                        },
                        "totals": {
                            "available": series_available,
                            "monitored": series_monitored,
                            "missing": series_missing,
                        },
                        "seasons": seasons,
                    }
                )

        self._enrich_sonarr_series_payload_quality_from_api(
            arr, payload, sonarr_api_quality_pending
        )

        result = {
            "counts": {
                "available": available_count,
                "monitored": monitored_count,
                "missing": missing_count,
            },
            "total": total_series,
            "page": resolved_page,
            "page_size": page_size,
            "series": payload,
        }
        if payload:
            first_series = payload[0]
            first_seasons = first_series.get("seasons", {})
            total_episodes_in_response = sum(
                len(season.get("episodes", [])) for season in first_seasons.values()
            )
            self.logger.info(
                "[Sonarr API] Returning %d series, first series '%s' has %d seasons, %d episodes (missing_only=%s)",
                len(payload),
                first_series.get("series", {}).get("title", "?"),
                len(first_seasons),
                total_episodes_in_response,
                missing_only,
            )
        return result

    # Routes
