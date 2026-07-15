"""Unit tests for config_reload_policy key classification."""

from __future__ import annotations

import unittest

from tests.support.branch_compat import HAS_CONFIG_RELOAD_POLICY


@unittest.skipUnless(HAS_CONFIG_RELOAD_POLICY, "config_reload_policy is refactor-only")
class TestConfigReloadPolicy(unittest.TestCase):
    def test_settings_loop_sleep_is_live(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(
            classify_config_key("Settings.LoopSleepTimer"),
            ReloadCategory.LIVE,
        )

    def test_settings_console_level_is_live(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(
            classify_config_key("Settings.ConsoleLevel"),
            ReloadCategory.LIVE,
        )

    def test_settings_console_level_requires_full_restart(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(
            classify_config_key("Settings.Logging"),
            ReloadCategory.FULL_RESTART,
        )

    def test_qbit_seeding_is_hot(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(
            classify_config_key("qBit.CategorySeeding.MaxUploadRatio"),
            ReloadCategory.QBIT_HOT,
        )

    def test_qbit_host_requires_full_restart(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(classify_config_key("qBit.Host"), ReloadCategory.FULL_RESTART)

    def test_qbit_seedbox_hot_reload(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(
            classify_config_key("qBit-Seedbox.CategorySeeding.StalledDelay"),
            ReloadCategory.QBIT_HOT,
        )

    def test_arr_uri_preserves_db(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(
            classify_config_key("Radarr.Main.URI"),
            ReloadCategory.ARR_PRESERVE_DB,
        )

    def test_arr_quality_profile_mapping_resets_db(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(
            classify_config_key("Sonarr-TV.EntrySearch.QualityProfileMappings"),
            ReloadCategory.ARR_RESET_DB,
        )

    def test_arr_torrent_setting_is_live(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(
            classify_config_key("Radarr.Main.Torrent.StalledDelay"),
            ReloadCategory.LIVE,
        )

    def test_webui_theme_is_frontend_only(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(classify_config_key("WebUI.Theme"), ReloadCategory.FRONTEND_ONLY)

    def test_classify_changes_live_only(self) -> None:
        from qBitrr.config_reload_policy import classify_config_changes

        plan = classify_config_changes(
            {
                "Settings.LoopSleepTimer": 10,
                "Settings.FailedCategory": "failed",
            }
        )
        self.assertEqual(plan.primary_reload_type(), "live")
        self.assertFalse(plan.needs_full_restart)

    def test_classify_changes_mixed_arr_reset_and_respawn(self) -> None:
        from qBitrr.config_reload_policy import classify_config_changes

        plan = classify_config_changes(
            {
                "Radarr.Main.URI": "http://radarr:7878",
                "Radarr.Main.EntrySearch.QualityProfileMappings": {"1": 2},
            }
        )
        self.assertIn("Radarr.Main", plan.arr_reset_instances)
        self.assertIn("Radarr.Main", plan.arr_respawn_instances)
        self.assertEqual(plan.primary_reload_type(), "single_arr")

    def test_classify_qbit_hot_plan(self) -> None:
        from qBitrr.config_reload_policy import classify_config_changes

        plan = classify_config_changes({"qBit.CategorySeeding.MaxUploadRatio": 2.0})
        self.assertEqual(plan.primary_reload_type(), "qbit_hot")
        self.assertIn("qBit", plan.qbit_hot_sections)


if __name__ == "__main__":
    unittest.main()
