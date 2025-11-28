# Glossary

Quick reference for common terms used throughout qBitrr documentation.

---

## A

**API Key**
: Authentication token used to access *Arr applications. Found in Settings → General in each *Arr instance.

**Arr / *Arr**
: Collective term for the family of media management applications: Radarr (movies), Sonarr (TV shows), and Lidarr (music/albums).

**Auto-Update**
: qBitrr feature that automatically checks for and applies new releases from GitHub.

---

## B

**Blacklist**
: List of releases that should not be downloaded again. qBitrr automatically blacklists failed/stalled torrents in the corresponding *Arr instance.

---

## C

**Category**
: qBittorrent organizational label used to group torrents. qBitrr tracks torrents by matching *Arr instance categories.

**Custom Format (CF)**
: Radarr/Sonarr feature that allows fine-grained control over release preferences based on naming patterns, codecs, groups, etc.

**CF Score**
: Numerical score calculated by *Arr based on custom format rules. Higher scores indicate better matches to your preferences.

---

## D

**Docker Compose**
: Tool for defining and running multi-container Docker applications using YAML configuration files.

**Download Client**
: Application that handles torrent/usenet downloads. For qBitrr, this is qBittorrent.

---

## E

**ETA (Estimated Time of Arrival)**
: Predicted time until torrent download completes, calculated from current speed and remaining data.

**Event Loop**
: Continuous process that monitors torrents, checks health, and triggers imports. Each *Arr instance runs its own event loop.

---

## F

**FFprobe**
: Media file analysis tool used by qBitrr to validate downloaded files before importing to *Arr.

**Free Space Management**
: qBitrr feature that pauses torrents when disk space falls below configured thresholds.

---

## H

**Hash**
: Unique identifier for a torrent, derived from its content. Used to track individual torrents across qBittorrent and *Arr.

**Health Check**
: Process of monitoring torrent status (speed, progress, ETA) to detect stalled or failed downloads.

---

## I

**Indexer**
: Torrent or usenet search engine configured in *Arr applications. Examples: TorrentLeech, NZBgeek.

**Import Mode**
: Method used by *Arr to transfer files from download folder to media library (Copy, Move, Hardlink, etc.).

**Instant Import**
: qBitrr feature that immediately triggers *Arr import when torrent completes, instead of waiting for periodic scans.

---

## L

**Lidarr**
: Music/album management application. Monitors artists and albums, searches for releases, and integrates with download clients.

**Loop Sleep Timer**
: Delay between event loop iterations. Controls how frequently qBitrr checks torrents.

---

## M

**MaxETA**
: Maximum allowed estimated time to completion. Torrents exceeding this value are marked as failed.

**Monitored**
: *Arr status indicating content should be automatically downloaded when available.

**Multiprocessing**
: qBitrr architecture where each *Arr instance runs in a separate OS process for isolation and parallelism.

---

## O

**Ombi**
: Request management system for Plex/Emby/Jellyfin. Users can request movies/shows, which qBitrr can automatically search for.

**Overseerr**
: Modern request management system for Plex/Jellyfin/Emby with advanced features like 4K support and release date filtering.

---

## P

**Peewee**
: Python ORM (Object-Relational Mapping) library used by qBitrr for SQLite database interactions.

**Process**
: Independent execution unit. qBitrr runs each *Arr manager in a separate process.

**Profile (Quality Profile)**
: *Arr configuration defining acceptable quality levels and formats for downloads.

---

## Q

**qBittorrent**
: Open-source BitTorrent client. qBitrr monitors and manages torrents downloaded by qBittorrent.

**Quality Cutoff**
: Quality level in *Arr that, once met, stops searching for upgrades.

**Quality Upgrade**
: Replacing existing media with higher quality version when available.

---

## R

**Radarr**
: Movie management application. Monitors movies, searches for releases, and integrates with download clients.

**Re-Search**
: Triggering a new search in *Arr after marking a torrent as failed. Attempts to find alternative releases.

**RSS Sync**
: Periodic check of indexer RSS feeds for new releases matching wanted content.

---

## S

**Seed / Seeding**
: Uploading torrent data to other peers after download completes. Required by private trackers to maintain ratio.

**Seed Ratio**
: Upload/download ratio. E.g., ratio of 1.0 means you've uploaded as much as you downloaded.

**Seed Time**
: Duration a torrent has been seeding.

**Sonarr**
: TV show management application. Monitors series, searches for episodes, and integrates with download clients.

**Stalled Torrent**
: Torrent with no download progress for extended period. Usually due to lack of seeders or connectivity issues.

---

## T

**Tag**
: Label applied to content in *Arr or qBittorrent for organization and filtering.

**TOML**
: Configuration file format used by qBitrr (`config.toml`). Stands for "Tom's Obvious, Minimal Language."

**Torrent**
: File containing metadata about files to be downloaded via BitTorrent protocol.

**Tracker**
: Server that coordinates BitTorrent swarm by tracking which peers have which pieces. Public (e.g., The Pirate Bay) or private (e.g., PassThePopcorn).

---

## U

**Unmet Cutoff**
: Content that hasn't reached the configured quality cutoff. Eligible for upgrade searches.

**Usenet**
: Alternative to BitTorrent for binary file distribution. Not directly supported by qBitrr (use SABnzbd or NZBGet).

**URI**
: Uniform Resource Identifier. Web address used to access *Arr APIs (e.g., `http://localhost:7878`).

---

## W

**WebUI**
: qBitrr's web-based user interface for monitoring processes, viewing logs, and editing configuration.

**Web API**
: HTTP interface for programmatic access to qBitrr functionality.

---

## Abbreviations

| Term | Meaning |
|------|---------|
| 4K | Ultra HD resolution (3840×2160) |
| 1080p | Full HD resolution (1920×1080) |
| 720p | HD resolution (1280×720) |
| API | Application Programming Interface |
| CF | Custom Format |
| CLI | Command-Line Interface |
| DB | Database |
| ETA | Estimated Time of Arrival |
| GUI | Graphical User Interface |
| HD | High Definition |
| JSON | JavaScript Object Notation |
| NZB | Usenet file format |
| ORM | Object-Relational Mapping |
| REST | Representational State Transfer |
| RSS | Really Simple Syndication |
| SDK | Software Development Kit |
| SQLite | Embedded relational database |
| TOML | Tom's Obvious, Minimal Language |
| UHD | Ultra High Definition |
| URI | Uniform Resource Identifier |
| URL | Uniform Resource Locator |
| YAML | YAML Ain't Markup Language |

---

## Common Config Keys

| Key | Location | Purpose |
|-----|----------|---------|
| `APIKey` | `[Radarr]` / `[Sonarr]` / `[Lidarr]` | *Arr authentication |
| `Category` | `[Radarr]` / `[Sonarr]` / `[Lidarr]` | qBittorrent category to track |
| `CheckInterval` | `[Settings]` | Torrent check frequency |
| `Host` | `[Settings.Qbittorrent]` | qBittorrent server address |
| `LogLevel` | `[Settings]` | Logging verbosity |
| `Managed` | `[Radarr]` / `[Sonarr]` / `[Lidarr]` | Enable/disable *Arr instance |
| `Port` | `[Settings.Qbittorrent]` | qBittorrent server port |
| `SearchMissing` | `[Radarr.EntrySearch]` | Auto-search missing content |
| `StalledDelay` | `[Radarr.Torrent]` | Time before marking as stalled |
| `URI` | `[Radarr]` / `[Sonarr]` / `[Lidarr]` | *Arr instance URL |

---

## File Extensions

| Extension | Description |
|-----------|-------------|
| `.db` | SQLite database file |
| `.db-wal` | SQLite Write-Ahead Log |
| `.db-shm` | SQLite Shared Memory |
| `.log` | Log file (text) |
| `.torrent` | BitTorrent metafile |
| `.toml` | Configuration file (qBitrr) |
| `.mkv` | Matroska video container |
| `.mp4` | MPEG-4 video container |
| `.flac` | Free Lossless Audio Codec |

---

## Port Numbers (Defaults)

| Service | Default Port |
|---------|--------------|
| qBitrr WebUI | 6969 |
| qBittorrent | 8080 |
| Radarr | 7878 |
| Sonarr | 8989 |
| Lidarr | 8686 |
| Overseerr | 5055 |
| Ombi | 3579 |
| Plex | 32400 |
| Jellyfin | 8096 |

---

## See Also

- [Configuration Reference](../configuration/config-file.md) - Detailed config key explanations
- [CLI Reference](cli.md) - Command-line options
- [API Documentation](api.md) - REST API endpoints
- [FAQ](../faq.md) - Frequently asked questions
