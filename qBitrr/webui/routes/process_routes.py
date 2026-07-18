"""Process list / restart WebUI routes."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from flask import jsonify

from qBitrr.arss import PlaceHolderArr, TorrentPolicyManager
from qBitrr.search_activity_store import clear_search_activity

if TYPE_CHECKING:
    from qBitrr.webui.app import WebUI


def register_process_routes(
    webui: WebUI,
    *,
    _dual_route: Callable[..., Any],
    _managed_objects: Callable[[], dict[str, Any]],
    _ensure_arr_manager_ready: Callable[[], bool],
    _webui_mod: Callable[[], Any],
) -> None:
    """Register process listing and restart routes."""

    def _processes_payload() -> dict[str, Any]:
        procs = []
        search_activity_map = _webui_mod().fetch_search_activities()

        def _parse_timestamp(raw_value):
            if not raw_value:
                return None
            try:
                if isinstance(raw_value, (int, float)):
                    return datetime.fromtimestamp(raw_value, timezone.utc).isoformat()
                if isinstance(raw_value, str):
                    trimmed = raw_value.rstrip("Z")
                    dt = datetime.fromisoformat(trimmed)
                    if raw_value.endswith("Z"):
                        dt = dt.replace(tzinfo=timezone.utc)
                    elif dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                return None
            return None

        def _format_queue_summary(arr_obj, record):
            if not isinstance(record, dict):
                return None
            pieces = []
            arr_type = (getattr(arr_obj, "type", "") or "").lower()
            if arr_type == "radarr":
                movie_info = record.get("movie") or {}
                title = movie_info.get("title")
                year = movie_info.get("year")
                release_title = record.get("title") or ""
                release_name = ""
                release_year = None
                if release_title:
                    cleaned = release_title.split("/")[-1]
                    cleaned = re.sub(r"\.[^.]+$", "", cleaned)
                    cleaned = re.sub(r"[-_.]+", " ", cleaned).strip()
                    release_name = cleaned
                    match = re.match(
                        r"(?P<name>.+?)\s+(?P<year>(?:19|20)\d{2})(?:\s|$)",
                        cleaned,
                    )
                    if match:
                        extracted_name = (match.group("name") or "").strip(" .-_")
                        if extracted_name:
                            release_name = re.sub(r"[-_.]+", " ", extracted_name).strip()
                        release_year = match.group("year")
                if not title and release_name:
                    title = release_name
                elif title and release_title and title == release_title and release_name:
                    title = release_name
                if not year:
                    year = release_year or record.get("year")
                if title:
                    pieces.append(title)
                if year:
                    pieces.append(str(year))
            elif arr_type == "sonarr":
                series = (record.get("series") or {}).get("title")
                episode = record.get("episode")
                if series:
                    pieces.append(series)
                season = None
                episode_number = None
                if isinstance(episode, dict):
                    season = episode.get("seasonNumber")
                    episode_number = episode.get("episodeNumber")
                if season is not None and episode_number is not None:
                    pieces.append(f"S{int(season):02d}E{int(episode_number):02d}")
                # Intentionally omit individual episode titles/status values
            else:
                title = record.get("title")
                if title:
                    pieces.append(title)
            cleaned = [str(part) for part in pieces if part]
            return " | ".join(cleaned) if cleaned else None

        def _collect_metrics(arr_obj):
            metrics = {
                "queue": None,
                "category": None,
                "summary": None,
                "timestamp": None,
                "metric_type": None,
            }
            manager_ref = getattr(arr_obj, "manager", None)
            if manager_ref and hasattr(manager_ref, "qbit_manager"):
                qbit_manager = manager_ref.qbit_manager
            else:
                qbit_manager = getattr(webui.manager, "qbit_manager", webui.manager)
            qbit_client = getattr(qbit_manager, "client", None)
            category = getattr(arr_obj, "category", None)

            if isinstance(arr_obj, TorrentPolicyManager):
                metrics["metric_type"] = "torrent-policy"
                metrics["category"] = int(getattr(arr_obj, "category_torrent_count", 0) or 0)
                # Keep queue metric aligned with monitored torrent count for process cards.
                metrics["queue"] = int(getattr(arr_obj, "category_torrent_count", 0) or 0)
                paused_for_space = int(getattr(arr_obj, "free_space_tagged_count", 0) or 0)
                if paused_for_space:
                    metrics["free_space_paused"] = paused_for_space
                return metrics

            if isinstance(arr_obj, PlaceHolderArr):
                metrics["metric_type"] = "category"
                if qbit_client and category:
                    try:
                        torrents = qbit_client.torrents_info(
                            status_filter="all", category=category
                        )
                        count = sum(
                            1
                            for torrent in torrents
                            if getattr(torrent, "category", None) == category
                        )
                        metrics["queue"] = count
                        metrics["category"] = count
                    except Exception:
                        webui.logger.debug(
                            "Process metrics (PlaceHolderArr) fetch failed", exc_info=True
                        )
                return metrics

            # Standard Arr (Radarr/Sonarr)
            records = []
            client = getattr(arr_obj, "client", None)
            if client is not None:
                try:
                    raw_queue = arr_obj.get_queue(
                        page=1, page_size=50, sort_direction="descending"
                    )
                    if isinstance(raw_queue, dict):
                        records = raw_queue.get("records", []) or []
                    else:
                        records = list(raw_queue or [])
                except Exception:
                    records = []
            queue_count = len(records)
            if queue_count:
                metrics["queue"] = queue_count
            if qbit_client and category:
                try:
                    torrents = qbit_client.torrents_info(status_filter="all", category=category)
                    metrics["category"] = sum(
                        1 for torrent in torrents if getattr(torrent, "category", None) == category
                    )
                except Exception:
                    webui.logger.debug("Process metrics (category count) failed", exc_info=True)
            category_key = getattr(arr_obj, "category", None)
            if category_key:
                entry = search_activity_map.get(str(category_key))
                if isinstance(entry, Mapping):
                    summary = entry.get("summary")
                    timestamp = entry.get("timestamp")
                    if summary:
                        metrics["summary"] = summary
                    if timestamp:
                        metrics["timestamp"] = timestamp
            if metrics["summary"] is None and not getattr(arr_obj, "_webui_db_loaded", True):
                metrics["summary"] = "Updating database"
            return metrics

        metrics_cache: dict[int, dict[str, object]] = {}

        def _populate_process_metadata(arr_obj, proc_kind, payload_dict):
            metrics = metrics_cache.get(id(arr_obj))
            if metrics is None:
                metrics = _collect_metrics(arr_obj)
            metrics_cache[id(arr_obj)] = metrics
            if proc_kind == "search":
                category_key = getattr(arr_obj, "category", None)
                entry = None
                if category_key:
                    entry = search_activity_map.get(str(category_key))
                summary = None
                timestamp = None
                if isinstance(entry, Mapping):
                    summary = entry.get("summary")
                    timestamp = entry.get("timestamp")
                if summary is None:
                    summary = getattr(arr_obj, "last_search_description", None)
                    timestamp = getattr(arr_obj, "last_search_timestamp", None)
                if summary is None:
                    metrics_summary = metrics.get("summary")
                    if metrics_summary:
                        summary = metrics_summary
                        metrics_timestamp = metrics.get("timestamp")
                        if metrics_timestamp:
                            timestamp = metrics_timestamp
                if summary:
                    payload_dict["searchSummary"] = summary
                    if timestamp:
                        if isinstance(timestamp, datetime):
                            payload_dict["searchTimestamp"] = timestamp.astimezone(
                                timezone.utc
                            ).isoformat()
                        else:
                            payload_dict["searchTimestamp"] = str(timestamp)
                elif category_key:
                    key = str(category_key)
                    clear_search_activity(key)
                    search_activity_map.pop(key, None)
            elif proc_kind == "torrent":
                queue_count = metrics.get("queue")
                if queue_count is None:
                    queue_count = getattr(arr_obj, "queue_active_count", None)
                category_count = metrics.get("category")
                if category_count is None:
                    category_count = getattr(arr_obj, "category_torrent_count", None)
                free_space_paused = metrics.get("free_space_paused")
                metric_type = metrics.get("metric_type")
                if queue_count is not None:
                    payload_dict["queueCount"] = queue_count
                if category_count is not None:
                    payload_dict["categoryCount"] = category_count
                if free_space_paused is not None:
                    payload_dict["freeSpacePaused"] = free_space_paused
                if metric_type:
                    payload_dict["metricType"] = metric_type

        for arr in _managed_objects().values():
            name = getattr(arr, "_name", "unknown")
            cat = getattr(arr, "category", name)
            for kind in ("search", "torrent"):
                p = getattr(arr, f"process_{kind}_loop", None)
                if p is None:
                    continue
                try:
                    payload = {
                        "category": cat,
                        "name": name,
                        "kind": kind,
                        "pid": getattr(p, "pid", None),
                        "alive": bool(p.is_alive()),
                        "rebuilding": webui._rebuilding_arrs,
                    }
                    _populate_process_metadata(arr, kind, payload)
                    procs.append(payload)
                except Exception:
                    payload = {
                        "category": cat,
                        "name": name,
                        "kind": kind,
                        "pid": getattr(p, "pid", None),
                        "alive": False,
                        "rebuilding": webui._rebuilding_arrs,
                    }
                    _populate_process_metadata(arr, kind, payload)
                    procs.append(payload)
        # qBit category manager processes
        for process, meta in list(webui.manager._process_registry.items()):
            if meta.get("role") != "category_manager":
                continue
            instance_name = meta.get("instance", "")
            cat = meta.get("category", f"qbit-{instance_name}")
            manager = webui.manager.qbit_category_managers.get(instance_name)
            category_count = len(manager.managed_categories) if manager else 0
            try:
                alive = bool(process.is_alive())
                pid = getattr(process, "pid", None)
            except Exception:
                alive = False
                pid = None
            display_name = (
                instance_name
                if instance_name.lower().startswith("qbit")
                else f"qBit-{instance_name}"
            )
            procs.append(
                {
                    "category": cat,
                    "name": display_name,
                    "kind": "category",
                    "pid": pid,
                    "alive": alive,
                    "categoryCount": category_count,
                }
            )
        return {"processes": procs}

    @_dual_route("/processes")
    def processes():
        return jsonify(_processes_payload())

    def _restart_process(category: str, kind: str):
        kind_normalized = kind.lower()
        if kind_normalized not in ("search", "torrent", "all", "category"):
            return jsonify({"error": "kind must be search, torrent, category or all"}), 400

        # Handle category manager restart
        if kind_normalized == "category":
            target_proc = None
            target_meta = None
            for proc, meta in list(webui.manager._process_registry.items()):
                if meta.get("role") == "category_manager" and meta.get("category") == category:
                    target_proc = proc
                    target_meta = meta
                    break
            if target_proc is None:
                return jsonify({"error": f"Unknown category manager {category}"}), 404
            instance_name = target_meta.get("instance", "")
            try:
                target_proc.kill()
            except Exception:
                webui.logger.debug(
                    "Category manager process kill failed for %s", category, exc_info=True
                )
            try:
                target_proc.terminate()
            except Exception:
                webui.logger.debug(
                    "Category manager process terminate failed for %s", category, exc_info=True
                )
            try:
                webui.manager.child_processes.remove(target_proc)
            except Exception:
                webui.logger.debug(
                    "child_processes.remove failed for category manager %s",
                    category,
                    exc_info=True,
                )
            webui.manager._process_registry.pop(target_proc, None)
            manager = webui.manager.qbit_category_managers.get(instance_name)
            if manager is None:
                return (
                    jsonify({"error": f"No category manager for instance {instance_name}"}),
                    404,
                )
            import pathos

            new_proc = pathos.helpers.mp.Process(
                target=manager.run_processing_loop,
                name=f"qBitCategory-{instance_name}",
                daemon=False,
            )
            new_proc.start()
            webui.manager.child_processes.append(new_proc)
            webui.manager._process_registry[new_proc] = {
                "category": category,
                "role": "category_manager",
                "instance": instance_name,
            }
            return jsonify({"status": "ok", "restarted": ["category"]})

        managed = _managed_objects()
        if not managed:
            if not _ensure_arr_manager_ready():
                return jsonify({"error": "Arr manager is still initialising"}), 503
        arr = managed.get(category)
        if arr is None:
            return jsonify({"error": f"Unknown category {category}"}), 404
        restarted: list[str] = []
        for loop_kind in ("search", "torrent"):
            if kind_normalized != "all" and loop_kind != kind_normalized:
                continue
            proc_attr = f"process_{loop_kind}_loop"
            process = getattr(arr, proc_attr, None)
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    webui.logger.debug(
                        "Process kill failed for %s %s", category, loop_kind, exc_info=True
                    )
                try:
                    process.terminate()
                except Exception:
                    webui.logger.debug(
                        "Process terminate failed for %s %s",
                        category,
                        loop_kind,
                        exc_info=True,
                    )
                try:
                    webui.manager.child_processes.remove(process)
                except Exception:
                    webui.logger.debug(
                        "child_processes.remove failed for %s %s",
                        category,
                        loop_kind,
                        exc_info=True,
                    )
                webui.manager._process_registry.pop(process, None)
            target = getattr(arr, f"run_{loop_kind}_loop", None)
            if target is None:
                continue
            import pathos

            new_process = pathos.helpers.mp.Process(target=target, daemon=False)
            setattr(arr, proc_attr, new_process)
            webui.manager.child_processes.append(new_process)
            webui.manager._process_registry[new_process] = {
                "category": getattr(arr, "category", ""),
                "name": getattr(arr, "_name", getattr(arr, "category", "")),
                "role": loop_kind,
            }
            new_process.start()
            restarted.append(loop_kind)
        return jsonify({"status": "ok", "restarted": restarted})

    # ``<path:category>`` (rather than the default ``<string:>``) so subcategory
    # paths like ``seed/tleech`` survive routing — see
    # ``docs/configuration/qbittorrent.md`` for the user-facing rules.
    @_dual_route("/processes/<path:category>/<kind>/restart", methods=("POST",))
    def restart_process(category: str, kind: str):
        return _restart_process(category, kind)

    @_dual_route("/processes/restart_all", methods=("POST",))
    def restart_all():
        webui._reload_all()
        return jsonify({"status": "ok"})

    @_dual_route("/arr/rebuild", methods=("POST",))
    def arr_rebuild():
        webui._reload_all()
        return jsonify({"status": "ok"})

    def _restart_arr_instance(arr):
        """Restart both search and torrent loops for an Arr instance."""
        restarted = []
        for k in ("search", "torrent"):
            proc_attr = f"process_{k}_loop"
            p = getattr(arr, proc_attr, None)
            if p is not None:
                try:
                    p.kill()
                except Exception:
                    webui.logger.debug(
                        "Process kill failed for %s %s",
                        getattr(arr, "_name", ""),
                        k,
                        exc_info=True,
                    )
                try:
                    p.terminate()
                except Exception:
                    webui.logger.debug(
                        "Process terminate failed for %s %s",
                        getattr(arr, "_name", ""),
                        k,
                        exc_info=True,
                    )
                try:
                    webui.manager.child_processes.remove(p)
                except Exception:
                    webui.logger.debug(
                        "child_processes.remove failed for %s %s",
                        getattr(arr, "_name", ""),
                        k,
                        exc_info=True,
                    )
                webui.manager._process_registry.pop(p, None)
            import pathos

            target = getattr(arr, f"run_{k}_loop", None)
            if target is None:
                continue
            new_p = pathos.helpers.mp.Process(target=target, daemon=False)
            setattr(arr, proc_attr, new_p)
            webui.manager.child_processes.append(new_p)
            webui.manager._process_registry[new_p] = {
                "category": getattr(arr, "category", ""),
                "name": getattr(arr, "_name", getattr(arr, "category", "")),
                "role": k,
            }
            new_p.start()
            restarted.append(k)
        return jsonify({"status": "ok", "restarted": restarted})

    @_dual_route("/arr/<section>/restart", methods=("POST",))
    def arr_restart(section: str):
        managed = _managed_objects()
        if not managed:
            if not _ensure_arr_manager_ready():
                return jsonify({"error": "Arr manager is still initialising"}), 503
        if section not in managed:
            return jsonify({"error": f"Unknown section {section}"}), 404
        arr = managed[section]
        return _restart_arr_instance(arr)
