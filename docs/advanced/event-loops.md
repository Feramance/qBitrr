# Event Loops

Deep dive into qBitrr's event loop architecture and control flow.

## Overview

Each Arr instance (Radarr/Sonarr/Lidarr) runs an independent event loop in its own process. The event loop is the core mechanism that monitors torrents, performs health checks, and triggers imports.

## Event Loop Lifecycle

### Loop Phases

```
┌─────────────────────────────────────────────────────────┐
│                    Event Loop Start                      │
└──────────────────┬──────────────────────────────────────┘
                   │
       ┌───────────▼──────────┐
       │  1. FETCH PHASE      │
       │  - Query qBittorrent  │
       │  - Get torrents by    │
       │    category/tags      │
       └───────────┬──────────┘
                   │
       ┌───────────▼──────────┐
       │  2. CLASSIFY PHASE   │
       │  - Check database    │
       │  - Determine state   │
       │  - Match to Arr      │
       └───────────┬──────────┘
                   │
       ┌───────────▼──────────┐
       │  3. HEALTH CHECK     │
       │  - Check ETA         │
       │  - Monitor stalls    │
       │  - Verify trackers   │
       └───────────┬──────────┘
                   │
       ┌───────────▼──────────┐
       │  4. ACTION PHASE     │
       │  - Import completed  │
       │  - Blacklist failed  │
       │  - Re-search         │
       │  - Cleanup old       │
       └───────────┬──────────┘
                   │
       ┌───────────▼──────────┐
       │  5. UPDATE PHASE     │
       │  - Update database   │
       │  - Log actions       │
       │  - Record metrics    │
       └───────────┬──────────┘
                   │
       ┌───────────▼──────────┐
       │  6. SLEEP PHASE      │
       │  - Wait for interval │
       │  - Check shutdown    │
       └───────────┬──────────┘
                   │
                   └──────────────┐
                                  │
                   ┌──────────────▼────┐
                   │ Shutdown signal?  │
                   │   Yes: Exit       │
                   │   No: Loop back   │
                   └───────────────────┘
```

## Implementation

### Main Loop Code

**File:** `qBitrr/arss.py:ArrManagerBase.run_loop()`

```python
def run_loop(self):
    """Main event loop for Arr instance."""
    logger.info(f"Starting event loop for {self.name}")

    while not self.shutdown_event.is_set():
        try:
            # Phase 1: Fetch torrents
            torrents = self._fetch_torrents_from_qbittorrent()

            # Phase 2: Classify torrents
            tracked = self._get_tracked_torrents()
            new_torrents = self._identify_new_torrents(torrents, tracked)

            # Phase 3: Health checks
            for torrent in torrents:
                try:
                    health_status = self._check_torrent_health(torrent)

                    # Phase 4: Take action based on health
                    if health_status == 'completed':
                        self._import_to_arr(torrent)
                    elif health_status == 'failed':
                        self._handle_failed_torrent(torrent)
                    elif health_status == 'stalled':
                        self._handle_stalled_torrent(torrent)

                except SkipException:
                    # Skip this torrent, continue with others
                    continue
                except Exception as e:
                    logger.error(f"Error processing {torrent['hash']}: {e}")
                    continue

            # Phase 5: Update database
            self._update_torrent_states(torrents)

            # Cleanup expired entries
            self._cleanup_expired_entries()

            # Phase 6: Sleep
            logger.debug(f"Loop complete, sleeping {self.check_interval}s")
            time.sleep(self.check_interval)

        except DelayLoopException as e:
            # Temporary delay (e.g., connection failure)
            logger.warning(f"Delaying loop for {e.length}s: {e.type}")
            time.sleep(e.length)

        except RestartLoopException:
            # Config changed, restart loop
            logger.info("Restarting loop due to config change")
            self._reload_config()
            continue

        except Exception as e:
            logger.exception(f"Unexpected error in event loop: {e}")
            time.sleep(60)  # Back off on unexpected errors

    logger.info(f"Event loop stopped for {self.name}")
```

## Control Flow Exceptions

qBitrr uses **exceptions for control flow** in the event loop. This is a deliberate design choice that makes loop control explicit and traceable.

### Exception Types

#### SkipException

**Purpose:** Skip processing the current torrent and continue with the next one.

**File:** `qBitrr/errors.py`

```python
class SkipException(qBitManagerError):
    """Dummy error to skip actions"""
```

**Usage:**

```python
def _check_torrent_health(self, torrent):
    # Skip torrents we don't care about
    if torrent['category'] not in self.categories:
        raise SkipException("Not our category")

    # Skip torrents without tags
    if not self._has_arr_tags(torrent):
        raise SkipException("Missing Arr tags")

    # Continue with health check...
```

#### DelayLoopException

**Purpose:** Pause the event loop temporarily (e.g., during connection failures).

```python
class DelayLoopException(qBitManagerError):
    def __init__(self, length: int, type: str):
        self.type = type      # Reason for delay
        self.length = length  # Seconds to delay
```

**Usage:**

```python
def _fetch_torrents_from_qbittorrent(self):
    try:
        return self.qbt_client.torrents()
    except ConnectionError:
        # Can't connect to qBittorrent, delay loop
        raise DelayLoopException(length=60, type="qbittorrent_offline")
```

#### RestartLoopException

**Purpose:** Restart the loop from the beginning (e.g., after config reload).

```python
class RestartLoopException(ArrManagerException):
    """Exception to trigger a loop restart"""
```

**Usage:**

```python
def _reload_config(self):
    logger.info("Config file changed, reloading...")
    new_config = load_config()

    if new_config != self.config:
        self.config = new_config
        self._reinitialize_clients()
        raise RestartLoopException()
```

#### NoConnectionrException

**Purpose:** Handle connection failures with retry logic.

*Note: The typo "Connectionr" is preserved for backward compatibility.*

```python
class NoConnectionrException(qBitManagerError):
    def __init__(self, message: str, type: str = "delay"):
        self.message = message
        self.type = type  # "delay" or "fatal"
```

**Usage:**

```python
def _import_to_arr(self, torrent):
    try:
        self.arr_client.import_torrent(torrent)
    except requests.exceptions.RequestException as e:
        # Connection to Arr failed
        if self.retry_count < MAX_RETRIES:
            raise NoConnectionrException(
                f"Failed to connect to {self.name}",
                type="delay"
            )
        else:
            raise NoConnectionrException(
                f"Max retries exceeded for {self.name}",
                type="fatal"
            )
```

## Configuration

### Check Interval

How often the loop runs:

```toml
[[Radarr]]
Name = "Radarr-4K"
CheckInterval = 60  # Check every 60 seconds (default)
```

**Tuning Recommendations:**

| Use Case | Interval | Rationale |
|----------|----------|-----------|
| High-activity server | 30s | Faster response to completed downloads |
| Normal usage | 60s | Good balance (default) |
| Low-power device | 300s | Reduce CPU/API load |
| Development/testing | 10s | Quick feedback for debugging |

### Delays After Actions

Control delays after specific operations:

```toml
[[Radarr]]
Name = "Radarr-4K"

# Wait 60s after importing before next loop
DelayAfterImport = 60

# Wait 5 minutes after triggering search
DelayAfterSearch = 300

# Wait 2 minutes after blacklisting
DelayAfterBlacklist = 120
```

**Why delays are needed:**
- Give Arr time to process imports
- Prevent hammering Arr API with searches
- Allow indexers time to respond to new searches

### Concurrent Checks

Limit parallel health checks:

```toml
[Settings]
MaxConcurrentChecks = 10  # Check up to 10 torrents simultaneously
```

**Impact:**
- Higher value: Faster loop completion, more CPU/API load
- Lower value: Slower loop, less resource usage
- Default (10): Good for most setups

## Loop State Machine

### Torrent States

Each torrent progresses through states:

```
        ┌─────────┐
        │ Detected│ (New torrent found in qBittorrent)
        └────┬────┘
             │
        ┌────▼─────────┐
        │ Downloading  │
        └────┬─────────┘
             │
    ┌────────┴────────┐
    │                 │
┌───▼────┐      ┌────▼─────┐
│Stalled │      │Completed │
└───┬────┘      └────┬─────┘
    │                │
┌───▼────┐      ┌────▼─────┐
│Failed  │      │Importing │
└───┬────┘      └────┬─────┘
    │                │
┌───▼────────┐  ┌────▼─────┐
│Blacklisted │  │Imported  │
└───┬────────┘  └────┬─────┘
    │                │
┌───▼────────┐  ┌────▼─────┐
│Re-searching│  │ Seeding  │
└────────────┘  └────┬─────┘
                     │
                ┌────▼─────┐
                │ Deleted  │ (After seed goals met)
                └──────────┘
```

### State Transitions

**Downloading → Completed:**
- Trigger: `torrent['progress'] == 1.0 && torrent['state'] == 'uploading'`
- Action: Mark as ready for import

**Downloading → Stalled:**
- Trigger: `ETA > MaxETA || no_progress_for > StallTimeout`
- Action: Monitor stall time, may blacklist if persistent

**Stalled → Downloading:**
- Trigger: Progress resumes
- Action: Resume normal monitoring

**Completed → Importing:**
- Trigger: Pass ffprobe validation (if enabled)
- Action: Call Arr import API

**Importing → Imported:**
- Trigger: Arr confirms import successful
- Action: Update database, start seeding phase

**Completed → Failed:**
- Trigger: Import fails, ffprobe validation fails
- Action: Mark for blacklisting

**Failed → Blacklisted:**
- Trigger: Retry limit exceeded
- Action: Add to Arr blacklist

**Blacklisted → Re-searching:**
- Trigger: `AutoReSearch == true` in config
- Action: Trigger new search in Arr

**Seeding → Deleted:**
- Trigger: Seed ratio/time goals met
- Action: Delete from qBittorrent

## Performance Considerations

### Loop Latency

**Factors affecting loop duration:**

1. **Number of torrents:** More torrents = longer loop
2. **API response time:** Slow Arr/qBittorrent = slower loop
3. **Health check complexity:** FFprobe checks add latency
4. **Database queries:** Large history = slower queries

**Typical loop times:**

| Torrents | Health Checks | Duration |
|----------|---------------|----------|
| 10 | None | 1-2s |
| 10 | FFprobe enabled | 5-15s |
| 50 | None | 5-10s |
| 50 | FFprobe enabled | 30-60s |
| 100+ | None | 15-30s |

### Optimization Strategies

**1. Batch API Calls**

```python
# BAD: One API call per torrent
for torrent in torrents:
    arr_item = arr_client.get_movie(torrent['media_id'])

# GOOD: Batch fetch
media_ids = [t['media_id'] for t in torrents]
arr_items = arr_client.get_movies(ids=media_ids)
```

**2. Cache Frequently Accessed Data**

```python
# Cache Arr quality profiles (rarely change)
@lru_cache(maxsize=1, ttl=3600)
def get_quality_profiles(self):
    return self.arr_client.get_quality_profiles()
```

**3. Parallel Health Checks**

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(self._check_health, t) for t in torrents]
    results = [f.result() for f in futures]
```

## Debugging

### Enable Loop Tracing

```toml
[Settings]
LogLevel = "DEBUG"
TraceLoopExecution = true
```

**Output:**

```
[DEBUG] Loop iteration 1234 started
[DEBUG] Fetch phase: Retrieved 15 torrents
[DEBUG] Classify phase: 10 tracked, 5 new
[DEBUG] Health check: torrent abc123 - ETA 1200s (under threshold 3600s)
[DEBUG] Action phase: Importing torrent abc123
[DEBUG] Update phase: Updated 15 entries in database
[DEBUG] Sleep phase: Waiting 60s
[DEBUG] Loop iteration 1234 completed in 2.5s
```

### Monitor Loop Performance

**WebUI Metrics (planned):**

```json
{
  "arr_instance": "Radarr-4K",
  "loop_iterations": 1234,
  "avg_loop_duration": 2.5,
  "max_loop_duration": 15.3,
  "errors_last_hour": 2,
  "torrents_imported_today": 10
}
```

### Common Issues

**Loop running too frequently:**
- Symptom: High CPU usage, excessive API calls
- Solution: Increase `CheckInterval`

**Loop taking too long:**
- Symptom: Delays between torrent completion and import
- Solution: Enable concurrent health checks, optimize queries

**Loop stuck:**
- Symptom: No log output, no imports happening
- Solution: Check for deadlocks in database, restart process

## Advanced Patterns

### Dynamic Interval Adjustment

Adjust interval based on activity:

```python
def _calculate_next_interval(self):
    active_downloads = self._count_active_downloads()

    if active_downloads > 10:
        return 30  # Check more frequently when busy
    elif active_downloads > 0:
        return 60  # Normal interval
    else:
        return 300  # Check infrequently when idle
```

### Priority Queue

Process high-priority torrents first:

```python
def _prioritize_torrents(self, torrents):
    # Sort by: completed > downloading > seeding
    return sorted(torrents, key=lambda t: (
        t['state'] != 'uploading',  # Completed first
        t['eta'],                   # Then by ETA
        t['added_on']               # Then by age
    ))
```

### Adaptive Rate Limiting

Back off API calls when rate limited:

```python
def _handle_rate_limit(self, response):
    if response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 60))
        raise DelayLoopException(length=retry_after, type="rate_limited")
```

## Related Documentation

- [Architecture](architecture.md) - Overall system design
- [Multiprocessing](multiprocessing.md) - Process management
- [Performance Tuning](performance.md) - Optimization guide
