# Advanced Topics

Advanced configuration and usage patterns for experienced qBitrr users.

## Architecture

### System Design

qBitrr uses a multi-process architecture:

- **Main Process** - Orchestrates worker processes
- **WebUI Process** - Serves the web interface
- **Arr Manager Processes** - One per configured Arr instance
- **Background Threads** - For network monitoring, auto-updates, etc.

### Data Flow

```
qBittorrent → qBitrr → Process Torrents → Arr Instance
     ↓                        ↓                  ↓
  Torrent Data        Health Checks        Import to Library
```

### Database

qBitrr uses SQLite for persistent state:

- **Location:** `<config_dir>/qBitManager/qbitrr.db` (config directory is `/config` in Docker, `.config` in the current working directory for native installs, or the path set by `QBITRR_OVERRIDES_DATA_PATH`)
- **Tables:**
  - `downloads` - Tracked torrent information
  - `searches` - Search activity history
  - `expiry` - Entry expiration tracking

**Backup:**
```bash
cp <config_dir>/qBitManager/qbitrr.db <config_dir>/qBitManager/qbitrr.db.backup
```

## Performance Tuning

### Optimize Loop Interval

Balance responsiveness vs. resource usage:

```toml
[Settings]
# How often each Arr instance's event loop runs a full check cycle (seconds)
LoopSleepTimer = 60  # Default: check every 60 seconds

# Reduce for faster response (more CPU)
LoopSleepTimer = 30

# Increase for lower resource usage
LoopSleepTimer = 300
```

!!! note "Actual key"
    The setting is `LoopSleepTimer`, not `CheckInterval`.

### Concurrent Operations

Limit concurrent health checks (if supported by your version; see [Configuration Reference](../configuration/config-file.md) for current Settings keys):

```toml
[Settings]
# Example: adjust based on system resources
# (Key names may vary; run qbitrr --gen-config to see generated options.)
```

### Memory Usage

For systems with limited RAM, reduce logging verbosity or retention if your config supports it (see generated config from `qbitrr --gen-config`). Log files are stored under `<config_dir>/logs/`.

## Custom Tracker Configuration

### Tracker-Specific Settings

Configure behavior per tracker:

```toml
[[Settings.TrackerRules]]
Tracker = "tracker.example.com"
MaxETA = 3600  # 1 hour in seconds
MinRatio = 1.0
MinSeedTime = 86400  # 24 hours
```

### Private Tracker Optimization

For private trackers with strict requirements:

```toml
[[Settings.TrackerRules]]
Tracker = "privatehd.tracker"
MaxETA = 7200  # Allow longer download times
MinRatio = 1.5  # Higher ratio requirement
MinSeedTime = 259200  # 3 days minimum seed
AutoDelete = false  # Never auto-delete
```

## FFprobe Integration

### Media Validation

qBitrr can validate media files before import. The only FFprobe-related setting in the main config is:

```toml
[Settings]
FFprobeAutoUpdate = true
```

The FFprobe binary is stored in the qBitrr data folder (`<config_dir>/qBitManager/`). There is no configurable `FFprobePath` in the current config schema.

**Benefits:**
- Detect corrupt files before import
- Verify codec compatibility
- Check for audio/video tracks
- Validate container format

For advanced FFprobe validation options (e.g. codec checks, minimum duration), see [Health Monitoring](../features/health-monitoring.md). Those options are documented as future reference and are not all implemented in the current version.

## Event Loops

### Understanding the Event Loop

Each Arr instance runs its own event loop:

1. **Check Phase** - Query torrents from qBittorrent
2. **Process Phase** - Evaluate health, check status
3. **Action Phase** - Import, blacklist, or re-search
4. **Sleep Phase** - Wait for next check interval

### Loop Delays

Control delays between operations:

```toml
[[Radarr]]
DelayAfterImport = 60  # Wait 60s after import
DelayAfterSearch = 300  # Wait 5m after search
```

## Multi-Instance Patterns

### Quality Tiers

Separate instances for different quality levels:

```toml
[[Radarr]]
Name = "Radarr-4K"
URI = "http://localhost:7878"
APIKey = "key1"
Category = "movies-4k"
QualityProfile = "Ultra HD"

[[Radarr]]
Name = "Radarr-1080p"
URI = "http://localhost:7879"
APIKey = "key2"
Category = "movies-1080p"
QualityProfile = "HD-1080p"
```

### Content Separation

Different instances for different content types:

```toml
[[Sonarr]]
Name = "Sonarr-TV"
URI = "http://localhost:8989"
Category = "tv"

[[Sonarr]]
Name = "Sonarr-Anime"
URI = "http://localhost:8990"
Category = "anime"
AnimeMode = true  # Special anime handling
```

## Database Maintenance

### Automatic Cleanup

qBitrr automatically cleans old data. See the generated config (`qbitrr --gen-config`) and [Configuration Reference](../configuration/config-file.md) for retention and cleanup options.

### Manual Vacuum

Optimize database size:

```bash
sqlite3 <config_dir>/qBitManager/qbitrr.db "VACUUM;"
```

### Recovery

If database becomes corrupt:

```bash
# qBitrr has automatic recovery
# Check logs for recovery messages
# Or manually delete and regenerate (stops qBitrr first):
rm <config_dir>/qBitManager/qbitrr.db
```

## Network Optimization

### Connection Pooling

qBitrr reuses HTTP connections:

```toml
[Settings]
MaxConnections = 100
ConnectionTimeout = 30
ReadTimeout = 60
```

### Retry Logic

Configure retry behavior:

```toml
[Settings]
MaxRetries = 3
RetryDelay = 5  # Seconds between retries
BackoffMultiplier = 2  # Exponential backoff
```

## Security Hardening

### API Security

Protect the WebUI with authentication:

```toml
[WebUI]
Token = "your-very-secure-random-token-here"
```

Generate a secure token:
```bash
openssl rand -base64 32
```

### Network Security

Bind to specific interfaces in `config.toml`:

```toml
[WebUI]
Host = "127.0.0.1"  # Localhost only
Port = 6969
```

Or for Docker:
```toml
[WebUI]
Host = "0.0.0.0"  # All interfaces (secured by Docker)
Port = 6969
```

## Logging Configuration

### Log Levels

Console output level is set in `[Settings]` (e.g. `ConsoleLevel = "INFO"`). See [Configuration Reference](../configuration/config-file.md) and run `qbitrr --gen-config` for the exact key. Environment override: `QBITRR_SETTINGS_CONSOLE_LEVEL`.

### Log Rotation

Log files are written to `<config_dir>/logs/`. Rotation and retention depend on your setup; see the configuration reference for available options.

### Separate Log Files

Each Arr instance gets its own log file under `<config_dir>/logs/`:

```
<config_dir>/logs/
├── Main.log
├── WebUI.log
├── Radarr-Main.log
├── Sonarr-TV.log
└── Lidarr-Music.log
```

## Custom Scripts

### Pre/Post Hooks

Run custom scripts before or after operations:

```toml
[Settings]
PreImportScript = "/path/to/pre-import.sh"
PostImportScript = "/path/to/post-import.sh"
```

**Script receives:**
- `$1` - Torrent hash
- `$2` - Torrent name
- `$3` - Arr instance name
- `$4` - Media ID

## Monitoring & Alerting

### Health Checks

External monitoring can check:

```bash
# Check if qBitrr is running
curl http://localhost:6969/health

# Expected response:
{"status": "healthy", "version": "5.5.5"}
```

### Metrics

Future feature: Prometheus metrics endpoint

## Experimental Features

### Features Under Development

Check configuration for experimental flags:

```toml
[Settings.Experimental]
FeatureName = true
```

**Warning:** Experimental features may change or be removed in future versions.

## Performance Monitoring

### Built-in Profiling

Enable profiling for performance analysis:

```toml
[Settings]
EnableProfiling = true
ProfilingOutput = "/config/profiling/"
```

### Resource Monitoring

Monitor resource usage:

```bash
# Docker
docker stats qbitrr

# System
htop
ps aux | grep qbitrr
```

## Disaster Recovery

### Backup Strategy

What to backup:

1. **Configuration:** `<config_dir>/config.toml`
2. **Database:** `<config_dir>/qBitManager/qbitrr.db`
3. **Logs (optional):** `<config_dir>/logs/`

### Restore Procedure

1. Stop qBitrr
2. Restore config and database
3. Start qBitrr
4. Verify in logs that restore was successful

## Advanced Troubleshooting

### Enable Debug Logging

Set console log level to DEBUG in config (`Settings.ConsoleLevel`) or use the environment variable `QBITRR_SETTINGS_CONSOLE_LEVEL=DEBUG`.

### Trace Specific Torrents

Follow a torrent through the system:

```bash
grep "torrent_hash" <config_dir>/logs/Main.log
```

### Database Inspection

Query the database directly:

```bash
sqlite3 <config_dir>/qBitManager/qbitrr.db
sqlite> SELECT * FROM downloads WHERE hash = 'torrent_hash';
sqlite> .quit
```

## Contributing

Want to add advanced features?

- See [Development Guide](../development/index.md)
- Review [AGENTS.md](https://github.com/Feramance/qBitrr/blob/master/AGENTS.md)
- Join discussions on [GitHub](https://github.com/Feramance/qBitrr/discussions)

## Further Reading

- [Configuration Reference](../configuration/config-file.md)
- [Troubleshooting](../troubleshooting/index.md)
- [FAQ](../faq.md)
