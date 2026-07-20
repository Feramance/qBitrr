from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from authlib.integrations.flask_client import OAuth
from flask import Flask, request

from qBitrr.bundled_data import patched_version, tagged_version
from qBitrr.errors import ConfigException
from qBitrr.versioning import fetch_latest_release, fetch_release_by_tag
from qBitrr.webui.auth import (
    _allow_insecure_exposure,
    _auth_disabled,
    _check_insecure_exposure,
    _oidc_enabled,
)
from qBitrr.webui.catalog.queries import Catalog
from qBitrr.webui.config_toml import _toml_set
from qBitrr.webui.lifecycle import Lifecycle
from qBitrr.webui.urlbase import _install_url_base_middleware, configured_url_base

# Waitress worker threads for concurrent API + poster thumbnail traffic.
_WAITRESS_THREADS = 16


def _config():
    import qBitrr.webui as webui_mod

    return webui_mod.CONFIG


def _run_logs(logger, name: str) -> None:
    import qBitrr.webui as webui_mod

    return webui_mod.run_logs(logger, name)


class WebUI(Catalog, Lifecycle):
    def __init__(self, manager, host: str = "0.0.0.0", port: int = 6969):
        self.manager = manager
        self.host = host
        self.port = port
        self.app = self._build_app()
        self.logger = logging.getLogger("qBitrr.WebUI")
        _run_logs(self.logger, "WebUI")
        self.logger.info("Initialising WebUI on %s:%s", self.host, self.port)
        insecure_error = _check_insecure_exposure(self.host)
        if insecure_error:
            self.logger.error(insecure_error)
            raise ConfigException(insecure_error)
        if self.host in {"0.0.0.0", "::"}:
            self.logger.warning(
                "WebUI configured to listen on %s. Expose this only behind a trusted reverse proxy.",
                self.host,
            )
            if _auth_disabled():
                if _allow_insecure_exposure() is None:
                    self.logger.warning(
                        "WebUI authentication is disabled on a public bind and "
                        "WebUI.AllowInsecureExposure is unset (legacy config). All API and WebUI "
                        "actions — including /api/token, /web/token, config writes, and self-update "
                        "— are available without credentials. Set AllowInsecureExposure = true to "
                        "acknowledge this, bind Host to 127.0.0.1, or set AuthDisabled = false."
                    )
                else:
                    self.logger.warning(
                        "WebUI authentication is disabled: all API and WebUI actions are available "
                        "without credentials to any client that can reach this port "
                        "(AllowInsecureExposure=true). If that is not intentional, enable "
                        "authentication (see WebUI.AuthDisabled), bind WebUI.Host to 127.0.0.1, "
                        "or place the service behind a trusted reverse proxy with its own "
                        "access controls."
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
        static_root = Path(__file__).resolve().parent.parent / "static"
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

    def _build_app(self) -> Flask:
        """Construct and configure the Flask application (test seam)."""
        static_root = Path(__file__).resolve().parent.parent / "static"
        app = Flask(
            "qBitrr.webui.app",
            static_folder=str(static_root),
            static_url_path="/static",
        )
        url_base = configured_url_base()
        if url_base:
            app.config["APPLICATION_ROOT"] = url_base
        logger = logging.getLogger("qBitrr.WebUI")
        app.logger.handlers.clear()
        app.logger.propagate = True
        app.logger.setLevel(logger.level)
        werkzeug_logger = logging.getLogger("werkzeug")
        werkzeug_logger.handlers.clear()
        werkzeug_logger.propagate = True
        werkzeug_logger.setLevel(logger.level)

        if _config().get("WebUI.BehindHttpsProxy", fallback=False):
            from werkzeug.middleware.proxy_fix import ProxyFix

            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

        _install_url_base_middleware(app)

        @app.after_request
        def add_cache_headers(response):
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            # Modest CSP: self by default; Swagger UI on /docs may load jsDelivr (SRI in HTML).
            path = request.path or ""
            if path.endswith("/docs") or path in {"/api/docs", "/web/docs"}:
                csp = (
                    "default-src 'self'; "
                    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
                    "img-src 'self' data: https://cdn.jsdelivr.net; "
                    "font-src 'self' https://cdn.jsdelivr.net; "
                    "connect-src 'self'; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self'"
                )
            else:
                csp = (
                    "default-src 'self'; "
                    "script-src 'self'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data: blob:; "
                    "font-src 'self' data:; "
                    "connect-src 'self'; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self'"
                )
            response.headers.setdefault("Content-Security-Policy", csp)
            if path in (
                "/static/index.html",
                "/ui",
                "/ui/",
                "/static/sw.js",
                "/sw.js",
            ):
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
            return response

        self.token = _config().get("WebUI.Token", fallback=None)
        if not self.token:
            self.token = secrets.token_hex(32)
            try:
                _toml_set(_config().config, "WebUI.Token", self.token)
                _config().save()
            except Exception:
                logger.warning("Failed to persist generated WebUI token to config", exc_info=True)
            else:
                logger.notice("Generated new WebUI token")

        app.secret_key = secrets.token_hex(32)
        session_config: dict[str, Any] = {
            "SESSION_COOKIE_NAME": "qbitrr_session",
            "SESSION_COOKIE_HTTPONLY": True,
            "SESSION_COOKIE_SAMESITE": "Lax",
            "SESSION_COOKIE_SECURE": bool(_config().get("WebUI.BehindHttpsProxy", fallback=False)),
            "PERMANENT_SESSION_LIFETIME": timedelta(days=7),
        }
        url_base = configured_url_base()
        if url_base:
            session_config["SESSION_COOKIE_PATH"] = f"{url_base}/"
        app.config.update(session_config)

        self._oauth = OAuth(app)
        if _oidc_enabled():
            authority = (_config().get("WebUI.OIDC.Authority", fallback="") or "").rstrip("/")
            self._oauth.register(
                name="oidc",
                server_metadata_url=f"{authority}/.well-known/openid-configuration",
                client_id=_config().get("WebUI.OIDC.ClientId", fallback=""),
                client_secret=_config().get("WebUI.OIDC.ClientSecret", fallback=""),
                client_kwargs={
                    "scope": _config().get("WebUI.OIDC.Scopes", fallback="openid profile")
                },
            )
        return app

    def _register_routes(self) -> None:
        from qBitrr.webui.routes import register_routes

        register_routes(self)

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

                target = None
                with self._version_lock:
                    target = self._version_cache.get("latest_version")
                if not perform_self_update(self.manager.logger, target_version=target):
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

    def start(self):
        if self._thread and self._thread.is_alive():
            self.logger.debug("WebUI already running on %s:%s", self.host, self.port)
            return
        self.logger.notice("Starting WebUI on %s:%s", self.host, self.port)
        self._thread = threading.Thread(target=self._serve, name="WebUI", daemon=True)
        self._thread.start()
        self.logger.success("WebUI thread started (name=%s)", self._thread.name)

    def _serve(self):
        server = None
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
                from waitress import create_server
            except Exception:
                self.logger.warning(
                    "Waitress is unavailable; falling back to Flask development server. "
                    "Install the 'waitress' extra or set QBITRR_USE_DEV_SERVER=1 to silence this message."
                )
                self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
                return

            self.logger.info(
                "Using Waitress WSGI server for WebUI (threads=%s)", _WAITRESS_THREADS
            )

            try:
                # Use poll() instead of select() to avoid file descriptor limit issues.
                # create_server (vs serve) keeps a handle we can close() for Host/Port rebind.
                server = create_server(
                    self.app,
                    host=self.host,
                    port=self.port,
                    ident="qBitrr-WebUI",
                    threads=_WAITRESS_THREADS,
                    asyncore_use_poll=True,
                )
            except Exception as exc:
                self.logger.error(
                    "Failed to bind WebUI on %s:%s: %s. "
                    "Restart the qBitrr process or fix WebUI.Host/WebUI.Port.",
                    self.host,
                    self.port,
                    exc,
                    exc_info=True,
                )
                return

            self._server = server

            def _close_on_shutdown() -> None:
                self._shutdown_event.wait()
                try:
                    if self._server is server:
                        server.close()
                except Exception:
                    self.logger.debug("Waitress close on shutdown failed", exc_info=True)

            watcher = threading.Thread(
                target=_close_on_shutdown, name="WebUIShutdownWatch", daemon=True
            )
            watcher.start()

            try:
                server.run()
            finally:
                try:
                    server.close()
                except Exception:
                    self.logger.debug("Waitress server.close() failed", exc_info=True)
                try:
                    server.task_dispatcher.shutdown(cancel_pending=True, timeout=5)
                except Exception:
                    self.logger.debug("Waitress task_dispatcher.shutdown failed", exc_info=True)

        except KeyboardInterrupt:
            self.logger.info("WebUI interrupted")
        except Exception:
            self.logger.exception("WebUI server terminated unexpectedly")
        finally:
            if self._server is server:
                self._server = None

            # Fallback restart path (primary rebind is owned by _restart_webui).
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
