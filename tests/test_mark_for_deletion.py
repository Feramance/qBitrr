"""Tests for multi-qBit instance torrent deletion routing."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from qBitrr.arss import Arr


def _make_torrent(hash_value: str = "abc123") -> SimpleNamespace:
    return SimpleNamespace(
        hash=hash_value,
        progress=0.5,
        ratio=0.0,
        seeding_time=0,
        name="test-torrent",
    )


class MarkForDeletionInstanceRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arr = Arr.__new__(Arr)
        self.arr.delete = set()
        self.arr.remove_from_qbit_by_instance = {}
        self.arr.logger = MagicMock()

    def test_routes_delete_to_named_qbit_instance(self) -> None:
        torrent = _make_torrent()
        self.arr._mark_for_deletion(torrent, "slow torrent deletion", instance_name="qBit-Seedbox")

        self.assertIn(torrent.hash, self.arr.delete)
        self.assertIn("qBit-Seedbox", self.arr.remove_from_qbit_by_instance)
        self.assertIn(torrent.hash, self.arr.remove_from_qbit_by_instance["qBit-Seedbox"])

    def test_default_instance_keeps_legacy_delete_set_only(self) -> None:
        torrent = _make_torrent("legacy-hash")
        self.arr._mark_for_deletion(torrent, "slow torrent deletion", instance_name="default")

        self.assertIn(torrent.hash, self.arr.delete)
        self.assertEqual(self.arr.remove_from_qbit_by_instance, {})


if __name__ == "__main__":
    unittest.main()
