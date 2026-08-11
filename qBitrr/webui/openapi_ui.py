from __future__ import annotations

import importlib.resources
import json
import threading
from typing import Any

_openapi_spec_lock = threading.Lock()
_openapi_spec: dict[str, Any] | None = None
_openapi_spec_api_only: dict[str, Any] | None = None


def _openapi_path_in_api_first_spec(path: str) -> bool:
    """Paths exposed in the filtered OpenAPI doc (Swagger): `/api/*` plus mirrored poster thumbnails."""
    if not path.startswith("/web/"):
        return True
    if not path.endswith("/thumbnail"):
        return False
    return path.startswith(("/web/radarr/", "/web/sonarr/", "/web/lidarr/", "/web/readarr/"))


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
