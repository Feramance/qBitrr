"""Golden-master tests for config_version helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tomlkit import parse

from qBitrr.config_version import (
    EXPECTED_CONFIG_VERSION,
    _parse_version,
    get_config_version,
    set_config_version,
    validate_config_version,
)
from qBitrr.gen_config import MyConfig


def _config_from_toml(text: str) -> MyConfig:
    doc = parse(text)
    with tempfile.NamedTemporaryFile(suffix=".toml") as tmp:
        return MyConfig(path=tmp.name, config=doc)


class TestParseVersionMatrix(unittest.TestCase):
    def test_legacy_integers_map_to_semver(self) -> None:
        self.assertEqual(str(_parse_version(1)), "0.0.1")
        self.assertEqual(str(_parse_version(4)), "0.0.4")

    def test_invalid_string_falls_back(self) -> None:
        self.assertEqual(str(_parse_version("not-a-version")), "0.0.1")

    def test_semver_passthrough(self) -> None:
        self.assertEqual(str(_parse_version("5.12.11")), "5.12.11")


class TestGetConfigVersion(unittest.TestCase):
    def test_reads_semver_string(self) -> None:
        cfg = _config_from_toml('[Settings]\nConfigVersion = "5.9.0"\n')
        self.assertEqual(get_config_version(cfg), "5.9.0")

    def test_coerces_legacy_integer(self) -> None:
        cfg = _config_from_toml("[Settings]\nConfigVersion = 2\n")
        self.assertEqual(get_config_version(cfg), "0.0.2")


class TestValidateConfigVersionMatrix(unittest.TestCase):
    def test_matches_expected(self) -> None:
        cfg = _config_from_toml(f'[Settings]\nConfigVersion = "{EXPECTED_CONFIG_VERSION}"\n')
        valid, msg = validate_config_version(cfg)
        self.assertTrue(valid)
        self.assertIsNone(msg)

    def test_older_needs_migration(self) -> None:
        cfg = _config_from_toml('[Settings]\nConfigVersion = "0.0.1"\n')
        valid, msg = validate_config_version(cfg)
        self.assertTrue(valid)
        self.assertEqual(msg, "migration_needed")

    def test_newer_is_invalid(self) -> None:
        cfg = _config_from_toml('[Settings]\nConfigVersion = "99.0.0"\n')
        valid, msg = validate_config_version(cfg)
        self.assertFalse(valid)
        self.assertIn("mismatch", msg or "")


class TestSetConfigVersion(unittest.TestCase):
    def test_creates_settings_table_when_missing(self) -> None:
        cfg = _config_from_toml("[qBit]\n")
        set_config_version(cfg, "5.0.0")
        self.assertEqual(cfg.get("Settings.ConfigVersion"), "5.0.0")


class TestBackupConfig(unittest.TestCase):
    def test_backup_creates_timestamped_copy(self) -> None:
        from qBitrr.config_version import backup_config

        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.toml"
            config_path.write_text("[Settings]\n", encoding="utf-8")
            backup = backup_config(config_path)
            self.assertIsNotNone(backup)
            assert backup is not None
            self.assertTrue(backup.exists())
            self.assertIn("config.backup.", backup.name)

    def test_backup_returns_none_for_missing_file(self) -> None:
        from qBitrr.config_version import backup_config

        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(backup_config(Path(tmp) / "missing.toml"))


class TestRestoreConfigBackup(unittest.TestCase):
    def test_restore_overwrites_target(self) -> None:
        from qBitrr.config_version import restore_config_backup

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config.toml"
            backup = Path(tmp) / "config.toml.bak"
            target.write_text("old", encoding="utf-8")
            backup.write_text("restored", encoding="utf-8")
            self.assertTrue(restore_config_backup(backup, target))
            self.assertEqual(target.read_text(encoding="utf-8"), "restored")

    def test_restore_false_when_backup_missing(self) -> None:
        from qBitrr.config_version import restore_config_backup

        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(
                restore_config_backup(Path(tmp) / "missing.bak", Path(tmp) / "config.toml")
            )


if __name__ == "__main__":
    unittest.main()
