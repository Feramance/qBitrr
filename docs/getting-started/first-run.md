# First Run Configuration

This guide walks you through configuring qBitrr for the first time after installation.

## Prerequisites

Before configuring qBitrr, ensure you have:

- ✅ qBitrr installed ([Installation Guide](installation/index.md))
- ✅ qBittorrent running and accessible
- ✅ At least one Arr instance configured (Radarr, Sonarr, or Lidarr)
- ✅ API keys for your Arr instances
- ✅ qBittorrent credentials (if authentication is enabled)

## Initial Setup

### 1. Start qBitrr

Start qBitrr for the first time to generate the default configuration:

=== "Docker"

    ```bash
    docker-compose up -d qbitrr
    docker logs -f qbitrr
    ```

=== "pip"

    ```bash
    qbitrr
    ```

=== "Systemd"

    ```bash
    sudo systemctl start qbitrr
    sudo journalctl -u qbitrr -f
    ```

### 2. Stop qBitrr

After the configuration file is generated, stop qBitrr:

=== "Docker"

    ```bash
    docker-compose down
    ```

=== "pip"

    Press ++ctrl+c++

=== "Systemd"

    ```bash
    sudo systemctl stop qbitrr
    ```

### 3. Find Configuration File

The configuration file location depends on your installation:

| Installation | Config Location |
|--------------|-----------------|
| Docker | `/path/to/config/config.toml` (where you mounted `/config`) |
| pip (Linux/macOS) | `~/config/config.toml` |
| pip (Windows) | `%USERPROFILE%\config\config.toml` |
| Systemd | Set via `QBITRR_CONFIG_PATH` environment variable |
| Binary | `~/.config/qbitrr/config.toml` |

## Minimum Required Configuration

At minimum, you need to configure:

1. qBittorrent connection
2. At least one Arr instance
3. Download folder path
4. Categories

### 1. qBittorrent Settings

Open `config.toml` and configure qBittorrent:

```toml
[qBit]
# qBittorrent URL (replace with your actual URL)
Host = "http://localhost:8080"

# qBittorrent credentials
Username = "admin"
Password = "adminpass"
```

!!! tip "Finding Your qBittorrent URL"
    - Local: `http://localhost:8080`
    - Docker: `http://qbittorrent:8080` (use container name)
    - Remote: `http://192.168.1.100:8080` (use server IP)

### 2. Download Folder

Set the path where qBittorrent saves completed downloads:

```toml
[Settings]
# This should match qBittorrent's "Default Save Path"
CompletedDownloadFolder = "/downloads"
```

!!! warning "Docker Path Mapping"
    All containers (qBittorrent, Arr instances, qBitrr) must see the same paths. If qBittorrent saves to `/downloads`, Radarr must also see `/downloads`.

### 3. Configure an Arr Instance

Configure at least one Arr instance. Here's an example for Radarr:

```toml
[Radarr-Movies]
# Radarr URL
URI = "http://localhost:7878"

# API Key (found in Radarr -> Settings -> General -> Security -> API Key)
APIKey = "your_radarr_api_key_here"
```

!!! tip "Finding API Keys"
    In Radarr/Sonarr/Lidarr:

    1. Go to Settings → General
    2. Scroll to "Security" section
    3. Copy the "API Key"

### 4. Categories

Configure categories that match your Arr download clients:

```toml
[Settings]
CategoryRadarr = "radarr-movies"
CategorySonarr = "sonarr-tv"
CategoryLidarr = "lidarr-music"
```

These must match the categories set in your Arr instances' download client configuration.

## Complete Minimal Configuration

Here's a complete minimal configuration:

```toml
[Settings]
CompletedDownloadFolder = "/downloads"
CategoryRadarr = "radarr-movies"
CategorySonarr = "sonarr-tv"
CategoryLidarr = "lidarr-music"

[qBit]
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "adminpass"

[Radarr-Movies]
URI = "http://localhost:7878"
APIKey = "your_radarr_api_key"

[Sonarr-TV]
URI = "http://localhost:8989"
APIKey = "your_sonarr_api_key"
```

## Category & Tag Configuration

### In qBittorrent

Your Arr instances' download clients should be configured to use the categories defined above.

### In Radarr

1. Go to Settings → Download Clients
2. Edit your qBittorrent client
3. Set **Category** to `radarr-movies`
4. Add a **Tag** (optional, e.g., `qbitrr`)
5. Save

### In Sonarr

Same as Radarr, but use category `sonarr-tv`.

### In Lidarr

Same as Radarr, but use category `lidarr-music`.

!!! warning "Categories Are Required"
    qBitrr uses categories to identify which torrents to monitor. Without matching categories, qBitrr won't process your downloads.

## Verify Configuration

### 1. Test qBittorrent Connection

Start qBitrr and check logs for connection messages:

```bash
# Look for:
# "Connecting to qBittorrent..."
# "Successfully connected to qBittorrent"
```

### 2. Test Arr Connections

Check logs for Arr connection messages:

```bash
# Look for:
# "Connecting to Radarr..."
# "Successfully connected to Radarr"
```

### 3. Test with WebUI

1. Start qBitrr
2. Open http://localhost:6969/ui
3. Go to the **Processes** tab
4. Verify Arr manager processes are running

## Optional Configuration

### Enable Automated Search

To enable automatic searching for missing media:

```toml
[Radarr-Movies.Search]
SearchMissing = true
SearchByYear = true
SearchLimit = 10
```

See [Automated Search](../features/automated-search.md) for details.

### Enable Free Space Management

To pause torrents when disk space is low:

```toml
[Settings]
FreeSpace = "100G"  # Pause when less than 100GB free
FreeSpaceFolder = "/downloads"
AutoPauseResume = true
```

### Configure Seeding Limits

Set global seeding limits:

```toml
[Radarr-Movies.Torrent]
MaximumETA = 604800  # 7 days in seconds
MaximumRatio = 2.0
MaximumSeedTime = 604800  # 7 days
```

See [Seeding Configuration](../configuration/seeding.md) for per-tracker settings.

### Enable Auto-Updates

To enable automatic qBitrr updates:

```toml
[Settings]
AutoUpdateEnabled = true
AutoUpdateCron = "0 3 * * 0"  # Sunday at 3 AM
```

### Configure WebUI Authentication

To secure the WebUI:

```toml
[WebUI]
Port = 6969
Token = "your_secret_token_here"
```

Then access with:
```bash
curl -H "Authorization: Bearer your_secret_token_here" \
  http://localhost:6969/api/health
```

## Common Configuration Mistakes

### 1. Path Mismatches

**Problem:** qBittorrent saves to `/downloads`, but Radarr sees `/data/downloads`

**Solution:** Use consistent paths across all containers:

```yaml
# docker-compose.yml
qbittorrent:
  volumes:
    - /mnt/storage/downloads:/downloads

radarr:
  volumes:
    - /mnt/storage/downloads:/downloads

qbitrr:
  volumes:
    - /mnt/storage/downloads:/downloads
```

### 2. Wrong Category

**Problem:** Radarr uses `radarr`, but config has `radarr-movies`

**Solution:** Ensure categories match exactly:

```toml
[Settings]
CategoryRadarr = "radarr"  # Must match Radarr's download client
```

### 3. Missing Tags

**Problem:** Torrents have tags but qBitrr has `Tagless = false`

**Solution:** Either:
- Enable tagless mode: `Tagless = true`
- Or configure tags in Arr download clients

### 4. Invalid API Keys

**Problem:** Copy-paste errors in API keys

**Solution:** Copy the entire key from Arr settings, including any dashes or special characters.

## Next Steps

Once configured:

1. **Start qBitrr**:
   ```bash
   docker-compose up -d  # or
   qbitrr  # or
   sudo systemctl start qbitrr
   ```

2. **Test with a download**:
   - Manually grab a small torrent in Radarr/Sonarr
   - Watch qBitrr logs
   - Verify it detects and processes the torrent

3. **Access WebUI**:
   - Navigate to http://localhost:6969/ui
   - Check Processes tab
   - Check Logs tab

4. **Further Configuration**:
   - [qBittorrent Settings](../configuration/qbittorrent.md)
   - [Arr Configuration](../configuration/arr/index.md)
   - [Automated Search](../features/automated-search.md)
   - [Seeding Rules](../configuration/seeding.md)

## Troubleshooting

### Config File Not Generated

If qBitrr doesn't generate a config file:

```bash
# Generate manually
qbitrr --gen-config
```

### Can't Find Config Location

Check the config path:

```bash
qbitrr --show-config-path
```

### Syntax Errors in Config

TOML syntax is strict. Common mistakes:

```toml
# ❌ Wrong - missing quotes
Host = http://localhost:8080

# ✅ Correct
Host = "http://localhost:8080"

# ❌ Wrong - wrong quotes
APIKey = 'abc123'

# ✅ Correct
APIKey = "abc123"
```

Validate your TOML:
```bash
python3 -c "import tomlkit; tomlkit.load(open('config.toml'))"
```

### qBitrr Won't Start

Check logs for specific errors:

```bash
# Docker
docker logs qbitrr

# Systemd
sudo journalctl -u qbitrr -n 50

# Direct
qbitrr  # Run in foreground to see errors
```

### Need More Help?

- [Configuration Reference](../configuration/config-file.md)
- [Common Issues](../troubleshooting/common-issues.md)
- [FAQ](../faq.md)
- [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions)
