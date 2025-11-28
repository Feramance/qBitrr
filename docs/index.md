# Welcome to qBitrr Documentation

<div style="text-align: center; margin: 2rem 0;">
  <img src="assets/logov2-clean.svg" alt="qBitrr Logo" width="200"/>
</div>

**qBitrr** is the intelligent glue between qBittorrent and the *Arr ecosystem (Radarr, Sonarr, Lidarr). It monitors torrent health, triggers instant imports when downloads complete, automates quality upgrades, manages disk space, integrates with request systems (Overseerr/Ombi), and provides a modern React dashboard for complete visibility and control.

[![PyPI](https://img.shields.io/pypi/v/qBitrr2?label=PyPI)](https://pypi.org/project/qBitrr2/)
[![Downloads](https://img.shields.io/pypi/dm/qBitrr2)](https://pypi.org/project/qBitrr2/)
[![Docker Pulls](https://img.shields.io/docker/pulls/feramance/qbitrr.svg)](https://hub.docker.com/r/feramance/qbitrr)
[![License: MIT](https://img.shields.io/pypi/l/qbitrr)](https://github.com/Feramance/qBitrr/blob/master/LICENSE)

## Quick Links

<div class="feature-grid">
  <div class="feature-card">
    <h3>🚀 Getting Started</h3>
    <p>Install qBitrr and get your first torrent monitored in minutes.</p>
    <a href="getting-started/index.md">Get Started →</a>
  </div>

  <div class="feature-card">
    <h3>⚙️ Configuration</h3>
    <p>Configure qBittorrent, Arr instances, and fine-tune your automation.</p>
    <a href="configuration/index.md">Configure →</a>
  </div>

  <div class="feature-card">
    <h3>✨ Features</h3>
    <p>Explore health monitoring, automated search, quality upgrades, and more.</p>
    <a href="features/index.md">Explore Features →</a>
  </div>

  <div class="feature-card">
    <h3>🔧 Troubleshooting</h3>
    <p>Resolve common issues and optimize your qBitrr installation.</p>
    <a href="troubleshooting/index.md">Troubleshoot →</a>
  </div>
</div>

## Core Features

### 🚑 Torrent Health & Import Management
- **Instant imports** – trigger downloads scans the moment torrents finish
- **Stalled torrent detection** – identify and handle stuck/slow downloads
- **Failed download handling** – automatically blacklist and re-search
- **FFprobe verification** – validate media files before import
- **Smart file filtering** – exclude samples, extras, trailers

### 🔍 Automated Search & Request Integration
- **Missing media search** – automatically search for missing content
- **Quality upgrade search** – find better releases for existing media
- **Custom format scoring** – search based on custom format requirements
- **Overseerr/Ombi integration** – prioritize user requests
- **Temporary quality profiles** – use lower profiles, upgrade later

### 📊 Quality & Metadata Management
- **RSS sync automation** – schedule periodic RSS feed refreshes
- **Queue management** – keep Arr instances in sync
- **Custom format enforcement** – remove torrents not meeting CF scores
- **Quality profile switching** – dynamic profile changes per search type
- **Interactive profile configuration** – test connections from WebUI

### 🌱 Seeding & Tracker Control
- **Per-tracker settings** – configure MaxETA, ratios, seeding time
- **Global seeding limits** – upload/download rate limits
- **Automatic removal** – remove torrents by ratio or time
- **Dead tracker cleanup** – auto-remove failed trackers
- **Tag management** – auto-tag torrents by tracker

### 💾 Disk Space & Resource Management
- **Free space monitoring** – pause torrents when space is low
- **Auto pause/resume** – manage activity based on disk availability
- **Configurable thresholds** – set limits in KB, MB, GB, or TB

### 🔄 Auto-Updates & Self-Healing
- **Scheduled auto-updates** – update on a cron schedule
- **Manual update trigger** – one-click updates from WebUI
- **Installation-aware** – detects git/pip/binary installs
- **Process auto-restart** – restart crashed processes automatically
- **Crash loop protection** – prevent infinite restart loops

### 💻 First-Party Web UI
- **Live process monitoring** – see all running Arr managers
- **Log viewer** – tail logs in real-time
- **Arr insights** – view movies, series, albums with filtering
- **Config editor** – edit configuration from the UI
- **Dark/light theme** – customizable appearance

## Installation

=== "Docker"

    ```bash
    docker run -d \
      --name qbitrr \
      -p 6969:6969 \
      -v /path/to/config:/config \
      feramance/qbitrr:latest
    ```

=== "Docker Compose"

    ```yaml
    services:
      qbitrr:
        image: feramance/qbitrr:latest
        container_name: qbitrr
        ports:
          - "6969:6969"
        volumes:
          - /path/to/config:/config
        restart: unless-stopped
    ```

=== "pip"

    ```bash
    pip install qBitrr2
    qbitrr
    ```

[View detailed installation instructions →](getting-started/installation/index.md)

## System Requirements

- Python 3.11 or higher (for pip/source installs)
- qBittorrent 4.x or 5.x
- At least one Arr instance (Radarr, Sonarr, or Lidarr)
- 512 MB RAM minimum (1 GB recommended)
- 100 MB disk space for application + logs

## Support

- **Documentation**: You're reading it!
- **Issues**: [GitHub Issues](https://github.com/Feramance/qBitrr/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions)
- **Support the Project**:
  - [Patreon](https://patreon.com/qBitrr)
  - [PayPal](https://www.paypal.me/feramance)

## License

qBitrr is licensed under the [MIT License](https://github.com/Feramance/qBitrr/blob/master/LICENSE).
