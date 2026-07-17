"""Regression tests for WebUI config save reload strategies (L1/L2)."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from qBitrr.webui import WebUI


def _config_get(key: str, fallback: Any = None) -> Any:
    values = {
        "WebUI.AuthDisabled": True,
        "WebUI.Token": "test-token",
        "WebUI.BehindHttpsProxy": False,
        "WebUI.LocalAuthEnabled": False,
        "WebUI.PasswordHash": "",
        "WebUI.Username": "",
        "WebUI.OIDC.CallbackPath": "/signin-oidc",
        "WebUI.Host": "0.0.0.0",
        "WebUI.Port": 6969,
        "Settings.ConfigVersion": "5.12.11",
    }
    return values.get(key, fallback)


class _WebUIClientTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = MagicMock()
        self.manager.is_alive = True
        self.manager.qBit_Host = "127.0.0.1"
        self.manager.qBit_Port = 8080
        self.manager.current_qbit_version = "5.0"
        self.manager.get_all_instances.return_value = []
        self.manager.is_instance_alive.return_value = False
        self.manager.get_instance_info.return_value = {}
        self.manager.qbit_category_managers = {}
        self.manager._process_registry = {}
        self.manager.child_processes = []
        self.manager.managed_objects = {}
        self.manager.arr_manager = None

        self.reload_all_patcher = patch.object(WebUI, "_reload_all")
        self.reload_all_mock = self.reload_all_patcher.start()

        patches = [
            patch("qBitrr.webui.CONFIG.get", side_effect=_config_get),
            patch("qBitrr.webui.CONFIG.config", {}),
            patch("qBitrr.webui.CONFIG.save"),
            patch("qBitrr.webui.CONFIG.load"),
            patch("qBitrr.webui.run_logs"),
            patch("qBitrr.webui.fetch_search_activities", return_value={}),
            patch.object(WebUI, "_ensure_version_info", return_value={"current_version": "0.0.0"}),
            patch.object(WebUI, "_trigger_manual_update", return_value=(True, "started")),
        ]
        self._patchers = patches
        for p in patches:
            p.start()
        self.webui = WebUI(self.manager)
        self.client = self.webui.app.test_client()

    def tearDown(self) -> None:
        for p in reversed(self._patchers):
            p.stop()
        self.reload_all_patcher.stop()


class TestWebUIConfigReload(_WebUIClientTestCase):
    def test_loop_sleep_timer_save_does_not_reload_all(self) -> None:
        response = self.client.post(
            "/web/config",
            json={"changes": {"Settings.LoopSleepTimer": 30}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["reloadType"], "live")
        self.assertTrue(payload["configReloaded"])
        self.reload_all_mock.assert_not_called()

    def test_live_settings_save_does_not_delete_arr_db(self) -> None:
        db_file = Path("/tmp/qbitrr-test-search.db")
        db_file.write_text("stub", encoding="utf-8")
        arr = MagicMock()
        arr._name = "Radarr.Main"
        arr.search_db_file = db_file
        self.manager.arr_manager = MagicMock()
        self.manager.arr_manager.managed_objects = {"movies": arr}

        with patch.object(WebUI, "_apply_arr_live_refresh") as live_refresh:
            response = self.client.post(
                "/web/config",
                json={"changes": {"Settings.FailedCategory": "failed-live"}},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["reloadType"], "live")
        self.reload_all_mock.assert_not_called()
        live_refresh.assert_not_called()
        self.assertTrue(db_file.exists(), "live Settings save must not delete search DB")
        db_file.unlink(missing_ok=True)

    def test_arr_live_key_save_calls_apply_arr_live_refresh(self) -> None:
        arr = MagicMock()
        arr._name = "Radarr.Main"
        self.manager.arr_manager = MagicMock()
        self.manager.arr_manager.managed_objects = {"movies": arr}

        with patch.object(WebUI, "_apply_arr_live_refresh") as live_refresh:
            response = self.client.post(
                "/web/config",
                json={"changes": {"Radarr.Main.EntrySearch.SearchMissing": True}},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["reloadType"], "live")
        self.assertTrue(payload["configReloaded"])
        self.reload_all_mock.assert_not_called()
        live_refresh.assert_called_once()
        plan = live_refresh.call_args.args[0]
        self.assertIn("Radarr.Main", plan.arr_live_instances)

    def test_preserve_db_reload_skips_db_deletion(self) -> None:
        db_file = Path("/tmp/qbitrr-preserve-db-test.db")
        db_file.write_text("stub", encoding="utf-8")
        old_arr = MagicMock()
        old_arr._name = "Radarr.Main"
        old_arr.search_db_file = db_file
        old_arr.uri = "http://old:7878"
        self.manager.arr_manager = MagicMock()
        self.manager.arr_manager.managed_objects = {"movies": old_arr}
        self.manager.arr_manager.groups = set()
        self.manager.arr_manager.uris = set()
        self.manager.arr_manager.arr_categories = set()

        with (
            patch("qBitrr.webui.CONFIG.sections", return_value=["Radarr.Main"]),
            patch.object(WebUI, "_start_arr_instance"),
            patch("qBitrr.webui.time.sleep"),
        ):
            self.webui._reload_arr_instance("Radarr.Main", preserve_db=True)

        self.assertTrue(db_file.exists(), "preserve_db reload must keep search DB on disk")
        db_file.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
