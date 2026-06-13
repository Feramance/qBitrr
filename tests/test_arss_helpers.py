"""Unit tests for small qBitrr.arss helpers."""

from __future__ import annotations

import unittest

from qBitrr.arss import _prune_hashes_from_instance_map


class PruneHashesFromInstanceMapTests(unittest.TestCase):
    """Tests for per-instance hash map pruning after qBit deletes."""

    def test_removes_only_deleted_hashes_and_empty_instances(self) -> None:
        mapping = {
            "primary": {"aaa", "bbb", "ccc"},
            "seedbox": {"ddd"},
        }

        _prune_hashes_from_instance_map(mapping, {"bbb", "ddd", "missing"})

        self.assertEqual(mapping, {"primary": {"aaa", "ccc"}})

    def test_no_op_on_empty_remove_set(self) -> None:
        mapping = {"primary": {"aaa"}}

        _prune_hashes_from_instance_map(mapping, set())

        self.assertEqual(mapping, {"primary": {"aaa"}})


if __name__ == "__main__":
    unittest.main()
