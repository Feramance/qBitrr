# <img src="assets/logov2-clean.png" alt="qBitrr Logo" width="40" style="vertical-align: middle;"/> qBitrr

[![PyPI](https://img.shields.io/pypi/v/qBitrr2?label=PyPI)](https://pypi.org/project/qBitrr2/)
[![Downloads](https://img.shields.io/pypi/dm/qBitrr2)](https://pypi.org/project/qBitrr2/)
[![Docker Pulls](https://img.shields.io/docker/pulls/feramance/qbitrr.svg)](https://hub.docker.com/r/feramance/qbitrr)
[![CodeQL](https://github.com/Feramance/qBitrr/actions/workflows/codeql.yml/badge.svg?branch=master)](https://github.com/Feramance/qBitrr/actions/workflows/codeql.yml)
[![Nightly Build](https://github.com/Feramance/qBitrr/actions/workflows/nightly.yml/badge.svg?branch=master)](https://github.com/Feramance/qBitrr/actions/workflows/nightly.yml)
[![pre-commit.ci](https://results.pre-commit.ci/badge/github/Feramance/qBitrr/master.svg)](https://results.pre-commit.ci/latest/github/Feramance/qBitrr/master)
[![License: MIT](https://img.shields.io/pypi/l/qbitrr)](LICENSE)

> 🧩 The intelligent glue between qBittorrent and the *Arr ecosystem (Radarr, Sonarr, Lidarr). Monitors torrent health, triggers instant imports, automates quality upgrades, manages disk space, integrates with request systems (Overseerr/Ombi), and provides a modern React dashboard for complete visibility and control.

## 📚 Documentation

**Full documentation is available at: https://feramance.github.io/qBitrr/**

- [Getting Started](https://feramance.github.io/qBitrr/getting-started/) – Installation guides for pip, Docker, and native setups
- [Configuration](https://feramance.github.io/qBitrr/configuration/) – qBittorrent, Arr instances, quality profiles, and more
- [Features](https://feramance.github.io/qBitrr/features/) – Health monitoring, automated search, quality management, disk space, auto-updates
- [WebUI](https://feramance.github.io/qBitrr/webui/) – Built-in React dashboard with live monitoring and config editor
- [Troubleshooting](https://feramance.github.io/qBitrr/troubleshooting/) – Common issues and debug logging
- [API Reference](https://feramance.github.io/qBitrr/webui/api/) – REST API documentation

## ⚡ Quick Start

### 🐍 Install with pip
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install qBitrr2

# First run creates config (Docker: /config/config.toml; native: .config/config.toml in current directory, or set QBITRR_OVERRIDES_DATA_PATH)
qbitrr
```

### 🐳 Run with Docker
```bash
docker run -d \
  --name qbitrr \
  --tty \
  -e TZ=Europe/London \
  -p 6969:6969 \
  -v /path/to/appdata/qbitrr:/config \
  -v /path/to/completed/downloads:/completed_downloads:rw \
  --restart unless-stopped \
  feramance/qbitrr:latest
```

**Docker Compose:**
```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    restart: unless-stopped
    tty: true
    environment:
      TZ: Europe/London
    ports:
      - "6969:6969"
    volumes:
      - /path/to/appdata/qbitrr:/config
      - /path/to/completed/downloads:/completed_downloads:rw
```

Access the WebUI at `http://<host>:6969/ui` after startup.

## ✨ Key Features

- **🚀 Multi-qBittorrent Support (v5.7.x+)** – Manage torrents across multiple qBittorrent instances for load balancing, redundancy, and VPN isolation
- **🚑 Torrent Health Monitoring** – Detect stalled/failed downloads, auto-blacklist, trigger re-searches
- **🔍 Automated Search** – Missing media, quality upgrades, custom format scoring
- **🎯 Request Integration** – Pull requests from Overseerr/Ombi, prioritize user-requested media
- **📊 Quality Management** – RSS sync, queue refresh, profile switching, custom format enforcement
- **🌱 Seeding Control** – Per-tracker settings, ratio/time limits, tracker injection
- **🛡️ Hit and Run Protection** – Automatic HnR obligation tracking with configurable thresholds, partial download handling, and dead tracker bypass
- **💾 Disk Space Management** – Auto-pause when low on space, configurable thresholds
- **🔄 Auto-Updates** – GitHub release-based updates with scheduled cron support
- **💻 Modern WebUI** – Live process monitoring, log viewer, Arr insights, config editor

## 🛠️ Essential Configuration

1. **Configure qBittorrent** in your config file (Docker: `/config/config.toml`; native: `.config/config.toml` in the current directory, or path set by `QBITRR_OVERRIDES_DATA_PATH`):
   ```toml
   [qBit]
   Host = "localhost"
   Port = 8080
   UserName = "admin"
   Password = "adminpass"
   ```

2. **Add Arr instances**:
   ```toml
   [Radarr-Movies]
   URI = "http://localhost:7878"
   APIKey = "your-radarr-api-key"
   Category = "radarr-movies"
   ```

3. **Set completed folder**:
   ```toml
   [Settings]
   CompletedDownloadFolder = "/path/to/completed"
   ```

### 🆕 Multi-qBittorrent (v5.7.x+)

Manage torrents across multiple qBittorrent instances:

```toml
[qBit]  # Default instance (required)
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "password"

[qBit-seedbox]  # Additional instance (optional)
Host = "192.168.1.100"
Port = 8080
UserName = "admin"
Password = "seedboxpass"
```

See [qBittorrent configuration](docs/configuration/qbittorrent.md) (multi-instance section) for complete documentation.

---

See [Configuration Guide](https://feramance.github.io/qBitrr/configuration/) and [config.example.toml](config.example.toml) for all available options.

## 📖 Resources

- **Documentation:** https://feramance.github.io/qBitrr/
- **PyPI Package:** https://pypi.org/project/qBitrr2/
- **Docker Hub:** https://hub.docker.com/r/feramance/qbitrr
- **Example Config:** [config.example.toml](config.example.toml)
- **API Documentation:** [docs/webui/api.md](docs/webui/api.md)
- **Systemd Setup:** [docs/getting-started/installation/systemd.md](docs/getting-started/installation/systemd.md)

## 🐛 Issues & Support

- **Report Bugs:** [Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.yml)
- **Request Features:** [Feature Request Template](.github/ISSUE_TEMPLATE/feature_request.yml)
- **Discussions:** [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions)
- **Troubleshooting:** [Common Issues](https://feramance.github.io/qBitrr/troubleshooting/)

## 🤝 Contributing

Contributions welcome! See [docs/development/contributing.md](docs/development/contributing.md) for coding guidelines and development setup.

**Development setup:**
```bash
# Python backend
make newenv && make syncenv
make reformat  # Format and lint

# WebUI
cd webui && npm ci
npm run dev    # Dev server at localhost:5173
```

## ❤️ Support

If qBitrr saves you time and headaches:
- ⭐ **Star the repo** – helps others discover qBitrr
- 💰 **Sponsor:** [Patreon](https://patreon.com/qBitrr) | [PayPal](https://www.paypal.me/feramance)

## 📄 License

Released under the [MIT License](LICENSE). Use it, modify it, share it—commercially or personally.

---

<div align="center">

**Made with ❤️ by the qBitrr community**

[Documentation](https://feramance.github.io/qBitrr/) • [PyPI](https://pypi.org/project/qBitrr2/) • [Docker](https://hub.docker.com/r/feramance/qbitrr) • [GitHub](https://github.com/Feramance/qBitrr)

</div>

## Star History

<a href="https://www.star-history.com/#Feramance/qBitrr&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Feramance/qBitrr&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Feramance/qBitrr&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Feramance/qBitrr&type=date&legend=top-left" />
 </picture>
</a>
