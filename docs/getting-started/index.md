# Getting Started with qBitrr

Welcome! This comprehensive guide will help you install and configure qBitrr for the first time.

---

## What is qBitrr?

qBitrr is an intelligent automation tool that bridges qBittorrent and the Arr ecosystem (Radarr/Sonarr/Lidarr). It provides:

- **Intelligent Health Monitoring** - Automatically detect and handle failed/stalled downloads
- **Instant Imports** - Import media to your library as soon as downloads complete
- **Automated Search** - Continuously search for missing media and quality upgrades
- **Request Integration** - Process Overseerr/Ombi requests automatically
- **Custom Format Enforcement** - Ensure downloads meet your quality standards
- **Seeding Management** - Per-tracker seeding rules and automatic cleanup
- **Web Interface** - Modern React UI for monitoring and configuration

---

## Prerequisites

### Required Components

Before installing qBitrr, ensure you have these components running:

#### 1. qBittorrent

- **Version:** 4.1.0+ or 5.x
- **WebUI:** Must be enabled (Settings → Web UI)
- **Authentication:** Note your username and password
- **Network:** Accessible from where qBitrr will run

**Verify qBittorrent:**

```bash
# Test WebUI access
curl http://localhost:8080
# Should return login page
```

#### 2. At Least One Arr Instance

Install and configure at least one of:

- **Radarr** (v3.0+) - Movie management
- **Sonarr** (v3.0+) - TV show management
- **Lidarr** (v1.0+) - Music management

**Requirements for each Arr instance:**

- ✅ Configured indexers (Prowlarr or direct)
- ✅ Download client pointing to qBittorrent
- ✅ Category set in download client (e.g., `radarr-movies`)
- ✅ API key available (Settings → General → Security)

**Verify Arr instance:**

```bash
# Test Radarr API
curl -H "X-Api-Key: YOUR_API_KEY" http://localhost:7878/api/v3/system/status
# Should return JSON with version info
```

#### 3. Storage & Permissions

- **Download folder:** Accessible by qBittorrent, Arr instances, and qBitrr
- **Config folder:** Write permissions for qBitrr
- **Logs folder:** Write permissions for qBitrr

### Optional Components

#### Overseerr or Ombi

For automated request processing:

- **Overseerr** (v1.26+) - Modern request management
- **Ombi** (v4.0+) - Alternative request management

#### FFprobe

For media file validation:

- Automatically downloaded by qBitrr (recommended)
- Or manually installed (`apt install ffmpeg`)

---

## Installation Methods

Choose the installation method that best fits your infrastructure:

### 🐳 Docker (Recommended)

**Best for:**

- Most users
- Easy updates
- Isolated environment
- Cross-platform support

**Advantages:**

- ✅ Pre-configured environment
- ✅ Automatic dependency management
- ✅ Easy rollback and updates
- ✅ Consistent across all platforms

**Requirements:**

- Docker 20.10+
- Docker Compose 2.0+ (optional but recommended)

[**Docker Installation Guide →**](installation/docker.md)

---

### 📦 pip (Python Package)

**Best for:**

- Python developers
- Native Linux/macOS installations
- Custom Python environments
- Integration with existing Python tools

**Advantages:**

- ✅ Native performance
- ✅ Easy integration with Python ecosystem
- ✅ Full control over environment

**Requirements:**

- Python 3.11+
- pip 20.0+
- virtualenv (recommended)

[**pip Installation Guide →**](installation/pip.md)

---

### 🔧 Systemd Service

**Best for:**

- Linux servers
- Production deployments
- Automatic startup on boot
- Native system integration

**Advantages:**

- ✅ Native Linux service
- ✅ Automatic restart on failure
- ✅ Logging via journalctl
- ✅ Resource limits and sandboxing

**Requirements:**

- Linux with systemd
- Python 3.11+ or qBitrr binary
- sudo/root access for setup

[**Systemd Installation Guide →**](installation/systemd.md)

---

### 📥 Binary (Standalone)

**Best for:**

- Advanced users
- Minimal dependencies
- Portable installations
- Testing without Python

**Advantages:**

- ✅ No Python required
- ✅ Portable executable
- ✅ Quick testing

**Platforms:**

- Linux (x86_64, aarch64)
- macOS (Intel, Apple Silicon)
- Windows (x86_64)

[**Binary Installation Guide →**](installation/binary.md)

---

## Installation Comparison

| Feature | Docker | pip | Systemd | Binary |
|---------|--------|-----|---------|--------|
| **Ease of Setup** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Updates** | Very Easy | Easy | Manual | Manual |
| **Dependencies** | Auto | Manual | Manual | None |
| **Cross-Platform** | Yes | Yes | Linux only | Yes |
| **Performance** | Good | Excellent | Excellent | Excellent |
| **Isolation** | Excellent | None | Good | None |
| **Auto-Start** | Yes | No | Yes | No |
| **Resource Usage** | Medium | Low | Low | Low |

---

## Quick Start

Once you've chosen and completed your installation method:

### Step 1: First Run

Start qBitrr to generate the default configuration:

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
    journalctl -u qbitrr -f
    ```

=== "Binary"

    ```bash
    ./qbitrr
    ```

**Look for:**

```
Configuration file not found. Generating default config...
Configuration file created at: /config/config.toml
Please edit the configuration file and restart qBitrr.
```

### Step 2: Stop qBitrr

Stop qBitrr to edit the configuration:

=== "Docker"

    ```bash
    docker-compose down
    ```

=== "pip/Binary"

    Press ++ctrl+c++

=== "Systemd"

    ```bash
    sudo systemctl stop qbitrr
    ```

### Step 3: Configure qBitrr

Edit the generated `config.toml` file:

=== "Docker"

    ```bash
    # Config is in your mounted volume
    nano /path/to/config/config.toml
    ```

=== "pip"

    ```bash
    nano ~/config/config.toml
    ```

=== "Systemd"

    ```bash
    sudo nano /home/qbitrr/config/config.toml
    ```

**Minimum required configuration:**

```toml
[qBit]
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "adminpass"

[Radarr-Movies]
URI = "http://localhost:7878"
APIKey = "your_radarr_api_key_here"
Category = "radarr-movies"
```

[**Detailed Configuration Guide →**](first-run.md)

### Step 4: Start qBitrr

Restart qBitrr with your configuration:

=== "Docker"

    ```bash
    docker-compose up -d
    ```

=== "pip"

    ```bash
    qbitrr
    ```

=== "Systemd"

    ```bash
    sudo systemctl start qbitrr
    sudo systemctl enable qbitrr  # Enable auto-start
    ```

### Step 5: Verify Installation

1. **Check logs for successful connections:**

    ```
    Successfully connected to qBittorrent
    Successfully connected to Radarr-Movies
    WebUI started on http://0.0.0.0:6969
    ```

2. **Access the WebUI:**

    Open http://localhost:6969/ui in your browser

3. **Verify Processes tab:**

    All Arr manager processes should show as "Running"

---

## First Steps After Installation

### 1. Test with a Manual Download

1. In Radarr/Sonarr, manually search and grab a small file
2. Watch qBitrr logs for activity
3. Verify qBitrr detects and monitors the download
4. Check that import triggers when complete

### 2. Enable Automated Search (Optional)

If you want qBitrr to search for missing media:

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
SearchLimit = 5
SearchByYear = true
SearchRequestsEvery = 300
```

[**Automated Search Guide →**](../features/automated-search.md)

### 3. Configure Health Monitoring

Customize how qBitrr handles failed downloads:

```toml
[Radarr-Movies.Torrent]
MaximumETA = 86400  # 24 hours
StalledDelay = 15  # 15 minutes
ReSearchStalled = true
```

[**Health Monitoring Guide →**](../features/health-monitoring.md)

### 4. Set Up Request Integration (Optional)

If using Overseerr or Ombi:

```toml
[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "your_overseerr_api_key"
ApprovedOnly = true
```

[**Request Integration Guide →**](../features/request-integration.md)

---

## Common Initial Setup Scenarios

### Scenario 1: Simple Home Server

**Setup:**
- Single Radarr instance
- Single Sonarr instance
- Basic health monitoring
- No request management

**Installation:** Docker via docker-compose

**Time to setup:** 15 minutes

[**Example Configuration →**](quickstart.md#simple-home-server)

---

### Scenario 2: Advanced Multi-Instance

**Setup:**
- Radarr 1080p + Radarr 4K
- Sonarr TV + Sonarr Anime
- Overseerr integration
- Custom format enforcement

**Installation:** Systemd service

**Time to setup:** 45 minutes

[**Example Configuration →**](quickstart.md#advanced-multi-instance)

---

### Scenario 3: Shared Seedbox

**Setup:**
- Remote qBittorrent
- Multiple users/Arr instances
- Strict seeding requirements
- Disk space management

**Installation:** pip + systemd

**Time to setup:** 30 minutes

[**Example Configuration →**](quickstart.md#shared-seedbox)

---

## Learning Path

### Beginner (Week 1)

1. ✅ Install qBitrr
2. ✅ Configure basic connectivity
3. ✅ Test with manual downloads
4. ✅ Explore WebUI

**Resources:**

- [First Run Guide](first-run.md)
- [qBittorrent Configuration](../configuration/qbittorrent.md)
- [WebUI Overview](../webui/index.md)

### Intermediate (Week 2-3)

1. ✅ Enable automated search
2. ✅ Configure health monitoring
3. ✅ Set up seeding rules
4. ✅ Add request integration

**Resources:**

- [Automated Search](../features/automated-search.md)
- [Health Monitoring](../features/health-monitoring.md)
- [Seeding Configuration](../configuration/seeding.md)
- [Request Integration](../features/request-integration.md)

### Advanced (Week 4+)

1. ✅ Custom format enforcement
2. ✅ Quality upgrades
3. ✅ Multi-instance setups
4. ✅ Per-tracker rules

**Resources:**

- [Custom Formats](../features/custom-formats.md)
- [Quality Upgrades](../features/quality-upgrades.md)
- [Advanced Topics](../advanced/index.md)

---

## Troubleshooting Installation

### qBitrr Won't Start

**Check:**

1. Python version (3.11+ required for pip/systemd)
2. Port 6969 not in use
3. Config file exists and is valid TOML
4. Permissions on config/logs folders

[**Troubleshooting Guide →**](../troubleshooting/index.md)

### Can't Connect to qBittorrent

**Solutions:**

1. Verify qBittorrent WebUI is enabled
2. Check host/port in config
3. Test credentials manually
4. Ensure no firewall blocking

[**qBittorrent Issues →**](../troubleshooting/common-issues.md#qbittorrent-connection)

### Can't Connect to Arr

**Solutions:**

1. Verify API key is correct
2. Check Arr instance is running
3. Test API manually with curl
4. Ensure network connectivity

[**Arr Connection Issues →**](../troubleshooting/common-issues.md#arr-connection)

---

## Next Steps

Choose your path based on your needs:

### 🎯 Quick Setup

Just want it working fast?

1. [Quick Start Guide](quickstart.md)
2. [First Run Configuration](first-run.md)
3. Test with downloads

**Time required:** 20 minutes

### 🔧 Comprehensive Setup

Want to understand everything?

1. [Installation Guide](installation/index.md)
2. [Configuration Overview](../configuration/index.md)
3. [Arr Configuration](../configuration/arr/index.md)
4. [Feature Guides](../features/index.md)

**Time required:** 2-3 hours

### 🚀 Advanced Configuration

Need complex features?

1. [Advanced Topics](../advanced/index.md)
2. [Custom Formats](../features/custom-formats.md)
3. [Quality Upgrades](../features/quality-upgrades.md)
4. [Multi-Instance Setup](../configuration/arr/index.md#multiple-instances)

**Time required:** 4-6 hours

---

## Getting Help

### Documentation

- [FAQ](../faq.md) - Frequently asked questions
- [Troubleshooting](../troubleshooting/index.md) - Common issues and solutions
- [Configuration Reference](../configuration/config-file.md) - Complete config documentation
- [API Reference](../reference/api.md) - REST API documentation

### Community

- **GitHub Discussions** - [Ask questions, share setups](https://github.com/Feramance/qBitrr/discussions)
- **GitHub Issues** - [Report bugs, request features](https://github.com/Feramance/qBitrr/issues)
- **Discord** - Real-time community support

### Contributing

Want to improve qBitrr?

- [Development Guide](../development/index.md)
- [AGENTS.md](https://github.com/Feramance/qBitrr/blob/master/AGENTS.md)

---

## Success Stories

!!! success "Migration from Manual Management"
    "Switching from manual torrent management to qBitrr saved me 2-3 hours per week. Failed downloads are handled automatically, and new episodes import within seconds!" - *Home media server user*

!!! success "Multi-Instance 4K Setup"
    "Running separate 1080p and 4K Radarr instances with qBitrr's custom format enforcement ensures I only grab the quality I want. Upgrade searches keep my library pristine." - *Quality enthusiast*

!!! success "Shared Seedbox"
    "qBitrr manages our family seedbox with per-tracker seeding rules. Everyone's Arr instances work independently, and we maintain great ratios on private trackers." - *Seedbox user*

---

Ready to get started? Pick your installation method above and follow the guide!
