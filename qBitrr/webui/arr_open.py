"""Build Arr UI deep-link redirects for catalog Open-in-Arr routes."""

from __future__ import annotations

from typing import Any

from qBitrr.arr_client import PyarrResourceNotFound
from qBitrr.arss.arr_shared import _ARR_RETRY_EXCEPTIONS, with_retry

OPEN_KINDS = frozenset({"movie", "series", "artist", "author"})
KIND_ARR_TYPE = {
    "movie": "radarr",
    "series": "sonarr",
    "artist": "lidarr",
    "author": "readarr",
}
KIND_PATH_SEGMENT = {
    "movie": "movie",
    "series": "series",
    "artist": "artist",
    "author": "author",
}


def resolve_open_route_token(kind: str, item: dict[str, Any]) -> str | int:
    """Pick the Arr UI route token for *kind* from an API item payload."""
    if kind in ("movie", "series"):
        slug = item.get("titleSlug")
        if slug:
            return slug
        return item.get("id", 0)
    if kind == "artist":
        foreign_id = item.get("foreignArtistId")
        if foreign_id:
            return foreign_id
        slug = item.get("titleSlug")
        if slug:
            return slug
        return item.get("id", 0)
    if kind == "author":
        foreign_id = item.get("foreignAuthorId")
        if foreign_id:
            return foreign_id
        slug = item.get("titleSlug")
        if slug:
            return slug
        return item.get("id", 0)
    return item.get("id", 0)


def _fetch_arr_item(arr: Any, kind: str, entry_id: int) -> dict[str, Any]:
    client = arr.client
    if kind == "movie":
        return with_retry(
            lambda: client.movie.get(item_id=entry_id),
            retries=3,
            backoff=0.5,
            max_backoff=3,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
    if kind == "series":
        return with_retry(
            lambda: client.series.get(item_id=entry_id),
            retries=3,
            backoff=0.5,
            max_backoff=3,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
    if kind == "artist":
        return with_retry(
            lambda: client.artist.get(item_id=entry_id),
            retries=3,
            backoff=0.5,
            max_backoff=3,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
    if kind == "author":
        return with_retry(
            lambda: client.author.get(item_id=entry_id),
            retries=3,
            backoff=0.5,
            max_backoff=3,
            exceptions=_ARR_RETRY_EXCEPTIONS,
        )
    raise ValueError(f"Unsupported kind: {kind}")


def build_arr_open_url(arr: Any, kind: str, entry_id: int) -> str | None:
    """Return a redirect URL for opening *entry_id* in the native Arr UI."""
    uri = getattr(arr, "uri", None)
    if not uri:
        return None
    item = _fetch_arr_item(arr, kind, entry_id)
    if not isinstance(item, dict) or not item:
        return None
    token = resolve_open_route_token(kind, item)
    if token in (None, "", 0):
        return None
    base = str(uri).rstrip("/")
    segment = KIND_PATH_SEGMENT[kind]
    return f"{base}/{segment}/{token}"


def open_arr_item_or_error(
    arr: Any,
    kind: str,
    entry_id: int,
) -> tuple[str | None, str | None]:
    """Return ``(redirect_url, error_message)`` for Open-in-Arr handlers."""
    if kind not in OPEN_KINDS:
        return None, f"Unknown item kind {kind}"
    uri = getattr(arr, "uri", None)
    if not uri:
        return None, "Arr URI is not configured"
    try:
        url = build_arr_open_url(arr, kind, entry_id)
    except PyarrResourceNotFound:
        return None, "Item not found in Arr"
    except Exception:
        return None, "Item lookup failed"
    if not url:
        return None, "Item not found in Arr"
    return url, None
