"""Regression tests for tracker vs SeedingMode limit merge (#547)."""

from __future__ import annotations

import logging
import unittest
from types import SimpleNamespace
from unittest import mock

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


class TestDurationTwoWeeks(unittest.TestCase):
    def test_parse_duration_2w(self) -> None:
        from qBitrr.duration_config import parse_duration

        self.assertEqual(parse_duration("2w", unit="seconds"), 1209600)


if __name__ == "__main__":
    unittest.main()
