# Configuration File Reference

This comprehensive guide explains every setting in qBitrr's `config.toml` configuration file.

---

## Configuration File Location

### Native Installation

```bash
~/config/config.toml           # Linux/macOS
%USERPROFILE%\config\config.toml  # Windows
```

### Docker Installation

```bash
/config/config.toml  # Inside container
```

Mounted from your host at the path specified in your Docker compose/run command.

---

## File Format

qBitrr uses **TOML** (Tom's Obvious, Minimal Language) for configuration.

**TOML basics:**

```toml
# Comments start with #
key = "value"
number = 42
boolean = true
list = ["item1", "item2", "item3"]

[Section]
nested_key = "nested value"

[[ArrayOfTables]]
name = "first"

[[ArrayOfTables]]
name = "second"
```

---

## Configuration Sections

qBitrr's configuration is organized into several sections:

1. **[Settings](#settings-section)** - Global qBitrr settings
2. **[WebUI](#webui-section)** - Web interface configuration
3. **[qBit](#qbit-section)** - qBittorrent connection
4. **[Sonarr-*](#arr-sections)** - Sonarr instance configuration
5. **[Radarr-*](#arr-sections)** - Radarr instance configuration
6. **[Lidarr-*](#arr-sections)** - Lidarr instance configuration

---

## Settings Section

The `[Settings]` section contains global configuration that applies to all qBitrr operations.

### Complete Settings Example

```toml
[Settings]
# Internal config schema version - DO NOT MODIFY
ConfigVersion = 3

# Logging
ConsoleLevel = "INFO"
Logging = true

# Paths
CompletedDownloadFolder = "/data/downloads"
FreeSpaceFolder = "/data/downloads"

# Disk space management
FreeSpace = "50G"
AutoPauseResume = true

# Timers
NoInternetSleepTimer = 15
LoopSleepTimer = 5
SearchLoopDelay = -1

# Special categories
FailedCategory = "failed"
RecheckCategory = "recheck"

# Torrent processing
Tagless = false
IgnoreTorrentsYoungerThan = 180

# Network
PingURLS = ["one.one.one.one", "dns.google.com"]

# FFprobe
FFprobeAutoUpdate = true

# Auto-updates
AutoUpdateEnabled = false
AutoUpdateCron = "0 3 * * 0"

# Process management
AutoRestartProcesses = true
MaxProcessRestarts = 5
ProcessRestartWindow = 300
ProcessRestartDelay = 5
```

---

### ConfigVersion

```toml
ConfigVersion = 3
```

**Type:** Integer
**Default:** `3`
**Required:** Yes (managed automatically)

Internal configuration schema version. **DO NOT MODIFY** this value manually. qBitrr uses it to detect when config migrations are needed.

---

### ConsoleLevel

```toml
ConsoleLevel = "INFO"
```

**Type:** String
**Default:** `"INFO"`
**Options:** `CRITICAL`, `ERROR`, `WARNING`, `NOTICE`, `INFO`, `DEBUG`, `TRACE`

Controls logging verbosity. Higher levels include all lower levels.

**Level descriptions:**

- `CRITICAL` - Only fatal errors
- `ERROR` - Errors that need attention
- `WARNING` - Warnings and errors
- `NOTICE` - Important notices, warnings, and errors
- `INFO` - **(Recommended)** General information
- `DEBUG` - Detailed debugging information
- `TRACE` - Very verbose, traces all operations

**Recommendation:** Start with `INFO`. Switch to `DEBUG` when troubleshooting.

---

### Logging

```toml
Logging = true
```

**Type:** Boolean
**Default:** `true`

Enable or disable logging to files. When enabled, logs are written to:

- Native: `~/logs/` or `%USERPROFILE%\logs\`
- Docker: `/config/logs/`

**Log files created:**

- `Main.log` - qBitrr main process
- `WebUI.log` - Web interface
- `Radarr-<name>.log` - Per Radarr instance
- `Sonarr-<name>.log` - Per Sonarr instance
- `Lidarr-<name>.log` - Per Lidarr instance

**Recommendation:** Keep enabled for troubleshooting.

---

### CompletedDownloadFolder

```toml
CompletedDownloadFolder = "/data/downloads"
```

**Type:** String (path)
**Required:** Yes

Path where qBittorrent saves completed downloads. This **must match** qBittorrent's "Default Save Path" setting.

**Finding this path:**

1. Open qBittorrent
2. Go to **Tools** → **Options** → **Downloads**
3. Note the **Default Save Path**

**Important:**

- Use forward slashes `/` (even on Windows)
- Don't include trailing slash
- Path must be accessible to qBitrr
- Docker: Must be the path as qBitrr sees it (inside container)

**Examples:**

```toml
# Linux/Docker
CompletedDownloadFolder = "/data/downloads"

# Windows (use forward slashes!)
CompletedDownloadFolder = "D:/Downloads/Complete"

# Network share (Docker)
CompletedDownloadFolder = "/mnt/nas/downloads"
```

---

### FreeSpace

```toml
FreeSpace = "50G"
```

**Type:** String
**Default:** `"-1"` (disabled)
**Format:** Number + Unit (`K`, `M`, `G`, `T`)

Minimum free space to maintain in download directory. When free space drops below this threshold, qBitrr pauses downloads.

**Units:**

- `K` - Kilobytes
- `M` - Megabytes
- `G` - Gigabytes (recommended)
- `T` - Terabytes

**Examples:**

```toml
FreeSpace = "50G"    # 50 gigabytes
FreeSpace = "100M"   # 100 megabytes
FreeSpace = "1T"     # 1 terabyte
FreeSpace = "-1"     # Disabled
```

**How it works:**

1. qBitrr monitors `FreeSpaceFolder` every loop
2. If free space < `FreeSpace` threshold:
   - Pauses all downloads
   - Keeps seeding active
   - Logs warning
3. When space frees up:
   - Resumes downloads automatically

**Recommendation:** Set to 10-20% of your disk capacity.

---

### FreeSpaceFolder

```toml
FreeSpaceFolder = "/data/downloads"
```

**Type:** String (path)
**Default:** Same as `CompletedDownloadFolder`

Folder to monitor for free space checks. Usually the same as `CompletedDownloadFolder`.

**Use cases for different path:**

- Download folder on SSD, monitoring HDD
- Monitoring parent filesystem
- Shared storage with multiple mount points

---

### AutoPauseResume

```toml
AutoPauseResume = true
```

**Type:** Boolean
**Default:** `true`

Enable automatic pausing and resuming of torrents. **Required** for `FreeSpace` feature to work.

When `true`:

- qBitrr can pause torrents when disk is full
- qBitrr can resume torrents when space frees up
- Health checks can pause/resume stalled torrents

**Recommendation:** Keep enabled.

---

### NoInternetSleepTimer

```toml
NoInternetSleepTimer = 15
```

**Type:** Integer (seconds)
**Default:** `15`

How long to wait when internet connection is lost before checking again.

**Process:**

1. qBitrr pings `PingURLS` to check connectivity
2. If all pings fail, internet is considered down
3. qBitrr sleeps for `NoInternetSleepTimer` seconds
4. Checks again

**Recommendation:** `15` for quick recovery, `60` for slower connections.

---

### LoopSleepTimer

```toml
LoopSleepTimer = 5
```

**Type:** Integer (seconds)
**Default:** `5`

Delay between each torrent processing loop. Lower values = more responsive, higher CPU usage.

**What happens each loop:**

- Check all managed torrents
- Detect stalled/failed downloads
- Process completed torrents
- Trigger imports
- Check disk space

**Recommendations:**

- `5` - **(Default)** Balanced
- `3` - More responsive
- `10` - Lower resource usage
- `1` - Very responsive (higher CPU)

---

### SearchLoopDelay

```toml
SearchLoopDelay = -1
```

**Type:** Integer (seconds)
**Default:** `-1` (uses 30 seconds)

Controls the delay **between individual search commands** when processing a batch of searches within a single search loop.

**How it works:**
- When set to `-1` (default): Uses 30 seconds between each search command
- When set to a positive value: Uses that many seconds between each search command
- Applies to both missing media searches and request searches (Overseerr/Ombi)

**Use cases:**
- **Default (`-1`)**: Recommended for most setups - 30 second delay prevents overwhelming indexers
- **Lower values (5-15)**: For faster request processing with high-quality indexers
- **Higher values (60-120)**: For limited indexer API calls or rate-limited trackers

**Example:**
If you have 10 missing movies to search:
- `SearchLoopDelay = -1` → 30 seconds between each movie search (5 minutes total)
- `SearchLoopDelay = 10` → 10 seconds between each movie search (1.7 minutes total)
- `SearchLoopDelay = 60` → 60 seconds between each movie search (10 minutes total)

!!! warning "Indexer Rate Limits"
    Setting this too low may trigger indexer rate limits. Most indexers allow 5-10 API calls per second, but spacing searches prevents hitting these limits.

**Recommendation:** Keep at `-1` for the default 30-second delay, or adjust based on your indexer's rate limits.

---

### FailedCategory

```toml
FailedCategory = "failed"
```

**Type:** String
**Default:** `"failed"`

qBittorrent category for manually marking torrents as failed.

**How to use:**

1. In qBittorrent, move a torrent to this category
2. qBitrr detects it on next loop
3. qBitrr marks it as failed in Arr
4. Triggers re-search (if enabled)
5. Removes torrent and files

**Use cases:**

- Fake/corrupt files
- Wrong content
- Manual intervention needed

---

### RecheckCategory

```toml
RecheckCategory = "recheck"
```

**Type:** String
**Default:** `"recheck"`

qBittorrent category for forcing torrent recheck.

**How to use:**

1. Move torrent to this category in qBittorrent
2. qBitrr forces a full recheck
3. Moves torrent back to original category
4. Continues normal processing

**Use cases:**

- Fix "missing files" errors
- After restoring from backup
- After moving download location

---

### Tagless

```toml
Tagless = false
```

**Type:** Boolean
**Default:** `false`

**Advanced feature:** Manage torrents without requiring Arr tags.

When `false` (default):

- qBitrr uses both category and tags to identify torrents
- More reliable
- Recommended

When `true`:

- qBitrr uses only categories
- Useful if Arr doesn't apply tags consistently
- May cause conflicts if multiple Arr instances share categories

**Recommendation:** Keep `false` unless you have specific tagging issues.

---

### IgnoreTorrentsYoungerThan

```toml
IgnoreTorrentsYoungerThan = 180
```

**Type:** Integer (seconds)
**Default:** `180` (3 minutes)

Ignore torrents newer than this age for certain operations.

**Applies to:**

- `FailedCategory` processing
- `RecheckCategory` processing
- Some health checks

**Why?**

- Torrents need time to start
- Prevents false "stalled" detection
- Allows metadata to load

**Recommendations:**

- `180` - **(Default)** 3 minutes
- `120` - 2 minutes (faster)
- `300` - 5 minutes (more conservative)

---

### PingURLS

```toml
PingURLS = ["one.one.one.one", "dns.google.com"]
```

**Type:** Array of strings
**Default:** `["one.one.one.one", "dns.google.com"]`

Hostnames to ping for internet connectivity checks.

**Requirements:**

- Must be reliable, always-online services
- Must respond to ICMP pings or HTTP
- Must tolerate frequent pings

**Examples:**

```toml
# Cloudflare and Google DNS
PingURLS = ["one.one.one.one", "dns.google.com"]

# Alternative DNS providers
PingURLS = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]

# Mix of services
PingURLS = ["cloudflare.com", "google.com", "github.com"]
```

**Recommendation:** Keep at least 2 URLs for redundancy.

---

### FFprobeAutoUpdate

```toml
FFprobeAutoUpdate = true
```

**Type:** Boolean
**Default:** `true`

Automatically download and update FFprobe binary for media file validation.

When `true`:

- qBitrr downloads FFprobe from https://ffbinaries.com/downloads
- Automatically updates to latest version
- Stored in `~/config/qBitManager/ffprobe`

When `false`:

- You must provide your own FFprobe binary
- Place at `~/config/qBitManager/ffprobe` (Linux/Mac) or `ffprobe.exe` (Windows)

**Recommendation:** Keep `true` for automatic management.

---

### AutoUpdateEnabled

```toml
AutoUpdateEnabled = false
```

**Type:** Boolean
**Default:** `false`

Enable automatic qBitrr updates on a schedule.

When `true`:

- qBitrr checks for updates on schedule (see `AutoUpdateCron`)
- Downloads and installs latest version
- Restarts automatically
- Logs update in `Main.log`

**Supported installation methods:**

- ✅ PyPI package (`pip install`)
- ✅ Docker (pulls latest image)
- ⚠️ Binary (manual, not fully automated)

**Recommendation:** Enable for Docker deployments. Consider manual updates for PyPI.

---

### AutoUpdateCron

```toml
AutoUpdateCron = "0 3 * * 0"
```

**Type:** String (cron expression)
**Default:** `"0 3 * * 0"` (Sundays at 3:00 AM)

Cron schedule for automatic updates (when `AutoUpdateEnabled = true`).

**Cron format:**

```
┌─ minute (0-59)
│ ┌─ hour (0-23)
│ │ ┌─ day of month (1-31)
│ │ │ ┌─ month (1-12)
│ │ │ │ ┌─ day of week (0-6, 0=Sunday)
│ │ │ │ │
* * * * *
```

**Examples:**

```toml
# Every Sunday at 3:00 AM
AutoUpdateCron = "0 3 * * 0"

# Every day at 2:00 AM
AutoUpdateCron = "0 2 * * *"

# Every Monday at 4:30 AM
AutoUpdateCron = "30 4 * * 1"

# First day of month at midnight
AutoUpdateCron = "0 0 1 * *"
```

**Tools:** Use [crontab.guru](https://crontab.guru) to validate expressions.

---

### AutoRestartProcesses

```toml
AutoRestartProcesses = true
```

**Type:** Boolean
**Default:** `true`

Automatically restart crashed worker processes.

When `true`:

- Crashed Arr manager processes restart automatically
- Subject to restart limits (see below)
- Prevents infinite crash loops

When `false`:

- Crashed processes stay down
- Only logs failures
- Requires manual intervention

**Recommendation:** Keep `true` for automatic recovery.

---

### MaxProcessRestarts

```toml
MaxProcessRestarts = 5
```

**Type:** Integer
**Default:** `5`

Maximum restart attempts per process within `ProcessRestartWindow`.

**How it works:**

- Process crashes
- qBitrr restarts it after `ProcessRestartDelay`
- If process crashes `MaxProcessRestarts` times within `ProcessRestartWindow`:
  - Auto-restart disabled for that process
  - Manual intervention required

**Recommendation:** `5` is safe. Increase if you have intermittent issues.

---

### ProcessRestartWindow

```toml
ProcessRestartWindow = 300
```

**Type:** Integer (seconds)
**Default:** `300` (5 minutes)

Time window for tracking restart attempts.

**Example:**

- `MaxProcessRestarts = 5`
- `ProcessRestartWindow = 300`
- If a process restarts 5 times within 5 minutes, auto-restart stops

**Recommendation:** `300` (5 minutes) prevents crash loops while allowing recovery.

---

### ProcessRestartDelay

```toml
ProcessRestartDelay = 5
```

**Type:** Integer (seconds)
**Default:** `5`

Wait time before attempting to restart a crashed process.

**Why wait?**

- Gives system time to recover
- Prevents immediate re-crash
- Allows logs to flush

**Recommendation:** `5` is sufficient. Increase if processes crash immediately after restart.

---

## WebUI Section

The `[WebUI]` section configures qBitrr's web interface.

### Complete WebUI Example

```toml
[WebUI]
Host = "0.0.0.0"
Port = 6969
Token = ""
LiveArr = true
GroupSonarr = true
GroupLidarr = true
Theme = "Dark"
```

---

### Host

```toml
Host = "0.0.0.0"
```

**Type:** String (IP address)
**Default:** `"0.0.0.0"`

IP address the WebUI listens on.

**Options:**

- `0.0.0.0` - **(Default)** Listen on all interfaces
- `127.0.0.1` - Localhost only (secure, but can't access remotely)
- Specific IP - Listen on one network interface

**Recommendation:** `0.0.0.0` for Docker, `127.0.0.1` + reverse proxy for native.

---

### Port

```toml
Port = 6969
```

**Type:** Integer
**Default:** `6969`

TCP port for the WebUI.

**Access:** `http://<host>:<port>/ui`

**Examples:**

```toml
Port = 6969   # http://localhost:6969/ui
Port = 8080   # http://localhost:8080/ui
Port = 443    # https://localhost:443/ui (with reverse proxy)
```

---

### Token

```toml
Token = ""
```

**Type:** String
**Default:** `""` (empty, no authentication)

Bearer token for API authentication.

When **empty:**

- WebUI and API are publicly accessible
- No authentication required

When **set:**

- All `/api/*` endpoints require authentication
- Must include `Authorization: Bearer` header in requests

**Setting up authentication:**

```toml
[WebUI]
Token = "my-secret-token-12345"
```

**Using authenticated API:**

```bash
curl -H "Authorization: Bearer my-secret-token-12345" \
  http://localhost:6969/api/processes
```

**Recommendation:** Set a token if qBitrr is accessible from the internet.

---

### LiveArr

```toml
LiveArr = true
```

**Type:** Boolean
**Default:** `true`

Enable live updates in Arr views (Radarr/Sonarr/Lidarr tabs).

When `true`:

- Real-time status updates
- Progress bars update live
- No manual refresh needed

When `false`:

- Static snapshots
- Must manually refresh page
- Lower resource usage

**Recommendation:** Keep `true` for best UX.

---

### GroupSonarr

```toml
GroupSonarr = true
```

**Type:** Boolean
**Default:** `true`

Group Sonarr episodes by series in the WebUI.

When `true`:

```
└─ Breaking Bad
   ├─ S01E01
   ├─ S01E02
   └─ S01E03
```

When `false`:

```
├─ Breaking Bad S01E01
├─ Breaking Bad S01E02
└─ Breaking Bad S01E03
```

**Recommendation:** `true` for cleaner view.

---

### GroupLidarr

```toml
GroupLidarr = true
```

**Type:** Boolean
**Default:** `true`

Group Lidarr albums by artist in the WebUI.

When `true`:

```
└─ Pink Floyd
   ├─ The Dark Side of the Moon
   ├─ The Wall
   └─ Wish You Were Here
```

When `false`:

```
├─ Pink Floyd - The Dark Side of the Moon
├─ Pink Floyd - The Wall
└─ Pink Floyd - Wish You Were Here
```

**Recommendation:** `true` for better organization.

---

### Theme

```toml
Theme = "Dark"
```

**Type:** String
**Default:** `"Dark"`
**Options:** `Dark`, `Light`

WebUI color theme.

- `Dark` - Dark mode (easier on eyes)
- `Light` - Light mode (better in bright environments)

**Note:** Users can toggle theme in the WebUI itself. This sets the default.

---

## qBit Section

The `[qBit]` section configures the connection to qBittorrent.

### Complete qBit Example

```toml
[qBit]
Disabled = false
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "adminpass"
```

For detailed qBittorrent configuration, see the [qBittorrent Configuration Guide](qbittorrent.md).

---

## Arr Sections

Arr sections follow the naming pattern `[<Type>-<Name>]`:

- `[Radarr-Movies]`
- `[Sonarr-TV]`
- `[Lidarr-Music]`

Each Arr instance has its own section with subsections for:

- `[<Type>-<Name>.EntrySearch]` - Automated searching
- `[<Type>-<Name>.Overseerr]` - Request integration (Radarr/Sonarr only)
- `[<Type>-<Name>.Torrent]` - Torrent management
- `[<Type>-<Name>.Torrent.SeedingMode]` - Seeding configuration
- `[[<Type>-<Name>.Torrent.Trackers]]` - Per-tracker settings

For complete Arr configuration documentation:

- [Radarr Configuration](arr/radarr.md)
- [Sonarr Configuration](arr/sonarr.md)
- [Lidarr Configuration](arr/lidarr.md)

---

## Configuration Best Practices

### 1. Start with Example Config

```bash
# Generate example config
qbitrr --gen-config

# Copy to config location
cp config.example.toml ~/config/config.toml
```

---

### 2. Use Environment Variables

Override settings with environment variables (Docker-friendly):

```bash
# Format: QBITRR_<SECTION>_<KEY>
export QBITRR_SETTINGS_CONSOLELEVEL=DEBUG
export QBITRR_WEBUI_PORT=8080
export QBITRR_QBIT_HOST=qbittorrent
```

---

### 3. Validate Your Config

Check for syntax errors:

```bash
# Python TOML validation
python3 -c "import toml; toml.load('~/config/config.toml')"

# Or use online validator
# https://www.toml-lint.com/
```

---

### 4. Backup Your Config

```bash
# Before major changes
cp ~/config/config.toml ~/config/config.toml.backup

# Automated backup (cron)
0 0 * * * cp ~/config/config.toml ~/config/config.toml.$(date +\%Y\%m\%d)
```

---

### 5. Version Control

```bash
# Initialize git repo
cd ~/config
git init
git add config.toml
git commit -m "Initial config"

# Track changes
git diff  # See what changed
git commit -am "Adjusted stall delay"
```

---

### 6. Security

**Sensitive data in config:**

```toml
# DON'T commit these to public repos
APIKey = "your-secret-key"
Password = "your-password"
Token = "your-token"
```

**Use environment variables for secrets:**

```bash
export QBITRR_RADARR_MOVIES_APIKEY="your-secret-key"
export QBITRR_QBIT_PASSWORD="your-password"
```

---

### 7. Documentation

Add comments to your config:

```toml
[Radarr-4K]
# Separate instance for 4K movies
# Uses higher quality profile and longer ETAs
MaximumETA = 172800  # 48 hours for large 4K files
```

---

## Troubleshooting Config Issues

### Config Not Loading

**Symptoms:** qBitrr uses defaults or doesn't start

**Solutions:**

1. **Check file location:**
   ```bash
   # Native
   ls -l ~/config/config.toml

   # Docker
   docker exec qbitrr ls -l /config/config.toml
   ```

2. **Check file permissions:**
   ```bash
   chmod 644 ~/config/config.toml
   ```

3. **Validate TOML syntax:**
   ```bash
   python3 -c "import toml; toml.load('/path/to/config.toml')"
   ```

---

### Invalid Value Errors

**Symptoms:** "Invalid value for X" errors in logs

**Solutions:**

1. **Check data types:**
   ```toml
   # Wrong
   Port = "6969"  # String

   # Right
   Port = 6969    # Integer
   ```

2. **Check enums:**
   ```toml
   # Wrong
   ConsoleLevel = "info"

   # Right
   ConsoleLevel = "INFO"
   ```

---

### Changes Not Applied

**Symptoms:** Modified config not taking effect

**Solution:** Restart qBitrr after config changes:

```bash
# Native
qbitrr --restart

# Docker
docker restart qbitrr

# Systemd
sudo systemctl restart qbitrr
```

---

### Missing Required Values

**Symptoms:** "Missing required config key" errors

**Solution:** Check these are set:

```toml
[Settings]
CompletedDownloadFolder = "/path/to/downloads"  # Required

[qBit]
Host = "localhost"  # Required
```

---

## Complete Minimal Config

Absolute minimum configuration to get started:

```toml
[Settings]
ConfigVersion = 3
CompletedDownloadFolder = "/data/downloads"

[WebUI]
Host = "0.0.0.0"
Port = 6969

[qBit]
Disabled = false
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "adminpass"

[Radarr-Movies]
Managed = true
URI = "http://localhost:7878"
APIKey = "your-radarr-api-key"
Category = "radarr-movies"
ReSearch = true
```

---

## Advanced/Hidden Settings

These configuration options exist but are not generated by `qbitrr --gen-config` because they are intended for advanced troubleshooting only.

### Settings.ProcessSpawnTimeoutSeconds

```toml
[Settings]
ProcessSpawnTimeoutSeconds = 60  # Increase if slow storage
```

**Type:** Integer (seconds)
**Default:** 30 seconds
**Added manually to config**

Timeout for spawning Arr instance worker processes during startup.

**When to adjust:**

- Slow disk I/O (network storage, HDD)
- High system load during startup
- Database on slow filesystem

**Behavior:**

- If process doesn't spawn within timeout, startup fails with error
- Increase if seeing "Process spawn timed out" errors
- Do NOT set below 10 seconds

**Default is usually sufficient** - only adjust if experiencing startup timeouts.

---

## Edge Case Behaviors

### Infinite Retry Loops

qBitrr uses infinite retry loops in specific scenarios for reliability:

#### Quality Profile Fetching (Startup)

**Location:** `arss.py`
**Behavior:** Retries forever until Arr responds with quality profiles

**Retry Strategy:**

- Network errors: Immediate retry
- Server errors: Wait 5 minutes, retry
- Unexpected errors: Give up

**Why:** Quality profiles are required for proper operation. Startup blocks until available.

**Impact:** Startup can hang if Arr is persistently unavailable. Check Arr logs if this occurs.

#### Search Command Posting

**Location:** `arss.py`
**Behavior:** Retries search API call until network succeeds

**Retry Strategy:**

- ChunkedEncodingError: Retry immediately
- ContentDecodingError: Retry immediately
- ConnectionError: Retry immediately
- JSONDecodeError: Retry immediately

**Why:** Ensures search commands are never lost due to transient network issues.

**Impact:** Search processing pauses during Arr downtime but resumes automatically when Arr recovers.

**Note:** `Searched=True` only set AFTER successful API call, so failed searches are retried.

---

## Implementation Details (Not User-Configurable)

### Database WAL Checkpoint

qBitrr automatically performs WAL checkpoint and VACUUM on database errors for self-repair.

**Not configurable** - happens automatically during database error recovery.

See [Database Troubleshooting](../troubleshooting/database.md) for details on manual database maintenance.

### TAGLESS Mode Exception

When `Settings.Tagless = true`, qBitrr emulates tags using database entries EXCEPT for the special `qBitrr-ignored` tag, which still uses a real qBittorrent tag.

**Why:** The ignore functionality requires a real tag to prevent qBitrr from processing marked torrents.

**This is intentional design**, not a bug.

---

## See Also

- [Getting Started Guide](../getting-started/index.md)
- [qBittorrent Configuration](qbittorrent.md)
- [Radarr Configuration](arr/radarr.md)
- [Sonarr Configuration](arr/sonarr.md)
- [Lidarr Configuration](arr/lidarr.md)
- [Troubleshooting](../troubleshooting/index.md)
