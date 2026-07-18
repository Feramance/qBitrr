"""Helpers for qBit / Arr category statistics used by WebUI routes."""

from __future__ import annotations

from typing import Any


def collect_torrents_for_category(qbit_manager: Any, category: str) -> list[Any]:
    """Return torrents in ``category`` across all configured qBit instances."""
    torrents: list[Any] = []
    if qbit_manager is None:
        return torrents
    get_all = getattr(qbit_manager, "get_all_instances", None)
    get_client = getattr(qbit_manager, "get_client", None)
    if not callable(get_all) or not callable(get_client):
        client = getattr(qbit_manager, "client", None)
        if client is None:
            return torrents
        try:
            return list(client.torrents_info(category=category))
        except Exception:
            return torrents
    for instance_name in get_all():
        client = get_client(instance_name)
        if client is None:
            continue
        try:
            torrents.extend(client.torrents_info(category=category))
        except Exception:
            continue
    return torrents


def summarize_category_torrents(torrents: list[Any]) -> dict[str, Any]:
    """Compute count/size/ratio aggregates for a torrent list."""
    total_count = len(torrents)
    seeding_count = len(
        [t for t in torrents if getattr(t, "state", None) in ("uploading", "stalledUP")]
    )
    total_size = sum(getattr(t, "size", 0) for t in torrents)
    avg_ratio = sum(getattr(t, "ratio", 0) for t in torrents) / total_count if total_count else 0
    avg_seeding_time = (
        sum(getattr(t, "seeding_time", 0) for t in torrents) / total_count if total_count else 0
    )
    return {
        "torrentCount": total_count,
        "seedingCount": seeding_count,
        "totalSize": total_size,
        "avgRatio": round(avg_ratio, 2),
        "avgSeedingTime": avg_seeding_time,
    }
