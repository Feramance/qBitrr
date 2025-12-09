# Performance Tuning

Optimize qBitrr for your specific use case, from low-power devices to high-throughput servers.

## Quick Start

### Recommended Settings by Use Case

#### Low-Power Device (Raspberry Pi, NAS)

```toml
[Settings]
CheckInterval = 300      # Check every 5 minutes
MaxConcurrentChecks = 3  # Limit parallel operations
EnableFFprobe = false    # Disable media validation
LogLevel = "WARNING"     # Reduce log verbosity
RetentionDays = 7        # Minimize database size
```

#### Normal Usage (Home Server)

```toml
[Settings]
CheckInterval = 60       # Check every minute (default)
MaxConcurrentChecks = 10
EnableFFprobe = true
LogLevel = "INFO"
RetentionDays = 30
```

#### High-Throughput Server

```toml
[Settings]
CheckInterval = 30       # Check every 30 seconds
MaxConcurrentChecks = 20 # More parallel processing
EnableFFprobe = true
CacheFFprobeResults = true
LogLevel = "INFO"
RetentionDays = 90
MaxConnections = 200     # More HTTP connections
```

## Configuration Tuning

### Check Interval Optimization

**Impact of Check Interval:**

| Interval | CPU Usage | API Calls/hr | Response Time |
|----------|-----------|--------------|---------------|
| 10s | High (5-10%) | 360 | Excellent |
| 30s | Medium (2-5%) | 120 | Good |
| 60s | Low (1-2%) | 60 | Fair (default) |
| 300s | Minimal (<1%) | 12 | Slow |

**Choose based on:**
- **Download speed** - Faster speeds need shorter intervals
- **System resources** - Limited CPU/RAM requires longer intervals
- **Download volume** - Many simultaneous downloads benefit from shorter intervals

### Concurrent Operations

```toml
[Settings]
MaxConcurrentChecks = 10  # Default

# Tuning guide:
# Low-power: 3-5
# Normal: 10-15
# High-performance: 20-50
```

**Factors to consider:**
- **CPU cores** - More cores = higher concurrency
- **Network latency** - High latency benefits from more concurrency
- **API rate limits** - Don't exceed Arr/qBittorrent limits

### Database Optimization

#### Retention Settings

```toml
[Settings]
RetentionDays = 30       # How long to keep torrent history
SearchRetentionDays = 14 # How long to keep search history
AutoVacuum = true        # Automatically optimize database
```

**Impact:**
- Lower retention = Smaller database = Faster queries
- Higher retention = Better history tracking

#### Auto-Vacuum

```toml
[Settings]
AutoVacuum = true        # Automatic optimization
VacuumThreshold = 100    # VACUUM if DB grows by 100 MB
```

**Manual vacuum:**

```bash
sqlite3 ~/config/qBitrr.db "VACUUM;"
```

### Network Optimization

#### Connection Pooling

```toml
[Settings]
MaxConnections = 100     # HTTP connection pool size
ConnectionTimeout = 30   # Connect timeout (seconds)
ReadTimeout = 60         # Read timeout (seconds)
```

**Guidelines:**
- `MaxConnections` should be: `(Arr instances + 1) × 20`
- Lower timeouts for fast local networks
- Higher timeouts for remote/VPN connections

#### Retry Configuration

```toml
[Settings]
MaxRetries = 3           # Number of retries on failure
RetryDelay = 5           # Seconds between retries
BackoffMultiplier = 2    # Exponential backoff factor
```

**Example backoff:**
1. First retry: 5s delay
2. Second retry: 10s delay (5 × 2)
3. Third retry: 20s delay (10 × 2)

### FFprobe Optimization

```toml
[Settings]
EnableFFprobe = true
FFprobeTimeout = 30       # Kill ffprobe after 30s
CacheFFprobeResults = true # Cache validation results
ValidateAllFiles = false  # Only check largest file
```

**Performance impact:**

| Configuration | Time per Torrent | CPU Impact |
|---------------|------------------|------------|
| Disabled | 0s | None |
| Enabled, largest file only | 1-5s | Low |
| Enabled, all files | 5-30s | Medium |
| Enabled, cached | <1s | Minimal |

## Resource Monitoring

### CPU Usage

**Normal load:**
- Idle: < 1% CPU
- Active checks: 2-5% CPU
- FFprobe validation: 10-20% CPU (temporary spikes)

**High CPU symptoms:**
- Check interval too short
- Too many concurrent checks
- Database issues (check for locks)

**Solutions:**

```toml
[Settings]
CheckInterval = 120      # Increase interval
MaxConcurrentChecks = 5  # Reduce concurrency
EnableFFprobe = false    # Disable if not needed
```

### Memory Usage

**Typical memory footprint:**

| Configuration | RAM Usage |
|---------------|-----------|
| 1 Arr instance | 100-150 MB |
| 4 Arr instances | 200-300 MB |
| 10 Arr instances | 400-600 MB |

**High memory symptoms:**
- Excessive database size
- Memory leaks (rare)
- Too many concurrent operations

**Solutions:**

```toml
[Settings]
RetentionDays = 7        # Reduce database size
MaxConcurrentChecks = 5  # Reduce memory pressure
```

```bash
# Restart qBitrr to clear memory
docker restart qbitrr
```

### Disk I/O

**Database operations:**
- Reads: Very frequent (every check interval)
- Writes: Moderate (on state changes)
- VACUUM: Infrequent (weekly if AutoVacuum enabled)

**Optimization:**

```toml
[Settings]
# Use SSD for database if possible
DataDir = "/path/to/ssd/config"

# Or reduce write frequency
UpdateInterval = 60  # Batch updates every 60s
```

### Network Bandwidth

**Typical usage:**
- qBittorrent API: 1-5 KB/s
- Arr API: 1-3 KB/s per instance
- WebUI: Minimal (only when accessing dashboard)

**Total:** < 10 KB/s for most setups

## Performance Profiling

### Enable Built-in Profiling

```toml
[Settings]
EnableProfiling = true
ProfilingOutput = "/config/profiling/"
```

**Output files:**
```
profiling/
├── loop_times.csv       # Event loop durations
├── api_calls.csv        # API call latencies
└── db_queries.csv       # Database query times
```

### Analyze Bottlenecks

**Check loop times:**

```bash
# Find slowest event loop iterations
sort -t, -k2 -rn /config/profiling/loop_times.csv | head -20
```

**Check API call latencies:**

```bash
# Average latency per API endpoint
awk -F, '{sum[$1]+=$2; count[$1]++} END {for(api in sum) print api, sum[api]/count[api]}' \
  /config/profiling/api_calls.csv
```

## Scaling Strategies

### Vertical Scaling (Single Machine)

**Increase resources:**

```yaml
# docker-compose.yml
services:
  qbitrr:
    deploy:
      resources:
        limits:
          cpus: '4.0'      # Allow up to 4 CPU cores
          memory: 2G       # Increase memory limit
```

**Optimize configuration:**

```toml
[Settings]
CheckInterval = 30       # Faster checks
MaxConcurrentChecks = 20 # More parallelism
MaxConnections = 200     # More connections
```

### Horizontal Scaling (Multiple Instances)

Split Arr instances across multiple qBitrr deployments:

**Instance 1 (Movies):**
```toml
[[Radarr]]
Name = "Radarr-4K"
# ...
```

**Instance 2 (TV):**
```toml
[[Sonarr]]
Name = "Sonarr-HD"
# ...

[[Sonarr]]
Name = "Sonarr-4K"
# ...
```

**Benefits:**
- Isolated failures
- Independent scaling
- Easier debugging

### Database Optimization

#### Indexes

qBitrr automatically creates indexes, but you can verify:

```sql
-- Check existing indexes
SELECT name FROM sqlite_master WHERE type = 'index';

-- Expected indexes:
-- idx_downloads_arr
-- idx_downloads_state
-- idx_downloads_media_id
-- idx_searches_arr
-- idx_expiry_time
```

#### Query Optimization

**Slow query example:**

```python
# BAD: Fetches all torrents then filters in Python
all_torrents = DownloadsModel.select()
completed = [t for t in all_torrents if t.state == 'completed']
```

**Optimized:**

```python
# GOOD: Filter in database
completed = DownloadsModel.select().where(
    DownloadsModel.state == 'completed'
)
```

## Troubleshooting Performance

### Slow Import Times

**Symptoms:** Torrents complete but take minutes to import

**Causes:**
1. FFprobe validation taking too long
2. Arr API responding slowly
3. Network latency

**Debug:**

```toml
[Settings]
LogLevel = "DEBUG"
```

**Look for:**
```
[DEBUG] FFprobe validation took 45.2s for torrent abc123
[DEBUG] Arr import API call took 12.3s
```

**Solutions:**
- Disable FFprobe: `EnableFFprobe = false`
- Check Arr performance (CPU, disk I/O)
- Verify network connectivity

### High API Call Rate

**Symptoms:** Arr/qBittorrent logs show excessive API calls

**Causes:**
- Check interval too short
- Too many Arr instances

**Debug:**

```bash
# Count API calls in logs
grep "API call to" ~/config/logs/Main.log | wc -l
```

**Solutions:**

```toml
[Settings]
CheckInterval = 120      # Reduce frequency
CacheAPIResponses = true # Enable caching (if available)
```

### Database Lock Errors

**Symptoms:**
```
[ERROR] database is locked
```

**Causes:**
- Multiple processes writing simultaneously
- Long-running VACUUM operation
- Disk I/O issues

**Solutions:**

```toml
[Settings]
AutoVacuum = false  # Disable automatic vacuum
```

```bash
# Manual vacuum during low activity
sqlite3 ~/config/qBitrr.db "VACUUM;"
```

### Memory Leaks

**Symptoms:** Memory usage grows over time, never decreases

**Debug:**

```bash
# Monitor memory over time
while true; do
  docker stats qbitrr --no-stream | awk '{print $4}'
  sleep 60
done
```

**Solutions:**
1. Restart qBitrr periodically (cron job)
2. Report issue on GitHub with logs
3. Reduce `CheckInterval` to limit loop iterations

## Benchmarks

### Event Loop Performance

**Test setup:** 50 torrents, 4 Arr instances, i5-10400 CPU, SSD

| Configuration | Loop Duration | Torrents/s |
|---------------|---------------|------------|
| FFprobe disabled, 10 workers | 2.5s | 20 |
| FFprobe enabled, 10 workers | 8.2s | 6 |
| FFprobe disabled, 20 workers | 1.8s | 28 |

### Database Performance

**SQLite query times (100k entries):**

| Operation | Time |
|-----------|------|
| SELECT by hash (indexed) | <1ms |
| SELECT by state (indexed) | 5-10ms |
| UPDATE single row | 1-2ms |
| Bulk INSERT (100 rows) | 50-100ms |
| VACUUM (10 MB DB) | 500ms |

### API Call Latency

**Average latency (local network):**

| API | Latency |
|-----|---------|
| qBittorrent: Get torrents | 50-100ms |
| Radarr: Get movie | 20-50ms |
| Sonarr: Get series | 30-60ms |
| Radarr: Trigger search | 100-200ms |

## Best Practices

1. **Start with defaults** - Only tune if you have specific issues
2. **Monitor before optimizing** - Identify actual bottlenecks
3. **Change one thing at a time** - Easier to identify what helped
4. **Test under load** - Optimize for peak usage, not idle state
5. **Document changes** - Keep notes on what works for your setup

## Related Documentation

- [Architecture](architecture.md) - System design overview
- [Event Loops](event-loops.md) - Loop execution details
- [Multiprocessing](multiprocessing.md) - Process management
- [Troubleshooting: Performance](../troubleshooting/performance.md) - Debug performance issues
