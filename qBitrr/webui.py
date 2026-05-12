from __future__ import annotations

import importlib.resources
import io
import json
import logging
import os
import re
import secrets
import threading
import time
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import bcrypt
from authlib.integrations.flask_client import OAuth
from flask import Flask, Response, jsonify, redirect, request, send_file, session
from peewee import SQL, fn

from qBitrr.arss import PlaceHolderArr, TorrentPolicyManager
from qBitrr.bundled_data import patched_version, tagged_version
from qBitrr.catalog_rollups import (
    _sum_case_int,
    get_lidarr_album_and_track_rollups,
    get_lidarr_track_counts_total,
    get_radarr_counts_total,
    get_sonarr_episode_instance_counts_total,
)
from qBitrr.config import CONFIG, HOME_PATH
from qBitrr.db_lock import database_lock
from qBitrr.logger import run_logs
from qBitrr.search_activity_store import (
    clear_search_activity,
    fetch_search_activities,
)
from qBitrr.versioning import fetch_latest_release, fetch_release_by_tag
from qBitrr.webui_thumbnails import (
    get_or_fetch_thumbnail_bytes,
    sha256_digest_bytes,
    thumbnail_quoted_etag,
)

_openapi_spec_lock = threading.Lock()
_openapi_spec: dict[str, Any] | None = None
_openapi_spec_api_only: dict[str, Any] | None = None


def _openapi_path_in_api_first_spec(path: str) -> bool:
    """Paths exposed in the filtered OpenAPI doc (Swagger): `/api/*` plus mirrored poster thumbnails."""
    if not path.startswith("/web/"):
        return True
    if not path.endswith("/thumbnail"):
        return False
    return path.startswith(("/web/radarr/", "/web/sonarr/", "/web/lidarr/"))


def _if_none_match_includes_etag(if_none_match: str | None, etag: str) -> bool:
    """True if ``If-None-Match`` matches ``etag`` (strong entity-tag, quoted)."""
    if not if_none_match:
        return False
    hv = if_none_match.strip()
    if hv == "*":
        return True
    for part in hv.split(","):
        p = part.strip()
        if p.startswith("W/"):
            p = p[2:].strip()
        if p == etag:
            return True
    return False


def _load_openapi_spec() -> dict[str, Any]:
    """Load bundled OpenAPI document (cached, thread-safe)."""
    global _openapi_spec
    with _openapi_spec_lock:
        if _openapi_spec is None:
            raw = (
                importlib.resources.files("qBitrr")
                .joinpath("openapi.json")
                .read_text(encoding="utf-8")
            )
            _openapi_spec = json.loads(raw)
        return _openapi_spec


def _load_openapi_spec_api_only() -> dict[str, Any]:
    """Load a cached OpenAPI view: `/api/*`-first, plus mirrored `/web/*` thumbnail paths only."""
    global _openapi_spec, _openapi_spec_api_only
    with _openapi_spec_lock:
        if _openapi_spec is None:
            raw = (
                importlib.resources.files("qBitrr")
                .joinpath("openapi.json")
                .read_text(encoding="utf-8")
            )
            _openapi_spec = json.loads(raw)
        if _openapi_spec_api_only is None:
            filtered_paths = {
                path: value
                for path, value in _openapi_spec.get("paths", {}).items()
                if _openapi_path_in_api_first_spec(path)
            }
            _openapi_spec_api_only = {**_openapi_spec, "paths": filtered_paths}
        return _openapi_spec_api_only


def _swagger_ui_html(spec_url: str) -> str:
    """Minimal Swagger UI page loading the given OpenAPI spec URL (same-origin)."""
    spec_url_json = json.dumps(spec_url)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>qBitrr API — Swagger UI</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.11.0/swagger-ui.css" integrity="sha384-+yyzNgM3K92sROwsXxYCxaiLWxWJ0G+v/9A+qIZ2rgefKgkdcmJI+L601cqPD/Ut" crossorigin="anonymous"/>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.11.0/swagger-ui-bundle.js" integrity="sha384-qn5tagrAjZi8cSmvZ+k3zk4+eDEEUcP9myuR2J6V+/H6rne++v6ChO7EeHAEzqxQ" crossorigin="anonymous"></script>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js" integrity="sha384-SiLF+uYBf9lVQW98s/XUYP14enXJN31bn0zu3BS1WFqr5hvnMF+w132WkE/v0uJw" crossorigin="anonymous"></script>
  <script>
    window.onload = function () {{
      window.ui = SwaggerUIBundle({{
        url: {spec_url_json},
        dom_id: "#swagger-ui",
        deepLinking: true,
        persistAuthorization: true,
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
        plugins: [SwaggerUIBundle.plugins.DownloadUrl],
        layout: "StandaloneLayout",
      }});
    }};
  </script>
</body>
</html>"""


class _RateLimiter:
    """Sliding-window IP rate limiter (thread-safe)."""

    def __init__(self, max_attempts: int, window_seconds: int):
        self._max = max_attempts
        self._window = window_seconds
        self._data: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            # Opportunistically prune stale entries so old IP keys do not accumulate forever.
            for existing_key, existing_times in list(self._data.items()):
                filtered_times = [t for t in existing_times if now - t < self._window]
                if filtered_times:
                    self._data[existing_key] = filtered_times
                else:
                    self._data.pop(existing_key, None)

            times = self._data.get(key, [])
            if len(times) >= self._max:
                return False
            times.append(now)
            self._data[key] = times
            return True


_login_limiter = _RateLimiter(max_attempts=10, window_seconds=900)
_setpw_limiter = _RateLimiter(max_attempts=5, window_seconds=900)
_setpw_lock = threading.Lock()


def _pw_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _pw_verify(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception:
        return False


def _auth_disabled() -> bool:
    return bool(CONFIG.get("WebUI.AuthDisabled", fallback=True))


def _local_auth_enabled() -> bool:
    return bool(CONFIG.get("WebUI.LocalAuthEnabled", fallback=False))


def _oidc_enabled() -> bool:
    return (
        bool(CONFIG.get("WebUI.OIDCEnabled", fallback=False))
        and bool(CONFIG.get("WebUI.OIDC.Authority", fallback=""))
        and bool(CONFIG.get("WebUI.OIDC.ClientId", fallback=""))
    )


def _toml_set(doc, dotted_key: str, value: Any):
    from tomlkit import inline_table, table

    keys = dotted_key.split(".")
    cur = doc
    for k in keys[:-1]:
        # Reuse existing node if it is a dict or a dict-like container (e.g. tomlkit
        # Table/InlineTable), so we do not replace CategorySeeding and lose other keys
        # when only one dotted key (e.g. qBit.CategorySeeding.MaxSeedingTime) is set.
        existing = cur.get(k) if k in cur else None
        is_nested_container = isinstance(existing, Mapping)
        if k not in cur or not is_nested_container:
            cur[k] = table()
        cur = cur[k]

    # Convert plain Python dicts to inline tables for proper TOML serialization
    # This ensures dicts are rendered as inline {key = "value"} not as sections [key]
    if isinstance(value, dict) and not hasattr(value, "as_string"):
        inline = inline_table()
        inline.update(value)
        cur[keys[-1]] = inline
    else:
        cur[keys[-1]] = value


def _toml_delete(doc, dotted_key: str) -> None:
    keys = dotted_key.split(".")
    cur = doc
    parents = []
    for k in keys[:-1]:
        if not isinstance(cur, Mapping):
            return
        next_cur = cur.get(k)
        if not isinstance(next_cur, Mapping):
            return
        parents.append((cur, k))
        cur = next_cur
    if not isinstance(cur, Mapping):
        return
    cur.pop(keys[-1], None)
    for parent, key in reversed(parents):
        node = parent.get(key)
        if isinstance(node, Mapping) and not node:
            parent.pop(key, None)
        else:
            break


_SENSITIVE_KEY_PATTERNS = re.compile(
    r"(apikey|api_key|token|password|secret|passkey|credential)", re.IGNORECASE
)

# Placeholder returned by API/Web UI for sensitive values; never send real secrets.
# When config update sends this value for a sensitive key, the existing secret is left unchanged.
REDACTED_PLACEHOLDER = "[redacted]"


def _is_sensitive_dotted_key(dotted_key: str) -> bool:
    """Return True if the config key is considered sensitive (e.g. qBit.Password, Radarr-x.APIKey)."""
    if not dotted_key or "." not in dotted_key:
        return bool(_SENSITIVE_KEY_PATTERNS.search(dotted_key))
    return bool(_SENSITIVE_KEY_PATTERNS.search(dotted_key.split(".")[-1]))


def _strip_sensitive_keys(obj: Any, _parent_key: str = "") -> Any:
    """Recursively redact values whose keys look like secrets."""
    if isinstance(obj, dict):
        return {
            k: (
                REDACTED_PLACEHOLDER
                if isinstance(v, str) and _SENSITIVE_KEY_PATTERNS.search(k)
                else _strip_sensitive_keys(v, k)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_strip_sensitive_keys(v, _parent_key) for v in obj]
    return obj


def _toml_to_jsonable(obj: Any) -> Any:
    try:
        if hasattr(obj, "unwrap"):
            return _toml_to_jsonable(obj.unwrap())
        if isinstance(obj, dict):
            return {k: _toml_to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_toml_to_jsonable(v) for v in obj]
        return obj
    except Exception:
        logging.getLogger("qBitrr.WebUI").debug("_toml_to_jsonable failed", exc_info=True)
        return obj


class WebUI:
    def __init__(self, manager, host: str = "0.0.0.0", port: int = 6969):
        self.manager = manager
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.logger = logging.getLogger("qBitrr.WebUI")
        run_logs(self.logger, "WebUI")
        self.logger.info("Initialising WebUI on %s:%s", self.host, self.port)
        if self.host in {"0.0.0.0", "::"}:
            self.logger.warning(
                "WebUI configured to listen on %s. Expose this only behind a trusted reverse proxy.",
                self.host,
            )
            if _auth_disabled():
                self.logger.warning(
                    "WebUI authentication is disabled: all API and WebUI actions are available "
                    "without credentials to any client that can reach this port. If that is not "
                    "intentional, enable authentication (see WebUI.AuthDisabled and login/token in "
                    "the docs), bind WebUI.Host to 127.0.0.1, or place the service behind a "
                    "trusted reverse proxy with its own access controls."
                )
        self.app.logger.handlers.clear()
        self.app.logger.propagate = True
        self.app.logger.setLevel(self.logger.level)
        werkzeug_logger = logging.getLogger("werkzeug")
        werkzeug_logger.handlers.clear()
        werkzeug_logger.propagate = True
        werkzeug_logger.setLevel(self.logger.level)

        # When behind HTTPS proxy, trust forwarded proto/ip for secure URLs and per-client limits
        if CONFIG.get("WebUI.BehindHttpsProxy", fallback=False):
            from werkzeug.middleware.proxy_fix import ProxyFix

            self.app.wsgi_app = ProxyFix(self.app.wsgi_app, x_for=1, x_proto=1)

        class _QbitrrPrefixMiddleware:
            """Support both / and /qbitrr path topologies behind reverse proxies."""

            def __init__(self, app):
                self._app = app

            def __call__(self, environ, start_response):
                path = environ.get("PATH_INFO", "")
                if path == "/qbitrr" or path.startswith("/qbitrr/"):
                    environ["SCRIPT_NAME"] = f"{environ.get('SCRIPT_NAME', '')}/qbitrr".rstrip("/")
                    stripped = path[len("/qbitrr") :]
                    environ["PATH_INFO"] = stripped or "/"
                return self._app(environ, start_response)

        self.app.wsgi_app = _QbitrrPrefixMiddleware(self.app.wsgi_app)

        # Add cache control and security headers
        @self.app.after_request
        def add_cache_headers(response):
            # Security headers
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            # Prevent caching of index.html and service worker to ensure fresh config loads
            if request.path in (
                "/static/index.html",
                "/ui",
                "/static/sw.js",
                "/sw.js",
            ):
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
            return response

        # Security token (optional) - auto-generate and persist if empty
        self.token = CONFIG.get("WebUI.Token", fallback=None)
        if not self.token:
            self.token = secrets.token_hex(32)
            try:
                _toml_set(CONFIG.config, "WebUI.Token", self.token)
                CONFIG.save()
            except Exception:
                self.logger.warning(
                    "Failed to persist generated WebUI token to config", exc_info=True
                )
            else:
                self.logger.notice("Generated new WebUI token")

        # Flask session config (HttpOnly signed cookies for web login)
        # Keep session signing separate from bearer token auth.
        self.app.secret_key = secrets.token_hex(32)
        self.app.config.update(
            SESSION_COOKIE_NAME="qbitrr_session",
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            SESSION_COOKIE_SECURE=bool(CONFIG.get("WebUI.BehindHttpsProxy", fallback=False)),
            PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        )

        # OIDC via Authlib
        self._oauth = OAuth(self.app)
        if _oidc_enabled():
            authority = (CONFIG.get("WebUI.OIDC.Authority", fallback="") or "").rstrip("/")
            self._oauth.register(
                name="oidc",
                server_metadata_url=f"{authority}/.well-known/openid-configuration",
                client_id=CONFIG.get("WebUI.OIDC.ClientId", fallback=""),
                client_secret=CONFIG.get("WebUI.OIDC.ClientSecret", fallback=""),
                client_kwargs={
                    "scope": CONFIG.get("WebUI.OIDC.Scopes", fallback="openid profile")
                },
            )

        self._github_repo = "Feramance/qBitrr"
        self._version_lock = threading.Lock()
        self._version_cache = {
            "current_version": patched_version,
            "latest_version": None,
            "changelog": "",  # Latest version changelog
            "current_version_changelog": "",  # Current version changelog
            "changelog_url": f"https://github.com/{self._github_repo}/releases",
            "repository_url": f"https://github.com/{self._github_repo}",
            "homepage_url": f"https://github.com/{self._github_repo}",
            "update_available": False,
            "last_checked": None,
            "error": None,
            "installation_type": "unknown",
            "binary_download_url": None,
            "binary_download_name": None,
            "binary_download_size": None,
            "binary_download_error": None,
        }
        self._version_cache_expiry = datetime.now(timezone.utc) - timedelta(seconds=1)
        self._update_state = {
            "in_progress": False,
            "last_result": None,
            "last_error": None,
            "completed_at": None,
        }
        self._update_thread: threading.Thread | None = None
        self._rebuilding_arrs = False
        self._register_routes()
        static_root = Path(__file__).with_name("static")
        if not (static_root / "index.html").exists():
            self.logger.warning(
                "WebUI static bundle is missing. Install npm and run "
                "'npm ci && npm run build' inside the 'webui' folder before packaging."
            )
        self._thread: threading.Thread | None = None
        self._use_dev_server: bool | None = None

        # Shutdown control for graceful restart
        self._shutdown_event = threading.Event()
        self._restart_requested = False
        self._server = None  # Will hold Waitress server reference

    def _fetch_version_info(self) -> dict[str, Any]:
        info = fetch_latest_release(self._github_repo)
        if info.get("error"):
            self.logger.debug("Failed to fetch latest release information: %s", info["error"])
            return {"error": info["error"]}
        latest_display = info.get("raw_tag") or info.get("normalized")
        return {
            "latest_version": latest_display,
            "update_available": bool(info.get("update_available")),
            "changelog": info.get("changelog") or "",
            "changelog_url": info.get("changelog_url"),
            "error": None,
        }

    def _fetch_current_version_changelog(self) -> dict[str, Any]:
        """Fetch changelog for the current running version."""
        current_ver = tagged_version
        if not current_ver:
            return {
                "changelog": "",
                "changelog_url": f"https://github.com/{self._github_repo}/releases",
                "error": "No current version",
            }

        info = fetch_release_by_tag(current_ver, self._github_repo)
        if info.get("error"):
            self.logger.debug("Failed to fetch current version changelog: %s", info["error"])
            # Fallback to generic releases page
            return {
                "changelog": "",
                "changelog_url": f"https://github.com/{self._github_repo}/releases",
                "error": info["error"],
            }

        return {
            "changelog": info.get("changelog") or "",
            "changelog_url": info.get("changelog_url")
            or f"https://github.com/{self._github_repo}/releases/tag/v{current_ver}",
            "error": None,
        }

    def _ensure_version_info(self, force: bool = False) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self._version_lock:
            if not force and now < self._version_cache_expiry:
                snapshot = dict(self._version_cache)
                snapshot["update_state"] = dict(self._update_state)
                return snapshot
            # optimistic expiry to avoid concurrent fetches
            self._version_cache_expiry = now + timedelta(minutes=5)

        latest_info = self._fetch_version_info()
        current_ver_info = self._fetch_current_version_changelog()

        with self._version_lock:
            if latest_info:
                if latest_info.get("latest_version") is not None:
                    self._version_cache["latest_version"] = latest_info["latest_version"]
                if latest_info.get("changelog") is not None:
                    self._version_cache["changelog"] = latest_info.get("changelog") or ""
                if latest_info.get("changelog_url"):
                    self._version_cache["changelog_url"] = latest_info["changelog_url"]
                if "update_available" in latest_info:
                    self._version_cache["update_available"] = bool(latest_info["update_available"])
                if "error" in latest_info:
                    self._version_cache["error"] = latest_info["error"]
            # Store current version changelog
            if current_ver_info and not current_ver_info.get("error"):
                self._version_cache["current_version_changelog"] = (
                    current_ver_info.get("changelog") or ""
                )

            self._version_cache["current_version"] = patched_version
            self._version_cache["last_checked"] = now.isoformat()

            # Add installation type and binary download info
            from qBitrr.auto_update import get_binary_download_url, get_installation_type

            install_type = get_installation_type()
            self._version_cache["installation_type"] = install_type

            # If binary and update available, get download URL
            if install_type == "binary" and self._version_cache.get("update_available"):
                latest_version = self._version_cache.get("latest_version")
                if latest_version:
                    binary_info = get_binary_download_url(latest_version, self.logger)
                    self._version_cache["binary_download_url"] = binary_info.get("url")
                    self._version_cache["binary_download_name"] = binary_info.get("name")
                    self._version_cache["binary_download_size"] = binary_info.get("size")
                    if binary_info.get("error"):
                        self._version_cache["binary_download_error"] = binary_info["error"]

            # Extend cache validity if fetch succeeded; otherwise allow quick retry.
            if not latest_info or latest_info.get("error"):
                self._version_cache_expiry = now + timedelta(minutes=5)
            else:
                self._version_cache_expiry = now + timedelta(hours=1)
            snapshot = dict(self._version_cache)
            snapshot["update_state"] = dict(self._update_state)
            return snapshot

    def _trigger_manual_update(self) -> tuple[bool, str]:
        with self._version_lock:
            if self._update_state["in_progress"]:
                return False, "An update is already in progress."
            update_thread = threading.Thread(
                target=self._run_manual_update, name="ManualUpdater", daemon=True
            )
            self._update_state["in_progress"] = True
            self._update_state["last_error"] = None
            self._update_state["last_result"] = None
            self._update_thread = update_thread
        update_thread.start()
        return True, "started"

    def _run_manual_update(self) -> None:
        result = "success"
        error_message: str | None = None
        try:
            self.logger.notice("Manual update triggered from WebUI")
            try:
                self.manager._perform_auto_update()
            except AttributeError:
                from qBitrr.auto_update import perform_self_update

                if not perform_self_update(self.manager.logger):
                    raise RuntimeError("pip upgrade did not complete successfully")
                try:
                    self.manager.request_restart()
                except Exception:
                    self.logger.warning(
                        "Update applied but restart request failed; exiting manually."
                    )
        except Exception as exc:
            result = "error"
            error_message = str(exc)
            self.logger.exception("Manual update failed")
        finally:
            completed_at = datetime.now(timezone.utc).isoformat()
            with self._version_lock:
                self._update_state.update(
                    {
                        "in_progress": False,
                        "last_result": result,
                        "last_error": error_message,
                        "completed_at": completed_at,
                    }
                )
                self._update_thread = None
                self._version_cache_expiry = datetime.now(timezone.utc) - timedelta(seconds=1)
            try:
                self.manager.configure_auto_update()
            except Exception:
                self.logger.exception("Failed to reconfigure auto update after manual update")
            try:
                self._ensure_version_info(force=True)
            except Exception:
                self.logger.debug("Version metadata refresh after update failed", exc_info=True)

    @staticmethod
    def _safe_str(value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    def _ensure_arr_db(self, arr) -> bool:
        """Ensure catalog models/DB are ready for read-only browse; do not run full Arr API sync here.

        Bulk ``db_update()`` runs in the Arr manager search loop (and related paths), not on HTTP requests.
        """
        if not getattr(arr, "search_setup_completed", False):
            try:
                arr.register_search_mode()
            except Exception:
                self.logger.debug(
                    "register_search_mode failed for %s", getattr(arr, "_name", arr), exc_info=True
                )
                return False
        if not getattr(arr, "search_setup_completed", False):
            return False
        return True

    @staticmethod
    def _query_truthy(value: Any) -> bool:
        """Parse a request query parameter as a boolean.

        Treats the string forms ``"0"``, ``"false"``, ``"none"`` (case-insensitive) as
        falsy in addition to standard Python falsy values. Used for ``request.args.get(...)``
        flags such as ``monitored``, ``has_file``, ``quality_met``.
        """
        return bool(value) and str(value).lower() not in {"0", "false", "none"}

    @staticmethod
    def _field_truthy(value: Any) -> bool:
        """Coerce a Peewee model attribute to a boolean for response payloads.

        Unlike :meth:`_query_truthy` this does NOT treat the literal string ``"0"`` as falsy
        because catalog fields can legitimately store the string ``"0"`` (e.g. external IDs).
        Standard Python truthiness applies: ``None``, ``0``, ``False``, ``""`` are falsy;
        everything else is truthy.
        """
        return bool(value)

    # Backward-compatible alias used by older call sites; prefer the explicit helpers above.
    @staticmethod
    def _safe_bool(value: Any) -> bool:
        return bool(value) and str(value).lower() not in {"0", "false", "none"}

    def _radarr_movies_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        year_min: int | None = None,
        year_max: int | None = None,
        monitored: bool | None = None,
        has_file: bool | None = None,
        quality_met: bool | None = None,
        is_request: bool | None = None,
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                    "quality_met": 0,
                    "requests": 0,
                },
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "movies": [],
            }
        model = getattr(arr, "model_file", None)
        db = getattr(arr, "db", None)
        if model is None or db is None:
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                    "quality_met": 0,
                    "requests": 0,
                },
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "movies": [],
            }
        page = max(page, 0)
        page_size = max(page_size, 1)
        arr_instance = getattr(arr, "_name", "")
        # Standardised order across all ``*_from_db`` helpers (M-2):
        #   1. Compute rollups (refresh from SQLite under its own short lock).
        #   2. Acquire database_lock for the page-read.
        #   3. Drain rows under the lock.
        #   4. Release lock; build payload from snapshots.
        rollup_counts, total = get_radarr_counts_total(arr)

        page_rows: list[Any] = []
        has_quality_profile_id = hasattr(model, "QualityProfileId")
        has_quality_profile_name = hasattr(model, "QualityProfileName")

        with database_lock():
            with db.connection_context():
                base_query = model.select().where(model.ArrInstance == arr_instance)

                # Build filtered query
                query = base_query
                if search:
                    query = query.where(model.Title.contains(search))
                if year_min is not None:
                    query = query.where(model.Year >= year_min)
                if year_max is not None:
                    query = query.where(model.Year <= year_max)
                if monitored is not None:
                    query = query.where(model.Monitored == monitored)
                if has_file is not None:
                    if has_file:
                        query = query.where(
                            (model.MovieFileId.is_null(False)) & (model.MovieFileId != 0)
                        )
                    else:
                        query = query.where(
                            (model.MovieFileId.is_null(True)) | (model.MovieFileId == 0)
                        )
                if quality_met is not None:
                    query = query.where(model.QualityMet == quality_met)
                if is_request is not None:
                    query = query.where(model.IsRequest == is_request)

                # Drain into a list so the lock is released before we serialise the payload.
                page_rows = list(query.order_by(model.Title.asc()).paginate(page + 1, page_size))

        # Lock released — build the per-row payloads now (B-3).
        movies = []
        for movie in page_rows:
            quality_profile_id = (
                getattr(movie, "QualityProfileId", None) if has_quality_profile_id else None
            )
            quality_profile_name = (
                getattr(movie, "QualityProfileName", None) if has_quality_profile_name else None
            )

            movies.append(
                {
                    "id": movie.EntryId,
                    "title": movie.Title or "",
                    "year": movie.Year,
                    "monitored": self._safe_bool(movie.Monitored),
                    "hasFile": self._safe_bool(movie.MovieFileId),
                    "qualityMet": self._safe_bool(movie.QualityMet),
                    "isRequest": self._safe_bool(movie.IsRequest),
                    "upgrade": self._safe_bool(movie.Upgrade),
                    "customFormatScore": movie.CustomFormatScore,
                    "minCustomFormatScore": movie.MinCustomFormatScore,
                    "customFormatMet": self._safe_bool(movie.CustomFormatMet),
                    "reason": movie.Reason,
                    "qualityProfileId": quality_profile_id,
                    "qualityProfileName": quality_profile_name,
                }
            )
        return {
            "counts": dict(rollup_counts),
            "total": total,
            "page": page,
            "page_size": page_size,
            "movies": movies,
        }

    @staticmethod
    def _lidarr_track_row_reason(
        *,
        track_monitored: bool,
        track_has_file: bool,
        album_reason: Any,
    ) -> str:
        """Derive a per-track search reason for the WebUI (SQLite tracks have no Reason column)."""
        ar = str(album_reason).strip() if album_reason is not None else ""
        if not track_monitored:
            return "Unmonitored"
        if not track_has_file:
            return "Missing"
        if ar and ar != "Missing":
            return ar
        return "Not being searched"

    def _lidarr_album_row_payload(
        self,
        arr,
        album: Any,
        prefetched_tracks: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Build one ``{album, totals, tracks}`` entry from an AlbumFiles row.

        When ``prefetched_tracks`` is supplied the helper does not issue any extra DB query
        (used by :meth:`_lidarr_artist_detail_from_db` to avoid N+1). When ``None`` we fall
        back to the per-album lookup for callers that have not adopted the JOIN-bucket flow.
        """
        track_model = getattr(arr, "track_file_model", None)
        tracks_list: list[dict[str, Any]] = []
        track_monitored_count = 0
        track_available_count = 0

        track_iterable: list[Any] = []
        if prefetched_tracks is not None:
            track_iterable = prefetched_tracks
        elif track_model:
            try:
                track_iterable = list(
                    track_model.select()
                    .where(track_model.AlbumId == album.EntryId)
                    .order_by(track_model.TrackNumber)
                )
            except Exception as e:
                self.logger.warning(
                    "Failed to fetch tracks for album %s (%s): %s",
                    album.EntryId,
                    album.Title,
                    e,
                )
                track_iterable = []

        album_reason_raw = getattr(album, "Reason", None)

        for track in track_iterable:
            is_monitored = self._safe_bool(getattr(track, "Monitored", False))
            has_file = self._safe_bool(getattr(track, "HasFile", False))

            if is_monitored:
                track_monitored_count += 1
            if has_file:
                track_available_count += 1

            track_reason = self._lidarr_track_row_reason(
                track_monitored=is_monitored,
                track_has_file=has_file,
                album_reason=album_reason_raw,
            )

            tracks_list.append(
                {
                    "id": getattr(track, "EntryId", None),
                    "trackNumber": getattr(track, "TrackNumber", None),
                    "title": getattr(track, "Title", None),
                    "duration": getattr(track, "Duration", None),
                    "hasFile": has_file,
                    "trackFileId": getattr(track, "TrackFileId", None),
                    "monitored": is_monitored,
                    "reason": track_reason,
                }
            )

        track_missing_count = max(track_monitored_count - track_available_count, 0)

        quality_profile_id = getattr(album, "QualityProfileId", None)
        quality_profile_name = getattr(album, "QualityProfileName", None)

        return {
            "album": {
                "id": album.EntryId,
                "title": album.Title,
                "artistId": album.ArtistId,
                "artistName": album.ArtistTitle,
                "monitored": self._safe_bool(album.Monitored),
                "hasFile": bool(album.AlbumFileId and album.AlbumFileId != 0),
                "foreignAlbumId": album.ForeignAlbumId,
                "releaseDate": (
                    album.ReleaseDate.isoformat()
                    if album.ReleaseDate and hasattr(album.ReleaseDate, "isoformat")
                    else (album.ReleaseDate if isinstance(album.ReleaseDate, str) else None)
                ),
                "qualityMet": self._safe_bool(album.QualityMet),
                "isRequest": self._safe_bool(album.IsRequest),
                "upgrade": self._safe_bool(album.Upgrade),
                "customFormatScore": album.CustomFormatScore,
                "minCustomFormatScore": album.MinCustomFormatScore,
                "customFormatMet": self._safe_bool(album.CustomFormatMet),
                "reason": album.Reason,
                "qualityProfileId": quality_profile_id,
                "qualityProfileName": quality_profile_name,
            },
            "totals": {
                "available": track_available_count,
                "monitored": track_monitored_count,
                "missing": track_missing_count,
            },
            "tracks": tracks_list,
        }

    @staticmethod
    def _lidarr_instance_keys(arr: Any) -> list[str]:
        """Return distinct non-empty ``ArrInstance`` keys to query for one Lidarr ``Arr``.

        Workers stamp ``ArtistFilesModel.ArrInstance`` with ``Arr._name``, but older or
        manually repaired databases may still carry ``Arr.category``. Matching only
        ``_name`` yields an empty browse with non-zero rollups.
        """
        name = (getattr(arr, "_name", None) or "").strip()
        cat = (getattr(arr, "category", None) or "").strip()
        keys: list[str] = []
        for k in (name, cat):
            if k and k not in keys:
                keys.append(k)
        if not keys:
            keys = [name] if name else [""]
        return keys

    @staticmethod
    def _lidarr_artist_browse_progress_maps(
        album_m: Any,
        track_m: Any,
        arr_instance_keys: list[str],
        artist_ids: list[int],
    ) -> tuple[dict[int, tuple[int, int]], dict[int, tuple[int, int]]]:
        """Return per-artist (monitored, on-disk) counts for albums and tracks.

        Album "available" matches catalog rules: monitored row with non-zero ``AlbumFileId``.
        Track "available": monitored with ``HasFile`` true.
        """
        alb_out: dict[int, tuple[int, int]] = {}
        trk_out: dict[int, tuple[int, int]] = {}
        if not artist_ids or not arr_instance_keys:
            return alb_out, trk_out

        artist_id_col = album_m.ArtistId.alias("artist_id")
        mon_alb = album_m.Monitored == True  # noqa: E712
        alb_file = (album_m.AlbumFileId.is_null(False)) & (album_m.AlbumFileId != 0)
        aq = (
            album_m.select(
                artist_id_col,
                _sum_case_int(mon_alb, "mon_n"),
                _sum_case_int(mon_alb & alb_file, "avail_n"),
            )
            .where(
                (album_m.ArrInstance.in_(arr_instance_keys)) & (album_m.ArtistId.in_(artist_ids))
            )
            .group_by(artist_id_col)
        )
        for row in aq.dicts():
            raw_aid = row.get("artist_id")
            if raw_aid is None:
                continue
            aid = int(raw_aid)
            alb_out[aid] = (int(row.get("mon_n") or 0), int(row.get("avail_n") or 0))

        if track_m is not None:
            mon_tr = track_m.Monitored == True  # noqa: E712
            tr_ok = track_m.HasFile == True  # noqa: E712
            tq = (
                track_m.select(
                    artist_id_col,
                    _sum_case_int(mon_tr, "mon_n"),
                    _sum_case_int(mon_tr & tr_ok, "avail_n"),
                )
                .join(album_m, on=(track_m.AlbumId == album_m.EntryId))
                .where(
                    (track_m.ArrInstance.in_(arr_instance_keys))
                    & (album_m.ArrInstance.in_(arr_instance_keys))
                    & (album_m.ArtistId.in_(artist_ids))
                )
                .group_by(artist_id_col)
            )
            # Joined aggregate is rooted at ``track_m``; model rows omit ``artist_id`` alias.
            for row in tq.dicts():
                raw_aid = row.get("artist_id")
                if raw_aid is None:
                    continue
                aid = int(raw_aid)
                trk_out[aid] = (int(row.get("mon_n") or 0), int(row.get("avail_n") or 0))

        return alb_out, trk_out

    def _lidarr_artists_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        monitored: bool | None = None,
        missing_only: bool = False,
        reason_filter: str | None = None,
    ) -> dict[str, Any]:
        empty = {
            "counts": {
                "available": 0,
                "monitored": 0,
                "missing": 0,
                "quality_met": 0,
                "requests": 0,
            },
            "counts_tracks": {"available": 0, "monitored": 0, "missing": 0},
            "total": 0,
            "page": max(page, 0),
            "page_size": max(page_size, 1),
            "artists": [],
        }

        if not self._ensure_arr_db(arr):
            return empty
        arm = getattr(arr, "artists_file_model", None)
        db = getattr(arr, "db", None)
        if arm is None or db is None:
            return empty

        page = max(page, 0)
        page_size = max(page_size, 1)
        arr_keys = self._lidarr_instance_keys(arr)

        (rollup_album_counts, album_total_inst), (rollup_track_counts, _) = (
            get_lidarr_album_and_track_rollups(arr)
        )

        slice_rows: list[Any] = []
        total = 0
        alb_maps: dict[int, tuple[int, int]] = {}
        trk_maps: dict[int, tuple[int, int]] = {}

        # Build the optional album-row predicate that maps Status / Search Reason filters to
        # the underlying ``AlbumFilesModel`` rows. ``Not being searched`` matches NULL too,
        # since older album rows may have left ``Reason`` unset.
        def _album_filter_extra(album_m: Any) -> Any | None:
            cond: Any | None = None
            if missing_only and album_m is not None:
                miss = (album_m.Monitored == True) & (  # noqa: E712
                    album_m.AlbumFileId.is_null() | (album_m.AlbumFileId == 0)
                )
                cond = miss if cond is None else cond & miss
            if reason_filter and album_m is not None:
                if reason_filter == "Not being searched":
                    rcond = (album_m.Reason == "Not being searched") | album_m.Reason.is_null()
                else:
                    rcond = album_m.Reason == reason_filter
                cond = rcond if cond is None else cond & rcond
            return cond

        with database_lock():
            with db.connection_context():
                album_m = getattr(arr, "model_file", None)
                track_m = getattr(arr, "track_file_model", None)

                album_filter_extra = _album_filter_extra(album_m)

                base = arm.select().where(arm.ArrInstance.in_(arr_keys))
                q_art = base
                if search:
                    q_art = q_art.where(arm.Title.contains(search))
                if monitored is not None:
                    q_art = q_art.where(arm.Monitored == monitored)
                if album_filter_extra is not None and album_m is not None:
                    artist_ids_subq = album_m.select(album_m.ArtistId).where(
                        album_m.ArrInstance.in_(arr_keys) & album_filter_extra
                    )
                    q_art = q_art.where(arm.EntryId.in_(artist_ids_subq))

                total = int(q_art.count() or 0)
                slice_rows = list(q_art.order_by(arm.Title.asc()).paginate(page + 1, page_size))

                # Album rows can be populated while ArtistFilesModel has no rows (e.g. artist
                # ingest skipped or legacy DB). Rollups then show album totals but browse was empty.
                if total == 0 and int(album_total_inst or 0) > 0 and album_m is not None:
                    conds: list[Any] = [album_m.ArrInstance.in_(arr_keys)]
                    if search:
                        conds.append(album_m.ArtistTitle.contains(search))
                    if album_filter_extra is not None:
                        conds.append(album_filter_extra)
                    grouped_artists = (
                        album_m.select(
                            album_m.ArtistId,
                            fn.MIN(album_m.ArtistTitle).alias("disp_title"),
                            fn.MAX(album_m.Monitored).alias("mx_mon"),
                        )
                        .where(*conds)
                        .group_by(album_m.ArtistId)
                    )
                    if monitored is True:
                        grouped_artists = grouped_artists.having(
                            fn.MAX(album_m.Monitored) == True  # noqa: E712
                        )
                    elif monitored is False:
                        grouped_artists = grouped_artists.having(
                            fn.MAX(album_m.Monitored) == False  # noqa: E712
                        )
                    count_wrap = grouped_artists.alias("lidarr_artists_fb")
                    total = int(album_m.select(fn.COUNT(SQL("*"))).from_(count_wrap).scalar() or 0)
                    slice_rows = []
                    for row in grouped_artists.order_by(
                        fn.MIN(album_m.ArtistTitle).asc(),
                        album_m.ArtistId.asc(),
                    ).paginate(page + 1, page_size):
                        aid = int(row.ArtistId)
                        ar_rec = arm.get_or_none(
                            (arm.EntryId == aid) & (arm.ArrInstance.in_(arr_keys))
                        )
                        if ar_rec is not None:
                            slice_rows.append(ar_rec)
                        else:
                            disp = getattr(row, "disp_title", None) or ""
                            mx = getattr(row, "mx_mon", None)
                            slice_rows.append(
                                SimpleNamespace(
                                    EntryId=aid,
                                    Title=disp,
                                    Monitored=mx,
                                    AlbumCount=0,
                                    TrackTotalCount=0,
                                    QualityProfileName=None,
                                    Searched=False,
                                )
                            )

                ids = [int(ar.EntryId) for ar in slice_rows]
                alb_maps, trk_maps = {}, {}
                if ids and album_m is not None:
                    alb_maps, trk_maps = WebUI._lidarr_artist_browse_progress_maps(
                        album_m, track_m, arr_keys, ids
                    )

        artists_out: list[dict[str, Any]] = []
        for ar in slice_rows:
            aid = int(ar.EntryId)
            am, aa = alb_maps.get(aid, (0, 0))
            tm, ta = trk_maps.get(aid, (0, 0))
            miss_a = max(am - aa, 0)
            miss_t = max(tm - ta, 0)
            artists_out.append(
                {
                    "artist": {
                        "id": ar.EntryId,
                        "name": ar.Title or "",
                        "monitored": self._safe_bool(ar.Monitored),
                        "albumCount": int(getattr(ar, "AlbumCount", None) or 0),
                        "trackTotalCount": int(getattr(ar, "TrackTotalCount", None) or 0),
                        "qualityProfileName": getattr(ar, "QualityProfileName", None),
                        "searched": self._safe_bool(ar.Searched),
                        "albumsMonitored": am,
                        "albumsAvailable": aa,
                        "albumsMissing": miss_a,
                        "tracksMonitored": tm,
                        "tracksAvailable": ta,
                        "tracksMissing": miss_t,
                    }
                }
            )

        return {
            "counts": dict(rollup_album_counts),
            "counts_tracks": dict(rollup_track_counts),
            "album_total": int(album_total_inst),
            "total": total,
            "page": page,
            "page_size": page_size,
            "artists": artists_out,
        }

    def _lidarr_artist_detail_from_db(self, arr, artist_id: int) -> dict[str, Any] | None:
        """Return a single artist with all albums and tracks in one DB visit.

        Lock scope is intentionally narrow: the SQLite ``database_lock`` only spans the read
        queries (B-3); rollups are gathered before the lock (M-2) and Python payload
        construction happens after release. Track lookup is a single JOIN query (H-2) bucketed
        per album in Python — replaces the prior N+1 ``select per album`` pattern.
        """
        arm = getattr(arr, "artists_file_model", None)
        album_m = getattr(arr, "model_file", None)
        track_m = getattr(arr, "track_file_model", None)
        db = getattr(arr, "db", None)

        if not self._ensure_arr_db(arr) or arm is None or album_m is None or db is None:
            return None

        arr_keys = self._lidarr_instance_keys(arr)

        # Compute rollups before acquiring the DB lock. Standardised ordering across all
        # ``*_from_db`` helpers (M-2): rollup -> lock -> read -> release -> build payload.
        (rollup_album_counts, _), (rollup_track_counts, _) = get_lidarr_album_and_track_rollups(
            arr
        )

        artist_row = None
        album_rows: list[Any] = []
        tracks_by_album: dict[int, list[Any]] = {}

        with database_lock():
            with db.connection_context():
                artist_row = arm.get_or_none(
                    (arm.EntryId == artist_id) & (arm.ArrInstance.in_(arr_keys))
                )
                if artist_row is None:
                    return None

                aq = album_m.select().where(
                    (album_m.ArtistId == artist_id) & (album_m.ArrInstance.in_(arr_keys))
                )
                try:
                    aq = aq.order_by(album_m.ReleaseDate, album_m.Title)
                except Exception:
                    aq = aq.order_by(album_m.Title)
                album_rows = list(aq)

                if track_m is not None and album_rows:
                    # Single JOIN: tracks for every album of this artist in one round-trip.
                    track_query = (
                        track_m.select(
                            track_m,
                            album_m.EntryId.alias("AlbumEntryId"),
                        )
                        .join(album_m, on=(track_m.AlbumId == album_m.EntryId))
                        .where(
                            (track_m.ArrInstance.in_(arr_keys))
                            & (album_m.ArrInstance.in_(arr_keys))
                            & (album_m.ArtistId == artist_id)
                        )
                        .order_by(album_m.EntryId, track_m.TrackNumber)
                    )
                    for trow in track_query:
                        album_id_for_track = int(getattr(trow, "AlbumId", 0) or 0)
                        tracks_by_album.setdefault(album_id_for_track, []).append(trow)

        # Lock released — build the response payload from the snapshots we just collected.
        album_items = [
            self._lidarr_album_row_payload(
                arr, al, prefetched_tracks=tracks_by_album.get(al.EntryId)
            )
            for al in album_rows
        ]

        artist_payload = {
            "id": artist_row.EntryId,
            "name": artist_row.Title or "",
            "monitored": self._safe_bool(artist_row.Monitored),
            "albumCount": int(getattr(artist_row, "AlbumCount", None) or 0),
            "trackTotalCount": int(getattr(artist_row, "TrackTotalCount", None) or 0),
            "qualityProfileName": getattr(artist_row, "QualityProfileName", None),
            "searched": self._safe_bool(artist_row.Searched),
        }

        return {
            "counts": dict(rollup_album_counts),
            "counts_tracks": dict(rollup_track_counts),
            "artist": artist_payload,
            "albums": album_items,
        }

    def _lidarr_albums_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        monitored: bool | None = None,
        has_file: bool | None = None,
        quality_met: bool | None = None,
        is_request: bool | None = None,
        group_by_artist: bool = True,
    ) -> dict[str, Any]:
        # Empty/fallback payload shape mirrors a successful response so callers (frontend)
        # never branch on missing keys. ``counts`` matches ``_ZERO_COUNTS_RAD`` and
        # ``counts_tracks`` matches ``_ZERO_COUNTS_EP3`` from ``catalog_rollups``.
        empty_albums_payload = {
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
            "page": max(page, 0),
            "page_size": max(page_size, 1),
            "albums": [],
        }
        if not self._ensure_arr_db(arr):
            return dict(empty_albums_payload)
        model = getattr(arr, "model_file", None)
        db = getattr(arr, "db", None)
        if model is None or db is None:
            return dict(empty_albums_payload)
        page = max(page, 0)
        page_size = max(page_size, 1)
        arr_instance = getattr(arr, "_name", "")

        # M-2: rollups (which take their own short lock) before the page-read lock.
        # Aggregate album+track rollups together so the "Tracks" header matches the artist
        # list shape; one SQLite refresh services both rollup readers.
        (rollup_counts, album_total_inst), (rollup_track_counts, _) = (
            get_lidarr_album_and_track_rollups(arr)
        )

        album_results: list[Any] = []
        track_m = getattr(arr, "track_file_model", None)
        tracks_by_album: dict[int, list[Any]] = {}

        with database_lock():
            with db.connection_context():
                base_query = model.select().where(model.ArrInstance == arr_instance)

                # Build filtered query
                query = base_query
                if search:
                    query = query.where(model.Title.contains(search))
                if monitored is not None:
                    query = query.where(model.Monitored == monitored)
                if has_file is not None:
                    if has_file:
                        query = query.where(
                            (model.AlbumFileId.is_null(False)) & (model.AlbumFileId != 0)
                        )
                    else:
                        query = query.where(
                            (model.AlbumFileId.is_null(True)) | (model.AlbumFileId == 0)
                        )
                if quality_met is not None:
                    query = query.where(model.QualityMet == quality_met)
                if is_request is not None:
                    query = query.where(model.IsRequest == is_request)

                if group_by_artist:
                    # Paginate by artists: Two-pass approach with Peewee
                    # First, get all distinct artist names from the filtered query
                    # Use a subquery to get distinct artists efficiently
                    artists_subquery = (
                        query.select(model.ArtistTitle).distinct().order_by(model.ArtistTitle)
                    )

                    all_artists = [row.ArtistTitle for row in artists_subquery]

                    start_idx = page * page_size
                    end_idx = start_idx + page_size
                    paginated_artists = all_artists[start_idx:end_idx]

                    if paginated_artists:
                        album_results = list(
                            query.where(model.ArtistTitle.in_(paginated_artists)).order_by(
                                model.ArtistTitle, model.ReleaseDate
                            )
                        )
                else:
                    # Flat mode: paginate by albums.
                    album_results = list(query.order_by(model.Title).paginate(page + 1, page_size))

                # Single JOIN of tracks for the page rather than N+1 per-album lookups (H-2).
                if track_m is not None and album_results:
                    album_ids = [int(getattr(a, "EntryId", 0) or 0) for a in album_results]
                    track_query = (
                        track_m.select()
                        .where(
                            (track_m.ArrInstance == arr_instance)
                            & (track_m.AlbumId.in_(album_ids))
                        )
                        .order_by(track_m.AlbumId, track_m.TrackNumber)
                    )
                    for trow in track_query:
                        bucket = tracks_by_album.setdefault(int(trow.AlbumId or 0), [])
                        bucket.append(trow)

        # Lock released — build payloads outside (B-3).
        total = album_total_inst
        albums = [
            self._lidarr_album_row_payload(
                arr, album, prefetched_tracks=tracks_by_album.get(int(album.EntryId or 0))
            )
            for album in album_results
        ]
        return {
            "counts": dict(rollup_counts),
            "counts_tracks": dict(rollup_track_counts),
            "album_total": int(album_total_inst),
            "total": total,
            "page": page,
            "page_size": page_size,
            "albums": albums,
        }

    def _lidarr_tracks_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        monitored: bool | None = None,
        has_file: bool | None = None,
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                },
                "total": 0,
                "page": page,
                "page_size": page_size,
                "tracks": [],
            }

        track_model = getattr(arr, "track_file_model", None)
        album_model = getattr(arr, "model_file", None)
        db = getattr(arr, "db", None)

        if not track_model or not album_model or db is None:
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                },
                "total": 0,
                "page": page,
                "page_size": page_size,
                "tracks": [],
            }

        arr_instance = getattr(arr, "_name", "")

        rollup_tracks, _inst_track_total = get_lidarr_track_counts_total(arr)

        try:
            track_rows: list[Any] = []
            total = 0
            with database_lock():
                with db.connection_context():
                    query = (
                        track_model.select(
                            track_model,
                            album_model.Title.alias("AlbumTitle"),
                            album_model.ArtistTitle,
                            album_model.ArtistId,
                        )
                        .join(album_model, on=(track_model.AlbumId == album_model.EntryId))
                        .where(
                            (track_model.ArrInstance == arr_instance)
                            & (album_model.ArrInstance == arr_instance)
                        )
                    )

                    if monitored is not None:
                        query = query.where(track_model.Monitored == monitored)
                    if has_file is not None:
                        query = query.where(track_model.HasFile == has_file)
                    if search:
                        query = query.where(
                            (track_model.Title.contains(search))
                            | (album_model.Title.contains(search))
                            | (album_model.ArtistTitle.contains(search))
                        )

                    total = query.count()
                    track_rows = list(
                        query.order_by(
                            album_model.ArtistTitle,
                            album_model.Title,
                            track_model.TrackNumber,
                        ).paginate(page + 1, page_size)
                    )

            # Lock released — build payload outside (B-3).
            tracks = [
                {
                    "id": track.EntryId,
                    "trackNumber": track.TrackNumber,
                    "title": track.Title,
                    "duration": track.Duration,
                    "hasFile": track.HasFile,
                    "trackFileId": track.TrackFileId,
                    "monitored": track.Monitored,
                    "albumId": track.AlbumId,
                    "albumTitle": track.AlbumTitle,
                    "artistTitle": track.ArtistTitle,
                    "artistId": track.ArtistId,
                }
                for track in track_rows
            ]

            return {
                "counts": dict(rollup_tracks),
                "total": total,
                "page": page,
                "page_size": page_size,
                "tracks": tracks,
            }
        except Exception as e:
            self.logger.error("Error fetching Lidarr tracks: %s", e)
            return {
                "counts": {"available": 0, "monitored": 0, "missing": 0},
                "total": 0,
                "page": page,
                "page_size": page_size,
                "tracks": [],
            }

    def _enrich_sonarr_series_payload_quality_from_api(
        self,
        arr: Any,
        payload: list[dict[str, Any]],
        pending: list[tuple[int, int]],
    ) -> None:
        """Fill quality profile from Sonarr HTTP API for episode-mode rows (after DB work).

        Run outside Peewee ``connection_context`` and outside :func:`~qBitrr.db_lock.database_lock`
        so no DB connection or cross-process DB lock is held during network I/O.
        """
        if not pending:
            return
        client = getattr(arr, "client", None)
        if not client or not hasattr(client, "get_series"):
            return
        for idx, series_id in pending:
            if not (0 <= idx < len(payload)):
                continue
            try:
                series_data = client.get_series(series_id)
                if not series_data:
                    continue
                quality_profile_id = series_data.get("qualityProfileId")
                quality_profile_name = None
                if quality_profile_id:
                    quality_cache = getattr(arr, "_quality_profile_cache", {})
                    if quality_profile_id in quality_cache:
                        quality_profile_name = quality_cache[quality_profile_id].get("name")
                    elif hasattr(client, "get_quality_profile"):
                        try:
                            profile = client.get_quality_profile(quality_profile_id)
                            quality_profile_name = profile.get("name") if profile else None
                        except Exception:
                            self.logger.debug(
                                "Sonarr quality profile lookup failed",
                                exc_info=True,
                            )
                series_obj = payload[idx].setdefault("series", {})
                if quality_profile_id is not None:
                    series_obj["qualityProfileId"] = quality_profile_id
                if quality_profile_name is not None:
                    series_obj["qualityProfileName"] = quality_profile_name
            except Exception:
                self.logger.debug("Sonarr series payload build failed", exc_info=True)

    def _sonarr_series_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        *,
        missing_only: bool = False,
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return {
                "counts": {"available": 0, "monitored": 0, "missing": 0},
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "series": [],
            }
        episodes_model = getattr(arr, "model_file", None)
        series_model = getattr(arr, "series_file_model", None)
        db = getattr(arr, "db", None)
        if episodes_model is None or db is None:
            return {
                "counts": {"available": 0, "monitored": 0, "missing": 0},
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "series": [],
            }
        page = max(page, 0)
        page_size = max(page_size, 1)
        resolved_page = page
        arr_instance = getattr(arr, "_name", "")
        missing_condition = episodes_model.EpisodeFileId.is_null(True) | (
            episodes_model.EpisodeFileId == 0
        )

        ep_instance_counts, rollup_total_series = get_sonarr_episode_instance_counts_total(arr)
        monitored_count = ep_instance_counts.get("monitored", 0)
        available_count = ep_instance_counts.get("available", 0)
        missing_count = ep_instance_counts.get("missing", 0)

        sonarr_api_quality_pending: list[tuple[int, int]] = []
        payload: list[dict[str, Any]] = []
        total_series = 0
        # Materialise raw rows inside the DB lock; build Python payloads after release (B-3).
        # Each tuple holds the bare data we need so payload assembly cannot touch the cursor.
        collected_series: list[tuple[Any, list[Any]]] = []  # (series_row, episodes_list)
        has_qp_id_field = bool(series_model) and hasattr(series_model, "QualityProfileId")
        has_qp_name_field = bool(series_model) and hasattr(series_model, "QualityProfileName")
        with database_lock():
            with db.connection_context():
                missing_series_ids: list[int] = []
                if missing_only:
                    missing_series_ids = [
                        row.SeriesId
                        for row in episodes_model.select(episodes_model.SeriesId)
                        .where(
                            (episodes_model.ArrInstance == arr_instance)
                            & (episodes_model.Monitored == True)  # noqa: E712
                            & missing_condition
                        )
                        .distinct()
                        if getattr(row, "SeriesId", None) is not None
                    ]
                    if not missing_series_ids:
                        return {
                            "counts": {
                                "available": available_count,
                                "monitored": monitored_count,
                                "missing": missing_count,
                            },
                            "total": 0,
                            "page": resolved_page,
                            "page_size": page_size,
                            "series": [],
                        }

                if series_model is not None:
                    base_series_query = series_model.select().where(
                        series_model.ArrInstance == arr_instance
                    )
                    total_series = rollup_total_series

                    series_query = base_series_query
                    if search:
                        series_query = series_query.where(series_model.Title.contains(search))
                    if missing_only and missing_series_ids:
                        series_query = series_query.where(
                            series_model.EntryId.in_(missing_series_ids)
                        )
                    filtered_series_count = series_query.count()
                    if filtered_series_count:
                        max_pages = (filtered_series_count + page_size - 1) // page_size
                        if max_pages:
                            resolved_page = min(resolved_page, max_pages - 1)
                        resolved_page = max(resolved_page, 0)
                        series_page = list(
                            series_query.order_by(series_model.Title.asc()).paginate(
                                resolved_page + 1, page_size
                            )
                        )
                        for series in series_page:
                            episodes_query = episodes_model.select().where(
                                (episodes_model.ArrInstance == arr_instance)
                                & (episodes_model.SeriesId == series.EntryId)
                            )
                            if missing_only:
                                episodes_query = episodes_query.where(missing_condition)
                            episodes_query = episodes_query.order_by(
                                episodes_model.SeasonNumber.asc(),
                                episodes_model.EpisodeNumber.asc(),
                            )
                            collected_series.append((series, list(episodes_query)))

        # ---- Lock released; build payloads from materialised rows ---------------------
        for series, episodes_list in collected_series:
            self.logger.debug(
                "[Sonarr Series] Series %s (ID %s) has %d episodes (missing_only=%s)",
                getattr(series, "Title", "unknown"),
                getattr(series, "EntryId", "?"),
                len(episodes_list),
                missing_only,
            )
            seasons: dict[str, dict[str, Any]] = {}
            series_monitored = 0
            series_available = 0
            for ep in episodes_list:
                season_value = getattr(ep, "SeasonNumber", None)
                season_key = str(season_value) if season_value is not None else "unknown"
                season_bucket = seasons.setdefault(
                    season_key,
                    {"monitored": 0, "available": 0, "episodes": []},
                )
                is_monitored = self._safe_bool(getattr(ep, "Monitored", None))
                has_file = self._safe_bool(getattr(ep, "EpisodeFileId", None))
                if is_monitored:
                    season_bucket["monitored"] += 1
                    series_monitored += 1
                if has_file:
                    season_bucket["available"] += 1
                    if is_monitored:
                        series_available += 1
                air_date = getattr(ep, "AirDateUtc", None)
                if hasattr(air_date, "isoformat"):
                    try:
                        air_value = air_date.isoformat()
                    except Exception:
                        air_value = str(air_date)
                elif isinstance(air_date, str):
                    air_value = air_date
                else:
                    air_value = ""
                if (not missing_only) or (not has_file):
                    season_bucket["episodes"].append(
                        {
                            "episodeNumber": getattr(ep, "EpisodeNumber", None),
                            "title": getattr(ep, "Title", "") or "",
                            "monitored": is_monitored,
                            "hasFile": has_file,
                            "airDateUtc": air_value,
                            "reason": getattr(ep, "Reason", None),
                        }
                    )
            for bucket in seasons.values():
                monitored_eps = int(bucket.get("monitored", 0) or 0)
                available_eps = int(bucket.get("available", 0) or 0)
                bucket["missing"] = max(monitored_eps - min(available_eps, monitored_eps), 0)
            series_missing = max(series_monitored - series_available, 0)
            if missing_only:
                seasons = {key: data for key, data in seasons.items() if data["episodes"]}
                if not seasons:
                    continue

            series_id = getattr(series, "EntryId", None)
            quality_profile_id = (
                getattr(series, "QualityProfileId", None) if has_qp_id_field else None
            )
            quality_profile_name = (
                getattr(series, "QualityProfileName", None) if has_qp_name_field else None
            )

            payload.append(
                {
                    "series": {
                        "id": series_id,
                        "title": getattr(series, "Title", "") or "",
                        "qualityProfileId": quality_profile_id,
                        "qualityProfileName": quality_profile_name,
                    },
                    "totals": {
                        "available": series_available,
                        "monitored": series_monitored,
                        "missing": series_missing,
                    },
                    "seasons": seasons,
                }
            )

        if not payload:
            # Episode-mode fallback: collect (series_id, series_title, episodes_list) tuples
            # inside the lock, then build the payload outside it.
            collected_fallback: list[tuple[Any, Any, list[Any]]] = []
            page_keys: list[tuple[Any, ...]] = []
            field_names: list[str] = []
            with database_lock():
                with db.connection_context():
                    base_episode_query = episodes_model.select().where(
                        episodes_model.ArrInstance == arr_instance
                    )
                    if search:
                        search_filters = []
                        if hasattr(episodes_model, "SeriesTitle"):
                            search_filters.append(episodes_model.SeriesTitle.contains(search))
                        search_filters.append(episodes_model.Title.contains(search))
                        expr = search_filters[0]
                        for extra in search_filters[1:]:
                            expr |= extra
                        base_episode_query = base_episode_query.where(expr)
                    if missing_only:
                        base_episode_query = base_episode_query.where(missing_condition)

                    series_id_field = (
                        getattr(episodes_model, "SeriesId", None)
                        if hasattr(episodes_model, "SeriesId")
                        else None
                    )
                    series_title_field = (
                        getattr(episodes_model, "SeriesTitle", None)
                        if hasattr(episodes_model, "SeriesTitle")
                        else None
                    )

                    distinct_fields = []
                    if series_id_field is not None:
                        distinct_fields.append(series_id_field)
                        field_names.append("SeriesId")
                    if series_title_field is not None:
                        distinct_fields.append(series_title_field)
                        field_names.append("SeriesTitle")
                    if not distinct_fields:
                        distinct_fields.append(episodes_model.Title.alias("SeriesTitle"))
                        field_names.append("SeriesTitle")

                    distinct_query = (
                        base_episode_query.select(*distinct_fields)
                        .distinct()
                        .order_by(
                            series_title_field.asc()
                            if series_title_field is not None
                            else episodes_model.Title.asc()
                        )
                    )
                    series_key_rows = list(distinct_query.tuples())
                    total_series = len(series_key_rows)
                    if total_series:
                        max_pages = (total_series + page_size - 1) // page_size
                        resolved_page = min(resolved_page, max_pages - 1)
                        resolved_page = max(resolved_page, 0)
                        start = resolved_page * page_size
                        end = start + page_size
                        page_keys = series_key_rows[start:end]
                    else:
                        resolved_page = 0
                        page_keys = []

                    for key in page_keys:
                        key_data = dict(zip(field_names, key))
                        fk_series_id = key_data.get("SeriesId")
                        fk_series_title = key_data.get("SeriesTitle")
                        episode_conditions = []
                        if fk_series_id is not None:
                            episode_conditions.append(episodes_model.SeriesId == fk_series_id)
                        if fk_series_title is not None:
                            episode_conditions.append(
                                episodes_model.SeriesTitle == fk_series_title
                            )
                        episodes_query = episodes_model.select().where(
                            episodes_model.ArrInstance == arr_instance
                        )
                        if episode_conditions:
                            condition = episode_conditions[0]
                            for extra in episode_conditions[1:]:
                                condition &= extra
                            episodes_query = episodes_query.where(condition)
                        if missing_only:
                            episodes_query = episodes_query.where(missing_condition)
                        episodes_query = episodes_query.order_by(
                            episodes_model.SeasonNumber.asc(),
                            episodes_model.EpisodeNumber.asc(),
                        )
                        collected_fallback.append(
                            (fk_series_id, fk_series_title, list(episodes_query))
                        )

            # Lock released — build payload from materialised rows (B-3).
            payload = []
            for fk_series_id, fk_series_title, episodes_list in collected_fallback:
                seasons: dict[str, dict[str, Any]] = {}
                series_monitored = 0
                series_available = 0
                # Track quality profile from first episode (all episodes share the same profile).
                quality_profile_id = None
                quality_profile_name = None
                for ep in episodes_list:
                    if quality_profile_id is None and hasattr(ep, "QualityProfileId"):
                        quality_profile_id = getattr(ep, "QualityProfileId", None)
                    if quality_profile_name is None and hasattr(ep, "QualityProfileName"):
                        quality_profile_name = getattr(ep, "QualityProfileName", None)
                    season_value = getattr(ep, "SeasonNumber", None)
                    season_key = str(season_value) if season_value is not None else "unknown"
                    season_bucket = seasons.setdefault(
                        season_key,
                        {"monitored": 0, "available": 0, "episodes": []},
                    )
                    is_monitored = self._safe_bool(getattr(ep, "Monitored", None))
                    has_file = self._safe_bool(getattr(ep, "EpisodeFileId", None))
                    if is_monitored:
                        season_bucket["monitored"] += 1
                        series_monitored += 1
                    if has_file:
                        season_bucket["available"] += 1
                        if is_monitored:
                            series_available += 1
                    air_date = getattr(ep, "AirDateUtc", None)
                    if hasattr(air_date, "isoformat"):
                        try:
                            air_value = air_date.isoformat()
                        except Exception:
                            air_value = str(air_date)
                    elif isinstance(air_date, str):
                        air_value = air_date
                    else:
                        air_value = ""
                    season_bucket["episodes"].append(
                        {
                            "episodeNumber": getattr(ep, "EpisodeNumber", None),
                            "title": getattr(ep, "Title", "") or "",
                            "monitored": is_monitored,
                            "hasFile": has_file,
                            "airDateUtc": air_value,
                            "reason": getattr(ep, "Reason", None),
                        }
                    )
                for bucket in seasons.values():
                    monitored_eps = int(bucket.get("monitored", 0) or 0)
                    available_eps = int(bucket.get("available", 0) or 0)
                    bucket["missing"] = max(monitored_eps - min(available_eps, monitored_eps), 0)
                series_missing = max(series_monitored - series_available, 0)
                if missing_only:
                    seasons = {key: data for key, data in seasons.items() if data["episodes"]}
                    if not seasons:
                        continue

                append_idx = len(payload)
                if quality_profile_id is None and fk_series_id is not None:
                    sonarr_api_quality_pending.append((append_idx, fk_series_id))

                payload.append(
                    {
                        "series": {
                            "id": fk_series_id,
                            "title": (
                                fk_series_title
                                or (
                                    f"Series {len(payload) + 1}"
                                    if fk_series_id is None
                                    else str(fk_series_id)
                                )
                            ),
                            "qualityProfileId": quality_profile_id,
                            "qualityProfileName": quality_profile_name,
                        },
                        "totals": {
                            "available": series_available,
                            "monitored": series_monitored,
                            "missing": series_missing,
                        },
                        "seasons": seasons,
                    }
                )

        self._enrich_sonarr_series_payload_quality_from_api(
            arr, payload, sonarr_api_quality_pending
        )

        result = {
            "counts": {
                "available": available_count,
                "monitored": monitored_count,
                "missing": missing_count,
            },
            "total": total_series,
            "page": resolved_page,
            "page_size": page_size,
            "series": payload,
        }
        if payload:
            first_series = payload[0]
            first_seasons = first_series.get("seasons", {})
            total_episodes_in_response = sum(
                len(season.get("episodes", [])) for season in first_seasons.values()
            )
            self.logger.info(
                "[Sonarr API] Returning %d series, first series '%s' has %d seasons, %d episodes (missing_only=%s)",
                len(payload),
                first_series.get("series", {}).get("title", "?"),
                len(first_seasons),
                total_episodes_in_response,
                missing_only,
            )
        return result

    # Routes
    def _register_routes(self):
        app = self.app
        logs_root = (HOME_PATH / "logs").resolve()

        def _resolve_log_file(name: str) -> Path | None:
            # Restrict to safe log file names (alphanumeric, dash, underscore, dot)
            if not name or not name.strip():
                return None
            safe = "".join(c for c in name if c.isalnum() or c in "._-").strip() or None
            if safe is None or safe != name:
                self.logger.debug("Rejected log file name (invalid characters): %r", name)
                return None
            try:
                candidate = (logs_root / safe).resolve(strict=False)
            except Exception:
                self.logger.debug("Failed to resolve log path for %r", safe, exc_info=True)
                return None
            try:
                candidate.relative_to(logs_root)
            except ValueError:
                return None
            return candidate

        def _managed_objects() -> dict[str, Any]:
            arr_manager = getattr(self.manager, "arr_manager", None)
            return getattr(arr_manager, "managed_objects", {}) if arr_manager else {}

        def _ensure_arr_manager_ready() -> bool:
            return getattr(self.manager, "arr_manager", None) is not None

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

        @app.get("/")
        def index():
            prefix = request.script_root.rstrip("/")
            return redirect(f"{prefix}/ui" if prefix else "/ui")

        def _authorized():
            _webui_logger = logging.getLogger("qBitrr.WebUI")

            def _get_supplied_token():
                header_token = (
                    request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                )
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

            # Auth disabled globally → always authorized
            if _auth_disabled():
                return True
            # Bearer token (API path) — constant-time comparison
            supplied = _get_supplied_token()
            if supplied and self.token and secrets.compare_digest(supplied, self.token):
                return True
            # Session cookie (web login path)
            return bool(session.get("authenticated"))

        def require_token():
            if not _authorized():
                return jsonify({"error": "unauthorized"}), 401
            return None

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

        @app.get("/api/openapi.json")
        def api_openapi_json():
            if (resp := require_token()) is not None:
                return resp
            return _openapi_json_response()

        @app.get("/web/openapi.json")
        def web_openapi_json():
            if (resp := require_token()) is not None:
                return resp
            return _openapi_json_response()

        @app.get("/api/docs")
        def api_swagger_docs():
            if (resp := require_token()) is not None:
                return resp
            return _swagger_ui_response("/api/openapi.json")

        @app.get("/web/docs")
        def web_swagger_docs():
            if (resp := require_token()) is not None:
                return resp
            return _swagger_ui_response("/web/openapi.json")

        @app.get("/ui")
        def ui_index():
            # Serve UI without requiring a token; API remains protected
            # Add cache-busting parameter based on config reload timestamp
            from flask import make_response

            prefix = request.script_root.rstrip("/")
            target = f"{prefix}/static/index.html" if prefix else "/static/index.html"
            response = make_response(redirect(target))
            # Prevent caching of the UI entry point
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

        @app.get("/sw.js")
        def service_worker():
            # Service worker must be served directly (not redirected) for PWA support
            # This allows the endpoint to be whitelisted in auth proxies (e.g., Authentik)
            import os

            from flask import send_from_directory

            static_dir = os.path.join(os.path.dirname(__file__), "static")
            response = send_from_directory(static_dir, "sw.js")
            # Prevent caching of the service worker to ensure updates are picked up
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

        @app.get("/login")
        def login_page():
            prefix = request.script_root.rstrip("/")
            return redirect(f"{prefix}/ui" if prefix else "/ui")

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
            stored_hash = CONFIG.get("WebUI.PasswordHash", fallback="") or ""
            if not stored_hash:
                return jsonify({"error": "Password not set", "code": "SETUP_REQUIRED"}), 403
            # Always verify both to prevent timing-based username enumeration
            pw_ok = _pw_verify(password, stored_hash)
            stored_username = CONFIG.get("WebUI.Username", fallback="") or ""
            user_ok = bool(stored_username) and secrets.compare_digest(username, stored_username)
            if not pw_ok or not user_ok:
                return jsonify({"error": "Invalid credentials"}), 401
            session.permanent = True
            session["authenticated"] = True
            session["username"] = username
            self.logger.info("User %s logged in via local auth", username)
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
            token_ok = (
                bool(env_token)
                and bool(setup_token)
                and secrets.compare_digest(setup_token, env_token)
            )
            with _setpw_lock:
                stored_hash = CONFIG.get("WebUI.PasswordHash", fallback="") or ""
                first_time = not stored_hash
                if not first_time and not token_ok:
                    return jsonify({"error": "Not allowed"}), 403
                new_hash = _pw_hash(password)
                try:
                    _toml_set(CONFIG.config, "WebUI.Username", username)
                    _toml_set(CONFIG.config, "WebUI.PasswordHash", new_hash)
                    _toml_set(CONFIG.config, "WebUI.AuthDisabled", False)
                    _toml_set(CONFIG.config, "WebUI.LocalAuthEnabled", True)
                    CONFIG.save()
                except Exception:
                    self.logger.error("Failed to save config after set-password", exc_info=True)
                    return jsonify({"error": "Failed to save configuration"}), 500
            self.logger.info("Password set for user %s", username)
            return jsonify({"success": True})

        oidc_callback_path = (
            CONFIG.get("WebUI.OIDC.CallbackPath", fallback="/signin-oidc") or "/signin-oidc"
        )
        if not oidc_callback_path.startswith("/"):
            oidc_callback_path = f"/{oidc_callback_path}"

        @app.get("/web/auth/oidc/challenge")
        def web_oidc_challenge():
            if not _oidc_enabled():
                return jsonify({"error": "OIDC not configured"}), 400
            redirect_uri = request.host_url.rstrip("/") + oidc_callback_path
            return self._oauth.oidc.authorize_redirect(redirect_uri)

        @app.get(oidc_callback_path)
        def web_oidc_callback():
            if not _oidc_enabled():
                return redirect("/ui")
            try:
                token = self._oauth.oidc.authorize_access_token()
                userinfo = token.get("userinfo") or self._oauth.oidc.userinfo()
                username = (
                    userinfo.get("preferred_username") or userinfo.get("email") or "oidc-user"
                )
                session.permanent = True
                session["authenticated"] = True
                session["username"] = username
                self.logger.info("User %s logged in via OIDC", username)
            except Exception:
                self.logger.warning("OIDC callback failed", exc_info=True)
                return redirect("/ui?auth_error=1")
            return redirect("/ui")

        def _processes_payload() -> dict[str, Any]:
            procs = []
            search_activity_map = fetch_search_activities()

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
                    qbit_manager = getattr(self.manager, "qbit_manager", self.manager)
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
                            self.logger.debug(
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
                        torrents = qbit_client.torrents_info(
                            status_filter="all", category=category
                        )
                        metrics["category"] = sum(
                            1
                            for torrent in torrents
                            if getattr(torrent, "category", None) == category
                        )
                    except Exception:
                        self.logger.debug("Process metrics (category count) failed", exc_info=True)
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
                            "rebuilding": self._rebuilding_arrs,
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
                            "rebuilding": self._rebuilding_arrs,
                        }
                        _populate_process_metadata(arr, kind, payload)
                        procs.append(payload)
            # qBit category manager processes
            for process, meta in list(self.manager._process_registry.items()):
                if meta.get("role") != "category_manager":
                    continue
                instance_name = meta.get("instance", "")
                cat = meta.get("category", f"qbit-{instance_name}")
                manager = self.manager.qbit_category_managers.get(instance_name)
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

        @app.get("/api/processes")
        def api_processes():
            if (resp := require_token()) is not None:
                return resp
            return jsonify(_processes_payload())

        # UI endpoints (mirror of /api/* for first-party WebUI clients)
        @app.get("/web/processes")
        def web_processes():
            if (resp := require_token()) is not None:
                return resp
            return jsonify(_processes_payload())

        def _restart_process(category: str, kind: str):
            kind_normalized = kind.lower()
            if kind_normalized not in ("search", "torrent", "all", "category"):
                return jsonify({"error": "kind must be search, torrent, category or all"}), 400

            # Handle category manager restart
            if kind_normalized == "category":
                target_proc = None
                target_meta = None
                for proc, meta in list(self.manager._process_registry.items()):
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
                    self.logger.debug(
                        "Category manager process kill failed for %s", category, exc_info=True
                    )
                try:
                    target_proc.terminate()
                except Exception:
                    self.logger.debug(
                        "Category manager process terminate failed for %s", category, exc_info=True
                    )
                try:
                    self.manager.child_processes.remove(target_proc)
                except Exception:
                    self.logger.debug(
                        "child_processes.remove failed for category manager %s",
                        category,
                        exc_info=True,
                    )
                self.manager._process_registry.pop(target_proc, None)
                manager = self.manager.qbit_category_managers.get(instance_name)
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
                self.manager.child_processes.append(new_proc)
                self.manager._process_registry[new_proc] = {
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
                        self.logger.debug(
                            "Process kill failed for %s %s", category, loop_kind, exc_info=True
                        )
                    try:
                        process.terminate()
                    except Exception:
                        self.logger.debug(
                            "Process terminate failed for %s %s",
                            category,
                            loop_kind,
                            exc_info=True,
                        )
                    try:
                        self.manager.child_processes.remove(process)
                    except Exception:
                        self.logger.debug(
                            "child_processes.remove failed for %s %s",
                            category,
                            loop_kind,
                            exc_info=True,
                        )
                    self.manager._process_registry.pop(process, None)
                target = getattr(arr, f"run_{loop_kind}_loop", None)
                if target is None:
                    continue
                import pathos

                new_process = pathos.helpers.mp.Process(target=target, daemon=False)
                setattr(arr, proc_attr, new_process)
                self.manager.child_processes.append(new_process)
                self.manager._process_registry[new_process] = {
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
        @app.post("/api/processes/<path:category>/<kind>/restart")
        def api_restart_process(category: str, kind: str):
            if (resp := require_token()) is not None:
                return resp
            return _restart_process(category, kind)

        @app.post("/web/processes/<path:category>/<kind>/restart")
        def web_restart_process(category: str, kind: str):
            if (resp := require_token()) is not None:
                return resp
            return _restart_process(category, kind)

        @app.post("/api/processes/restart_all")
        def api_restart_all():
            if (resp := require_token()) is not None:
                return resp
            self._reload_all()
            return jsonify({"status": "ok"})

        @app.post("/web/processes/restart_all")
        def web_restart_all():
            if (resp := require_token()) is not None:
                return resp
            self._reload_all()
            return jsonify({"status": "ok"})

        def _handle_loglevel():
            body = request.get_json(silent=True) or {}
            level = str(body.get("level", "INFO")).upper()
            valid = {"CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"}
            if level not in valid:
                return jsonify({"error": f"invalid level {level}"}), 400
            target_level = getattr(logging, level, logging.INFO)
            logging.getLogger().setLevel(target_level)
            for name, lg in logging.root.manager.loggerDict.items():
                if isinstance(lg, logging.Logger) and str(name).startswith("qBitrr"):
                    lg.setLevel(target_level)
            try:
                _toml_set(CONFIG.config, "Settings.ConsoleLevel", level)
                CONFIG.save()
            except Exception:
                self.logger.debug("Failed to persist log level to config", exc_info=True)
            return jsonify({"status": "ok", "level": level})

        @app.post("/api/loglevel")
        def api_loglevel():
            if (resp := require_token()) is not None:
                return resp
            return _handle_loglevel()

        @app.post("/web/loglevel")
        def web_loglevel():
            if (resp := require_token()) is not None:
                return resp
            return _handle_loglevel()

        @app.post("/api/arr/rebuild")
        def api_arr_rebuild():
            if (resp := require_token()) is not None:
                return resp
            self._reload_all()
            return jsonify({"status": "ok"})

        @app.post("/web/arr/rebuild")
        def web_arr_rebuild():
            if (resp := require_token()) is not None:
                return resp
            self._reload_all()
            return jsonify({"status": "ok"})

        def _list_logs() -> list[str]:
            if not logs_root.exists():
                return []
            log_files = sorted(f.name for f in logs_root.glob("*.log*"))
            return log_files

        @app.get("/api/logs")
        def api_logs():
            if (resp := require_token()) is not None:
                return resp
            return jsonify({"files": _list_logs()})

        @app.get("/web/logs")
        def web_logs():
            if (resp := require_token()) is not None:
                return resp
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
                self.logger.debug("Failed to read log file %s", file, exc_info=True)
                content = ""
            response = send_file(
                io.BytesIO(content.encode("utf-8")),
                mimetype="text/plain",
                as_attachment=False,
            )
            response.headers["Content-Type"] = "text/plain; charset=utf-8"
            response.headers["Cache-Control"] = "no-cache"
            return response

        @app.get("/api/logs/<name>")
        def api_log(name: str):
            if (resp := require_token()) is not None:
                return resp
            return _serve_log_content(name)

        @app.get("/web/logs/<name>")
        def web_log(name: str):
            if (resp := require_token()) is not None:
                return resp
            return _serve_log_content(name)

        @app.get("/api/logs/<name>/download")
        def api_log_download(name: str):
            if (resp := require_token()) is not None:
                return resp
            file = _resolve_log_file(name)
            if file is None or not file.exists():
                return jsonify({"error": "not found"}), 404
            return send_file(file, as_attachment=True)

        @app.get("/web/logs/<name>/download")
        def web_log_download(name: str):
            if (resp := require_token()) is not None:
                return resp
            file = _resolve_log_file(name)
            if file is None or not file.exists():
                return jsonify({"error": "not found"}), 404
            return send_file(file, as_attachment=True)

        def _handle_radarr_movies(category: str):
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            arr = managed.get(category)
            if arr is None or getattr(arr, "type", None) != "radarr":
                return jsonify({"error": f"Unknown radarr category {category}"}), 404
            q = request.args.get("q", default=None, type=str)
            page = request.args.get("page", default=0, type=int)
            page_size = min(request.args.get("page_size", default=50, type=int), 1000)
            year_min = request.args.get("year_min", default=None, type=int)
            year_max = request.args.get("year_max", default=None, type=int)
            monitored = (
                self._query_truthy(request.args.get("monitored"))
                if "monitored" in request.args
                else None
            )
            has_file = (
                self._query_truthy(request.args.get("has_file"))
                if "has_file" in request.args
                else None
            )
            quality_met = (
                self._query_truthy(request.args.get("quality_met"))
                if "quality_met" in request.args
                else None
            )
            is_request = (
                self._query_truthy(request.args.get("is_request"))
                if "is_request" in request.args
                else None
            )
            payload = self._radarr_movies_from_db(
                arr,
                q,
                page,
                page_size,
                year_min=year_min,
                year_max=year_max,
                monitored=monitored,
                has_file=has_file,
                quality_met=quality_met,
                is_request=is_request,
            )
            payload["category"] = category
            return jsonify(payload)

        @app.get("/api/radarr/<path:category>/movies")
        def api_radarr_movies(category: str):
            if (resp := require_token()) is not None:
                return resp
            return _handle_radarr_movies(category)

        @app.get("/web/radarr/<path:category>/movies")
        def web_radarr_movies(category: str):
            if (resp := require_token()) is not None:
                return resp
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
            # ``private`` rather than ``public``: thumbnail responses are token-bearing
            # (Bearer header or ``?token=`` query) and must not be cached by shared proxies.
            cache_headers = {
                "Cache-Control": "private, max-age=86400",
            }
            inm = request.headers.get("If-None-Match")
            etag = thumbnail_quoted_etag(kind=kind, instance_name=name, entry_id=entry_id)
            if etag:
                cache_headers["ETag"] = etag
                if _if_none_match_includes_etag(inm, etag):
                    return Response(status=304, headers=cache_headers)
            out = get_or_fetch_thumbnail_bytes(
                kind=kind, instance_name=name, arr=arr, entry_id=entry_id
            )
            if not out:
                return "", 404
            data, mime = out
            # Derive the ETag straight from the bytes we just produced (avoids re-streaming the
            # cache file). Honour ``If-None-Match`` against the post-fetch hash too — a fresh
            # cache write whose bytes match a client-known ETag should still 304.
            etag_after = f'"{sha256_digest_bytes(data)}"'
            cache_headers["ETag"] = etag_after
            if _if_none_match_includes_etag(inm, etag_after):
                return Response(status=304, headers=cache_headers)
            return Response(data, mimetype=mime, headers=cache_headers)

        @app.get("/api/radarr/<path:category>/movie/<int:entry_id>/thumbnail")
        def api_radarr_thumb(category: str, entry_id: int):
            if (resp := require_token()) is not None:
                return resp
            return _arr_thumbnail(category, "radarr", entry_id)

        @app.get("/web/radarr/<path:category>/movie/<int:entry_id>/thumbnail")
        def web_radarr_thumb(category: str, entry_id: int):
            if (resp := require_token()) is not None:
                return resp
            return _arr_thumbnail(category, "radarr", entry_id)

        def _handle_sonarr_series(category: str):
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            arr = managed.get(category)
            if arr is None or getattr(arr, "type", None) != "sonarr":
                return jsonify({"error": f"Unknown sonarr category {category}"}), 404
            q = request.args.get("q", default=None, type=str)
            page = request.args.get("page", default=0, type=int)
            page_size = min(request.args.get("page_size", default=25, type=int), 1000)
            missing_only = self._query_truthy(
                request.args.get("missing") or request.args.get("only_missing")
            )
            payload = self._sonarr_series_from_db(
                arr, q, page, page_size, missing_only=missing_only
            )
            payload["category"] = category
            return jsonify(payload)

        @app.get("/api/sonarr/<path:category>/series")
        def api_sonarr_series(category: str):
            if (resp := require_token()) is not None:
                return resp
            return _handle_sonarr_series(category)

        @app.get("/web/sonarr/<path:category>/series")
        def web_sonarr_series(category: str):
            if (resp := require_token()) is not None:
                return resp
            return _handle_sonarr_series(category)

        @app.get("/api/sonarr/<path:category>/series/<int:entry_id>/thumbnail")
        def api_sonarr_thumb(category: str, entry_id: int):
            if (resp := require_token()) is not None:
                return resp
            return _arr_thumbnail(category, "sonarr", entry_id)

        @app.get("/web/sonarr/<path:category>/series/<int:entry_id>/thumbnail")
        def web_sonarr_thumb(category: str, entry_id: int):
            if (resp := require_token()) is not None:
                return resp
            return _arr_thumbnail(category, "sonarr", entry_id)

        def _handle_lidarr_albums(category: str):
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            arr = _resolve_managed_lidarr(category)
            if arr is None:
                return jsonify({"error": f"Unknown lidarr category {category}"}), 404
            q = request.args.get("q", default=None, type=str)
            page = request.args.get("page", default=0, type=int)
            page_size = _lidarr_page_size_from_request(50)
            monitored = (
                self._query_truthy(request.args.get("monitored"))
                if "monitored" in request.args
                else None
            )
            has_file = (
                self._query_truthy(request.args.get("has_file"))
                if "has_file" in request.args
                else None
            )
            quality_met = (
                self._query_truthy(request.args.get("quality_met"))
                if "quality_met" in request.args
                else None
            )
            is_request = (
                self._query_truthy(request.args.get("is_request"))
                if "is_request" in request.args
                else None
            )
            flat_mode = self._query_truthy(request.args.get("flat_mode", False))

            if flat_mode:
                # Flat mode: return tracks directly
                payload = self._lidarr_tracks_from_db(
                    arr,
                    q,
                    page,
                    page_size,
                    monitored=monitored,
                    has_file=has_file,
                )
            else:
                # Grouped mode: return albums with tracks, paginated by artist
                payload = self._lidarr_albums_from_db(
                    arr,
                    q,
                    page,
                    page_size,
                    monitored=monitored,
                    has_file=has_file,
                    quality_met=quality_met,
                    is_request=is_request,
                    group_by_artist=True,
                )
            payload["category"] = str(arr.category)
            return jsonify(payload)

        @app.get("/api/lidarr/<path:category>/albums")
        def api_lidarr_albums(category: str):
            if (resp := require_token()) is not None:
                return resp
            return _handle_lidarr_albums(category)

        @app.get("/web/lidarr/<path:category>/albums")
        def web_lidarr_albums(category: str):
            if (resp := require_token()) is not None:
                return resp
            return _handle_lidarr_albums(category)

        def _handle_lidarr_artists(category: str):
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            arr = _resolve_managed_lidarr(category)
            if arr is None:
                return jsonify({"error": f"Unknown lidarr category {category}"}), 404
            q = request.args.get("q", default=None, type=str)
            page = request.args.get("page", default=0, type=int)
            page_size = _lidarr_page_size_from_request(50)
            monitored = (
                self._query_truthy(request.args.get("monitored"))
                if "monitored" in request.args
                else None
            )
            missing_only = self._query_truthy(
                request.args.get("missing") or request.args.get("only_missing")
            )
            reason = request.args.get("reason", default=None, type=str)
            if reason and reason.strip().lower() == "all":
                reason = None
            payload = self._lidarr_artists_from_db(
                arr,
                q,
                page,
                page_size,
                monitored=monitored,
                missing_only=missing_only,
                reason_filter=reason,
            )
            payload["category"] = str(arr.category)
            return jsonify(payload)

        def _handle_lidarr_artist_detail(category: str, artist_id: int):
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            arr = _resolve_managed_lidarr(category)
            if arr is None:
                return jsonify({"error": f"Unknown lidarr category {category}"}), 404
            detail = self._lidarr_artist_detail_from_db(arr, artist_id)
            if detail is None:
                return jsonify({"error": "Artist not found"}), 404
            detail["category"] = str(arr.category)
            return jsonify(detail)

        @app.get("/api/lidarr/<path:category>/artists")
        def api_lidarr_artists(category: str):
            if (resp := require_token()) is not None:
                return resp
            return _handle_lidarr_artists(category)

        @app.get("/web/lidarr/<path:category>/artists")
        def web_lidarr_artists(category: str):
            if (resp := require_token()) is not None:
                return resp
            return _handle_lidarr_artists(category)

        @app.get("/api/lidarr/<path:category>/artist/<int:artist_id>")
        def api_lidarr_artist_detail(category: str, artist_id: int):
            if (resp := require_token()) is not None:
                return resp
            return _handle_lidarr_artist_detail(category, artist_id)

        @app.get("/web/lidarr/<path:category>/artist/<int:artist_id>")
        def web_lidarr_artist_detail(category: str, artist_id: int):
            if (resp := require_token()) is not None:
                return resp
            return _handle_lidarr_artist_detail(category, artist_id)

        @app.get("/api/lidarr/<path:category>/artist/<int:artist_id>/thumbnail")
        def api_lidarr_artist_thumb(category: str, artist_id: int):
            if (resp := require_token()) is not None:
                return resp
            return _arr_thumbnail(category, "lidarr_artist", artist_id)

        @app.get("/web/lidarr/<path:category>/artist/<int:artist_id>/thumbnail")
        def web_lidarr_artist_thumb(category: str, artist_id: int):
            if (resp := require_token()) is not None:
                return resp
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

        @app.get("/api/arr")
        def api_arr_list():
            if (resp := require_token()) is not None:
                return resp
            return jsonify(_arr_list_payload())

        @app.get("/web/arr")
        def web_arr_list():
            if (resp := require_token()) is not None:
                return resp
            return jsonify(_arr_list_payload())

        @app.get("/web/qbit/categories")
        def web_qbit_categories():
            """Get all qBit-managed and Arr-managed categories with seeding statistics."""
            if (resp := require_token()) is not None:
                return resp
            categories_data = []

            # Add qBit-managed categories
            if self.manager.qbit_category_managers:
                for instance_name, manager in self.manager.qbit_category_managers.items():
                    client = self.manager.get_client(instance_name)
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
                            self.logger.debug(
                                "Error fetching qBit category '%s' stats for instance '%s'",
                                category,
                                instance_name,
                            )
                            continue

            # Add Arr-managed categories
            if hasattr(self.manager, "arr_manager") and self.manager.arr_manager:
                for arr in self.manager.arr_manager.managed_objects.values():
                    if isinstance(arr, (PlaceHolderArr, TorrentPolicyManager)):
                        continue
                    try:
                        # Get the qBit instance for this Arr (use default for now)
                        client = self.manager.client
                        if not client:
                            continue

                        category = arr.category
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

                        categories_data.append(
                            {
                                "category": category,
                                "instance": arr._name,
                                "managedBy": "arr",
                                "torrentCount": total_count,
                                "seedingCount": seeding_count,
                                "totalSize": total_size,
                                "avgRatio": round(avg_ratio, 2),
                                "avgSeedingTime": avg_seeding_time,
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
                        self.logger.debug(
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
            force = self._query_truthy(request.args.get("force"))
            return jsonify(self._ensure_version_info(force=force))

        @app.get("/web/meta")
        def web_meta():
            force = self._query_truthy(request.args.get("force"))
            result = dict(self._ensure_version_info(force=force))
            result["auth_required"] = not _auth_disabled()
            result["local_auth_enabled"] = _local_auth_enabled()
            result["oidc_enabled"] = _oidc_enabled()
            # First-time setup: auth required, no password set, no OIDC — show create-credentials screen
            stored_hash = (CONFIG.get("WebUI.PasswordHash", fallback="") or "").strip()
            result["setup_required"] = (
                not _auth_disabled() and not stored_hash and not _oidc_enabled()
            )
            return jsonify(result)

        def _handle_update():
            ok, message = self._trigger_manual_update()
            if not ok:
                return jsonify({"error": message}), 409
            return jsonify({"status": "started"})

        @app.post("/api/update")
        def api_update():
            if (resp := require_token()) is not None:
                return resp
            return _handle_update()

        @app.post("/web/update")
        def web_update():
            if (resp := require_token()) is not None:
                return resp
            return _handle_update()

        def _handle_download_update():
            from qBitrr.auto_update import get_installation_type

            install_type = get_installation_type()

            if install_type != "binary":
                return jsonify({"error": "Download only available for binary installations"}), 400

            version_info = self._ensure_version_info()

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

        @app.get("/api/download-update")
        def api_download_update():
            if (resp := require_token()) is not None:
                return resp
            return _handle_download_update()

        @app.get("/web/download-update")
        def web_download_update():
            if (resp := require_token()) is not None:
                return resp
            return _handle_download_update()

        def _status_payload() -> dict[str, Any]:
            # Legacy single-instance qBit info (for backward compatibility)
            qb = {
                "alive": bool(self.manager.is_alive),
                "host": self.manager.qBit_Host,
                "port": self.manager.qBit_Port,
                "version": (
                    str(self.manager.current_qbit_version)
                    if self.manager.current_qbit_version
                    else None
                ),
            }

            # Multi-instance qBit info
            qbit_instances = {}
            for instance_name in self.manager.get_all_instances():
                info = self.manager.get_instance_info(instance_name)
                qbit_instances[instance_name] = {
                    "alive": self.manager.is_instance_alive(instance_name),
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
                                self.logger.debug(
                                    "Process is_alive check failed for %s", k, exc_info=True
                                )
                    name = getattr(arr, "_name", k)
                    category = getattr(arr, "category", k)
                    arrs.append({"category": category, "name": name, "type": t, "alive": alive})
            # WebUI settings
            webui_settings = {
                "LiveArr": CONFIG.get("WebUI.LiveArr", fallback=True),
                "GroupSonarr": CONFIG.get("WebUI.GroupSonarr", fallback=True),
                "GroupLidarr": CONFIG.get("WebUI.GroupLidarr", fallback=True),
                "Theme": CONFIG.get("WebUI.Theme", fallback="Dark"),
                "ViewDensity": CONFIG.get("WebUI.ViewDensity", fallback="Comfortable"),
            }

            return {
                "qbit": qb,  # Legacy single-instance (default) for backward compatibility
                "qbitInstances": qbit_instances,  # Multi-instance info
                "arrs": arrs,
                "ready": _ensure_arr_manager_ready(),
                "webui": webui_settings,
            }

        @app.get("/api/status")
        def api_status():
            if (resp := require_token()) is not None:
                return resp
            return jsonify(_status_payload())

        @app.get("/web/status")
        def web_status():
            if (resp := require_token()) is not None:
                return resp
            return jsonify(_status_payload())

        @app.get("/api/torrents/distribution")
        def api_torrents_distribution():
            """Get torrent distribution across qBit instances grouped by category"""
            if (resp := require_token()) is not None:
                return resp

            distribution = {}
            for instance_name in self.manager.get_all_instances():
                if not self.manager.is_instance_alive(instance_name):
                    continue

                try:
                    client = self.manager.get_client(instance_name)
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
            return jsonify({"token": self.token})

        @app.get("/web/token")
        def web_token():
            if not _auth_disabled() and not _authorized():
                return jsonify({"token": ""}), 401
            return jsonify({"token": self.token})

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
                        self.logger.debug(
                            "Process kill failed for %s %s",
                            getattr(arr, "_name", ""),
                            k,
                            exc_info=True,
                        )
                    try:
                        p.terminate()
                    except Exception:
                        self.logger.debug(
                            "Process terminate failed for %s %s",
                            getattr(arr, "_name", ""),
                            k,
                            exc_info=True,
                        )
                    try:
                        self.manager.child_processes.remove(p)
                    except Exception:
                        self.logger.debug(
                            "child_processes.remove failed for %s %s",
                            getattr(arr, "_name", ""),
                            k,
                            exc_info=True,
                        )
                    self.manager._process_registry.pop(p, None)
                import pathos

                target = getattr(arr, f"run_{k}_loop", None)
                if target is None:
                    continue
                new_p = pathos.helpers.mp.Process(target=target, daemon=False)
                setattr(arr, proc_attr, new_p)
                self.manager.child_processes.append(new_p)
                self.manager._process_registry[new_p] = {
                    "category": getattr(arr, "category", ""),
                    "name": getattr(arr, "_name", getattr(arr, "category", "")),
                    "role": k,
                }
                new_p.start()
                restarted.append(k)
            return jsonify({"status": "ok", "restarted": restarted})

        @app.post("/api/arr/<section>/restart")
        def api_arr_restart(section: str):
            if (resp := require_token()) is not None:
                return resp
            # Section is the category key in managed_objects
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            if section not in managed:
                return jsonify({"error": f"Unknown section {section}"}), 404
            arr = managed[section]
            return _restart_arr_instance(arr)

        @app.post("/web/arr/<section>/restart")
        def web_arr_restart(section: str):
            if (resp := require_token()) is not None:
                return resp
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            if section not in managed:
                return jsonify({"error": f"Unknown section {section}"}), 404
            arr = managed[section]
            return _restart_arr_instance(arr)

        @app.get("/api/config")
        def api_get_config():
            if (resp := require_token()) is not None:
                return resp
            try:
                # Reload config from disk to reflect latest file
                try:
                    CONFIG.load()
                except Exception:
                    self.logger.debug("CONFIG.load failed in api_get_config", exc_info=True)
                # Render current config as a JSON-able dict via tomlkit; never expose secrets
                data = _toml_to_jsonable(CONFIG.config)
                data = _strip_sensitive_keys(data)
                return jsonify(data)
            except Exception:
                self.logger.debug("api_get_config failed", exc_info=True)
                return jsonify({"error": "Failed to load config"}), 500

        @app.get("/web/config")
        def web_get_config():
            if (resp := require_token()) is not None:
                return resp
            try:
                try:
                    CONFIG.load()
                except Exception:
                    self.logger.debug("CONFIG.load failed in web_get_config", exc_info=True)
                data = _toml_to_jsonable(CONFIG.config)
                # Always redact secrets so API/Web UI never expose qBit passwords or Arr API keys
                data = _strip_sensitive_keys(data)

                # Check config version and add warning if mismatch
                from qBitrr.config_version import get_config_version, validate_config_version

                is_valid, validation_result = validate_config_version(CONFIG)
                if not is_valid:
                    # Add version mismatch warning to response
                    response_data = {
                        "config": data,
                        "warning": {
                            "type": "config_version_mismatch",
                            "message": validation_result,
                            "currentVersion": get_config_version(CONFIG),
                        },
                    }
                    return jsonify(response_data)

                return jsonify(data)
            except Exception:
                self.logger.debug("web_get_config failed", exc_info=True)
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

            # Define key categories
            frontend_only_keys = {
                "WebUI.LiveArr",
                "WebUI.GroupSonarr",
                "WebUI.GroupLidarr",
                "WebUI.Theme",
                "WebUI.ViewDensity",
            }
            webui_restart_keys = {
                "WebUI.Host",
                "WebUI.Port",
                "WebUI.Token",
                "WebUI.AuthDisabled",
                "WebUI.BehindHttpsProxy",
                "WebUI.LocalAuthEnabled",
                "WebUI.OIDCEnabled",
                "WebUI.PasswordHash",
                "WebUI.OIDC.Authority",
                "WebUI.OIDC.ClientId",
                "WebUI.OIDC.ClientSecret",
                "WebUI.OIDC.Scopes",
                "WebUI.OIDC.CallbackPath",
                "WebUI.OIDC.RequireHttpsMetadata",
            }

            # Analyze changes to determine reload strategy
            affected_arr_instances = set()
            has_global_changes = False
            has_webui_changes = False
            has_frontend_only_changes = False

            for key in changes.keys():
                if key in frontend_only_keys:
                    has_frontend_only_changes = True
                elif key in webui_restart_keys:
                    has_webui_changes = True
                elif key.startswith("WebUI."):
                    # Unknown WebUI key, treat as webui change for safety
                    has_webui_changes = True
                elif match := re.match(
                    r"^(Radarr|Sonarr|Lidarr|Animarr)[^.]*\.(.+)$", key, re.IGNORECASE
                ):
                    # Arr instance specific change
                    instance_name = key.split(".")[0]
                    affected_arr_instances.add(instance_name)
                else:
                    # Settings.*, qBit.*, or unknown - requires full reload
                    has_global_changes = True

            # Apply all changes to config
            for key, val in changes.items():
                if val is None:
                    _toml_delete(CONFIG.config, key)
                    if key == "WebUI.Token":
                        self.token = ""
                    continue
                # Never overwrite a real secret with the redaction placeholder from the client
                if _is_sensitive_dotted_key(key) and str(val).strip() == REDACTED_PLACEHOLDER:
                    continue
                _toml_set(CONFIG.config, key, val)
                if key == "WebUI.Token":
                    # Update in-memory token immediately
                    self.token = str(val) if val is not None else ""

            # Persist config
            try:
                CONFIG.save()
            except Exception:
                self.logger.debug("Failed to save config", exc_info=True)
                return jsonify({"error": "Failed to save config"}), 500

            # Determine reload strategy
            reload_type = "none"
            affected_instances_list = []

            if has_global_changes:
                # Global settings changed - full reload required
                # This affects ALL instances (qBit settings, loop timers, etc.)
                reload_type = "full"
                self.logger.notice("Global settings changed, performing full reload")
                try:
                    self.manager.configure_auto_update()
                except Exception:
                    self.logger.exception("Failed to refresh auto update configuration")
                self._reload_all()

            elif len(affected_arr_instances) >= 1:
                # One or more Arr instances changed - reload each individually
                # NEVER trigger global reload for Arr-only changes
                reload_type = "multi_arr" if len(affected_arr_instances) > 1 else "single_arr"
                affected_instances_list = sorted(affected_arr_instances)

                self.logger.notice(
                    "Reloading %d Arr instance(s): %s",
                    len(affected_instances_list),
                    ", ".join(affected_instances_list),
                )

                # Reload each affected instance in sequence
                for instance_name in affected_instances_list:
                    self._reload_arr_instance(instance_name)

            elif has_webui_changes:
                # Only WebUI settings changed - restart WebUI
                reload_type = "webui"
                self.logger.notice("WebUI settings changed, restarting WebUI server")
                # Run restart in background thread to avoid blocking response
                restart_thread = threading.Thread(
                    target=self._restart_webui, name="WebUIRestart", daemon=True
                )
                restart_thread.start()

            elif has_frontend_only_changes:
                # Only frontend settings changed - no reload
                reload_type = "frontend"
                self.logger.debug("Frontend-only settings changed, no reload required")

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
            if reload_type in ("full", "single_arr", "multi_arr", "webui"):
                response.headers["X-Config-Reloaded"] = "true"

            return response

        @app.post("/api/config")
        def api_update_config():
            if (resp := require_token()) is not None:
                return resp
            return _handle_config_update()

        @app.post("/web/config")
        def web_update_config():
            if (resp := require_token()) is not None:
                return resp
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
                            jsonify(
                                {"success": False, "message": "Missing required field: arrType"}
                            ),
                            400,
                        )
                    try:
                        CONFIG.load()
                    except Exception:
                        pass
                    uri = CONFIG.get(f"{instance_key}.URI", fallback=None)
                    api_key = CONFIG.get(f"{instance_key}.APIKey", fallback=None)
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
                        jsonify(
                            {"success": False, "message": "URI must use http or https scheme"}
                        ),
                        400,
                    )
                if not parsed.hostname:
                    return (
                        jsonify(
                            {"success": False, "message": "URI must contain a valid hostname"}
                        ),
                        400,
                    )

                # Try to find existing Arr instance with matching URI
                existing_arr = None
                managed = _managed_objects()
                for group_name, arr_instance in managed.items():
                    if hasattr(arr_instance, "uri") and hasattr(arr_instance, "apikey"):
                        if arr_instance.uri == uri and arr_instance.apikey == api_key:
                            existing_arr = arr_instance
                            self.logger.info("Using existing Arr instance: %s", group_name)
                            break

                # Use existing client if available, otherwise create temporary one
                if existing_arr and hasattr(existing_arr, "client"):
                    client = existing_arr.client
                    self.logger.info("Reusing existing client for %s", existing_arr._name)
                else:
                    # Create temporary Arr API client
                    self.logger.info("Creating temporary %s client for %s", arr_type, uri)
                    if instance_key:
                        skip_tls_servarr = CONFIG.get(
                            f"{instance_key}.SkipTLSVerify", fallback=False
                        )
                    else:
                        skip_tls_servarr = bool(data.get("skipTlsVerify", False))
                    verify_ssl = not skip_tls_servarr
                    if arr_type == "radarr":
                        from qBitrr.pyarr_compat import RadarrAPI

                        client = RadarrAPI(uri, api_key, verify_ssl=verify_ssl)
                    elif arr_type == "sonarr":
                        from qBitrr.pyarr_compat import SonarrAPI

                        client = SonarrAPI(uri, api_key, verify_ssl=verify_ssl)
                    elif arr_type == "lidarr":
                        from qBitrr.pyarr_compat import LidarrAPI

                        client = LidarrAPI(uri, api_key, verify_ssl=verify_ssl)
                    else:
                        return (
                            jsonify({"success": False, "message": f"Invalid arrType: {arr_type}"}),
                            400,
                        )

                # Test connection (no timeout - Flask/Waitress handles this)
                try:
                    self.logger.info("Testing connection to %s at %s", arr_type, uri)

                    # Get system info to verify connection
                    system_info = client.get_system_status()
                    self.logger.info(
                        "System status retrieved: %s", system_info.get("version", "unknown")
                    )

                    # Fetch quality profiles with retry logic (same as backend)
                    from json import JSONDecodeError

                    import requests

                    from qBitrr.pyarr_compat import PyarrServerError

                    max_retries = 3
                    retry_count = 0
                    quality_profiles = []

                    while retry_count < max_retries:
                        try:
                            quality_profiles = client.get_quality_profile()
                            self.logger.info(
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
                            self.logger.warning(
                                "Transient error fetching quality profiles (attempt %d/%d): %s",
                                retry_count,
                                max_retries,
                                e,
                            )
                            if retry_count >= max_retries:
                                self.logger.error("Failed to fetch quality profiles after retries")
                                quality_profiles = []
                                break
                            time.sleep(1)
                        except PyarrServerError as e:
                            self.logger.error("Server error fetching quality profiles: %s", e)
                            quality_profiles = []
                            break
                        except Exception as e:
                            self.logger.error("Unexpected error fetching quality profiles: %s", e)
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
                    self.logger.error("Connection test failed: %s", error_msg)

                    if "401" in error_msg or "Unauthorized" in error_msg:
                        return jsonify(
                            {"success": False, "message": "Unauthorized: Invalid API key"}
                        )
                    elif "404" in error_msg:
                        return jsonify(
                            {"success": False, "message": f"Not found: Check URI ({uri})"}
                        )
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
                self.logger.error("Test connection error: %s", e)
                return jsonify({"success": False, "message": "Connection test failed"}), 500

        @app.post("/api/arr/test-connection")
        def api_arr_test_connection():
            if (resp := require_token()) is not None:
                return resp
            return _handle_test_connection()

        @app.post("/web/arr/test-connection")
        def web_arr_test_connection():
            if (resp := require_token()) is not None:
                return resp
            return _handle_test_connection()

    def _reload_all(self):
        # Set rebuilding flag
        self._rebuilding_arrs = True
        try:
            # Stop current processes
            for p in list(self.manager.child_processes):
                try:
                    p.kill()
                except Exception:
                    self.logger.debug("Reload: process kill failed", exc_info=True)
                try:
                    p.terminate()
                except Exception:
                    self.logger.debug("Reload: process terminate failed", exc_info=True)
            self.manager.child_processes.clear()
            self.manager._process_registry.clear()

            # Delete database files for all arr instances before rebuilding
            if hasattr(self.manager, "arr_manager") and self.manager.arr_manager:
                for arr in self.manager.arr_manager.managed_objects.values():
                    try:
                        if hasattr(arr, "search_db_file") and arr.search_db_file:
                            # Delete main database file
                            if arr.search_db_file.exists():
                                self.logger.info("Deleting database file: %s", arr.search_db_file)
                                arr.search_db_file.unlink()
                                self.logger.success("Deleted database file for %s", arr._name)
                            # Delete WAL file (Write-Ahead Log)
                            wal_file = arr.search_db_file.with_suffix(".db-wal")
                            if wal_file.exists():
                                self.logger.info("Deleting WAL file: %s", wal_file)
                                wal_file.unlink()
                            # Delete SHM file (Shared Memory)
                            shm_file = arr.search_db_file.with_suffix(".db-shm")
                            if shm_file.exists():
                                self.logger.info("Deleting SHM file: %s", shm_file)
                                shm_file.unlink()
                    except Exception as e:
                        self.logger.warning(
                            "Failed to delete database files for %s: %s", arr._name, e
                        )

            # Rebuild arr manager from config and spawn fresh
            from qBitrr.arss import ArrManager

            self.manager.arr_manager = ArrManager(self.manager).build_arr_instances()
            self.manager.configure_auto_update()
            # Spawn and start new processes
            for arr in self.manager.arr_manager.managed_objects.values():
                _, procs = arr.spawn_child_processes()
                for p in procs:
                    try:
                        p.start()
                    except Exception:
                        self.logger.debug(
                            "Reload: failed to start process for %s",
                            getattr(arr, "_name", ""),
                            exc_info=True,
                        )

            # Rebuild qBit category managers from fresh config
            self.manager.qbit_category_configs.clear()
            self.manager.qbit_category_managers.clear()
            self.manager._reload_qbit_category_configs()
            self.manager._initialize_qbit_category_managers()
            self.manager._spawn_qbit_category_workers()
        finally:
            # Clear rebuilding flag
            self._rebuilding_arrs = False

    def _restart_webui(self):
        """
        Gracefully restart the WebUI server without affecting Arr processes.
        This is used when WebUI.Host, WebUI.Port, or WebUI.Token changes.
        """
        self.logger.notice("WebUI restart requested (config changed)")

        # Reload config values
        try:
            CONFIG.load()
        except Exception as e:
            self.logger.warning("Failed to reload config: %s", e)

        # Update in-memory values
        new_host = CONFIG.get("WebUI.Host", fallback="0.0.0.0")
        new_port = CONFIG.get("WebUI.Port", fallback=6969)
        new_token = CONFIG.get("WebUI.Token", fallback=None)

        # Check if restart is actually needed
        needs_restart = new_host != self.host or new_port != self.port

        # Token can be updated without restart
        if new_token != self.token:
            self.token = new_token
            self.logger.info("WebUI token updated")

        if not needs_restart:
            self.logger.info("WebUI Host/Port unchanged, restart not required")
            return

        # Update host/port
        self.host = new_host
        self.port = new_port

        # Signal restart
        self._restart_requested = True
        self._shutdown_event.set()

        self.logger.info("WebUI will restart on %s:%s", self.host, self.port)

    def _stop_arr_instance(self, arr, category: str):
        """Stop and cleanup a single Arr instance."""
        self.logger.info("Stopping Arr instance: %s", category)

        # Stop processes
        for loop_kind in ("search", "torrent"):
            proc_attr = f"process_{loop_kind}_loop"
            process = getattr(arr, proc_attr, None)
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    self.logger.debug(
                        "Stop instance: process kill failed for %s %s",
                        category,
                        loop_kind,
                        exc_info=True,
                    )
                try:
                    process.terminate()
                except Exception:
                    self.logger.debug(
                        "Stop instance: process terminate failed for %s %s",
                        category,
                        loop_kind,
                        exc_info=True,
                    )
                try:
                    self.manager.child_processes.remove(process)
                except Exception:
                    self.logger.debug(
                        "Stop instance: child_processes.remove failed for %s %s",
                        category,
                        loop_kind,
                        exc_info=True,
                    )
                self.logger.debug("Stopped %s process for %s", loop_kind, category)

        # Delete database files
        try:
            if hasattr(arr, "search_db_file") and arr.search_db_file:
                if arr.search_db_file.exists():
                    self.logger.info("Deleting database file: %s", arr.search_db_file)
                    arr.search_db_file.unlink()
                    self.logger.success(
                        "Deleted database file for %s", getattr(arr, "_name", category)
                    )
                # Delete WAL and SHM files
                for suffix in (".db-wal", ".db-shm"):
                    aux_file = arr.search_db_file.with_suffix(suffix)
                    if aux_file.exists():
                        self.logger.debug("Deleting auxiliary file: %s", aux_file)
                        aux_file.unlink()
        except Exception as e:
            self.logger.warning(
                "Failed to delete database files for %s: %s", getattr(arr, "_name", category), e
            )

        # Remove from managed_objects
        self.manager.arr_manager.managed_objects.pop(category, None)
        self.manager.arr_manager.groups.discard(getattr(arr, "_name", ""))
        self.manager.arr_manager.uris.discard(getattr(arr, "uri", ""))
        self.manager.arr_manager.arr_categories.discard(category)

        self.logger.success("Stopped and cleaned up Arr instance: %s", category)

    def _start_arr_instance(self, instance_name: str):
        """Create and start a single Arr instance."""
        self.logger.info("Starting Arr instance: %s", instance_name)

        # Check if instance is managed
        if not CONFIG.get(f"{instance_name}.Managed", fallback=False):
            self.logger.info("Instance %s is not managed, skipping", instance_name)
            return

        # Determine client class based on name
        client_cls = None
        if re.match(r"^(Rad|rad)arr", instance_name):
            from qBitrr.pyarr_compat import RadarrAPI

            client_cls = RadarrAPI
        elif re.match(r"^(Son|son|Anim|anim)arr", instance_name):
            from qBitrr.pyarr_compat import SonarrAPI

            client_cls = SonarrAPI
        elif re.match(r"^(Lid|lid)arr", instance_name):
            from qBitrr.pyarr_compat import LidarrAPI

            client_cls = LidarrAPI
        else:
            self.logger.error("Unknown Arr type for instance: %s", instance_name)
            return

        try:
            # Create new Arr instance
            from qBitrr.arss import Arr
            from qBitrr.errors import SkipException

            new_arr = Arr(instance_name, self.manager.arr_manager, client_cls=client_cls)

            # Register in manager
            self.manager.arr_manager.groups.add(instance_name)
            self.manager.arr_manager.uris.add(new_arr.uri)
            self.manager.arr_manager.managed_objects[new_arr.category] = new_arr
            self.manager.arr_manager.arr_categories.add(new_arr.category)

            # Spawn and start processes
            _, procs = new_arr.spawn_child_processes()
            for p in procs:
                try:
                    p.start()
                    self.logger.debug("Started process (PID: %s) for %s", p.pid, instance_name)
                except Exception as e:
                    self.logger.error("Failed to start process for %s: %s", instance_name, e)

            self.logger.success(
                "Started Arr instance: %s (category: %s)", instance_name, new_arr.category
            )

        except SkipException:
            self.logger.info("Instance %s skipped (not managed or disabled)", instance_name)
        except Exception as e:
            self.logger.error(
                "Failed to start Arr instance %s: %s", instance_name, e, exc_info=True
            )

    def _reload_arr_instance(self, instance_name: str):
        """Reload a single Arr instance without affecting others."""
        self.logger.notice("Reloading Arr instance: %s", instance_name)

        if not hasattr(self.manager, "arr_manager") or not self.manager.arr_manager:
            self.logger.warning("Cannot reload Arr instance: ArrManager not initialized")
            return

        managed_objects = self.manager.arr_manager.managed_objects

        # Find the instance by name (key is category, so search by _name attribute)
        old_arr = None
        old_category = None
        for category, arr in list(managed_objects.items()):
            if getattr(arr, "_name", None) == instance_name:
                old_arr = arr
                old_category = category
                break

        # Check if instance exists in config
        instance_exists_in_config = instance_name in CONFIG.sections()

        # Handle deletion case
        if not instance_exists_in_config:
            if old_arr:
                self.logger.info("Instance %s removed from config, stopping...", instance_name)
                self._stop_arr_instance(old_arr, old_category)
            else:
                self.logger.debug("Instance %s not found in config or memory", instance_name)
            return

        # Handle update/addition
        if old_arr:
            # Update existing - stop old processes first
            self.logger.info("Updating existing Arr instance: %s", instance_name)
            self._stop_arr_instance(old_arr, old_category)
        else:
            self.logger.info("Adding new Arr instance: %s", instance_name)

        # Small delay to ensure cleanup completes
        time.sleep(0.5)

        # Create new instance
        self._start_arr_instance(instance_name)

        self.logger.success("Successfully reloaded Arr instance: %s", instance_name)

    def start(self):
        if self._thread and self._thread.is_alive():
            self.logger.debug("WebUI already running on %s:%s", self.host, self.port)
            return
        self.logger.notice("Starting WebUI on %s:%s", self.host, self.port)
        self._thread = threading.Thread(target=self._serve, name="WebUI", daemon=True)
        self._thread.start()
        self.logger.success("WebUI thread started (name=%s)", self._thread.name)

    def _serve(self):
        try:
            # Reset shutdown event at start
            self._shutdown_event.clear()

            if self._should_use_dev_server():
                self.logger.info("Using Flask development server for WebUI")
                # Flask dev server - will exit on KeyboardInterrupt
                try:
                    self.app.run(
                        host=self.host,
                        port=self.port,
                        debug=False,
                        use_reloader=False,
                        threaded=True,
                    )
                except (KeyboardInterrupt, SystemExit):
                    pass
                return

            try:
                from waitress import serve as waitress_serve
            except Exception:
                self.logger.warning(
                    "Waitress is unavailable; falling back to Flask development server. "
                    "Install the 'waitress' extra or set QBITRR_USE_DEV_SERVER=1 to silence this message."
                )
                self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
                return

            self.logger.info("Using Waitress WSGI server for WebUI")

            # For graceful restart capability, we need to use waitress_serve with channels
            # However, for now we'll use the simpler approach and just run the server
            # Restart capability will require stopping the entire process
            # Use poll() instead of select() to avoid file descriptor limit issues
            waitress_serve(
                self.app,
                host=self.host,
                port=self.port,
                ident="qBitrr-WebUI",
                asyncore_use_poll=True,
            )

        except KeyboardInterrupt:
            self.logger.info("WebUI interrupted")
        except Exception:
            self.logger.exception("WebUI server terminated unexpectedly")
        finally:
            self._server = None

            # If restart was requested, start a new server
            if self._restart_requested:
                self._restart_requested = False
                self.logger.info("Restarting WebUI server...")
                time.sleep(0.5)  # Brief pause
                self.start()  # Restart

    def _should_use_dev_server(self) -> bool:
        if self._use_dev_server is not None:
            return self._use_dev_server
        override = os.environ.get("QBITRR_USE_DEV_SERVER", "")
        if override:
            self._use_dev_server = override.strip().lower() not in {"0", "false", "no", "off"}
            return self._use_dev_server
        self._use_dev_server = False
        return self._use_dev_server
