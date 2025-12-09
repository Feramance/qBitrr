# Docker Installation

Docker is the recommended way to run qBitrr. It provides an isolated, consistent environment that works across all platforms.

## Prerequisites

- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- Docker Compose installed (optional but recommended)
- qBittorrent running and accessible
- At least one Arr instance (Radarr, Sonarr, or Lidarr)

## Quick Start

### Using Docker Run

```bash
docker run -d \
  --name qbitrr \
  --restart unless-stopped \
  -p 6969:6969 \
  -v /path/to/config:/config \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=America/New_York \
  feramance/qbitrr:latest
```

### Using Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: "3.8"

services:
  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    restart: unless-stopped
    ports:
      - "6969:6969"
    volumes:
      - /path/to/config:/config
      - /path/to/downloads:/downloads  # Same as qBittorrent
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
```

Then run:

```bash
docker-compose up -d
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | `1000` | User ID for file permissions |
| `PGID` | `1000` | Group ID for file permissions |
| `TZ` | `UTC` | Timezone (e.g., `America/New_York`, `Europe/London`) |
| `QBITRR_CONFIG_PATH` | `/config` | Path to config directory |
| `QBITRR_LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### Volume Mapping

!!! warning "Path Mapping is Critical"
    qBitrr, qBittorrent, and your Arr instances MUST all see the same paths for downloads. This is the #1 cause of issues with Docker setups.

**Required volumes:**

- `/config` - Configuration files and database
- `/downloads` - Must match qBittorrent and Arr download paths

**Example:**

If qBittorrent downloads to `/downloads/torrents`, and Radarr expects files in `/downloads/torrents`, then qBitrr needs the same mount:

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/storage/downloads:/downloads

  radarr:
    volumes:
      - /mnt/storage/downloads:/downloads

  qbitrr:
    volumes:
      - /mnt/storage/downloads:/downloads  # Same path!
```

## Docker Compose Example (Complete)

Here's a complete example with qBittorrent, Radarr, and qBitrr:

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
      - /path/to/qbittorrent/config:/config
      - /path/to/downloads:/downloads
    ports:
      - "8080:8080"
      - "6881:6881"
      - "6881:6881/udp"
    restart: unless-stopped

  radarr:
    image: lscr.io/linuxserver/radarr:latest
    container_name: radarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - /path/to/radarr/config:/config
      - /path/to/downloads:/downloads
      - /path/to/movies:/movies
    ports:
      - "7878:7878"
    restart: unless-stopped

  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - /path/to/qbitrr/config:/config
      - /path/to/downloads:/downloads  # Must match!
    ports:
      - "6969:6969"
    restart: unless-stopped
    depends_on:
      - qbittorrent
      - radarr
```

## Image Tags

| Tag | Description |
|-----|-------------|
| `latest` | Latest stable release (recommended) |
| `nightly` | Latest development build (bleeding edge) |
| `5.x.x` | Specific version (e.g., `5.5.5`) |

**Recommended:** Use `latest` for production, `nightly` for testing new features.

## First Run

1. **Start the container:**
   ```bash
   docker-compose up -d
   ```

2. **Check logs:**
   ```bash
   docker logs -f qbitrr
   ```

3. **Configuration file created:**
   qBitrr will generate `/config/config.toml` on first run

4. **Stop the container to edit config:**
   ```bash
   docker-compose down
   ```

5. **Edit the configuration:**
   ```bash
   nano /path/to/config/config.toml
   ```

6. **Start again:**
   ```bash
   docker-compose up -d
   ```

See the [First Run Guide](../first-run.md) for detailed configuration steps.

## Accessing the WebUI

Once running, access the WebUI at:

```
http://localhost:6969/ui
```

Or replace `localhost` with your server's IP address.

## Updating

### Docker Compose

```bash
docker-compose pull
docker-compose up -d
```

### Docker Run

```bash
docker pull feramance/qbitrr:latest
docker stop qbitrr
docker rm qbitrr
# Run the docker run command again
```

!!! tip "Auto-Updates"
    qBitrr has a built-in auto-update feature that works in Docker. It will pull the latest image and restart the container automatically if configured.

## Troubleshooting

### Container Won't Start

**Problem:** Container exits immediately or fails to start

**Check logs:**
```bash
docker logs qbitrr
```

**Common issues:**

1. **Port Already in Use**
   ```
   Error: bind: address already in use
   ```
   **Solution:**
   ```bash
   # Check what's using port 6969
   sudo lsof -i :6969

   # Change port in docker-compose.yml
   ports:
     - "6970:6969"  # Map to different host port
   ```

2. **Config Directory Permissions**
   ```
   PermissionError: [Errno 13] Permission denied: '/config'
   ```
   **Solution:**
   ```bash
   # Create directory with correct ownership
   mkdir -p /path/to/config
   sudo chown -R 1000:1000 /path/to/config
   chmod -R 755 /path/to/config
   ```

3. **Invalid config.toml Syntax**
   ```
   TOMLDecodeError: Invalid TOML
   ```
   **Solution:**
   ```bash
   # Validate TOML syntax
   docker run --rm -v /path/to/config:/config \
     feramance/qbitrr:latest qbitrr --validate-config

   # Or delete and regenerate
   mv /path/to/config/config.toml /path/to/config/config.toml.old
   docker restart qbitrr  # Generates new config
   ```

4. **Missing Environment Variables**
   ```
   KeyError: 'QBITRR_CONFIG_PATH'
   ```
   **Solution:** Ensure all required environment variables are set in docker-compose.yml

### Can't Connect to qBittorrent/Arr

**Problem:** qBitrr can't reach qBittorrent or Arr instances

**Diagnosis:**

1. **Check Container Communication:**
   ```bash
   # Ping qBittorrent from qBitrr
   docker exec qbitrr ping -c 3 qbittorrent

   # Check if port is reachable
   docker exec qbitrr wget -O- http://qbittorrent:8080
   ```

2. **Verify Network Configuration:**
   ```bash
   # Check which network containers are on
   docker inspect qbitrr | grep NetworkMode
   docker inspect qbittorrent | grep NetworkMode

   # List all networks
   docker network ls
   ```

**Solutions:**

1. **Use Container Names (Same Network):**
   ```toml
   [Settings.Qbittorrent]
   Host = "http://qbittorrent:8080"  # Use container name

   [[Radarr]]
   URI = "http://radarr:7878"  # Use container name
   ```

2. **Use Host IP (Different Networks):**
   ```toml
   [Settings.Qbittorrent]
   Host = "http://192.168.1.100:8080"  # Host IP

   [[Radarr]]
   URI = "http://192.168.1.100:7878"  # Host IP
   ```

3. **Put All Containers on Same Network:**
   ```yaml
   networks:
     media:
       driver: bridge

   services:
     qbitrr:
       networks:
         - media
     qbittorrent:
       networks:
         - media
     radarr:
       networks:
         - media
   ```

4. **Use host.docker.internal (Docker Desktop):**
   ```toml
   [Settings.Qbittorrent]
   Host = "http://host.docker.internal:8080"
   ```

### Permission Issues

**Problem:** Permission denied errors when accessing files

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied
OSError: [Errno 1] Operation not permitted
```

**Diagnosis:**

1. **Check Current PUID/PGID:**
   ```bash
   # On host
   id yourusername
   # Output: uid=1000(user) gid=1000(user)

   # In container
   docker exec qbitrr id
   ```

2. **Check File Ownership:**
   ```bash
   ls -la /path/to/config
   ls -la /path/to/downloads
   ```

**Solutions:**

1. **Set Correct PUID/PGID:**
   ```yaml
   environment:
     - PUID=1000  # Match your user's UID
     - PGID=1000  # Match your user's GID
   ```

2. **Fix Existing File Permissions:**
   ```bash
   # Fix config directory
   sudo chown -R 1000:1000 /path/to/config

   # Fix downloads directory
   sudo chown -R 1000:1000 /path/to/downloads

   # Set proper permissions
   chmod -R 775 /path/to/downloads
   ```

3. **For NFS/SMB Shares:**
   ```yaml
   volumes:
     - type: volume
       source: nfs-share
       target: /downloads
       volume:
         nocopy: true

   volumes:
     nfs-share:
       driver: local
       driver_opts:
         type: nfs
         o: addr=192.168.1.100,rw,nfsvers=4
         device: ":/mnt/media/downloads"
   ```

### Path Not Found Errors

**Problem:** qBitrr can't find downloaded files

**Symptoms:**
```
FileNotFoundError: [Errno 2] No such file or directory
```

**Diagnosis:**

```bash
# Check path in qBitrr
docker exec qbitrr ls -la /downloads

# Check same path in qBittorrent
docker exec qbittorrent ls -la /downloads

# Check same path in Radarr
docker exec radarr ls -la /downloads

# All should show the SAME files
```

**Solutions:**

1. **Ensure Identical Volume Mappings:**
   ```yaml
   services:
     qbittorrent:
       volumes:
         - /mnt/storage/downloads:/downloads  # Same host path

     radarr:
       volumes:
         - /mnt/storage/downloads:/downloads  # Same host path

     qbitrr:
       volumes:
         - /mnt/storage/downloads:/downloads  # Same host path
   ```

2. **Check qBittorrent Save Path:**
   - Open qBittorrent WebUI
   - Settings → Downloads
   - Default Save Path should be `/downloads` (or whatever you mapped)

3. **Verify Remote Path Mapping in Arr:**
   - Open Radarr/Sonarr
   - Settings → Download Clients → qBittorrent
   - Remote Path Mappings should be empty (if using same paths)
   - Or map qBittorrent's path to Arr's path if different

### Import Failures

**Problem:** Downloads complete but don't import to Arr

**Check qBitrr logs:**
```bash
docker logs qbitrr | grep -i import
```

**Check Arr logs:**
```bash
docker logs radarr | grep -i import
```

**Common Causes:**

1. **Path Mismatch:**
   - qBittorrent sees: `/downloads/Movie.mkv`
   - Arr sees: `/media/downloads/Movie.mkv`
   - **Fix:** Use same volume mappings (see above)

2. **Missing Instant Import:**
   ```toml
   [[Radarr]]
   InstantImport = true  # Add this
   ```

3. **FFprobe Validation Failed:**
   ```bash
   # Check logs for FFprobe errors
   docker logs qbitrr | grep -i ffprobe

   # Disable validation temporarily
   # In config.toml:
   [Settings]
   FFprobeDownload = false
   ```

4. **Category Not Configured:**
   - qBittorrent assigns category: `radarr`
   - Arr download client category: `movies` (different!)
   - **Fix:** Match categories in both

### Database Locked Errors

**Problem:** SQLite database locked errors in logs

**Symptoms:**
```
sqlite3.OperationalError: database is locked
```

**Solutions:**

1. **Stop Multiple Instances:**
   ```bash
   # Check for multiple containers
   docker ps --filter name=qbitrr

   # Stop extras
   docker stop qbitrr-old
   ```

2. **Fix Permissions:**
   ```bash
   sudo chown 1000:1000 /path/to/config/qbitrr.db*
   chmod 644 /path/to/config/qbitrr.db*
   ```

3. **Repair Database:**
   ```bash
   docker exec qbitrr qbitrr --repair-db
   ```

### Network Issues

**Problem:** Can't access WebUI or APIs

**Check container is running:**
```bash
docker ps | grep qbitrr
```

**Check port mapping:**
```bash
docker port qbitrr
# Should show: 6969/tcp -> 0.0.0.0:6969
```

**Test from inside container:**
```bash
docker exec qbitrr wget -O- http://localhost:6969/api/health
```

**Test from host:**
```bash
curl http://localhost:6969/api/health
```

**Solutions:**

1. **Firewall Blocking Port:**
   ```bash
   # Allow port 6969
   sudo ufw allow 6969/tcp

   # Or check firewalld
   sudo firewall-cmd --add-port=6969/tcp --permanent
   sudo firewall-cmd --reload
   ```

2. **Wrong Bind Address:**
   ```toml
   [WebUI]
   Host = "0.0.0.0"  # Listen on all interfaces
   Port = 6969
   ```

3. **Container Network Mode:**
   ```yaml
   # Use bridge mode (default)
   services:
     qbitrr:
       network_mode: bridge  # Not host
   ```

### High CPU/Memory Usage

**Problem:** Container using too many resources

**Check resource usage:**
```bash
docker stats qbitrr
```

**Solutions:**

1. **Set Resource Limits:**
   ```yaml
   services:
     qbitrr:
       deploy:
         resources:
           limits:
             cpus: '1.0'      # Max 1 CPU core
             memory: 512M      # Max 512MB RAM
           reservations:
             cpus: '0.25'
             memory: 128M
   ```

2. **Reduce Logging:**
   ```toml
   [Settings]
   LogLevel = "INFO"  # Change from DEBUG
   ```

3. **Increase Search Delay:**
   ```toml
   [Radarr.EntrySearch]
   SearchRequestsEvery = 600  # Search less frequently
   ```

4. **Optimize Database:**
   ```bash
   docker exec qbitrr qbitrr --vacuum-db
   ```

### Auto-Update Not Working

**Problem:** Container doesn't auto-update

**Docker auto-update requires:**

1. **Watchtower or similar:**
   ```yaml
   services:
     watchtower:
       image: containrrr/watchtower
       volumes:
         - /var/run/docker.sock:/var/run/docker.sock
       command: --interval 86400  # Check daily
   ```

2. **Or enable qBitrr's built-in update:**
   ```toml
   [Settings]
   AutoUpdateEnabled = true
   AutoUpdateCron = "0 3 * * *"  # 3 AM daily
   ```

### Container Keeps Restarting

**Problem:** Container in restart loop

**Check restart count:**
```bash
docker ps -a | grep qbitrr
```

**View last logs before crash:**
```bash
docker logs --tail 100 qbitrr
```

**Common Causes:**

1. **Config Error:** Invalid TOML syntax
   - Fix: Validate config with `--validate-config`

2. **Missing Dependencies:** FFprobe download failed
   - Fix: Manually download FFprobe

3. **Database Corruption:**
   - Fix: Delete database, let qBitrr recreate

**Disable auto-restart temporarily:**
```bash
docker update --restart=no qbitrr
```

## Advanced Configuration

### Custom Network

Create a dedicated network for your media stack:

```yaml
networks:
  media:
    driver: bridge

services:
  qbitrr:
    networks:
      - media
    # ... rest of config
```

### Resource Limits

Limit CPU and memory usage:

```yaml
services:
  qbitrr:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

### Health Checks

Add a health check:

```yaml
services:
  qbitrr:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6969/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## Docker Compose Examples

### Example 1: Complete Media Stack

Full stack with qBittorrent, Radarr, Sonarr, and qBitrr:

```yaml
version: "3.8"

networks:
  media:
    driver: bridge

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
      - ./qbittorrent:/config
      - /mnt/storage/downloads:/downloads
    ports:
      - "8080:8080"
      - "6881:6881"
      - "6881:6881/udp"
    networks:
      - media
    restart: unless-stopped

  radarr:
    image: lscr.io/linuxserver/radarr:latest
    container_name: radarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./radarr:/config
      - /mnt/storage/downloads:/downloads
      - /mnt/storage/movies:/movies
    ports:
      - "7878:7878"
    networks:
      - media
    restart: unless-stopped

  sonarr:
    image: lscr.io/linuxserver/sonarr:latest
    container_name: sonarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./sonarr:/config
      - /mnt/storage/downloads:/downloads
      - /mnt/storage/tv:/tv
    ports:
      - "8989:8989"
    networks:
      - media
    restart: unless-stopped

  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./qbitrr:/config
      - /mnt/storage/downloads:/downloads
    ports:
      - "6969:6969"
    networks:
      - media
    depends_on:
      - qbittorrent
      - radarr
      - sonarr
    restart: unless-stopped
```

### Example 2: With Overseerr

Add request management:

```yaml
version: "3.8"

networks:
  media:
    driver: bridge

services:
  # ... qbittorrent, radarr, sonarr from above ...

  overseerr:
    image: lscr.io/linuxserver/overseerr:latest
    container_name: overseerr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./overseerr:/config
    ports:
      - "5055:5055"
    networks:
      - media
    restart: unless-stopped

  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./qbitrr:/config
      - /mnt/storage/downloads:/downloads
    ports:
      - "6969:6969"
    networks:
      - media
    depends_on:
      - qbittorrent
      - radarr
      - sonarr
      - overseerr
    restart: unless-stopped
```

### Example 3: With VPN

Run qBittorrent through VPN:

```yaml
version: "3.8"

services:
  vpn:
    image: qmcgaw/gluetun
    container_name: vpn
    cap_add:
      - NET_ADMIN
    environment:
      - VPN_SERVICE_PROVIDER=nordvpn
      - VPN_TYPE=openvpn
      - OPENVPN_USER=your_username
      - OPENVPN_PASSWORD=your_password
      - SERVER_COUNTRIES=United States
    volumes:
      - ./gluetun:/gluetun
    ports:
      - "8080:8080"  # qBittorrent WebUI
      - "6881:6881"  # qBittorrent
      - "6881:6881/udp"
    restart: unless-stopped

  qbittorrent:
    image: lscr.io/linuxserver/qbittorrent:latest
    container_name: qbittorrent
    network_mode: "service:vpn"  # Route through VPN
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
      - WEBUI_PORT=8080
    volumes:
      - ./qbittorrent:/config
      - /mnt/storage/downloads:/downloads
    depends_on:
      - vpn
    restart: unless-stopped

  # radarr, sonarr, qbitrr don't need VPN
  radarr:
    image: lscr.io/linuxserver/radarr:latest
    # ... normal config, NOT through VPN
```

### Example 4: With Traefik Reverse Proxy

```yaml
version: "3.8"

networks:
  web:
    external: true
  media:
    driver: bridge

services:
  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/New_York
    volumes:
      - ./qbitrr:/config
      - /mnt/storage/downloads:/downloads
    networks:
      - web
      - media
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.qbitrr.rule=Host(`qbitrr.yourdomain.com`)"
      - "traefik.http.routers.qbitrr.entrypoints=websecure"
      - "traefik.http.routers.qbitrr.tls.certresolver=letsencrypt"
      - "traefik.http.services.qbitrr.loadbalancer.server.port=6969"
    restart: unless-stopped
```

## Best Practices

### 1. Use Named Volumes for Config

```yaml
volumes:
  qbitrr-config:

services:
  qbitrr:
    volumes:
      - qbitrr-config:/config  # Persistent, managed by Docker
      - /mnt/storage/downloads:/downloads
```

### 2. Set Proper Restart Policies

```yaml
services:
  qbitrr:
    restart: unless-stopped  # Don't restart if manually stopped
```

### 3. Use Health Checks

```yaml
services:
  qbitrr:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6969/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### 4. Enable Logging Limits

```yaml
services:
  qbitrr:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 5. Use Docker Secrets for API Keys

```yaml
secrets:
  radarr_api_key:
    file: ./secrets/radarr_api_key.txt

services:
  qbitrr:
    secrets:
      - radarr_api_key
    environment:
      - RADARR_API_KEY_FILE=/run/secrets/radarr_api_key
```

## Migration from Other Setups

### From Native Install

1. **Copy config:**
   ```bash
   cp ~/.config/qBitrr/config.toml /path/to/docker/config/
   ```

2. **Copy database:**
   ```bash
   cp ~/.config/qBitrr/*.db /path/to/docker/config/
   ```

3. **Update paths in config.toml:**
   - Change `/home/user/downloads` to `/downloads`

4. **Start Docker container**

### From Unraid

1. **Add qBitrr from Community Applications**
2. **Map paths to match existing setup**
3. **Import existing config if desired**

## Performance Tips

### 1. Optimize Volume Performance

**Use delegated/cached mounts on macOS:**
```yaml
volumes:
  - /mnt/storage/downloads:/downloads:delegated
```

### 2. Reduce Image Size

**Use specific version tags:**
```yaml
image: feramance/qbitrr:5.5.5  # Not latest
```

### 3. Limit Log Output

```yaml
environment:
  - QBITRR_LOG_LEVEL=INFO  # Not DEBUG
```

### 4. Use Local DNS

```yaml
services:
  qbitrr:
    dns:
      - 1.1.1.1
      - 1.0.0.1
    extra_hosts:
      - "radarr:192.168.1.100"
      - "qbittorrent:192.168.1.100"
```

## Next Steps

Ready to configure qBitrr?

1. **Configure qBittorrent** - [qBittorrent Setup Guide](../../configuration/qbittorrent.md)
2. **Configure Arr Instances** - [Arr Configuration Guide](../../configuration/arr/index.md)
3. **First Run** - [Complete the First Run Setup](../first-run.md)
4. **Troubleshooting** - [Docker-Specific Issues](../../troubleshooting/docker.md)

---

## Related Documentation

- [Configuration File Reference](../../configuration/config-file.md) - Complete TOML syntax
- [Environment Variables](../../configuration/environment.md) - All ENV vars
- [Path Mapping Guide](../../troubleshooting/path-mapping.md) - Fix path issues
- [Docker Troubleshooting](../../troubleshooting/docker.md) - Comprehensive Docker guide
- [WebUI Access](../../webui/index.md) - Access the web interface
