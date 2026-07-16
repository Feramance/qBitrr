"""qBitrr WebUI package.

Public imports and test patch targets remain on ``qBitrr.webui`` for compatibility.
"""

from __future__ import annotations

import time

from qBitrr.config import CONFIG
from qBitrr.logger import run_logs
from qBitrr.search_activity_store import fetch_search_activities
from qBitrr.webui.app import WebUI
from qBitrr.webui.catalog.common import (
    empty_catalog_payload,
    parse_catalog_filters,
    resolve_arr_handler,
)
from qBitrr.webui.config_toml import (
    REDACTED_PLACEHOLDER,
    _strip_sensitive_keys,
    _toml_to_jsonable,
)
from qBitrr.webui.routing import dual_route
from qBitrr.webui.urlbase import UrlBaseMiddleware, configured_url_base

__all__ = [
    "CONFIG",
    "REDACTED_PLACEHOLDER",
    "UrlBaseMiddleware",
    "WebUI",
    "_strip_sensitive_keys",
    "_toml_to_jsonable",
    "configured_url_base",
    "dual_route",
    "empty_catalog_payload",
    "fetch_search_activities",
    "parse_catalog_filters",
    "resolve_arr_handler",
    "run_logs",
    "time",
]
