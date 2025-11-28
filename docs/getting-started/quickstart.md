# Quick Start Guide

Get qBitrr running in 5 minutes!

## Prerequisites

- qBittorrent installed and running
- At least one Arr instance (Radarr, Sonarr, or Lidarr)
- qBitrr installed ([installation guide](installation/index.md))

## Step 1: Start qBitrr

=== "Docker"

    ```bash
    docker run -d \
      --name qbitrr \
      -p 6969:6969 \
      -v /path/to/config:/config \
      feramance/qbitrr:latest
    ```

=== "pip"

    ```bash
    qbitrr
    ```

=== "Systemd"

    ```bash
    sudo systemctl start qbitrr
    ```

On first run, qBitrr will generate a default `config.toml` file.

## Step 2: Stop qBitrr

Stop qBitrr so you can edit the configuration:

=== "Docker"

    ```bash
    docker stop qbitrr
    ```

=== "pip"

    Press ++ctrl+c++ in the terminal

=== "Systemd"

    ```bash
    sudo systemctl stop qbitrr
    ```

## Step 3: Edit Configuration

Find and edit your `config.toml` file:

=== "Docker"

    Location: `/path/to/config/config.toml` (where you mounted `/config`)

=== "pip"

    Location: `~/config/config.toml` (home directory)

=== "Systemd"

    Location: Set via `Environment="QBITRR_CONFIG_PATH=/path/to/config"` in service file

### Minimal Configuration

Here's the minimum configuration needed:

```toml
[Settings.Qbittorrent]
Host = "http://localhost:8080"  # Your qBittorrent URL
Username = "admin"               # qBittorrent username
Password = "adminpass"           # qBittorrent password
Version5 = false                 # Set to true for qBittorrent 5.x

[Radarr-Movies]  # Or Sonarr-TV, Lidarr-Music
URI = "http://localhost:7878"  # Your Radarr URL
APIKey = "your_radarr_api_key"  # From Radarr Settings > General > Security
```

!!! tip "Finding API Keys"
    - **Radarr**: Settings → General → Security → API Key
    - **Sonarr**: Settings → General → Security → API Key
    - **Lidarr**: Settings → General → Security → API Key

## Step 4: Configure Categories & Tags

qBitrr **requires** your Arr downloads to be tagged so it knows which torrents to monitor.

### In qBittorrent

1. Go to Tools → Options → Downloads
2. Set "Default Save Path" categories:
   - `radarr-movies` for Radarr downloads
   - `sonarr-tv` for Sonarr downloads
   - `lidarr-music` for Lidarr downloads

### In Radarr/Sonarr/Lidarr

1. Go to Settings → Download Clients
2. Edit your qBittorrent client
3. Set the **Category** to match your config:
   - Radarr: `radarr-movies`
   - Sonarr: `sonarr-tv`
   - Lidarr: `lidarr-music`
4. Add a **Tag** (e.g., `qbitrr`)
5. Save

### In qBitrr config.toml

Make sure your category names match:

```toml
[Settings]
CategoryRadarr = "radarr-movies"
CategorySonarr = "sonarr-tv"
CategoryLidarr = "lidarr-music"
```

## Step 5: Start qBitrr Again

=== "Docker"

    ```bash
    docker start qbitrr
    ```

=== "pip"

    ```bash
    qbitrr
    ```

=== "Systemd"

    ```bash
    sudo systemctl start qbitrr
    ```

## Step 6: Verify It's Working

### Check Logs

=== "Docker"

    ```bash
    docker logs -f qbitrr
    ```

=== "pip"

    ```bash
    tail -f ~/logs/Main.log
    ```

=== "Systemd"

    ```bash
    sudo journalctl -u qbitrr -f
    ```

Look for these messages:

- ✅ `Connecting to qBittorrent...`
- ✅ `Connecting to Radarr/Sonarr/Lidarr...`
- ✅ `Starting Arr manager process...`
- ❌ `Failed to connect...` (fix your URL/API key)

### Access the WebUI

1. Open your browser to `http://localhost:6969/ui`
2. Go to the **Processes** tab
3. You should see your Arr manager(s) running

## Step 7: Test with a Download

1. In Radarr/Sonarr/Lidarr, search for a movie/show/album
2. Manually grab a small torrent (for testing)
3. Watch qBitrr logs – it should detect the new torrent
4. When the download completes, qBitrr will trigger an import

## What's Next?

Now that qBitrr is running:

- ⚙️ [Configure advanced settings](../configuration/index.md)
- 🔍 [Enable automated search](../features/automated-search.md)
- 🎯 [Set up quality profiles](../configuration/quality-profiles.md)
- 📊 [Configure custom format scoring](../features/custom-formats.md)
- 🌱 [Set up seeding rules](../configuration/seeding.md)

## Troubleshooting

- **Torrents not being monitored**: Check categories and tags match
- **Imports not triggering**: Verify FFprobe validation is passing
- **Connection errors**: Double-check URLs and API keys
- **High CPU usage**: Adjust loop sleep timers

[Full Troubleshooting Guide →](../troubleshooting/index.md)
