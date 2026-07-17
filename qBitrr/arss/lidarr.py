"""Lidarr-specific Arr worker."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import requests
from ujson import JSONDecodeError

from qBitrr.arss._shared import (
    _ARR_RETRY_EXCEPTIONS,
    _ARR_RETRY_EXCEPTIONS_EXTENDED,
    TAGLESS,
    AlbumFilesModel,
    AlbumQueueModel,
    ArtistFilesModel,
    Lidarr,
    PyarrResourceNotFound,
    TorrentLibrary,
    TrackFilesModel,
    execute_command,
    with_retry,
)
from qBitrr.arss.base import ArrBase

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
            from qBitrr.arss._shared import build_lidarr_client

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
                ).on_conflict_ignore()
