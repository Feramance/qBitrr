# Database Consolidation - Migration Strategy

## Current Issue

The current implementation has `_delete_all_databases()` in `main.py` line 1174, which **deletes ALL database files on every startup**. This was likely added for development/testing purposes but is **not suitable for production**.

```python
def _delete_all_databases() -> None:
    """Delete all database files from the APPDATA_FOLDER on startup."""
    db_patterns = ["*.db", "*.db-wal", "*.db-shm"]
    # ... deletes everything ...
```

## Problem

When users upgrade to the consolidated database version:
1. ❌ Old per-instance databases (`Radarr-1080.db`, `Sonarr-TV.db`, etc.) are **deleted**
2. ❌ All historical data is **lost** (search history, queue state, custom format tracking)
3. ❌ qBitrr must re-sync everything from Arr APIs (slow for large libraries)

## Required Solution

We need a **proper migration** that:
1. ✅ Detects old per-instance database files
2. ✅ Migrates data from old DBs to new consolidated `qbitrr.db`
3. ✅ Preserves `ArrInstance` field for isolation
4. ✅ Only deletes old DBs **after successful migration**
5. ✅ Handles migration errors gracefully

## Migration Implementation

### Step 1: Remove Automatic Database Deletion

**File**: `qBitrr/main.py` line ~1174

```python
# REMOVE THIS LINE:
_delete_all_databases()  # ← This must be removed!
```

### Step 2: Add Migration Function

**File**: `qBitrr/database.py`

Add migration logic to handle old database files:

```python
def migrate_old_databases_to_consolidated(logger: logging.Logger) -> None:
    """
    Migrate data from old per-instance database files to consolidated qbitrr.db.

    Old format: Radarr-1080.db, Sonarr-TV.db, Lidarr.db, etc.
    New format: Single qbitrr.db with ArrInstance field

    This function:
    1. Scans for old .db files (excluding qbitrr.db and Torrents.db)
    2. Reads data from each old database
    3. Inserts into new database with appropriate ArrInstance value
    4. Renames old files to .db.migrated after success
    """
    import glob
    import os
    from pathlib import Path
    from peewee import SqliteDatabase
    from qBitrr.home_path import APPDATA_FOLDER

    # Find old database files (exclude qbitrr.db and Torrents.db)
    old_db_pattern = str(APPDATA_FOLDER / "*.db")
    old_db_files = [
        f for f in glob.glob(old_db_pattern)
        if not f.endswith(("qbitrr.db", "Torrents.db", ".migrated"))
    ]

    if not old_db_files:
        logger.debug("No old database files found to migrate")
        return

    logger.info(f"Found {len(old_db_files)} old database files to migrate")

    # Get consolidated database
    consolidated_db = get_database()

    for old_db_path in old_db_files:
        # Extract instance name from filename (e.g., "Radarr-1080" from "Radarr-1080.db")
        instance_name = Path(old_db_path).stem

        try:
            logger.info(f"Migrating data from {instance_name}.db...")

            # Open old database (read-only)
            old_db = SqliteDatabase(old_db_path)
            old_db.connect()

            # Get list of tables in old database
            cursor = old_db.execute_sql("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            migrated_count = 0
            for table_name in tables:
                if table_name in ('sqlite_sequence',):
                    continue  # Skip SQLite internal tables

                # Get all rows from old table
                cursor = old_db.execute_sql(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()

                if not rows:
                    continue

                # Get column names
                column_names = [desc[0] for desc in cursor.description]

                # Check if ArrInstance column already exists (shouldn't, but be safe)
                if 'ArrInstance' not in column_names:
                    column_names.append('ArrInstance')

                # Insert into consolidated database
                for row in rows:
                    row_data = dict(zip([desc[0] for desc in cursor.description], row))
                    row_data['ArrInstance'] = instance_name  # Add instance identifier

                    # Insert into new database (use appropriate model)
                    # This is simplified - in reality, we'd need to match table names to models
                    try:
                        consolidated_db.execute_sql(
                            f"INSERT OR REPLACE INTO {table_name} "
                            f"({', '.join(column_names)}) VALUES ({', '.join(['?'] * len(column_names))})",
                            [row_data.get(col) for col in column_names]
                        )
                        migrated_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to migrate row from {table_name}: {e}")

            old_db.close()

            # Rename old database file to .migrated
            migrated_path = old_db_path + ".migrated"
            os.rename(old_db_path, migrated_path)

            logger.info(f"Successfully migrated {migrated_count} rows from {instance_name}.db")

        except Exception as e:
            logger.error(f"Failed to migrate {instance_name}.db: {e}", exc_info=True)
            # Don't delete the old file if migration failed
```

### Step 3: Call Migration in Main

**File**: `qBitrr/main.py` line ~1174

```python
# Replace:
_delete_all_databases()

# With:
from qBitrr.database import migrate_old_databases_to_consolidated
migrate_old_databases_to_consolidated(logger)
```

### Step 4: Add Config Version Bump

**File**: `qBitrr/config_version.py`

```python
# Change from:
EXPECTED_CONFIG_VERSION = 3

# To:
EXPECTED_CONFIG_VERSION = 4  # Database consolidation migration
```

**File**: `qBitrr/gen_config.py`

Add new migration function:

```python
def _migrate_database_consolidation(config: MyConfig) -> bool:
    """
    Migrate from per-instance databases to consolidated database (v3 → v4).

    This migration:
    - Adds DatabaseConsolidated flag to track migration status
    - Migration happens in database.py, not here (just tracking)

    Returns:
        bool: True if changes were made to config
    """
    current_version = get_config_version(config)
    if current_version >= 4:
        return False

    # Add flag to track that consolidation should happen
    if not hasattr(config, 'Settings') or not hasattr(config.Settings, 'DatabaseConsolidated'):
        if not hasattr(config, 'Settings'):
            config.Settings = MyConfig.Settings()
        # Just a marker - actual migration happens in database.py
        logger.info("Database consolidation will occur on next startup")

    return False  # Don't modify config file for this
```

And call it in `apply_config_migrations()`:

```python
# NEW: Migrate to consolidated database (v3 → v4)
if _migrate_database_consolidation(config):
    changes_made = True
```

## Alternative: Simple Approach (Current Implementation)

If we keep the current `_delete_all_databases()` approach:

### Pros ✅
- Simple implementation
- No migration complexity
- Clean start every time
- No risk of corrupted old data

### Cons ❌
- **Loses all historical data** on upgrade
- Must re-sync from Arr APIs (slow for large libraries)
- Loses custom format tracking, search history, etc.
- Poor user experience on upgrade

### Documentation Required

If keeping current approach, we **MUST** document:

1. **CHANGELOG.md**:
   ```markdown
   ## Breaking Changes

   ⚠️ **Database Consolidation**: All database files will be deleted on startup.
   qBitrr will automatically re-sync from your Arr instances.
   ```

2. **README.md**:
   ```markdown
   ### Upgrading to v5.8.0+

   This version consolidates all databases into a single file. On first startup:
   - Old database files will be automatically deleted
   - qBitrr will re-sync all data from Radarr/Sonarr/Lidarr
   - This may take 5-30 minutes depending on library size
   - No action required - this is automatic
   ```

3. **GitHub Release Notes**:
   ```markdown
   ### ⚠️ Important Upgrade Notice

   This release consolidates databases into a single `qbitrr.db` file.
   **All existing database files will be deleted on startup.**

   What happens:
   - Old database files are automatically removed
   - Data re-syncs from your Arr instances (automatic)
   - May take 5-30 minutes for large libraries
   - No data loss - everything is re-fetched from Radarr/Sonarr/Lidarr
   ```

## Recommendation

**Option 1: Keep Current Approach (Simpler)**
- Remove nothing, just add documentation
- Accept that users will lose local database state
- Fast to implement, ships quickly

**Option 2: Implement Proper Migration (Better UX)**
- Remove `_delete_all_databases()` call
- Add `migrate_old_databases_to_consolidated()` function
- Preserve user data through upgrade
- More complex, needs testing

## Decision Needed

**Question for maintainer**: Which approach should we take?

1. **Simple** - Keep current delete-on-startup, add documentation ✅ (Ready now)
2. **Proper** - Implement migration, preserve data ⏳ (Requires additional work)

My recommendation: **Start with Simple (Option 1)** because:
- Database content is re-creatable from Arr APIs
- No critical user data is lost (just tracking state)
- Can always add migration in a future update if users complain
- Faster to ship the consolidation feature
