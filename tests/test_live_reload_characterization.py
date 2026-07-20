"""Characterization tests for live-reload Arr / FreeSpace / PlaceHolder / AutoPauseResume."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from qBitrr.arss import Arr, PlaceHolderArr, TorrentPolicyManager
from qBitrr.arss.qbit_side_effects import pause_hashes_by_instance, resume_hashes_by_instance
from qBitrr.config_reload_policy import classify_config_changes
from qBitrr.webui.lifecycle import Lifecycle


def _bare_arr_for_refresh() -> Arr:
    """Minimal Arr for ``apply_config_refresh`` / LIVE sync (no full ``__init__``)."""
    arr = Arr.__new__(Arr)
    arr._name = "Radarr.Main"
    arr.uri = "http://old:7878"
    arr.apikey = "old-key"
    arr.skip_tls_verify_servarr = False
    arr._client_builder = MagicMock(return_value=MagicMock(name="client"))
    arr.client = MagicMock()
    arr.managed = True
    arr.re_search = False
    arr.import_mode = "Auto"
    arr.arr_error_codes_to_blocklist = []
    arr.case_sensitive_matches = False
    arr.folder_exclusion_regex = None
    arr.file_name_exclusion_regex = None
    arr.file_extension_allowlist = None
    arr.folder_exclusion_regex_re = None
    arr.file_name_exclusion_regex_re = None
    arr.file_extension_allowlist_re = None
    arr.auto_delete = False
    arr.maximum_deletable_percentage = 0.95
    arr.do_not_remove_slow = False
    arr.re_search_stalled = False
    arr.remove_dead_trackers = False
    arr.seeding_mode_global_download_limit = -1
    arr.seeding_mode_global_upload_limit = -1
    arr.seeding_mode_global_max_upload_ratio = -1
    arr.seeding_mode_global_max_seeding_time = -1
    arr.seeding_mode_global_remove_torrent = -1
    arr.seeding_mode_global_bad_tracker_msg = []
    arr.search_missing = False
    arr.reset_on_completion = False
    arr.do_upgrade_search = False
    arr.quality_unmet_search = False
    arr.custom_format_unmet_search = False
    arr.force_minimum_custom_format = False
    arr.search_specials = False
    arr.search_unmonitored = False
    arr.search_by_year = True
    arr.search_in_reverse = False
    arr._delta = -1
    arr.prioritize_todays_release = True
    arr.series_search = False
    arr.ombi_search_requests = False
    arr.overseerr_requests = False
    arr.ombi_uri = None
    arr.ombi_api_key = None
    arr.overseerr_uri = None
    arr.overseerr_api_key = None
    arr.overseerr_is_4k = False
    arr.ombi_approved_only = True
    arr.overseerr_approved_only = True
    arr.skip_tls_verify_overseerr = False
    arr.skip_tls_verify_ombi = False
    arr.search_requests_every_x_seconds = 300
    arr.request_search_timer = None
    arr.search_command_limit = 5
    arr.ignore_torrents_younger_than = 180
    arr.maximum_eta = 86400
    arr.rss_sync_timer = 15
    arr.refresh_downloads_timer = 1
    arr.stalled_delay = 15
    arr.allowed_stalled = True
    arr.monitored_trackers = []
    arr.completed_folder = Path("/tmp/completed/movies")
    arr.logger = MagicMock()
    arr.timed_ignore_cache = MagicMock()
    arr.timed_ignore_cache_2 = MagicMock()
    arr.timed_skip = MagicMock()
    return arr


def _live_config_get(key: str, fallback=None):
    """CONFIG.get values representing a post-save LIVE snapshot."""
    values = {
        "Radarr.Main.ReSearch": True,
        "Radarr.Main.ArrErrorCodesToBlocklist": ["DownloadFailed"],
        "Radarr.Main.Torrent.CaseSensitiveMatches": True,
        "Radarr.Main.Torrent.FolderExclusionRegex": ["sample"],
        "Radarr.Main.Torrent.FileNameExclusionRegex": ["trailer"],
        "Radarr.Main.Torrent.FileExtensionAllowlist": [".mkv"],
        "Radarr.Main.Torrent.AutoDelete": True,
        "Radarr.Main.Torrent.MaximumDeletablePercentage": 0.8,
        "Radarr.Main.Torrent.DoNotRemoveSlow": True,
        "Radarr.Main.Torrent.ReSearchStalled": True,
        "Radarr.Main.Torrent.StalledDelay": 20,
        "Radarr.Main.Torrent.SeedingMode.RemoveDeadTrackers": True,
        "Radarr.Main.Torrent.SeedingMode.DownloadRateLimitPerTorrent": 100,
        "Radarr.Main.Torrent.SeedingMode.UploadRateLimitPerTorrent": 50,
        "Radarr.Main.Torrent.SeedingMode.MaxUploadRatio": 2.0,
        "Radarr.Main.Torrent.SeedingMode.MaxSeedingTime": 3600,
        "Radarr.Main.Torrent.SeedingMode.RemoveTorrent": True,
        "Radarr.Main.Torrent.SeedingMode.RemoveTrackerWithMessage": ["unregistered"],
        "Radarr.Main.EntrySearch.SearchMissing": True,
        "Radarr.Main.EntrySearch.SearchAgainOnSearchCompletion": True,
        "Radarr.Main.EntrySearch.DoUpgradeSearch": True,
        "Radarr.Main.EntrySearch.QualityUnmetSearch": True,
        "Radarr.Main.EntrySearch.CustomFormatUnmetSearch": True,
        "Radarr.Main.EntrySearch.ForceMinimumCustomFormat": True,
        "Radarr.Main.EntrySearch.AlsoSearchSpecials": True,
        "Radarr.Main.EntrySearch.Unmonitored": True,
        "Radarr.Main.EntrySearch.SearchByYear": False,
        "Radarr.Main.EntrySearch.SearchInReverse": True,
        "Radarr.Main.EntrySearch.SearchLimit": 9,
        "Radarr.Main.EntrySearch.PrioritizeTodaysReleases": False,
        "Radarr.Main.EntrySearch.SearchBySeries": "smart",
        "Radarr.Main.EntrySearch.Ombi.SearchOmbiRequests": True,
        "Radarr.Main.EntrySearch.Ombi.OmbiURI": "http://ombi:3579",
        "Radarr.Main.EntrySearch.Ombi.OmbiAPIKey": "ombi-key",
        "Radarr.Main.EntrySearch.Ombi.ApprovedOnly": False,
        "Radarr.Main.EntrySearch.Ombi.SkipTLSVerify": True,
        "Radarr.Main.EntrySearch.Overseerr.SearchOverseerrRequests": True,
        "Radarr.Main.EntrySearch.Overseerr.OverseerrURI": "http://overseerr:5055",
        "Radarr.Main.EntrySearch.Overseerr.OverseerrAPIKey": "os-key",
        "Radarr.Main.EntrySearch.Overseerr.ApprovedOnly": False,
        "Radarr.Main.EntrySearch.Overseerr.Is4K": True,
        "Radarr.Main.EntrySearch.Overseerr.SkipTLSVerify": True,
        "Radarr.Main.EntrySearch.SearchRequestsEvery": 120,
        "qBit.Trackers": [],
        "Radarr.Main.Torrent.Trackers": [
            {"Name": "live-tracker", "URI": "http://tracker.example/announce"}
        ],
        # ARR_PRESERVE_DB — must NOT be applied by worker LIVE sync
        "Radarr.Main.Managed": False,
        "Radarr.Main.SkipTLSVerify": True,
        "Radarr.Main.importMode": "Copy",
    }
    return values.get(key, fallback)


class TestArrApplyConfigRefresh(unittest.TestCase):
    """Arr LIVE keys → apply_config_refresh updates in-memory attrs."""

    def test_apply_config_refresh_updates_search_missing_auto_delete_trackers(self) -> None:
        arr = _bare_arr_for_refresh()
        tracker_rows = [{"Name": "live-tracker", "URI": "http://tracker.example/announce"}]

        def config_get_or_raise(key: str):
            return {
                "Radarr.Main.URI": "http://old:7878",
                "Radarr.Main.APIKey": "old-key",
            }[key]

        with (
            patch("qBitrr.arss.arr_base.CONFIG") as mock_config,
            patch("qBitrr.arss.arr_base.PROCESS_ONLY", False),
            patch("qBitrr.arss.arr_base.SEARCH_ONLY", True),
            patch("qBitrr.arss.arr_base.sync_config_from_disk"),
            patch.object(arr, "_get_ignore_torrents_younger_than", return_value=180),
            patch.object(arr, "_get_maximum_eta", return_value=86400),
            patch.object(arr, "_get_search_command_limit", return_value=9),
            patch.object(arr, "_get_rss_sync_timer", return_value=15),
            patch.object(arr, "_get_refresh_downloads_timer", return_value=1),
            patch.object(arr, "_merge_trackers", return_value=tracker_rows) as merge,
            patch.object(arr, "_install_tracker_index") as install,
            patch(
                "qBitrr.arss.arr_base.build_tracker_index", return_value=MagicMock()
            ) as build_idx,
        ):
            mock_config.get.side_effect = _live_config_get
            mock_config.get_or_raise.side_effect = config_get_or_raise
            mock_config.get_duration.side_effect = lambda key, fallback=0, unit=None: {
                "Radarr.Main.Torrent.StalledDelay": 20,
                "Radarr.Main.Torrent.SeedingMode.MaxSeedingTime": 3600,
                "Radarr.Main.EntrySearch.SearchRequestsEvery": 120,
            }.get(key, fallback)
            arr.apply_config_refresh(preserve_db=True)

        self.assertTrue(arr.search_missing)
        self.assertTrue(arr.auto_delete)
        self.assertTrue(arr.re_search)
        self.assertTrue(arr.case_sensitive_matches)
        self.assertEqual(arr.monitored_trackers, tracker_rows)
        merge.assert_called_once_with([], tracker_rows)
        build_idx.assert_called_once()
        install.assert_called_once()
        # Main-process may refresh SkipTLSVerify; Managed/importMode stay as-is (respawn path)
        self.assertTrue(arr.skip_tls_verify_servarr)
        self.assertTrue(arr.managed)
        self.assertEqual(arr.import_mode, "Auto")

    def test_worker_loop_sync_live_attr_matrix(self) -> None:
        """Worker loops must apply the full Arr LIVE attr set (not only timers)."""
        arr = _bare_arr_for_refresh()
        tracker_rows = [{"Name": "live-tracker", "URI": "http://tracker.example/announce"}]
        # Preserve-db identity must remain untouched by worker sync
        arr.managed = True
        arr.skip_tls_verify_servarr = False
        arr.import_mode = "Auto"

        with (
            patch("qBitrr.arss.arr_base.CONFIG") as mock_config,
            patch("qBitrr.arss.arr_base.PROCESS_ONLY", False),
            patch("qBitrr.arss.arr_base.SEARCH_ONLY", True),
            patch("qBitrr.arss.arr_base.sync_config_from_disk") as sync_disk,
            patch.object(arr, "_get_ignore_torrents_younger_than", return_value=600),
            patch.object(arr, "_get_maximum_eta", return_value=43200),
            patch.object(arr, "_get_search_command_limit", return_value=9),
            patch.object(arr, "_get_rss_sync_timer", return_value=30),
            patch.object(arr, "_get_refresh_downloads_timer", return_value=5),
            patch.object(arr, "_merge_trackers", return_value=tracker_rows),
            patch.object(arr, "_install_tracker_index"),
            patch("qBitrr.arss.arr_base.build_tracker_index", return_value=MagicMock()),
            patch("qBitrr.arss.arr_base.ExpiringSet") as expiring,
        ):
            mock_config.get.side_effect = _live_config_get
            mock_config.get_duration.side_effect = lambda key, fallback=0, unit=None: {
                "Radarr.Main.Torrent.StalledDelay": 20,
                "Radarr.Main.Torrent.SeedingMode.MaxSeedingTime": 3600,
                "Radarr.Main.EntrySearch.SearchRequestsEvery": 120,
            }.get(key, fallback)
            arr._sync_loop_settings_from_config()

        sync_disk.assert_called_once()
        self.assertEqual(expiring.call_count, 3)  # ignore-younger caches rebuilt

        # Timers / ETA / ignore-younger
        self.assertEqual(arr.ignore_torrents_younger_than, 600)
        self.assertEqual(arr.maximum_eta, 43200)
        self.assertEqual(arr.search_command_limit, 9)
        self.assertEqual(arr.rss_sync_timer, 30)
        self.assertEqual(arr.refresh_downloads_timer, 5)
        self.assertEqual(arr.stalled_delay, 20)
        self.assertTrue(arr.allowed_stalled)

        # Torrent LIVE
        self.assertTrue(arr.case_sensitive_matches)
        self.assertEqual(arr.folder_exclusion_regex, ["sample"])
        self.assertEqual(arr.file_name_exclusion_regex, ["trailer"])
        self.assertIsNotNone(arr.folder_exclusion_regex_re)
        self.assertTrue(arr.auto_delete)
        self.assertEqual(arr.maximum_deletable_percentage, 0.8)
        self.assertTrue(arr.do_not_remove_slow)
        self.assertTrue(arr.re_search_stalled)
        self.assertTrue(arr.remove_dead_trackers)
        self.assertEqual(arr.seeding_mode_global_download_limit, 100)
        self.assertEqual(arr.seeding_mode_global_upload_limit, 50)
        self.assertEqual(arr.seeding_mode_global_max_upload_ratio, 2.0)
        self.assertEqual(arr.seeding_mode_global_max_seeding_time, 3600)
        self.assertTrue(arr.seeding_mode_global_remove_torrent)
        self.assertEqual(arr.seeding_mode_global_bad_tracker_msg, ["unregistered"])
        self.assertEqual(arr.monitored_trackers, tracker_rows)

        # EntrySearch LIVE
        self.assertTrue(arr.search_missing)
        self.assertTrue(arr.reset_on_completion)
        self.assertTrue(arr.do_upgrade_search)
        self.assertTrue(arr.quality_unmet_search)
        self.assertTrue(arr.custom_format_unmet_search)
        self.assertTrue(arr.force_minimum_custom_format)
        self.assertTrue(arr.search_specials)
        self.assertTrue(arr.search_unmonitored)
        self.assertFalse(arr.search_by_year)
        self.assertTrue(arr.search_in_reverse)
        self.assertEqual(arr._delta, 1)
        self.assertFalse(arr.prioritize_todays_release)
        self.assertEqual(arr.series_search, "smart")
        self.assertTrue(arr.re_search)
        self.assertEqual(arr.arr_error_codes_to_blocklist, ["DownloadFailed"])

        # Ombi / Overseerr LIVE
        self.assertTrue(arr.ombi_search_requests)
        self.assertTrue(arr.overseerr_requests)
        self.assertEqual(arr.ombi_uri, "http://ombi:3579")
        self.assertEqual(arr.ombi_api_key, "ombi-key")
        self.assertEqual(arr.overseerr_uri, "http://overseerr:5055")
        self.assertEqual(arr.overseerr_api_key, "os-key")
        self.assertFalse(arr.ombi_approved_only)
        self.assertFalse(arr.overseerr_approved_only)
        self.assertTrue(arr.overseerr_is_4k)
        self.assertTrue(arr.skip_tls_verify_ombi)
        self.assertTrue(arr.skip_tls_verify_overseerr)
        self.assertEqual(arr.search_requests_every_x_seconds, 120)
        self.assertEqual(arr.request_search_timer, 0)

        # ARR_PRESERVE_DB identity — worker LIVE must not touch these
        self.assertTrue(arr.managed)
        self.assertFalse(arr.skip_tls_verify_servarr)
        self.assertEqual(arr.import_mode, "Auto")

    def test_lifecycle_live_refresh_invokes_apply_config_refresh(self) -> None:
        arr = MagicMock()
        arr._name = "Radarr.Main"
        # Keep reconcile from spawning: search already "alive"
        arr.search_missing = True
        arr.process_search_loop = MagicMock()
        arr.process_search_loop.is_alive.return_value = True
        plan = classify_config_changes({"Radarr.Main.EntrySearch.SearchMissing": True})
        self.assertIn("Radarr.Main", plan.arr_live_instances)

        webui = Lifecycle()
        webui.logger = MagicMock()
        webui.manager = MagicMock()
        webui.manager.arr_manager = MagicMock()
        webui.manager.arr_manager.managed_objects = {"movies": arr}
        webui.manager.child_processes = []
        webui.manager._process_registry = {}

        webui._apply_arr_live_refresh(plan)
        arr.apply_config_refresh.assert_called_once_with(preserve_db=True)


class TestArrLiveSearchWorkerReconcile(unittest.TestCase):
    """LIVE refresh must start/stop the search worker when SearchMissing changes."""

    def _webui_with_arr(self, arr) -> Lifecycle:
        webui = Lifecycle()
        webui.logger = MagicMock()
        webui.manager = MagicMock()
        webui.manager.arr_manager = MagicMock()
        webui.manager.arr_manager.managed_objects = {"movies": arr}
        webui.manager.child_processes = []
        webui.manager._process_registry = {}
        return webui

    def test_live_refresh_spawns_search_when_missing_enabled(self) -> None:
        arr = MagicMock()
        arr._name = "Radarr.Main"
        arr.category = "movies"
        arr.search_missing = True
        arr.process_search_loop = None
        arr.run_search_loop = MagicMock(name="run_search_loop")
        plan = classify_config_changes({"Radarr.Main.EntrySearch.SearchMissing": True})

        webui = self._webui_with_arr(arr)
        new_proc = MagicMock(name="search_proc")
        new_proc.pid = 4242

        with patch("pathos.helpers.mp.Process", return_value=new_proc) as process_cls:
            webui._apply_arr_live_refresh(plan)

        arr.apply_config_refresh.assert_called_once_with(preserve_db=True)
        process_cls.assert_called_once_with(target=arr.run_search_loop, daemon=False)
        new_proc.start.assert_called_once()
        self.assertIs(arr.process_search_loop, new_proc)
        self.assertIn(new_proc, webui.manager.child_processes)
        self.assertEqual(
            webui.manager._process_registry[new_proc],
            {"category": "movies", "name": "Radarr.Main", "role": "search"},
        )

    def test_live_refresh_stops_search_when_missing_disabled(self) -> None:
        existing = MagicMock(name="existing_search")
        existing.is_alive.return_value = True
        arr = MagicMock()
        arr._name = "Radarr.Main"
        arr.category = "movies"
        arr.search_missing = False
        arr.process_search_loop = existing
        plan = classify_config_changes({"Radarr.Main.EntrySearch.SearchMissing": False})

        webui = self._webui_with_arr(arr)
        webui.manager.child_processes = [existing]
        webui.manager._process_registry = {
            existing: {"category": "movies", "name": "Radarr.Main", "role": "search"}
        }

        with patch("pathos.helpers.mp.Process") as process_cls:
            webui._apply_arr_live_refresh(plan)

        process_cls.assert_not_called()
        existing.kill.assert_called_once()
        existing.terminate.assert_called_once()
        self.assertIsNone(arr.process_search_loop)
        self.assertNotIn(existing, webui.manager.child_processes)
        self.assertNotIn(existing, webui.manager._process_registry)

    def test_live_refresh_idempotent_when_search_already_alive(self) -> None:
        existing = MagicMock(name="existing_search")
        existing.is_alive.return_value = True
        arr = MagicMock()
        arr._name = "Radarr.Main"
        arr.category = "movies"
        arr.search_missing = True
        arr.process_search_loop = existing
        plan = classify_config_changes({"Radarr.Main.EntrySearch.SearchMissing": True})

        webui = self._webui_with_arr(arr)
        webui.manager.child_processes = [existing]
        webui.manager._process_registry = {
            existing: {"category": "movies", "name": "Radarr.Main", "role": "search"}
        }

        with patch("pathos.helpers.mp.Process") as process_cls:
            webui._apply_arr_live_refresh(plan)

        process_cls.assert_not_called()
        existing.kill.assert_not_called()
        existing.terminate.assert_not_called()
        existing.start.assert_not_called()
        self.assertIs(arr.process_search_loop, existing)
        self.assertEqual(webui.manager.child_processes, [existing])


class TestAutoPauseResumeLiveGate(unittest.TestCase):
    """AutoPauseResume toggles pause/resume side effects without process restart."""

    def test_pause_skipped_when_auto_pause_resume_disabled(self) -> None:
        worker = MagicMock()
        worker.pause_by_instance = {"default": {"abc"}}
        worker.needs_cleanup = False
        worker._get_qbit_client.return_value = MagicMock()

        with patch(
            "qBitrr.arss.qbit_side_effects.get_auto_pause_resume_effective",
            return_value=False,
        ):
            pause_hashes_by_instance(worker)

        worker._get_qbit_client.assert_not_called()
        self.assertEqual(worker.pause_by_instance, {"default": {"abc"}})
        self.assertFalse(worker.needs_cleanup)

    def test_pause_runs_when_auto_pause_resume_enabled(self) -> None:
        client = MagicMock()
        worker = MagicMock()
        worker.pause_by_instance = {"vpn": {"hash1"}}
        worker.needs_cleanup = False
        worker.logger = MagicMock()
        worker.manager = MagicMock()
        worker.manager.qbit_manager.name_cache = {}
        worker._get_qbit_client.return_value = client

        with (
            patch(
                "qBitrr.arss.qbit_side_effects.get_auto_pause_resume_effective",
                return_value=True,
            ),
            patch("qBitrr.arss.qbit_side_effects.with_retry", side_effect=lambda fn, **_: fn()),
        ):
            pause_hashes_by_instance(worker)

        client.torrents_pause.assert_called_once_with(torrent_hashes=["hash1"])
        self.assertTrue(worker.needs_cleanup)
        self.assertEqual(worker.pause_by_instance, {})

    def test_resume_skipped_when_auto_pause_resume_disabled(self) -> None:
        worker = MagicMock()
        worker.resume_by_instance = {"default": {"xyz"}}
        worker.needs_cleanup = False

        with patch(
            "qBitrr.arss.qbit_side_effects.get_auto_pause_resume_effective",
            return_value=False,
        ):
            resume_hashes_by_instance(worker)

        worker._get_qbit_client.assert_not_called()
        self.assertEqual(worker.resume_by_instance, {"default": {"xyz"}})


class TestFreeSpaceLiveSync(unittest.TestCase):
    """FreeSpace enable/disable and threshold change mid-loop."""

    def test_sync_enables_free_space_from_disabled(self) -> None:
        arr = TorrentPolicyManager.__new__(TorrentPolicyManager)
        arr.enable_free_space = False
        arr.categories = {"movies"}
        arr.manager = MagicMock()
        arr.manager.arr_categories = {"movies"}
        arr.min_free_space = "-1"
        arr._min_free_space_bytes = 0
        arr.completed_folder = Path("/tmp/old")
        arr._disk_usage_path = Path("/tmp/old")
        arr._path_for_disk_usage = Path("/tmp/old")
        arr._free_space_folder_is_auto = True
        client = MagicMock()

        with (
            patch("qBitrr.arss.torrent_policy.sync_config_from_disk"),
            patch(
                "qBitrr.arss.torrent_policy.get_free_space_guard_settings",
                return_value=("2GB", "/downloads"),
            ),
            patch("qBitrr.arss.torrent_policy.get_auto_pause_resume_effective", return_value=True),
            patch("qBitrr.arss.torrent_policy.get_effective_qbit_disabled", return_value=False),
            patch("qBitrr.arss.torrent_policy.parse_size", return_value=2 * 1024**3),
            patch.object(arr, "_get_primary_qbit_client", return_value=client),
        ):
            arr._sync_free_space_settings_from_config()

        self.assertTrue(arr.enable_free_space)
        self.assertEqual(arr.min_free_space, "2GB")
        self.assertEqual(arr._min_free_space_bytes, 2 * 1024**3)
        client.torrents_create_tags.assert_called_once_with(["qBitrr-free_space_paused"])


class TestPlaceHolderLiveSync(unittest.TestCase):
    """PlaceHolder ignore-younger + completed-folder sync from live Settings."""

    def test_sync_updates_ignore_younger_and_completed_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_root = Path(tmp) / "old"
            new_root = Path(tmp) / "new"
            old_root.mkdir()
            new_root.mkdir()

            arr = PlaceHolderArr.__new__(PlaceHolderArr)
            arr.category = "failed"
            arr.ignore_torrents_younger_than = 180
            arr.timed_ignore_cache = MagicMock()
            arr.timed_ignore_cache_2 = MagicMock()
            arr.timed_skip = MagicMock()
            arr.completed_folder = old_root / "failed"
            arr.manager = MagicMock()
            arr.manager.completed_folders = {arr.completed_folder}

            with (
                patch("qBitrr.arss.placeholder_arr.sync_config_from_disk"),
                patch(
                    "qBitrr.arss.placeholder_arr.get_ignore_torrents_younger_than_effective",
                    return_value=600,
                ),
                patch(
                    "qBitrr.arss.placeholder_arr.get_completed_download_folder_effective",
                    return_value=str(new_root),
                ),
                patch("qBitrr.arss.placeholder_arr.ExpiringSet") as expiring,
            ):
                arr._sync_loop_settings_from_config()

            self.assertEqual(arr.ignore_torrents_younger_than, 600)
            self.assertEqual(arr.completed_folder, new_root / "failed")
            self.assertEqual(arr.manager.completed_folders, {new_root / "failed"})
            self.assertEqual(expiring.call_count, 3)


if __name__ == "__main__":
    unittest.main()
