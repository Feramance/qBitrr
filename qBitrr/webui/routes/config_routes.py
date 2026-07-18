"""Config GET/POST/schema and Arr test-connection WebUI routes."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from flask import jsonify, request

from qBitrr.config_reload_policy import classify_config_changes
from qBitrr.logger import reconfigure_logging_from_config
from qBitrr.utils import normalize_url_base
from qBitrr.webui.config_toml import (
    REDACTED_PLACEHOLDER,
    _is_sensitive_dotted_key,
    _toml_delete,
    _toml_set,
)

if TYPE_CHECKING:
    from qBitrr.webui.app import WebUI


def register_config_routes(
    webui: WebUI,
    *,
    app: Any,
    _dual_route: Callable[..., Any],
    require_token: Callable[[], Any],
    _managed_objects: Callable[[], dict[str, Any]],
    _webui_mod: Callable[[], Any],
) -> None:
    """Register config and Arr connection-test routes."""

    def _load_redacted_config() -> dict[str, Any]:
        """Reload TOML from disk and return a JSON-safe, secret-stripped dict."""
        try:
            _webui_mod().CONFIG.load()
        except Exception:
            webui.logger.debug("CONFIG.load failed in config GET", exc_info=True)
        return _webui_mod()._strip_sensitive_keys(
            _webui_mod()._toml_to_jsonable(_webui_mod().CONFIG.config)
        )

    @app.get("/api/config")
    def api_get_config():
        if (resp := require_token()) is not None:
            return resp
        try:
            return jsonify(_load_redacted_config())
        except Exception:
            webui.logger.debug("api_get_config failed", exc_info=True)
            return jsonify({"error": "Failed to load config"}), 500

    @_dual_route("/config/schema")
    def api_config_schema():
        """Return the structured config field registry (labels, kinds, reload hints)."""
        if (resp := require_token()) is not None:
            return resp
        try:
            from qBitrr.gen_config.fields import build_config_schema

            return jsonify(build_config_schema())
        except Exception:
            webui.logger.debug("api_config_schema failed", exc_info=True)
            return jsonify({"error": "Failed to load config schema"}), 500

    @app.get("/web/config")
    def web_get_config():
        if (resp := require_token()) is not None:
            return resp
        try:
            data = _load_redacted_config()

            # Check config version and add warning if mismatch
            from qBitrr.config_version import get_config_version, validate_config_version

            is_valid, validation_result = validate_config_version(_webui_mod().CONFIG)
            if not is_valid:
                # Add version mismatch warning to response
                response_data = {
                    "config": data,
                    "warning": {
                        "type": "config_version_mismatch",
                        "message": validation_result,
                        "currentVersion": get_config_version(_webui_mod().CONFIG),
                    },
                }
                return jsonify(response_data)

            return jsonify(data)
        except Exception:
            webui.logger.debug("web_get_config failed", exc_info=True)
            return jsonify({"error": "Failed to load config"}), 500

    def _handle_config_update():
        """Common handler for config updates with intelligent reload detection."""
        body = request.get_json(silent=True) or {}
        changes: dict[str, Any] = body.get("changes", {})
        if not isinstance(changes, dict):
            return jsonify({"error": "changes must be an object"}), 400

        # Prevent ConfigVersion from being modified by user
        protected_keys = {"Settings.ConfigVersion"}
        for key in protected_keys:
            if key in changes:
                return (
                    jsonify({"error": f"Cannot modify protected configuration key: {key}"}),
                    403,
                )

        # Analyze changes to determine reload strategy
        plan = classify_config_changes(changes)

        previous_token = webui.token

        # Apply all changes to in-memory config first (not persisted until validated)
        for key, val in changes.items():
            if val is None:
                _toml_delete(_webui_mod().CONFIG.config, key)
                if key == "WebUI.Token":
                    webui.token = ""
                continue
            # Never overwrite a real secret with the redaction placeholder from the client
            if _is_sensitive_dotted_key(key) and str(val).strip() == REDACTED_PLACEHOLDER:
                continue
            if key == "WebUI.UrlBase":
                val = normalize_url_base(str(val) if val is not None else "")
            _toml_set(_webui_mod().CONFIG.config, key, val)
            if key == "WebUI.Token":
                # Update in-memory token for validation context only
                webui.token = str(val) if val is not None else ""

        from qBitrr.webui.config_validate import validate_config_update

        validation_errors = validate_config_update(_webui_mod().CONFIG, changes)
        if validation_errors:
            # Roll back in-memory edits; do not persist or reload
            try:
                _webui_mod().CONFIG.load()
            except Exception:
                webui.logger.debug("CONFIG.load failed during validation rollback", exc_info=True)
            webui.token = previous_token
            return (
                jsonify(
                    {
                        "error": "Configuration validation failed",
                        "validationErrors": validation_errors,
                    }
                ),
                400,
            )

        # Persist config
        try:
            _webui_mod().CONFIG.save()
        except Exception:
            webui.logger.debug("Failed to save config", exc_info=True)
            return jsonify({"error": "Failed to save config"}), 500

        # Determine reload strategy from classified plan
        reload_type = plan.primary_reload_type()
        affected_instances_list = sorted(plan.affected_arr_instances)

        if plan.needs_full_restart:
            from qBitrr.webui.lifecycle import full_restart_is_placeholder_rename_only

            delete_arr_dbs = not full_restart_is_placeholder_rename_only(plan.full_restart_keys)
            webui.logger.notice(
                "Full restart required for keys: %s (delete_arr_dbs=%s)",
                ", ".join(plan.full_restart_keys),
                delete_arr_dbs,
            )
            try:
                webui.manager.configure_auto_update()
            except Exception:
                webui.logger.exception("Failed to refresh auto update configuration")
            webui._reload_all(delete_arr_dbs=delete_arr_dbs)

        else:
            if plan.has_arr_worker_reload:
                reset_instances = set(plan.arr_reset_instances)
                respawn_instances = set(plan.arr_respawn_instances) - reset_instances
                all_reload = sorted(reset_instances | respawn_instances)
                affected_instances_list = all_reload
                reload_type = "multi_arr" if len(all_reload) > 1 else "single_arr"
                webui.logger.notice(
                    "Reloading %d Arr instance(s): %s",
                    len(all_reload),
                    ", ".join(all_reload),
                )
                for instance_name in all_reload:
                    preserve_db = instance_name not in reset_instances
                    webui._reload_arr_instance(instance_name, preserve_db=preserve_db)

            if plan.arr_live_instances:
                webui.logger.notice(
                    "Applying live Arr config refresh for: %s",
                    ", ".join(sorted(plan.arr_live_instances)),
                )
                webui._apply_arr_live_refresh(plan)

            if plan.needs_qbit_hot:
                webui.logger.notice(
                    "Applying qBit hot reload for sections: %s",
                    ", ".join(sorted(plan.qbit_hot_sections)),
                )
                webui.manager.refresh_qbit_hot()

            if plan.live_keys:
                webui.logger.notice(
                    "Live settings changed (no worker restart): %s",
                    ", ".join(plan.live_keys),
                )

            if any(k.startswith("Settings.AutoUpdate") for k in plan.live_keys):
                try:
                    webui.manager.configure_auto_update()
                except Exception:
                    webui.logger.exception("Failed to refresh auto update configuration")

            if "Settings.ConsoleLevel" in plan.live_keys:
                try:
                    reconfigure_logging_from_config()
                except Exception:
                    webui.logger.exception("Failed to reconfigure logging from config")

            if plan.needs_webui_restart:
                webui.logger.notice("WebUI settings changed, restarting WebUI server")
                restart_thread = threading.Thread(
                    target=webui._restart_webui, name="WebUIRestart", daemon=True
                )
                restart_thread.start()
                if reload_type == "none" and not plan.has_arr_worker_reload:
                    reload_type = "webui"

            if plan.frontend_keys and reload_type == "none":
                webui.logger.debug("Frontend-only settings changed, no reload required")

            if reload_type == "none" and (
                plan.live_keys or plan.arr_live_instances or plan.needs_qbit_hot
            ):
                reload_type = plan.primary_reload_type()

        # Build response
        response_data = {
            "status": "ok",
            "configReloaded": reload_type not in ("none", "frontend"),
            "reloadType": reload_type,
            "affectedInstances": affected_instances_list,
        }

        response = jsonify(response_data)

        # Add headers for cache control
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        # Legacy header for compatibility
        if reload_type in ("full", "single_arr", "multi_arr", "webui", "live", "qbit_hot"):
            response.headers["X-Config-Reloaded"] = "true"

        return response

    @_dual_route("/config", methods=("POST",))
    def update_config():
        return _handle_config_update()

    def _handle_test_connection():
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "Missing request body"}), 400

            arr_type = data.get("arrType")  # "radarr" | "sonarr" | "lidarr"
            instance_key = data.get("instanceKey")
            uri = data.get("uri")
            api_key = data.get("apiKey")

            # When instanceKey is provided, load URI and APIKey from config (e.g. redacted UI)
            if instance_key:
                if not arr_type:
                    return (
                        jsonify({"success": False, "message": "Missing required field: arrType"}),
                        400,
                    )
                try:
                    _webui_mod().CONFIG.load()
                except Exception:
                    pass
                uri = _webui_mod().CONFIG.get(f"{instance_key}.URI", fallback=None)
                api_key = _webui_mod().CONFIG.get(f"{instance_key}.APIKey", fallback=None)
                if not uri or not api_key:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": "Instance not found or missing URI/APIKey in config",
                            }
                        ),
                        400,
                    )

            # Validate inputs (uri and api_key either from body or from instanceKey path above)
            if not all([arr_type, uri, api_key]):
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Missing required fields: arrType, uri, or apiKey",
                        }
                    ),
                    400,
                )

            from urllib.parse import urlparse as _urlparse

            parsed = _urlparse(uri)
            if parsed.scheme not in ("http", "https"):
                return (
                    jsonify({"success": False, "message": "URI must use http or https scheme"}),
                    400,
                )
            if not parsed.hostname:
                return (
                    jsonify({"success": False, "message": "URI must contain a valid hostname"}),
                    400,
                )

            # Try to find existing Arr instance with matching URI
            existing_arr = None
            managed = _managed_objects()
            for group_name, arr_instance in managed.items():
                if hasattr(arr_instance, "uri") and hasattr(arr_instance, "apikey"):
                    if arr_instance.uri == uri and arr_instance.apikey == api_key:
                        existing_arr = arr_instance
                        webui.logger.info("Using existing Arr instance: %s", group_name)
                        break

            # Use existing client if available, otherwise create temporary one
            if existing_arr and hasattr(existing_arr, "client"):
                client = existing_arr.client
                webui.logger.info("Reusing existing client for %s", existing_arr._name)
            else:
                # Create temporary Arr API client
                webui.logger.info("Creating temporary %s client for %s", arr_type, uri)
                if instance_key:
                    skip_tls_servarr = _webui_mod().CONFIG.get(
                        f"{instance_key}.SkipTLSVerify", fallback=False
                    )
                else:
                    skip_tls_servarr = bool(data.get("skipTlsVerify", False))
                verify_ssl = not skip_tls_servarr
                if arr_type == "radarr":
                    from qBitrr.arr_client import build_radarr_client

                    client = build_radarr_client(uri, api_key, verify_ssl=verify_ssl)
                elif arr_type == "sonarr":
                    from qBitrr.arr_client import build_sonarr_client

                    client = build_sonarr_client(uri, api_key, verify_ssl=verify_ssl)
                elif arr_type == "lidarr":
                    from qBitrr.arr_client import build_lidarr_client

                    client = build_lidarr_client(uri, api_key, verify_ssl=verify_ssl)
                else:
                    return (
                        jsonify({"success": False, "message": f"Invalid arrType: {arr_type}"}),
                        400,
                    )

            # Test connection (no timeout - Flask/Waitress handles this)
            try:
                webui.logger.info("Testing connection to %s at %s", arr_type, uri)

                # Get system info to verify connection
                system_info = client.system.get_status()
                webui.logger.info(
                    "System status retrieved: %s", system_info.get("version", "unknown")
                )

                # Fetch quality profiles with retry logic (same as backend)
                from json import JSONDecodeError

                import requests

                from qBitrr.arr_client import PyarrServerError

                max_retries = 3
                retry_count = 0
                quality_profiles = []

                while retry_count < max_retries:
                    try:
                        quality_profiles = client.quality_profile.get()
                        webui.logger.info(
                            "Quality profiles retrieved: %d profiles", len(quality_profiles)
                        )
                        break
                    except (
                        requests.exceptions.ChunkedEncodingError,
                        requests.exceptions.ContentDecodingError,
                        requests.exceptions.ConnectionError,
                        JSONDecodeError,
                    ) as e:
                        retry_count += 1
                        webui.logger.warning(
                            "Transient error fetching quality profiles (attempt %d/%d): %s",
                            retry_count,
                            max_retries,
                            e,
                        )
                        if retry_count >= max_retries:
                            webui.logger.error("Failed to fetch quality profiles after retries")
                            quality_profiles = []
                            break
                        _webui_mod().time.sleep(1)
                    except PyarrServerError as e:
                        webui.logger.error("Server error fetching quality profiles: %s", e)
                        quality_profiles = []
                        break
                    except Exception as e:
                        webui.logger.error("Unexpected error fetching quality profiles: %s", e)
                        quality_profiles = []
                        break

                # Format response
                return jsonify(
                    {
                        "success": True,
                        "message": "Connected successfully",
                        "systemInfo": {
                            "version": system_info.get("version", "unknown"),
                            "branch": system_info.get("branch"),
                        },
                        "qualityProfiles": [
                            {"id": p["id"], "name": p["name"]} for p in quality_profiles
                        ],
                    }
                )

            except Exception as e:
                # Handle specific error types. Return 200 with success: false so the
                # frontend does not treat Arr errors as WebUI auth failure (which uses 401).
                error_msg = str(e)
                # Log full error for debugging but sanitize user-facing message
                webui.logger.error("Connection test failed: %s", error_msg)

                if "401" in error_msg or "Unauthorized" in error_msg:
                    return jsonify({"success": False, "message": "Unauthorized: Invalid API key"})
                elif "404" in error_msg:
                    return jsonify({"success": False, "message": f"Not found: Check URI ({uri})"})
                elif "Connection refused" in error_msg or "ConnectionError" in error_msg:
                    return jsonify(
                        {
                            "success": False,
                            "message": f"Connection refused: Cannot reach {uri}",
                        }
                    )
                else:
                    # Generic error message - details logged above
                    return (
                        jsonify({"success": False, "message": "Connection test failed"}),
                        500,
                    )

        except Exception as e:
            webui.logger.error("Test connection error: %s", e)
            return jsonify({"success": False, "message": "Connection test failed"}), 500

    @_dual_route("/arr/test-connection", methods=("POST",))
    def arr_test_connection():
        return _handle_test_connection()
