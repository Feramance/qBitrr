# Migration Guide

This guide helps you migrate from older versions of qBitrr or similar tools to the latest version.

---

## Upgrading qBitrr

### Before You Upgrade

1. **Backup your configuration:**
   ```bash
   # Native
   cp ~/config/config.toml ~/config/config.toml.backup

   # Docker
   docker exec qbitrr cat /config/config.toml > config.toml.backup
   ```

2. **Backup your database:**
   ```bash
   # Native
   cp ~/config/qBitrr.db ~/config/qBitrr.db.backup

   # Docker
   docker cp qbitrr:/config/qBitrr.db qBitrr.db.backup
   ```

3. **Review release notes:**
   - Check [CHANGELOG.md](https://github.com/Feramance/qBitrr/blob/master/CHANGELOG.md) for breaking changes
   - Review [GitHub Releases](https://github.com/Feramance/qBitrr/releases) for version-specific notes

---

## Version-Specific Migration

### Migrating to v5.8.0+ (Database Consolidation)

!!! warning "Breaking Change: Database Consolidation"
    Version 5.8.0 introduces **single consolidated database** architecture. Old per-instance databases will be automatically deleted and data will be re-synced from your Arr instances.

#### What Changes

**Before (v5.7.x and earlier):**
```
~/config/qBitManager/
├── Radarr-4K.db
├── Radarr-1080.db
├── Sonarr-TV.db
├── Sonarr-4K.db
├── Lidarr.db
└── webui_activity.db
```

**After (v5.8.0+):**
```
~/config/qBitManager/
└── qbitrr.db  (single consolidated database)
```

#### Automatic Migration Process

When you upgrade to v5.8.0+:

1. **New consolidated database is created**
   - Single `qbitrr.db` file with `ArrInstance` field for data isolation
   - You'll see: `Initialized single database: /config/qBitManager/qbitrr.db`

2. **Old data is cleaned up** on first startup
   - Records without `ArrInstance` field are automatically removed
   - You'll see: `Database migration: Removed X old records without ArrInstance. qBitrr will repopulate data from Arr instances.`
   - This ensures data integrity and prevents mixing data between instances

3. **Performance indexes are created**
   - Indexes on `ArrInstance` field improve WebUI query performance
   - You'll see: `Created index: idx_arrinstance_moviesfilesmodel on moviesfilesmodel.ArrInstance` (×11)

4. **Data is automatically re-synced** from Arr instances
   - Takes 5-30 minutes depending on library size
   - Search history, queue state, and tracking data are rebuilt from Arr APIs
   - Each instance's data is properly tagged with its `ArrInstance` name
   - No manual intervention required

#### Benefits

- ✅ **Single file backup** instead of 9+ separate databases
- ✅ **Simplified management** (one VACUUM, one integrity check)
- ✅ **Better performance** (shared connection pool, reduced I/O, indexed queries)
- ✅ **78% less database code** (easier maintenance)
- ✅ **Proper data isolation** (`ArrInstance` field prevents data mixing)
- ✅ **Optimized WebUI queries** (11 indexes on `ArrInstance` field)

#### No Action Required

The migration is **fully automatic**. Just update and restart qBitrr.

!!! tip "First Startup May Take Longer"
    Allow 5-30 minutes for initial re-sync from Arr APIs on first startup after upgrade.

---

### Migrating from v4.x to v5.x

#### Major Changes

- **Config schema v3:** Adds process auto-restart settings
- **WebUI moved to separate section:** `[WebUI]` replaces `Settings.Host/Port/Token`
- **Quality profile mappings:** Changed from list-based to dict-based

#### Automatic Migration

qBitrr automatically migrates your config on first run:

```bash
# Native
qbitrr

# Docker
docker-compose up qbitrr
```

You'll see:

```
Config schema upgrade needed (v2 -> v3)
Config backup created: /config/config.toml.backup_20250326_120000
Migrated WebUI Host from Settings to WebUI section
Migration v2→v3: Added process auto-restart configuration settings
Configuration has been updated with migrations and defaults.
```

#### Manual Migration (If Needed)

**1. Move WebUI settings:**

**Old (v4.x):**

```toml
[Settings]
Host = "0.0.0.0"
Port = 6969
Token = "mytoken"
```

**New (v5.x):**

```toml
[WebUI]
Host = "0.0.0.0"
Port = 6969
Token = "mytoken"
LiveArr = true
GroupSonarr = true
GroupLidarr = true
Theme = "Dark"
```

**2. Update quality profile mappings:**

**Old (v4.x):**

```toml
[Radarr-Movies.EntrySearch]
MainQualityProfile = ["Ultra-HD", "HD-1080p"]
TempQualityProfile = ["HD-1080p", "HDTV-720p"]
```

**New (v5.x):**

```toml
[Radarr-Movies.EntrySearch]
QualityProfileMappings = { "Ultra-HD" = "HD-1080p", "HD-1080p" = "HDTV-720p" }
```

**3. Add process restart settings (optional):**

```toml
[Settings]
AutoRestartProcesses = true
MaxProcessRestarts = 5
ProcessRestartWindow = 300
ProcessRestartDelay = 5
```

---

### Migrating from v3.x to v4.x

#### Major Changes

- **qBittorrent 5.x support:** Automatic version detection (no config needed)
- **Custom format enhancements:** Better CF score handling
- **Search optimizations:** Smarter series vs. episode search

#### Steps

1. **Review custom format settings:**

```toml
[Radarr-Movies.EntrySearch]
CustomFormatUnmetSearch = false  # Enable if using TRaSH guides
ForceMinimumCustomFormat = false  # Enable for strict CF enforcement
```

3. **Update Sonarr search mode:**

```toml
[Sonarr-TV.EntrySearch]
SearchBySeries = "smart"  # New smart mode (recommended)
```

---

### Migrating from v2.x to v3.x

#### Major Changes

- **Multi-instance support:** Better handling of multiple Arr instances
- **Overseerr/Ombi integration:** Request prioritization
- **FFprobe auto-update:** Automatic binary management

#### Steps

1. **Update instance names:**

Ensure all Arr instances follow naming convention:

```toml
# ✅ Correct
[Radarr-Movies]
[Sonarr-TV]
[Lidarr-Music]

# ❌ Incorrect (will be ignored)
[Movies]
[TV]
```

2. **Configure FFprobe (now automatic):**

```toml
[Settings]
FFprobeAutoUpdate = true  # Default, downloads ffprobe automatically
```

3. **Add request integration (optional):**

```toml
[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = false
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "your-api-key"
ApprovedOnly = true
Is4K = false
```

---

## Migrating from Other Tools

### From qBittorrent-Manager

qBittorrent-Manager users will find qBitrr familiar but with many enhancements.

#### Key Differences

| Feature | qBittorrent-Manager | qBitrr |
|---------|-------------------|--------|
| Arr instances | Single instance | Multiple instances |
| Search automation | Limited | Full automation |
| Request integration | None | Overseerr/Ombi |
| WebUI | None | Full-featured React UI |
| Quality upgrades | Manual | Automated |
| Custom formats | Not supported | Full support |

#### Migration Steps

1. **Install qBitrr:**
   - Follow [Installation Guide](installation/index.md)

2. **Stop qBittorrent-Manager:**
   ```bash
   systemctl stop qbittorrent-manager
   ```

3. **Create qBitrr config:**
   ```bash
   qbitrr --gen-config
   ```

4. **Port configuration:**
   - Copy Arr connection details
   - Copy qBittorrent connection details
   - Set categories to match Arr download clients

5. **Test qBitrr:**
   ```bash
   qbitrr
   ```

6. **Disable qBittorrent-Manager:**
   ```bash
   systemctl disable qbittorrent-manager
   ```

---

### From Arr-Scripts

Users running custom Arr scripts can consolidate functionality into qBitrr.

#### qBitrr Replaces These Scripts

- ✅ Stalled torrent removal scripts
- ✅ Missing media search scripts
- ✅ Quality upgrade scripts
- ✅ Import trigger scripts
- ✅ Disk space monitoring scripts

#### Migration Steps

1. **Identify script functionality:**
   - List what each script does
   - Match to qBitrr features

2. **Configure equivalent qBitrr settings:**

   **Stalled removal script:**
   ```toml
   [Radarr-Movies.Torrent]
   StalledDelay = 15
   ReSearchStalled = true
   ```

   **Missing media script:**
   ```toml
   [Radarr-Movies.EntrySearch]
   SearchMissing = true
   SearchByYear = true
   SearchAgainOnSearchCompletion = true
   ```

   **Upgrade script:**
   ```toml
   [Radarr-Movies.EntrySearch]
   DoUpgradeSearch = true
   QualityUnmetSearch = true
   CustomFormatUnmetSearch = true
   ```

3. **Test qBitrr:**
   - Run in parallel with scripts initially
   - Verify qBitrr handles all functionality
   - Disable old scripts once confident

---

## Docker Migration

### From Docker Run to Docker Compose

**Old (docker run):**

```bash
docker run -d \
  --name qbitrr \
  -v /path/to/config:/config \
  -p 6969:6969 \
  feramance/qbitrr:latest
```

**New (docker-compose.yml):**

```yaml
version: "3.8"
services:
  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    volumes:
      - /path/to/config:/config
    ports:
      - "6969:6969"
    restart: unless-stopped
```

**Migrate:**

```bash
# Stop old container
docker stop qbitrr
docker rm qbitrr

# Start with compose
docker-compose up -d qbitrr
```

---

### Changing Docker Networks

**Scenario:** Moving from bridge to custom network

**Steps:**

1. **Update docker-compose.yml:**

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    networks:
      - mediastack  # Add custom network

networks:
  mediastack:
    external: true  # Or create here
```

2. **Update config.toml:**

```toml
[qBit]
Host = "qbittorrent"  # Use container name, not IP

[Radarr-Movies]
URI = "http://radarr:7878"  # Use container name
```

3. **Recreate container:**

```bash
docker-compose down qbitrr
docker-compose up -d qbitrr
```

---

## Configuration Consolidation

### Multiple Config Files to Single File

If you had split configs (one per Arr instance), consolidate to one `config.toml`:

**Old structure:**

```
config/
├── radarr.toml
├── sonarr.toml
├── lidarr.toml
└── settings.toml
```

**New structure:**

```
config/
└── config.toml  # Single file
```

**Consolidation:**

```toml
# Combine all sections into one file

[Settings]
# Global settings

[qBit]
# qBittorrent settings

[Radarr-Movies]
# Radarr instance 1

[Radarr-4K]
# Radarr instance 2

[Sonarr-TV]
# Sonarr instance

[Lidarr-Music]
# Lidarr instance
```

---

## Testing Your Migration

### Verification Checklist

After migrating, verify:

- [ ] **qBittorrent connection:**
  - Open WebUI → Processes tab
  - Check qBittorrent status: ✅ Connected

- [ ] **Arr connections:**
  - WebUI → Radarr/Sonarr/Lidarr tabs
  - Verify each shows "Connected"

- [ ] **Torrent monitoring:**
  - Add a test download in Arr
  - Verify qBitrr processes it
  - Check logs for activity

- [ ] **Search automation:**
  - Add a missing movie/show
  - Wait for search cycle
  - Check logs for search activity

- [ ] **WebUI access:**
  - Open http://localhost:6969
  - Verify all tabs load
  - Check real-time updates work

- [ ] **Logs:**
  - Review logs for errors
  - Look for migration messages
  - Verify expected operations

### Test Commands

```bash
# Check qBitrr is running
ps aux | grep qbitrr  # Native
docker ps | grep qbitrr  # Docker

# View logs
tail -f ~/logs/Main.log  # Native
docker logs -f qbitrr  # Docker

# Test API
curl http://localhost:6969/health

# Test qBittorrent connection
curl http://localhost:6969/api/qbittorrent/status
```

---

## Rollback Procedure

If migration fails or causes issues:

### Native Rollback

```bash
# Stop qBitrr
killall qbitrr

# Restore config
cp ~/config/config.toml.backup ~/config/config.toml

# Restore database
cp ~/config/qBitrr.db.backup ~/config/qBitrr.db

# Downgrade qBitrr
pip install qBitrr2==4.5.0  # Replace with desired version

# Restart
qbitrr
```

### Docker Rollback

```bash
# Stop container
docker-compose down qbitrr

# Restore config
docker cp config.toml.backup qbitrr:/config/config.toml

# Use older image
docker pull feramance/qbitrr:4.5.0
```

**docker-compose.yml:**

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:4.5.0  # Pin to old version
```

```bash
# Start with old version
docker-compose up -d qbitrr
```

---

## Getting Help

If you encounter issues during migration:

1. **Check logs for errors:**
   ```bash
   # Enable debug logging
   ConsoleLevel = "DEBUG"
   ```

2. **Review migration messages:**
   - Look for "Config schema upgrade needed"
   - Check for backup file creation
   - Note any migration warnings

3. **Compare configs:**
   ```bash
   diff config.toml.backup config.toml
   ```

4. **Ask for help:**
   - [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions)
   - [GitHub Issues](https://github.com/Feramance/qBitrr/issues)
   - Include:
     - Old version number
     - New version number
     - Migration error messages
     - Relevant log excerpts

---

## Related Documentation

- [Installation Guide](installation/index.md)
- [First Run Configuration](quickstart.md)
- [Configuration Overview](../configuration/index.md)
- [Troubleshooting](../troubleshooting/common-issues.md)
