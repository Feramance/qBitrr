"""Golden-master tests for Sonarr series payload quality enrichment (pyarr v6)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from qBitrr.webui import WebUI


def _config_get(key: str, fallback: Any = None) -> Any:
    values = {
        "WebUI.AuthDisabled": True,
        "WebUI.OIDC.Authority": "",
        "WebUI.OIDC.ClientId": "",
        "WebUI.OIDC.ClientSecret": "",
    }
    return values.get(key, fallback)


class TestSonarrSeriesPayloadQualityEnrichment(unittest.TestCase):
    def setUp(self) -> None:
        patches = [
            patch("qBitrr.webui.CONFIG.get", side_effect=_config_get),
            patch("qBitrr.webui.CONFIG.config", {}),
            patch("qBitrr.webui.CONFIG.save"),
            patch("qBitrr.webui.run_logs"),
            patch.object(WebUI, "_ensure_version_info", return_value={"current_version": "0.0.0"}),
        ]
        self._patchers = patches
        for p in patches:
            p.start()
        self.webui = WebUI(MagicMock())

    def tearDown(self) -> None:
        for p in reversed(self._patchers):
            p.stop()

    def test_no_op_when_pyarr_v6_client_lacks_legacy_get_series(self) -> None:
        """Pyarr v6 clients expose ``series.get``, not ``get_series`` — guard must not no-op."""
        client = MagicMock(spec=["series", "quality_profile"])
        client.configure_mock(**{"series.get.return_value": None})
        del client.get_series  # pyarr v6: no flat get_series
        arr = SimpleNamespace(client=client, _quality_profile_cache={})
        payload = [{"series": {}}]
        pending = [(0, 42)]

        self.webui._enrich_sonarr_series_payload_quality_from_api(arr, payload, pending)

        client.series.get.assert_called_once_with(item_id=42)

    def test_enriches_quality_profile_from_series_and_profile_api(self) -> None:
        client = MagicMock()
        client.series.get.return_value = {"qualityProfileId": 7}
        client.quality_profile.get.return_value = {"name": "HD-1080p"}
        arr = SimpleNamespace(client=client, _quality_profile_cache={})
        payload = [{"series": {}}]

        self.webui._enrich_sonarr_series_payload_quality_from_api(arr, payload, [(0, 99)])

        self.assertEqual(payload[0]["series"]["qualityProfileId"], 7)
        self.assertEqual(payload[0]["series"]["qualityProfileName"], "HD-1080p")
        client.quality_profile.get.assert_called_once_with(item_id=7)

    def test_uses_cached_quality_profile_name(self) -> None:
        client = MagicMock()
        client.series.get.return_value = {"qualityProfileId": 3}
        arr = SimpleNamespace(
            client=client,
            _quality_profile_cache={3: {"name": "Any"}},
        )
        payload = [{"series": {}}]

        self.webui._enrich_sonarr_series_payload_quality_from_api(arr, payload, [(0, 1)])

        self.assertEqual(payload[0]["series"]["qualityProfileName"], "Any")
        client.quality_profile.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
