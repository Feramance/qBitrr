"""Unit tests for config_reload_policy key classification."""

from __future__ import annotations

import unittest


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

    def test_readarr_keys_follow_arr_policy(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(
            classify_config_key("Readarr-Books.URI"),
            ReloadCategory.ARR_PRESERVE_DB,
        )
        self.assertEqual(
            classify_config_key("Readarr-Books.EntrySearch.QualityProfileMappings"),
            ReloadCategory.ARR_RESET_DB,
        )
        self.assertEqual(
            classify_config_key("Readarr-Books.Torrent.StalledDelay"),
            ReloadCategory.LIVE,
        )
        self.assertEqual(
            classify_config_key("Readarr-Books.EntrySearch.SearchMissing"),
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
                "Settings.AutoPauseResume": True,
            }
        )
        self.assertEqual(plan.primary_reload_type(), "live")
        self.assertFalse(plan.needs_full_restart)
        self.assertEqual(
            plan.live_keys,
            ["Settings.LoopSleepTimer", "Settings.AutoPauseResume"],
        )
        self.assertFalse(plan.arr_live_instances)

    def test_failed_recheck_category_requires_full_restart(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(
            classify_config_key("Settings.FailedCategory"),
            ReloadCategory.FULL_RESTART,
        )
        self.assertEqual(
            classify_config_key("Settings.RecheckCategory"),
            ReloadCategory.FULL_RESTART,
        )

    def test_classify_key_case_insensitive(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(
            classify_config_key("settings.loopsleeptimer"),
            ReloadCategory.LIVE,
        )
        self.assertEqual(
            classify_config_key("radarr.main.uri"),
            ReloadCategory.ARR_PRESERVE_DB,
        )

    def test_classify_changes_arr_live_populates_arr_live_instances(self) -> None:
        from qBitrr.config_reload_policy import classify_config_changes

        plan = classify_config_changes(
            {
                "Radarr.Main.EntrySearch.SearchMissing": True,
                "Radarr.Main.Torrent.AutoDelete": False,
                "Settings.LoopSleepTimer": 15,
            }
        )
        self.assertEqual(plan.primary_reload_type(), "live")
        self.assertIn("Radarr.Main", plan.arr_live_instances)
        self.assertEqual(
            plan.arr_live_instances["Radarr.Main"],
            [
                "Radarr.Main.EntrySearch.SearchMissing",
                "Radarr.Main.Torrent.AutoDelete",
            ],
        )
        self.assertEqual(plan.live_keys, ["Settings.LoopSleepTimer"])

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
