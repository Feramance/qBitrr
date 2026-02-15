"""Configuration version management for qBitrr.

This module manages config schema versioning and migrations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.version import InvalidVersion, Version

if TYPE_CHECKING:
    from qBitrr.gen_config import MyConfig

# Current expected config version - updated automatically by bump2version
EXPECTED_CONFIG_VERSION = "5.9.0"

# Legacy integer version → semver mapping
_LEGACY_VERSION_MAP = {
    1: "0.0.1",
    2: "0.0.2",
    3: "0.0.3",
    4: "0.0.4",
}

logger = logging.getLogger(__name__)


def _parse_version(v: str | int) -> Version:
    """Parse a version string or legacy integer into a packaging.version.Version."""
    if isinstance(v, int):
        v = _LEGACY_VERSION_MAP.get(v, f"0.0.{v}")
    try:
        return Version(str(v))
    except InvalidVersion:
        logger.warning(f"Invalid version string: {v}, falling back to 0.0.1")
        return Version("0.0.1")


def get_config_version(config: MyConfig) -> str:
    """
    Get the ConfigVersion from the config file.

    Args:
        config: MyConfig instance

    Returns:
        Config version as a semver string
    """
    version = config.get("Settings.ConfigVersion", fallback="0.0.1")
    if isinstance(version, int):
        return _LEGACY_VERSION_MAP.get(version, f"0.0.{version}")
    try:
        Version(str(version))
        return str(version)
    except InvalidVersion:
        logger.warning(f"Invalid ConfigVersion value: {version}, defaulting to 0.0.1")
        return "0.0.1"


def set_config_version(config: MyConfig, version: str) -> None:
    """
    Set the ConfigVersion in the config file.

    Args:
        config: MyConfig instance
        version: Version string to set
    """
    if "Settings" not in config.config:
        from tomlkit import table

        config.config["Settings"] = table()

    config.config["Settings"]["ConfigVersion"] = version
    logger.info(f"Set ConfigVersion to {version}")


def validate_config_version(config: MyConfig) -> tuple[bool, str | None]:
    """
    Validate config version and determine if migration is needed.

    Args:
        config: MyConfig instance

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None): Config version matches expected
        - (True, "migration_needed"): Config version is older, migration required
        - (False, error_msg): Config version is newer, show error to user
    """
    current = _parse_version(get_config_version(config))
    expected = _parse_version(EXPECTED_CONFIG_VERSION)

    if current == expected:
        logger.debug(f"Config version matches expected: {EXPECTED_CONFIG_VERSION}")
        return True, None

    if current < expected:
        logger.info(
            f"Config version {current} is older than expected {expected}, " "migration needed"
        )
        return True, "migration_needed"

    # Config version is newer than expected
    error_msg = (
        f"Config version mismatch: found {current}, expected {expected}. "
        f"Your config may have been created with a newer version of qBitrr and may not work correctly. "
        f"Please update qBitrr or restore a compatible config backup."
    )
    logger.error(error_msg)
    return False, error_msg


def backup_config(config_path: Path) -> Path | None:
    """
    Create a timestamped backup of the config file.

    Args:
        config_path: Path to config.toml

    Returns:
        Path to backup file, or None if backup failed
    """
    if not config_path.exists():
        logger.warning(f"Config file not found for backup: {config_path}")
        return None

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = config_path.parent / f"{config_path.stem}.backup.{timestamp}{config_path.suffix}"

    try:
        import shutil

        shutil.copy2(config_path, backup_path)
        logger.info(f"Created config backup: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create config backup: {e}")
        return None


def restore_config_backup(backup_path: Path, config_path: Path) -> bool:
    """
    Restore config from a backup file.

    Args:
        backup_path: Path to backup file
        config_path: Path to config.toml

    Returns:
        True if restore succeeded, False otherwise
    """
    if not backup_path.exists():
        logger.error(f"Backup file not found: {backup_path}")
        return False

    try:
        import shutil

        shutil.copy2(backup_path, config_path)
        logger.info(f"Restored config from backup: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to restore config from backup: {e}")
        return False
