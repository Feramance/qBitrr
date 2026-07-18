"""Status / meta / qBit category WebUI routes."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from flask import jsonify, request

from qBitrr.arss import PlaceHolderArr, TorrentPolicyManager
from qBitrr.utils import coerce_bool
from qBitrr.webui.auth import _auth_disabled, _local_auth_enabled, _oidc_enabled
from qBitrr.webui.urlbase import configured_url_base

if TYPE_CHECKING:
    from qBitrr.webui.app import WebUI


def register_status_routes(
    webui: WebUI,
    *,
    app: Any,
    _dual_route: Callable[..., Any],
    require_token: Callable[[], Any],
    _managed_objects: Callable[[], dict[str, Any]],
    _ensure_arr_manager_ready: Callable[[], bool],
    _webui_mod: Callable[[], Any],
) -> None:
    """Register status, meta, Arr list, and qBit category routes."""

    def _arr_list_payload() -> dict[str, Any]:
        items = []
        for k, arr in _managed_objects().items():
            t = getattr(arr, "type", None)
            if t in ("radarr", "sonarr", "lidarr"):
                name = getattr(arr, "_name", k)
                category = getattr(arr, "category", k)
                items.append({"category": category, "name": name, "type": t})
        return {"arr": items, "ready": _ensure_arr_manager_ready()}

    @_dual_route("/arr")
    def arr_list():
        return jsonify(_arr_list_payload())

    @app.get("/web/qbit/categories")
    def web_qbit_categories():
        """Get all qBit-managed and Arr-managed categories with seeding statistics."""
        if (resp := require_token()) is not None:
            return resp
        categories_data = []

        # Add qBit-managed categories
        if webui.manager.qbit_category_managers:
            for instance_name, manager in webui.manager.qbit_category_managers.items():
                client = webui.manager.get_client(instance_name)
                if not client:
                    continue

                for category in manager.managed_categories:
                    try:
                        from qBitrr.webui.routes.category_stats import summarize_category_torrents

                        torrents = client.torrents_info(category=category)
                        stats = summarize_category_torrents(list(torrents))

                        # Get seeding config for this category
                        seeding_config = manager.get_seeding_config(category)

                        categories_data.append(
                            {
                                "category": category,
                                "instance": instance_name,
                                "managedBy": "qbit",
                                **stats,
                                "seedingConfig": {
                                    "maxRatio": seeding_config.get("MaxUploadRatio", -1),
                                    "maxTime": seeding_config.get("MaxSeedingTime", -1),
                                    "removeMode": seeding_config.get("RemoveTorrent", -1),
                                    "downloadLimit": seeding_config.get(
                                        "DownloadRateLimitPerTorrent", -1
                                    ),
                                    "uploadLimit": seeding_config.get(
                                        "UploadRateLimitPerTorrent", -1
                                    ),
                                },
                            }
                        )
                    except Exception:
                        webui.logger.debug(
                            "Error fetching qBit category '%s' stats for instance '%s'",
                            category,
                            instance_name,
                        )
                        continue

        # Add Arr-managed categories (aggregate torrents across all qBit instances)
        if hasattr(webui.manager, "arr_manager") and webui.manager.arr_manager:
            from qBitrr.webui.routes.category_stats import (
                collect_torrents_for_category,
                summarize_category_torrents,
            )

            for arr in webui.manager.arr_manager.managed_objects.values():
                if isinstance(arr, (PlaceHolderArr, TorrentPolicyManager)):
                    continue
                try:
                    category = arr.category
                    torrents = collect_torrents_for_category(webui.manager, category)
                    stats = summarize_category_torrents(torrents)

                    categories_data.append(
                        {
                            "category": category,
                            "instance": arr._name,
                            "managedBy": "arr",
                            **stats,
                            "seedingConfig": {
                                "maxRatio": arr.seeding_mode_global_max_upload_ratio,
                                "maxTime": arr.seeding_mode_global_max_seeding_time,
                                "removeMode": arr.seeding_mode_global_remove_torrent,
                                "downloadLimit": arr.seeding_mode_global_download_limit,
                                "uploadLimit": arr.seeding_mode_global_upload_limit,
                            },
                        }
                    )
                except Exception:
                    webui.logger.debug(
                        "Error fetching Arr category '%s' stats for instance '%s'",
                        getattr(arr, "category", "unknown"),
                        getattr(arr, "_name", "unknown"),
                    )
                    continue

        return jsonify({"categories": categories_data, "ready": True})

    @app.get("/web/qbit/overview")
    def web_qbit_overview():
        """Get monitored categories with per-torrent details, optionally filtered by qBit instance."""
        if (resp := require_token()) is not None:
            return resp
        from qBitrr.webui.routes.category_stats import build_qbit_overview

        instance = (request.args.get("instance") or "").strip() or None
        arr_manager = getattr(webui.manager, "arr_manager", None)
        payload = build_qbit_overview(
            webui.manager,
            instance_filter=instance,
            arr_manager=arr_manager,
        )
        return jsonify(payload)

    @app.get("/api/meta")
    def api_meta():
        if (resp := require_token()) is not None:
            return resp
        force = coerce_bool(request.args.get("force"))
        return jsonify(webui._ensure_version_info(force=force))

    @app.get("/web/meta")
    def web_meta():
        force = coerce_bool(request.args.get("force"))
        result = dict(webui._ensure_version_info(force=force))
        auth_required = not _auth_disabled()
        local_auth_enabled = _local_auth_enabled()
        oidc_enabled = _oidc_enabled()
        result["auth_required"] = auth_required
        result["local_auth_enabled"] = local_auth_enabled
        result["oidc_enabled"] = oidc_enabled
        # First-time setup: auth required, no password set, no OIDC — show create-credentials screen
        stored_hash = (_webui_mod().CONFIG.get("WebUI.PasswordHash", fallback="") or "").strip()
        setup_required = auth_required and not stored_hash and not oidc_enabled
        result["setup_required"] = setup_required
        result["url_base"] = configured_url_base()
        return jsonify(result)

    def _status_payload() -> dict[str, Any]:
        # Legacy single-instance qBit info (for backward compatibility)
        qb = {
            "alive": bool(webui.manager.is_alive),
            "host": webui.manager.qBit_Host,
            "port": webui.manager.qBit_Port,
            "version": (
                str(webui.manager.current_qbit_version)
                if webui.manager.current_qbit_version
                else None
            ),
        }

        # Multi-instance qBit info
        qbit_instances = {}
        for instance_name in webui.manager.get_all_instances():
            info = webui.manager.get_instance_info(instance_name)
            qbit_instances[instance_name] = {
                "alive": webui.manager.is_instance_alive(instance_name),
                "host": info.get("host", ""),
                "port": info.get("port", 0),
                "version": info.get("version", None),
            }

        arrs = []
        for k, arr in _managed_objects().items():
            t = getattr(arr, "type", None)
            if t in ("radarr", "sonarr", "lidarr"):
                # Determine liveness based on child search/torrent processes
                alive = False
                for loop in ("search", "torrent"):
                    p = getattr(arr, f"process_{loop}_loop", None)
                    if p is not None:
                        try:
                            if p.is_alive():
                                alive = True
                                break
                        except Exception:
                            webui.logger.debug(
                                "Process is_alive check failed for %s", k, exc_info=True
                            )
                name = getattr(arr, "_name", k)
                category = getattr(arr, "category", k)
                arrs.append({"category": category, "name": name, "type": t, "alive": alive})
        # WebUI settings
        webui_settings = {
            "LiveArr": _webui_mod().CONFIG.get("WebUI.LiveArr", fallback=True),
            "Theme": _webui_mod().CONFIG.get("WebUI.Theme", fallback="Dark"),
            "ViewDensity": _webui_mod().CONFIG.get("WebUI.ViewDensity", fallback="Comfortable"),
        }

        return {
            "qbit": qb,  # Legacy single-instance (default) for backward compatibility
            "qbitInstances": qbit_instances,  # Multi-instance info
            "arrs": arrs,
            "ready": _ensure_arr_manager_ready(),
            "webui": webui_settings,
        }

    @_dual_route("/status")
    def status():
        return jsonify(_status_payload())

    @app.get("/api/torrents/distribution")
    def api_torrents_distribution():
        """Get torrent distribution across qBit instances grouped by category"""
        if (resp := require_token()) is not None:
            return resp

        distribution = {}
        for instance_name in webui.manager.get_all_instances():
            if not webui.manager.is_instance_alive(instance_name):
                continue

            try:
                client = webui.manager.get_client(instance_name)
                torrents = client.torrents.info()

                # Group by category
                for torrent in torrents:
                    category = getattr(torrent, "category", "uncategorized")
                    if category not in distribution:
                        distribution[category] = {}
                    if instance_name not in distribution[category]:
                        distribution[category][instance_name] = 0
                    distribution[category][instance_name] += 1
            except Exception:
                # Skip instances that fail
                pass

        return jsonify({"distribution": distribution})
