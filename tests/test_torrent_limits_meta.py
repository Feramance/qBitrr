"""Regression tests for tracker vs SeedingMode limit merge (#547)."""

from __future__ import annotations

import logging
import unittest
from types import SimpleNamespace
from unittest import mock

from qbittorrentapi import TorrentStates

from qBitrr.arss.torrent_limits import TorrentLimits


class _LimitsHarness(TorrentLimits):
    """Minimal TorrentLimits host with stubbed tracker resolution."""

    def __init__(
        self,
        *,
        tracker: dict | None,
        max_upload_ratio: float | int = -1,
        max_seeding_time: float | int | str = -1,
        maximum_eta: float | int | str = 86400,
        remove_torrent: int = 2,
    ) -> None:
        self.seeding_mode_global_max_upload_ratio = max_upload_ratio
        self.seeding_mode_global_max_seeding_time = max_seeding_time
        self.seeding_mode_global_download_limit = -1
        self.seeding_mode_global_upload_limit = -1
        self.maximum_eta = maximum_eta
        self.seeding_mode_global_remove_torrent = remove_torrent
        self._warned_no_seeding_limits = False
        self.logger = logging.getLogger("qBitrr.test.torrent_limits")
        self._tracker = tracker or {}
        self.monitored_trackers: list[dict] = []

    def _get_torrent_important_trackers(self, torrent):  # noqa: ARG002
        return set(), {"https://tracker.example/announce"}

    def _get_most_important_tracker_and_tags(self, monitored_trackers, removed):  # noqa: ARG002
        return self._tracker, set()


def _torrent(**kwargs):
    defaults = {
        "name": "Test",
        "hash": "abc",
        "super_seeding": False,
        "ratio_limit": -1,
        "seeding_time_limit": -1,
        "dl_limit": -1,
        "up_limit": -1,
        "ratio": 0.0,
        "seeding_time": 0,
        "progress": 1.0,
        "last_activity": 0,
        "state_enum": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestPreferLimitMerge(unittest.TestCase):
    def test_parent_limit_survives_tracker_minus_one(self) -> None:
        harness = _LimitsHarness(
            tracker={"MaxSeedingTime": -1, "MaxUploadRatio": -1, "MaximumETA": -1},
            max_seeding_time=1209600,
            max_upload_ratio=2.0,
            maximum_eta=86400,
        )
        settings, _ = harness._get_torrent_limit_meta(_torrent())
        self.assertEqual(settings["seeding_time_limit"], 1209600)
        self.assertEqual(settings["ratio_limit"], 2.0)
        self.assertEqual(settings["max_eta"], 86400)

    def test_tracker_duration_string_overrides_parent_unset(self) -> None:
        harness = _LimitsHarness(
            tracker={"MaxSeedingTime": "2w", "MaximumETA": "2h"},
            max_seeding_time=-1,
            maximum_eta=-1,
        )
        settings, _ = harness._get_torrent_limit_meta(_torrent())
        self.assertEqual(settings["seeding_time_limit"], 1209600)
        self.assertEqual(settings["max_eta"], 7200)

    def test_tracker_int_overrides_parent_limit(self) -> None:
        harness = _LimitsHarness(
            tracker={"MaxSeedingTime": 86400, "MaxUploadRatio": 1.5},
            max_seeding_time=1209600,
            max_upload_ratio=2.0,
        )
        settings, _ = harness._get_torrent_limit_meta(_torrent())
        self.assertEqual(settings["seeding_time_limit"], 86400)
        self.assertEqual(settings["ratio_limit"], 1.5)

    def test_both_unset_yields_unlimited_sentinel(self) -> None:
        harness = _LimitsHarness(
            tracker={"MaxSeedingTime": -1, "MaxUploadRatio": -1, "MaximumETA": -1},
            max_seeding_time=-1,
            max_upload_ratio=-1,
            maximum_eta=-1,
        )
        settings, _ = harness._get_torrent_limit_meta(_torrent())
        self.assertEqual(settings["seeding_time_limit"], -5)
        self.assertEqual(settings["ratio_limit"], -5)
        self.assertEqual(settings["max_eta"], -1)

    def test_missing_tracker_keys_use_parent(self) -> None:
        harness = _LimitsHarness(
            tracker={"Name": "OnlyName"},
            max_seeding_time=1209600,
            max_upload_ratio=2.0,
            maximum_eta=3600,
        )
        settings, _ = harness._get_torrent_limit_meta(_torrent())
        self.assertEqual(settings["seeding_time_limit"], 1209600)
        self.assertEqual(settings["ratio_limit"], 2.0)
        self.assertEqual(settings["max_eta"], 3600)

    def test_remove_torrent_mode_2_does_not_warn_when_time_inherited(self) -> None:
        harness = _LimitsHarness(
            tracker={"MaxSeedingTime": -1, "MaxUploadRatio": -1},
            max_seeding_time=1209600,
            max_upload_ratio=-1,
            remove_torrent=2,
        )
        settings, _ = harness._get_torrent_limit_meta(_torrent())
        torrent = _torrent(seeding_time=0, ratio=0.0)
        with mock.patch.object(harness.logger, "warning") as warn:
            result = harness.torrent_limit_check(
                torrent, settings["seeding_time_limit"], settings["ratio_limit"]
            )
        self.assertFalse(result)
        warn.assert_not_called()
        self.assertFalse(harness._warned_no_seeding_limits)

    def test_remove_torrent_mode_2_warns_when_no_limits(self) -> None:
        harness = _LimitsHarness(
            tracker={"MaxSeedingTime": -1},
            max_seeding_time=-1,
            max_upload_ratio=-1,
            remove_torrent=2,
        )
        settings, _ = harness._get_torrent_limit_meta(_torrent())
        torrent = _torrent()
        with mock.patch.object(harness.logger, "warning") as warn:
            result = harness.torrent_limit_check(
                torrent, settings["seeding_time_limit"], settings["ratio_limit"]
            )
        self.assertFalse(result)
        warn.assert_called_once()
        self.assertTrue(harness._warned_no_seeding_limits)


_TWO_WEEKS = 1_209_600
_NOW = 1_700_000_000


class TestStalledUploadIdleRemoval(unittest.TestCase):
    """stalledUP last_activity can satisfy MaxSeedingTime when seeding_time has not."""

    def _harness(self, *, remove_torrent: int = 2) -> _LimitsHarness:
        return _LimitsHarness(
            tracker={},
            max_seeding_time=_TWO_WEEKS,
            max_upload_ratio=-1,
            remove_torrent=remove_torrent,
        )

    def _stalled_idle_torrent(self, *, last_activity: int, seeding_time: int = 3600):
        return _torrent(
            seeding_time=seeding_time,
            state_enum=TorrentStates.STALLED_UPLOAD,
            last_activity=last_activity,
            ratio=0.0,
            progress=1.0,
        )

    def test_mode_2_stalled_idle_older_than_limit(self) -> None:
        harness = self._harness()
        torrent = self._stalled_idle_torrent(last_activity=_NOW - _TWO_WEEKS - 1)
        with mock.patch("qBitrr.arss.torrent_limits.time.time", return_value=_NOW):
            self.assertTrue(harness.torrent_limit_check(torrent, _TWO_WEEKS, -1))

    def test_mode_2_stalled_idle_recent(self) -> None:
        harness = self._harness()
        torrent = self._stalled_idle_torrent(last_activity=_NOW - 3600)
        with mock.patch("qBitrr.arss.torrent_limits.time.time", return_value=_NOW):
            self.assertFalse(harness.torrent_limit_check(torrent, _TWO_WEEKS, -1))

    def test_mode_2_uploading_idle_age_does_not_count(self) -> None:
        harness = self._harness()
        torrent = _torrent(
            seeding_time=3600,
            state_enum=TorrentStates.UPLOADING,
            last_activity=_NOW - _TWO_WEEKS - 1,
        )
        with mock.patch("qBitrr.arss.torrent_limits.time.time", return_value=_NOW):
            self.assertFalse(harness.torrent_limit_check(torrent, _TWO_WEEKS, -1))

    def test_mode_1_stalled_idle_does_not_remove(self) -> None:
        harness = self._harness(remove_torrent=1)
        torrent = self._stalled_idle_torrent(last_activity=_NOW - _TWO_WEEKS - 1)
        with mock.patch("qBitrr.arss.torrent_limits.time.time", return_value=_NOW):
            self.assertFalse(harness.torrent_limit_check(torrent, _TWO_WEEKS, 2.0))

    def test_mode_2_last_activity_zero(self) -> None:
        harness = self._harness()
        torrent = self._stalled_idle_torrent(last_activity=0)
        with mock.patch("qBitrr.arss.torrent_limits.time.time", return_value=_NOW):
            self.assertFalse(harness.torrent_limit_check(torrent, _TWO_WEEKS, -1))

    def test_hnr_and_blocks_delete_despite_stalled_idle(self) -> None:
        """Idle time can meet MaxSeedingTime; HnR still uses actual seeding_time."""
        harness = self._harness()
        harness.monitored_trackers = [
            {"URI": "https://tracker.example/announce", "HitAndRunMode": "and"}
        ]
        torrent = self._stalled_idle_torrent(
            last_activity=_NOW - _TWO_WEEKS - 1, seeding_time=3600
        )
        with mock.patch("qBitrr.arss.torrent_limits.time.time", return_value=_NOW):
            self.assertTrue(harness.torrent_limit_check(torrent, _TWO_WEEKS, -1))
        data_settings = {
            "hnr_clear_mode": "and",
            "hnr_min_seed_ratio": 1.0,
            "hnr_min_seeding_time_days": 14,
            "hnr_min_download_percent": 10,
            "hnr_partial_seed_ratio": 1.0,
            "hnr_tracker_update_buffer": 0,
        }
        self.assertFalse(
            harness._hnr_allows_delete(torrent, "ratio/seed", data_settings=data_settings)
        )


class TestDurationTwoWeeks(unittest.TestCase):
    def test_parse_duration_2w(self) -> None:
        from qBitrr.duration_config import parse_duration

        self.assertEqual(parse_duration("2w", unit="seconds"), 1209600)


if __name__ == "__main__":
    unittest.main()
