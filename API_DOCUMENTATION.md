# qBitrr API Documentation

[![API Version](https://img.shields.io/badge/API-v1-blue)](https://github.com/Feramance/qBitrr)
[![WebUI Port](https://img.shields.io/badge/Default%20Port-6969-green)](http://localhost:6969/ui)

> 📡 Complete REST API reference for qBitrr's WebUI and programmatic access

## 📚 Table of Contents

- [Overview](#-overview)
- [Authentication](#-authentication)
- [Base URL & Endpoints](#-base-url--endpoints)
- [Radarr Endpoints](#-radarr-endpoints)
- [Sonarr Endpoints](#-sonarr-endpoints)
- [Lidarr Endpoints](#-lidarr-endpoints)
- [Process Management](#-process-management)
- [Arr Instance Management](#-arr-instance-management)
- [Logs](#-logs)
- [Configuration](#-configuration)
- [Meta & Updates](#-meta--updates)
- [Error Handling](#-error-handling)
- [Rate Limiting & Best Practices](#-rate-limiting--best-practices)
- [Code Examples](#-code-examples)
- [Changelog](#-changelog)

---

## 🌐 Overview

The qBitrr WebUI exposes a comprehensive REST API for:
- 🎬 Managing and querying Radarr/Sonarr/Lidarr instances
- 📊 Monitoring process status and activity
- 📝 Viewing and searching logs
- ⚙️ Updating configuration
- 🔄 Triggering updates and restarts
- 📈 Accessing media library statistics

### API Architecture
- **RESTful design** – standard HTTP methods (GET, POST)
- **JSON responses** – all endpoints return JSON
- **Dual access paths** – authenticated `/api/*` and public `/web/*`
- **Pagination support** – efficient handling of large datasets
- **Real-time data** – live status and metrics

---

## 🔐 Authentication

### 🔒 API Endpoints (`/api/*`)
**Protected endpoints** requiring Bearer token authentication.

**Configuration:**
```toml
[WebUI]
Token = "your-secret-token-here"
```

**Usage:**
```bash
# Using Authorization header
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:6969/api/status

# Using X-API-Token header (alternative)
curl -H "X-API-Token: YOUR_TOKEN" \
  http://localhost:6969/api/status
```

**Python example:**
```python
import requests

headers = {"Authorization": "Bearer YOUR_TOKEN"}
response = requests.get("http://localhost:6969/api/status", headers=headers)
print(response.json())
```

### 🌍 Web Endpoints (`/web/*`)
**Public endpoints** with no authentication required.

**Usage:**
```bash
curl http://localhost:6969/web/status
```

> 💡 **Tip:** Use `/api/*` endpoints for programmatic access with token security. Use `/web/*` endpoints for internal network access where authentication isn't required.

---

## 🔗 Base URL & Endpoints

### Default Configuration
```
Base URL: http://<host>:6969
WebUI: http://<host>:6969/ui
API: http://<host>:6969/api/*
Web: http://<host>:6969/web/*
```

### Custom Configuration
```toml
[WebUI]
Host = "0.0.0.0"  # Bind to all interfaces
Port = 6969       # Custom port
```

---

## 🎬 Radarr Endpoints

### 📋 List Movies

**Endpoint:**
```
GET /api/radarr/<category>/movies
GET /web/radarr/<category>/movies
```

Retrieve movies from a Radarr instance with advanced filtering, search, and pagination.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | ✅ Yes | Radarr instance category name (e.g., `radarr-4k`, `radarr-1080`) |

#### Query Parameters

**🔍 Search & Pagination:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | - | Search movies by title (case-insensitive) |
| `page` | integer | `0` | Page number (zero-indexed) |
| `page_size` | integer | `50` | Items per page (max: 500) |

**🎯 Filtering Options:**

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| `year_min` | integer | - | Minimum release year (e.g., `2020`) |
| `year_max` | integer | - | Maximum release year (e.g., `2024`) |
| `monitored` | boolean | `true`/`false` | Filter by monitored status |
| `has_file` | boolean | `true`/`false` | Filter by file availability |
| `quality_met` | boolean | `true`/`false` | Filter by quality profile satisfaction |
| `is_request` | boolean | `true`/`false` | Filter by request status (Overseerr/Ombi) |

> 💡 **Tip:** Omit filter parameters to include all items (e.g., omit `monitored` to get both monitored and unmonitored).

#### Response Structure

```json
{
  "category": "radarr-4k",
  "counts": {
    "available": 1250,
    "monitored": 2000,
    "missing": 750,
    "quality_met": 1100,
    "requests": 50
  },
  "total": 2000,
  "page": 0,
  "page_size": 50,
  "movies": [
    {
      "id": 12345,
      "title": "The Matrix",
      "year": 1999,
      "monitored": true,
      "hasFile": true,
      "qualityMet": true,
      "isRequest": false,
      "upgrade": false,
      "customFormatScore": 5000,
      "minCustomFormatScore": 3000,
      "customFormatMet": true,
      "reason": "Quality upgrade available"
    }
  ]
}
```

#### Response Fields

**Top-level:**

| Field | Type | Description |
|-------|------|-------------|
| `category` | string | Radarr instance category |
| `counts` | object | Aggregate statistics |
| `total` | integer | Total movies matching filters |
| `page` | integer | Current page number |
| `page_size` | integer | Items per page |
| `movies` | array | Array of movie objects |

**Movie object:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Radarr movie ID |
| `title` | string | Movie title |
| `year` | integer | Release year |
| `monitored` | boolean | Whether movie is monitored |
| `hasFile` | boolean | Whether movie file exists |
| `qualityMet` | boolean | Whether quality profile is satisfied |
| `isRequest` | boolean | Whether added via Overseerr/Ombi |
| `upgrade` | boolean | Whether eligible for quality upgrade |
| `customFormatScore` | integer\|null | Current custom format score |
| `minCustomFormatScore` | integer\|null | Required minimum CF score |
| `customFormatMet` | boolean | Whether CF requirements are met |
| `reason` | string\|null | Status reason or upgrade explanation |

**Counts object:**

| Field | Type | Description |
|-------|------|-------------|
| `available` | integer | Movies with files |
| `monitored` | integer | Monitored movies |
| `missing` | integer | Monitored movies without files |
| `quality_met` | integer | Movies meeting quality requirements |
| `requests` | integer | Movies added via request systems |

#### Examples

**Get all 4K movies from 2020-2024:**
```bash
curl "http://localhost:6969/web/radarr/radarr-4k/movies?year_min=2020&year_max=2024"
```

**Get missing monitored movies (for searching):**
```bash
curl "http://localhost:6969/web/radarr/movies-hd/movies?monitored=true&has_file=false"
```

**Get movies requiring quality upgrade:**
```bash
curl "http://localhost:6969/web/radarr/movies/movies?quality_met=false&has_file=true"
```

**Get user-requested movies:**
```bash
curl "http://localhost:6969/web/radarr/movies/movies?is_request=true"
```

**Search with pagination:**
```bash
curl "http://localhost:6969/web/radarr/movies/movies?q=matrix&page=0&page_size=25"
```

**Python example:**
```python
import requests

params = {
    "year_min": 2020,
    "year_max": 2024,
    "monitored": True,
    "has_file": False,
    "page_size": 100
}

response = requests.get(
    "http://localhost:6969/web/radarr/radarr-4k/movies",
    params=params
)

data = response.json()
print(f"Found {data['total']} missing movies")
for movie in data['movies']:
    print(f"- {movie['title']} ({movie['year']})")
```

---

## 📺 Sonarr Endpoints

### 📋 List Series & Episodes

**Endpoint:**
```
GET /api/sonarr/<category>/series
GET /web/sonarr/<category>/series
```

Retrieve TV series and episodes from a Sonarr instance with hierarchical season/episode data.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | ✅ Yes | Sonarr instance category name (e.g., `sonarr-tv`, `sonarr-anime`) |

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | - | Search series by title (case-insensitive) |
| `page` | integer | `0` | Page number (zero-indexed) |
| `page_size` | integer | `25` | Series per page (max: 500) |
| `missing` | boolean | - | Show only series with missing episodes |
| `only_missing` | boolean | - | Alias for `missing` parameter |

> 💡 **Note:** Response includes nested season and episode data. Page size applies to series count, not total episodes.

#### Response Structure

```json
{
  "category": "sonarr-anime",
  "counts": {
    "available": 5000,
    "monitored": 8000,
    "missing": 3000
  },
  "total": 150,
  "page": 0,
  "page_size": 25,
  "series": [
    {
      "series": {
        "id": 123,
        "title": "Attack on Titan",
        "year": 2013,
        "tvdbId": 267440,
        "imdbId": "tt2560140"
      },
      "monitored": 120,
      "available": 80,
      "seasons": {
        "1": {
          "seasonNumber": 1,
          "monitored": 25,
          "available": 25,
          "episodes": [
            {
              "id": 1,
              "episodeNumber": 1,
              "seasonNumber": 1,
              "title": "To You, in 2000 Years",
              "monitored": true,
              "hasFile": true,
              "airDateUtc": "2013-04-07T00:00:00Z",
              "qualityMet": true,
              "customFormatScore": 1000
            }
          ]
        }
      }
    }
  ]
}
```

#### Response Fields

**Top-level:**

| Field | Type | Description |
|-------|------|-------------|
| `category` | string | Sonarr instance category |
| `counts` | object | Aggregate episode statistics |
| `total` | integer | Total series matching filters |
| `page` | integer | Current page number |
| `page_size` | integer | Series per page |
| `series` | array | Array of series objects |

**Series object:**

| Field | Type | Description |
|-------|------|-------------|
| `series` | object | Series metadata (id, title, year, etc.) |
| `monitored` | integer | Count of monitored episodes |
| `available` | integer | Count of episodes with files |
| `seasons` | object | Season data keyed by season number |

**Season object:**

| Field | Type | Description |
|-------|------|-------------|
| `seasonNumber` | integer | Season number (0 = specials) |
| `monitored` | integer | Monitored episodes in season |
| `available` | integer | Episodes with files in season |
| `episodes` | array | Array of episode objects |

**Episode object:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Sonarr episode ID |
| `episodeNumber` | integer | Episode number in season |
| `seasonNumber` | integer | Season number |
| `title` | string | Episode title |
| `monitored` | boolean | Whether episode is monitored |
| `hasFile` | boolean | Whether episode file exists |
| `airDateUtc` | string | Air date (ISO 8601 format) |
| `qualityMet` | boolean | Whether quality profile is satisfied |
| `customFormatScore` | integer\|null | Custom format score |

**Counts object:**

| Field | Type | Description |
|-------|------|-------------|
| `available` | integer | Total episodes with files |
| `monitored` | integer | Total monitored episodes |
| `missing` | integer | Monitored episodes without files |

#### Examples

**Get all anime series:**
```bash
curl "http://localhost:6969/web/sonarr/sonarr-anime/series"
```

**Get series with missing episodes:**
```bash
curl "http://localhost:6969/web/sonarr/sonarr-tv/series?missing=true"
```

**Search for specific series:**
```bash
curl "http://localhost:6969/web/sonarr/sonarr-tv/series?q=breaking%20bad"
```

**Paginated results:**
```bash
curl "http://localhost:6969/web/sonarr/sonarr-tv/series?page=0&page_size=50"
```

**Python example - Find missing episodes:**
```python
import requests

response = requests.get(
    "http://localhost:6969/web/sonarr/sonarr-tv/series",
    params={"missing": True}
)

data = response.json()
print(f"Series with missing episodes: {data['total']}")
print(f"Total missing episodes: {data['counts']['missing']}")

for show in data['series']:
    title = show['series']['title']
    missing = show['monitored'] - show['available']
    print(f"- {title}: {missing} missing episodes")
```

---

## 🎵 Lidarr Endpoints

### 📋 List Artists & Albums

**Endpoint:**
```
GET /api/lidarr/<category>/artists
GET /web/lidarr/<category>/artists
```

Retrieve artists and albums from a Lidarr instance with hierarchical album data.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | ✅ Yes | Lidarr instance category name (e.g., `lidarr-music`) |

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | - | Search artists by name (case-insensitive) |
| `page` | integer | `0` | Page number (zero-indexed) |
| `page_size` | integer | `25` | Artists per page (max: 500) |
| `missing` | boolean | - | Show only artists with missing albums |

#### Response Structure

```json
{
  "category": "lidarr-music",
  "counts": {
    "available": 2500,
    "monitored": 3000,
    "missing": 500
  },
  "total": 75,
  "page": 0,
  "page_size": 25,
  "artists": [
    {
      "artist": {
        "id": 456,
        "name": "Pink Floyd",
        "disambiguation": "UK progressive rock band"
      },
      "monitored": 15,
      "available": 12,
      "albums": [
        {
          "id": 789,
          "title": "The Dark Side of the Moon",
          "releaseDate": "1973-03-01",
          "monitored": true,
          "hasFile": true,
          "qualityMet": true
        }
      ]
    }
  ]
}
```

> 💡 **Note:** Similar structure to Sonarr but for music. Albums are grouped under artists.

#### Examples

**Get all artists:**
```bash
curl "http://localhost:6969/web/lidarr/lidarr-music/artists"
```

**Get artists with missing albums:**
```bash
curl "http://localhost:6969/web/lidarr/lidarr-music/artists?missing=true"
```

**Search for artist:**
```bash
curl "http://localhost:6969/web/lidarr/lidarr-music/artists?q=pink%20floyd"
```

---

## 🔄 Process Management

### 📊 Get All Processes

**Endpoint:**
```
GET /api/processes
GET /web/processes
```

Get status and activity of all running Arr manager processes.

#### Response Structure

```json
{
  "processes": [
    {
      "category": "movies",
      "name": "Radarr Manager",
      "kind": "search",
      "pid": 12345,
      "alive": true,
      "searchSummary": "The Matrix | 1999",
      "searchTimestamp": "2024-10-31T12:00:00Z",
      "queueCount": 5,
      "categoryCount": 120,
      "metricType": "category"
    },
    {
      "category": "tv-shows",
      "name": "Sonarr Manager",
      "kind": "health",
      "pid": 12346,
      "alive": true,
      "searchSummary": null,
      "searchTimestamp": null,
      "queueCount": 12,
      "categoryCount": 450,
      "metricType": "queue"
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `category` | string | Arr instance category name |
| `name` | string | Human-readable process name |
| `kind` | string | Current activity (`search`, `health`, `idle`) |
| `pid` | integer | Process ID |
| `alive` | boolean | Whether process is running |
| `searchSummary` | string\|null | Current search item description |
| `searchTimestamp` | string\|null | ISO 8601 timestamp of current search |
| `queueCount` | integer | Items in download queue |
| `categoryCount` | integer | Total items in category |
| `metricType` | string | Type of metric (`category`, `queue`, `search`) |

#### Example

```bash
curl "http://localhost:6969/web/processes"
```

---

### ✅ Get Backend Status

**Endpoint:**
```
GET /api/status
GET /web/status
```

Get readiness status and available Arr instances.

#### Response Structure

```json
{
  "ready": true,
  "arrs": ["movies", "tv-shows", "anime", "music"]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `ready` | boolean | Whether backend is fully initialized |
| `arrs` | array | List of configured Arr instance categories |

#### Example

```bash
curl "http://localhost:6969/web/status"
```

**Use case:** Check this endpoint before making other API calls to ensure qBitrr is ready.

---

## ⚙️ Arr Instance Management

### 📋 List All Arr Instances

**Endpoint:**
```
GET /api/arr
GET /web/arr
```

List all configured Arr instances with their types and categories.

#### Response Structure

```json
{
  "arr": [
    {
      "category": "movies",
      "name": "Radarr 4K",
      "type": "radarr"
    },
    {
      "category": "tv-shows",
      "name": "Sonarr HD",
      "type": "sonarr"
    },
    {
      "category": "anime",
      "name": "Sonarr Anime",
      "type": "sonarr"
    },
    {
      "category": "music",
      "name": "Lidarr",
      "type": "lidarr"
    }
  ],
  "ready": true
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `arr` | array | List of configured Arr instances |
| `ready` | boolean | Whether backend is initialized |

**Arr instance object:**

| Field | Type | Description |
|-------|------|-------------|
| `category` | string | Category name (used in config and API paths) |
| `name` | string | Display name for the instance |
| `type` | string | Arr type (`radarr`, `sonarr`, or `lidarr`) |

#### Example

```bash
curl "http://localhost:6969/web/arr"
```

---

### 🔄 Restart Arr Instance

**Endpoint:**
```
POST /api/arr/<section>/restart
POST /web/arr/<section>/restart
```

Restart a specific Arr instance manager process.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `section` | string | ✅ Yes | Arr instance category name |

#### Response Structure

```json
{
  "message": "Restart triggered for movies"
}
```

#### Examples

**Restart Radarr instance:**
```bash
curl -X POST "http://localhost:6969/web/arr/movies/restart"
```

**Restart with authentication:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:6969/api/arr/tv-shows/restart"
```

**Python example:**
```python
import requests

response = requests.post(
    "http://localhost:6969/web/arr/movies/restart"
)
print(response.json()['message'])
```

> ⚠️ **Note:** The process will restart immediately. Any ongoing searches or operations will be interrupted.

---

### 🔨 Rebuild Arr Metadata

**Endpoint:**
```
POST /api/arr/rebuild
POST /web/arr/rebuild
```

Rebuild metadata caches for all Arr instances.

#### Response Structure

```json
{
  "message": "Rebuild triggered for all Arr instances"
}
```

#### Example

```bash
curl -X POST "http://localhost:6969/web/arr/rebuild"
```

> 💡 **Use case:** Rebuild when Arr data seems stale or after major configuration changes.

---

## 📝 Logs

### 📋 List Log Files

**Endpoint:**
```
GET /api/logs
GET /web/logs
```

List all available log files.

#### Response Structure

```json
{
  "logs": [
    "Main.log",
    "WebUI.log",
    "radarr-4k.log",
    "sonarr-tv.log",
    "sonarr-anime.log",
    "lidarr-music.log"
  ]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `logs` | array | List of available log file names |

#### Example

```bash
curl "http://localhost:6969/web/logs"
```

---

### 📖 Read Log File

**Endpoint:**
```
GET /api/logs/<name>
GET /web/logs/<name>
```

Read contents of a specific log file with optional offset and limit.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | ✅ Yes | Log file name (from list endpoint) |

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `offset` | integer | `0` | Line offset to start reading from |
| `limit` | integer | `5000` | Maximum number of lines to return |

#### Response Structure

```json
{
  "name": "Main.log",
  "content": "2024-11-04 12:00:00 [INFO] Starting qBitrr...\n2024-11-04 12:00:01 [INFO] Loaded config from /config/config.toml\n...",
  "lines": 150,
  "offset": 0,
  "total_lines": 5432
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Log file name |
| `content` | string | Log file content (newline-separated) |
| `lines` | integer | Number of lines returned |
| `offset` | integer | Starting line offset used |
| `total_lines` | integer | Total lines in log file |

#### Examples

**Read entire log:**
```bash
curl "http://localhost:6969/web/logs/Main.log"
```

**Read last 100 lines:**
```bash
# First get total lines
TOTAL=$(curl -s "http://localhost:6969/web/logs/Main.log" | jq -r '.total_lines')
OFFSET=$((TOTAL - 100))

# Then read from offset
curl "http://localhost:6969/web/logs/Main.log?offset=$OFFSET&limit=100"
```

**Paginated reading:**
```bash
# Read lines 1000-1500
curl "http://localhost:6969/web/logs/Main.log?offset=1000&limit=500"
```

**Python example - Tail logs:**
```python
import requests
import time

def tail_log(log_name, lines=50):
    """Tail a log file (like tail -f)"""
    offset = 0

    while True:
        response = requests.get(
            f"http://localhost:6969/web/logs/{log_name}",
            params={"offset": offset, "limit": 1000}
        )

        data = response.json()

        if data['lines'] > 0:
            print(data['content'], end='')
            offset += data['lines']

        time.sleep(2)  # Poll every 2 seconds

# Usage
tail_log("Main.log")
```

> 💡 **Tip:** Use offset and limit for efficient pagination of large log files.

---

## ⚙️ Configuration

### 📖 Get Current Configuration

**Endpoint:**
```
GET /api/config
GET /web/config
```

Retrieve the current configuration (sanitized to remove sensitive values).

#### Response Structure

```json
{
  "Settings": {
    "Logging": true,
    "ConsoleLevel": "INFO",
    "CompletedDownloadFolder": "/downloads/completed",
    "FreeSpace": "50G",
    "AutoPauseResume": true,
    "LoopSleepTimer": 5,
    "AutoUpdateEnabled": true,
    "AutoUpdateCron": "0 3 * * 0"
  },
  "WebUI": {
    "Host": "0.0.0.0",
    "Port": 6969,
    "LiveArr": true,
    "GroupSonarr": true,
    "GroupLidarr": true,
    "Theme": "dark"
  },
  "qBit": {
    "Host": "qbittorrent",
    "Port": 8080,
    "UserName": "admin"
  },
  "Radarr-4K": {
    "Managed": true,
    "URI": "http://radarr:7878",
    "Category": "radarr-4k",
    "ReSearch": true
  }
}
```

> 🔒 **Security:** Sensitive fields (passwords, API keys, tokens) are automatically removed from the response.

#### Example

```bash
curl "http://localhost:6969/web/config"
```

---

### ✏️ Update Configuration

**Endpoint:**
```
POST /api/config
POST /web/config
```

Update configuration values or delete configuration keys.

#### Request Body

```json
{
  "changes": {
    "WebUI.Theme": "light",
    "Settings.CompletedDownloadFolder": "/new/path",
    "Settings.FreeSpace": "100G",
    "Radarr-4K.ReSearch": true
  },
  "deletions": [
    "Settings.OldSetting",
    "Radarr-Legacy"
  ]
}
```

#### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `changes` | object | No | Key-value pairs to add/update (dot notation) |
| `deletions` | array | No | Keys to delete (dot notation) |

> 💡 **Dot notation:** Use `Section.Key` format (e.g., `WebUI.Theme`, `Settings.Logging`)

#### Response Structure

**Success:**
```json
{
  "success": true,
  "message": "Configuration updated successfully"
}
```

**Error:**
```json
{
  "success": false,
  "error": "Invalid configuration key: InvalidSection.Key"
}
```

#### Examples

**Change theme:**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"changes": {"WebUI.Theme": "light"}}' \
  "http://localhost:6969/web/config"
```

**Update multiple settings:**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "changes": {
      "Settings.LoopSleepTimer": 10,
      "Settings.AutoUpdateEnabled": true,
      "WebUI.LiveArr": false
    }
  }' \
  "http://localhost:6969/web/config"
```

**Delete deprecated settings:**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"deletions": ["Settings.OldKey", "Radarr-Old"]}' \
  "http://localhost:6969/web/config"
```

**Python example:**
```python
import requests

changes = {
    "WebUI.Theme": "dark",
    "Settings.FreeSpace": "200G",
    "Settings.AutoUpdateEnabled": True
}

response = requests.post(
    "http://localhost:6969/web/config",
    json={"changes": changes}
)

print(response.json()['message'])
```

> ⚠️ **Important:**
> - Configuration changes take effect immediately (no restart required for most settings)
> - Invalid keys will return an error response
> - Deleting required keys may cause qBitrr to malfunction

---

## 🔄 Meta & Updates

### 📊 Get Version & Update Info

**Endpoint:**
```
GET /api/meta
GET /web/meta
```

Get current version, latest available version, changelog, and update status.

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `force` | boolean | `false` | Force refresh version check (bypass cache) |

#### Response Structure

```json
{
  "current_version": "v5.2.0",
  "latest_version": "v5.3.0",
  "update_available": true,
  "changelog": "## What's New in v5.3.0\n\n### Features\n- Add Lidarr support\n- Improve search performance\n\n### Bug Fixes\n- Fix stalled torrent detection\n- Resolve WebUI pagination issue",
  "changelog_url": "https://github.com/Feramance/qBitrr/releases/tag/v5.3.0",
  "repository_url": "https://github.com/Feramance/qBitrr",
  "last_checked": "2024-11-04T12:00:00Z",
  "update_state": {
    "in_progress": false,
    "last_result": "success",
    "last_error": null,
    "completed_at": "2024-11-03T10:00:00Z"
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `current_version` | string | Currently installed version |
| `latest_version` | string | Latest available version on PyPI/GitHub |
| `update_available` | boolean | Whether an update is available |
| `changelog` | string | Markdown-formatted changelog for latest version |
| `changelog_url` | string | URL to GitHub release page |
| `repository_url` | string | GitHub repository URL |
| `last_checked` | string | ISO 8601 timestamp of last version check |
| `update_state` | object | Status of last update operation |

**Update state object:**

| Field | Type | Description |
|-------|------|-------------|
| `in_progress` | boolean | Whether an update is currently running |
| `last_result` | string | Result of last update (`success`, `failed`, or `null`) |
| `last_error` | string\|null | Error message if last update failed |
| `completed_at` | string\|null | ISO 8601 timestamp of last completed update |

#### Examples

**Get version info:**
```bash
curl "http://localhost:6969/web/meta"
```

**Force fresh version check:**
```bash
curl "http://localhost:6969/web/meta?force=true"
```

**Python example - Check for updates:**
```python
import requests

response = requests.get("http://localhost:6969/web/meta")
data = response.json()

if data['update_available']:
    print(f"Update available: {data['current_version']} → {data['latest_version']}")
    print(f"\nChangelog:\n{data['changelog']}")
else:
    print(f"Already on latest version: {data['current_version']}")
```

---

### 🚀 Trigger Application Update

**Endpoint:**
```
POST /api/update
POST /web/update
```

Manually trigger an application update. qBitrr will download the latest version and restart automatically.

#### Response Structure

**Success:**
```json
{
  "message": "Update initiated",
  "current_version": "v5.2.0",
  "target_version": "v5.3.0"
}
```

**No update available:**
```json
{
  "message": "Already on latest version",
  "current_version": "v5.3.0"
}
```

**Update in progress:**
```json
{
  "error": "Update already in progress"
}
```

#### Examples

**Trigger update:**
```bash
curl -X POST "http://localhost:6969/web/update"
```

**With authentication:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:6969/api/update"
```

**Python example - Auto-update script:**
```python
import requests
import time

def check_and_update():
    # Check for updates
    meta = requests.get("http://localhost:6969/web/meta?force=true").json()

    if not meta['update_available']:
        print("Already on latest version")
        return

    print(f"Updating from {meta['current_version']} to {meta['latest_version']}")

    # Trigger update
    response = requests.post("http://localhost:6969/web/update")
    print(response.json()['message'])

    # Wait for restart
    print("Waiting for qBitrr to restart...")
    time.sleep(10)

    # Verify update
    for i in range(30):
        try:
            new_meta = requests.get("http://localhost:6969/web/meta", timeout=5).json()
            if new_meta['current_version'] == meta['latest_version']:
                print(f"✓ Successfully updated to {new_meta['current_version']}")
                return
        except:
            pass
        time.sleep(2)

    print("⚠ Update may have failed - check logs")

# Run
check_and_update()
```

> ⚠️ **Important:**
> - The application will restart automatically after update
> - Ongoing operations will be interrupted
> - Docker users: Update applies to the container, not the image (manual image pull recommended)
> - Systemd users: See [SYSTEMD_SERVICE.md](../SYSTEMD_SERVICE.md) for service configuration

---

### 🔁 Restart Application

**Endpoint:**
```
POST /api/restart
POST /web/restart
```

Manually restart qBitrr without updating.

#### Response Structure

```json
{
  "message": "Restart initiated"
}
```

#### Example

```bash
curl -X POST "http://localhost:6969/web/restart"
```

> 💡 **Use cases:**
> - Apply configuration changes that require restart
> - Recover from stuck processes
> - Reset internal state after manual interventions

---

## ❌ Error Handling

### HTTP Status Codes

All endpoints return standard HTTP status codes:

| Code | Status | Description |
|------|--------|-------------|
| `200` | OK | Request successful |
| `400` | Bad Request | Invalid parameters or malformed request |
| `401` | Unauthorized | Missing or invalid authentication token |
| `404` | Not Found | Endpoint or resource not found |
| `500` | Internal Server Error | Server-side error occurred |
| `503` | Service Unavailable | Backend still initializing |

### Error Response Format

**Standard error response:**
```json
{
  "error": "Unknown radarr category: invalid-category",
  "code": "UNKNOWN_CATEGORY"
}
```

**Validation error:**
```json
{
  "error": "Invalid parameter: year_min must be less than year_max",
  "code": "VALIDATION_ERROR",
  "details": {
    "parameter": "year_min",
    "value": 2024,
    "constraint": "Must be less than year_max (2020)"
  }
}
```

**Authentication error:**
```json
{
  "error": "Unauthorized: Invalid or missing bearer token",
  "code": "UNAUTHORIZED"
}
```

### Common Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `UNKNOWN_CATEGORY` | Arr category not found in config | Check available categories via `/api/arr` |
| `VALIDATION_ERROR` | Invalid parameter value | Review parameter constraints |
| `UNAUTHORIZED` | Missing/invalid token | Provide valid `Authorization: Bearer <token>` header |
| `NOT_READY` | Backend still initializing | Wait and retry, check `/api/status` |
| `UPDATE_IN_PROGRESS` | Update already running | Wait for current update to complete |
| `CONFIG_ERROR` | Configuration update failed | Verify configuration syntax |

### Error Handling Examples

**Python with error handling:**
```python
import requests

def get_movies_safe(category):
    try:
        response = requests.get(
            f"http://localhost:6969/web/radarr/{category}/movies",
            timeout=10
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Category '{category}' not found")
        elif e.response.status_code == 401:
            print("Authentication required")
        else:
            error_data = e.response.json()
            print(f"Error: {error_data.get('error', 'Unknown error')}")
        return None

    except requests.exceptions.Timeout:
        print("Request timed out")
        return None

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

# Usage
movies = get_movies_safe("radarr-4k")
if movies:
    print(f"Found {movies['total']} movies")
```

**Bash with error handling:**
```bash
#!/bin/bash

response=$(curl -s -w "\n%{http_code}" "http://localhost:6969/web/status")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

if [ "$http_code" -eq 200 ]; then
    echo "Success: $body"
elif [ "$http_code" -eq 503 ]; then
    echo "Service unavailable - backend still starting"
    exit 1
else
    echo "Error (HTTP $http_code): $body"
    exit 1
fi
```

---

## 📊 Rate Limiting & Best Practices

### Performance Guidelines

1. **Pagination**
   - ✅ Use `page_size` to control response size (max: 500)
   - ✅ Start with smaller page sizes (25-50) for faster responses
   - ✅ Increase page size only when needed
   ```bash
   # Good: Smaller pages for UI
   curl "http://localhost:6969/web/radarr/movies/movies?page_size=50"

   # OK: Larger pages for batch processing
   curl "http://localhost:6969/web/radarr/movies/movies?page_size=200"
   ```

2. **Filtering**
   - ✅ Combine filters to reduce payload size
   - ✅ Filter on the server side, not client side
   - ❌ Don't fetch all data and filter locally
   ```bash
   # Good: Server-side filtering
   curl "http://localhost:6969/web/radarr/movies/movies?has_file=false&monitored=true"

   # Bad: Fetching everything
   curl "http://localhost:6969/web/radarr/movies/movies" | jq 'filter(.hasFile == false)'
   ```

3. **Polling**
   - ✅ Poll status endpoints every 5-10 seconds for live updates
   - ✅ Use exponential backoff for error retries
   - ❌ Don't poll more frequently than every 2 seconds
   ```python
   import time

   # Good: Reasonable polling interval
   while True:
       status = get_status()
       time.sleep(5)  # Poll every 5 seconds

   # Bad: Too frequent
   while True:
       status = get_status()
       time.sleep(0.5)  # Don't do this!
   ```

4. **Caching**
   - ✅ Cache responses when appropriate
   - ✅ Use `force=true` parameter sparingly
   - ✅ Respect API response times
   ```python
   import requests
   from cachetools import TTLCache

   # Cache responses for 30 seconds
   cache = TTLCache(maxsize=100, ttl=30)

   def get_movies_cached(category):
       if category in cache:
           return cache[category]

       response = requests.get(f"http://localhost:6969/web/radarr/{category}/movies")
       data = response.json()
       cache[category] = data
       return data
   ```

5. **Authentication**
   - ✅ Use `/api/*` endpoints for programmatic access
   - ✅ Use `/web/*` endpoints for internal/trusted networks
   - ✅ Store tokens securely (environment variables, secrets manager)
   - ❌ Don't hardcode tokens in source code
   ```python
   import os

   # Good: Token from environment
   token = os.getenv('QBITRR_TOKEN')
   headers = {'Authorization': f'Bearer {token}'}

   # Bad: Hardcoded token
   headers = {'Authorization': 'Bearer abc123...'}  # Don't do this!
   ```

6. **Connection Management**
   - ✅ Reuse HTTP connections (sessions)
   - ✅ Set reasonable timeouts
   - ✅ Handle connection errors gracefully
   ```python
   import requests

   # Good: Reuse session
   session = requests.Session()
   session.headers.update({'Authorization': f'Bearer {token}'})

   for category in categories:
       response = session.get(
           f"http://localhost:6969/api/radarr/{category}/movies",
           timeout=10
       )
   ```

### Rate Limits

Currently, qBitrr does **not enforce** strict rate limits, but recommended limits:

| Endpoint Type | Recommended Max | Notes |
|--------------|-----------------|-------|
| Status/Process | 6 req/min | Lightweight, safe to poll |
| Arr Lists | 30 req/min | Can be heavy with large libraries |
| Logs | 10 req/min | Can be large, use pagination |
| Config | 5 req/min | Write operations are expensive |
| Updates | 1 req/5min | Avoid hammering update checks |

> ⚠️ **Note:** Excessive requests may impact qBitrr's ability to manage torrents. Be respectful of resources.

---

## 💡 Code Examples

### Complete Python Client

```python
import requests
from typing import Optional, Dict, List, Any

class QBitrrClient:
    """Python client for qBitrr API"""

    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

        if token:
            self.session.headers.update({'Authorization': f'Bearer {token}'})

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        """Make GET request"""
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, json: Optional[Dict] = None) -> Any:
        """Make POST request"""
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = self.session.post(url, json=json, timeout=10)
        response.raise_for_status()
        return response.json()

    # Status & Processes
    def get_status(self) -> Dict:
        """Get backend status"""
        return self._get('/web/status')

    def get_processes(self) -> List[Dict]:
        """Get all running processes"""
        return self._get('/web/processes')['processes']

    # Radarr
    def get_radarr_movies(self, category: str, **filters) -> Dict:
        """Get movies from Radarr instance

        Filters: q, page, page_size, year_min, year_max,
                 monitored, has_file, quality_met, is_request
        """
        return self._get(f'/web/radarr/{category}/movies', params=filters)

    # Sonarr
    def get_sonarr_series(self, category: str, **filters) -> Dict:
        """Get series from Sonarr instance

        Filters: q, page, page_size, missing
        """
        return self._get(f'/web/sonarr/{category}/series', params=filters)

    # Lidarr
    def get_lidarr_artists(self, category: str, **filters) -> Dict:
        """Get artists from Lidarr instance

        Filters: q, page, page_size, missing
        """
        return self._get(f'/web/lidarr/{category}/artists', params=filters)

    # Arr Management
    def get_arrs(self) -> List[Dict]:
        """List all configured Arr instances"""
        return self._get('/web/arr')['arr']

    def restart_arr(self, category: str) -> Dict:
        """Restart specific Arr instance"""
        return self._post(f'/web/arr/{category}/restart')

    def rebuild_arrs(self) -> Dict:
        """Rebuild all Arr metadata"""
        return self._post('/web/arr/rebuild')

    # Logs
    def list_logs(self) -> List[str]:
        """List available log files"""
        return self._get('/web/logs')['logs']

    def get_log(self, name: str, offset: int = 0, limit: int = 5000) -> Dict:
        """Read log file"""
        params = {'offset': offset, 'limit': limit}
        return self._get(f'/web/logs/{name}', params=params)

    # Configuration
    def get_config(self) -> Dict:
        """Get current configuration"""
        return self._get('/web/config')

    def update_config(self, changes: Optional[Dict] = None,
                     deletions: Optional[List[str]] = None) -> Dict:
        """Update configuration"""
        payload = {}
        if changes:
            payload['changes'] = changes
        if deletions:
            payload['deletions'] = deletions
        return self._post('/web/config', json=payload)

    # Meta & Updates
    def get_meta(self, force: bool = False) -> Dict:
        """Get version and update info"""
        params = {'force': force} if force else None
        return self._get('/web/meta', params=params)

    def update(self) -> Dict:
        """Trigger application update"""
        return self._post('/web/update')

    def restart(self) -> Dict:
        """Restart application"""
        return self._post('/web/restart')


# Usage examples
if __name__ == '__main__':
    # Initialize client
    client = QBitrrClient('http://localhost:6969')

    # Check status
    status = client.get_status()
    print(f"Backend ready: {status['ready']}")

    # Get missing movies
    movies = client.get_radarr_movies(
        'radarr-4k',
        has_file=False,
        monitored=True,
        year_min=2020
    )
    print(f"Missing movies: {movies['counts']['missing']}")

    # Check for updates
    meta = client.get_meta(force=True)
    if meta['update_available']:
        print(f"Update available: {meta['latest_version']}")
        # Uncomment to auto-update
        # client.update()

    # Tail logs
    logs = client.get_log('Main.log', limit=50)
    print(logs['content'])
```

### Bash Integration Script

```bash
#!/bin/bash
# qbitrr-tools.sh - Utility script for qBitrr API

QBITRR_URL="${QBITRR_URL:-http://localhost:6969}"
QBITRR_TOKEN="${QBITRR_TOKEN:-}"

# Helper function for API calls
api_call() {
    local method=$1
    local path=$2
    local data=$3

    local auth_header=""
    if [ -n "$QBITRR_TOKEN" ]; then
        auth_header="-H 'Authorization: Bearer $QBITRR_TOKEN'"
    fi

    if [ "$method" = "GET" ]; then
        curl -s $auth_header "$QBITRR_URL$path"
    else
        curl -s -X "$method" $auth_header \
            -H "Content-Type: application/json" \
            -d "$data" "$QBITRR_URL$path"
    fi
}

# Check status
status() {
    api_call GET "/web/status" | jq -r '.ready'
}

# List missing movies
missing_movies() {
    local category=${1:-radarr-4k}
    api_call GET "/web/radarr/$category/movies?has_file=false&monitored=true" \
        | jq -r '.movies[] | "\(.title) (\(.year))"'
}

# Check for updates
check_updates() {
    local meta=$(api_call GET "/web/meta?force=true")
    local current=$(echo "$meta" | jq -r '.current_version')
    local latest=$(echo "$meta" | jq -r '.latest_version')

    echo "Current: $current"
    echo "Latest: $latest"

    if [ "$current" != "$latest" ]; then
        echo "Update available!"
        return 0
    else
        echo "Up to date"
        return 1
    fi
}

# Trigger update
update() {
    echo "Triggering update..."
    api_call POST "/web/update" | jq -r '.message'
}

# Tail logs
tail_logs() {
    local log_name=${1:-Main.log}
    local offset=0

    while true; do
        local response=$(api_call GET "/web/logs/$log_name?offset=$offset&limit=100")
        local lines=$(echo "$response" | jq -r '.lines')

        if [ "$lines" -gt 0 ]; then
            echo "$response" | jq -r '.content'
            offset=$((offset + lines))
        fi

        sleep 2
    done
}

# Main command dispatcher
case "${1:-}" in
    status)
        status
        ;;
    missing)
        missing_movies "$2"
        ;;
    check-updates)
        check_updates
        ;;
    update)
        update
        ;;
    tail)
        tail_logs "$2"
        ;;
    *)
        echo "Usage: $0 {status|missing|check-updates|update|tail}"
        echo ""
        echo "Commands:"
        echo "  status              - Check backend status"
        echo "  missing [category]  - List missing movies"
        echo "  check-updates       - Check for qBitrr updates"
        echo "  update              - Trigger update"
        echo "  tail [log]          - Tail log file"
        exit 1
        ;;
esac
```

---

## 📝 Changelog

### v5.3.0 (Current)
- ✨ Added Lidarr support with full API endpoints
- ✨ Enhanced process monitoring with detailed metrics
- ✨ Improved error handling with structured error codes
- 🐛 Fixed pagination issues in large libraries
- 📚 Comprehensive API documentation update

### v5.2.0
- ✨ Enhanced Radarr endpoints with advanced filtering (year range, quality, status)
- ✨ Added quality metrics (qualityMet, customFormatScore, upgrade status)
- ✨ New aggregate counts: missing, quality_met, requests
- ✨ Improved response granularity for all movie fields
- 🔄 Auto-update and restart endpoints

### v5.1.0
- ✨ Configuration management endpoints (read/write)
- ✨ Log viewing with pagination
- 🔐 Bearer token authentication support

### v5.0.0
- 🎉 Initial API release
- 📊 Radarr and Sonarr endpoints
- 🔄 Process and status management
- 📝 Log access

---

## 🔗 Additional Resources

- 📖 **Main Documentation:** [README.md](../README.md)
- ⚙️ **Systemd Setup:** [SYSTEMD_SERVICE.md](../SYSTEMD_SERVICE.md)
- 📝 **Configuration Reference:** [config.example.toml](../config.example.toml)
- 🤝 **Contributing:** [Pull Request Template](../.github/pull_request_template.md)
- 🐛 **Report Issues:** [Bug Report Template](../.github/ISSUE_TEMPLATE/bug_report.yml)
- ✨ **Request Features:** [Feature Request Template](../.github/ISSUE_TEMPLATE/feature_request.yml)

---

<div align="center">

**qBitrr API Documentation** • Built with ❤️ by the qBitrr community

[GitHub](https://github.com/Feramance/qBitrr) • [PyPI](https://pypi.org/project/qBitrr2/) • [Docker Hub](https://hub.docker.com/r/feramance/qbitrr)

</div>
