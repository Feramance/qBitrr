"""Readarr-specific Arr worker."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import requests
from ujson import JSONDecodeError

from qBitrr.arr_client import (
    JsonObject,
    PyarrResourceNotFound,
    Readarr,
    build_readarr_client,
    execute_command,
)
from qBitrr.arss.arr_base import ArrBase
from qBitrr.arss.arr_shared import (
    _ARR_RETRY_EXCEPTIONS,
    _ARR_RETRY_EXCEPTIONS_EXTENDED,
    with_retry,
)
from qBitrr.arss.db_update_handlers import (
    _readarr_release_is_future,
    _readarr_release_year,
    update_readarr_author,
    update_readarr_book,
)
from qBitrr.arss.search_handlers import search_readarr
from qBitrr.config import TAGLESS
from qBitrr.tables import (
    AuthorFilesModel,
    BookFilesModel,
    BookQueueModel,
    TorrentLibrary,
)

if TYPE_CHECKING:
    from qBitrr.arss.manager import ArrManager


class ReadarrArr(ArrBase):
    """Readarr worker: book/author search DB, queue fields, and re-search."""

    arr_type = "readarr"

    def __init__(
        self,
        name: str,
        manager: ArrManager,
        client_builder: Callable[..., Readarr] | None = None,
    ):
        if client_builder is None:
            client_builder = build_readarr_client
        super().__init__(name, manager, client_builder=client_builder)

    def _apply_type_feature_gates(self) -> None:
        self.ombi_search_requests = False
        self.overseerr_requests = False
        self.ombi_uri = None
        self.ombi_api_key = None
        self.overseerr_uri = None
        self.overseerr_api_key = None

    def _db_get_files_impl(
        self,
    ) -> Iterable[tuple[BookFilesModel, bool, bool, bool, int]]:
        from qBitrr.arss.db_queries import db_get_files_books

        booklist = db_get_files_books(self)
        if not booklist:
            return
        for books in booklist:
            yield books[0], books[1], books[2], False, len(booklist)

    def _db_maybe_reset_searched_state_impl(self) -> None:
        from qBitrr.arss.db_queries import db_reset__book_searched_state

        db_reset__book_searched_state(self)

    def _iter_temp_profile_items(self) -> list[dict]:
        return self.client.author.get()

    def _temp_profile_item_label(self) -> str:
        return "author"

    def _update_item_quality_profile(self, item: dict) -> bool:
        item_id = item.get("id")
        if item_id is None:
            return False
        return self._retry_profile_switch_update(
            lambda: self.client.author.update(item_id, item), "author"
        )

    def _temp_profile_db_model(self):
        return self.artists_file_model

    def _temp_profile_timeout_entity_label(self) -> str:
        return "author"

    def _reset_timed_out_temp_profile(self, db_item, original_profile: int) -> None:
        author = self.client.author.get(item_id=db_item.EntryId)
        author["qualityProfileId"] = original_profile
        self.client.author.update(db_item.EntryId, author)

    def _db_update_media(self) -> None:
        authors = with_retry(
            lambda: self.client.author.get(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
        )
        self._readarr_author_profile_cache = {
            author["id"]: author
            for author in authors
            if isinstance(author, dict) and author.get("id") is not None
        }
        books = with_retry(
            lambda: self.client.book.get(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
        )
        for book in books:
            if isinstance(book, str):
                continue
            release_date = book.get("releaseDate")
            if release_date and _readarr_release_is_future(release_date):
                continue
            self.db_update_single_series(db_entry=book)
        for author in authors:
            if isinstance(author, str):
                continue
            self.db_update_single_series(db_entry=author, artist=True)
        self.db_update_processed = True

    def _bind_type_specific_models(self, series_or_artist_model, track_model) -> None:
        del track_model
        self.series_file_model = None
        self.artists_file_model = series_or_artist_model
        self.track_file_model = None

    def _get_models(self):
        return (
            BookFilesModel,
            BookQueueModel,
            AuthorFilesModel,
            None,
            TorrentLibrary if TAGLESS else None,
        )

    def _custom_format_queue_fields(self) -> tuple[str, str | None] | None:
        return "bookId", "BookFileId"

    def build_queue_caches_from_queue(
        self, queue: list[dict[str, Any]]
    ) -> tuple[dict[Any, Any], set[Any]]:
        field = "bookId"
        requeue_map = {entry["id"]: entry[field] for entry in queue if entry.get(field)}
        file_ids = {entry[field] for entry in queue if entry.get(field)}
        return requeue_map, file_ids

    def collect_years_for_search(self) -> list[int]:
        years_list: set[int] = set()
        books = with_retry(
            lambda: self.client.book.get(),
            retries=3,
            backoff=0.5,
            max_backoff=3,
            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
        )
        now_year = datetime.now(timezone.utc).year
        for book in books:
            if not isinstance(book, dict) or not book.get("monitored"):
                continue
            year = _readarr_release_year(book.get("releaseDate"))
            if year is None or year == 0 or year > now_year:
                continue
            years_list.add(year)
        ordered = dict.fromkeys(years_list)
        reverse = bool(getattr(self, "search_in_reverse", False))
        return [
            key for key, _ in sorted(ordered.items(), key=lambda item: item[0], reverse=reverse)
        ]

    def _re_search_failed_media(self, object_id: Any) -> None:
        self.logger.trace("Requeue cache entry: %s", object_id)
        book_found = False
        try:
            data = with_retry(
                lambda: self.client.book.get(item_id=object_id),
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
                author_title = data.get("authorTitle") or data.get("author", {}).get(
                    "authorName", ""
                )
                foreign_book_id = data.get("foreignBookId", "")
                self.logger.notice(
                    "Re-Searching book: %s - %s | [foreignBookId=%s|id=%s]",
                    author_title,
                    name,
                    foreign_book_id,
                    object_id,
                )
            else:
                self.logger.notice("Re-Searching book: %s", object_id)
            book_found = True
        except PyarrResourceNotFound as e:
            self.logger.warning(
                "Book %s not found in Readarr (likely removed): %s", object_id, str(e)
            )
        if object_id in self.queue_file_ids:
            self.queue_file_ids.remove(object_id)
        if book_found:
            with_retry(
                lambda: execute_command(self.client, "BookSearch", bookIds=[object_id]),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
            if self.persistent_queue:
                self.persistent_queue.insert(
                    EntryId=object_id, ArrInstance=self._name
                ).on_conflict_ignore().execute()

    def _db_update_single_entry(
        self,
        db_entry: JsonObject,
        *,
        request: bool = False,
        series: bool = False,
        artist: bool = False,
    ) -> None:
        del series
        if not artist:
            update_readarr_book(self, db_entry, request=request)
        else:
            update_readarr_author(self, db_entry)

    def _log_db_update_json_error(
        self, db_entry: JsonObject, *, series: bool = False, artist: bool = False
    ) -> None:
        del db_entry, series, artist

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
        return search_readarr(
            self,
            file_model,
            request_tag=request_tag,
            request=request,
            todays=todays,
            bypass_limit=bypass_limit,
            series_search=series_search,
            commands=commands,
        )
