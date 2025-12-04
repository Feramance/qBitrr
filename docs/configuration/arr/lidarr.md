# Lidarr Configuration

This guide covers how to configure Lidarr instances in qBitrr for music library management, automated searching, and quality upgrades.

---

## Quick Start

Every Lidarr instance in qBitrr requires a dedicated section in your `config.toml` file. The section name must follow the pattern `Lidarr-<name>`.

### Basic Configuration

```toml
[Lidarr-Music]
# Toggle whether to manage this Lidarr instance
Managed = true

# The URL used to access Lidarr (e.g., http://ip:port)
URI = "http://localhost:8686"

# Lidarr API Key (Settings > General > Security)
APIKey = "your-lidarr-api-key"

# Category applied by Lidarr to torrents in qBittorrent
# MUST match: Lidarr > Settings > Download Clients > qBittorrent > Category
Category = "lidarr-music"

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
  "Not an upgrade for existing track file(s)",
  "Not a preferred word upgrade for existing track file(s)",
  "Unable to determine if file is a sample"
]
```

---

## Connection Settings

### Finding Your Lidarr Details

1. **URI**: Open Lidarr in your browser and copy the URL (e.g., `http://192.168.1.100:8686`)
2. **APIKey**: In Lidarr, go to **Settings** → **General** → **Security** → Copy the **API Key**
3. **Category**: Go to **Settings** → **Download Clients** → Click your qBittorrent client → Note the **Category** field

!!! warning "Category Mismatch"
    The `Category` value in qBitrr **must exactly match** the category configured in Lidarr's qBittorrent download client settings. If they don't match, qBitrr won't process your Lidarr torrents.

---

### Multiple Lidarr Instances

You can configure multiple Lidarr instances (e.g., separate instances for different music quality levels):

```toml
[Lidarr-Music]
URI = "http://localhost:8686"
APIKey = "api-key-1"
Category = "lidarr-music"
# ... other settings

[Lidarr-Lossless]
URI = "http://localhost:8687"
APIKey = "api-key-2"
Category = "lidarr-lossless"
# ... other settings
```

!!! tip "Naming Convention"
    Instance names must start with `Lidarr-` followed by any descriptive name. Examples:

    - ✅ `Lidarr-Music`
    - ✅ `Lidarr-Lossless`
    - ✅ `Lidarr-4K`
    - ❌ `Music` (missing prefix)
    - ❌ `lidarr-music` (lowercase)

---

## Basic Settings

### Managed

```toml
Managed = true  # Enable management for this Lidarr instance
```

When `Managed = false`, qBitrr will completely ignore this Lidarr instance. Useful for temporarily disabling an instance without removing its configuration.

---

### Import Mode

```toml
importMode = "Auto"  # Auto | Move | Copy
```

| Mode | Behavior |
|------|----------|
| `Auto` | Let Lidarr decide based on its own settings |
| `Move` | Move files from download folder to library (faster, frees disk space) |
| `Copy` | Copy files and leave original (preserves seeding torrents) |

!!! tip "Seeding for Music"
    Music trackers often have strict seeding requirements. Use `Copy` mode to preserve torrents for seeding while importing to your library.

---

### ReSearch

```toml
ReSearch = true
```

When enabled, qBitrr automatically triggers a new search in Lidarr when:

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

Periodically tells Lidarr to refresh its RSS feeds from indexers. This helps Lidarr discover new album releases faster.

**Recommended values:**

- `1` - Very responsive (checks every minute)
- `5` - Balanced (checks every 5 minutes)
- `15` - Conservative (checks every 15 minutes)
- `0` - Disabled (not recommended)

!!! info "Lidarr's Built-in RSS"
    Lidarr has its own RSS sync schedule. qBitrr's `RssSyncTimer` is **additional** to Lidarr's built-in sync, providing extra responsiveness for new releases.

---

### Refresh Downloads Timer

```toml
RefreshDownloadsTimer = 1  # Minutes between queue refreshes (0 = disabled)
```

Tells Lidarr to update its download queue, ensuring it stays in sync with qBittorrent's actual state.

**Recommended values:**

- `1` - Very responsive (recommended)
- `5` - Balanced
- `0` - Disabled (not recommended, may cause sync issues)

---

## Error Handling

### Arr Error Codes to Blacklist

```toml
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing track file(s)",
  "Not a preferred word upgrade for existing track file(s)",
  "Unable to determine if file is a sample"
]
```

When Lidarr encounters these error messages during import, qBitrr will:

1. ✅ Remove the failed files
2. ✅ Mark the release as failed in Lidarr
3. ✅ Blacklist the release to prevent re-download
4. ✅ Trigger a new search (if `ReSearch = true`)

**Common error codes to add:**

- `"Not an upgrade for existing track file(s)"` – Prevents re-downloading lower quality
- `"Unable to determine if file is a sample"` – Blocks sample/fake files
- `"Not a preferred word upgrade for existing track file(s)"` – Enforces preferred words

**Disable error handling:**

```toml
ArrErrorCodesToBlocklist = []  # Empty list = disabled
```

---

## Automated Search Configuration

qBitrr can automatically search for missing albums and quality upgrades. Configure these settings in the `[Lidarr-Music.EntrySearch]` subsection.

### Basic Search Settings

```toml
[Lidarr-Music.EntrySearch]
# Enable automated search for missing albums
SearchMissing = true

# Reverse search order (true = oldest first, false = newest first)
SearchInReverse = false

# Delay between searches in seconds
SearchRequestsEvery = 300

# Restart search loop when all albums are processed
SearchAgainOnSearchCompletion = true
```

!!! info "Lidarr-Specific Settings"
    Lidarr doesn't have some Sonarr/Radarr features like:

    - No `SearchByYear` (albums don't sort by year the same way)
    - No `SearchLimit` (Lidarr manages its own task queue)
    - No `AlsoSearchSpecials` (not applicable to music)
    - No `Unmonitored` option (handled differently)
    - No `SearchBySeries` (not applicable to music)

---

### Quality Upgrade Searches

```toml
[Lidarr-Music.EntrySearch]
# Search for better quality versions of existing albums
DoUpgradeSearch = false

# Search for albums not meeting quality profile requirements
QualityUnmetSearch = false

# Search for albums not meeting custom format score requirements
CustomFormatUnmetSearch = false

# Automatically remove torrents below minimum custom format score
ForceMinimumCustomFormat = false
```

**When to enable:**

- `DoUpgradeSearch = true` – You want to continuously find better quality releases (e.g., upgrade MP3 → FLAC)
- `QualityUnmetSearch = true` – You have quality profiles set and want to enforce them
- `CustomFormatUnmetSearch = true` – You use custom formats for music quality/sources
- `ForceMinimumCustomFormat = true` – Strictly enforce CF scores (removes non-compliant torrents)

!!! warning "Upgrade Bandwidth"
    Music files are large, especially lossless formats. Upgrade searches can consume significant bandwidth and indexer API calls. Enable selectively.

---

### Temporary Quality Profiles

Temporarily lower quality standards for missing albums, then upgrade them later:

```toml
[Lidarr-Music.EntrySearch]
# Use temp profile for missing albums
UseTempForMissing = false

# Don't switch back to main profile after import
KeepTempProfile = false

# Map main profiles to temp profiles
QualityProfileMappings = { "Lossless" = "MP3-320", "MP3-320" = "MP3-V0" }

# Reset all temp profiles on qBitrr startup
ForceResetTempProfiles = false

# Auto-reset temp profiles after timeout (0 = disabled)
TempProfileResetTimeoutMinutes = 0

# Retry failed profile switch API calls
ProfileSwitchRetryAttempts = 3
```

**How it works:**

1. Album is missing and uses `Lossless` profile
2. qBitrr switches it to `MP3-320` profile (temp)
3. Lidarr searches with lower quality requirements
4. After import, qBitrr switches back to `Lossless` (main)
5. Future upgrade searches look for lossless quality

**Common use case:**

```toml
# Grab MP3 now, upgrade to FLAC later
QualityProfileMappings = { "Lossless (FLAC)" = "Lossy (MP3-320)" }
```

---

## Request Integration

!!! warning "No Overseerr/Ombi Support"
    Overseerr and Ombi **do not support music requests**. These settings are not available for Lidarr instances. Music request management must be handled through Lidarr's built-in wanted list.

---

## Torrent Management

Configure how qBitrr handles Lidarr's torrents in the `[Lidarr-Music.Torrent]` subsection.

### Audio File Configuration

```toml
[Lidarr-Music.Torrent]
# Case-sensitive regex matching
CaseSensitiveMatches = false

# Exclude folders matching these patterns
FolderExclusionRegex = ["\\bextras?\\b", "\\bsamples?\\b", "\\bscans?\\b", "\\bartwork\\b"]

# Exclude files matching these patterns
FileNameExclusionRegex = ["\\bsample\\b", "\\btrailer\\b", "\\bcover\\b"]

# Only allow these file extensions (music-specific)
FileExtensionAllowlist = [".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".ape", ".wma", ".!qB", ".parts"]

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

!!! info "Music File Extensions"
    Lidarr uses different file extensions than Radarr/Sonarr:

    **Lossless:**
    - `.flac` - Free Lossless Audio Codec
    - `.ape` - Monkey's Audio
    - `.wav` - Waveform Audio

    **Lossy:**
    - `.mp3` - MP3
    - `.m4a` - AAC/ALAC
    - `.ogg` - Vorbis
    - `.opus` - Opus
    - `.wma` - Windows Media Audio

---

### Music Tracker Considerations

Music trackers often have stricter rules than movie/TV trackers:

```toml
[Lidarr-Music.Torrent]
# Longer stall delay for music trackers
StalledDelay = 30  # 30 minutes instead of 15

# Be conservative with slow torrent removal
DoNotRemoveSlow = true

# Higher ETA tolerance for rare albums
MaximumETA = 86400  # 24 hours
```

---

## Seeding Configuration

Configure seeding limits and behavior in the `[Lidarr-Music.Torrent.SeedingMode]` subsection.

### Music Seeding Best Practices

```toml
[Lidarr-Music.Torrent.SeedingMode]
# Download rate limit per torrent (-1 = unlimited, or KB/s)
DownloadRateLimitPerTorrent = -1

# Upload rate limit per torrent (-1 = unlimited, or KB/s)
UploadRateLimitPerTorrent = -1

# Maximum upload ratio before stopping seeding (-1 = unlimited)
MaxUploadRatio = 3.0  # Music trackers often require higher ratios

# Maximum seeding time in seconds (-1 = unlimited)
MaxSeedingTime = 2592000  # 30 days

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

!!! warning "Music Tracker Seeding Requirements"
    Many music trackers have **strict seeding requirements**:

    - **RED/OPS:** Seed for 72 hours OR reach 1.0 ratio
    - **APL:** Seed for 120 hours OR reach 1.0 ratio
    - **Private trackers:** Often require minimum 1.0 ratio

    Configure `MaxUploadRatio` and `MaxSeedingTime` accordingly!

---

### Tracker-Specific Configuration

Example for RED (Redacted):

```toml
[[Lidarr-Music.Torrent.Trackers]]
Name = "RED"
Priority = 10
URI = "https://flacsfor.me/announce"

# RED requires 72 hours OR 1.0 ratio
MaxSeedingTime = 259200  # 72 hours
MaxUploadRatio = 1.0

# Other settings
DownloadRateLimit = -1
UploadRateLimit = -1
AddTrackerIfMissing = false
RemoveIfExists = false
SuperSeedMode = false
AddTags = ["qBitrr-music", "RED"]
```

---

## Complete Examples

### Standard Music Library

```toml
[Lidarr-Music]
Managed = true
URI = "http://localhost:8686"
APIKey = "your-lidarr-api-key"
Category = "lidarr-music"
ReSearch = true
importMode = "Copy"  # Preserve seeding
RssSyncTimer = 5
RefreshDownloadsTimer = 5
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing track file(s)",
  "Unable to determine if file is a sample"
]

[Lidarr-Music.EntrySearch]
SearchMissing = true
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

[Lidarr-Music.Torrent]
CaseSensitiveMatches = false
FolderExclusionRegex = ["\\bextras?\\b", "\\bsamples?\\b", "\\bartwork\\b"]
FileNameExclusionRegex = ["\\bsample\\b", "\\bcover\\b"]
FileExtensionAllowlist = [".mp3", ".flac", ".m4a", ".ogg", ".!qB", ".parts"]
AutoDelete = false
IgnoreTorrentsYoungerThan = 180
MaximumETA = -1
MaximumDeletablePercentage = 0.99
DoNotRemoveSlow = true
StalledDelay = 30
ReSearchStalled = false

[Lidarr-Music.Torrent.SeedingMode]
DownloadRateLimitPerTorrent = -1
UploadRateLimitPerTorrent = -1
MaxUploadRatio = 2.0
MaxSeedingTime = 2592000  # 30 days
RemoveTorrent = 3
RemoveDeadTrackers = false
```

---

### Lossless-Only Library with Temp Profiles

```toml
[Lidarr-Lossless]
Managed = true
URI = "http://localhost:8687"
APIKey = "your-lossless-lidarr-api-key"
Category = "lidarr-lossless"
ReSearch = true
importMode = "Copy"
RssSyncTimer = 5
RefreshDownloadsTimer = 5

[Lidarr-Lossless.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true  # Always look for better lossless releases
QualityUnmetSearch = true
CustomFormatUnmetSearch = true
ForceMinimumCustomFormat = true  # Strictly enforce lossless

# Grab MP3 now, upgrade to FLAC later
UseTempForMissing = true
QualityProfileMappings = { "Lossless (FLAC)" = "Lossy (MP3-320)" }
TempProfileResetTimeoutMinutes = 10080  # 7 days

[Lidarr-Lossless.Torrent]
FileExtensionAllowlist = [".flac", ".ape", ".wav", ".!qB", ".parts"]  # Lossless only
MaximumETA = 86400  # 24 hours (lossless files are larger)
StalledDelay = 45  # Longer wait for rare albums

[Lidarr-Lossless.Torrent.SeedingMode]
MaxUploadRatio = 3.0  # Higher ratio for lossless
MaxSeedingTime = 5184000  # 60 days
RemoveTorrent = 4  # Remove only when BOTH ratio AND time met
```

---

### Private Tracker Setup (RED/OPS)

```toml
[Lidarr-PrivateTracker]
Managed = true
URI = "http://localhost:8688"
APIKey = "your-api-key"
Category = "lidarr-private"
ReSearch = true
importMode = "Copy"  # Must preserve seeding!

[Lidarr-PrivateTracker.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true  # Look for better encodes
CustomFormatUnmetSearch = true  # Enforce scene/source rules

[Lidarr-PrivateTracker.Torrent]
# Strict file filtering for private trackers
FileExtensionAllowlist = [".flac", ".mp3", ".!qB", ".parts"]
MaximumETA = 172800  # 48 hours (be patient with rare albums)
StalledDelay = 60  # 1 hour stall tolerance
DoNotRemoveSlow = true  # Never remove slow torrents

[Lidarr-PrivateTracker.Torrent.SeedingMode]
MaxUploadRatio = -1  # Never stop based on ratio
MaxSeedingTime = 6220800  # 72 hours minimum
RemoveTorrent = 2  # Remove only after 72 hours

[[Lidarr-PrivateTracker.Torrent.Trackers]]
Name = "RED"
Priority = 10
URI = "https://flacsfor.me/announce"
MaxSeedingTime = 259200  # 72 hours
MaxUploadRatio = 1.0
AddTags = ["RED", "private", "lossless"]
```

---

## Troubleshooting

### Torrents Not Being Processed

**Symptoms:** qBitrr doesn't monitor or manage Lidarr torrents

**Solutions:**

1. ✅ Verify `Category` in qBitrr matches Lidarr's download client category exactly
2. ✅ Check `Managed = true` in config
3. ✅ Ensure Lidarr's qBittorrent download client is tagging torrents
4. ✅ Enable debug logging: `ConsoleLevel = "DEBUG"` in `[Settings]`
5. ✅ Check category-specific log: `~/logs/Lidarr-Music.log`

---

### Searches Not Triggering

**Symptoms:** qBitrr doesn't search for missing albums

**Solutions:**

1. ✅ Verify `SearchMissing = true` in `[Lidarr-Music.EntrySearch]`
2. ✅ Ensure Lidarr has indexers configured and working
3. ✅ Review `SearchRequestsEvery` delay setting
4. ✅ Check Lidarr logs for rate limiting or indexer errors
5. ✅ Verify albums are marked as "Wanted" in Lidarr

---

### Files Not Importing

**Symptoms:** Albums download but don't import to library

**Solutions:**

1. ✅ Check `FileExtensionAllowlist` includes your audio formats
2. ✅ Verify path mapping between qBittorrent and Lidarr (common Docker issue)
3. ✅ Check file permissions on downloaded albums
4. ✅ Look for "Unknown Artist" or "Unknown Album" in Lidarr (metadata issue)
5. ✅ Review Lidarr's import logs for specific errors

---

### Seeding Ratio Not Met

**Symptoms:** Torrents removed before meeting tracker requirements

**Solutions:**

1. ✅ Increase `MaxUploadRatio`:
   ```toml
   MaxUploadRatio = 3.0  # Or higher for strict trackers
   ```

2. ✅ Increase `MaxSeedingTime`:
   ```toml
   MaxSeedingTime = 259200  # 72 hours for RED/OPS
   ```

3. ✅ Change removal condition:
   ```toml
   RemoveTorrent = 4  # Remove only when BOTH ratio AND time met
   ```

4. ✅ Use `Copy` import mode:
   ```toml
   importMode = "Copy"  # Preserves files for seeding
   ```

---

### Connection Failures

**Symptoms:** "Connection refused" or "Unauthorized" errors

**Solutions:**

1. ✅ Test Lidarr API manually:
   ```bash
   curl -H "X-Api-Key: your-api-key" http://localhost:8686/api/v1/system/status
   ```

2. ✅ Verify `URI` is correct (include `http://` or `https://`)
3. ✅ Check `APIKey` is copied correctly (no extra spaces)
4. ✅ Ensure Lidarr is running and accessible
5. ✅ Check firewall rules if Lidarr is on a different machine

---

## Next Steps

- **Configure Radarr:** [Radarr Configuration](radarr.md)
- **Configure Sonarr:** [Sonarr Configuration](sonarr.md)
- **Advanced Torrent Settings:** [Torrent Configuration](../torrents.md)
- **Seeding Configuration:** [Seeding Settings](../seeding.md)
- **Troubleshooting:** [Common Issues](../../troubleshooting/common-issues.md)
