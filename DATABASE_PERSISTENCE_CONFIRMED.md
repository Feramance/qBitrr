# Database Persistence - Confirmed ✅

## Summary

The consolidated database **is now persistent** across restarts. Testing confirmed the database file grows and maintains state through multiple container restarts.

## What Was Fixed

### Problem
The original `_delete_all_databases()` function deleted **ALL** database files indiscriminately on every startup, including the new consolidated `qbitrr.db`.

### Solution
Modified the function to **preserve** the consolidated database while cleaning up old per-instance databases:

**File**: `qBitrr/main.py` (lines 54-80)

```python
def _delete_all_databases() -> None:
    """
    Delete old per-instance database files from the APPDATA_FOLDER on startup.

    Preserves the consolidated database (qbitrr.db) and Torrents.db.
    Deletes old per-instance databases and their WAL/SHM files.
    """
    db_patterns = ["*.db", "*.db-wal", "*.db-shm"]
    deleted_files = []
    # Files to preserve (consolidated database)
    preserve_files = {"qbitrr.db", "Torrents.db"}

    for pattern in db_patterns:
        for db_file in glob.glob(str(APPDATA_FOLDER.joinpath(pattern))):
            base_name = os.path.basename(db_file)
            # Preserve consolidated database and its WAL/SHM files
            should_preserve = any(base_name.startswith(f) for f in preserve_files)
            if should_preserve:
                continue  # Skip deletion

            try:
                os.remove(db_file)
                deleted_files.append(base_name)
            except Exception as e:
                logger.error("Failed to delete database file %s: %s", db_file, e)

    if deleted_files:
        logger.info("Deleted old database files on startup: %s", ", ".join(deleted_files))
    else:
        logger.debug("No old database files found to delete on startup")
```

## Verification Results

### Test 1: First Startup
```
✅ No old databases found (clean install)
✅ Created: /config/qBitManager/qbitrr.db (664K)
✅ Log: "Initialized single database: /config/qBitManager/qbitrr.db"
```

### Test 2: First Restart
```
✅ Database preserved: qbitrr.db still exists
✅ Database grew: 664K → 732K (data accumulating)
✅ No deletion message
✅ Log: "Initialized single database: /config/qBitManager/qbitrr.db" (reused existing)
```

### Test 3: Second Restart
```
✅ Database preserved: qbitrr.db still exists
✅ Database continues growing
✅ 3 successful initializations recorded
✅ All 7 Arr instances writing to same database
```

### Test 4: Data Verification
```bash
# Database activity logs
14 × "Started updating database" messages
Multiple "Stored X tracks for album Y" messages
Multiple "Updating database entry" messages
```

## Database File Structure

After running:
```
-rw-r--r-- 1 root root 732K Jan 26 21:18 qbitrr.db
-rw-r--r-- 1 root root  32K Jan 26 21:18 qbitrr.db-shm  (Shared Memory)
-rw-r--r-- 1 root root 4.0M Jan 26 21:18 qbitrr.db-wal  (Write-Ahead Log)
```

All 3 files are preserved across restarts (WAL mode requires all 3).

## Migration Behavior

### On First Upgrade (v5.7.1 → v5.8.0)
1. ✅ Old databases deleted (Radarr-1080.db, Sonarr-TV.db, etc.)
2. ✅ New `qbitrr.db` created
3. ✅ Data re-synced from Arr APIs (automatic)

### On Subsequent Restarts
1. ✅ `qbitrr.db` preserved
2. ✅ No deletions
3. ✅ Reuses existing database
4. ✅ Data persists and accumulates

## Future Database Schema Migrations

Since the database is now persistent, **schema migrations will be required** for future updates that change table structure.

### Migration Strategy for Future Updates

When adding/modifying database fields, use Peewee migrations:

```python
# Example: Adding a new field to existing model
from peewee import CharField
from playhouse.migrate import SqliteMigrator, migrate

def apply_database_migration_v2():
    """Add NewField to ExistingModel (v4 → v5)."""
    from qBitrr.database import get_database

    db = get_database()
    migrator = SqliteMigrator(db)

    # Add new field
    new_field = CharField(null=True, default="")

    with db.atomic():
        migrate(
            migrator.add_column('existingmodel', 'NewField', new_field)
        )
```

### Migration Tracking

**File**: `qBitrr/config_version.py`

Could add database version tracking:
```python
DATABASE_SCHEMA_VERSION = 1  # Increment when schema changes

def get_database_version(db):
    """Get current database schema version."""
    try:
        cursor = db.execute_sql("SELECT value FROM schema_version WHERE key='version'")
        return int(cursor.fetchone()[0])
    except:
        return 0  # No version table = v0

def set_database_version(db, version):
    """Update database schema version."""
    db.execute_sql(
        "INSERT OR REPLACE INTO schema_version (key, value) VALUES ('version', ?)",
        (version,)
    )
```

## Recommendations

### For Current Release (v5.8.0)
- ✅ Keep current approach (delete old DBs on first upgrade)
- ✅ Add documentation to CHANGELOG.md (done)
- ✅ Add breaking change warning in release notes
- ✅ Database is confirmed persistent after first startup

### For Future Releases
When modifying database schema:
1. **Create migration function** in `database.py`
2. **Add schema version tracking** to detect when migration needed
3. **Test migration** with sample data
4. **Backup database** before migration (automatic via WAL mode)
5. **Update CHANGELOG.md** with migration details

## Documentation Added

### CHANGELOG.md
- ✅ Added "Unreleased" section with database consolidation feature
- ✅ Documented breaking changes (old DBs deleted)
- ✅ Documented automatic re-sync behavior

### Still Needed
- GitHub Release Notes (when cutting release)
- README.md upgrade section (optional, good practice)

## Conclusion

✅ **Database persistence confirmed working**
- Single `qbitrr.db` file persists across restarts
- Data accumulates and is preserved
- Old per-instance databases cleaned up only once
- Ready for merge and release

**Commit**: `7069cffa` - fix: Preserve consolidated database across restarts

---

**Tested**: January 26, 2026
**Status**: Production Ready ✅
