"""Feature detection for cross-branch unittest compatibility.

Tests that depend on refactor-only modules or known bug fixes should gate on these
flags so ``master`` runs skip cleanly while ``refactor/simplify-codebase`` executes
the full characterization suite.
"""

from __future__ import annotations

import importlib.util
import inspect


def _has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ModuleNotFoundError, AttributeError, ValueError):
        return False


HAS_DB_UPDATE_HANDLERS = _has_module("qBitrr.arss.db_update_handlers")
HAS_QUALITY_PROFILE_HELPERS = _has_module("qBitrr.quality_profile_helpers")
HAS_ARR_CLIENT = _has_module("qBitrr.arr_client")
HAS_QBIT_SEEDING_CONFIG = _has_module("qBitrr.qbit_seeding_config")
HAS_TORRENT_BATCH_MIXIN = _has_module("qBitrr.arss.torrent_batch_mixin")
HAS_ARR_SUBMODULE = _has_module("qBitrr.arss.arr")


def _has_merge_tracker_configs() -> bool:
    try:
        from qBitrr import arr_tracker_index as ati

        return hasattr(ati, "merge_tracker_configs")
    except Exception:
        return False


HAS_MERGE_TRACKER_CONFIGS = _has_merge_tracker_configs()


def _has_auto_update_platform_message_fix() -> bool:
    """Refactor fixes unsupported-platform error text (commit 9de1e0b1)."""
    try:
        from qBitrr import auto_update

        source = inspect.getsource(auto_update.get_binary_download_url)
    except Exception:
        return False
    return "matched = next" in source


HAS_AUTO_UPDATE_PLATFORM_FIX = _has_auto_update_platform_message_fix()


def _has_live_reload_getters() -> bool:
    """Phase-2 config getters extracted for live reload (refactor-only)."""
    try:
        from qBitrr import config as cfg

        return hasattr(cfg, "get_ping_urls_effective")
    except Exception:
        return False


HAS_LIVE_RELOAD_GETTERS = _has_live_reload_getters()


def _has_extended_config_getters() -> bool:
    """Free-space guard + qBit-disabled helpers present on both branches."""
    try:
        from qBitrr import config as cfg

        return hasattr(cfg, "get_free_space_guard_settings")
    except Exception:
        return False


HAS_EXTENDED_CONFIG_GETTERS = _has_extended_config_getters()


def _has_catalog_rollup_slice() -> bool:
    """Catalog rollup slice helpers added during refactor (Phase 4)."""
    try:
        from qBitrr import catalog_rollups as cr

        return hasattr(cr, "_availability_counts") and hasattr(cr, "get_rollup_slice")
    except Exception:
        return False


HAS_CATALOG_ROLLUP_SLICE = _has_catalog_rollup_slice()


def _has_webui_catalog_helpers() -> bool:
    """Catalog filter parsing and empty payloads extracted in refactor."""
    try:
        from qBitrr import webui

        return hasattr(webui, "empty_catalog_payload") and hasattr(webui, "parse_catalog_filters")
    except Exception:
        return False


HAS_WEBUI_CATALOG_HELPERS = _has_webui_catalog_helpers()


def _has_dual_route() -> bool:
    """``dual_route`` decorator introduced during WebUI route refactor."""
    try:
        from qBitrr import webui

        return hasattr(webui, "dual_route")
    except Exception:
        return False


HAS_DUAL_ROUTE = _has_dual_route()


def _has_parse_duration() -> bool:
    try:
        from qBitrr import duration_config as dc

        return hasattr(dc, "parse_duration")
    except Exception:
        return False


HAS_PARSE_DURATION = _has_parse_duration()


def _has_arr_section_helpers() -> bool:
    try:
        from qBitrr import gen_config as gc

        return hasattr(gc, "ARR_SECTION_PREFIXES")
    except Exception:
        return False


HAS_ARR_SECTION_HELPERS = _has_arr_section_helpers()


def torrent_batch_with_retry_target() -> str:
    if HAS_TORRENT_BATCH_MIXIN:
        return "qBitrr.arss.torrent_batch_mixin.with_retry"
    return "qBitrr.arss.with_retry"


def torrent_batch_execute_command_target() -> str:
    if HAS_TORRENT_BATCH_MIXIN:
        return "qBitrr.arss.torrent_batch_mixin.execute_command"
    return "qBitrr.arss.execute_command"


def arss_auto_pause_resume_target() -> str:
    if HAS_ARR_SUBMODULE:
        return "qBitrr.arss.arr.AUTO_PAUSE_RESUME"
    return "qBitrr.arss.AUTO_PAUSE_RESUME"


def arss_execute_command_target() -> str:
    if HAS_ARR_SUBMODULE:
        return "qBitrr.arss.arr.execute_command"
    return "qBitrr.arss.execute_command"


def arss_periodic_command_uses_execute_command() -> bool:
    return HAS_ARR_SUBMODULE


def arss_with_retry_target() -> str:
    if HAS_ARR_SUBMODULE:
        return "qBitrr.arss.arr.with_retry"
    return "qBitrr.arss.with_retry"


def periodic_command_fn_target() -> str:
    """Patch target for Arr periodic/import command dispatch."""
    if HAS_ARR_SUBMODULE:
        return "qBitrr.arss.arr.execute_command"
    return "qBitrr.arss.execute_command"
