"""Radarr-specific Arr worker."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import requests
from ujson import JSONDecodeError

from qBitrr.arr_client import (
    JsonObject,
    PyarrResourceNotFound,
    Radarr,
    build_radarr_client,
    execute_command,
)
from qBitrr.arss.arr_base import ArrBase
from qBitrr.arss.arr_shared import (
    _ARR_RETRY_EXCEPTIONS,
    _ARR_RETRY_EXCEPTIONS_EXTENDED,
    with_retry,
)
from qBitrr.arss.db_update_handlers import db_update_single_series, update_radarr_entry
from qBitrr.arss.search_handlers import search_radarr
from qBitrr.config import TAGLESS
from qBitrr.tables import EpisodeFilesModel, MovieQueueModel, MoviesFilesModel, TorrentLibrary

if TYPE_CHECKING:
    from qBitrr.arss.manager import ArrManager


class RadarrArr(ArrBase):
    """Radarr worker: movie search DB, queue fields, and re-search."""

    arr_type = "radarr"

    def __init__(
        self,
        name: str,
        manager: ArrManager,
        client_builder: Callable[..., Radarr] | None = None,
    ):
        if client_builder is None:
            client_builder = build_radarr_client
        super().__init__(name, manager, client_builder=client_builder)

    def _db_get_files_impl(
        self,
    ) -> Iterable[tuple[MoviesFilesModel, bool, bool, bool, int]]:
        from qBitrr.arss.db_queries import db_get_files_movies

        movielist = db_get_files_movies(self)
        if not movielist:
            return
        for movies in movielist:
            yield movies[0], movies[1], movies[2], False, len(movielist)

    def _db_maybe_reset_searched_state_impl(self) -> None:
        from qBitrr.arss.db_queries import db_reset__movie_searched_state

        db_reset__movie_searched_state(self)

    def _db_get_request_files_impl(
        self,
    ) -> Iterable[tuple[MoviesFilesModel | EpisodeFilesModel, int]]:
        from qBitrr.arss.db_queries import db_get_request_files_radarr

        return db_get_request_files_radarr(self)

    def _overseerr_request_media_type(self) -> str | None:
        return "movie"

    def _add_overseerr_type_ids(self, media: dict, data: defaultdict) -> None:
        if tmdbId := media.get("tmdbId"):
            data["TmdbId"].add(tmdbId)

    def _overseerr_request_count(self) -> int:
        return len(
            self._temp_overseer_request_cache.get("ImdbId", [])
            or self._temp_overseer_request_cache.get("TmdbId", [])
        )

    def _ombi_request_total_path(self) -> str | None:
        return "/api/v1/Request/movie/total"

    def _ombi_request_list_path(self) -> str | None:
        return "/api/v1/Request/movie"

    def _ombi_should_include_request(self, request: dict) -> bool:
        if self.ombi_approved_only and request.get("denied") is True:
            return False
        return True

    def _add_ombi_request_ids(self, request: dict, data: defaultdict) -> None:
        if theMovieDbId := request.get("theMovieDbId"):
            data["TmdbId"].add(theMovieDbId)

    def _db_request_update_impl(self, request_ids: dict[str, set[int | str]]) -> None:
        if not any(i in request_ids for i in ["ImdbId", "TmdbId"]):
            return
        ImdbIds = request_ids.get("ImdbId")
        TmdbIds = request_ids.get("TmdbId")
        movies = with_retry(
            lambda: self.client.movie.get(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
        for m in movies:
            if m["year"] > datetime.now().year or m["year"] == 0:
                continue
            if TmdbIds and ImdbIds and "tmdbId" in m and "imdbId" in m:
                if m["tmdbId"] not in TmdbIds or m["imdbId"] not in ImdbIds:
                    continue
            if ImdbIds and "imdbId" in m:
                if m["imdbId"] not in ImdbIds:
                    continue
            if TmdbIds and "tmdbId" in m:
                if m["tmdbId"] not in TmdbIds:
                    continue
            if not m["monitored"]:
                continue
            if m["hasFile"]:
                continue
            db_update_single_series(self, db_entry=m, request=True)

    def _iter_temp_profile_items(self) -> list[dict]:
        return self.client.movie.get()

    def _temp_profile_item_label(self) -> str:
        return "movie"

    def _update_item_quality_profile(self, item: dict) -> bool:
        return self._retry_profile_switch_update(
            lambda: self.client.movie.update(data=item), "movie"
        )

    def _temp_profile_db_model(self):
        return self.model_file

    def _temp_profile_timeout_entity_label(self) -> str:
        return "movie"

    def _reset_timed_out_temp_profile(self, db_item, original_profile: int) -> None:
        item = self.client.movie.get(item_id=db_item.EntryId)
        item["qualityProfileId"] = original_profile
        self.client.movie.update(data=item)

    def _db_update_media(self) -> None:
        movies = with_retry(
            lambda: self.client.movie.get(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
        )
        # Process all movies
        for m in movies:
            if isinstance(m, str):
                continue
            self.db_update_single_series(db_entry=m)
        self.db_update_processed = True

    def _bind_type_specific_models(self, series_or_artist_model, track_model) -> None:
        self.series_file_model = None
        self.artists_file_model = None
        self.track_file_model = None

    def _get_models(self):
        return (
            MoviesFilesModel,
            MovieQueueModel,
            None,
            None,
            TorrentLibrary if TAGLESS else None,
        )

    def _custom_format_queue_fields(self) -> tuple[str, str | None] | None:
        return "movieId", "MovieFileId"

    def build_queue_caches_from_queue(
        self, queue: list[dict[str, Any]]
    ) -> tuple[dict[Any, Any], set[Any]]:
        field = "movieId"
        requeue_map = {entry["id"]: entry[field] for entry in queue if entry.get(field)}
        file_ids = {entry[field] for entry in queue if entry.get(field)}
        return requeue_map, file_ids

    def collect_years_for_search(self) -> list[int]:
        years_list: set[int] = set()
        movies = with_retry(
            lambda: self.client.movie.get(),
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
        ordered = dict.fromkeys(years_list)
        reverse = bool(getattr(self, "search_in_reverse", False))
        return [
            key for key, _ in sorted(ordered.items(), key=lambda item: item[0], reverse=reverse)
        ]

    def _re_search_failed_media(self, object_id: Any) -> None:
        self.logger.trace("Requeue cache entry: %s", object_id)
        movie_found = False
        try:
            data = with_retry(
                lambda: self.client.movie.get(item_id=object_id),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=(
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.ContentDecodingError,
                    requests.exceptions.ConnectionError,
                    JSONDecodeError,
                    AttributeError,
                ),
            )
            name = data.get("title")
            if name:
                year = data.get("year", 0)
                tmdbId = data.get("tmdbId", 0)
                self.logger.notice(
                    "Re-Searching movie: %s (%s) | [tmdbId=%s|id=%s]",
                    name,
                    year,
                    tmdbId,
                    object_id,
                )
            else:
                self.logger.notice("Re-Searching movie: %s", object_id)
            movie_found = True
        except PyarrResourceNotFound as e:
            self.logger.warning(
                "Movie %s not found in Radarr (likely removed): %s", object_id, str(e)
            )
        if object_id in self.queue_file_ids:
            self.queue_file_ids.remove(object_id)
        if movie_found:
            with_retry(
                lambda: execute_command(self.client, "MoviesSearch", movieIds=[object_id]),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
            if self.persistent_queue:
                self.persistent_queue.insert(
                    EntryId=object_id, ArrInstance=self._name
                ).on_conflict_ignore()

    def _db_update_single_entry(
        self,
        db_entry: JsonObject,
        *,
        request: bool = False,
        series: bool = False,
        artist: bool = False,
    ) -> None:
        del series, artist
        update_radarr_entry(self, db_entry, request=request)

    def _log_db_update_json_error(
        self, db_entry: JsonObject, *, series: bool = False, artist: bool = False
    ) -> None:
        del series, artist
        self.logger.warning(
            "Error getting movie info: [%s][%s]", db_entry["id"], db_entry.get("path")
        )

    def _maybe_do_search_impl(
        self,
        file_model,
        *,
        request_tag: str,
        request: bool,
        todays: bool,
        bypass_limit: bool,
        series_search: bool,
        commands: int,
    ):
        return search_radarr(
            self,
            file_model,
            request_tag=request_tag,
            request=request,
            todays=todays,
            bypass_limit=bypass_limit,
            series_search=series_search,
            commands=commands,
        )
