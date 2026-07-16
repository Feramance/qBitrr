"""Golden-master and regression tests for db_update_single_series split."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from qBitrr.arss import Arr
from qBitrr.arss.db_update_handlers import db_update_single_series
from qBitrr.quality_profile_helpers import (
    compute_search_reason,
    plan_temp_profile_switch,
    should_mark_searched,
)


def _search_enabled_arr(**overrides) -> Arr:
    arr = Arr.__new__(Arr)
    arr._name = overrides.get("_name", "TestArr")
    arr.type = overrides.get("type", "sonarr")
    arr.search_missing = overrides.get("search_missing", True)
    arr.do_upgrade_search = overrides.get("do_upgrade_search", False)
    arr.quality_unmet_search = overrides.get("quality_unmet_search", False)
    arr.custom_format_unmet_search = overrides.get("custom_format_unmet_search", False)
    arr.search_unmonitored = overrides.get("search_unmonitored", False)
    arr.search_specials = overrides.get("search_specials", False)
    arr.use_temp_for_missing = overrides.get("use_temp_for_missing", False)
    arr.keep_temp_profile = overrides.get("keep_temp_profile", False)
    arr.series_search = overrides.get("series_search", False)
    arr.main_quality_profile_ids = overrides.get("main_quality_profile_ids", {2: 1})
    arr.temp_quality_profile_ids = overrides.get("temp_quality_profile_ids", {1: 2})
    arr.profile_switch_retry_attempts = 3
    arr._quality_profile_cache = {}
    arr._invalid_quality_profiles = set()
    arr.logger = MagicMock()
    arr.client = MagicMock()
    arr.model_file = MagicMock()
    arr.model_queue = MagicMock()
    arr.series_file_model = MagicMock()
    arr.artists_file_model = MagicMock()
    arr.track_file_model = None
    arr.minimum_availability_check = MagicMock(return_value=True)
    arr._retry_profile_switch_update = MagicMock(return_value=True)
    return arr


class TestQualityProfileHelpers(unittest.TestCase):
    def test_should_mark_searched_requires_content(self) -> None:
        self.assertFalse(
            should_mark_searched(
                has_content=False,
                quality_unmet_search=True,
                quality_unmet=True,
                custom_format_unmet_search=False,
                custom_format=0,
                min_custom_format=0,
            )
        )

    def test_plan_temp_profile_switch_conditional(self) -> None:
        data, ts, orig, current = plan_temp_profile_switch(
            searched=False,
            has_file=False,
            quality_profile_id=1,
            main_quality_profile_ids={2: 1},
            temp_quality_profile_ids={1: 2},
            keep_temp_profile=False,
        )
        self.assertEqual(data, {"qualityProfileId": 2})
        self.assertIsNotNone(ts)
        self.assertEqual(orig, 1)
        self.assertEqual(current, 2)

    def test_compute_search_reason_missing(self) -> None:
        self.assertEqual(
            compute_search_reason(
                has_content=False,
                quality_unmet_search=True,
                quality_unmet=True,
                custom_format_unmet_search=False,
                custom_format_met=True,
                do_upgrade_search=False,
                searched=False,
            ),
            "Missing",
        )


class TestArrMixinInheritance(unittest.TestCase):
    def test_arr_inherits_torrent_mixins(self) -> None:
        self.assertTrue(hasattr(Arr, "_process_paused"))
        self.assertTrue(hasattr(Arr, "_process_single_torrent"))
        self.assertTrue(hasattr(Arr, "is_alive"))
        self.assertTrue(hasattr(Arr, "is_ignored_state"))


class TestRadarrMinimumAvailabilityPreserved(unittest.TestCase):
    """Inconsistency #1: Radarr-only minimum_availability_check gate."""

    def test_skips_movie_when_minimum_availability_fails(self) -> None:
        arr = _search_enabled_arr(type="radarr")
        arr.minimum_availability_check.return_value = False
        arr.model_file.get_or_none.return_value = None
        db_update_single_series(arr, db_entry={"id": 1, "title": "Movie", "monitored": True})
        arr.client.quality_profile.get.assert_not_called()


class TestSonarrSeriesConditionalProfileUpdate(unittest.TestCase):
    """Inconsistency #2: series-level PUT only when profile changes."""

    def test_no_series_update_when_profile_unchanged(self) -> None:
        arr = _search_enabled_arr(type="sonarr", use_temp_for_missing=True)
        arr.series_file_model.get_or_none.return_value = SimpleNamespace(MinCustomFormatScore=10)
        arr.client.series.get.return_value = {
            "title": "Show",
            "qualityProfileId": 1,
            "seasons": [
                {
                    "seasonNumber": 1,
                    "statistics": {
                        "episodeCount": 1,
                        "totalEpisodeCount": 1,
                        "episodeFileCount": 0,
                    },
                }
            ],
        }
        db_entry = {"id": 5, "title": "Show", "monitored": True, "qualityProfileId": 99}
        db_update_single_series(arr, db_entry=db_entry, series=True)
        arr._retry_profile_switch_update.assert_not_called()


class TestSonarrEpisodeProfileTrackingFixes(unittest.TestCase):
    """Inconsistencies #3 and #5."""

    def test_no_timestamp_when_main_mapping_missing(self) -> None:
        arr = _search_enabled_arr(type="sonarr", use_temp_for_missing=True)
        arr.main_quality_profile_ids = {}
        arr.model_file.get_or_none.return_value = SimpleNamespace(
            MinCustomFormatScore=0, CustomFormatScore=0, EpisodeFileId=99
        )
        arr.client.episode.get.return_value = {
            "id": 10,
            "seriesId": 1,
            "seasonNumber": 1,
            "episodeNumber": 1,
            "title": "Pilot",
            "airDateUtc": "2020-01-01T00:00:00Z",
            "episodeFileId": 99,
            "monitored": True,
            "hasFile": True,
            "series": {"title": "Show", "qualityProfileId": 99},
            "episodeFile": {"id": 99, "qualityCutoffNotMet": False},
        }
        arr.client.quality_profile.get.return_value = {"minFormatScore": 0}
        arr.model_file.insert.return_value.on_conflict.return_value.execute = MagicMock()
        db_update_single_series(
            arr,
            db_entry={"id": 10, "title": "Pilot", "hasFile": True, "qualityProfileId": 1},
            series=False,
        )
        conflict_update = arr.model_file.insert.return_value.on_conflict.call_args.kwargs["update"]
        self.assertNotIn(arr.model_file.LastProfileSwitchTime, conflict_update)

    def test_temp_switch_uses_series_profile_not_db_entry(self) -> None:
        arr = _search_enabled_arr(type="sonarr", use_temp_for_missing=True)
        arr.model_file.get_or_none.return_value = None
        arr._retry_profile_switch_update = MagicMock(side_effect=lambda fn, kind: fn())
        arr.client.episode.get.return_value = {
            "id": 10,
            "seriesId": 1,
            "seasonNumber": 1,
            "episodeNumber": 1,
            "title": "Pilot",
            "airDateUtc": "2020-01-01T00:00:00Z",
            "episodeFileId": 0,
            "monitored": True,
            "hasFile": False,
            "series": {"title": "Show", "qualityProfileId": 1},
        }
        arr.client.quality_profile.get.return_value = {"minFormatScore": 0}
        arr.model_file.insert.return_value.on_conflict.return_value.execute = MagicMock()
        db_update_single_series(
            arr,
            db_entry={"id": 10, "title": "Pilot", "hasFile": False, "qualityProfileId": 999},
            series=False,
        )
        arr._retry_profile_switch_update.assert_called_once()
        update_call = arr.client.episode.update.call_args
        self.assertEqual(update_call.kwargs["data"], {"qualityProfileId": 2})


class TestRadarrMovieConditionalProfileUpdate(unittest.TestCase):
    """Inconsistency #2 for Radarr movies."""

    def test_no_movie_update_when_profile_unchanged(self) -> None:
        arr = _search_enabled_arr(type="radarr", use_temp_for_missing=True)
        arr.model_file.get_or_none.return_value = SimpleNamespace(
            MinCustomFormatScore=10, MovieFileId=0, CustomFormatScore=0
        )
        arr.client.quality_profile.get.return_value = {"minFormatScore": 10}
        db_entry = {
            "id": 1,
            "title": "Movie",
            "monitored": True,
            "hasFile": False,
            "qualityProfileId": 99,
            "tmdbId": 1,
            "year": 2020,
            "movieFileId": 0,
        }
        db_update_single_series(arr, db_entry=db_entry)
        arr._retry_profile_switch_update.assert_not_called()


class TestLidarrArtistProfileTracking(unittest.TestCase):
    """Inconsistencies #4, #7, #8."""

    def test_searched_semantics_album_count_and_size(self) -> None:
        arr = _search_enabled_arr(type="lidarr")
        arr.artists_file_model.get_or_none.return_value = SimpleNamespace(MinCustomFormatScore=0)
        arr.client.artist.get.return_value = {
            "artistName": "Artist",
            "qualityProfileId": 1,
            "statistics": {"albumCount": 2, "sizeOnDisk": 100},
        }
        arr.client.quality_profile.get.return_value = {"minFormatScore": 0}
        arr.artists_file_model.insert.return_value.on_conflict.return_value.execute = MagicMock()
        db_update_single_series(
            arr,
            db_entry={"id": 1, "monitored": True, "artistName": "Artist"},
            artist=True,
        )
        insert_kwargs = arr.artists_file_model.insert.call_args.kwargs
        self.assertTrue(insert_kwargs["Searched"])

    def test_artist_temp_downgrade_tracks_profile_fields(self) -> None:
        arr = _search_enabled_arr(type="lidarr", use_temp_for_missing=True)
        arr.artists_file_model.get_or_none.return_value = SimpleNamespace(MinCustomFormatScore=0)
        arr.client.artist.get.return_value = {
            "artistName": "Artist",
            "qualityProfileId": 1,
            "statistics": {"albumCount": 0, "sizeOnDisk": 0},
        }
        arr.client.quality_profile.get.return_value = {"minFormatScore": 0}
        arr.artists_file_model.insert.return_value.on_conflict.return_value.execute = MagicMock()
        db_update_single_series(
            arr,
            db_entry={"id": 1, "monitored": True, "artistName": "Artist"},
            artist=True,
        )
        arr.artists_file_model.insert.call_args.kwargs
        conflict_update = arr.artists_file_model.insert.return_value.on_conflict.call_args.kwargs[
            "update"
        ]
        self.assertIn(arr.artists_file_model.LastProfileSwitchTime, conflict_update)
        self.assertEqual(conflict_update[arr.artists_file_model.OriginalProfileId], 1)
        self.assertEqual(conflict_update[arr.artists_file_model.CurrentProfileId], 2)

    def test_upgrade_log_uses_distinct_profile_ids(self) -> None:
        arr = _search_enabled_arr(type="lidarr", use_temp_for_missing=True)
        arr.artists_file_model.get_or_none.return_value = SimpleNamespace(MinCustomFormatScore=0)
        arr.client.artist.get.return_value = {
            "artistName": "Artist",
            "qualityProfileId": 2,
            "statistics": {"albumCount": 1, "sizeOnDisk": 100},
        }
        arr.client.quality_profile.get.return_value = {"minFormatScore": 0}
        arr.artists_file_model.insert.return_value.on_conflict.return_value.execute = MagicMock()
        db_update_single_series(
            arr,
            db_entry={"id": 1, "monitored": True, "artistName": "Artist"},
            artist=True,
        )
        debug_calls = [str(c) for c in arr.logger.debug.call_args_list]
        upgrade_logs = [c for c in debug_calls if "Upgrading artist" in c]
        self.assertTrue(upgrade_logs)
        self.assertIn("2", upgrade_logs[0])
        self.assertIn("1", upgrade_logs[0])


class TestLidarrAlbumCustomFormatPreserved(unittest.TestCase):
    """Inconsistency #9: Lidarr albums hardcode custom format score to 0."""

    def test_album_custom_format_score_zero(self) -> None:
        arr = _search_enabled_arr(type="lidarr")
        arr.model_file.get_or_none.return_value = None
        arr.client.artist.get.return_value = {"qualityProfileId": 1}
        arr.client.quality_profile.get.return_value = {"minFormatScore": 5}
        arr.client.track.get.return_value = []
        arr.model_file.insert.return_value.on_conflict.return_value.execute = MagicMock()
        db_entry = {
            "id": 3,
            "title": "Album",
            "monitored": True,
            "artistId": 1,
            "profileId": 1,
            "statistics": {"percentOfTracks": 100},
            "artist": {"artistName": "Artist"},
        }
        db_update_single_series(arr, db_entry=db_entry)
        insert_kwargs = arr.model_file.insert.call_args.kwargs
        self.assertEqual(insert_kwargs["CustomFormatScore"], 0)


class TestJsonDecodeErrorMessagingPreserved(unittest.TestCase):
    """Inconsistency #10: type-specific JSONDecodeError log messages."""

    def test_sonarr_episode_json_error_message(self) -> None:
        arr = _search_enabled_arr(type="sonarr")
        arr.model_file.get_or_none.return_value = None
        from ujson import JSONDecodeError

        arr.client.episode.get.side_effect = JSONDecodeError("bad")
        db_update_single_series(
            arr,
            db_entry={"id": 1, "title": "Ep"},
            series=False,
        )
        arr.logger.warning.assert_called_with("Error getting episode info: [%s][%s]", 1, "Ep")

    def test_lidarr_artist_json_error_has_no_type_specific_message(self) -> None:
        """Lidarr has no Sonarr/Radarr-style JSONDecodeError warning branch."""
        arr = _search_enabled_arr(type="lidarr")
        arr.artists_file_model.get_or_none.return_value = None
        from ujson import JSONDecodeError

        arr.client.artist.get.side_effect = JSONDecodeError("bad")
        db_update_single_series(
            arr,
            db_entry={"id": 1, "monitored": True, "artistName": "Artist"},
            artist=True,
        )
        arr.logger.warning.assert_not_called()
        arr.logger.error.assert_not_called()


class TestQualityUnmetNestedKeyGuardPreserved(unittest.TestCase):
    """Inconsistency #6: episodeFile presence check without nested-key guard."""

    def test_sonarr_episode_swallows_malformed_episode_file(self) -> None:
        """Malformed episodeFile is handled by the generic exception handler (not re-raised)."""
        arr = _search_enabled_arr(type="sonarr", quality_unmet_search=True)
        arr.model_file.get_or_none.return_value = SimpleNamespace(
            MinCustomFormatScore=0, CustomFormatScore=0, EpisodeFileId=99
        )
        arr.client.episode.get.return_value = {
            "id": 10,
            "seriesId": 1,
            "seasonNumber": 1,
            "episodeNumber": 1,
            "title": "Pilot",
            "airDateUtc": "2020-01-01T00:00:00Z",
            "episodeFileId": 99,
            "monitored": True,
            "hasFile": True,
            "series": {"title": "Show", "qualityProfileId": 1},
            "episodeFile": None,
        }
        arr.client.quality_profile.get.return_value = {"minFormatScore": 0}
        db_update_single_series(
            arr,
            db_entry={"id": 10, "title": "Pilot", "hasFile": True},
            series=False,
        )
        arr.logger.error.assert_called_once()


class TestDbUpdateEpisodeRetry(unittest.TestCase):
    """Inconsistency #11: with_retry on Sonarr episode list fetch."""

    def test_db_update_wraps_episode_get_with_retry(self) -> None:
        from qBitrr.utils import with_retry as real_with_retry

        arr = _search_enabled_arr(type="sonarr")
        arr.db_update_processed = False
        arr.db_update_todays_releases = MagicMock()
        arr._record_search_activity = MagicMock()
        arr._webui_db_loaded = True
        arr.client.series.get.return_value = [{"id": 1, "monitored": True}]
        arr.client.episode.get.return_value = []
        arr.series_file_model.insert.return_value.on_conflict.return_value.execute = MagicMock()
        with patch("qBitrr.arss.arr.with_retry", side_effect=real_with_retry) as mock_retry:
            with patch("qBitrr.arss.arr.fetch_search_activities", return_value={}):
                with patch(
                    "qBitrr.arss.db_update_handlers.refresh_rollups_after_db_update",
                    return_value=None,
                ):
                    arr.db_update()
        self.assertGreaterEqual(mock_retry.call_count, 2)
        arr.client.episode.get.assert_called()


class TestDbUpdateRadarrMovieProfileSwitch(unittest.TestCase):
    """Radarr movie temp-profile downgrade when missing."""

    def test_movie_temp_switch_when_missing(self) -> None:
        arr = _search_enabled_arr(type="radarr", use_temp_for_missing=True)
        arr.model_file.get_or_none.return_value = None
        arr._retry_profile_switch_update = MagicMock(side_effect=lambda fn, kind: fn())
        arr.client.quality_profile.get.return_value = {"minFormatScore": 0}
        arr.model_file.insert.return_value.on_conflict.return_value.execute = MagicMock()
        db_entry = {
            "id": 1,
            "title": "Movie",
            "monitored": True,
            "hasFile": False,
            "qualityProfileId": 1,
            "tmdbId": 1,
            "year": 2020,
            "movieFileId": 0,
        }
        db_update_single_series(arr, db_entry=db_entry)
        arr._retry_profile_switch_update.assert_called_once()
        self.assertEqual(
            arr.client.movie.update.call_args.kwargs["data"]["qualityProfileId"],
            2,
        )


class TestDbUpdateUnmonitoredSkip(unittest.TestCase):
    def test_skips_unmonitored_sonarr_series(self) -> None:
        arr = _search_enabled_arr(type="sonarr")
        db_update_single_series(
            arr,
            db_entry={"id": 1, "title": "Show", "monitored": False},
            series=True,
        )
        arr.client.series.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
