#!/usr/bin/env python3
"""
Repair corrupted qBitrr database.

This script uses the existing database recovery tools to repair
the corrupted database caused by the unsafe synchronous=0 setting.
"""

import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DBRepair")

# Find database
DB_PATH = Path("/home/qBitrr/.config/qBitManager/qbitrr.db")
if not DB_PATH.exists():
    logger.error(f"Database not found at {DB_PATH}")
    sys.exit(1)

logger.info(f"Found database at {DB_PATH}")
logger.info(f"Database size: {DB_PATH.stat().st_size:,} bytes")

# Import recovery functions
try:
    from qBitrr.db_recovery import checkpoint_wal, repair_database
except ImportError:
    logger.error(
        "Failed to import qBitrr.db_recovery. Make sure you're running from the correct directory."
    )
    sys.exit(1)


def main():
    """Run database repair."""
    logger.info("=" * 60)
    logger.info("Starting database repair process")
    logger.info("=" * 60)

    # Step 1: Try WAL checkpoint first (least invasive)
    logger.info("\nStep 1: Attempting WAL checkpoint...")
    try:
        if checkpoint_wal(DB_PATH, logger):
            logger.info("✓ WAL checkpoint successful!")

            # Verify if this fixed the issue
            import sqlite3

            try:
                conn = sqlite3.connect(str(DB_PATH))
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]
                conn.close()

                if result == "ok":
                    logger.info("✓ Database integrity verified - repair complete!")
                    return 0
                else:
                    logger.warning(f"Database still has issues: {result}")
                    logger.info("Proceeding to full repair...")
            except Exception as e:
                logger.warning(f"Verification failed: {e}")
                logger.info("Proceeding to full repair...")
        else:
            logger.warning("WAL checkpoint failed or incomplete")
            logger.info("Proceeding to full repair...")
    except Exception as e:
        logger.error(f"WAL checkpoint error: {e}")
        logger.info("Proceeding to full repair...")

    # Step 2: Full database repair (more invasive)
    logger.info("\nStep 2: Attempting full database repair...")
    logger.info("This will:")
    logger.info("  1. Create a backup of the current database")
    logger.info("  2. Dump all recoverable data")
    logger.info("  3. Rebuild the database from recovered data")
    logger.info("  4. Verify integrity of repaired database")

    try:
        if repair_database(DB_PATH, backup=True, logger_override=logger):
            logger.info("=" * 60)
            logger.info("✓ Database repair SUCCESSFUL!")
            logger.info("=" * 60)
            logger.info(f"Original database backed up to: {DB_PATH.with_suffix('.db.backup')}")
            logger.info("The application should now start normally.")
            return 0
        else:
            logger.error("=" * 60)
            logger.error("❌ Database repair FAILED")
            logger.error("=" * 60)
            logger.error("Manual intervention required.")
            logger.error(f"Backup available at: {DB_PATH.with_suffix('.db.backup')}")
            return 1
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ Database repair FAILED with exception: {e}")
        logger.error("=" * 60)
        logger.error("Manual intervention required.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
