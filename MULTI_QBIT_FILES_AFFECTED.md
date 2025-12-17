# Files Affected by Multi-qBittorrent Implementation

## Files to CREATE (10 new files)

### Configuration Examples
1. `config.single-instance.example.toml` - Single instance config example
2. `config.multi-instance.example.toml` - Multi-instance config example
3. `docker-compose.example.yml` - Docker Compose setup example

### Frontend Components
4. `webui/src/pages/QbitInstancesView.tsx` - qBit instances dashboard
5. `webui/src/pages/TransferStatsView.tsx` - Transfer statistics view (optional)

### Documentation
6. `docs/configuration/qbittorrent.md` - qBit configuration guide
7. `docs/getting-started/migration-multi-qbit.md` - Migration guide
8. `docs/troubleshooting/multi-qbit.md` - Troubleshooting guide

### Testing
9. `test_multi_qbit.py` - Unit tests
10. `test_multi_qbit.sh` - Manual testing script

---

## Files to MODIFY (16 existing files)

### Backend Core (7 files)

#### 1. `qBitrr/config.py`
**Lines affected**: Multiple additions
**Changes**:
- Add `_migrate_qbit_multi_instance()` function (new)
- Update `apply_config_migrations()` to call new migration
- Add `validate_multi_qbit_config()` function (new)
- Update config loading to support multiple qBit sections

#### 2. `qBitrr/config_version.py`
**Lines affected**: Line 1 (constant)
**Changes**:
- Change `EXPECTED_CONFIG_VERSION` from 3 to 4

#### 3. `qBitrr/gen_config.py`
**Lines affected**: Lines 250-287, 289-378
**Changes**:
- Update `_add_qbit_section()` to document multi-instance support
- Update `_gen_default_cat()` to add `qBitInstance` field
- Add comments about additional instance configuration

#### 4. `qBitrr/main.py` (qBitManager class)
**Lines affected**: Lines 80-175, 430-462, extensive changes
**Changes**:
- Replace `self.client` with `self.clients: dict[str, Client]`
- Add `self.qbit_versions: dict[str, VersionClass]`
- Add `_initialize_qbit_instances()` method (new)
- Add `get_client(instance_name)` method (new)
- Add `get_version(instance_name)` method (new)
- Add `is_instance_alive(instance_name)` method (new)
- Update `is_alive` property to check multiple instances
- Update `transfer_info()` to accept instance_name parameter
- Update `_validate_version()` to be per-instance

#### 5. `qBitrr/arss.py` (Arr class)
**Lines affected**: Lines 125-202, 91+ references throughout file
**Changes**:
- Add `self.qbit_instance_name` in `__init__` (line ~140)
- Add validation for qBit instance existence (line ~145)
- Add `@property qbit_client()` method (new, ~line 200)
- Replace ALL `self.manager.qbit_manager.client` with `self.qbit_client`
  - Line 152: Category lookup
  - Line 168: Category creation
  - Line 624, 641: Tag operations
  - Lines 4456, 4472, 6899, 7000, 7126: Torrent queries
  - Plus ~80+ more references throughout file

#### 6. `qBitrr/arss.py` (ArrManager class)
**Lines affected**: Lines 7194-7253
**Changes**:
- Add `self.category_to_qbit_instance: dict[str, str]` (new)
- Change `self.qbit: Client` to reference manager instead
- Update `build_arr_instances()` to track category→instance mapping
- Add `get_qbit_client_for_category()` method (new)
- Add logging for qBit instance assignments

#### 7. `qBitrr/webui.py`
**Lines affected**: Lines 2124-2153, multiple additions
**Changes**:
- Update `_status_payload()` to return all qBit instances
- Add `/api/qbit/instances` endpoint (new)
- Add `/api/qbit/<instance_name>/transfer` endpoint (new)
- Update status response format to include `qbitInstances`
- Add `qbitInstance` field to arr info in status

### Backend Optional (2 files)

#### 8. `qBitrr/env_config.py`
**Lines affected**: QbitEnvConfig class definition
**Changes**:
- Add support for multiple qBit instances via env vars (optional)
- Add parsing for `QBITRR_QBIT_<NAME>_HOST` pattern

#### 9. `qBitrr/utils.py`
**Lines affected**: Review only (no changes expected)
**Changes**:
- Verify `has_internet()` works with multiple clients (already parameterized)
- No modifications needed

### Frontend (5 files)

#### 10. `webui/src/api/types.ts`
**Lines affected**: Lines 42-53, new interfaces
**Changes**:
- Add `QbitInstance` interface (new)
- Update `StatusResponse` interface to add `qbitInstances`
- Update `ArrInfo` interface to add `qbitInstance` field
- Add `QbitInstancesResponse` interface (new)

#### 11. `webui/src/api/client.ts`
**Lines affected**: Add new functions
**Changes**:
- Add `getQbitInstances()` function (new)
- Add `getQbitTransferInfo(instanceName)` function (new)

#### 12. `webui/src/pages/ProcessesView.tsx`
**Lines affected**: Line ~250+ (process card rendering)
**Changes**:
- Add qBit instance indicator to process cards
- Show which qBit instance each Arr uses

#### 13. `webui/src/pages/ConfigView.tsx`
**Lines affected**: Multiple sections
**Changes**:
- Add qBit instance dropdown for Arr configs
- Add validation for qBit instance references
- Add button to create new qBit instance
- Add visual indicator for invalid references

#### 14. `webui/src/App.tsx`
**Lines affected**: Tab navigation
**Changes**:
- Add "qBittorrent" tab to navigation
- Wire up QbitInstancesView component

### Documentation (6 files)

#### 15. `README.md`
**Lines affected**: Features section, new section after features
**Changes**:
- Add "Multiple qBittorrent Instances" section
- Add quick start example
- Link to detailed configuration guide

#### 16. `CHANGELOG.md`
**Lines affected**: Top of file (Unreleased section)
**Changes**:
- Add "Multi-qBittorrent Instance Support" feature
- Note config version bump to v4
- Note automatic migration

#### 17. `API_DOCUMENTATION.md`
**Lines affected**: New endpoints section
**Changes**:
- Document `/api/qbit/instances` endpoint
- Document `/api/qbit/<instance>/transfer` endpoint
- Update `/api/status` documentation

#### 18. `docs/faq.md`
**Lines affected**: New section
**Changes**:
- Add multi-qBit FAQ section (6-8 Q&A pairs)

#### 19. `docs/configuration/index.md` (if exists)
**Lines affected**: Navigation/links
**Changes**:
- Add link to new qbittorrent.md guide

#### 20. Potentially: `mkdocs.yml`
**Lines affected**: Navigation section
**Changes**:
- Add new documentation pages to navigation

---

## Files NOT Affected (No Changes Needed)

### Database
- `qBitrr/tables.py` - Database schema (torrent hashes are unique, no changes needed)

### Other Core
- `qBitrr/errors.py` - Error classes (no new errors needed)
- `qBitrr/logger.py` - Logging setup (no changes needed)
- `qBitrr/ffprobe.py` - FFprobe functionality (independent of qBit)
- `qBitrr/versioning.py` - Version checking (qBitrr version, not qBit)
- `qBitrr/auto_update.py` - Auto-update functionality (independent)

### Other Frontend
- `webui/src/context/` - Context providers (no changes needed)
- `webui/src/hooks/` - Custom hooks (no changes needed)
- `webui/src/icons/` - Icon assets (no changes needed)
- Most other view pages (Radarr, Sonarr, Lidarr, Logs views are unchanged)

### Build/Deploy
- `setup.py` - Package setup (no changes needed)
- `pyproject.toml` - Project config (no changes needed)
- `Dockerfile` - Docker build (no changes needed)
- `qbitrr.service` - systemd service (no changes needed)
- `.github/workflows/*` - CI/CD workflows (no changes needed)

---

## Summary

| Category | New Files | Modified Files | Total |
|----------|-----------|----------------|-------|
| Backend | 0 | 7 | 7 |
| Frontend | 2 | 3 | 5 |
| Config Examples | 3 | 0 | 3 |
| Documentation | 3 | 4 | 7 |
| Testing | 2 | 0 | 2 |
| Optional | 0 | 2 | 2 |
| **TOTAL** | **10** | **16** | **26** |

---

## Change Density by File

| File | Lines Changed | Complexity | Priority |
|------|---------------|------------|----------|
| `qBitrr/arss.py` | 200-300 | High | Critical |
| `qBitrr/main.py` | 150-200 | High | Critical |
| `qBitrr/config.py` | 100-150 | Medium | Critical |
| `qBitrr/webui.py` | 80-120 | Medium | High |
| `qBitrr/gen_config.py` | 50-80 | Low | High |
| `webui/src/api/types.ts` | 40-60 | Low | High |
| `webui/src/pages/QbitInstancesView.tsx` | 150-200 (new) | Medium | Medium |
| All other files | < 50 each | Low | Low-Medium |

---

## Implementation Order

1. **Phase 1**: Config files (gen_config.py, config.py, config_version.py)
2. **Phase 2**: Core refactor (main.py qBitManager class)
3. **Phase 3**: Arr routing (arss.py Arr class - 91+ references!)
4. **Phase 4**: Manager tracking (arss.py ArrManager class)
5. **Phase 5**: WebUI backend (webui.py)
6. **Phase 6-8**: Frontend (types, client, components)
7. **Phase 9-10**: Testing & documentation
8. **Phase 11+**: Edge cases, polish, additional features

---

**Total Lines of Code**: ~2,500-3,500 new/modified
**Estimated Effort**: 135-185 hours
**Risk Level**: Medium (well-documented, backward compatible)
