"""Regression tests for StalledDelay = -1 behavior (#616).

Ensures that disabling stalled-torrent removal (StalledDelay = -1, allowed_stalled = False)
does not immediately mark stalled downloads or metadata downloads for deletion.
"""

from __future__ import annotations

import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from qbittorrentapi import TorrentStates

from qBitrr.arss.arr_base import ArrBase


class TestStalledDelayDisabled(unittest.TestCase):
    def setUp(self) -> None:
        self.arr = ArrBase.__new__(ArrBase)
        self.arr.logger = MagicMock()
        self.arr.cleaned_torrents = set()
        self.arr.re_search_stalled = False
        self.arr.ignore_torrents_younger_than = 60
        self.arr.tracker_delay = {}
        self.arr.custom_format_unmet_search = False
        self.arr.manager = SimpleNamespace(
            qbit_manager=SimpleNamespace(cache={}, name_cache={}),
            policy_manager_owns_tracker_sync_for_category=lambda *a, **k: False,
        )
        self.arr._process_single_torrent_trackers = MagicMock()
        self.arr._should_leave_alone = MagicMock(return_value=(False, -1, False, None, None))
        self.arr._is_missing_files_torrent = MagicMock(return_value=False)
        self.arr.is_ignored_state = MagicMock(return_value=False)
        self.arr._process_single_torrent_stalled_torrent = MagicMock()
        self.arr._mark_for_deletion = MagicMock()
        self.arr.remove_tags = MagicMock()
        self.arr.add_tags = MagicMock()
        self.arr.special_casing_file_check = set()
        self.arr.timed_ignore_cache = set()
        self.arr.resume_by_instance = {}
        self.arr.maximum_deletable_percentage = 0.8
        self.arr.is_complete_state = MagicMock(return_value=False)
        self.arr._is_metadata_stuck_state = MagicMock(return_value=False)
        self.arr._process_single_torrent_process_files = MagicMock()
        self.arr._process_single_torrent_percentage_threshold = MagicMock()

    def test_stalled_check_returns_true_when_allowed_stalled_is_false(self) -> None:
        """When allowed_stalled is False (StalledDelay = -1), _stalled_check must return True to ignore the torrent."""
        self.arr.allowed_stalled = False
        self.arr.stalled_delay = -1

        now = time.time()
        torrent = SimpleNamespace(
            name="Test Movie (2026)",
            hash="HASH123",
            added_on=now - 300,
            last_activity=now - 300,
            state_enum=TorrentStates.STALLED_DOWNLOAD,
            tags="",
            category="movies",
            progress=0.142,
            availability=0.0,
            amount_left=1000000,
        )
        self.arr.in_tags = MagicMock(return_value=False)

        res = self.arr._stalled_check(torrent, now, "default")
        self.assertTrue(res, "_stalled_check should return True when allowed_stalled is False")

    def test_stalled_check_removes_allowed_stalled_tag_when_disabled(self) -> None:
        """When allowed_stalled is False and the torrent still has qBitrr-allowed_stalled, it should be removed."""
        self.arr.allowed_stalled = False
        self.arr.stalled_delay = -1

        now = time.time()
        torrent = SimpleNamespace(
            name="Test Movie (2026)",
            hash="HASH123",
            added_on=now - 300,
            last_activity=now - 300,
            state_enum=TorrentStates.STALLED_DOWNLOAD,
            tags="qBitrr-allowed_stalled",
            category="movies",
            progress=0.142,
            availability=0.0,
            amount_left=1000000,
        )

        def mock_in_tags(t, tag, instance_name="default"):
            return tag == "qBitrr-allowed_stalled"

        self.arr.in_tags = MagicMock(side_effect=mock_in_tags)

        res = self.arr._stalled_check(torrent, now, "default")
        self.assertTrue(res)
        self.arr.remove_tags.assert_called_once_with(
            torrent, ["qBitrr-allowed_stalled"], "default"
        )

    def test_process_single_torrent_does_not_delete_stalled_when_disabled(self) -> None:
        """When StalledDelay = -1, _process_single_torrent must not call _process_single_torrent_stalled_torrent."""
        self.arr.allowed_stalled = False
        self.arr.stalled_delay = -1

        now = time.time()
        torrent = SimpleNamespace(
            name="Test Movie (2026)",
            hash="HASH123",
            added_on=now - 300,
            last_activity=now - 300,
            state_enum=TorrentStates.STALLED_DOWNLOAD,
            tags="",
            category="movies",
            progress=0.142,
            availability=0.0,
            amount_left=1000000,
            eta=86400,
        )
        self.arr.in_tags = MagicMock(return_value=False)

        self.arr._process_single_torrent(torrent, "default")

        self.arr._process_single_torrent_stalled_torrent.assert_not_called()

    def test_process_single_torrent_does_not_delete_metadata_download_when_disabled(self) -> None:
        """Metadata downloads must also not be marked for deletion when StalledDelay = -1."""
        self.arr.allowed_stalled = False
        self.arr.stalled_delay = -1

        now = time.time()
        for state in (TorrentStates.METADATA_DOWNLOAD, TorrentStates.FORCED_METADATA_DOWNLOAD):
            self.arr._process_single_torrent_stalled_torrent.reset_mock()
            torrent = SimpleNamespace(
                name="Metadata Movie",
                hash="HASH_META",
                added_on=now - 500,
                last_activity=now - 500,
                state_enum=state,
                tags="",
                category="movies",
                progress=0.0,
                availability=0.0,
                amount_left=1000000,
                eta=86400,
            )
            self.arr.in_tags = MagicMock(return_value=False)
            self.arr._process_single_torrent(torrent, "default")
            self.arr._process_single_torrent_stalled_torrent.assert_not_called()

    def test_stalled_check_expires_when_allowed_stalled_is_true(self) -> None:
        """When allowed_stalled is True, _stalled_check returns False after stalled_delay expires."""
        self.arr.allowed_stalled = True
        self.arr.stalled_delay = 15  # 15 minutes = 900 seconds

        now = time.time()
        torrent = SimpleNamespace(
            name="Expired Stalled Movie",
            hash="HASH_EXP",
            added_on=now - 1200,
            last_activity=now - 1000,  # 1000s > 900s
            state_enum=TorrentStates.STALLED_DOWNLOAD,
            tags="",
            category="movies",
            progress=0.10,
            availability=0.0,
            amount_left=1000000,
        )
        self.arr.in_tags = MagicMock(return_value=False)

        res = self.arr._stalled_check(torrent, now, "default")
        self.assertFalse(res, "_stalled_check should return False when delay has expired")

    def test_stalled_check_remains_ignored_before_delay_expires(self) -> None:
        """When allowed_stalled is True and delay has not expired, _stalled_check returns True and tags torrent."""
        self.arr.allowed_stalled = True
        self.arr.stalled_delay = 15  # 15 minutes = 900 seconds

        now = time.time()
        torrent = SimpleNamespace(
            name="Recently Stalled Movie",
            hash="HASH_RECENT",
            added_on=now - 400,
            last_activity=now - 100,  # 100s < 900s
            state_enum=TorrentStates.STALLED_DOWNLOAD,
            tags="",
            category="movies",
            progress=0.10,
            availability=0.0,
            amount_left=1000000,
        )
        self.arr.in_tags = MagicMock(return_value=False)

        res = self.arr._stalled_check(torrent, now, "default")
        self.assertTrue(res, "_stalled_check should return True while delay has not expired")
        self.arr.add_tags.assert_called_once_with(
            torrent, ["qBitrr-allowed_stalled"], "default"
        )
