"""SQLite database recovery utilities."""

from __future__ import annotations

import logging
import shutil
import sqlite3
from pathlib import Path

logger = logging.getLogger("qBitrr.DBRecovery")


class DatabaseRecoveryError(Exception):
    """Raised when database recovery fails."""


def checkpoint_wal(db_path: Path, logger_override=None) -> bool:
    """
    Force checkpoint of WAL file to main database.

    This operation flushes all Write-Ahead Log entries to the main database
    file, which can resolve certain types of corruption and reduce the risk
    of data loss.

    Args:
        db_path: Path to SQLite database file
        logger_override: Optional logger instance to use instead of module logger

    Returns:
        True if successful, False otherwise
    """
    log = logger_override or logger

    try:
        log.info("Starting WAL checkpoint for database: %s", db_path)
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        cursor = conn.cursor()

        # Force WAL checkpoint with TRUNCATE mode
        # This checkpoints all frames and truncates the WAL file
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        result = cursor.fetchone()

        conn.close()

        # Result is (busy, log_pages, checkpointed_pages)
        # If busy=0, checkpoint was fully successful
        if result and result[0] == 0:
            log.info(
                "WAL checkpoint successful: %s frames checkpointed, %s pages in log",
                result[2],
                result[1],
            )
            return True
        else:
            log.warning(
                "WAL checkpoint partially successful: result=%s (database may be busy)",
                result,
            )
            return True  # Still consider partial success as success

    except sqlite3.OperationalError as e:
        log.error("WAL checkpoint failed (OperationalError): %s", e)
        return False
    except Exception as e:
        log.error("WAL checkpoint failed (unexpected error): %s", e)
        return False


def repair_database(db_path: Path, backup: bool = True, logger_override=None) -> bool:
    """
    Attempt to repair corrupted SQLite database via dump/restore.

    This operation:
    1. Creates a backup of the corrupted database
    2. Dumps all recoverable data to a temporary database
    3. Replaces the original with the repaired copy
    4. Verifies integrity of the repaired database

    WARNING: Some data may be lost if corruption is severe.

    Args:
        db_path: Path to SQLite database file
        backup: Whether to create backup before repair (default: True)
        logger_override: Optional logger instance to use instead of module logger

    Returns:
        True if repair successful, False otherwise

    Raises:
        DatabaseRecoveryError: If repair fails critically
    """
    log = logger_override or logger

    backup_path = db_path.with_suffix(".db.backup")
    temp_path = db_path.with_suffix(".db.temp")

    try:
        # Step 1: Backup original
        if backup:
            log.info("Creating backup: %s", backup_path)
            shutil.copy2(db_path, backup_path)

        # Step 2: Dump recoverable data
        log.info("Dumping recoverable data from corrupted database...")
        source_conn = sqlite3.connect(str(db_path))

        temp_conn = sqlite3.connect(str(temp_path))

        # Dump schema and data
        skipped_rows = 0
        for line in source_conn.iterdump():
            try:
                temp_conn.execute(line)
            except sqlite3.Error as e:
                # Log but continue - recover what we can
                skipped_rows += 1
                log.debug("Skipping corrupted row during dump: %s", e)

        if skipped_rows > 0:
            log.warning("Skipped %s corrupted rows during dump", skipped_rows)

        temp_conn.commit()
        temp_conn.close()
        source_conn.close()

        # Step 3: Replace original with repaired copy
        log.info("Replacing database with repaired version...")
        db_path.unlink()
        shutil.move(str(temp_path), str(db_path))

        # Step 4: Verify integrity
        log.info("Verifying integrity of repaired database...")
        verify_conn = sqlite3.connect(str(db_path))
        cursor = verify_conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        verify_conn.close()

        if result != "ok":
            raise DatabaseRecoveryError(f"Repair verification failed: {result}")

        log.info("Database repair successful!")
        return True

    except Exception as e:
        log.error("Database repair failed: %s", e)

        # Attempt to restore backup
        if backup and backup_path.exists():
            log.warning("Restoring from backup...")
            try:
                shutil.copy2(backup_path, db_path)
                log.info("Backup restored successfully")
            except Exception as restore_error:
                log.error("Failed to restore backup: %s", restore_error)

        # Cleanup temp files
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass  # Best effort cleanup

        raise DatabaseRecoveryError(f"Repair failed: {e}") from e


def vacuum_database(db_path: Path, logger_override=None) -> bool:
    """
    Run VACUUM to reclaim space and optimize database.

    VACUUM rebuilds the database file, repacking it into a minimal amount of
    disk space. This can help resolve some types of corruption and improve
    performance.

    Note: VACUUM requires free disk space approximately 2x the database size.

    Args:
        db_path: Path to SQLite database file
        logger_override: Optional logger instance to use instead of module logger

    Returns:
        True if successful, False otherwise
    """
    log = logger_override or logger

    try:
        log.info("Running VACUUM on database: %s", db_path)
        conn = sqlite3.connect(str(db_path), timeout=30.0)

        conn.execute("VACUUM")
        conn.close()

        log.info("VACUUM completed successfully")
        return True

    except sqlite3.OperationalError as e:
        log.error("VACUUM failed (OperationalError): %s", e)
        return False
    except Exception as e:
        log.error("VACUUM failed (unexpected error): %s", e)
        return False
