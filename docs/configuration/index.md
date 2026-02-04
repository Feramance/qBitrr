# Configuration

Welcome to the qBitrr configuration guide! This section covers all aspects of configuring qBitrr to work with your setup.

## Quick Links

- [Configuration File Reference](config-file.md) - Complete `config.toml` reference
- [qBittorrent Setup](qbittorrent.md) - Configure qBittorrent connection
- [Arr Instances](arr/index.md) - Configure Radarr, Sonarr, and Lidarr

## Configuration Overview

qBitrr's configuration is organized into several logical sections, each controlling different aspects of functionality.

### Configuration Structure

```toml
[Settings]                    # Global settings
[WebUI]                       # WebUI configuration
[qBit]                        # qBittorrent connection

[[Radarr]]                    # Radarr instance(s)
  [Radarr.Torrent]           # Torrent settings
  [Radarr.EntrySearch]       # Search settings

[[Sonarr]]                    # Sonarr instance(s)
  [Sonarr.Torrent]
  [Sonarr.EntrySearch]

[[Lidarr]]                    # Lidarr instance(s)
  [Lidarr.Torrent]
  [Lidarr.EntrySearch]
```

**Minimum required:**
```toml
[qBit]
Host = "http://localhost"
Port = 8080
Username = "admin"
Password = "adminadmin"
```

## Configuration Sections

### Essential Configuration

These settings are **required** for qBitrr to function:

#### 1. qBittorrent Connection

**[qBittorrent Configuration Guide](qbittorrent.md)**

Configure connection to your qBittorrent instance:

- Host, port, and authentication
- Version-specific settings (v4.x vs v5.x)
- Docker networking considerations
- HTTPS/SSL configuration

**Minimum required:**
```toml
[qBit]
Host = "http://localhost"
Port = 8080
Username = "admin"
Password = "adminadmin"
```

#### 2. Arr Instances

**[Arr Configuration Guide](arr/index.md)**

Configure at least one Arr application:

- **[Radarr](arr/radarr.md)** - Movie library management
  - Movie searches
  - Quality upgrades
  - Custom formats
  - 4K instance support

- **[Sonarr](arr/sonarr.md)** - TV show library management
  - Episode monitoring
  - Season packs
  - Anime support
  - Specials handling

- **[Lidarr](arr/lidarr.md)** - Music library management
  - Album monitoring
  - Artist tracking
  - Lossless vs lossy quality
  - Metadata-driven organization

**Minimum required:**
```toml
[[Radarr]]
Name = "Radarr"
URI = "http://localhost:7878"
APIKey = "your-api-key-here"
```

### Feature Configuration

Optional features to enhance functionality:

#### 1. Automated Search

**[Search Configuration Guide](search/index.md)**

Automatically search for missing or wanted content:

- **Missing Content Search** - Find content not in your library
- **Quality Upgrades** - Replace lower quality with higher
- **Custom Format Scoring** - Enforce quality requirements
- **Schedule Configuration** - Control search frequency

**Key settings:**
```toml
[Radarr.EntrySearch]
SearchMissing = true
SearchRequestsEvery = 300
DoUpgradeSearch = true
```

#### 2. Torrent Management

**[Torrent Configuration Guide](torrents.md)**

Control how torrents are handled:

- **Health Monitoring** - Detect stalled/failed downloads
- **Automatic Removal** - Clean up completed torrents
- **ETA Limits** - Maximum allowed download time
- **Speed Thresholds** - Minimum download speeds

**Key settings:**
```toml
[Radarr.Torrent]
MaximumETA = 86400           # 24 hours
StalledDelay = 30            # 30 seconds
DoNotRemoveSlow = true       # Keep slow but progressing
```

#### 3. Seeding Management

**[Seeding Configuration Guide](seeding.md)**

Configure seeding behavior and limits:

- **Ratio Limits** - Maximum upload ratio
- **Time Limits** - Maximum seeding duration
- **Per-Tracker Rules** - Custom limits per tracker
- **Private Tracker Support** - Special handling

**Key settings:**
```toml
[Radarr.Torrent.SeedingMode]
MaxUploadRatio = 2.0
MaxSeedingTime = 604800      # 7 days
RemoveTorrent = 3            # Remove when ratio OR time met
```

#### 4. Quality Profiles

**[Quality Profile Guide](quality-profiles.md)**

Manage quality profiles and temporary quality handling:

- **Profile Mappings** - Map high → low quality temporarily
- **Automatic Reset** - Restore original profiles
- **Custom Format Integration** - Score-based upgrades

**Key settings:**
```toml
[Lidarr.EntrySearch]
UseTempForMissing = true
QualityProfileMappings = {"Lossless (FLAC)" = "Any (MP3-320)"}
```

#### 5. Request Integration

**[Request Integration Guide](search/index.md)**

Integrate with Overseerr or Ombi:

- **[Overseerr](search/overseerr.md)** - Popular request management
- **[Ombi](search/ombi.md)** - Alternative request manager
- **Approved-Only Mode** - Process only approved requests
- **4K Routing** - Route 4K requests to dedicated instances

**Key settings:**
```toml
[Radarr.Overseerr]
OverseerrURL = "http://localhost:5055"
OverseerrAPIKey = "your-overseerr-api-key"
ApprovedOnly = true
```

#### 6. WebUI Configuration

**[WebUI Guide](webui.md)**

Configure the web interface:

- **Access Control** - Token-based authentication
- **Display Settings** - Theme, grouping options
- **Network Settings** - Host, port binding

**Key settings:**
```toml
[WebUI]
Host = "0.0.0.0"
Port = 6969
Token = "your-secret-token"
Theme = "Dark"
```

### Advanced Configuration

Power-user features for specific scenarios:

#### 1. Environment Variables

**[Environment Variables Guide](environment.md)**

Configure qBitrr via environment variables:

- Override config file settings
- Container-friendly configuration
- Secret management integration
- Dynamic configuration

**Common variables:**
```bash
QBITRR_LOG_LEVEL=DEBUG
QBITRR_CONFIG_PATH=/custom/path
QBITRR_QBITTORRENT_HOST=http://qbittorrent:8080
```

#### 2. Logging Configuration

**[Logging Settings](config-file.md#logging)**

Control logging behavior:

- **Log Levels** - DEBUG, INFO, WARNING, ERROR
- **Log Rotation** - Automatic log file rotation
- **Per-Instance Logs** - Separate log files per Arr
- **Console vs File** - Output destinations

**Key settings:**
```toml
[Settings]
LogLevel = "INFO"
LogRotation = true
MaxLogSize = "10M"
```

#### 3. Database Configuration

**[Database Settings](../advanced/index.md#database)**

Configure SQLite database behavior:

- **Database Location** - Custom path support
- **WAL Mode** - Write-ahead logging (default)
- **Backup Settings** - Automatic backups
- **Optimization** - VACUUM scheduling

**Key settings:**
```toml
[Settings]
DatabasePath = "/config/qbitrr.db"
DatabaseBackupEnabled = true
```

## Configuration File Location

The configuration file is located at:

=== "Docker"
    ```
    /config/config.toml
    ```

=== "Native Install"
    ```
    ~/config/config.toml
    ```

=== "pip Install"
    ```
    ~/.config/qBitrr/config.toml
    ```

## Getting Started

1. **Generate Default Config**

   On first run, qBitrr automatically generates a default configuration file.

2. **Edit Configuration**

   Open the config file in your preferred text editor:
   ```bash
   nano ~/config/config.toml
   ```

3. **Configure Required Settings**

   At minimum, you need to configure:
   - qBittorrent connection details
   - At least one Arr instance (Radarr, Sonarr, or Lidarr)

4. **Restart qBitrr**

   After making changes, restart qBitrr for them to take effect.

## Configuration Best Practices

### Security

- **Never commit your config.toml** to version control
- **Use strong passwords** for qBittorrent and Arr instances
- **Enable authentication** on all services
- **Use HTTPS** when accessing services remotely

### Performance

- **Set appropriate intervals** - Don't check too frequently
- **Use categories** - Organize torrents by Arr instance
- **Enable instant imports** - For faster media availability
- **Configure logging** - Balance detail vs. disk space

### Reliability

- **Test connections** - Verify all services are accessible
- **Check logs** - Monitor for errors after configuration changes
- **Backup your config** - Save a copy before major changes
- **Use health checks** - Enable torrent health monitoring

## Common Configuration Scenarios

### Single Radarr Instance

Simplest setup for movie management only:

```toml
[qBit]
Host = "http://localhost"
Port = 8080
Username = "admin"
Password = "adminadmin"

[[Radarr]]
Name = "Radarr"
URI = "http://localhost:7878"
APIKey = "your-radarr-api-key"
```

### Multiple Arr Instances

Complete media server with movies, TV, and music:

```toml
[qBit]
Host = "http://localhost"
Port = 8080

[[Radarr]]
Name = "Radarr-Movies"
URI = "http://localhost:7878"
APIKey = "radarr-api-key"

[[Sonarr]]
Name = "Sonarr-TV"
URI = "http://localhost:8989"
APIKey = "sonarr-api-key"

[[Lidarr]]
Name = "Lidarr-Music"
URI = "http://localhost:8686"
APIKey = "lidarr-api-key"
```

### Docker Setup

Using Docker with custom network:

```toml
[qBit]
Host = "http://qbittorrent"  # Container name
Port = 8080

[[Radarr]]
Name = "Radarr"
URI = "http://radarr:7878"   # Container name
APIKey = "your-api-key"
```

## Configuration Workflow

Follow this recommended workflow when setting up qBitrr:

### Step 1: Initial Setup

1. **Install qBitrr** - Choose your installation method:
   - [Docker](../getting-started/installation/docker.md) (recommended)
   - [pip](../getting-started/installation/pip.md)
   - [Binary](../getting-started/installation/binary.md)

2. **Generate Default Config**:
   ```bash
   # Docker
   docker start qbitrr  # Stops after generating config

   # Native
   qbitrr --gen-config
   ```

3. **Locate Config File**:
   - Docker: `/config/config.toml`
   - Native: `~/config/config.toml`
   - pip: `~/.config/qBitrr/config.toml`

### Step 2: Configure Essentials

1. **Edit Config File**:
   ```bash
   nano /config/config.toml
   ```

2. **Configure qBittorrent**:
   ```toml
   [qBit]
   Host = "http://qbittorrent"
   Port = 8080
   Username = "admin"
   Password = "your-password"
   ```

   See: [qBittorrent Configuration](qbittorrent.md)

3. **Configure Arr Instance(s)**:
   ```toml
   [[Radarr]]
   Name = "Radarr-Movies"
   URI = "http://radarr:7878"
   APIKey = "your-radarr-api-key"
   ```

   See: [Arr Configuration](arr/index.md)

### Step 3: Enable Features

Choose which features to enable:

**For Beginners** - Start simple:
```toml
[[Radarr]]
# Basic health monitoring only
InstantImport = true
HealthCheck = true
```

**For Intermediate** - Add automation:
```toml
[Radarr.EntrySearch]
SearchMissing = true
SearchRequestsEvery = 300

[Radarr.Torrent]
MaximumETA = 86400
StalledDelay = 30
```

**For Advanced** - Full automation:
```toml
[Radarr.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true
QualityUnmetSearch = true
CustomFormatUnmetSearch = true

[Radarr.Torrent.SeedingMode]
MaxUploadRatio = 2.0
MaxSeedingTime = 604800

[Radarr.Overseerr]
OverseerrURL = "http://overseerr:5055"
OverseerrAPIKey = "your-key"
```

### Step 4: Validate Configuration

1. **Start qBitrr**:
   ```bash
   # Docker
   docker start qbitrr

   # Native
   qbitrr
   ```

2. **Check Logs**:
   ```bash
   # Docker
   docker logs -f qbitrr

   # Native
   tail -f ~/config/logs/Main.log
   ```

3. **Look for Success Messages**:
   ```
   INFO - Successfully connected to qBittorrent
   INFO - Successfully connected to Radarr-Movies
   INFO - Starting Radarr-Movies manager
   ```

4. **Access WebUI**:
   ```
   http://localhost:6969/ui
   ```

5. **Test Download**:
   - Add a test torrent to qBittorrent
   - Assign correct category (e.g., `radarr`)
   - Wait for completion
   - Verify import to Radarr

### Step 5: Fine-Tune Settings

Monitor and adjust based on your needs:

1. **Review Logs** - Check for errors or warnings
2. **Adjust Timings** - Tune search frequency, ETA limits
3. **Configure Seeding** - Set appropriate ratio/time limits
4. **Enable Upgrades** - Turn on quality upgrade searches
5. **Add Integrations** - Connect Overseerr/Ombi if desired

## Configuration Templates

### Template 1: Basic Home Server

Minimal setup for personal use:

```toml
[Settings]
LogLevel = "INFO"
FreeSpace = "10G"

[qBit]
Host = "http://localhost"
Port = 8080
Username = "admin"
Password = "adminadmin"

[[Radarr]]
Name = "Radarr-Movies"
URI = "http://localhost:7878"
APIKey = "your-radarr-api-key"
Category = "radarr"

[Radarr.Torrent]
MaximumETA = 86400

[[Sonarr]]
Name = "Sonarr-TV"
URI = "http://localhost:8989"
APIKey = "your-sonarr-api-key"
Category = "sonarr"

[Sonarr.Torrent]
MaximumETA = 172800  # 48 hours for TV
```

### Template 2: Power User with Automation

Full automation and quality management:

```toml
[Settings]
LogLevel = "INFO"
FreeSpace = "50G"
AutoPauseResume = true

[qBit]
Host = "http://qbittorrent"
Port = 8080

[[Radarr]]
Name = "Radarr-4K"
URI = "http://radarr:7878"
APIKey = "radarr-api-key"
Category = "radarr-4k"
ImportMode = "Hardlink"

[Radarr-4K.EntrySearch]
SearchMissing = true
SearchRequestsEvery = 300
DoUpgradeSearch = true
QualityUnmetSearch = true
CustomFormatUnmetSearch = true
ForceMinimumCustomFormat = true

[Radarr-4K.Torrent]
MaximumETA = -1  # No limit
DoNotRemoveSlow = true
StalledDelay = 60

[Radarr-4K.Torrent.SeedingMode]
MaxUploadRatio = 2.0
MaxSeedingTime = 1209600  # 14 days

[[Radarr-4K.Torrent.Trackers]]
Name = "Private Tracker"
URI = "https://tracker.example.com/announce"
MaxUploadRatio = 3.0  # Higher for private
MaxSeedingTime = 2592000  # 30 days
```

### Template 3: Docker Compose Stack

Complete Docker stack configuration:

```toml
[Settings]
LogLevel = "INFO"
FreeSpace = "20G"

[qBit]
Host = "http://qbittorrent"  # Container name
Port = 8080
Username = "admin"
Password = "adminadmin"

[WebUI]
Host = "0.0.0.0"
Port = 6969
Token = "change-this-secret-token"

[[Radarr]]
Name = "Radarr"
URI = "http://radarr:7878"  # Container name
APIKey = "${RADARR_API_KEY}"  # From environment

[[Sonarr]]
Name = "Sonarr"
URI = "http://sonarr:8989"  # Container name
APIKey = "${SONARR_API_KEY}"  # From environment

[[Lidarr]]
Name = "Lidarr"
URI = "http://lidarr:8686"  # Container name
APIKey = "${LIDARR_API_KEY}"  # From environment
```

### Template 4: Private Tracker Seedbox

Optimized for private trackers:

```toml
[Settings]
LogLevel = "INFO"

[qBit]
Host = "http://localhost"
Port = 8080

[[Radarr]]
Name = "Radarr-Private"
URI = "http://localhost:7878"
APIKey = "radarr-api-key"
Category = "radarr-private"
ImportMode = "Copy"  # Keep seeding after import

[Radarr-Private.Torrent]
DoNotRemoveSlow = true  # Never remove slow torrents
MaximumDeletablePercentage = 0.99  # Only remove if 99%+ complete
StalledDelay = 90  # Be very patient
MaximumETA = -1  # No ETA limit

[Radarr-Private.Torrent.SeedingMode]
MaxUploadRatio = -1  # Never stop based on ratio
MaxSeedingTime = 2592000  # Seed for 30 days minimum
RemoveTorrent = 2  # Only remove based on time

[[Radarr-Private.Torrent.Trackers]]
Name = "MyPrivateTracker"
Priority = 10
URI = "https://private.tracker.com/announce"
MaxUploadRatio = -1
MaxSeedingTime = 5184000  # 60 days for private
```

### Template 5: Request Integration (Overseerr)

Setup with Overseerr request management:

```toml
[qBit]
Host = "http://qbittorrent"
Port = 8080

[[Radarr]]
Name = "Radarr-1080p"
URI = "http://radarr:7878"
APIKey = "radarr-api-key"
Category = "radarr-1080p"

[Radarr-1080p.EntrySearch]
SearchMissing = true
SearchRequestsEvery = 180  # Check every 3 minutes

[Radarr-1080p.Overseerr]
OverseerrURL = "http://overseerr:5055"
OverseerrAPIKey = "overseerr-api-key"
ApprovedOnly = true
Is4K = false

[[Radarr]]
Name = "Radarr-4K"
URI = "http://radarr4k:7878"
APIKey = "radarr4k-api-key"
Category = "radarr-4k"

[Radarr-4K.Overseerr]
OverseerrURL = "http://overseerr:5055"
OverseerrAPIKey = "overseerr-api-key"
ApprovedOnly = true
Is4K = true  # Route 4K requests here
```

## Validation

After configuring qBitrr, verify your setup:

### Automated Validation

```bash
# Validate config syntax
qbitrr --validate-config

# Test connections
qbitrr --test-connections

# Dry run (don't make changes)
qbitrr --dry-run
```

### Manual Validation Checklist

- [ ] **Config Syntax** - TOML file is valid
- [ ] **qBittorrent Connection** - Can connect and authenticate
- [ ] **Arr Connections** - Each Arr instance accessible
- [ ] **Categories Match** - qBittorrent categories configured in Arr
- [ ] **Paths Accessible** - qBitrr can read download paths
- [ ] **Logs Clean** - No errors in startup logs
- [ ] **WebUI Accessible** - Can access http://localhost:6969/ui
- [ ] **Test Import** - Complete download imports successfully

### Verification Steps

1. **Check Logs for Connections**:
   ```bash
   docker logs qbitrr | grep "Successfully connected"
   ```

   Should see:
   ```
   INFO - Successfully connected to qBittorrent
   INFO - Successfully connected to Radarr-Movies
   INFO - Successfully connected to Sonarr-TV
   ```

2. **Verify in WebUI**:
   - Open http://localhost:6969/ui
   - Check "Processes" tab - all Arr managers should be running
   - Check "Logs" tab - no errors

3. **Test with Download**:
   ```bash
   # Add test torrent to qBittorrent with correct category
   # Wait for completion
   # Check Radarr for imported media
   ```

4. **Monitor Health Checks**:
   ```bash
   tail -f ~/config/logs/Radarr-Movies.log | grep health
   ```

## Troubleshooting Configuration

Common configuration issues and solutions:

### TOML Syntax Errors

**Problem**: Config file won't parse

**Symptoms**:
```
TOMLDecodeError: Invalid TOML syntax
```

**Solutions**:
- Check for missing quotes around strings
- Ensure proper section headers: `[Settings]` not `[settings]`
- Use correct array syntax: `[[Radarr]]` for instances
- Validate at [TOML Checker](https://www.toml-lint.com/)

**Example fixes**:
```toml
# Wrong
Host = http://localhost  # Missing quotes!

# Right
Host = "http://localhost"

# Wrong
[radarr]  # Lowercase, should be array

# Right
[[Radarr]]  # Double brackets for array
```

### Connection Failures

**Problem**: Can't connect to qBittorrent or Arr

See: [Connection Troubleshooting](../troubleshooting/common-issues.md#connection-issues)

### Path Mapping Issues

**Problem**: Downloads complete but don't import

See: [Path Mapping Guide](../troubleshooting/path-mapping.md)

### Category Mismatches

**Problem**: qBitrr doesn't track torrents

**Solution**: Ensure categories match:
1. qBitrr config: `Category = "radarr"`
2. Radarr download client: Category = `radarr`
3. qBittorrent: Category `radarr` exists

### Performance Issues

**Problem**: qBitrr uses too much CPU/memory

**Solutions**:
- Reduce search frequency: `SearchRequestsEvery = 600`
- Lower log level: `LogLevel = "INFO"`
- Increase delays: `StalledDelay = 60`

See: [Performance Troubleshooting](../troubleshooting/performance.md)

## Configuration Management

### Backup Configuration

```bash
# Backup config and database
cp ~/config/config.toml ~/config/config.toml.backup
cp ~/config/qbitrr.db ~/config/qbitrr.db.backup

# Docker
docker cp qbitrr:/config/config.toml ./config.toml.backup
```

### Version Control

**Don't commit secrets!** Use environment variables:

```toml
# config.toml
[[Radarr]]
APIKey = "${RADARR_API_KEY}"

[[Sonarr]]
APIKey = "${SONARR_API_KEY}"
```

Then use `.env` file (don't commit!):
```bash
# .env
RADARR_API_KEY=your-secret-key
SONARR_API_KEY=your-secret-key
```

### Migration Between Hosts

1. **Copy config and database**:
   ```bash
   scp ~/config/* newhost:~/config/
   ```

2. **Update paths** in config.toml if needed

3. **Update URIs** if services moved

4. **Restart qBitrr**

## Further Reading

### Configuration Guides

- **[Complete Configuration Reference](config-file.md)** - Every setting explained
- **[qBittorrent Setup](qbittorrent.md)** - qBittorrent connection guide
- **[Arr Configuration](arr/index.md)** - Radarr/Sonarr/Lidarr setup
- **[Search Configuration](search/index.md)** - Automated search settings
- **[Seeding Management](seeding.md)** - Seeding rules and limits
- **[Environment Variables](environment.md)** - ENV var configuration

### Getting Started

- **[First Run Guide](../getting-started/first-run.md)** - Step-by-step setup
- **[Quick Start](../getting-started/quickstart.md)** - Fastest path to working setup
- **[Installation](../getting-started/installation/index.md)** - Choose install method

### Troubleshooting

- **[Common Issues](../troubleshooting/common-issues.md)** - Frequent problems
- **[Docker Issues](../troubleshooting/docker.md)** - Docker-specific help
- **[Path Mapping](../troubleshooting/path-mapping.md)** - Fix import issues
- **[Debug Logging](../troubleshooting/debug-logging.md)** - Enable detailed logs

### Reference

- **[FAQ](../faq.md)** - Frequently asked questions
- **[Glossary](../reference/glossary.md)** - Technical terms explained
- **[API Reference](../reference/api.md)** - REST API documentation

---

## Related Documentation

- [Features Overview](../features/index.md) - What qBitrr can do
- [WebUI Guide](../webui/index.md) - Use the web interface
- [Development Guide](../development/index.md) - Contribute to qBitrr
