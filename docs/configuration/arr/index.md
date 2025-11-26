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

## Next Steps

Choose your Arr application to configure:

- [Configure Radarr →](radarr.md)
- [Configure Sonarr →](sonarr.md)
- [Configure Lidarr →](lidarr.md)

Or return to [Configuration Overview](../index.md)
