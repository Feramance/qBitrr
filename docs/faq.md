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

1. **Categories don't match**: Your Arr download client category must match the category configured in your Arr instance section
2. **Missing tags**: Arr downloads need tags configured
3. **qBittorrent not connected**: Check connection settings in `[qBit]` section
4. **Wrong credentials**: Verify username and password match qBittorrent settings

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

[Performance tuning →](troubleshooting/performance.md)

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

See the [Development Guide](development/index.md) for:

- Code style guidelines
- Development setup
- Pull request process
- Testing requirements

### Where can I request features?

- [GitHub Issues](https://github.com/Feramance/qBitrr/issues) for bugs
- [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions) for feature ideas

### How do I backup my qBitrr configuration?

Backup these files/folders:

```bash
# Essential
~/config/config.toml      # Configuration file
~/config/qBitrr.db        # Database

# Optional
~/config/logs/            # Log files (if needed)
```

**Docker backup:**
```bash
docker cp qbitrr:/config/config.toml ./config.toml.backup
docker cp qbitrr:/config/qBitrr.db ./qBitrr.db.backup
```

### Can I run qBitrr on NAS devices?

Yes! qBitrr runs on many NAS platforms:

- **Synology**: Docker or native Python
- **QNAP**: Container Station (Docker)
- **Unraid**: Community Applications
- **TrueNAS**: Jails or Docker

[NAS installation guide →](getting-started/installation/docker.md#nas-devices)

### Does qBitrr work with VPN?

Yes, qBitrr works with VPN setups. Common configurations:

1. **qBittorrent behind VPN**: qBitrr and Arr instances access qBit normally
2. **All containers in VPN**: Ensure proper network configuration
3. **Split tunnel**: Route only torrent traffic through VPN

The key is that qBitrr must be able to reach qBittorrent and Arr instances on the network.

### What's the difference between instant import and Arr's import?

**Arr's default behavior:**
- Scans download folder every 1-15 minutes
- Import delay: 1-15 minutes after download completes

**qBitrr's instant import:**
- Monitors qBittorrent events in real-time
- Triggers import command immediately (within seconds)
- Import delay: 5-10 seconds after download completes

Result: **2-15 minutes faster** import to your library.

### Can qBitrr delete torrents automatically?

Yes, with seeding rules:

```toml
[Radarr-Movies.Torrent.SeedingMode]
MaxUploadRatio = 2.0          # Delete after 2.0 ratio
MaxSeedingTime = 604800       # Or after 7 days
RemoveTorrent = 3             # Remove when EITHER met
```

Options for `RemoveTorrent`:
- `-1` = Never remove
- `1` = Remove when ratio met
- `2` = Remove when time met
- `3` = Remove when EITHER met
- `4` = Remove when BOTH met

[Seeding configuration →](configuration/seeding.md)

### How does FFprobe validation work?

FFprobe validates media files before import:

1. **Download completes** in qBittorrent
2. **qBitrr runs FFprobe** to check file integrity
3. **If valid**: Trigger import to Arr
4. **If invalid**: Mark as failed, blacklist, re-search

Benefits:
- Prevents importing corrupt files
- Detects fake/sample files
- Verifies codec compatibility

```toml
[Settings]
EnableFFprobe = true
FFprobeAutoUpdate = true  # Auto-download FFprobe
```

### What happens when disk space is low?

With disk space management enabled:

```toml
[Settings]
FreeSpace = "50G"           # Threshold
FreeSpaceFolder = "/downloads"
AutoPauseResume = true
```

**Behavior:**
1. Disk space drops below 50GB
2. qBitrr pauses all torrents
3. Arr imports completed downloads (frees space)
4. Space increases above threshold
5. qBitrr resumes torrents automatically

[Disk space management →](features/disk-space.md)

### Can I use qBitrr with Prowlarr?

Yes! Prowlarr manages indexers for Radarr/Sonarr/Lidarr. qBitrr works alongside Prowlarr:

- **Prowlarr**: Manages indexers, syncs to Arr instances
- **qBitrr**: Monitors torrents, triggers imports, automates searches

They complement each other - no conflicts.

### Does qBitrr support Usenet?

No, qBitrr is specifically designed for torrents via qBittorrent. For Usenet:

- Arr instances handle Usenet natively (SABnzbd/NZBGet)
- qBitrr only monitors qBittorrent categories

### How do I migrate from another tool?

Common migrations:

**From qBittorrent-Manager:**
1. Install qBitrr
2. Port your category/tag configuration
3. Disable old manager
4. Verify qBitrr detects torrents

**From manual scripts:**
1. Identify what scripts do
2. Configure equivalent qBitrr features
3. Test in parallel
4. Remove scripts once verified

[Migration guide →](getting-started/migration.md)

### Can I customize search behavior?

Yes, extensive search customization:

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true              # Auto-search missing
SearchByYear = true               # Order by release year
SearchInReverse = false           # Newest first
SearchLimit = 10                  # Max concurrent
SearchRequestsEvery = 300         # Check every 5 min
DoUpgradeSearch = true            # Search for upgrades
CustomFormatUnmetSearch = true    # Enforce CF scores
```

[Search configuration →](configuration/search/index.md)

### What are custom formats and how does qBitrr use them?

Custom Formats (CF) are Radarr/Sonarr scoring rules for releases. qBitrr can:

1. **Enforce minimum scores**: Remove torrents below threshold
2. **Search for CF improvements**: Find releases with better scores
3. **Force quality standards**: Block non-compliant releases

```toml
[Radarr-Movies.EntrySearch]
CustomFormatUnmetSearch = true     # Search for CF improvements
ForceMinimumCustomFormat = true    # Remove below threshold
```

[Custom format guide →](features/custom-formats.md)

### How do I handle ratio requirements on private trackers?

Configure per-tracker seeding rules:

```toml
[[Radarr-Movies.Torrent.Trackers]]
Name = "PrivateHD"
URI = "https://tracker.privatehd.com"
MaxUploadRatio = 3.0      # Higher ratio for private
MaxSeedingTime = 1209600  # 14 days minimum
RemoveTorrent = 4         # Must meet BOTH requirements
```

This ensures you maintain good standing on private trackers.

[Private tracker setup →](advanced/index.md#private-tracker-configuration)

### Can I schedule searches at specific times?

Currently, searches run on intervals:

```toml
SearchRequestsEvery = 300  # Every 5 minutes
```

For advanced scheduling, consider:
- Using cron to restart qBitrr at specific times
- Adjusting intervals based on your indexer limits
- Request integration for on-demand searches

### How do I troubleshoot "No connection" errors?

**For qBittorrent:**
```bash
# Test connection
curl -u admin:password http://localhost:8080/api/v2/app/version

# Check if running
docker ps | grep qbittorrent
```

**For Arr instances:**
```bash
# Test API
curl -H "X-Api-Key: YOUR_KEY" http://localhost:7878/api/v3/system/status

# Check if running
docker ps | grep radarr
```

**Common fixes:**
1. Use container names in Docker (not `localhost`)
2. Verify ports are correct
3. Check firewall rules
4. Ensure services are running

[Connection troubleshooting →](troubleshooting/common-issues.md#connection-issues)

### Does qBitrr support Windows?

Yes! Installation options:

1. **Docker Desktop**: Recommended for Windows
2. **pip install**: Requires Python 3.11+

**Note:** Pre-built binaries are not currently available. Use Docker or pip installation methods.

**Windows-specific notes:**
- Use Windows paths (e.g., `C:\Downloads`)
- PowerShell or CMD for commands
- Docker Desktop requires WSL2

[Windows installation →](getting-started/installation/pip.md#windows)

### How often should I update qBitrr?

Update frequency depends on your needs:

- **Stable releases**: Every 1-2 months
- **Security updates**: Immediately
- **Feature updates**: When you need new features
- **Development builds**: Only for testing

Enable auto-updates:
```toml
[Settings]
AutoUpdateEnabled = true
AutoUpdateCron = "0 3 * * 0"  # Sundays at 3 AM
```

[Auto-update guide →](features/auto-updates.md)

### Can I use qBitrr with Plex/Jellyfin/Emby?

Yes! qBitrr works with any media server:

1. qBitrr → manages qBittorrent torrents
2. Radarr/Sonarr/Lidarr → organizes media
3. Plex/Jellyfin/Emby → serves media to users

qBitrr doesn't interact directly with media servers - it works through the Arr stack.

### What's the performance impact of qBitrr?

Typical resource usage:

- **CPU**: 1-5% average (spikes during scans)
- **RAM**: 100-300 MB
- **Disk**: ~50 MB (application + database)
- **Network**: Minimal (API calls only)

For 100+ torrents:
- CPU: 5-10% during checks
- RAM: 300-500 MB

[Performance tuning →](troubleshooting/performance.md)

### How do I report bugs?

Before reporting:

1. **Check logs** for error messages
2. **Search existing issues** on GitHub
3. **Try latest version** (bug might be fixed)

When reporting:

1. Go to [GitHub Issues](https://github.com/Feramance/qBitrr/issues)
2. Click "New Issue"
3. Include:
   - qBitrr version
   - Installation method
   - Error logs (redact sensitive info)
   - Steps to reproduce
   - Expected vs actual behavior

### Can I contribute without coding?

Yes! Non-code contributions:

- **Documentation**: Improve guides and examples
- **Testing**: Test new features and report issues
- **Support**: Help others in Discussions
- **Feedback**: Suggest improvements
- **Translations**: Help translate (future feature)

[Contributing guide →](development/index.md)

---

## Quick Reference

### Essential Commands

```bash
# Start qBitrr
qbitrr                              # pip/native
docker start qbitrr                 # Docker
sudo systemctl start qbitrr         # Systemd

# View logs
docker logs -f qbitrr               # Docker
journalctl -u qbitrr -f             # Systemd
tail -f ~/config/logs/Main.log      # Native

# Access WebUI
http://localhost:6969/ui
```

### Essential Configuration

```toml
# Minimum config
[Settings.Qbittorrent]
Host = "http://localhost:8080"
Username = "admin"
Password = "adminpass"

[Radarr-Movies]
URI = "http://localhost:7878"
APIKey = "your-api-key"
Category = "radarr-movies"
```

### Common File Locations

- **Config**: `~/config/config.toml` or `/config/config.toml`
- **Database**: `~/config/qBitrr.db` or `/config/qBitrr.db`
- **Logs**: `~/config/logs/` or `/config/logs/`
- **WebUI**: `http://localhost:6969/ui`

---

## Related Documentation

### Getting Started
- [Installation Guide](getting-started/installation/index.md)
- [Quick Start](getting-started/quickstart.md)
- [First Run Configuration](getting-started/first-run.md)

### Configuration
- [Complete Configuration Reference](configuration/config-file.md)
- [qBittorrent Setup](configuration/qbittorrent.md)
- [Arr Configuration](configuration/arr/index.md)
- [Search Settings](configuration/search/index.md)

### Features
- [Automated Search](features/automated-search.md)
- [Instant Imports](features/instant-imports.md)
- [Health Monitoring](features/health-monitoring.md)
- [Custom Formats](features/custom-formats.md)

### Troubleshooting
- [Common Issues](troubleshooting/common-issues.md)
- [Docker Problems](troubleshooting/docker.md)
- [Performance Tuning](troubleshooting/performance.md)
- [Path Mapping](troubleshooting/path-mapping.md)

### Advanced
- [Advanced Topics](advanced/index.md)
- [CLI Reference](reference/cli.md)
- [API Documentation](reference/api.md)
- [Development Guide](development/index.md)

---

## Need More Help?

- 💬 **Community Support**: [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions)
- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/Feramance/qBitrr/issues)
- 📚 **Documentation**: You're reading it!
- 🚀 **Quick Start**: [5-minute setup guide](getting-started/quickstart.md)
