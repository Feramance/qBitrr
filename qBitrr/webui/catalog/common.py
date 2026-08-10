from __future__ import annotations

from typing import Any

from qBitrr.utils import coerce_bool


def parse_catalog_filters(
    req: Any,
    *,
    default_page_size: int = 50,
    page_size_cap: int = 1000,
    include_missing_only: bool = False,
    include_reason: bool = False,
) -> dict[str, Any]:
    """Parse shared catalog list query parameters from a Flask request."""
    filters: dict[str, Any] = {
        "q": req.args.get("q", default=None, type=str),
        "page": req.args.get("page", default=0, type=int),
        "page_size": min(
            req.args.get("page_size", default=default_page_size, type=int), page_size_cap
        ),
    }
    if include_missing_only:
        filters["missing_only"] = coerce_bool(
            req.args.get("missing") or req.args.get("only_missing")
        )
    if include_reason:
        filters["reason"] = req.args.get("reason", default=None, type=str)
    return filters


def resolve_arr_handler(
    category: str,
    expected_type: str,
    managed_objects: dict[str, Any],
    *,
    arr_manager_ready: bool,
    slug_resolver: Any | None = None,
) -> tuple[Any | None, tuple[Any, int] | None]:
    """Resolve an Arr instance for catalog routes; return (arr, error_response) or (arr, None)."""
    from flask import jsonify

    if not managed_objects:
        if not arr_manager_ready:
            return None, (jsonify({"error": "Arr manager is still initialising"}), 503)
        return None, (jsonify({"error": f"Unknown {expected_type} category {category}"}), 404)
    arr = managed_objects.get(category)
    if arr is None and slug_resolver is not None:
        arr = slug_resolver(category, managed_objects)
    if arr is None or getattr(arr, "type", None) != expected_type:
        return None, (jsonify({"error": f"Unknown {expected_type} category {category}"}), 404)
    return arr, None


def empty_catalog_payload(
    kind: str,
    *,
    page: int = 0,
    page_size: int = 50,
) -> dict[str, Any]:
    """Return the empty-state catalog payload shape for *kind* (mirrors successful responses)."""
    page = max(page, 0)
    page_size = max(page_size, 1)
    if kind == "radarr":
        return {
            "counts": {
                "available": 0,
                "monitored": 0,
                "missing": 0,
                "quality_met": 0,
                "requests": 0,
            },
            "total": 0,
            "page": page,
            "page_size": page_size,
            "movies": [],
        }
    if kind == "sonarr":
        return {
            "counts": {"available": 0, "monitored": 0, "missing": 0},
            "total": 0,
            "page": page,
            "page_size": page_size,
            "series": [],
        }
    if kind == "lidarr_albums":
        return {
            "counts": {
                "available": 0,
                "monitored": 0,
                "missing": 0,
                "quality_met": 0,
                "requests": 0,
            },
            "counts_tracks": {"available": 0, "monitored": 0, "missing": 0},
            "album_total": 0,
            "total": 0,
            "page": page,
            "page_size": page_size,
            "albums": [],
        }
    if kind == "readarr_authors":
        return {
            "counts": {
                "available": 0,
                "monitored": 0,
                "missing": 0,
                "quality_met": 0,
                "requests": 0,
            },
            "book_total": 0,
            "total": 0,
            "page": page,
            "page_size": page_size,
            "authors": [],
        }
    raise ValueError(f"unknown catalog kind: {kind}")
