"""Regression tests for the StalledDelay sentinel contract."""

from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from qbittorrentapi import TorrentStates

from qBitrr.arss.arr_base import ArrBase


class TestStalledDelaySemantics(unittest.TestCase):
    """Verify immediate, infinite, and delayed stalled cleanup semantics."""

    def setUp(self) -> None:
        self.arr = ArrBase.__new__(ArrBase)
        self.arr.logger = MagicMock()
        self.arr.cleaned_torrents = set()
        self.arr.ignore_torrents_younger_than = 60
        self.arr._is_metadata_stuck_state = MagicMock(return_value=False)
        self.arr.in_tags = MagicMock(return_value=False)
        self.arr.add_tags = MagicMock()
        self.arr.remove_tags = MagicMock()

    def _torrent(self, *, added_on: float, last_activity: float) -> SimpleNamespace:
        return SimpleNamespace(
            name="Example",
            hash="HASH",
            added_on=added_on,
            last_activity=last_activity,
            state_enum=TorrentStates.STALLED_DOWNLOAD,
            availability=0.0,
        )

    def test_negative_one_is_infinite(self) -> None:
        self.arr.stalled_delay = -1
        self.arr.allowed_stalled = self.arr.stalled_delay != 0
        now = time.time()

        self.assertTrue(
            self.arr._stalled_check(
                self._torrent(added_on=now - 3600, last_activity=now - 3600), now
            )
        )
        self.arr.add_tags.assert_called_once()

    def test_zero_is_immediate(self) -> None:
        self.arr.stalled_delay = 0
        self.arr.allowed_stalled = self.arr.stalled_delay != 0
        now = time.time()

        self.assertFalse(
            self.arr._stalled_check(self._torrent(added_on=now - 60, last_activity=now - 60), now)
        )
        self.arr.add_tags.assert_not_called()

    def test_positive_delay_waits_before_expiry(self) -> None:
        self.arr.stalled_delay = 15
        self.arr.allowed_stalled = self.arr.stalled_delay != 0
        now = time.time()

        self.assertTrue(
            self.arr._stalled_check(self._torrent(added_on=now - 60, last_activity=now - 60), now)
        )
        self.assertFalse(
            self.arr._stalled_check(
                self._torrent(added_on=now - 1200, last_activity=now - 1200), now
            )
        )


if __name__ == "__main__":
    unittest.main()
