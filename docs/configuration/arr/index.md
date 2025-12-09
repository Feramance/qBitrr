# Arr Instance Configuration

qBitrr integrates with Radarr, Sonarr, and Lidarr to automate torrent management for your media library.

## Supported Arr Applications

### Radarr (Movies)

[Radarr](radarr.md) manages your movie library.

**Features:**
- Automatic quality upgrades
- Missing movie search
- Custom format support
- Overseerr/Ombi integration

**Configuration:** See [Radarr Configuration Guide](radarr.md)

### Sonarr (TV Shows)

[Sonarr](sonarr.md) manages your TV show library.

**Features:**
- Season and episode monitoring
- Anime support with NCOP/NCED filtering
- Series vs. episode search modes
- Quality upgrades per season

**Configuration:** See [Sonarr Configuration Guide](sonarr.md)

### Lidarr (Music)

[Lidarr](lidarr.md) manages your music library.

**Features:**
- Album and artist monitoring
- Lossless vs. lossy quality handling
- Private music tracker support
- Metadata-driven organization

**Configuration:** See [Lidarr Configuration Guide](lidarr.md)

## General Configuration

All Arr instances share common configuration options:

### Required Settings

```toml
[[Radarr]]  # or [[Sonarr]] or [[Lidarr]]
Name = "Radarr-Main"
URI = "http://localhost:7878"
APIKey = "your-api-key-here"
```

- **Name** - Unique identifier for this instance
- **URI** - Full URL to the Arr application
- **APIKey** - API key from Settings → General in the Arr UI

### Optional Settings

```toml
[[Radarr]]
Name = "Radarr-Main"
URI = "http://localhost:7878"
APIKey = "your-api-key-here"

# Optional settings
Category = "radarr"                    # qBittorrent category
AutoStart = true                       # Start monitoring on launch
HealthCheck = true                     # Enable health monitoring
InstantImport = true                   # Trigger instant imports
SearchMissing = false                  # Auto-search missing media
SearchPeriodDays = 7                   # Days to search for missing
```

## Multiple Instances

You can configure multiple instances of the same Arr type:

```toml
[[Radarr]]
Name = "Radarr-Movies-4K"
URI = "http://localhost:7878"
APIKey = "radarr-api-key"
Category = "radarr-4k"

[[Radarr]]
Name = "Radarr-Movies-1080p"
URI = "http://localhost:7879"
APIKey = "radarr2-api-key"
Category = "radarr-1080p"

[[Sonarr]]
Name = "Sonarr-TV"
URI = "http://localhost:8989"
APIKey = "sonarr-api-key"
Category = "sonarr"

[[Sonarr]]
Name = "Sonarr-Anime"
URI = "http://localhost:8990"
APIKey = "sonarr-anime-api-key"
Category = "sonarr-anime"
```

## Finding Your API Key

To get your API key from any Arr application:

1. Open the Arr web interface
2. Go to **Settings** → **General**
3. Scroll to **Security** section
4. Copy the **API Key**

## Testing Your Configuration

After configuring an Arr instance:

1. **Check Logs** - Look for connection success messages:
   ```
   INFO - Successfully connected to Radarr-Main
   ```

2. **WebUI Test** - Use the configuration test in the WebUI

3. **Trigger Import** - Complete a download and verify it imports to the Arr instance

## Common Patterns

### Docker Network

When running in Docker with a custom network:

```toml
[[Radarr]]
Name = "Radarr"
URI = "http://radarr:7878"  # Use container name
APIKey = "your-api-key"
```

### Remote Instance

For Arr instances on different machines:

```toml
[[Radarr]]
Name = "Radarr-Remote"
URI = "http://192.168.1.100:7878"
APIKey = "your-api-key"
```

### HTTPS Connection

For secure connections:

```toml
[[Radarr]]
Name = "Radarr-Secure"
URI = "https://radarr.yourdomain.com"
APIKey = "your-api-key"
```

## Categories

qBitrr uses qBittorrent categories to track which Arr instance owns each torrent:

- **Default Categories:**
  - `radarr` - For Radarr instances
  - `sonarr` - For Sonarr instances
  - `lidarr` - For Lidarr instances

- **Custom Categories:**
  ```toml
  [[Radarr]]
  Name = "Radarr-4K"
  Category = "movies-4k"  # Custom category
  ```

**Important:** Make sure your Arr instances are configured to use these categories in their download client settings.

## Integration Features

### Instant Imports

qBitrr can trigger imports immediately when downloads complete:

```toml
[[Radarr]]
InstantImport = true
```

Benefits:
- Media available faster
- Reduces time between download and availability
- More responsive to user requests

### Health Monitoring

Monitor and fix stalled or failed downloads:

```toml
[[Radarr]]
HealthCheck = true
```

Features:
- Detect stalled torrents
- Blacklist failed downloads
- Automatic re-search
- FFprobe validation

### Search Automation

Automatically search for missing or wanted media:

```toml
[[Radarr]]
SearchMissing = true
SearchPeriodDays = 7  # Search every 7 days
```

## Troubleshooting

### Connection Issues

**Problem:** qBitrr can't connect to Arr instance

**Solutions:**
- Verify URI is correct and accessible
- Check API key is correct
- Ensure Arr instance is running
- Check firewall rules

See: [Common Issues](../../troubleshooting/common-issues.md#arr-connection-issues)

### Category Mismatch

**Problem:** Downloads not being tracked

**Solutions:**
- Verify category in qBitrr matches Arr download client category
- Check qBittorrent category exists
- Review Arr download client settings

### Import Failures

**Problem:** Downloads complete but don't import

**Solutions:**
- Check path mappings in Arr
- Verify file permissions
- Enable instant import
- Check Arr logs for errors

See: [Troubleshooting Guide](../../troubleshooting/common-issues.md#import-issues)

## Advanced Configuration

### Import Mode

Control how files are handled when imported to your Arr instance:

```toml
[[Radarr]]
ImportMode = "Move"  # or "Copy" or "Hardlink"
```

**Options:**

| Mode | Behavior | Use Case |
|------|----------|----------|
| `Move` | Moves files from download to media folder | Fast, saves disk space |
| `Copy` | Copies files, leaves original | Keep seeding after import |
| `Hardlink` | Creates hardlink to original | Best of both (same filesystem required) |

**Recommendation:**
- **Private trackers** - Use `Copy` or `Hardlink` to maintain seeding
- **Public trackers** - Use `Move` to save disk space
- **Docker** - Use `Hardlink` if download and media paths are on same volume

### Quality Profiles

Map quality profiles for temporary searches:

```toml
[[Lidarr]]
# Accept lower quality temporarily, upgrade later
QualityProfileMappings = {
    "Lossless (FLAC)" = "Any (MP3-320)",
    "High Quality (1080p)" = "Standard (720p)"
}
```

This allows qBitrr to temporarily lower quality requirements to get *something* now, then upgrade when better releases appear.

### Custom Format Enforcement

Enforce minimum custom format scores:

```toml
[[Radarr]]
# Require custom format score of at least 1000
ForceMinimumCustomFormat = true
MinimumCustomFormatScore = 1000
```

**Example use case:**
- You have custom formats for HDR, DTS-HD, etc.
- Each format adds points (e.g., HDR=500, DTS-HD=500)
- Setting minimum to 1000 requires both HDR *and* DTS-HD

### Search Scheduling

Configure when and how often qBitrr searches for missing content:

```toml
[[Radarr]]
SearchMissing = true
SearchRequestsEvery = 300  # Search every 5 minutes
SearchAgainOnSearchCompletion = true  # Restart after each cycle
SearchByYear = true  # Prioritize newest content
SearchInReverse = false  # Start from newest to oldest
```

**Optimization tips:**
- **Large libraries** - Increase `SearchRequestsEvery` to reduce API load
- **New content priority** - Enable `SearchByYear` and disable `SearchInReverse`
- **Rare content** - Enable `SearchAgainOnSearchCompletion` for continuous searching

### Overseerr/Ombi Integration

Integrate with request management systems:

```toml
[[Radarr]]
[Radarr.Overseerr]
OverseerrURL = "http://localhost:5055"
OverseerrAPIKey = "overseerr-api-key"
ApprovedOnly = true  # Only process approved requests
Is4K = false  # Route 4K requests to different instance

[[Radarr-4K]]
[Radarr-4K.Overseerr]
OverseerrURL = "http://localhost:5055"
OverseerrAPIKey = "overseerr-api-key"
ApprovedOnly = true
Is4K = true  # This instance handles 4K requests
```

**Workflow:**
1. User requests movie in Overseerr
2. Admin approves request
3. Overseerr adds to Radarr
4. qBitrr searches for and downloads
5. qBitrr imports to Radarr
6. Overseerr marks request as complete

### Per-Instance Torrent Settings

Override global torrent settings per Arr instance:

```toml
[[Radarr-Movies]]
[Radarr-Movies.Torrent]
MaximumETA = 86400  # 24 hours max
DoNotRemoveSlow = true  # Keep slow but progressing torrents
StalledDelay = 30  # Mark as stalled after 30 seconds
MaximumDeletablePercentage = 0.95  # Don't delete if >95% complete

[Radarr-Movies.Torrent.SeedingMode]
MaxUploadRatio = 2.0  # Seed to 2.0 ratio
MaxSeedingTime = 604800  # Seed for 7 days max
RemoveTorrent = 3  # Remove when ratio OR time met
```

### Search Filters

Filter what content qBitrr searches for:

```toml
[[Sonarr]]
[Sonarr.EntrySearch]
# Only search for monitored content
Monitored = true

# Search for unmonitored content (Sonarr only)
Unmonitored = false

# Prioritize today's releases
PrioritizeTodaysReleases = true

# Search for specials (Sonarr only)
AlsoSearchSpecials = false

# Limit searches per cycle (Sonarr only)
SearchLimit = 50  # Search max 50 episodes per cycle
```

### Logging Configuration

Control logging per Arr instance:

```toml
[[Radarr]]
LogLevel = "DEBUG"  # Override global log level
```

Useful for debugging specific instance issues without flooding logs from other instances.

## Configuration Examples

### Example 1: Basic Setup

Simple single-instance configuration:

```toml
[[Radarr]]
Name = "Radarr-Movies"
URI = "http://localhost:7878"
APIKey = "your-radarr-api-key"
Category = "radarr"
InstantImport = true
HealthCheck = true
```

### Example 2: 4K + 1080p Split

Separate instances for different qualities:

```toml
[[Radarr]]
Name = "Radarr-1080p"
URI = "http://localhost:7878"
APIKey = "radarr-1080p-api-key"
Category = "radarr-1080p"
ImportMode = "Move"

[Radarr-1080p.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true

[[Radarr]]
Name = "Radarr-4K"
URI = "http://localhost:7879"
APIKey = "radarr-4k-api-key"
Category = "radarr-4k"
ImportMode = "Hardlink"

[Radarr-4K.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true
CustomFormatUnmetSearch = true
ForceMinimumCustomFormat = true
```

### Example 3: TV Show with Anime

Separate Sonarr instances for different content types:

```toml
[[Sonarr]]
Name = "Sonarr-TV"
URI = "http://localhost:8989"
APIKey = "sonarr-tv-api-key"
Category = "sonarr-tv"

[Sonarr-TV.EntrySearch]
SearchMissing = true
SearchLimit = 100  # Search up to 100 episodes
AlsoSearchSpecials = false
PrioritizeTodaysReleases = true

[[Sonarr]]
Name = "Sonarr-Anime"
URI = "http://localhost:8990"
APIKey = "sonarr-anime-api-key"
Category = "sonarr-anime"

[Sonarr-Anime.EntrySearch]
SearchMissing = true
AlsoSearchSpecials = true  # Search for OVAs, specials
```

### Example 4: Music Library

Lidarr with temporary quality profiles:

```toml
[[Lidarr]]
Name = "Lidarr-Music"
URI = "http://localhost:8686"
APIKey = "lidarr-api-key"
Category = "lidarr"

[Lidarr-Music.EntrySearch]
SearchMissing = true
UseTempForMissing = true  # Accept lower quality temporarily

# Profile mappings: preferred → temporary
QualityProfileMappings = {
    "Lossless (FLAC)" = "Any (MP3-320)",
    "High Quality (320)" = "Standard (192)"
}

# Reset profiles after 7 days
TempProfileResetTimeoutMinutes = 10080
ForceResetTempProfiles = true
```

### Example 5: Private Tracker Setup

Configuration optimized for private trackers:

```toml
[[Radarr]]
Name = "Radarr-Private"
URI = "http://localhost:7878"
APIKey = "radarr-api-key"
Category = "radarr-private"
ImportMode = "Copy"  # Keep seeding after import

[Radarr-Private.Torrent]
DoNotRemoveSlow = true  # Never remove slow torrents
MaximumDeletablePercentage = 0.99  # Only remove if 99%+ complete
StalledDelay = 60  # Be patient with slow starts

[Radarr-Private.Torrent.SeedingMode]
MaxUploadRatio = -1  # Never stop seeding based on ratio
MaxSeedingTime = 2592000  # Seed for 30 days minimum
RemoveTorrent = 2  # Only remove based on time, not ratio
```

### Example 6: Overseerr Integration

Complete Overseerr setup with 4K routing:

```toml
[[Radarr]]
Name = "Radarr-1080p"
URI = "http://localhost:7878"
APIKey = "radarr-1080p-api-key"
Category = "radarr-1080p"

[Radarr-1080p.Overseerr]
OverseerrURL = "http://localhost:5055"
OverseerrAPIKey = "overseerr-api-key"
ApprovedOnly = true
Is4K = false

[[Radarr]]
Name = "Radarr-4K"
URI = "http://localhost:7879"
APIKey = "radarr-4k-api-key"
Category = "radarr-4k"

[Radarr-4K.Overseerr]
OverseerrURL = "http://localhost:5055"
OverseerrAPIKey = "overseerr-api-key"
ApprovedOnly = true
Is4K = true

[[Sonarr]]
Name = "Sonarr-TV"
URI = "http://localhost:8989"
APIKey = "sonarr-api-key"
Category = "sonarr-tv"

[Sonarr-TV.Overseerr]
OverseerrURL = "http://localhost:5055"
OverseerrAPIKey = "overseerr-api-key"
ApprovedOnly = true
```

## Best Practices

### 1. Use Descriptive Names

```toml
# Good
[[Radarr]]
Name = "Radarr-Movies-4K-Private"

# Bad
[[Radarr]]
Name = "Radarr1"
```

Descriptive names help you identify instances in logs and the WebUI.

### 2. Separate Categories

Always use unique categories for each instance:

```toml
[[Radarr]]
Category = "radarr-4k"  # Unique

[[Radarr]]
Category = "radarr-1080p"  # Different

# Don't do this:
[[Radarr]]
Category = "radarr"  # Same!

[[Radarr]]
Category = "radarr"  # Same! Will cause conflicts!
```

### 3. Match Import Modes to Use Case

| Use Case | Import Mode | Reason |
|----------|-------------|--------|
| Private trackers | `Copy` or `Hardlink` | Keep seeding |
| Public trackers | `Move` | Save disk space |
| Upgrade workflow | `Hardlink` | Keep old version seeding |
| Docker (same volume) | `Hardlink` | Best performance |
| Docker (different volumes) | `Copy` or `Move` | Hardlink won't work |

### 4. Configure Overseerr Per Instance

If using Overseerr, configure it on every relevant Arr instance:

```toml
# Configure on Radarr
[[Radarr]]
[Radarr.Overseerr]
# ... config

# Configure on Sonarr
[[Sonarr]]
[Sonarr.Overseerr]
# ... config

# Don't configure on Lidarr (not supported)
```

### 5. Test Before Full Deployment

1. Start with one Arr instance
2. Verify connection and imports work
3. Add additional instances gradually
4. Monitor logs for errors

### 6. Use Environment Variables for Secrets

Instead of hardcoding API keys:

```toml
[[Radarr]]
APIKey = "${RADARR_API_KEY}"  # Reference environment variable
```

Then set in Docker or systemd:
```bash
export RADARR_API_KEY="your-api-key"
```

## Troubleshooting

### Connection Issues

**Problem:** qBitrr can't connect to Arr instance

**Solutions:**
- Verify URI is correct and accessible from qBitrr container/host
- Check API key is correct (copy/paste from Arr settings)
- Ensure Arr instance is running: `curl http://localhost:7878/api/v3/system/status?apikey=YOUR_KEY`
- Check firewall rules allow traffic
- For Docker, ensure containers are on same network

**Verify connection:**
```bash
# Test Radarr connection
curl -H "X-Api-Key: YOUR_API_KEY" http://localhost:7878/api/v3/system/status

# Should return JSON with version info
```

See: [Common Issues](../../troubleshooting/common-issues.md#arr-connection-issues)

### Category Mismatch

**Problem:** Downloads not being tracked

**Cause:** Category in qBitrr doesn't match Arr download client category

**Solution:**
1. Check qBitrr category: `Category = "radarr"` in config
2. Open Arr → Settings → Download Clients → qBittorrent
3. Set **Category** to match: `radarr`
4. Verify in qBittorrent that category exists

**Verify:**
```bash
# Check categories in qBittorrent
curl "http://qbittorrent:8080/api/v2/torrents/categories"
```

### Import Failures

**Problem:** Downloads complete but don't import

**Common Causes:**

1. **Path Mapping Issues**
   - Arr can't access download path
   - Fix: Configure remote path mapping in Arr
   - See: [Path Mapping Guide](../../troubleshooting/path-mapping.md)

2. **Permission Errors**
   - Arr doesn't have read/write permissions
   - Fix: Set correct ownership: `chown -R 1000:1000 /downloads`

3. **Instant Import Disabled**
   - Arr waits for periodic scan
   - Fix: Enable `InstantImport = true` in qBitrr config

4. **FFprobe Validation Failure**
   - Files fail media validation
   - Fix: Check FFprobe logs, disable validation if needed

See: [Troubleshooting Guide](../../troubleshooting/common-issues.md#import-issues)

### Search Not Working

**Problem:** Automated search doesn't find anything

**Solutions:**

1. **Check search is enabled:**
   ```toml
   [Radarr.EntrySearch]
   SearchMissing = true
   ```

2. **Verify indexers configured in Arr:**
   - Open Arr → Settings → Indexers
   - Ensure at least one indexer is enabled
   - Test indexers with manual search

3. **Check search logs:**
   ```bash
   tail -f ~/config/logs/Radarr-Movies.log | grep -i search
   ```

4. **Adjust search frequency:**
   ```toml
   SearchRequestsEvery = 300  # Increase if too fast
   ```

## Next Steps

Choose your Arr application to configure:

- [Configure Radarr →](radarr.md)
- [Configure Sonarr →](sonarr.md)
- [Configure Lidarr →](lidarr.md)

Or explore related topics:

- [Torrent Configuration](../torrents.md) - Health checks, seeding limits
- [Search Configuration](../search/index.md) - Automated search options
- [Quality Profiles](../quality-profiles.md) - Quality management
- [Seeding Configuration](../seeding.md) - Seeding rules per tracker

---

## Related Documentation

- [Configuration File Reference](../config-file.md) - Complete TOML syntax
- [qBittorrent Configuration](../qbittorrent.md) - qBittorrent setup
- [Overseerr Integration](../search/overseerr.md) - Request management
- [Ombi Integration](../search/ombi.md) - Alternative requests
- [Troubleshooting](../../troubleshooting/index.md) - Common issues
- [Features Overview](../../features/index.md) - What qBitrr can do

Or return to [Configuration Overview](../index.md)
