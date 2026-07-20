"""Golden-master tests for config_version helpers."""

from __future__ import annotations

import re
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
from qBitrr.gen_config.fields import SETTINGS_FIELDS

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_APP_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)-(?P<build>\d+)$")
_BUNDLED_VERSION_RE = re.compile(
    r'^version\s*=\s*"(?P<version>\d+\.\d+\.\d+-\d+)"\s*$',
    flags=re.MULTILINE,
)


def _config_from_toml(text: str) -> MyConfig:
    doc = parse(text)
    with tempfile.NamedTemporaryFile(suffix=".toml") as tmp:
        return MyConfig(path=tmp.name, config=doc)


def _app_version_from_bundled_data() -> str:
    text = (_REPO_ROOT / "qBitrr/bundled_data.py").read_text(encoding="utf-8")
    match = _BUNDLED_VERSION_RE.search(text)
    if match is None:
        raise AssertionError('qBitrr/bundled_data.py missing version = "MAJOR.MINOR.PATCH-BUILD"')
    return match.group("version")


def _schema_core_from_app_version(app_version: str) -> str:
    match = _APP_VERSION_RE.fullmatch(app_version)
    if match is None:
        raise AssertionError(f"App version must be MAJOR.MINOR.PATCH-BUILD, got {app_version!r}")
    return f"{match.group('major')}.{match.group('minor')}.{match.group('patch')}"


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


class TestConfigVersionBumpPolicy(unittest.TestCase):
    """ConfigVersion is MAJOR.MINOR.PATCH only and tracks the app version core."""

    def test_expected_config_version_is_major_minor_patch(self) -> None:
        self.assertRegex(EXPECTED_CONFIG_VERSION, _CONFIG_VERSION_RE)

    def test_expected_matches_app_version_core(self) -> None:
        self.assertEqual(
            EXPECTED_CONFIG_VERSION,
            _schema_core_from_app_version(_app_version_from_bundled_data()),
        )

    def test_settings_field_default_matches_expected(self) -> None:
        config_version_field = next(
            field for field in SETTINGS_FIELDS if field.path == ("ConfigVersion",)
        )
        self.assertEqual(config_version_field.default, EXPECTED_CONFIG_VERSION)

    def test_config_example_matches_expected(self) -> None:
        text = (_REPO_ROOT / "config.example.toml").read_text(encoding="utf-8")
        match = re.search(
            r'^ConfigVersion\s*=\s*"(?P<version>[^"]+)"\s*$',
            text,
            flags=re.MULTILINE,
        )
        self.assertIsNotNone(match, "config.example.toml missing ConfigVersion")
        assert match is not None
        self.assertEqual(match.group("version"), EXPECTED_CONFIG_VERSION)

    def test_config_file_docs_match_expected(self) -> None:
        text = (_REPO_ROOT / "docs/configuration/config-file.md").read_text(encoding="utf-8")
        match = re.search(
            r'^ConfigVersion\s*=\s*"(?P<version>[^"]+)"\s*$',
            text,
            flags=re.MULTILINE,
        )
        self.assertIsNotNone(match, "config-file.md missing uncommented ConfigVersion")
        assert match is not None
        self.assertEqual(match.group("version"), EXPECTED_CONFIG_VERSION)


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
