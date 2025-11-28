# Getting Started with qBitrr

Welcome! This guide will help you install and configure qBitrr for the first time.

## What You'll Need

Before you begin, make sure you have:

- ✅ **qBittorrent** (v4.x or v5.x) installed and running
- ✅ **At least one Arr instance** (Radarr, Sonarr, or Lidarr) configured
- ✅ **API keys** for your Arr instances
- ✅ **qBittorrent credentials** (if authentication is enabled)
- ✅ (Optional) **Overseerr or Ombi** for request integration

## Installation Methods

Choose the installation method that best fits your setup:

### 🐳 Docker (Recommended)
Perfect for most users. Easy to update, isolated environment, works everywhere.

[Docker Installation Guide →](installation/docker.md)

### 📦 pip (Python Package)
Ideal if you're already using Python for other tools or prefer native installs.

[pip Installation Guide →](installation/pip.md)

### 🔧 Systemd Service
Run qBitrr as a native Linux service with automatic startup.

[Systemd Installation Guide →](installation/systemd.md)

### 📥 Binary (Standalone)
Pre-built executables for Linux, macOS, and Windows (advanced users).

[Binary Installation Guide →](installation/binary.md)

## Quick Start

Once installed, follow these steps:

1. **Generate configuration file** – qBitrr creates `config.toml` on first run
2. **Configure qBittorrent connection** – add host, port, username, password
3. **Configure Arr instances** – add at least one Radarr/Sonarr/Lidarr
4. **Start qBitrr** – the application will begin monitoring torrents
5. **Access WebUI** – navigate to `http://localhost:6969/ui`

[Detailed Quick Start Guide →](quickstart.md)

## What's Next?

After installation:

- ⚙️ [Configure qBittorrent settings](../configuration/qbittorrent.md)
- 📺 [Set up Arr instances](../configuration/arr/index.md)
- 🔍 [Enable automated search](../features/automated-search.md)
- 🌐 [Configure the WebUI](../configuration/webui.md)

## Need Help?

- [FAQ](../faq.md)
- [Troubleshooting Guide](../troubleshooting/index.md)
- [Common Issues](../troubleshooting/common-issues.md)
