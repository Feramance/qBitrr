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


class TestRollupCacheAndRefresh(unittest.TestCase):
    def test_ensure_arr_webui_rollups_uses_ttl_cache(self) -> None:
        from qBitrr import catalog_rollups as cr

        arr = mock.MagicMock()
        arr.db = object()
        arr._name = "Sonarr"
        arr.type = "sonarr"
        arr._webui_catalog_rollups = {"sonarr_episodes": {"counts": {}, "total_series": 1}}
        with (
            mock.patch.object(cr, "refresh_arr_webui_rollups") as refresh,
            mock.patch.object(cr, "_rollup_cache", {}),
            mock.patch.object(cr, "time") as time_mock,
        ):
            time_mock.monotonic.return_value = 100.0
            cr._rollup_cache[(id(arr), "Sonarr")] = (99.0, {"cached": True})
            cr.ensure_arr_webui_rollups(arr)
            refresh.assert_not_called()
            self.assertEqual(arr._webui_catalog_rollups, {"cached": True})

    def test_refresh_arr_webui_rollups_clears_unknown_arr_type(self) -> None:
        from qBitrr.catalog_rollups import refresh_arr_webui_rollups

        arr = mock.MagicMock()
        arr.db = object()
        arr.type = "unknown"
        refresh_arr_webui_rollups(arr)
        self.assertEqual(arr._webui_catalog_rollups, {})

    def test_get_radarr_counts_total_uses_zero_counts_fallback(self) -> None:
        from qBitrr.catalog_rollups import get_radarr_counts_total

        arr = mock.MagicMock()
        arr._webui_catalog_rollups = {}
        with mock.patch("qBitrr.catalog_rollups.ensure_arr_webui_rollups"):
            counts, total = get_radarr_counts_total(arr)
        self.assertEqual(counts["requests"], 0)
        self.assertEqual(total, 0)

    def test_get_lidarr_album_and_track_rollups_reads_both_sections(self) -> None:
        from qBitrr.catalog_rollups import get_lidarr_album_and_track_rollups

        arr = mock.MagicMock()
        arr._webui_catalog_rollups = {
            "lidarr_albums": {
                "counts": {"available": 2, "monitored": 3, "missing": 1},
                "total": 4,
            },
            "lidarr_tracks": {
                "counts": {"available": 10, "monitored": 12, "missing": 2},
                "total": 50,
            },
        }
        with mock.patch("qBitrr.catalog_rollups.ensure_arr_webui_rollups"):
            (album_counts, album_total), (track_counts, track_total) = (
                get_lidarr_album_and_track_rollups(arr)
            )
        self.assertEqual(album_total, 4)
        self.assertEqual(track_total, 50)
        self.assertEqual(album_counts["missing"], 1)
        self.assertEqual(track_counts["available"], 10)

    def test_get_readarr_book_counts_total_reads_section(self) -> None:
        from qBitrr.catalog_rollups import get_readarr_book_counts_total

        arr = mock.MagicMock()
        arr._webui_catalog_rollups = {
            "readarr_books": {
                "counts": {"available": 5, "monitored": 8, "missing": 3},
                "total": 12,
            }
        }
        with mock.patch("qBitrr.catalog_rollups.ensure_arr_webui_rollups"):
            counts, total = get_readarr_book_counts_total(arr)
        self.assertEqual(total, 12)
        self.assertEqual(counts["missing"], 3)
        self.assertEqual(counts["available"], 5)


class TestRefreshRollupsAfterDbUpdate(unittest.TestCase):
    def test_noop_without_db_or_entry(self) -> None:
        from qBitrr.catalog_rollups import refresh_rollups_after_db_update

        arr = mock.MagicMock()
        arr.db = None
        refresh_rollups_after_db_update(arr, {"id": 1}, series=False, artist=False)

    def test_sonarr_series_update_calls_season_totals(self) -> None:
        from qBitrr.catalog_rollups import refresh_rollups_after_db_update

        arr = mock.MagicMock()
        arr.db = object()
        arr.type = "sonarr"
        arr.model_file = mock.MagicMock()
        arr.series_file_model = mock.MagicMock()
        with mock.patch("qBitrr.catalog_rollups.update_series_season_episode_totals") as update:
            refresh_rollups_after_db_update(arr, {"id": 9}, series=True, artist=False)
        update.assert_called_once_with(arr, 9, arr.model_file, arr.series_file_model)

    def test_lidarr_album_update_chains_artist_totals(self) -> None:
        from qBitrr.catalog_rollups import refresh_rollups_after_db_update

        arr = mock.MagicMock()
        arr.db = object()
        arr.type = "lidarr"
        arr.model_file = mock.MagicMock()
        arr.track_file_model = mock.MagicMock()
        arr.artists_file_model = mock.MagicMock()
        album_row = mock.MagicMock()
        album_row.ArtistId = 3
        with (
            mock.patch(
                "qBitrr.catalog_rollups.update_album_total_tracks",
                return_value=album_row,
            ) as album_update,
            mock.patch("qBitrr.catalog_rollups.update_artist_album_track_totals") as artist_update,
        ):
            refresh_rollups_after_db_update(arr, {"id": 7}, series=False, artist=False)
        album_update.assert_called_once()
        artist_update.assert_called_once_with(
            arr, 3, arr.model_file, arr.track_file_model, arr.artists_file_model
        )

    def test_readarr_book_update_chains_author_totals(self) -> None:
        from qBitrr.catalog_rollups import refresh_rollups_after_db_update

        arr = mock.MagicMock()
        arr.db = object()
        arr.type = "readarr"
        arr.model_file = mock.MagicMock()
        arr.artists_file_model = mock.MagicMock()
        with mock.patch("qBitrr.catalog_rollups.update_author_book_count") as author_update:
            refresh_rollups_after_db_update(
                arr, {"id": 7, "authorId": 4}, series=False, artist=False
            )
        author_update.assert_called_once_with(arr, 4, arr.model_file, arr.artists_file_model)
