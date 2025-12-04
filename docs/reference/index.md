# Reference

Quick reference documentation for qBitrr commands, APIs, and specifications.

## Command Line Interface

### Basic Usage

```bash
# Start qBitrr
qbitrr

# Generate default configuration
qbitrr --gen-config

# Specify custom config location
qbitrr --config /path/to/config.toml

# Show version
qbitrr --version

# Show help
qbitrr --help
```

### Environment Variables

qBitrr supports environment variable configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `QBITRR_CONFIG` | Path to config.toml | `~/config/config.toml` |
| `QBITRR_LOG_LEVEL` | Logging level | `INFO` |
| `QBITRR_HOME` | qBitrr home directory | `~` |

**Example:**
```bash
export QBITRR_CONFIG=/custom/path/config.toml
export QBITRR_LOG_LEVEL=DEBUG
qbitrr
```

## API Reference

### REST API Endpoints

The qBitrr WebUI is powered by a REST API:

#### Process Management

```http
GET /api/processes
```
**Response:**
```json
{
  "processes": [
    {
      "name": "Radarr-Main",
      "status": "running",
      "pid": 12345,
      "uptime": 3600
    }
  ]
}
```

#### Logs

```http
GET /api/logs?limit=100&level=INFO
```
**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2025-11-26T12:00:00Z",
      "level": "INFO",
      "message": "Torrent imported successfully",
      "source": "Radarr-Main"
    }
  ]
}
```

#### Radarr Movies

```http
GET /api/radarr/movies?instance=Radarr-Main
```
**Response:**
```json
{
  "movies": [
    {
      "id": 1,
      "title": "Example Movie",
      "year": 2024,
      "monitored": true,
      "hasFile": true
    }
  ]
}
```

#### Configuration

```http
GET /api/config
POST /api/config
```

### Authentication

If WebUI token is configured:

```bash
curl http://localhost:6969/api/processes \
  -H "X-API-Token: your-token-here"
```

## Configuration Schema

### Main Settings

```toml
[Settings]
LogLevel = "INFO"           # DEBUG | INFO | WARNING | ERROR | CRITICAL
CheckInterval = 60          # Seconds between torrent checks
MaxConcurrentChecks = 10    # Max parallel health checks
RetentionDays = 30          # Days to keep old data
WebUIPort = 6969            # WebUI port
WebUIHost = "0.0.0.0"       # WebUI bind address
WebUIToken = ""             # Optional API token
```

### qBittorrent

```toml
[Settings.Qbittorrent]
Host = "http://localhost"   # qBittorrent URL
Port = 8080                 # qBittorrent port
Username = "admin"          # qBit username
Password = "adminadmin"     # qBit password
Version5 = false            # Use v5 API
```

### Arr Instances

```toml
[[Radarr]]  # or [[Sonarr]] or [[Lidarr]]
Name = "Radarr-Main"        # Unique identifier
URI = "http://localhost:7878"
APIKey = "your-api-key"
Category = "radarr"         # qBit category
AutoStart = true            # Start on launch
HealthCheck = true          # Enable health monitoring
InstantImport = true        # Instant imports
SearchMissing = false       # Auto-search missing
SearchPeriodDays = 7        # Search interval
```

## File Locations

### Default Paths

| File | Docker | Native | pip |
|------|--------|--------|-----|
| Config | `/config/config.toml` | `~/config/config.toml` | `~/.config/qBitrr/config.toml` |
| Database | `/config/qBitrr.db` | `~/config/qBitrr.db` | `~/.config/qBitrr/qBitrr.db` |
| Logs | `/config/logs/` | `~/config/logs/` | `~/.config/qBitrr/logs/` |
| Cache | `/config/cache/` | `~/config/cache/` | `~/.config/qBitrr/cache/` |

### Log Files

- `Main.log` - qBitrr application logs
- `WebUI.log` - Web interface logs
- `{ArrName}.log` - Per-Arr instance logs

## Error Codes

### Common Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Connection error |
| 4 | Database error |

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request |
| 401 | Unauthorized (missing/invalid token) |
| 404 | Not found |
| 500 | Internal server error |

## Database Schema

### Tables

#### downloads
Tracks downloaded torrents:

```sql
CREATE TABLE downloads (
  id INTEGER PRIMARY KEY,
  hash TEXT UNIQUE NOT NULL,
  name TEXT,
  arr_instance TEXT,
  status TEXT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

#### searches
Search activity history:

```sql
CREATE TABLE searches (
  id INTEGER PRIMARY KEY,
  arr_instance TEXT,
  media_id INTEGER,
  search_type TEXT,
  created_at TIMESTAMP
);
```

#### expiry
Entry expiration tracking:

```sql
CREATE TABLE expiry (
  id INTEGER PRIMARY KEY,
  entry_type TEXT,
  entry_id INTEGER,
  expires_at TIMESTAMP
);
```

## Glossary

| Term | Definition |
|------|------------|
| **Arr** | Radarr, Sonarr, or Lidarr |
| **Instant Import** | Triggering import immediately on completion |
| **Health Check** | Monitoring torrent status and validity |
| **FFprobe** | Media file validation tool |
| **Stalled Torrent** | Download stuck or progressing too slowly |
| **ETA** | Estimated Time to Arrival (completion) |
| **MaxETA** | Maximum allowed ETA before marking as stalled |
| **Category** | qBittorrent label for organizing torrents |
| **Quality Profile** | Arr quality/format preferences |
| **Custom Format** | Arr-specific release preferences |

## Configuration Examples

### Minimal Configuration

```toml
[Settings.Qbittorrent]
Host = "http://localhost"
Port = 8080

[[Radarr]]
Name = "Radarr"
URI = "http://localhost:7878"
APIKey = "your-api-key"
```

### Complete Configuration

See [Configuration File Reference](../configuration/config-file.md) for comprehensive examples.

## Version Compatibility

### qBittorrent

- **v4.x** - Fully supported (set `Version5 = false`)
- **v5.x** - Fully supported (set `Version5 = true`)

### Arr Applications

- **Radarr** - v3.x, v4.x, v5.x
- **Sonarr** - v3.x, v4.x
- **Lidarr** - v1.x, v2.x

### Python

- **Minimum** - Python 3.11
- **Recommended** - Python 3.12+

## Useful Links

- **Repository:** https://github.com/Feramance/qBitrr
- **PyPI:** https://pypi.org/project/qBitrr2/
- **Docker Hub:** https://hub.docker.com/r/feramance/qbitrr
- **Documentation:** https://feramance.github.io/qBitrr/
- **Issues:** https://github.com/Feramance/qBitrr/issues
- **Discussions:** https://github.com/Feramance/qBitrr/discussions

## Related Documentation

- [Configuration Guide](../configuration/index.md)
- [Troubleshooting](../troubleshooting/index.md)
- [FAQ](../faq.md)
- [Development](../development/index.md)

## Support

Need help? Check out:

- [FAQ](../faq.md) - Common questions
- [Troubleshooting](../troubleshooting/index.md) - Problem solving
- [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions) - Community support
