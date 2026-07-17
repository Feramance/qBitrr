"""Sonarr-specific Arr worker."""

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
    EpisodeFilesModel,
    EpisodeQueueModel,
    PyarrResourceNotFound,
    SeriesFilesModel,
    Sonarr,
    TorrentLibrary,
    execute_command,
    with_retry,
)
from qBitrr.arss.arr_type_config import collect_years_for_search as _collect_years_for_search
from qBitrr.arss.base import ArrBase

if TYPE_CHECKING:
    from qBitrr.arss.manager import ArrManager


class SonarrArr(ArrBase):
    """Sonarr worker: series/episode search DB, queue fields, and re-search."""

    arr_type = "sonarr"

    def __init__(
        self,
        name: str,
        manager: ArrManager,
        client_builder: Callable[..., Sonarr] | None = None,
    ):
        if client_builder is None:
            from qBitrr.arss._shared import build_sonarr_client

            client_builder = build_sonarr_client
        super().__init__(name, manager, client_builder=client_builder)

    def _init_search_api_command(self) -> None:
        if (
            self.quality_unmet_search
            or self.do_upgrade_search
            or self.custom_format_unmet_search
            or self.series_search is True
        ):
            self.search_api_command = "SeriesSearch"
        elif self.series_search == "smart":
            # In smart mode, the command will be determined dynamically
            self.search_api_command = "SeriesSearch"  # Default, will be overridden per search
        else:
            self.search_api_command = "MissingEpisodeSearch"

    def _db_update_todays_releases(self) -> None:
        try:
            series = with_retry(
                lambda: self.client.series.get(),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
            for s in series:
                episodes = self.client.episode.get(series_id=s["id"])
                for e in episodes:
                    if "airDateUtc" in e:
                        if (
                            datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ")
                            .replace(tzinfo=timezone.utc)
                            .date()
                            > datetime.now(timezone.utc).date()
                            or datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ")
                            .replace(tzinfo=timezone.utc)
                            .date()
                            < datetime.now(timezone.utc).date()
                        ):
                            continue
                        if not self.search_specials and e["seasonNumber"] == 0:
                            continue
                        if not e["monitored"]:
                            continue
                        if e["episodeFileId"] != 0:
                            continue
                        self.logger.trace("Updating todays releases")
                        self.db_update_single_series(db_entry=e)
        except Exception:
            self.logger.debug("No episode releases found for today")

    def _db_update_media(self) -> None:
        # Always fetch series list for both episode and series-level tracking
        series = with_retry(
            lambda: self.client.series.get(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
        )

        # Process episodes for episode-level tracking (all episodes)
        for s in series:
            if isinstance(s, str):
                continue
            episodes = with_retry(
                lambda sid=s["id"]: self.client.episode.get(series_id=sid),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
            )
            for e in episodes:
                if isinstance(e, str):
                    continue
                if "airDateUtc" in e:
                    if datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc
                    ) > datetime.now(timezone.utc):
                        continue
                    if not self.search_specials and e["seasonNumber"] == 0:
                        continue
                    self.db_update_single_series(db_entry=e, series=False)

        # Process series for series-level tracking (all series)
        for s in series:
            if isinstance(s, str):
                continue
            self.db_update_single_series(db_entry=s, series=True)

        self.db_update_processed = True

    def _bind_type_specific_models(self, series_or_artist_model, track_model) -> None:
        self.series_file_model = series_or_artist_model
        self.artists_file_model = None
        self.track_file_model = None

    def _get_models(self):
        return (
            EpisodeFilesModel,
            EpisodeQueueModel,
            SeriesFilesModel,
            None,
            TorrentLibrary if TAGLESS else None,
        )

    def _custom_format_queue_fields(self) -> tuple[str, str | None] | None:
        if self.series_search:
            return "seriesId", None
        return "episodeId", "EpisodeFileId"

    def collect_years_for_search(self) -> list[int]:
        return _collect_years_for_search(self)

    def _re_search_failed_media(self, object_id: Any) -> None:
        object_ids = list(object_id)
        self.logger.trace("Requeue cache entry list: %s", object_ids)
        if self.series_search:
            series_id = None
            try:
                data = with_retry(
                    lambda: self.client.series.get(item_id=object_ids[0]),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )
                name = data["title"]
                series_id = data["id"]
                if name:
                    year = data.get("year", 0)
                    tvdbId = data.get("tvdbId", 0)
                    self.logger.notice(
                        "Re-Searching series: %s (%s) | [tvdbId=%s|id=%s]",
                        name,
                        year,
                        tvdbId,
                        series_id,
                    )
                else:
                    self.logger.notice("Re-Searching series: %s", series_id)
            except PyarrResourceNotFound as e:
                self.logger.warning(
                    "Series %s not found in Sonarr (likely removed): %s",
                    object_ids[0],
                    str(e),
                )
            for object_id in object_ids:
                if object_id in self.queue_file_ids:
                    self.queue_file_ids.remove(object_id)
            if series_id:
                self.logger.trace("Research series id: %s", series_id)
                with_retry(
                    lambda sid=series_id: execute_command(
                        self.client, self.search_api_command, seriesId=sid
                    ),
                    retries=5,
                    backoff=0.5,
                    max_backoff=5,
                    exceptions=_ARR_RETRY_EXCEPTIONS,
                )
                if self.persistent_queue:
                    self.persistent_queue.insert(
                        EntryId=series_id, ArrInstance=self._name
                    ).on_conflict_ignore()
        else:
            for object_id in object_ids:
                episode_found = False
                try:
                    data = with_retry(
                        lambda oid=object_id: self.client.episode.get(item_id=oid),
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
                    series_id = data.get("series", {}).get("id")
                    if name:
                        episodeNumber = data.get("episodeNumber", 0)
                        absoluteEpisodeNumber = data.get("absoluteEpisodeNumber", 0)
                        seasonNumber = data.get("seasonNumber", 0)
                        seriesTitle = data.get("series", {}).get("title")
                        year = data.get("series", {}).get("year", 0)
                        tvdbId = data.get("series", {}).get("tvdbId", 0)
                        self.logger.notice(
                            "Re-Searching episode: %s (%s) | "
                            "S%02dE%03d "
                            "(E%04d) | "
                            "%s | "
                            "[tvdbId=%s|id=%s]",
                            seriesTitle,
                            year,
                            seasonNumber,
                            episodeNumber,
                            absoluteEpisodeNumber,
                            name,
                            tvdbId,
                            object_id,
                        )
                    else:
                        self.logger.notice("Re-Searching episode: %s", object_id)
                    episode_found = True
                except PyarrResourceNotFound as e:
                    self.logger.warning(
                        "Episode %s not found in Sonarr (likely removed): %s",
                        object_id,
                        str(e),
                    )

                if object_id in self.queue_file_ids:
                    self.queue_file_ids.remove(object_id)
                if episode_found:
                    with_retry(
                        lambda oid=object_id: execute_command(
                            self.client, "EpisodeSearch", episodeIds=[oid]
                        ),
                        retries=5,
                        backoff=0.5,
                        max_backoff=5,
                        exceptions=_ARR_RETRY_EXCEPTIONS,
                    )
                    if self.persistent_queue:
                        self.persistent_queue.insert(
                            EntryId=object_id, ArrInstance=self._name
                        ).on_conflict_ignore()
