"""Unit tests for multi-qBittorrent delete and recheck routing in arss.py."""

from __future__ import annotations

import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import qbittorrentapi

from tests.support.branch_compat import (
    HAS_TORRENT_BATCH_MIXIN,
    arss_auto_pause_resume_target,
    arss_periodic_command_uses_execute_command,
    arss_with_retry_target,
    torrent_batch_execute_command_target,
    torrent_batch_with_retry_target,
)

from qBitrr.arss import (
    Arr,
    PlaceHolderArr,
    TorrentPolicyManager,
    _collect_instance_hash_map_hashes,
    _prune_instance_hash_map,
)
from qBitrr.errors import DelayLoopException


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
    arr.change_priority = {}
    arr.change_priority_by_instance = defaultdict(dict)
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
    arr.manager.qbit_manager.get_all_instances.return_value = ["default"]
    arr._dedicated_qbit_clients = {}
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
        legacy_client = MagicMock()

        with (
            patch.object(arr, "_qbit_retry", side_effect=lambda fn, **_: fn()),
            patch.object(arr, "_get_legacy_default_qbit_client", return_value=legacy_client),
        ):
            arr._process_failed()

        legacy_client.torrents_delete.assert_not_called()
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

        with patch(torrent_batch_with_retry_target(), side_effect=lambda fn, **_: fn()):
            arr._process_paused()

        arr.manager.qbit_manager.get_client.assert_called_once_with("vpn")
        client.torrents_pause.assert_called_once_with(torrent_hashes=["hash1"])
        self.assertEqual(dict(arr.pause_by_instance), {})

    def test_retains_pause_on_failure(self) -> None:
        arr = _bare_arr()
        arr.pause_by_instance = defaultdict(set, {"vpn": {"hash1"}})
        client = MagicMock()
        client.torrents_pause.side_effect = qbittorrentapi.exceptions.APIConnectionError("timeout")
        arr.manager.qbit_manager.get_client.return_value = client

        with patch(torrent_batch_with_retry_target(), side_effect=lambda fn, **_: fn()):
            arr._process_paused()

        self.assertEqual(dict(arr.pause_by_instance), {"vpn": {"hash1"}})

    def test_resume_uses_owning_client(self) -> None:
        arr = _bare_arr()
        arr.resume_by_instance = defaultdict(set, {"vpn": {"hash1"}})
        client = MagicMock()
        arr.manager.qbit_manager.get_client.return_value = client

        with patch(torrent_batch_with_retry_target(), side_effect=lambda fn, **_: fn()):
            arr._process_resume()

        arr.manager.qbit_manager.get_client.assert_called_once_with("vpn")
        client.torrents_resume.assert_called_once_with(torrent_hashes=["hash1"])
        self.assertEqual(dict(arr.resume_by_instance), {})

    def test_pause_by_instance_stays_defaultdict_after_success(self) -> None:
        arr = _bare_arr()
        arr.pause_by_instance = defaultdict(set, {"vpn": {"hash1"}})
        client = MagicMock()
        arr.manager.qbit_manager.get_client.return_value = client

        with patch(torrent_batch_with_retry_target(), side_effect=lambda fn, **_: fn()):
            arr._process_paused()

        arr.pause_by_instance["vpn"].add("hash2")
        self.assertEqual(arr.pause_by_instance["vpn"], {"hash2"})

    def test_resume_by_instance_stays_defaultdict_after_success(self) -> None:
        arr = _bare_arr()
        arr.resume_by_instance = defaultdict(set, {"vpn": {"hash1"}})
        client = MagicMock()
        arr.manager.qbit_manager.get_client.return_value = client

        with patch(torrent_batch_with_retry_target(), side_effect=lambda fn, **_: fn()):
            arr._process_resume()

        arr.resume_by_instance["seedbox"].add("hash2")
        self.assertEqual(arr.resume_by_instance["seedbox"], {"hash2"})


def _bare_placeholder_arr() -> PlaceHolderArr:
    """Build a PlaceHolderArr with only the attributes needed for pause tests."""
    arr = PlaceHolderArr.__new__(PlaceHolderArr)
    arr.logger = MagicMock()
    arr.needs_cleanup = False
    arr.pause = set()
    arr.pause_by_instance = defaultdict(set)
    arr.resume = set()
    arr.resume_by_instance = defaultdict(set)
    arr.import_torrents = []
    arr.timed_ignore_cache = MagicMock()
    arr.timed_ignore_cache_2 = MagicMock()
    arr.manager = MagicMock()
    arr.manager.qbit_manager.get_all_instances.return_value = ["default"]
    arr._dedicated_qbit_clients = {}
    arr.recheck_by_instance = {}
    return arr


def _bare_arr_for_imports() -> Arr:
    """Build an Arr with only the attributes needed for _process_imports."""
    arr = Arr.__new__(Arr)
    arr.logger = MagicMock()
    arr.needs_cleanup = False
    arr.import_torrents = []
    arr.sent_to_scan = set()
    arr.sent_to_scan_hashes = set()
    arr.timed_ignore_cache = set()
    arr.type = "radarr"
    arr.import_mode = "Auto"
    arr.client = MagicMock()
    return arr


class TestProcessImportsScanFailure(unittest.TestCase):
    """Ensure failed Arr import scans can be retried on a later loop."""

    def test_does_not_mark_imported_when_scan_fails(self) -> None:
        arr = _bare_arr_for_imports()
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = Path(tmpdir) / "Movie.2024" / "Movie.2024.mkv"
            content_path.parent.mkdir()
            content_path.touch()
            torrent = MagicMock()
            torrent.hash = "abc123"
            torrent.content_path = str(content_path)
            arr.import_torrents = [(torrent, "default")]

            if HAS_TORRENT_BATCH_MIXIN:
                command_ctx = patch(
                    torrent_batch_execute_command_target(),
                    side_effect=ConnectionError("arr offline"),
                )
            else:
                arr.client.post_command.side_effect = ConnectionError("arr offline")
                command_ctx = patch(
                    torrent_batch_with_retry_target(),
                    side_effect=lambda fn, **_: fn(),
                )
            with command_ctx:
                with patch.object(arr, "add_tags") as add_tags:
                    with patch(
                        torrent_batch_with_retry_target(),
                        side_effect=lambda fn, **_: fn(),
                    ):
                        arr._process_imports()

            add_tags.assert_not_called()
            self.assertNotIn("abc123", arr.sent_to_scan_hashes)
            self.assertNotIn(content_path.parent, arr.sent_to_scan)
            self.assertEqual(arr.import_torrents, [])

    def test_marks_imported_only_after_successful_scan(self) -> None:
        arr = _bare_arr_for_imports()
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = Path(tmpdir) / "Movie.2024" / "Movie.2024.mkv"
            content_path.parent.mkdir()
            content_path.touch()
            torrent = MagicMock()
            torrent.hash = "abc123"
            torrent.content_path = str(content_path)
            arr.import_torrents = [(torrent, "vpn")]

            if HAS_TORRENT_BATCH_MIXIN:
                with patch(torrent_batch_execute_command_target()) as execute_command:
                    with patch.object(arr, "add_tags") as add_tags:
                        with patch(
                            torrent_batch_with_retry_target(),
                            side_effect=lambda fn, **_: fn(),
                        ):
                            arr._process_imports()
                execute_command.assert_called_once()
            else:
                with patch(
                    torrent_batch_with_retry_target(),
                    side_effect=lambda fn, **_: fn(),
                ):
                    with patch.object(arr, "add_tags") as add_tags:
                        arr._process_imports()
                arr.client.post_command.assert_called_once()
            add_tags.assert_called_once_with(torrent, ["qBitrr-imported"], "vpn")
            self.assertIn("abc123", arr.sent_to_scan_hashes)
            self.assertIn(content_path.parent, arr.sent_to_scan)


class TestRunPeriodicCommand(unittest.TestCase):
    """Ensure periodic Arr commands report success/failure without raising."""

    def test_returns_false_on_command_failure(self) -> None:
        arr = Arr.__new__(Arr)
        arr._name = "Sonarr"
        arr.type = "sonarr"
        arr.logger = MagicMock()
        arr.client = MagicMock()
        if arss_periodic_command_uses_execute_command():
            with patch(
                "qBitrr.arss.arr.execute_command",
                side_effect=ValueError(
                    "Expected a dictionary response from the 'command' endpoint"
                ),
            ):
                with patch(arss_with_retry_target(), side_effect=lambda fn, **_: fn()):
                    result = arr._run_periodic_command("RssSync")
        else:
            arr.client.post_command.side_effect = ValueError(
                "Expected a dictionary response from the 'command' endpoint"
            )
            with patch(arss_with_retry_target(), side_effect=lambda fn, **_: fn()):
                result = arr._run_periodic_command("RssSync")

        self.assertFalse(result)
        arr.logger.warning.assert_called()

    def test_returns_true_on_success(self) -> None:
        arr = Arr.__new__(Arr)
        arr._name = "Sonarr"
        arr.type = "sonarr"
        arr.logger = MagicMock()
        arr.client = MagicMock()
        if arss_periodic_command_uses_execute_command():
            with patch("qBitrr.arss.arr.execute_command", return_value={"status": "ok"}):
                with patch(arss_with_retry_target(), side_effect=lambda fn, **_: fn()):
                    result = arr._run_periodic_command("RssSync")
        else:
            arr.client.post_command.return_value = {"status": "ok"}
            with patch(arss_with_retry_target(), side_effect=lambda fn, **_: fn()):
                result = arr._run_periodic_command("RssSync")

        self.assertTrue(result)


class TestQbitInstanceReachability(unittest.TestCase):
    """Ensure reachability probes use the worker's own qBit client."""

    def test_uses_get_qbit_client_not_manager_is_instance_alive(self) -> None:
        arr = Arr.__new__(Arr)
        arr._name = "Radarr"
        arr.logger = MagicMock()
        arr._dedicated_qbit_clients = {}
        arr.manager = MagicMock()
        client = MagicMock()
        client.app_version.return_value = "v5.0.0"

        with patch.object(arr, "_get_qbit_client", return_value=client) as get_client:
            self.assertTrue(arr._is_qbit_instance_reachable("vpn"))

        get_client.assert_called_once_with("vpn")
        arr.manager.is_instance_alive.assert_not_called()


class TestLegacyDefaultClientRouting(unittest.TestCase):
    """Ensure legacy pause/delete paths use the primary qBit client helper."""

    def test_legacy_pause_uses_primary_client(self) -> None:
        arr = _bare_arr()
        arr.pause = {"hash1"}
        legacy_client = MagicMock()
        arr.manager.qbit_manager.name_cache = {"hash1": "Example"}

        with (
            patch(arss_auto_pause_resume_target(), True),
            patch(torrent_batch_with_retry_target(), side_effect=lambda fn, **_: fn()),
            patch.object(arr, "_get_legacy_default_qbit_client", return_value=legacy_client),
        ):
            arr._process_paused()

        legacy_client.torrents_pause.assert_called_once_with(torrent_hashes=["hash1"])
        self.assertEqual(arr.pause, set())

    def test_legacy_delete_uses_primary_client(self) -> None:
        arr = _bare_arr()
        arr.delete = {"hash1"}
        arr.remove_from_qbit = set()
        arr.skip_blacklist = set()
        arr.delete_by_instance = {}
        arr.remove_from_qbit_by_instance = {}
        arr.missing_files_post_delete = set()
        arr.downloads_with_bad_error_message_blocklist = set()
        legacy_client = MagicMock()

        with (
            patch.object(arr, "_qbit_retry", side_effect=lambda fn, **_: fn()),
            patch.object(arr, "_get_legacy_default_qbit_client", return_value=legacy_client),
        ):
            arr._process_failed()

        legacy_client.torrents_delete.assert_called_once()


class TestWorkerQbitPreflight(unittest.TestCase):
    """Ensure worker loops probe qBit via dedicated clients, not parent sessions."""

    def test_is_any_qbit_instance_reachable_checks_configured_instances(self) -> None:
        arr = Arr.__new__(Arr)
        arr._name = "Radarr"
        arr.logger = MagicMock()
        arr.manager = MagicMock()
        arr.manager.qbit_manager.get_all_instances.return_value = ["vpn", "seedbox"]

        with patch.object(
            arr,
            "_is_qbit_instance_reachable",
            side_effect=lambda name: name == "seedbox",
        ) as reachable:
            self.assertTrue(arr._is_any_qbit_instance_reachable())

        self.assertEqual(reachable.call_count, 2)

    def test_validate_qbit_preflight_uses_worker_reachability(self) -> None:
        arr = TorrentPolicyManager.__new__(TorrentPolicyManager)
        arr.logger = MagicMock()
        arr.manager = MagicMock()

        with (
            patch.object(arr, "_is_any_qbit_instance_reachable", return_value=False),
            patch.object(arr, "_get_primary_qbit_client"),
        ):
            with self.assertRaises(DelayLoopException) as ctx:
                arr._validate_qbit_preflight()

        self.assertEqual(ctx.exception.error_type, "no_downloads")


class TestFilePriorityRouting(unittest.TestCase):
    """Ensure file-priority updates target the owning qBittorrent instance."""

    def test_file_priority_uses_owning_client(self) -> None:
        arr = _bare_arr()
        arr.change_priority = {}
        arr.change_priority_by_instance = defaultdict(dict, {"vpn": {"hash1": [1, 2]}})
        arr.manager.qbit_manager.name_cache = {"hash1": "Example"}
        client = MagicMock()

        with (
            patch.object(arr, "_get_qbit_client", return_value=client) as get_client,
            patch(torrent_batch_with_retry_target(), side_effect=lambda fn, **_: fn()),
        ):
            arr._process_file_priority()

        get_client.assert_called_once_with("vpn")
        client.torrents_file_priority.assert_called_once_with(
            torrent_hash="hash1", file_ids=[1, 2], priority=0
        )
        self.assertEqual(arr.change_priority_by_instance, {})

    def test_file_priority_retains_hash_on_failure(self) -> None:
        arr = _bare_arr()
        arr.change_priority = {}
        arr.change_priority_by_instance = defaultdict(dict, {"vpn": {"hash1": [1, 2]}})
        arr.manager.qbit_manager.name_cache = {"hash1": "Example"}
        client = MagicMock()
        client.torrents_file_priority.side_effect = qbittorrentapi.exceptions.APIConnectionError(
            "timeout"
        )

        with (
            patch.object(arr, "_get_qbit_client", return_value=client),
            patch(torrent_batch_with_retry_target(), side_effect=lambda fn, **_: fn()),
        ):
            arr._process_file_priority()

        self.assertEqual(dict(arr.change_priority_by_instance), {"vpn": {"hash1": [1, 2]}})

    def test_legacy_file_priority_retains_hash_on_failure(self) -> None:
        arr = _bare_arr()
        arr.change_priority = {"hash1": [1, 2]}
        arr.change_priority_by_instance = defaultdict(dict)
        arr.manager.qbit_manager.name_cache = {"hash1": "Example"}
        legacy_client = MagicMock()
        legacy_client.torrents_file_priority.side_effect = (
            qbittorrentapi.exceptions.APIConnectionError("timeout")
        )

        with (
            patch.object(arr, "_get_legacy_default_qbit_client", return_value=legacy_client),
            patch(torrent_batch_with_retry_target(), side_effect=lambda fn, **_: fn()),
        ):
            arr._process_file_priority()

        self.assertEqual(arr.change_priority, {"hash1": [1, 2]})

    def test_file_priority_retains_hash_when_name_missing(self) -> None:
        arr = _bare_arr()
        arr.change_priority = {}
        arr.change_priority_by_instance = defaultdict(dict, {"vpn": {"hash1": [1, 2]}})
        client = MagicMock()

        with patch.object(arr, "_get_qbit_client", return_value=client):
            arr._process_file_priority()

        self.assertEqual(dict(arr.change_priority_by_instance), {"vpn": {"hash1": [1, 2]}})
        client.torrents_file_priority.assert_not_called()
        arr.logger.error.assert_called_once_with("Torrent does not exist? %s", "hash1")

    def test_legacy_file_priority_retains_hash_when_name_missing(self) -> None:
        arr = _bare_arr()
        arr.change_priority = {"hash1": [1, 2]}
        arr.change_priority_by_instance = defaultdict(dict)
        legacy_client = MagicMock()

        with patch.object(arr, "_get_legacy_default_qbit_client", return_value=legacy_client):
            arr._process_file_priority()

        self.assertEqual(arr.change_priority, {"hash1": [1, 2]})
        legacy_client.torrents_file_priority.assert_not_called()
        arr.logger.error.assert_called_once_with("Torrent does not exist? %s", "hash1")


class TestLegacyResumeRetry(unittest.TestCase):
    """Ensure legacy resume path retries like legacy pause."""

    def test_legacy_resume_uses_with_retry(self) -> None:
        arr = _bare_arr()
        arr.resume = {"hash1"}
        legacy_client = MagicMock()

        with (
            patch(arss_auto_pause_resume_target(), True),
            patch(
                "qBitrr.arss.torrent_batch_mixin.with_retry", side_effect=lambda fn, **_: fn()
            ) as with_retry_mock,
            patch.object(arr, "_get_legacy_default_qbit_client", return_value=legacy_client),
        ):
            arr._process_resume()

        with_retry_mock.assert_called()
        legacy_client.torrents_resume.assert_called_once_with(torrent_hashes=["hash1"])
        self.assertEqual(arr.resume, set())


class TestPlaceHolderRecheckRegression(unittest.TestCase):
    """Regression guard for PlaceHolderArr recheck client assignment."""

    def test_process_errored_assigns_client_when_hashes_present(self) -> None:
        arr = _bare_placeholder_arr()
        arr.recheck_by_instance = {"vpn": {"hash1"}}
        arr.manager.qbit_manager.cache = {}
        client = MagicMock()

        with (
            patch.object(arr, "_get_qbit_client", return_value=client) as get_client,
            patch(torrent_batch_with_retry_target(), side_effect=lambda fn, **_: fn()),
        ):
            arr._process_errored()

        get_client.assert_called_once_with("vpn")
        client.torrents_recheck.assert_called_once_with(torrent_hashes=["hash1"])
        self.assertEqual(arr.recheck_by_instance, {})


class TestPlaceHolderArrPauseRetention(unittest.TestCase):
    """Ensure free-space pause requests survive transient qBit failures."""

    def test_process_with_empty_pause_resume_queues_does_not_raise(self) -> None:
        arr = _bare_placeholder_arr()

        with (
            patch(arss_auto_pause_resume_target(), True),
            patch.object(arr, "_process_errored"),
            patch.object(arr, "_process_file_priority"),
            patch.object(arr, "_process_failed"),
        ):
            arr.process()

    def test_retains_pause_when_client_unavailable(self) -> None:
        arr = _bare_placeholder_arr()
        arr.pause_by_instance = defaultdict(set, {"vpn": {"hash1"}})
        arr.manager.qbit_manager.get_client.return_value = None

        with patch(arss_auto_pause_resume_target(), True):
            arr._process_paused()

        self.assertEqual(dict(arr.pause_by_instance), {"vpn": {"hash1"}})

    def test_retains_resume_when_client_unavailable(self) -> None:
        arr = _bare_placeholder_arr()
        arr.resume_by_instance = defaultdict(set, {"vpn": {"hash1"}})
        arr.manager.qbit_manager.get_client.return_value = None

        with patch(arss_auto_pause_resume_target(), True):
            arr._process_resume()

        self.assertEqual(dict(arr.resume_by_instance), {"vpn": {"hash1"}})


if __name__ == "__main__":
    unittest.main()
