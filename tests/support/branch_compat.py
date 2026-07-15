"""Feature detection for cross-branch unittest compatibility.

Tests that depend on refactor-only modules or known bug fixes should gate on these
flags so ``master`` runs skip cleanly while ``refactor/simplify-codebase`` executes
the full characterization suite.
"""

from __future__ import annotations

import importlib.util
import inspect


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


HAS_DB_UPDATE_HANDLERS = _has_module("qBitrr.arss.db_update_handlers")
HAS_QUALITY_PROFILE_HELPERS = _has_module("qBitrr.quality_profile_helpers")
HAS_ARR_CLIENT = _has_module("qBitrr.arr_client")
HAS_QBIT_SEEDING_CONFIG = _has_module("qBitrr.qbit_seeding_config")


def _has_auto_update_platform_message_fix() -> bool:
    """Refactor fixes unsupported-platform error text (commit 9de1e0b1)."""
    try:
        from qBitrr import auto_update

        source = inspect.getsource(auto_update.get_binary_download_url)
    except Exception:
        return False
    return "matched = next" in source


HAS_AUTO_UPDATE_PLATFORM_FIX = _has_auto_update_platform_message_fix()


def _has_extended_config_getters() -> bool:
    try:
        from qBitrr import config as cfg

        return hasattr(cfg, "get_effective_qbit_disabled")
    except Exception:
        return False


HAS_EXTENDED_CONFIG_GETTERS = _has_extended_config_getters()
