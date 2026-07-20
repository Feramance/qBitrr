"""Tests for WebUI config update validation (save-gate before reload)."""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import MagicMock

from tomlkit import parse

from qBitrr.gen_config import MyConfig
from qBitrr.webui.config_toml import _toml_delete, _toml_set
from qBitrr.webui.config_validate import validate_config_update


def _config_from_toml(text: str) -> MyConfig:
    doc = parse(text)
    with tempfile.NamedTemporaryFile(suffix=".toml") as tmp:
        return MyConfig(path=tmp.name, config=doc)


class TestValidateConfigUpdate(unittest.TestCase):
    def test_rejects_animarr_keys(self) -> None:
        cfg = _config_from_toml(
            """
            [Sonarr]
            Managed = true
            URI = "http://localhost:8989"
            APIKey = "key"
            Category = "tv"
            """
        )
        errors = validate_config_update(cfg, {"Animarr.URI": "http://x"})
        self.assertTrue(any("Animarr" in e["message"] for e in errors))

    def test_rejects_invalid_number(self) -> None:
        cfg = _config_from_toml(
            """
            [WebUI]
            Port = 6969
            """
        )
        _toml_set(cfg.config, "WebUI.Port", "nope")
        errors = validate_config_update(cfg, {"WebUI.Port": "nope"})
        self.assertTrue(any(e["path"] == "WebUI.Port" for e in errors))

    def test_requires_managed_arr_fields(self) -> None:
        cfg = _config_from_toml(
            """
            [Radarr]
            Managed = true
            URI = ""
            APIKey = ""
            Category = ""
            """
        )
        errors = validate_config_update(cfg, {"Radarr.Managed": True})
        paths = {e["path"] for e in errors}
        self.assertIn("Radarr.URI", paths)
        self.assertIn("Radarr.APIKey", paths)
        self.assertIn("Radarr.Category", paths)

    def test_valid_qbit_change_passes(self) -> None:
        cfg = _config_from_toml(
            """
            [qBit]
            Disabled = false
            Host = "localhost"
            Port = 8080
            """
        )
        _toml_set(cfg.config, "qBit.Port", 9090)
        errors = validate_config_update(cfg, {"qBit.Port": 9090})
        self.assertEqual(errors, [])

    def test_skips_invariants_when_arr_unmanaged(self) -> None:
        cfg = _config_from_toml(
            """
            [Radarr]
            Managed = false
            URI = ""
            """
        )
        errors = validate_config_update(cfg, {"Radarr.Managed": False})
        self.assertEqual(errors, [])

    def test_accepts_numeric_remove_torrent_on_max_seeding_time(self) -> None:
        cfg = _config_from_toml(
            """
            [Lidarr]
            Managed = true
            URI = "http://localhost:8686"
            APIKey = "key"
            Category = "music"
            """
        )
        errors = validate_config_update(
            cfg,
            {
                "Lidarr.Torrent.SeedingMode.RemoveTorrent": 2,
                "Lidarr.Torrent.SeedingMode.MaxSeedingTime": 86400,
                "Lidarr.Torrent.AutoDelete": True,
            },
        )
        self.assertEqual(errors, [])

    def test_accepts_negative_one_arr_seeding_rate_limits(self) -> None:
        cfg = _config_from_toml(
            """
            [Lidarr]
            Managed = true
            URI = "http://localhost:8686"
            APIKey = "key"
            Category = "music"
            """
        )
        errors = validate_config_update(
            cfg,
            {
                "Lidarr.Torrent.SeedingMode.DownloadRateLimitPerTorrent": -1,
                "Lidarr.Torrent.SeedingMode.UploadRateLimitPerTorrent": -1,
                "Lidarr.Torrent.SeedingMode.MaxUploadRatio": -1,
            },
        )
        self.assertEqual(errors, [])

    def test_rejects_invalid_remove_torrent_select_string(self) -> None:
        cfg = _config_from_toml(
            """
            [Lidarr]
            Managed = true
            URI = "http://localhost:8686"
            APIKey = "key"
            Category = "music"
            """
        )
        errors = validate_config_update(cfg, {"Lidarr.Torrent.SeedingMode.RemoveTorrent": ""})
        self.assertTrue(
            any(e["path"] == "Lidarr.Torrent.SeedingMode.RemoveTorrent" for e in errors)
        )

    def test_accepts_negative_one_qbit_category_seeding_rate_limits(self) -> None:
        cfg = _config_from_toml(
            """
            [qBit]
            Disabled = false
            Host = "localhost"
            Port = 8080
            """
        )
        errors = validate_config_update(
            cfg,
            {
                "qBit.CategorySeeding.DownloadRateLimitPerTorrent": -1,
                "qBit.CategorySeeding.UploadRateLimitPerTorrent": -1,
                "qBit.CategorySeeding.MaxUploadRatio": -1,
            },
        )
        self.assertEqual(errors, [])

    def test_rename_qbit_does_not_emit_old_section_host_port_errors(self) -> None:
        cfg = _config_from_toml(
            """
            [qBit]
            Disabled = false
            Host = "192.168.0.240"
            Port = 8080
            """
        )
        _toml_set(cfg.config, "qBit-General.Disabled", False)
        _toml_set(cfg.config, "qBit-General.Host", "192.168.0.240")
        _toml_set(cfg.config, "qBit-General.Port", 8080)
        _toml_delete(cfg.config, "qBit.Host")
        _toml_delete(cfg.config, "qBit.Port")
        _toml_delete(cfg.config, "qBit.Disabled")
        errors = validate_config_update(
            cfg,
            {
                "qBit-General.Disabled": False,
                "qBit-General.Host": "192.168.0.240",
                "qBit-General.Port": 8080,
                "qBit.Host": None,
                "qBit.Port": None,
                "qBit.Disabled": None,
            },
        )
        paths = {e["path"] for e in errors}
        self.assertNotIn("qBit.Host", paths)
        self.assertNotIn("qBit.Port", paths)
        self.assertEqual(errors, [])

    def test_rename_arr_does_not_emit_old_section_invariant_errors(self) -> None:
        cfg = _config_from_toml(
            """
            [Radarr]
            Managed = true
            URI = "http://localhost:7878"
            APIKey = "secret-key"
            Category = "movies"
            """
        )
        _toml_set(cfg.config, "Radarr-X.Managed", True)
        _toml_set(cfg.config, "Radarr-X.URI", "http://localhost:7878")
        _toml_set(cfg.config, "Radarr-X.APIKey", "secret-key")
        _toml_set(cfg.config, "Radarr-X.Category", "movies")
        for leaf in ("Managed", "URI", "APIKey", "Category"):
            _toml_delete(cfg.config, f"Radarr.{leaf}")
        errors = validate_config_update(
            cfg,
            {
                "Radarr-X.Managed": True,
                "Radarr-X.URI": "http://localhost:7878",
                "Radarr-X.APIKey": "secret-key",
                "Radarr-X.Category": "movies",
                "Radarr.Managed": None,
                "Radarr.URI": None,
                "Radarr.APIKey": None,
                "Radarr.Category": None,
            },
        )
        paths = {e["path"] for e in errors}
        self.assertNotIn("Radarr.URI", paths)
        self.assertNotIn("Radarr.APIKey", paths)
        self.assertNotIn("Radarr.Category", paths)
        self.assertEqual(errors, [])


class TestCommentRuleValidation(unittest.TestCase):
    """Save-gate checks that mirror config.example.toml comment constraints."""

    def test_rejects_invalid_console_level(self) -> None:
        cfg = _config_from_toml(
            """
            [Settings]
            ConsoleLevel = "INFO"
            """
        )
        errors = validate_config_update(cfg, {"Settings.ConsoleLevel": "VERBOSE"})
        self.assertTrue(any(e["path"] == "Settings.ConsoleLevel" for e in errors))

    def test_rejects_invalid_remove_torrent_values(self) -> None:
        cfg = _config_from_toml(
            """
            [qBit]
            Disabled = false
            Host = "localhost"
            Port = 8080
            """
        )
        for bad in (0, 5, ""):
            errors = validate_config_update(cfg, {"qBit.CategorySeeding.RemoveTorrent": bad})
            self.assertTrue(
                any(e["path"] == "qBit.CategorySeeding.RemoveTorrent" for e in errors),
                msg=f"expected rejection for RemoveTorrent={bad!r}",
            )

    def test_accepts_valid_remove_torrent_values(self) -> None:
        cfg = _config_from_toml(
            """
            [Lidarr]
            Managed = true
            URI = "http://localhost:8686"
            APIKey = "key"
            Category = "music"
            """
        )
        for good in (-1, 1, 2, 3, 4):
            errors = validate_config_update(
                cfg, {"Lidarr.Torrent.SeedingMode.RemoveTorrent": good}
            )
            self.assertEqual(errors, [], msg=f"expected accept RemoveTorrent={good}")

    def test_rejects_invalid_hit_and_run_mode(self) -> None:
        cfg = _config_from_toml(
            """
            [qBit]
            Disabled = false
            Host = "localhost"
            Port = 8080
            """
        )
        errors = validate_config_update(cfg, {"qBit.CategorySeeding.HitAndRunMode": "both"})
        self.assertTrue(any(e["path"] == "qBit.CategorySeeding.HitAndRunMode" for e in errors))

    def test_rejects_hnr_percent_out_of_range(self) -> None:
        cfg = _config_from_toml(
            """
            [qBit]
            Disabled = false
            Host = "localhost"
            Port = 8080
            """
        )
        for bad in (-1, 101):
            errors = validate_config_update(
                cfg, {"qBit.CategorySeeding.HitAndRunMinimumDownloadPercent": bad}
            )
            self.assertTrue(
                any(
                    e["path"] == "qBit.CategorySeeding.HitAndRunMinimumDownloadPercent"
                    for e in errors
                ),
                msg=f"expected rejection for HnR percent={bad}",
            )

    def test_rejects_invalid_import_mode_and_search_by_series(self) -> None:
        cfg = _config_from_toml(
            """
            [Sonarr]
            Managed = true
            URI = "http://localhost:8989"
            APIKey = "key"
            Category = "tv"
            """
        )
        errors = validate_config_update(cfg, {"Sonarr.importMode": "Hardlink"})
        self.assertTrue(any(e["path"] == "Sonarr.importMode" for e in errors))
        errors = validate_config_update(cfg, {"Sonarr.EntrySearch.SearchBySeries": "auto"})
        self.assertTrue(any(e["path"] == "Sonarr.EntrySearch.SearchBySeries" for e in errors))

    def test_rejects_bad_free_space_and_missing_folder(self) -> None:
        cfg = _config_from_toml(
            """
            [Settings]
            FreeSpace = "-1"
            FreeSpaceFolder = "CHANGE_ME"
            """
        )
        errors = validate_config_update(cfg, {"Settings.FreeSpace": "lots"})
        self.assertTrue(any(e["path"] == "Settings.FreeSpace" for e in errors))

        _toml_set(cfg.config, "Settings.FreeSpace", "10G")
        _toml_set(cfg.config, "Settings.FreeSpaceFolder", "CHANGE_ME")
        errors = validate_config_update(
            cfg, {"Settings.FreeSpace": "10G", "Settings.FreeSpaceFolder": "CHANGE_ME"}
        )
        self.assertTrue(any(e["path"] == "Settings.FreeSpaceFolder" for e in errors))

    def test_accepts_valid_free_space(self) -> None:
        cfg = _config_from_toml(
            """
            [Settings]
            FreeSpace = "-1"
            FreeSpaceFolder = "/downloads"
            """
        )
        _toml_set(cfg.config, "Settings.FreeSpace", "10G")
        _toml_set(cfg.config, "Settings.FreeSpaceFolder", "/downloads")
        errors = validate_config_update(
            cfg, {"Settings.FreeSpace": "10G", "Settings.FreeSpaceFolder": "/downloads"}
        )
        self.assertEqual(errors, [])

    def test_rejects_change_me_completed_download_folder(self) -> None:
        cfg = _config_from_toml(
            """
            [Settings]
            CompletedDownloadFolder = "/downloads"
            """
        )
        errors = validate_config_update(cfg, {"Settings.CompletedDownloadFolder": "CHANGE_ME"})
        self.assertTrue(any(e["path"] == "Settings.CompletedDownloadFolder" for e in errors))

    def test_rejects_managed_arr_change_me_credentials(self) -> None:
        cfg = _config_from_toml(
            """
            [Radarr]
            Managed = true
            URI = "CHANGE_ME"
            APIKey = "CHANGE_ME"
            Category = "movies"
            """
        )
        errors = validate_config_update(
            cfg,
            {
                "Radarr.Managed": True,
                "Radarr.URI": "CHANGE_ME",
                "Radarr.APIKey": "CHANGE_ME",
                "Radarr.Category": "movies",
            },
        )
        paths = {e["path"] for e in errors}
        self.assertIn("Radarr.URI", paths)
        self.assertIn("Radarr.APIKey", paths)

    def test_rejects_invalid_ports(self) -> None:
        cfg = _config_from_toml(
            """
            [WebUI]
            Host = "127.0.0.1"
            Port = 6969
            AuthDisabled = false
            AllowInsecureExposure = false
            """
        )
        for bad in (0, 70000):
            errors = validate_config_update(cfg, {"WebUI.Port": bad})
            self.assertTrue(
                any(e["path"] == "WebUI.Port" for e in errors),
                msg=f"expected rejection for WebUI.Port={bad}",
            )

        cfg2 = _config_from_toml(
            """
            [qBit]
            Disabled = false
            Host = "localhost"
            Port = 8080
            """
        )
        _toml_set(cfg2.config, "qBit.Port", 70000)
        errors = validate_config_update(cfg2, {"qBit.Port": 70000})
        self.assertTrue(any(e["path"] == "qBit.Port" for e in errors))

    def test_rejects_auth_disabled_public_bind_without_ack(self) -> None:
        cfg = _config_from_toml(
            """
            [WebUI]
            Host = "0.0.0.0"
            Port = 6969
            AuthDisabled = true
            AllowInsecureExposure = false
            """
        )
        errors = validate_config_update(
            cfg,
            {
                "WebUI.AuthDisabled": True,
                "WebUI.Host": "0.0.0.0",
                "WebUI.AllowInsecureExposure": False,
            },
        )
        self.assertTrue(any(e["path"] == "WebUI.AllowInsecureExposure" for e in errors))

    def test_accepts_auth_disabled_public_bind_with_ack(self) -> None:
        cfg = _config_from_toml(
            """
            [WebUI]
            Host = "0.0.0.0"
            Port = 6969
            AuthDisabled = true
            AllowInsecureExposure = true
            """
        )
        errors = validate_config_update(
            cfg,
            {
                "WebUI.AuthDisabled": True,
                "WebUI.Host": "0.0.0.0",
                "WebUI.AllowInsecureExposure": True,
            },
        )
        self.assertEqual(errors, [])

    def test_rejects_invalid_url_base_and_cron(self) -> None:
        cfg = _config_from_toml(
            """
            [WebUI]
            Host = "127.0.0.1"
            Port = 6969
            UrlBase = ""
            AuthDisabled = false
            """
        )
        errors = validate_config_update(cfg, {"WebUI.UrlBase": "qbitrr/"})
        self.assertTrue(any(e["path"] == "WebUI.UrlBase" for e in errors))
        errors = validate_config_update(cfg, {"WebUI.UrlBase": "/qbitrr/"})
        self.assertTrue(any(e["path"] == "WebUI.UrlBase" for e in errors))

        cfg2 = _config_from_toml(
            """
            [Settings]
            AutoUpdateCron = "0 3 * * 0"
            """
        )
        errors = validate_config_update(cfg2, {"Settings.AutoUpdateCron": "0 3 *"})
        self.assertTrue(any(e["path"] == "Settings.AutoUpdateCron" for e in errors))

    def test_rejects_maximum_deletable_percentage_out_of_range(self) -> None:
        cfg = _config_from_toml(
            """
            [Lidarr]
            Managed = true
            URI = "http://localhost:8686"
            APIKey = "key"
            Category = "music"
            """
        )
        errors = validate_config_update(cfg, {"Lidarr.Torrent.MaximumDeletablePercentage": 1.5})
        self.assertTrue(
            any(e["path"] == "Lidarr.Torrent.MaximumDeletablePercentage" for e in errors)
        )

    def test_rejects_rate_limit_below_sentinel(self) -> None:
        cfg = _config_from_toml(
            """
            [qBit]
            Disabled = false
            Host = "localhost"
            Port = 8080
            """
        )
        errors = validate_config_update(
            cfg, {"qBit.CategorySeeding.DownloadRateLimitPerTorrent": -2}
        )
        self.assertTrue(
            any(e["path"] == "qBit.CategorySeeding.DownloadRateLimitPerTorrent" for e in errors)
        )


class TestMaterializeRedactedRenameSecrets(unittest.TestCase):
    def test_copies_apikey_from_deleted_old_section(self) -> None:
        from qBitrr.webui.config_toml import (
            REDACTED_PLACEHOLDER,
            materialize_redacted_rename_secrets,
        )

        cfg = _config_from_toml(
            """
            [Radarr]
            Managed = true
            URI = "http://localhost:7878"
            APIKey = "real-secret"
            Category = "movies"
            """
        )
        changes = {
            "Radarr-X.Managed": True,
            "Radarr-X.URI": "http://localhost:7878",
            "Radarr-X.APIKey": REDACTED_PLACEHOLDER,
            "Radarr-X.Category": "movies",
            "Radarr.APIKey": None,
            "Radarr.URI": None,
            "Radarr.Managed": None,
            "Radarr.Category": None,
        }
        materialized = materialize_redacted_rename_secrets(cfg, changes)
        self.assertEqual(materialized["Radarr-X.APIKey"], "real-secret")

        # Simulate apply: set new, delete old, then validate
        for key, val in materialized.items():
            if val is None:
                _toml_delete(cfg.config, key)
            else:
                _toml_set(cfg.config, key, val)
        errors = validate_config_update(cfg, materialized)
        self.assertEqual(errors, [])


class TestConfigUpdateRouteValidation(unittest.TestCase):
    """Smoke: invalid updates must not call save/reload helpers."""

    def test_validate_before_persist_pattern(self) -> None:
        cfg = _config_from_toml(
            """
            [qBit]
            Disabled = false
            Host = "localhost"
            Port = 8080
            """
        )
        cfg.save = MagicMock()
        cfg.load = MagicMock()
        _toml_set(cfg.config, "qBit.Host", "")
        errors = validate_config_update(cfg, {"qBit.Host": ""})
        self.assertTrue(errors)
        # Caller must not save when errors present
        cfg.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
