"""Ombi/Overseerr request fetch and DB update helpers (split from Arr).

Shared orchestration lives here; Arr-type differences dispatch to concrete hooks
(``_overseerr_request_media_type``, ``_add_overseerr_type_ids``, Ombi paths, etc.).
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timezone

import requests

from qBitrr.arss.arr_shared import (
    _is_media_available,
    _is_media_processing,
    _normalize_media_status,
)


def _get_oversee_requests_all(arr) -> dict[str, set]:
    try:
        data = defaultdict(set)
        key = "approved" if arr.overseerr_approved_only else "unavailable"
        take = 100
        skip = 0
        type_ = arr._overseerr_request_media_type()
        if type_ is None:
            arr._temp_overseer_request_cache = defaultdict(set)
            return arr._temp_overseer_request_cache
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
                    arr._add_overseerr_type_ids(media, data)
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
    return arr._overseerr_request_count()


def _get_ombi_request_count(arr) -> int:
    extras = arr._ombi_request_total_path()
    if extras is None:
        return 0
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
    extras = arr._ombi_request_list_path()
    if extras is None:
        return []
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
    requests_list = _get_ombi_requests(arr)
    data = defaultdict(set)
    for request in requests_list:
        if not arr._ombi_should_include_request(request):
            continue
        if imdbId := request.get("imdbId"):
            data["ImdbId"].add(imdbId)
        arr._add_ombi_request_ids(request, data)
    return data


def db_request_update(arr):
    if arr.overseerr_requests:
        db_overseerr_update(arr)
    else:
        db_ombi_update(arr)


def _db_request_update(arr, request_ids: dict[str, set[int | str]]):
    """Dispatch request-ID matching to the concrete Arr hook."""
    arr._db_request_update_impl(request_ids)


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
