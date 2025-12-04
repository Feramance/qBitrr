# Performance Troubleshooting

This guide covers performance optimization, resource usage tuning, and troubleshooting slow or resource-heavy qBitrr deployments.

## Overview

qBitrr is designed to be lightweight and efficient, but performance can degrade with:

- **Large libraries** (10,000+ movies/series/albums)
- **High torrent counts** (500+ active torrents)
- **Frequent search loops** (aggressive automation)
- **Resource-constrained environments** (Raspberry Pi, low-memory VPS)
- **Network latency** (slow Arr API responses)

This guide helps identify bottlenecks and optimize qBitrr for your environment.

---

## Performance Symptoms

### CPU Usage Issues

**High CPU (> 50% single core constantly)**:

- Event loops running too frequently
- Complex regex operations on large file lists
- Database queries without proper indexes
- FFprobe verification on many files simultaneously

**CPU Spikes**:

- Database updates (normal during library refreshes)
- RSS sync operations
- Search loops triggering simultaneously
- Process restarts

### Memory Usage Issues

**High Memory (> 500 MB)**:

- Large library metadata cached in memory
- Many concurrent Arr API requests
- Database result sets not paginated
- Log buffer accumulation

**Memory Leaks**:

- Gradual memory growth over days/weeks
- Not releasing completed torrent references
- WebUI connections not closed properly

### Network Issues

**Slow Arr API Responses**:

- Network latency to Arr instances
- Arr instances overloaded (shared with other tools)
- Large API payloads (full library dumps)

**Rate Limiting**:

- qBittorrent API rate limits
- Arr API throttling (429 errors)

---

## Loop Timer Optimization

### Event Loop Timers

qBitrr has multiple event loops with configurable timers:

| Loop | Purpose | Config Key | Default | Recommended Range |
|------|---------|------------|---------|-------------------|
| **Main Loop** | Check torrents, trigger imports | `LoopSleepTimer` | 5s | 5-60s |
| **Search Loop** | Automated searches | `SearchLoopDelay` | -1 (disabled) | 300-3600s |
| **RSS Sync** | Refresh RSS feeds | `RssSyncTimer` | 15min | 5-60min |
| **Refresh Downloads** | Update queue status | `RefreshDownloadsTimer` | 1min | 1-15min |
| **Stalled Check** | Detect stalled torrents | `StalledDelay` | 15min | 10-60min |

### Main Loop Timer

**Controls:** How often qBitrr checks torrents for completion and triggers imports.

```toml
[Settings]
LoopSleepTimer = 5  # Seconds between checks
```

**Tuning Guidance:**

| Library Size | Torrent Count | Recommended Timer |
|--------------|---------------|-------------------|
| < 1,000 items | < 50 torrents | 5s (default) |
| 1,000-10,000 items | 50-200 torrents | 10-15s |
| > 10,000 items | 200-500 torrents | 30-60s |
| > 50,000 items | > 500 torrents | 60s+ |

**Impact:**

- **Lower values** (faster loops):
  - ✅ Faster imports (detects completion sooner)
  - ❌ Higher CPU usage
  - ❌ More API requests to qBittorrent

- **Higher values** (slower loops):
  - ✅ Lower CPU usage
  - ✅ Fewer API requests
  - ❌ Slower import detection (up to `LoopSleepTimer` delay)

**Example Configurations:**

=== "Fast (Responsive)"
    ```toml
    [Settings]
    LoopSleepTimer = 5  # Check every 5 seconds
    ```

    **Use when:** Small library, few torrents, powerful hardware

=== "Balanced"
    ```toml
    [Settings]
    LoopSleepTimer = 15  # Check every 15 seconds
    ```

    **Use when:** Medium library, moderate torrent count

=== "Slow (Low Resource)"
    ```toml
    [Settings]
    LoopSleepTimer = 60  # Check every minute
    ```

    **Use when:** Large library, many torrents, limited CPU/memory

### Search Loop Timer

**Controls:** Automated search frequency for missing/upgrade candidates.

```toml
[Settings]
SearchLoopDelay = 3600  # Seconds between automated searches (-1 = disabled)
```

**Tuning Guidance:**

| Search Volume | Recommended Timer |
|---------------|-------------------|
| Light (< 10 searches/hour) | 1800s (30 min) |
| Moderate (10-50/hour) | 3600s (1 hour) |
| Heavy (> 50/hour) | 7200s (2 hours) |
| Very heavy (> 100/hour) | Disable (-1), use cron instead |

**Impact:**

- **Lower values**:
  - ✅ Faster media acquisition
  - ❌ High CPU during searches
  - ❌ Arr API load spikes
  - ❌ Risk of rate limiting

- **Higher values**:
  - ✅ Lower resource usage
  - ✅ Reduced Arr API load
  - ❌ Slower media acquisition

**Alternative: Disable and Use Manual Searches**

```toml
[Settings]
SearchLoopDelay = -1  # Disable automated searches
```

Trigger searches manually via:

- WebUI "Search" buttons
- Arr instance manual search
- External automation (cron, scripts)

### RSS Sync Timer

**Controls:** How often qBitrr triggers RSS feed refreshes in Arr instances.

```toml
[Radarr-Movies]
RssSyncTimer = 15  # Minutes between RSS syncs
```

**Tuning Guidance:**

| Use Case | Recommended Timer |
|----------|-------------------|
| High-priority (new releases) | 5-10 min |
| Normal priority | 15-30 min |
| Low priority (backlog only) | 60 min |
| Disabled (Arr handles RSS) | 0 (disabled) |

**Impact:**

- **Lower values**:
  - ✅ Faster new release detection
  - ❌ More Arr API requests
  - ❌ Higher CPU during sync

- **Higher values**:
  - ✅ Reduced Arr API load
  - ❌ Slower new release detection

!!! tip "Let Arr Handle RSS"
    If your Arr instance already has RSS configured with its own timer, you can disable qBitrr's RSS sync:

    ```toml
    [Radarr-Movies]
    RssSyncTimer = 0
    ```

### Refresh Downloads Timer

**Controls:** How often qBitrr refreshes the download queue in Arr.

```toml
[Radarr-Movies]
RefreshDownloadsTimer = 1  # Minutes between queue refreshes
```

**Tuning Guidance:**

| Queue Activity | Recommended Timer |
|----------------|-------------------|
| High (many downloads) | 1-2 min |
| Moderate | 5 min |
| Low (few downloads) | 10-15 min |
| Disabled (instant imports only) | 0 |

**Impact:**

- **Lower values**:
  - ✅ Faster queue status updates
  - ❌ More Arr API requests

- **Higher values**:
  - ✅ Reduced Arr API load
  - ❌ Slower queue status updates

---

## Resource Optimization

### CPU Optimization

#### 1. Reduce Loop Frequency

```toml
[Settings]
LoopSleepTimer = 30  # Increase from default 5s
SearchLoopDelay = -1  # Disable automated searches

[Radarr-Movies]
RssSyncTimer = 30  # Increase from default 15 min
RefreshDownloadsTimer = 5  # Increase from default 1 min
```

#### 2. Limit Concurrent Operations

```toml
[Settings]
SearchRequestsEvery = 600  # Delay between request searches (10 min)
```

Reduces CPU spikes during request processing.

#### 3. Disable Expensive Features

```toml
[Settings]
FFprobeAutoUpdate = false  # Skip FFprobe verification
```

**Caution:** Disabling FFprobe allows corrupted files to import.

#### 4. Optimize Regex

Complex regex patterns in file exclusions can slow down file processing:

```toml
# ❌ Slow: Multiple complex patterns
[Settings.Files]
FileNameExclusionRegEx = [
    '(?i)\\b(sample|trailer|extra|bonus|featurette)\\b.*',
    '(?i).*\\b(behind[\\s.-]*the[\\s.-]*scenes|deleted[\\s.-]*scenes)\\b.*',
    # ... many more
]

# ✅ Fast: Simplified patterns
[Settings.Files]
FileNameExclusionRegEx = [
    '(?i)(sample|trailer|extra)',
]
```

Use `FileExtensionAllowlist` to filter by extension first (faster):

```toml
[Settings.Files]
FileExtensionAllowlist = [".mkv", ".mp4", ".avi"]
```

### Memory Optimization

#### 1. Limit Log Retention

```toml
[Settings]
LogLevel = "INFO"  # Reduce from DEBUG
MaximumRollingLogFiles = 5  # Default 10
MaximumRollingLogSize = 10485760  # 10MB (default 50MB)
```

#### 2. Disable WebUI Live Updates

```toml
[WebUI]
LiveArr = false  # Disable real-time Arr library updates in WebUI
```

Reduces memory used by WebUI caching.

#### 3. Use Docker Memory Limits

```yaml
services:
  qbitrr:
    mem_limit: 512m  # Limit to 512MB RAM
    memswap_limit: 512m  # Disable swap
```

#### 4. Restart qBitrr Periodically

For long-running instances (weeks/months), restart qBitrr to clear accumulated memory:

```bash
# Cron: Weekly restart at 3 AM Sunday
0 3 * * 0 docker restart qbitrr
```

### Network Optimization

#### 1. Use Docker Network

Place qBitrr, qBittorrent, and Arr instances in the same Docker network:

```yaml
networks:
  mediastack:

services:
  qbittorrent:
    networks:
      - mediastack

  radarr:
    networks:
      - mediastack

  qbitrr:
    networks:
      - mediastack
```

**Benefits:**

- ✅ Low latency (internal network)
- ✅ No external network overhead
- ✅ Faster API responses

#### 2. Increase API Timeouts

If Arr instances are slow, increase timeouts:

```toml
[Radarr-Movies]
Timeout = 60  # Seconds (default 30)
```

#### 3. Reduce Concurrent Requests

Limit simultaneous searches to avoid overwhelming Arr:

```toml
[Settings]
SearchRequestsEvery = 300  # Space out searches by 5 minutes
```

---

## Database Optimization

### VACUUM Database

Reclaim space and optimize SQLite:

```bash
# Stop qBitrr
docker stop qbitrr

# Vacuum database
docker run --rm -v /path/to/config:/config -it alpine sh -c "apk add sqlite && sqlite3 /config/qbitrr.db 'VACUUM;'"

# Restart
docker start qbitrr
```

Run monthly for large libraries.

### ANALYZE Statistics

Update query planner statistics:

```bash
docker exec qbitrr sqlite3 /config/qbitrr.db "ANALYZE;"
```

Run after major library changes (1000+ new entries).

### Database Size Monitoring

```bash
# Check database size
docker exec qbitrr ls -lh /config/qbitrr.db

# Check WAL size
docker exec qbitrr ls -lh /config/qbitrr.db-wal
```

If database exceeds 500 MB, consider:

- Vacuuming to reclaim space
- Checking for duplicate entries
- Reviewing historical data retention

---

## Large Library Handling

### 10,000+ Items

**Symptoms:**

- Database updates take minutes
- High memory usage (> 300 MB)
- Slow WebUI Arr views

**Optimizations:**

```toml
[Settings]
LoopSleepTimer = 30  # Slower main loop
SearchLoopDelay = -1  # Disable automated searches

[Radarr-Movies]
RssSyncTimer = 60  # Slower RSS sync
RefreshDownloadsTimer = 10  # Slower queue refresh
```

**WebUI:**

Disable live Arr views:

```toml
[WebUI]
LiveArr = false
```

**Database:**

- Run `VACUUM` monthly
- Run `ANALYZE` after major updates
- Monitor database size

### 500+ Active Torrents

**Symptoms:**

- qBittorrent API slow (> 1s responses)
- High CPU during torrent checks
- Frequent loop delays

**Optimizations:**

```toml
[Settings]
LoopSleepTimer = 60  # Check torrents once per minute
NoInternetSleepTimer = 300  # Longer delay on connection issues
```

**qBittorrent:**

- Enable "Limit upload rate" in qBit to reduce network overhead
- Use categories to organize torrents
- Remove completed torrents promptly

### Multiple Arr Instances

**Symptoms:**

- Event loops overlap, causing CPU spikes
- Database lock contention
- Memory usage proportional to instance count

**Optimizations:**

Stagger timers across instances:

```toml
[Radarr-Movies]
RssSyncTimer = 15  # Sync at :00, :15, :30, :45

[Sonarr-TV]
RssSyncTimer = 20  # Sync at :00, :20, :40

[Lidarr-Music]
RssSyncTimer = 25  # Sync at :00, :25, :50
```

This prevents all instances syncing simultaneously.

---

## Monitoring Performance

### CPU and Memory

```bash
# Docker stats
docker stats qbitrr

# Output:
# CONTAINER ID   NAME     CPU %     MEM USAGE / LIMIT     MEM %
# abc123...      qbitrr   5.2%      256MiB / 2GiB         12.5%
```

**Expected Values:**

| Metric | Idle | Active | High Load |
|--------|------|--------|-----------|
| CPU | < 5% | 10-20% | 30-50% |
| Memory | 50-150 MB | 150-300 MB | 300-500 MB |

**Alerts:**

- CPU > 50% sustained → Reduce loop frequency
- Memory > 500 MB → Check for leaks, restart qBitrr
- Memory growth > 10 MB/hour → Potential memory leak

### Event Loop Delays

Check logs for delay messages:

```bash
docker logs qbitrr | grep -i delay
```

**Example Output:**

```
[Radarr-Movies] Delaying loop by 300 seconds (qbit connection error)
[Sonarr-TV] Delaying search loop by 600 seconds (no internet)
```

**Causes:**

- `type=qbit` → qBittorrent connection issues
- `type=internet` → Network connectivity problems
- `type=delay` → Manual delay (e.g., rate limiting)
- `type=no_downloads` → No active downloads (idle)

### API Response Times

Enable debug logging to see API timings:

```toml
[Settings]
ConsoleLevel = "DEBUG"
```

```bash
docker logs qbitrr | grep "API request"
```

**Example:**

```
[Radarr-Movies] API request: GET /api/v3/movie (1.2s)
[Sonarr-TV] API request: GET /api/v3/queue (0.8s)
```

**Normal Response Times:**

- < 1s: Healthy
- 1-3s: Acceptable (large libraries)
- > 3s: Slow (consider optimizing Arr or network)

---

## Troubleshooting Slow Performance

### Step 1: Identify Bottleneck

1. **Check CPU usage:**

   ```bash
   docker stats qbitrr
   ```

   If CPU > 30%, proceed to "CPU Optimization"

2. **Check memory usage:**

   ```bash
   docker stats qbitrr
   ```

   If memory > 400 MB, proceed to "Memory Optimization"

3. **Check event loop delays:**

   ```bash
   docker logs qbitrr | tail -100 | grep -i delay
   ```

   If frequent delays, check qBittorrent/Arr connectivity

4. **Check database size:**

   ```bash
   docker exec qbitrr ls -lh /config/qbitrr.db
   ```

   If > 500 MB, run VACUUM

### Step 2: Apply Optimizations

Based on bottleneck:

**CPU:**

- Increase `LoopSleepTimer` to 30-60s
- Disable `SearchLoopDelay` (-1)
- Increase `RssSyncTimer` to 30-60 min

**Memory:**

- Set `LogLevel = "INFO"`
- Disable `WebUI.LiveArr`
- Restart qBitrr

**Network:**

- Check Arr API response times
- Use Docker network (same host)
- Increase timeouts

**Database:**

- Run `VACUUM`
- Run `ANALYZE`
- Check for duplicate entries

### Step 3: Monitor Improvement

After changes, monitor for 1-2 hours:

```bash
# Watch CPU/memory in real-time
docker stats qbitrr

# Tail logs for errors
docker logs -f qbitrr
```

Expected improvements:

- CPU drops by 50-70%
- Memory stabilizes (no growth)
- Fewer delay messages in logs

---

## Resource-Constrained Environments

### Raspberry Pi

**Hardware:**

- Raspberry Pi 4 (2GB+ RAM)
- SD card or USB SSD (faster I/O)

**Configuration:**

```toml
[Settings]
LoopSleepTimer = 60  # Very slow loops
SearchLoopDelay = -1  # Disable automated searches
LogLevel = "INFO"  # Minimal logging
FFprobeAutoUpdate = false  # Skip verification

[Radarr-Movies]
RssSyncTimer = 60  # Slow RSS sync
RefreshDownloadsTimer = 15  # Slow queue refresh

[WebUI]
LiveArr = false  # Disable live updates
```

**Docker Memory Limit:**

```yaml
services:
  qbitrr:
    mem_limit: 256m  # Limit to 256MB
```

### Low-Memory VPS

**Hardware:**

- 512 MB - 1 GB RAM
- Shared CPU

**Configuration:**

```toml
[Settings]
LoopSleepTimer = 30
SearchLoopDelay = -1
MaximumRollingLogFiles = 3  # Reduce log storage
MaximumRollingLogSize = 5242880  # 5MB logs

[WebUI]
LiveArr = false
```

**Swap Configuration:**

```bash
# Add swap file (1GB)
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## Advanced Tuning

### Multi-Core Utilization

qBitrr uses `pathos.multiprocessing` to run each Arr instance in a separate process:

- **1 Arr instance** → 1 process (single core)
- **3 Arr instances** → 3 processes (up to 3 cores)

**CPU Limit:**

```yaml
services:
  qbitrr:
    deploy:
      resources:
        limits:
          cpus: '2.0'  # Limit to 2 CPU cores
```

### Process Priority

Lower qBitrr's process priority:

```yaml
services:
  qbitrr:
    cpu_shares: 512  # Default 1024 (50% priority)
```

### I/O Scheduling

For systems with high disk I/O:

```yaml
services:
  qbitrr:
    blkio_config:
      weight: 300  # Default 500 (lower = less I/O priority)
```

---

## Performance Benchmarks

### Baseline Performance

Typical resource usage (default config):

| Library Size | CPU (idle) | CPU (active) | Memory | DB Size |
|--------------|------------|--------------|--------|---------|
| 500 items | 2-5% | 10-15% | 80-120 MB | 5-10 MB |
| 5,000 items | 3-8% | 15-25% | 150-200 MB | 50-100 MB |
| 50,000 items | 5-15% | 25-40% | 300-400 MB | 500 MB - 1 GB |

### Optimized Performance

After tuning (slow timers, disabled features):

| Library Size | CPU (idle) | CPU (active) | Memory | DB Size |
|--------------|------------|--------------|--------|---------|
| 500 items | 1-2% | 5-8% | 60-80 MB | 5-10 MB |
| 5,000 items | 1-3% | 8-12% | 100-150 MB | 50-100 MB |
| 50,000 items | 2-5% | 12-20% | 200-300 MB | 500 MB - 1 GB |

---

## Quick Reference

### Performance Checklist

- [ ] `LoopSleepTimer` appropriate for library size
- [ ] `SearchLoopDelay` disabled or set to 1+ hour
- [ ] `RssSyncTimer` set to 30-60 min
- [ ] `RefreshDownloadsTimer` set to 5-15 min
- [ ] `LogLevel` set to INFO (not DEBUG)
- [ ] `WebUI.LiveArr` disabled for large libraries
- [ ] Database vacuumed monthly
- [ ] Docker memory limits configured
- [ ] Docker network used (same host setup)

### Recommended Configurations

#### Small Library (< 1,000 items, < 50 torrents)

```toml
[Settings]
LoopSleepTimer = 5
SearchLoopDelay = 1800  # 30 min
LogLevel = "INFO"

[Radarr-Movies]
RssSyncTimer = 15
RefreshDownloadsTimer = 1
```

#### Medium Library (1,000-10,000 items, 50-200 torrents)

```toml
[Settings]
LoopSleepTimer = 15
SearchLoopDelay = 3600  # 1 hour
LogLevel = "INFO"

[Radarr-Movies]
RssSyncTimer = 30
RefreshDownloadsTimer = 5
```

#### Large Library (> 10,000 items, > 200 torrents)

```toml
[Settings]
LoopSleepTimer = 60
SearchLoopDelay = -1  # Disabled
LogLevel = "INFO"
MaximumRollingLogFiles = 5

[Radarr-Movies]
RssSyncTimer = 60
RefreshDownloadsTimer = 10

[WebUI]
LiveArr = false
```

---

## Related Documentation

- [Debug Logging](debug-logging.md) - Log analysis for performance issues
- [Database Troubleshooting](database.md) - Database optimization
- [Common Issues](common-issues.md) - General troubleshooting
- [Configuration Reference](../configuration/config-file.md) - Full config options

---

## External Resources

- [SQLite Performance Tuning](https://www.sqlite.org/performance.html) - Official SQLite docs
- [Docker Resource Limits](https://docs.docker.com/config/containers/resource_constraints/) - Docker documentation
