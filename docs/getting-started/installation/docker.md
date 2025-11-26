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

Check logs:
```bash
docker logs qbitrr
```

Common issues:
- Port 6969 already in use
- Config directory permissions
- Invalid config.toml syntax

### Can't Connect to qBittorrent/Arr

1. **Check if containers can communicate:**
   ```bash
   docker exec qbitrr ping qbittorrent
   ```

2. **Use container names or IPs:**
   ```toml
   [Settings.Qbittorrent]
   Host = "http://qbittorrent:8080"  # Use container name
   ```

3. **Ensure they're on the same Docker network**

### Permission Issues

If you get "Permission denied" errors:

1. **Check PUID/PGID:**
   ```bash
   id yourusername
   ```
   Use the output values for PUID and PGID

2. **Fix ownership:**
   ```bash
   sudo chown -R 1000:1000 /path/to/config
   ```

### Path Not Found Errors

Verify volume mappings match across all containers:

```bash
docker exec qbitrr ls -la /downloads
docker exec qbittorrent ls -la /downloads
docker exec radarr ls -la /downloads
```

All should show the same files.

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

## Next Steps

- [Configure qBittorrent](../../configuration/qbittorrent.md)
- [Configure Arr Instances](../../configuration/arr/index.md)
- [First Run Guide](../first-run.md)
- [Troubleshooting Docker Issues](../../troubleshooting/docker.md)
