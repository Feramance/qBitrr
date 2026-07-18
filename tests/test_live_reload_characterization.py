"""Characterization tests for live-reload Arr / FreeSpace / PlaceHolder / AutoPauseResume."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from qBitrr.arss import Arr, PlaceHolderArr, TorrentPolicyManager
from qBitrr.arss.qbit_side_effects import pause_hashes_by_instance, resume_hashes_by_instance
from qBitrr.config_reload_policy import classify_config_changes
from qBitrr.webui.lifecycle import LifecycleMixin


def _bare_arr_for_refresh() -> Arr:
    """Minimal Arr for ``apply_config_refresh`` (no full ``__init__``)."""
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
    arr.auto_delete = False
    arr.search_missing = False
    arr.search_command_limit = 5
    arr.ignore_torrents_younger_than = 180
    arr.maximum_eta = 86400
    arr.rss_sync_timer = 15
    arr.refresh_downloads_timer = 1
    arr.stalled_delay = 15
    arr.allowed_stalled = True
    arr.monitored_trackers = []
    arr.seeding_mode_global_bad_tracker_msg = []
    arr.logger = MagicMock()
    arr.timed_ignore_cache = MagicMock()
    arr.timed_ignore_cache_2 = MagicMock()
    arr.timed_skip = MagicMock()
    return arr


class TestArrApplyConfigRefresh(unittest.TestCase):
    """Arr LIVE keys → apply_config_refresh updates in-memory attrs."""

    def test_apply_config_refresh_updates_search_missing_auto_delete_trackers(self) -> None:
        arr = _bare_arr_for_refresh()
        tracker_rows = [{"Name": "live-tracker", "URI": "http://tracker.example/announce"}]

        def config_get(key: str, fallback=None):
            values = {
                "Radarr.Main.Managed": True,
                "Radarr.Main.SkipTLSVerify": False,
                "Radarr.Main.ReSearch": True,
                "Radarr.Main.importMode": "Auto",
                "Radarr.Main.ArrErrorCodesToBlocklist": [],
                "Radarr.Main.Torrent.CaseSensitiveMatches": True,
                "Radarr.Main.Torrent.AutoDelete": True,
                "Radarr.Main.EntrySearch.SearchMissing": True,
                "Radarr.Main.EntrySearch.SearchLimit": 9,
                "qBit.Trackers": [],
                "Radarr.Main.Torrent.Trackers": tracker_rows,
                "Radarr.Main.Torrent.StalledDelay": 20,
            }
            return values.get(key, fallback)

        def config_get_or_raise(key: str):
            return {
                "Radarr.Main.URI": "http://old:7878",
                "Radarr.Main.APIKey": "old-key",
            }[key]

        with (
            patch("qBitrr.arss.base.CONFIG") as mock_config,
            patch("qBitrr.arss.base.PROCESS_ONLY", False),
            patch("qBitrr.arss.base.sync_config_from_disk"),
            patch.object(arr, "_get_ignore_torrents_younger_than", return_value=180),
            patch.object(arr, "_get_maximum_eta", return_value=86400),
            patch.object(arr, "_get_search_command_limit", return_value=9),
            patch.object(arr, "_get_rss_sync_timer", return_value=15),
            patch.object(arr, "_get_refresh_downloads_timer", return_value=1),
            patch.object(arr, "_merge_trackers", return_value=tracker_rows) as merge,
            patch.object(arr, "_install_tracker_index") as install,
            patch("qBitrr.arss.base.build_tracker_index", return_value=MagicMock()) as build_idx,
        ):
            mock_config.get.side_effect = config_get
            mock_config.get_or_raise.side_effect = config_get_or_raise
            mock_config.get_duration.side_effect = lambda key, fallback=0, unit=None: fallback
            arr.apply_config_refresh(preserve_db=True)

        self.assertTrue(arr.search_missing)
        self.assertTrue(arr.auto_delete)
        self.assertTrue(arr.re_search)
        self.assertTrue(arr.case_sensitive_matches)
        self.assertEqual(arr.monitored_trackers, tracker_rows)
        merge.assert_called_once_with([], tracker_rows)
        build_idx.assert_called_once()
        install.assert_called_once()

    def test_worker_loop_sync_updates_search_missing_and_auto_delete(self) -> None:
        """Worker loops must apply Arr LIVE attrs (not only timers)."""
        arr = _bare_arr_for_refresh()
        tracker_rows = [{"Name": "worker-tracker", "URI": "http://tracker.example/announce"}]

        def config_get(key: str, fallback=None):
            values = {
                "Radarr.Main.Managed": True,
                "Radarr.Main.SkipTLSVerify": False,
                "Radarr.Main.ReSearch": True,
                "Radarr.Main.importMode": "Auto",
                "Radarr.Main.ArrErrorCodesToBlocklist": [],
                "Radarr.Main.Torrent.CaseSensitiveMatches": True,
                "Radarr.Main.Torrent.AutoDelete": True,
                "Radarr.Main.EntrySearch.SearchMissing": True,
                "qBit.Trackers": [],
                "Radarr.Main.Torrent.Trackers": tracker_rows,
            }
            return values.get(key, fallback)

        with (
            patch("qBitrr.arss.base.CONFIG") as mock_config,
            patch("qBitrr.arss.base.PROCESS_ONLY", False),
            patch("qBitrr.arss.base.sync_config_from_disk") as sync_disk,
            patch.object(arr, "_get_ignore_torrents_younger_than", return_value=180),
            patch.object(arr, "_get_maximum_eta", return_value=86400),
            patch.object(arr, "_get_search_command_limit", return_value=5),
            patch.object(arr, "_get_rss_sync_timer", return_value=15),
            patch.object(arr, "_get_refresh_downloads_timer", return_value=1),
            patch.object(arr, "_merge_trackers", return_value=tracker_rows),
            patch.object(arr, "_install_tracker_index"),
            patch("qBitrr.arss.base.build_tracker_index", return_value=MagicMock()),
        ):
            mock_config.get.side_effect = config_get
            mock_config.get_duration.side_effect = lambda key, fallback=0, unit=None: fallback
            arr._sync_loop_settings_from_config()

        sync_disk.assert_called_once()
        self.assertTrue(arr.search_missing)
        self.assertTrue(arr.auto_delete)
        self.assertTrue(arr.re_search)
        self.assertEqual(arr.monitored_trackers, tracker_rows)

    def test_lifecycle_live_refresh_invokes_apply_config_refresh(self) -> None:
        arr = MagicMock()
        arr._name = "Radarr.Main"
        plan = classify_config_changes({"Radarr.Main.EntrySearch.SearchMissing": True})
        self.assertIn("Radarr.Main", plan.arr_live_instances)

        webui = LifecycleMixin()
        webui.manager = MagicMock()
        webui.manager.arr_manager = MagicMock()
        webui.manager.arr_manager.managed_objects = {"movies": arr}

        webui._apply_arr_live_refresh(plan)
        arr.apply_config_refresh.assert_called_once_with(preserve_db=True)


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
                patch("qBitrr.arss.placeholder.sync_config_from_disk"),
                patch(
                    "qBitrr.arss.placeholder.get_ignore_torrents_younger_than_effective",
                    return_value=600,
                ),
                patch(
                    "qBitrr.arss.placeholder.get_completed_download_folder_effective",
                    return_value=str(new_root),
                ),
                patch("qBitrr.arss.placeholder.ExpiringSet") as expiring,
            ):
                arr._sync_loop_settings_from_config()

            self.assertEqual(arr.ignore_torrents_younger_than, 600)
            self.assertEqual(arr.completed_folder, new_root / "failed")
            self.assertEqual(arr.manager.completed_folders, {new_root / "failed"})
            self.assertEqual(expiring.call_count, 3)


if __name__ == "__main__":
    unittest.main()
