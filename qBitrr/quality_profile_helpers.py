"""Shared quality-profile and search-state helpers for Arr db_update paths."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

import requests
from ujson import JSONDecodeError

from qBitrr.arr_client import JsonObject
from qBitrr.utils import with_retry

_ARR_RETRY_EXCEPTIONS = (
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.ContentDecodingError,
    requests.exceptions.ConnectionError,
    JSONDecodeError,
)

T = TypeVar("T")


def arr_with_retry(fn: Callable[[], T], *, retries: int = 5) -> T:
    """Arr API call wrapper using the standard retry exception tuple."""
    return with_retry(
        fn,
        retries=retries,
        backoff=0.5,
        max_backoff=5,
        exceptions=_ARR_RETRY_EXCEPTIONS,
    )


def should_mark_searched(
    *,
    has_content: bool,
    quality_unmet_search: bool,
    quality_unmet: bool,
    custom_format_unmet_search: bool,
    custom_format: int,
    min_custom_format: int,
) -> bool:
    """True when the entry has content and no active quality/custom-format search applies."""
    if not has_content:
        return False
    if quality_unmet_search and quality_unmet:
        return False
    if custom_format_unmet_search and custom_format < min_custom_format:
        return False
    return True


def mark_queue_completed(model_queue: Any, entry_id: int, arr_instance: str) -> None:
    """Mark a queue row completed for the given entry."""
    model_queue.update(Completed=True).where(
        (model_queue.EntryId == entry_id) & (model_queue.ArrInstance == arr_instance)
    ).execute()


def resolve_min_format_score(
    *,
    stored_score: int | None,
    quality_profile_id: int | None,
    fetch_profile: Callable[[int], JsonObject | None],
    logger: Any,
    label: str,
    entry_id: int | str,
) -> int:
    """Resolve minimum custom format score from DB cache or quality profile API."""
    if stored_score:
        return stored_score
    if quality_profile_id:
        profile = fetch_profile(quality_profile_id) or {}
        return profile.get("minFormatScore") or 0
    logger.warning(
        "%s %s missing qualityProfileId; defaulting custom format threshold to 0",
        label,
        entry_id,
    )
    return 0


def resolve_custom_format_score(
    *,
    has_content: bool,
    content_file_id: int | None,
    stored_file_id: int | None,
    stored_score: int | None,
    fetch_file_score: Callable[[int], int],
) -> int:
    """Resolve custom format score from DB cache or file API (Sonarr/Radarr)."""
    if not has_content or not content_file_id:
        return 0
    if stored_file_id and content_file_id == stored_file_id and stored_score is not None:
        return stored_score
    return fetch_file_score(content_file_id)


def compute_quality_met(*, has_content: bool, quality_unmet: bool) -> bool:
    return not quality_unmet if has_content else False


def compute_search_reason(
    *,
    has_content: bool,
    quality_unmet_search: bool,
    quality_unmet: bool,
    custom_format_unmet_search: bool,
    custom_format_met: bool,
    do_upgrade_search: bool,
    searched: bool,
    missing_label: str = "Missing",
) -> str:
    """Compute Reason column value shared across movie/episode/album paths."""
    if not has_content:
        return missing_label
    if quality_unmet_search and quality_unmet:
        return "Quality"
    if custom_format_unmet_search and not custom_format_met:
        return "CustomFormat"
    if do_upgrade_search:
        return "Upgrade"
    if searched:
        return "Not being searched"
    return "Not being searched"


def plan_temp_profile_switch(
    *,
    searched: bool,
    has_file: bool,
    quality_profile_id: int | None,
    main_quality_profile_ids: dict[int, int],
    temp_quality_profile_ids: dict[int, int],
    keep_temp_profile: bool,
) -> tuple[JsonObject | None, datetime | None, int | None, int | None]:
    """Plan episode-style conditional temp profile switch (PUT only when data is set)."""
    data: JsonObject | None = None
    profile_switch_timestamp: datetime | None = None
    original_profile_for_db: int | None = None
    current_profile_for_db: int | None = None

    if searched and quality_profile_id in main_quality_profile_ids and not keep_temp_profile:
        new_profile_id = main_quality_profile_ids.get(quality_profile_id)
        if new_profile_id is None:
            return None, None, None, None
        data = {"qualityProfileId": new_profile_id}
        profile_switch_timestamp = datetime.now()
    elif not searched and not has_file and quality_profile_id in temp_quality_profile_ids:
        new_profile_id = temp_quality_profile_ids[quality_profile_id]
        data = {"qualityProfileId": new_profile_id}
        profile_switch_timestamp = datetime.now()
        original_profile_for_db = quality_profile_id
        current_profile_for_db = new_profile_id

    return data, profile_switch_timestamp, original_profile_for_db, current_profile_for_db


def get_profile_name_cached(
    *,
    quality_profile_id: int | None,
    cache: dict[int, dict],
    fetch_profile: Callable[[int], JsonObject | None],
) -> str | None:
    if not quality_profile_id:
        return None
    try:
        if quality_profile_id not in cache:
            profile = fetch_profile(quality_profile_id)
            if profile:
                cache[quality_profile_id] = profile
        return (cache.get(quality_profile_id) or {}).get("name")
    except Exception:
        return None
