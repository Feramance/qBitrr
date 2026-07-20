"""Golden-master tests for config.py live-reload getters (Phase 2)."""

from __future__ import annotations

import unittest
from unittest import mock

import qBitrr.config as config_module


def _patch_enviro_config(**settings_overrides: object) -> mock.MagicMock:
    """Replace frozen ENVIRO_CONFIG with a MagicMock (avoids FrozenInstanceError)."""
    mock_env = mock.MagicMock()
    mock_settings = mock.MagicMock()
    for key, value in settings_overrides.items():
        setattr(mock_settings, key, value)
    mock_env.settings = mock_settings
    mock_env.qbit = mock.MagicMock()
    mock_env.qbit.disabled = None
    mock_env.overrides = mock.MagicMock()
    return mock_env


class TestConfigLiveReloadGoldenMaster(unittest.TestCase):
    def setUp(self) -> None:
        self.config_mock = mock.MagicMock()
        self.env_patch = mock.patch.object(config_module, "ENVIRO_CONFIG")
        self.config_patch = mock.patch.object(config_module, "CONFIG", self.config_mock)
        self.env_mock = self.env_patch.start()
        self.config_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.addCleanup(self.config_patch.stop)

    def test_frozen_ping_urls_stale_after_config_change(self) -> None:
        """Characterize import-time constant: does not track CONFIG mutations."""
        original = config_module.PING_URLS
        self.config_mock.get.return_value = ["changed.example"]
        self.env_mock.settings.ping_urls = None
        self.assertEqual(original, config_module.PING_URLS)

    def test_get_ping_urls_effective_reads_live_config(self) -> None:
        self.env_mock.settings.ping_urls = None
        self.config_mock.get.return_value = ["live.example"]
        self.assertEqual(config_module.get_ping_urls_effective(), ["live.example"])

    def test_get_ping_urls_effective_env_wins_over_toml(self) -> None:
        self.env_mock.settings.ping_urls = ["env.example"]
        self.config_mock.get.return_value = ["toml.example"]
        self.assertEqual(config_module.get_ping_urls_effective(), ["env.example"])

    def test_get_failed_category_effective_reads_live_config(self) -> None:
        self.env_mock.settings.failed_category = None
        self.config_mock.get.return_value = "failed-live"
        self.assertEqual(config_module.get_failed_category_effective(), "failed-live")

    def test_get_recheck_category_effective_reads_live_config(self) -> None:
        self.env_mock.settings.recheck_category = None
        self.config_mock.get.return_value = "recheck-live"
        self.assertEqual(config_module.get_recheck_category_effective(), "recheck-live")

    def test_get_loop_sleep_timer_effective_reads_live_config(self) -> None:
        self.env_mock.settings.loop_sleep_timer = None
        self.config_mock.get_duration.return_value = 42
        self.assertEqual(config_module.get_loop_sleep_timer_effective(), 42)

    def test_get_search_loop_delay_effective_reads_live_config(self) -> None:
        self.env_mock.settings.search_loop_delay = None
        self.config_mock.get_duration.return_value = 99
        self.assertEqual(config_module.get_search_loop_delay_effective(), 99)

    def test_get_no_internet_sleep_timer_effective_reads_live_config(self) -> None:
        self.env_mock.settings.no_internet_sleep_timer = None
        self.config_mock.get_duration.return_value = 77
        self.assertEqual(config_module.get_no_internet_sleep_timer_effective(), 77)

    def test_get_ignore_torrents_younger_than_effective_reads_live_config(self) -> None:
        self.env_mock.settings.ignore_torrents_younger_than = None
        self.config_mock.get_duration.return_value = 555
        self.assertEqual(config_module.get_ignore_torrents_younger_than_effective(), 555)

    def test_get_ffprobe_auto_update_effective_reads_live_config(self) -> None:
        self.env_mock.settings.ffprobe_auto_update = None
        self.config_mock.get.return_value = False
        self.assertFalse(config_module.get_ffprobe_auto_update_effective())

    def test_get_completed_download_folder_effective_reads_live_config(self) -> None:
        self.env_mock.settings.completed_download_folder = None
        self.config_mock.get_or_raise.return_value = "/downloads/live"
        self.assertEqual(
            config_module.get_completed_download_folder_effective(), "/downloads/live"
        )


class TestConfigLiveReloadExtendedGetters(unittest.TestCase):
    def setUp(self) -> None:
        self.config_mock = mock.MagicMock()
        self.env_patch = mock.patch.object(config_module, "ENVIRO_CONFIG")
        self.config_patch = mock.patch.object(config_module, "CONFIG", self.config_mock)
        self.env_mock = self.env_patch.start()
        self.config_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.addCleanup(self.config_patch.stop)

    def test_get_auto_update_settings_env_overrides_toml(self) -> None:
        self.env_mock.settings.auto_update_enabled = True
        self.env_mock.settings.auto_update_cron = "0 4 * * *"
        self.config_mock.get.side_effect = lambda key, fallback=None: {
            "Settings.AutoUpdateEnabled": False,
            "Settings.AutoUpdateCron": "0 3 * * 0",
        }.get(key, fallback)
        enabled, cron = config_module.get_auto_update_settings()
        self.assertTrue(enabled)
        self.assertEqual(cron, "0 4 * * *")

    def test_get_auto_pause_resume_effective_env_wins(self) -> None:
        self.env_mock.settings.auto_pause_resume = False
        self.config_mock.get.return_value = True
        self.assertFalse(config_module.get_auto_pause_resume_effective())

    def test_get_effective_qbit_disabled_search_only_forces_disabled(self) -> None:
        self.env_mock.qbit.disabled = False
        with mock.patch.object(config_module, "SEARCH_ONLY", True):
            with mock.patch.object(config_module, "_has_any_qbit_section", return_value=True):
                self.config_mock.get.return_value = False
                self.assertTrue(config_module.get_effective_qbit_disabled())

    def test_get_free_space_guard_disabled_when_minus_one(self) -> None:
        self.env_mock.settings.free_space = None
        self.env_mock.settings.free_space_folder = None
        self.config_mock.get.return_value = "-1"
        free_space, folder = config_module.get_free_space_guard_settings()
        self.assertEqual(free_space, "-1")
        self.assertEqual(folder, "")

    def test_get_free_space_guard_reads_folder_when_enabled(self) -> None:
        self.env_mock.settings.free_space = "10GB"
        self.env_mock.settings.free_space_folder = None
        self.config_mock.get_or_raise.return_value = "/data"
        free_space, folder = config_module.get_free_space_guard_settings()
        self.assertEqual(free_space, "10GB")
        self.assertEqual(folder, "/data")

    def test_failed_category_normalizes_backslashes(self) -> None:
        self.env_mock.settings.failed_category = None
        self.config_mock.get.return_value = "parent\\child"
        with mock.patch.object(config_module, "_CFG_LOGGER") as log:
            result = config_module.get_failed_category_effective()
        self.assertEqual(result, "parent\\child")
        log.warning.assert_called_once()


class TestEnviroConfigHarness(unittest.TestCase):
    def test_patch_whole_enviro_config_avoids_frozen_instance_error(self) -> None:
        mock_env = _patch_enviro_config(ping_urls=["harness.test"])
        with mock.patch.object(config_module, "ENVIRO_CONFIG", mock_env):
            self.assertEqual(config_module.get_ping_urls_effective(), ["harness.test"])
