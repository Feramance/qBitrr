# Processes View

The **Processes View** provides real-time monitoring and control of qBitrr's multiprocessing architecture. Each Arr instance (Radarr/Sonarr/Lidarr) runs two independent processes—**search** and **torrent**—that can be monitored and restarted individually.

---

## Overview

qBitrr orchestrates torrent management across multiple Arr instances using a multiprocessing model. The Processes tab gives you visibility into:

- **Process Status**: Whether each process is running or stopped
- **Search Activity**: Latest search operations and their timestamps
- **Queue & Category Metrics**: Torrent counts in Arr queues and qBittorrent categories
- **Manual Restart**: Restart individual processes or rebuild all Arr connections

---

## Process Architecture

### Process Types

Each managed Arr instance spawns **two separate processes**:

1. **Search Process** (`search`)
    - Polls Radarr/Sonarr/Lidarr for missing/wanted media
    - Triggers searches based on EntrySearch configuration
    - Handles Overseerr/Ombi request integration
    - Logs the most recent search operation (e.g., "Movie Title (2023)")

2. **Torrent Process** (`torrent`)
    - Monitors qBittorrent for active torrents in the Arr's category
    - Performs health checks (stalled, failed, slow transfers)
    - Triggers instant imports when torrents complete
    - Cleans up completed/seeded torrents based on SeedingMode settings

### Special Processes

- **Free Space Manager**
    - Monitors disk space and pauses torrents when threshold is reached
    - Displays count of torrents paused due to low disk space

- **qBittorrent** (if configured as a category-only tracker)
    - Displays total torrent count in the category

---

## UI Layout

### Section Groups

Processes are grouped by application type:

- **Radarr**: All Radarr instances (e.g., `Radarr-Movies`, `Radarr-4K`)
- **Sonarr**: All Sonarr instances (e.g., `Sonarr-TV`, `Sonarr-Anime`)
- **qBittorrent**: Free space manager and category-only processes
- **Other**: Custom trackers or unclassified instances

### Process Cards

Each instance displays:

```plaintext
┌────────────────────────────────────┐
│ Instance Name          [Status]     │
│ 2 processes                          │
│                                      │
│ Search         🟢                    │
│ Last search: Movie Title (2023)     │
│ [Restart]                            │
│                                      │
│ Torrent        🟢                    │
│ Queue: 3 / Category: 12             │
│ [Restart]                            │
│                                      │
│           [Restart All]              │
└────────────────────────────────────┘
```

**Field Descriptions**:

| Field | Description |
|-------|-------------|
| **Instance Name** | Display name from config (e.g., `Radarr-Movies`) |
| **Status Indicator** | 🟢 All running, 🔴 All stopped, 🟠 Partial |
| **Search Summary** | Latest search description or "No searches recorded" |
| **Search Timestamp** | ISO 8601 timestamp of last search operation |
| **Queue Count** | Number of items in Arr's download queue (`/api/v3/queue`) |
| **Category Count** | Number of torrents in qBittorrent with matching category |
| **Metric Type** | Special metric for Free Space (`free-space`) or qBit (`category`) |

---

## Actions

### Restart Individual Process

**Location**: Process chip → **Restart** button
**Endpoint**: `POST /api/processes/<category>/<kind>/restart`

Terminates and recreates the specified process (search or torrent). Useful when:

- A search loop appears hung
- Torrent monitoring stops updating
- Process crashes and needs manual recovery

**Example**:
```bash
POST /api/processes/Radarr-Movies/search/restart
```

**Response**:
```json
{
  "status": "ok",
  "restarted": ["search"]
}
```

### Restart All Processes (Group)

**Location**: Process card → **Restart All** button

Restarts both search and torrent processes for the selected instance. Equivalent to:
```bash
POST /api/processes/Radarr-Movies/all/restart
```

### Restart All Processes (Global)

**Location**: Top toolbar → **Restart All** button
**Endpoint**: `POST /api/processes/restart_all`

Kills and recreates **all** search and torrent processes across **all** managed Arr instances. Use when:

- Configuration changes require full reload
- Systemwide performance issues
- Debugging connectivity problems

**Confirmation Required**: Modal dialog prevents accidental execution.

### Rebuild Arrs

**Location**: Top toolbar → **Rebuild Arrs** button
**Endpoint**: `POST /api/arr/rebuild`

Recreates the entire Arr manager subsystem:

1. Terminates all existing processes
2. Reloads configuration from `config.toml`
3. Re-establishes Arr API connections
4. Recreates qBittorrent client
5. Spawns new search and torrent processes

**Use Cases**:

- After adding/removing Arr instances in config
- After changing Arr URIs or API keys
- When Arr connections appear corrupted

**⚠️ Warning**: This operation interrupts all torrent management for 5-15 seconds.

---

## Refresh Behavior

The Processes view **auto-refreshes** at adaptive intervals:

| Condition | Refresh Interval |
|-----------|------------------|
| Active search process running | 5 seconds |
| Queue activity (count > 0) | 10 seconds |
| Idle (no activity) | 20 seconds |
| Tab inactive | Paused (resumes on tab focus) |

**Manual Refresh**: Click the **Refresh** button to force an immediate update.

---

## Process States

### Running (🟢)

- Process has a valid PID
- `is_alive()` returns `True`
- Process is actively polling Arr APIs or qBittorrent

### Stopped (🔴)

- Process terminated (expected shutdown)
- Process crashed and was not auto-restarted
- `AutoRestartProcesses` disabled in config

### Rebuilding (🔄)

- Arr rebuild in progress
- All processes show as inactive during rebuild
- Processes respawn within 10-30 seconds

---

## Metrics Explained

### Search Process

**Field**: `searchSummary`
**Source**: `qBitrr/search_activity_store.py`

Displays the most recent search operation formatted as:

- **Radarr**: `Movie Title (Year)`
- **Sonarr**: `Series Name | S01E02`
- **Generic**: Raw search description

**Sanitization**:

- Removes release tokens (720p, WEB-DL, x264)
- Removes excessive year/date duplicates
- Trims to first sentence if multi-line

**Example**:
```
Before: "Inception 2010 1080p BluRay x264-GROUP"
After:  "Inception (2010)"
```

### Torrent Process

**Field**: `queueCount` (Arr queue) + `categoryCount` (qBit category)

- **Queue Count**: Active downloads in Arr's `/api/v3/queue`
- **Category Count**: Torrents in qBittorrent matching `Settings.CategoryX`

**Metric Types**:

| Type | Description | Queue | Category |
|------|-------------|-------|----------|
| `arr` (default) | Standard Radarr/Sonarr | ✓ | ✓ |
| `category` | qBit category tracker | ❌ | ✓ |
| `free-space` | Free Space Manager | ✓ | ✓ (paused count) |

---

## API Reference

### GET /api/processes

**Description**: Fetch process states and metrics for all managed instances.

**Headers**:
```http
Authorization: Bearer <token>
```

**Response**:
```json
{
  "processes": [
    {
      "category": "Radarr-Movies",
      "name": "Radarr-Movies",
      "kind": "search",
      "pid": 12345,
      "alive": true,
      "rebuilding": false,
      "searchSummary": "Inception (2010)",
      "searchTimestamp": "2025-11-27T10:30:15Z"
    },
    {
      "category": "Radarr-Movies",
      "name": "Radarr-Movies",
      "kind": "torrent",
      "pid": 12346,
      "alive": true,
      "queueCount": 3,
      "categoryCount": 12
    }
  ]
}
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `category` | `string` | qBittorrent category identifier |
| `name` | `string` | Display name from config |
| `kind` | `string` | `search`, `torrent`, or other |
| `pid` | `int` \| `null` | Process ID (null if not started) |
| `alive` | `boolean` | Whether process is running |
| `rebuilding` | `boolean` | Arr rebuild in progress |
| `searchSummary` | `string` | Latest search description (search only) |
| `searchTimestamp` | `string` | ISO 8601 timestamp (search only) |
| `queueCount` | `int` | Arr queue count (torrent only) |
| `categoryCount` | `int` | qBit category count (torrent only) |
| `metricType` | `string` | `category`, `free-space`, or absent |

### POST /api/processes/:category/:kind/restart

**Description**: Restart a specific process.

**Path Parameters**:

- `category`: Instance category (e.g., `Radarr-Movies`)
- `kind`: Process type (`search`, `torrent`, or `all`)

**Response**:
```json
{
  "status": "ok",
  "restarted": ["search"]
}
```

### POST /api/processes/restart_all

**Description**: Restart all search and torrent processes globally.

**Response**:
```json
{
  "status": "ok"
}
```

### POST /api/arr/rebuild

**Description**: Rebuild the entire Arr manager subsystem.

**Response**:
```json
{
  "status": "ok"
}
```

---

## Configuration

### AutoRestartProcesses

**Path**: `Settings.AutoRestartProcesses`
**Type**: `bool`
**Default**: `true`

Automatically restart processes that crash or exit unexpectedly.

**Example** (`config.toml`):
```toml
[Settings]
AutoRestartProcesses = true
MaxProcessRestarts = 3
ProcessRestartWindow = 300  # 5 minutes
ProcessRestartDelay = 10    # 10 seconds
```

See [Process Management](../features/process-management.md) for restart policies.

---

## Troubleshooting

### Process shows as stopped but was not manually terminated

**Possible Causes**:

1. Process crashed due to unhandled exception
2. API connection to Arr timed out repeatedly
3. Database lock contention (SQLite)
4. Out of memory (OOM killer on Linux)

**Solutions**:

- Check `Main.log` or `<ArrName>.log` for traceback
- Increase `Settings.LoopSleepTimer` to reduce API call frequency
- Verify Arr URI and API key are correct
- Restart the process manually

### Search summary shows "No searches recorded"

**Possible Causes**:

1. Search process just started and hasn't run a cycle yet
2. `EntrySearch.SearchMissing` is disabled
3. No missing media to search
4. Search database (`search_activity.db`) was cleared

**Solutions**:

- Wait 1-2 minutes for first search cycle
- Verify `SearchMissing = true` in config
- Check Arr's "Wanted" page for missing items

### Queue count doesn't match qBittorrent UI

**Possible Causes**:

1. Torrents in qBit don't have Arr tags (if `Settings.Tagless = false`)
2. Torrent category mismatch
3. Caching delay (up to 20 seconds)

**Solutions**:

- Verify torrents have tags matching `Settings.CategoryX`
- Check torrent category in qBit matches `Settings.CategoryX`
- Force refresh to clear cache

---

## See Also

- [Process Management](../features/process-management.md) – Auto-restart policies and multiprocessing architecture
- [WebUI Configuration](../configuration/webui.md) – WebUI settings and authentication
- [Logs View](logs.md) – Real-time log streaming for debugging processes
- [API Documentation](api.md) – Full API endpoint reference
