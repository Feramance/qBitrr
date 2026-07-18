"""Unit tests for WebUI Arr/qBit category stats helpers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from qBitrr.webui.routes.category_stats import (
    collect_torrents_for_category,
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


if __name__ == "__main__":
    unittest.main()
