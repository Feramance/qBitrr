"""Per-Arr-type DB file query and search-state reset helpers (split from Arr)."""

from __future__ import annotations

from collections.abc import Iterable
from copy import copy
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from qBitrr.arss._shared import (
    _ARR_RETRY_EXCEPTIONS,
    AlbumFilesModel,
    EpisodeFilesModel,
    MoviesFilesModel,
    SeriesFilesModel,
    database_lock,
    with_retry,
)

if TYPE_CHECKING:
    from qBitrr.arss.arr import Arr


def db_get_files(
    arr: Arr,
) -> Iterable[
    tuple[MoviesFilesModel | EpisodeFilesModel | SeriesFilesModel, bool, bool, bool, int]
]:
    if arr.type == "sonarr" and arr.series_search is True:
        serieslist = arr.db_get_files_series()
        for series in serieslist:
            yield series[0], series[1], series[2], series[2] is not True, len(serieslist)
    elif arr.type == "sonarr" and arr.series_search == "smart":
        # Smart mode: decide dynamically based on what needs to be searched
        episodelist = arr.db_get_files_episodes()
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
                    arr.logger.info(
                        "[SMART MODE] Using series search for %s episodes from series ID %s",
                        len(episodes),
                        series_id,
                    )
                    # Create a series entry for searching
                    series_model = (
                        arr.series_file_model.select()
                        .where(
                            (arr.series_file_model.EntryId == series_id)
                            & (arr.series_file_model.ArrInstance == arr._name)
                        )
                        .first()
                    )
                    if series_model:
                        yield series_model, episodes[0][1], episodes[0][2], True, len(episodelist)
                else:
                    # Single episode - use episode search (smart decision)
                    episode = episodes[0][0]
                    arr.logger.info(
                        "[SMART MODE] Using episode search for single episode: %s S%02dE%03d",
                        episode.SeriesTitle,
                        episode.SeasonNumber,
                        episode.EpisodeNumber,
                    )
                    yield episodes[0][0], episodes[0][1], episodes[0][2], False, len(episodelist)
    elif arr.type == "sonarr" and arr.series_search == False:
        episodelist = arr.db_get_files_episodes()
        for episodes in episodelist:
            yield episodes[0], episodes[1], episodes[2], False, len(episodelist)
    elif arr.type == "radarr":
        movielist = arr.db_get_files_movies()
        for movies in movielist:
            yield movies[0], movies[1], movies[2], False, len(movielist)
    elif arr.type == "lidarr":
        albumlist = arr.db_get_files_movies()  # This calls the lidarr section we added
        for albums in albumlist:
            yield albums[0], albums[1], albums[2], False, len(albumlist)


def db_maybe_reset_entry_searched_state(arr):
    if arr.type == "sonarr":
        arr.db_reset__series_searched_state()
        arr.db_reset__episode_searched_state()
    elif arr.type == "radarr":
        arr.db_reset__movie_searched_state()
    elif arr.type == "lidarr":
        arr.db_reset__album_searched_state()
    arr.loop_completed = False


def db_reset__series_searched_state(arr):
    ids = []
    arr.series_file_model: SeriesFilesModel
    arr.model_file: EpisodeFilesModel
    if (
        arr.loop_completed and arr.reset_on_completion and arr.series_search
    ):  # Only wipe if a loop completed was tagged
        with database_lock():
            arr.series_file_model.update(Searched=False, Upgrade=False).where(
                (arr.series_file_model.Searched == True)
                & (arr.series_file_model.ArrInstance == arr._name)
            ).execute()
        series = with_retry(
            lambda: arr.client.series.get(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
        for s in series:
            ids.append(s["id"])
        with database_lock():
            if ids:
                arr.series_file_model.delete().where(
                    (arr.series_file_model.EntryId.not_in(ids))
                    & (arr.series_file_model.ArrInstance == arr._name)
                ).execute()
            else:
                arr.logger.warning(
                    "%s: No series returned from Arr API during reset; "
                    "skipping DB prune to prevent data loss",
                    arr._name,
                )
        arr.loop_completed = False


def db_reset__episode_searched_state(arr):
    ids = []
    arr.model_file: EpisodeFilesModel
    if (
        arr.loop_completed is True and arr.reset_on_completion
    ):  # Only wipe if a loop completed was tagged
        with database_lock():
            arr.model_file.update(Searched=False, Upgrade=False).where(
                (arr.model_file.Searched == True) & (arr.model_file.ArrInstance == arr._name)
            ).execute()
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
        with database_lock():
            if ids:
                arr.model_file.delete().where(
                    (arr.model_file.EntryId.not_in(ids))
                    & (arr.model_file.ArrInstance == arr._name)
                ).execute()
            else:
                arr.logger.warning(
                    "%s: No episodes returned from Arr API during reset; "
                    "skipping DB prune to prevent data loss",
                    arr._name,
                )
        arr.loop_completed = False


def db_reset__movie_searched_state(arr):
    ids = []
    arr.model_file: MoviesFilesModel
    if (
        arr.loop_completed is True and arr.reset_on_completion
    ):  # Only wipe if a loop completed was tagged
        with database_lock():
            arr.model_file.update(Searched=False, Upgrade=False).where(
                (arr.model_file.Searched == True) & (arr.model_file.ArrInstance == arr._name)
            ).execute()
        movies = with_retry(
            lambda: arr.client.movie.get(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
        for m in movies:
            ids.append(m["id"])
        with database_lock():
            if ids:
                arr.model_file.delete().where(
                    (arr.model_file.EntryId.not_in(ids))
                    & (arr.model_file.ArrInstance == arr._name)
                ).execute()
            else:
                arr.logger.warning(
                    "%s: No movies returned from Arr API during reset; "
                    "skipping DB prune to prevent data loss",
                    arr._name,
                )
        arr.loop_completed = False


def db_reset__album_searched_state(arr):
    ids = []
    arr.model_file: AlbumFilesModel
    if (
        arr.loop_completed is True and arr.reset_on_completion
    ):  # Only wipe if a loop completed was tagged
        with database_lock():
            arr.model_file.update(Searched=False, Upgrade=False).where(
                (arr.model_file.Searched == True) & (arr.model_file.ArrInstance == arr._name)
            ).execute()
        artists = with_retry(
            lambda: arr.client.artist.get(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
        for artist in artists:
            albums = with_retry(
                lambda a=artist: arr.client.album.get(artist_id=a["id"]),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
            for album in albums:
                ids.append(album["id"])
        with database_lock():
            if ids:
                arr.model_file.delete().where(
                    (arr.model_file.EntryId.not_in(ids))
                    & (arr.model_file.ArrInstance == arr._name)
                ).execute()
            else:
                arr.logger.warning(
                    "%s: No albums returned from Arr API during reset; "
                    "skipping DB prune to prevent data loss",
                    arr._name,
                )
        arr.loop_completed = False


def _db_search_quality_cf_condition(arr, *, missing_file_field):
    """Build Searched / QualityMet / CustomFormatMet / missing-file WHERE fragment.

    Shared by ``db_get_files_series|episodes|movies`` (and Lidarr albums).
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
    entries = []
    if not (arr.search_missing or arr.do_upgrade_search):
        return None
    elif not arr.series_search:
        return None
    elif arr.type == "sonarr":
        condition = arr.model_file.AirDateUtc.is_null(False)
        if not arr.search_specials:
            condition &= arr.model_file.SeasonNumber != 0
        condition &= arr._db_search_quality_cf_condition(
            missing_file_field=arr.model_file.EpisodeFileId
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
    entries = []
    if not (arr.search_missing or arr.do_upgrade_search):
        return None
    elif arr.type == "sonarr":
        condition = (arr.model_file.AirDateUtc.is_null(False)) & (
            arr.model_file.ArrInstance == arr._name
        )
        if not arr.search_specials:
            condition &= arr.model_file.SeasonNumber != 0
        condition &= arr._db_search_quality_cf_condition(
            missing_file_field=arr.model_file.EpisodeFileId
        )
        today_condition = copy(condition)
        today_condition &= arr.model_file.AirDateUtc > (
            datetime.now(timezone.utc) - timedelta(days=1)
        )
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
    entries = []
    if not (arr.search_missing or arr.do_upgrade_search):
        return None
    if arr.type == "radarr":
        condition = (arr.model_file.Year.is_null(False)) & (
            arr.model_file.ArrInstance == arr._name
        )
        condition &= arr._db_search_quality_cf_condition(
            missing_file_field=arr.model_file.MovieFileId
        )
        if arr.search_by_year:
            condition &= arr.model_file.Year == arr.search_current_year

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
            .order_by(
                reason_priority.asc(),  # Primary: order by reason priority
                arr.model_file.MovieFileId.asc(),
            )
            .execute()
        ):
            entries.append([entry, False, False])
        return entries
    elif arr.type == "lidarr":
        condition = arr.model_file.ArrInstance == arr._name
        condition &= arr._db_search_quality_cf_condition(
            missing_file_field=arr.model_file.AlbumFileId
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
            .order_by(
                reason_priority.asc(),  # Primary: order by reason priority
                arr.model_file.AlbumFileId.asc(),
            )
            .execute()
        ):
            entries.append([entry, False, False])
        return entries


def db_get_request_files(arr) -> Iterable[tuple[MoviesFilesModel | EpisodeFilesModel, int]]:
    entries = []
    arr.logger.trace("Getting request files")
    if arr.type == "sonarr":
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
    elif arr.type == "radarr":
        condition = (arr.model_file.IsRequest == True) & (arr.model_file.ArrInstance == arr._name)
        condition &= arr.model_file.Year.is_null(False)
        condition &= arr.model_file.MovieFileId == 0
        condition &= arr.model_file.Searched == False
        entries = list(
            arr.model_file.select().where(condition).order_by(arr.model_file.Title.asc()).execute()
        )
    for entry in entries:
        yield entry, len(entries)
