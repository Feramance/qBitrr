from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from qBitrr.home_path import APPDATA_FOLDER

if os.name == "nt":  # pragma: no cover - platform specific
    import msvcrt
else:  # pragma: no cover
    import fcntl

_LOCK_FILE = APPDATA_FOLDER.joinpath("qbitrr.db.lock")


class _InterProcessFileLock:
    """Cross-process, re-entrant file lock to guard SQLite access."""

    def __init__(self, path: Path):
        self._path = path
        self._thread_gate = threading.RLock()
        self._local = threading.local()

    def acquire(self) -> None:
        depth = getattr(self._local, "depth", 0)
        if depth == 0:
            self._thread_gate.acquire()
            self._path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(self._path, "a+b")
            try:
                if os.name == "nt":  # pragma: no cover - Windows specific branch
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:  # pragma: no cover - POSIX branch
                    fcntl.flock(handle, fcntl.LOCK_EX)
            except Exception:
                handle.close()
                self._thread_gate.release()
                raise
            self._local.handle = handle
        self._local.depth = depth + 1

    def release(self) -> None:
        depth = getattr(self._local, "depth", 0)
        if depth <= 0:
            raise RuntimeError("Attempted to release an unacquired database lock")
        depth -= 1
        if depth == 0:
            handle = getattr(self._local, "handle")
            try:
                if os.name == "nt":  # pragma: no cover
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    fcntl.flock(handle, fcntl.LOCK_UN)
            finally:
                handle.close()
                del self._local.handle
                self._thread_gate.release()
        self._local.depth = depth

    @contextmanager
    def context(self) -> Iterator[None]:
        self.acquire()
        try:
            yield
        finally:
            self.release()


_DB_LOCK = _InterProcessFileLock(_LOCK_FILE)


@contextmanager
def database_lock() -> Iterator[None]:
    """Provide a shared lock used to serialize SQLite access across processes."""
    with _DB_LOCK.context():
        yield


def with_database_retry(
    func,
    *,
    retries: int = 5,
    backoff: float = 0.5,
    max_backoff: float = 10.0,
    jitter: float = 0.25,
    logger=None,
):
    """
    Execute database operation with retry logic for transient I/O errors.

    Catches:
    - sqlite3.OperationalError (disk I/O, database locked)
    - sqlite3.DatabaseError (corruption that may resolve)

    Does NOT retry:
    - sqlite3.IntegrityError (data constraint violations)
    - sqlite3.ProgrammingError (SQL syntax errors)

    Args:
        func: Callable to execute (should take no arguments)
        retries: Maximum number of retry attempts (default: 5)
        backoff: Initial backoff delay in seconds (default: 0.5)
        max_backoff: Maximum backoff delay in seconds (default: 10.0)
        jitter: Random jitter added to delay in seconds (default: 0.25)
        logger: Logger instance for logging retry attempts

    Returns:
        Result of func() if successful

    Raises:
        sqlite3.OperationalError or sqlite3.DatabaseError if retries exhausted
    """
    import random
    import sqlite3
    import time

    attempt = 0
    while True:
        try:
            return func()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            error_msg = str(e).lower()

            # Don't retry on non-transient errors
            if "syntax" in error_msg or "constraint" in error_msg:
                raise

            attempt += 1
            if attempt >= retries:
                if logger:
                    logger.error(
                        "Database operation failed after %s attempts: %s",
                        retries,
                        e,
                    )
                raise

            delay = min(max_backoff, backoff * (2 ** (attempt - 1)))
            delay += random.random() * jitter

            if logger:
                logger.warning(
                    "Database I/O error (attempt %s/%s): %s. Retrying in %.2fs",
                    attempt,
                    retries,
                    e,
                    delay,
                )

            time.sleep(delay)


def check_database_health(db_path: Path, logger=None) -> tuple[bool, str]:
    """
    Perform lightweight SQLite integrity check.

    Args:
        db_path: Path to SQLite database file
        logger: Logger instance for logging health check results

    Returns:
        (is_healthy, error_message) - True if healthy, False with error message otherwise
    """
    import sqlite3

    try:
        # Use a short timeout to avoid blocking
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        cursor = conn.cursor()

        # Quick integrity check (fast, catches major corruption)
        cursor.execute("PRAGMA quick_check")
        result = cursor.fetchone()[0]

        conn.close()

        if result != "ok":
            error_msg = f"PRAGMA quick_check failed: {result}"
            if logger:
                logger.error("Database health check failed: %s", error_msg)
            return False, error_msg

        if logger:
            logger.debug("Database health check passed")
        return True, "Database healthy"

    except sqlite3.OperationalError as e:
        error_msg = f"Cannot access database: {e}"
        if logger:
            logger.error("Database health check failed: %s", error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error during health check: {e}"
        if logger:
            logger.error("Database health check failed: %s", error_msg)
        return False, error_msg
