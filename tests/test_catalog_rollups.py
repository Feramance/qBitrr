"""Golden-master tests for catalog_rollups helpers (Phase 4)."""

from __future__ import annotations

import unittest
from unittest import mock

from qBitrr.catalog_rollups import (
    _availability_counts,
    get_rollup_slice,
    get_sonarr_episode_instance_counts_total,
    get_sonarr_series_counts_total,
)


class TestAvailabilityCounts(unittest.TestCase):
    def test_missing_is_monitored_minus_available(self) -> None:
        self.assertEqual(
            _availability_counts(10, 4),
            {"available": 4, "monitored": 10, "missing": 6},
        )


class TestGetRollupSlice(unittest.TestCase):
    def test_reads_section_after_ensure(self) -> None:
        arr = mock.MagicMock()
        arr._webui_catalog_rollups = {
            "sonarr_episodes": {
                "counts": {"available": 1, "monitored": 2, "missing": 1},
                "total_series": 9,
            }
        }
        with mock.patch("qBitrr.catalog_rollups.ensure_arr_webui_rollups"):
            counts, total = get_rollup_slice(arr, "sonarr_episodes", total_key="total_series")
        self.assertEqual(total, 9)
        self.assertEqual(counts["missing"], 1)

    def test_sonarr_series_alias_matches_old_name(self) -> None:
        arr = mock.MagicMock()
        arr._webui_catalog_rollups = {
            "sonarr_episodes": {
                "counts": {"available": 0, "monitored": 0, "missing": 0},
                "total_series": 3,
            }
        }
        with mock.patch("qBitrr.catalog_rollups.ensure_arr_webui_rollups"):
            legacy = get_sonarr_episode_instance_counts_total(arr)
            renamed = get_sonarr_series_counts_total(arr)
        self.assertEqual(legacy, renamed)
