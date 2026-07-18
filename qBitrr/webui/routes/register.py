from __future__ import annotations

import io
import logging
import os
import re
import secrets
import threading
from collections.abc import Mapping
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Response, jsonify, redirect, request, send_file, session

from qBitrr.arss import PlaceHolderArr, TorrentPolicyManager
from qBitrr.config import HOME_PATH
from qBitrr.config_reload_policy import classify_config_changes
from qBitrr.logger import reconfigure_logging_from_config
from qBitrr.search_activity_store import clear_search_activity
from qBitrr.utils import coerce_bool, normalize_url_base
from qBitrr.webui.auth import (
    _auth_disabled,
    _local_auth_enabled,
    _login_limiter,
    _oidc_enabled,
    _pw_hash,
    _pw_verify,
    _setpw_limiter,
    _setpw_lock,
)
from qBitrr.webui.catalog.common import (
    parse_catalog_filters,
    resolve_arr_handler,
)
from qBitrr.webui.catalog.safety import _arr_catalog_db_safe
from qBitrr.webui.config_toml import (
    REDACTED_PLACEHOLDER,
    _is_sensitive_dotted_key,
    _toml_delete,
    _toml_set,
)
from qBitrr.webui.openapi_ui import (
    _if_none_match_includes_etag,
    _load_openapi_spec_api_only,
    _swagger_ui_html,
)
from qBitrr.webui.routing import dual_route
from qBitrr.webui.urlbase import configured_url_base
from qBitrr.webui_thumbnails import (
    get_or_fetch_thumbnail,
    thumbnail_quoted_etag,
)


def _webui_mod():
    import qBitrr.webui as webui_mod

    return webui_mod


if TYPE_CHECKING:
    from qBitrr.webui.app import WebUI


def register_routes(webui: WebUI) -> None:
    app = webui.app
    logs_root = (HOME_PATH / "logs").resolve()

    def _resolve_log_file(name: str) -> Path | None:
        # Restrict to safe log file names (alphanumeric, dash, underscore, dot)
        if not name or not name.strip():
            return None
        safe = "".join(c for c in name if c.isalnum() or c in "._-").strip() or None
        if safe is None or safe != name:
            webui.logger.debug("Rejected log file name (invalid characters): %r", name)
            return None
        try:
            candidate = (logs_root / safe).resolve(strict=False)
        except Exception:
            webui.logger.debug("Failed to resolve log path for %r", safe, exc_info=True)
            return None
        try:
            candidate.relative_to(logs_root)
        except ValueError:
            return None
        return candidate

    def _managed_objects() -> dict[str, Any]:
        arr_manager = getattr(webui.manager, "arr_manager", None)
        return getattr(arr_manager, "managed_objects", {}) if arr_manager else {}

    def _ensure_arr_manager_ready() -> bool:
        return getattr(webui.manager, "arr_manager", None) is not None

    def _resolve_managed_lidarr(category: str) -> Any | None:
        """Resolve a Lidarr ``Arr`` from the URL *category* segment.

        ``managed_objects`` keys are instance/qBittorrent category strings, not type
        names. Some callers use the type slug ``lidarr`` (e.g. OpenAPI defaults);
        when exactly one Lidarr instance exists, resolve it unambiguously.
        """
        managed = _managed_objects()
        if not managed:
            return None
        arr = managed.get(category)
        if arr is not None:
            return arr if getattr(arr, "type", None) == "lidarr" else None
        slug = (category or "").strip().lower()
        if slug != "lidarr":
            return None
        matches = [a for a in managed.values() if getattr(a, "type", None) == "lidarr"]
        resolved = matches[0] if len(matches) == 1 else None
        return resolved

    def _lidarr_page_size_from_request(default: int = 50) -> int:
        """``page_size`` with ``size`` as alias (some clients send only ``size``)."""
        ps = request.args.get("page_size", type=int)
        sz = request.args.get("size", type=int)
        if ps is not None:
            return min(ps, 1000)
        if sz is not None:
            return min(sz, 1000)
        return default

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    def _public_url(path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        prefix = request.script_root.rstrip("/") or configured_url_base()
        return f"{prefix}{path}" if prefix else path

    @app.get("/")
    def index():
        return redirect(_public_url("/ui"))

    def _get_supplied_token() -> str | None:
        _webui_logger = logging.getLogger("qBitrr.WebUI")

        header_token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if header_token:
            return header_token
        query_token = request.args.get("token")
        if query_token:
            _webui_logger.warning(
                "Token supplied via query parameter from %s — this is insecure "
                "(token visible in logs and browser history). Use Authorization header instead.",
                request.remote_addr,
            )
            return query_token
        return None

    def _has_authenticated_principal() -> bool:
        supplied = _get_supplied_token()
        if supplied and webui.token and secrets.compare_digest(supplied, webui.token):
            return True
        return bool(session.get("authenticated"))

    def _authorized():

        # Auth disabled globally → always authorized
        if _auth_disabled():
            return True
        # Bearer token (API path) — constant-time comparison
        # Session cookie (web login path)
        return _has_authenticated_principal()

    def require_token():
        if not _authorized():
            return jsonify({"error": "unauthorized"}), 401
        return None

    def _dual_route(path: str, *, methods: tuple[str, ...] = ("GET",)) -> Any:
        """Register token-guarded identical ``/api`` and ``/web`` routes."""

        def decorator(fn: Any) -> Any:
            @wraps(fn)
            def guarded(*args: Any, **kwargs: Any) -> Any:
                if (resp := require_token()) is not None:
                    return resp
                return fn(*args, **kwargs)

            dual_route(app, path, methods=methods)(guarded)
            return fn

        return decorator

    def _openapi_json_response():
        spec = _load_openapi_spec_api_only()
        response = jsonify(spec)
        response.headers["Cache-Control"] = "no-store"
        return response

    def _swagger_ui_response(spec_path: str):
        from flask import make_response

        response = make_response(_swagger_ui_html(spec_path))
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        response.headers["Cache-Control"] = "no-store"
        return response

    @_dual_route("/openapi.json")
    def openapi_json():
        return _openapi_json_response()

    def _swagger_docs_response():
        spec_path = (
            _public_url("/api/openapi.json")
            if request.path.startswith("/api")
            else _public_url("/web/openapi.json")
        )
        return _swagger_ui_response(spec_path)

    @_dual_route("/docs")
    def swagger_docs():
        return _swagger_docs_response()

    @app.get("/ui")
    def ui_index():
        # Serve UI without requiring a token; API remains protected
        # Add cache-busting parameter based on config reload timestamp
        from flask import make_response

        response = make_response(redirect(_public_url("/static/index.html")))
        # Prevent caching of the UI entry point
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.get("/sw.js")
    def service_worker():
        # Service worker must be served directly (not redirected) for PWA support
        # This allows the endpoint to be whitelisted in auth proxies (e.g., Authentik)
        pass

        from flask import send_from_directory

        static_root = Path(__file__).resolve().parent.parent.parent / "static"
        response = send_from_directory(str(static_root), "sw.js")
        # Prevent caching of the service worker to ensure updates are picked up
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.get("/login")
    def login_page():
        return redirect(_public_url("/ui"))

    @app.post("/web/login")
    def web_login():
        ip = request.remote_addr or "unknown"
        if not _login_limiter.allow(ip):
            return jsonify({"error": "Too many login attempts. Try again later."}), 429
        if not _local_auth_enabled():
            return jsonify({"error": "Local login not configured"}), 400
        body = request.get_json(silent=True) or {}
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", ""))
        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400
        stored_hash = _webui_mod().CONFIG.get("WebUI.PasswordHash", fallback="") or ""
        if not stored_hash:
            return jsonify({"error": "Password not set", "code": "SETUP_REQUIRED"}), 403
        # Always verify both to prevent timing-based username enumeration
        pw_ok = _pw_verify(password, stored_hash)
        stored_username = _webui_mod().CONFIG.get("WebUI.Username", fallback="") or ""
        user_ok = bool(stored_username) and secrets.compare_digest(username, stored_username)
        if not pw_ok or not user_ok:
            return jsonify({"error": "Invalid credentials"}), 401
        session.permanent = True
        session["authenticated"] = True
        session["username"] = username
        webui.logger.info("User %s logged in via local auth", username)
        return jsonify({"success": True})

    @app.post("/web/logout")
    def web_logout():
        session.clear()
        return jsonify({"success": True})

    @app.post("/web/auth/set-password")
    def web_set_password():
        ip = request.remote_addr or "unknown"
        if not _setpw_limiter.allow(ip):
            return jsonify({"error": "Too many attempts. Try again later."}), 429
        body = request.get_json(silent=True) or {}
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", ""))
        setup_token = str(body.get("setupToken", "")).strip()
        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400
        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400
        env_token = os.environ.get("QBITRR_SETUP_TOKEN", "")
        token_ok = bool(setup_token) and (
            (bool(env_token) and secrets.compare_digest(setup_token, env_token))
            or (bool(webui.token) and secrets.compare_digest(setup_token, webui.token))
        )
        with _setpw_lock:
            stored_hash = _webui_mod().CONFIG.get("WebUI.PasswordHash", fallback="") or ""
            first_time = not stored_hash
            if not (token_ok or _has_authenticated_principal()):
                if first_time:
                    return (
                        jsonify(
                            {
                                "error": (
                                    "Setup token required. Use QBITRR_SETUP_TOKEN or the "
                                    "WebUI.Token value from config.toml."
                                )
                            }
                        ),
                        403,
                    )
                return jsonify({"error": "Not allowed"}), 403
            new_hash = _pw_hash(password)
            try:
                _toml_set(_webui_mod().CONFIG.config, "WebUI.Username", username)
                _toml_set(_webui_mod().CONFIG.config, "WebUI.PasswordHash", new_hash)
                _toml_set(_webui_mod().CONFIG.config, "WebUI.AuthDisabled", False)
                _toml_set(_webui_mod().CONFIG.config, "WebUI.LocalAuthEnabled", True)
                _webui_mod().CONFIG.save()
            except Exception:
                webui.logger.error("Failed to save config after set-password", exc_info=True)
                return jsonify({"error": "Failed to save configuration"}), 500
        webui.logger.info("Password set for user %s", username)
        return jsonify({"success": True})

    oidc_callback_path = (
        _webui_mod().CONFIG.get("WebUI.OIDC.CallbackPath", fallback="/signin-oidc")
        or "/signin-oidc"
    )
    if not oidc_callback_path.startswith("/"):
        oidc_callback_path = f"/{oidc_callback_path}"

    @app.get("/web/auth/oidc/challenge")
    def web_oidc_challenge():
        if not _oidc_enabled():
            return jsonify({"error": "OIDC not configured"}), 400
        url_base = configured_url_base()
        redirect_uri = request.host_url.rstrip("/") + url_base + oidc_callback_path
        return webui._oauth.oidc.authorize_redirect(redirect_uri)

    @app.get(oidc_callback_path)
    def web_oidc_callback():
        if not _oidc_enabled():
            return redirect(_public_url("/ui"))
        try:
            token = webui._oauth.oidc.authorize_access_token()
            userinfo = token.get("userinfo") or webui._oauth.oidc.userinfo()
            username = userinfo.get("preferred_username") or userinfo.get("email") or "oidc-user"
            session.permanent = True
            session["authenticated"] = True
            session["username"] = username
            webui.logger.info("User %s logged in via OIDC", username)
        except Exception:
            webui.logger.warning("OIDC callback failed", exc_info=True)
            return redirect(_public_url("/ui?auth_error=1"))
        return redirect(_public_url("/ui"))

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

    def _handle_loglevel():
        body = request.get_json(silent=True) or {}
        level = str(body.get("level", "INFO")).upper()
        valid = {"CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"}
        if level not in valid:
            return jsonify({"error": f"invalid level {level}"}), 400
        try:
            _toml_set(_webui_mod().CONFIG.config, "Settings.ConsoleLevel", level)
            _webui_mod().CONFIG.save()
        except Exception:
            webui.logger.debug("Failed to persist log level to config", exc_info=True)
        reconfigure_logging_from_config()
        return jsonify({"status": "ok", "level": level})

    @_dual_route("/loglevel", methods=("POST",))
    def loglevel():
        return _handle_loglevel()

    @_dual_route("/arr/rebuild", methods=("POST",))
    def arr_rebuild():
        webui._reload_all()
        return jsonify({"status": "ok"})

    def _list_logs() -> list[str]:
        if not logs_root.exists():
            return []
        log_files = sorted(f.name for f in logs_root.glob("*.log*"))
        return log_files

    @_dual_route("/logs")
    def logs():
        return jsonify({"files": _list_logs()})

    def _read_tail(path: Path, n: int, offset: int = 0) -> str:
        """Read n lines from the end of the file, optionally skipping the last `offset` lines.
        So offset=0 returns the last n lines; offset=2000 returns the n lines before that.
        """
        if n <= 0:
            return ""
        to_read = n + offset
        if to_read <= 0:
            return ""
        try:
            size = path.stat().st_size
        except OSError:
            return ""
        if size == 0:
            return ""
        chunk_size = 65536
        with path.open("rb") as f:
            buf = b""
            pos = size
            while pos > 0:
                read_size = min(chunk_size, pos)
                pos -= read_size
                f.seek(pos)
                buf = f.read(read_size) + buf
                text = buf.decode("utf-8", errors="ignore")
                if text.count("\n") + (1 if text.rstrip("\n") else 0) >= to_read:
                    break
            text = buf.decode("utf-8", errors="ignore")
        lines = text.splitlines()
        total = len(lines)
        if total <= offset:
            return ""
        # Return the n lines ending at (end - offset): lines[-(offset+n):-offset] or lines[-n:] when offset==0
        start = -(offset + n) if (offset + n) <= total else 0
        end = -offset if offset > 0 else total
        if start >= end:
            return ""
        return "\n".join(lines[start:end])

    def _serve_log_content(name: str):
        file = _resolve_log_file(name)
        if file is None or not file.exists():
            return jsonify({"error": "not found"}), 404
        lines_param = request.args.get("lines", type=int)
        offset_param = request.args.get("offset", default=0, type=int)
        try:
            if lines_param is not None and lines_param > 0:
                content = _read_tail(
                    file,
                    min(lines_param, 50000),
                    offset=max(0, offset_param),
                )
            else:
                content = file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            webui.logger.debug("Failed to read log file %s", file, exc_info=True)
            content = ""
        response = send_file(
            io.BytesIO(content.encode("utf-8")),
            mimetype="text/plain",
            as_attachment=False,
        )
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @_dual_route("/logs/<name>")
    def log(name: str):
        return _serve_log_content(name)

    def _log_download(name: str):
        file = _resolve_log_file(name)
        if file is None or not file.exists():
            return jsonify({"error": "not found"}), 404
        return send_file(file, as_attachment=True)

    @_dual_route("/logs/<name>/download")
    def log_download(name: str):
        return _log_download(name)

    @_arr_catalog_db_safe
    def _handle_radarr_movies(category: str):
        managed = _managed_objects()
        arr, err = resolve_arr_handler(
            category,
            "radarr",
            managed,
            arr_manager_ready=_ensure_arr_manager_ready(),
        )
        if err is not None:
            return err
        filters = parse_catalog_filters(request, default_page_size=50)
        year_min = request.args.get("year_min", default=None, type=int)
        year_max = request.args.get("year_max", default=None, type=int)
        monitored = (
            coerce_bool(request.args.get("monitored")) if "monitored" in request.args else None
        )
        has_file = (
            coerce_bool(request.args.get("has_file")) if "has_file" in request.args else None
        )
        quality_met = (
            coerce_bool(request.args.get("quality_met")) if "quality_met" in request.args else None
        )
        is_request = (
            coerce_bool(request.args.get("is_request")) if "is_request" in request.args else None
        )
        payload = webui._radarr_movies_from_db(
            arr,
            filters["q"],
            filters["page"],
            filters["page_size"],
            year_min=year_min,
            year_max=year_max,
            monitored=monitored,
            has_file=has_file,
            quality_met=quality_met,
            is_request=is_request,
        )
        payload["category"] = category
        return jsonify(payload)

    @_dual_route("/radarr/<path:category>/movies")
    def radarr_movies(category: str):
        return _handle_radarr_movies(category)

    def _arr_thumbnail(category: str, kind: str, entry_id: int) -> Response | tuple[Any, int]:
        managed = _managed_objects()
        if not managed:
            if not _ensure_arr_manager_ready():
                return jsonify({"error": "Arr manager is still initialising"}), 503
        expected_type = "lidarr" if kind == "lidarr_artist" else kind
        if kind == "lidarr_artist":
            arr = _resolve_managed_lidarr(category)
        else:
            arr = managed.get(category)
        arr_type = getattr(arr, "type", None) if arr is not None else None
        if arr is None or arr_type != expected_type:
            return jsonify({"error": f"Unknown {kind} category {category}"}), 404
        name = getattr(arr, "_name", category)
        # ``private`` rather than ``public``: session/token-bearing responses must not be
        # cached by shared proxies.
        cache_headers = {
            "Cache-Control": "private, max-age=86400",
        }
        inm = request.headers.get("If-None-Match")
        etag = thumbnail_quoted_etag(kind=kind, instance_name=name, entry_id=entry_id)
        if etag:
            cache_headers["ETag"] = etag
            if _if_none_match_includes_etag(inm, etag):
                return Response(status=304, headers=cache_headers)
        out = get_or_fetch_thumbnail(kind=kind, instance_name=name, arr=arr, entry_id=entry_id)
        if not out:
            return "", 404
        if out.digest_hex:
            etag_after = f'"{out.digest_hex}"'
            cache_headers["ETag"] = etag_after
            if _if_none_match_includes_etag(inm, etag_after):
                return Response(status=304, headers=cache_headers)
        if out.path is not None:
            resp = send_file(
                out.path,
                mimetype=out.mime,
                conditional=False,
                etag=False,
                max_age=86400,
            )
            for key, value in cache_headers.items():
                resp.headers[key] = value
            return resp
        if out.data is None:
            return "", 404
        return Response(out.data, mimetype=out.mime, headers=cache_headers)

    @_dual_route("/radarr/<path:category>/movie/<int:entry_id>/thumbnail")
    def radarr_thumb(category: str, entry_id: int):
        return _arr_thumbnail(category, "radarr", entry_id)

    @_arr_catalog_db_safe
    def _handle_sonarr_series(category: str):
        managed = _managed_objects()
        arr, err = resolve_arr_handler(
            category,
            "sonarr",
            managed,
            arr_manager_ready=_ensure_arr_manager_ready(),
        )
        if err is not None:
            return err
        filters = parse_catalog_filters(
            request,
            default_page_size=25,
            include_missing_only=True,
        )
        payload = webui._sonarr_series_from_db(
            arr,
            filters["q"],
            filters["page"],
            filters["page_size"],
            missing_only=filters["missing_only"],
        )
        payload["category"] = category
        return jsonify(payload)

    @_dual_route("/sonarr/<path:category>/series")
    def sonarr_series(category: str):
        return _handle_sonarr_series(category)

    @_dual_route("/sonarr/<path:category>/series/<int:entry_id>/thumbnail")
    def sonarr_thumb(category: str, entry_id: int):
        return _arr_thumbnail(category, "sonarr", entry_id)

    @_arr_catalog_db_safe
    def _handle_lidarr_albums(category: str):
        managed = _managed_objects()
        arr, err = resolve_arr_handler(
            category,
            "lidarr",
            managed,
            arr_manager_ready=_ensure_arr_manager_ready(),
            slug_resolver=_resolve_managed_lidarr,
        )
        if err is not None:
            return err
        filters = parse_catalog_filters(request, default_page_size=50)
        page_size = _lidarr_page_size_from_request(filters["page_size"])
        monitored = (
            coerce_bool(request.args.get("monitored")) if "monitored" in request.args else None
        )
        has_file = (
            coerce_bool(request.args.get("has_file")) if "has_file" in request.args else None
        )
        quality_met = (
            coerce_bool(request.args.get("quality_met")) if "quality_met" in request.args else None
        )
        is_request = (
            coerce_bool(request.args.get("is_request")) if "is_request" in request.args else None
        )
        flat_mode = coerce_bool(request.args.get("flat_mode", False))
        # Optional ``group_by_artist=0`` pages by album rows. Default remains
        # artist-grouped payloads; that mode reports artist-count ``total`` so
        # aggregate clients stop after the last artist page instead of looping
        # on the album rollup count.
        if "group_by_artist" in request.args:
            group_by_artist = coerce_bool(request.args.get("group_by_artist"))
        else:
            group_by_artist = True

        if flat_mode:
            payload = webui._lidarr_tracks_from_db(
                arr,
                filters["q"],
                filters["page"],
                page_size,
                monitored=monitored,
                has_file=has_file,
            )
        else:
            payload = webui._lidarr_albums_from_db(
                arr,
                filters["q"],
                filters["page"],
                page_size,
                monitored=monitored,
                has_file=has_file,
                quality_met=quality_met,
                is_request=is_request,
                group_by_artist=group_by_artist,
            )
        payload["category"] = str(arr.category)
        return jsonify(payload)

    @_dual_route("/lidarr/<path:category>/albums")
    def lidarr_albums(category: str):
        return _handle_lidarr_albums(category)

    @_arr_catalog_db_safe
    def _handle_lidarr_artists(category: str):
        managed = _managed_objects()
        arr, err = resolve_arr_handler(
            category,
            "lidarr",
            managed,
            arr_manager_ready=_ensure_arr_manager_ready(),
            slug_resolver=_resolve_managed_lidarr,
        )
        if err is not None:
            return err
        filters = parse_catalog_filters(
            request,
            default_page_size=50,
            include_missing_only=True,
            include_reason=True,
        )
        page_size = _lidarr_page_size_from_request(filters["page_size"])
        monitored = (
            coerce_bool(request.args.get("monitored")) if "monitored" in request.args else None
        )
        reason = filters.get("reason")
        if reason and reason.strip().lower() == "all":
            reason = None
        payload = webui._lidarr_artists_from_db(
            arr,
            filters["q"],
            filters["page"],
            page_size,
            monitored=monitored,
            missing_only=filters["missing_only"],
            reason_filter=reason,
        )
        payload["category"] = str(arr.category)
        return jsonify(payload)

    @_arr_catalog_db_safe
    def _handle_lidarr_artist_detail(category: str, artist_id: int):
        managed = _managed_objects()
        arr, err = resolve_arr_handler(
            category,
            "lidarr",
            managed,
            arr_manager_ready=_ensure_arr_manager_ready(),
            slug_resolver=_resolve_managed_lidarr,
        )
        if err is not None:
            return err
        detail = webui._lidarr_artist_detail_from_db(arr, artist_id)
        if detail is None:
            return jsonify({"error": "Artist not found"}), 404
        detail["category"] = str(arr.category)
        return jsonify(detail)

    @_dual_route("/lidarr/<path:category>/artists")
    def lidarr_artists(category: str):
        return _handle_lidarr_artists(category)

    @_dual_route("/lidarr/<path:category>/artist/<int:artist_id>")
    def lidarr_artist_detail(category: str, artist_id: int):
        return _handle_lidarr_artist_detail(category, artist_id)

    @_dual_route("/lidarr/<path:category>/artist/<int:artist_id>/thumbnail")
    def lidarr_artist_thumb(category: str, artist_id: int):
        return _arr_thumbnail(category, "lidarr_artist", artist_id)

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
                        torrents = client.torrents_info(category=category)

                        # Calculate statistics
                        total_count = len(torrents)
                        seeding_count = len(
                            [t for t in torrents if t.state in ("uploading", "stalledUP")]
                        )
                        total_size = sum(t.size for t in torrents)
                        avg_ratio = (
                            sum(t.ratio for t in torrents) / total_count if total_count else 0
                        )
                        avg_seeding_time = (
                            sum(t.seeding_time for t in torrents) / total_count
                            if total_count
                            else 0
                        )

                        # Get seeding config for this category
                        seeding_config = manager.get_seeding_config(category)

                        categories_data.append(
                            {
                                "category": category,
                                "instance": instance_name,
                                "managedBy": "qbit",
                                "torrentCount": total_count,
                                "seedingCount": seeding_count,
                                "totalSize": total_size,
                                "avgRatio": round(avg_ratio, 2),
                                "avgSeedingTime": avg_seeding_time,
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

    def _handle_update():
        ok, message = webui._trigger_manual_update()
        if not ok:
            return jsonify({"error": message}), 409
        return jsonify({"status": "started"})

    @_dual_route("/update", methods=("POST",))
    def update():
        return _handle_update()

    def _handle_download_update():
        from qBitrr.auto_update import get_installation_type

        install_type = get_installation_type()

        if install_type != "binary":
            return jsonify({"error": "Download only available for binary installations"}), 400

        version_info = webui._ensure_version_info()

        if not version_info.get("update_available"):
            return jsonify({"error": "No update available"}), 404

        download_url = version_info.get("binary_download_url")
        if not download_url:
            error = version_info.get(
                "binary_download_error", "No binary available for your platform"
            )
            return jsonify({"error": error}), 404

        from flask import redirect

        return redirect(download_url)

    @_dual_route("/download-update")
    def download_update():
        return _handle_download_update()

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

    @app.get("/api/token")
    def api_token():
        if (resp := require_token()) is not None:
            return resp
        # Expose token for API clients only; UI uses /web endpoints
        return jsonify({"token": webui.token})

    @app.get("/web/token")
    def web_token():
        if not _auth_disabled() and not _authorized():
            return jsonify({"token": ""}), 401
        return jsonify({"token": webui.token})

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

        # Apply all changes to config
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
                # Update in-memory token immediately
                webui.token = str(val) if val is not None else ""

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
            webui.logger.notice(
                "Full restart required for keys: %s",
                ", ".join(plan.full_restart_keys),
            )
            try:
                webui.manager.configure_auto_update()
            except Exception:
                webui.logger.exception("Failed to refresh auto update configuration")
            webui._reload_all()

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
