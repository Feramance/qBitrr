"""Golden-master tests for gen_config migration functions."""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from tomlkit import parse

from qBitrr.gen_config import (
    MyConfig,
    _migrate_animarr_sections,
    _migrate_hnr_settings,
    _migrate_hnr_single_key,
    _migrate_process_restart_settings,
    _migrate_qbit_category_settings,
    _migrate_qbit_subcategory_match,
    _migrate_quality_profile_mappings,
    _migrate_readarr_file_extension_allowlist,
    _migrate_webui_config,
    apply_config_migrations,
)


def _config_from_toml(text: str) -> MyConfig:
    doc = parse(text)
    with tempfile.NamedTemporaryFile(suffix=".toml") as tmp:
        return MyConfig(path=tmp.name, config=doc)


class TestMigrateWebuiConfig(unittest.TestCase):
    def test_migrates_settings_host_port_token(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            Host = "127.0.0.1"
            Port = 6969
            Token = "secret"
            """)
        self.assertTrue(_migrate_webui_config(cfg))
        self.assertEqual(cfg.get("WebUI.Host"), "127.0.0.1")
        self.assertEqual(cfg.get("WebUI.Port"), 6969)
        self.assertEqual(cfg.get("WebUI.Token"), "secret")


class TestMigrateReadarrFileExtensionAllowlist(unittest.TestCase):
    def test_expands_untouched_ebook_default_for_existing_instances(self) -> None:
        """Regression: upgraded Readarr configs still deleted .m4b torrent payloads."""
        cfg = _config_from_toml("""
            [Settings]
            ConfigVersion = "5.14.0"

            [Readarr-Audiobooks]
            [Readarr-Audiobooks.Torrent]
            FileExtensionAllowlist = [".epub", ".mobi", ".azw", ".azw3", ".pdf", ".cbz", ".cbr", ".!qB", ".parts"]
            """)

        self.assertTrue(_migrate_readarr_file_extension_allowlist(cfg))
        allowlist = cfg.get("Readarr-Audiobooks.Torrent.FileExtensionAllowlist")
        self.assertIn(".m4b", allowlist)
        self.assertIn(".kepub", allowlist)
        self.assertFalse(_migrate_readarr_file_extension_allowlist(cfg))

    def test_preserves_user_customized_allowlist(self) -> None:
        cfg = _config_from_toml("""
            [Readarr-Books]
            [Readarr-Books.Torrent]
            FileExtensionAllowlist = [".epub", ".pdf"]
            """)

        self.assertFalse(_migrate_readarr_file_extension_allowlist(cfg))
        self.assertEqual(
            list(cfg.get("Readarr-Books.Torrent.FileExtensionAllowlist")),
            [".epub", ".pdf"],
        )


class TestMigrateQualityProfileMappings(unittest.TestCase):
    def test_list_profiles_become_inline_mapping(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            ConfigVersion = "0.0.1"

            [Radarr]
            [Radarr.EntrySearch]
            MainQualityProfile = ["HD", "UHD"]
            TempQualityProfile = ["SD", "HD-720"]
            """)
        self.assertTrue(_migrate_quality_profile_mappings(cfg))
        mappings = cfg.get("Radarr.EntrySearch.QualityProfileMappings")
        self.assertEqual(dict(mappings), {"HD": "SD", "UHD": "HD-720"})
        self.assertIsNone(cfg.get("Radarr.EntrySearch.MainQualityProfile", fallback=None))


class TestMigrateProcessRestartSettings(unittest.TestCase):
    def test_adds_restart_defaults_for_pre_003(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            ConfigVersion = "0.0.2"
            """)
        self.assertTrue(_migrate_process_restart_settings(cfg))
        self.assertTrue(cfg.get("Settings.AutoRestartProcesses"))
        self.assertEqual(cfg.get("Settings.MaxProcessRestarts"), 5)
        self.assertEqual(cfg.get("Settings.ProcessRestartWindow"), 300)
        self.assertEqual(cfg.get("Settings.ProcessRestartDelay"), 5)


class TestMigrateQbitCategorySettings(unittest.TestCase):
    def test_adds_managed_categories_and_seeding(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            ConfigVersion = "0.0.3"
            [qBit]
            """)
        self.assertTrue(_migrate_qbit_category_settings(cfg))
        self.assertEqual(cfg.get("qBit.ManagedCategories"), [])
        self.assertEqual(cfg.get("qBit.CategorySeeding.HitAndRunMode"), "disabled")


class TestMigrateQbitSubcategoryMatch(unittest.TestCase):
    def test_adds_match_subcategories_false(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            ConfigVersion = "5.12.11"
            [qBit]
            Host = "127.0.0.1"
            """)
        self.assertTrue(_migrate_qbit_subcategory_match(cfg))
        self.assertFalse(cfg.get("qBit.MatchSubcategories"))


class TestMigrateHnrSettings(unittest.TestCase):
    def test_adds_tracker_hnr_defaults_pre_588(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            ConfigVersion = "5.8.7"

            [Radarr]
            [Radarr.Torrent]
            [[Radarr.Torrent.Trackers]]
            URI = "https://tracker.example.org/announce"
            """)
        self.assertTrue(_migrate_hnr_settings(cfg))
        tracker = cfg.config["Radarr"]["Torrent"]["Trackers"][0]
        self.assertEqual(tracker["HitAndRunMode"], "disabled")
        self.assertEqual(tracker["MinSeedRatio"], 1.0)


class TestMigrateHnrSingleKey(unittest.TestCase):
    def test_consolidates_hit_and_run_clear_mode(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            ConfigVersion = "5.9.1"

            [qBit]
            [qBit.CategorySeeding]
            HitAndRunMode = true
            HitAndRunClearMode = "or"
            """)
        self.assertTrue(_migrate_hnr_single_key(cfg))
        self.assertEqual(cfg.get("qBit.CategorySeeding.HitAndRunMode"), "or")
        section = cfg.config["qBit"]["CategorySeeding"]
        self.assertNotIn("HitAndRunClearMode", section)


class TestApplyConfigMigrationsIntegration(unittest.TestCase):
    def test_legacy_config_runs_full_migration_chain(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            Host = "127.0.0.1"
            Port = 6969
            Token = "secret"
            ConfigVersion = "0.0.1"

            [Radarr]
            [Radarr.EntrySearch]
            MainQualityProfile = ["HD"]
            TempQualityProfile = ["SD"]

            [qBit]
            """)
        with (
            patch("qBitrr.gen_config._write_config_file"),
            patch("qBitrr.config_version.validate_config_version", return_value=(True, "")),
            patch("qBitrr.config_version.backup_config", return_value="/tmp/config.bak"),
            patch("builtins.print"),
        ):
            apply_config_migrations(cfg)
        self.assertEqual(cfg.get("WebUI.Host"), "127.0.0.1")
        self.assertEqual(dict(cfg.get("Radarr.EntrySearch.QualityProfileMappings")), {"HD": "SD"})
        self.assertTrue(cfg.get("Settings.AutoRestartProcesses"))
        self.assertEqual(cfg.get("qBit.ManagedCategories"), [])


class TestCurrentConfigShape(unittest.TestCase):
    def test_current_version_skips_versioned_migrations(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            ConfigVersion = "5.12.11"
            AutoRestartProcesses = true

            [qBit]
            MatchSubcategories = false
            ManagedCategories = []
            """)
        self.assertFalse(_migrate_process_restart_settings(cfg))
        self.assertFalse(_migrate_qbit_category_settings(cfg))
        self.assertFalse(_migrate_hnr_settings(cfg))


class TestMigrateQualityProfileMappingsEdgeCases(unittest.TestCase):
    def test_noop_when_mappings_already_inline(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            ConfigVersion = "0.0.1"
            [Radarr.EntrySearch]
            QualityProfileMappings = { HD = "SD" }
            """)
        self.assertFalse(_migrate_quality_profile_mappings(cfg))

    def test_skips_when_only_one_profile_list(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            ConfigVersion = "0.0.1"
            [Sonarr.EntrySearch]
            MainQualityProfile = ["HD"]
            """)
        self.assertFalse(_migrate_quality_profile_mappings(cfg))


class TestMigrateWebuiConfigEdgeCases(unittest.TestCase):
    def test_noop_when_webui_section_already_present(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            Host = "127.0.0.1"
            [WebUI]
            Host = "0.0.0.0"
            """)
        self.assertFalse(_migrate_webui_config(cfg))

    def test_removes_obsolete_group_sonarr_lidarr_keys(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            Host = "127.0.0.1"
            [WebUI]
            Host = "0.0.0.0"
            GroupSonarr = true
            GroupLidarr = false
            """)
        self.assertTrue(_migrate_webui_config(cfg))
        webui = cfg.get("WebUI")
        self.assertNotIn("GroupSonarr", webui)
        self.assertNotIn("GroupLidarr", webui)


class TestMigrateAnimarrSections(unittest.TestCase):
    def test_renames_animarr_to_sonarr_with_collision(self) -> None:
        cfg = _config_from_toml("""
            [Animarr]
            URI = "http://anime.local"
            [Animarr.EntrySearch]
            SearchMissing = true
            [Animarr-Extra]
            URI = "http://anime2.local"
            [Sonarr]
            URI = "http://tv.local"
            """)
        self.assertTrue(_migrate_animarr_sections(cfg))
        self.assertNotIn("Animarr", cfg.config)
        self.assertNotIn("Animarr-Extra", cfg.config)
        self.assertIn("Sonarr-Animarr", cfg.config)
        self.assertIn("Sonarr-Extra", cfg.config)
        self.assertEqual(cfg.get("Sonarr-Animarr.URI"), "http://anime.local")
        self.assertTrue(cfg.get("Sonarr-Animarr.EntrySearch.SearchMissing"))
        self.assertEqual(cfg.get("Sonarr-Extra.URI"), "http://anime2.local")

    def test_noop_when_no_animarr(self) -> None:
        cfg = _config_from_toml("""
            [Sonarr]
            URI = "http://tv.local"
            """)
        self.assertFalse(_migrate_animarr_sections(cfg))


class TestMigrateHnrSingleKeyEdgeCases(unittest.TestCase):
    def test_noop_when_mode_already_string(self) -> None:
        cfg = _config_from_toml("""
            [Settings]
            ConfigVersion = "5.9.2"
            [qBit.CategorySeeding]
            HitAndRunMode = "and"
            """)
        self.assertFalse(_migrate_hnr_single_key(cfg))


if __name__ == "__main__":
    unittest.main()
