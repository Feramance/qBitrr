from __future__ import annotations

import logging
import os
import secrets
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Response, jsonify, redirect, request, send_file, session

from qBitrr.config import HOME_PATH
from qBitrr.utils import coerce_bool
from qBitrr.webui.auth import (
    _allow_insecure_token_query,
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
from qBitrr.webui.config_toml import _toml_set
from qBitrr.webui.openapi_ui import (
    _if_none_match_includes_etag,
    _load_openapi_spec_api_only,
    _swagger_ui_html,
)
from qBitrr.webui.routes.config_routes import register_config_routes
from qBitrr.webui.routes.log_routes import register_log_routes
from qBitrr.webui.routes.process_routes import register_process_routes
from qBitrr.webui.routes.status_routes import register_status_routes
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
            if not _allow_insecure_token_query():
                _webui_logger.warning(
                    "Ignoring ?token= from %s — WebUI.AllowInsecureTokenQuery is false. "
                    "Use Authorization: Bearer instead.",
                    request.remote_addr,
                )
                return None
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

    def _ui_index_redirect():
        # Serve UI without requiring a token; API remains protected
        from flask import make_response

        response = make_response(redirect(_public_url("/static/index.html")))
        # Prevent caching of the UI entry point
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.get("/ui")
    @app.get("/ui/")
    def ui_index():
        return _ui_index_redirect()

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

    register_process_routes(
        webui,
        _dual_route=_dual_route,
        _managed_objects=_managed_objects,
        _ensure_arr_manager_ready=_ensure_arr_manager_ready,
        _webui_mod=_webui_mod,
    )
    register_log_routes(
        webui,
        _dual_route=_dual_route,
        _resolve_log_file=_resolve_log_file,
        logs_root=logs_root,
        _webui_mod=_webui_mod,
    )
    register_status_routes(
        webui,
        app=app,
        _dual_route=_dual_route,
        require_token=require_token,
        _managed_objects=_managed_objects,
        _ensure_arr_manager_ready=_ensure_arr_manager_ready,
        _webui_mod=_webui_mod,
    )
    register_config_routes(
        webui,
        app=app,
        _dual_route=_dual_route,
        require_token=require_token,
        _managed_objects=_managed_objects,
        _webui_mod=_webui_mod,
    )
