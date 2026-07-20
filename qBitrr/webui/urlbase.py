from __future__ import annotations

from typing import Any

from flask import Flask

# CONFIG is re-exported on qBitrr.webui; import from config for construction,
# but configured_url_base reads via qBitrr.webui.CONFIG when patched.
from qBitrr.config import CONFIG as _CONFIG_DEFAULT
from qBitrr.utils import normalize_url_base


def _get_config():
    import qBitrr.webui as webui_mod

    return getattr(webui_mod, "CONFIG", _CONFIG_DEFAULT)


def configured_url_base() -> str:
    """Return the configured public URL path prefix for the WebUI."""
    return normalize_url_base(_get_config().get("WebUI.UrlBase", fallback=""))


def _forwarded_url_prefix(environ: dict[str, Any]) -> str:
    """Read public path prefix set by a reverse proxy (strip-mode deployments)."""
    for header in ("HTTP_X_FORWARDED_PREFIX", "HTTP_X_SCRIPT_NAME"):
        raw = environ.get(header, "")
        if not raw:
            continue
        return normalize_url_base(raw.split(",")[0].strip())
    return ""


def _merge_script_name(environ: dict[str, Any], prefix: str) -> None:
    """Set SCRIPT_NAME so Flask generates browser-facing URLs under UrlBase."""
    if not prefix:
        return
    existing = environ.get("SCRIPT_NAME", "").rstrip("/")
    if existing == prefix or existing.endswith(prefix):
        return
    environ["SCRIPT_NAME"] = f"{existing}{prefix}" if existing else prefix


class UrlBaseMiddleware:
    """Normalize UrlBase for WSGI: strip incoming prefix or honor proxy strip headers."""

    def __init__(self, app: Any) -> None:
        self._app = app

    def __call__(self, environ: dict[str, Any], start_response: Any) -> Any:
        prefix = configured_url_base()
        path = environ.get("PATH_INFO", "") or "/"
        if not prefix:
            return self._app(environ, start_response)

        forwarded_prefix = _forwarded_url_prefix(environ)
        if path == prefix or path.startswith(f"{prefix}/"):
            _merge_script_name(environ, prefix)
            stripped = path[len(prefix) :]
            environ["PATH_INFO"] = stripped or "/"
        elif forwarded_prefix == prefix:
            _merge_script_name(environ, prefix)
        return self._app(environ, start_response)


def _unwrap_url_base_middleware(wsgi_app: Any) -> Any:
    """Return the WSGI app below any stacked UrlBaseMiddleware layers."""
    while isinstance(wsgi_app, UrlBaseMiddleware):
        wsgi_app = wsgi_app._app
    return wsgi_app


def _install_url_base_middleware(app: Flask) -> None:
    """Ensure exactly one UrlBaseMiddleware wraps the current WSGI stack."""
    inner = _unwrap_url_base_middleware(app.wsgi_app)
    app.wsgi_app = UrlBaseMiddleware(inner)
