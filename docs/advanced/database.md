# Database Schema

Complete reference for qBitrr's SQLite database structure and operations.

## Overview

qBitrr uses **SQLite** with **Peewee ORM** for persistent state management.

**Database Location:**
- Native install: `~/config/qBitManager/qbitrr.db`
- Docker: `/config/qBitManager/qbitrr.db`

!!! success "Single Consolidated Database (v5.8.0+)"
    As of version 5.8.0, qBitrr uses a **single consolidated database** file for all Arr instances, replacing the previous per-instance database approach. This simplifies backups, reduces file overhead, and improves performance.

**Why SQLite?**
- Zero configuration required
- Single-file storage (easy backups)
- ACID compliant
- Sufficient for qBitrr's write patterns
- Cross-platform compatibility
- WAL mode for concurrent access

## Database Architecture

### Consolidated Database (v5.8.0+)

All Arr instances now share a single database file with **ArrInstance field** for data isolation:

```
qbitrr.db
├── MoviesFilesModel      (ArrInstance: "Radarr-4K", "Radarr-1080", etc.)
├── EpisodeFilesModel     (ArrInstance: "Sonarr-TV", "Sonarr-4K", etc.)
├── AlbumFilesModel       (ArrInstance: "Lidarr", etc.)
├── SeriesFilesModel      (ArrInstance: "Sonarr-TV", etc.)
├── ArtistFilesModel      (ArrInstance: "Lidarr", etc.)
├── TrackFilesModel       (ArrInstance: "Lidarr", etc.)
├── MovieQueueModel       (ArrInstance: per-Radarr instance)
├── EpisodeQueueModel     (ArrInstance: per-Sonarr instance)
├── AlbumQueueModel       (ArrInstance: per-Lidarr instance)
├── FilesQueued           (ArrInstance: cross-instance)
├── TorrentLibrary        (ArrInstance: "TAGLESS" when enabled)
└── SearchActivity        (WebUI activity tracking)
```

**Benefits:**
- Single file to backup instead of 9+ separate databases
- Simplified database management and maintenance
- Better performance with shared connection pool
- Reduced disk I/O overhead

### Schema Definition

All models include an **ArrInstance field** to isolate data by Arr instance:

```sql
ArrInstance = CharField(null=True, default="")
```

qBitrr maintains tables defined in `qBitrr/tables.py`:

#### downloads

Tracks all torrents managed by qBitrr.

```sql
CREATE TABLE downloads (
    hash TEXT PRIMARY KEY,           -- qBittorrent torrent hash
    name TEXT NOT NULL,              -- Torrent name
    arr_type TEXT NOT NULL,          -- "radarr", "sonarr", or "lidarr"
    arr_name TEXT NOT NULL,          -- Arr instance name from config
    media_id INTEGER NOT NULL,       -- Movie/Series/Album ID in Arr
    state TEXT NOT NULL,             -- Current state (see below)
    added_at DATETIME NOT NULL,      -- When added to qBittorrent
    updated_at DATETIME NOT NULL,    -- Last state update
    completed_at DATETIME,           -- When torrent completed
    imported_at DATETIME,            -- When imported to Arr
    ratio REAL,                      -- Current seed ratio
    seed_time INTEGER,               -- Seconds seeded
    tracker TEXT,                    -- Primary tracker domain
    category TEXT,                   -- qBittorrent category
    save_path TEXT,                  -- Download location
    content_path TEXT,               -- Path to downloaded files
    size INTEGER,                    -- Total size in bytes
    downloaded INTEGER,              -- Bytes downloaded
    uploaded INTEGER,                -- Bytes uploaded
    eta INTEGER,                     -- Estimated time remaining (seconds)
    progress REAL,                   -- Download progress (0.0-1.0)
    error_message TEXT,              -- Last error encountered
    retry_count INTEGER DEFAULT 0,   -- Number of retry attempts
    blacklisted BOOLEAN DEFAULT 0,   -- Whether torrent is blacklisted
    deleted BOOLEAN DEFAULT 0        -- Soft delete flag
);
```

**State Values:**

| State | Description |
|-------|-------------|
| `downloading` | Actively downloading |
| `stalled` | Download stalled (no progress) |
| `completed` | Download finished, not yet imported |
| `importing` | Import to Arr in progress |
| `imported` | Successfully imported to Arr |
| `seeding` | Actively seeding after import |
| `failed` | Download or import failed |
| `blacklisted` | Added to Arr blacklist |
| `deleted` | Removed from qBittorrent |

**Indexes:**

```sql
CREATE INDEX idx_downloads_arr ON downloads(arr_type, arr_name);
CREATE INDEX idx_downloads_state ON downloads(state);
CREATE INDEX idx_downloads_media_id ON downloads(media_id);
CREATE INDEX idx_downloads_updated ON downloads(updated_at);
```

#### searches

Records search activity history for auditing and rate limiting.

```sql
CREATE TABLE searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arr_type TEXT NOT NULL,
    arr_name TEXT NOT NULL,
    media_id INTEGER NOT NULL,
    media_title TEXT,                -- Movie/Series/Album title
    query TEXT NOT NULL,             -- Search query sent to Arr
    searched_at DATETIME NOT NULL,   -- When search was triggered
    result_count INTEGER DEFAULT 0,  -- Number of results returned
    best_result_hash TEXT,           -- Hash of best result (if grabbed)
    success BOOLEAN DEFAULT 0,       -- Whether search found results
    error_message TEXT               -- Error if search failed
);
```

**Indexes:**

```sql
CREATE INDEX idx_searches_arr ON searches(arr_type, arr_name);
CREATE INDEX idx_searches_media ON searches(media_id);
CREATE INDEX idx_searches_date ON searches(searched_at);
```

**Use Cases:**
- Prevent duplicate searches within cooldown period
- Track search success rate
- Audit trail for troubleshooting
- Rate limit Arr API calls

#### expiry

Manages automatic cleanup of old database entries.

```sql
CREATE TABLE expiry (
    entry_id TEXT PRIMARY KEY,       -- Foreign key to downloads.hash
    entry_type TEXT NOT NULL,        -- "download" or "search"
    expires_at DATETIME NOT NULL,    -- When to delete entry
    created_at DATETIME NOT NULL     -- When expiry was set
);
```

**Indexes:**

```sql
CREATE INDEX idx_expiry_time ON expiry(expires_at);
CREATE INDEX idx_expiry_type ON expiry(entry_type);
```

**Cleanup Schedule:**

```toml
[Settings]
RetentionDays = 30  # Keep entries for 30 days
```

Cleanup runs automatically during each event loop iteration.

## Peewee ORM Models

**File:** `qBitrr/tables.py`

### DownloadsModel

```python
from peewee import *
from datetime import datetime

class DownloadsModel(Model):
    hash = CharField(primary_key=True)
    name = CharField()
    arr_type = CharField()
    arr_name = CharField()
    media_id = IntegerField()
    state = CharField()
    added_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    # ... additional fields

    class Meta:
        database = database_proxy
        table_name = 'downloads'
```

**Common Queries:**

```python
# Get all downloading torrents for Radarr instance
torrents = (DownloadsModel
    .select()
    .where(
        (DownloadsModel.arr_name == 'Radarr-4K') &
        (DownloadsModel.state == 'downloading')
    ))

# Update torrent state
download = DownloadsModel.get(DownloadsModel.hash == torrent_hash)
download.state = 'completed'
download.completed_at = datetime.now()
download.save()

# Bulk delete old entries
deleted = (DownloadsModel
    .delete()
    .where(DownloadsModel.updated_at < cutoff_date)
    .execute())
```

### SearchModel

```python
class SearchModel(Model):
    arr_type = CharField()
    arr_name = CharField()
    media_id = IntegerField()
    query = CharField()
    searched_at = DateTimeField(default=datetime.now)
    result_count = IntegerField(default=0)

    class Meta:
        database = database_proxy
        table_name = 'searches'
```

**Common Queries:**

```python
# Check if searched recently (prevent duplicate searches)
recent = (SearchModel
    .select()
    .where(
        (SearchModel.media_id == movie_id) &
        (SearchModel.searched_at > datetime.now() - timedelta(hours=1))
    )
    .exists())

# Get search success rate for instance
total = SearchModel.select().where(SearchModel.arr_name == 'Radarr-4K').count()
successful = SearchModel.select().where(
    (SearchModel.arr_name == 'Radarr-4K') &
    (SearchModel.success == True)
).count()
success_rate = (successful / total * 100) if total > 0 else 0
```

### EntryExpiry

```python
class EntryExpiry(Model):
    entry_id = CharField(primary_key=True)
    entry_type = CharField()
    expires_at = DateTimeField()
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        database = database_proxy
        table_name = 'expiry'
```

## Database Operations

### Initialization

**File:** `qBitrr/database.py`

Database is initialized on first run using the centralized `get_database()` function:

```python
from qBitrr.database import get_database

def main():
    db = get_database()  # Returns singleton instance
    # Database is at: ~/config/qBitManager/qbitrr.db
    # Tables are created automatically if they don't exist
```

The `get_database()` function:

1. Creates database at `APPDATA_FOLDER/qbitrr.db`
2. Configures WAL mode and performance pragmas
3. Binds all model classes to the database
4. Creates all tables with `safe=True` (no error if exists)
5. Returns the shared database instance

**All Arr instances share this single database**, with isolation provided by the `ArrInstance` field in each model.

### Concurrency Control

**File:** `qBitrr/db_lock.py`

All database writes use a global lock:

```python
from qBitrr.db_lock import locked_database

# Safe concurrent access
with locked_database():
    DownloadsModel.create(
        hash=torrent_hash,
        name=torrent_name,
        state='downloading'
    )
```

**Why locking is needed:**
- Multiple Arr manager processes write concurrently
- SQLite has limited concurrent write support
- Lock prevents "database is locked" errors
- Uses `threading.RLock()` for reentrant locking

### Transactions

Peewee automatically wraps operations in transactions:

```python
# Atomic transaction
with database.atomic():
    download = DownloadsModel.get(hash=torrent_hash)
    download.state = 'imported'
    download.save()

    # If this fails, download.save() is rolled back
    SearchModel.create(media_id=download.media_id, ...)
```

### Migrations

#### Consolidated Database Migration (v5.7.x → v5.8.0)

**File:** `qBitrr/main.py:_delete_all_databases()`

When upgrading to v5.8.0+, qBitrr performs a **clean slate migration**:

1. **Deletes old per-instance databases** (Radarr-*.db, Sonarr-*.db, etc.)
2. **Creates new consolidated database** (`qbitrr.db`)
3. **Preserves the consolidated database** across future restarts
4. **Re-syncs data** from Arr APIs automatically

```python
def _delete_all_databases() -> None:
    """Delete old per-instance databases, preserve consolidated database."""
    preserve_files = {"qbitrr.db", "Torrents.db"}

    for db_file in glob.glob(str(APPDATA_FOLDER / "*.db*")):
        if any(base in db_file for base in preserve_files):
            continue  # Preserve consolidated database

        os.remove(db_file)  # Delete old per-instance databases
```

This approach ensures:
- ✅ Clean database schema (no migration conflicts)
- ✅ Automatic data recovery from Arr APIs
- ✅ No complex migration logic required

#### Future Schema Changes

When adding/modifying fields in future versions:

```python
# Example: Adding a new field to existing model
from playhouse.migrate import SqliteMigrator, migrate

def apply_database_migration_v9():
    """Add NewField to ExistingModel (v8 → v9)."""
    from qBitrr.database import get_database

    db = get_database()
    migrator = SqliteMigrator(db)

    # Add new field with default value
    new_field = CharField(null=True, default="")

    with db.atomic():
        migrate(
            migrator.add_column('moviesfilesmodel', 'NewField', new_field)
        )
```

**Best Practices:**
- Always provide `null=True` and `default` values for new columns
- Test migrations on backup database first
- Increment config version in `config_version.py`
- Document migration in CHANGELOG.md
- Consider adding migration to `apply_config_migrations()`

## Maintenance

### Backup

**Recommended Backup Strategy:**

```bash
# Manual backup
cp ~/config/qBitrr.db ~/config/qBitrr.db.backup

# Automated backup (cron)
0 2 * * * cp ~/config/qBitrr.db ~/config/qBitrr.db.$(date +\%Y\%m\%d)

# Docker backup
docker exec qbitrr sqlite3 /config/qBitrr.db ".backup /config/qBitrr.db.backup"
```

**What to backup:**
- `qBitrr.db` - Primary database
- `config.toml` - Configuration file
- `logs/` - Optional, for troubleshooting

### VACUUM

**Optimize database size:**

```bash
# Manual vacuum
sqlite3 ~/config/qBitrr.db "VACUUM;"

# Or use qBitrr CLI
qbitrr --vacuum-db
```

**When to vacuum:**
- After deleting large number of entries
- Database file larger than expected
- Performance degradation

**Automatic vacuum:**

```toml
[Settings]
AutoVacuum = true  # VACUUM during startup if DB > threshold
```

### Integrity Check

**Validate database integrity:**

```bash
# Check for corruption
sqlite3 ~/config/qBitrr.db "PRAGMA integrity_check;"

# Expected output: ok
```

**Auto-recovery:**

qBitrr includes automatic recovery in `qBitrr/db_recovery.py`:

```python
def recover_database(db_path):
    # Attempt to dump and recreate database
    try:
        subprocess.run(['sqlite3', db_path, '.dump'],
                      stdout=temp_file, check=True)
        os.rename(db_path, f"{db_path}.corrupt")
        subprocess.run(['sqlite3', db_path],
                      stdin=temp_file, check=True)
        logger.info("Database recovered successfully")
    except Exception as e:
        logger.error(f"Recovery failed: {e}")
```

### Reset Operations

**Clear all data:**

```bash
# Reset all torrent tracking (keeps searches)
qbitrr --reset-torrents

# Reset all search history (keeps torrents)
qbitrr --reset-searches

# Reset everything (destructive!)
rm ~/config/qBitrr.db
qbitrr  # Will recreate on next start
```

## Performance Optimization

### Indexing Strategy

Indexes are automatically created for:
- Primary keys (hash, id)
- Foreign keys (entry_id)
- Frequently queried columns (state, arr_name, updated_at)

**Impact:**
- SELECT queries: 10-100x faster with indexes
- INSERT/UPDATE: Minimal overhead (< 5%)
- Disk space: Indexes add ~20% to DB size

### Query Optimization

**Slow query example:**

```python
# BAD: N+1 query problem
for download in DownloadsModel.select():
    expiry = EntryExpiry.get(entry_id=download.hash)  # Extra query!
```

**Optimized:**

```python
# GOOD: Single query with JOIN
downloads = (DownloadsModel
    .select(DownloadsModel, EntryExpiry)
    .join(EntryExpiry, JOIN.LEFT_OUTER,
          on=(DownloadsModel.hash == EntryExpiry.entry_id))
    .execute())
```

### Batch Operations

**Bulk insert:**

```python
# BAD: One insert per torrent
for torrent in torrents:
    DownloadsModel.create(**torrent)  # N queries

# GOOD: Batch insert
with database.atomic():
    DownloadsModel.insert_many(torrents).execute()  # 1 query
```

## Troubleshooting

### "Database is locked"

**Cause:** Concurrent write from multiple processes without lock

**Solution:**

```python
# Always use locked_database() context manager
with locked_database():
    DownloadsModel.create(...)
```

### Corruption Detection

**Symptoms:**
- "database disk image is malformed" error
- Queries returning wrong data
- Random crashes

**Recovery:**

```bash
# Try auto-recovery
qbitrr --repair-db

# Manual recovery
sqlite3 ~/config/qBitrr.db ".dump" > dump.sql
mv ~/config/qBitrr.db ~/config/qBitrr.db.corrupt
sqlite3 ~/config/qBitrr.db < dump.sql
```

### High Disk Usage

**Cause:** Large number of old entries not cleaned up

**Solution:**

```toml
[Settings]
RetentionDays = 7  # Reduce from default 30
AutoVacuum = true
```

```bash
# Immediate cleanup
qbitrr --vacuum-db
```

## Security Considerations

### File Permissions

**Recommended:**

```bash
# Restrict access to database
chmod 600 ~/config/qBitrr.db
chown qbitrr:qbitrr ~/config/qBitrr.db

# Docker automatically sets via PUID/PGID
```

### Sensitive Data

**What's stored:**
- Torrent hashes (public data)
- Media IDs (internal Arr IDs)
- File paths (may contain personal info)

**What's NOT stored:**
- API keys (only in config.toml)
- Passwords
- User credentials

**Data Retention:**

```toml
[Settings]
RetentionDays = 7  # Minimize data retention for privacy
```

## Future Enhancements

**Planned for v6.0:**

- **PostgreSQL Support** - Better concurrent write performance
- **Time-series Tables** - Optimized for metrics/stats
- **Full-text Search** - Search logs and torrents
- **Schema Versioning** - Alembic-style migrations
- **Sharding** - Split data by Arr instance for scale

## Related Documentation

- [Architecture](architecture.md) - System design overview
- [Performance Tuning](performance.md) - Optimization strategies
- [Troubleshooting: Database Issues](../troubleshooting/database.md) - Common problems
