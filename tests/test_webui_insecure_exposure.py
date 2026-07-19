"""Tests for WebUI.AllowInsecureExposure bind gate and token endpoint stability."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from qBitrr.errors import ConfigException
from qBitrr.webui import WebUI
from qBitrr.webui.auth import _check_insecure_exposure


def _config_side_effect(values: dict[str, Any]):
    def _get(key: str, fallback: Any = None) -> Any:
        if key in values:
            return values[key]
        return fallback

    return _get


class TestCheckInsecureExposure(unittest.TestCase):
    def test_missing_key_is_warn_only(self) -> None:
        with patch(
            "qBitrr.webui.CONFIG.get",
            side_effect=_config_side_effect({"WebUI.AuthDisabled": True}),
        ):
            self.assertIsNone(_check_insecure_exposure("0.0.0.0"))

    def test_explicit_false_refuses_public_bind(self) -> None:
        with patch(
            "qBitrr.webui.CONFIG.get",
            side_effect=_config_side_effect(
                {"WebUI.AuthDisabled": True, "WebUI.AllowInsecureExposure": False}
            ),
        ):
            msg = _check_insecure_exposure("0.0.0.0")
            self.assertIsNotNone(msg)
            self.assertIn("AllowInsecureExposure", msg or "")

    def test_explicit_true_allows_public_bind(self) -> None:
        with patch(
            "qBitrr.webui.CONFIG.get",
            side_effect=_config_side_effect(
                {"WebUI.AuthDisabled": True, "WebUI.AllowInsecureExposure": True}
            ),
        ):
            self.assertIsNone(_check_insecure_exposure("0.0.0.0"))

    def test_loopback_ok_without_ack(self) -> None:
        with patch(
            "qBitrr.webui.CONFIG.get",
            side_effect=_config_side_effect(
                {"WebUI.AuthDisabled": True, "WebUI.AllowInsecureExposure": False}
            ),
        ):
            self.assertIsNone(_check_insecure_exposure("127.0.0.1"))

    def test_auth_enabled_ok_on_public_bind(self) -> None:
        with patch(
            "qBitrr.webui.CONFIG.get",
            side_effect=_config_side_effect(
                {"WebUI.AuthDisabled": False, "WebUI.AllowInsecureExposure": False}
            ),
        ):
            self.assertIsNone(_check_insecure_exposure("0.0.0.0"))


class TestWebUIInsecureExposureInit(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = MagicMock()

    def test_refuses_start_when_ack_false(self) -> None:
        patches = [
            patch(
                "qBitrr.webui.CONFIG.get",
                side_effect=_config_side_effect(
                    {
                        "WebUI.AuthDisabled": True,
                        "WebUI.AllowInsecureExposure": False,
                        "WebUI.Token": "test-token",
                        "WebUI.BehindHttpsProxy": False,
                        "WebUI.LocalAuthEnabled": False,
                        "WebUI.OIDC.CallbackPath": "/signin-oidc",
                    }
                ),
            ),
            patch("qBitrr.webui.CONFIG.config", {}),
            patch("qBitrr.webui.CONFIG.save"),
            patch("qBitrr.webui.run_logs"),
        ]
        for p in patches:
            p.start()
        try:
            with self.assertRaises(ConfigException):
                WebUI(self.manager, host="0.0.0.0")
        finally:
            for p in reversed(patches):
                p.stop()

    def test_token_endpoints_unchanged_when_auth_disabled(self) -> None:
        patches = [
            patch(
                "qBitrr.webui.CONFIG.get",
                side_effect=_config_side_effect(
                    {
                        "WebUI.AuthDisabled": True,
                        "WebUI.Token": "test-token",
                        "WebUI.BehindHttpsProxy": False,
                        "WebUI.LocalAuthEnabled": False,
                        "WebUI.OIDC.CallbackPath": "/signin-oidc",
                    }
                ),
            ),
            patch("qBitrr.webui.CONFIG.config", {}),
            patch("qBitrr.webui.CONFIG.save"),
            patch("qBitrr.webui.run_logs"),
            patch.object(WebUI, "_ensure_version_info", return_value={"current_version": "0.0.0"}),
        ]
        for p in patches:
            p.start()
        try:
            webui = WebUI(self.manager, host="127.0.0.1")
            client = webui.app.test_client()
            api = client.get("/api/token")
            web = client.get("/web/token")
            self.assertEqual(api.status_code, 200)
            self.assertEqual(web.status_code, 200)
            self.assertEqual(api.get_json(), {"token": "test-token"})
            self.assertEqual(web.get_json(), {"token": "test-token"})
        finally:
            for p in reversed(patches):
                p.stop()


if __name__ == "__main__":
    unittest.main()
