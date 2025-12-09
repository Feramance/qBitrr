# Multiprocessing

qBitrr's multiprocessing architecture enables parallel execution and fault isolation for managing multiple Arr instances simultaneously.

## Architecture

### Process Model

```
┌──────────────────────────────────────────────────────────┐
│              Main Process (PID 1)                        │
│  - Configuration management                               │
│  - Process lifecycle orchestration                        │
│  - Signal handling (SIGTERM, SIGINT, SIGHUP)             │
│  - Health monitoring of child processes                   │
└──────────────────┬───────────────────────────────────────┘
                   │
         ┌─────────┼─────────┬─────────────────┐
         │         │         │                 │
    ┌────▼───┐ ┌──▼───┐ ┌───▼────┐     ┌─────▼──────┐
    │ WebUI  │ │Radarr│ │ Sonarr │ ... │   Lidarr   │
    │Process │ │  Mgr │ │   Mgr  │     │    Mgr     │
    │        │ │      │ │        │     │            │
    │Flask+  │ │Event │ │ Event  │     │   Event    │
    │Waitress│ │Loop  │ │  Loop  │     │   Loop     │
    └────────┘ └──────┘ └────────┘     └────────────┘
         │         │         │                 │
         └─────────┴─────────┴─────────────────┘
                           │
                  ┌────────▼─────────┐
                  │  Shared Resources │
                  │  - SQLite DB      │
                  │  - Config file    │
                  │  - Log files      │
                  └───────────────────┘
```

## Implementation

### Pathos Multiprocessing

qBitrr uses **`pathos.multiprocessing`** instead of stdlib `multiprocessing`:

**Why Pathos?**

| Feature | stdlib multiprocessing | pathos.multiprocessing |
|---------|----------------------|----------------------|
| Windows support | Limited (no fork) | Full support |
| Serialization | pickle (limited) | dill (comprehensive) |
| Process pools | Basic | Advanced management |
| Cross-platform | Platform-dependent | Unified API |

**File:** `qBitrr/main.py`

```python
from pathos.multiprocessing import ProcessingPool as Pool
from pathos.multiprocessing import Process
import multiprocessing as mp

def start_arr_manager(arr_config, shutdown_event):
    """Entry point for Arr manager process."""
    manager = create_arr_manager(arr_config)
    manager.run_loop(shutdown_event)

def main():
    # Create shutdown event (shared between processes)
    manager = mp.Manager()
    shutdown_event = manager.Event()

    processes = []

    # Start WebUI process
    webui_process = Process(
        target=start_webui,
        args=(CONFIG, shutdown_event),
        name="WebUI"
    )
    webui_process.start()
    processes.append(webui_process)

    # Start Arr manager processes
    for arr_config in CONFIG.get_arr_instances():
        arr_process = Process(
            target=start_arr_manager,
            args=(arr_config, shutdown_event),
            name=f"ArrManager-{arr_config.Name}"
        )
        arr_process.start()
        processes.append(arr_process)

    # Monitor processes
    monitor_processes(processes, shutdown_event)
```

### Process Communication

#### Shared State

**Event-based signaling:**

```python
import multiprocessing as mp

# Create shared event for shutdown coordination
manager = mp.Manager()
shutdown_event = manager.Event()

# In main process
shutdown_event.set()  # Signal all processes to stop

# In child process
while not shutdown_event.is_set():
    # Keep running
    pass
```

**Shared memory (avoided):**

qBitrr deliberately **avoids** shared memory between Arr managers for:
- Simplicity - No race conditions or locking complexity
- Isolation - One manager crash doesn't affect others
- Independence - Each manager operates autonomously

#### Database Access

All processes access SQLite with locking:

**File:** `qBitrr/db_lock.py`

```python
import threading

# Global lock for database access
db_lock = threading.RLock()

@contextmanager
def locked_database():
    """Context manager for safe database access."""
    with db_lock:
        yield
```

**Usage:**

```python
from qBitrr.db_lock import locked_database

# Process A
with locked_database():
    DownloadsModel.create(hash="abc", name="Movie")

# Process B (waits for Process A)
with locked_database():
    download = DownloadsModel.get(hash="abc")
```

### Process Lifecycle

#### Startup Sequence

```
1. Main Process Init
   ├─ Load configuration
   ├─ Initialize logging
   ├─ Create shutdown event
   └─ Initialize database

2. Spawn WebUI Process
   ├─ Initialize Flask app
   ├─ Start Waitress server
   └─ Enter serving loop

3. Spawn Arr Manager Processes (parallel)
   ├─ For each Arr instance in config
   │  ├─ Initialize Arr client
   │  ├─ Initialize qBittorrent client
   │  ├─ Load tracked torrents from DB
   │  └─ Enter event loop
   └─ Wait for all to initialize

4. Main Process Monitoring Loop
   ├─ Check process health every 30s
   ├─ Restart crashed processes
   └─ Wait for shutdown signal
```

#### Graceful Shutdown

**Signal handling:**

```python
import signal

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")

    # Signal all processes to stop
    shutdown_event.set()

    # Wait for processes to finish
    for process in processes:
        process.join(timeout=30)

        if process.is_alive():
            logger.warning(f"{process.name} did not stop, forcing...")
            process.terminate()
            process.join(timeout=5)

            if process.is_alive():
                logger.error(f"{process.name} won't die, killing...")
                process.kill()

    logger.info("All processes stopped")
    sys.exit(0)

# Register handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
```

#### Process Restart

**Auto-restart on crash:**

```python
def monitor_processes(processes, shutdown_event):
    """Monitor child processes and restart on failure."""
    while not shutdown_event.is_set():
        for i, process in enumerate(processes):
            if not process.is_alive() and not shutdown_event.is_set():
                logger.error(f"{process.name} died, restarting...")

                # Create new process with same config
                new_process = Process(
                    target=process._target,
                    args=process._args,
                    name=process.name
                )
                new_process.start()
                processes[i] = new_process

        time.sleep(30)  # Check every 30 seconds
```

## Resource Management

### Memory Isolation

Each process has independent memory:

**Typical memory usage:**

| Component | Memory | Notes |
|-----------|--------|-------|
| Main process | 50 MB | Minimal overhead |
| WebUI process | 80 MB | Flask + React assets |
| Arr manager (each) | 30 MB | Per instance |

**Example (4 Arr instances):**
- Main: 50 MB
- WebUI: 80 MB
- 4 × Arr managers: 120 MB
- **Total: ~250 MB**

### CPU Utilization

**Parallel execution benefits:**

```
Single-threaded (hypothetical):
  Radarr check: 2s
  Sonarr check: 2s
  Lidarr check: 2s
  Total: 6s per cycle

Multi-process (actual):
  All checks in parallel: 2s per cycle
  3x speedup!
```

**CPU core usage:**

```toml
[Settings]
MaxWorkers = 4  # Limit concurrent Arr managers

# If you have 8 cores, setting MaxWorkers = 6 ensures
# some cores remain available for OS and qBittorrent
```

### File Descriptor Limits

Each process opens connections to:
- qBittorrent API
- Arr APIs
- Database
- Log files

**Increase limits if needed:**

```bash
# Check current limit
ulimit -n

# Increase (temporary)
ulimit -n 4096

# Increase (permanent) - add to /etc/security/limits.conf
qbitrr soft nofile 4096
qbitrr hard nofile 8192
```

## Process Safety

### Database Contention

**Problem:** SQLite doesn't handle concurrent writes well

**Solution:** Global lock via `db_lock.py`

**Performance impact:**
- Read queries: No impact (SQLite allows concurrent reads)
- Write queries: Serialized (one at a time)

**Alternative (planned):** PostgreSQL support for true concurrent writes

### Logging Thread Safety

**File:** `qBitrr/logger.py`

Each process writes to separate log files:

```
logs/
├── Main.log              # Main process
├── WebUI.log            # WebUI process
├── Radarr-4K.log        # Radarr manager
├── Sonarr-TV.log        # Sonarr manager
└── Lidarr-Music.log     # Lidarr manager
```

**Thread-safe handlers:**

```python
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    filename=log_path,
    maxBytes=10485760,  # 10 MB
    backupCount=5,
    mode='a'
)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)

# Thread-safe by default
logger.addHandler(handler)
```

### Exception Handling

**Per-process error isolation:**

```python
def start_arr_manager(arr_config, shutdown_event):
    """Process entry point with error handling."""
    try:
        manager = create_arr_manager(arr_config)
        manager.run_loop(shutdown_event)
    except Exception as e:
        logger.exception(f"Fatal error in {arr_config.Name}: {e}")
        # Process exits, main process will restart it
        sys.exit(1)
```

## Performance Tuning

### Process Count Optimization

**Guideline:**

```
Optimal process count = Number of Arr instances + 2

Example:
- 3 Radarr instances
- 2 Sonarr instances
- 1 Lidarr instance
= 6 Arr managers + 1 WebUI + 1 Main = 8 processes total
```

**CPU cores:**
- 2 cores: Works, but may be sluggish with many instances
- 4 cores: Good for up to 6 Arr instances
- 8+ cores: Excellent for 10+ instances

### Process Priority

**Linux:**

```bash
# Run qBitrr with nice value (lower priority)
nice -n 10 qbitrr

# Or adjust running process
renice -n 10 -p $(pgrep -f qbitrr)
```

**Docker:**

```yaml
services:
  qbitrr:
    cpus: 2.0          # Limit to 2 CPU cores
    mem_limit: 512M    # Limit to 512 MB RAM
    cpu_shares: 512    # Lower priority (1024 = default)
```

### Connection Pooling

Each process maintains HTTP connection pools:

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Per-process session
session = requests.Session()

# Connection pooling
adapter = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=Retry(total=3, backoff_factor=1)
)

session.mount('http://', adapter)
session.mount('https://', adapter)
```

## Debugging

### Process Inspection

**List running processes:**

```bash
# Linux/macOS
ps aux | grep qbitrr

# Output:
# qbitrr  1234  1.0  0.5  Main
# qbitrr  1235  0.5  0.3  WebUI
# qbitrr  1236  0.3  0.2  ArrManager-Radarr-4K
# qbitrr  1237  0.3  0.2  ArrManager-Sonarr-TV
```

**Docker:**

```bash
docker top qbitrr

# Or detailed:
docker exec qbitrr ps aux
```

### Process-Specific Logs

Each process writes to its own log:

```bash
# Main process
tail -f ~/config/logs/Main.log

# Specific Arr manager
tail -f ~/config/logs/Radarr-4K.log

# All logs
tail -f ~/config/logs/*.log
```

### Deadlock Detection

**Symptoms:**
- Process hangs indefinitely
- No log output
- High CPU usage

**Debug:**

```bash
# Get process PID
pgrep -f "qbitrr"

# Attach debugger (Python)
py-spy dump --pid 1236

# Or send signal to dump stack trace
kill -USR1 1236  # Check logs for stack trace
```

## Docker Considerations

### Process Management

**PID 1 Problem:**

In Docker, the main process runs as PID 1, which has special signal handling.

**Solution:** qBitrr uses `tini` as init system:

```dockerfile
FROM python:3.12-slim

# Install tini
RUN apt-get update && apt-get install -y tini

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["qbitrr"]
```

**Benefits:**
- Proper signal forwarding
- Zombie process reaping
- Clean shutdown handling

### Resource Limits

**docker-compose.yml:**

```yaml
services:
  qbitrr:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 1G
        reservations:
          cpus: '1.0'
          memory: 256M
```

## Troubleshooting

### Process Won't Start

**Symptoms:** Process starts then immediately exits

**Debug:**

```bash
# Check logs
tail ~/config/logs/ArrManager-Radarr.log

# Common causes:
# - Configuration error
# - Can't connect to Arr/qBittorrent
# - Database locked
```

### Process Consuming Too Much Memory

**Debug:**

```bash
# Check memory usage
ps aux | grep qbitrr | awk '{print $6}'

# Or with Docker
docker stats qbitrr
```

**Solutions:**
- Reduce `CheckInterval` (checks less often)
- Lower `MaxConcurrentChecks`
- Limit torrent history retention

### Zombie Processes

**Symptoms:** Process shows as `<defunct>` in ps output

**Cause:** Parent process not calling `wait()` on exited children

**Solution:** Already handled by `tini` in Docker, or by proper signal handling in native installs

## Future Enhancements

**Planned for v6.0:**

- **Process Pools** - Reuse processes instead of spawning new ones
- **Dynamic Scaling** - Start/stop Arr managers based on load
- **IPC Optimization** - Faster inter-process communication
- **Async IO** - Reduce threads with asyncio (Python 3.11+ feature)

## Related Documentation

- [Architecture](architecture.md) - Overall system design
- [Event Loops](event-loops.md) - Loop mechanics per process
- [Performance Tuning](performance.md) - Optimize for your setup
- [Troubleshooting: Performance](../troubleshooting/performance.md) - Debug slow performance
