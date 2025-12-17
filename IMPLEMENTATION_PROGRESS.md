# Multi-qBittorrent v3.0 Implementation Progress

**Branch**: `feature/multi-qbit-v3`
**Started**: 2025-12-17
**Architecture**: Equal Multi-Instance Monitoring (Arr-Managed)

---

## Progress Overview

| Phase | Status | Progress | Time Spent | Notes |
|-------|--------|----------|------------|-------|
| Phase 1: Database Schema | 🚧 In Progress | 0% | 0h | Starting with TorrentLibrary model |
| Phase 2: qBitManager Multi-Instance | ⏳ Pending | 0% | 0h | - |
| Phase 3: Arr Multi-Instance Scanning | ⏳ Pending | 0% | 0h | - |
| Phase 4: WebUI Backend | ⏳ Pending | 0% | 0h | - |
| Phase 5: Frontend | ⏳ Pending | 0% | 0h | - |
| Phase 6: Migration & Testing | ⏳ Pending | 0% | 0h | - |

**Overall Progress**: 0% (0/6 phases complete)

---

## Phase 1: Database Schema Updates (6-8 hours estimated)

### 1.1 Update TorrentLibrary Model ✅ DONE
- **Status**: ✅ Complete
- **File**: `qBitrr/tables.py`
- **Changes**:
  - [x] Add `QbitInstance` column to TorrentLibrary
  - [x] Add compound unique index on (Hash, QbitInstance) via Meta class
  - [x] No migration needed (databases recreated on restart)
- **Time**: 0.25h
- **Notes**: Model updated with QbitInstance field and compound unique constraint

### 1.2 Update Database Queries 🚧 IN PROGRESS
- **Status**: 🚧 In Progress
- **Files**: Multiple (arss.py, main.py, webui.py)
- **Changes**:
  - [ ] Find all TorrentLibrary.get() calls
  - [ ] Find all TorrentLibrary.select() calls
  - [ ] Find all TorrentLibrary.delete() calls
  - [ ] Add instance context to all queries
- **Time**: 0h
- **Notes**: Database migration not needed - DBs recreated on restart



---

## Phase 2: qBitManager Multi-Instance Support (16-24 hours estimated)

### 2.1 Add Multi-Client Dictionary
- **Status**: ⏳ Pending
- **File**: `qBitrr/main.py`
- **Changes**:
  - [ ] Add `self.clients: dict[str, qbittorrentapi.Client]`
  - [ ] Add `self.qbit_versions: dict[str, VersionClass]`
  - [ ] Add `self.instance_metadata: dict[str, dict]`
  - [ ] Add `self.instance_health: dict[str, bool]`
  - [ ] Keep backward compatibility with `self.client`

### 2.2 Implement Instance Initialization
- **Status**: ⏳ Pending
- **Changes**:
  - [ ] Create `_initialize_qbit_instances()` method
  - [ ] Create `_init_instance()` method
  - [ ] Parse config for [qBit-XXX] sections
  - [ ] Initialize all clients

### 2.3 Add Health Checking
- **Status**: ⏳ Pending
- **Changes**:
  - [ ] Create `is_instance_alive(instance_name)` method
  - [ ] Create `get_all_instances()` method
  - [ ] Update existing `is_alive` property for backward compat

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

## Phase 6: Migration & Testing (8-12 hours estimated)

### 6.1 Config Migration
- **Status**: ⏳ Pending
- **File**: `qBitrr/config.py`
- **Changes**:
  - [ ] Create `_migrate_to_multi_qbit_v4()` function
  - [ ] Bump config version to 4
  - [ ] Run database migration

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

1. `[TIMESTAMP]` - Initial commit: Updated database schema for multi-qBit support

---

## Issues Encountered

_None yet_

---

## Next Steps

1. ✅ Create feature branch
2. ✅ Create progress tracking file
3. 🚧 Update TorrentLibrary model in tables.py
4. Create database migration function
5. Test migration on sample database

---

## Legend

- ✅ Complete
- 🚧 In Progress
- ⏳ Pending
- ❌ Blocked
- ⚠️ Issue/Warning

---

## Current Status Summary

- ✅ **Phase 1.1 Complete**: TorrentLibrary model updated with QbitInstance field and compound unique index
- 🚧 **Phase 1.2 In Progress**: Need to update all database queries to include instance context
  - Found extensive usage in arss.py (~20+ query locations)
  - Need to pass `instance_name` parameter through call chains
  - This is a prerequisite for Phase 2 (qBitManager multi-instance support)

**Last Updated**: 2025-12-17 (Phase 1.1 complete, Phase 1.2 starting)
