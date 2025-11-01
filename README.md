# qBitrr

[![PyPI](https://img.shields.io/pypi/v/qBitrr2?label=PyPI)](https://pypi.org/project/qBitrr2/)
[![Downloads](https://img.shields.io/pypi/dm/qBitrr2)](https://pypi.org/project/qBitrr2/)
[![Docker Pulls](https://img.shields.io/docker/pulls/feramance/qbitrr.svg)](https://hub.docker.com/r/feramance/qbitrr)
[![CodeQL](https://github.com/Feramance/qBitrr/actions/workflows/codeql.yml/badge.svg?branch=master)](https://github.com/Feramance/qBitrr/actions/workflows/codeql.yml)
[![Nightly Build](https://github.com/Feramance/qBitrr/actions/workflows/nightly.yml/badge.svg?branch=master)](https://github.com/Feramance/qBitrr/actions/workflows/nightly.yml)
[![pre-commit.ci](https://results.pre-commit.ci/badge/github/Feramance/qBitrr/master.svg)](https://results.pre-commit.ci/latest/github/Feramance/qBitrr/master)
[![License: MIT](https://img.shields.io/pypi/l/qbitrr)](LICENSE)

> 🧩 qBitrr keeps qBittorrent, Radarr, Sonarr, Lidarr, and your request tools chatting happily so downloads finish, import, and clean up without babysitting.

## 📚 What's Inside
- [Overview](#-overview)
- [Highlights](#-highlights)
- [State of the Project](#-state-of-the-project)
- [Quickstart](#-quickstart)
  - [Install with pip](#install-with-pip)
  - [Run with Docker](#run-with-docker)
- [Configuration](#-configuration)
- [Built-in Web UI](#-built-in-web-ui)
- [Day-to-day Ops](#-day-to-day-ops)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [Support](#-support)
- [License](#-license)

## 🧠 Overview
qBitrr is the glue that keeps the *Arr ecosystem tidy. It watches qBittorrent for stalled jobs, kicks Radarr/Sonarr/Lidarr when something finishes, prunes your completed folder, and even offers a slick React dashboard so you can see what's running at a glance.

## ✨ Highlights
- 🚑 **Health checks** – spot stalled or broken torrents, blacklist them on the relevant Arr, and optionally trigger a re-search.
- 📬 **Instant imports** – call `DownloadedMoviesScan` and `DownloadedEpisodesScan` the moment qBittorrent is done.
- 🧹 **Smart skips & cleanup** – ignore by extension, folder, or regex and keep completed downloads tidy.
- 🔍 **ffprobe verification** – confirm files are real media before handing them off.
- 🔄 **Arr keep-alive** – schedule RSS refreshes, queue updates, missing-media searches, CF-score rescans, and more.
- 🛰️ **Request automation** – pull in Overseerr/Ombi asks and auto-manage trackers.
- 💾 **Disk guard rails** – pause torrenting when free space dips under your threshold.
- 💻 **First-party Web UI** – live process monitoring, log tails, Arr insights, and config edits in one place.

## 📌 State of the Project
The long-term plan is still to ship a C# rewrite, but the Python edition isn't going anywhere—it gets regular fixes and features, and the Web UI is now production-ready. Ideas and PRs are welcome! Head over to the [issue templates](.github/ISSUE_TEMPLATE) or the [PR checklist](.github/pull_request_template.md) to get started.

## ⚡ Quickstart
qBitrr supports Python 3.12+ on Linux, macOS, and Windows. Run it natively or in Docker—whatever fits your stack.

### Install with pip
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install qBitrr2

# First run creates ~/config/config.toml
qBitrr2
```

Update later with:
```bash
python -m pip install --upgrade qBitrr2
```

### Run with Docker
Minimal setup:
```bash
docker run -d \
  --name qbitrr \
  --tty \
  -e TZ=Europe/London \
  -p 6969:6969 \
  -v /etc/localtime:/etc/localtime:ro \
  -v /path/to/appdata/qbitrr:/config \
  -v /path/to/completed/downloads:/completed_downloads:rw \
  --restart unless-stopped \
  feramance/qbitrr:latest
```

The container automatically binds its WebUI to `0.0.0.0`; exposing `6969` makes the dashboard reachable at `http://<host>:6969/ui`.

Compose example with a little more structure:
```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    user: 1000:1000
    restart: unless-stopped
    tty: true
    environment:
      TZ: Europe/London
    ports:
      - "6969:6969"
    volumes:
      - /etc/localtime:/etc/localtime:ro
      - /path/to/appdata/qbitrr:/config
      - /path/to/completed/downloads:/completed_downloads:rw
    logging:
      driver: json-file
      options:
        max-size: 50m
        max-file: "3"
    depends_on:
      - qbittorrent
      - radarr-1080p
      - sonarr-1080p
```

> ℹ️ On first boot the container writes `config.toml` under `/config`. Update the values to match your mounts and restart the container.

## 🛠️ Configuration
- Default config path: `~/config/config.toml` (native) or `/config/config.toml` (Docker).
- Tag new downloads in Radarr/Sonarr/Lidarr so qBitrr can map them correctly.
- qBittorrent 5.x works via a config flag (will become default later). The latest validated build is **4.6.7**.
- Turn on logging (`Settings.Logging = true`) when you need support—logs land in `~/logs/` or `/config/logs`.

See `config.example.toml` for every knob and dial.

## 🖥️ Built-in Web UI
The React + Vite dashboard listens on `http://<host>:6969/ui` by default.

- 🔐 **Authentication** – set `Settings.WebUIToken` to protect `/api/*`. The UI itself uses the `/web/*` helpers.
- 🗂️ **Tabs** – Processes, Logs, Radarr, Sonarr, Lidarr, and Config—all live data, all actionable.
- 🧪 **Developing the UI** – the source lives in `webui/`. Run `npm ci && npm run dev` to hack locally, and `npm run build` (or `make syncenv`) before committing so the bundled assets stay current.

## 🔁 Day-to-day Ops
- ♻️ Rebuild Arr metadata via "Rebuild Arrs" in the UI or `POST /api/arr/rebuild`.
- 🔁 Restart individual loops or slam the "Restart All" button when something is stuck.
- 📬 Overseerr/Ombi integration pulls new requests automatically once configured.
- 🗃️ Logs roll into `~/logs/` (think `Main.log`, `WebUI.log`, etc.)—view them in the UI or right off disk.

## 🆘 Troubleshooting
1. Enable file logging, reproduce the issue, and grab the relevant snippets (scrub secrets).
2. Open the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml). Include:
   - qBitrr version (`qBitrr2 --version` or Docker tag)
   - OS / deployment details
   - qBittorrent + Arr versions (and request tools if used)
   - Reproduction steps and what you expected to happen
3. For feature ideas, hop over to the [feature request template](.github/ISSUE_TEMPLATE/feature_request.yml).

## 🤝 Contributing
We'd love your help! Before opening a PR:
- Read the [pull request template](.github/pull_request_template.md).
- Run `make lint` or `pre-commit run --all-files` for Python changes; `npm run lint` for UI code.
- Add or update tests when behaviour changes.
- Mention docs or release notes updates if users should know about the change.

Unsure whether an idea fits? File a feature request first and we'll chat.

## ❤️ Support
- ⭐ Star the repo to spread the word.
- 🐛 Report issues with logs attached so we can fix them faster.
- 🛠️ Contribute code, docs, translations—whatever you enjoy.
- ☕ Sponsor development:
  - [Patreon](https://patreon.com/qBitrr)
  - [PayPal](https://www.paypal.me/feramance)

Every bit of support keeps qBitrr humming—thanks for being here!

## 📄 License
qBitrr is released under the [MIT License](LICENSE).
