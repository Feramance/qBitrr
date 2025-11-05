from __future__ import annotations

import logging
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from croniter import croniter
from croniter.croniter import CroniterBadCronError


def get_installation_type() -> str:
    """Detect how qBitrr is installed.

    Returns:
        "binary" - PyInstaller frozen executable
        "git" - Git repository installation
        "pip" - PyPI package installation
    """
    # Check if running as PyInstaller binary
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return "binary"

    # Check for git repository
    repo_root = Path(__file__).resolve().parent.parent
    git_dir = repo_root / ".git"
    if git_dir.exists():
        return "git"

    # Default to pip installation
    return "pip"


class AutoUpdater:
    """Background worker that executes a callback on a cron schedule."""

    def __init__(self, cron_expr: str, callback: Callable[[], None], logger: logging.Logger):
        self._cron_expr = cron_expr
        self._callback = callback
        self._logger = logger
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._iterator = None

    def start(self) -> bool:
        """Start the background worker. Returns False if cron expression is invalid."""

        self.stop()
        try:
            self._iterator = croniter(self._cron_expr, datetime.now())
        except CroniterBadCronError as exc:
            self._logger.error(
                "Auto update disabled: invalid cron expression '%s' (%s)",
                self._cron_expr,
                exc,
            )
            self._iterator = None
            return False

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="AutoUpdater", daemon=True)
        self._thread.start()
        self._logger.info("Auto update scheduled with cron '%s'.", self._cron_expr)
        return True

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
            if thread.is_alive():
                self._logger.warning("Auto update worker failed to stop within timeout")
        self._thread = None

    def _run(self) -> None:
        iterator = self._iterator
        if iterator is None:
            return
        stop_event = self._stop_event
        while True:
            next_run = iterator.get_next(datetime)
            self._logger.debug("Next auto update scheduled for %s", next_run.isoformat())
            while True:
                if stop_event.is_set():
                    return
                wait_seconds = (next_run - datetime.now()).total_seconds()
                if wait_seconds <= 0:
                    break
                stop_event.wait(timeout=min(wait_seconds, 60))
            if stop_event.is_set():
                return
            self._execute()

    def _execute(self) -> None:
        self._logger.info("Auto update triggered")
        try:
            self._callback()
        except Exception:  # pragma: no cover - safeguard for background thread
            self._logger.exception("Auto update failed")
        else:
            self._logger.info("Auto update completed")


def verify_update_success(expected_version: str, logger: logging.Logger) -> bool:
    """Verify that the installed version matches the expected version.

    Args:
        expected_version: Expected version string (e.g., "5.4.3")
        logger: Logger instance for output

    Returns:
        True if version matches, False otherwise
    """
    try:
        # Re-import bundled_data to get fresh version
        pass

        # Remove cached module
        if "qBitrr.bundled_data" in sys.modules:
            del sys.modules["qBitrr.bundled_data"]

        # Re-import
        from qBitrr import bundled_data
        from qBitrr.versioning import normalize_version

        current = normalize_version(bundled_data.version)
        expected = normalize_version(expected_version)

        if current == expected:
            logger.info("Update verified: version %s installed successfully", current)
            return True
        logger.warning(
            "Version mismatch after update: expected %s, got %s",
            expected,
            current,
        )
        return False

    except Exception as exc:
        logger.error("Failed to verify update: %s", exc)
        return False


def perform_self_update(logger: logging.Logger, target_version: str | None = None) -> bool:
    """Attempt to update qBitrr in-place using appropriate method for installation type.

    Args:
        logger: Logger instance for output
        target_version: Optional specific version to update to (e.g., "5.4.3")

    Returns:
        True when the update command completed successfully, False otherwise.
    """

    # Detect installation type
    install_type = get_installation_type()
    logger.debug("Installation type detected: %s", install_type)

    # BINARY INSTALLATION - Cannot auto-update
    if install_type == "binary":
        logger.info("Binary installation detected - manual update required")
        if target_version:
            logger.info(
                "Update available: v%s",
                target_version if target_version.startswith("v") else f"v{target_version}",
            )
            logger.info("Download from: https://github.com/Feramance/qBitrr/releases/latest")
            logger.info("Instructions:")
            logger.info("  1. Download the binary for your platform")
            logger.info("  2. Extract the archive")
            logger.info("  3. Replace current executable with new binary")
            logger.info("  4. Restart qBitrr")
        return False  # Binary updates require manual intervention

    # GIT INSTALLATION
    elif install_type == "git":
        repo_root = Path(__file__).resolve().parent.parent
        repo_root / ".git"
        logger.debug("Git repository detected at %s", repo_root)

        if target_version:
            # Strict version: checkout specific tag
            tag = target_version if target_version.startswith("v") else f"v{target_version}"

            try:
                logger.debug("Fetching tags from remote")
                subprocess.run(
                    ["git", "fetch", "--tags", "--force"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    check=True,
                )

                result = subprocess.run(
                    ["git", "rev-parse", tag],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    logger.error("Tag %s not found in repository", tag)
                    logger.warning("Falling back to git pull")
                else:
                    result = subprocess.run(
                        ["git", "checkout", tag],
                        cwd=str(repo_root),
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    stdout = (result.stdout or "").strip()
                    if stdout:
                        logger.info("git checkout output:\n%s", stdout)
                    logger.info("Checked out tag %s", tag)
                    return True

            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or "").strip()
                logger.error("Failed to checkout tag %s: %s", tag, stderr or exc)
                logger.warning("Falling back to git pull")

        # Default: git pull
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=True,
            )
            stdout = (result.stdout or "").strip()
            if stdout:
                logger.info("git pull output:\n%s", stdout)
            return True
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            logger.error("Failed to update repository via git: %s", stderr or exc)
            return False

    # PIP INSTALLATION
    elif install_type == "pip":
        logger.debug("PyPI installation detected")

        package = "qBitrr2"
        if target_version:
            # Strict version: install exact version
            version = target_version[1:] if target_version.startswith("v") else target_version
            package = f"{package}=={version}"

        logger.debug("Upgrading package: %s", package)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", package],
                capture_output=True,
                text=True,
                check=True,
            )
            stdout = (result.stdout or "").strip()
            if stdout:
                logger.info("pip upgrade output:\n%s", stdout)
            return True
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            logger.error("Failed to upgrade package via pip: %s", stderr or exc)
            return False

    logger.error("Unknown installation type: %s", install_type)
    return False
