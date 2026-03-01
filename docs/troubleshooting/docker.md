# Docker Troubleshooting

This page covers Docker-specific issues with qBitrr and their solutions.

---

## Container Won't Start

### Symptom: Container exits immediately after starting

**Check container logs:**

```bash
docker logs qbitrr
```

**Common Causes & Solutions:**

#### 1. Config File Missing or Invalid

**Error:** `FileNotFoundError: [Errno 2] No such file or directory: '/config/config.toml'`

**Solution:**

```bash
# Generate default config
docker run --rm -v /path/to/config:/config feramance/qbitrr:latest --gen-config

# Or create directory and let qBitrr generate it
mkdir -p /path/to/config
docker-compose up -d qbitrr
```

#### 2. Permission Issues

**Error:** `PermissionError: [Errno 13] Permission denied: '/config/config.toml'`

**Solution:**

```bash
# Fix permissions (qBitrr runs as UID 1000 by default)
sudo chown -R 1000:1000 /path/to/config
sudo chmod -R 755 /path/to/config
```

**Or specify custom UID/GID:**

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    user: "1001:1001"  # Your user's UID:GID
    volumes:
      - /path/to/config:/config
```

#### 3. Invalid TOML Syntax

**Error:** `tomlkit.exceptions.ParseError`

**Solution:**

1. Validate config with online TOML parser
2. Check for:
   - Missing quotes around strings
   - Unescaped backslashes in regex (should be `\\b`, not `\b`)
   - Mismatched brackets `[]` or braces `{}`

---

## Networking Issues

### Can't Connect to qBittorrent in Same Docker Network

**Symptom:** `Connection refused` when qBittorrent container is running

**Solution: Use Container Name, Not Localhost**

```yaml
services:
  qbittorrent:
    container_name: qbittorrent
    image: linuxserver/qbittorrent:latest
    networks:
      - mediastack

  qbitrr:
    image: feramance/qbitrr:latest
    networks:
      - mediastack
    volumes:
      - ./config:/config

networks:
  mediastack:
```

**config.toml:**

```toml
[qBit]
Host = "qbittorrent"  # Use container name, NOT "localhost"
Port = 8080
```

---

### Can't Connect to qBittorrent on Host Network

**Symptom:** qBittorrent is running on host, qBitrr in Docker can't connect

**Solution: Use Special Docker Host Alias**

**macOS/Windows:**

```toml
[qBit]
Host = "host.docker.internal"  # Special DNS name
Port = 8080
```

**Linux:**

```toml
[qBit]
Host = "172.17.0.1"  # Docker bridge IP
Port = 8080
```

**Or use host network mode:**

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    network_mode: host  # Use host's network directly
    volumes:
      - ./config:/config
```

```toml
[qBit]
Host = "localhost"  # Now localhost works
Port = 8080
```

!!! warning "Host Network Mode"
    `network_mode: host` bypasses Docker networking. WebUI will be exposed on host's port 6969 directly.

---

### Can't Access WebUI from Browser

**Symptom:** Browser shows "Connection refused" to http://localhost:6969

**Check port mapping:**

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    ports:
      - "6969:6969"  # host:container
```

**Test from host:**

```bash
curl http://localhost:6969/health
```

**If using custom port:**

```yaml
services:
  qbitrr:
    ports:
      - "7000:6969"  # Access via http://localhost:7000
```

**Firewall check:**

```bash
# Linux
sudo ufw allow 6969/tcp

# Check if port is listening
netstat -tuln | grep 6969
```

---

## Volume & Path Issues

### Path Mismatch Between Containers

**Symptom:** Imports fail, "Path not found" errors

**Problem:**

qBittorrent and Arr containers have different volume mappings for the same physical location.

**Example of WRONG setup:**

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/storage/torrents:/downloads  # qBit sees it as /downloads

  radarr:
    volumes:
      - /mnt/storage/torrents:/data/torrents  # Radarr sees it as /data/torrents
```

Radarr tells qBittorrent to save to `/data/torrents/Movie.mkv`, but qBittorrent doesn't know that path!

**Solution: Use Consistent Paths**

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/storage/torrents:/data/torrents  # Same inside path

  radarr:
    volumes:
      - /mnt/storage/torrents:/data/torrents  # Same inside path

  qbitrr:
    volumes:
      - /mnt/storage/torrents:/data/torrents  # Same inside path
```

**config.toml:**

```toml
[Settings]
CompletedDownloadFolder = "/data/torrents"
```

---

### qBitrr Can't See Completed Downloads

**Symptom:** Torrents complete but qBitrr doesn't trigger import

**Check volume mapping:**

```bash
# List files inside qBitrr container
docker exec qbitrr ls -la /data/torrents

# Compare with qBittorrent save path
docker exec qbittorrent ls -la /downloads
```

**Solution:**

Map the same **host directory** to the same **container path** in all containers.

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/storage:/data  # Host -> Container

  radarr:
    volumes:
      - /mnt/storage:/data  # Same mapping

  qbitrr:
    volumes:
      - /mnt/storage:/data  # Same mapping
```

---

## Environment Variables

### Config Not Being Honored

**Symptom:** Settings from environment variables not taking effect

**Supported environment variables:**

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    environment:
      - CONSOLE_LEVEL=DEBUG
      - QBIT_HOST=qbittorrent
      - QBIT_PORT=8080
      - WEBUI_HOST=0.0.0.0
      - WEBUI_PORT=6969
```

**Note:** Config file values take precedence over environment variables.

**To debug:**

```bash
docker exec qbitrr printenv | grep -i qbit
```

---

## Container Health

### Database Corruption After Restart (Docker)

**Symptom:** After `docker stop` / `docker restart`, logs show "database disk image is malformed" or integrity check failures.

**Cause:** The main process did not receive SIGTERM (or was killed before cleanup), so the database WAL was never checkpointed. This used to happen when Python was PID 1 in the container.

**What qBitrr does to prevent it:**

- The official image runs **tini** as PID 1 so SIGTERM is forwarded to the Python process. On SIGTERM, qBitrr checkpoints the database WAL and then exits.
- Use **`stop_grace_period: 30s`** (or more) in your Compose file so Docker waits long enough for cleanup before sending SIGKILL.

**Example:**

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    stop_grace_period: 30s   # Give time for DB checkpoint on stop
    # ... rest of config
```

**Do not:** Use `docker kill` or `docker stop -t 0`; that skips graceful shutdown and can corrupt the database.

---

### Container Constantly Restarting

**Check restart policy:**

```yaml
services:
  qbitrr:
    restart: unless-stopped  # or "always", "on-failure"
```

**Check crash logs:**

```bash
# View last 100 lines before crash
docker logs --tail 100 qbitrr

# Follow logs in real-time
docker logs -f qbitrr
```

**Common causes:**

1. **Config error:** Fix config.toml syntax
2. **Missing dependencies:** Use official image (not custom builds)
3. **Out of memory:** Increase Docker memory limit
4. **Database corruption:** Delete `/config/qBitrr.db` (will rebuild)

---

### High Memory Usage

**Check container stats:**

```bash
docker stats qbitrr
```

**Solutions:**

1. **Limit memory:**
   ```yaml
   services:
     qbitrr:
       mem_limit: 512m
       memswap_limit: 512m
   ```

2. **Reduce logging:**
   ```toml
   [Settings]
   ConsoleLevel = "WARNING"
   ```

3. **Disable WebUI live updates:**
   ```toml
   [WebUI]
   LiveArr = false
   ```

---

## Multi-Container Setup

### Complete Docker Compose Example

```yaml
version: "3.8"

services:
  qbittorrent:
    image: lscr.io/linuxserver/qbittorrent:latest
    container_name: qbittorrent
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
      - WEBUI_PORT=8080
    volumes:
      - ./qbittorrent/config:/config
      - /mnt/storage:/data
    ports:
      - "8080:8080"
      - "6881:6881"
      - "6881:6881/udp"
    restart: unless-stopped
    networks:
      - mediastack

  radarr:
    image: lscr.io/linuxserver/radarr:latest
    container_name: radarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./radarr/config:/config
      - /mnt/storage:/data
    ports:
      - "7878:7878"
    restart: unless-stopped
    networks:
      - mediastack

  sonarr:
    image: lscr.io/linuxserver/sonarr:latest
    container_name: sonarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./sonarr/config:/config
      - /mnt/storage:/data
    ports:
      - "8989:8989"
    restart: unless-stopped
    networks:
      - mediastack

  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    user: "1000:1000"
    volumes:
      - ./qbitrr/config:/config
      - /mnt/storage:/data
    ports:
      - "6969:6969"
    restart: unless-stopped
    depends_on:
      - qbittorrent
      - radarr
      - sonarr
    networks:
      - mediastack

networks:
  mediastack:
    driver: bridge
```

**Matching config.toml:**

```toml
[qBit]
Host = "qbittorrent"  # Docker service name
Port = 8080
UserName = "admin"
Password = "password"

[Radarr-Movies]
URI = "http://radarr:7878"  # Docker service name
APIKey = "your-api-key"
Category = "radarr-movies"

[Sonarr-TV]
URI = "http://sonarr:8989"  # Docker service name
APIKey = "your-api-key"
Category = "sonarr-tv"

[Settings]
CompletedDownloadFolder = "/data/torrents"

[WebUI]
Host = "0.0.0.0"
Port = 6969
```

---

## Debugging Commands

### View Logs

```bash
# All logs
docker logs qbitrr

# Last 50 lines
docker logs --tail 50 qbitrr

# Follow logs in real-time
docker logs -f qbitrr

# Save logs to file
docker logs qbitrr > qbitrr.log 2>&1
```

### Inspect Container

```bash
# View container details
docker inspect qbitrr

# Check network connectivity
docker exec qbitrr ping -c 3 qbittorrent

# Test curl inside container
docker exec qbitrr curl http://qbittorrent:8080/api/v2/app/version

# Check files inside container
docker exec qbitrr ls -la /config
docker exec qbitrr cat /config/config.toml
```

### Container Shell Access

```bash
# Open shell inside running container
docker exec -it qbitrr /bin/sh

# Or bash if available
docker exec -it qbitrr /bin/bash

# Check environment variables
docker exec qbitrr printenv

# Check process
docker exec qbitrr ps aux | grep qbitrr
```

### Test Connectivity

```bash
# From host to container
curl http://localhost:6969/health

# From container to qBittorrent
docker exec qbitrr curl -v http://qbittorrent:8080/api/v2/app/version

# From container to Radarr
docker exec qbitrr curl -H "X-Api-Key: your-api-key" http://radarr:7878/api/v3/system/status
```

---

## Updating qBitrr

### Pull Latest Image

```bash
# Stop container
docker-compose down qbitrr

# Pull latest image
docker-compose pull qbitrr

# Start container
docker-compose up -d qbitrr

# Or all at once
docker-compose pull && docker-compose up -d
```

### Rollback to Previous Version

```bash
# Use specific version tag
docker-compose down qbitrr
docker pull feramance/qbitrr:5.1.0  # Specific version
docker-compose up -d qbitrr
```

**Or in docker-compose.yml:**

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:5.1.0  # Pin to specific version
```

---

## Backup & Restore

### Backup Configuration

```bash
# Backup config directory
tar -czf qbitrr-backup-$(date +%Y%m%d).tar.gz ./qbitrr/config/

# Or just the config file
cp ./qbitrr/config/config.toml qbitrr-config-backup.toml
```

### Restore Configuration

```bash
# Extract backup
tar -xzf qbitrr-backup-20250326.tar.gz

# Or copy config
cp qbitrr-config-backup.toml ./qbitrr/config/config.toml

# Restart container
docker-compose restart qbitrr
```

---

## Performance Tuning

### Resource Limits

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    deploy:
      resources:
        limits:
          cpus: '0.5'      # Limit to 50% of 1 CPU
          memory: 512M     # Limit to 512MB RAM
        reservations:
          cpus: '0.25'     # Reserve 25% of 1 CPU
          memory: 256M     # Reserve 256MB RAM
```

### Logging Configuration

```yaml
services:
  qbitrr:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"   # Max log file size
        max-file: "3"     # Keep 3 log files
```

---

## Common Docker Errors

### `dial tcp: lookup qbittorrent: no such host`

**Cause:** Containers not in same Docker network

**Solution:**

```yaml
services:
  qbittorrent:
    networks:
      - mediastack  # Add network

  qbitrr:
    networks:
      - mediastack  # Add same network

networks:
  mediastack:
```

---

### `driver failed programming external connectivity`

**Cause:** Port already in use

**Solution:**

```bash
# Check what's using the port
sudo netstat -tulpn | grep 6969

# Kill process or change port mapping
```

```yaml
services:
  qbitrr:
    ports:
      - "7000:6969"  # Use different host port
```

---

### `error while creating mount source path: mkdir: read-only file system`

**Cause:** Host directory doesn't exist or is read-only

**Solution:**

```bash
# Create directory first
mkdir -p /path/to/config

# Check permissions
ls -ld /path/to/config
sudo chown -R 1000:1000 /path/to/config
```

---

## Related Documentation

- [Installation: Docker](../getting-started/installation/docker.md)
- [Common Issues](common-issues.md)
- [qBittorrent Configuration](../configuration/qbittorrent.md)
