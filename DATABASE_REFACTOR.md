# Database Refactoring Summary

## Overview
This document summarizes the complete database refactoring that replaced the complex consolidated/legacy dual-mode system with a clean, simple architecture.

## What Was Changed

### 1. New Database Module (`qBitrr/database.py`)
Created a clean, centralized database initialization module that:
- Uses a single `qbitrr.db` SQLite database file
- Provides per-Arr-instance isolation via the `ArrInstance` field
- Eliminates all consolidated mode complexity
- Provides simple initialization functions:
  - `init_global_database()`: Initializes the single qbitrr.db database
  - `init_arr_database()`: Sets up models for a specific Arr instance
  - `init_torrent_database()`: Sets up the shared torrent tracking database
  - `get_database_path()`: Returns path to the single database file

### 2. Simplified Table Models (`qBitrr/tables.py`)
Completely rewritten to:
- Remove all `ScopedModel` complexity and monkey-patching
- Use simple Peewee `Model` base class
- Include `ArrInstance` field in all models for per-instance isolation
- Define clean model classes:
  - `FilesQueued`: Queue persistence
  - `MoviesFilesModel`, `EpisodeFilesModel`, `AlbumFilesModel`: File tracking
  - `MovieQueueModel`, `EpisodeQueueModel`, `AlbumQueueModel`: Queue management
  - `SeriesFilesModel`, `ArtistFilesModel`, `TrackFilesModel`: Additional metadata
  - `TorrentLibrary`: Torrent tracking (shared across all instances)
  - `SchemaVersion`: Database schema version tracking

### 3. Cleaned Up ArrManager (`qBitrr/arss.py`)
Rewrote `register_search_mode()` method from 330 lines to 61 lines:
- **Before**: Complex branching logic with consolidated/legacy modes, monkey-patching, ScopedModel injection
- **After**: Simple, clean initialization using the new database module
- Removed all `db_compat` imports and usage
- Removed all `is_consolidated_mode()` checks
- Removed all monkey-patching of model methods
- Database initialization now just calls `init_arr_database()` or `init_torrent_database()`

### 4. Removed Files
These files are now obsolete and can be removed:
- `qBitrr/db_compat.py` - Consolidated/legacy compatibility layer
- `qBitrr/db_pool.py` - Complex database pooling (replaced by simple Peewee connections)
- Any migration scripts specific to consolidated mode

## Architecture Benefits

### Single Database File
- **Before**: Multiple .db files per Arr instance (Search.db, Torrents.db) OR a single consolidated.db
- **After**: One `qbitrr.db` file containing all data with `ArrInstance` field for isolation

### No More Mode Switching
- **Before**: Runtime checks for `is_consolidated_mode()` throughout codebase
- **After**: Single code path, no mode checks needed

### Clean Model Inheritance
- **Before**: Complex monkey-patching of methods onto model classes at runtime
- **After**: Simple Peewee models with standard inheritance

### Simplified Queries
- **Before**: Automatic ArrInstance filtering via monkey-patched methods
- **After**: Explicit filtering on ArrInstance field (clearer, more maintainable)

### Better Performance
- Single database connection pool instead of multiple connections
- WAL mode enabled for better concurrency
- Optimized pragmas for read-heavy workloads

## Migration Path

### For Users
No action required. On first run with the new version:
1. qBitrr will create the new `qbitrr.db` database
2. Existing Search.db and Torrents.db files remain untouched (for rollback)
3. Data will be re-populated from Arr instances during normal operation

### For Developers
When writing queries, use explicit filtering:
```python
# Old way (automatic via ScopedModel):
Movies.select().where(...)

# New way (explicit filtering):
Movies.select().where(
    (Movies.ArrInstance == arr_name) & (...)
)
```

Or use the helper functions in `database.py`:
```python
from qBitrr.database import set_current_arr

set_current_arr("Radarr")
# Queries within this context will use "Radarr" as the instance
```

## Testing Checklist

- [ ] Fresh install with no existing databases
- [ ] Upgrade from legacy mode (separate .db files)
- [ ] Upgrade from consolidated mode (single consolidated.db)
- [ ] Multiple Arr instances (Radarr + Sonarr + Lidarr)
- [ ] Torrent tracking across all instances
- [ ] Search functionality (missing, upgrades, requests)
- [ ] Database locking under concurrent access
- [ ] WebUI database queries

## Rollback Plan

If issues arise, rollback is simple:
1. Revert to previous version
2. Old .db files are still present and will be used
3. Data in `qbitrr.db` can be exported if needed

## Future Improvements

With the clean architecture in place, these enhancements become easier:
1. **Database migrations**: Clean schema versioning with `SchemaVersion` table
2. **Query optimization**: Easier to add indexes and optimize queries
3. **Alternative backends**: Could support PostgreSQL or MySQL in future
4. **Backup/restore**: Single file makes backups trivial
5. **WebUI enhancements**: Easier to query across all Arr instances
