# Backend unittest suite

Run the full suite from the repository root:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

## Branch compatibility

Tests are written to pass on **`master`** and **`refactor/simplify-codebase`**. Refactor-only
modules and fixed-bug characterization tests skip automatically via
[`tests/support/branch_compat.py`](support/branch_compat.py).

| Flag | Meaning | Skipped on `master` |
|------|---------|---------------------|
| `HAS_ARR_CLIENT` | `qBitrr.arr_client` (pyarr v6 migration) | `test_pyarr_v6_migration.py` (entire module) |
| `HAS_DB_UPDATE_HANDLERS` | `qBitrr.arss.db_update_handlers` split | `test_db_update_single_series.py` (entire module) |
| `HAS_QUALITY_PROFILE_HELPERS` | `qBitrr.quality_profile_helpers` | `test_quality_profile_helpers.py` (entire module) |
| `HAS_QBIT_SEEDING_CONFIG` | `qBitrr.qbit_seeding_config` | `TestLoadQbitSeedingConfig` in `test_phase1_helpers.py` |
| `HAS_PARSE_DURATION` | unified `parse_duration()` helper | `TestParseDurationGoldenMaster` in `test_phase1_helpers.py` |
| `HAS_ARR_SECTION_HELPERS` | `iter_arr_sections` / `ARR_SECTION_PREFIXES` | `TestIterArrSections` in `test_phase1_helpers.py` |
| `HAS_LIVE_RELOAD_GETTERS` | `get_ping_urls_effective` and related getters | `TestConfigLiveReloadGoldenMaster`, `TestEnviroConfigHarness` in `test_config_live_reload.py` |
| `HAS_CATALOG_ROLLUP_SLICE` | `_availability_counts`, `get_rollup_slice` | First two classes in `test_catalog_rollups.py` |
| `HAS_WEBUI_CATALOG_HELPERS` | `empty_catalog_payload`, `parse_catalog_filters`, `resolve_arr_handler` | Catalog helper classes in `test_webui_routes.py` |
| `HAS_DUAL_ROUTE` | `@dual_route` decorator | `TestDualRouteRegistration`, `TestDualRoute` in `test_webui_routes.py` |
| `HAS_MERGE_TRACKER_CONFIGS` | `merge_tracker_configs` | `TestMergeTrackerConfigsCombinations` in `test_arr_tracker_index.py` |
| `HAS_AUTO_UPDATE_PLATFORM_FIX` | Unsupported-platform error names first pattern (9de1e0b1) | Platform-message tests in `test_auto_update.py`, `test_phase1_helpers.py` |

Tests without skip markers are expected to pass on both branches (e.g. `test_arr_tracker_index.py`,
`test_category_paths.py`, `test_config_version.py`, `test_config_migrations.py`,
`test_main_spawn_cleanup.py`, route-pair contracts in `test_webui_routes.py`).

Patch-target helpers (`torrent_batch_with_retry_target`, `arss_with_retry_target`, etc.) branch
internally so `test_arss_multi_instance.py` works against monolithic `arss.py` on `master` and the
split `qBitrr.arss` package on refactor.

## Adding refactor-only tests

1. Add a detection helper to `branch_compat.py` if module import alone is insufficient.
2. Gate with `@unittest.skipUnless(FLAG, "reason")` on the class or use conditional imports
   when the module would fail to import on `master`.
3. Document the flag in the table above.
