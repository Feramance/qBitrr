"""Unit tests for supervisor spawn failure cleanup in main.py."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from qBitrr.main import qBitManager


def _bare_qbit_manager() -> qBitManager:
    """Build a qBitManager with only spawn-tracking attributes."""
    mgr = qBitManager.__new__(qBitManager)
    mgr.child_processes = []
    mgr._process_registry = {}
    mgr._failed_spawn_attempts = {}
    mgr._pending_spawns = []
    mgr.logger = MagicMock()
    return mgr


def _mock_arr(category: str = "radarr", name: str = "Radarr") -> MagicMock:
    arr = MagicMock()
    arr.category = category
    arr._name = name
    return arr


class TestDiscardUnstartedSpawn(unittest.TestCase):
    """Tests for _discard_unstarted_spawn supervisor helper."""

    def test_discard_unstarted_spawn_removes_proc_and_registry(self) -> None:
        mgr = _bare_qbit_manager()
        proc = MagicMock()
        mgr.child_processes.append(proc)
        mgr._process_registry[proc] = {"category": "radarr", "role": "torrent", "name": "Radarr"}

        mgr._discard_unstarted_spawn(proc)

        self.assertNotIn(proc, mgr.child_processes)
        self.assertNotIn(proc, mgr._process_registry)

    def test_discard_unstarted_spawn_noop_when_proc_missing(self) -> None:
        mgr = _bare_qbit_manager()
        proc = MagicMock()

        mgr._discard_unstarted_spawn(proc)

        self.assertEqual(mgr.child_processes, [])
        self.assertEqual(mgr._process_registry, {})


class TestEnqueueFailedSpawn(unittest.TestCase):
    """Tests for _enqueue_failed_spawn deduplication."""

    def test_enqueue_failed_spawn_dedupes_pending(self) -> None:
        mgr = _bare_qbit_manager()
        arr = _mock_arr()

        mgr._enqueue_failed_spawn(arr, "torrent")
        mgr._enqueue_failed_spawn(arr, "torrent")

        self.assertEqual(len(mgr._pending_spawns), 1)
        self.assertEqual(mgr._failed_spawn_attempts[("radarr", "torrent")], 2)

    def test_enqueue_failed_spawn_allows_distinct_roles(self) -> None:
        mgr = _bare_qbit_manager()
        arr = _mock_arr()

        mgr._enqueue_failed_spawn(arr, "search")
        mgr._enqueue_failed_spawn(arr, "torrent")

        self.assertEqual(len(mgr._pending_spawns), 2)


class TestDbRecoveryFailureCleanup(unittest.TestCase):
    """Simulate coordinated DB recovery failure cleanup path."""

    def test_db_recovery_failure_discards_from_child_processes(self) -> None:
        mgr = _bare_qbit_manager()
        arr = _mock_arr()
        proc = MagicMock()
        proc.is_alive.return_value = False
        proc.exitcode = 1
        mgr.child_processes.append(proc)
        mgr._process_registry[proc] = {
            "category": "radarr",
            "role": "torrent",
            "name": "Radarr",
        }

        mgr._discard_unstarted_spawn(proc)
        mgr._enqueue_failed_spawn(arr, "torrent")

        self.assertNotIn(proc, mgr.child_processes)
        self.assertNotIn(proc, mgr._process_registry)
        self.assertEqual(len(mgr._pending_spawns), 1)
        pending_arr, pending_meta = mgr._pending_spawns[0]
        self.assertIs(pending_arr, arr)
        self.assertEqual(pending_meta["role"], "torrent")
        self.assertEqual(pending_meta["category"], "radarr")
