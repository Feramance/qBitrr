"""Config schema generation, validation, and migrations."""

from __future__ import annotations

from qBitrr.gen_config.config_class import MyConfig
from qBitrr.gen_config.fields import (
    QBIT_FIELDS,
    SETTINGS_FIELDS,
    WEBUI_FIELDS,
    build_config_schema,
)
from qBitrr.gen_config.migrations import (
    _migrate_animarr_sections,
    _migrate_hnr_settings,
    _migrate_hnr_single_key,
    _migrate_process_restart_settings,
    _migrate_qbit_category_settings,
    _migrate_qbit_subcategory_match,
    _migrate_quality_profile_mappings,
    _migrate_webui_config,
    _write_config_file,
    apply_config_migrations,
)
from qBitrr.gen_config.sections import ARR_SECTION_PREFIXES, generate_doc, iter_arr_sections
from qBitrr.gen_config.validate import (
    _normalize_theme_value,
    _normalize_url_base_value,
    _normalize_view_density_value,
    _validate_and_fill_config,
)

__all__ = [
    "ARR_SECTION_PREFIXES",
    "MyConfig",
    "QBIT_FIELDS",
    "SETTINGS_FIELDS",
    "WEBUI_FIELDS",
    "_migrate_animarr_sections",
    "_migrate_hnr_settings",
    "_migrate_hnr_single_key",
    "_migrate_process_restart_settings",
    "_migrate_qbit_category_settings",
    "_migrate_qbit_subcategory_match",
    "_migrate_quality_profile_mappings",
    "_migrate_webui_config",
    "_normalize_theme_value",
    "_normalize_url_base_value",
    "_normalize_view_density_value",
    "_validate_and_fill_config",
    "_write_config_file",
    "apply_config_migrations",
    "build_config_schema",
    "generate_doc",
    "iter_arr_sections",
]
