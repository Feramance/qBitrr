"""Unit tests for WebUI Arr/qBit category stats helpers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from qBitrr.webui.routes.category_stats import (
    build_qbit_overview,
    collect_torrents_for_category,
    collect_torrents_for_category_on_instance,
    serialize_torrent,
    summarize_category_torrents,
)


class TestCategoryStats(unittest.TestCase):
    def test_collect_aggregates_across_instances(self) -> None:
        t1 = SimpleNamespace(state="uploading", size=10, ratio=1.0, seeding_time=100)
        t2 = SimpleNamespace(state="downloading", size=20, ratio=0.5, seeding_time=50)
        manager = MagicMock()
        manager.get_all_instances.return_value = ["qBit", "qBit-Seedbox"]
        c1 = MagicMock()
        c1.torrents_info.return_value = [t1]
        c2 = MagicMock()
        c2.torrents_info.return_value = [t2]
        manager.get_client.side_effect = lambda name: c1 if name == "qBit" else c2

        torrents = collect_torrents_for_category(manager, "movies")
        self.assertEqual(len(torrents), 2)
        stats = summarize_category_torrents(torrents)
        self.assertEqual(stats["torrentCount"], 2)
        self.assertEqual(stats["seedingCount"], 1)
        self.assertEqual(stats["totalSize"], 30)

    def test_collect_on_instance_only(self) -> None:
        t1 = SimpleNamespace(state="uploading", size=10, ratio=1.0, seeding_time=100)
        manager = MagicMock()
        c1 = MagicMock()
        c1.torrents_info.return_value = [t1]
        manager.get_client.return_value = c1

        torrents = collect_torrents_for_category_on_instance(manager, "qBit", "movies")
        self.assertEqual(len(torrents), 1)
        c1.torrents_info.assert_called_once_with(category="movies")
        manager.get_client.assert_called_once_with("qBit")

    def test_serialize_torrent_camel_case(self) -> None:
        torrent = SimpleNamespace(
            hash="abc123",
            name="Movie.mkv",
            category="movies",
            tags="qbitrr,keep",
            state="uploading",
            progress=1.0,
            priority=1,
            eta=8640000,
            availability=1.0,
            size=100,
            total_size=100,
            downloaded=100,
            uploaded=200,
            amount_left=0,
            ratio=2.0,
            dlspeed=0,
            upspeed=50,
            num_seeds=10,
            num_leechs=2,
            num_complete=20,
            num_incomplete=5,
            added_on=1700000000,
            completion_on=1700001000,
            seeding_time=3600,
            time_active=7200,
            last_activity=1700002000,
            save_path="/data",
            content_path="/data/Movie.mkv",
            tracker="https://tracker.example/announce",
            ratio_limit=-1,
            seeding_time_limit=-1,
            dl_limit=-1,
            up_limit=-1,
        )
        payload = serialize_torrent(torrent)
        self.assertEqual(payload["hash"], "abc123")
        self.assertEqual(payload["tags"], ["qbitrr", "keep"])
        self.assertEqual(payload["totalSize"], 100)
        self.assertEqual(payload["numSeeds"], 10)
        self.assertEqual(payload["dlspeed"], 0)
        self.assertEqual(payload["seedingTime"], 3600)

    def test_build_qbit_overview_filters_instance(self) -> None:
        torrent = SimpleNamespace(
            hash="h1",
            name="A",
            category="downloads",
            tags="",
            state="uploading",
            progress=1.0,
            priority=0,
            eta=8640000,
            availability=1.0,
            size=10,
            total_size=10,
            downloaded=10,
            uploaded=10,
            amount_left=0,
            ratio=1.0,
            dlspeed=0,
            upspeed=0,
            num_seeds=1,
            num_leechs=0,
            num_complete=1,
            num_incomplete=0,
            added_on=1,
            completion_on=2,
            seeding_time=10,
            time_active=20,
            last_activity=3,
            save_path="/",
            content_path="/",
            tracker="",
            ratio_limit=-1,
            seeding_time_limit=-1,
            dl_limit=-1,
            up_limit=-1,
        )
        client = MagicMock()
        client.torrents_info.return_value = [torrent]
        cat_manager = MagicMock()
        cat_manager.managed_categories = ["downloads"]
        cat_manager.get_seeding_config.return_value = {
            "MaxUploadRatio": 2.0,
            "MaxSeedingTime": -1,
            "RemoveTorrent": 1,
            "DownloadRateLimitPerTorrent": -1,
            "UploadRateLimitPerTorrent": -1,
        }

        manager = MagicMock()
        manager.get_all_instances.return_value = ["qBit", "qBit-Seedbox"]
        manager.get_client.return_value = client
        manager.qbit_category_managers = {"qBit": cat_manager, "qBit-Seedbox": cat_manager}

        arr = SimpleNamespace(
            type="radarr",
            category="movies",
            _name="Radarr",
            seeding_mode_global_max_upload_ratio=-1,
            seeding_mode_global_max_seeding_time=-1,
            seeding_mode_global_remove_torrent=-1,
            seeding_mode_global_download_limit=-1,
            seeding_mode_global_upload_limit=-1,
        )
        arr_manager = MagicMock()
        arr_manager.managed_objects = {"Radarr": arr}

        payload = build_qbit_overview(manager, instance_filter="qBit", arr_manager=arr_manager)
        self.assertEqual(payload["instances"], ["qBit"])
        self.assertTrue(any(c["category"] == "downloads" for c in payload["categories"]))
        self.assertTrue(any(c["category"] == "movies" for c in payload["categories"]))
        self.assertTrue(all(c["qbitInstance"] == "qBit" for c in payload["categories"]))
        downloads = next(c for c in payload["categories"] if c["category"] == "downloads")
        self.assertEqual(len(downloads["torrents"]), 1)
        self.assertEqual(downloads["torrents"][0]["name"], "A")


if __name__ == "__main__":
    unittest.main()
