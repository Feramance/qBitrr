# Sonarr Configuration

This guide covers how to configure Sonarr instances in qBitrr for TV show management, automated searching, episode tracking, and quality upgrades.

---

## Quick Start

Every Sonarr instance in qBitrr requires a dedicated section in your `config.toml` file. The section name must follow the pattern `Sonarr-<name>`.

### Basic Configuration

```toml
[Sonarr-TV]
# Toggle whether to manage this Sonarr instance
Managed = true

# The URL used to access Sonarr (e.g., http://ip:port)
URI = "http://localhost:8989"

# Sonarr API Key (Settings > General > Security)
APIKey = "your-sonarr-api-key"

# Category applied by Sonarr to torrents in qBittorrent
# MUST match: Sonarr > Settings > Download Clients > qBittorrent > Category
Category = "sonarr-tv"

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
  "Not an upgrade for existing episode file(s)",
  "Not a preferred word upgrade for existing episode file(s)",
  "Unable to determine if file is a sample"
]
```

---

## Connection Settings

### Finding Your Sonarr Details

1. **URI**: Open Sonarr in your browser and copy the URL (e.g., `http://192.168.1.100:8989`)
2. **APIKey**: In Sonarr, go to **Settings** → **General** → **Security** → Copy the **API Key**
3. **Category**: Go to **Settings** → **Download Clients** → Click your qBittorrent client → Note the **Category** field

!!! warning "Category Mismatch"
    The `Category` value in qBitrr **must exactly match** the category configured in Sonarr's qBittorrent download client settings. If they don't match, qBitrr won't process your Sonarr torrents.

---

### Multiple Sonarr Instances

You can configure multiple Sonarr instances (e.g., separate instances for TV shows and anime):

```toml
[Sonarr-TV]
URI = "http://localhost:8989"
APIKey = "api-key-1"
Category = "sonarr-tv"
# ... other settings

[Sonarr-Anime]
URI = "http://localhost:8990"
APIKey = "api-key-2"
Category = "sonarr-anime"
# ... other settings
```

!!! tip "Naming Convention"
    Instance names must start with `Sonarr-` followed by any descriptive name. Examples:

    - ✅ `Sonarr-TV`
    - ✅ `Sonarr-Anime`
    - ✅ `Sonarr-4K`
    - ❌ `TV` (missing prefix)
    - ❌ `sonarr-tv` (lowercase)

---

## Basic Settings

### Managed

```toml
Managed = true  # Enable management for this Sonarr instance
```

When `Managed = false`, qBitrr will completely ignore this Sonarr instance. Useful for temporarily disabling an instance without removing its configuration.

---

### Import Mode

```toml
importMode = "Auto"  # Auto | Move | Copy
```

| Mode | Behavior |
|------|----------|
| `Auto` | Let Sonarr decide based on its own settings |
| `Move` | Move files from download folder to library (faster, frees disk space) |
| `Copy` | Copy files and leave original (preserves seeding torrents) |

!!! tip "Seeding Considerations"
    Use `Copy` if you want to keep seeding torrents after import. Use `Move` if disk space is limited and you don't seed long-term.

---

### ReSearch

```toml
ReSearch = true
```

When enabled, qBitrr automatically triggers a new search in Sonarr when:

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

Periodically tells Sonarr to refresh its RSS feeds from indexers. This is especially important for TV shows where new episodes release frequently.

**Recommended values:**

- `1` - Very responsive (checks every minute) - **Recommended for active series**
- `5` - Balanced (checks every 5 minutes)
- `15` - Conservative (checks every 15 minutes)
- `0` - Disabled (not recommended)

!!! info "Sonarr's Built-in RSS"
    Sonarr has its own RSS sync schedule. qBitrr's `RssSyncTimer` is **additional** to Sonarr's built-in sync, providing extra responsiveness for new episode releases.

---

### Refresh Downloads Timer

```toml
RefreshDownloadsTimer = 1  # Minutes between queue refreshes (0 = disabled)
```

Tells Sonarr to update its download queue, ensuring it stays in sync with qBittorrent's actual state.

**Recommended values:**

- `1` - Very responsive (recommended)
- `5` - Balanced
- `0` - Disabled (not recommended, may cause sync issues)

---

## Error Handling

### Arr Error Codes to Blacklist

```toml
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing episode file(s)",
  "Not a preferred word upgrade for existing episode file(s)",
  "Unable to determine if file is a sample"
]
```

When Sonarr encounters these error messages during import, qBitrr will:

1. ✅ Remove the failed files
2. ✅ Mark the release as failed in Sonarr
3. ✅ Blacklist the release to prevent re-download
4. ✅ Trigger a new search (if `ReSearch = true`)

**Common error codes to add:**

- `"Not an upgrade for existing episode file(s)"` – Prevents re-downloading lower quality
- `"Unable to determine if file is a sample"` – Blocks sample/fake files
- `"Not a preferred word upgrade for existing episode file(s)"` – Enforces preferred words
- `"This file is a Proper and ReEncodes are not configured as preferred"` – Blocks re-encodes

**Disable error handling:**

```toml
ArrErrorCodesToBlocklist = []  # Empty list = disabled
```

---

## Automated Search Configuration

qBitrr can automatically search for missing episodes, quality upgrades, and user requests. Configure these settings in the `[Sonarr-TV.EntrySearch]` subsection.

### Basic Search Settings

```toml
[Sonarr-TV.EntrySearch]
# Enable automated search for missing episodes
SearchMissing = true

# Include Season 00 (specials) in searches
AlsoSearchSpecials = false

# Include unmonitored episodes/series in searches
Unmonitored = false

# Maximum concurrent searches qBitrr will queue (Sonarr hardcoded cap: 3)
SearchLimit = 5

# Order searches by episode air year
SearchByYear = true

# Reverse search order (true = oldest first, false = newest first)
SearchInReverse = false

# Delay between searches in seconds
SearchRequestsEvery = 300

# Restart search loop when all episodes are processed
SearchAgainOnSearchCompletion = true
```

!!! warning "Sonarr Task Limit"
    Sonarr has a **hardcoded limit of 3 simultaneous tasks**. Setting `SearchLimit` higher than 3 won't increase actual concurrency, but it does affect qBitrr's search queue management.

---

### Search Mode (Series vs. Episode)

```toml
[Sonarr-TV.EntrySearch]
# Search mode: true | false | "smart"
SearchBySeries = "smart"
```

| Mode | Behavior |
|------|----------|
| `true` | Always use series-level search (searches entire series at once) |
| `false` | Always use episode-level search (searches individual episodes) |
| `"smart"` | **(Recommended)** Automatically chooses:  <br>- Series search for entire seasons/series  <br>- Episode search for single episodes |

!!! tip "Smart Mode Benefits"
    `"smart"` mode optimizes search efficiency by using series search for bulk operations and episode search for granular control. This reduces indexer API calls and improves search speed.

---

### Prioritize Today's Releases

```toml
[Sonarr-TV.EntrySearch]
# Prioritize episodes that aired today
PrioritizeTodaysReleases = true
```

When enabled, qBitrr searches for episodes that aired **today** before processing the general missing episode queue. This ensures new episodes are grabbed quickly after they air.

**Effect:**

- ✅ New episodes searched within minutes of availability
- ✅ Simulates RSS-like behavior for ongoing series
- ✅ Works even if Sonarr's RSS sync is delayed

!!! info "Sonarr-Specific Feature"
    This setting **only works on Sonarr**. Radarr and Lidarr don't have air date tracking for prioritization.

---

### Quality Upgrade Searches

```toml
[Sonarr-TV.EntrySearch]
# Search for better quality versions of existing episodes
DoUpgradeSearch = false

# Search for episodes not meeting quality profile requirements
QualityUnmetSearch = false

# Search for episodes not meeting custom format score requirements
CustomFormatUnmetSearch = false

# Automatically remove torrents below minimum custom format score
ForceMinimumCustomFormat = false
```

**When to enable:**

- `DoUpgradeSearch = true` – You want to continuously find better quality releases
- `QualityUnmetSearch = true` – You have quality profiles set and want to enforce them
- `CustomFormatUnmetSearch = true` – You use custom formats (TRaSH guides, etc.)
- `ForceMinimumCustomFormat = true` – Strictly enforce CF scores (removes non-compliant torrents)

!!! warning "Series Search Limitations"
    When `SearchBySeries = true` or `"smart"` (for series-level searches), **QualityUnmetSearch** and **CustomFormatUnmetSearch** are **ignored**. Series searches don't support granular quality filtering.

!!! tip "Bandwidth Considerations"
    Upgrade searches can generate significant indexer traffic, especially for large TV libraries. Enable these only if you have:

    - Fast internet connection
    - Indexers with generous API limits
    - Sufficient disk space for re-downloads

---

### Temporary Quality Profiles

Temporarily lower quality standards for missing episodes, then upgrade them later:

```toml
[Sonarr-TV.EntrySearch]
# Use temp profile for missing episodes
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

1. Episode is missing and uses `Ultra-HD` profile
2. qBitrr switches it to `Web-DL 1080p` profile (temp)
3. Sonarr searches with lower quality requirements
4. After import, qBitrr switches back to `Ultra-HD` (main)
5. Future upgrade searches look for Ultra-HD quality

**Configuration via WebUI:**

1. Open **Config** tab in WebUI
2. Find your Sonarr instance
3. Click **"Test Connection"** to load quality profiles
4. Add profile mappings using dropdowns (no JSON editing!)
5. Save and restart

---

## Request Integration

### Overseerr

```toml
[Sonarr-TV.EntrySearch.Overseerr]
# Enable Overseerr request processing
SearchOverseerrRequests = false

# Overseerr URL
OverseerrURI = "http://localhost:5055"

# Overseerr API Key (Settings > General > API Key)
OverseerrAPIKey = "your-overseerr-api-key"

# Only process approved requests
ApprovedOnly = true

# Set to true for 4K Sonarr instances
Is4K = false
```

When enabled, qBitrr:

1. 📥 Polls Overseerr for pending TV show requests
2. 🔍 Prioritizes requests over general missing episode searches
3. ⭐ Marks requests in WebUI with `isRequest = true`
4. 📊 Processes requests based on approval status

!!! info "4K Instance Detection"
    Set `Is4K = true` if your Sonarr instance is configured as the 4K instance in Overseerr. This ensures qBitrr pulls the correct requests.

---

### Ombi

```toml
[Sonarr-TV.EntrySearch.Ombi]
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

Configure how qBitrr handles Sonarr's torrents in the `[Sonarr-TV.Torrent]` subsection. See the [Torrent Settings](../torrents.md) page for comprehensive documentation.

### Quick Example

```toml
[Sonarr-TV.Torrent]
# Case-sensitive regex matching
CaseSensitiveMatches = false

# Exclude folders matching these patterns
FolderExclusionRegex = ["\\bextras?\\b", "\\bsamples?\\b", "\\bfeaturettes?\\b", "\\bnc(ed|op)?(\\\\d+)?\\b"]

# Exclude files matching these patterns
FileNameExclusionRegex = ["\\bncop\\\\d+?\\b", "\\bnced\\\\d+?\\b", "\\bsample\\b", "\\btrailer\\b"]

# Only allow these file extensions
FileExtensionAllowlist = [".mp4", ".mkv", ".avi", ".sub", ".ass", ".srt", ".!qB", ".parts"]

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

!!! info "NCOP/NCED Files"
    The `nc(ed|op)` regex patterns exclude:

    - **NCOP**: Non-Credit Opening sequences
    - **NCED**: Non-Credit Ending sequences

    These are common in anime releases but typically not wanted in your library.

---

## Anime-Specific Configuration

For anime-focused Sonarr instances, add extra folder/file exclusions:

```toml
[Sonarr-Anime.Torrent]
# Extra anime-specific exclusions
FolderExclusionRegex = [
  "\\bextras?\\b",
  "\\bsamples?\\b",
  "\\bspecials?\\b",  # Anime special episodes folder
  "\\bova\\b",         # OVA episodes folder
  "\\bnc(ed|op)?(\\\\d+)?\\b"  # Non-credit sequences
]

FileNameExclusionRegex = [
  "\\bncop\\\\d+?\\b",
  "\\bnced\\\\d+?\\b",
  "\\bsample\\b",
  "\\btrailer\\b"
]
```

---

## Seeding Configuration

Configure seeding limits and behavior in the `[Sonarr-TV.Torrent.SeedingMode]` subsection. See the [Seeding Settings](../seeding.md) page for full details.

### Quick Example

```toml
[Sonarr-TV.Torrent.SeedingMode]
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

## Complete Examples

### Standard TV Sonarr Instance

```toml
[Sonarr-TV]
Managed = true
URI = "http://localhost:8989"
APIKey = "your-sonarr-api-key"
Category = "sonarr-tv"
ReSearch = true
importMode = "Auto"
RssSyncTimer = 1
RefreshDownloadsTimer = 1
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing episode file(s)",
  "Unable to determine if file is a sample"
]

[Sonarr-TV.EntrySearch]
SearchMissing = true
AlsoSearchSpecials = false
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
SearchBySeries = "smart"
PrioritizeTodaysReleases = true

[Sonarr-TV.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "your-overseerr-api-key"
ApprovedOnly = true
Is4K = false

[Sonarr-TV.Torrent]
CaseSensitiveMatches = false
FolderExclusionRegex = ["\\bextras?\\b", "\\bsamples?\\b", "\\bnc(ed|op)?(\\\\d+)?\\b"]
FileNameExclusionRegex = ["\\bncop\\\\d+?\\b", "\\bnced\\\\d+?\\b", "\\bsample\\b"]
FileExtensionAllowlist = [".mp4", ".mkv", ".avi", ".sub", ".srt", ".!qB", ".parts"]
AutoDelete = false
IgnoreTorrentsYoungerThan = 180
MaximumETA = -1
MaximumDeletablePercentage = 0.99
DoNotRemoveSlow = true
StalledDelay = 15
ReSearchStalled = false

[Sonarr-TV.Torrent.SeedingMode]
DownloadRateLimitPerTorrent = -1
UploadRateLimitPerTorrent = -1
MaxUploadRatio = 2.0
MaxSeedingTime = 604800
RemoveTorrent = 3
RemoveDeadTrackers = false
```

---

### Anime Sonarr Instance

```toml
[Sonarr-Anime]
Managed = true
URI = "http://localhost:8990"
APIKey = "your-anime-sonarr-api-key"
Category = "sonarr-anime"
ReSearch = true
importMode = "Copy"  # Copy to preserve seeding for anime trackers
RssSyncTimer = 1
RefreshDownloadsTimer = 1
ArrErrorCodesToBlocklist = ["Not an upgrade for existing episode file(s)"]

[Sonarr-Anime.EntrySearch]
SearchMissing = true
AlsoSearchSpecials = true  # Often want anime specials
Unmonitored = false
SearchLimit = 5
SearchByYear = true
SearchInReverse = false
SearchRequestsEvery = 300
SearchBySeries = "smart"
PrioritizeTodaysReleases = true

[Sonarr-Anime.Torrent]
FolderExclusionRegex = [
  "\\bextras?\\b",
  "\\bsamples?\\b",
  "\\bspecials?\\b",
  "\\bova\\b",
  "\\bnc(ed|op)?(\\\\d+)?\\b"
]
FileNameExclusionRegex = [
  "\\bncop\\\\d+?\\b",
  "\\bnced\\\\d+?\\b",
  "\\bsample\\b"
]
FileExtensionAllowlist = [".mp4", ".mkv", ".sub", ".ass", ".srt", ".!qB"]
IgnoreTorrentsYoungerThan = 180
MaximumETA = 86400  # 24 hours (anime trackers can be slower)
DoNotRemoveSlow = true
StalledDelay = 30  # Longer stall delay for anime

[Sonarr-Anime.Torrent.SeedingMode]
MaxUploadRatio = 3.0  # Seed longer for anime
MaxSeedingTime = 1209600  # 14 days
RemoveTorrent = 4  # Remove only when both ratio AND time met
```

---

## Troubleshooting

### Torrents Not Being Processed

**Symptoms:** qBitrr doesn't monitor or manage Sonarr torrents

**Solutions:**

1. ✅ Verify `Category` in qBitrr matches Sonarr's download client category exactly
2. ✅ Check `Managed = true` in config
3. ✅ Ensure Sonarr's qBittorrent download client is tagging torrents
4. ✅ Enable debug logging: `ConsoleLevel = "DEBUG"` in `[Settings]`
5. ✅ Check category-specific log: `~/logs/Sonarr-TV.log`

---

### Searches Not Triggering

**Symptoms:** qBitrr doesn't search for missing episodes

**Solutions:**

1. ✅ Verify `SearchMissing = true` in `[Sonarr-TV.EntrySearch]`
2. ✅ Check `SearchLimit` isn't too low
3. ✅ Ensure Sonarr has indexers configured and working
4. ✅ Review `SearchRequestsEvery` delay setting
5. ✅ Check Sonarr logs for rate limiting or indexer errors

---

### Today's Releases Not Prioritized

**Symptoms:** New episodes aren't grabbed quickly

**Solutions:**

1. ✅ Verify `PrioritizeTodaysReleases = true`
2. ✅ Check `RssSyncTimer` is set low (e.g., `1`)
3. ✅ Ensure episodes have correct air dates in Sonarr
4. ✅ Verify indexers are returning results for new episodes
5. ✅ Check qBitrr logs for search activity

---

### Overseerr Requests Not Processing

**Symptoms:** Overseerr requests aren't being searched

**Solutions:**

1. ✅ Verify `SearchOverseerrRequests = true`
2. ✅ Check `OverseerrURI` and `OverseerrAPIKey` are correct
3. ✅ Ensure `Is4K` matches your Sonarr instance type
4. ✅ Verify `ApprovedOnly = true` if you only want approved requests
5. ✅ Test Overseerr API manually:
   ```bash
   curl -H "X-Api-Key: your-api-key" http://localhost:5055/api/v1/request
   ```

---

### Connection Failures

**Symptoms:** "Connection refused" or "Unauthorized" errors

**Solutions:**

1. ✅ Test Sonarr API manually:
   ```bash
   curl -H "X-Api-Key: your-api-key" http://localhost:8989/api/v3/system/status
   ```
2. ✅ Verify `URI` is correct (include `http://` or `https://`)
3. ✅ Check `APIKey` is copied correctly (no extra spaces)
4. ✅ Ensure Sonarr is running and accessible
5. ✅ Check firewall rules if Sonarr is on a different machine

---

## Next Steps

- **Configure Radarr:** [Radarr Configuration](radarr.md)
- **Configure Lidarr:** [Lidarr Configuration](lidarr.md)
- **Advanced Torrent Settings:** [Torrent Configuration](../torrents.md)
- **Seeding Configuration:** [Seeding Settings](../seeding.md)
- **Troubleshooting:** [Common Issues](../../troubleshooting/common-issues.md)
