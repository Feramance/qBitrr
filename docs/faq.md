# Frequently Asked Questions

## General Questions

### What is qBitrr?

qBitrr is an automation tool that bridges qBittorrent with Radarr, Sonarr, and Lidarr. It monitors torrent health, triggers instant imports, automates searches, manages quality upgrades, and provides a modern web interface for complete control.

### Why do I need qBitrr?

qBitrr solves several common problems:

- **Slow imports**: Arr instances only scan for completed downloads every 1-15 minutes. qBitrr triggers imports instantly.
- **Stalled torrents**: qBitrr detects and handles stuck downloads automatically.
- **Manual quality upgrades**: qBitrr can search for better releases automatically.
- **Request management**: Integrates with Overseerr/Ombi to prioritize user requests.
- **Disk space issues**: Automatically pauses torrents when disk space is low.

### Is qBitrr compatible with my setup?

qBitrr works with:

- **qBittorrent**: v4.x and v5.x
- **Radarr**: v3.x and v4.x
- **Sonarr**: v3.x and v4.x
- **Lidarr**: v1.x
- **Python**: 3.11 or higher
- **Platforms**: Linux, macOS, Windows, Docker

## Installation Questions

### Which installation method should I use?

- **Docker**: Best for most users. Easy updates, isolated environment.
- **pip**: Good if you're already using Python or prefer native installs.
- **Systemd**: Ideal for running as a Linux service.
- **Binary**: Pre-built executables for advanced users.

[Installation guides →](getting-started/installation/index.md)

### Can I run multiple instances of qBitrr?

Yes, but each instance needs:

- Its own config directory
- Different port for WebUI (default: 6969)
- Different Arr instances or categories to monitor

## Configuration Questions

### Why aren't my torrents being monitored?

Check these common issues:

1. **Categories don't match**: Your Arr download client category must match `Settings.CategoryRadarr` (or Sonarr/Lidarr) in config.toml
2. **Missing tags**: Arr downloads need tags configured
3. **qBittorrent not connected**: Check connection settings in config
4. **Wrong version setting**: Set `Settings.Qbittorrent.Version5 = true` for qBit 5.x

### How do I find my Arr API key?

In Radarr/Sonarr/Lidarr:

1. Go to Settings → General
2. Scroll to "Security" section
3. Copy the "API Key" value

### What categories should I use?

Default recommendations:

- `radarr-movies` for Radarr
- `sonarr-tv` for Sonarr
- `lidarr-music` for Lidarr

These must match in:

1. qBitrr `config.toml`
2. Arr download client configuration
3. qBittorrent category settings (optional)

## Feature Questions

### How does instant import work?

qBitrr monitors qBittorrent for completed torrents. When a download finishes:

1. qBitrr validates the files (optional FFprobe check)
2. Triggers `DownloadedMoviesScan` or `DownloadedEpisodesScan` in the Arr instance
3. Arr imports the files immediately (no waiting for periodic scan)

### What is MaxETA?

MaxETA (Maximum Estimated Time of Arrival) is the longest time qBitrr will wait for a torrent before marking it as failed. For example, `MaximumETA = 604800` means 7 days. If a torrent won't finish within 7 days, qBitrr marks it as failed, blacklists it in Arr, and triggers a new search.

### How does automated search work?

qBitrr can automatically search for:

- **Missing media**: Movies/shows/albums not yet downloaded
- **Quality upgrades**: Better releases for existing media
- **Custom format upgrades**: Releases meeting minimum CF scores

Configure search in the Arr instance section of config.toml:

```toml
[Radarr-Movies.Search]
SearchMissing = true
SearchByYear = true
SearchInReverse = false
SearchLimit = 10
```

### Can I use multiple Radarr/Sonarr instances?

Yes! Add multiple sections in config.toml:

```toml
[Radarr-Movies]
URI = "http://localhost:7878"
APIKey = "key1"

[Radarr-4K]
URI = "http://localhost:7879"
APIKey = "key2"

[Sonarr-TV]
URI = "http://localhost:8989"
APIKey = "key3"
```

Each instance runs in its own process.

### Does qBitrr support private trackers?

Yes! qBitrr works with both public and private trackers. You can configure per-tracker settings for:

- MaxETA thresholds
- Ratio limits
- Seeding time limits
- Tag management

[Tracker configuration →](configuration/seeding.md)

## Troubleshooting Questions

### Imports aren't triggering

Common causes:

1. **FFprobe validation failing**: Check logs for media validation errors
2. **File permissions**: Arr instance can't read downloaded files
3. **Path mapping**: Paths don't match between qBittorrent, Arr, and qBitrr
4. **Category mismatch**: Torrent category doesn't match config

[Troubleshooting guide →](troubleshooting/common-issues.md)

### High CPU or memory usage

Reduce resource usage:

1. **Increase loop sleep timers**: `SleepTimer` in Arr instance config
2. **Reduce search limits**: Lower `SearchLimit` values
3. **Disable verbose logging**: Set log level to INFO or WARNING
4. **Limit concurrent searches**: Reduce `SearchLimit` per instance

[Performance tuning →](advanced/performance.md)

### Docker path issues

Ensure paths are accessible:

1. Mount qBittorrent download directory to qBitrr container
2. Arr instances need same path mapping
3. Use consistent paths across all containers

Example:

```yaml
qbitrr:
  volumes:
    - /downloads:/downloads  # Same as qBittorrent and Arr
```

[Docker path mapping →](troubleshooting/path-mapping.md)

### Updates failing

Check these:

1. **Installation type**: qBitrr must detect git/pip/binary install correctly
2. **Permissions**: User running qBitrr needs write access
3. **GitHub API rate limit**: Check if you're rate-limited
4. **Docker**: Pull new image instead of using built-in updater

[Update troubleshooting →](troubleshooting/common-issues.md)

## WebUI Questions

### Can I change the WebUI port?

Yes, set in config.toml:

```toml
[Settings]
WebUIPort = 8080  # Default is 6969
```

### How do I secure the WebUI?

Enable authentication:

```toml
[Settings]
WebUIToken = "your_secret_token_here"
```

Then add `X-API-Token: your_secret_token_here` header to API requests.

### Can I access WebUI remotely?

Yes, but secure it first:

1. Enable `WebUIToken` authentication
2. Use a reverse proxy (nginx, Caddy) with HTTPS
3. Don't expose port directly to the internet

## Advanced Questions

### Can I run custom scripts on events?

Not directly, but you can:

1. Monitor logs for specific events
2. Use Arr's "Custom Scripts" feature
3. Build webhooks using Arr's "Connect" feature

### How do I contribute to qBitrr?

See the [Contributing Guide](development/contributing.md) for:

- Code style guidelines
- Development setup
- Pull request process
- Testing requirements

### Where can I request features?

- [GitHub Issues](https://github.com/Feramance/qBitrr/issues) for bugs
- [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions) for feature ideas

---

**Still have questions?** Ask in [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions) or check the [Troubleshooting Guide](troubleshooting/index.md).
