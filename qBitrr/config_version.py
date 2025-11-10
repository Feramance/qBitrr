"""Configuration version management for qBitrr.

This module manages config schema versioning and migrations.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qBitrr.gen_config import MyConfig

# Current expected config version - increment when schema changes require migration
EXPECTED_CONFIG_VERSION = 1

logger = logging.getLogger(__name__)


def get_config_version(config: MyConfig) -> int:
    """
    Get the ConfigVersion from the config file.

    Args:
        config: MyConfig instance

    Returns:
        Config version as integer, defaults to 1 if not found
    """
    version = config.get("Settings.ConfigVersion", fallback=1)
    try:
        return int(version)
    except (ValueError, TypeError):
        logger.warning(f"Invalid ConfigVersion value: {version}, defaulting to 1")
        return 1


def set_config_version(config: MyConfig, version: int) -> None:
    """
    Set the ConfigVersion in the config file.

    Args:
        config: MyConfig instance
        version: Version number to set
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
    current_version = get_config_version(config)

    if current_version == EXPECTED_CONFIG_VERSION:
        logger.debug(f"Config version matches expected: {EXPECTED_CONFIG_VERSION}")
        return True, None

    if current_version < EXPECTED_CONFIG_VERSION:
        logger.info(
            f"Config version {current_version} is older than expected {EXPECTED_CONFIG_VERSION}, "
            "migration needed"
        )
        return True, "migration_needed"

    # Config version is newer than expected
    error_msg = (
        f"Config version mismatch: found {current_version}, expected {EXPECTED_CONFIG_VERSION}. "
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
