# Environment Variables

qBitrr supports environment variable overrides for configuration settings, making it easy to deploy and manage in containerized environments like Docker, Kubernetes, or systemd services.

---

## Overview

Environment variables override corresponding settings in `config.toml`, providing:

- **Container-native configuration** without editing files
- **Secret management** for sensitive values (passwords, API keys)
- **Dynamic configuration** based on deployment environment
- **CI/CD integration** for automated deployments

**Priority:**

```
Environment Variable > config.toml > Default Value
```

If an environment variable is set, it takes precedence over the config file.

---

## Naming Convention

All environment variables use the `QBITRR_` prefix followed by the section and key name in SCREAMING_SNAKE_CASE.

**Format:**

```bash
QBITRR_<SECTION>_<KEY>=value
```

**Examples:**

| Config File | Environment Variable |
|-------------|---------------------|
| `[Settings]`<br>`ConsoleLevel = "INFO"` | `QBITRR_SETTINGS_CONSOLE_LEVEL=INFO` |
| `[qBit]`<br>`Host = "localhost"` | `QBITRR_QBIT_HOST=localhost` |
| `[WebUI]`<br>`Port = 6969` | `QBITRR_WEBUI_PORT=6969` |

---

## Core Settings

### QBITRR_SETTINGS_CONSOLE_LEVEL

**Type:** String
**Default:** `INFO`
**Options:** `CRITICAL`, `ERROR`, `WARNING`, `NOTICE`, `INFO`, `DEBUG`, `TRACE`

Console logging level.

```bash
QBITRR_SETTINGS_CONSOLE_LEVEL=DEBUG
```

---

### QBITRR_SETTINGS_LOGGING

**Type:** Boolean
**Default:** `true`

Enable file logging.

```bash
QBITRR_SETTINGS_LOGGING=true
```

**Boolean Values:**

- `true`, `yes`, `y`, `on`, `1` → Enable
- `false`, `no`, `n`, `off`, `0` → Disable

---

### QBITRR_SETTINGS_COMPLETED_DOWNLOAD_FOLDER

**Type:** String
**Required:** Yes

qBittorrent's completed download folder path.

```bash
QBITRR_SETTINGS_COMPLETED_DOWNLOAD_FOLDER=/downloads/complete
```

!!! warning "Path Format"
    Use forward slashes (`/`) even on Windows. Replace backslashes (`\`) with forward slashes.

---

### QBITRR_SETTINGS_FREE_SPACE

**Type:** String
**Default:** `-1` (disabled)

Minimum free space to maintain (K/M/G/T units).

```bash
QBITRR_SETTINGS_FREE_SPACE=100G
```

**Examples:**

```bash
QBITRR_SETTINGS_FREE_SPACE=50G   # 50 gigabytes
QBITRR_SETTINGS_FREE_SPACE=500M  # 500 megabytes
QBITRR_SETTINGS_FREE_SPACE=-1    # Disabled
```

---

### QBITRR_SETTINGS_FREE_SPACE_FOLDER

**Type:** String
**Default:** `CHANGE_ME`

Folder to monitor for free space.

```bash
QBITRR_SETTINGS_FREE_SPACE_FOLDER=/downloads
```

---

### QBITRR_SETTINGS_AUTO_PAUSE_RESUME

**Type:** Boolean
**Default:** `true`

Enable automatic pause/resume of torrents based on free space.

```bash
QBITRR_SETTINGS_AUTO_PAUSE_RESUME=true
```

---

### QBITRR_SETTINGS_NO_INTERNET_SLEEP_TIMER

**Type:** Integer
**Default:** `15`

Seconds to wait when internet connection is lost.

```bash
QBITRR_SETTINGS_NO_INTERNET_SLEEP_TIMER=30
```

---

### QBITRR_SETTINGS_LOOP_SLEEP_TIMER

**Type:** Integer
**Default:** `5`

Seconds between torrent processing loops.

```bash
QBITRR_SETTINGS_LOOP_SLEEP_TIMER=10
```

---

### QBITRR_SETTINGS_SEARCH_LOOP_DELAY

**Type:** Integer
**Default:** `-1` (disabled)

Seconds to sleep between posting search commands.

```bash
QBITRR_SETTINGS_SEARCH_LOOP_DELAY=300
```

---

### QBITRR_SETTINGS_FAILED_CATEGORY

**Type:** String
**Default:** `failed`

qBittorrent category for failed torrents.

```bash
QBITRR_SETTINGS_FAILED_CATEGORY=failed
```

---

### QBITRR_SETTINGS_RECHECK_CATEGORY

**Type:** String
**Default:** `recheck`

qBittorrent category for torrents requiring recheck.

```bash
QBITRR_SETTINGS_RECHECK_CATEGORY=recheck
```

---

### QBITRR_SETTINGS_TAGLESS

**Type:** Boolean
**Default:** `false`

Disable tagging entirely (process all torrents regardless of tags).

```bash
QBITRR_SETTINGS_TAGLESS=false
```

---

### QBITRR_SETTINGS_IGNORE_TORRENTS_YOUNGER_THAN

**Type:** Integer
**Default:** `180` (3 minutes)

Seconds to wait before processing new torrents.

```bash
QBITRR_SETTINGS_IGNORE_TORRENTS_YOUNGER_THAN=300
```

---

### QBITRR_SETTINGS_PING_URLS

**Type:** List (comma-separated)
**Default:** `one.one.one.one,dns.google.com`

URLs to ping for internet connectivity checks.

```bash
QBITRR_SETTINGS_PING_URLS=one.one.one.one,dns.google.com,cloudflare.com
```

---

### QBITRR_SETTINGS_FFPROBE_AUTO_UPDATE

**Type:** Boolean
**Default:** `true`

Enable automatic FFprobe binary updates.

```bash
QBITRR_SETTINGS_FFPROBE_AUTO_UPDATE=true
```

---

### QBITRR_SETTINGS_AUTO_UPDATE_ENABLED

**Type:** Boolean
**Default:** `false`

Enable automatic qBitrr updates on a schedule.

```bash
QBITRR_SETTINGS_AUTO_UPDATE_ENABLED=true
```

---

### QBITRR_SETTINGS_AUTO_UPDATE_CRON

**Type:** String
**Default:** `0 3 * * 0` (weekly Sunday 3 AM)

Cron expression for auto-update schedule.

```bash
QBITRR_SETTINGS_AUTO_UPDATE_CRON="0 3 * * *"
```

---

## qBittorrent Settings

### QBITRR_QBIT_DISABLED

**Type:** Boolean
**Default:** `false`

Disable qBittorrent integration (for testing).

```bash
QBITRR_QBIT_DISABLED=false
```

---

### QBITRR_QBIT_HOST

**Type:** String
**Default:** `localhost`

qBittorrent WebUI hostname or IP.

```bash
QBITRR_QBIT_HOST=qbittorrent
```

---

### QBITRR_QBIT_PORT

**Type:** Integer
**Default:** `8080`

qBittorrent WebUI port.

```bash
QBITRR_QBIT_PORT=8080
```

---

### QBITRR_QBIT_USERNAME

**Type:** String
**Default:** `CHANGE_ME`

qBittorrent WebUI username.

```bash
QBITRR_QBIT_USERNAME=CHANGE_ME
```

---

### QBITRR_QBIT_PASSWORD

**Type:** String
**Default:** `CHANGE_ME`

qBittorrent WebUI password.

```bash
QBITRR_QBIT_PASSWORD=CHANGE_ME
```

!!! warning "Security"
    Storing passwords in environment variables is safer than in config files, but consider using Docker secrets or Kubernetes secrets for production.

---

## Advanced Overrides

### QBITRR_OVERRIDES_SEARCH_ONLY

**Type:** Boolean
**Default:** `false`

Only run search loops (skip torrent processing).

```bash
QBITRR_OVERRIDES_SEARCH_ONLY=true
```

**Use Case:** Separate search and processing instances for scaling.

---

### QBITRR_OVERRIDES_PROCESSING_ONLY

**Type:** Boolean
**Default:** `false`

Only process torrents (skip search loops).

```bash
QBITRR_OVERRIDES_PROCESSING_ONLY=true
```

**Use Case:** Dedicated processing instance for high-volume downloads.

---

### QBITRR_OVERRIDES_DATA_PATH

**Type:** String
**Default:** Platform-dependent

Override the data directory path.

```bash
QBITRR_OVERRIDES_DATA_PATH=/custom/config/path
```

**Default Locations:**

- **Linux:** `~/.local/share/qBitrr`
- **macOS:** `~/Library/Application Support/qBitrr`
- **Windows:** `%APPDATA%\qBitrr`
- **Docker:** `/config`

---

## Docker Examples

### Basic Docker Run

```bash
docker run -d \
  --name qbitrr \
  -e QBITRR_SETTINGS_CONSOLE_LEVEL=INFO \
  -e QBITRR_SETTINGS_COMPLETED_DOWNLOAD_FOLDER=/downloads/complete \
  -e QBITRR_QBIT_HOST=qbittorrent \
  -e QBITRR_QBIT_PORT=8080 \
  -e QBITRR_QBIT_USERNAME=admin \
  -e QBITRR_QBIT_PASSWORD=supersecret \
  -v /host/config:/config \
  -v /host/downloads:/downloads \
  feramance/qbitrr:latest
```

---

### Docker Compose

```yaml
version: "3"
services:
  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    restart: unless-stopped
    volumes:
      - ./config:/config
      - /mnt/downloads:/downloads
    environment:
      # Core Settings
      QBITRR_SETTINGS_CONSOLE_LEVEL: DEBUG
      QBITRR_SETTINGS_COMPLETED_DOWNLOAD_FOLDER: /downloads/complete
      QBITRR_SETTINGS_FREE_SPACE: 100G
      QBITRR_SETTINGS_FREE_SPACE_FOLDER: /downloads
      QBITRR_SETTINGS_AUTO_PAUSE_RESUME: "true"

      # qBittorrent
      QBITRR_QBIT_HOST: qbittorrent
      QBITRR_QBIT_PORT: 8080
      QBITRR_QBIT_USERNAME: admin
      QBITRR_QBIT_PASSWORD: ${QBIT_PASSWORD}  # From .env file

      # Auto-Update
      QBITRR_SETTINGS_AUTO_UPDATE_ENABLED: "false"  # Use Watchtower instead
```

**`.env` file:**

```bash
QBIT_PASSWORD=mysecretpassword
```

---

### Docker Compose with Secrets

```yaml
version: "3.8"
services:
  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    restart: unless-stopped
    volumes:
      - ./config:/config
      - /mnt/downloads:/downloads
    environment:
      QBITRR_QBIT_PASSWORD_FILE: /run/secrets/qbit_password
    secrets:
      - qbit_password

secrets:
  qbit_password:
    file: ./secrets/qbit_password.txt
```

!!! note "Secret Files"
    qBitrr supports `_FILE` suffix for sensitive variables. The value will be read from the file path specified.

---

## Kubernetes Example

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: qbitrr-config
  namespace: media
data:
  QBITRR_SETTINGS_CONSOLE_LEVEL: "INFO"
  QBITRR_SETTINGS_COMPLETED_DOWNLOAD_FOLDER: "/downloads/complete"
  QBITRR_SETTINGS_FREE_SPACE: "100G"
  QBITRR_SETTINGS_FREE_SPACE_FOLDER: "/downloads"
  QBITRR_QBIT_HOST: "qbittorrent.media.svc.cluster.local"
  QBITRR_QBIT_PORT: "8080"
  QBITRR_QBIT_USERNAME: "admin"
```

---

### Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: qbitrr-secret
  namespace: media
type: Opaque
stringData:
  QBITRR_QBIT_PASSWORD: "supersecretpassword"
```

---

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qbitrr
  namespace: media
spec:
  replicas: 1
  selector:
    matchLabels:
      app: qbitrr
  template:
    metadata:
      labels:
        app: qbitrr
    spec:
      containers:
      - name: qbitrr
        image: feramance/qbitrr:latest
        envFrom:
        - configMapRef:
            name: qbitrr-config
        - secretRef:
            name: qbitrr-secret
        volumeMounts:
        - name: config
          mountPath: /config
        - name: downloads
          mountPath: /downloads
      volumes:
      - name: config
        persistentVolumeClaim:
          claimName: qbitrr-config-pvc
      - name: downloads
        persistentVolumeClaim:
          claimName: downloads-pvc
```

---

## Systemd Service Example

**`/etc/systemd/system/qbitrr.service`:**

```ini
[Unit]
Description=qBitrr - qBittorrent and *arr Integration
After=network.target

[Service]
Type=simple
User=media
Group=media
WorkingDirectory=/opt/qbitrr

# Environment Variables
Environment="QBITRR_SETTINGS_CONSOLE_LEVEL=INFO"
Environment="QBITRR_SETTINGS_COMPLETED_DOWNLOAD_FOLDER=/mnt/downloads/complete"
Environment="QBITRR_SETTINGS_FREE_SPACE=100G"
Environment="QBITRR_SETTINGS_FREE_SPACE_FOLDER=/mnt/downloads"
Environment="QBITRR_QBIT_HOST=localhost"
Environment="QBITRR_QBIT_PORT=8080"
Environment="QBITRR_QBIT_USERNAME=admin"
Environment="QBITRR_QBIT_PASSWORD=secretpassword"

# Optional: Load from file
EnvironmentFile=-/etc/qbitrr/environment

ExecStart=/usr/local/bin/qbitrr
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**`/etc/qbitrr/environment`:**

```bash
QBITRR_SETTINGS_AUTO_UPDATE_ENABLED=true
QBITRR_SETTINGS_AUTO_UPDATE_CRON="0 3 * * 0"
```

**Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable qbitrr
sudo systemctl start qbitrr
```

---

## Binary Installation Example

**Linux/macOS (bash):**

```bash
#!/bin/bash
export QBITRR_SETTINGS_CONSOLE_LEVEL=DEBUG
export QBITRR_SETTINGS_COMPLETED_DOWNLOAD_FOLDER=/downloads/complete
export QBITRR_QBIT_HOST=localhost
export QBITRR_QBIT_PORT=8080
export QBITRR_QBIT_USERNAME=admin
export QBITRR_QBIT_PASSWORD=password

./qbitrr
```

**Windows (PowerShell):**

```powershell
$env:QBITRR_SETTINGS_CONSOLE_LEVEL="DEBUG"
$env:QBITRR_SETTINGS_COMPLETED_DOWNLOAD_FOLDER="C:/Downloads/Complete"
$env:QBITRR_QBIT_HOST="localhost"
$env:QBITRR_QBIT_PORT="8080"
$env:QBITRR_QBIT_USERNAME="admin"
$env:QBITRR_QBIT_PASSWORD="password"

.\qbitrr.exe
```

---

## Troubleshooting

### Environment Variable Not Working

**Symptom:** Setting environment variable has no effect

**Check:**

1. **Verify syntax:**
   ```bash
   echo $QBITRR_SETTINGS_CONSOLE_LEVEL
   ```

2. **Check precedence:**
   Environment variables override config.toml. If config.toml has a value, the env var must be explicitly set.

3. **Restart required:**
   Changes to environment variables require qBitrr restart.

4. **Case sensitivity:**
   Variable names are case-sensitive: `QBITRR_SETTINGS_CONSOLE_LEVEL` not `qbitrr_settings_console_level`

---

### Boolean Values Not Recognized

**Symptom:** Boolean environment variable not working as expected

**Accepted values:**

- **True:** `true`, `yes`, `y`, `on`, `1`
- **False:** `false`, `no`, `n`, `off`, `0`

**Incorrect:**

```bash
QBITRR_SETTINGS_LOGGING=True  # Capital T not recognized
```

**Correct:**

```bash
QBITRR_SETTINGS_LOGGING=true
```

---

### List Values Not Parsing

**Symptom:** Comma-separated list not working

**Correct format:**

```bash
QBITRR_SETTINGS_PING_URLS=google.com,github.com,cloudflare.com
```

**No spaces:**

```bash
# Incorrect
QBITRR_SETTINGS_PING_URLS="google.com, github.com"

# Correct
QBITRR_SETTINGS_PING_URLS="google.com,github.com"
```

---

### Docker Environment Variables Not Applied

**Symptom:** Environment variables in `docker-compose.yml` ignored

**Check YAML syntax:**

```yaml
environment:
  # Correct (quoted)
  QBITRR_SETTINGS_CONSOLE_LEVEL: "INFO"
  QBITRR_SETTINGS_AUTO_PAUSE_RESUME: "true"

  # Incorrect (unquoted booleans interpreted as YAML booleans)
  QBITRR_SETTINGS_AUTO_PAUSE_RESUME: true  # Becomes Python True, not string "true"
```

**Always quote boolean strings:**

```yaml
QBITRR_SETTINGS_AUTO_PAUSE_RESUME: "true"  # Correct
```

---

## Best Practices

### 1. Use Environment Variables for Secrets

```yaml
# config.toml - Public configuration
[Settings]
ConsoleLevel = "INFO"
CompletedDownloadFolder = "/downloads/complete"

# Environment - Sensitive data
QBITRR_QBIT_PASSWORD=secretpassword
```

---

### 2. Use `.env` Files for Local Development

```bash
# .env
QBITRR_SETTINGS_CONSOLE_LEVEL=DEBUG
QBITRR_QBIT_HOST=localhost
QBITRR_QBIT_USERNAME=admin
QBITRR_QBIT_PASSWORD=password
```

**Load with docker-compose:**

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    env_file:
      - .env
```

---

### 3. Document Environment Overrides

Include a README or `.env.example` file:

```bash
# .env.example
# Copy to .env and fill in values

# qBittorrent Connection
QBITRR_QBIT_HOST=localhost
QBITRR_QBIT_PORT=8080
QBITRR_QBIT_USERNAME=admin
QBITRR_QBIT_PASSWORD=changeme

# Paths (adjust for your system)
QBITRR_SETTINGS_COMPLETED_DOWNLOAD_FOLDER=/downloads/complete
QBITRR_SETTINGS_FREE_SPACE_FOLDER=/downloads
```

---

### 4. Validate Configuration on Startup

Check logs for configuration applied:

```bash
docker logs qbitrr | grep -i "config"
```

**Expected output:**

```
[INFO] ConsoleLevel: DEBUG (from environment)
[INFO] qBit.Host: qbittorrent (from environment)
```

---

### 5. Use Kubernetes ConfigMaps for Non-Secrets

Separate public config (ConfigMap) from sensitive data (Secret):

```yaml
# ConfigMap for public settings
QBITRR_SETTINGS_CONSOLE_LEVEL: INFO
QBITRR_QBIT_HOST: qbittorrent

# Secret for passwords
QBITRR_QBIT_PASSWORD: <base64 encoded>
```

---

## Reference

### Complete Environment Variable List

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `QBITRR_SETTINGS_CONSOLE_LEVEL` | String | `INFO` | Console logging level |
| `QBITRR_SETTINGS_LOGGING` | Boolean | `true` | Enable file logging |
| `QBITRR_SETTINGS_COMPLETED_DOWNLOAD_FOLDER` | String | `CHANGE_ME` | Completed downloads folder |
| `QBITRR_SETTINGS_FREE_SPACE` | String | `-1` | Minimum free space (K/M/G/T) |
| `QBITRR_SETTINGS_FREE_SPACE_FOLDER` | String | `CHANGE_ME` | Folder to monitor for free space |
| `QBITRR_SETTINGS_AUTO_PAUSE_RESUME` | Boolean | `true` | Auto pause/resume torrents |
| `QBITRR_SETTINGS_NO_INTERNET_SLEEP_TIMER` | Integer | `15` | Sleep seconds when no internet |
| `QBITRR_SETTINGS_LOOP_SLEEP_TIMER` | Integer | `5` | Sleep seconds between loops |
| `QBITRR_SETTINGS_SEARCH_LOOP_DELAY` | Integer | `-1` | Delay between search commands |
| `QBITRR_SETTINGS_FAILED_CATEGORY` | String | `failed` | Failed torrents category |
| `QBITRR_SETTINGS_RECHECK_CATEGORY` | String | `recheck` | Recheck torrents category |
| `QBITRR_SETTINGS_TAGLESS` | Boolean | `false` | Process all torrents (ignore tags) |
| `QBITRR_SETTINGS_IGNORE_TORRENTS_YOUNGER_THAN` | Integer | `180` | Ignore new torrents (seconds) |
| `QBITRR_SETTINGS_PING_URLS` | List | `one.one.one.one,dns.google.com` | Connectivity check URLs |
| `QBITRR_SETTINGS_FFPROBE_AUTO_UPDATE` | Boolean | `true` | Auto-update FFprobe binary |
| `QBITRR_SETTINGS_AUTO_UPDATE_ENABLED` | Boolean | `false` | Enable qBitrr auto-updates |
| `QBITRR_SETTINGS_AUTO_UPDATE_CRON` | String | `0 3 * * 0` | Auto-update cron schedule |
| `QBITRR_QBIT_DISABLED` | Boolean | `false` | Disable qBittorrent integration |
| `QBITRR_QBIT_HOST` | String | `localhost` | qBittorrent WebUI host |
| `QBITRR_QBIT_PORT` | Integer | `8080` | qBittorrent WebUI port |
| `QBITRR_QBIT_USERNAME` | String | `CHANGE_ME` | qBittorrent username |
| `QBITRR_QBIT_PASSWORD` | String | `CHANGE_ME` | qBittorrent password |
| `QBITRR_OVERRIDES_SEARCH_ONLY` | Boolean | `false` | Only run search loops |
| `QBITRR_OVERRIDES_PROCESSING_ONLY` | Boolean | `false` | Only process torrents |
| `QBITRR_OVERRIDES_DATA_PATH` | String | Platform default | Override data directory |

---

## Related Documentation

- **[Configuration File](config-file.md)** - Complete config.toml reference
- **[Docker Installation](../getting-started/installation/docker.md)** - Docker setup guide
- **[qBittorrent Configuration](qbittorrent.md)** - qBittorrent connection setup

---

## Summary

- All config settings can be overridden with `QBITRR_<SECTION>_<KEY>` environment variables
- Environment variables take precedence over `config.toml`
- Use environment variables for **secrets** (passwords, API keys)
- **Quote boolean strings** in Docker Compose (`"true"`, `"false"`)
- **Comma-separated lists** for multi-value settings (no spaces)
- Restart qBitrr after changing environment variables
