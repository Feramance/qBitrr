"""Sonarr-specific Arr worker."""

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
    Sonarr,
    build_sonarr_client,
    execute_command,
)
from qBitrr.arss._shared import (
    _ARR_RETRY_EXCEPTIONS,
    _ARR_RETRY_EXCEPTIONS_EXTENDED,
    with_retry,
)
from qBitrr.arss.arr_type_config import sonarr_queue_id_field
from qBitrr.arss.base import ArrBase
from qBitrr.arss.db_update_handlers import (
    db_update_single_series,
    update_sonarr_episode,
    update_sonarr_series,
)
from qBitrr.arss.search_handlers import search_sonarr
from qBitrr.config import TAGLESS
from qBitrr.tables import (
    EpisodeFilesModel,
    EpisodeQueueModel,
    MoviesFilesModel,
    SeriesFilesModel,
    TorrentLibrary,
)

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
            client_builder = build_sonarr_client
        super().__init__(name, manager, client_builder=client_builder)

    def _db_get_files_impl(
        self,
    ) -> Iterable[tuple[EpisodeFilesModel | SeriesFilesModel, bool, bool, bool, int]]:
        from qBitrr.arss.db_queries import db_get_files_episodes, db_get_files_series

        if self.series_search is True:
            serieslist = db_get_files_series(self)
            if not serieslist:
                return
            for series in serieslist:
                yield series[0], series[1], series[2], series[2] is not True, len(serieslist)
            return

        if self.series_search == "smart":
            # Smart mode: decide dynamically based on what needs to be searched
            episodelist = db_get_files_episodes(self)
            if not episodelist:
                return
            # Group episodes by series to determine if we should search by series or episode
            series_episodes_map: dict[Any, list] = {}
            for episode_entry in episodelist:
                episode = episode_entry[0]
                series_id = episode.SeriesId
                if series_id not in series_episodes_map:
                    series_episodes_map[series_id] = []
                series_episodes_map[series_id].append(episode_entry)

            for series_id, episodes in series_episodes_map.items():
                if len(episodes) > 1:
                    self.logger.info(
                        "[SMART MODE] Using series search for %s episodes from series ID %s",
                        len(episodes),
                        series_id,
                    )
                    series_model = (
                        self.series_file_model.select()
                        .where(
                            (self.series_file_model.EntryId == series_id)
                            & (self.series_file_model.ArrInstance == self._name)
                        )
                        .first()
                    )
                    if series_model:
                        yield series_model, episodes[0][1], episodes[0][2], True, len(episodelist)
                else:
                    episode = episodes[0][0]
                    self.logger.info(
                        "[SMART MODE] Using episode search for single episode: %s S%02dE%03d",
                        episode.SeriesTitle,
                        episode.SeasonNumber,
                        episode.EpisodeNumber,
                    )
                    yield episodes[0][0], episodes[0][1], episodes[0][2], False, len(episodelist)
            return

        # series_search is False (episode search)
        episodelist = db_get_files_episodes(self)
        if not episodelist:
            return
        for episodes in episodelist:
            yield episodes[0], episodes[1], episodes[2], False, len(episodelist)

    def _db_maybe_reset_searched_state_impl(self) -> None:
        from qBitrr.arss.db_queries import (
            db_reset__episode_searched_state,
            db_reset__series_searched_state,
        )

        db_reset__series_searched_state(self)
        db_reset__episode_searched_state(self)

    def _db_get_request_files_impl(
        self,
    ) -> Iterable[tuple[MoviesFilesModel | EpisodeFilesModel, int]]:
        from qBitrr.arss.db_queries import db_get_request_files_sonarr

        return db_get_request_files_sonarr(self)

    def _overseerr_request_media_type(self) -> str | None:
        return "tv"

    def _add_overseerr_type_ids(self, media: dict, data: defaultdict) -> None:
        if tvdbId := media.get("tvdbId"):
            data["TvdbId"].add(tvdbId)

    def _overseerr_request_count(self) -> int:
        return len(
            self._temp_overseer_request_cache.get("TvdbId", [])
            or self._temp_overseer_request_cache.get("ImdbId", [])
        )

    def _ombi_request_total_path(self) -> str | None:
        return "/api/v1/Request/tv/total"

    def _ombi_request_list_path(self) -> str | None:
        return "/api/v1/Request/tvlite"

    def _ombi_should_include_request(self, request: dict) -> bool:
        if not self.ombi_approved_only:
            return True
        # Partial approvals are searchable when any child request is approved.
        children = request.get("childRequests") or []
        return any(child.get("denied") is not True for child in children)

    def _add_ombi_request_ids(self, request: dict, data: defaultdict) -> None:
        if tvDbId := request.get("tvDbId"):
            data["TvdbId"].add(tvDbId)

    def _db_request_update_impl(self, request_ids: dict[str, set[int | str]]) -> None:
        if not any(i in request_ids for i in ["ImdbId", "TvdbId"]):
            return
        TvdbIds = request_ids.get("TvdbId")
        ImdbIds = request_ids.get("ImdbId")
        series = with_retry(
            lambda: self.client.series.get(),
            retries=5,
            backoff=0.5,
            max_backoff=5,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
        for s in series:
            episodes = with_retry(
                lambda s=s: self.client.episode.get(series_id=s["id"]),
                retries=5,
                backoff=0.5,
                max_backoff=5,
                exceptions=_ARR_RETRY_EXCEPTIONS,
            )
            for e in episodes:
                if "airDateUtc" in e:
                    if datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc
                    ) > datetime.now(timezone.utc):
                        continue
                    if not self.search_specials and e["seasonNumber"] == 0:
                        continue
                    if TvdbIds and ImdbIds and "tvdbId" in e and "imdbId" in e:
                        if s["tvdbId"] not in TvdbIds or s["imdbId"] not in ImdbIds:
                            continue
                    if ImdbIds and "imdbId" in e:
                        if s["imdbId"] not in ImdbIds:
                            continue
                    if TvdbIds and "tvdbId" in e:
                        if s["tvdbId"] not in TvdbIds:
                            continue
                    if not e["monitored"]:
                        continue
                    if e["episodeFileId"] != 0:
                        continue
                    db_update_single_series(self, db_entry=e, request=True)

    def _iter_temp_profile_items(self) -> list[dict]:
        return self.client.series.get()

    def _temp_profile_item_label(self) -> str:
        return "series"

    def _update_item_quality_profile(self, item: dict) -> bool:
        return self._retry_profile_switch_update(
            lambda: self.client.series.update(data=item), "series"
        )

    def _temp_profile_db_model(self):
        return self.model_file

    def _temp_profile_timeout_entity_label(self) -> str:
        return "episode"

    def _reset_timed_out_temp_profile(self, db_item, original_profile: int) -> None:
        series = self.client.series.get(item_id=db_item.SeriesId)
        series["qualityProfileId"] = original_profile
        self.client.series.update(data=series)

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

    def build_queue_caches_from_queue(
        self, queue: list[dict[str, Any]]
    ) -> tuple[dict[Any, Any], set[Any]]:
        field = sonarr_queue_id_field(series_search=bool(self.series_search))
        requeue: dict[Any, set[Any]] = defaultdict(set)
        for entry in queue:
            if media_id := entry.get(field):
                requeue[entry["id"]].add(media_id)
        file_ids = {entry[field] for entry in queue if entry.get(field)}
        return requeue, file_ids

    def collect_years_for_search(self) -> list[int]:
        years_list: set[int] = set()
        series = with_retry(
            lambda: self.client.series.get(),
            retries=3,
            backoff=0.5,
            max_backoff=3,
            exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
        )
        for show in series:
            episodes = with_retry(
                lambda s=show: self.client.episode.get(series_id=s["id"]),
                retries=3,
                backoff=0.5,
                max_backoff=3,
                exceptions=_ARR_RETRY_EXCEPTIONS_EXTENDED,
            )
            for episode in episodes:
                if "airDateUtc" not in episode:
                    continue
                if not self.search_specials and episode["seasonNumber"] == 0:
                    continue
                if not episode["monitored"]:
                    continue
                years_list.add(
                    datetime.strptime(episode["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ")
                    .replace(tzinfo=timezone.utc)
                    .year
                )
        ordered = dict.fromkeys(years_list)
        reverse = bool(getattr(self, "search_in_reverse", False))
        return [
            key for key, _ in sorted(ordered.items(), key=lambda item: item[0], reverse=reverse)
        ]

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

    def _db_update_single_entry(
        self,
        db_entry: JsonObject,
        *,
        request: bool = False,
        series: bool = False,
        artist: bool = False,
    ) -> None:
        del artist
        if not series:
            update_sonarr_episode(self, db_entry, request=request)
        else:
            update_sonarr_series(self, db_entry)

    def _log_db_update_json_error(
        self, db_entry: JsonObject, *, series: bool = False, artist: bool = False
    ) -> None:
        del artist
        if self.series_search or series:
            self.logger.warning(
                "Error getting series info: [%s][%s]", db_entry["id"], db_entry.get("title")
            )
        else:
            self.logger.warning(
                "Error getting episode info: [%s][%s]", db_entry["id"], db_entry.get("title")
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
        return search_sonarr(
            self,
            file_model,
            request_tag=request_tag,
            request=request,
            todays=todays,
            bypass_limit=bypass_limit,
            series_search=series_search,
            commands=commands,
        )
