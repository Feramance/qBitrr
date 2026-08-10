"""Helpers for qBit / Arr category statistics used by WebUI routes."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("qBitrr.WebUI")

# Active / queued seeding states shown as "seeding" in the WebUI overview.
SEEDING_STATES = frozenset(
    {
        "uploading",
        "stalledUP",
        "forcedUP",
        "queuedUP",
    }
)

# Cap per-category torrent payloads to keep overview responses bounded.
OVERVIEW_MAX_TORRENTS_PER_CATEGORY = 500


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


def collect_torrents_for_category_on_instances(
    qbit_manager: Any, instance_names: list[str], category: str
) -> list[Any]:
    """Return torrents in ``category`` across the given qBit instance names."""
    if len(instance_names) == 1:
        return collect_torrents_for_category_on_instance(qbit_manager, instance_names[0], category)
    torrents: list[Any] = []
    for instance_name in instance_names:
        torrents.extend(
            collect_torrents_for_category_on_instance(qbit_manager, instance_name, category)
        )
    return torrents


def is_seeding_state(state: Any) -> bool:
    """Return True when ``state`` counts as seeding for WebUI aggregates."""
    return state in SEEDING_STATES


def summarize_category_torrents(torrents: list[Any]) -> dict[str, Any]:
    """Compute count/size/ratio aggregates for a torrent list."""
    total_count = len(torrents)
    seeding_count = len([t for t in torrents if is_seeding_state(getattr(t, "state", None))])
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
    """Map a qbittorrent-api torrent object to VueTorrent-aligned camelCase JSON.

    Path and tracker fields are omitted from the overview payload (defense-in-depth;
    the WebUI row does not display them).
    """
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
        "ratioLimit": float(_attr(torrent, "ratio_limit", -1)),
        "seedingTimeLimit": int(_attr(torrent, "seeding_time_limit", -1)),
        "dlLimit": int(_attr(torrent, "dl_limit", -1)),
        "upLimit": int(_attr(torrent, "up_limit", -1)),
    }


def _serialize_torrents_safe(torrents: list[Any]) -> tuple[list[dict[str, Any]], bool]:
    """Serialize torrents, skipping failures and capping list length.

    Returns
    -------
    tuple[list[dict], bool]
        Serialized torrents and whether the list was truncated to the cap.
    """
    serialized: list[dict[str, Any]] = []
    truncated = len(torrents) > OVERVIEW_MAX_TORRENTS_PER_CATEGORY
    for torrent in torrents[:OVERVIEW_MAX_TORRENTS_PER_CATEGORY]:
        try:
            serialized.append(serialize_torrent(torrent))
        except Exception:
            logger.debug("Skipping malformed torrent in overview serialize", exc_info=True)
            continue
    return serialized, truncated


def _arr_qbit_instance_label(instances: list[str]) -> str:
    """Label for Arr-managed rows: single client name, or ``all`` when aggregated."""
    if len(instances) == 1:
        return instances[0]
    return "all"


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

    Notes
    -----
    qBit-managed categories are emitted per qBit client. Arr-managed categories are
    emitted once per Arr (aligned with ``/web/qbit/categories``), with torrents
    collected from the in-scope client(s) rather than fanned across every instance.
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
        if manager is None:
            continue
        for category in getattr(manager, "managed_categories", []) or []:
            try:
                torrents = collect_torrents_for_category_on_instance(
                    qbit_manager, instance_name, category
                )
                stats = summarize_category_torrents(torrents)
                seeding_config = {}
                get_cfg = getattr(manager, "get_seeding_config", None)
                if callable(get_cfg):
                    seeding_config = get_cfg(category) or {}
                torrent_payloads, truncated = _serialize_torrents_safe(torrents)
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
                        "torrents": torrent_payloads,
                        "torrentsTruncated": truncated,
                    }
                )
            except Exception:
                logger.debug(
                    "Error building qBit overview for category '%s' on '%s'",
                    category,
                    instance_name,
                    exc_info=True,
                )
                continue

    # Arr-managed categories: one row per Arr (not one row per qBit client).
    if arr_manager is not None and instances:
        managed_objects = getattr(arr_manager, "managed_objects", None) or {}
        arr_instance_label = _arr_qbit_instance_label(instances)
        for arr in managed_objects.values():
            arr_type = getattr(arr, "type", None)
            if arr_type not in ("radarr", "sonarr", "lidarr", "readarr"):
                continue
            category = getattr(arr, "category", None)
            if not category:
                continue
            try:
                torrents = collect_torrents_for_category_on_instances(
                    qbit_manager, instances, category
                )
                stats = summarize_category_torrents(torrents)
                torrent_payloads, truncated = _serialize_torrents_safe(torrents)
                categories_data.append(
                    {
                        "category": category,
                        "qbitInstance": arr_instance_label,
                        "managedBy": "arr",
                        "arrName": getattr(arr, "_name", None),
                        **stats,
                        "seedingConfig": {
                            "maxRatio": getattr(arr, "seeding_mode_global_max_upload_ratio", -1),
                            "maxTime": getattr(arr, "seeding_mode_global_max_seeding_time", -1),
                            "removeMode": getattr(arr, "seeding_mode_global_remove_torrent", -1),
                            "downloadLimit": getattr(
                                arr, "seeding_mode_global_download_limit", -1
                            ),
                            "uploadLimit": getattr(arr, "seeding_mode_global_upload_limit", -1),
                        },
                        "torrents": torrent_payloads,
                        "torrentsTruncated": truncated,
                    }
                )
            except Exception:
                logger.debug(
                    "Error building Arr overview for category '%s' (%s)",
                    category,
                    getattr(arr, "_name", "?"),
                    exc_info=True,
                )
                continue

    return {"instances": instances, "categories": categories_data, "ready": True}
