#!/usr/bin/env python3
"""
Targeted database repair for qBitrr.

Only the moviequeuemodel table is corrupted. This script:
1. Creates a fresh database with proper schema
2. Copies all accessible data from corrupted database
3. Skips/recreates the corrupted moviequeuemodel table
"""

import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

DB_PATH = Path("/home/qBitrr/.config/qBitManager/qbitrr.db")


def main():
    """Run targeted database repair."""
    logger.info("=" * 60)
    logger.info("Starting targeted database repair")
    logger.info("=" * 60)

    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}")
        return 1

    # Create backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.parent / f"qbitrr.db.corrupted_{timestamp}"
    logger.info(f"Creating backup: {backup_path}")
    shutil.copy2(DB_PATH, backup_path)

    # Path for new database
    new_db_path = DB_PATH.parent / "qbitrr.db.new"
    if new_db_path.exists():
        new_db_path.unlink()

    logger.info("Opening corrupted database...")
    old_conn = sqlite3.connect(str(DB_PATH))
    old_cursor = old_conn.cursor()

    logger.info("Creating new database...")
    new_conn = sqlite3.connect(str(new_db_path))
    new_cursor = new_conn.cursor()

    # Get all tables
    old_cursor.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = old_cursor.fetchall()

    logger.info(f"Found {len(tables)} tables to process")

    total_rows = 0
    skipped_tables = []

    # Process each table
    for table_name, create_sql in tables:
        logger.info(f"\nProcessing table: {table_name}")

        # Create table in new database
        try:
            if create_sql:
                logger.info(f"  Creating table structure...")
                new_cursor.execute(create_sql)
        except Exception as e:
            logger.error(f"  ❌ Failed to create table: {e}")
            skipped_tables.append((table_name, "create failed"))
            continue

        # Try to copy data
        try:
            # Get row count
            old_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = old_cursor.fetchone()[0]
            logger.info(f"  Found {count} rows")

            if count > 0:
                # Get all rows
                old_cursor.execute(f"SELECT * FROM {table_name}")
                rows = old_cursor.fetchall()

                # Get column count
                col_count = len(rows[0]) if rows else 0

                # Insert rows
                if rows:
                    placeholders = ",".join(["?" * col_count])
                    new_cursor.executemany(
                        f"INSERT INTO {table_name} VALUES ({placeholders})", rows
                    )
                    logger.info(f"  ✓ Copied {len(rows)} rows")
                    total_rows += len(rows)
            else:
                logger.info(f"  Table is empty - skipping data copy")

        except sqlite3.DatabaseError as e:
            if "malformed" in str(e).lower():
                logger.warning(f"  ⚠ Table {table_name} is corrupted - skipping data")
                logger.info(f"  Creating empty table structure only")
                skipped_tables.append((table_name, "corrupted"))
            else:
                logger.error(f"  ❌ Error reading table: {e}")
                skipped_tables.append((table_name, str(e)))
        except Exception as e:
            logger.error(f"  ❌ Unexpected error: {e}")
            skipped_tables.append((table_name, str(e)))

    # Copy indexes
    logger.info("\nCopying indexes...")
    old_cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
    indexes = old_cursor.fetchall()
    for (index_sql,) in indexes:
        try:
            new_cursor.execute(index_sql)
            logger.info(f"  ✓ Created index")
        except Exception as e:
            logger.warning(f"  ⚠ Failed to create index: {e}")

    # Commit changes
    new_conn.commit()

    # Verify new database
    logger.info("\nVerifying new database integrity...")
    new_cursor.execute("PRAGMA integrity_check")
    result = new_cursor.fetchone()[0]

    old_conn.close()
    new_conn.close()

    if result == "ok":
        logger.info("✓ New database integrity check PASSED")

        # Replace old database with new one
        logger.info("\nReplacing corrupted database with repaired version...")
        DB_PATH.unlink()
        shutil.move(str(new_db_path), str(DB_PATH))

        logger.info("=" * 60)
        logger.info("✓ Database repair SUCCESSFUL!")
        logger.info("=" * 60)
        logger.info(f"Total rows recovered: {total_rows:,}")
        logger.info(f"Backup saved to: {backup_path}")

        if skipped_tables:
            logger.warning("\nSkipped tables (will be repopulated by application):")
            for table, reason in skipped_tables:
                logger.warning(f"  - {table}: {reason}")

        return 0
    else:
        logger.error(f"❌ New database integrity check FAILED: {result}")
        logger.error("Keeping original database")
        new_db_path.unlink()
        return 1


if __name__ == "__main__":
    sys.exit(main())
