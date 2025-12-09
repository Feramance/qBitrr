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

---

## Common Quick Start Scenarios

### Scenario 1: Simple Home Server

**Setup:** Single Radarr for movies, basic monitoring

**Time:** 10 minutes

```toml
[Settings.Qbittorrent]
Host = "http://localhost:8080"
Username = "admin"
Password = "adminpass"
Version5 = false

[Radarr-Movies]
URI = "http://localhost:7878"
APIKey = "your-api-key-here"
Category = "radarr-movies"
Managed = true
ReSearch = true
importMode = "Auto"
```

**What You Get:**
- ✅ Automatic torrent health monitoring
- ✅ Instant imports when downloads complete
- ✅ Automatic re-search on failed downloads
- ✅ WebUI for monitoring

---

### Scenario 2: Multi-Arr Setup

**Setup:** Radarr + Sonarr + Lidarr, full automation

**Time:** 20 minutes

```toml
[Settings.Qbittorrent]
Host = "http://localhost:8080"
Username = "admin"
Password = "adminpass"
Version5 = false

[Settings]
# Global settings
CompletedDownloadFolder = "/downloads"
FreeSpace = "50G"  # Pause when less than 50GB free
AutoPauseResume = true

[Radarr-Movies]
URI = "http://localhost:7878"
APIKey = "radarr-api-key"
Category = "radarr-movies"
Managed = true
ReSearch = true

[Radarr-Movies.EntrySearch]
SearchMissing = true
SearchLimit = 5
SearchByYear = true

[Sonarr-TV]
URI = "http://localhost:8989"
APIKey = "sonarr-api-key"
Category = "sonarr-tv"
Managed = true
ReSearch = true

[Sonarr-TV.EntrySearch]
SearchMissing = true
PrioritizeTodaysReleases = true
SearchBySeries = "smart"

[Lidarr-Music]
URI = "http://localhost:8686"
APIKey = "lidarr-api-key"
Category = "lidarr-music"
Managed = true
ReSearch = true
```

**What You Get:**
- ✅ All three Arr types managed
- ✅ Automated search for missing content
- ✅ Disk space management
- ✅ Today's TV episodes prioritized
- ✅ Smart series vs episode search

---

### Scenario 3: Power User with Quality Control

**Setup:** Radarr 4K + 1080p, Sonarr, Custom Formats

**Time:** 45 minutes

```toml
[Settings.Qbittorrent]
Host = "http://qbittorrent:8080"  # Docker container name
Username = "admin"
Password = "secure-password-here"
Version5 = true  # Using qBittorrent 5.x

[Settings]
EnableFFprobe = true  # Validate files before import
FFprobeAutoUpdate = true

# Radarr for 4K movies
[Radarr-4K]
URI = "http://radarr-4k:7879"
APIKey = "radarr-4k-api-key"
Category = "radarr-4k"
Managed = true
importMode = "Copy"  # Keep seeding

[Radarr-4K.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true
CustomFormatUnmetSearch = true
ForceMinimumCustomFormat = true
SearchLimit = 3

[Radarr-4K.Torrent]
MaximumETA = 86400  # 24 hours
StalledDelay = 30
FileExtensionAllowlist = [".mkv", ".mp4", ".!qB", ".parts"]

[Radarr-4K.Torrent.SeedingMode]
MaxUploadRatio = 3.0
MaxSeedingTime = 1209600  # 14 days
RemoveTorrent = 4  # Both ratio AND time

# Radarr for 1080p movies
[Radarr-HD]
URI = "http://radarr:7878"
APIKey = "radarr-hd-api-key"
Category = "radarr-hd"
Managed = true
importMode = "Move"

[Radarr-HD.EntrySearch]
SearchMissing = true
SearchLimit = 10

# Sonarr for TV
[Sonarr-TV]
URI = "http://sonarr:8989"
APIKey = "sonarr-api-key"
Category = "sonarr-tv"
Managed = true

[Sonarr-TV.EntrySearch]
SearchMissing = true
PrioritizeTodaysReleases = true
AlsoSearchSpecials = false
SearchBySeries = "smart"
```

**What You Get:**
- ✅ Separate 4K and HD libraries
- ✅ FFprobe validation for file integrity
- ✅ Custom format enforcement
- ✅ Quality upgrade searches
- ✅ Per-library seeding rules
- ✅ Automated search for missing content

---

### Scenario 4: Docker Compose Full Stack

**Setup:** Complete media stack with Overseerr

**Time:** 30 minutes

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  qbittorrent:
    image: linuxserver/qbittorrent:latest
    container_name: qbittorrent
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
      - WEBUI_PORT=8080
    volumes:
      - ./qbittorrent/config:/config
      - /mnt/storage/downloads:/downloads
    ports:
      - "8080:8080"
      - "6881:6881"
    restart: unless-stopped

  radarr:
    image: linuxserver/radarr:latest
    container_name: radarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./radarr/config:/config
      - /mnt/storage:/storage
    ports:
      - "7878:7878"
    restart: unless-stopped

  sonarr:
    image: linuxserver/sonarr:latest
    container_name: sonarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./sonarr/config:/config
      - /mnt/storage:/storage
    ports:
      - "8989:8989"
    restart: unless-stopped

  overseerr:
    image: sctx/overseerr:latest
    container_name: overseerr
    environment:
      - LOG_LEVEL=info
      - TZ=America/New_York
    ports:
      - "5055:5055"
    volumes:
      - ./overseerr/config:/app/config
    restart: unless-stopped

  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./qbitrr/config:/config
      - /mnt/storage:/storage  # Same as Arr instances
    ports:
      - "6969:6969"
    depends_on:
      - qbittorrent
      - radarr
      - sonarr
    restart: unless-stopped
```

**qBitrr config.toml:**
```toml
[Settings.Qbittorrent]
Host = "http://qbittorrent:8080"  # Use container names
Username = "admin"
Password = "adminpass"

[Settings]
CompletedDownloadFolder = "/storage/downloads"

[Radarr-Movies]
URI = "http://radarr:7878"
APIKey = "your-radarr-api-key"
Category = "radarr-movies"
Managed = true

[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://overseerr:5055"
OverseerrAPIKey = "your-overseerr-api-key"
ApprovedOnly = true
Is4K = false

[Sonarr-TV]
URI = "http://sonarr:8989"
APIKey = "your-sonarr-api-key"
Category = "sonarr-tv"
Managed = true

[Sonarr-TV.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://overseerr:5055"
OverseerrAPIKey = "your-overseerr-api-key"
ApprovedOnly = true
```

**What You Get:**
- ✅ Complete Docker stack with consistent paths
- ✅ Overseerr integration for requests
- ✅ Automatic container dependencies
- ✅ Easy backup (just copy folders)
- ✅ Network isolation

---

## Configuration Checklist

Before starting, verify:

### qBittorrent Configuration
- [ ] WebUI enabled (Tools → Options → Web UI)
- [ ] Authentication configured (username/password)
- [ ] Default save path set
- [ ] Categories created for each Arr instance

### Arr Configuration
- [ ] API key available (Settings → General → Security)
- [ ] qBittorrent download client added
- [ ] Category set in download client
- [ ] Optional: Tags configured
- [ ] Root folders configured
- [ ] Quality profiles set up

### Network Configuration
- [ ] All services can reach each other
- [ ] Ports not blocked by firewall
- [ ] Docker networks configured (if using Docker)
- [ ] Path mappings consistent across services

---

## Verification Commands

Test your setup with these commands:

### Test qBittorrent Connection
```bash
# From qBitrr container/host
curl -u admin:adminpass http://qbittorrent:8080/api/v2/app/version

# Expected: {"version":"4.6.0"} or similar
```

### Test Radarr Connection
```bash
curl -H "X-Api-Key: your-api-key" http://radarr:7878/api/v3/system/status

# Expected: JSON with version, branch, etc.
```

### Test Sonarr Connection
```bash
curl -H "X-Api-Key: your-api-key" http://sonarr:8989/api/v3/system/status

# Expected: JSON with version, branch, etc.
```

### Test qBitrr WebUI
```bash
curl http://localhost:6969/api/health

# Expected: {"status":"healthy","version":"5.5.5"}
```

---

## Common First-Run Issues

### Issue: "Connection refused"

**Symptoms:**
```
ERROR - Failed to connect to qBittorrent at http://localhost:8080
```

**Solutions:**

1. **Check service is running:**
   ```bash
   docker ps | grep qbittorrent
   netstat -tulpn | grep 8080
   ```

2. **Use correct hostname:**
   ```toml
   # Docker: Use container name
   Host = "http://qbittorrent:8080"

   # Native: Use localhost or IP
   Host = "http://localhost:8080"
   ```

3. **Verify port mapping:**
   ```bash
   docker port qbittorrent
   ```

---

### Issue: "Unauthorized" / 401 Error

**Symptoms:**
```
ERROR - qBittorrent authentication failed
```

**Solutions:**

1. **Check credentials:**
   ```toml
   Username = "admin"  # Must match qBittorrent
   Password = "adminpass"  # Case-sensitive!
   ```

2. **Test manually:**
   ```bash
   curl -u admin:adminpass http://localhost:8080/api/v2/app/version
   ```

3. **Reset qBittorrent password if forgotten**

---

### Issue: "Torrents not being monitored"

**Symptoms:** qBitrr runs but doesn't detect torrents

**Solutions:**

1. **Verify category matches:**
   ```toml
   # qBitrr config
   [Radarr-Movies]
   Category = "radarr-movies"

   # Radarr download client
   # Category must be exactly "radarr-movies"
   ```

2. **Check torrent has category:**
   - In qBittorrent, check torrent properties
   - Category should show "radarr-movies"

3. **Enable category in qBittorrent:**
   - Tools → Options → Downloads → Category
   - Add "radarr-movies" category

---

### Issue: "Imports not triggering"

**Symptoms:** Downloads complete but don't import to Arr

**Solutions:**

1. **Check path mapping:**
   ```yaml
   # All services must see same paths
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

2. **Verify file permissions:**
   ```bash
   ls -la /downloads/radarr-movies/
   # Files should be readable by Radarr user
   ```

3. **Enable instant imports:**
   ```toml
   [Radarr-Movies]
   InstantImport = true  # Default is true
   ```

4. **Check Radarr logs:**
   - Look for "Import failed" messages
   - Common: Path mapping, permissions, file format issues

---

### Issue: "FFprobe validation failed"

**Symptoms:**
```
WARNING - FFprobe validation failed for torrent XYZ
```

**Solutions:**

1. **Let qBitrr download FFprobe:**
   ```toml
   [Settings]
   EnableFFprobe = true
   FFprobeAutoUpdate = true
   ```

2. **Temporarily disable to test:**
   ```toml
   [Settings]
   EnableFFprobe = false
   ```

3. **Check file is complete:**
   - Torrent might still be downloading
   - Wait for 100% completion

---

### Issue: "High CPU usage"

**Symptoms:** qBitrr using excessive CPU

**Solutions:**

1. **Increase check interval:**
   ```toml
   [Settings]
   CheckInterval = 120  # Check every 2 minutes
   ```

2. **Reduce concurrent checks:**
   ```toml
   [Settings]
   MaxConcurrentChecks = 5
   ```

3. **Disable FFprobe temporarily:**
   ```toml
   [Settings]
   EnableFFprobe = false
   ```

---

## What's Next?

### Immediate Next Steps

1. **Enable Automated Search:**
   ```toml
   [Radarr-Movies.EntrySearch]
   SearchMissing = true
   SearchLimit = 5
   SearchByYear = true
   ```
   [Automated Search Guide →](../features/automated-search.md)

2. **Configure Health Monitoring:**
   ```toml
   [Radarr-Movies.Torrent]
   MaximumETA = 86400  # 24 hours
   StalledDelay = 15   # 15 minutes
   ReSearchStalled = true
   ```
   [Health Monitoring Guide →](../features/health-monitoring.md)

3. **Set Up Seeding Rules:**
   ```toml
   [Radarr-Movies.Torrent.SeedingMode]
   MaxUploadRatio = 2.0
   MaxSeedingTime = 604800  # 7 days
   RemoveTorrent = 3  # Either condition met
   ```
   [Seeding Configuration →](../configuration/seeding.md)

### Advanced Configuration

- ⚙️ [Complete Configuration Reference](../configuration/index.md)
- 🎯 [Quality Profiles & Custom Formats](../features/custom-formats.md)
- 🔍 [Request Integration (Overseerr/Ombi)](../features/request-integration.md)
- 💾 [Disk Space Management](../features/disk-space.md)
- 🔄 [Auto-Updates](../features/auto-updates.md)

### Explore WebUI

Access your qBitrr WebUI at http://localhost:6969/ui to:

- Monitor processes in real-time
- View logs with filtering
- Browse Arr libraries
- Edit configuration
- Check system status

[WebUI Documentation →](../webui/index.md)

---

## Getting Help

### Before Asking for Help

1. **Check logs for errors:**
   ```bash
   docker logs qbitrr | grep ERROR
   ```

2. **Verify configuration:**
   - URLs are correct
   - API keys are valid
   - Categories match exactly

3. **Search existing issues:**
   - [GitHub Issues](https://github.com/Feramance/qBitrr/issues)
   - [Discussions](https://github.com/Feramance/qBitrr/discussions)

### Where to Get Help

- 📚 [Troubleshooting Guide](../troubleshooting/index.md) - Detailed solutions
- ❓ [FAQ](../faq.md) - Common questions
- 💬 [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions) - Community support
- 🐛 [GitHub Issues](https://github.com/Feramance/qBitrr/issues) - Bug reports

### Creating a Support Request

Include:

1. **Environment:**
   ```
   qBitrr version: 5.5.5
   Installation method: Docker
   OS: Ubuntu 22.04
   qBittorrent: 4.6.0
   Radarr: 5.0.0
   ```

2. **Problem description:**
   - What you expected
   - What actually happened
   - Steps to reproduce

3. **Relevant logs:**
   ```bash
   docker logs qbitrr 2>&1 | tail -100
   ```

4. **Configuration (redact sensitive info):**
   ```toml
   [Settings.Qbittorrent]
   Host = "http://qbittorrent:8080"
   Username = "admin"
   Password = "REDACTED"
   ```

---

**Congratulations!** 🎉 You've successfully set up qBitrr. Happy automating!
