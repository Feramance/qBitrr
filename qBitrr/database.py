"""Single consolidated database for all Arr instances."""

from __future__ import annotations

import logging
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
                "synchronous": 0,
                "read_uncommitted": 1,
            },
            timeout=15,
        )

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

        db.commit()
    except Exception as e:
        logger.error("Error creating ArrInstance indexes: %s", e)
