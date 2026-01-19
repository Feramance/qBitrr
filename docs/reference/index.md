# Reference

Quick reference documentation for qBitrr commands, APIs, and specifications.

## Command Line Interface

Complete CLI reference for qBitrr command-line options.

### Basic Usage

```bash
# Start qBitrr with default config
qbitrr

# Generate default configuration
qbitrr --gen-config

# Show version information
qbitrr --version

# Show license information
qbitrr --license

# Show source code link
qbitrr --source

# Show help message
qbitrr --help
```

**Note:** qBitrr uses configuration files and environment variables for all settings. There are no CLI flags for database operations, debugging, or service management. Use systemd, Docker, or process managers for service control.

### Environment Variables

qBitrr supports extensive environment variable configuration:

#### Core Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `QBITRR_CONFIG` | Path to config.toml | `~/config/config.toml` | `/config/config.toml` |
| `QBITRR_LOG_LEVEL` | Logging level | `INFO` | `DEBUG`, `WARNING` |
| `QBITRR_HOME` | qBitrr home directory | `~` | `/opt/qbitrr` |
| `QBITRR_CONFIG_PATH` | Config directory | `~/config` | `/config` |
| `QBITRR_DATA_DIR` | Data directory | `~/config` | `/data` |

#### qBittorrent Settings

| Variable | Description | Example |
|----------|-------------|---------|
| `QBITRR_QBITTORRENT_HOST` | qBittorrent URL | `http://qbittorrent:8080` |
| `QBITRR_QBITTORRENT_USERNAME` | qBittorrent username | `admin` |
| `QBITRR_QBITTORRENT_PASSWORD` | qBittorrent password | `adminadmin` |
| `QBITRR_QBITTORRENT_VERSION5` | Use qBittorrent v5 API | `true`, `false` |

#### Arr Instance Settings

For each Arr type, you can set:

| Variable Pattern | Description | Example |
|----------|-------------|---------|
| `QBITRR_RADARR_URL` | Radarr URL | `http://radarr:7878` |
| `QBITRR_RADARR_API_KEY` | Radarr API key | `your-api-key` |
| `QBITRR_SONARR_URL` | Sonarr URL | `http://sonarr:8989` |
| `QBITRR_SONARR_API_KEY` | Sonarr API key | `your-api-key` |
| `QBITRR_LIDARR_URL` | Lidarr URL | `http://lidarr:8686` |
| `QBITRR_LIDARR_API_KEY` | Lidarr API key | `your-api-key` |

#### WebUI Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `QBITRR_WEBUI_HOST` | WebUI bind address | `0.0.0.0` | `127.0.0.1` |
| `QBITRR_WEBUI_PORT` | WebUI port | `6969` | `8080` |
| `QBITRR_WEBUI_TOKEN` | API authentication token | (none) | `secret-token` |

#### Docker-Specific

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `PUID` | User ID for file permissions | `1000` | `1001` |
| `PGID` | Group ID for file permissions | `1000` | `1001` |
| `TZ` | Timezone | `UTC` | `America/New_York` |

### Usage Examples

#### Basic Startup

```bash
# Default startup
qbitrr

# With custom config
qbitrr --config /custom/config.toml

# With debug logging
export QBITRR_LOG_LEVEL=DEBUG
qbitrr
```

#### Docker Environment

```bash
# Run with environment variables
docker run -d \
  -e QBITRR_LOG_LEVEL=DEBUG \
  -e QBITRR_QBITTORRENT_HOST=http://qbittorrent:8080 \
  -e QBITRR_RADARR_URL=http://radarr:7878 \
  -e QBITRR_RADARR_API_KEY=your-key \
  -v /config:/config \
  feramance/qbitrr:latest
```

#### Database Maintenance

```bash
# Check database health
qbitrr --validate-db

# If corruption detected, repair
qbitrr --repair-db

# Optimize database
qbitrr --vacuum-db

# Reset search state (useful after config changes)
qbitrr --reset-searches
```

#### Debugging

```bash
# Test configuration without starting
qbitrr --validate-config
qbitrr --test-connections

# Run once and exit (for testing event loop)
qbitrr --once --debug

# Dry run (see what would happen without making changes)
qbitrr --dry-run
```

#### Systemd Service

```bash
# Check if running
systemctl status qbitrr

# View logs
journalctl -u qbitrr -f

# Restart service
systemctl restart qbitrr
```

### Exit Codes

qBitrr uses standard exit codes to indicate success or failure:

| Code | Meaning | Description |
|------|---------|-------------|
| `0` | Success | Normal exit, no errors |
| `1` | General error | Unspecified error occurred |
| `2` | Configuration error | Invalid config.toml or missing settings |
| `3` | Connection error | Can't connect to qBittorrent or Arr |
| `4` | Database error | Database corruption or access failure |
| `5` | Permission error | File permission issues |
| `6` | Import error | Failed to import Python modules |
| `130` | SIGINT (Ctrl+C) | User interrupted |
| `143` | SIGTERM | Terminated by system/Docker |

### Configuration File Priority

qBitrr searches for configuration in this order:

1. **Command-line argument**: `--config /path/to/config.toml`
2. **Environment variable**: `QBITRR_CONFIG=/path/to/config.toml`
3. **Docker default**: `/config/config.toml` (if running in Docker)
4. **User config**: `~/.config/qBitrr/config.toml` (pip install)
5. **Local config**: `~/config/config.toml` (native install)

### Logging Levels

Control log verbosity with `QBITRR_LOG_LEVEL` or `--debug`:

| Level | When to Use | Output Includes |
|-------|-------------|-----------------|
| `DEBUG` | Development, troubleshooting | All messages, API calls, database queries |
| `INFO` | Normal operation (default) | Status updates, imports, searches |
| `WARNING` | Production (less verbose) | Warnings, retryable errors |
| `ERROR` | Production (minimal) | Only errors that need attention |
| `CRITICAL` | Minimal (errors only) | Fatal errors only |

**Examples:**
```bash
# Debug mode
qbitrr --debug

# Or via environment
export QBITRR_LOG_LEVEL=DEBUG
qbitrr

# Or in config.toml
[Settings]
LogLevel = "DEBUG"
```

## API Reference

### REST API Endpoints

The qBitrr WebUI is powered by a REST API:

#### Process Management

```http
GET /api/processes
```
**Response:**
```json
{
  "processes": [
    {
      "name": "Radarr-Main",
      "status": "running",
      "pid": 12345,
      "uptime": 3600
    }
  ]
}
```

#### Logs

```http
GET /api/logs?limit=100&level=INFO
```
**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2025-11-26T12:00:00Z",
      "level": "INFO",
      "message": "Torrent imported successfully",
      "source": "Radarr-Main"
    }
  ]
}
```

#### Radarr Movies

```http
GET /api/radarr/movies?instance=Radarr-Main
```
**Response:**
```json
{
  "movies": [
    {
      "id": 1,
      "title": "Example Movie",
      "year": 2024,
      "monitored": true,
      "hasFile": true
    }
  ]
}
```

#### Configuration

```http
GET /api/config
POST /api/config
```

### Authentication

If WebUI token is configured:

```bash
curl http://localhost:6969/api/processes \
  -H "X-API-Token: your-token-here"
```

## Configuration Schema

### Main Settings

```toml
[Settings]
LogLevel = "INFO"           # DEBUG | INFO | WARNING | ERROR | CRITICAL
CheckInterval = 60          # Seconds between torrent checks
MaxConcurrentChecks = 10    # Max parallel health checks
RetentionDays = 30          # Days to keep old data
WebUIPort = 6969            # WebUI port
WebUIHost = "0.0.0.0"       # WebUI bind address
WebUIToken = ""             # Optional API token
```

### qBittorrent

```toml
[qBit]
Host = "localhost"          # qBittorrent URL
Port = 8080                 # qBittorrent port
UserName = "admin"          # qBit username
Password = "adminadmin"     # qBit password
```

### Arr Instances

```toml
[[Radarr]]  # or [[Sonarr]] or [[Lidarr]]
Name = "Radarr-Main"        # Unique identifier
URI = "http://localhost:7878"
APIKey = "your-api-key"
Category = "radarr"         # qBit category
AutoStart = true            # Start on launch
HealthCheck = true          # Enable health monitoring
InstantImport = true        # Instant imports
SearchMissing = false       # Auto-search missing
SearchPeriodDays = 7        # Search interval
```

## File Locations

### Default Paths

| File | Docker | Native | pip |
|------|--------|--------|-----|
| Config | `/config/config.toml` | `~/config/config.toml` | `~/.config/qBitrr/config.toml` |
| Database | `/config/qBitrr.db` | `~/config/qBitrr.db` | `~/.config/qBitrr/qBitrr.db` |
| Logs | `/config/logs/` | `~/config/logs/` | `~/.config/qBitrr/logs/` |
| Cache | `/config/cache/` | `~/config/cache/` | `~/.config/qBitrr/cache/` |

### Log Files

- `Main.log` - qBitrr application logs
- `WebUI.log` - Web interface logs
- `{ArrName}.log` - Per-Arr instance logs

## Error Codes

### Common Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Connection error |
| 4 | Database error |

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request |
| 401 | Unauthorized (missing/invalid token) |
| 404 | Not found |
| 500 | Internal server error |

## Database Schema

### Tables

#### downloads
Tracks downloaded torrents:

```sql
CREATE TABLE downloads (
  id INTEGER PRIMARY KEY,
  hash TEXT UNIQUE NOT NULL,
  name TEXT,
  arr_instance TEXT,
  status TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

#### searches
Search activity history:

```sql
CREATE TABLE searches (
  id INTEGER PRIMARY KEY,
  arr_instance TEXT,
  media_id INTEGER,
  search_type TEXT,
  created_at TIMESTAMP
);
```

#### expiry
Entry expiration tracking:

```sql
CREATE TABLE expiry (
  id INTEGER PRIMARY KEY,
  entry_type TEXT,
  entry_id INTEGER,
  expires_at TIMESTAMP
);
```

## Glossary

Comprehensive glossary of qBitrr and related terminology.

### qBitrr Terminology

| Term | Definition | Example/Notes |
|------|------------|---------------|
| **Arr** | Collective term for Radarr, Sonarr, and Lidarr | "Configure your Arr instances" |
| **Arr Instance** | A configured Radarr/Sonarr/Lidarr connection | Can have multiple instances per type |
| **Instant Import** | Triggering import immediately when download completes | Faster than Arr's periodic scan |
| **Health Check** | Monitoring torrent status and validity | Detects stalled, corrupted, or failed downloads |
| **FFprobe** | Media file validation tool | Verifies files are playable before import |
| **Stalled Torrent** | Download stuck or progressing too slowly | Triggered by ETA or speed thresholds |
| **ETA** | Estimated Time to Arrival (completion time) | Calculated by qBittorrent |
| **MaxETA** | Maximum allowed ETA before marking as stalled | E.g., 86400 = 24 hours max |
| **Category** | qBittorrent label for organizing torrents | Must match between qBitrr and Arr |
| **Import Mode** | How files are moved: Move, Copy, or Hardlink | Affects seeding after import |
| **Search Loop** | Periodic automated search for missing content | Configurable frequency and limits |
| **Quality Profile** | Arr quality/format preferences | E.g., "1080p", "Any", "4K HDR" |
| **Custom Format** | Arr-specific release preferences with scoring | E.g., prefer DTS-HD, HDR, specific groups |
| **Temporary Profile** | Lower quality profile used temporarily | E.g., accept MP3, upgrade to FLAC later |
| **Entry Search** | Search configuration for an Arr instance | Controls what/when to search |
| **Seeding Mode** | Controls when to stop seeding | Based on ratio, time, or both |
| **Tracker** | BitTorrent tracker configuration | Can have per-tracker seeding rules |

### Torrent Terminology

| Term | Definition | Example/Notes |
|------|------------|---------------|
| **Hash** | Unique torrent identifier | 40-character hexadecimal string |
| **Seed** | Upload torrent data to others | Required for torrent health |
| **Leech** | Download torrent data | Also called "peer" when partial |
| **Ratio** | Upload/download ratio | 2.0 = uploaded twice what downloaded |
| **Seeding Time** | Duration torrent has been seeding | Measured in seconds |
| **Tracker** | Server coordinating torrent swarm | Announces peers to each other |
| **DHT** | Distributed Hash Table (trackerless) | Decentralized peer discovery |
| **PEX** | Peer Exchange | Peers share peer lists |
| **Swarm** | All peers downloading/seeding a torrent | Larger swarm = better speeds |
| **Availability** | Percentage of torrent pieces available | <1.0 means incomplete swarm |

### Media Terminology

| Term | Definition | Example/Notes |
|------|------------|---------------|
| **Quality** | Video resolution and encoding | 1080p, 4K, 720p, etc. |
| **Codec** | Video/audio compression format | x264, x265, AV1, AAC, DTS |
| **Container** | File format wrapper | MKV, MP4, AVI |
| **HDR** | High Dynamic Range | HDR10, Dolby Vision |
| **Resolution** | Video dimensions | 1920x1080, 3840x2160 |
| **Bitrate** | Data rate of media | Higher = better quality |
| **Source** | Origin of media | Blu-ray, WEB-DL, HDTV |
| **Proper** | Fixed release replacing flawed one | Usually higher quality |
| **Repack** | Re-released to fix issues | Same quality, fixed problems |

### Arr-Specific Terms

| Term | Definition | Example/Notes |
|------|------------|---------------|
| **Monitored** | Arr is actively tracking this media | Will search for missing/upgrades |
| **Unmonitored** | Arr ignores this media | Won't search or upgrade |
| **Quality Cutoff** | Stop upgrading at this quality | E.g., stop at 1080p |
| **Quality Met** | File meets quality cutoff | No upgrade needed |
| **Quality Unmet** | File below quality cutoff | Eligible for upgrade |
| **Custom Format Score** | Points from custom format rules | Higher score = better quality |
| **Import** | Move/copy file to media library | From downloads to library |
| **Queue** | Downloads waiting to import | Arr's import queue |
| **Missing** | Media not in library | Eligible for search |
| **Wanted** | Missing monitored media | Arr will search for these |

### Technical Terms

| Term | Definition | Example/Notes |
|------|------------|---------------|
| **API** | Application Programming Interface | How qBitrr talks to Arr/qBittorrent |
| **API Key** | Authentication token for API | Found in Arr settings |
| **TOML** | Configuration file format | Human-readable config syntax |
| **SQLite** | Database engine | Used for qBitrr's persistent state |
| **WAL** | Write-Ahead Logging | SQLite mode for better concurrency |
| **Multiprocessing** | Running multiple processes | One per Arr instance |
| **Event Loop** | Repeated checking cycle | Torrent health checks happen here |
| **REST** | HTTP API architecture | qBitrr's WebUI API |
| **WebUI** | Web User Interface | Browser-based dashboard |
| **Docker** | Containerization platform | Recommended deployment method |
| **Volume** | Docker storage mount | Maps host directories to container |
| **Network** | Docker network | Connects containers together |
| **Environment Variable** | System configuration value | E.g., PUID, PGID, TZ |

### Status Terms

| Term | Meaning | Context |
|------|---------|---------|
| **Downloading** | Torrent actively downloading | Normal state |
| **Seeding** | Torrent uploading to others | After completion |
| **Paused** | Torrent stopped by user or qBitrr | Manual or automatic pause |
| **Stalled** | Torrent not progressing | Marked for removal/re-search |
| **Failed** | Download or import failed | Will trigger re-search if enabled |
| **Completed** | Download finished | Ready for import |
| **Imported** | Successfully imported to Arr | In media library now |
| **Queued** | Waiting in Arr import queue | Will import soon |
| **Pending** | Search scheduled but not run yet | Will search next cycle |
| **Blacklisted** | Release marked as failed in Arr | Won't be downloaded again |

For more detailed definitions, see the [Complete Glossary](glossary.md).

## Quick Reference Tables

### Common Configuration Values

#### Log Levels

| Level | Verbosity | Use Case |
|-------|-----------|----------|
| `DEBUG` | Highest | Development, troubleshooting |
| `INFO` | Normal | Default, production use |
| `WARNING` | Less | Production, reduce noise |
| `ERROR` | Minimal | Only errors |
| `CRITICAL` | Lowest | Fatal errors only |

#### Import Modes

| Mode | Behavior | Best For |
|------|----------|----------|
| `Move` | Moves files (default) | Public trackers, save space |
| `Copy` | Copies files, keeps original | Private trackers, continue seeding |
| `Hardlink` | Creates hardlink (same filesystem) | Best of both if same volume |

#### Seeding Modes (RemoveTorrent)

| Value | Behavior | When to Remove |
|-------|----------|----------------|
| `1` | Ratio only | When ratio met |
| `2` | Time only | When time met |
| `3` | Ratio OR Time | When either met |
| `4` | Ratio AND Time | When both met |

#### Search Ordering

| Setting | Effect | Use Case |
|---------|--------|----------|
| `SearchByYear = true` | Newest first | Prioritize recent content |
| `SearchByYear = false` | Alphabetical | Equal priority |
| `SearchInReverse = true` | Reverse order | Start from oldest |
| `SearchInReverse = false` | Normal order | Start from newest/A |

### Default Port Numbers

| Service | Default Port | Protocol |
|---------|--------------|----------|
| qBittorrent | 8080 | HTTP |
| qBittorrent | 6881 | BitTorrent |
| Radarr | 7878 | HTTP |
| Sonarr | 8989 | HTTP |
| Lidarr | 8686 | HTTP |
| Overseerr | 5055 | HTTP |
| Ombi | 3579 | HTTP |
| qBitrr WebUI | 6969 | HTTP |

### File Size Units

qBitrr accepts these file size units:

| Unit | Meaning | Example | Bytes |
|------|---------|---------|-------|
| `B` | Bytes | `1000B` | 1,000 |
| `KB` | Kilobytes | `10KB` | 10,000 |
| `MB` | Megabytes | `100MB` | 100,000,000 |
| `GB` | Gigabytes | `50GB` | 50,000,000,000 |
| `TB` | Terabytes | `2TB` | 2,000,000,000,000 |
| `K` | Kilobytes (short) | `10K` | 10,000 |
| `M` | Megabytes (short) | `100M` | 100,000,000 |
| `G` | Gigabytes (short) | `50G` | 50,000,000,000 |

**Example:**
```toml
[Settings]
FreeSpace = "50G"  # 50 gigabytes
```

### Time Units

qBitrr uses seconds for time values. Common conversions:

| Duration | Seconds | Config Value |
|----------|---------|--------------|
| 30 seconds | 30 | `30` |
| 1 minute | 60 | `60` |
| 5 minutes | 300 | `300` |
| 1 hour | 3,600 | `3600` |
| 6 hours | 21,600 | `21600` |
| 24 hours | 86,400 | `86400` |
| 7 days | 604,800 | `604800` |
| 14 days | 1,209,600 | `1209600` |
| 30 days | 2,592,000 | `2592000` |
| No limit | -1 | `-1` |

**Example:**
```toml
[Radarr.Torrent]
MaximumETA = 86400  # 24 hours
StalledDelay = 30   # 30 seconds

[Radarr.Torrent.SeedingMode]
MaxSeedingTime = 604800  # 7 days
```

### API Response Formats

All qBitrr API endpoints return JSON with this structure:

**Success:**
```json
{
  "status": "success",
  "data": {
    // Response data here
  }
}
```

**Error:**
```json
{
  "status": "error",
  "error": "Error message description",
  "code": 400
}
```

### Cron Expression Examples

For scheduled tasks (auto-updates, etc.):

| Expression | Meaning |
|------------|---------|
| `0 3 * * *` | Every day at 3:00 AM |
| `0 */6 * * *` | Every 6 hours |
| `0 0 * * 0` | Every Sunday at midnight |
| `*/15 * * * *` | Every 15 minutes |
| `0 2 * * 1` | Every Monday at 2:00 AM |
| `0 0 1 * *` | First day of every month |

## Configuration Examples

### Minimal Configuration

Simplest possible setup:

```toml
[Settings.Qbittorrent]
Host = "http://localhost"
Port = 8080
Username = "admin"
Password = "adminadmin"

[[Radarr]]
Name = "Radarr"
URI = "http://localhost:7878"
APIKey = "your-api-key-here"
```

### Production Configuration

Recommended production settings:

```toml
[Settings]
LogLevel = "INFO"
FreeSpace = "50G"
AutoPauseResume = true

[qBit]
Host = "qbittorrent"
Port = 8080
UserName = "admin"
Password = "your-secure-password"

[WebUI]
Host = "0.0.0.0"
Port = 6969
Token = "your-secret-token-here"

[[Radarr]]
Name = "Radarr-Movies"
URI = "http://radarr:7878"
APIKey = "${RADARR_API_KEY}"
Category = "radarr"
ImportMode = "Hardlink"

[Radarr-Movies.EntrySearch]
SearchMissing = true
SearchRequestsEvery = 300
DoUpgradeSearch = true

[Radarr-Movies.Torrent]
MaximumETA = 86400
StalledDelay = 30
DoNotRemoveSlow = true

[Radarr-Movies.Torrent.SeedingMode]
MaxUploadRatio = 2.0
MaxSeedingTime = 604800
RemoveTorrent = 3
```

### Complete Configuration

See [Configuration File Reference](../configuration/config-file.md) for comprehensive examples.

## Version Compatibility

### qBittorrent

- **v4.x** - Fully supported (automatically detected)
- **v5.x** - Fully supported (automatically detected)

### Arr Applications

- **Radarr** - v3.x, v4.x, v5.x
- **Sonarr** - v3.x, v4.x
- **Lidarr** - v1.x, v2.x

### Python

- **Minimum** - Python 3.11
- **Recommended** - Python 3.12+

## Useful Links

- **Repository:** https://github.com/Feramance/qBitrr
- **PyPI:** https://pypi.org/project/qBitrr2/
- **Docker Hub:** https://hub.docker.com/r/feramance/qbitrr
- **Documentation:** https://feramance.github.io/qBitrr/
- **Issues:** https://github.com/Feramance/qBitrr/issues
- **Discussions:** https://github.com/Feramance/qBitrr/discussions

## Related Documentation

- [Configuration Guide](../configuration/index.md)
- [Troubleshooting](../troubleshooting/index.md)
- [FAQ](../faq.md)
- [Development](../development/index.md)

## Support

Need help? Check out:

- [FAQ](../faq.md) - Common questions
- [Troubleshooting](../troubleshooting/index.md) - Problem solving
- [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions) - Community support
