"""Ombi/Overseerr request fetch and DB update helpers (split from Arr)."""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import requests

from qBitrr.arss._shared import (
    _ARR_RETRY_EXCEPTIONS,
    UnhandledError,
    _is_media_available,
    _is_media_processing,
    _normalize_media_status,
    with_retry,
)
from qBitrr.arss.db_update_handlers import db_update_single_series

if TYPE_CHECKING:
    pass


def _get_oversee_requests_all(arr) -> dict[str, set]:
    try:
        data = defaultdict(set)
        key = "approved" if arr.overseerr_approved_only else "unavailable"
        take = 100
        skip = 0
        type_ = None
        if arr.type == "radarr":
            type_ = "movie"
        elif arr.type == "sonarr":
            type_ = "tv"
        _now = datetime.now(timezone.utc)
        while True:
            response = arr.session.get(
                url=f"{arr.overseerr_uri}/api/v1/request",
                headers={"X-Api-Key": arr.overseerr_api_key},
                params={"take": take, "skip": skip, "sort": "added", "filter": key},
                timeout=5,
                verify=not arr.skip_tls_verify_overseerr,
            )
            response.raise_for_status()
            payload = response.json()
            results = []
            if isinstance(payload, list):
                results = payload
            elif isinstance(payload, dict):
                if isinstance(payload.get("results"), list):
                    results = payload["results"]
                elif isinstance(payload.get("data"), list):
                    results = payload["data"]
            if not results:
                break
            for entry in results:
                # NOTE: 'type' field is not documented in official Overseerr API spec
                # but exists in practice. May break if Overseerr changes API.
                type__ = entry.get("type")
                if not type__:
                    arr.logger.debug(
                        "Overseerr request missing 'type' field (entry ID: %s). "
                        "This may indicate an API change.",
                        entry.get("id", "unknown"),
                    )
                    continue
                if type__ == "movie":
                    id__ = entry.get("media", {}).get("tmdbId")
                elif type__ == "tv":
                    # Overseerr's /api/v1/tv/{id} takes a TMDB id, not a TVDB id
                    # (same as /api/v1/movie/{id}); `media` carries both.
                    id__ = entry.get("media", {}).get("tmdbId")
                else:
                    id__ = None
                if not id__ or type_ != type__:
                    continue
                media = entry.get("media") or {}
                # NOTE: 'status4k' field is not documented in official Overseerr API spec
                # but exists for 4K request tracking. Falls back to 'status' for non-4K.
                status_key = "status4k" if entry.get("is4k") else "status"
                status_value = _normalize_media_status(media.get(status_key))
                if entry.get("is4k"):
                    if not arr.overseerr_is_4k:
                        continue
                elif arr.overseerr_is_4k:
                    continue
                if arr.overseerr_approved_only:
                    if not _is_media_processing(status_value):
                        continue
                else:
                    if _is_media_available(status_value):
                        continue
                if id__ in arr.overseerr_requests_release_cache:
                    date = arr.overseerr_requests_release_cache[id__]
                else:
                    date = datetime(day=1, month=1, year=1970)
                    date_string_backup = f"{_now.year}-{_now.month:02}-{_now.day:02}"
                    date_string = None
                    try:
                        if type_ == "movie":
                            _entry = arr.session.get(
                                url=f"{arr.overseerr_uri}/api/v1/movie/{id__}",
                                headers={"X-Api-Key": arr.overseerr_api_key},
                                timeout=5,
                                verify=not arr.skip_tls_verify_overseerr,
                            )
                            _entry.raise_for_status()
                            date_string = _entry.json().get("releaseDate")
                        elif type__ == "tv":
                            _entry = arr.session.get(
                                url=f"{arr.overseerr_uri}/api/v1/tv/{id__}",
                                headers={"X-Api-Key": arr.overseerr_api_key},
                                timeout=5,
                                verify=not arr.skip_tls_verify_overseerr,
                            )
                            _entry.raise_for_status()
                            # We don't do granular (episode/season) searched here so no need to
                            # suppose them
                            date_string = _entry.json().get("firstAirDate")
                        if not date_string:
                            date_string = date_string_backup
                        date = datetime.strptime(date_string[:10], "%Y-%m-%d").replace(
                            tzinfo=timezone.utc
                        )
                        if date > _now:
                            continue
                        arr.overseerr_requests_release_cache[id__] = date
                    except Exception as e:
                        arr.logger.warning("Failed to query release date from Overseerr: %s", e)
                if media:
                    if imdbId := media.get("imdbId"):
                        data["ImdbId"].add(imdbId)
                    if arr.type == "sonarr" and (tvdbId := media.get("tvdbId")):
                        data["TvdbId"].add(tvdbId)
                    elif arr.type == "radarr" and (tmdbId := media.get("tmdbId")):
                        data["TmdbId"].add(tmdbId)
            if len(results) < take:
                break
            skip += take
        arr._temp_overseer_request_cache = data
    except requests.exceptions.ConnectionError:
        arr.logger.warning("Couldn't connect to Overseerr")
        arr._temp_overseer_request_cache = defaultdict(set)
        return arr._temp_overseer_request_cache
    except requests.exceptions.ReadTimeout:
        arr.logger.warning("Connection to Overseerr timed out")
        arr._temp_overseer_request_cache = defaultdict(set)
        return arr._temp_overseer_request_cache
    except Exception as e:
        arr.logger.exception(e, exc_info=sys.exc_info())
        arr._temp_overseer_request_cache = defaultdict(set)
        return arr._temp_overseer_request_cache
    else:
        return arr._temp_overseer_request_cache


def _get_overseerr_requests_count(arr) -> int:
    _get_oversee_requests_all(arr)
    if arr.type == "sonarr":
        return len(
            arr._temp_overseer_request_cache.get("TvdbId", [])
            or arr._temp_overseer_request_cache.get("ImdbId", [])
        )
    elif arr.type == "radarr":
        return len(
            arr._temp_overseer_request_cache.get("ImdbId", [])
            or arr._temp_overseer_request_cache.get("TmdbId", [])
        )
    return 0


def _get_ombi_request_count(arr) -> int:
    if arr.type == "sonarr":
        extras = "/api/v1/Request/tv/total"
    elif arr.type == "radarr":
        extras = "/api/v1/Request/movie/total"
    else:
        raise UnhandledError(f"Well you shouldn't have reached here, Arr.type={arr.type}")
    total = 0
    try:
        response = arr.session.get(
            url=f"{arr.ombi_uri}{extras}",
            headers={"ApiKey": arr.ombi_api_key},
            timeout=5,
            verify=not arr.skip_tls_verify_ombi,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            for key in ("total", "count", "totalCount", "totalRecords", "pending", "value"):
                value = payload.get(key)
                if isinstance(value, int):
                    total = value
                    break
        elif isinstance(payload, list):
            total = len(payload)
    except Exception as e:
        arr.logger.exception(e, exc_info=sys.exc_info())
    return total


def _get_ombi_requests(arr) -> list[dict]:
    if arr.type == "sonarr":
        extras = "/api/v1/Request/tvlite"
    elif arr.type == "radarr":
        extras = "/api/v1/Request/movie"
    else:
        raise UnhandledError(f"Well you shouldn't have reached here, Arr.type={arr.type}")
    try:
        response = arr.session.get(
            url=f"{arr.ombi_uri}{extras}",
            headers={"ApiKey": arr.ombi_api_key},
            timeout=5,
            verify=not arr.skip_tls_verify_ombi,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("result", "results", "requests", "data", "items"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        return []
    except Exception as e:
        arr.logger.exception(e, exc_info=sys.exc_info())
        return []


def _process_ombi_requests(arr) -> dict[str, set[str, int]]:
    requests = _get_ombi_requests(arr)
    data = defaultdict(set)
    for request in requests:
        if arr.type == "radarr" and arr.ombi_approved_only and request.get("denied") is True:
            continue
        elif arr.type == "sonarr" and arr.ombi_approved_only:
            # This is me being lazy and not wanting to deal with partially approved requests.
            if any(child.get("denied") is True for child in request.get("childRequests", [])):
                continue
        if imdbId := request.get("imdbId"):
            data["ImdbId"].add(imdbId)
        if arr.type == "radarr" and (theMovieDbId := request.get("theMovieDbId")):
            data["TmdbId"].add(theMovieDbId)
        if arr.type == "sonarr" and (tvDbId := request.get("tvDbId")):
            data["TvdbId"].add(tvDbId)
    return data


def db_request_update(arr):
    if arr.overseerr_requests:
        db_overseerr_update(arr)
    else:
        db_ombi_update(arr)


def _db_request_update(arr, request_ids: dict[str, set[int | str]]):
    if arr.type == "sonarr" and any(i in request_ids for i in ["ImdbId", "TvdbId"]):
        TvdbIds = request_ids.get("TvdbId")
        ImdbIds = request_ids.get("ImdbId")
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
                if "airDateUtc" in e:
                    if datetime.strptime(e["airDateUtc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc
                    ) > datetime.now(timezone.utc):
                        continue
                    if not arr.search_specials and e["seasonNumber"] == 0:
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
                    db_update_single_series(arr, db_entry=e, request=True)
    elif arr.type == "radarr" and any(i in request_ids for i in ["ImdbId", "TmdbId"]):
        ImdbIds = request_ids.get("ImdbId")
        TmdbIds = request_ids.get("TmdbId")
        movies = with_retry(
            lambda: arr.client.movie.get(),
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
            db_update_single_series(arr, db_entry=m, request=True)


def db_overseerr_update(arr):
    if (not arr.search_missing) or (not arr.overseerr_requests):
        return
    if _get_overseerr_requests_count(arr) == 0:
        return
    request_ids = arr._temp_overseer_request_cache
    if not any(i in request_ids for i in ["ImdbId", "TmdbId", "TvdbId"]):
        return
    arr.logger.notice("Started updating database with Overseerr request entries.")
    _db_request_update(arr, request_ids)
    arr.logger.notice("Finished updating database with Overseerr request entries")


def db_ombi_update(arr):
    if (not arr.search_missing) or (not arr.ombi_search_requests):
        return
    if _get_ombi_request_count(arr) == 0:
        return
    request_ids = _process_ombi_requests(arr)
    if not any(i in request_ids for i in ["ImdbId", "TmdbId", "TvdbId"]):
        return
    arr.logger.notice("Started updating database with Ombi request entries.")
    _db_request_update(arr, request_ids)
    arr.logger.notice("Finished updating database with Ombi request entries")
