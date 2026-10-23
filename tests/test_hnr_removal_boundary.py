"""HnR is a mandatory veto for client removal and referenced content cleanup."""

from __future__ import annotations

import logging
import tempfile
import time
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import qbittorrentapi

from qBitrr.arss.arr_base import ArrBase
from qBitrr.arss.qbit_side_effects import (
    content_removal_allowed,
    delete_hashes_on_primary,
    delete_hashes_per_instance,
)
from qBitrr.arss.torrent_batch import TorrentBatch
from qBitrr.arss.torrent_limits import TorrentLimits


def tracker(url="https://tracker.example/announce", status=2, msg=""):
    return SimpleNamespace(url=url, status=status, msg=msg)


class Worker(TorrentLimits, TorrentBatch):
    def __init__(self):
        self.logger = logging.getLogger("hnr-test")
        self.monitored_trackers = []
        self.seeding_mode_global_remove_torrent = 1
        self.stalled_delay = 0
        self.ignore_torrents_younger_than = 0
        self._warned_no_seeding_limits = False
        self._get_torrent_limit_meta = lambda torrent, **kwargs: (
            {"ratio_limit": 1, "seeding_time_limit": 86400},
            {},
        )
        self._stalled_upload_idle_exceeds_limit = lambda *a: False
        self.clients = {}
        self.manager = SimpleNamespace(
            qbit_manager=SimpleNamespace(get_all_instances=lambda: list(self.clients))
        )
        self.delete = set()
        self.delete_by_instance = defaultdict(set)
        self.remove_from_qbit = set()
        self.remove_from_qbit_by_instance = defaultdict(set)
        self.skip_blacklist = set()
        self.missing_files_post_delete = set()
        self.downloads_with_bad_error_message_blocklist = set()
        self._log_deletion_summary_line = MagicMock()
        self._log_deletion_sample_debug = MagicMock()
        self._evict_hashes_from_qbit_side_caches = MagicMock()
        self._process_failed_dispatch_queue_deletes = MagicMock()

    def _get_qbit_client(self, instance):
        return self.clients.get(instance)

    def add(self, instance="one", private=True, **values):
        torrent = SimpleNamespace(
            hash="superman",
            name="Superman 2025 Hybrid",
            category="movies",
            progress=0.5416,
            ratio=0.000249,
            seeding_time=0,
            save_path="/downloads",
            added_on=1,
            last_activity=1,
            super_seeding=False,
            state_enum=qbittorrentapi.TorrentStates.DOWNLOADING,
            state="downloading",
            tags="",
        )
        torrent.__dict__.update(values)
        client = MagicMock()
        client.torrents_info.return_value = [torrent]
        client.torrents_properties.return_value = {"is_private": private}
        client.torrents_trackers.return_value = [tracker()]
        client.torrents_files.return_value = [SimpleNamespace(name="movie.mkv")]
        self.clients[instance] = client
        return torrent, client

    def _qbit_retry(self, fn, **kwargs):
        return fn()


class HnrRemovalTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "URI": "https://tracker.example",
            "HitAndRunMode": "and",
            "MinSeedRatio": 1,
            "MinSeedingTimeDays": 8,
            "HitAndRunMinimumDownloadPercent": 10,
            "HitAndRunPartialSeedRatio": 1,
            "TrackerUpdateBuffer": 3600,
        }
        self.seeding = {
            "default_seeding": {
                "HitAndRunMode": "disabled",
                "RemoveTorrent": 1,
                "MaxUploadRatio": 1,
                "MaxSeedingTime": 86400,
            },
            "stalled_delay": 0,
            "category_overrides": {},
            "trackers": [self.policy],
            "match_subcategories": False,
        }
        self.patch = patch(
            "qBitrr.qbit_seeding_config.load_qbit_seeding_config",
            side_effect=lambda *a, **k: self.seeding,
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.worker = Worker()
        self.torrent, self.client = self.worker.add()

    def allowed(self):
        return self.worker._hnr_allows_delete(
            self.torrent, "test", instance_name="one", client=self.client
        )

    def test_final_boundary_requires_every_protection(self):
        self.torrent.ratio = 2
        for key, value in (
            ("added_on", time.time()),
            ("last_activity", time.time()),
            ("tags", "qBitrr-ignored"),
            ("tags", "qBitrr-free_space_paused"),
            ("super_seeding", True),
        ):
            with self.subTest(key=key, value=value):
                old = getattr(self.torrent, key)
                setattr(self.torrent, key, value)
                self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
                self.client.torrents_delete.assert_not_called()
                setattr(self.torrent, key, old)
        self.seeding["default_seeding"]["RemoveTorrent"] = -1
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.client.torrents_delete.assert_not_called()

    def test_stalled_grace_and_complete_seeding_policy_are_mandatory(self):
        self.torrent.ratio = 2
        self.seeding["stalled_delay"] = -1
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.seeding["stalled_delay"] = 60
        self.torrent.last_activity = time.time() - 1800
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.torrent.progress = 1
        self.torrent.seeding_time = 0
        self.policy["HitAndRunMode"] = "disabled"
        self.torrent.is_private = False
        self.client.torrents_properties.return_value = {"is_private": False}
        self.seeding["default_seeding"]["RemoveTorrent"] = 4
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.seeding["default_seeding"]["RemoveTorrent"] = 3
        self.assertEqual(
            delete_hashes_per_instance(self.worker, {"one": {"superman"}}), {("one", "superman")}
        )

    def test_stale_pending_candidate_never_deletes_a_readded_or_active_torrent(self):
        from qBitrr.arss.qbit_side_effects import removal_candidate

        self.torrent.ratio = 2
        self.worker._removal_candidates = {("one", "superman"): removal_candidate(self.torrent)}
        self.torrent.added_on = 2
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.torrent.added_on = 1
        self.torrent.last_activity = 2
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.client.torrents_delete.assert_not_called()

    def test_new_pass_discards_blocked_requests_for_fresh_classification(self):
        self.worker.delete.add("superman")
        self.worker.delete_by_instance["one"].add("superman")
        self.worker._reset_removal_requests()
        self.worker._process_failed()
        self.client.torrents_delete.assert_not_called()
        self.assertFalse(self.worker.delete)
        self.assertFalse(self.worker.delete_by_instance)

    def test_custom_format_reason_is_rechecked_before_deletion(self):
        self.torrent.ratio = 2
        self.worker._removal_reasons = {("one", "superman"): "CF unmet deletion"}
        self.worker.custom_format_unmet_search = True
        self.worker.custom_format_unmet_check = lambda torrent: False
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.client.torrents_delete.assert_not_called()

    def test_actual_client_never_remove_cannot_use_another_clients_permission(self):
        self.torrent.ratio = 2
        self.worker._name = "placeholder"
        self.worker.category = "movies"
        self.seeding["default_seeding"]["RemoveTorrent"] = -1
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.client.torrents_delete.assert_not_called()
        self.seeding["default_seeding"]["RemoveTorrent"] = 1
        self.seeding["stalled_delay"] = 0
        self.assertEqual(
            delete_hashes_per_instance(self.worker, {"one": {"superman"}}), {("one", "superman")}
        )

    def test_completed_cleanup_uses_real_client_and_tracker_limit_merge(self):
        self.worker._name = "placeholder"
        self.worker.category = "movies"
        self.worker._get_torrent_limit_meta = (
            lambda torrent, **kwargs: TorrentLimits._get_torrent_limit_meta(
                self.worker, torrent, **kwargs
            )
        )
        self.torrent.progress = 1
        self.torrent.ratio = 2
        self.torrent.seeding_time = 9 * 86400
        self.seeding["default_seeding"].update(
            RemoveTorrent=1, MaxUploadRatio=4, MaxSeedingTime=3600
        )
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.seeding["trackers"][0]["MaxUploadRatio"] = 1
        self.assertEqual(
            delete_hashes_per_instance(self.worker, {"one": {"superman"}}), {("one", "superman")}
        )

    def test_shared_content_uses_owners_arr_hnr_policy(self):
        self.torrent.ratio = 2
        self.worker._name = "Radarr-Worker"
        self.worker.category = "films"
        settings = {
            "Radarr-Worker.Category": "films",
            "Sonarr-Owner.Category": "movies",
            "Sonarr-Owner.Torrent.Trackers": [{**self.policy, "HitAndRunPartialSeedRatio": 5}],
        }
        config = MagicMock()
        config.sections.return_value = ["Radarr-Worker", "Sonarr-Owner"]
        config.get.side_effect = lambda key, fallback=None: settings.get(key, fallback)
        with patch("qBitrr.config.CONFIG", config):
            self.assertFalse(self.allowed())
            self.assertFalse(content_removal_allowed(self.worker, [Path("/downloads/movie.mkv")]))
        self.client.torrents_delete.assert_not_called()

    def test_superman_cfunmet_cannot_remove_or_dispatch_arr_cleanup(self):
        self.worker.delete.add("superman")
        self.worker.delete_by_instance["one"].add("superman")
        self.worker._process_failed()
        self.client.torrents_delete.assert_not_called()
        self.worker._process_failed_dispatch_queue_deletes.assert_not_called()
        self.assertIn("superman", self.worker.delete_by_instance["one"])

    def test_partial_threshold_and_full_and_or_rules(self):
        self.torrent.progress = 0.0999
        self.assertTrue(self.allowed())
        self.torrent.progress = 0.10
        self.assertFalse(self.allowed())
        self.torrent.ratio = 1
        self.assertTrue(self.allowed())
        self.torrent.progress = 1
        self.assertFalse(self.allowed())
        self.policy["HitAndRunMode"] = "or"
        self.assertTrue(self.allowed())
        self.policy["HitAndRunMode"] = "and"
        self.torrent.seeding_time = 8 * 86400 + 3599
        self.assertFalse(self.allowed())
        self.torrent.seeding_time += 1
        self.assertTrue(self.allowed())

    def test_all_trackers_apply_despite_priority_or_remove_if_exists(self):
        self.seeding["trackers"].append(
            {**self.policy, "Priority": 999, "HitAndRunMode": "disabled"}
        )
        self.policy["RemoveIfExists"] = True
        self.assertFalse(self.allowed())

    def test_dead_or_unavailable_tracker_is_not_clearance(self):
        self.torrent.ratio = 100
        self.torrent.seeding_time = 99999999
        self.client.torrents_trackers.return_value = [
            tracker(status=4, msg="unregistered torrent")
        ]
        self.assertFalse(self.allowed())
        self.client.torrents_trackers.side_effect = RuntimeError("offline")
        self.assertFalse(self.allowed())

    def test_private_disabled_unknown_and_public(self):
        self.seeding["trackers"] = []
        self.assertFalse(self.allowed())
        self.client.torrents_properties.return_value = {}
        self.assertFalse(self.allowed())
        self.client.torrents_properties.return_value = {"is_private": False}
        self.assertTrue(self.allowed())

    def test_invalid_thresholds_do_not_allow_removal(self):
        self.policy["MinSeedRatio"] = float("nan")
        self.assertFalse(self.allowed())
        self.policy["MinSeedRatio"] = -1
        self.assertFalse(self.allowed())
        self.policy["MinSeedRatio"] = 1
        self.policy["HitAndRunMode"] = "invalid"
        self.assertFalse(self.allowed())

    def test_mode_validation_and_existing_case_insensitive_values(self):
        self.policy["HitAndRunMode"] = 0
        self.client.torrents_properties.return_value = {"is_private": False}
        self.assertFalse(self.allowed())
        self.policy["HitAndRunMode"] = " AND "
        self.assertFalse(self.allowed())
        self.torrent.ratio = 2
        self.assertTrue(self.allowed())

    def test_category_override_applies_and_duration_is_preserved(self):
        self.seeding["trackers"] = []
        self.seeding["category_overrides"] = {
            "movies": {**self.policy, "MinSeedingTimeDays": "8d"}
        }
        self.assertFalse(self.allowed())
        self.torrent.progress = 1
        self.torrent.ratio = 2
        self.torrent.seeding_time = 8 * 86400 + 3600
        self.assertTrue(self.allowed())

    def test_unique_eligible_removal_and_ambiguous_legacy_owner(self):
        self.torrent.ratio = 2
        self.assertEqual(
            delete_hashes_on_primary(self.worker, {"superman"}), {("one", "superman")}
        )
        self.client.torrents_delete.assert_called_once()
        self.worker.add("two", ratio=2)
        self.assertEqual(delete_hashes_on_primary(self.worker, {"superman"}), set())

    def test_same_hash_on_other_client_remains_protected_and_pending(self):
        self.torrent.ratio = 2
        self.worker.add("two")
        self.worker.delete_by_instance = {"one": {"superman"}, "two": {"superman"}}
        self.worker.delete = {"superman"}
        # Isolate client-removal bookkeeping; shared-file HnR is tested separately.
        with patch("qBitrr.arss.qbit_side_effects.content_removal_allowed", return_value=True):
            self.worker._process_failed()
        self.assertNotIn("one", self.worker.delete_by_instance)
        self.assertEqual(self.worker.delete_by_instance["two"], {"superman"})
        self.assertIn("superman", self.worker.delete)
        self.worker._process_failed_dispatch_queue_deletes.assert_not_called()

    def test_other_protected_owner_blocks_content_deletion(self):
        self.torrent.ratio = 2
        self.worker.add("two")
        self.assertFalse(content_removal_allowed(self.worker, [Path("/downloads/movie.mkv")]))
        self.assertEqual(delete_hashes_per_instance(self.worker, {"one": {"superman"}}), set())
        self.client.torrents_delete.assert_not_called()

    def test_legacy_default_bucket_resolves_a_unique_actual_client(self):
        self.torrent.ratio = 2
        self.worker.delete_by_instance = {"default": {"superman"}}
        self.worker.delete.add("superman")
        self.worker._process_failed()
        self.client.torrents_delete.assert_called_once()
        self.assertFalse(self.worker.delete_by_instance)
        self.assertFalse(self.worker.delete)

    def test_unsafe_file_paths_block_client_and_content_removal(self):
        self.torrent.ratio = 2
        self.client.torrents_files.return_value = [SimpleNamespace(name="../outside")]
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.client.torrents_delete.assert_not_called()

    def test_each_client_uses_its_own_rules(self):
        self.torrent.ratio = 2
        other, client = self.worker.add("two", ratio=2)
        with patch(
            "qBitrr.qbit_seeding_config.load_qbit_seeding_config",
            side_effect=lambda instance, **kwargs: {
                **self.seeding,
                "trackers": [
                    {**self.policy, "HitAndRunPartialSeedRatio": 1 if instance == "one" else 3}
                ],
            },
        ):
            self.assertTrue(self.allowed())
            self.assertFalse(
                self.worker._hnr_allows_delete(other, "test", instance_name="two", client=client)
            )

    def test_tracker_cleanup_cannot_erase_an_outstanding_obligation(self):
        from qBitrr.arss.torrent_dispatch import TorrentDispatch

        self.worker.tracker_delay = set()
        self.worker._get_torrent_important_trackers = lambda *a, **k: (set(), set())
        self.worker._get_most_important_tracker_and_tags = lambda *a: ({}, set())
        self.worker.remove_dead_trackers = True
        self.worker._normalized_bad_tracker_msgs = ["unregistered"]
        self.worker._remove_tracker_hosts = set()
        self.worker.seeding_mode_global_download_limit = 0
        self.worker.seeding_mode_global_upload_limit = 0
        self.torrent.trackers = [tracker(status=4, msg="unregistered torrent")]
        self.torrent.dl_limit = self.torrent.up_limit = 0
        self.torrent.remove_trackers = MagicMock()
        TorrentDispatch._process_single_torrent_trackers(
            self.worker, self.torrent, "one", frozenset()
        )
        self.torrent.remove_trackers.assert_not_called()

    def test_retry_rechecks_new_obligations(self):
        self.torrent.ratio = 2

        def delete(**kwargs):
            self.torrent.ratio = 0
            raise qbittorrentapi.exceptions.APIError("retry")

        self.client.torrents_delete.side_effect = delete

        def retry(fn, **kwargs):
            try:
                return fn()
            except qbittorrentapi.exceptions.APIError:
                return fn()

        self.worker._qbit_retry = retry
        self.assertEqual(delete_hashes_per_instance(self.worker, {"one": {"superman"}}), set())
        self.client.torrents_delete.assert_called_once()

    def test_queue_deletion_cannot_delegate_removal_to_arr(self):
        arr = ArrBase.__new__(ArrBase)
        arr.cache = {}
        arr.client = MagicMock()
        self.assertFalse(arr.delete_from_queue(1, remove_from_client=True))
        arr.client.queue.delete.assert_not_called()

    def test_error_cleanup_preserves_blocked_iterator_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "movie.mkv"
            path.write_text("keep")
            arr = ArrBase.__new__(ArrBase)
            arr.files_to_explicitly_delete = iter([("superman", path)])
            arr.remove_and_maybe_blocklist = MagicMock(return_value=False)
            arr.post_download_error_cleanup()
            self.assertEqual(list(arr.files_to_explicitly_delete), [("superman", path)])
            self.assertTrue(path.exists())

    def test_cleanup_resolves_download_hash_to_arr_queue_id_after_clearance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "movie.mkv"
            path.write_text("keep")
            arr = ArrBase.__new__(ArrBase)
            arr.completed_folder = Path(directory)
            arr.cache = {"SUPERMAN": 17}
            arr.delete_from_queue = MagicMock()
            with (
                patch(
                    "qBitrr.arss.qbit_side_effects.resolve_removal_torrent",
                    return_value=("one", self.client, self.torrent),
                ),
                patch(
                    "qBitrr.arss.qbit_side_effects.delete_hashes_per_instance", return_value=set()
                ) as deletion,
            ):
                self.assertFalse(arr.remove_and_maybe_blocklist("superman", path))
                arr.delete_from_queue.assert_not_called()
                self.assertTrue(path.exists())
                deletion.return_value = {("one", "SUPERMAN")}
                self.assertTrue(arr.remove_and_maybe_blocklist("superman", path))
                arr.delete_from_queue.assert_called_once_with(
                    id_=17, remove_from_client=False, blacklist=True
                )

    def test_cleanup_cannot_escape_the_completed_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            arr = ArrBase.__new__(ArrBase)
            arr.completed_folder = Path(directory) / "owned"
            outside = Path(directory) / "keep.mkv"
            outside.write_text("keep")
            self.assertFalse(arr.remove_and_maybe_blocklist(None, outside))
            self.assertTrue(outside.exists())

    def test_protected_file_cleanup_keeps_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "movie.mkv"
            path.write_text("keep")
            self.torrent.save_path = directory
            self.assertFalse(content_removal_allowed(self.worker, [path]))
            self.assertTrue(path.exists())
