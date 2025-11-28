# Debug Logging

Comprehensive guide to enabling, reading, and analyzing qBitrr logs for effective troubleshooting.

---

## Overview

qBitrr provides extensive logging capabilities to help diagnose issues:

- **Structured Logging**: Organized by module and severity
- **Multiple Log Levels**: From CRITICAL to TRACE
- **Per-Instance Logs**: Separate log files for each Arr instance
- **Automatic Rotation**: Logs rotate at 10 MB, keeping 5 backups
- **Real-Time Monitoring**: View logs via WebUI or command line

---

## Log Levels

### Available Levels (Least to Most Verbose)

| Level | Use Case | What It Shows |
|-------|----------|---------------|
| `CRITICAL` | Production | Only fatal errors that stop qBitrr |
| `ERROR` | Production | Errors that cause operations to fail |
| `WARNING` | Production | Potential issues, degraded functionality |
| `NOTICE` | Production | Important operational events |
| `INFO` | Default | Normal operations, status changes |
| `DEBUG` | Troubleshooting | Detailed execution flow, API calls |
| `TRACE` | Development | Extremely verbose, every function call |

### Recommended Levels

**Production (Normal Operation)**:
```toml
[Settings]
ConsoleLevel = "INFO"
Logging = true
```

**Troubleshooting**:
```toml
ConsoleLevel = "DEBUG"
```

**Deep Debugging** (Very verbose, use sparingly):
```toml
ConsoleLevel = "TRACE"
```

---

## Enabling Debug Logging

### Method 1: Configuration File (Persistent)

Edit `config.toml`:

```toml
[Settings]
ConsoleLevel = "DEBUG"  # Change from INFO
Logging = true           # Ensure logging is enabled
```

Restart qBitrr:

=== "Docker"
    ```bash
    docker restart qbitrr
    ```

=== "Systemd"
    ```bash
    sudo systemctl restart qbitrr
    ```

=== "pip/Native"
    ```bash
    # Stop qBitrr (Ctrl+C if running in foreground)
    # Then restart:
    qbitrr
    ```

### Method 2: WebUI (Temporary, No Restart)

1. Navigate to **Processes** page in WebUI
2. Click **Change Log Level** button
3. Select **DEBUG** from dropdown
4. Click **Apply**

**Note**: Changes made via WebUI are **not persistent** and reset after restart.

### Method 3: API Call (Temporary)

```bash
curl -X POST http://localhost:6969/web/loglevel \
  -H "Content-Type: application/json" \
  -d '{"level": "DEBUG"}'
```

---

## Log File Locations

### Native Installation

```
~/config/logs/
├── Main.log              # Core qBitrr operations
├── Main.log.1            # Previous rotation (backup)
├── Main.log.2            # Older backup
├── Main.log.3
├── Main.log.4
├── Main.log.5            # Oldest backup (deleted on next rotation)
├── WebUI.log             # WebUI server logs
├── Radarr-4K.log         # Per-instance logs
├── Sonarr-TV.log
└── Lidarr.log
```

### Docker Installation

```
/config/logs/  (inside container)
# Mapped to host path via volume:
# docker run -v /host/path:/config
```

**Access Docker logs**:
```bash
# Container logs (stdout/stderr)
docker logs qbitrr

# File-based logs (persistent)
docker exec qbitrr ls -lh /config/logs
docker exec qbitrr tail -f /config/logs/Main.log
```

---

## Log File Structure

### Log Entry Format

```
2025-11-27 12:34:56,789 | INFO     | qBitrr.arr.Radarr-4K | Processing torrent: Movie.2024.1080p.mkv [hash123abc]
```

**Components**:

1. **Timestamp**: `2025-11-27 12:34:56,789` (YYYY-MM-DD HH:MM:SS,milliseconds)
2. **Level**: `INFO` / `DEBUG` / `WARNING` / `ERROR` / `TRACE`
3. **Logger**: `qBitrr.arr.Radarr-4K` (module.submodule.instance)
4. **Message**: Descriptive log message

### Logger Hierarchy

```
qBitrr                    # Root logger
├── qBitrr.arr            # Arr management
│   ├── qBitrr.arr.Radarr-4K
│   ├── qBitrr.arr.Sonarr-TV
│   └── qBitrr.arr.Lidarr
├── qBitrr.webui          # WebUI server
├── qBitrr.config         # Configuration loading
├── qBitrr.ffprobe        # Media validation
└── qBitrr.auto_update    # Auto-update system
```

---

## Viewing Logs

### Via WebUI

1. Navigate to **Logs** page
2. Select log file from dropdown
3. View real-time updates with auto-scroll
4. Download log files for offline analysis

**Features**:
- ANSI color highlighting
- Auto-scroll toggle
- Auto-refresh (every 5 seconds)
- Download logs as `.log` files

### Command Line (Real-Time)

=== "Docker"
    ```bash
    # Container stdout/stderr
    docker logs -f qbitrr

    # Specific log file
    docker exec qbitrr tail -f /config/logs/Main.log

    # Multiple files
    docker exec qbitrr tail -f /config/logs/*.log
    ```

=== "Systemd"
    ```bash
    # Via journalctl (stdout/stderr)
    journalctl -u qbitrr -f

    # Specific log file
    tail -f ~/config/logs/Main.log

    # Last 100 lines
    tail -n 100 ~/config/logs/Main.log
    ```

=== "pip/Native"
    ```bash
    # Real-time follow
    tail -f ~/config/logs/Main.log

    # All logs combined
    tail -f ~/config/logs/*.log
    ```

### Command Line (Historical)

```bash
# View last 100 lines
tail -n 100 ~/config/logs/Main.log

# View entire file
cat ~/config/logs/Main.log

# Search for specific term
grep -i "error" ~/config/logs/Main.log

# Search across all logs
grep -i "connection refused" ~/config/logs/*.log

# Search with context (5 lines before/after)
grep -C 5 -i "failed" ~/config/logs/Main.log
```

---

## Log Analysis Techniques

### Finding Errors

```bash
# All errors in Main.log
grep "ERROR" ~/config/logs/Main.log

# All critical errors
grep "CRITICAL" ~/config/logs/Main.log

# Errors and warnings
grep -E "ERROR|WARNING" ~/config/logs/Main.log

# Count errors by type
grep "ERROR" ~/config/logs/Main.log | sort | uniq -c | sort -rn
```

### Tracing Specific Operations

**Example: Track specific torrent**

```bash
# Follow torrent by hash
grep "hash123abc" ~/config/logs/*.log

# Follow torrent by name
grep "Movie.2024.1080p" ~/config/logs/*.log

# With timestamps
grep "Movie.2024.1080p" ~/config/logs/*.log | sort
```

**Example: Track Arr instance operations**

```bash
# All Radarr-4K operations
tail -f ~/config/logs/Radarr-4K.log

# Search operations only
grep -i "search" ~/config/logs/Radarr-4K.log

# Import operations only
grep -i "import" ~/config/logs/Radarr-4K.log
```

### Analyzing Connection Issues

```bash
# Find connection errors
grep -i "connection" ~/config/logs/Main.log | grep -i "error\|refused\|timeout"

# API call failures
grep -i "api" ~/config/logs/*.log | grep -i "failed\|error"

# Authentication issues
grep -i "auth" ~/config/logs/*.log | grep -i "failed\|invalid"
```

### Monitoring Performance

```bash
# Find slow operations (if logged)
grep -i "slow\|timeout\|exceeded" ~/config/logs/*.log

# Database operations
grep -i "database\|sqlite" ~/config/logs/*.log

# Loop timing
grep -i "loop.*completed\|loop.*duration" ~/config/logs/*.log
```

---

## Common Log Patterns

### Successful Operations

#### Torrent Processing
```
INFO | qBitrr.arr.Radarr-4K | Processing torrent: Movie.2024.1080p.mkv [hash123]
DEBUG | qBitrr.arr.Radarr-4K | Torrent status: downloading, progress: 45.2%
DEBUG | qBitrr.arr.Radarr-4K | ETA: 1234 seconds, peers: 15
INFO | qBitrr.arr.Radarr-4K | Torrent completed: Movie.2024.1080p.mkv
```

#### Instant Import
```
INFO | qBitrr.arr.Radarr-4K | Triggering instant import for: Movie.2024.1080p.mkv
DEBUG | qBitrr.arr.Radarr-4K | POST /api/v3/command {"name": "DownloadedMoviesScan", "path": "/downloads/Movie.2024.1080p.mkv"}
INFO | qBitrr.arr.Radarr-4K | Import command sent successfully
```

#### Search Operations
```
INFO | qBitrr.arr.Radarr-4K | Starting missing media search
DEBUG | qBitrr.arr.Radarr-4K | Found 12 missing movies
DEBUG | qBitrr.arr.Radarr-4K | Searching for: "Movie Title (2024)"
DEBUG | qBitrr.arr.Radarr-4K | POST /api/v3/command {"name": "MoviesSearch", "movieIds": [123]}
INFO | qBitrr.arr.Radarr-4K | Search completed: 12 items searched, 5 found
```

### Error Patterns

#### Connection Failures
```
ERROR | qBitrr.arr.Radarr-4K | Connection refused: http://radarr:7878/api/v3/system/status
ERROR | qBitrr.arr.Radarr-4K | Failed to connect to Radarr instance
WARNING | qBitrr.arr.Radarr-4K | Will retry in 30 seconds
```

**Diagnosis**: Radarr is down or unreachable. Check service status and network connectivity.

#### Authentication Failures
```
ERROR | qBitrr.qbit | qBittorrent login failed: Invalid username or password
ERROR | qBitrr.qbit | Authentication error, check credentials in config.toml
```

**Diagnosis**: Wrong qBittorrent credentials. Verify username/password or check authentication bypass settings.

#### API Key Errors
```
ERROR | qBitrr.arr.Radarr-4K | HTTP 401: Unauthorized
ERROR | qBitrr.arr.Radarr-4K | API key is invalid or missing
```

**Diagnosis**: Wrong API key. Copy correct key from Radarr Settings → General → Security.

#### Path Mapping Issues
```
ERROR | qBitrr.arr.Radarr-4K | Completed download folder not accessible: /downloads
ERROR | qBitrr.arr.Radarr-4K | FileNotFoundError: [Errno 2] No such file or directory: '/downloads/Movie.2024.1080p.mkv'
```

**Diagnosis**: Path mismatch between qBittorrent, Arr, and qBitrr. Verify Docker volumes or native paths.

#### Database Errors
```
ERROR | qBitrr | Database is locked
ERROR | qBitrr | OperationalError: database is locked
WARNING | qBitrr | Retrying database operation (attempt 2/5)
```

**Diagnosis**: Multiple qBitrr instances or file permissions issue. Check for duplicate processes.

---

## Log Rotation

### Automatic Rotation

qBitrr automatically rotates logs when they reach **10 MB**:

```
Main.log       # Current log (0-10 MB)
Main.log.1     # Previous rotation (10 MB)
Main.log.2     # Older backup (10 MB)
Main.log.3     # Older backup (10 MB)
Main.log.4     # Older backup (10 MB)
Main.log.5     # Oldest backup (10 MB, deleted on next rotation)
```

**Total space per log file**: ~60 MB (6 files × 10 MB)

### Manual Rotation

Force log rotation:

```bash
# Stop qBitrr
docker stop qbitrr

# Rotate logs manually
cd /config/logs
mv Main.log Main.log.backup
mv Radarr-4K.log Radarr-4K.log.backup

# Restart qBitrr (creates new logs)
docker start qbitrr
```

### Archiving Old Logs

```bash
# Compress old logs
cd ~/config/logs
tar -czf logs-backup-$(date +%Y%m%d).tar.gz *.log.*

# Delete old backups
rm *.log.[2-5]

# Keep only current and .1 backups
```

---

## Log Filtering and Analysis Tools

### grep (Basic Searching)

```bash
# Case-insensitive search
grep -i "error" Main.log

# Show line numbers
grep -n "ERROR" Main.log

# Invert match (exclude lines)
grep -v "DEBUG" Main.log

# Multiple patterns (OR)
grep -E "ERROR|CRITICAL" Main.log

# Context lines (before/after)
grep -A 5 "ERROR" Main.log  # 5 lines after
grep -B 5 "ERROR" Main.log  # 5 lines before
grep -C 5 "ERROR" Main.log  # 5 lines before AND after
```

### awk (Advanced Filtering)

```bash
# Extract only timestamps and messages
awk -F' | ' '{print $1, $4}' Main.log

# Filter by log level
awk '/ERROR/ || /CRITICAL/' Main.log

# Count log entries by level
awk -F' | ' '{print $2}' Main.log | sort | uniq -c

# Logs from specific time range
awk '/2025-11-27 12:[0-5][0-9]:/' Main.log
```

### tail (Real-Time Monitoring)

```bash
# Follow log with updates
tail -f Main.log

# Last 100 lines
tail -n 100 Main.log

# Multiple files simultaneously
tail -f Main.log Radarr-4K.log WebUI.log

# Follow with grep filter
tail -f Main.log | grep --line-buffered "ERROR"
```

### less (Interactive Viewing)

```bash
# Open log in less
less Main.log

# Search within less:
# Press '/' then type search term
# Press 'n' for next match, 'N' for previous

# Jump to end
less +G Main.log

# Follow mode (like tail -f)
less +F Main.log
```

---

## Exporting Logs for Support

### Creating a Support Package

```bash
# Collect all logs into archive
tar -czf qbitrr-logs-$(date +%Y%m%d-%H%M%S).tar.gz \
  ~/config/logs/*.log \
  ~/config/config.toml

# Upload to file sharing service
# Or attach to GitHub issue
```

**Before sharing**:

1. **Redact sensitive information:**
   ```bash
   # Create redacted config
   sed 's/APIKey = "[^"]*"/APIKey = "REDACTED"/g' ~/config/config.toml > config-redacted.toml
   sed -i 's/Password = "[^"]*"/Password = "REDACTED"/g' config-redacted.toml
   sed -i 's/Token = "[^"]*"/Token = "REDACTED"/g' config-redacted.toml
   ```

2. **Include only relevant logs** (last 500 lines):
   ```bash
   tail -n 500 ~/config/logs/Main.log > Main-excerpt.log
   ```

3. **Compress for easier sharing**:
   ```bash
   tar -czf support-logs.tar.gz Main-excerpt.log config-redacted.toml
   ```

---

## Performance Impact

### Log Level Impact on Performance

| Level | CPU Impact | Disk I/O | File Size Growth |
|-------|-----------|----------|------------------|
| CRITICAL | Negligible | Minimal | Very slow |
| ERROR | Negligible | Minimal | Slow |
| WARNING | Very low | Low | Slow |
| NOTICE | Low | Low | Moderate |
| **INFO** | Low | Moderate | Moderate |
| **DEBUG** | Moderate | High | Fast |
| **TRACE** | **High** | **Very High** | **Very Fast** |

**Recommendations**:

- **Production**: Use INFO or WARNING
- **Troubleshooting**: Use DEBUG temporarily, revert to INFO after
- **Avoid TRACE** unless absolutely necessary (generates gigabytes of logs quickly)

### Reducing Log Size

```toml
[Settings]
# Less verbose level
ConsoleLevel = "WARNING"

# Disable file logging (stdout only)
Logging = false  # Not recommended - no persistent logs
```

**Alternative**: Increase rotation frequency by monitoring log sizes and archiving/deleting old backups manually.

---

## Best Practices

1. **Start with INFO level** for normal operation
2. **Enable DEBUG only when troubleshooting** a specific issue
3. **Never leave TRACE enabled** in production (performance/storage impact)
4. **Monitor log file sizes** to avoid filling disk
5. **Archive old logs** periodically (logs.1-5 files)
6. **Use specific loggers** when possible (e.g., `Radarr-4K.log` instead of `Main.log`)
7. **Search logs efficiently** using grep/awk instead of opening entire files
8. **Redact sensitive data** before sharing logs publicly
9. **Include timestamps** when reporting issues to pinpoint when errors occurred
10. **Combine logs with config** when creating support requests (redacted)

---

## Troubleshooting Logging Issues

### Logs Not Being Created

**Check**:

1. Logging is enabled:
   ```toml
   [Settings]
   Logging = true
   ```

2. Log directory exists and is writable:
   ```bash
   ls -ld ~/config/logs
   chmod 755 ~/config/logs
   ```

3. No disk space issues:
   ```bash
   df -h ~/config
   ```

### Logs Empty or Missing Entries

**Check**:

1. Log level is not too restrictive:
   ```toml
   ConsoleLevel = "INFO"  # Not CRITICAL/ERROR
   ```

2. qBitrr is actually running:
   ```bash
   docker ps | grep qbitrr  # Docker
   systemctl status qbitrr  # Systemd
   ```

3. Check stdout/stderr instead:
   ```bash
   docker logs qbitrr  # Docker
   journalctl -u qbitrr  # Systemd
   ```

### Logs Growing Too Fast

**Solutions**:

1. Reduce log level:
   ```toml
   ConsoleLevel = "WARNING"  # From DEBUG/TRACE
   ```

2. Implement external log rotation:
   ```bash
   # Create logrotate config
   sudo nano /etc/logrotate.d/qbitrr
   ```

   ```
   /config/logs/*.log {
       daily
       rotate 7
       compress
       delaycompress
       missingok
       notifempty
   }
   ```

---

## Related Documentation

- [Common Issues](common-issues.md) - Specific error solutions
- [Docker Issues](docker.md) - Docker-specific logging
- [Performance Issues](performance.md) - Optimizing performance
- [WebUI Logs Page](../webui/logs.md) - WebUI log viewer

---

## See Also

- [Troubleshooting Overview](index.md)
- [Configuration Reference](../configuration/config-file.md)
- [GitHub Issues](https://github.com/Feramance/qBitrr/issues)
