"""Single consolidated database for all Arr instances."""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from pathlib import Path

from peewee import OperationalError, SqliteDatabase

from qBitrr.config import APPDATA_FOLDER
from qBitrr.db_lock import database_lock, with_database_retry
from qBitrr.tables import (
    AlbumFilesModel,
    AlbumQueueModel,
    ArtistFilesModel,
    EpisodeFilesModel,
    EpisodeQueueModel,
    FilesQueued,
    MovieQueueModel,
    MoviesFilesModel,
    SeriesFilesModel,
    TorrentLibrary,
    TrackFilesModel,
)

logger = logging.getLogger("qBitrr.database")

# Global database instance
_db: SqliteDatabase | None = None


def _ensure_db_directory_writable(db_path: Path) -> None:
    """
    Try to make the database directory and file writable (e.g. when running in
    Docker with a mounted volume that had wrong permissions). Ignore errors.
    """
    try:
        os.chmod(db_path.parent, 0o755)
    except (PermissionError, OSError):
        pass
    if db_path.exists():
        try:
            os.chmod(db_path, 0o644)
        except (PermissionError, OSError):
            pass
    for extra in (f"{db_path.name}-wal", f"{db_path.name}-shm"):
        p = db_path.parent / extra
        if p.exists():
            try:
                os.chmod(p, 0o644)
            except (PermissionError, OSError):
                pass


def _offer_fresh_start(db_path: Path) -> bool:
    """
    Delete corrupt database so a fresh one is created on connect.
    Use only after repair has failed; causes loss of existing DB data.

    Returns:
        True if all files were successfully removed, False otherwise.
    """
    all_removed = True
    for candidate in (
        db_path,
        db_path.parent / f"{db_path.name}-wal",
        db_path.parent / f"{db_path.name}-shm",
        db_path.with_suffix(".db.temp-journal"),
    ):
        try:
            candidate.unlink()
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.error("Failed to delete corrupt database file %s: %s", candidate, e)
            all_removed = False
    if all_removed:
        logger.warning(
            "Deleted corrupt database and auxiliary files; "
            "a fresh database will be created on connect.",
        )
    else:
        logger.critical(
            "Could not fully remove corrupt database files. "
            "The database may still be corrupt on next connection.",
        )
    return all_removed


def _startup_integrity_check_and_repair(db_path: Path) -> bool:
    """
    Run PRAGMA integrity_check on existing database; if not ok, try WAL checkpoint
    then full repair. As a last resort, delete the database for a fresh start.

    Returns:
        True if the database is healthy (repaired or fresh), False if corrupt
        and could not be fixed or removed.
    """
    if not db_path.exists():
        return True

    result = "unknown"
    try:
        with sqlite3.connect(str(db_path), timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
        if result == "ok":
            return True
    except Exception as e:
        logger.warning("Startup integrity check failed (will attempt repair): %s", e)

    logger.warning(
        "Database integrity check failed (result=%s). Attempting automatic repair...",
        result,
    )
    from qBitrr.db_recovery import checkpoint_wal, repair_database

    if checkpoint_wal(db_path, logger_override=logger):
        try:
            with sqlite3.connect(str(db_path), timeout=10.0) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]
            if result == "ok":
                logger.info("WAL checkpoint resolved database issue - integrity ok")
                return True
        except Exception as e:
            logger.debug("Integrity re-check after checkpoint failed: %s", e)

    logger.warning("Attempting full database repair (dump/restore)...")
    try:
        if repair_database(db_path, backup=True, logger_override=logger):
            logger.info("Database repair successful - integrity verified")
            return True
    except Exception as e:
        logger.critical(
            "Automatic database repair failed: %s. "
            "Corrupt database will be removed for a fresh start (data loss).",
            e,
        )

    logger.warning("All repair attempts failed. Removing corrupt database for fresh start...")
    if db_path.exists():
        return _offer_fresh_start(db_path)
    return True


def get_database() -> SqliteDatabase:
    """Get or create the global database instance."""
    global _db
    if _db is None:
        db_path = Path(APPDATA_FOLDER) / "qbitrr.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _ensure_db_directory_writable(db_path)

        _db = SqliteDatabase(
            str(db_path),
            pragmas={
                "journal_mode": "wal",
                "cache_size": -64_000,
                "foreign_keys": 1,
                "ignore_check_constraints": 0,
                "synchronous": 2,  # FULL mode - maximum safety, prevents corruption on power loss
                "read_uncommitted": 1,
                "wal_autocheckpoint": 100,  # Checkpoint every 100 pages (more frequent = safer)
                "journal_size_limit": 67108864,  # 64MB max WAL size
            },
            timeout=15,
        )

        if not _startup_integrity_check_and_repair(db_path):
            logger.critical(
                "Database is corrupt and could not be repaired or removed. "
                "Please manually delete '%s' and restart.",
                db_path,
            )

        with database_lock():
            with_database_retry(
                lambda: _db.connect(reuse_if_open=True),
                logger=logger,
            )

            # Bind models to database
            models = [
                MoviesFilesModel,
                EpisodeFilesModel,
                AlbumFilesModel,
                SeriesFilesModel,
                ArtistFilesModel,
                TrackFilesModel,
                MovieQueueModel,
                EpisodeQueueModel,
                AlbumQueueModel,
                FilesQueued,
                TorrentLibrary,
            ]
            _db.bind(models)

            # Create all tables (and indexes); retry once if readonly (e.g. Docker volume perms)
            def _create_tables_and_indexes() -> None:
                _db.create_tables(models, safe=True)
                _migrate_arrinstance_field(models)
                _create_arrinstance_indexes(_db, models)

            try:
                _create_tables_and_indexes()
            except OperationalError as e:
                if "readonly" in str(e).lower():
                    logger.warning(
                        "Database is read-only (often due to volume permissions). "
                        "Attempting to fix permissions and retry..."
                    )
                    _ensure_db_directory_writable(db_path)
                    try:
                        _create_tables_and_indexes()
                    except OperationalError as e2:
                        if "readonly" in str(e2).lower():
                            logger.critical(
                                "Database directory or file is read-only. "
                                "Ensure the config volume is writable by the container user (e.g. set PUID/PGID in docker-compose). "
                                "On the host: chown -R PUID:PGID /path/to/config. "
                                "Alternatively remove the database directory and restart to recreate it (data loss)."
                            )
                            _db.close()
                            _db = None
                        raise
                else:
                    raise

        logger.info("Initialized single database: %s", db_path)

    return _db


def _migrate_arrinstance_field(models: list) -> None:
    """
    Migration: Remove records with empty ArrInstance field.

    After database consolidation, old records don't have ArrInstance set.
    Since we can't reliably determine which instance they belong to,
    we delete them and let the application repopulate with correct values.
    """
    try:
        deleted_count = 0
        for model in models:
            # Check if model has ArrInstance field
            if hasattr(model, "ArrInstance"):
                # Delete records where ArrInstance is NULL or empty string
                query = model.delete().where(
                    (model.ArrInstance.is_null()) | (model.ArrInstance == "")
                )
                count = query.execute()
                if count > 0:
                    logger.info(
                        "Migrated %s: deleted %d records with empty ArrInstance",
                        model.__name__,
                        count,
                    )
                    deleted_count += count

        if deleted_count > 0:
            logger.warning(
                "Database migration: Removed %d old records without ArrInstance. "
                "qBitrr will repopulate data from Arr instances.",
                deleted_count,
            )
    except Exception as e:
        logger.error("Error during ArrInstance migration: %s", e)


def _create_arrinstance_indexes(db: SqliteDatabase, models: list) -> None:
    """
    Create database indexes on ArrInstance field for performance.

    Indexes improve query performance when filtering by ArrInstance,
    which is done on every WebUI page load.
    """
    try:
        with db.atomic():
            cursor = db.cursor()
            for model in models:
                if hasattr(model, "ArrInstance"):
                    table_name = model._meta.table_name
                    index_name = f"idx_arrinstance_{table_name}"

                    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", index_name):
                        logger.warning("Skipping invalid index name: %s", index_name)
                        continue
                    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
                        logger.warning("Skipping invalid table name: %s", table_name)
                        continue

                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                        (index_name,),
                    )
                    if cursor.fetchone():
                        continue

                    cursor.execute(f"CREATE INDEX {index_name} ON {table_name}(ArrInstance)")
                    logger.info("Created index: %s on %s.ArrInstance", index_name, table_name)
    except Exception as e:
        logger.error("Error creating ArrInstance indexes: %s", e)


def get_database_path() -> Path:
    """Get the path to the database file."""
    return Path(APPDATA_FOLDER) / "qbitrr.db"


def checkpoint_database() -> bool:
    """
    Checkpoint the database WAL to prevent corruption on shutdown.

    This is called automatically on graceful shutdown to ensure all
    WAL entries are flushed to the main database file.

    Returns:
        True if checkpoint successful, False otherwise
    """
    from qBitrr.db_recovery import checkpoint_wal

    db_path = get_database_path()
    if not db_path.exists():
        logger.debug("Database file does not exist, skipping checkpoint")
        return True

    logger.info("Checkpointing database WAL before shutdown...")
    return checkpoint_wal(db_path, logger_override=logger)
