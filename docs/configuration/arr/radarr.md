# Radarr Configuration

This guide covers how to configure Radarr instances in qBitrr for movie management, automated searching, and quality upgrades.

---

## Quick Start

Every Radarr instance in qBitrr requires a dedicated section in your `config.toml` file. The section name must follow the pattern `Radarr-<name>`.

### Basic Configuration

```toml
[Radarr-Movies]
# Toggle whether to manage this Radarr instance
Managed = true

# The URL used to access Radarr (e.g., http://ip:port)
URI = "http://localhost:7878"

# Radarr API Key (Settings > General > Security)
APIKey = "your-radarr-api-key"

# Category applied by Radarr to torrents in qBittorrent
# MUST match: Radarr > Settings > Download Clients > qBittorrent > Category
Category = "radarr-movies"

# Toggle whether to re-search failed torrents
ReSearch = true

# Import mode (Auto, Move, or Copy)
importMode = "Auto"

# RSS sync timer in minutes (0 = disabled)
RssSyncTimer = 1

# Refresh downloads timer in minutes (0 = disabled)
RefreshDownloadsTimer = 1

# Error messages to automatically blacklist
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing movie file(s)",
  "Not a preferred word upgrade for existing movie file(s)",
  "Unable to determine if file is a sample"
]
```

---

## Connection Settings

### Finding Your Radarr Details

1. **URI**: Open Radarr in your browser and copy the URL (e.g., `http://192.168.1.100:7878`)
2. **APIKey**: In Radarr, go to **Settings** → **General** → **Security** → Copy the **API Key**
3. **Category**: Go to **Settings** → **Download Clients** → Click your qBittorrent client → Note the **Category** field

!!! warning "Category Mismatch"
    The `Category` value in qBitrr **must exactly match** the category configured in Radarr's qBittorrent download client settings. If they don't match, qBitrr won't process your Radarr torrents.

---

### Multiple Radarr Instances

You can configure multiple Radarr instances (e.g., separate instances for 1080p and 4K movies):

```toml
[Radarr-1080p]
URI = "http://localhost:7878"
APIKey = "api-key-1"
Category = "radarr-1080p"
# ... other settings

[Radarr-4K]
URI = "http://localhost:7879"
APIKey = "api-key-2"
Category = "radarr-4k"
# ... other settings
```

!!! tip "Naming Convention"
    Instance names must start with `Radarr-` followed by any descriptive name. Examples:

    - ✅ `Radarr-Movies`
    - ✅ `Radarr-1080p`
    - ✅ `Radarr-4K`
    - ❌ `Movies` (missing prefix)
    - ❌ `radarr-movies` (lowercase)

---

## Basic Settings

### Managed

```toml
Managed = true  # Enable management for this Radarr instance
```

When `Managed = false`, qBitrr will completely ignore this Radarr instance. Useful for temporarily disabling an instance without removing its configuration.

---

### Import Mode

```toml
importMode = "Auto"  # Auto | Move | Copy
```

| Mode | Behavior |
|------|----------|
| `Auto` | Let Radarr decide based on its own settings |
| `Move` | Move files from download folder to library (faster, frees disk space) |
| `Copy` | Copy files and leave original (preserves seeding torrents) |

!!! tip "Seeding Considerations"
    Use `Copy` if you want to keep seeding torrents after import. Use `Move` if disk space is limited and you don't seed long-term.

---

### ReSearch

```toml
ReSearch = true
```

When enabled, qBitrr automatically triggers a new search in Radarr when:

- A torrent fails or stalls beyond configured thresholds
- A torrent is manually moved to the `failed` category
- FFprobe validation detects a corrupted/fake file
- An error code from `ArrErrorCodesToBlocklist` is encountered

---

## Automation Settings

### RSS Sync Timer

```toml
RssSyncTimer = 1  # Minutes between RSS syncs (0 = disabled)
```

Periodically tells Radarr to refresh its RSS feeds from indexers. This helps Radarr discover new releases faster.

**Recommended values:**

- `1` - Very responsive (checks every minute)
- `5` - Balanced (checks every 5 minutes)
- `15` - Conservative (checks every 15 minutes)
- `0` - Disabled (not recommended)

!!! info "Radarr's Built-in RSS"
    Radarr has its own RSS sync schedule. qBitrr's `RssSyncTimer` is **additional** to Radarr's built-in sync, providing extra responsiveness.

---

### Refresh Downloads Timer

```toml
RefreshDownloadsTimer = 1  # Minutes between queue refreshes (0 = disabled)
```

Tells Radarr to update its download queue, ensuring it stays in sync with qBittorrent's actual state.

**Recommended values:**

- `1` - Very responsive (recommended)
- `5` - Balanced
- `0` - Disabled (not recommended, may cause sync issues)

---

## Error Handling

### Arr Error Codes to Blacklist

```toml
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing movie file(s)",
  "Not a preferred word upgrade for existing movie file(s)",
  "Unable to determine if file is a sample"
]
```

When Radarr encounters these error messages during import, qBitrr will:

1. ✅ Remove the failed files
2. ✅ Mark the release as failed in Radarr
3. ✅ Blacklist the release to prevent re-download
4. ✅ Trigger a new search (if `ReSearch = true`)

**Common error codes to add:**

- `"Not an upgrade for existing movie file(s)"` – Prevents re-downloading lower quality
- `"Unable to determine if file is a sample"` – Blocks sample/fake files
- `"Not a preferred word upgrade for existing movie file(s)"` – Enforces preferred words
- `"This file is a Proper and ReEncodes are not configured as preferred"` – Blocks re-encodes

**Disable error handling:**

```toml
ArrErrorCodesToBlocklist = []  # Empty list = disabled
```

---

## Automated Search Configuration

qBitrr can automatically search for missing movies, quality upgrades, and user requests. Configure these settings in the `[Radarr-Movies.EntrySearch]` subsection.

### Basic Search Settings

```toml
[Radarr-Movies.EntrySearch]
# Enable automated search for missing movies
SearchMissing = true

# Include unmonitored movies in searches
Unmonitored = false

# Maximum concurrent searches (Radarr default: 3, max: 10)
SearchLimit = 5

# Order searches by movie release year
SearchByYear = true

# Reverse search order (true = oldest first, false = newest first)
SearchInReverse = false

# Delay between searches in seconds
SearchRequestsEvery = 300

# Restart search loop when all movies are processed
SearchAgainOnSearchCompletion = true
```

!!! warning "Radarr Task Limit"
    Radarr has a default of **3 simultaneous tasks**. You can increase this up to 10 by setting the `THREAD_LIMIT` environment variable in Radarr, but **this is unsupported** by Radarr's developers. Use at your own risk.

---

### Quality Upgrade Searches

```toml
[Radarr-Movies.EntrySearch]
# Search for better quality versions of existing movies
DoUpgradeSearch = false

# Search for movies not meeting quality profile requirements
QualityUnmetSearch = false

# Search for movies not meeting custom format score requirements
CustomFormatUnmetSearch = false

# Automatically remove torrents below minimum custom format score
ForceMinimumCustomFormat = false
```

**When to enable:**

- `DoUpgradeSearch = true` – You want to continuously find better quality releases
- `QualityUnmetSearch = true` – You have quality profiles set and want to enforce them
- `CustomFormatUnmetSearch = true` – You use custom formats (TRaSH guides, etc.)
- `ForceMinimumCustomFormat = true` – Strictly enforce CF scores (removes non-compliant torrents)

!!! tip "Bandwidth Considerations"
    Upgrade searches can generate significant indexer traffic. Enable these only if you have:

    - Fast internet connection
    - Indexers with generous API limits
    - Sufficient disk space for re-downloads

---

### Temporary Quality Profiles

Temporarily lower quality standards for missing movies, then upgrade them later:

```toml
[Radarr-Movies.EntrySearch]
# Use temp profile for missing movies
UseTempForMissing = false

# Don't switch back to main profile after import
KeepTempProfile = false

# Map main profiles to temp profiles
QualityProfileMappings = { "Ultra-HD" = "Web-DL 1080p", "HD-1080p" = "HDTV-720p" }

# Reset all temp profiles on qBitrr startup
ForceResetTempProfiles = false

# Auto-reset temp profiles after timeout (0 = disabled)
TempProfileResetTimeoutMinutes = 0

# Retry failed profile switch API calls
ProfileSwitchRetryAttempts = 3
```

**How it works:**

1. Movie is missing and uses `Ultra-HD` profile
2. qBitrr switches it to `Web-DL 1080p` profile (temp)
3. Radarr searches with lower quality requirements
4. After import, qBitrr switches back to `Ultra-HD` (main)
5. Future upgrade searches look for Ultra-HD quality

**Configuration via WebUI:**

1. Open **Config** tab in WebUI
2. Find your Radarr instance
3. Click **"Test Connection"** to load quality profiles
4. Add profile mappings using dropdowns (no JSON editing!)
5. Save and restart

---

## Request Integration

### Overseerr

```toml
[Radarr-Movies.EntrySearch.Overseerr]
# Enable Overseerr request processing
SearchOverseerrRequests = false

# Overseerr URL
OverseerrURI = "http://localhost:5055"

# Overseerr API Key (Settings > General > API Key)
OverseerrAPIKey = "your-overseerr-api-key"

# Only process approved requests
ApprovedOnly = true

# Set to true for 4K Radarr instances
Is4K = false
```

When enabled, qBitrr:

1. 📥 Polls Overseerr for pending requests
2. 🔍 Prioritizes requests over general missing movie searches
3. ⭐ Marks requests in WebUI with `isRequest = true`
4. 📊 Processes requests based on approval status

!!! info "4K Instance Detection"
    Set `Is4K = true` if your Radarr instance is configured as the 4K instance in Overseerr. This ensures qBitrr pulls the correct requests.

---

### Ombi

```toml
[Radarr-Movies.EntrySearch.Ombi]
# Enable Ombi request processing
SearchOmbiRequests = false

# Ombi URL
OmbiURI = "http://localhost:3579"

# Ombi API Key (Settings > Configuration > API Key)
OmbiAPIKey = "your-ombi-api-key"

# Only process approved requests
ApprovedOnly = true
```

!!! warning "Overseerr vs. Ombi"
    If both `SearchOverseerrRequests` and `SearchOmbiRequests` are enabled, **Ombi will be ignored**. Choose one or the other.

---

## Torrent Management

Configure how qBitrr handles Radarr's torrents in the `[Radarr-Movies.Torrent]` subsection. See the [Torrent Settings](../torrents.md) page for comprehensive documentation.

### Quick Example

```toml
[Radarr-Movies.Torrent]
# Case-sensitive regex matching
CaseSensitiveMatches = false

# Exclude folders matching these patterns
FolderExclusionRegex = ["\\bextras?\\b", "\\bsamples?\\b", "\\bfeaturettes?\\b"]

# Exclude files matching these patterns
FileNameExclusionRegex = ["\\bsample\\b", "\\btrailer\\b"]

# Only allow these file extensions
FileExtensionAllowlist = [".mp4", ".mkv", ".avi", ".sub", ".srt", ".!qB", ".parts"]

# Auto-delete non-playable files
AutoDelete = false

# Ignore torrents younger than this (seconds)
IgnoreTorrentsYoungerThan = 180

# Maximum allowed ETA before considering torrent failed (seconds, -1 = disabled)
MaximumETA = -1

# Don't delete torrents above this completion percentage
MaximumDeletablePercentage = 0.99

# Ignore slow torrents instead of removing them
DoNotRemoveSlow = true

# Maximum stalled time before removal (minutes, -1 = disabled)
StalledDelay = 15

# Re-search before removing stalled torrents
ReSearchStalled = false
```

---

## Seeding Configuration

Configure seeding limits and behavior in the `[Radarr-Movies.Torrent.SeedingMode]` subsection. See the [Seeding Settings](../seeding.md) page for full details.

### Quick Example

```toml
[Radarr-Movies.Torrent.SeedingMode]
# Download rate limit per torrent (-1 = unlimited, or KB/s)
DownloadRateLimitPerTorrent = -1

# Upload rate limit per torrent (-1 = unlimited, or KB/s)
UploadRateLimitPerTorrent = -1

# Maximum upload ratio before stopping seeding (-1 = unlimited)
MaxUploadRatio = 2.0

# Maximum seeding time in seconds (-1 = unlimited)
MaxSeedingTime = 604800  # 7 days

# Remove torrent condition:
# -1 = Never remove
#  1 = Remove when MaxUploadRatio is met
#  2 = Remove when MaxSeedingTime is met
#  3 = Remove when EITHER condition is met
#  4 = Remove when BOTH conditions are met
RemoveTorrent = 3

# Remove dead trackers automatically
RemoveDeadTrackers = false

# Remove trackers with these error messages
RemoveTrackerWithMessage = [
  "skipping tracker announce (unreachable)",
  "No such host is known",
  "unsupported URL protocol",
  "info hash is not authorized with this tracker"
]
```

---

## Complete Example

### Standard 1080p Radarr Instance

```toml
[Radarr-Movies]
Managed = true
URI = "http://localhost:7878"
APIKey = "your-radarr-api-key"
Category = "radarr-movies"
ReSearch = true
importMode = "Auto"
RssSyncTimer = 1
RefreshDownloadsTimer = 1
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing movie file(s)",
  "Unable to determine if file is a sample"
]

[Radarr-Movies.EntrySearch]
SearchMissing = true
Unmonitored = false
SearchLimit = 5
SearchByYear = true
SearchInReverse = false
SearchRequestsEvery = 300
DoUpgradeSearch = false
QualityUnmetSearch = false
CustomFormatUnmetSearch = false
ForceMinimumCustomFormat = false
SearchAgainOnSearchCompletion = true
UseTempForMissing = false
KeepTempProfile = false
QualityProfileMappings = {}
ForceResetTempProfiles = false
TempProfileResetTimeoutMinutes = 0
ProfileSwitchRetryAttempts = 3

[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "your-overseerr-api-key"
ApprovedOnly = true
Is4K = false

[Radarr-Movies.Torrent]
CaseSensitiveMatches = false
FolderExclusionRegex = ["\\bextras?\\b", "\\bsamples?\\b"]
FileNameExclusionRegex = ["\\bsample\\b", "\\btrailer\\b"]
FileExtensionAllowlist = [".mp4", ".mkv", ".avi", ".sub", ".srt", ".!qB", ".parts"]
AutoDelete = false
IgnoreTorrentsYoungerThan = 180
MaximumETA = -1
MaximumDeletablePercentage = 0.99
DoNotRemoveSlow = true
StalledDelay = 15
ReSearchStalled = false

[Radarr-Movies.Torrent.SeedingMode]
DownloadRateLimitPerTorrent = -1
UploadRateLimitPerTorrent = -1
MaxUploadRatio = 2.0
MaxSeedingTime = 604800
RemoveTorrent = 3
RemoveDeadTrackers = false
```

---

### 4K Radarr Instance with Overseerr

```toml
[Radarr-4K]
Managed = true
URI = "http://localhost:7879"
APIKey = "your-4k-radarr-api-key"
Category = "radarr-4k"
ReSearch = true
importMode = "Copy"  # Copy mode to preserve seeding
RssSyncTimer = 5
RefreshDownloadsTimer = 5
ArrErrorCodesToBlocklist = ["Not an upgrade for existing movie file(s)"]

[Radarr-4K.EntrySearch]
SearchMissing = true
SearchLimit = 3
DoUpgradeSearch = true  # Enabled for 4K upgrades
CustomFormatUnmetSearch = true  # Enforce CF scores
ForceMinimumCustomFormat = true  # Strict CF enforcement

[Radarr-4K.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "your-overseerr-api-key"
ApprovedOnly = true
Is4K = true  # 4K instance flag

[Radarr-4K.Torrent.SeedingMode]
MaxUploadRatio = 3.0  # Seed longer for 4K content
MaxSeedingTime = 1209600  # 14 days
RemoveTorrent = 4  # Remove only when both ratio AND time met
```

---

## Troubleshooting

### Torrents Not Being Processed

**Symptoms:** qBitrr doesn't monitor or manage Radarr torrents

**Solutions:**

1. ✅ Verify `Category` in qBitrr matches Radarr's download client category exactly
2. ✅ Check `Managed = true` in config
3. ✅ Ensure Radarr's qBittorrent download client is tagging torrents
4. ✅ Enable debug logging: `ConsoleLevel = "DEBUG"` in `[Settings]`
5. ✅ Check category-specific log: `~/logs/Radarr-Movies.log`

---

### Searches Not Triggering

**Symptoms:** qBitrr doesn't search for missing movies

**Solutions:**

1. ✅ Verify `SearchMissing = true` in `[Radarr-Movies.EntrySearch]`
2. ✅ Check `SearchLimit` isn't too low
3. ✅ Ensure Radarr has indexers configured and working
4. ✅ Review `SearchRequestsEvery` delay setting
5. ✅ Check Radarr logs for rate limiting or indexer errors

---

### Overseerr Requests Not Processing

**Symptoms:** Overseerr requests aren't being searched

**Solutions:**

1. ✅ Verify `SearchOverseerrRequests = true`
2. ✅ Check `OverseerrURI` and `OverseerrAPIKey` are correct
3. ✅ Ensure `Is4K` matches your Radarr instance type
4. ✅ Verify `ApprovedOnly = true` if you only want approved requests
5. ✅ Test Overseerr API manually:
   ```bash
   curl -H "X-Api-Key: your-api-key" http://localhost:5055/api/v1/request
   ```

---

### Connection Failures

**Symptoms:** "Connection refused" or "Unauthorized" errors

**Solutions:**

1. ✅ Test Radarr API manually:
   ```bash
   curl -H "X-Api-Key: your-api-key" http://localhost:7878/api/v3/system/status
   ```
2. ✅ Verify `URI` is correct (include `http://` or `https://`)
3. ✅ Check `APIKey` is copied correctly (no extra spaces)
4. ✅ Ensure Radarr is running and accessible
5. ✅ Check firewall rules if Radarr is on a different machine

---

## Next Steps

- **Configure Sonarr:** [Sonarr Configuration](sonarr.md)
- **Configure Lidarr:** [Lidarr Configuration](lidarr.md)
- **Advanced Torrent Settings:** [Torrent Configuration](../torrents.md)
- **Seeding Configuration:** [Seeding Settings](../seeding.md)
- **Troubleshooting:** [Common Issues](../../troubleshooting/common-issues.md)
