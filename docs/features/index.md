# Features Overview

qBitrr provides intelligent automation and monitoring for your media management setup, bridging the gap between qBittorrent and the Arr stack (Radarr/Sonarr/Lidarr).

---

## Core Features

### 🏥 [Health Monitoring](health-monitoring.md)

Continuous torrent health checks with automatic failure detection and recovery.

**Key capabilities:**

- **Stalled torrent detection** - Automatically identifies and handles stuck downloads
- **Slow torrent handling** - Monitors download speeds and ETA thresholds
- **File validation** - Uses FFprobe to verify media file integrity
- **Tracker monitoring** - Detects dead or unreachable trackers
- **Smart removal** - Protects near-complete downloads from accidental deletion

[Learn more about Health Monitoring →](health-monitoring.md)

---

### ⚡ Instant Imports

Trigger imports in your Arr instances as soon as downloads complete, without waiting for Arr's periodic scans.

**Benefits:**

- **Faster availability** - Media appears in your library within seconds
- **Reduced wait time** - No more waiting for Arr's refresh cycles
- **Lower API load** - Targeted import commands instead of full queue scans
- **Better UX** - Request fulfillment happens immediately

**How it works:**

1. qBittorrent finishes downloading a file
2. qBitrr detects completion instantly
3. qBitrr validates files with FFprobe (optional)
4. qBitrr tells Arr to import the specific download
5. Arr processes import immediately
6. Media appears in your library

**Configuration:**

Instant imports are automatic when qBitrr is managing an Arr instance. No special configuration needed - just ensure `Managed = true` for your Arr instances.

---

### 🔄 Automated Re-searching

When downloads fail, qBitrr automatically triggers new searches to find alternative releases.

**Triggers:**

- Stalled torrents exceeding `StalledDelay`
- Files failing FFprobe validation
- Torrents moved to the `failed` category
- Arr import errors matching `ArrErrorCodesToBlocklist`
- Tracker errors or unavailable peers

**Configuration:**

```toml
[Radarr-Movies]
# Enable automatic re-searching
ReSearch = true

# Error codes that trigger re-search
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing movie file(s)",
  "Unable to determine if file is a sample"
]
```

**Workflow:**

1. qBitrr detects download failure
2. Marks release as failed in Arr
3. Blacklists the release to prevent re-download
4. Removes torrent and files
5. Triggers Arr to search for alternative releases
6. Arr finds and downloads a new release

---

### 🔍 Missing Content Search

Automatically search for missing media in your Arr libraries.

**Features:**

- **Continuous searching** - Automatically queries for missing movies/shows/albums
- **Smart scheduling** - Configurable delays between searches to respect indexer limits
- **Search ordering** - Search by date, reverse order, or quality priority
- **Upgrade searches** - Find better quality versions of existing media
- **Quality unmet search** - Enforce quality profile requirements
- **Custom format search** - Search for releases meeting custom format scores

**Example configuration:**

```toml
[Sonarr-TV.EntrySearch]
# Search for missing episodes
SearchMissing = true

# Delay between searches (seconds)
SearchRequestsEvery = 300  # 5 minutes

# Search order
SearchByYear = true
SearchInReverse = false

# Upgrade searches
DoUpgradeSearch = true
QualityUnmetSearch = true
```

**Use cases:**

- **Initial library setup** - Search through entire wanted list
- **New content** - Automatically find newly aired episodes
- **Quality upgrades** - Replace existing files with better versions
- **Hard-to-find media** - Continuous searching for rare content

---

### 📊 Quality Upgrades

Automatically replace existing media with higher quality versions.

**How it works:**

1. qBitrr monitors your library for quality-unmet items
2. Searches for releases matching your quality profile
3. Downloads better quality versions
4. Arr replaces old files with upgraded versions
5. qBittorrent continues seeding old files (if using `Copy` mode)

**Configuration:**

```toml
[Radarr-Movies.EntrySearch]
# Enable upgrade searching
DoUpgradeSearch = true

# Search for quality-unmet items
QualityUnmetSearch = true

# Custom format score enforcement
CustomFormatUnmetSearch = true
ForceMinimumCustomFormat = false
```

**Example scenarios:**

- **SD → HD** - Upgrade 480p/720p to 1080p
- **HD → 4K** - Upgrade 1080p to 2160p
- **Lossy → Lossless** - Upgrade MP3 to FLAC (Lidarr)
- **Better codec** - Upgrade x264 to x265/AV1
- **Proper/Repack** - Replace scene releases with fixed versions

---

### 🎭 Temporary Quality Profiles

Temporarily lower quality requirements for missing media, then upgrade later.

**Use case:** You want FLAC music, but you'll accept MP3 for now to avoid missing content.

**Workflow:**

1. Album is missing, quality profile set to "Lossless (FLAC)"
2. qBitrr temporarily switches it to "Any (MP3-320)"
3. Lidarr finds and downloads an MP3 release
4. After import, qBitrr switches back to "Lossless (FLAC)"
5. Future upgrade searches look for FLAC versions

**Configuration:**

```toml
[Lidarr-Music.EntrySearch]
# Enable temporary profiles
UseTempForMissing = true

# Profile mappings (main → temporary)
QualityProfileMappings = {"Lossless (FLAC)" = "Any (MP3-320)"}

# Auto-reset after timeout
TempProfileResetTimeoutMinutes = 10080  # 7 days

# Reset on startup
ForceResetTempProfiles = true
```

---

### 🌐 Request Integration (Overseerr/Ombi)

Automatically process media requests from Overseerr or Ombi.

**Features:**

- **Approved-only mode** - Only process approved requests
- **4K instance support** - Route 4K requests to dedicated Arr instances
- **Automatic triggering** - RSS sync and refresh on new requests
- **Status tracking** - Monitor request fulfillment

**Configuration:**

```toml
[Radarr-Movies.Overseerr]
# Overseerr URL
OverseerrURL = "http://localhost:5055"

# Overseerr API key
OverseerrAPIKey = "your-api-key"

# Only process approved requests
ApprovedOnly = true

# 4K instance flag
Is4K = false
```

**Supported:**

- ✅ Radarr (movies)
- ✅ Sonarr (TV shows)
- ❌ Lidarr (Overseerr/Ombi don't support music)

---

### 🎯 Smart Seeding Management

Intelligent seeding controls with per-tracker customization.

**Features:**

- **Ratio limits** - Stop seeding after reaching target ratio
- **Time limits** - Remove torrents after seeding duration
- **Rate limiting** - Control upload/download speeds per torrent
- **Per-tracker settings** - Different rules for different trackers
- **Dead tracker removal** - Clean up non-responsive trackers
- **Hit and Run protection** - Prevent removal until tracker seeding obligations are met

**Configuration:**

```toml
[Radarr-Movies.Torrent.SeedingMode]
# Maximum upload ratio
MaxUploadRatio = 2.0

# Maximum seeding time (seconds)
MaxSeedingTime = 2592000  # 30 days

# Removal condition
RemoveTorrent = 3  # Remove when ratio OR time met
```

**Per-tracker example:**

```toml
[[Radarr-Movies.Torrent.Trackers]]
Name = "Private Tracker"
Priority = 10
URI = "https://tracker.example.com/announce"
MaxUploadRatio = 1.5
MaxSeedingTime = 1209600  # 14 days
```

---

### 🧹 Disk Space Management

Automatically pause/resume torrents based on available disk space.

**Configuration:**

```toml
[Settings]
# Free space threshold
FreeSpace = "50G"  # Pause downloads below 50 GB free

# Directory to monitor
FreeSpaceFolder = "/path/to/downloads"

# Enable auto pause/resume
AutoPauseResume = true
```

**How it works:**

1. qBitrr monitors `FreeSpaceFolder` disk usage
2. When free space drops below `FreeSpace` threshold:
   - Pauses all downloads
   - Keeps seeding active
   - Logs warning message
3. When space frees up (files imported/deleted):
   - Resumes paused downloads
   - Continues normal operation

**Benefits:**

- Prevents "disk full" errors
- Avoids corrupted downloads
- Maintains system stability
- Automatic recovery

---

### 🔄 Auto-Updates

Automatically update qBitrr to the latest version on a schedule.

**Configuration:**

```toml
[Settings]
# Enable auto-updates
AutoUpdateEnabled = true

# Update schedule (cron expression)
AutoUpdateCron = "0 3 * * 0"  # Sundays at 3:00 AM
```

**Update process:**

1. qBitrr checks for new versions on schedule
2. Downloads latest release from GitHub
3. Installs update (PyPI package or binary)
4. Restarts qBitrr automatically
5. Logs update in `Main.log`

**Supported installation methods:**

- ✅ PyPI package (`pip install -U qbitrr2`)
- ✅ Docker (pull latest image)
- ⚠️ Binary (manual download, not fully automated)

---

### 📝 Process Management

Automatic restart of crashed worker processes with configurable limits.

**Configuration:**

```toml
[Settings]
# Enable auto-restart
AutoRestartProcesses = true

# Maximum restarts within window
MaxProcessRestarts = 5

# Restart window (seconds)
ProcessRestartWindow = 300  # 5 minutes

# Delay before restart (seconds)
ProcessRestartDelay = 5
```

**How it works:**

- Each Arr instance runs in a separate process
- If a process crashes, qBitrr automatically restarts it
- If a process crashes repeatedly (5 times in 5 minutes), auto-restart is disabled for that process
- Prevents infinite crash loops

**Monitored processes:**

- Radarr manager processes
- Sonarr manager processes
- Lidarr manager processes
- WebUI server
- Auto-update worker
- Network monitor

---

### 🌐 Web UI

Modern React-based dashboard for monitoring and management.

**Features:**

- **Real-time updates** - Live status of all torrents and Arr instances
- **Process monitoring** - View active processes and their status
- **Log viewer** - Browse and search logs from the web interface
- **Configuration editor** - Edit config.toml via web UI
- **Statistics** - Dashboard with download stats and health metrics
- **Mobile responsive** - Works on phones and tablets

**Access:**

```
http://localhost:6969/ui
```

**Configuration:**

```toml
[WebUI]
Host = "0.0.0.0"
Port = 6969

# Optional authentication token
Token = "your-secret-token"

# Theme
Theme = "Dark"  # Dark or Light

# Group Sonarr episodes by series
GroupSonarr = true

# Group Lidarr albums by artist
GroupLidarr = true
```

**Security:**

If `Token` is set, all API requests require the `Authorization: Bearer` header:

```bash
curl -H "Authorization: Bearer your-secret-token" http://localhost:6969/api/processes
```

---

### 📊 FFprobe File Validation

Verify media file integrity using FFprobe before import.

**What it checks:**

- File is playable
- Video/audio codecs are valid
- Duration is reasonable
- No corruption detected
- Streams are accessible

**Configuration:**

```toml
[Settings]
# Auto-download FFprobe binary
FFprobeAutoUpdate = true
```

**Workflow:**

1. Torrent completes download
2. qBitrr scans for media files
3. FFprobe validates each file
4. ✅ Valid files → Trigger import
5. ❌ Invalid files → Mark as failed, re-search

**Benefits:**

- Prevents importing fake/sample files
- Detects corruption early
- Saves time (no manual verification)
- Reduces manual intervention

---

### 🏷️ Tagless Operation

Manage torrents without requiring Arr instance tags (advanced).

**Configuration:**

```toml
[Settings]
# Disable tag requirement
Tagless = false  # Set to true to enable
```

**When enabled:**

- qBitrr uses categories instead of tags
- Useful for setups where Arr doesn't apply tags consistently
- May cause conflicts if multiple Arr instances use the same category

**Recommended:** Leave disabled (`false`) unless you have specific issues with tagging.

---

## Feature Comparison

| Feature | Radarr | Sonarr | Lidarr |
|---------|--------|--------|--------|
| Health Monitoring | ✅ | ✅ | ✅ |
| Instant Imports | ✅ | ✅ | ✅ |
| Automated Re-searching | ✅ | ✅ | ✅ |
| Missing Content Search | ✅ | ✅ | ✅ |
| Quality Upgrades | ✅ | ✅ | ✅ |
| Temporary Profiles | ❌ | ❌ | ✅ |
| Request Integration | ✅ | ✅ | ❌ |
| Smart Seeding | ✅ | ✅ | ✅ |
| Per-Tracker Settings | ✅ | ✅ | ✅ |
| Hit and Run Protection | ✅ | ✅ | ✅ |
| FFprobe Validation | ✅ | ✅ | ✅ |
| Search by Year | ✅ | ✅ | ❌ |
| Search Specials | ❌ | ✅ | ❌ |

---

## Getting Started with Features

1. **Start simple** - Enable basic health monitoring first
2. **Add search automation** - Configure missing content search
3. **Enable upgrades** - Turn on quality upgrade searches
4. **Tune thresholds** - Adjust ETA, stall delays, and limits based on your setup
5. **Add advanced features** - Temporary profiles, request integration, etc.

---

## Common Feature Combinations

### Media Hoarder Setup

For users who want everything, quickly:

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
SearchRequestsEvery = 180
DoUpgradeSearch = false
SearchAgainOnSearchCompletion = true

[Radarr-Movies.Torrent]
MaximumETA = 172800  # 48 hours
DoNotRemoveSlow = true
StalledDelay = 30
```

---

### Quality-Focused Setup

For users prioritizing quality over speed:

```toml
[Radarr-4K.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true
QualityUnmetSearch = true
CustomFormatUnmetSearch = true
ForceMinimumCustomFormat = true

[Radarr-4K.Torrent]
MaximumETA = -1  # No limit
DoNotRemoveSlow = true
StalledDelay = 60
```

---

### Private Tracker Setup

For users on private trackers with strict rules:

```toml
[Radarr-Private]
importMode = "Copy"  # Preserve seeding

[Radarr-Private.Torrent]
DoNotRemoveSlow = true
StalledDelay = 45
MaximumDeletablePercentage = 0.99

[Radarr-Private.Torrent.SeedingMode]
MaxUploadRatio = -1  # Never stop
MaxSeedingTime = 2592000  # 30 days minimum
RemoveTorrent = 2  # Time-based only
```

---

## Feature Documentation

Detailed guides for each feature:

- [Health Monitoring](health-monitoring.md) - Comprehensive torrent health checks
- [Instant Imports](instant-imports.md) - Fast media library updates
- [Automated Search](automated-search.md) - Missing content automation
- [Quality Upgrades](quality-upgrades.md) - Automatic quality improvements
- [Custom Formats](custom-formats.md) - Advanced quality scoring
- [Request Integration](request-integration.md) - Overseerr/Ombi integration
- [Process Management](process-management.md) - Automatic restart handling
- [Disk Space Management](disk-space.md) - Free space monitoring
- [Auto Updates](auto-updates.md) - Automatic version updates

---

## Need Help?

- [Configuration Guide](../configuration/index.md) - Learn how to configure features
- [Troubleshooting](../troubleshooting/index.md) - Common issues and solutions
- [FAQ](../faq.md) - Frequently asked questions
- [GitHub Issues](https://github.com/Drapersniper/qBitrr/issues) - Report bugs or request features

---

## Related Documentation

### Feature Guides
- [Health Monitoring](health-monitoring.md) - Comprehensive torrent health checks
- [Instant Imports](instant-imports.md) - Fast media library updates
- [Automated Search](automated-search.md) - Missing content automation
- [Quality Upgrades](quality-upgrades.md) - Automatic quality improvements
- [Custom Formats](custom-formats.md) - Advanced quality scoring
- [Request Integration](request-integration.md) - Overseerr/Ombi integration
- [Process Management](process-management.md) - Automatic restart handling
- [Disk Space Management](disk-space.md) - Free space monitoring

### Configuration
- [Arr Configuration](../configuration/arr/index.md) - Radarr/Sonarr/Lidarr setup
- [Search Configuration](../configuration/search/index.md) - Search automation settings
- [Seeding Configuration](../configuration/seeding.md) - Seeding rules and limits
- [Torrent Configuration](../configuration/torrents.md) - Torrent handling options

### Getting Started
- [Quick Start Guide](../getting-started/quickstart.md) - Set up your first feature
- [Installation](../getting-started/installation/index.md) - Install qBitrr
- [First Run](../getting-started/quickstart.md) - Initial configuration

---

## Next Steps

1. **Choose Your Features** - Review the features above and decide which ones fit your workflow
2. **Configure Settings** - Follow the [Configuration Guide](../configuration/index.md) to enable features
3. **Test & Monitor** - Use the [WebUI](../webui/index.md) to monitor feature performance
4. **Optimize** - Tune thresholds and delays based on your setup
5. **Get Support** - Check [Troubleshooting](../troubleshooting/index.md) if issues arise
