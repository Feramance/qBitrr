# Configuration Schema

Complete reference for qBitrr's TOML configuration schema.

## Schema Overview

qBitrr uses TOML (Tom's Obvious, Minimal Language) for configuration. The schema is defined in `qBitrr/gen_config.py` and validated on startup.

## Configuration Structure

```toml
[Settings]
# Global settings

[Settings.Qbittorrent]
# qBittorrent connection settings

[[Radarr]]
# Radarr instance configuration (can have multiple)

[[Sonarr]]
# Sonarr instance configuration (can have multiple)

[[Lidarr]]
# Lidarr instance configuration (can have multiple)
```

## Settings Section

### Core Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `LogLevel` | string | `"INFO"` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `CheckInterval` | int | `60` | Seconds between torrent health checks |
| `FreeSpace` | string | `"10G"` | Minimum free disk space before pausing downloads |
| `DataDir` | string | `"~/config"` | Directory for database and logs |
| `WebUIHost` | string | `"0.0.0.0"` | WebUI bind address |
| `WebUIPort` | int | `6969` | WebUI port |
| `WebUIToken` | string | (empty) | API authentication token (optional) |

**Example:**

```toml
[Settings]
LogLevel = "INFO"
CheckInterval = 60
FreeSpace = "20G"
WebUIHost = "127.0.0.1"
WebUIPort = 6969
WebUIToken = "your-secret-token-here"
```

### Qbittorrent Subsection

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `Host` | string | **required** | qBittorrent URL (e.g., `http://localhost:8080`) |
| `Username` | string | **required** | qBittorrent username |
| `Password` | string | **required** | qBittorrent password |
| `Version5` | bool | `false` | Use qBittorrent API v5 |

**Example:**

```toml
[Settings.Qbittorrent]
Host = "http://qbittorrent:8080"
Username = "admin"
Password = "adminadmin"
Version5 = true
```

### Advanced Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `RetentionDays` | int | `30` | Days to keep torrent history |
| `AutoVacuum` | bool | `true` | Automatically optimize database |
| `MaxConcurrentChecks` | int | `10` | Max parallel health checks |
| `MaxConnections` | int | `100` | HTTP connection pool size |
| `ConnectionTimeout` | int | `30` | Connection timeout (seconds) |
| `ReadTimeout` | int | `60` | Read timeout (seconds) |
| `MaxRetries` | int | `3` | Max retry attempts on failure |
| `RetryDelay` | int | `5` | Seconds between retries |

**Example:**

```toml
[Settings]
RetentionDays = 14
MaxConcurrentChecks = 20
MaxRetries = 5
```

### FFprobe Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `EnableFFprobe` | bool | `true` | Enable media file validation |
| `FFprobePath` | string | (auto) | Path to ffprobe binary |
| `FFprobeAutoUpdate` | bool | `true` | Auto-download ffprobe if missing |
| `FFprobeTimeout` | int | `30` | FFprobe timeout (seconds) |
| `ValidateAllFiles` | bool | `false` | Validate all files (vs. largest only) |

**Example:**

```toml
[Settings]
EnableFFprobe = true
FFprobePath = "/usr/bin/ffprobe"
FFprobeTimeout = 60
ValidateAllFiles = false
```

## Radarr Section

Configure Radarr movie management instances. You can have multiple `[[Radarr]]` sections.

### Required Fields

| Key | Type | Description |
|-----|------|-------------|
| `Name` | string | Unique name for this instance |
| `URI` | string | Radarr URL (e.g., `http://localhost:7878`) |
| `APIKey` | string | Radarr API key |

### Optional Fields

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `Managed` | bool | `true` | Whether qBitrr manages this instance |
| `Category` | string | `"radarr-movies"` | qBittorrent category for this instance |
| `QualityProfile` | string | (none) | Force specific quality profile |
| `CheckInterval` | int | (global) | Override global check interval |
| `AutoReSearch` | bool | `false` | Re-search for failed downloads |
| `SearchMissing` | bool | `false` | Automatically search for missing movies |
| `SearchByCriteria` | bool | `false` | Search by quality criteria |
| `SearchOnAdd` | bool | `false` | Search when movie added to Radarr |
| `SearchByYear` | bool | `false` | Include year in search queries |

### Health Check Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `MaximumETA` | int | `3600` | Max ETA before marking stalled (seconds) |
| `StalledDelay` | int | `300` | Delay before rechecking stalled torrent |
| `MinimumAge` | int | `300` | Minimum age before health checks (seconds) |

### Seeding Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `MinimumSeedTime` | int | `86400` | Min seed time before deletion (seconds, 24h default) |
| `MinimumRatio` | float | `1.0` | Min seed ratio before deletion |
| `MaximumSeedTime` | int | (none) | Max seed time (force delete after) |
| `MaximumRatio` | float | (none) | Max seed ratio (force delete after) |
| `DeleteOnMaximum` | bool | `true` | Delete when max seed reached |

### Import Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `DelayAfterImport` | int | `60` | Seconds to wait after import |
| `ImportPath` | string | (auto) | Custom import path |
| `AutoImport` | bool | `true` | Automatically import completed torrents |

**Example:**

```toml
[[Radarr]]
Name = "Radarr-4K"
URI = "http://localhost:7878"
APIKey = "your-radarr-api-key"
Category = "movies-4k"
QualityProfile = "Ultra HD"

# Health checks
MaximumETA = 7200
StalledDelay = 600

# Seeding
MinimumSeedTime = 172800  # 2 days
MinimumRatio = 1.5

# Searching
AutoReSearch = true
SearchMissing = true
```

## Sonarr Section

Configure Sonarr TV show management instances. Schema is identical to Radarr.

### Key Differences

| Key | Default | Notes |
|-----|---------|-------|
| `Category` | `"sonarr-tv"` | Different default category |
| `AnimeMode` | `false` | Special handling for anime |

**Example:**

```toml
[[Sonarr]]
Name = "Sonarr-TV"
URI = "http://localhost:8989"
APIKey = "your-sonarr-api-key"
Category = "tv-shows"

[[Sonarr]]
Name = "Sonarr-Anime"
URI = "http://localhost:8990"
APIKey = "your-sonarr-anime-api-key"
Category = "anime"
AnimeMode = true
```

## Lidarr Section

Configure Lidarr music management instances. Schema similar to Radarr/Sonarr.

### Key Differences

| Key | Default | Notes |
|-----|---------|-------|
| `Category` | `"lidarr-music"` | Different default category |
| `ArtistMode` | `true` | Group by artist |

**Example:**

```toml
[[Lidarr]]
Name = "Lidarr-Music"
URI = "http://localhost:8686"
APIKey = "your-lidarr-api-key"
Category = "music"
MinimumSeedTime = 259200  # 3 days (music trackers often require longer)
```

## Environment Variable Overrides

Any configuration key can be overridden with environment variables using the pattern:

```
QBITRR_<SECTION>_<KEY>
```

### Examples

```bash
# Override global settings
export QBITRR_SETTINGS_LOGLEVEL="DEBUG"
export QBITRR_SETTINGS_CHECKINTERVAL="30"

# Override qBittorrent settings
export QBITRR_QBITTORRENT_HOST="http://qbittorrent:8080"
export QBITRR_QBITTORRENT_USERNAME="admin"
export QBITRR_QBITTORRENT_PASSWORD="secret"

# Override Arr settings (first instance)
export QBITRR_RADARR_URL="http://radarr:7878"
export QBITRR_RADARR_API_KEY="your-api-key"
```

### Docker Compose Example

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    environment:
      - QBITRR_SETTINGS_LOGLEVEL=DEBUG
      - QBITRR_QBITTORRENT_HOST=http://qbittorrent:8080
      - QBITRR_RADARR_URL=http://radarr:7878
      - QBITRR_RADARR_API_KEY=${RADARR_API_KEY}
    volumes:
      - ./config:/config
```

## Validation Rules

### Required Fields

The following fields **must** be present:

- `Settings.Qbittorrent.Host`
- `Settings.Qbittorrent.Username`
- `Settings.Qbittorrent.Password`

For each Arr instance:
- `Name` (must be unique)
- `URI`
- `APIKey`

### Data Type Validation

- **Integers**: Must be non-negative unless specified
- **Strings**: Must not be empty for required fields
- **URLs**: Must start with `http://` or `https://`
- **File paths**: Must be valid paths (validated on first use)
- **API keys**: Must be alphanumeric (32+ characters typical)

### Value Ranges

| Setting | Min | Max | Unit |
|---------|-----|-----|------|
| `CheckInterval` | 10 | 3600 | seconds |
| `MaxConcurrentChecks` | 1 | 100 | count |
| `MaximumETA` | 60 | 86400 | seconds |
| `MinimumSeedTime` | 0 | (none) | seconds |
| `MinimumRatio` | 0.0 | (none) | ratio |
| `WebUIPort` | 1024 | 65535 | port |

## Configuration Generation

### Generate Default Config

```bash
# Generate default configuration
qbitrr --gen-config

# Generate at specific location
qbitrr --gen-config --config /custom/path/config.toml
```

### Validate Existing Config

```bash
# Validate configuration syntax
qbitrr --validate-config

# Test connections to all services
qbitrr --test-connections
```

## Migration

### Config Version

qBitrr automatically migrates old configurations to new schema versions.

**Current version:** Check `CURRENT_CONFIG_VERSION` in `qBitrr/config.py`

**Migration logic:** `qBitrr/config.py:apply_config_migrations()`

### Manual Migration

If automatic migration fails:

1. **Backup existing config:**
   ```bash
   cp ~/config/config.toml ~/config/config.toml.backup
   ```

2. **Generate new config:**
   ```bash
   qbitrr --gen-config --config ~/config/config.toml.new
   ```

3. **Manually transfer settings:**
   - Copy your API keys, URLs, and custom settings to new config
   - Compare old and new configs to identify changes

4. **Validate new config:**
   ```bash
   qbitrr --validate-config --config ~/config/config.toml.new
   ```

5. **Replace old config:**
   ```bash
   mv ~/config/config.toml.new ~/config/config.toml
   ```

## Complete Example

```toml
[Settings]
LogLevel = "INFO"
CheckInterval = 60
FreeSpace = "20G"
DataDir = "/config"
WebUIHost = "0.0.0.0"
WebUIPort = 6969
WebUIToken = "your-secret-token-here"

RetentionDays = 30
MaxConcurrentChecks = 10
EnableFFprobe = true

[Settings.Qbittorrent]
Host = "http://qbittorrent:8080"
Username = "admin"
Password = "adminadmin"
Version5 = true

[[Radarr]]
Name = "Radarr-1080p"
URI = "http://radarr:7878"
APIKey = "radarr-api-key-here"
Category = "movies-1080p"
QualityProfile = "HD-1080p"
MaximumETA = 3600
MinimumSeedTime = 86400
MinimumRatio = 1.0
AutoReSearch = true
SearchMissing = true

[[Radarr]]
Name = "Radarr-4K"
URI = "http://radarr-4k:7878"
APIKey = "radarr-4k-api-key-here"
Category = "movies-4k"
QualityProfile = "Ultra HD"
MaximumETA = 7200
MinimumSeedTime = 172800
MinimumRatio = 1.5
AutoReSearch = true

[[Sonarr]]
Name = "Sonarr-TV"
URI = "http://sonarr:8989"
APIKey = "sonarr-api-key-here"
Category = "tv-shows"
MaximumETA = 3600
MinimumSeedTime = 86400
MinimumRatio = 1.0
AutoReSearch = true
SearchMissing = true

[[Lidarr]]
Name = "Lidarr-Music"
URI = "http://lidarr:8686"
APIKey = "lidarr-api-key-here"
Category = "music"
MinimumSeedTime = 259200
MinimumRatio = 2.0
AutoReSearch = false
```

## Related Documentation

- [Configuration: Config File](../configuration/config-file.md) - Configuration guide
- [Configuration: Environment Variables](../configuration/environment.md) - Environment variable details
- [Reference: CLI](cli.md) - Command-line interface
- [Getting Started: First Run](../getting-started/first-run.md) - Initial configuration
