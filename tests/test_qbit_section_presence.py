"""qBit is optional: enabled by section presence, never auto-created on validate."""

from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from unittest.mock import MagicMock, patch

from tomlkit import parse

from qBitrr import config as config_module
from qBitrr.gen_config import MyConfig, _validate_and_fill_config
from qBitrr.main import qBitManager


def _config_from_toml(text: str) -> MyConfig:
    doc = parse(text)
    with tempfile.NamedTemporaryFile(suffix=".toml") as tmp:
        return MyConfig(path=tmp.name, config=doc)


class TestValidateDoesNotCreateQbitSection(unittest.TestCase):
    def test_named_only_does_not_create_bare_qbit(self) -> None:
        cfg = _config_from_toml(
            """
            [Settings]
            ConfigVersion = "5.12.12"

            [qBit-General]
            Host = "192.168.0.240"
            Port = 8080
            """
        )
        _validate_and_fill_config(cfg)
        self.assertNotIn("qBit", cfg.config)
        self.assertIn("qBit-General", cfg.config)
        self.assertFalse(cfg.get("qBit-General.Disabled"))

    def test_no_qbit_section_stays_absent(self) -> None:
        cfg = _config_from_toml(
            """
            [Settings]
            ConfigVersion = "5.12.12"
            """
        )
        _validate_and_fill_config(cfg)
        self.assertNotIn("qBit", cfg.config)
        self.assertFalse(any(str(s).startswith("qBit") for s in cfg.config.keys()))

    def test_fills_missing_keys_on_existing_named_section(self) -> None:
        cfg = _config_from_toml(
            """
            [Settings]
            ConfigVersion = "5.12.12"

            [qBit-General]
            Host = "192.168.0.240"
            """
        )
        changed = _validate_and_fill_config(cfg)
        self.assertTrue(changed)
        self.assertEqual(cfg.get("qBit-General.Host"), "192.168.0.240")
        self.assertEqual(cfg.get("qBit-General.Port"), 8105)
        self.assertFalse(cfg.get("qBit-General.Disabled"))
        self.assertNotIn("qBit", cfg.config)


class TestEffectiveQbitDisabledByPresence(unittest.TestCase):
    def setUp(self) -> None:
        self.env_mock = MagicMock()
        self.env_mock.qbit.disabled = None
        self.env_patch = mock.patch.object(config_module, "ENVIRO_CONFIG", self.env_mock)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_no_sections_means_disabled(self) -> None:
        with (
            mock.patch.object(config_module, "SEARCH_ONLY", False),
            mock.patch.object(config_module, "_has_any_qbit_section", return_value=False),
        ):
            self.assertTrue(config_module.get_effective_qbit_disabled())

    def test_named_section_means_enabled(self) -> None:
        with (
            mock.patch.object(config_module, "SEARCH_ONLY", False),
            mock.patch.object(config_module, "_has_any_qbit_section", return_value=True),
        ):
            self.assertFalse(config_module.get_effective_qbit_disabled())

    def test_bare_qbit_disabled_flag_does_not_disable_globally(self) -> None:
        """Presence enables globally; per-instance Disabled is handled at init."""
        config_mock = MagicMock()
        config_mock.get.return_value = True  # would be qBit.Disabled under old logic
        with (
            mock.patch.object(config_module, "SEARCH_ONLY", False),
            mock.patch.object(config_module, "CONFIG", config_mock),
            mock.patch.object(config_module, "_has_any_qbit_section", return_value=True),
        ):
            self.assertFalse(config_module.get_effective_qbit_disabled())


class TestSkipDisabledQbitInstance(unittest.TestCase):
    def test_initialize_skips_disabled_sections(self) -> None:
        manager = MagicMock(spec=qBitManager)
        manager.logger = MagicMock()
        manager.clients = {}
        manager.qbit_versions = {}
        manager.instance_health = {}
        manager._validated_version = False
        manager.current_qbit_version = None

        def _config_get(key: str, fallback=None):
            if key == "qBit-General.Disabled":
                return True
            if key == "qBit.Disabled":
                return False
            return fallback

        with (
            patch("qBitrr.main.QBIT_DISABLED", False),
            patch("qBitrr.main.SEARCH_ONLY", False),
            patch("qBitrr.main.qbit_sections", return_value=["qBit", "qBit-General"]),
            patch("qBitrr.main.CONFIG") as config,
        ):
            config.get.side_effect = _config_get
            qBitManager._initialize_qbit_instances(manager)

        manager._init_instance.assert_called_once_with("qBit", "qBit")
        manager.logger.info.assert_any_call("Skipping disabled qBit instance: %s", "qBit-General")

    def test_prune_drops_disabled_instance_clients(self) -> None:
        class _Fake(qBitManager):
            def __init__(self) -> None:
                self.clients = {"qBit": object(), "qBit-General": object()}
                self.qbit_versions = {"qBit": "5.0", "qBit-General": "5.0"}
                self.instance_metadata = {"qBit": {}, "qBit-General": {}}
                self.instance_health = {"qBit": True, "qBit-General": True}
                self.qbit_category_configs = {}
                self.qbit_category_managers = {}
                self._process_registry = {}
                self.child_processes = []
                self.logger = MagicMock()

        mgr = _Fake()

        def _config_get(key: str, fallback=None):
            if key == "qBit-General.Disabled":
                return True
            if key == "qBit.Disabled":
                return False
            return fallback

        with (
            patch("qBitrr.main.QBIT_DISABLED", False),
            patch("qBitrr.main.SEARCH_ONLY", False),
            patch("qBitrr.main.qbit_sections", return_value=["qBit", "qBit-General"]),
            patch("qBitrr.main.CONFIG") as config,
        ):
            config.get.side_effect = _config_get
            mgr._prune_stale_qbit_runtime()

        self.assertEqual(list(mgr.clients.keys()), ["qBit"])
        self.assertNotIn("qBit-General", mgr.clients)


if __name__ == "__main__":
    unittest.main()
