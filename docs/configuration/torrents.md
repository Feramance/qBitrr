# Torrent Configuration

qBitrr provides granular control over how torrents are processed, filtered, and managed for each Arr instance. This page covers all torrent-specific settings available in the `[<Arr>-<Name>.Torrent]` section.

---

## Overview

Torrent settings control:

- **File filtering** - Which files to download/ignore based on extensions, names, folders
- **Processing timing** - When to start processing torrents
- **Completion thresholds** - Percentage and ETA requirements
- **Stalled torrent handling** - Detection and removal of stuck downloads
- **Seeding rules** - Per-instance seeding configurations
- **Tracker-specific overrides** - Custom settings per tracker

**Configuration section:**

```toml
[Radarr-Movies.Torrent]
# All torrent settings for this Arr instance
```

---

## File Filtering

### CaseSensitiveMatches

**Type:** Boolean
**Default:** `false`

Enable case-sensitive regex matching for file/folder exclusions.

```toml
CaseSensitiveMatches = false
```

**Examples:**

| Value | Pattern | Matches |
|-------|---------|---------|
| `false` | `\bsample\b` | `Sample`, `SAMPLE`, `sample` |
| `true` | `\bsample\b` | `sample` only |

---

### FolderExclusionRegex

**Type:** List of regex patterns
**Default:** Common extras/sample folders

Exclude entire folders matching these regex patterns from processing.

**Default patterns:**

```toml
FolderExclusionRegex = [
    "\\bextras?\\b",        # Extras, Extra
    "\\bfeaturettes?\\b",   # Featurettes
    "\\bsamples?\\b",       # Samples, Sample
    "\\bscreens?\\b",       # Screens, Screenshots
    "\\bnc(ed|op)?(\\d+)?\\b"  # NCOP, NCED (anime)
]
```

**Anime-specific additions:**

```toml
FolderExclusionRegex = [
    "\\bextras?\\b",
    "\\bsamples?\\b",
    "\\bspecials?\\b",     # Specials (anime)
    "\\bova\\b",           # OVA folders
    "\\bnc(ed|op)?(\\d+)?\\b"
]
```

**Custom examples:**

```toml
# Exclude bonus content
FolderExclusionRegex = [
    "\\bbehind.the.scenes\\b",
    "\\bdeleted.scenes\\b",
    "\\binterviews?\\b"
]
```

!!! warning "Regex Escaping"
    Backslashes must be doubled in TOML strings: `\\b` not `\b`

---

### FileNameExclusionRegex

**Type:** List of regex patterns
**Default:** Common junk file patterns

Exclude individual files matching these regex patterns.

**Default patterns:**

```toml
FileNameExclusionRegex = [
    "\\bncop\\d+?\\b",          # Anime NCOP files
    "\\bnced\\d+?\\b",          # Anime NCED files
    "\\bsample\\b",             # Sample videos
    "brarbg.com\\b",            # RARBG ads
    "\\btrailer\\b",            # Trailers
    "music video",              # Music videos
    "comandotorrents.com"       # Torrent site ads
]
```

**Custom examples:**

```toml
# Block specific release groups
FileNameExclusionRegex = [
    "\\bYIFY\\b",
    "\\bRAR?BG\\b",
    "\\b1337x\\b"
]

# Block unwanted audio tracks
FileNameExclusionRegex = [
    "\\.commentary\\.",
    "\\.ac3\\.audio\\."
]
```

---

### FileExtensionAllowlist

**Type:** List of file extensions
**Default:** Common video/subtitle extensions

Only allow files with these extensions. Empty list = allow all.

**Default:**

```toml
FileExtensionAllowlist = [
    ".mp4", ".mkv",      # Video files
    ".sub", ".ass", ".srt",  # Subtitles
    ".!qB", ".parts"     # Incomplete download markers
]
```

**Custom examples:**

```toml
# Only MKV and MP4 (no subtitles)
FileExtensionAllowlist = [".mkv", ".mp4"]

# Include audio for music
FileExtensionAllowlist = [".flac", ".mp3", ".m4a", ".alac"]

# Allow all files (empty list)
FileExtensionAllowlist = []
```

!!! tip "Performance"
    Using an allowlist reduces bandwidth by not downloading unwanted files (NFO, images, etc.)

---

### AutoDelete

**Type:** Boolean
**Default:** `false`

Automatically delete files that don't match the allowlist or match exclusion patterns.

```toml
AutoDelete = false
```

**When enabled:**

- Non-playable files (`.exe`, `.txt`, `.nfo`) are deleted immediately
- Files matching `FileNameExclusionRegex` are deleted
- Files not in `FileExtensionAllowlist` are deleted

**Recommendation:** `false` to review files manually before deletion

---

## Processing Timing

### IgnoreTorrentsYoungerThan

**Type:** Integer (seconds)
**Default:** `180` (3 minutes)

Wait this many seconds after torrent is added before processing.

```toml
IgnoreTorrentsYoungerThan = 300  # 5 minutes
```

**Why delay processing?**

- **Metadata downloads:** Torrents need time to fetch file lists
- **Fast starts:** Avoid processing before files begin downloading
- **Duplicate prevention:** Give Arr time to process the download

**Examples:**

```toml
# Fast processing (risky)
IgnoreTorrentsYoungerThan = 60  # 1 minute

# Standard (recommended)
IgnoreTorrentsYoungerThan = 180  # 3 minutes

# Conservative (slow tracker/large torrents)
IgnoreTorrentsYoungerThan = 600  # 10 minutes
```

!!! warning "Too Low Values"
    Values below 60 seconds can cause duplicate imports or missing files.

---

### MaximumETA

**Type:** Integer (seconds) or `-1` (disabled)
**Default:** `-1` (disabled)

Maximum allowed estimated time to completion. Torrents exceeding this are removed.

```toml
MaximumETA = 3600  # 1 hour
```

**How it works:**

- qBitrr calculates remaining time based on download speed
- If ETA > MaximumETA, torrent is **marked for removal**
- **Removal happens AFTER download completes** (`amount_left == 0`)
- Prevents seeding slow torrents, but allows them to finish downloading

!!! warning "Removal Timing"

    **MaximumETA is enforced AFTER completion, not during download.**

    1. During download: qBitrr calculates ETA
    2. If ETA > MaximumETA: Torrent marked for removal
    3. **Removal happens**: After `amount_left == 0` (download complete)

    **Why:** Deleting incomplete downloads wastes bandwidth. qBitrr waits for completion, then removes if it took too long.

    **Example:**
    ```
    MaximumETA = 3600  # 1 hour

    Torrent downloads in 2 hours (exceeds limit)
    → qBitrr allows it to finish downloading
    → After completion, removes torrent (won't seed)
    ```

**Examples:**

```toml
# Remove torrents taking over 2 hours
MaximumETA = 7200

# Remove torrents taking over 30 minutes
MaximumETA = 1800

# Disabled (no ETA limit)
MaximumETA = -1
```

!!! info "Tracker Override"
    If `MaximumETA` is set on a tracker basis (`[<Arr>.<Torrent>.Trackers.<TrackerName>]`), that value overrides this global setting.

---

### MaximumDeletablePercentage

**Type:** Float (0.0-1.0)
**Default:** `0.99` (99%)

Don't delete torrents that have downloaded more than this percentage.

```toml
MaximumDeletablePercentage = 0.95  # 95%
```

**Why use this?**

Prevents accidentally deleting nearly-complete torrents due to temporary stalls or tracker issues.

**Examples:**

```toml
# Very conservative (only delete if < 50% complete)
MaximumDeletablePercentage = 0.50

# Aggressive (delete even at 99%)
MaximumDeletablePercentage = 0.99

# Never auto-delete based on completion
MaximumDeletablePercentage = 0.01  # Only delete if < 1% complete
```

---

## Stalled Torrent Handling

### DoNotRemoveSlow

**Type:** Boolean
**Default:** `true`

Don't remove slow torrents automatically.

```toml
DoNotRemoveSlow = true
```

**When enabled:**

- Slow torrents are **not** automatically deleted
- Manual intervention required for stuck downloads

**When disabled:**

- Slow/stalled torrents are removed based on `StalledDelay`

**Recommendation:** `true` to avoid removing torrents on slow but working trackers

---

### StalledDelay

**Type:** Integer (minutes) or `-1` (disabled)
**Default:** `15` minutes

Maximum time a torrent can remain stalled before removal.

```toml
StalledDelay = 30  # 30 minutes
```

**Stalled conditions:**

- No download/upload progress
- No seeds available
- Tracker offline

**Values:**

- `-1` = Disabled (never remove stalled torrents)
- `0` = Infinite (mark as stalled but never remove)
- `> 0` = Minutes until removal

**Examples:**

```toml
# Quick removal (5 minutes)
StalledDelay = 5

# Patient (1 hour)
StalledDelay = 60

# Never remove
StalledDelay = -1
```

---

### ReSearchStalled

**Type:** Boolean
**Default:** `false`

Trigger a new search **before** removing a stalled torrent.

```toml
ReSearchStalled = true
```

**When enabled:**

1. Torrent detected as stalled
2. qBitrr triggers Arr to search for alternatives
3. Original stalled torrent is removed

**When disabled:**

1. Torrent detected as stalled
2. Torrent is removed
3. Arr's natural retry logic handles re-search

**Recommendation:** `false` to avoid aggressive re-searching; let Arr handle retries

---

## Seeding Configuration

Seeding settings are configured in the `[<Arr>.Torrent.SeedingMode]` subsection. See **[Seeding Configuration](seeding.md)** for complete details.

**Quick reference:**

```toml
[Radarr-Movies.Torrent.SeedingMode]
DownloadRateLimitPerTorrent = -1        # KB/s download limit (-1 = unlimited)
UploadRateLimitPerTorrent = -1          # KB/s upload limit (-1 = unlimited)
MaxUploadRatio = 2.0                    # Remove after 2:1 ratio
MaxSeedingTime = 43200                  # Remove after 12 hours (seconds)
RemoveTorrent = -1                      # Additional removal delay (seconds)
RemoveDeadTrackers = false              # Remove torrents with dead trackers
RemoveTrackerWithMessage = []           # Remove if tracker message matches
```

**See also:** [Seeding Configuration Guide](seeding.md)

---

## Tracker-Specific Configuration

Override global torrent settings on a per-tracker basis.

### Tracker Configuration Structure

```toml
[Radarr-Movies.Torrent.Trackers]

[[Radarr-Movies.Torrent.Trackers.PassThePopcorn]]
UseTracker = true
MaximumETA = 1800                       # 30 minutes (overrides global)
DownloadRateLimit = -1
UploadRateLimit = -1
MaxUploadRatio = 3.0                    # Seed to 3:1
MaxSeedingTime = 86400                  # 24 hours
RemoveTorrent = -1
TrackerURLInclude = ["passthepopcorn.me"]
```

### Tracker Settings

#### UseTracker

**Type:** Boolean
**Default:** `true`

Enable tracking for this tracker configuration.

```toml
UseTracker = true
```

---

#### TrackerURLInclude

**Type:** List of strings
**Required:** Yes

URL patterns to match for this tracker.

```toml
TrackerURLInclude = ["passthepopcorn.me", "ptp.me"]
```

**Matching:**

- Partial match against tracker announce URL
- Case-insensitive

---

#### MaximumETA (per-tracker)

**Type:** Integer (seconds) or `-1`
**Default:** Inherits global setting

Override global `MaximumETA` for this tracker.

```toml
MaximumETA = 3600  # 1 hour for this tracker only
```

---

#### Download/Upload Rate Limits (per-tracker)

**Type:** Integer (KB/s) or `-1` (unlimited)
**Default:** Inherits global setting

```toml
DownloadRateLimit = 5000  # 5 MB/s
UploadRateLimit = 2000    # 2 MB/s
```

---

#### Seeding Limits (per-tracker)

**Type:** Float (ratio) or Integer (seconds)
**Default:** Inherits global setting

```toml
MaxUploadRatio = 3.0      # Seed to 3:1
MaxSeedingTime = 172800   # 48 hours
```

---

## Complete Configuration Examples

### Example 1: Movies (Radarr)

```toml
[Radarr-Movies.Torrent]
CaseSensitiveMatches = false

# Exclude extras and samples
FolderExclusionRegex = [
    "\\bextras?\\b",
    "\\bfeaturettes?\\b",
    "\\bsamples?\\b",
    "\\bbehind.the.scenes\\b"
]

# Exclude junk files
FileNameExclusionRegex = [
    "\\bsample\\b",
    "\\btrailer\\b",
    "brarbg.com\\b"
]

# Only video/subtitle files
FileExtensionAllowlist = [".mkv", ".mp4", ".srt", ".ass"]

AutoDelete = false
IgnoreTorrentsYoungerThan = 180  # 3 minutes
MaximumETA = 7200  # 2 hours
MaximumDeletablePercentage = 0.95  # 95%

DoNotRemoveSlow = true
StalledDelay = 30  # 30 minutes
ReSearchStalled = false

[Radarr-Movies.Torrent.SeedingMode]
MaxUploadRatio = 2.0
MaxSeedingTime = 43200  # 12 hours
```

---

### Example 2: TV (Sonarr)

```toml
[Sonarr-TV.Torrent]
CaseSensitiveMatches = false

FolderExclusionRegex = [
    "\\bextras?\\b",
    "\\bsamples?\\b"
]

FileNameExclusionRegex = [
    "\\bsample\\b",
    "\\btrailer\\b"
]

FileExtensionAllowlist = [".mkv", ".mp4", ".srt"]

AutoDelete = false
IgnoreTorrentsYoungerThan = 120  # 2 minutes (faster for new episodes)
MaximumETA = 3600  # 1 hour
MaximumDeletablePercentage = 0.99

DoNotRemoveSlow = false  # Remove slow downloads for TV
StalledDelay = 15  # 15 minutes
ReSearchStalled = true  # Re-search quickly for new episodes

[Sonarr-TV.Torrent.SeedingMode]
MaxUploadRatio = 1.5
MaxSeedingTime = 21600  # 6 hours
```

---

### Example 3: Anime (Sonarr)

```toml
[Sonarr-Anime.Torrent]
CaseSensitiveMatches = false

# Anime-specific exclusions
FolderExclusionRegex = [
    "\\bextras?\\b",
    "\\bsamples?\\b",
    "\\bspecials?\\b",
    "\\bova\\b",
    "\\bnc(ed|op)?(\\d+)?\\b"
]

FileNameExclusionRegex = [
    "\\bncop\\d+?\\b",
    "\\bnced\\d+?\\b",
    "\\bsample\\b"
]

FileExtensionAllowlist = [".mkv", ".mp4", ".ass", ".srt"]

AutoDelete = false
IgnoreTorrentsYoungerThan = 300  # 5 minutes (larger files)
MaximumETA = -1  # Disabled (anime can be slow)
MaximumDeletablePercentage = 0.99

DoNotRemoveSlow = true  # Keep slow anime torrents
StalledDelay = 60  # 1 hour
ReSearchStalled = false

[Sonarr-Anime.Torrent.SeedingMode]
MaxUploadRatio = 2.0
MaxSeedingTime = 86400  # 24 hours
```

---

### Example 4: Music (Lidarr)

```toml
[Lidarr-Music.Torrent]
CaseSensitiveMatches = false

FolderExclusionRegex = [
    "\\bscans?\\b",
    "\\bartwork\\b"
]

FileNameExclusionRegex = [
    "\\bcover\\b",
    "\\.log$",
    "\\.cue$"
]

# Allow audio + cue/log for verification
FileExtensionAllowlist = [
    ".flac", ".mp3", ".m4a",
    ".cue", ".log"
]

AutoDelete = false
IgnoreTorrentsYoungerThan = 180
MaximumETA = -1  # No limit for music
MaximumDeletablePercentage = 0.95

DoNotRemoveSlow = true
StalledDelay = -1  # Never remove (music trackers can be slow)
ReSearchStalled = false

[Lidarr-Music.Torrent.SeedingMode]
MaxUploadRatio = 3.0  # Higher ratio for music
MaxSeedingTime = 172800  # 48 hours
```

---

### Example 5: Private Tracker with Custom Rules

```toml
[Radarr-Movies.Torrent]
IgnoreTorrentsYoungerThan = 180
MaximumETA = -1  # Disabled globally
MaximumDeletablePercentage = 0.99
DoNotRemoveSlow = true
StalledDelay = -1

[Radarr-Movies.Torrent.SeedingMode]
MaxUploadRatio = -1  # No global ratio limit
MaxSeedingTime = -1  # No global time limit

# Tracker-specific overrides
[[Radarr-Movies.Torrent.Trackers.PassThePopcorn]]
UseTracker = true
TrackerURLInclude = ["passthepopcorn.me"]
MaximumETA = 1800  # 30 minutes (fast tracker)
MaxUploadRatio = 3.0
MaxSeedingTime = 86400  # 24 hours
DownloadRateLimit = -1
UploadRateLimit = -1

[[Radarr-Movies.Torrent.Trackers.BroadcasTheNet]]
UseTracker = true
TrackerURLInclude = ["broadcasthe.net", "landof.tv"]
MaximumETA = 3600  # 1 hour
MaxUploadRatio = 2.0
MaxSeedingTime = 172800  # 48 hours (more patient)
```

---

## Troubleshooting

### Files Not Downloading

**Symptom:** Torrent added but no files download

**Check:**

1. **FileExtensionAllowlist:**
   ```toml
   # If too restrictive, no files match
   FileExtensionAllowlist = [".mkv"]  # Won't download .mp4 files
   ```

2. **FolderExclusionRegex:**
   ```toml
   # Too broad, excludes everything
   FolderExclusionRegex = [".*"]  # BAD: Matches all folders
   ```

**Solution:** Widen allowlist or reduce exclusions

---

### Torrents Deleted Too Quickly

**Symptom:** Torrents removed before completing

**Check:**

1. **MaximumETA:**
   ```toml
   MaximumETA = 600  # 10 minutes (too aggressive)
   ```

2. **StalledDelay:**
   ```toml
   StalledDelay = 5  # 5 minutes (too quick)
   ```

**Solution:** Increase timeouts or disable with `-1`

---

### Stalled Torrents Not Removed

**Symptom:** Stuck torrents never delete

**Check:**

1. **StalledDelay disabled:**
   ```toml
   StalledDelay = -1  # Never removes stalled torrents
   ```

2. **DoNotRemoveSlow enabled:**
   ```toml
   DoNotRemoveSlow = true  # Keeps slow torrents
   ```

**Solution:** Enable stalled detection:
```toml
DoNotRemoveSlow = false
StalledDelay = 30  # 30 minutes
```

---

### Regex Not Matching

**Symptom:** Exclusion patterns don't work

**Check escaping:**

```toml
# Incorrect
FolderExclusionRegex = ["\bsample\b"]  # Single backslash

# Correct
FolderExclusionRegex = ["\\bsample\\b"]  # Double backslash
```

**Test regex:**

Use online regex testers with test strings:

- Test string: `Sample.mkv`
- Pattern: `\\bsample\\b` (case-insensitive)
- Should match: ✅

---

## Best Practices

### 1. Start Conservative

```toml
# Safe defaults
AutoDelete = false  # Manual review first
MaximumETA = -1  # No automatic removal
StalledDelay = -1  # Manual intervention
```

Test for 1-2 weeks, then enable automated removal.

---

### 2. Use Allowlists for Bandwidth Savings

```toml
# Only download video files
FileExtensionAllowlist = [".mkv", ".mp4"]
```

Saves bandwidth by not downloading NFO, artwork, etc.

---

### 3. Adjust IgnoreTorrentsYoungerThan by Content Type

```toml
# TV (fast processing for new episodes)
IgnoreTorrentsYoungerThan = 120  # 2 minutes

# Movies (larger files, more patient)
IgnoreTorrentsYoungerThan = 300  # 5 minutes

# Music/Anime (very patient)
IgnoreTorrentsYoungerThan = 600  # 10 minutes
```

---

### 4. Use Tracker-Specific Overrides

```toml
# Slow public tracker
[[Radarr-Movies.Torrent.Trackers.YTS]]
UseTracker = true
TrackerURLInclude = ["yts.mx"]
MaximumETA = -1  # Disable ETA limit
MaxSeedingTime = 3600  # Seed for 1 hour only

# Fast private tracker
[[Radarr-Movies.Torrent.Trackers.PrivateHD]]
UseTracker = true
TrackerURLInclude = ["privatehd.to"]
MaximumETA = 1800  # 30 minutes
MaxSeedingTime = 86400  # Seed for 24 hours
```

---

### 5. Monitor Exclusions Impact

Check logs for excluded files:

```
[DEBUG] Excluded folder: /data/torrents/movie-2023/Extras/
[DEBUG] Excluded file: sample.mkv (matches: \\bsample\\b)
```

Adjust patterns if too many valid files are excluded.

---

## Related Documentation

- **[Seeding Configuration](seeding.md)** - Complete seeding and ratio management
- **[qBittorrent Configuration](qbittorrent.md)** - qBittorrent connection setup
- **[Health Monitoring](../features/health-monitoring.md)** - Torrent health checks

---

## Summary

- **File filtering** - Control which files are downloaded with allowlists and exclusions
- **Processing timing** - Delay processing with `IgnoreTorrentsYoungerThan`
- **Completion thresholds** - Set `MaximumETA` and `MaximumDeletablePercentage`
- **Stalled handling** - Configure `StalledDelay` and `DoNotRemoveSlow`
- **Tracker overrides** - Custom settings per tracker for optimal performance
- **Start conservative** and enable automation after testing
