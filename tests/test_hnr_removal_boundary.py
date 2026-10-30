"""HnR is a mandatory veto for client removal and referenced content cleanup."""

from __future__ import annotations

import logging
import re
import tempfile
import time
import unittest
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import qbittorrentapi

from qBitrr.arss.arr_base import ArrBase
from qBitrr.arss.qbit_side_effects import (
    content_removal_allowed,
    delete_hashes_on_primary,
    delete_hashes_per_instance,
    is_metadata_only_torrent,
)
from qBitrr.arss.torrent_batch import TorrentBatch
from qBitrr.arss.torrent_dispatch import TorrentDispatch
from qBitrr.arss.torrent_inspect import TorrentInspect
from qBitrr.arss.torrent_limits import TorrentLimits


def tracker(url="https://tracker.example/announce", status=2, msg=""):
    """Build an isolated tracker response for removal-clearance tests."""
    return SimpleNamespace(url=url, status=status, msg=msg)


class Worker(TorrentLimits, TorrentBatch, TorrentDispatch, TorrentInspect):
    def __init__(self):
        """Initialize a worker with mocked side effects and explicit removal state."""
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
            qbit_manager=SimpleNamespace(
                get_all_instances=lambda: list(self.clients), name_cache={}
            )
        )
        self.delete = set()
        self.delete_by_instance = defaultdict(set)
        self.remove_from_qbit = set()
        self.remove_from_qbit_by_instance = defaultdict(set)
        self.skip_blacklist = set()
        self.missing_files_post_delete = set()
        self.downloads_with_bad_error_message_blocklist = set()
        self.cache = {}
        self.requeue_cache = {}
        self.re_search = False
        self._log_deletion_summary_line = MagicMock()
        self._log_deletion_sample_debug = MagicMock()
        self._evict_hashes_from_qbit_side_caches = MagicMock()
        self._process_failed_dispatch_queue_deletes = MagicMock()

    def _get_qbit_client(self, instance):
        """Return the mocked client registered for this instance."""
        return self.clients.get(instance)

    def add(self, instance="one", private=True, **values):
        """Register a mock client and torrent with overridable accounting fields."""
        torrent = SimpleNamespace(
            hash="superman",
            name="Superman 2025 Hybrid",
            category="movies",
            progress=0.5416,
            downloaded=1024,
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
        """Run a mocked client action without sleeping."""
        return fn()


class HnrRemovalTests(unittest.TestCase):
    def setUp(self):
        """Install isolated seeding policy and client fixtures for each test."""
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
        """Evaluate HnR clearance against the current mocked client and policy."""
        return self.worker._hnr_allows_delete(
            self.torrent, "test", instance_name="one", client=self.client
        )

    def test_final_boundary_requires_every_protection(self):
        """Verify final boundary requires every protection."""
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
        """Verify stalled grace and complete seeding policy are mandatory."""
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

    def test_candidate_rejects_readded_torrent_but_revalidates_activity(self):
        """Verify candidate rejects readded torrent but revalidates activity."""
        from qBitrr.arss.qbit_side_effects import removal_candidate

        self.torrent.ratio = 2
        self.worker._removal_candidates = {("one", "superman"): removal_candidate(self.torrent)}
        self.torrent.added_on = 2
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.torrent.added_on = 1
        self.torrent.last_activity = time.time()
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.client.torrents_delete.assert_not_called()
        self.torrent.last_activity = 2
        self.assertEqual(
            delete_hashes_per_instance(self.worker, {"one": {"superman"}}), {("one", "superman")}
        )

    def test_arr_owner_uses_exact_then_longest_prefix_and_all_section_names(self):
        """Verify arr owner uses exact then longest prefix and all section names."""
        settings = {
            "radarr.Managed": True,
            "Radarr4K.Managed": True,
            "radarr.Category": "movies",
            "Radarr4K.Category": "movies/4k",
            "one.MatchSubcategories": True,
        }
        config = MagicMock()
        config.sections.return_value = ["radarr", "Radarr4K"]
        config.get.side_effect = lambda key, fallback=None: settings.get(key, fallback)
        with patch("qBitrr.config.CONFIG", config):
            for category, expected in (
                ("movies", "radarr"),
                ("movies/4k", "Radarr4K"),
                ("movies/4k/new", "Radarr4K"),
                ("unrelated", None),
            ):
                self.torrent.category = category
                self.assertEqual(self.worker._removal_arr_section(self.torrent, "one"), expected)
            settings["Radarr4K.MatchSubcategories"] = False
            self.assertEqual(self.worker._removal_arr_section(self.torrent, "one"), None)
            self.torrent.category = "movies/4k/new"
            self.assertEqual(self.worker._removal_arr_section(self.torrent, "one"), "radarr")
            settings["Radarr4K.Category"] = "movies"
            self.torrent.category = "movies"
            with self.assertRaises(ValueError):
                self.worker._removal_arr_section(self.torrent, "one")

    def test_qbit_managed_children_take_precedence_over_parent_arr(self) -> None:
        """Resolve exact and longest-prefix ownership across Arr and qBit categories."""
        settings = {
            "Radarr-Parent.Managed": True,
            "Radarr-Parent.Category": "movies",
            "Radarr-Parent.MatchSubcategories": True,
            "Radarr-Parent.Torrent.SeedingMode": {"RemoveTorrent": -1},
            "qBit.ManagedCategories": [" movies/4k/ "],
            "qBit-Other.ManagedCategories": ["movies/4k"],
            "qBit.MatchSubcategories": False,
        }
        config = MagicMock()
        config.sections.return_value = ["Radarr-Parent", "qBit", "qBit-Other"]
        config.get.side_effect = lambda key, fallback=None: settings.get(key, fallback)
        config.get_duration.side_effect = lambda key, fallback=0, **kwargs: fallback
        self.torrent.category = "movies/4k"
        self.torrent.progress = 1
        self.torrent.ratio = 2
        self.torrent.seeding_time = 9 * 86400
        with patch("qBitrr.config.CONFIG", config):
            self.assertIsNone(self.worker._removal_arr_section(self.torrent, "qBit"))
            self.assertTrue(
                self.worker._deletion_rules_allow(
                    self.torrent, "test", instance_name="qBit", client=self.client
                )
            )
            self.torrent.category = "movies/4k/new"
            self.assertEqual(
                self.worker._removal_arr_section(self.torrent, "qBit"), "Radarr-Parent"
            )
            settings["qBit.MatchSubcategories"] = True
            self.assertIsNone(self.worker._removal_arr_section(self.torrent, "qBit"))
            settings.update(
                {
                    "Sonarr-Child.Managed": True,
                    "Sonarr-Child.Category": "movies/4k/new",
                    "Sonarr-Child.MatchSubcategories": True,
                }
            )
            config.sections.return_value.append("Sonarr-Child")
            self.assertEqual(
                self.worker._removal_arr_section(self.torrent, "qBit"), "Sonarr-Child"
            )
            self.torrent.category = "movies/4k/new/deeper"
            self.assertEqual(
                self.worker._removal_arr_section(self.torrent, "qBit"), "Sonarr-Child"
            )

    def test_arr_tracker_override_applies_to_ordinary_limits_only(self):
        """Verify arr tracker override applies to ordinary limits only."""
        self.torrent.progress = 1
        self.torrent.ratio = 2
        self.torrent.seeding_time = 9 * 86400
        self.seeding["trackers"][0]["MaxUploadRatio"] = 10
        self.worker._get_torrent_limit_meta = lambda torrent, **kwargs: (
            TorrentLimits._get_torrent_limit_meta(self.worker, torrent, **kwargs)
        )
        settings = {
            "Radarr4K.Managed": True,
            "Radarr4K.Category": "movies",
            "Radarr4K.Torrent.SeedingMode": {"RemoveTorrent": 1},
            "Radarr4K.Torrent.Trackers": [{**self.policy, "MaxUploadRatio": 1}],
        }
        config = MagicMock()
        config.sections.return_value = ["Radarr4K"]
        config.get.side_effect = lambda key, fallback=None: settings.get(key, fallback)
        config.get_duration.side_effect = lambda key, fallback=0, **kwargs: fallback
        with patch("qBitrr.config.CONFIG", config):
            self.assertTrue(
                self.worker._deletion_rules_allow(
                    self.torrent, "test", instance_name="one", client=self.client
                )
            )
            self.seeding["trackers"][0]["MinSeedRatio"] = 10
            self.assertFalse(self.allowed())

    def test_older_qbit_privacy_uses_localized_discovery_rows(self):
        """Verify older qbit privacy uses localized discovery rows."""
        self.client.torrents_properties.return_value = {}
        self.torrent.ratio = 2
        for message, private in (("", False), ("Ce torrent est privé", True)):
            self.client.torrents_trackers.return_value = [tracker()] + [
                tracker(url=f"** [{kind}] **", status=0, msg=message)
                for kind in ("DHT", "PeX", "LSD")
            ]
            self.assertTrue(self.allowed())
            self.seeding["trackers"] = []
            self.assertEqual(self.allowed(), not private)
            self.seeding["trackers"] = [self.policy]
        self.torrent.state_enum = qbittorrentapi.TorrentStates.METADATA_DOWNLOAD
        self.assertFalse(self.allowed())
        self.torrent.state_enum = qbittorrentapi.TorrentStates.DOWNLOADING
        self.client.torrents_trackers.return_value.pop()
        self.assertFalse(self.allowed())

    def test_expired_metadata_dispatch_removes_client_and_confirms_arr_followups(self) -> None:
        """Dispatch both empty-magnet states after positive stalled grace expires."""
        self.torrent.progress = 0
        self.torrent.downloaded = 0
        self.torrent.added_on = time.time() - 1200
        self.torrent.last_activity = time.time()
        self.worker.logger = MagicMock()
        self.worker.stalled_delay = 15
        self.worker.allowed_stalled = True
        self.worker.custom_format_unmet_search = False
        self.worker.in_tags = MagicMock(return_value=False)
        self.worker._should_leave_alone = MagicMock(return_value=(False, -1, False, None, None))
        self.worker.manager.qbit_manager.cache = {}
        self.worker.manager.policy_manager_owns_tracker_sync_for_category = MagicMock(
            return_value=True
        )
        self.seeding["stalled_delay"] = 15
        self.client.torrents_files.return_value = []
        self.client.torrents_properties.return_value = {}
        self.client.torrents_trackers.side_effect = RuntimeError("No tracker metadata")
        for state in (
            qbittorrentapi.TorrentStates.METADATA_DOWNLOAD,
            qbittorrentapi.TorrentStates.FORCED_METADATA_DOWNLOAD,
        ):
            with self.subTest(state=state):
                self.torrent.state_enum = state
                self.client.torrents_delete.reset_mock()
                self.worker._process_failed_dispatch_queue_deletes.reset_mock()
                self.assertFalse(self.worker.delete)
                self.assertFalse(self.worker.delete_by_instance)
                self.worker._process_single_torrent(self.torrent, "one")
                self.assertEqual(self.worker.delete, {"superman"})
                self.assertEqual(self.worker.delete_by_instance, {"one": {"superman"}})
                self.worker._process_failed()
                self.client.torrents_delete.assert_called_once_with(
                    hashes=["superman"], delete_files=False
                )
                self.worker._process_failed_dispatch_queue_deletes.assert_called_once_with(
                    {"superman"}, set(), cross_arr=False
                )
                self.assertNotIn("one", self.worker.delete_by_instance)
        self.client.torrents_properties.assert_not_called()
        self.client.torrents_trackers.assert_not_called()

    def test_metadata_only_removal_preserves_age_stall_and_never_remove_rules(self) -> None:
        """Having no payload does not authorize early or disabled torrent removal."""
        self.torrent.state_enum = qbittorrentapi.TorrentStates.METADATA_DOWNLOAD
        self.torrent.progress = 0
        self.torrent.downloaded = 0
        self.client.torrents_files.return_value = []
        for values, policy in (
            ({"added_on": time.time()}, {}),
            ({"added_on": time.time() - 3600}, {"StalledDelay": 240}),
            ({"added_on": 1}, {"StalledDelay": -1}),
            ({"added_on": 1}, {"RemoveTorrent": -1}),
            ({"added_on": 1, "tags": "qBitrr-ignored"}, {}),
        ):
            with self.subTest(values=values, policy=policy):
                self.torrent.__dict__.update(values)
                original = dict(self.seeding["default_seeding"])
                self.seeding["default_seeding"].update(policy)
                self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
                self.client.torrents_delete.assert_not_called()
                self.seeding["default_seeding"] = original

    def test_metadata_only_requires_verified_empty_payload(self) -> None:
        """Unknown accounting, ordinary states, and nonempty file lists stay protected."""
        self.torrent.state_enum = qbittorrentapi.TorrentStates.METADATA_DOWNLOAD
        self.torrent.progress = 0
        self.torrent.downloaded = 0
        self.client.torrents_files.return_value = []
        self.assertTrue(is_metadata_only_torrent(self.client, self.torrent))
        for key, value in (
            ("downloaded", None),
            ("downloaded", False),
            ("downloaded", -1),
            ("downloaded", 1),
            ("progress", 0.1),
            ("progress", False),
            ("state_enum", qbittorrentapi.TorrentStates.DOWNLOADING),
        ):
            with self.subTest(key=key, value=value):
                original = getattr(self.torrent, key)
                setattr(self.torrent, key, value)
                self.assertFalse(is_metadata_only_torrent(self.client, self.torrent))
                setattr(self.torrent, key, original)
        for files in (None, [SimpleNamespace(name="movie.mkv")]):
            self.client.torrents_files.return_value = files
            self.assertFalse(is_metadata_only_torrent(self.client, self.torrent))
        self.client.torrents_files.side_effect = RuntimeError("Unavailable files")
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.client.torrents_delete.assert_not_called()

    def test_metadata_only_candidate_rechecks_new_metadata_before_removal(self) -> None:
        """Do not use metadata-only clearance after metadata or payload appears."""
        self.torrent.state_enum = qbittorrentapi.TorrentStates.METADATA_DOWNLOAD
        self.torrent.progress = 0
        self.torrent.downloaded = 0
        self.client.torrents_files.return_value = []
        replacement = SimpleNamespace(**vars(self.torrent))
        replacement.state_enum = qbittorrentapi.TorrentStates.DOWNLOADING
        self.client.torrents_info.side_effect = [[self.torrent], [replacement]]
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.client.torrents_delete.assert_not_called()
        self.client.torrents_info.side_effect = None
        self.client.torrents_files.side_effect = [[], [], [SimpleNamespace(name="movie.mkv")]]
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.client.torrents_delete.assert_not_called()

    def test_metadata_only_peer_does_not_veto_shared_folder_cleanup(self) -> None:
        """Ignore empty magnets on another client while retaining real file owners."""
        self.torrent.ratio = 2
        other, client = self.worker.add(
            "two",
            hash="magnet",
            progress=0,
            downloaded=0,
            state_enum=qbittorrentapi.TorrentStates.METADATA_DOWNLOAD,
        )
        client.torrents_files.return_value = []
        targets = [Path("/downloads/movie.mkv")]
        self.assertTrue(content_removal_allowed(self.worker, targets))
        other.downloaded = 1
        self.assertFalse(content_removal_allowed(self.worker, targets))
        other.downloaded = 0
        other.progress = 0.5
        client.torrents_files.return_value = [SimpleNamespace(name="movie.mkv")]
        self.assertFalse(content_removal_allowed(self.worker, targets))

    def test_unrelated_metadata_and_unsafe_files_do_not_veto_content_cleanup(self):
        """Verify unrelated metadata and unsafe files do not veto content cleanup."""
        self.torrent.ratio = 2
        other, client = self.worker.add("two", save_path="/other")
        for files in ([], [SimpleNamespace(name="../unsafe")]):
            client.torrents_files.return_value = files
            self.assertTrue(content_removal_allowed(self.worker, [Path("/downloads/movie.mkv")]))
            client.torrents_files.assert_not_called()
            other.save_path = "/downloads"
            self.assertFalse(content_removal_allowed(self.worker, [Path("/downloads/movie.mkv")]))
            other.save_path = "/other"
            client.torrents_files.reset_mock()

    def test_confirmed_queue_cleanup_retries_after_torrent_and_cache_disappear(self):
        """Verify confirmed queue cleanup retries after torrent and cache disappear."""
        self.torrent.ratio = 2
        self.worker.delete.add("superman")
        self.worker.delete_by_instance["one"].add("superman")
        self.worker.cache = {"SUPERMAN": 17}
        self.worker.requeue_cache = {17: 42}
        self.worker.re_search = True
        self.worker.process_entries = lambda hashes: ArrBase.process_entries(self.worker, hashes)
        self.worker._process_failed_dispatch_queue_deletes = lambda *a, **kw: (
            TorrentBatch._process_failed_dispatch_queue_deletes(self.worker, *a, **kw)
        )
        self.worker.delete_from_queue = MagicMock(side_effect=[RuntimeError("offline"), None])
        self.worker._re_search_failed_media = MagicMock(
            side_effect=[RuntimeError("offline"), None]
        )
        self.worker._process_failed()
        self.assertIn(17, self.worker._pending_queue_deletes)
        self.client.torrents_info.return_value = []
        self.worker.cache.clear()
        self.worker.requeue_cache.clear()
        self.worker._reset_removal_requests()
        self.assertIn(17, self.worker._pending_queue_deletes)
        self.worker.delete_from_queue.side_effect = None
        self.worker._process_failed()
        self.assertFalse(self.worker._pending_queue_deletes)
        self.worker._re_search_failed_media.assert_called_with(42)
        self.client.torrents_delete.assert_called_once()

    def test_placeholder_scan_retries_arr_cleanup_before_empty_torrent_shortcut(self):
        """Retry confirmed Arr work even after the placeholder category becomes empty."""
        arr = MagicMock()
        self.worker.manager.managed_objects = {"movies": arr}
        self.worker._reset_removal_requests(cross_arr=True)
        arr._retry_pending_queue_deletes.assert_called_once()

    def test_new_pass_discards_blocked_requests_for_fresh_classification(self):
        """Verify new pass discards blocked requests for fresh classification."""
        self.worker.delete.add("superman")
        self.worker.delete_by_instance["one"].add("superman")
        self.worker._reset_removal_requests()
        self.worker._process_failed()
        self.client.torrents_delete.assert_not_called()
        self.assertFalse(self.worker.delete)
        self.assertFalse(self.worker.delete_by_instance)

    def test_custom_format_reason_is_rechecked_before_deletion(self):
        """Verify custom format reason is rechecked before deletion."""
        self.torrent.ratio = 2
        self.worker._removal_reasons = {("one", "superman"): "CF unmet deletion"}
        self.worker.custom_format_unmet_search = True
        self.worker.custom_format_unmet_check = lambda torrent: False
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.client.torrents_delete.assert_not_called()

    def test_actual_client_never_remove_cannot_use_another_clients_permission(self):
        """Verify actual client never remove cannot use another clients permission."""
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
        """Verify completed cleanup uses real client and tracker limit merge."""
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
        """Verify shared content uses owners arr hnr policy."""
        self.torrent.ratio = 2
        self.worker._name = "Radarr-Worker"
        self.worker.category = "films"
        settings = {
            "Radarr-Worker.Managed": True,
            "Sonarr-Owner.Managed": True,
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
        """Verify superman cfunmet cannot remove or dispatch arr cleanup."""
        self.worker.delete.add("superman")
        self.worker.delete_by_instance["one"].add("superman")
        self.worker._process_failed()
        self.client.torrents_delete.assert_not_called()
        self.worker._process_failed_dispatch_queue_deletes.assert_not_called()
        self.assertIn("superman", self.worker.delete_by_instance["one"])

    def test_partial_threshold_and_full_and_or_rules(self):
        """Verify partial threshold and full and or rules."""
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
        """Verify all trackers apply despite priority or remove if exists."""
        self.seeding["trackers"].append(
            {**self.policy, "Priority": 999, "HitAndRunMode": "disabled"}
        )
        self.policy["RemoveIfExists"] = True
        self.assertFalse(self.allowed())

    def test_dead_or_unavailable_tracker_is_not_clearance(self):
        """Verify dead or unavailable tracker is not clearance."""
        self.torrent.ratio = 100
        self.torrent.seeding_time = 99999999
        self.client.torrents_trackers.return_value = [
            tracker(status=4, msg="unregistered torrent")
        ]
        self.assertFalse(self.allowed())
        self.client.torrents_trackers.side_effect = RuntimeError("offline")
        self.assertFalse(self.allowed())

    def test_private_disabled_unknown_and_public(self):
        """Verify private disabled unknown and public."""
        self.seeding["trackers"] = []
        self.assertFalse(self.allowed())
        self.client.torrents_properties.return_value = {}
        self.assertFalse(self.allowed())
        self.client.torrents_properties.return_value = {"is_private": False}
        self.assertTrue(self.allowed())

    def test_verified_public_trackerless_torrents_keep_category_protections(self) -> None:
        """Clear public DHT-only torrents while retaining category and privacy vetoes."""
        self.client.torrents_properties.return_value = {"is_private": False}
        self.torrent.progress = 1
        self.torrent.ratio = 2
        self.torrent.seeding_time = 9 * 86400
        for trackers in (
            [],
            [tracker(url=f"** [{kind}] **", msg="") for kind in ("DHT", "PeX", "LSD")],
        ):
            with self.subTest(trackers=trackers):
                self.client.torrents_trackers.return_value = trackers
                self.seeding["category_overrides"] = {}
                self.assertTrue(self.allowed())
                self.assertTrue(
                    content_removal_allowed(self.worker, [Path("/downloads/movie.mkv")])
                )
                self.assertEqual(
                    delete_hashes_per_instance(self.worker, {"one": {"superman"}}),
                    {("one", "superman")},
                )
                self.seeding["category_overrides"] = {"movies": {**self.policy, "MinSeedRatio": 3}}
                self.assertFalse(self.allowed())
                self.torrent.ratio = 3
                self.assertTrue(self.allowed())
                self.torrent.ratio = 2
                self.client.torrents_properties.return_value = {"is_private": True}
                self.assertFalse(self.allowed())
                self.client.torrents_properties.return_value = {"is_private": False}
        self.client.torrents_properties.return_value = {}
        self.client.torrents_trackers.return_value = []
        self.assertFalse(self.allowed())
        self.client.torrents_properties.return_value = {"is_private": False}
        self.client.torrents_trackers.side_effect = RuntimeError("offline")
        self.assertFalse(self.allowed())

    def test_unmanaged_sections_do_not_own_removal_policies(self) -> None:
        """Ignore unmanaged duplicate categories and unmanaged qBit category owners."""
        settings = {
            "Radarr-Active.Managed": True,
            "Radarr-Active.Category": "movies",
            "Radarr-Old.Managed": False,
            "Radarr-Old.Category": "movies",
        }
        config = MagicMock()
        config.sections.return_value = ["Radarr-Old", "Radarr-Active"]
        config.get.side_effect = lambda key, fallback=None: settings.get(key, fallback)
        with patch("qBitrr.config.CONFIG", config):
            self.assertEqual(
                self.worker._removal_arr_section(self.torrent, "one"), "Radarr-Active"
            )
            settings["Radarr-Active.Managed"] = False
            self.assertIsNone(self.worker._removal_arr_section(self.torrent, "one"))

    def test_removal_age_uses_environment_fallback_and_explicit_client_age(self) -> None:
        """Honor the effective global age without weakening explicit client/category overrides."""
        self.patch.stop()
        from qBitrr.qbit_seeding_config import load_qbit_seeding_config

        settings = {"one.CategorySeeding.RemoveTorrent": 1}
        durations = {
            "Settings.IgnoreTorrentsYoungerThan": 86400,
            "one.CategorySeeding.StalledDelay": 0,
        }
        config = MagicMock()
        config.sections.return_value = []
        config.get.side_effect = lambda key, fallback=None: settings.get(key, fallback)
        config.get_duration.side_effect = lambda key, fallback=0, **kwargs: durations.get(
            key, fallback
        )
        env = SimpleNamespace(settings=SimpleNamespace(ignore_torrents_younger_than=180))
        self.torrent.added_on = self.torrent.last_activity = time.time() - 600
        self.client.torrents_properties.return_value = {"is_private": False}
        with (
            patch("qBitrr.config.CONFIG", config),
            patch("qBitrr.qbit_seeding_config.CONFIG", config),
            patch("qBitrr.config.ENVIRO_CONFIG", env),
        ):
            self.assertEqual(load_qbit_seeding_config("one")["ignore_torrents_younger_than"], 180)
            self.assertTrue(
                self.worker._deletion_rules_allow(
                    self.torrent, "test", instance_name="one", client=self.client
                )
            )
            durations["one.CategorySeeding.IgnoreTorrentsYoungerThan"] = 1800
            self.assertFalse(
                self.worker._deletion_rules_allow(
                    self.torrent, "test", instance_name="one", client=self.client
                )
            )
            durations.pop("one.CategorySeeding.IgnoreTorrentsYoungerThan")
            settings["one.CategorySeeding.Categories"] = [
                {"Name": "movies", "IgnoreTorrentsYoungerThan": 1800}
            ]
            self.assertFalse(
                self.worker._deletion_rules_allow(
                    self.torrent, "test", instance_name="one", client=self.client
                )
            )

    def test_lost_delete_response_is_confirmed_on_retry(self) -> None:
        """A successful absence lookup after a sent delete preserves Arr follow-up work."""
        self.torrent.ratio = 2
        self.worker.cache = {"SUPERMAN": 17}
        self.worker.requeue_cache = {17: 42}
        followups = self.worker._removal_queue_followups({"superman"}, set())

        def delete(**kwargs: object) -> None:
            """Remove the torrent but lose the client's response."""
            self.client.torrents_info.return_value = []
            raise qbittorrentapi.exceptions.APIConnectionError("response lost")

        def retry(fn: Callable[[], bool], **kwargs: object) -> bool:
            """Retry the failed deletion without waiting."""
            try:
                return fn()
            except qbittorrentapi.exceptions.APIConnectionError:
                return fn()

        self.client.torrents_delete.side_effect = delete
        self.worker._qbit_retry = retry
        self.assertEqual(
            delete_hashes_per_instance(
                self.worker, {"one": {"superman"}}, queue_followups=followups
            ),
            {("one", "superman")},
        )
        self.client.torrents_delete.assert_called_once()
        self.worker._reset_removal_requests()
        # No Arr API fake exists here: confirmation queues the saved work for retry.
        self.assertEqual(self.worker._pending_queue_deletes[17], ("SUPERMAN", False, 42))

    def test_lost_delete_response_survives_offline_scans_and_lost_arr_cache(self) -> None:
        """Keep uncertain client deletion and original media IDs until a successful absence lookup."""
        self.torrent.ratio = 2
        self.worker.delete = {"superman"}
        self.worker.delete_by_instance["one"].add("superman")
        self.worker.cache = {"SUPERMAN": 17}
        self.worker.requeue_cache = {17: 42}
        self.worker.re_search = True
        self.worker.delete_from_queue = MagicMock()
        self.worker._re_search_failed_media = MagicMock()

        def delete(**kwargs: object) -> None:
            """Lose the deletion response and all subsequent client lookups."""
            self.client.torrents_info.side_effect = qbittorrentapi.exceptions.APIConnectionError(
                "offline"
            )
            self.client.torrents_info.return_value = []
            raise qbittorrentapi.exceptions.APIConnectionError("response lost")

        self.client.torrents_delete.side_effect = delete
        self.worker._process_failed()
        self.worker.cache.clear()
        self.worker.requeue_cache.clear()
        self.worker._reset_removal_requests()
        self.assertTrue(self.worker._pending_client_removals)
        self.worker.delete_from_queue.assert_not_called()
        self.client.torrents_info.side_effect = None
        self.worker._reset_removal_requests()
        self.worker.delete_from_queue.assert_called_once_with(
            id_=17, remove_from_client=False, blacklist=True
        )
        self.worker._re_search_failed_media.assert_called_once_with(42)
        self.assertFalse(self.worker._pending_client_removals)
        self.client.torrents_delete.assert_called_once()

    def test_uncertain_delete_does_not_cleanup_readded_or_other_targeted_torrent(self) -> None:
        """Require all targeted clients to be absent and reject a re-added incarnation."""
        self.torrent.ratio = 2
        self.worker.add("two", ratio=0)
        self.worker.delete_by_instance = {"one": {"superman"}, "two": {"superman"}}
        self.worker.cache = {"SUPERMAN": 17}
        followups = self.worker._removal_queue_followups({"superman"}, set())

        def delete(**kwargs: object) -> None:
            """Lose the response after deleting from only one of the targeted clients."""
            self.client.torrents_info.return_value = []
            raise qbittorrentapi.exceptions.APIConnectionError("response lost")

        self.client.torrents_delete.side_effect = delete
        with patch("qBitrr.arss.qbit_side_effects.content_removal_allowed", return_value=True):
            delete_hashes_per_instance(
                self.worker, {"one": {"superman"}}, queue_followups=followups
            )
        self.worker._reset_removal_requests()
        self.assertTrue(self.worker._pending_client_removals)
        self.assertFalse(getattr(self.worker, "_pending_queue_deletes", {}))
        self.torrent.added_on = 2
        self.client.torrents_info.return_value = [self.torrent]
        self.worker._reset_removal_requests()
        self.assertFalse(self.worker._pending_client_removals)
        self.assertFalse(getattr(self.worker, "_pending_queue_deletes", {}))

    def test_confirmed_partial_batch_waits_for_all_targeted_clients(self) -> None:
        """Keep saved queue work until every targeted copy has disappeared."""
        self.torrent.ratio = 2
        _, other_client = self.worker.add("two", ratio=0)
        self.worker.delete_by_instance = {"one": {"superman"}, "two": {"superman"}}
        self.worker.cache = {"SUPERMAN": 17}
        followups = self.worker._removal_queue_followups({"superman"}, set())
        with patch("qBitrr.arss.qbit_side_effects.content_removal_allowed", return_value=True):
            self.assertEqual(
                delete_hashes_per_instance(
                    self.worker, {"one": {"superman"}}, queue_followups=followups
                ),
                {("one", "superman")},
            )
        self.client.torrents_info.return_value = []
        self.worker._reset_removal_requests()
        self.assertTrue(self.worker._pending_client_removals)
        self.assertFalse(getattr(self.worker, "_pending_queue_deletes", {}))
        other_client.torrents_info.return_value = []
        self.worker._reset_removal_requests()
        self.assertFalse(self.worker._pending_client_removals)
        self.assertIn(17, self.worker._pending_queue_deletes)

    def test_invalid_thresholds_do_not_allow_removal(self):
        """Verify invalid thresholds do not allow removal."""
        self.policy["MinSeedRatio"] = float("nan")
        self.assertFalse(self.allowed())
        self.policy["MinSeedRatio"] = -1
        self.assertFalse(self.allowed())
        self.policy["MinSeedRatio"] = 1
        self.policy["HitAndRunMode"] = "invalid"
        self.assertFalse(self.allowed())

    def test_mode_validation_and_existing_case_insensitive_values(self):
        """Verify mode validation and existing case insensitive values."""
        self.policy["HitAndRunMode"] = 0
        self.client.torrents_properties.return_value = {"is_private": False}
        self.assertFalse(self.allowed())
        self.policy["HitAndRunMode"] = " AND "
        self.assertFalse(self.allowed())
        self.torrent.ratio = 2
        self.assertTrue(self.allowed())

    def test_category_override_applies_and_duration_is_preserved(self):
        """Verify category override applies and duration is preserved."""
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
        """Verify unique eligible removal and ambiguous legacy owner."""
        self.torrent.ratio = 2
        self.assertEqual(
            delete_hashes_on_primary(self.worker, {"superman"}), {("one", "superman")}
        )
        self.client.torrents_delete.assert_called_once()
        self.worker.add("two", ratio=2)
        self.assertEqual(delete_hashes_on_primary(self.worker, {"superman"}), set())

    def test_same_hash_on_other_client_remains_protected_and_pending(self):
        """Verify same hash on other client remains protected and pending."""
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
        """Verify other protected owner blocks content deletion."""
        self.torrent.ratio = 2
        self.worker.add("two")
        self.assertFalse(content_removal_allowed(self.worker, [Path("/downloads/movie.mkv")]))
        self.assertEqual(delete_hashes_per_instance(self.worker, {"one": {"superman"}}), set())
        self.client.torrents_delete.assert_not_called()

    def test_every_batched_content_target_needs_a_verified_owner(self):
        """Verify every batched content target needs a verified owner."""
        self.torrent.ratio = 2
        targets = [Path("/downloads/movie.mkv"), Path("/downloads/unowned.txt")]
        self.assertFalse(content_removal_allowed(self.worker, targets))
        self.client.torrents_files.return_value.append(SimpleNamespace(name="unowned.txt"))
        self.assertTrue(content_removal_allowed(self.worker, targets))

    def test_legacy_default_bucket_resolves_a_unique_actual_client(self):
        """Verify legacy default bucket resolves a unique actual client."""
        self.torrent.ratio = 2
        self.worker.delete_by_instance = {"default": {"superman"}}
        self.worker.delete.add("superman")
        self.worker._process_failed()
        self.client.torrents_delete.assert_called_once()
        self.assertFalse(self.worker.delete_by_instance)
        self.assertFalse(self.worker.delete)

    def test_unsafe_file_paths_block_client_and_content_removal(self):
        """Verify unsafe file paths block client and content removal."""
        self.torrent.ratio = 2
        self.client.torrents_files.return_value = [SimpleNamespace(name="../outside")]
        self.assertFalse(delete_hashes_per_instance(self.worker, {"one": {"superman"}}))
        self.client.torrents_delete.assert_not_called()

    def test_each_client_uses_its_own_rules(self):
        """Verify each client uses its own rules."""
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
        """Verify tracker cleanup cannot erase an outstanding obligation."""
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
        """Verify retry rechecks new obligations."""
        self.torrent.ratio = 2

        def delete(**kwargs):
            """Simulate accounting changing after a failed client deletion."""
            self.torrent.ratio = 0
            raise qbittorrentapi.exceptions.APIError("retry")

        self.client.torrents_delete.side_effect = delete

        def retry(fn, **kwargs):
            """Retry once after the simulated client API failure."""
            try:
                return fn()
            except qbittorrentapi.exceptions.APIError:
                return fn()

        self.worker._qbit_retry = retry
        self.assertEqual(delete_hashes_per_instance(self.worker, {"one": {"superman"}}), set())
        self.client.torrents_delete.assert_called_once()

    def test_refused_retries_discard_uncertain_arr_followups(self) -> None:
        """Refusals after fresh presence cannot release Arr work on a later unrelated removal."""
        for refusal in (
            "identity",
            "cf",
            "rules",
            "files",
            "path_error",
            "post_scan",
            "lookup_recovery",
        ):
            with self.subTest(refusal=refusal):
                worker = Worker()
                torrent, client = worker.add(ratio=2)
                worker.cache = {"SUPERMAN": 17}
                worker.requeue_cache = {17: 42}
                worker.custom_format_unmet_search = True
                worker.custom_format_unmet_check = MagicMock(return_value=True)
                if refusal == "cf":
                    worker._removal_reasons = {("one", "superman"): "CF unmet deletion"}
                if refusal == "post_scan":
                    worker._deletion_rules_allow = MagicMock(side_effect=[True, True, True, False])

                def delete(**kwargs: object) -> None:
                    """Leave the torrent present and make the next removal check refuse."""
                    if refusal == "identity":
                        torrent.added_on = 2
                    elif refusal == "cf":
                        worker.custom_format_unmet_check.return_value = False
                    elif refusal == "rules":
                        torrent.ratio = 0
                    elif refusal == "files":
                        client.torrents_files.return_value = []
                    elif refusal == "path_error":
                        client.torrents_files.return_value = [SimpleNamespace(name="../escape")]
                    elif refusal == "lookup_recovery":
                        client.torrents_info.side_effect = [
                            qbittorrentapi.exceptions.APIConnectionError("offline"),
                            [torrent],
                        ]
                    raise qbittorrentapi.exceptions.APIError("request failed")

                def retry(fn: Callable[[], bool], **kwargs: object) -> bool:
                    """Retry the failed request immediately with current torrent data."""
                    try:
                        return fn()
                    except qbittorrentapi.exceptions.APIError:
                        return fn()

                client.torrents_delete.side_effect = delete
                worker._qbit_retry = retry
                self.assertFalse(
                    delete_hashes_per_instance(
                        worker,
                        {"one": {"superman"}},
                        queue_followups=worker._removal_queue_followups({"superman"}, set()),
                    )
                )
                client.torrents_delete.assert_called_once()
                self.assertFalse(worker._pending_client_removals)
                client.torrents_info.side_effect = None
                client.torrents_info.return_value = []
                worker._reset_removal_requests()
                self.assertFalse(getattr(worker, "_pending_queue_deletes", {}))

    def test_fresh_presence_cancels_uncertain_deletion_before_reclassification(self) -> None:
        """A present torrent invalidates uncertain Arr work even when no retry is classified."""
        self.torrent.ratio = 2
        self.worker.cache = {"SUPERMAN": 17}
        self.client.torrents_delete.side_effect = qbittorrentapi.exceptions.APIError("offline")
        delete_hashes_per_instance(
            self.worker,
            {"one": {"superman"}},
            queue_followups=self.worker._removal_queue_followups({"superman"}, set()),
        )
        self.assertTrue(self.worker._pending_client_removals)
        self.worker._reset_removal_requests()
        self.assertFalse(self.worker._pending_client_removals)
        self.client.torrents_info.return_value = []
        self.worker._reset_removal_requests()
        self.assertFalse(getattr(self.worker, "_pending_queue_deletes", {}))

    def test_queue_deletion_cannot_delegate_removal_to_arr(self):
        """Verify queue deletion cannot delegate removal to arr."""
        arr = ArrBase.__new__(ArrBase)
        arr.cache = {}
        arr.client = MagicMock()
        self.assertFalse(arr.delete_from_queue(1, remove_from_client=True))
        arr.client.queue.delete.assert_not_called()

    def test_error_cleanup_preserves_blocked_iterator_entries(self):
        """Verify error cleanup preserves blocked iterator entries."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "movie.mkv"
            path.write_text("keep")
            arr = ArrBase.__new__(ArrBase)
            arr.files_to_explicitly_delete = iter([("superman", path)])
            arr.remove_and_maybe_blocklist = MagicMock(return_value=False)
            arr.post_download_error_cleanup()
            self.assertEqual(list(arr.files_to_explicitly_delete), [("superman", path)])
            self.assertTrue(path.exists())

    def test_error_cleanup_retries_when_arr_warning_disappears(self):
        """Keep blocked import-error paths scheduled across empty warning refreshes."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "movie.mkv"
            path.write_text("keep")
            arr = ArrBase.__new__(ArrBase)
            arr.auto_delete = True
            arr.needs_cleanup = False
            arr.completed_folder = Path(directory)
            arr.arr_error_codes_to_blocklist = ["bad import"]
            arr.downloads_with_bad_error_message_blocklist = set()
            arr.files_to_explicitly_delete = iter([("superman", path)])
            arr.get_queue = MagicMock(return_value=[])
            arr.post_file_cleanup = MagicMock()
            arr.folder_cleanup = MagicMock(return_value=True)
            arr._remove_empty_folders = MagicMock()
            arr.remove_and_maybe_blocklist = MagicMock(return_value=False)
            arr.all_folder_cleanup()
            arr.remove_and_maybe_blocklist.assert_called_once_with("superman", path)
            self.assertFalse(arr.needs_cleanup)
            arr.remove_and_maybe_blocklist.reset_mock()
            arr.arr_error_codes_to_blocklist = []
            arr.all_folder_cleanup()
            arr.remove_and_maybe_blocklist.assert_called_once_with("superman", path)
            path.unlink()
            arr.all_folder_cleanup()
            self.assertFalse(list(arr.files_to_explicitly_delete))

    def test_cleanup_resolves_download_hash_to_arr_queue_id_after_clearance(self):
        """Verify cleanup resolves download hash to arr queue id after clearance."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "movie.mkv"
            path.write_text("keep")
            arr = ArrBase.__new__(ArrBase)
            arr.completed_folder = Path(directory)
            arr.cache = {"SUPERMAN": 17}
            arr.logger = MagicMock()
            arr.manager = self.worker.manager
            arr.requeue_cache = {}
            arr.re_search = False
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

    def test_completed_folder_cleanup_drops_successful_and_unnecessary_entries(self):
        """Verify completed folder cleanup drops successful and unnecessary entries."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "movie.mkv"
            path.write_text("valid media remains")
            arr = ArrBase.__new__(ArrBase)
            arr.files_to_cleanup = {("superman", path)}
            arr.folder_cleanup = MagicMock(return_value=False)
            arr.post_file_cleanup()
            self.assertTrue(arr.files_to_cleanup)
            arr.folder_cleanup.return_value = True
            arr.post_file_cleanup()
            self.assertFalse(arr.files_to_cleanup)
            self.assertTrue(path.exists())

    def test_invalid_file_batch_uses_one_ownership_scan(self):
        """Verify invalid file batch uses one ownership scan."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            movie = root / "movie.mkv"
            extras = [root / "one.txt", root / "two.txt"]
            for path in [movie, *extras]:
                path.write_text("content")
            arr = ArrBase.__new__(ArrBase)
            arr.auto_delete = True
            arr.completed_folder = root
            arr.logger = MagicMock()
            arr.file_extension_allowlist = [".mkv"]
            arr.file_extension_allowlist_re = re.compile(r"\.mkv$")
            arr.file_is_probeable = lambda path: True
            with patch(
                "qBitrr.arss.qbit_side_effects.content_removal_allowed", return_value=True
            ) as check:
                self.assertTrue(arr.folder_cleanup(None, root))
                check.assert_called_once()
                self.assertEqual(set(check.call_args.args[1]), set(extras))
            self.assertTrue(movie.exists())
            self.assertTrue(all(not path.exists() for path in extras))

    def test_cleanup_cannot_escape_the_completed_folder(self):
        """Verify cleanup cannot escape the completed folder."""
        with tempfile.TemporaryDirectory() as directory:
            arr = ArrBase.__new__(ArrBase)
            arr.completed_folder = Path(directory) / "owned"
            outside = Path(directory) / "keep.mkv"
            outside.write_text("keep")
            self.assertFalse(arr.remove_and_maybe_blocklist(None, outside))
            self.assertTrue(outside.exists())

    def test_protected_file_cleanup_keeps_file(self):
        """Verify protected file cleanup keeps file."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "movie.mkv"
            path.write_text("keep")
            self.torrent.save_path = directory
            self.assertFalse(content_removal_allowed(self.worker, [path]))
            self.assertTrue(path.exists())
