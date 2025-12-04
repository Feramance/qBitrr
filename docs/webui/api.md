# WebUI API Reference

Complete API reference for qBitrr's WebUI REST API. All endpoints are accessible via the built-in WebUI server (default port 6969).

---

## Overview

### Base URL

```
http://<host>:<port>
```

**Default**: `http://localhost:6969`

### Endpoint Patterns

qBitrr provides dual endpoint patterns for flexibility:

| Pattern | Purpose | Authentication | Use Case |
|---------|---------|----------------|----------|
| `/api/*` | API-first endpoints | **Required** (Bearer token) | External clients, scripts, automation |
| `/web/*` | First-party endpoints | **Optional** (no token required) | WebUI, reverse proxies with auth bypass |

Both patterns return identical responses. Choose based on your authentication requirements.

---

## Authentication

### Bearer Token

If `WebUI.Token` is configured, `/api/*` endpoints require authentication via Bearer token:

**Header**:
```http
Authorization: Bearer <token>
```

**Query Parameter** (alternative):
```
?token=<token>
```

**Example**:
```bash
curl -H "Authorization: Bearer abc123..." http://localhost:6969/api/processes
```

### Public Endpoints

The following endpoints are **always public** (no authentication):

- `GET /health` - Health check
- `GET /` - Root redirect
- `GET /ui` - WebUI entry point
- `GET /sw.js` - Service worker
- `GET /static/*` - Static assets
- `GET /web/*` - All first-party endpoints

### Token Retrieval

**Endpoint**: `GET /api/token`

**Authentication**: Required

**Response**:
```json
{
  "token": "abc123def456..."
}
```

**Use Case**: Retrieve current token for API clients.

---

## Endpoint Categories

1. [System](#system-endpoints) - Health, status, version info
2. [Processes](#process-endpoints) - Process monitoring and control
3. [Logs](#log-endpoints) - Log file access
4. [Arr Views](#arr-view-endpoints) - Radarr/Sonarr/Lidarr library browsing
5. [Configuration](#configuration-endpoints) - Config management
6. [Updates](#update-endpoints) - Auto-update and version management

---

## System Endpoints

### Health Check

Check if WebUI is running.

**Endpoint**: `GET /health`

**Authentication**: None

**Response**:
```json
{
  "status": "ok"
}
```

**Use Case**: Monitoring, reverse proxy health checks, container liveness probes.

---

### Root Redirect

Redirect to WebUI.

**Endpoint**: `GET /`

**Authentication**: None

**Response**: HTTP 302 redirect to `/ui`

---

### WebUI Entry Point

Serve React SPA.

**Endpoint**: `GET /ui`

**Authentication**: None

**Response**: HTTP 302 redirect to `/static/index.html`

**Headers**:
```http
Cache-Control: no-cache, no-store, must-revalidate
Pragma: no-cache
Expires: 0
```

---

### Service Worker

Serve service worker for PWA support.

**Endpoint**: `GET /sw.js`

**Authentication**: None

**Response**: JavaScript file (text/javascript)

**Headers**:
```http
Cache-Control: no-cache, no-store, must-revalidate
```

**Use Case**: Progressive Web App functionality, offline support.

---

### System Status

Get qBittorrent and Arr instance statuses.

**Endpoints**:
- `GET /api/status` (requires auth)
- `GET /web/status` (public)

**Response**:
```json
{
  "qbit": {
    "alive": true,
    "host": "localhost",
    "port": 8080,
    "version": "4.6.0"
  },
  "arrs": [
    {
      "category": "radarr-4k",
      "name": "Radarr-4K",
      "type": "radarr",
      "alive": true
    },
    {
      "category": "sonarr-tv",
      "name": "Sonarr-TV",
      "type": "sonarr",
      "alive": true
    }
  ],
  "ready": true
}
```

**Fields**:

- `qbit.alive` - qBittorrent connection status
- `qbit.version` - qBittorrent version string
- `arrs[].alive` - Arr instance process health (checks both search and torrent processes)
- `ready` - Overall system ready state

---

### Version Metadata

Get current version, latest version, update availability, and changelog.

**Endpoints**:
- `GET /api/meta` (requires auth)
- `GET /web/meta` (public)

**Query Parameters**:
- `force` (boolean, optional) - Force refresh from GitHub (bypasses 1-hour cache)

**Response**:
```json
{
  "current_version": "5.2.0",
  "latest_version": "5.3.0",
  "update_available": true,
  "changelog": "## What's Changed\n- Added feature X\n- Fixed bug Y",
  "current_version_changelog": "## Previous Release\n- Added feature A",
  "changelog_url": "https://github.com/Feramance/qBitrr/releases/tag/v5.3.0",
  "repository_url": "https://github.com/Feramance/qBitrr",
  "homepage_url": "https://github.com/Feramance/qBitrr",
  "last_checked": "2025-11-27T12:00:00Z",
  "installation_type": "pip",
  "error": null,
  "update_state": {
    "in_progress": false,
    "last_result": null,
    "last_error": null,
    "completed_at": null
  }
}
```

**Installation Types**:

- `pip` - Installed via pip/PyPI
- `docker` - Running in Docker container
- `binary` - Standalone binary
- `source` - Running from source
- `unknown` - Cannot determine

**Update State**:

- `in_progress` - Manual update in progress
- `last_result` - `"success"` or `"error"` (last update result)
- `last_error` - Error message (if last update failed)
- `completed_at` - ISO 8601 timestamp (when last update completed)

**Caching**: Results cached for 1 hour. Use `?force=true` to bypass cache.

---

## Process Endpoints

### List Processes

Get all Arr instance processes (search and torrent loops).

**Endpoints**:
- `GET /api/processes` (requires auth)
- `GET /web/processes` (public)

**Response**:
```json
{
  "processes": [
    {
      "category": "radarr-4k",
      "name": "Radarr-4K",
      "kind": "search",
      "pid": 12345,
      "alive": true,
      "rebuilding": false,
      "searchSummary": "Found 12 missing movies, searched 5",
      "searchTimestamp": "2025-11-27T12:00:00Z"
    },
    {
      "category": "radarr-4k",
      "name": "Radarr-4K",
      "kind": "torrent",
      "pid": 12346,
      "alive": true,
      "rebuilding": false,
      "queueCount": 3,
      "categoryCount": 8
    }
  ]
}
```

**Fields**:

- `kind` - Process type (`"search"` or `"torrent"`)
- `pid` - Process ID (null if not started)
- `alive` - Process running state
- `rebuilding` - Global rebuild state (all processes restarting)

**Search Process Fields**:

- `searchSummary` - Human-readable search status (e.g., "Searched 5 movies, found 2 missing")
- `searchTimestamp` - Last search activity timestamp (ISO 8601)

**Torrent Process Fields**:

- `queueCount` - Active downloads in Arr queue
- `categoryCount` - Torrents in qBittorrent with matching category
- `metricType` - Special metric type (`"free-space"` or `"category"` for PlaceHolderArr)

**Refresh Interval**: Poll this endpoint every 5-10 seconds for real-time updates.

---

### Restart Process

Restart specific Arr instance process(es).

**Endpoints**:
- `POST /api/processes/<category>/<kind>/restart` (requires auth)
- `POST /web/processes/<category>/<kind>/restart` (public)

**Path Parameters**:

- `category` (string, required) - Arr instance category (e.g., `radarr-4k`)
- `kind` (string, required) - Process type: `search`, `torrent`, or `all`

**Request**: No body required

**Response** (Success):
```json
{
  "status": "ok",
  "restarted": ["search", "torrent"]
}
```

**Response** (Error):
```json
{
  "error": "Unknown category radarr-4k"
}
```

**HTTP Status Codes**:

- `200` - Success
- `400` - Invalid kind parameter
- `404` - Unknown category
- `503` - Arr manager not ready

**Behavior**:

1. Kills existing process(es) via `SIGTERM`
2. Removes from child process list
3. Spawns new process(es) via multiprocessing
4. Returns immediately (restart is asynchronous)

---

### Restart All Processes

Restart all Arr instance processes (global restart).

**Endpoints**:
- `POST /api/processes/restart_all` (requires auth)
- `POST /web/processes/restart_all` (public)

**Request**: No body required

**Response**:
```json
{
  "status": "ok",
  "restarted": [
    "radarr-4k.search",
    "radarr-4k.torrent",
    "sonarr-tv.search",
    "sonarr-tv.torrent"
  ]
}
```

**Behavior**: Iterates through all managed Arr instances and restarts both search and torrent processes.

---

### Change Log Level

Dynamically change application log level without restart.

**Endpoints**:
- `POST /api/loglevel` (requires auth)
- `POST /web/loglevel` (public)

**Request Body**:
```json
{
  "level": "DEBUG"
}
```

**Valid Levels**: `CRITICAL`, `ERROR`, `WARNING`, `NOTICE`, `INFO`, `DEBUG`, `TRACE`

**Response** (Success):
```json
{
  "status": "ok",
  "level": "DEBUG"
}
```

**Response** (Error):
```json
{
  "error": "Invalid log level"
}
```

**Behavior**:

1. Updates root logger level
2. Updates all child loggers (qBitrr, qBitrr.arr, qBitrr.webui, etc.)
3. Changes take effect immediately (no restart required)
4. Does **not** persist to config file

---

### Rebuild Arr Databases

Trigger database rebuild for all Arr instances.

**Endpoints**:
- `POST /api/arr/rebuild` (requires auth)
- `POST /web/arr/rebuild` (public)

**Request**: No body required

**Response**:
```json
{
  "status": "started"
}
```

**Behavior**:

1. Spawns background thread
2. Restarts all Arr instances sequentially
3. Triggers `db_update()` for each instance
4. Refreshes cached library data from Arr APIs
5. Returns immediately (rebuild is asynchronous)

**Use Case**: Force refresh after bulk library changes in Radarr/Sonarr/Lidarr.

---

### Restart Arr Instance

Restart specific Arr instance (both search and torrent processes).

**Endpoints**:
- `POST /api/arr/<section>/restart` (requires auth)
- `POST /web/arr/<section>/restart` (public)

**Path Parameters**:

- `section` (string, required) - Arr instance key (e.g., `Radarr-4K`, `Sonarr-TV`)

**Request**: No body required

**Response** (Success):
```json
{
  "status": "ok",
  "restarted": ["search", "torrent"]
}
```

**Response** (Error)**:
```json
{
  "error": "Unknown section Radarr-4K"
}
```

**HTTP Status Codes**:

- `200` - Success
- `404` - Unknown section
- `503` - Arr manager not ready

---

## Log Endpoints

### List Log Files

Get all available log files.

**Endpoints**:
- `GET /api/logs` (requires auth)
- `GET /web/logs` (public)

**Response**:
```json
{
  "files": [
    {
      "name": "Main.log",
      "path": "/config/logs/Main.log",
      "size": 1048576,
      "modified": "2025-11-27T12:00:00Z"
    },
    {
      "name": "WebUI.log",
      "path": "/config/logs/WebUI.log",
      "size": 524288,
      "modified": "2025-11-27T11:30:00Z"
    }
  ]
}
```

**Fields**:

- `name` - Filename (used in subsequent requests)
- `path` - Absolute path on disk
- `size` - File size in bytes
- `modified` - Last modified timestamp (ISO 8601)

**Log Rotation**: Log files rotate at 10 MB, keeping 5 backups. Older backups appear as `Main.log.1`, `Main.log.2`, etc.

---

### Get Log Content

Stream log file content as plain text.

**Endpoints**:
- `GET /api/logs/<name>` (requires auth)
- `GET /web/logs/<name>` (public)

**Path Parameters**:

- `name` (string, required) - Log filename (e.g., `Main.log`)

**Response**: Plain text (MIME type: `text/plain; charset=utf-8`)

**Headers**:
```http
Cache-Control: no-cache
Content-Type: text/plain; charset=utf-8
```

**Example**:
```bash
curl http://localhost:6969/web/logs/Main.log
```

**Behavior**:

- Reads entire log file into memory
- Returns full content (supports dynamic loading in LazyLog component)
- Invalid UTF-8 sequences ignored (errors="ignore")

---

### Download Log File

Download log file as attachment.

**Endpoints**:
- `GET /api/logs/<name>/download` (requires auth)
- `GET /web/logs/<name>/download` (public)

**Path Parameters**:

- `name` (string, required) - Log filename

**Response**: File attachment (MIME type: `application/octet-stream`)

**Headers**:
```http
Content-Disposition: attachment; filename="Main.log"
```

**Example**:
```bash
curl -O http://localhost:6969/web/logs/Main.log/download
```

---

## Arr View Endpoints

### Radarr Movies

Browse Radarr movie library from cached database.

**Endpoints**:
- `GET /api/radarr/<category>/movies` (requires auth)
- `GET /web/radarr/<category>/movies` (public)

**Path Parameters**:

- `category` (string, required) - Radarr instance category (e.g., `radarr-4k`)

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | null | Search query (title substring match) |
| `page` | integer | 0 | Page number (0-indexed) |
| `page_size` | integer | 50 | Results per page (1-100) |
| `year_min` | integer | null | Minimum release year filter |
| `year_max` | integer | null | Maximum release year filter |
| `monitored` | boolean | null | Filter by monitored status |
| `has_file` | boolean | null | Filter by file availability |
| `quality_met` | boolean | null | Filter by quality profile met |
| `is_request` | boolean | null | Filter by request status (Ombi/Overseerr) |

**Response**:
```json
{
  "category": "radarr-4k",
  "counts": {
    "available": 120,
    "monitored": 150,
    "missing": 30,
    "quality_met": 100,
    "requests": 5
  },
  "total": 150,
  "page": 0,
  "page_size": 50,
  "movies": [
    {
      "id": 1,
      "title": "Inception",
      "year": 2010,
      "monitored": true,
      "hasFile": true,
      "movieFileId": 12345,
      "tmdbId": 27205,
      "imdbId": "tt1375666",
      "qualityMet": true,
      "isRequest": false,
      "upgrade": false,
      "customFormatScore": 0,
      "minCustomFormatScore": 0,
      "customFormatMet": true,
      "reason": null,
      "qualityProfileId": 1,
      "qualityProfileName": "Ultra-HD"
    }
  ]
}
```

**Fields**:

- `counts` - Aggregate totals (unaffected by pagination)
- `total` - Total movies matching filters
- `page` / `page_size` - Pagination echo
- `movies[].reason` - Why entry appears in search results (e.g., "Missing", "Quality Unmet")

**Performance**: Uses cached database (SQLite). For real-time data, enable `WebUI.LiveArr = true` (increases Arr API load).

---

### Sonarr Series

Browse Sonarr series library from cached database.

**Endpoints**:
- `GET /api/sonarr/<category>/series` (requires auth)
- `GET /web/sonarr/<category>/series` (public)

**Path Parameters**:

- `category` (string, required) - Sonarr instance category

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | null | Search query (series title) |
| `page` | integer | 0 | Page number |
| `page_size` | integer | 25 | Results per page |
| `missing` / `only_missing` | boolean | false | Show only missing episodes |

**Response**:
```json
{
  "category": "sonarr-tv",
  "counts": {
    "available": 500,
    "monitored": 600,
    "missing": 100
  },
  "total": 50,
  "page": 0,
  "page_size": 25,
  "series": [
    {
      "series": {
        "id": 1,
        "title": "Breaking Bad",
        "tvdbId": 81189,
        "seriesType": "standard",
        "monitored": true,
        "qualityProfileId": 1,
        "qualityProfileName": "HD-1080p"
      },
      "totals": {
        "available": 62,
        "monitored": 62,
        "missing": 0
      },
      "seasons": [
        {
          "seasonNumber": 1,
          "available": 7,
          "monitored": 7,
          "missing": 0,
          "episodes": [
            {
              "id": 101,
              "episodeNumber": 1,
              "title": "Pilot",
              "airDateUtc": "2008-01-20T00:00:00Z",
              "hasFile": true,
              "episodeFileId": 1001,
              "monitored": true
            }
          ]
        }
      ]
    }
  ]
}
```

**Grouping**: Episodes grouped by series → season (hierarchical structure).

---

### Lidarr Albums

Browse Lidarr album library from cached database.

**Endpoints**:
- `GET /api/lidarr/<category>/albums` (public, no auth endpoint exists)
- `GET /web/lidarr/<category>/albums` (public)

**Path Parameters**:

- `category` (string, required) - Lidarr instance category

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | null | Search query (artist or album name) |
| `page` | integer | 0 | Page number |
| `page_size` | integer | 25 | Results per page |
| `monitored` | boolean | null | Filter by monitored status |
| `has_file` | boolean | null | Filter by file availability |

**Response**:
```json
{
  "category": "lidarr",
  "counts": {
    "available": 200,
    "monitored": 250,
    "missing": 50,
    "quality_met": 180,
    "requests": 2
  },
  "total": 250,
  "page": 0,
  "page_size": 25,
  "albums": [
    {
      "album": {
        "id": 1,
        "title": "Dark Side of the Moon",
        "artistId": 1,
        "artistName": "Pink Floyd",
        "monitored": true,
        "hasFile": true,
        "foreignAlbumId": "12345",
        "releaseDate": "1973-03-01",
        "qualityMet": true,
        "isRequest": false,
        "upgrade": false,
        "customFormatScore": 0,
        "minCustomFormatScore": 0,
        "customFormatMet": true,
        "reason": null,
        "qualityProfileId": 1,
        "qualityProfileName": "Lossless"
      },
      "totals": {
        "available": 10,
        "monitored": 10,
        "missing": 0
      },
      "tracks": [
        {
          "id": 101,
          "trackNumber": 1,
          "title": "Speak to Me",
          "duration": 70,
          "hasFile": true,
          "trackFileId": 1001,
          "monitored": true
        }
      ]
    }
  ]
}
```

**Grouping**: Tracks nested within albums.

---

### List Arr Instances

Get all configured Arr instances.

**Endpoints**:
- `GET /api/arr` (requires auth)
- `GET /web/arr` (public)

**Response**:
```json
{
  "instances": [
    {
      "category": "radarr-4k",
      "name": "Radarr-4K",
      "type": "radarr"
    },
    {
      "category": "sonarr-tv",
      "name": "Sonarr-TV",
      "type": "sonarr"
    },
    {
      "category": "lidarr",
      "name": "Lidarr",
      "type": "lidarr"
    }
  ]
}
```

**Fields**:

- `category` - qBittorrent category (used in API paths)
- `name` - Friendly display name
- `type` - Arr type (`radarr`, `sonarr`, `lidarr`)

---

## Configuration Endpoints

### Get Configuration

Fetch current configuration from disk.

**Endpoints**:
- `GET /api/config` (requires auth)
- `GET /web/config` (public)

**Response**:
```json
{
  "Settings": {
    "ConsoleLevel": "INFO",
    "Logging": true,
    "CompletedDownloadFolder": "/mnt/downloads",
    "FreeSpace": "100G",
    "AutoUpdateEnabled": true
  },
  "WebUI": {
    "Host": "0.0.0.0",
    "Port": 6969,
    "Token": "abc123...",
    "LiveArr": false,
    "GroupSonarr": true,
    "Theme": "Dark"
  },
  "qBit": {
    "Host": "localhost",
    "Port": 8080,
    "UserName": "admin",
    "Password": "***"
  },
  "Radarr-4K": {
    "Managed": true,
    "URI": "http://localhost:7878",
    "APIKey": "***",
    "Category": "radarr-4k"
  }
}
```

**Behavior**:

- Reloads config from disk (always fresh)
- Returns entire config tree as JSON
- Converts TOML to JSON-compatible structure

**Public Endpoint**: `/web/config` includes config version mismatch warnings:

```json
{
  "config": { ... },
  "warning": {
    "type": "config_version_mismatch",
    "message": "Config version 1 is outdated (current: 2)",
    "currentVersion": 1
  }
}
```

---

### Update Configuration

Apply changes to configuration and trigger reload.

**Endpoints**:
- `POST /api/config` (requires auth)
- `POST /web/config` (public)

**Request Body**:
```json
{
  "changes": {
    "Settings.LoopSleepTimer": 60,
    "Radarr-4K.EntrySearch.SearchLimit": 10,
    "WebUI.Theme": "Dark"
  }
}
```

**Dotted Key Format**: Use dot notation for nested keys (e.g., `Radarr-4K.Torrent.AutoDelete`).

**Deletion**: Set value to `null` to delete key:
```json
{
  "changes": {
    "WebUI.Token": null
  }
}
```

**Response** (Success):
```json
{
  "status": "ok",
  "configReloaded": true,
  "reloadType": "single_arr",
  "affectedInstances": ["Radarr-4K"]
}
```

**Reload Types**:

| Type | Description | Behavior |
|------|-------------|----------|
| `frontend` | Frontend-only changes | No reload (e.g., `WebUI.Theme`) |
| `webui` | WebUI server settings | Restart WebUI server |
| `single_arr` | One Arr instance | Reload that instance only |
| `multi_arr` | Multiple Arr instances | Reload each instance sequentially |
| `full` | Global settings | Reload all components |

**Response** (Validation Error):
```json
{
  "error": "Please resolve the following issues:\nWebUI.Port: WebUI Port must be between 1 and 65535."
}
```

**Response** (Protected Key Error):
```json
{
  "error": "Cannot modify protected configuration key: Settings.ConfigVersion"
}
```

**HTTP Status Codes**:

- `200` - Success
- `400` - Invalid request body
- `403` - Protected key modification attempt
- `500` - Save failure

**Protected Keys**:

- `Settings.ConfigVersion` - Managed automatically by migration system

---

### Test Arr Connection

Test connection to Arr instance without saving configuration.

**Endpoints**:
- `POST /api/arr/test-connection` (requires auth)
- `POST /web/arr/test-connection` (public)

**Request Body**:
```json
{
  "arrType": "radarr",
  "uri": "http://localhost:7878",
  "apiKey": "abc123..."
}
```

**Valid Arr Types**: `radarr`, `sonarr`, `lidarr`

**Response** (Success):
```json
{
  "success": true,
  "version": "4.3.2.6857",
  "qualityProfiles": [
    {
      "id": 1,
      "name": "HD-1080p"
    },
    {
      "id": 4,
      "name": "Ultra-HD"
    }
  ]
}
```

**Response** (Failure):
```json
{
  "success": false,
  "message": "Connection refused"
}
```

**HTTP Status Codes**:

- `200` - Connection test completed (check `success` field)
- `400` - Missing required fields
- `500` - Unexpected error

**Use Case**: Validate Arr credentials before saving config changes.

---

## Update Endpoints

### Trigger Manual Update

Trigger qBitrr self-update (pip or binary).

**Endpoints**:
- `POST /api/update` (requires auth)
- `POST /web/update` (public)

**Request**: No body required

**Response** (Success):
```json
{
  "status": "started"
}
```

**Response** (Already Running):
```json
{
  "error": "An update is already in progress."
}
```

**HTTP Status Codes**:

- `200` - Update started
- `409` - Update already in progress

**Behavior**:

1. Spawns background thread
2. Runs `pip install --upgrade qBitrr2` (pip) or downloads binary (binary)
3. Restarts qBitrr on success
4. Returns immediately (update is asynchronous)

**Monitoring**: Poll `GET /api/meta` to check `update_state.in_progress` and `update_state.last_result`.

---

### Download Binary Update

Redirect to GitHub binary download URL for current platform.

**Endpoints**:
- `GET /api/download-update` (requires auth)
- `GET /web/download-update` (public)

**Response** (Success): HTTP 302 redirect to GitHub asset URL

**Response** (Not Binary):
```json
{
  "error": "Download only available for binary installations"
}
```

**Response** (No Update):
```json
{
  "error": "No update available"
}
```

**Response** (No Binary):
```json
{
  "error": "No binary available for your platform"
}
```

**HTTP Status Codes**:

- `302` - Redirect to download
- `400` - Not a binary installation
- `404` - No update or no binary available

**Use Case**: Manual binary download for offline update.

---

## Error Responses

### Standard Error Format

All errors return JSON with an `error` field:

```json
{
  "error": "Error message"
}
```

### Common HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| `200` | Success | Request completed successfully |
| `302` | Redirect | Root endpoint, binary download |
| `400` | Bad Request | Invalid parameters, malformed JSON |
| `401` | Unauthorized | Missing or invalid token |
| `403` | Forbidden | Protected key modification |
| `404` | Not Found | Unknown category, missing log file |
| `409` | Conflict | Update already in progress |
| `500` | Server Error | Config save failure, unexpected exception |
| `503` | Service Unavailable | Arr manager not ready |

---

## Rate Limiting

**No rate limiting** is enforced by default. External reverse proxies (e.g., Nginx, Traefik) should implement rate limiting if exposed publicly.

---

## CORS

**Cross-Origin Requests**: Not explicitly configured. CORS headers are **not** set by default. Configure reverse proxy to add CORS headers if needed:

```nginx
add_header Access-Control-Allow-Origin *;
add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
add_header Access-Control-Allow-Headers "Authorization, Content-Type";
```

---

## WebSocket Support

**Not supported**. Use HTTP polling for real-time updates:

- `GET /api/processes` - Poll every 5-10 seconds
- `GET /api/meta` - Poll every 60 seconds (cached for 1 hour)
- `GET /api/status` - Poll every 10-30 seconds

---

## Pagination

Arr view endpoints support pagination via `page` and `page_size` parameters:

**Example**:
```bash
# Page 1 (first 50 results)
curl "http://localhost:6969/web/radarr/radarr-4k/movies?page=0&page_size=50"

# Page 2 (next 50 results)
curl "http://localhost:6969/web/radarr/radarr-4k/movies?page=1&page_size=50"
```

**Response**:
```json
{
  "total": 150,
  "page": 0,
  "page_size": 50,
  "movies": [ ... ]
}
```

**Calculating Pages**:
```javascript
const totalPages = Math.ceil(response.total / response.page_size);
```

---

## Filtering

Arr view endpoints support multiple filters:

**Example** (Radarr):
```bash
# Missing 4K movies from 2020-2023
curl "http://localhost:6969/web/radarr/radarr-4k/movies?has_file=false&year_min=2020&year_max=2023&monitored=true"
```

**Filters are cumulative** (AND logic). All specified filters must match.

---

## Best Practices

1. **Use `/web/*` endpoints** for WebUI to avoid token management
2. **Use `/api/*` endpoints** for external clients with Bearer token
3. **Cache `/api/meta` responses** for 1 hour to reduce GitHub API load
4. **Poll `/api/processes`** every 5-10 seconds (not faster to avoid overhead)
5. **Enable `WebUI.LiveArr`** only when real-time Arr data is required (increases API load)
6. **Set `WebUI.Token`** when exposing WebUI publicly
7. **Use reverse proxy** for HTTPS, rate limiting, and authentication
8. **Monitor update state** via `/api/meta` after triggering `/api/update`
9. **Test Arr connections** via `/api/arr/test-connection` before saving config
10. **Page Arr views** to avoid memory issues with large libraries (use `page_size=50`)

---

## Example: Python Client

```python
import requests

class QbitrrClient:
    def __init__(self, base_url, token=None):
        self.base_url = base_url
        self.token = token

    def _headers(self):
        if self.token:
            return {"Authorization": f"Bearer {self.token}"}
        return {}

    def get_processes(self):
        url = f"{self.base_url}/api/processes"
        response = requests.get(url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def restart_process(self, category, kind):
        url = f"{self.base_url}/api/processes/{category}/{kind}/restart"
        response = requests.post(url, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def get_radarr_movies(self, category, page=0, page_size=50, has_file=None):
        url = f"{self.base_url}/api/radarr/{category}/movies"
        params = {"page": page, "page_size": page_size}
        if has_file is not None:
            params["has_file"] = str(has_file).lower()
        response = requests.get(url, params=params, headers=self._headers())
        response.raise_for_status()
        return response.json()

# Usage
client = QbitrrClient("http://localhost:6969", token="abc123...")
processes = client.get_processes()
print(f"Found {len(processes['processes'])} processes")

movies = client.get_radarr_movies("radarr-4k", has_file=False)
print(f"Missing movies: {movies['counts']['missing']}")
```

---

## Example: cURL Commands

### Get Processes
```bash
curl -H "Authorization: Bearer abc123..." \
  http://localhost:6969/api/processes
```

### Restart Arr Instance
```bash
curl -X POST \
  http://localhost:6969/web/processes/radarr-4k/all/restart
```

### Get Radarr Movies (Missing Only)
```bash
curl "http://localhost:6969/web/radarr/radarr-4k/movies?has_file=false&monitored=true"
```

### Update Configuration
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer abc123..." \
  -d '{"changes": {"Settings.LoopSleepTimer": 60}}' \
  http://localhost:6969/api/config
```

### Trigger Update
```bash
curl -X POST \
  http://localhost:6969/web/update
```

---

## Related Pages

- [Configuration Editor](config-editor.md) - WebUI config management
- [Processes Page](processes.md) - Process monitoring interface
- [Logs Page](logs.md) - Log viewing interface
- [Arr Views](arr-views.md) - Library browsing interface
- [WebUI Overview](index.md) - Introduction to WebUI

---

## See Also

- [Configuration File Reference](../configuration/config-file.md) - Manual TOML editing
- [First Run Guide](../getting-started/first-run.md) - Initial setup
- [Troubleshooting](../troubleshooting/index.md) - Common issues
