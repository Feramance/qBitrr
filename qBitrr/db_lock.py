from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from qBitrr.db_recovery import checkpoint_wal, repair_database
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

    On detecting database corruption, attempts automatic recovery before retrying.

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
    corruption_recovery_attempted = False

    while True:
        try:
            return func()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            error_msg = str(e).lower()

            # Don't retry on non-transient errors
            if "syntax" in error_msg or "constraint" in error_msg:
                raise

            # Detect corruption or persistent I/O errors and attempt recovery (only once)
            if not corruption_recovery_attempted and (
                "disk image is malformed" in error_msg
                or "database disk image is malformed" in error_msg
                or "database corruption" in error_msg
                or "disk i/o error" in error_msg
            ):
                corruption_recovery_attempted = True
                if logger:
                    if "disk i/o error" in error_msg:
                        logger.error(
                            "Persistent database I/O error detected: %s. "
                            "This may indicate disk issues, filesystem problems, or database corruption. "
                            "Attempting automatic recovery...",
                            e,
                        )
                    else:
                        logger.error(
                            "Database corruption detected: %s. Attempting automatic recovery...",
                            e,
                        )

                recovery_succeeded = False
                try:
                    db_path = APPDATA_FOLDER / "qbitrr.db"

                    # Step 1: Try WAL checkpoint (least invasive)
                    if logger:
                        logger.info("Attempting WAL checkpoint...")
                    if checkpoint_wal(db_path, logger):
                        if logger:
                            logger.info("WAL checkpoint successful - retrying operation")
                        recovery_succeeded = True
                    else:
                        # Step 2: Try full repair (more invasive)
                        if logger:
                            logger.warning(
                                "WAL checkpoint failed - attempting full database repair..."
                            )
                        if repair_database(db_path, backup=True, logger_override=logger):
                            if logger:
                                logger.info("Database repair successful - retrying operation")
                            recovery_succeeded = True

                except Exception as recovery_error:
                    if logger:
                        logger.error(
                            "Database recovery error: %s",
                            recovery_error,
                        )

                if recovery_succeeded:
                    # Reset attempt counter after successful recovery
                    attempt = 0
                    time.sleep(1)  # Brief pause before retry
                    continue

                # If we reach here, recovery failed - log and continue with normal retry
                if logger:
                    logger.critical(
                        "Automatic database recovery FAILED. "
                        "Both WAL checkpoint and full database repair were unsuccessful. "
                        "This indicates serious underlying issues. "
                        "Attempting normal retry, but manual intervention will likely be required."
                    )

            attempt += 1
            if attempt >= retries:
                if logger:
                    logger.critical(
                        "Database operation EXHAUSTED %s retry attempts. "
                        "Error: %s. "
                        "This will be re-raised to the calling code for handling.",
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


class ResilientSqliteDatabase:
    """
    Wrapper for Peewee SqliteDatabase that adds retry logic to connection attempts.

    This solves the issue where disk I/O errors occur during database connection
    (specifically when setting PRAGMAs), before query-level retry logic can help.
    """

    def __init__(self, database, max_retries=5, backoff=0.5, logger=None):
        """
        Args:
            database: Peewee SqliteDatabase instance to wrap
            max_retries: Maximum connection retry attempts
            backoff: Initial backoff delay in seconds
            logger: Optional logger instance for logging recovery attempts
        """
        self._db = database
        self._max_retries = max_retries
        self._backoff = backoff
        self._logger = logger

    def __getattr__(self, name):
        """Delegate all attribute access to the wrapped database."""
        return getattr(self._db, name)

    def connect(self, reuse_if_open=False):
        """
        Connect to database with retry logic for transient I/O errors.

        Args:
            reuse_if_open: If True, return without error if already connected

        Returns:
            Result from underlying database.connect()
        """
        import random
        import sqlite3
        import time

        from peewee import DatabaseError, OperationalError

        last_error = None
        delay = self._backoff
        corruption_recovery_attempted = False

        for attempt in range(1, self._max_retries + 1):
            try:
                return self._db.connect(reuse_if_open=reuse_if_open)
            except (OperationalError, DatabaseError, sqlite3.OperationalError) as e:
                error_msg = str(e).lower()

                # Detect corruption or persistent I/O errors and attempt recovery (only once)
                if not corruption_recovery_attempted and (
                    "disk image is malformed" in error_msg
                    or "database disk image is malformed" in error_msg
                    or "database corruption" in error_msg
                    or "disk i/o error" in error_msg
                ):
                    corruption_recovery_attempted = True
                    if self._logger:
                        self._logger.error(
                            "Database corruption detected during connection: %s. "
                            "Attempting automatic recovery...",
                            e,
                        )

                    recovery_succeeded = False
                    try:
                        db_path = APPDATA_FOLDER / "qbitrr.db"

                        # Close current connection if any
                        try:
                            if not self._db.is_closed():
                                self._db.close()
                        except Exception:
                            pass  # Ignore errors closing corrupted connection

                        # Step 1: Try WAL checkpoint
                        if self._logger:
                            self._logger.info("Attempting WAL checkpoint...")
                        if checkpoint_wal(db_path, self._logger):
                            if self._logger:
                                self._logger.info(
                                    "WAL checkpoint successful - retrying connection"
                                )
                            recovery_succeeded = True
                        else:
                            # Step 2: Try full repair
                            if self._logger:
                                self._logger.warning(
                                    "WAL checkpoint failed - attempting full database repair..."
                                )
                            if repair_database(db_path, backup=True, logger_override=self._logger):
                                if self._logger:
                                    self._logger.info(
                                        "Database repair successful - retrying connection"
                                    )
                                recovery_succeeded = True

                    except Exception as recovery_error:
                        if self._logger:
                            self._logger.error(
                                "Database recovery error: %s",
                                recovery_error,
                            )

                    if recovery_succeeded:
                        time.sleep(1)
                        continue

                    # Recovery failed - log and continue with normal retry
                    if self._logger:
                        self._logger.critical(
                            "Automatic database recovery failed. "
                            "Manual intervention may be required."
                        )

                # Retry on transient I/O errors
                if (
                    "disk i/o error" in error_msg
                    or "database is locked" in error_msg
                    or "disk image is malformed" in error_msg
                ):
                    last_error = e

                    if attempt < self._max_retries:
                        # Add jitter to prevent thundering herd
                        jittered_delay = delay * (1 + random.uniform(-0.25, 0.25))
                        time.sleep(jittered_delay)
                        delay = min(delay * 2, 10.0)  # Exponential backoff, max 10s
                    else:
                        # Final attempt failed
                        raise
                else:
                    # Non-transient error, fail immediately
                    raise

        # Should never reach here, but just in case
        if last_error:
            raise last_error


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
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA quick_check")
            result = cursor.fetchone()[0]
        finally:
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
