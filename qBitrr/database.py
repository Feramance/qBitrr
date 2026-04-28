"""Single consolidated database for all Arr instances."""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from pathlib import Path

from peewee import Model, OperationalError, SqliteDatabase

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
_TARGET_DB_SCHEMA_VERSION = 2
_ARR_FILE_TABLE_MODELS = (
    MoviesFilesModel,
    EpisodeFilesModel,
    AlbumFilesModel,
    SeriesFilesModel,
    ArtistFilesModel,
    TrackFilesModel,
)


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
            raise RuntimeError(
                f"Database '{db_path}' is corrupt and could not be repaired or removed. "
                "Please manually delete it and restart."
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
                _apply_db_schema_migrations(_db)
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


def _quote_identifier(identifier: str) -> str:
    """Safely quote SQLite identifiers after validating expected characters."""
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier):
        raise ValueError(f"Invalid SQLite identifier: {identifier}")
    return f'"{identifier}"'


def _table_exists(db: SqliteDatabase, table_name: str) -> bool:
    """Return True when the given table exists."""
    cursor = db.execute_sql(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _get_table_columns(db: SqliteDatabase, table_name: str) -> list[str]:
    """Fetch table columns in declaration order."""
    cursor = db.execute_sql(f"PRAGMA table_info({_quote_identifier(table_name)})")
    return [row[1] for row in cursor.fetchall()]


def _has_composite_primary_key(
    db: SqliteDatabase,
    table_name: str,
    expected_columns: tuple[str, ...],
) -> bool:
    """Check whether table uses the expected composite primary key columns."""
    cursor = db.execute_sql(f"PRAGMA table_info({_quote_identifier(table_name)})")
    pk_rows = sorted(
        ((row[5], row[1]) for row in cursor.fetchall() if row[5] > 0), key=lambda r: r[0]
    )
    pk_columns = tuple(name for _, name in pk_rows)
    return pk_columns == expected_columns


def _drop_non_auto_indexes_for_table(db: SqliteDatabase, table_name: str) -> None:
    """Drop explicitly created indexes for a table before rebuilding it."""
    cursor = db.execute_sql(f"PRAGMA index_list({_quote_identifier(table_name)})")
    for row in cursor.fetchall():
        # Columns: seq, name, unique, origin, partial
        index_name = row[1]
        if index_name.startswith("sqlite_autoindex_"):
            continue
        db.execute_sql(f"DROP INDEX IF EXISTS {_quote_identifier(index_name)}")


def _copy_table_with_dedupe(
    db: SqliteDatabase,
    source_table: str,
    destination_table: str,
    copy_columns: list[str],
) -> None:
    """Copy rows from source to destination, deduping by (EntryId, ArrInstance)."""
    quoted_columns = ", ".join(_quote_identifier(col) for col in copy_columns)
    has_entry_id = "EntryId" in copy_columns
    has_arr_instance = "ArrInstance" in copy_columns

    if has_entry_id and has_arr_instance:
        db.execute_sql(
            f"""
            INSERT INTO {_quote_identifier(destination_table)} ({quoted_columns})
            SELECT {quoted_columns}
            FROM (
                SELECT
                    {quoted_columns},
                    ROW_NUMBER() OVER (
                        PARTITION BY "EntryId", "ArrInstance"
                        ORDER BY rowid DESC
                    ) AS _qbitrr_rn
                FROM {_quote_identifier(source_table)}
            )
            WHERE _qbitrr_rn = 1
            """
        )
    else:
        db.execute_sql(
            f"""
            INSERT INTO {_quote_identifier(destination_table)} ({quoted_columns})
            SELECT {quoted_columns}
            FROM {_quote_identifier(source_table)}
            """
        )


def _rebuild_arr_file_table_with_composite_pk(db: SqliteDatabase, model: type[Model]) -> None:
    """Rebuild an Arr file table to match canonical composite PK schema."""
    table_name = model._meta.table_name
    legacy_table_name = f"{table_name}__legacy_pre_schema_v{_TARGET_DB_SCHEMA_VERSION}"

    if _table_exists(db, legacy_table_name):
        raise RuntimeError(
            f"Cannot migrate table {table_name}: legacy table {legacy_table_name} already exists."
        )

    with db.atomic():
        old_row_count_cursor = db.execute_sql(
            f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}"
        )
        old_row_count = old_row_count_cursor.fetchone()[0]

        db.execute_sql(
            f"ALTER TABLE {_quote_identifier(table_name)} RENAME TO {_quote_identifier(legacy_table_name)}"
        )
        _drop_non_auto_indexes_for_table(db, legacy_table_name)
        model.create_table(safe=False)

        source_columns = set(_get_table_columns(db, legacy_table_name))
        destination_columns = _get_table_columns(db, table_name)
        copy_columns = [col for col in destination_columns if col in source_columns]
        if not copy_columns:
            raise RuntimeError(
                f"Cannot migrate table {table_name}: no overlapping columns to copy"
            )

        _copy_table_with_dedupe(
            db=db,
            source_table=legacy_table_name,
            destination_table=table_name,
            copy_columns=copy_columns,
        )

        new_row_count_cursor = db.execute_sql(
            f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}"
        )
        new_row_count = new_row_count_cursor.fetchone()[0]
        dropped_duplicates = max(0, old_row_count - new_row_count)

        db.execute_sql(f"DROP TABLE {_quote_identifier(legacy_table_name)}")
        logger.info(
            "Migrated table %s to composite primary key (EntryId, ArrInstance); "
            "rows before=%d, after=%d, duplicates dropped=%d",
            table_name,
            old_row_count,
            new_row_count,
            dropped_duplicates,
        )


def _migrate_arr_file_table_constraints(db: SqliteDatabase) -> None:
    """Ensure all Arr file tables use the canonical composite PK schema."""
    expected_pk = ("EntryId", "ArrInstance")
    for model in _ARR_FILE_TABLE_MODELS:
        table_name = model._meta.table_name
        if not _table_exists(db, table_name):
            continue
        if _has_composite_primary_key(db, table_name, expected_pk):
            continue
        logger.warning(
            "Schema drift detected for table %s. Rebuilding to enforce primary key %s.",
            table_name,
            expected_pk,
        )
        _rebuild_arr_file_table_with_composite_pk(db, model)


def _get_db_schema_version(db: SqliteDatabase) -> int:
    """Read the SQLite user_version schema marker."""
    cursor = db.execute_sql("PRAGMA user_version")
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def _set_db_schema_version(db: SqliteDatabase, version: int) -> None:
    """Write the SQLite user_version schema marker."""
    db.execute_sql(f"PRAGMA user_version = {int(version)}")


def _migrate_v2_catalog_denormalized_columns(db: SqliteDatabase) -> None:
    """Add catalog denormalized count columns used by WebUI (see qBitrr.tables + catalog_rollups)."""
    from qBitrr.tables import (
        AlbumFilesModel,
        ArtistFilesModel,
        EpisodeFilesModel,
        SeriesFilesModel,
        TrackFilesModel,
    )

    additions = [
        (
            AlbumFilesModel,
            [
                ("TotalTracks", "INTEGER DEFAULT 0"),
            ],
        ),
        (
            SeriesFilesModel,
            [
                ("SeasonCount", "INTEGER DEFAULT 0"),
                ("EpisodeTotalCount", "INTEGER DEFAULT 0"),
            ],
        ),
        (
            ArtistFilesModel,
            [
                ("AlbumCount", "INTEGER DEFAULT 0"),
                ("TrackTotalCount", "INTEGER DEFAULT 0"),
            ],
        ),
    ]
    for model, cols in additions:
        tn = model._meta.table_name
        if not _table_exists(db, tn):
            continue
        have = set(_get_table_columns(db, tn))
        for col_name, col_def in cols:
            if col_name in have:
                continue
            db.execute_sql(
                f"ALTER TABLE {_quote_identifier(tn)} ADD COLUMN {_quote_identifier(col_name)} {col_def}"
            )
            logger.info("Added column %s.%s", tn, col_name)

    amt = AlbumFilesModel._meta.table_name
    trt = TrackFilesModel._meta.table_name
    sert = SeriesFilesModel._meta.table_name
    ept = EpisodeFilesModel._meta.table_name
    art = ArtistFilesModel._meta.table_name
    try:
        with db.atomic():
            if (
                _table_exists(db, amt)
                and _table_exists(db, trt)
                and "TotalTracks" in _get_table_columns(db, amt)
            ):
                for album in AlbumFilesModel.select().iterator():  # type: ignore[arg-type]
                    n = (
                        TrackFilesModel.select()
                        .where(
                            (TrackFilesModel.AlbumId == album.EntryId)
                            & (TrackFilesModel.ArrInstance == album.ArrInstance)
                        )
                        .count()
                    )
                    AlbumFilesModel.update(TotalTracks=n).where(
                        (AlbumFilesModel.EntryId == album.EntryId)
                        & (AlbumFilesModel.ArrInstance == album.ArrInstance)
                    ).execute()
            if (
                _table_exists(db, ept)
                and _table_exists(db, sert)
                and "EpisodeTotalCount" in _get_table_columns(db, sert)
                and "SeasonCount" in _get_table_columns(db, sert)
            ):
                for srow in SeriesFilesModel.select().iterator():  # type: ignore[arg-type]
                    ep_q = EpisodeFilesModel.select().where(
                        (EpisodeFilesModel.ArrInstance == srow.ArrInstance)
                        & (EpisodeFilesModel.SeriesId == srow.EntryId)
                    )
                    ep_total = ep_q.count()
                    sn = (
                        EpisodeFilesModel.select(EpisodeFilesModel.SeasonNumber)
                        .where(
                            (EpisodeFilesModel.ArrInstance == srow.ArrInstance)
                            & (EpisodeFilesModel.SeriesId == srow.EntryId)
                        )
                        .distinct()
                        .count()
                    )
                    SeriesFilesModel.update(SeasonCount=sn, EpisodeTotalCount=ep_total).where(
                        (SeriesFilesModel.EntryId == srow.EntryId)
                        & (SeriesFilesModel.ArrInstance == srow.ArrInstance)
                    ).execute()
            if (
                _table_exists(db, art)
                and _table_exists(db, amt)
                and _table_exists(db, trt)
                and "AlbumCount" in _get_table_columns(db, art)
            ):
                for arow in ArtistFilesModel.select().iterator():  # type: ignore[arg-type]
                    alb_n = (
                        AlbumFilesModel.select()
                        .where(
                            (AlbumFilesModel.ArtistId == arow.EntryId)
                            & (AlbumFilesModel.ArrInstance == arow.ArrInstance)
                        )
                        .count()
                    )
                    tr_n = (
                        TrackFilesModel.select()
                        .join(
                            AlbumFilesModel,
                            on=(TrackFilesModel.AlbumId == AlbumFilesModel.EntryId),
                        )
                        .where(
                            (TrackFilesModel.ArrInstance == AlbumFilesModel.ArrInstance)
                            & (TrackFilesModel.ArrInstance == arow.ArrInstance)
                            & (AlbumFilesModel.ArtistId == arow.EntryId)
                        )
                        .count()
                    )
                    ArtistFilesModel.update(AlbumCount=alb_n, TrackTotalCount=tr_n).where(
                        (ArtistFilesModel.EntryId == arow.EntryId)
                        & (ArtistFilesModel.ArrInstance == arow.ArrInstance)
                    ).execute()
    except Exception as e:
        logger.warning("Backfill of denormalized catalog columns failed: %s", e)


def _apply_db_schema_migrations(db: SqliteDatabase) -> None:
    """Run idempotent DB schema migrations guarded by user_version."""
    current_version = _get_db_schema_version(db)
    if current_version >= _TARGET_DB_SCHEMA_VERSION:
        return

    logger.info(
        "Database schema upgrade needed (%d -> %d).",
        current_version,
        _TARGET_DB_SCHEMA_VERSION,
    )
    _migrate_arr_file_table_constraints(db)
    if current_version < 2:
        _migrate_v2_catalog_denormalized_columns(db)
    _set_db_schema_version(db, _TARGET_DB_SCHEMA_VERSION)
    logger.info("Database schema upgrade complete (version %d).", _TARGET_DB_SCHEMA_VERSION)


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
