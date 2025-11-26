# Configuration

Welcome to the qBitrr configuration guide! This section covers all aspects of configuring qBitrr to work with your setup.

## Quick Links

- [Configuration File Reference](config-file.md) - Complete `config.toml` reference
- [qBittorrent Setup](qbittorrent.md) - Configure qBittorrent connection
- [Arr Instances](arr/index.md) - Configure Radarr, Sonarr, and Lidarr

## Configuration Sections

### Essential Configuration

These settings are required for qBitrr to function:

- **[qBittorrent](qbittorrent.md)** - Configure connection to qBittorrent
  - Host, port, and authentication
  - Version-specific settings (v4.x vs v5.x)
  - Docker networking considerations

- **[Arr Instances](arr/index.md)** - Configure at least one Arr application
  - [Radarr](arr/radarr.md) - Movie management
  - [Sonarr](arr/sonarr.md) - TV show management
  - [Lidarr](arr/lidarr.md) - Music management

### Advanced Configuration

Optional settings to customize qBitrr's behavior:

- **[Quality Profiles](quality-profiles.md)** - Map quality profiles to categories
- **[Seeding Rules](seeding.md)** - Configure seeding behavior
- **[Search Settings](search/index.md)** - Automated search configuration

## Configuration File Location

The configuration file is located at:

=== "Docker"
    ```
    /config/config.toml
    ```

=== "Native Install"
    ```
    ~/config/config.toml
    ```

=== "pip Install"
    ```
    ~/.config/qBitrr/config.toml
    ```

## Getting Started

1. **Generate Default Config**

   On first run, qBitrr automatically generates a default configuration file.

2. **Edit Configuration**

   Open the config file in your preferred text editor:
   ```bash
   nano ~/config/config.toml
   ```

3. **Configure Required Settings**

   At minimum, you need to configure:
   - qBittorrent connection details
   - At least one Arr instance (Radarr, Sonarr, or Lidarr)

4. **Restart qBitrr**

   After making changes, restart qBitrr for them to take effect.

## Configuration Best Practices

### Security

- **Never commit your config.toml** to version control
- **Use strong passwords** for qBittorrent and Arr instances
- **Enable authentication** on all services
- **Use HTTPS** when accessing services remotely

### Performance

- **Set appropriate intervals** - Don't check too frequently
- **Use categories** - Organize torrents by Arr instance
- **Enable instant imports** - For faster media availability
- **Configure logging** - Balance detail vs. disk space

### Reliability

- **Test connections** - Verify all services are accessible
- **Check logs** - Monitor for errors after configuration changes
- **Backup your config** - Save a copy before major changes
- **Use health checks** - Enable torrent health monitoring

## Common Configuration Scenarios

### Single Radarr Instance

Simplest setup for movie management only:

```toml
[Settings.Qbittorrent]
Host = "http://localhost"
Port = 8080
Username = "admin"
Password = "adminadmin"

[[Radarr]]
Name = "Radarr"
URI = "http://localhost:7878"
APIKey = "your-radarr-api-key"
```

### Multiple Arr Instances

Complete media server with movies, TV, and music:

```toml
[Settings.Qbittorrent]
Host = "http://localhost"
Port = 8080

[[Radarr]]
Name = "Radarr-Movies"
URI = "http://localhost:7878"
APIKey = "radarr-api-key"

[[Sonarr]]
Name = "Sonarr-TV"
URI = "http://localhost:8989"
APIKey = "sonarr-api-key"

[[Lidarr]]
Name = "Lidarr-Music"
URI = "http://localhost:8686"
APIKey = "lidarr-api-key"
```

### Docker Setup

Using Docker with custom network:

```toml
[Settings.Qbittorrent]
Host = "http://qbittorrent"  # Container name
Port = 8080

[[Radarr]]
Name = "Radarr"
URI = "http://radarr:7878"   # Container name
APIKey = "your-api-key"
```

## Validation

After configuring qBitrr, verify your setup:

1. **Check Logs** - Look for connection success messages
2. **Test in WebUI** - Use the configuration test feature
3. **Trigger Import** - Complete a download and verify import works
4. **Monitor Health** - Check torrent health monitoring is active

## Troubleshooting Configuration

If you encounter issues:

- [Common Issues](../troubleshooting/common-issues.md#configuration-issues)
- [Docker Networking](../troubleshooting/docker.md#networking)
- [Connection Problems](../troubleshooting/common-issues.md#connection-issues)

## Further Reading

- [Complete Configuration Reference](config-file.md) - Every setting explained
- [First Run Guide](../getting-started/first-run.md) - Step-by-step initial configuration
- [FAQ](../faq.md) - Common configuration questions
