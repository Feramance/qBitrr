# Architecture

Detailed overview of qBitrr's system architecture and design patterns.

## System Design

qBitrr uses a multi-process architecture designed for reliability, scalability, and isolation:

```
┌─────────────────────────────────────────────────────────────┐
│                       Main Process                           │
│  - Orchestrates all worker processes                        │
│  - Manages process lifecycle (start/stop/restart)           │
│  - Monitors health of child processes                       │
│  - Handles graceful shutdown                                │
└─────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │ WebUI Process│    │ Arr Manager  │    │ Arr Manager  │
    │              │    │  (Radarr-4K) │    │ (Sonarr-TV)  │
    │ - Flask API  │    │              │    │              │
    │ - Waitress   │    │ - Event Loop │    │ - Event Loop │
    │ - React SPA  │    │ - Health Mon │    │ - Health Mon │
    └──────────────┘    └──────────────┘    └──────────────┘
           │                    │                    │
           └────────────────────┴────────────────────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │    qBittorrent      │
                    │  - Torrent Client   │
                    │  - Web API (v4/v5)  │
                    └─────────────────────┘
```

### Core Processes

#### Main Process
**File:** `qBitrr/main.py`

Responsibilities:
- Initializes configuration and logging
- Spawns WebUI and Arr manager processes using `pathos.multiprocessing`
- Monitors child process health and restarts on failure
- Handles SIGTERM, SIGINT for graceful shutdown
- Coordinates cross-process communication via shared queue

#### WebUI Process
**File:** `qBitrr/webui.py`

Responsibilities:
- Serves Flask REST API on `/api/*` routes
- Hosts React SPA from `qBitrr/static/`
- Provides token-based authentication for API endpoints
- Streams logs in real-time via WebSocket (planned)
- Exposes health check endpoint for monitoring

#### Arr Manager Processes
**File:** `qBitrr/arss.py`

Each configured Arr instance (Radarr/Sonarr/Lidarr) runs in an isolated process:

Responsibilities:
- Runs independent event loop checking qBittorrent every N seconds
- Queries Arr API for media information
- Performs health checks on torrents
- Triggers imports when torrents complete
- Manages blacklisting and re-searching
- Tracks state in SQLite database

### Background Threads

#### Auto-Update Monitor
**File:** `qBitrr/auto_update.py`

- Runs in main process as daemon thread
- Checks GitHub releases for new versions
- Downloads and validates release packages
- Triggers restart when update is available
- Configurable update channel (stable/nightly)

#### Network Monitor
**File:** `qBitrr/main.py`

- Monitors connectivity to qBittorrent and Arr instances
- Retries connections with exponential backoff
- Logs connection state changes
- Triggers process restart on persistent failures

#### FFprobe Downloader
**File:** `qBitrr/ffprobe.py`

- Downloads ffprobe binary if not found
- Validates media files before import
- Runs in background to avoid blocking operations
- Caches results to reduce repeated checks

## Data Flow

### Torrent Processing Pipeline

```
1. Detection
   qBittorrent API → Arr Manager
   - Fetch all torrents with Arr tags
   - Filter by configured categories

2. Classification
   Arr Manager → Database
   - Check if torrent is tracked in downloads table
   - Determine state: downloading, stalled, completed, seeding

3. Health Check
   Arr Manager → qBittorrent API
   - Check ETA vs. MaxETA threshold
   - Monitor stall time vs. StallTimeout
   - Verify tracker status

4. Action Decision
   Arr Manager Logic
   - Import: completed + valid → trigger Arr import
   - Blacklist: failed health → add to Arr blacklist
   - Re-search: blacklisted → trigger new search
   - Cleanup: seeded enough → delete from qBittorrent

5. State Update
   Arr Manager → Database
   - Update downloads table with new state
   - Record actions taken for audit trail
   - Update expiry times for cleanup
```

### Configuration Flow

```
1. Load
   TOML file → config.py:MyConfig
   - Parse with tomli (read) or tomli_w (write)
   - Validate required fields
   - Apply config migrations if version mismatch

2. Environment Override
   env_config.py
   - Check for QBITRR_* environment variables
   - Override TOML values with env vars
   - Useful for Docker deployments

3. Validation
   config.py:validate_config()
   - Check required values present
   - Validate URLs, API keys
   - Test connections to services

4. Distribution
   CONFIG singleton → All processes
   - Main process loads config once
   - Passed to child processes on spawn
   - WebUI reads from shared config
```

### API Request Flow

```
Client → WebUI Flask API → Backend Logic → Database/Arr APIs
  |          |                    |               |
  |     Authentication       Process Request    Return Data
  |    (WebUIToken)          (query/mutate)
  |          |                    |               |
  └──────────┴────────────────────┴───────────────┘
                      JSON Response
```

## Component Interactions

### Multiprocessing Architecture

qBitrr uses `pathos.multiprocessing` for cross-platform compatibility:

**Why pathos instead of stdlib multiprocessing?**
- Better Windows support (no fork())
- Dill-based serialization (more flexible than pickle)
- Process pool management with restart capabilities

**Process Communication:**
- Each Arr manager is **isolated** - no shared memory between managers
- WebUI reads database directly for stats (no IPC needed)
- Logging uses thread-safe file handlers with `db_lock.py`

**Benefits:**
- **Fault Isolation** - One Arr instance crash doesn't affect others
- **Scalability** - CPU-bound work parallelized across cores
- **Simplicity** - No complex IPC protocols needed

### Database Architecture

**File:** `qBitrr/tables.py`

qBitrr uses **Peewee ORM** with **SQLite**:

#### Schema

```python
# downloads table
class DownloadsModel:
    hash: str          # Torrent hash (primary key)
    name: str          # Torrent name
    arr_type: str      # "radarr", "sonarr", "lidarr"
    arr_name: str      # Arr instance name
    media_id: int      # Movie/Series/Album ID in Arr
    state: str         # "downloading", "stalled", "completed", etc.
    added_at: datetime # When torrent was added to qBittorrent
    updated_at: datetime # Last state update

# searches table
class SearchModel:
    id: int            # Auto-increment primary key
    arr_type: str
    arr_name: str
    media_id: int
    query: str         # Search query sent to Arr
    searched_at: datetime
    result_count: int

# expiry table
class EntryExpiry:
    entry_id: str      # Foreign key to downloads.hash
    expires_at: datetime # When to delete entry
```

#### Locking Strategy

**File:** `qBitrr/db_lock.py`

All database access uses context manager:

```python
with locked_database():
    # Acquire exclusive lock
    DownloadsModel.create(...)
    # Released on exit
```

**Why locks are needed:**
- Multiple Arr manager processes write concurrently
- SQLite doesn't handle concurrent writes well by default
- Lock ensures ACID properties maintained

#### Migration Strategy

**File:** `qBitrr/config.py:apply_config_migrations()`

When schema changes:
1. Bump `CURRENT_CONFIG_VERSION` constant
2. Add migration logic to detect old version
3. Apply ALTER TABLE / data transformations
4. Update config version in database

### Event Loop Architecture

**File:** `qBitrr/arss.py:ArrManagerBase.run_loop()`

Each Arr instance runs this loop:

```python
while not shutdown_event.is_set():
    try:
        # 1. Fetch torrents from qBittorrent
        torrents = qbt_client.get_torrents(category=self.category)

        # 2. Check database for tracked state
        tracked = DownloadsModel.select().where(...)

        # 3. Process each torrent
        for torrent in torrents:
            self._process_torrent(torrent)

        # 4. Cleanup old entries
        self._cleanup_expired()

        # 5. Sleep until next check
        time.sleep(self.check_interval)

    except DelayLoopException as e:
        # Temporary delay (network issue)
        time.sleep(e.length)

    except RestartLoopException:
        # Config changed, restart loop
        self._reload_config()
        continue
```

**Exception-Based Control Flow:**

- `DelayLoopException` - Pause loop temporarily (connection failures)
- `RestartLoopException` - Restart loop from beginning (config reload)
- `SkipException` - Skip processing single torrent, continue loop
- `NoConnectionrException` - Connection failure, retry with backoff

## Security Architecture

### Authentication

**WebUI Token:**
```toml
[Settings]
WebUIToken = "your-secure-token"
```

- All `/api/*` endpoints check `X-API-Token` header
- Token stored in config.toml (not in database)
- React app reads token from localStorage
- No session management needed (stateless)

### Network Binding

**Configuration:**
```toml
[Settings]
WebUIHost = "127.0.0.1"  # Localhost only
WebUIPort = 6969
```

- Default: `0.0.0.0` (all interfaces) for Docker
- Recommended: `127.0.0.1` for native installs behind reverse proxy
- No TLS built-in - use reverse proxy (nginx/Caddy) for HTTPS

### Input Validation

- All API inputs validated via Pydantic models (planned)
- SQL injection prevented by Peewee ORM parameterization
- File paths validated to prevent directory traversal
- Config values sanitized before passing to shell commands

## Performance Characteristics

### Resource Usage

**Typical Load (4 Arr instances, 50 torrents):**
- CPU: 1-2% average, 5-10% during health checks
- RAM: 150-250 MB
- Disk I/O: Minimal (SQLite writes are batched)
- Network: 1-5 KB/s (API polling)

**Scaling:**
- Each Arr instance adds ~30 MB RAM
- Check interval trades CPU for responsiveness
- Database size grows with torrent history (auto-vacuum mitigates)

### Bottlenecks

1. **SQLite Write Contention** - Mitigated by locking, future: PostgreSQL support
2. **Arr API Rate Limits** - Batched requests, exponential backoff
3. **qBittorrent API Overhead** - Fetch only needed fields, cache responses

## Extensibility

### Adding New Arr Types

1. Subclass `ArrManagerBase` in `arss.py`
2. Implement `_process_failed_individual()` method
3. Register in `main.py:start_arr_manager()`
4. Add config section to `gen_config.py:MyConfig`

### Custom Healthcheck Logic

Override in subclass:

```python
class CustomRadarrManager(RadarrManager):
    def _is_torrent_healthy(self, torrent):
        # Custom logic here
        return super()._is_torrent_healthy(torrent)
```

### Plugin System

Planned for v6.0:
- Pre/post hooks for all operations
- Python plugin API
- WebUI extensions via iframe

## Further Reading

- [Event Loops](event-loops.md) - Deep dive into loop mechanics
- [Database Schema](database.md) - Complete schema documentation
- [Multiprocessing](multiprocessing.md) - Process management details
- [Performance Tuning](performance.md) - Optimization strategies
