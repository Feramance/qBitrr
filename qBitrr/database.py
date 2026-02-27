"""Single consolidated database for all Arr instances."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from peewee import SqliteDatabase

from qBitrr.config import APPDATA_FOLDER
from qBitrr.db_lock import with_database_retry
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


def _offer_fresh_start(db_path: Path) -> None:
    """
    Delete corrupt database so a fresh one is created on connect.
    Use only after repair has failed; causes loss of existing DB data.
    """
    try:
        for candidate in (
            db_path,
            db_path.parent / f"{db_path.name}-wal",
            db_path.parent / f"{db_path.name}-shm",
        ):
            try:
                candidate.unlink()
            except FileNotFoundError:
                continue
        logger.warning(
            "Deleted corrupt database and SQLite WAL/SHM files; "
            "a fresh database will be created on connect.",
        )
    except Exception as e:
        logger.debug("Could not delete corrupt database files: %s", e)


def _startup_integrity_check_and_repair(db_path: Path) -> None:
    """
    Run PRAGMA integrity_check on existing database; if not ok, try WAL checkpoint
    then full repair. Runs once at startup before any connection so repair has no contention.
    """
    if not db_path.exists():
        return
    result = "unknown"
    try:
        with sqlite3.connect(str(db_path), timeout=10.0) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
        if result == "ok":
            return
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
                return
        except Exception as e:
            logger.debug("Integrity re-check after checkpoint failed: %s", e)

    logger.warning("Attempting full database repair (dump/restore)...")
    try:
        if repair_database(db_path, backup=True, logger_override=logger):
            try:
                with sqlite3.connect(str(db_path), timeout=10.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check")
                    result = cursor.fetchone()[0]
                if result == "ok":
                    logger.info("Database repair successful - integrity verified")
                    return
                logger.critical(
                    "Database repair completed but integrity still failing: %s. "
                    "Continuing anyway; consider manual repair or fresh DB.",
                    result,
                )
            except Exception as e:
                logger.critical("Database repair verification failed: %s. Continuing anyway.", e)
            return
    except Exception as e:
        from qBitrr.db_recovery import DatabaseRecoveryError

        logger.critical(
            "Automatic database repair failed: %s. "
            "Corrupt database will be removed and a fresh one created on connect (data loss).",
            e,
        )
        if isinstance(e, DatabaseRecoveryError) and db_path.exists():
            _offer_fresh_start(db_path)


def get_database() -> SqliteDatabase:
    """Get or create the global database instance."""
    global _db
    if _db is None:
        db_path = Path(APPDATA_FOLDER) / "qbitrr.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

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

        # Automatic startup repair: integrity check and repair before any connection
        _startup_integrity_check_and_repair(db_path)

        # Connect with retry logic
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

        # Create all tables
        _db.create_tables(models, safe=True)

        # Run migrations
        _migrate_arrinstance_field(models)
        _create_arrinstance_indexes(_db, models)

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

                    # Check if index already exists
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
                        (index_name,),
                    )
                    if cursor.fetchone():
                        continue  # Index already exists

                    # Create index
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
