"""Characterization tests for Waitress Host/Port rebind via create_server/close."""

from __future__ import annotations

import unittest
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
        "WebUI.Host": "127.0.0.1",
        "WebUI.Port": 7979,
        "Settings.ConfigVersion": "5.12.11",
    }
    return values.get(key, fallback)


class TestWaitressHostPortRebind(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = MagicMock()
        patches = [
            patch("qBitrr.webui.CONFIG.get", side_effect=_config_get),
            patch("qBitrr.webui.CONFIG.config", {}),
            patch("qBitrr.webui.CONFIG.save"),
            patch("qBitrr.webui.CONFIG.load"),
            patch("qBitrr.webui.run_logs"),
            patch.object(WebUI, "_ensure_version_info", return_value={"current_version": "0.0.0"}),
        ]
        self._patchers = patches
        for p in patches:
            p.start()
        self.webui = WebUI(self.manager, host="0.0.0.0", port=6969)
        self.webui.token = "test-token"

    def tearDown(self) -> None:
        for p in reversed(self._patchers):
            p.stop()

    def test_restart_webui_closes_prior_waitress_server(self) -> None:
        prior_server = MagicMock(name="prior_waitress")
        self.webui._server = prior_server
        self.webui._thread = MagicMock()
        self.webui._thread.is_alive.return_value = False

        with patch.object(self.webui, "start") as start_mock:
            self.webui._restart_webui()

        prior_server.close.assert_called_once()
        start_mock.assert_called_once()
        self.assertEqual(self.webui.host, "127.0.0.1")
        self.assertEqual(self.webui.port, 7979)
        self.assertIsNone(self.webui._server)
        self.assertFalse(self.webui._restart_requested)

    def test_restart_webui_token_only_soft_applies_without_close(self) -> None:
        prior_server = MagicMock(name="prior_waitress")
        self.webui._server = prior_server
        self.webui.host = "127.0.0.1"
        self.webui.port = 7979

        def _get(key: str, fallback: Any = None) -> Any:
            if key == "WebUI.Token":
                return "rotated-token"
            return _config_get(key, fallback)

        with (
            patch("qBitrr.webui.CONFIG.get", side_effect=_get),
            patch.object(self.webui, "_apply_webui_runtime_settings") as apply_runtime,
            patch.object(self.webui, "start") as start_mock,
        ):
            self.webui._restart_webui()

        prior_server.close.assert_not_called()
        start_mock.assert_not_called()
        apply_runtime.assert_called_once()
        self.assertEqual(self.webui.token, "rotated-token")
        self.assertIs(self.webui._server, prior_server)

    def test_restart_webui_logs_error_when_start_fails(self) -> None:
        prior_server = MagicMock(name="prior_waitress")
        self.webui._server = prior_server
        self.webui._thread = MagicMock()
        self.webui._thread.is_alive.return_value = False

        with (
            patch.object(self.webui, "start", side_effect=OSError("bind failed")),
            patch.object(self.webui.logger, "error") as error_mock,
        ):
            self.webui._restart_webui()

        prior_server.close.assert_called_once()
        error_mock.assert_called()
        self.assertIn("rebind", error_mock.call_args.args[0].lower())


if __name__ == "__main__":
    unittest.main()
