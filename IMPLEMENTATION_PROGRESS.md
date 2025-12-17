# Multi-qBittorrent v3.0 Implementation Progress

**Branch**: `feature/multi-qbit-v3`
**Started**: 2025-12-17
**Architecture**: Equal Multi-Instance Monitoring (Arr-Managed)

---

## Progress Overview

| Phase | Status | Progress | Time Spent | Notes |
|-------|--------|----------|------------|-------|
| Phase 1: Database Schema | ✅ Complete | 100% | 1.25h | TorrentLibrary model + query updates |
| Phase 2: qBitManager Multi-Instance | ✅ Complete | 100% | 3.0h | Multi-client infra, init, health, API routing |
| Phase 3: Arr Multi-Instance Scanning | ⏳ Pending | 0% | 0h | - |
| Phase 4: WebUI Backend | ⏳ Pending | 0% | 0h | - |
| Phase 5: Frontend | ⏳ Pending | 0% | 0h | - |
| Phase 6: Config Migration & Testing | ⏳ Pending | 0% | 0h | No DB migration needed |

**Overall Progress**: 33% (2/6 phases complete)

---

## Phase 1: Database Schema Updates (4-6 hours estimated)

### 1.1 Update TorrentLibrary Model ✅ DONE
- **Status**: ✅ Complete
- **File**: `qBitrr/tables.py`
- **Changes**:
  - [x] Add `QbitInstance` column to TorrentLibrary
  - [x] Add compound unique index on (Hash, QbitInstance) via Meta class
  - [x] No migration needed (databases recreated on restart)
- **Time**: 0.25h
- **Notes**: Model updated with QbitInstance field and compound unique constraint

### 1.2 Update Database Queries ✅ DONE
- **Status**: ✅ Complete
- **Files**: qBitrr/arss.py
- **Changes**:
  - [x] Added `instance_name` parameter to `in_tags()` method (default="default")
  - [x] Added `instance_name` parameter to `remove_tags()` method (default="default")
  - [x] Added `instance_name` parameter to `add_tags()` method (default="default")
  - [x] Updated all TorrentLibrary.select() queries to include QbitInstance condition
  - [x] Updated all TorrentLibrary.insert() calls to include QbitInstance field
  - [x] Updated all TorrentLibrary.update() calls to include QbitInstance condition
- **Time**: 1h
- **Notes**:
  - Database migration not needed - DBs recreated on restart/update
  - All TAGLESS mode queries now include instance context
  - Backward compatible with default="default" parameter
  - Affects ~60 database operations in arss.py



---

## Phase 2: qBitManager Multi-Instance Support (16-24 hours estimated)

### 2.1 Add Multi-Client Dictionary ✅ DONE
- **Status**: ✅ Complete
- **File**: `qBitrr/main.py`
- **Changes**:
  - [x] Add `self.clients: dict[str, qbittorrentapi.Client]`
  - [x] Add `self.qbit_versions: dict[str, VersionClass]`
  - [x] Add `self.instance_metadata: dict[str, dict]`
  - [x] Add `self.instance_health: dict[str, bool]`
  - [x] Keep backward compatibility with `self.client`
- **Time**: 0.5h
- **Commit**: `e833d55a`

### 2.2 Implement Instance Initialization ✅ DONE
- **Status**: ✅ Complete
- **Changes**:
  - [x] Create `_initialize_qbit_instances()` method
  - [x] Create `_init_instance()` method
  - [x] Parse config for [qBit-XXX] sections
  - [x] Initialize all clients
  - [x] Call during startup in `_complete_startup()`
- **Time**: 1.0h
- **Commit**: `e84e27ea`

### 2.3 Add Health Checking ✅ DONE
- **Status**: ✅ Complete
- **Changes**:
  - [x] Create `is_instance_alive(instance_name)` method
  - [x] Create `get_all_instances()` method
  - [x] Create `get_healthy_instances()` method
  - [x] Create `get_instance_info()` method
  - [x] Update existing `is_alive` property for backward compat
- **Time**: 1.0h
- **Commit**: `435cfe54`

### 2.4 Update qBit API Call Routing ✅ DONE
- **Status**: ✅ Complete
- **Changes**:
  - [x] Add `get_client()` helper method for instance routing
  - [x] Update `app_version()` with instance_name parameter
  - [x] Update `transfer_info()` with instance_name parameter
  - [x] Route all calls through `get_client()`
  - [x] Maintain backward compatibility with default="default"
- **Time**: 0.5h
- **Commit**: `6ea52bb4`
- **Notes**: Main.py has minimal direct client usage; most routing will be in Arr classes

---

## Phase 3: Arr Class Updates (24-32 hours estimated)

### 3.1 Category Creation on All Instances
- **Status**: ⏳ Pending
- **File**: `qBitrr/arss.py`
- **Changes**:
  - [ ] Create `_ensure_category_on_all_instances()` method
  - [ ] Call from Arr.__init__()
  - [ ] Handle failures gracefully

### 3.2 Multi-Instance Torrent Scanning
- **Status**: ⏳ Pending
- **Changes**:
  - [ ] Create `process_torrents_multi_instance()` method
  - [ ] Iterate over all instances
  - [ ] Get torrents by category from each instance
  - [ ] Process with instance context

### 3.3 Update Torrent Operations
- **Status**: ⏳ Pending
- **Changes**:
  - [ ] Update `_process_single_torrent()` signature
  - [ ] Update `_update_torrent_db()` with instance
  - [ ] Update `_remove_torrent()` with instance
  - [ ] Update all health check operations

---

## Phase 4: WebUI Backend Updates (10-14 hours estimated)

### 4.1 Update Status Endpoint
- **Status**: ⏳ Pending
- **File**: `qBitrr/webui.py`
- **Changes**:
  - [ ] Return `qbitInstances` dict in status payload
  - [ ] Keep `qbit` for backward compatibility
  - [ ] Add instance metadata to Arr objects

### 4.2 Add Distribution Endpoint
- **Status**: ⏳ Pending
- **Changes**:
  - [ ] Create `/api/torrents/distribution` endpoint
  - [ ] Return torrent counts per instance
  - [ ] Group by category

---

## Phase 5: Frontend Updates (12-18 hours estimated)

### 5.1 Update TypeScript Types
- **Status**: ⏳ Pending
- **File**: `webui/src/api/types.ts`
- **Changes**:
  - [ ] Add `QbitInstance` interface
  - [ ] Update `QbitStatusResponse` interface
  - [ ] Add `TorrentDistribution` interface

### 5.2 Create QbitInstancesView
- **Status**: ⏳ Pending
- **File**: `webui/src/pages/QbitInstancesView.tsx`
- **Changes**:
  - [ ] Create new component
  - [ ] Display all instances
  - [ ] Show torrent distribution
  - [ ] Add to navigation

---

## Phase 6: Config Migration & Testing (6-8 hours estimated)

### 6.1 Config Migration (Database Migration NOT Needed)
- **Status**: ⏳ Pending
- **File**: `qBitrr/config.py`, `qBitrr/config_version.py`
- **Changes**:
  - [ ] Create `_migrate_config_v3_to_v4()` function (optional)
  - [ ] Bump CURRENT_CONFIG_VERSION to 4 in config_version.py
  - [ ] Add informational message about multi-qBit support
- **Notes**:
  - ✅ No database migration code needed (DBs recreated on restart/update)
  - Config migration only needed if ConfigVersion bump is required
  - Existing single-instance configs work without changes

### 6.2 Testing
- **Status**: ⏳ Pending
- **Tests**:
  - [ ] Single instance (backward compat)
  - [ ] Two instances
  - [ ] Three+ instances
  - [ ] Instance failure handling
  - [ ] Migration from v3 to v4
  - [ ] WebUI displays correctly

---

## Commits Made

1. `c8e5fa51` - Phase 1.1: Add QbitInstance field to TorrentLibrary model
2. `7b96dc7b` - Update implementation plan: clarify no database migration needed
3. `10c862b1` - Phase 1.2: Update all database queries with instance context
4. `e833d55a` - Phase 2.1: Add multi-client dictionaries to qBitManager
5. `e84e27ea` - Phase 2.2: Implement instance initialization methods
6. `435cfe54` - Phase 2.3: Add instance health checking methods
7. `8157a82f` - docs: Update progress tracker with Phase 2.1-2.3 completion
8. `6ea52bb4` - Phase 2.4: Add instance routing for qBit API calls in main.py

---

## Issues Encountered

_None yet_

---

## Next Steps

1. ✅ Create feature branch
2. ✅ Create progress tracking file
3. ✅ Update TorrentLibrary model in tables.py
4. 🚧 Update all database queries with instance context (Phase 1.2)
5. Implement qBitManager multi-instance support (Phase 2)

**Note**: Database migration is NOT needed - DBs are recreated on restart/update

---

## Legend

- ✅ Complete
- 🚧 In Progress
- ⏳ Pending
- ❌ Blocked
- ⚠️ Issue/Warning

---

## Current Status Summary

- ✅ **Phase 1 Complete** (1.25h): Database schema fully updated for multi-instance support
  - ✅ Phase 1.1: TorrentLibrary model with QbitInstance field and compound unique index
  - ✅ Phase 1.2: All database queries updated with instance context (~60 operations)
    - Updated `in_tags()`, `add_tags()`, `remove_tags()` methods with instance_name parameter
    - All TAGLESS mode queries now include QbitInstance condition
    - 100% backward compatible (default="default")

- ✅ **Phase 2 Complete** (3.0h): Multi-instance infrastructure in qBitManager
  - ✅ Phase 2.1: Multi-client dictionaries (clients, versions, metadata, health)
  - ✅ Phase 2.2: Instance initialization (_initialize_qbit_instances, _init_instance)
  - ✅ Phase 2.3: Health checking (is_instance_alive, get_all_instances, get_instance_info)
  - ✅ Phase 2.4: API call routing (get_client, app_version, transfer_info with instance_name)

**Next**: Phase 3 - Arr class multi-instance torrent scanning

**Database Migration**: ✅ NOT NEEDED - Databases are recreated on restart/update per user constraint

**Last Updated**: 2025-12-17 (Phase 2 complete, starting Phase 3)
