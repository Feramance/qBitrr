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

- **Location:** `~/config/qBitrr.db`
- **Tables:**
  - `downloads` - Tracked torrent information
  - `searches` - Search activity history
  - `expiry` - Entry expiration tracking

**Backup:**
```bash
cp ~/config/qBitrr.db ~/config/qBitrr.db.backup
```

## Performance Tuning

### Optimize Check Intervals

Balance responsiveness vs. resource usage:

```toml
[Settings]
# How often to check torrents (seconds)
CheckInterval = 60  # Default

# Reduce for faster response (more CPU)
CheckInterval = 30

# Increase for lower resource usage
CheckInterval = 300
```

### Concurrent Operations

Limit concurrent health checks:

```toml
[Settings]
MaxConcurrentChecks = 10  # Adjust based on system resources
```

### Memory Usage

For systems with limited RAM:

```toml
[Settings]
# Reduce log retention
LogRetentionDays = 7

# Limit torrent history
TorrentHistoryDays = 30
```

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

qBitrr can validate media files before import:

```toml
[Settings]
FFprobeAutoUpdate = true
FFprobePath = "/usr/bin/ffprobe"
```

**Benefits:**
- Detect corrupt files before import
- Verify codec compatibility
- Check for audio/video tracks
- Validate container format

### FFprobe Rules

Configure what qBitrr checks:

```toml
[Settings.FFprobe]
CheckVideoCodec = true
CheckAudioCodec = true
CheckDuration = true
MinDuration = 60  # Reject files shorter than 1 minute
```

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

qBitrr automatically cleans old data:

```toml
[Settings]
RetentionDays = 30  # Keep data for 30 days
AutoVacuum = true   # Automatically vacuum database
```

### Manual Vacuum

Optimize database size:

```bash
sqlite3 ~/config/qBitrr.db "VACUUM;"
```

### Recovery

If database becomes corrupt:

```bash
# qBitrr has automatic recovery
# Check logs for recovery messages
# Or manually delete and regenerate:
rm ~/config/qBitrr.db
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
[Settings]
WebUIToken = "your-very-secure-random-token-here"
```

Generate a secure token:
```bash
openssl rand -base64 32
```

### Network Security

Bind to specific interfaces:

```toml
[Settings]
WebUIHost = "127.0.0.1"  # Localhost only
WebUIPort = 6969
```

Or for Docker:
```toml
[Settings]
WebUIHost = "0.0.0.0"  # All interfaces (secured by Docker)
WebUIPort = 6969
```

## Logging Configuration

### Log Levels

```toml
[Settings]
LogLevel = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Levels:**
- **DEBUG** - Everything (very verbose)
- **INFO** - Normal operations
- **WARNING** - Potential issues
- **ERROR** - Errors that don't stop execution
- **CRITICAL** - Fatal errors

### Log Rotation

```toml
[Settings]
LogRotation = true
LogMaxSize = 10485760  # 10 MB
LogBackupCount = 5
```

### Separate Log Files

Each Arr instance gets its own log file:

```
~/config/logs/
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

1. **Configuration:** `~/config/config.toml`
2. **Database:** `~/config/qBitrr.db`
3. **Logs (optional):** `~/config/logs/`

### Restore Procedure

1. Stop qBitrr
2. Restore config and database
3. Start qBitrr
4. Verify in logs that restore was successful

## Advanced Troubleshooting

### Enable Debug Logging

```toml
[Settings]
LogLevel = "DEBUG"
```

### Trace Specific Torrents

Follow a torrent through the system:

```bash
grep "torrent_hash" ~/config/logs/Main.log
```

### Database Inspection

Query the database directly:

```bash
sqlite3 ~/config/qBitrr.db
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
