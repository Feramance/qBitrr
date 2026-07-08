#!/usr/bin/env python3
"""Online backup of qBitrr SQLite catalog using the SQLite backup API.

Safe to run while qBitrr is running (uses a read-only connection and the
built-in backup API). For cron, prefer this over copying qbitrr.db directly.

Example cron (daily at 03:00 UTC, Docker bind mount at ./.config):

    0 3 * * * docker compose -f /path/to/qBitrr/docker-compose.yml exec -T qbitrr \\
        python /app/scripts/backup_database.py --dest /config/qBitManager/backups/qbitrr.db.$(date -u +\\%Y\\%m\\%d)
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("DBBackup")


def _default_source_path() -> Path:
    """Resolve the catalog database path for native or Docker layouts."""
    for candidate in (
        Path("/config/qBitManager/qbitrr.db"),
        Path(".config/qBitManager/qbitrr.db"),
    ):
        if candidate.is_file():
            return candidate
    try:
        from qBitrr.home_path import APPDATA_FOLDER

        return Path(APPDATA_FOLDER) / "qbitrr.db"
    except ImportError:
        return Path(".config/qBitManager/qbitrr.db")


def backup_database(source: Path, dest: Path) -> bool:
    """Copy *source* to *dest* via sqlite3.Connection.backup and verify with quick_check."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=60.0)
    try:
        dest_conn = sqlite3.connect(str(dest))
        try:
            with dest_conn:
                src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()

    verify = sqlite3.connect(str(dest), timeout=30.0)
    try:
        result = verify.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        verify.close()

    if result != "ok":
        logger.error("Backup failed integrity quick_check: %s", result)
        return False
    logger.info("Backup integrity quick_check: ok")
    return True


def main() -> int:
    """Run backup from CLI."""
    parser = argparse.ArgumentParser(description="Backup qBitrr SQLite catalog database")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Source qbitrr.db path (default: auto-detect)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Destination .db path (default: qbitrr.db.YYYYMMDD alongside source)",
    )
    args = parser.parse_args()

    source = args.source or _default_source_path()
    if not source.is_file():
        logger.error("Database not found: %s", source)
        return 1

    if args.dest is not None:
        dest = args.dest
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        dest = source.parent / "backups" / f"qbitrr.db.{stamp}"

    logger.info("Backing up %s -> %s", source, dest)
    if not backup_database(source, dest):
        return 1

    logger.info("Backup complete (%s bytes): %s", dest.stat().st_size, dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
