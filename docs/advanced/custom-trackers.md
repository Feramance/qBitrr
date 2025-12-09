# Custom Tracker Configuration

Configure qBitrr behavior based on specific torrent trackers, enabling tracker-specific rules for seeding, health checks, and cleanup.

## Overview

Different torrent trackers have different requirements:

- **Private trackers** - Strict ratio requirements, longer seed times
- **Public trackers** - Minimal requirements, quick cleanup acceptable
- **Specialized trackers** - Unique rules (e.g., Anime trackers, 4K content)

qBitrr allows you to define tracker-specific rules that override global settings.

## Configuration

### Basic Tracker Rule

```toml
[[Settings.TrackerRules]]
Tracker = "tracker.example.com"    # Tracker domain (matches any protocol)
MinRatio = 1.0                     # Minimum seed ratio before deletion
MinSeedTime = 86400                # Minimum seed time in seconds (24 hours)
MaxETA = 3600                      # Maximum ETA before marking stalled (1 hour)
AutoDelete = true                  # Allow automatic deletion when seeding goals met
Priority = 10                      # Rule priority (higher = higher priority)
```

### Tracker Matching

**Tracker domain extraction:**

qBitrr automatically extracts tracker domains from torrent tracker URLs:

```
Tracker URL: http://tracker.example.com:8080/announce
Matched Domain: tracker.example.com

Tracker URL: https://private.tracker.net:443/abc123/announce
Matched Domain: private.tracker.net
```

**Wildcard matching:**

```toml
[[Settings.TrackerRules]]
Tracker = "*.privatehd.to"  # Matches all subdomains
```

**Multiple trackers (OR logic):**

```toml
[[Settings.TrackerRules]]
Tracker = ["tracker1.com", "tracker2.net"]  # Matches either tracker
MinRatio = 1.5
```

## Common Tracker Profiles

### Private Tracker (Strict Rules)

```toml
[[Settings.TrackerRules]]
Tracker = "privatehd.tracker"
MinRatio = 1.5              # Must seed to 150%
MinSeedTime = 259200        # 3 days minimum
MaxETA = 7200               # Allow 2 hours for slow downloads
AutoDelete = false          # Never auto-delete
CheckInterval = 60          # Check every minute
IgnoreClientRules = false   # Respect tracker client rules
```

### Public Tracker (Permissive)

```toml
[[Settings.TrackerRules]]
Tracker = "public.tracker.org"
MinRatio = 0.1              # Minimal seeding required
MinSeedTime = 3600          # 1 hour minimum
MaxETA = 1800               # Mark stalled after 30 mins
AutoDelete = true           # Delete when done
Priority = 5                # Lower priority than private trackers
```

### Specialized: Anime Tracker

```toml
[[Settings.TrackerRules]]
Tracker = "anime.tracker.moe"
MinRatio = 1.0
MinSeedTime = 172800        # 2 days
PreferredCodec = "h265"     # HEVC preferred for anime
RequireSubtitles = true     # Must have subtitle tracks
MaxFileSize = 5368709120    # 5 GB max (for 1080p anime)
```

### Specialized: 4K/Remux Tracker

```toml
[[Settings.TrackerRules]]
Tracker = "4k.private.tracker"
MinRatio = 2.0              # High ratio for large files
MinSeedTime = 604800        # 7 days minimum
MaxETA = 14400              # 4 hours (large files take time)
MinFileSize = 21474836480   # 20 GB minimum (ensures quality)
RequireHDR = true           # Must have HDR metadata
```

## Advanced Configuration

### Rule Priority

When a torrent matches multiple rules, the highest priority rule wins:

```toml
# Default rule for all trackers
[[Settings.TrackerRules]]
Tracker = "*"               # Wildcard matches all
MinRatio = 0.5
MinSeedTime = 7200
Priority = 1                # Lowest priority

# Specific rule overrides default
[[Settings.TrackerRules]]
Tracker = "privatehd.to"
MinRatio = 1.5
MinSeedTime = 259200
Priority = 10               # Higher priority, takes precedence
```

### Conditional Rules

Apply rules based on additional criteria:

```toml
[[Settings.TrackerRules]]
Tracker = "tracker.example.com"
MinRatio = 1.0

# Only apply to specific categories
OnlyCategories = ["movies-4k", "tv-4k"]

# Only apply to specific Arr instances
OnlyArrInstances = ["Radarr-4K"]

# Only apply to files larger than 10 GB
MinFileSize = 10737418240
```

### Health Check Customization

```toml
[[Settings.TrackerRules]]
Tracker = "slow.tracker.net"

# Extend thresholds for slow tracker
MaxETA = 14400              # 4 hours
StallTimeout = 3600         # 1 hour of no progress before stalling
MaxRetries = 5              # More retry attempts

# Disable certain health checks
SkipETACheck = false
SkipStalledCheck = false
SkipTrackerCheck = true     # Don't check if tracker is down
```

### Cleanup Customization

```toml
[[Settings.TrackerRules]]
Tracker = "private.tracker.net"

# Custom cleanup rules
DeleteAfterImport = false           # Keep seeding after import
DeleteWhenRatioReached = true       # Delete when ratio goal met
DeleteWhenSeedTimeReached = false   # Ignore seed time for deletion
KeepEvenIfFailed = true             # Don't delete failed torrents

# Grace period before deletion
DeletionGracePeriod = 3600          # Wait 1 hour after goals met
```

## Tracker-Specific Features

### Freeleech Detection

Some trackers offer freeleech (downloads don't count toward ratio):

```toml
[[Settings.TrackerRules]]
Tracker = "privatehd.to"
DetectFreeleech = true      # Parse tracker response for FL
FreeleechMinRatio = 0.5     # Lower ratio requirement for FL
FreeleechMinSeedTime = 43200 # 12 hours for FL (vs. 3 days normally)
```

### Hit-and-Run Protection

Prevent hit-and-run violations:

```toml
[[Settings.TrackerRules]]
Tracker = "private.tracker.net"
HitAndRunProtection = true
HitAndRunMinSeedTime = 259200  # 3 days minimum
HitAndRunMinRatio = 1.0        # 100% minimum

# Don't delete until both conditions met
RequireBothConditions = true
```

### Bonus Point Systems

Some trackers award bonus points for seeding:

```toml
[[Settings.TrackerRules]]
Tracker = "bonus.tracker.net"
MaximizeBonusPoints = true         # Keep seeding longer for bonus
BonusPointThreshold = 1000         # Stop seeding when 1000 points earned
BonusPointsPerHour = 10            # Estimated points per hour
```

## Use Cases

### Multi-Tracker Torrents

Torrents with multiple trackers use the **most restrictive** rule:

```toml
# Torrent has trackers: privatehd.to + public.tracker.org

[[Settings.TrackerRules]]
Tracker = "privatehd.to"
MinRatio = 1.5              # This rule will apply...
MinSeedTime = 259200

[[Settings.TrackerRules]]
Tracker = "public.tracker.org"
MinRatio = 0.1              # ...because privatehd.to has stricter requirements
MinSeedTime = 3600
```

**Override behavior:**

```toml
[Settings]
MultiTrackerBehavior = "most_restrictive"  # Default
# MultiTrackerBehavior = "least_restrictive"
# MultiTrackerBehavior = "first_match"
# MultiTrackerBehavior = "highest_priority"
```

### Tracker-Specific Categories

Route tracker torrents to specific qBittorrent categories:

```toml
[[Settings.TrackerRules]]
Tracker = "anime.tracker.moe"
ForceCategory = "anime"     # Override Arr-assigned category
```

### Dynamic Tracker Detection

qBitrr can auto-detect private vs. public trackers:

```toml
[Settings]
AutoDetectPrivateTrackers = true

# Default rules for auto-detected private trackers
[Settings.PrivateTrackerDefaults]
MinRatio = 1.0
MinSeedTime = 86400
AutoDelete = false

# Default rules for public trackers
[Settings.PublicTrackerDefaults]
MinRatio = 0.1
MinSeedTime = 3600
AutoDelete = true
```

## Debugging

### Enable Tracker Logging

```toml
[Settings]
LogLevel = "DEBUG"
LogTrackerMatching = true
```

**Output:**

```
[DEBUG] Torrent abc123: Detected trackers: privatehd.to, backup.tracker.net
[DEBUG] Matched rule for privatehd.to: MinRatio=1.5, MinSeedTime=259200
[DEBUG] Matched rule for backup.tracker.net: MinRatio=1.0, MinSeedTime=86400
[DEBUG] Using most restrictive rule: privatehd.to
```

### Test Tracker Rules

```bash
# Dry run mode to test rules without making changes
qbitrr --dry-run --test-tracker-rules
```

**Output:**

```
Torrent: Big.Movie.2024.2160p.mkv
├─ Tracker: privatehd.to
├─ Matched Rule: PrivateHD
├─ MinRatio: 1.5 (current: 0.8) ❌
├─ MinSeedTime: 259200s (current: 43200s) ❌
└─ Action: Continue seeding
```

## Common Issues

### Rule Not Applying

**Symptom:** Tracker rule doesn't seem to apply to torrents

**Causes:**
1. Tracker domain mismatch
2. Lower priority than another rule
3. Conditional criteria not met

**Debug:**

```toml
[Settings]
LogTrackerMatching = true
```

Check logs for tracker matching details.

### Unexpected Deletion

**Symptom:** Torrents deleted despite tracker rule saying not to

**Causes:**
1. Global `AutoDelete` overriding tracker rule
2. Multiple tracker rules with different settings
3. Manual deletion in qBittorrent

**Solution:**

```toml
[[Settings.TrackerRules]]
Tracker = "privatehd.to"
AutoDelete = false
OverrideGlobalSettings = true  # Force this rule to take precedence
```

## Best Practices

1. **Start with conservative rules** - Easier to relax than tighten
2. **Use priorities** - Ensure specific rules override general ones
3. **Test with dry run** - Verify rules before applying
4. **Monitor ratio** - Check qBittorrent stats to ensure compliance
5. **Document rules** - Add comments explaining why each rule exists

**Example with comments:**

```toml
[[Settings.TrackerRules]]
# PrivateHD requires 1.5 ratio and 3 days seed time
# Source: https://privatehd.to/rules
Tracker = "privatehd.to"
MinRatio = 1.5
MinSeedTime = 259200
AutoDelete = false
Priority = 10
```

## Tracker Rule Templates

### General Private Tracker

```toml
[[Settings.TrackerRules]]
Tracker = "your.private.tracker"
MinRatio = 1.0
MinSeedTime = 172800        # 2 days
MaxETA = 7200
AutoDelete = false
Priority = 10
```

### General Public Tracker

```toml
[[Settings.TrackerRules]]
Tracker = "your.public.tracker"
MinRatio = 0.1
MinSeedTime = 3600          # 1 hour
MaxETA = 1800
AutoDelete = true
Priority = 5
```

### Ratio-Based Tracker

```toml
[[Settings.TrackerRules]]
Tracker = "ratio.tracker.net"
MinRatio = 2.0              # Focus on ratio, not time
MinSeedTime = 0
DeleteWhenRatioReached = true
DeleteWhenSeedTimeReached = false
```

### Time-Based Tracker

```toml
[[Settings.TrackerRules]]
Tracker = "time.tracker.net"
MinRatio = 0.0              # Focus on time, not ratio
MinSeedTime = 604800        # 7 days
DeleteWhenRatioReached = false
DeleteWhenSeedTimeReached = true
```

## Future Enhancements

**Planned for v6.0:**

- **Tracker API Integration** - Query tracker for requirements
- **Dynamic Rules** - Adjust based on account stats
- **Rule Import/Export** - Share rules with community
- **Tracker Presets** - Built-in rules for popular trackers
- **Per-Torrent Overrides** - Manual overrides in WebUI

## Related Documentation

- [Configuration: Seeding](../configuration/seeding.md) - Global seeding configuration
- [Configuration: Torrents](../configuration/torrents.md) - Torrent handling
- [Features: Automated Search](../features/automated-search.md) - Search behavior
- [Advanced: Performance](performance.md) - Optimize tracker operations
