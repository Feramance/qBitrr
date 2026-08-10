"""Lidarr-specific Arr worker."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import requests
from ujson import JSONDecodeError

from qBitrr.arr_client import (
    JsonObject,
    Lidarr,
    PyarrResourceNotFound,
    build_lidarr_client,
    execute_command,
)
from qBitrr.arss.arr_base import ArrBase
from qBitrr.arss.arr_shared import (
    _ARR_RETRY_EXCEPTIONS,
    _ARR_RETRY_EXCEPTIONS_EXTENDED,
    with_retry,
)
from qBitrr.arss.db_update_handlers import update_lidarr_album, update_lidarr_artist
from qBitrr.arss.search_handlers import search_lidarr
from qBitrr.config import TAGLESS
from qBitrr.tables import (
    AlbumFilesModel,
    AlbumQueueModel,
    ArtistFilesModel,
    TorrentLibrary,
    TrackFilesModel,
)

if TYPE_CHECKING:
    from qBitrr.arss.manager import ArrManager


class LidarrArr(ArrBase):
    """Lidarr worker: album/artist search DB, queue fields, and re-search."""

    arr_type = "lidarr"

    def __init__(
        self,
        name: str,
        manager: ArrManager,
        client_builder: Callable[..., Lidarr] | None = None,
    ):
        if client_builder is None:
            client_builder = build_lidarr_client
        super().__init__(name, manager, client_builder=client_builder)

    def _apply_type_feature_gates(self) -> None:
        self.search_by_year = False
        self.ombi_search_requests = False
        self.overseerr_requests = False
        self.ombi_uri = None
        self.ombi_api_key = None
        self.overseerr_uri = None
        self.overseerr_api_key = None

    def _db_get_files_impl(
        self,
    ) -> Iterable[tuple[AlbumFilesModel, bool, bool, bool, int]]:
        from qBitrr.arss.db_queries import db_get_files_albums

        albumlist = db_get_files_albums(self)
        if not albumlist:
            return
        for albums in albumlist:
            yield albums[0], albums[1], albums[2], False, len(albumlist)

    def _db_maybe_reset_searched_state_impl(self) -> None:
        from qBitrr.arss.db_queries import db_reset__album_searched_state

        db_reset__album_searched_state(self)

    def _iter_temp_profile_items(self) -> list[dict]:
        return self.client.artist.get()

    def _temp_profile_item_label(self) -> str:
        return "artist"

    def _update_item_quality_profile(self, item: dict) -> bool:
        return self._retry_profile_switch_update(
            lambda: self.client.artist.update(data=item), "artist"
        )

    def _temp_profile_db_model(self):
        return self.artists_file_model

    def _temp_profile_timeout_entity_label(self) -> str:
        return "artist"

    def _reset_timed_out_temp_profile(self, db_item, original_profile: int) -> None:
        artist = self.client.artist.get(item_id=db_item.EntryId)
        artist["qualityProfileId"] = original_profile
        self.client.artist.update(data=artist)

    def _db_update_media(self) -> None:
        artists = with_retry(
            lambda: self.client.artist.get(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
        )
        for artist in artists:
            if isinstance(artist, str):
                continue
            albums = with_retry(
                lambda a=artist: self.client.album.get(artist_id=a["id"], all_artist_albums=True),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
            )
            for album in albums:
                if isinstance(album, str):
                    continue
                # For Lidarr, we don't have a specific releaseDate field
                # Check if album has been released
                if "releaseDate" in album:
                    release_date = datetime.strptime(
                        album["releaseDate"], "%Y-%m-%dT%H:%M:%SZ"
                    ).replace(tzinfo=timezone.utc)
                    if release_date > datetime.now(timezone.utc):
                        continue
                self.db_update_single_series(db_entry=album)
        # Process artists for artist-level tracking
        for artist in artists:
            if isinstance(artist, str):
                continue
            self.db_update_single_series(db_entry=artist, artist=True)
        self.db_update_processed = True

    def _bind_type_specific_models(self, series_or_artist_model, track_model) -> None:
        self.series_file_model = None
        self.artists_file_model = series_or_artist_model
        self.track_file_model = track_model

    def _get_models(self):
        return (
            AlbumFilesModel,
            AlbumQueueModel,
            ArtistFilesModel,
            TrackFilesModel,
            TorrentLibrary if TAGLESS else None,
        )

    def _custom_format_queue_fields(self) -> tuple[str, str | None] | None:
        return "albumId", "AlbumFileId"

    def build_queue_caches_from_queue(
        self, queue: list[dict[str, Any]]
    ) -> tuple[dict[Any, Any], set[Any]]:
        field = "albumId"
        requeue_map = {entry["id"]: entry[field] for entry in queue if entry.get(field)}
        file_ids = {entry[field] for entry in queue if entry.get(field)}
        return requeue_map, file_ids

    def _re_search_failed_media(self, object_id: Any) -> None:
        self.logger.trace("Requeue cache entry: %s", object_id)
        album_found = False
        try:
            data = with_retry(
                lambda: self.client.album.get(item_id=object_id),
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
                artist_title = data.get("artist", {}).get("artistName", "")
                foreign_album_id = data.get("foreignAlbumId", "")
                self.logger.notice(
                    "Re-Searching album: %s - %s | [foreignAlbumId=%s|id=%s]",
                    artist_title,
                    name,
                    foreign_album_id,
                    object_id,
                )
            else:
                self.logger.notice("Re-Searching album: %s", object_id)
            album_found = True
        except PyarrResourceNotFound as e:
            self.logger.warning(
                "Album %s not found in Lidarr (likely removed): %s", object_id, str(e)
            )
        if object_id in self.queue_file_ids:
            self.queue_file_ids.remove(object_id)
        if album_found:
            with_retry(
                lambda: execute_command(self.client, "AlbumSearch", albumIds=[object_id]),
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
            update_lidarr_album(self, db_entry, request=request)
        else:
            update_lidarr_artist(self, db_entry)

    def _log_db_update_json_error(
        self, db_entry: JsonObject, *, series: bool = False, artist: bool = False
    ) -> None:
        # Historical behavior: Lidarr had no JSONDecodeError warning branch.
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
        return search_lidarr(
            self,
            file_model,
            request_tag=request_tag,
            request=request,
            todays=todays,
            bypass_limit=bypass_limit,
            series_search=series_search,
            commands=commands,
        )
