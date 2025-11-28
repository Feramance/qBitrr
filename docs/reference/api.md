# API Documentation

For complete API reference documentation, see the [WebUI API Reference](../webui/api.md).

This page covers the REST API endpoints exposed by qBitrr's WebUI.

---

## Quick Links

- **[Full API Reference](../webui/api.md)** - Complete endpoint documentation
- **[Authentication](../webui/api.md#authentication)** - Token-based auth
- **[Process Management](../webui/api.md#process-management-endpoints)** - Start/stop/restart Arr processes
- **[Logs](../webui/api.md#logs-endpoints)** - Query and filter logs
- **[Configuration](../webui/api.md#configuration-endpoints)** - Get/update config
- **[Arr Views](../webui/api.md#arr-view-endpoints)** - Movies, series, albums data

---

## Overview

qBitrr provides a REST API through its WebUI component, accessible by default at `http://localhost:6969/api/`.

### Key Features

- **Token-Based Authentication** - Optional API token protection
- **JSON Responses** - All endpoints return JSON
- **Real-Time Data** - Live process, log, and library information
- **Configuration Management** - Get and update settings via API
- **Process Control** - Start, stop, restart Arr instances

### Base URL

=== "Default"
    ```
    http://localhost:6969/api/
    ```

=== "Docker"
    ```
    http://container-ip:6969/api/
    ```

=== "Custom Port"
    ```
    http://localhost:8080/api/
    ```

---

## Authentication

If `Settings.WebUIToken` is configured, all `/api/*` endpoints require authentication.

**Header:**
```
X-API-Token: your-token-here
```

**Example:**
```bash
curl -H "X-API-Token: abc123" http://localhost:6969/api/processes
```

[→ See full authentication details](../webui/api.md#authentication)

---

## Common Endpoints

### Health Check

```http
GET /api/health
```

Returns qBitrr health status (no auth required).

**Response:**
```json
{
  "status": "healthy",
  "version": "5.5.5"
}
```

---

### Get Processes

```http
GET /api/processes
```

Returns all Arr manager processes and their status.

**Response:**
```json
{
  "processes": [
    {
      "name": "Radarr-Movies",
      "category": "radarr-movies",
      "status": "running",
      "pid": 12345,
      "uptime": 3600
    }
  ]
}
```

---

### Get Logs

```http
GET /api/logs?limit=100&level=INFO&source=Radarr-Movies
```

Query logs with filters.

**Parameters:**
- `limit` (int) - Max number of log entries (default: 100)
- `level` (string) - Filter by level: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `source` (string) - Filter by source (process name)

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2025-11-27T12:00:00Z",
      "level": "INFO",
      "source": "Radarr-Movies",
      "message": "Torrent imported successfully"
    }
  ]
}
```

---

### Get Configuration

```http
GET /api/config
```

Returns current configuration (TOML format).

**Response:**
```json
{
  "config": "... TOML content ..."
}
```

---

### Update Configuration

```http
POST /api/config
Content-Type: application/json

{
  "config": "... new TOML content ..."
}
```

Updates configuration file and reloads qBitrr.

---

## Complete Documentation

For the full API reference with all endpoints, request/response schemas, error codes, and examples:

**[→ View Complete API Documentation](../webui/api.md)**

---

## Client Libraries

### Python Example

```python
import requests

base_url = "http://localhost:6969/api"
headers = {"X-API-Token": "your-token"}

# Get processes
response = requests.get(f"{base_url}/processes", headers=headers)
processes = response.json()

# Get logs
response = requests.get(
    f"{base_url}/logs",
    headers=headers,
    params={"limit": 50, "level": "ERROR"}
)
logs = response.json()
```

### cURL Examples

```bash
# Health check (no auth)
curl http://localhost:6969/api/health

# Get processes (with auth)
curl -H "X-API-Token: your-token" \
  http://localhost:6969/api/processes

# Get logs with filters
curl -H "X-API-Token: your-token" \
  "http://localhost:6969/api/logs?limit=100&level=ERROR"

# Restart process
curl -X POST \
  -H "X-API-Token: your-token" \
  http://localhost:6969/api/processes/Radarr-Movies/restart
```

### JavaScript/TypeScript Example

```typescript
const BASE_URL = 'http://localhost:6969/api';
const API_TOKEN = 'your-token';

async function getProcesses() {
  const response = await fetch(`${BASE_URL}/processes`, {
    headers: {
      'X-API-Token': API_TOKEN
    }
  });
  return response.json();
}

async function getLogs(limit = 100, level = 'INFO') {
  const response = await fetch(
    `${BASE_URL}/logs?limit=${limit}&level=${level}`,
    {
      headers: {
        'X-API-Token': API_TOKEN
      }
    }
  );
  return response.json();
}
```

---

## Rate Limiting

The qBitrr API currently has **no rate limiting**. However, excessive requests may impact performance.

**Best Practices:**
- Poll at reasonable intervals (e.g., every 5-10 seconds for logs)
- Use WebSocket connections for real-time updates (planned feature)
- Cache responses when possible

---

## Error Handling

All API endpoints return standard HTTP status codes:

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid parameters |
| 401 | Unauthorized | Missing or invalid API token |
| 404 | Not Found | Endpoint or resource not found |
| 500 | Internal Server Error | Server-side error |

**Error Response Format:**
```json
{
  "error": "Error message",
  "details": "Additional context"
}
```

---

## Webhooks

qBitrr can send webhook notifications for events (planned feature).

**Supported Events:**
- Torrent completed
- Import successful
- Health check failed
- Process restarted

---

## OpenAPI Specification

An OpenAPI (Swagger) specification is planned for future releases, which will enable automatic client generation.

---

## Next Steps

- **[Full API Reference](../webui/api.md)** - Complete endpoint documentation
- **[WebUI Overview](../webui/index.md)** - WebUI features
- **[Configuration](../configuration/webui.md)** - WebUI settings
- **[Troubleshooting](../troubleshooting/common-issues.md)** - Common API issues
