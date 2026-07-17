"""Radarr-specific Arr worker."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import requests
from ujson import JSONDecodeError

from qBitrr.arss._shared import (
    _ARR_RETRY_EXCEPTIONS,
    _ARR_RETRY_EXCEPTIONS_EXTENDED,
    TAGLESS,
    MovieQueueModel,
    MoviesFilesModel,
    PyarrResourceNotFound,
    Radarr,
    TorrentLibrary,
    execute_command,
    with_retry,
)
from qBitrr.arss.arr_type_config import collect_years_for_search as _collect_years_for_search
from qBitrr.arss.base import ArrBase

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
            from qBitrr.arss._shared import build_radarr_client

            client_builder = build_radarr_client
        super().__init__(name, manager, client_builder=client_builder)

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

    def collect_years_for_search(self) -> list[int]:
        return _collect_years_for_search(self)

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
