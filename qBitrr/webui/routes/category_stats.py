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


def collect_torrents_for_category_on_instance(
    qbit_manager: Any, instance_name: str, category: str
) -> list[Any]:
    """Return torrents in ``category`` on a single qBit instance."""
    if qbit_manager is None:
        return []
    get_client = getattr(qbit_manager, "get_client", None)
    if not callable(get_client):
        client = getattr(qbit_manager, "client", None)
        if client is None:
            return []
        try:
            return list(client.torrents_info(category=category))
        except Exception:
            return []
    client = get_client(instance_name)
    if client is None:
        return []
    try:
        return list(client.torrents_info(category=category))
    except Exception:
        return []


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


def _torrent_tags(torrent: Any) -> list[str]:
    """Normalize torrent tags to a list of non-empty strings."""
    raw = getattr(torrent, "tags", "") or ""
    if isinstance(raw, (list, tuple)):
        return [str(tag).strip() for tag in raw if str(tag).strip()]
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def _attr(torrent: Any, name: str, default: Any) -> Any:
    """Return attribute ``name`` from ``torrent``, using ``default`` when missing/None."""
    value = getattr(torrent, name, default)
    return default if value is None else value


def serialize_torrent(torrent: Any) -> dict[str, Any]:
    """Map a qbittorrent-api torrent object to VueTorrent-aligned camelCase JSON."""
    hash_value = getattr(torrent, "hash", None) or getattr(torrent, "infohash_v1", "") or ""
    return {
        "hash": str(hash_value),
        "name": str(_attr(torrent, "name", "")),
        "category": str(_attr(torrent, "category", "")),
        "tags": _torrent_tags(torrent),
        "state": str(_attr(torrent, "state", "unknown") or "unknown"),
        "progress": float(_attr(torrent, "progress", 0)),
        "priority": int(_attr(torrent, "priority", 0)),
        "eta": int(_attr(torrent, "eta", 8640000)),
        "availability": float(_attr(torrent, "availability", 0)),
        "size": int(_attr(torrent, "size", 0)),
        "totalSize": int(_attr(torrent, "total_size", 0)),
        "downloaded": int(_attr(torrent, "downloaded", 0)),
        "uploaded": int(_attr(torrent, "uploaded", 0)),
        "amountLeft": int(_attr(torrent, "amount_left", 0)),
        "ratio": float(_attr(torrent, "ratio", 0)),
        "dlspeed": int(_attr(torrent, "dlspeed", 0)),
        "upspeed": int(_attr(torrent, "upspeed", 0)),
        "numSeeds": int(_attr(torrent, "num_seeds", 0)),
        "numLeechs": int(_attr(torrent, "num_leechs", 0)),
        "numComplete": int(_attr(torrent, "num_complete", 0)),
        "numIncomplete": int(_attr(torrent, "num_incomplete", 0)),
        "addedOn": int(_attr(torrent, "added_on", 0)),
        "completionOn": int(_attr(torrent, "completion_on", 0)),
        "seedingTime": int(_attr(torrent, "seeding_time", 0)),
        "timeActive": int(_attr(torrent, "time_active", 0)),
        "lastActivity": int(_attr(torrent, "last_activity", 0)),
        "savePath": str(_attr(torrent, "save_path", "")),
        "contentPath": str(_attr(torrent, "content_path", "")),
        "tracker": str(_attr(torrent, "tracker", "")),
        "ratioLimit": float(_attr(torrent, "ratio_limit", -1)),
        "seedingTimeLimit": int(_attr(torrent, "seeding_time_limit", -1)),
        "dlLimit": int(_attr(torrent, "dl_limit", -1)),
        "upLimit": int(_attr(torrent, "up_limit", -1)),
    }


def build_qbit_overview(
    qbit_manager: Any,
    *,
    instance_filter: str | None = None,
    arr_manager: Any | None = None,
) -> dict[str, Any]:
    """Build the qBit overview payload of monitored categories with torrents.

    Parameters
    ----------
    qbit_manager:
        The ``QBitManager`` (or compatible) instance.
    instance_filter:
        When set to a specific instance name, only that client is included.
        ``None`` / empty / ``\"all\"`` includes every configured instance.
    arr_manager:
        Optional Arr manager used to discover Arr-managed categories.
    """
    if qbit_manager is None:
        return {"instances": [], "categories": [], "ready": True}

    get_all = getattr(qbit_manager, "get_all_instances", None)
    all_instances: list[str] = list(get_all()) if callable(get_all) else []
    if not all_instances:
        # Legacy single-client fallback
        default_name = getattr(qbit_manager, "default_instance", None) or "qBit"
        if getattr(qbit_manager, "client", None) is not None or callable(
            getattr(qbit_manager, "get_client", None)
        ):
            all_instances = [default_name]

    filter_name = (instance_filter or "").strip()
    if filter_name and filter_name.lower() != "all":
        instances = [name for name in all_instances if name == filter_name]
    else:
        instances = list(all_instances)

    categories_data: list[dict[str, Any]] = []
    category_managers = getattr(qbit_manager, "qbit_category_managers", None) or {}

    for instance_name in instances:
        manager = category_managers.get(instance_name)
        if manager is not None:
            for category in getattr(manager, "managed_categories", []) or []:
                torrents = collect_torrents_for_category_on_instance(
                    qbit_manager, instance_name, category
                )
                stats = summarize_category_torrents(torrents)
                seeding_config = {}
                get_cfg = getattr(manager, "get_seeding_config", None)
                if callable(get_cfg):
                    seeding_config = get_cfg(category) or {}
                categories_data.append(
                    {
                        "category": category,
                        "qbitInstance": instance_name,
                        "managedBy": "qbit",
                        "arrName": None,
                        **stats,
                        "seedingConfig": {
                            "maxRatio": seeding_config.get("MaxUploadRatio", -1),
                            "maxTime": seeding_config.get("MaxSeedingTime", -1),
                            "removeMode": seeding_config.get("RemoveTorrent", -1),
                            "downloadLimit": seeding_config.get("DownloadRateLimitPerTorrent", -1),
                            "uploadLimit": seeding_config.get("UploadRateLimitPerTorrent", -1),
                        },
                        "torrents": [serialize_torrent(t) for t in torrents],
                    }
                )

        if arr_manager is None:
            continue
        managed_objects = getattr(arr_manager, "managed_objects", None) or {}
        for arr in managed_objects.values():
            arr_type = getattr(arr, "type", None)
            if arr_type not in ("radarr", "sonarr", "lidarr"):
                continue
            category = getattr(arr, "category", None)
            if not category:
                continue
            torrents = collect_torrents_for_category_on_instance(
                qbit_manager, instance_name, category
            )
            stats = summarize_category_torrents(torrents)
            categories_data.append(
                {
                    "category": category,
                    "qbitInstance": instance_name,
                    "managedBy": "arr",
                    "arrName": getattr(arr, "_name", None),
                    **stats,
                    "seedingConfig": {
                        "maxRatio": getattr(arr, "seeding_mode_global_max_upload_ratio", -1),
                        "maxTime": getattr(arr, "seeding_mode_global_max_seeding_time", -1),
                        "removeMode": getattr(arr, "seeding_mode_global_remove_torrent", -1),
                        "downloadLimit": getattr(arr, "seeding_mode_global_download_limit", -1),
                        "uploadLimit": getattr(arr, "seeding_mode_global_upload_limit", -1),
                    },
                    "torrents": [serialize_torrent(t) for t in torrents],
                }
            )

    return {"instances": instances, "categories": categories_data, "ready": True}
