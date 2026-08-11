"""Per-Arr-type DB file query and search-state reset helpers (split from Arr).

Module-level entry points are thin wrappers that dispatch to Arr concrete hooks.
Typed query/reset helpers below are called only from those hooks (or tests).
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import copy
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from qBitrr.arss.arr_shared import _ARR_RETRY_EXCEPTIONS, with_retry
from qBitrr.db_lock import database_lock
from qBitrr.tables import (
    AlbumFilesModel,
    BookFilesModel,
    EpisodeFilesModel,
    MoviesFilesModel,
    SeriesFilesModel,
)

if TYPE_CHECKING:
    from qBitrr.arss.arr_base import ArrBase as Arr


def db_get_files(
    arr: Arr,
) -> Iterable[
    tuple[
        MoviesFilesModel | EpisodeFilesModel | SeriesFilesModel | AlbumFilesModel | BookFilesModel,
        bool,
        bool,
        bool,
        int,
    ]
]:
    """Dispatch to the concrete Arr ``_db_get_files_impl`` hook."""
    return arr._db_get_files_impl()


def db_maybe_reset_entry_searched_state(arr):
    """Dispatch searched-state reset to the concrete Arr hook, then clear loop flag."""
    arr._db_maybe_reset_searched_state_impl()
    arr.loop_completed = False


def db_get_request_files(arr) -> Iterable[tuple[MoviesFilesModel | EpisodeFilesModel, int]]:
    """Dispatch request-file query to the concrete Arr hook."""
    return arr._db_get_request_files_impl()


def _db_reset_searched_state(
    arr, *, model, collect_ids, entity_label: str, extra_gate: bool = True
):
    """Clear Searched/Upgrade flags, prune orphans not returned by Arr, reset loop flag."""
    if not (arr.loop_completed and arr.reset_on_completion and extra_gate):
        return
    with database_lock():
        model.update(Searched=False, Upgrade=False).where(
            (model.Searched == True) & (model.ArrInstance == arr._name)
        ).execute()
    ids = list(collect_ids())
    with database_lock():
        if ids:
            model.delete().where(
                (model.EntryId.not_in(ids)) & (model.ArrInstance == arr._name)
            ).execute()
        else:
            arr.logger.warning(
                "%s: No %s returned from Arr API during reset; "
                "skipping DB prune to prevent data loss",
                arr._name,
                entity_label,
            )
    arr.loop_completed = False


def _collect_series_ids(arr):
    series = with_retry(
        lambda: arr.client.series.get(),
        retries=5,
        backoff=0.5,
        max_backoff=5,
        exceptions=_ARR_RETRY_EXCEPTIONS,
    )
    return [s["id"] for s in series]


def _collect_episode_ids(arr):
    ids = []
    series = with_retry(
        lambda: arr.client.series.get(),
        retries=5,
        backoff=0.5,
        max_backoff=5,
        exceptions=_ARR_RETRY_EXCEPTIONS,
    )
    for s in series:
        episodes = with_retry(
            lambda s=s: arr.client.episode.get(series_id=s["id"]),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
        for e in episodes:
            ids.append(e["id"])
    return ids


def _collect_movie_ids(arr):
    movies = with_retry(
        lambda: arr.client.movie.get(),
        retries=5,
        backoff=0.5,
        max_backoff=5,
        exceptions=_ARR_RETRY_EXCEPTIONS,
    )
    return [m["id"] for m in movies]


def _collect_album_ids(arr):
    ids = []
    artists = with_retry(
        lambda: arr.client.artist.get(),
        retries=5,
        backoff=0.5,
        max_backoff=5,
        exceptions=_ARR_RETRY_EXCEPTIONS,
    )
    for artist in artists:
        albums = with_retry(
            lambda a=artist: arr.client.album.get(artist_id=a["id"], all_artist_albums=True),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
        for album in albums:
            ids.append(album["id"])
    return ids


def _collect_book_ids(arr):
    books = with_retry(
        lambda: arr.client.book.get(),
        retries=5,
        backoff=0.5,
        max_backoff=5,
        exceptions=_ARR_RETRY_EXCEPTIONS,
    )
    return [b["id"] for b in books if isinstance(b, dict) and "id" in b]


def db_reset__series_searched_state(arr):
    arr.series_file_model: SeriesFilesModel
    arr.model_file: EpisodeFilesModel
    _db_reset_searched_state(
        arr,
        model=arr.series_file_model,
        collect_ids=lambda: _collect_series_ids(arr),
        entity_label="series",
        extra_gate=bool(arr.series_search),
    )


def db_reset__episode_searched_state(arr):
    arr.model_file: EpisodeFilesModel
    _db_reset_searched_state(
        arr,
        model=arr.model_file,
        collect_ids=lambda: _collect_episode_ids(arr),
        entity_label="episodes",
    )


def db_reset__movie_searched_state(arr):
    arr.model_file: MoviesFilesModel
    _db_reset_searched_state(
        arr,
        model=arr.model_file,
        collect_ids=lambda: _collect_movie_ids(arr),
        entity_label="movies",
    )


def db_reset__album_searched_state(arr):
    arr.model_file: AlbumFilesModel
    _db_reset_searched_state(
        arr,
        model=arr.model_file,
        collect_ids=lambda: _collect_album_ids(arr),
        entity_label="albums",
    )


def db_reset__book_searched_state(arr):
    """Clear Searched/Upgrade on Readarr book rows and prune orphans."""
    arr.model_file: BookFilesModel
    _db_reset_searched_state(
        arr,
        model=arr.model_file,
        collect_ids=lambda: _collect_book_ids(arr),
        entity_label="books",
    )


def _db_search_quality_cf_condition(arr, *, missing_file_field):
    """Build Searched / QualityMet / CustomFormatMet / missing-file WHERE fragment.

    Shared by ``db_get_files_series|episodes|movies|albums|books``.
    ``missing_file_field`` is the model column for "no file yet" (e.g. EpisodeFileId).
    """
    model = arr.model_file
    if arr.do_upgrade_search:
        return model.Upgrade == False
    if arr.quality_unmet_search and not arr.custom_format_unmet_search:
        return (model.Searched == False) | (model.QualityMet == False)
    if not arr.quality_unmet_search and arr.custom_format_unmet_search:
        return (model.Searched == False) | (model.CustomFormatMet == False)
    if arr.quality_unmet_search and arr.custom_format_unmet_search:
        return (
            (model.Searched == False)
            | (model.QualityMet == False)
            | (model.CustomFormatMet == False)
        )
    return (missing_file_field == 0) & (model.Searched == False)


def db_get_files_series(arr) -> list[list[SeriesFilesModel, bool, bool]] | None:
    """Sonarr series-search candidates (called only from SonarrArr)."""
    entries = []
    if not (arr.search_missing or arr.do_upgrade_search):
        return None
    if not arr.series_search:
        return None
    condition = arr.model_file.AirDateUtc.is_null(False)
    if not arr.search_specials:
        condition &= arr.model_file.SeasonNumber != 0
    condition &= _db_search_quality_cf_condition(
        arr, missing_file_field=arr.model_file.EpisodeFileId
    )
    todays_condition = copy(condition)
    todays_condition &= arr.model_file.AirDateUtc > (
        datetime.now(timezone.utc) - timedelta(days=1)
    )
    todays_condition &= arr.model_file.AirDateUtc < (
        datetime.now(timezone.utc) - timedelta(hours=1)
    )
    condition &= arr.model_file.AirDateUtc < (datetime.now(timezone.utc) - timedelta(days=1))
    if arr.search_by_year and arr.search_current_year is not None:
        condition &= (
            arr.model_file.AirDateUtc
            >= datetime(month=1, day=1, year=int(arr.search_current_year)).date()
        )
        condition &= (
            arr.model_file.AirDateUtc
            <= datetime(month=12, day=31, year=int(arr.search_current_year)).date()
        )
    for i1, i2, i3 in arr._search_todays(condition):
        if i1 is not None:
            entries.append([i1, i2, i3])
    if not arr.do_upgrade_search:
        condition = (arr.series_file_model.Searched == False) & (
            arr.series_file_model.ArrInstance == arr._name
        )
    else:
        condition = (arr.series_file_model.Upgrade == False) & (
            arr.series_file_model.ArrInstance == arr._name
        )

    # Collect series entries with their priority based on episode reasons
    # Missing > CustomFormat > Quality > Upgrade
    reason_priority_map = {
        "Missing": 1,
        "CustomFormat": 2,
        "Quality": 3,
        "Upgrade": 4,
    }

    # Pre-fetch all episode reasons in a single query, grouped by SeriesId
    series_ids = [
        e.EntryId
        for e in arr.series_file_model.select(arr.series_file_model.EntryId)
        .where(condition)
        .execute()
    ]
    reasons_by_series: dict[int, int] = {}
    if series_ids:
        for ep in (
            arr.model_file.select(arr.model_file.SeriesId, arr.model_file.Reason)
            .where(arr.model_file.SeriesId.in_(series_ids))
            .execute()
        ):
            if ep.Reason:
                priority = reason_priority_map.get(ep.Reason, 5)
                sid = ep.SeriesId
                if sid not in reasons_by_series or priority < reasons_by_series[sid]:
                    reasons_by_series[sid] = priority

    series_entries = []
    for entry_ in arr.series_file_model.select().where(condition).execute():
        min_priority = reasons_by_series.get(entry_.EntryId, 5)
        series_entries.append((entry_, min_priority))

    # Sort by priority, then by EntryId
    series_entries.sort(key=lambda x: (x[1], x[0].EntryId))

    for entry_, _ in series_entries:
        arr.logger.trace("Adding %s to search list", entry_.Title)
        entries.append([entry_, False, False])
    return entries


def db_get_files_episodes(arr) -> list[list[EpisodeFilesModel, bool, bool]] | None:
    """Sonarr episode-search candidates (called only from SonarrArr)."""
    entries = []
    if not (arr.search_missing or arr.do_upgrade_search):
        return None
    condition = (arr.model_file.AirDateUtc.is_null(False)) & (
        arr.model_file.ArrInstance == arr._name
    )
    if not arr.search_specials:
        condition &= arr.model_file.SeasonNumber != 0
    condition &= _db_search_quality_cf_condition(
        arr, missing_file_field=arr.model_file.EpisodeFileId
    )
    today_condition = copy(condition)
    today_condition &= arr.model_file.AirDateUtc > (datetime.now(timezone.utc) - timedelta(days=1))
    today_condition &= arr.model_file.AirDateUtc < (
        datetime.now(timezone.utc) - timedelta(hours=1)
    )
    condition &= arr.model_file.AirDateUtc < (datetime.now(timezone.utc) - timedelta(days=1))
    if arr.search_by_year and arr.search_current_year is not None:
        condition &= (
            arr.model_file.AirDateUtc
            >= datetime(month=1, day=1, year=int(arr.search_current_year)).date()
        )
        condition &= (
            arr.model_file.AirDateUtc
            <= datetime(month=12, day=31, year=int(arr.search_current_year)).date()
        )
    # Order searches by priority: Missing > CustomFormat > Quality > Upgrade
    # Use CASE to assign priority values to each reason
    from peewee import Case

    reason_priority = Case(
        None,
        (
            (arr.model_file.Reason == "Missing", 1),
            (arr.model_file.Reason == "CustomFormat", 2),
            (arr.model_file.Reason == "Quality", 3),
            (arr.model_file.Reason == "Upgrade", 4),
        ),
        5,  # Default priority for other reasons
    )

    for entry in (
        arr.model_file.select()
        .where(condition)
        .group_by(arr.model_file.SeriesId)
        .order_by(
            reason_priority.asc(),
            arr.model_file.EpisodeFileId.asc(),
            arr.model_file.SeriesTitle,
            arr.model_file.SeasonNumber.desc(),
            arr.model_file.AirDateUtc.desc(),
        )
        .execute()
    ):
        entries.append([entry, False, False])
    for i1, i2, i3 in arr._search_todays(today_condition):
        if i1 is not None:
            entries.append([i1, i2, i3])
    return entries


def db_get_files_movies(arr) -> list[list[MoviesFilesModel, bool, bool]] | None:
    """Radarr movie-search candidates (called only from RadarrArr)."""
    entries = []
    if not (arr.search_missing or arr.do_upgrade_search):
        return None
    condition = (arr.model_file.Year.is_null(False)) & (arr.model_file.ArrInstance == arr._name)
    condition &= _db_search_quality_cf_condition(
        arr, missing_file_field=arr.model_file.MovieFileId
    )
    if arr.search_by_year:
        condition &= arr.model_file.Year == arr.search_current_year

    # Order searches by priority: Missing > CustomFormat > Quality > Upgrade
    from peewee import Case

    reason_priority = Case(
        None,
        (
            (arr.model_file.Reason == "Missing", 1),
            (arr.model_file.Reason == "CustomFormat", 2),
            (arr.model_file.Reason == "Quality", 3),
            (arr.model_file.Reason == "Upgrade", 4),
        ),
        5,  # Default priority for other reasons
    )

    for entry in (
        arr.model_file.select()
        .where(condition)
        .order_by(
            reason_priority.asc(),
            arr.model_file.MovieFileId.asc(),
        )
        .execute()
    ):
        entries.append([entry, False, False])
    return entries


def db_get_files_albums(arr) -> list[list[AlbumFilesModel, bool, bool]] | None:
    """Lidarr album-search candidates (called only from LidarrArr)."""
    entries = []
    if not (arr.search_missing or arr.do_upgrade_search):
        return None
    condition = arr.model_file.ArrInstance == arr._name
    condition &= _db_search_quality_cf_condition(
        arr, missing_file_field=arr.model_file.AlbumFileId
    )

    from peewee import Case

    reason_priority = Case(
        None,
        (
            (arr.model_file.Reason == "Missing", 1),
            (arr.model_file.Reason == "CustomFormat", 2),
            (arr.model_file.Reason == "Quality", 3),
            (arr.model_file.Reason == "Upgrade", 4),
        ),
        5,  # Default priority for other reasons
    )

    for entry in (
        arr.model_file.select()
        .where(condition)
        .order_by(
            reason_priority.asc(),
            arr.model_file.AlbumFileId.asc(),
        )
        .execute()
    ):
        entries.append([entry, False, False])
    return entries


def db_get_files_books(arr) -> list[list[BookFilesModel, bool, bool]] | None:
    """Readarr book-search candidates (called only from ReadarrArr)."""
    entries = []
    if not (arr.search_missing or arr.do_upgrade_search):
        return None
    condition = arr.model_file.ArrInstance == arr._name
    condition &= _db_search_quality_cf_condition(arr, missing_file_field=arr.model_file.BookFileId)
    if arr.search_by_year and arr.search_current_year is not None:
        condition &= arr.model_file.ReleaseDate.is_null(False)
        condition &= arr.model_file.ReleaseDate >= datetime(
            month=1, day=1, year=int(arr.search_current_year)
        )
        condition &= arr.model_file.ReleaseDate <= datetime(
            month=12, day=31, hour=23, minute=59, second=59, year=int(arr.search_current_year)
        )

    from peewee import Case

    reason_priority = Case(
        None,
        (
            (arr.model_file.Reason == "Missing", 1),
            (arr.model_file.Reason == "CustomFormat", 2),
            (arr.model_file.Reason == "Quality", 3),
            (arr.model_file.Reason == "Upgrade", 4),
        ),
        5,  # Default priority for other reasons
    )

    for entry in (
        arr.model_file.select()
        .where(condition)
        .order_by(
            reason_priority.asc(),
            arr.model_file.BookFileId.asc(),
        )
        .execute()
    ):
        entries.append([entry, False, False])
    return entries


def db_get_request_files_sonarr(arr) -> Iterable[tuple[EpisodeFilesModel, int]]:
    """Yield Sonarr request-tagged episode rows needing search."""
    arr.logger.trace("Getting request files")
    condition = (arr.model_file.IsRequest == True) & (arr.model_file.ArrInstance == arr._name)
    condition &= arr.model_file.AirDateUtc.is_null(False)
    condition &= arr.model_file.EpisodeFileId == 0
    condition &= arr.model_file.Searched == False
    condition &= arr.model_file.AirDateUtc < (datetime.now(timezone.utc) - timedelta(days=1))
    entries = list(
        arr.model_file.select()
        .where(condition)
        .order_by(
            arr.model_file.SeriesTitle,
            arr.model_file.SeasonNumber.desc(),
            arr.model_file.AirDateUtc.desc(),
        )
        .execute()
    )
    for entry in entries:
        yield entry, len(entries)


def db_get_request_files_radarr(arr) -> Iterable[tuple[MoviesFilesModel, int]]:
    """Yield Radarr request-tagged movie rows needing search."""
    arr.logger.trace("Getting request files")
    condition = (arr.model_file.IsRequest == True) & (arr.model_file.ArrInstance == arr._name)
    condition &= arr.model_file.Year.is_null(False)
    condition &= arr.model_file.MovieFileId == 0
    condition &= arr.model_file.Searched == False
    entries = list(
        arr.model_file.select().where(condition).order_by(arr.model_file.Title.asc()).execute()
    )
    for entry in entries:
        yield entry, len(entries)
