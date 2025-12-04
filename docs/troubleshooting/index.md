# Troubleshooting

Having issues with qBitrr? This section provides solutions to common problems and debugging techniques.

## Quick Links

- [Common Issues](common-issues.md) - Frequently encountered problems and solutions
- [Docker Issues](docker.md) - Docker-specific troubleshooting
- [FAQ](../faq.md) - Frequently asked questions

## Common Problems

### Connection Issues

Can't connect to qBittorrent or Arr instances?

**Quick Fixes:**
- Verify all services are running
- Check host/port configuration
- Verify API keys are correct
- Test connections from qBitrr container/host

**Detailed Guide:** [Connection Problems](common-issues.md#connection-issues)

### Import Issues

Downloads complete but don't import to Arr?

**Quick Fixes:**
- Check path mappings
- Verify file permissions
- Enable instant import
- Check Arr logs

**Detailed Guide:** [Import Failures](common-issues.md#import-issues)

### Docker Networking

Problems with Docker container communication?

**Quick Fixes:**
- Use container names instead of localhost
- Check Docker network configuration
- Verify port mappings
- Test inter-container connectivity

**Detailed Guide:** [Docker Networking](docker.md#networking)

### Stalled Torrents

Torrents stuck and not completing?

**Quick Fixes:**
- Check torrent health monitoring is enabled
- Verify tracker connectivity
- Check available disk space
- Review torrent client logs

**Detailed Guide:** [Stalled Torrents](common-issues.md#stalled-torrents)

## Debugging Steps

### 1. Check Logs

qBitrr logs provide detailed information about operations:

=== "Docker"
    ```bash
    # View logs
    docker logs qbitrr

    # Follow logs in real-time
    docker logs -f qbitrr

    # Save logs to file
    docker logs qbitrr > qbitrr.log 2>&1
    ```

=== "Systemd"
    ```bash
    # View logs
    journalctl -u qbitrr

    # Follow logs
    journalctl -u qbitrr -f

    # Recent logs
    journalctl -u qbitrr -n 100
    ```

=== "pip/Native"
    ```bash
    # Logs are in ~/config/logs/
    tail -f ~/config/logs/Main.log
    ```

### 2. Verify Configuration

Check your configuration file for errors:

```bash
# Native
cat ~/config/config.toml

# Docker
docker exec qbitrr cat /config/config.toml
```

Common configuration mistakes:
- Wrong API keys
- Incorrect host/port
- Missing required fields
- Typos in service names

### 3. Test Connectivity

Verify services are accessible:

```bash
# Test qBittorrent
curl http://localhost:8080

# Test Radarr
curl http://localhost:7878/api/v3/system/status \
  -H "X-Api-Key: your-api-key"

# Test Sonarr
curl http://localhost:8989/api/v3/system/status \
  -H "X-Api-Key: your-api-key"
```

### 4. Check Service Status

Ensure all required services are running:

=== "Docker"
    ```bash
    docker ps | grep -E "qbittorrent|radarr|sonarr|qbitrr"
    ```

=== "Systemd"
    ```bash
    systemctl status qbittorrent radarr sonarr qbitrr
    ```

### 5. Review Permissions

File permission issues can cause imports to fail:

```bash
# Check ownership
ls -la /path/to/downloads

# Check qBitrr can read files
docker exec qbitrr ls -la /downloads
```

## Getting Help

### Before Asking for Help

1. **Check the documentation:**
   - [Common Issues](common-issues.md)
   - [Docker Troubleshooting](docker.md)
   - [FAQ](../faq.md)

2. **Gather information:**
   - qBitrr version
   - Installation method (Docker/pip/binary)
   - Arr versions
   - Relevant log excerpts
   - Configuration (redact API keys!)

3. **Search existing issues:**
   - [GitHub Issues](https://github.com/Feramance/qBitrr/issues)
   - [Discussions](https://github.com/Feramance/qBitrr/discussions)

### Where to Get Help

- **GitHub Issues** - For bugs and feature requests
- **GitHub Discussions** - For questions and community support
- **Discord** - Real-time help from the community

### Creating a Good Issue Report

Include:

1. **Environment:**
   ```
   qBitrr version: 5.5.5
   Installation: Docker
   OS: Ubuntu 22.04
   qBittorrent: 4.6.0
   Radarr: 5.0.0
   ```

2. **Problem Description:**
   - What you expected to happen
   - What actually happened
   - Steps to reproduce

3. **Relevant Logs:**
   ```
   [Include relevant log excerpts]
   ```

4. **Configuration:**
   ```toml
   # Redact sensitive information!
   [Settings.Qbittorrent]
   Host = "http://qbittorrent"
   Port = 8080
   Username = "admin"
   Password = "REDACTED"
   ```

## Debug Mode

Enable debug logging for more detailed information:

```toml
[Settings]
LogLevel = "DEBUG"
```

**Warning:** Debug logs can be very verbose and may impact performance. Only enable when troubleshooting.

## Performance Issues

If qBitrr is running slowly:

1. **Check system resources:**
   ```bash
   # Docker
   docker stats qbitrr

   # System
   top
   htop
   ```

2. **Reduce check intervals:**
   ```toml
   [Settings]
   CheckInterval = 300  # Increase to 5 minutes
   ```

3. **Limit concurrent operations:**
   ```toml
   [Settings]
   MaxConcurrentChecks = 5
   ```

## Clean Restart

Sometimes a clean restart resolves issues:

=== "Docker"
    ```bash
    docker stop qbitrr
    docker rm qbitrr
    # Then recreate with your docker run command
    ```

=== "Systemd"
    ```bash
    sudo systemctl restart qbitrr
    ```

=== "pip/Native"
    ```bash
    # Stop qBitrr (Ctrl+C if running in foreground)
    # Then restart
    qbitrr
    ```

## Database Issues

If the database becomes corrupt:

1. **Backup existing database:**
   ```bash
   cp ~/config/qBitrr.db ~/config/qBitrr.db.backup
   ```

2. **Let qBitrr recreate:**
   ```bash
   rm ~/config/qBitrr.db
   # Restart qBitrr - it will create a new database
   ```

3. **Recovery:** qBitrr has automatic database recovery. Check logs for recovery messages.

## Still Need Help?

If you've tried the troubleshooting steps and still have issues:

1. Review [Common Issues](common-issues.md) for detailed solutions
2. Check [Docker-specific issues](docker.md) if using Docker
3. Search [GitHub Issues](https://github.com/Feramance/qBitrr/issues)
4. Ask in [GitHub Discussions](https://github.com/Feramance/qBitrr/discussions)

We're here to help! 🚀
