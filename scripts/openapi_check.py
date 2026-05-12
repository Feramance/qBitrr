#!/usr/bin/env python3
"""
Static drift check between Flask routes registered in :mod:`qBitrr.webui` and the
OpenAPI document at ``qBitrr/openapi.json``.

The check is intentionally text-based: it parses ``qBitrr/webui.py`` for every
``@app.<method>("/path")`` decorator and walks the OpenAPI ``paths`` object once.
That keeps it fast and side-effect free (no need to import the WebUI, no DB or
config dependency, no Flask runtime).

Drift directions reported (each is a non-zero exit):

1. **Missing in OpenAPI** — a route is registered on the Flask app but no
   matching ``(path, method)`` exists under ``paths`` in ``openapi.json``.
   This caught the `/api/lidarr/<category>/albums` regression flagged in
   the 5.12 deep review (B-2, L-8).
2. **Missing in code** — the OpenAPI spec advertises a path/method but no
   decorator registers it.

Path scoping
------------
The Flask app exposes both `/api/*` (documented) and `/web/*` (helpers).
Historically only `/api/*` was in OpenAPI, but the thumbnail proxy now
mirrors `/web/...` paths in the spec (see ``docs/webui/api.md``).  We
therefore check **every** path that appears in either side rather than
filter to a single prefix; if the two stop agreeing, the diff fires.

Parameter naming
----------------
We compare path *shape* not parameter labels.  Both ``/foo/{id}`` and
``/foo/{entry_id}`` collapse to ``/foo/{*}`` for the diff so a cosmetic
rename (which OpenAPI lets you do without breaking clients) doesn't
masquerade as drift.  Method mismatches and missing path segments still
fire.

Dynamic paths
-------------
Some routes are registered with a configurable path (e.g. the OIDC
callback ``WebUI.OIDC.CallbackPath``).  Those decorators read from a
variable and are not statically resolvable, so we record their default
value in :data:`_DYNAMIC_ROUTES` and treat them as registered.

Usage::

    python scripts/openapi_check.py            # exit 0 / 1
    make openapi-check                         # same, via Makefile

Run it locally before opening a PR that adds or renames a route.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEBUI_PY = REPO_ROOT / "qBitrr" / "webui.py"
OPENAPI_JSON = REPO_ROOT / "qBitrr" / "openapi.json"

# Methods we care about.  ``route`` is the generic flask decorator; the others
# are the per-method shortcuts used throughout webui.py.
_HTTP_METHODS = ("get", "post", "put", "delete", "patch")
_DECORATOR_RE = re.compile(
    r"^\s*@app\.(?P<method>get|post|put|delete|patch|route)\(\s*"
    r"(?P<quote>[\"'])(?P<path>[^\"']+)(?P=quote)"
    r"(?:\s*,\s*methods\s*=\s*\[(?P<methods>[^\]]+)\])?",
    re.MULTILINE,
)
_FLASK_PARAM_RE = re.compile(r"<(?:[a-zA-Z_]+:)?([a-zA-Z_][a-zA-Z0-9_]*)>")
_OPENAPI_PARAM_RE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")

# Routes registered with a config-variable path; we cannot resolve them statically,
# so we register the default value as if it were declared.  When a config option's
# default genuinely changes, both this list and the OpenAPI document need updating.
_DYNAMIC_ROUTES: tuple[tuple[str, str], ...] = (("/signin-oidc", "get"),)


def _normalise_flask_path(path: str) -> str:
    """Convert Flask ``<int:foo>`` parameter syntax to a placeholder ``{*}``."""
    return _FLASK_PARAM_RE.sub("{*}", path)


def _normalise_openapi_path(path: str) -> str:
    """Collapse OpenAPI ``{foo}`` parameters to a placeholder ``{*}``."""
    return _OPENAPI_PARAM_RE.sub("{*}", path)


def _parse_flask_routes(source: str) -> set[tuple[str, str]]:
    """Return ``{(normalised_path, method_lower)}`` for every ``@app.*`` decorator."""
    out: set[tuple[str, str]] = set()
    for match in _DECORATOR_RE.finditer(source):
        method = match.group("method").lower()
        path = _normalise_flask_path(match.group("path"))
        if method == "route":
            methods_raw = match.group("methods") or ""
            extracted = re.findall(r"['\"]([A-Za-z]+)['\"]", methods_raw) or ["GET"]
            for m in extracted:
                out.add((path, m.lower()))
        else:
            out.add((path, method))
    for path, method in _DYNAMIC_ROUTES:
        out.add((_normalise_flask_path(path), method))
    return out


def _parse_openapi(spec: dict) -> set[tuple[str, str]]:
    """Return ``{(normalised_path, method_lower)}`` for every documented operation."""
    out: set[tuple[str, str]] = set()
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        normalised = _normalise_openapi_path(path)
        for method in _HTTP_METHODS:
            if method in item:
                out.add((normalised, method))
    return out


def main() -> int:
    if not WEBUI_PY.is_file():
        print(f"openapi-check: cannot find {WEBUI_PY}", file=sys.stderr)
        return 2
    if not OPENAPI_JSON.is_file():
        print(f"openapi-check: cannot find {OPENAPI_JSON}", file=sys.stderr)
        return 2

    flask_routes = _parse_flask_routes(WEBUI_PY.read_text(encoding="utf-8"))
    try:
        spec = json.loads(OPENAPI_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"openapi-check: openapi.json is not valid JSON: {exc}", file=sys.stderr)
        return 2
    openapi_routes = _parse_openapi(spec)

    missing_in_spec = sorted(flask_routes - openapi_routes)
    missing_in_code = sorted(openapi_routes - flask_routes)

    if not missing_in_spec and not missing_in_code:
        print(
            f"openapi-check: OK ({len(flask_routes)} routes, "
            f"{len(openapi_routes)} OpenAPI operations)"
        )
        return 0

    if missing_in_spec:
        print("openapi-check: routes registered in Flask but missing from openapi.json:")
        for path, method in missing_in_spec:
            print(f"  + {method.upper():<6} {path}")
    if missing_in_code:
        print("openapi-check: paths in openapi.json with no Flask route registered:")
        for path, method in missing_in_code:
            print(f"  - {method.upper():<6} {path}")
    print(
        "\nFix by registering the missing route(s) or updating qBitrr/openapi.json so "
        "the runtime contract and the published spec stay aligned."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
