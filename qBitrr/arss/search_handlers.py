"""Per-Arr-type search handlers (split from Arr.maybe_do_search)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qBitrr.arr_client import execute_command
from qBitrr.arss._shared import _ARR_RETRY_EXCEPTIONS, with_retry
from qBitrr.errors import NoConnectionrException
from qBitrr.tables import (
    AlbumFilesModel,
    EpisodeFilesModel,
    MoviesFilesModel,
    SeriesFilesModel,
)

if TYPE_CHECKING:
    from qBitrr.arss.base import ArrBase as Arr


def maybe_do_search(
    arr: Arr,
    file_model: EpisodeFilesModel | MoviesFilesModel | SeriesFilesModel,
    request: bool = False,
    todays: bool = False,
    bypass_limit: bool = False,
    series_search: bool = False,
    commands: int = 0,
):
    """Trigger an Arr search for the given file model when search features are enabled."""
    request_tag = (
        "[OVERSEERR REQUEST]: "
        if request and arr.overseerr_requests
        else (
            "[OMBI REQUEST]: "
            if request and arr.ombi_search_requests
            else "[PRIORITY SEARCH - TODAY]: " if todays else ""
        )
    )
    arr.refresh_download_queue()
    if request or todays:
        bypass_limit = True
    if file_model is None:
        return None
    features_enabled = (
        arr.search_missing
        or arr.do_upgrade_search
        or arr.quality_unmet_search
        or arr.custom_format_unmet_search
        or arr.ombi_search_requests
        or arr.overseerr_requests
    )
    if not features_enabled and not (request or todays):
        return None
    if not arr.is_alive:
        raise NoConnectionrException(f"Could not connect to {arr.uri}", error_type="arr")
    return arr._maybe_do_search_impl(
        file_model,
        request_tag=request_tag,
        request=request,
        todays=todays,
        bypass_limit=bypass_limit,
        series_search=series_search,
        commands=commands,
    )


def search_sonarr(
    arr: Arr,
    file_model: EpisodeFilesModel | SeriesFilesModel,
    *,
    request_tag: str,
    request: bool,
    todays: bool,
    bypass_limit: bool,
    series_search: bool,
    commands: int,
):
    """Sonarr episode/series search command path."""
    if not series_search:
        file_model: EpisodeFilesModel
        if not (request or todays):
            (
                arr.model_queue.select(arr.model_queue.Completed)
                .where(arr.model_queue.EntryId == file_model.EntryId)
                .execute()
            )
        else:
            pass
        if file_model.EntryId in arr.queue_file_ids:
            arr.logger.debug(
                "%sSkipping: Already Searched: %s | " "S%02dE%03d | " "%s | [id=%s|AirDateUTC=%s]",
                request_tag,
                file_model.SeriesTitle,
                file_model.SeasonNumber,
                file_model.EpisodeNumber,
                file_model.Title,
                file_model.EntryId,
                file_model.AirDateUtc,
            )
            arr.model_file.update(Searched=True, Upgrade=True).where(
                (arr.model_file.EntryId == file_model.EntryId)
                & (arr.model_file.ArrInstance == arr._name)
            ).execute()
            return True
        active_commands = arr.arr_db_query_commands_count()
        arr.logger.info(
            "%s active search commands, %s remaining",
            active_commands,
            commands,
        )
        if not bypass_limit and active_commands >= arr._get_search_command_limit():
            arr.logger.trace(
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
        arr.persistent_queue.insert(
            EntryId=file_model.EntryId, ArrInstance=arr._name
        ).on_conflict_ignore().execute()
        arr.model_queue.insert(
            Completed=False, EntryId=file_model.EntryId, ArrInstance=arr._name
        ).on_conflict_replace().execute()
        if file_model.EntryId not in arr.queue_file_ids:
            with_retry(
                lambda: execute_command(
                    arr.client, "EpisodeSearch", episodeIds=[file_model.EntryId]
                ),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
        arr.model_file.update(Searched=True, Upgrade=True).where(
            (arr.model_file.EntryId == file_model.EntryId)
            & (arr.model_file.ArrInstance == arr._name)
        ).execute()
        reason_text = getattr(file_model, "Reason", None) or None
        if reason_text:
            arr.logger.hnotice(
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
            arr.logger.hnotice(
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
        context_label = arr._humanize_request_tag(request_tag)
        arr._record_search_activity(
            description,
            context=context_label,
            detail=str(reason_text) if reason_text else None,
        )
        return True
    else:
        file_model: SeriesFilesModel
        active_commands = arr.arr_db_query_commands_count()
        arr.logger.info(
            "%s active search commands, %s remaining",
            active_commands,
            commands,
        )
        if not bypass_limit and active_commands >= arr._get_search_command_limit():
            arr.logger.trace(
                "Idle: Too many commands in queue: %s | [id=%s]",
                file_model.Title,
                file_model.EntryId,
            )
            return False
        arr.persistent_queue.insert(
            EntryId=file_model.EntryId, ArrInstance=arr._name
        ).on_conflict_ignore().execute()
        arr.model_queue.insert(
            Completed=False, EntryId=file_model.EntryId, ArrInstance=arr._name
        ).on_conflict_replace().execute()
        with_retry(
            lambda: execute_command(
                arr.client, arr.search_api_command, seriesId=file_model.EntryId
            ),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
        arr.model_file.update(Searched=True, Upgrade=True).where(
            (arr.model_file.EntryId == file_model.EntryId)
            & (arr.model_file.ArrInstance == arr._name)
        ).execute()
        arr.logger.hnotice(
            "%sSearching for: %s | %s | [id=%s]",
            request_tag,
            ("Missing episodes in" if "Missing" in arr.search_api_command else "All episodes in"),
            file_model.Title,
            file_model.EntryId,
        )
        context_label = arr._humanize_request_tag(request_tag)
        scope = "Missing episodes in" if "Missing" in arr.search_api_command else "All episodes in"
        description = f"{scope} {file_model.Title}"
        arr._record_search_activity(description, context=context_label)
        return True


def search_radarr(
    arr: Arr,
    file_model: MoviesFilesModel,
    *,
    request_tag: str,
    request: bool,
    todays: bool,
    bypass_limit: bool,
    series_search: bool,
    commands: int,
):
    """Radarr movie search command path."""
    del series_search  # unused for movies
    file_model: MoviesFilesModel
    if not (request or todays):
        (
            arr.model_queue.select(arr.model_queue.Completed)
            .where(arr.model_queue.EntryId == file_model.EntryId)
            .execute()
        )
    else:
        pass
    if file_model.EntryId in arr.queue_file_ids:
        arr.logger.debug(
            "%sSkipping: Already Searched: %s (%s)",
            request_tag,
            file_model.Title,
            file_model.EntryId,
        )
        arr.model_file.update(Searched=True, Upgrade=True).where(
            (arr.model_file.EntryId == file_model.EntryId)
            & (arr.model_file.ArrInstance == arr._name)
        ).execute()
        return True
    active_commands = arr.arr_db_query_commands_count()
    arr.logger.info("%s active search commands, %s remaining", active_commands, commands)
    if not bypass_limit and active_commands >= arr._get_search_command_limit():
        arr.logger.trace(
            "Idle: Too many commands in queue: %s | [id=%s]",
            file_model.Title,
            file_model.EntryId,
        )
        return False
    arr.persistent_queue.insert(
        EntryId=file_model.EntryId, ArrInstance=arr._name
    ).on_conflict_ignore().execute()

    arr.model_queue.insert(
        Completed=False, EntryId=file_model.EntryId, ArrInstance=arr._name
    ).on_conflict_replace().execute()
    if file_model.EntryId:
        with_retry(
            lambda: execute_command(arr.client, "MoviesSearch", movieIds=[file_model.EntryId]),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
    arr.model_file.update(Searched=True, Upgrade=True).where(
        (arr.model_file.EntryId == file_model.EntryId) & (arr.model_file.ArrInstance == arr._name)
    ).execute()
    reason_text = getattr(file_model, "Reason", None)
    if reason_text:
        arr.logger.hnotice(
            "%sSearching for: %s (%s) [tmdbId=%s|id=%s][%s]",
            request_tag,
            file_model.Title,
            file_model.Year,
            file_model.TmdbId,
            file_model.EntryId,
            reason_text,
        )
    else:
        arr.logger.hnotice(
            "%sSearching for: %s (%s) [tmdbId=%s|id=%s]",
            request_tag,
            file_model.Title,
            file_model.Year,
            file_model.TmdbId,
            file_model.EntryId,
        )
    context_label = arr._humanize_request_tag(request_tag)
    description = (
        f"{file_model.Title} ({file_model.Year})"
        if getattr(file_model, "Year", None)
        else f"{file_model.Title}"
    )
    arr._record_search_activity(
        description,
        context=context_label,
        detail=str(reason_text) if reason_text else None,
    )
    return True


def search_lidarr(
    arr: Arr,
    file_model: AlbumFilesModel,
    *,
    request_tag: str,
    request: bool,
    todays: bool,
    bypass_limit: bool,
    series_search: bool,
    commands: int,
):
    """Lidarr album search command path."""
    del series_search  # unused for albums
    file_model: AlbumFilesModel
    if not (request or todays):
        (
            arr.model_queue.select(arr.model_queue.Completed)
            .where(arr.model_queue.EntryId == file_model.EntryId)
            .execute()
        )
    else:
        pass
    if file_model.EntryId in arr.queue_file_ids:
        arr.logger.debug(
            "%sSkipping: Already Searched: %s - %s (%s)",
            request_tag,
            file_model.ArtistTitle,
            file_model.Title,
            file_model.EntryId,
        )
        arr.model_file.update(Searched=True, Upgrade=True).where(
            (arr.model_file.EntryId == file_model.EntryId)
            & (arr.model_file.ArrInstance == arr._name)
        ).execute()
        return True
    active_commands = arr.arr_db_query_commands_count()
    arr.logger.info("%s active search commands, %s remaining", active_commands, commands)
    if not bypass_limit and active_commands >= arr._get_search_command_limit():
        arr.logger.trace(
            "Idle: Too many commands in queue: %s - %s | [id=%s]",
            file_model.ArtistTitle,
            file_model.Title,
            file_model.EntryId,
        )
        return False
    arr.persistent_queue.insert(
        EntryId=file_model.EntryId, ArrInstance=arr._name
    ).on_conflict_ignore().execute()

    arr.model_queue.insert(
        Completed=False, EntryId=file_model.EntryId, ArrInstance=arr._name
    ).on_conflict_replace().execute()
    if file_model.EntryId:
        with_retry(
            lambda: execute_command(arr.client, "AlbumSearch", albumIds=[file_model.EntryId]),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
    arr.model_file.update(Searched=True, Upgrade=True).where(
        (arr.model_file.EntryId == file_model.EntryId) & (arr.model_file.ArrInstance == arr._name)
    ).execute()
    reason_text = getattr(file_model, "Reason", None)
    if reason_text:
        arr.logger.hnotice(
            "%sSearching for: %s - %s [foreignAlbumId=%s|id=%s][%s]",
            request_tag,
            file_model.ArtistTitle,
            file_model.Title,
            file_model.ForeignAlbumId,
            file_model.EntryId,
            reason_text,
        )
    else:
        arr.logger.hnotice(
            "%sSearching for: %s - %s [foreignAlbumId=%s|id=%s]",
            request_tag,
            file_model.ArtistTitle,
            file_model.Title,
            file_model.ForeignAlbumId,
            file_model.EntryId,
        )
    context_label = arr._humanize_request_tag(request_tag)
    description = f"{file_model.ArtistTitle} - {file_model.Title}"
    arr._record_search_activity(
        description,
        context=context_label,
        detail=str(reason_text) if reason_text else None,
    )
    return True
