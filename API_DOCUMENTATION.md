# qBitrr API Documentation

## Overview

The qBitrr WebUI exposes a comprehensive REST API for managing Radarr and Sonarr instances, viewing logs, and monitoring processes. The API supports both authenticated (`/api/*`) and unauthenticated (`/web/*`) endpoints.

## Authentication

### API Endpoints (`/api/*`)
Require Bearer token authentication:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:6969/api/status
```

### Web Endpoints (`/web/*`)
No authentication required. Suitable for UI access.

---

## Enhanced Radarr Endpoints

### GET `/api/radarr/<category>/movies`
### GET `/web/radarr/<category>/movies`

Retrieve movies from a Radarr instance with advanced filtering capabilities.

#### Path Parameters
- `category` (string, required): The Radarr instance category name

#### Query Parameters

**Search & Pagination:**
- `q` (string, optional): Search movies by title
- `page` (integer, default: 0): Page number (zero-indexed)
- `page_size` (integer, default: 50): Number of items per page

**New Filtering Parameters:**
- `year_min` (integer, optional): Minimum release year (e.g., 2020)
- `year_max` (integer, optional): Maximum release year (e.g., 2024)
- `monitored` (boolean, optional): Filter by monitored status
  - `true`: Only monitored movies
  - `false`: Only unmonitored movies
  - omit: All movies
- `has_file` (boolean, optional): Filter by file availability
  - `true`: Only movies with files
  - `false`: Only missing movies
  - omit: All movies
- `quality_met` (boolean, optional): Filter by quality requirements
  - `true`: Only movies meeting quality profile
  - `false`: Only movies not meeting quality
  - omit: All movies
- `is_request` (boolean, optional): Filter by request status
  - `true`: Only requested movies
  - `false`: Only non-requested movies
  - omit: All movies

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

#### New Response Fields

- `qualityMet` (boolean): Whether movie meets configured quality profile
- `isRequest` (boolean): Whether movie was added via request system
- `upgrade` (boolean): Whether movie is eligible for quality upgrade
- `customFormatScore` (integer|null): Current custom format score
- `minCustomFormatScore` (integer|null): Minimum required custom format score
- `customFormatMet` (boolean): Whether custom format requirements are met
- `reason` (string|null): Status reason or upgrade explanation
- `counts.missing` (integer): Count of monitored movies without files
- `counts.quality_met` (integer): Count of movies meeting quality requirements
- `counts.requests` (integer): Count of requested movies

#### Example Requests

**Get all 4K movies from 2020-2024:**
```bash
curl "http://localhost:6969/web/radarr/radarr-4k/movies?year_min=2020&year_max=2024"
```

**Get missing monitored movies:**
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

---

## Sonarr Endpoints

### GET `/api/sonarr/<category>/series`
### GET `/web/sonarr/<category>/series`

Retrieve TV series and episodes from a Sonarr instance.

#### Path Parameters
- `category` (string, required): The Sonarr instance category name

#### Query Parameters
- `q` (string, optional): Search series by title
- `page` (integer, default: 0): Page number (zero-indexed)
- `page_size` (integer, default: 25): Number of series per page
- `missing` or `only_missing` (boolean, optional): Show only series with missing episodes

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
        "title": "Attack on Titan"
      },
      "monitored": 120,
      "available": 80,
      "seasons": {
        "1": {
          "monitored": 25,
          "available": 25,
          "episodes": [
            {
              "episodeNumber": 1,
              "title": "To You, in 2000 Years",
              "monitored": true,
              "hasFile": true,
              "airDateUtc": "2013-04-07T00:00:00Z"
            }
          ]
        }
      }
    }
  ]
}
```

---

## Process & Status Endpoints

### GET `/api/processes`
### GET `/web/processes`

Get all running processes and their status.

**Response:**
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
    }
  ]
}
```

### GET `/api/status`
### GET `/web/status`

Get backend readiness status.

**Response:**
```json
{
  "ready": true,
  "arrs": ["movies", "tv-shows", "anime"]
}
```

---

## Arr Instance Management

### GET `/api/arr`
### GET `/web/arr`

List all configured Arr instances.

**Response:**
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
    }
  ],
  "ready": true
}
```

### POST `/api/arr/<section>/restart`
### POST `/web/arr/<section>/restart`

Restart a specific Arr instance manager.

**Parameters:**
- `section` (string): The arr instance category

**Response:**
```json
{
  "message": "Restart triggered for movies"
}
```

---

## Logs

### GET `/api/logs`
### GET `/web/logs`

List available log files.

**Response:**
```json
{
  "logs": ["qBitrr.log", "qBitrr.log.1", "qBitrr.log.2"]
}
```

### GET `/api/logs/<name>`
### GET `/web/logs/<name>`

Read a specific log file.

**Query Parameters:**
- `offset` (integer, optional): Line offset to start from
- `limit` (integer, default: 5000): Maximum number of lines to return

**Response:**
```json
{
  "name": "qBitrr.log",
  "content": "2024-10-31 12:00:00 [INFO] Starting qBitrr...\n...",
  "lines": 150,
  "offset": 0
}
```

---

## Configuration

### GET `/api/config`
### GET `/web/config`

Get current configuration (sanitized).

**Response:**
```json
{
  "Settings": {
    "IgnoreTorrentClientDownloadsOnAdd": true,
    "CompletedDownloadFolder": "/downloads/completed"
  },
  "WebUI": {
    "LiveArr": true,
    "GroupSonarr": true,
    "Theme": "dark"
  }
}
```

### POST `/api/config`
### POST `/web/config`

Update configuration.

**Request Body:**
```json
{
  "changes": {
    "WebUI.Theme": "light",
    "Settings.CompletedDownloadFolder": "/new/path"
  },
  "deletions": ["Settings.OldSetting"]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Configuration updated successfully"
}
```

---

## Meta & Updates

### GET `/api/meta`
### GET `/web/meta`

Get version and update information.

**Query Parameters:**
- `force` (boolean, optional): Force refresh version check

**Response:**
```json
{
  "current_version": "v4.6.7",
  "latest_version": "v4.7.0",
  "update_available": true,
  "changelog": "## What's New\n- Feature X\n- Bug fix Y",
  "changelog_url": "https://github.com/Feramance/qBitrr/releases/tag/v4.7.0",
  "repository_url": "https://github.com/Feramance/qBitrr",
  "last_checked": "2024-10-31T12:00:00Z",
  "update_state": {
    "in_progress": false,
    "last_result": "success",
    "last_error": null,
    "completed_at": "2024-10-30T10:00:00Z"
  }
}
```

### POST `/api/update`
### POST `/web/update`

Trigger application update.

**Response:**
```json
{
  "message": "Update initiated"
}
```

---

## Rate Limiting & Best Practices

1. **Pagination**: Use `page_size` to control response size (max 500)
2. **Caching**: Most endpoints support caching; use appropriate cache headers
3. **Filtering**: Combine multiple filter parameters to reduce payload size
4. **Authentication**: Use API endpoints with tokens for programmatic access
5. **Polling**: For live data, poll status endpoints every 5-10 seconds

---

## Error Responses

All endpoints return standard HTTP status codes:

- `200 OK`: Success
- `400 Bad Request`: Invalid parameters
- `401 Unauthorized`: Missing or invalid token (API endpoints only)
- `404 Not Found`: Resource not found
- `503 Service Unavailable`: Backend still initializing

**Error Response Format:**
```json
{
  "error": "Unknown radarr category invalid-category"
}
```

---

## Changelog

### v4.7.0 (Latest)
- ✨ Enhanced Radarr endpoints with advanced filtering (year range, quality, status)
- ✨ Added quality metrics (qualityMet, customFormatScore, upgrade status)
- ✨ New counts: missing, quality_met, requests
- ✨ Improved response granularity for all movie fields

### v4.6.x
- Initial API endpoints for Radarr/Sonarr
- Process and log management
- Configuration endpoints
