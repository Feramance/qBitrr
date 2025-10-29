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


def perform_self_update(logger: logging.Logger) -> bool:
    """Attempt to update qBitrr in-place using git or pip.

    Returns True when the update command completed successfully, False otherwise.
    """

    repo_root = Path(__file__).resolve().parent.parent
    git_dir = repo_root / ".git"
    if git_dir.exists():
        logger.debug("Detected git repository at %s", repo_root)
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

    package = "qBitrr2"
    logger.debug("Fallback to pip upgrade for package %s", package)
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
