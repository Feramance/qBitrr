# WebUI

qBitrr includes a modern, React-based web interface for monitoring and managing your qBitrr instance.

## Accessing the WebUI

The WebUI is available at:

```
http://localhost:6969/ui
```

Or if you've changed the port:

```
http://localhost:YOUR_PORT/ui
```

## Features

### Process Monitoring

View all running Arr manager processes:

- **Status** - See if each Arr instance is running
- **Health** - Monitor connection status
- **Statistics** - View torrent counts and activity
- **Actions** - Restart or stop individual processes

### Live Logs

Tail logs in real-time from the web interface:

- **Main Log** - qBitrr application logs
- **WebUI Log** - Web interface logs
- **Arr Logs** - Individual logs for each Arr instance
- **Filtering** - Filter logs by level (DEBUG, INFO, WARNING, ERROR)
- **Search** - Find specific log entries

### Arr Instance Views

Browse your media library from qBitrr:

- **Radarr View** - See movies managed by Radarr
- **Sonarr View** - View TV series and episodes
- **Lidarr View** - Browse music albums and artists
- **Filtering** - Filter by status, quality, tags
- **Search** - Find specific media items

### Configuration Editor

Edit your qBitrr configuration from the web:

- **Syntax Highlighting** - TOML syntax highlighting
- **Validation** - Check for configuration errors
- **Apply Changes** - Restart qBitrr with new configuration
- **Backup** - Save configuration backups

### System Information

View system and version information:

- **Version** - Current qBitrr version
- **Uptime** - How long qBitrr has been running
- **Python Version** - Python runtime version
- **Dependencies** - Installed package versions

## Authentication

If you've configured a WebUI token, you'll need to authenticate:

```toml
[Settings]
WebUIToken = "your-secure-token"
```

The token is required in the `X-API-Token` header for API requests.

## Dark/Light Mode

The WebUI supports both dark and light themes:

- **Auto** - Follows system preference
- **Dark** - Dark theme
- **Light** - Light theme

Toggle using the theme switcher in the navigation bar.

## Mobile Support

The WebUI is fully responsive and works on:

- **Desktop** - Full feature set
- **Tablet** - Optimized layout
- **Mobile** - Touch-friendly interface

## API Access

The WebUI is built on top of the qBitrr REST API:

**Endpoints:**
- `/api/processes` - Process status
- `/api/logs` - Log entries
- `/api/radarr/movies` - Radarr movies
- `/api/sonarr/series` - Sonarr series
- `/api/lidarr/albums` - Lidarr albums
- `/api/config` - Configuration

See the API documentation (coming soon) for detailed endpoint information.

## Troubleshooting

### WebUI Not Loading

**Problem:** Can't access WebUI at http://localhost:6969/ui

**Solutions:**

1. **Check qBitrr is running:**
   ```bash
   # Docker
   docker ps | grep qbitrr

   # Systemd
   systemctl status qbitrr
   ```

2. **Verify port is correct:**
   ```toml
   [Settings]
   WebUIPort = 6969  # Check your configuration
   ```

3. **Check port mapping (Docker):**
   ```bash
   docker run -p 6969:6969 ...
   ```

4. **Check firewall:**
   ```bash
   # Allow port 6969
   sudo ufw allow 6969
   ```

### Authentication Errors

**Problem:** API requests return 401 Unauthorized

**Solutions:**

1. **Check token configuration:**
   ```toml
   [Settings]
   WebUIToken = "your-token"
   ```

2. **Include token in requests:**
   ```bash
   curl http://localhost:6969/api/processes \
     -H "X-API-Token: your-token"
   ```

### Slow Performance

**Problem:** WebUI is slow or unresponsive

**Solutions:**

1. **Reduce data being fetched:**
   - Limit log entries shown
   - Filter large media libraries
   - Disable auto-refresh if not needed

2. **Check system resources:**
   ```bash
   docker stats qbitrr
   ```

3. **Clear browser cache**

## Future Features

Planned WebUI enhancements:

- Interactive configuration wizard
- Torrent management interface
- Search triggering from WebUI
- Real-time notifications
- Multi-language support
- Custom dashboard layouts

## Development

The WebUI is built with:

- **React 18** - UI framework
- **TypeScript** - Type-safe development
- **Mantine** - Component library
- **Vite** - Build tool and dev server
- **TanStack Table** - Data tables

Source code: `webui/src/` in the repository

## Related Documentation

- [Installation](../getting-started/installation/index.md) - Installing qBitrr with WebUI
- [Configuration](../configuration/index.md) - Configuring WebUI settings
- [API Documentation](../reference/index.md) - API reference (coming soon)

## Feedback

Have suggestions for the WebUI?

- [Open an issue](https://github.com/Feramance/qBitrr/issues)
- [Start a discussion](https://github.com/Feramance/qBitrr/discussions)
