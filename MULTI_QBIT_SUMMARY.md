# Multi-qBittorrent Implementation v3.0 - Executive Summary

## What Changed from v2.0?

**v2.0 Approach** (DEPRECATED):
- qBitrr attempted to route torrents to instances
- Priority system for instance selection
- Complex smart routing logic
- qBitrr managed download client assignment

**v3.0 Approach** (CURRENT):
- **Radarr/Sonarr/Lidarr handle download client selection**
- qBitrr **monitors ALL instances** for torrents
- No routing, no priorities, no smart selection
- Simple: scan all instances, process what's found

## Core Concept

```
Traditional (Single Instance):
Radarr → Download Client Config → qBittorrent
                                       ↓
                                  qBitrr monitors (health, import, cleanup)

v3.0 (Multi-Instance Monitoring):
Radarr → Download Client 1 → qBit-1
      → Download Client 2 → qBit-2    } qBitrr scans ALL instances
      → Download Client 3 → qBit-3      for "radarr" tagged torrents
                               ↓
                    Health checks, imports, cleanup on correct instance
```

### Key Insight

**Radarr/Sonarr/Lidarr already know how to distribute downloads** across multiple qBit instances via their download client settings. qBitrr doesn't need to be smart—it just needs to **find torrents wherever they are** and manage them on the correct instance.

## Configuration

### Multiple qBit Instances (All Equal)

```toml
# Default qBittorrent instance
[qBit]
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "password"

# Additional instances (equal status)
[qBit-Seedbox]
Host = "seedbox.example.com"
Port = 8080
UserName = "seedbox_user"
Password = "seedbox_pass"

[qBit-Server2]
Host = "192.168.1.100"
Port = 8090
UserName = "server2_user"
Password = "server2_pass"
```

### Arr Configuration (No Changes)

```toml
[Radarr-Movies]
Category = "radarr"
# That's it! qBitrr will scan ALL instances for "radarr" torrents

[Sonarr-TV]
Category = "sonarr"
# qBitrr will scan ALL instances for "sonarr" torrents
```

### Important Notes

1. **No routing fields**: No `Priority`, `AllowedCategories`, or `qBitInstance` fields needed
2. **Arr manages distribution**: Configure multiple download clients in Radarr/Sonarr
3. **qBitrr discovers torrents**: Scans all instances for category-tagged torrents
4. **Instance-aware operations**: All operations (health, import, cleanup) use correct instance

## How It Works

### 1. Arr Sends Torrent

User initiates download → Radarr/Sonarr decides which qBit instance to use (via its download client config) → Torrent appears on that instance with category tag

### 2. qBitrr Discovers Torrent

qBitrr scans ALL qBit instances → Finds torrent tagged "radarr" on qBit-Seedbox → Records `(hash, "qBit-Seedbox")` in database

### 3. qBitrr Monitors & Manages

- **Health checks**: Runs on qBit-Seedbox (where torrent exists)
- **Import trigger**: Tells Radarr to import from qBit-Seedbox path
- **Cleanup**: Removes from qBit-Seedbox when seeding done

## Architecture Changes

| Aspect | Current (v3) | New (v4) |
|--------|-------------|----------|
| **qBit Instances** | Single instance | Multiple instances (equal) |
| **Instance Selection** | N/A (only one) | Arr configures download clients |
| **Torrent Discovery** | Single scan | Scan ALL instances |
| **Database Schema** | Hash unique globally | `(Hash, QbitInstance)` unique |
| **Category Management** | One instance | Created on ALL instances |
| **Health Checks** | Single instance | Per-instance checks |
| **Import Triggering** | Single instance | Instance-aware |
| **Cleanup** | Single instance | Instance-specific |

## Benefits

### 1. **Simpler Architecture**
- No complex routing logic
- No priority calculations
- No "primary" vs "secondary" concepts
- Just scan and process

### 2. **Arr-Native Distribution**
- Uses Radarr/Sonarr's built-in download client management
- Leverages existing features (tags, priorities, conditions)
- No reinventing the wheel

### 3. **Transparent to Users**
- Configure qBit instances in qBitrr config
- Configure download clients in Arr
- Everything just works

### 4. **Flexible Deployment**
- Load balancing: Arr distributes across instances
- Geographic: Use different instances per region
- Performance: Fast instance for 4K, slow for 1080p
- All controlled in Arr, not qBitrr

## Configuration Examples

### Example 1: Simple High Availability

```toml
[qBit]
Host = "localhost"
Port = 8080

[qBit-Backup]
Host = "192.168.1.100"
Port = 8080

[Radarr-Movies]
Category = "radarr"
```

**In Radarr**: Configure 2 download clients:
- qBittorrent (localhost:8080) - Priority 1
- qBittorrent-Backup (192.168.1.100:8080) - Priority 0 (failover)

**Result**: Radarr uses localhost, falls back to backup if down. qBitrr monitors both.

### Example 2: Load Distribution

```toml
[qBit]
Host = "192.168.1.10"
Port = 8080

[qBit-Server2]
Host = "192.168.1.20"
Port = 8080

[qBit-Server3]
Host = "192.168.1.30"
Port = 8080

[Sonarr-TV]
Category = "sonarr"
```

**In Sonarr**: Configure 3 download clients with equal priority.

**Result**: Sonarr round-robins across all 3 instances. qBitrr monitors all 3.

### Example 3: Content Separation

```toml
[qBit]
Host = "localhost"
Port = 8080

[qBit-4K]
Host = "seedbox.example.com"
Port = 8080

[Radarr-1080p]
Category = "radarr"

[Radarr-4K]
Category = "radarr-4k"
```

**In Radarr-1080p**: Configure localhost download client.
**In Radarr-4K**: Configure seedbox download client.

**Result**: 1080p goes to localhost, 4K goes to seedbox. qBitrr monitors both.

## Implementation Effort

| Phase | Hours | Description |
|-------|-------|-------------|
| Database Schema | 6-8 | Add `QbitInstance` column, compound unique constraint |
| qBitManager Core | 16-24 | Multi-client initialization |
| Arr Monitoring | 24-32 | Scan all instances for category-tagged torrents |
| WebUI Backend | 10-14 | API endpoints for multi-instance status |
| Frontend | 12-18 | UI for viewing all instances |
| Migration | 8-12 | v3→v4 migration + testing |
| **Total** | **76-108** | **~2 weeks** |

## Migration Path

### From Single Instance (v3)

1. Upgrade qBitrr (automatic database migration)
2. Add additional qBit instances to config (optional):
   ```toml
   [qBit-Seedbox]
   Host = "seedbox.example.com"
   Port = 8080
   ```
3. Configure additional download clients in Radarr/Sonarr (if using multiple instances)
4. Restart qBitrr
5. Done! qBitrr now monitors all configured instances

### Config Changes

```diff
# v3 config (still works in v4!)
[qBit]
Host = "localhost"
Port = 8080

[Radarr-Movies]
Category = "radarr"

# v4 config (add more instances)
[qBit]
Host = "localhost"
Port = 8080

+ [qBit-Seedbox]
+ Host = "seedbox.example.com"
+ Port = 8080

[Radarr-Movies]
Category = "radarr"
# Now qBitrr monitors both instances for "radarr" torrents!
```

## Use Cases

### 1. High Availability
- Primary qBit on localhost
- Backup qBit on remote server
- Radarr/Sonarr fail over automatically
- qBitrr monitors both

### 2. Load Distribution
- 3+ qBit instances
- Radarr/Sonarr distribute downloads evenly
- qBitrr monitors all instances

### 3. Content Separation
- Fast SSD instance for 4K
- HDD instance for 1080p
- Separate Radarr instances point to different qBit instances
- qBitrr monitors all

### 4. Geographic Distribution
- qBit in US, EU, Asia
- Route by tracker/indexer in Radarr/Sonarr
- qBitrr monitors globally

## Comparison with v2.0

| Feature | v2.0 (Smart Routing) | v3.0 (Arr-Managed) |
|---------|---------------------|-------------------|
| Who selects instance? | qBitrr | Radarr/Sonarr |
| Routing logic | Complex (priority, rules) | None (discovery) |
| Configuration | Priority, AllowedCategories | Just host/port |
| Failover | qBitrr handles | Arr handles |
| Load balancing | qBitrr handles | Arr handles |
| Complexity | High | Low |
| User control | Limited (via qBitrr config) | Full (via Arr settings) |

## Benefits Over v2.0

1. **Simpler codebase**: No routing algorithm
2. **More powerful**: Leverages Arr's mature download client management
3. **User-friendly**: Configure distribution in familiar Arr UI
4. **Maintainable**: Less code, fewer bugs
5. **Flexible**: Use Arr's conditions, tags, indexer restrictions, etc.

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Database migration | High | Low | Automatic, tested, reversible |
| Instance discovery bugs | Medium | Low | Straightforward iteration |
| Performance (multi-scan) | Low | Very Low | Scans are fast, parallelizable |
| Breaking changes | High | Very Low | 100% backward compatible |

**Overall Risk**: Very Low ✅

## Success Criteria

- ✅ Multiple qBit instances configured
- ✅ Torrents discovered across all instances
- ✅ Health checks work on correct instance
- ✅ Imports triggered with correct instance context
- ✅ Cleanup removes from correct instance
- ✅ WebUI shows all instances
- ✅ Existing single-instance configs still work

## Next Steps

1. Review this summary and the full implementation plan
2. Ask questions / request clarifications
3. Begin Phase 1: Database schema updates

---

**Version**: 3.0
**Status**: ✅ Ready for Implementation
**Architecture**: Equal Multi-Instance Monitoring
**Backward Compatible**: ✅ 100%
**User Configuration**: Minimal (just add [qBit-Name] sections)
**Routing**: Handled by Radarr/Sonarr (not qBitrr)
