from __future__ import annotations

import os
import pathlib
import types
import unittest

TEST_DATA_PATH = pathlib.Path("/tmp/qbitrr-test-config")
TEST_DATA_PATH.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("QBITRR_OVERRIDES_DATA_PATH", str(TEST_DATA_PATH))

from qBitrr.arss import Arr  # noqa: E402


class HnrTrackerDeadTest(unittest.TestCase):
    def _arr_with_hnr_tracker(self) -> Arr:
        arr = Arr.__new__(Arr)
        arr.monitored_trackers = [
            {
                "URI": "https://tracker.example/announce",
                "HitAndRunMode": "and",
            }
        ]
        return arr

    @staticmethod
    def _torrent_with_tracker_message(message: str) -> types.SimpleNamespace:
        return types.SimpleNamespace(
            trackers=[
                types.SimpleNamespace(
                    url="https://tracker.example/announce",
                    msg=message,
                )
            ]
        )

    def test_transient_host_not_found_does_not_bypass_hnr(self) -> None:
        arr = self._arr_with_hnr_tracker()
        torrent = self._torrent_with_tracker_message("Host not found (authoritative)")

        self.assertFalse(arr._hnr_tracker_is_dead(torrent))

    def test_torrent_specific_not_found_bypasses_hnr(self) -> None:
        arr = self._arr_with_hnr_tracker()
        torrent = self._torrent_with_tracker_message("Torrent not found")

        self.assertTrue(arr._hnr_tracker_is_dead(torrent))


if __name__ == "__main__":
    unittest.main()
