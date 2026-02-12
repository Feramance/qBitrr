# Seeding Configuration

Configure intelligent seeding management with per-torrent and per-tracker rules for ratio limits, seeding time, and automatic cleanup.

---

## Overview

qBitrr provides granular control over torrent seeding behavior:

- **Global seeding limits** - Apply to all torrents in an Arr category
- **Per-tracker overrides** - Different rules for different trackers
- **Ratio-based removal** - Remove after upload/download ratio reached
- **Time-based removal** - Remove after seeding duration
- **Combined conditions** - Remove when ratio OR/AND time met
- **Rate limiting** - Control upload/download speeds per torrent
- **Dead tracker cleanup** - Remove non-responsive trackers

**Key benefits:**

- Comply with private tracker seeding requirements
- Automatically free up disk space
- Maintain healthy torrent ecosystems
- Optimize bandwidth usage
- Prevent hit-and-runs

---

## Configuration Structure

Seeding is configured in the `[<Arr>-<Name>.Torrent.SeedingMode]` section:

```toml
[Radarr-Movies.Torrent.SeedingMode]
# Global seeding settings for this Arr instance

[[Radarr-Movies.Torrent.Trackers]]
# Per-tracker override for specific trackers
```

---

## Global Seeding Settings

### Complete Example

```toml
[Radarr-Movies.Torrent.SeedingMode]
# Rate limits (KB/s, -1 = unlimited)
DownloadRateLimitPerTorrent = -1
UploadRateLimitPerTorrent = -1

# Seeding limits
MaxUploadRatio = 2.0     # Seed to 2:1 ratio
MaxSeedingTime = 259200  # 72 hours (3 days)

# Removal condition
RemoveTorrent = 3  # Remove when ratio OR time met

# Dead tracker management
RemoveDeadTrackers = false
RemoveTrackerWithMessage = [
  "skipping tracker announce (unreachable)",
  "No such host is known"
]
```

---

### DownloadRateLimitPerTorrent

```toml
DownloadRateLimitPerTorrent = -1
```

**Type:** Integer (KB/s)
**Default:** `-1` (unlimited)

Limit download speed for individual torrents managed by this Arr instance.

**Values:**

- `-1` - Unlimited (default)
- `1024` - 1 MB/s
- `5120` - 5 MB/s
- `10240` - 10 MB/s

**Use cases:**

- Slow connections - prevent one torrent from saturating bandwidth
- Background downloads - limit while torrents complete
- Fair sharing - distribute bandwidth across torrents

**Example:**

```toml
# Limit to 5 MB/s per torrent
DownloadRateLimitPerTorrent = 5120
```

---

### UploadRateLimitPerTorrent

```toml
UploadRateLimitPerTorrent = -1
```

**Type:** Integer (KB/s)
**Default:** `-1` (unlimited)

Limit upload speed for individual torrents.

**Use cases:**

- Preserve download bandwidth
- Meet minimum ratio without excessive upload
- Comply with ISP upload limits

**Example:**

```toml
# Limit to 2 MB/s per torrent
UploadRateLimitPerTorrent = 2048
```

---

### MaxUploadRatio

```toml
MaxUploadRatio = 2.0
```

**Type:** Float
**Default:** `-1` (unlimited)

Maximum upload ratio (uploaded/downloaded) before triggering removal.

**Ratio calculation:**

```
Ratio = Total Uploaded ÷ Total Downloaded
```

**Examples:**

| Ratio | Downloaded | Uploaded | Meaning |
|-------|------------|----------|---------|
| `1.0` | 10 GB | 10 GB | 1:1 ratio |
| `2.0` | 10 GB | 20 GB | 2:1 ratio |
| `0.5` | 10 GB | 5 GB | 0.5:1 ratio |

**Common values:**

- `-1` - Never remove based on ratio (unlimited seeding)
- `1.0` - Minimum for most private trackers
- `1.5` - Generous seeding
- `2.0` - Very generous
- `5.0` - Maximum for some trackers

!!! warning "Private Tracker Requirements"
    Many private trackers **require** minimum ratios:

    - Common: 1.0 (1:1 ratio)
    - Strict: 1.5 or higher
    - New users: May have higher requirements

    Check your tracker's rules before setting this value!

---

### MaxSeedingTime

```toml
MaxSeedingTime = 259200  # 72 hours
```

**Type:** Integer (seconds)
**Default:** `-1` (unlimited)

Maximum seeding duration before triggering removal.

**Time conversions:**

| Duration | Seconds | Config Value |
|----------|---------|--------------|
| 1 hour | 3,600 | `3600` |
| 6 hours | 21,600 | `21600` |
| 12 hours | 43,200 | `43200` |
| 1 day | 86,400 | `86400` |
| 3 days | 259,200 | `259200` |
| 1 week | 604,800 | `604800` |
| 2 weeks | 1,209,600 | `1209600` |
| 30 days | 2,592,000 | `2592000` |
| 90 days | 7,776,000 | `7776000` |

**Use cases:**

- **Public trackers:** 1-3 days sufficient
- **Private trackers:** Often require 48-72 hours minimum
- **Music trackers:** May require weeks or months
- **Long-term seeding:** 30+ days for rare content

**Example:**

```toml
# Seed for 7 days
MaxSeedingTime = 604800
```

---

### RemoveTorrent

```toml
RemoveTorrent = 3
```

**Type:** Integer
**Default:** `-1` (never remove)

Controls when qBitrr removes torrents based on seeding limits.

**Options:**

| Value | Condition | Behavior |
|-------|-----------|----------|
| `-1` | **Never** | Keep seeding indefinitely |
| `1` | **Ratio** | Remove when `MaxUploadRatio` reached |
| `2` | **Time** | Remove when `MaxSeedingTime` reached |
| `3` | **OR** | Remove when EITHER ratio OR time met |
| `4` | **AND** | Remove when BOTH ratio AND time met |

**Comparison:**

```toml
# Example: MaxUploadRatio = 2.0, MaxSeedingTime = 259200 (3 days)
```

| RemoveTorrent | After 1 day @ 3.0 ratio | After 5 days @ 0.5 ratio | After 4 days @ 2.5 ratio |
|---------------|------------------------|-------------------------|-------------------------|
| `-1` | Keep | Keep | Keep |
| `1` (ratio only) | Remove (ratio met) | Keep (ratio not met) | Remove (ratio met) |
| `2` (time only) | Keep (time not met) | Remove (time met) | Remove (time met) |
| `3` (OR) | Remove (ratio met) | Remove (time met) | Remove (either met) |
| `4` (AND) | Keep (time not met) | Keep (ratio not met) | Remove (both met) |

**Recommendations:**

| Use Case | RemoveTorrent | MaxUploadRatio | MaxSeedingTime |
|----------|---------------|----------------|----------------|
| **Public trackers** | `3` (OR) | `1.0` | `86400` (1 day) |
| **Private trackers** | `4` (AND) | `1.5` | `259200` (3 days) |
| **Long-term seeding** | `-1` (Never) | `-1` | `-1` |
| **Ratio priority** | `1` (Ratio) | `2.0` | `-1` |
| **Time priority** | `2` (Time) | `-1` | `604800` (7 days) |

---

### RemoveDeadTrackers

```toml
RemoveDeadTrackers = false
```

**Type:** Boolean
**Default:** `false`

Automatically remove tracker entries that return errors.

When `true`:

- qBitrr monitors tracker announce responses
- Removes trackers matching `RemoveTrackerWithMessage` errors
- Keeps working trackers

**Use cases:**

- Tracker shutdown/migration
- Clean up dead backup trackers
- Maintain healthy tracker lists

!!! warning "Private Tracker Caution"
    Be careful with private trackers:

    - Some trackers have temporary outages
    - Removing tracker may violate rules
    - May lose credit for seeding time

    **Recommendation:** Keep `false` for private trackers.

---

### RemoveTrackerWithMessage

```toml
RemoveTrackerWithMessage = [
  "skipping tracker announce (unreachable)",
  "No such host is known",
  "unsupported URL protocol",
  "info hash is not authorized with this tracker"
]
```

**Type:** Array of strings
**Default:** See example above

Error messages that trigger tracker removal (when `RemoveDeadTrackers = true`).

**Common error messages:**

```toml
RemoveTrackerWithMessage = [
  # Network errors
  "skipping tracker announce (unreachable)",
  "No such host is known",
  "timed out",

  # DNS errors
  "Could not resolve host",
  "temporary failure in name resolution",

  # Authentication errors
  "info hash is not authorized with this tracker",
  "unregistered torrent",

  # Protocol errors
  "unsupported URL protocol"
]
```

---

## Per-Tracker Configuration

Override global settings for specific trackers using `[[<Arr>-<Name>.Torrent.Trackers]]` sections.

### Complete Tracker Example

```toml
[[Radarr-Movies.Torrent.Trackers]]
# Tracker identification
Name = "BeyondHD"
Priority = 10
URI = "https://tracker.beyond-hd.me/announce"

# Seeding requirements
MaxUploadRatio = 1.0
MaxSeedingTime = 432000  # 5 days

# Rate limits
DownloadRateLimit = -1
UploadRateLimit = 5242880  # 5 MB/s

# Tracker management
AddTrackerIfMissing = false
RemoveIfExists = false
SuperSeedMode = false

# Tagging
AddTags = ["BeyondHD", "private"]
```

---

### Tracker Fields

#### Name

```toml
Name = "BeyondHD"
```

**Type:** String
**Purpose:** Human-readable identifier (for your reference only)

Not used by qBitrr currently, but may be used for logging/reporting in future versions.

---

#### Priority

```toml
Priority = 10
```

**Type:** Integer
**Default:** `0`

When a torrent has multiple trackers, the tracker with the **highest priority** has its settings applied.

**Example:**

```toml
[[Radarr-Movies.Torrent.Trackers]]
Name = "BeyondHD"
Priority = 10  # Highest priority
MaxUploadRatio = 1.0

[[Radarr-Movies.Torrent.Trackers]]
Name = "Public Fallback"
Priority = 5  # Lower priority
MaxUploadRatio = 2.0

# Torrent with both trackers → Uses BeyondHD settings (ratio 1.0)
```

---

#### URI

```toml
URI = "https://tracker.beyond-hd.me/announce"
```

**Type:** String (tracker announce URL)
**Required:** Yes

The tracker announce URL as it appears in qBittorrent.

**How to find:**

1. In qBittorrent, select a torrent
2. Right-click → Properties → Trackers tab
3. Copy the announce URL exactly

**Must match exactly** (including protocol, subdomain, path, passkey).

---

#### MaximumETA

```toml
MaximumETA = 18000  # 5 hours
```

**Type:** Integer (seconds)
**Default:** Inherits from `[<Arr>-<Name>.Torrent].MaximumETA`

Override the maximum allowed download ETA for this tracker.

**Use cases:**

- Slow private trackers (rare content) - higher ETA
- Fast public trackers - lower ETA
- Freeleech torrents - higher tolerance

---

#### MaxUploadRatio / MaxSeedingTime

Override global seeding limits for this tracker:

```toml
MaxUploadRatio = 1.5
MaxSeedingTime = 604800  # 7 days
```

**Example - Different tracker requirements:**

```toml
# Private tracker - strict requirements
[[Radarr-4K.Torrent.Trackers]]
Name = "PassThePopcorn"
URI = "https://please.passthepopcorn.me:2443/announce"
Priority = 10
MaxUploadRatio = 1.0
MaxSeedingTime = 259200  # 72 hours minimum

# Public tracker - lenient
[[Radarr-4K.Torrent.Trackers]]
Name = "YTS"
URI = "udp://open.stealth.si:80/announce"
Priority = 5
MaxUploadRatio = 0.5
MaxSeedingTime = 86400  # 24 hours
```

---

#### DownloadRateLimit / UploadRateLimit

Per-tracker rate limiting:

```toml
DownloadRateLimit = -1
UploadRateLimit = 2097152  # 2 MB/s
```

---

#### AddTrackerIfMissing

```toml
AddTrackerIfMissing = false
```

**Type:** Boolean
**Default:** `false`

Automatically add this tracker to torrents that don't have it.

When `true`:

- qBitrr checks if torrent has this tracker
- If missing, adds tracker announce URL
- Useful for adding backup trackers

**Use case:** Add public tracker backups to private torrents.

!!! warning "Tracker Rules"
    Some private trackers prohibit adding external trackers. Check rules before enabling.

---

#### RemoveIfExists

```toml
RemoveIfExists = false
```

**Type:** Boolean
**Default:** `false`

Remove this tracker from any torrent that has it.

**Use case:** Remove old/shutdown trackers automatically.

---

#### SuperSeedMode

```toml
SuperSeedMode = false
```

**Type:** Boolean
**Default:** `false`

Enable qBittorrent's "super seeding" mode for torrents with this tracker.

**What is super seeding?**

- Optimized for initial seeding
- Sends different pieces to each peer
- More efficient for new torrents
- Slower overall, but better distribution

**Recommendation:** `true` only for initial seeds on slow trackers.

---

#### AddTags

```toml
AddTags = ["private", "BeyondHD", "keep-seeding"]
```

**Type:** Array of strings
**Default:** `[]` (empty)

Automatically add tags to torrents with this tracker.

**Use cases:**

- Organize by tracker
- Mark private vs public
- Flag for special handling
- Integration with other tools

---

## Configuration Examples

### Example 1: Public Tracker (Generous Seeding)

```toml
[Radarr-Movies.Torrent.SeedingMode]
DownloadRateLimitPerTorrent = -1
UploadRateLimitPerTorrent = -1
MaxUploadRatio = 2.0     # Seed to 2:1
MaxSeedingTime = 604800  # 7 days
RemoveTorrent = 3        # Remove when either met
RemoveDeadTrackers = true
```

**Result:** Seeds to 2:1 ratio or 7 days, whichever comes first.

---

### Example 2: Private Tracker (Strict Requirements)

```toml
[Radarr-Private.Torrent.SeedingMode]
MaxUploadRatio = 1.5
MaxSeedingTime = 432000  # 5 days
RemoveTorrent = 4        # Remove only when BOTH met
RemoveDeadTrackers = false  # Keep all trackers
```

**Result:** Must seed to 1.5:1 ratio AND 5 days before removal.

---

### Example 3: Mixed Setup with Per-Tracker Rules

```toml
[Radarr-Movies.Torrent.SeedingMode]
# Global defaults (conservative)
MaxUploadRatio = 1.0
MaxSeedingTime = 259200  # 3 days
RemoveTorrent = 3

# Private tracker - higher requirements
[[Radarr-Movies.Torrent.Trackers]]
Name = "BeyondHD"
Priority = 10
URI = "https://tracker.beyond-hd.me/announce"
MaxUploadRatio = 1.5
MaxSeedingTime = 432000  # 5 days
AddTags = ["private", "BeyondHD"]

# Public tracker - lenient
[[Radarr-Movies.Torrent.Trackers]]
Name = "YTS"
Priority = 5
URI = "udp://open.stealth.si:80/announce"
MaxUploadRatio = 0.5
MaxSeedingTime = 86400  # 1 day
AddTags = ["public", "YTS"]
```

---

### Example 4: Music Tracker (Long-term Seeding)

```toml
[Lidarr-Music.Torrent.SeedingMode]
MaxUploadRatio = 1.0
MaxSeedingTime = 6220800  # 72 hours minimum (RED/OPS requirement)
RemoveTorrent = 2  # Remove based on time only
RemoveDeadTrackers = false

[[Lidarr-Music.Torrent.Trackers]]
Name = "RED"
Priority = 10
URI = "https://flacsfor.me/announce"
MaxUploadRatio = -1  # Never remove based on ratio
MaxSeedingTime = 259200  # 72 hours
AddTags = ["RED", "music", "lossless"]
```

---

### Example 5: Freeleech Torrents (Seed Forever)

```toml
[Radarr-Freeleech.Torrent.SeedingMode]
MaxUploadRatio = -1  # Never remove
MaxSeedingTime = -1  # Never remove
RemoveTorrent = -1   # Never remove

[[Radarr-Freeleech.Torrent.Trackers]]
Name = "Freeleech Tracker"
URI = "https://tracker.example.com/announce"
Priority = 10
AddTags = ["freeleech", "permanent-seed"]
```

---

## Import Mode and Seeding

The `importMode` setting affects seeding behavior:

### Copy Mode (Recommended for Seeding)

```toml
[Radarr-Movies]
importMode = "Copy"
```

**What happens:**

1. Download completes
2. Arr **copies** files to library
3. Original files remain in download folder
4. Torrent continues seeding

**Pros:**

- Preserves torrents for seeding
- Meets tracker requirements
- Maintains ratio

**Cons:**

- Uses more disk space (2x)
- Slower import (copy operation)

---

### Move Mode (Frees Disk Space)

```toml
[Radarr-Movies]
importMode = "Move"
```

**What happens:**

1. Download completes
2. Arr **moves** files to library
3. Torrent can no longer seed (files missing)
4. qBitrr removes torrent

**Pros:**

- Saves disk space
- Faster import (move operation)

**Cons:**

- Can't seed after import
- May violate private tracker rules
- Hit-and-run risk

!!! danger "Private Tracker Warning"
    Using `importMode = "Move"` on private trackers can result in:

    - Hit-and-run warnings
    - Ratio penalties
    - Account suspension
    - Permanent ban

    **Always use `importMode = "Copy"` for private trackers.**

---

## Tracker-Specific Recommendations

### Private Movie Trackers

**PassThePopcorn, BeyondHD, etc.**

```toml
MaxUploadRatio = 1.0  # Minimum required
MaxSeedingTime = 432000  # 5 days
RemoveTorrent = 4  # Both conditions
importMode = "Copy"
```

---

### Private TV Trackers

**BTN, MTV, etc.**

```toml
MaxUploadRatio = 1.0
MaxSeedingTime = 259200  # 3 days
RemoveTorrent = 4
importMode = "Copy"
```

---

### Private Music Trackers

**RED, OPS, APL**

```toml
MaxUploadRatio = 1.0
MaxSeedingTime = 259200  # 72 hours minimum
RemoveTorrent = 2  # Time-based (ratio harder for music)
importMode = "Copy"
```

---

### Public Trackers

**RARBG, YTS, EZTV, etc.**

```toml
MaxUploadRatio = 1.0  # Be generous
MaxSeedingTime = 86400  # 1 day
RemoveTorrent = 3  # Either condition
importMode = "Move"  # Save space
```

---

## Monitoring Seeding

### WebUI

View seeding status:

1. Open `http://localhost:6969/ui`
2. Navigate to Arr tab
3. Check torrent status and ratio

---

### qBittorrent

Check seeding in qBittorrent:

1. Open qBittorrent WebUI
2. View ratio, upload speed, seeding time
3. Sort by ratio or seeding time

---

### Logs

Monitor seeding removal in logs:

```bash
tail -f ~/logs/Radarr-Movies.log | grep -i "remov\|seed\|ratio"
```

**Example log output:**

```
2025-11-27 14:00:00 - INFO - Torrent reached 2.0 ratio: The Matrix (1999)
2025-11-27 14:00:05 - INFO - Removing torrent (ratio met): The Matrix (1999)
2025-11-27 14:00:10 - INFO - Torrent seeded for 7 days: Inception (2010)
2025-11-27 14:00:15 - INFO - Removing torrent (time met): Inception (2010)
```

---

## Troubleshooting

### Torrents Not Removed

**Symptom:** Torrents continue seeding past limits

**Solutions:**

1. **Check RemoveTorrent setting:**
   ```toml
   RemoveTorrent = 3  # Must not be -1
   ```

2. **Verify limits are set:**
   ```toml
   MaxUploadRatio = 2.0  # Must not be -1
   MaxSeedingTime = 604800  # Must not be -1
   ```

3. **Check import mode:**
   ```toml
   importMode = "Copy"  # Files must exist for seeding
   ```

4. **Review logs:**
   ```bash
   grep -i "seed\|ratio" ~/logs/Radarr-Movies.log
   ```

---

### Removed Too Early

**Symptom:** Torrents removed before meeting requirements

**Solutions:**

1. **Increase limits:**
   ```toml
   MaxUploadRatio = 2.0  # Up from 1.0
   MaxSeedingTime = 604800  # 7 days instead of 3
   ```

2. **Change removal condition:**
   ```toml
   RemoveTorrent = 4  # Require BOTH (was 3 = OR)
   ```

3. **Check per-tracker overrides:**
   - Ensure tracker settings aren't overriding globals
   - Verify tracker URI matches exactly

---

### Hit-and-Run Warnings

**Symptom:** Private tracker warnings about insufficient seeding

**Solutions:**

1. **Use Copy mode:**
   ```toml
   importMode = "Copy"
   ```

2. **Increase seeding requirements:**
   ```toml
   MaxUploadRatio = 1.5  # Higher than tracker minimum
   MaxSeedingTime = 432000  # 5 days
   RemoveTorrent = 4  # Require both
   ```

3. **Never remove:**
   ```toml
   RemoveTorrent = -1  # Seed forever
   ```

4. **Check tracker rules:**
   - Review minimum seeding requirements
   - Set qBitrr limits above minimums

---

## Best Practices

### 1. Know Your Tracker Requirements

Before configuring:

- Read tracker rules carefully
- Note minimum ratio requirements
- Note minimum seeding time
- Check hit-and-run policies

---

### 2. Set Limits Above Minimums

```toml
# Tracker requires 1.0 ratio and 48 hours
# Set qBitrr to 1.5 ratio and 72 hours for safety margin

MaxUploadRatio = 1.5
MaxSeedingTime = 259200  # 72 hours
```

---

### 3. Use Copy Mode for Private Trackers

```toml
[Radarr-Private]
importMode = "Copy"
```

Never risk hit-and-runs.

---

### 4. Test with Public Trackers First

- Configure public tracker seeding first
- Monitor for a few days
- Verify removal works correctly
- Then apply to private trackers

---

### 5. Monitor Disk Space

With `importMode = "Copy"`:

```toml
[Settings]
FreeSpace = "100G"  # Ensure adequate free space
AutoPauseResume = true
```

---

### 6. Use Per-Tracker Rules for Mixed Setups

Different trackers have different requirements - configure accordingly:

```toml
# Conservative global default
[Radarr-Movies.Torrent.SeedingMode]
MaxUploadRatio = 2.0
MaxSeedingTime = 604800

# Specific tracker overrides
[[Radarr-Movies.Torrent.Trackers]]
Name = "Private1"
MaxUploadRatio = 1.5
MaxSeedingTime = 432000

[[Radarr-Movies.Torrent.Trackers]]
Name = "Public1"
MaxUploadRatio = 1.0
MaxSeedingTime = 86400
```

---

## Hit and Run Protection

Hit and Run (HnR) is a rule enforced by private trackers: after downloading a torrent you **must** seed it back to a minimum ratio (typically 1:1) or for a minimum period of time (often 4-10 days depending on user class). Violating HnR rules can result in warnings, ratio penalties, or permanent bans.

qBitrr's HnR protection acts as a **safety layer** on top of the existing seeding limits. Even when `RemoveTorrent` conditions are met, HnR protection will block removal until the tracker's seeding obligations are satisfied.

---

### How It Works

- **Full downloads** (100% complete): HnR clears when **either** `MinSeedRatio` OR `MinSeedingTimeDays` is met
- **Partial downloads** (>=10% but <100%): HnR clears only when `HitAndRunPartialSeedRatio` is met (time does not apply)
- **Downloads <10%**: Not subject to HnR (most trackers don't count these)
- **`TrackerUpdateBuffer`**: Extra seconds subtracted from seeding time to account for tracker stats lag (~30 min behind the client)

When `HitAndRunMode = false` (default), behavior is identical to previous versions.

---

### Global HnR Settings

Add to `[<Arr>-<Name>.Torrent.SeedingMode]`:

```toml
[Radarr-Movies.Torrent.SeedingMode]
# Enable HnR protection
HitAndRunMode = false

# Minimum ratio before removal allowed
MinSeedRatio = 1.0

# Minimum seeding days (0 = ratio only)
MinSeedingTimeDays = 0

# Ratio for partial downloads (>=10% but <100%)
HitAndRunPartialSeedRatio = 1.0

# Extra seconds to wait after meeting criteria (tracker lag buffer)
TrackerUpdateBuffer = 0
```

#### HitAndRunMode

**Type:** Boolean
**Default:** `false`

Master switch for HnR protection. When `true`, torrents will not be removed until HnR obligations are met, regardless of `RemoveTorrent` settings.

#### MinSeedRatio

**Type:** Float
**Default:** `1.0`

Minimum upload ratio required to clear HnR. A value of `1.0` means you must upload at least as much as you downloaded.

#### MinSeedingTimeDays

**Type:** Integer (days)
**Default:** `0` (disabled)

Minimum number of days to seed before HnR clears. Set to `0` to use ratio-only protection.

For full downloads, **either** ratio OR time clears the obligation (whichever comes first).

#### HitAndRunPartialSeedRatio

**Type:** Float
**Default:** `1.0`

Ratio required for partial downloads (downloaded >=10% but <100%). Most trackers require partial downloads to reach a 1:1 ratio — time does not apply.

#### TrackerUpdateBuffer

**Type:** Integer (seconds)
**Default:** `0`

Extra seconds to wait after meeting HnR criteria before allowing removal. Tracker statistics typically lag 15-30 minutes behind the client. Setting this to `1800` (30 minutes) provides a safety margin.

---

### Per-Tracker HnR Settings

Override global HnR settings for specific trackers:

```toml
[[Radarr-Movies.Torrent.Trackers]]
Name = "TorrentLeech"
URI = "https://tracker.torrentleech.org/announce"
Priority = 10

# Per-tracker HnR overrides
HitAndRunMode = true
MinSeedRatio = 1.0
MinSeedingTimeDays = 10
HitAndRunPartialSeedRatio = 1.0
TrackerUpdateBuffer = 1800
```

Per-tracker settings take priority over global settings when the tracker is the most important (highest priority) tracker on the torrent.

---

### TorrentLeech Example

TorrentLeech enforces HnR with seeding time requirements based on user class:

| User Class | Minimum Seed Time |
|------------|-------------------|
| Member | 10 days |
| Power User | 8 days |
| Elite | 7 days |
| VIP | 6 days |
| Legend | 4 days |

**Conservative setup** (for Member class):

```toml
[Radarr-Movies.Torrent.SeedingMode]
MaxUploadRatio = 2.0
MaxSeedingTime = 1296000   # 15 days
RemoveTorrent = 3          # Remove when either met

# HnR protection
HitAndRunMode = true
MinSeedRatio = 1.0
MinSeedingTimeDays = 10    # Member class requirement
HitAndRunPartialSeedRatio = 1.0
TrackerUpdateBuffer = 1800 # 30 min buffer for tracker lag
```

**Aggressive setup** (for Legend class):

```toml
[Radarr-Movies.Torrent.SeedingMode]
MaxUploadRatio = 1.5
MaxSeedingTime = 604800    # 7 days
RemoveTorrent = 3

HitAndRunMode = true
MinSeedRatio = 1.0
MinSeedingTimeDays = 4     # Legend class requirement
TrackerUpdateBuffer = 1800
```

**Per-tracker mixed setup** (different trackers, different rules):

```toml
[Radarr-Movies.Torrent.SeedingMode]
MaxUploadRatio = 2.0
MaxSeedingTime = 1296000
RemoveTorrent = 3

# Global HnR defaults
HitAndRunMode = true
MinSeedRatio = 1.0
MinSeedingTimeDays = 10

# TorrentLeech - strict HnR
[[Radarr-Movies.Torrent.Trackers]]
Name = "TorrentLeech"
URI = "https://tracker.torrentleech.org/announce"
Priority = 10
HitAndRunMode = true
MinSeedRatio = 1.0
MinSeedingTimeDays = 10
TrackerUpdateBuffer = 1800

# IPTorrents - shorter requirement
[[Radarr-Movies.Torrent.Trackers]]
Name = "IPTorrents"
URI = "https://tracker.iptorrents.com/announce"
Priority = 8
HitAndRunMode = true
MinSeedRatio = 1.0
MinSeedingTimeDays = 4
TrackerUpdateBuffer = 1800

# Public tracker - no HnR
[[Radarr-Movies.Torrent.Trackers]]
Name = "Public"
URI = "udp://open.stealth.si:80/announce"
Priority = 1
HitAndRunMode = false
```

---

## See Also

- [qBittorrent Configuration](qbittorrent.md) - qBittorrent setup
- [Instant Imports](../features/instant-imports.md) - Import behavior and seeding
- [Radarr Configuration](arr/radarr.md) - Radarr instance setup
- [Sonarr Configuration](arr/sonarr.md) - Sonarr instance setup
- [Lidarr Configuration](arr/lidarr.md) - Lidarr instance setup
- [Config File Reference](config-file.md) - All configuration options
