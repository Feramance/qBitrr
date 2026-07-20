"""Regression tests: Processes ghosts after qBit/Arr section renames."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from qBitrr.main import qBitManager
from qBitrr.webui import WebUI


def _webui_config_get(key: str, fallback: Any = None) -> Any:
    values = {
        "WebUI.AuthDisabled": True,
        "WebUI.Token": "test-token",
        "WebUI.BehindHttpsProxy": False,
        "WebUI.LocalAuthEnabled": False,
        "WebUI.PasswordHash": "",
        "WebUI.Username": "",
        "WebUI.OIDC.CallbackPath": "/signin-oidc",
        "WebUI.OIDC.Authority": "",
        "WebUI.Host": "0.0.0.0",
        "WebUI.Port": 6969,
        "Settings.ConfigVersion": "5.12.11",
    }
    return values.get(key, fallback)


class TestReloadAllReconcilesQbitClients(unittest.TestCase):
    def test_reload_all_drops_stale_qbit_client_keys(self) -> None:
        manager = MagicMock()
        manager.child_processes = []
        manager._process_registry = {}
        manager.clients = {"qBit": object()}
        manager.qbit_versions = {"qBit": "5.0"}
        manager.instance_metadata = {"qBit": {"host": "localhost"}}
        manager.instance_health = {"qBit": True}
        manager.qbit_category_configs = {"qBit": {"managed_categories": ["misc"]}}
        manager.qbit_category_managers = {}
        manager.arr_manager = MagicMock()
        manager.arr_manager.managed_objects = {}

        def _init_instances() -> None:
            manager.clients["qBit-General"] = object()
            manager.qbit_versions["qBit-General"] = "5.0"
            manager.instance_metadata["qBit-General"] = {"host": "localhost"}
            manager.instance_health["qBit-General"] = True

        manager._initialize_qbit_instances.side_effect = _init_instances

        with (
            patch("qBitrr.webui.CONFIG.get", side_effect=_webui_config_get),
            patch("qBitrr.webui.CONFIG.config", {}),
            patch("qBitrr.webui.run_logs"),
            patch.object(WebUI, "_ensure_version_info", return_value={"current_version": "0.0.0"}),
            patch("qBitrr.arss.ArrManager") as arr_manager_cls,
            patch.object(manager, "_reload_qbit_category_configs"),
            patch.object(manager, "_initialize_qbit_category_managers"),
            patch.object(manager, "_spawn_qbit_category_workers"),
        ):
            rebuilt = MagicMock()
            rebuilt.managed_objects = {}
            arr_manager_cls.return_value.build_arr_instances.return_value = rebuilt
            webui = WebUI(manager)
            webui._reload_all(delete_arr_dbs=False)

        manager._initialize_qbit_instances.assert_called_once()
        self.assertEqual(list(manager.clients.keys()), ["qBit-General"])
        self.assertNotIn("qBit", manager.clients)
        self.assertNotIn("qBit", manager.qbit_versions)
        self.assertNotIn("qBit", manager.instance_metadata)
        self.assertNotIn("qBit", manager.instance_health)


class _FakeQbitManager:
    """Minimal stand-in that reuses qBitManager prune/reload helpers."""

    _reload_qbit_category_configs = qBitManager._reload_qbit_category_configs
    _stop_qbit_category_worker = qBitManager._stop_qbit_category_worker
    _prune_stale_qbit_runtime = qBitManager._prune_stale_qbit_runtime

    def __init__(self) -> None:
        self.clients = {"qBit": object(), "qBit-General": object()}
        self.qbit_versions = {"qBit": "5.0", "qBit-General": "5.0"}
        self.instance_metadata = {"qBit": {}, "qBit-General": {}}
        self.instance_health = {"qBit": True, "qBit-General": True}
        self.qbit_category_configs = {
            "qBit": {"managed_categories": ["old"]},
            "qBit-General": {"managed_categories": ["new"]},
        }
        self.qbit_category_managers = {
            "qBit": MagicMock(),
            "qBit-General": MagicMock(),
        }
        self.stale_proc = MagicMock(name="stale-qbit-worker")
        self.keep_proc = MagicMock(name="keep-qbit-worker")
        self._process_registry = {
            self.stale_proc: {
                "role": "category_manager",
                "instance": "qBit",
                "category": "qbit-qBit",
            },
            self.keep_proc: {
                "role": "category_manager",
                "instance": "qBit-General",
                "category": "qbit-qBit-General",
            },
        }
        self.child_processes = [self.stale_proc, self.keep_proc]
        self.logger = MagicMock()


class TestRefreshQbitHotPrune(unittest.TestCase):
    def test_prune_stale_qbit_runtime_removes_clients_managers_and_registry(self) -> None:
        mgr = _FakeQbitManager()

        def _config_get(key: str, fallback=None):
            if key == "qBit-General.ManagedCategories":
                return ["new"]
            return fallback

        with (
            patch("qBitrr.main.QBIT_DISABLED", False),
            patch("qBitrr.main.SEARCH_ONLY", False),
            patch("qBitrr.main.qbit_sections", return_value=["qBit-General"]),
            patch("qBitrr.main.CONFIG") as config,
            patch("qBitrr.main.load_qbit_seeding_config", return_value={}),
        ):
            config.get.side_effect = _config_get
            mgr._reload_qbit_category_configs()
            mgr._prune_stale_qbit_runtime()

        self.assertEqual(list(mgr.clients.keys()), ["qBit-General"])
        self.assertEqual(list(mgr.qbit_category_configs.keys()), ["qBit-General"])
        self.assertEqual(list(mgr.qbit_category_managers.keys()), ["qBit-General"])
        self.assertNotIn(mgr.stale_proc, mgr._process_registry)
        self.assertIn(mgr.keep_proc, mgr._process_registry)
        self.assertNotIn(mgr.stale_proc, mgr.child_processes)
        mgr.stale_proc.kill.assert_called()


class TestArrRegistryHygiene(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = MagicMock()
        self.manager.child_processes = []
        self.manager._process_registry = {}
        self.manager.arr_manager = MagicMock()
        self.manager.arr_manager.managed_objects = {}
        self.manager.arr_manager.groups = set()
        self.manager.arr_manager.uris = set()
        self.manager.arr_manager.arr_categories = set()

        patches = [
            patch("qBitrr.webui.CONFIG.get", side_effect=_webui_config_get),
            patch("qBitrr.webui.CONFIG.config", {}),
            patch("qBitrr.webui.run_logs"),
            patch.object(WebUI, "_ensure_version_info", return_value={"current_version": "0.0.0"}),
            patch.object(WebUI, "_reload_all"),
        ]
        self._patchers = patches
        for p in patches:
            p.start()
        self.webui = WebUI(self.manager)

    def tearDown(self) -> None:
        for p in reversed(self._patchers):
            p.stop()

    def test_stop_arr_instance_pops_process_registry(self) -> None:
        search_proc = MagicMock(name="search")
        torrent_proc = MagicMock(name="torrent")
        arr = MagicMock()
        arr._name = "Radarr.Old"
        arr.uri = "http://radarr:7878"
        arr.search_db_file = None
        arr.process_search_loop = search_proc
        arr.process_torrent_loop = torrent_proc
        self.manager.child_processes = [search_proc, torrent_proc]
        self.manager._process_registry = {
            search_proc: {"category": "movies", "name": "Radarr.Old", "role": "search"},
            torrent_proc: {"category": "movies", "name": "Radarr.Old", "role": "torrent"},
        }
        self.manager.arr_manager.managed_objects = {"movies": arr}
        self.manager.arr_manager.groups = {"Radarr.Old"}
        self.manager.arr_manager.uris = {arr.uri}
        self.manager.arr_manager.arr_categories = {"movies"}

        self.webui._stop_arr_instance(arr, "movies", delete_db=False)

        self.assertEqual(self.manager._process_registry, {})
        self.assertEqual(self.manager.child_processes, [])
        self.assertNotIn("movies", self.manager.arr_manager.managed_objects)

    def test_start_arr_instance_registers_processes(self) -> None:
        search_proc = MagicMock(name="search")
        torrent_proc = MagicMock(name="torrent")
        new_arr = MagicMock()
        new_arr.category = "movies"
        new_arr.uri = "http://radarr:7878"
        new_arr._name = "Radarr.New"
        new_arr.process_search_loop = search_proc
        new_arr.process_torrent_loop = torrent_proc
        new_arr.spawn_child_processes.return_value = (2, [search_proc, torrent_proc])

        with (
            patch("qBitrr.webui.lifecycle._config") as cfg,
            patch("qBitrr.arss.build_arr_instance", return_value=new_arr),
        ):
            cfg.return_value.get.return_value = True
            self.webui._start_arr_instance("Radarr.New")

        self.assertEqual(
            self.manager._process_registry[search_proc]["role"],
            "search",
        )
        self.assertEqual(
            self.manager._process_registry[torrent_proc]["role"],
            "torrent",
        )
        self.assertEqual(self.manager._process_registry[search_proc]["name"], "Radarr.New")

    def test_reload_arr_instances_ordered_stops_before_starts(self) -> None:
        order: list[str] = []

        def _reload(name: str, *, preserve_db: bool = False) -> None:
            order.append(name)

        with (
            patch("qBitrr.webui.lifecycle._config") as cfg,
            patch.object(self.webui, "_reload_arr_instance", side_effect=_reload),
        ):
            cfg.return_value.sections.return_value = ["Radarr.New"]
            self.webui._reload_arr_instances_ordered(
                ["Radarr.New", "Radarr.Old"],
                reset_instances={"Radarr.New", "Radarr.Old"},
            )

        self.assertEqual(order, ["Radarr.Old", "Radarr.New"])


if __name__ == "__main__":
    unittest.main()
