# qBitrr

[![PyPI](https://img.shields.io/pypi/v/qBitrr2?label=PyPI)](https://pypi.org/project/qBitrr2/)
[![Downloads](https://img.shields.io/pypi/dm/qBitrr2)](https://pypi.org/project/qBitrr2/)
[![Docker Pulls](https://img.shields.io/docker/pulls/feramance/qbitrr.svg)](https://hub.docker.com/r/feramance/qbitrr)
[![CodeQL](https://github.com/Feramance/qBitrr/actions/workflows/codeql.yml/badge.svg?branch=master)](https://github.com/Feramance/qBitrr/actions/workflows/codeql.yml)
[![Nightly Build](https://github.com/Feramance/qBitrr/actions/workflows/nightly.yml/badge.svg?branch=master)](https://github.com/Feramance/qBitrr/actions/workflows/nightly.yml)
[![pre-commit.ci](https://results.pre-commit.ci/badge/github/Feramance/qBitrr/master.svg)](https://results.pre-commit.ci/latest/github/Feramance/qBitrr/master)
[![License: MIT](https://img.shields.io/pypi/l/qbitrr)](LICENSE)

> 🧩 qBitrr keeps qBittorrent, Radarr, Sonarr, Lidarr, and your request tools chatting happily so downloads finish, import, and clean up without babysitting.

## 📚 What's Inside
- [Overview](#-overview)
- [Core Features](#-core-features)
- [State of the Project](#-state-of-the-project)
- [Quickstart](#-quickstart)
  - [Install with pip](#install-with-pip)
  - [Run with Docker](#run-with-docker)
  - [Native Systemd Service](#native-systemd-service)
- [Configuration](#-configuration)
- [Feature Deep Dive](#-feature-deep-dive)
  - [Torrent Health Monitoring](#-torrent-health-monitoring)
  - [Automated Search & Requests](#-automated-search--requests)
  - [Quality Management](#-quality-management)
  - [Seeding & Tracker Control](#-seeding--tracker-control)
  - [Disk Space Management](#-disk-space-management)
  - [Auto-Updates & Restarts](#-auto-updates--restarts)
- [Built-in Web UI](#-built-in-web-ui)
- [Day-to-day Operations](#-day-to-day-operations)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [Support](#-support)
- [License](#-license)

## 🧠 Overview
qBitrr is the intelligent glue between qBittorrent and the *Arr ecosystem (Radarr, Sonarr, Lidarr). It monitors torrent health, triggers instant imports when downloads complete, automates quality upgrades, manages disk space, integrates with request systems (Overseerr/Ombi), and provides a modern React dashboard for complete visibility and control.

## ✨ Core Features

### 🚑 Torrent Health & Import Management
- **Instant imports** – trigger `DownloadedMoviesScan`/`DownloadedEpisodesScan` the moment torrents finish
- **Stalled torrent detection** – identify and handle stuck/slow downloads with configurable thresholds
- **Failed download handling** – automatically blacklist failed torrents in Arr instances and trigger re-searches
- **FFprobe verification** – validate media files are playable before import (auto-downloads FFprobe binary)
- **Smart file filtering** – exclude samples, extras, trailers via regex and extension allowlists

### 🔍 Automated Search & Request Integration
- **Missing media search** – automatically search for missing movies/episodes/albums on schedules
- **Quality upgrade search** – find better releases for existing media based on quality profiles
- **Custom format scoring** – search for releases meeting minimum custom format scores
- **Overseerr/Ombi integration** – auto-pull and prioritize user requests from request management tools
- **Smart search modes** – series-level or episode-level search for TV shows based on context
- **Temporary quality profiles** – use lower quality profiles for missing items, upgrade later with flexible mapping

### 📊 Quality & Metadata Management
- **RSS sync automation** – schedule periodic RSS feed refreshes across all Arr instances
- **Queue management** – auto-refresh download queues to keep Arr instances in sync
- **Custom format enforcement** – automatically remove torrents not meeting minimum CF scores
- **Quality profile switching** – dynamically change profiles for missing vs. upgrade searches with per-profile mapping
- **Interactive profile configuration** – test Arr connections and select quality profiles from dropdowns in WebUI
- **Auto-reset profiles** – force reset temp profiles on startup or after configurable timeouts
- **Year-based search ordering** – prioritize searches by release date (newest first or reverse)

### 🌱 Seeding & Tracker Control
- **Per-tracker settings** – configure MaxETA, ratios, seeding time per tracker
- **Global seeding limits** – set upload/download rate limits, max ratios, and seeding times
- **Automatic removal** – remove torrents based on ratio, time, or both
- **Dead tracker cleanup** – auto-remove trackers with specific error messages
- **Tracker injection** – add missing trackers or remove existing ones per torrent
- **Super seed mode** – enable super seeding for specific trackers
- **Tag management** – auto-tag torrents by tracker or custom rules

### 💾 Disk Space & Resource Management
- **Free space monitoring** – pause all torrents when disk space falls below threshold
- **Auto pause/resume** – intelligently manage torrent activity based on disk availability
- **Configurable thresholds** – set limits in KB, MB, GB, or TB
- **Path-specific monitoring** – watch specific directories for space issues

### 🔄 Auto-Updates & Self-Healing
- **GitHub release-based updates** – automatically checks for published (non-draft) releases via GitHub API
- **Scheduled auto-updates** – update qBitrr on a cron schedule (default: weekly Sunday 3 AM)
- **Manual update trigger** – one-click updates from WebUI
- **Installation-aware updates** – detects git/pip/binary installs and uses appropriate update method
- **Version verification** – confirms installed version matches target before restart
- **Smart restart mechanism** – uses `os.execv()` for true in-place restarts (no supervisor needed)
- **Cross-platform compatibility** – works in Docker, systemd, native installs, Windows, Linux, macOS
- **Graceful shutdown** – cleanly closes databases, flushes logs, terminates child processes
- **Process auto-restart** – automatically restarts crashed Arr manager processes with crash loop protection
- **Crash loop detection** – prevents infinite restart loops with configurable max restart limits and time windows
- **Configurable restart behavior** – control restart delays, maximum attempts, and monitoring windows via WebUI

### 💻 First-Party Web UI
- **Live process monitoring** – see all running Arr managers and their current activity
- **Log viewer** – tail logs in real-time with filtering and search
- **Arr insights** – view movies, series, albums with filtering by year, quality, status, and quality profiles
- **Config editor** – edit configuration directly from the UI with validation and helpful tooltips
- **Test connections** – validate Arr credentials and load quality profiles with one click
- **Restart controls** – restart individual processes or the entire application
- **Dark/light theme** – customizable UI appearance
- **Token authentication** – optional API protection with bearer tokens

## 📌 State of the Project
The long-term plan is still to ship a C# rewrite, but the Python edition isn't going anywhere—it gets regular fixes and features, and the Web UI is now production-ready. Ideas and PRs are welcome! Head over to the [issue templates](.github/ISSUE_TEMPLATE) or the [PR checklist](.github/pull_request_template.md) to get started.



## ⚡ Quickstart
qBitrr supports Python 3.12+ on Linux, macOS, and Windows. Run it natively or in Docker—whatever fits your stack.

### 🐍 Install with pip
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install qBitrr2

# First run creates ~/config/config.toml
qBitrr2
```

**Update later:**
```bash
python -m pip install --upgrade qBitrr2
```

**Or enable auto-updates** in `config.toml`:
```toml
[Settings]
AutoUpdateEnabled = true
AutoUpdateCron = "0 3 * * 0"  # Weekly on Sunday at 3 AM
```

> 📝 **Note:** Auto-updates check GitHub releases for new versions. Only published (non-draft) releases trigger updates. Binary installations receive update notifications but require manual download.

### 🐳 Run with Docker
**Minimal setup:**
```bash
docker run -d \
  --name qbitrr \
  --tty \
  -e TZ=Europe/London \
  -p 6969:6969 \
  -v /etc/localtime:/etc/localtime:ro \
  -v /path/to/appdata/qbitrr:/config \
  -v /path/to/completed/downloads:/completed_downloads:rw \
  --restart unless-stopped \
  feramance/qbitrr:latest
```

The container automatically binds its WebUI to `0.0.0.0`; exposing `6969` makes the dashboard reachable at `http://<host>:6969/ui`.

**Docker Compose example:**
```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    user: 1000:1000
    restart: unless-stopped
    tty: true
    environment:
      TZ: Europe/London
    ports:
      - "6969:6969"
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - /path/to/appdata/qbitrr:/config
      - /path/to/completed/downloads:/completed_downloads:rw
    logging:
      driver: json-file
      options:
        max-size: 50m
        max-file: "3"
    depends_on:
      - qbittorrent
      - radarr
      - sonarr
```

> ℹ️ On first boot the container writes `config.toml` under `/config`. Update the values to match your mounts and restart the container.

### ⚙️ Native Systemd Service
For Linux users running qBitrr natively (non-Docker), you can set up automatic startup and restart management using systemd.

**Quick setup:**
```bash
# Install qBitrr
pip install qBitrr2

# Copy systemd service file
sudo cp qbitrr.service /etc/systemd/system/qbitrr.service

# Enable and start
sudo systemctl enable qbitrr
sudo systemctl start qbitrr

# Check status
sudo systemctl status qbitrr
```

**Benefits:**
- ✅ Auto-start on boot
- ✅ Automatic restarts after crashes or updates
- ✅ Integrated logging with `journalctl`
- ✅ Resource limits and security hardening
- ✅ Works seamlessly with qBitrr's auto-update feature

**See the full guide:** [SYSTEMD_SERVICE.md](SYSTEMD_SERVICE.md) for detailed setup instructions, troubleshooting, and security hardening options.

## 🛠️ Configuration

### 📂 Config Location
- **Native install:** `~/config/config.toml`
- **Docker:** `/config/config.toml`
- **First run:** Auto-generates a template config file
- **Manual generation:** `qbitrr --gen-config`

### 🔧 Essential Setup
1. **Configure qBittorrent connection** in `[qBit]` section:
   - Set `Host`, `Port`, `UserName`, `Password`
   - qBittorrent 5.x requires `Version5 = true` (4.6.7 is the latest validated 4.x build)

2. **Configure Arr instances** (Radarr/Sonarr/Lidarr):
   - Each instance needs: `URI`, `APIKey`, `Category`
   - **Naming format:** Instance names must follow pattern `(Radarr|Sonarr|Lidarr)-<name>` (e.g., `Radarr-Movies`, `Sonarr-TV4K`)
   - **Important:** Use matching categories in Arr's download client settings
   - **Tagging:** Ensure Arr instances tag their downloads so qBitrr can track them

3. **Set completed download folder:**
   ```toml
   [Settings]
   CompletedDownloadFolder = "/path/to/completed"
   ```

4. **Enable logging** for troubleshooting:
   ```toml
   [Settings]
   Logging = true
   ConsoleLevel = "INFO"  # or DEBUG for verbose output
   ```

### 📖 Configuration Reference
See [`config.example.toml`](config.example.toml) for comprehensive documentation of all settings, including:
- Torrent health check thresholds
- Search automation options
- Seeding limits and tracker rules
- Request system integration
- WebUI settings
- File filtering and exclusion rules

## 🎯 Feature Deep Dive

### 🚑 Torrent Health Monitoring

qBitrr continuously monitors your torrents and takes intelligent action when problems arise.

**Stalled Torrent Detection:**
```toml
[Radarr-Movies.Torrent]
StalledDelay = 15              # Minutes before considering a torrent stalled
ReSearchStalled = true         # Re-search before removing stalled torrents
MaximumETA = 604800           # Max ETA in seconds (7 days)
IgnoreTorrentsYoungerThan = 600  # Grace period for new torrents (10 min)
```

**Automatic Blacklisting:**
When torrents fail or stall beyond thresholds, qBitrr:
1. ✅ Marks the release as failed in the Arr instance
2. ✅ Blacklists the release to prevent re-download
3. ✅ Optionally triggers an automatic re-search
4. ✅ Removes the failed torrent from qBittorrent

**Smart Completion Rules:**
```toml
[Radarr-Movies.Torrent]
MaximumDeletablePercentage = 0.99  # Don't delete torrents >99% complete
DoNotRemoveSlow = true             # Protect slow but active torrents
```

**File Verification:**
```toml
[Settings]
FFprobeAutoUpdate = true  # Auto-download FFprobe binary
```
- Validates media files are playable before import
- Detects corrupted or fake files
- Prevents broken media from being imported into Arr

**Error Code Handling:**
```toml
[Radarr-Movies]
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing movie file(s)",
  "Unable to determine if file is a sample"
]
```
Automatically handle specific Arr error messages by removing failed files and triggering re-searches.

---

### 🔍 Automated Search & Requests

**Missing Media Search:**
```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true              # Enable automated searching
SearchLimit = 5                   # Max concurrent searches
SearchByYear = true               # Order by release year
SearchInReverse = false           # Newest first (true = oldest first)
SearchRequestsEvery = 300         # Delay between searches (seconds)
SearchAgainOnSearchCompletion = true  # Loop continuously
```

**Quality Upgrade Search:**
```toml
[Radarr-Movies.EntrySearch]
DoUpgradeSearch = true            # Search for better quality versions
QualityUnmetSearch = true         # Search for unmet quality profiles
CustomFormatUnmetSearch = true    # Search for better custom format scores
ForceMinimumCustomFormat = true   # Auto-remove torrents below CF threshold
```

**Overseerr Integration:**
```toml
[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://overseerr:5055"
OverseerrAPIKey = "your-api-key"
ApprovedOnly = true               # Only process approved requests
Is4K = false                      # Set true for 4K Arr instances
```

**Ombi Integration:**
```toml
[Radarr-Movies.EntrySearch.Ombi]
SearchOmbiRequests = true
OmbiURI = "http://ombi:3579"
OmbiAPIKey = "your-api-key"
ApprovedOnly = true
```

**Smart Search Modes (Sonarr):**
```toml
[Sonarr-TV.EntrySearch]
SearchBySeries = "smart"          # auto | true (series) | false (episode)
# smart: Series search for full seasons, episode search for singles
PrioritizeTodaysReleases = true   # Search today's episodes first (RSS-like)
AlsoSearchSpecials = false        # Include season 00 episodes
Unmonitored = false               # Include unmonitored items
```

**Temporary Quality Profiles:**
```toml
[Radarr-Movies.EntrySearch]
UseTempForMissing = true
KeepTempProfile = false

# New: Map each main profile to a temp profile
QualityProfileMappings = { "Ultra-HD" = "Web-DL", "HD-1080p" = "HDTV-720p" }

# Auto-reset options
ForceResetTempProfiles = false           # Reset all on startup
TempProfileResetTimeoutMinutes = 0       # Auto-reset after timeout (0 = disabled)
ProfileSwitchRetryAttempts = 3           # Retry failed profile switches

# Searches missing items with temp profile, switches back after import
```

**Configure via WebUI:**
1. Edit your Arr instance in the Config tab
2. Click "Test Connection" to load available quality profiles
3. Add profile mappings with the interactive UI (no JSON editing needed!)
4. Select main and temp profiles from dropdowns
5. Save and restart

---

### 📊 Quality Management

**RSS Sync Automation:**
```toml
[Radarr-Movies]
RssSyncTimer = 5  # Minutes between RSS feed refreshes (0 = disabled)
```
Keeps Arr instances checking indexers for new releases regularly.

**Queue Refresh:**
```toml
[Radarr-Movies]
RefreshDownloadsTimer = 5  # Minutes between queue updates (0 = disabled)
```
Ensures Arr instances stay in sync with qBittorrent's download state.

**Import Mode:**
```toml
[Radarr-Movies]
importMode = "Auto"  # Auto | Move | Copy
```
- **Auto:** Let Arr decide based on its settings
- **Move:** Move files from download folder to library
- **Copy:** Copy files (preserves seeding torrents)

**Custom Format Score Enforcement:**
When `ForceMinimumCustomFormat = true`, qBitrr automatically removes torrents that don't meet the minimum custom format score defined in your Arr quality profile.

---

### 🌱 Seeding & Tracker Control

**Global Seeding Limits:**
```toml
[Radarr-Movies.Torrent.SeedingMode]
DownloadRateLimitPerTorrent = -1  # -1 = unlimited, or KB/s
UploadRateLimitPerTorrent = -1    # -1 = unlimited, or KB/s
MaxUploadRatio = 2.0              # Stop seeding at 2.0 ratio
MaxSeedingTime = 604800           # Stop after 7 days (seconds)
RemoveTorrent = 3                 # 1=ratio, 2=time, 3=either, 4=both, -1=never
```

**Per-Tracker Settings:**
```toml
[[Radarr-Movies.Torrent.Trackers]]
Name = "MyTracker"
Priority = 10                     # Higher = processed first
URI = "https://tracker.example/announce"
MaximumETA = 18000               # Override global MaxETA for this tracker
DownloadRateLimit = 5000         # KB/s limit for this tracker
UploadRateLimit = 1000           # KB/s limit for this tracker
MaxUploadRatio = 1.5             # Tracker-specific ratio limit
MaxSeedingTime = 86400           # Tracker-specific time limit (1 day)
AddTrackerIfMissing = true       # Inject this tracker into matching torrents
RemoveIfExists = false           # Remove this tracker if found
SuperSeedMode = true             # Enable super seeding for this tracker
AddTags = ["private", "MyTracker"]  # Auto-tag matching torrents
```

**Tracker Cleanup:**
```toml
[Radarr-Movies.Torrent.SeedingMode]
RemoveDeadTrackers = true
RemoveTrackerWithMessage = [
  "skipping tracker announce (unreachable)",
  "No such host is known",
  "unsupported URL protocol"
]
```

**File Filtering:**
```toml
[Radarr-Movies.Torrent]
CaseSensitiveMatches = false
FolderExclusionRegex = ["\\bextras?\\b", "\\bsamples?\\b", "\\bfeaturettes?\\b"]
FileNameExclusionRegex = ["\\bsample\\b", "\\btrailer\\b"]
FileExtensionAllowlist = [".mp4", ".mkv", ".avi", ".sub", ".srt"]
AutoDelete = false  # Auto-delete non-playable files (.exe, .png, etc.)
```

---

### 💾 Disk Space Management

**Free Space Monitoring:**
```toml
[Settings]
FreeSpace = "50G"              # Pause when <50GB free (K/M/G/T units)
FreeSpaceFolder = "/downloads" # Path to monitor
AutoPauseResume = true         # Required for FreeSpace to work
```

**How it works:**
1. 📊 Continuously monitors specified folder
2. ⏸️ Pauses **all** torrents when space falls below threshold
3. ▶️ Auto-resumes when space is reclaimed
4. 🔔 Logs warnings when approaching limit

**Disable monitoring:**
```toml
[Settings]
FreeSpace = ""  # Empty string or 0 disables monitoring
```

---

### 🔄 Auto-Updates & Restarts

qBitrr can automatically update itself by checking GitHub releases for new versions. The update behavior varies by installation type.

#### 🔍 How Updates Work

**Update Detection:**
1. 📡 Queries GitHub API for latest **published** (non-draft) release
2. 🔢 Compares release version with current version using semantic versioning
3. ⏩ Skips prereleases (beta, rc, alpha) by default
4. 📦 Only updates when a newer **stable** version is available

**Installation Types:**

| Type | Detection | Update Method | Version Control |
|------|-----------|---------------|-----------------|
| **Git** | `.git` directory exists | `git checkout <tag>` or `git pull` | Checks out specific release tag |
| **PyPI** | Installed via pip | `pip install qBitrr2==<version>` | Installs exact version from PyPI |
| **Binary** | PyInstaller executable | Notification only | Logs download URL for manual update |

**Why different methods?**
- **Git installations** can checkout specific tags for precise version control
- **PyPI installations** can pin to exact versions for reliability
- **Binary installations** cannot self-update (would require replacing running executable), so qBitrr logs the download URL and version info for manual update

---

#### ⚙️ Configuration

**Basic Setup:**
```toml
[Settings]
AutoUpdateEnabled = true
AutoUpdateCron = "0 3 * * 0"  # Cron expression (default: Sunday 3 AM)
```

**Cron Expression Examples:**
```bash
0 3 * * 0      # Every Sunday at 3:00 AM
0 */6 * * *    # Every 6 hours
0 0 * * *      # Daily at midnight
0 2 * * 1-5    # Weekdays at 2:00 AM
```

---

#### 📋 Update Process Flow

**For Git & PyPI Installations:**

1. **Check Phase:**
   - Fetch latest release from GitHub API
   - Validate release is not draft or prerelease
   - Compare versions (semantic versioning)
   - Skip if already on latest version

2. **Download Phase:**
   - **Git:** `git fetch --tags && git checkout v<version>`
   - **PyPI:** `pip install --upgrade qBitrr2==<version>`

3. **Verification Phase:**
   - Reload version information
   - Verify installed version matches target
   - Log warning if mismatch

4. **Restart Phase:**
   - Gracefully shutdown (close DBs, flush logs)
   - Terminate child processes
   - Execute in-place restart via `os.execv()`
   - Maintain same PID (systemd-friendly)

**For Binary Installations:**

1. **Check Phase:** Same as above
2. **Notification:** Logs message with download URL and instructions
3. **Manual Update:** User downloads new binary from GitHub releases
4. **No Auto-Restart:** User manually restarts after replacing binary

Example binary update log:
```
[INFO] Update available: v5.4.2 -> v5.4.3
[INFO] Binary installation detected - manual update required
[INFO] Download: https://github.com/Feramance/qBitrr/releases/latest
[INFO] Instructions:
  1. Download the binary for your platform
  2. Extract the archive
  3. Replace current executable with new binary
  4. Restart qBitrr
```

---

#### 🔧 Manual Updates

**Via WebUI:**
- Navigate to **Config tab**
- Click **"Check for Updates"** to see available version
- Click **"Update Now"** button
- Confirm when prompted
- Application restarts automatically (git/pip only)

**Via Command Line:**

```bash
# Git installation
cd /path/to/qBitrr
git fetch --tags
git checkout v5.4.3  # or: git pull
qbitrr  # restart

# PyPI installation
pip install --upgrade qBitrr2
# or: pip install qBitrr2==5.4.3  # specific version
qbitrr  # restart

# Binary installation
# Download from: https://github.com/Feramance/qBitrr/releases/latest
# Extract and replace binary, then restart

# Docker installation
docker pull feramance/qbitrr:latest
docker restart qbitrr
# or: docker-compose pull && docker-compose up -d
```

---

#### 🔐 Security & Reliability

**GitHub API Dependency:**
- Auto-update requires GitHub API access
- Rate limit: 60 requests/hour (unauthenticated)
- Cron schedule should account for rate limits
- Failures are logged but don't crash the application

**Version Verification:**
- After update, qBitrr verifies installed version
- Helps catch failed updates or PyPI lag issues
- Logs warning if version mismatch detected

**Draft & Prerelease Handling:**
- Draft releases are **always skipped** (unpublished)
- Prereleases (beta/rc/alpha) are skipped by default
- Useful for testing but not recommended for production

**Rollback:**
- Git installations: `git checkout <previous-tag>`
- PyPI installations: `pip install qBitrr2==<previous-version>`
- Binary installations: Keep backup of previous binary
- No automatic rollback (manual intervention required)

---

#### 🚀 Restart Mechanism

**How it Works:**
```python
os.execv(sys.executable, [sys.executable] + sys.argv)
```

**Benefits:**
- ✅ **Same PID** – systemd doesn't detect a restart
- ✅ **No supervisor** – doesn't require external process manager
- ✅ **Clean state** – fresh Python interpreter, no memory leaks
- ✅ **Fast** – near-instant restart (< 1 second)

**Supported Environments:**
- 🐳 **Docker** – container stays running, process restarts
- ⚙️ **systemd** – service remains "active", no restart count increment
- 💻 **Native** – works on Linux, macOS, Windows
- 🪟 **Windows** – handles different executable extensions (.exe, .cmd)

**Graceful Shutdown:**
1. Stop all Arr manager child processes
2. Close database connections
3. Flush log buffers to disk
4. Release file locks
5. Execute in-place restart

---

#### 🛠️ Restart via API

**Restart entire application:**
```bash
curl -X POST http://localhost:6969/api/restart

# With authentication
curl -X POST http://localhost:6969/api/restart \
  -H "Authorization: Bearer your-token"
```

**Restart specific Arr manager:**
```bash
curl -X POST http://localhost:6969/api/arr/radarr-movies/restart
```

---

#### ⚠️ Troubleshooting Updates

**Update not triggering:**
- ✅ Check `AutoUpdateEnabled = true` in config
- ✅ Verify cron expression is valid (use [crontab.guru](https://crontab.guru))
- ✅ Check `Main.log` for GitHub API errors
- ✅ Ensure internet connectivity to api.github.com
- ✅ Check if already on latest version

**Version mismatch after update:**
- ✅ Review logs for pip/git errors
- ✅ Manually verify installation: `pip show qBitrr2` or `git describe`
- ✅ Check if PyPI is behind GitHub releases (can take hours)
- ✅ Try manual update to force correct version

**Binary updates not working:**
- ℹ️ **Expected behavior** – binaries cannot auto-update
- ✅ Check logs for download URL
- ✅ Download matching binary for your platform
- ✅ Extract and replace current executable
- ✅ Ensure new binary has execute permissions (Unix)

**Restart fails:**
- ✅ Check file permissions on qBitrr installation
- ✅ Review systemd journal if using systemd
- ✅ Verify no file locks preventing restart
- ✅ Check disk space for logs and databases
- ✅ Manual restart: Stop service, start again

**For systemd users:** See [SYSTEMD_SERVICE.md](SYSTEMD_SERVICE.md) for automatic restart configuration with `Restart=always`.

---

curl -X POST http://localhost:6969/api/arr/radarr-movies/restart
```

**For systemd users:** See [SYSTEMD_SERVICE.md](SYSTEMD_SERVICE.md) for automatic restart configuration.

---

### 🔁 Process Auto-Restart & Crash Loop Protection

Your Arr manager processes (Radarr/Sonarr/Lidarr) automatically restart if they crash, preventing downtime. Built-in protection stops restart loops if a process keeps failing.

#### ⚙️ Configuration

**Basic Setup:**
```toml
[Settings]
AutoRestartProcesses = true        # Enable automatic restart
MaxProcessRestarts = 5              # Stop trying after 5 crashes
ProcessRestartWindow = 300          # Within 5 minutes
ProcessRestartDelay = 5             # Wait 5 seconds before restarting
```

**What this means:**
- If a process crashes fewer than 5 times in 5 minutes, it auto-restarts
- If it crashes 5+ times in 5 minutes, qBitrr stops trying and logs an error
- After the 5-minute window passes, the counter resets and auto-restart resumes

**Configure via WebUI:**
1. Navigate to **Config** tab
2. Find the **Process Management** section
3. Adjust restart behavior to your preference
4. Save and restart qBitrr

#### 📊 Monitoring

**Via WebUI:**
- **Processes tab** shows all running managers with restart history
- Manually restart individual processes if needed

**Via Logs:**
```bash
# See restart activity
tail -f ~/logs/Main.log | grep restart        # Native
docker logs -f qbitrr | grep restart          # Docker
sudo journalctl -u qbitrr -f | grep restart   # Systemd
```

#### 🆕 First-Time Setup

Existing configs automatically upgrade to version 3 on first startup. A timestamped backup is created before any changes. No manual action needed!

---

## 🖥️ Built-in Web UI
The React + Vite dashboard provides complete visibility and control over your qBitrr instance.

### 🌐 Access & Authentication
- **Default URL:** `http://<host>:6969/ui`
- **Custom host/port:** Configure in `config.toml`:
  ```toml
  [WebUI]
  Host = "0.0.0.0"  # Bind address (0.0.0.0 for all interfaces)
  Port = 6969       # Web server port
  ```
- **Authentication:** Protect API endpoints with bearer token:
  ```toml
  [WebUI]
  Token = "your-secret-token"
  ```
  When set, all `/api/*` endpoints require `Authorization: Bearer <token>` header.
  The UI itself uses unauthenticated `/web/*` endpoints.

### 🗂️ Dashboard Tabs

**📊 Processes Tab:**
- View all running Arr manager processes
- See current activity and search status
- Monitor queue counts and metrics
- Restart individual processes or all at once

**📝 Logs Tab:**
- Real-time log viewer with filtering
- View `Main.log`, `WebUI.log`, and per-Arr logs
- Search and navigate large log files
- Download logs for troubleshooting

**🎬 Radarr/Sonarr/Lidarr Tabs:**
- Browse your media library with advanced filtering
- Filter by year range, quality status, monitored state
- See custom format scores and upgrade availability
- Identify missing media and quality issues
- View request status for Overseerr/Ombi items

**⚙️ Config Tab:**
- Edit configuration directly in the UI
- Trigger manual updates
- View version and changelog
- Rebuild Arr metadata
- Restart application

### 🎨 Customization
```toml
[WebUI]
Theme = "dark"          # or "light"
LiveArr = true          # Enable live updates for Arr views
GroupSonarr = true      # Group episodes by series
GroupLidarr = true      # Group albums by artist
```

### 🧪 Development
The WebUI source lives in `webui/`:
```bash
cd webui
npm ci                  # Install dependencies
npm run dev             # Dev server with HMR at localhost:5173
npm run lint            # ESLint check
npm run build           # Build for production
```
Build outputs to `webui/dist/`, which gets bundled into `qBitrr/static/`.

**API Documentation:** See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for complete API reference.

---

## 🔁 Day-to-day Operations

### 🔄 Restart & Rebuild
- **Restart application:** WebUI → Config tab → "Restart All" button
- **Restart individual Arr manager:** WebUI → Processes tab → Click restart icon
- **Rebuild Arr metadata:** WebUI → Config tab → "Rebuild Arrs" button
- **API endpoints:**
  ```bash
  POST /api/restart                    # Restart qBitrr
  POST /api/arr/<category>/restart     # Restart specific manager
  POST /api/arr/rebuild                # Rebuild all Arr caches
  ```

### 📋 Monitoring
- **Logs location:** `~/logs/` (native) or `/config/logs` (Docker)
- **Log files:**
  - `Main.log` – Main application logs
  - `WebUI.log` – Web interface logs
  - `<CategoryName>.log` – Per-Arr instance logs
- **View in UI:** WebUI → Logs tab → Select log file
- **View in terminal:**
  ```bash
  # Native
  tail -f ~/logs/Main.log

  # Docker
  docker logs -f qbitrr
  docker exec qbitrr tail -f /config/logs/Main.log

  # Systemd
  sudo journalctl -u qbitrr -f
  ```

### 🔍 Request Integration
Once configured, qBitrr automatically:
1. 📥 Polls Overseerr/Ombi for new requests
2. 🔍 Searches requested items in Arr instances
3. ⭐ Prioritizes requests over general missing media searches
4. 📊 Identifies requests in WebUI Arr tabs with `isRequest` flag

### 🛠️ Special Categories
qBitrr monitors special qBittorrent categories for manual intervention:

**Failed Category:**
```toml
[Settings]
FailedCategory = "failed"
```
Manually move torrents here to mark them as failed and trigger blacklisting + re-search.

**Recheck Category:**
```toml
[Settings]
RecheckCategory = "recheck"
```
Manually move torrents here to trigger a proper recheck operation.

### 🏷️ Tagless Operation
```toml
[Settings]
Tagless = true
```
Disables qBitrr from tagging torrents in qBittorrent. Use this if you prefer to manage qBittorrent tags manually or avoid tag clutter.

---

## 🆘 Troubleshooting

### 🐛 Common Issues

**Torrents not being processed:**
1. ✅ Verify Arr instance is using the correct **category** in download client settings
2. ✅ Ensure Arr instance **tags** match qBitrr's category configuration
3. ✅ Check `IgnoreTorrentsYoungerThan` – new torrents have a grace period
4. ✅ Enable debug logging: `ConsoleLevel = "DEBUG"`
5. ✅ Check category-specific log file in `~/logs/` or `/config/logs/`

**Imports not triggering:**
1. ✅ Verify `CompletedDownloadFolder` path is correct and accessible
2. ✅ Check file extensions against `FileExtensionAllowlist`
3. ✅ Review `FolderExclusionRegex` and `FileNameExclusionRegex` for over-matching
4. ✅ Enable FFprobe logging to see media validation results
5. ✅ Check Arr instance has proper path mappings (especially in Docker)

**Search not finding releases:**
1. ✅ Verify `SearchMissing = true` in the EntrySearch section
2. ✅ Check `SearchLimit` isn't too low for your queue
3. ✅ Review `SearchByYear` and `SearchInReverse` settings
4. ✅ Ensure Arr instance has indexers configured and working
5. ✅ Check for rate limiting in Arr instance logs

**High CPU/memory usage:**
1. ✅ Reduce `SearchLimit` to lower concurrent searches
2. ✅ Increase `LoopSleepTimer` to slow down processing
3. ✅ Disable `DoUpgradeSearch` if not needed
4. ✅ Set `LiveArr = false` in WebUI config to reduce refresh overhead

**Docker path issues:**
1. ✅ Ensure volume mounts match between qBittorrent, Arr, and qBitrr
2. ✅ Use consistent paths across all containers
3. ✅ Example: All containers should see `/downloads` as the same physical path

**Updates failing:**
1. ✅ Check internet connectivity
2. ✅ Verify pip/Python installation is writable
3. ✅ Review update logs in `Main.log` or `WebUI.log`
4. ✅ Manual update: `pip install --upgrade qBitrr2` (native) or pull new Docker image

### 📊 Enable Debug Logging
```toml
[Settings]
Logging = true
ConsoleLevel = "DEBUG"  # TRACE for even more detail
```
Logs output to:
- **Native:** `~/logs/`
- **Docker:** `/config/logs/`
- **Systemd:** `sudo journalctl -u qbitrr -n 100`

### 🐞 Reporting Issues
When reporting bugs:

1. **Enable file logging** and reproduce the issue
2. **Collect information:**
   - qBitrr version: `qBitrr2 --version` or Docker tag
   - OS and deployment method (Docker/native/systemd)
   - qBittorrent version and API version (4.x vs 5.x)
   - Arr instance versions (Radarr/Sonarr/Lidarr)
   - Request tool versions (Overseerr/Ombi) if applicable
3. **Grab relevant log snippets** (scrub API keys and tokens!)
4. **Open an issue** using the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml)
5. **Include:**
   - Clear reproduction steps
   - Expected vs. actual behavior
   - Relevant config sections (with secrets removed)
   - Error messages and stack traces

### 💡 Feature Requests
Have an idea? Submit it via the [feature request template](.github/ISSUE_TEMPLATE/feature_request.yml)!

### 📚 Additional Resources
- **API Documentation:** [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Systemd Setup:** [SYSTEMD_SERVICE.md](SYSTEMD_SERVICE.md)
- **Example Config:** [config.example.toml](config.example.toml)
- **GitHub Issues:** [Search existing issues](https://github.com/Feramance/qBitrr/issues)

---

## 🤝 Contributing

We welcome contributions from the community! Whether it's code, documentation, bug reports, or feature ideas, your help makes qBitrr better.

### 🔧 Development Setup

**Python Backend:**
```bash
# Clone the repo
git clone https://github.com/Feramance/qBitrr.git
cd qBitrr

# Create virtual environment
make newenv
# or: python -m venv .venv && source .venv/bin/activate

# Install dependencies
make syncenv
# or: pip install -e .[all]

# Run linting and formatting
make reformat
# or: pre-commit run --all-files
```

**TypeScript/React WebUI:**
```bash
cd webui
npm ci                    # Install exact versions from package-lock.json
npm run dev               # Dev server at localhost:5173
npm run lint              # ESLint check
npm run build             # Build for production
```

### 📝 Before Submitting a PR

1. ✅ Read the [pull request template](.github/pull_request_template.md)
2. ✅ **Format code:**
   - Python: `make reformat` or `pre-commit run --all-files`
   - TypeScript: `npm run lint` in `webui/`
3. ✅ **Test your changes:**
   - Run against live qBittorrent + Arr instances
   - Test in both Docker and native environments if possible
4. ✅ **Update documentation:**
   - Add/update relevant sections in README.md
   - Update `config.example.toml` if adding config options
   - Document API changes in `API_DOCUMENTATION.md`
5. ✅ **Clean commit history:**
   - Use descriptive commit messages
   - Follow [conventional commits](https://www.conventionalcommits.org/) format
   - Squash WIP commits before submitting

### 💡 Contribution Ideas

- 🐛 **Bug fixes** – check [open issues](https://github.com/Feramance/qBitrr/issues)
- ✨ **Features** – see [feature requests](https://github.com/Feramance/qBitrr/labels/enhancement)
- 📚 **Documentation** – improve guides, add examples, fix typos
- 🌍 **Translations** – help internationalize the WebUI
- 🧪 **Testing** – add test coverage, validate edge cases

**Unsure if an idea fits?** Open a [feature request](.github/ISSUE_TEMPLATE/feature_request.yml) first and let's discuss!

### 📜 Code Guidelines

See [CONTRIBUTION.md](CONTRIBUTION.md) for comprehensive coding standards and architecture details.

**Quick summary:**
- **Python:** Black formatting (99 chars), type hints required, PEP 8 naming
- **TypeScript:** ESLint strict mode, explicit types, functional components only
- **Commits:** LF line endings, no trailing whitespace, EOF newline required
- **Errors:** Inherit from `qBitManagerError`, provide actionable messages

---

## ❤️ Support

### 🌟 Show Your Support
- ⭐ **Star the repo** – helps others discover qBitrr
- 🐛 **Report bugs** – attach logs so we can fix issues faster
- 💬 **Share feedback** – tell us what works and what doesn't
- 🛠️ **Contribute** – code, docs, translations, or just good vibes

### 💰 Sponsor Development
If qBitrr saves you time and headaches, consider supporting its development:

- 🎨 [Patreon](https://patreon.com/qBitrr) – monthly support
- 💸 [PayPal](https://www.paypal.me/feramance) – one-time donations

Your support keeps qBitrr maintained, updated, and improving. Thank you! 🙏

---

## 📄 License

qBitrr is released under the [MIT License](LICENSE).

**TL;DR:** Use it, modify it, share it—commercially or personally. Just keep the copyright notice and don't blame us if things break. 😊

---

## 🔗 Quick Links

- 📦 [PyPI Package](https://pypi.org/project/qBitrr2/)
- 🐳 [Docker Hub](https://hub.docker.com/r/feramance/qbitrr)
- 📚 [API Documentation](API_DOCUMENTATION.md)
- ⚙️ [Systemd Setup Guide](SYSTEMD_SERVICE.md)
- 📝 [Example Configuration](config.example.toml)
- 🐛 [Report a Bug](.github/ISSUE_TEMPLATE/bug_report.yml)
- ✨ [Request a Feature](.github/ISSUE_TEMPLATE/feature_request.yml)
- 💬 [Discussions](https://github.com/Feramance/qBitrr/discussions)

---

<div align="center">

**Made with ❤️ by the qBitrr community**

</div>
