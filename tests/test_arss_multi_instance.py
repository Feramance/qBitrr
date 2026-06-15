"""Unit tests for multi-qBittorrent delete and recheck routing in arss.py."""

from __future__ import annotations

import unittest
from collections import defaultdict
from unittest.mock import MagicMock, patch

import qbittorrentapi

from qBitrr.arss import (
    Arr,
    PlaceHolderArr,
    _collect_instance_hash_map_hashes,
    _prune_instance_hash_map,
)


class TestPruneInstanceHashMap(unittest.TestCase):
    """Tests for the per-instance hash map pruning helper."""

    def test_prunes_only_specified_hashes(self) -> None:
        mapping = {"vpn": {"a", "b", "c"}, "default": {"d"}}
        _prune_instance_hash_map(mapping, {"a", "d"})
        self.assertEqual(mapping, {"vpn": {"b", "c"}})

    def test_drops_empty_instance_buckets(self) -> None:
        mapping = {"vpn": {"a"}}
        _prune_instance_hash_map(mapping, {"a"})
        self.assertEqual(mapping, {})

    def test_noop_when_hashes_empty(self) -> None:
        mapping = {"vpn": {"a"}}
        _prune_instance_hash_map(mapping, set())
        self.assertEqual(mapping, {"vpn": {"a"}})


class TestCollectInstanceHashMapHashes(unittest.TestCase):
    """Tests for collecting pending hashes across per-instance maps."""

    def test_collects_across_multiple_maps(self) -> None:
        pending = _collect_instance_hash_map_hashes(
            {"vpn": {"a", "b"}},
            {"seedbox": {"c"}},
        )
        self.assertEqual(pending, {"a", "b", "c"})


def _bare_arr() -> Arr:
    """Build an Arr with only the attributes needed for _process_failed / _process_errored."""
    arr = Arr.__new__(Arr)
    arr.logger = MagicMock()
    arr.delete = set()
    arr.delete_by_instance = {}
    arr.remove_from_qbit_by_instance = {}
    arr.remove_from_qbit = set()
    arr.skip_blacklist = set()
    arr.missing_files_post_delete = set()
    arr.downloads_with_bad_error_message_blocklist = set()
    arr.cleaned_torrents = set()
    arr.sent_to_scan_hashes = set()
    arr.needs_cleanup = False
    arr.recheck_by_instance = {}
    arr.pause = set()
    arr.pause_by_instance = defaultdict(set)
    arr.resume = set()
    arr.resume_by_instance = defaultdict(set)
    arr.timed_ignore_cache = MagicMock()
    arr.timed_ignore_cache_2 = MagicMock()
    arr.manager = MagicMock()
    arr.manager.qbit_manager.name_cache = {}
    arr.manager.qbit_manager.cache = {}
    arr.manager.qbit = MagicMock()
    arr._log_deletion_summary_line = MagicMock()
    arr._log_deletion_sample_debug = MagicMock()
    arr._process_failed_dispatch_queue_deletes = MagicMock()
    arr._evict_hashes_from_qbit_side_caches = MagicMock()
    return arr


class TestProcessFailedRetention(unittest.TestCase):
    """Ensure failed per-instance deletes are retained for retry."""

    def test_retains_hashes_when_per_instance_delete_fails(self) -> None:
        arr = _bare_arr()
        arr.delete = {"hash1"}
        arr.delete_by_instance = {"vpn": {"hash1"}}
        client = MagicMock()
        client.torrents_delete.side_effect = qbittorrentapi.exceptions.APIError("offline")
        arr.manager.qbit_manager.get_client.return_value = client
        arr.manager.qbit.torrents_delete.side_effect = qbittorrentapi.exceptions.APIError(
            "not on default instance"
        )

        with patch.object(arr, "_qbit_retry", side_effect=lambda fn, **_: fn()):
            arr._process_failed()

        self.assertIn("hash1", arr.delete_by_instance.get("vpn", set()))
        self.assertIn("hash1", arr.delete)

    def test_prunes_hashes_after_successful_per_instance_delete(self) -> None:
        arr = _bare_arr()
        arr.delete = {"hash1", "hash2"}
        arr.delete_by_instance = {"vpn": {"hash1"}, "default": {"hash2"}}
        vpn_client = MagicMock()
        default_client = MagicMock()

        def get_client(name: str) -> MagicMock | None:
            return {"vpn": vpn_client, "default": default_client}.get(name)

        arr.manager.qbit_manager.get_client.side_effect = get_client

        with patch.object(arr, "_qbit_retry", side_effect=lambda fn, **_: fn()):
            arr._process_failed()

        self.assertNotIn("hash1", arr.delete_by_instance.get("vpn", set()))
        self.assertNotIn("hash2", arr.delete_by_instance.get("default", set()))
        self.assertNotIn("hash1", arr.delete)
        self.assertNotIn("hash2", arr.delete)
        vpn_client.torrents_delete.assert_called_once()
        default_client.torrents_delete.assert_called_once()
        arr._process_failed_dispatch_queue_deletes.assert_called_once()

    def test_defers_queue_dispatch_until_qbit_delete_succeeds(self) -> None:
        arr = _bare_arr()
        arr.delete = {"hash1"}
        arr.delete_by_instance = {"vpn": {"hash1"}}
        client = MagicMock()
        client.torrents_delete.side_effect = qbittorrentapi.exceptions.APIError("offline")
        arr.manager.qbit_manager.get_client.return_value = client

        with patch.object(arr, "_qbit_retry", side_effect=lambda fn, **_: fn()):
            arr._process_failed()

        arr._process_failed_dispatch_queue_deletes.assert_not_called()
        self.assertIn("hash1", arr.delete_by_instance.get("vpn", set()))

    def test_skips_default_delete_for_pending_per_instance_hashes(self) -> None:
        arr = _bare_arr()
        arr.delete = {"hash1"}
        arr.delete_by_instance = {"vpn": {"hash1"}}
        vpn_client = MagicMock()
        vpn_client.torrents_delete.side_effect = qbittorrentapi.exceptions.APIError("offline")
        arr.manager.qbit_manager.get_client.return_value = vpn_client

        with patch.object(arr, "_qbit_retry", side_effect=lambda fn, **_: fn()):
            arr._process_failed()

        arr.manager.qbit.torrents_delete.assert_not_called()
        self.assertIn("hash1", arr.delete)


class TestProcessErroredRouting(unittest.TestCase):
    """Ensure recheck operations target the owning qBittorrent instance."""

    def test_recheck_uses_owning_client(self) -> None:
        arr = _bare_arr()
        arr.recheck_by_instance = {"vpn": {"hash1"}}
        client = MagicMock()
        arr.manager.qbit_manager.get_client.return_value = client

        with patch.object(arr, "_qbit_retry", side_effect=lambda fn, **_: fn()):
            arr._process_errored()

        arr.manager.qbit_manager.get_client.assert_called_once_with("vpn")
        client.torrents_recheck.assert_called_once_with(torrent_hashes=["hash1"])
        arr.manager.qbit.torrents_recheck.assert_not_called()
        self.assertEqual(arr.recheck_by_instance, {})

    def test_retains_recheck_on_failure(self) -> None:
        arr = _bare_arr()
        arr.recheck_by_instance = {"vpn": {"hash1"}}
        client = MagicMock()
        arr.manager.qbit_manager.get_client.return_value = client

        def fail_retry(fn, **_) -> None:
            fn()

        with patch.object(arr, "_qbit_retry", side_effect=fail_retry):
            client.torrents_recheck.side_effect = qbittorrentapi.exceptions.APIConnectionError(
                "timeout"
            )
            arr._process_errored()

        self.assertEqual(arr.recheck_by_instance, {"vpn": {"hash1"}})


class TestArrPauseResumeRouting(unittest.TestCase):
    """Ensure pause/resume operations target the owning qBittorrent instance."""

    def test_pause_uses_owning_client(self) -> None:
        arr = _bare_arr()
        arr.pause_by_instance = defaultdict(set, {"vpn": {"hash1"}})
        client = MagicMock()
        arr.manager.qbit_manager.get_client.return_value = client

        with patch("qBitrr.arss.with_retry", side_effect=lambda fn, **_: fn()):
            arr._process_paused()

        arr.manager.qbit_manager.get_client.assert_called_once_with("vpn")
        client.torrents_pause.assert_called_once_with(torrent_hashes=["hash1"])
        arr.manager.qbit.torrents_pause.assert_not_called()
        self.assertEqual(arr.pause_by_instance, {})

    def test_retains_pause_on_failure(self) -> None:
        arr = _bare_arr()
        arr.pause_by_instance = defaultdict(set, {"vpn": {"hash1"}})
        client = MagicMock()
        client.torrents_pause.side_effect = qbittorrentapi.exceptions.APIConnectionError("timeout")
        arr.manager.qbit_manager.get_client.return_value = client

        with patch("qBitrr.arss.with_retry", side_effect=lambda fn, **_: fn()):
            arr._process_paused()

        self.assertEqual(dict(arr.pause_by_instance), {"vpn": {"hash1"}})

    def test_resume_uses_owning_client(self) -> None:
        arr = _bare_arr()
        arr.resume_by_instance = defaultdict(set, {"vpn": {"hash1"}})
        client = MagicMock()
        arr.manager.qbit_manager.get_client.return_value = client

        with patch("qBitrr.arss.with_retry", side_effect=lambda fn, **_: fn()):
            arr._process_resume()

        arr.manager.qbit_manager.get_client.assert_called_once_with("vpn")
        client.torrents_resume.assert_called_once_with(torrent_hashes=["hash1"])
        arr.manager.qbit.torrents_resume.assert_not_called()
        self.assertEqual(arr.resume_by_instance, {})


def _bare_placeholder_arr() -> PlaceHolderArr:
    """Build a PlaceHolderArr with only the attributes needed for pause tests."""
    arr = PlaceHolderArr.__new__(PlaceHolderArr)
    arr.logger = MagicMock()
    arr.needs_cleanup = False
    arr.pause = set()
    arr.pause_by_instance = defaultdict(set)
    arr.manager = MagicMock()
    arr.manager.qbit = MagicMock()
    return arr


class TestPlaceHolderArrPauseRetention(unittest.TestCase):
    """Ensure free-space pause requests survive transient qBit failures."""

    def test_retains_pause_when_client_unavailable(self) -> None:
        arr = _bare_placeholder_arr()
        arr.pause_by_instance = defaultdict(set, {"vpn": {"hash1"}})
        arr.manager.qbit_manager.get_client.return_value = None

        with patch("qBitrr.arss.AUTO_PAUSE_RESUME", True):
            arr._process_paused()

        self.assertEqual(dict(arr.pause_by_instance), {"vpn": {"hash1"}})


if __name__ == "__main__":
    unittest.main()
