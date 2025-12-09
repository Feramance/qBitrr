# CLI Reference

Command-line interface reference for qBitrr. This page documents all available commands, options, and environment variables.

---

## Basic Usage

### Starting qBitrr

=== "Docker"

    ```bash
    docker run -d \
      --name qbitrr \
      -v /path/to/config:/config \
      -p 6969:6969 \
      feramance/qbitrr:latest
    ```

=== "systemd"

    ```bash
    # Start the service
    sudo systemctl start qbitrr

    # Enable on boot
    sudo systemctl enable qbitrr

    # Check status
    sudo systemctl status qbitrr
    ```

=== "pip"

    ```bash
    # Start qBitrr
    qbitrr

    # Run in background with nohup
    nohup qbitrr &
    ```

=== "Binary"

    ```bash
    # Make executable
    chmod +x qbitrr

    # Run
    ./qbitrr
    ```

---

## Command-Line Options

### `qbitrr`

Main command to start qBitrr.

```bash
qbitrr [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--config PATH` | Path to config.toml file | `~/config/config.toml` (native)<br>`/config/config.toml` (Docker) |
| `--gen-config` | Generate default configuration file and exit | - |
| `--version` | Show version information and exit | - |
| `--help` | Show help message and exit | - |

**Examples:**

```bash
# Start with default config
qbitrr

# Use custom config location
qbitrr --config /opt/qbitrr/config.toml

# Generate default config
qbitrr --gen-config

# Show version
qbitrr --version
```

---

### `--gen-config`

Generate a default `config.toml` file with all available settings.

```bash
qbitrr --gen-config
```

**Behavior:**

- Creates `config.toml` in the default location (`~/config/config.toml` or `/config/config.toml`)
- File contains all configuration sections with default values
- Includes helpful comments for each setting
- Will **not overwrite** existing config files

**Output:**

```
Generated default configuration at: /config/config.toml
Please edit the file and configure your Arr instances and qBittorrent connection.
```

**Next Steps:**

1. Edit `config.toml` with your settings
2. Configure at least one Arr instance
3. Set qBittorrent connection details
4. Run `qbitrr` to start

---

### `--config PATH`

Specify a custom configuration file location.

```bash
qbitrr --config /path/to/custom/config.toml
```

**Use Cases:**

- Running multiple qBitrr instances with different configs
- Testing configuration changes without affecting production
- Storing config in a non-standard location

**Example:**

```bash
# Development instance
qbitrr --config /opt/qbitrr/dev-config.toml

# Production instance
qbitrr --config /opt/qbitrr/prod-config.toml
```

---

### `--version`

Display qBitrr version information and exit.

```bash
qbitrr --version
```

**Output:**

```
qBitrr version 5.5.5
Python version 3.12.0
```

---

### `--help`

Display help message with all available options.

```bash
qbitrr --help
```

**Output:**

```
Usage: qbitrr [OPTIONS]

qBitrr - Intelligent automation for qBittorrent and *Arr apps

Options:
  --config PATH      Path to configuration file
  --gen-config       Generate default configuration file
  --version          Show version information
  --help             Show this message and exit
```

---

## Environment Variables

qBitrr supports configuration via environment variables, useful for Docker deployments and CI/CD.

### General Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `QBITRR_CONFIG` | Path to config.toml | `~/config/config.toml` | `/custom/path/config.toml` |
| `QBITRR_HOME` | qBitrr home directory | `~` | `/opt/qbitrr` |
| `QBITRR_LOG_LEVEL` | Logging level | `INFO` | `DEBUG` |
| `QBITRR_DOCKER_RUNNING` | Docker environment marker | - | `69420` (set automatically) |

**Example:**

```bash
export QBITRR_CONFIG=/custom/config.toml
export QBITRR_LOG_LEVEL=DEBUG
qbitrr
```

---

### Configuration Overrides

Environment variables can override config.toml settings using a special naming convention:

**Format:** `QBITRR_SECTION__KEY=value`

**Syntax:**
- Prefix: `QBITRR_`
- Section separator: `__` (double underscore)
- Nested sections: Use additional `__`
- Array indices: Use `__N__` where N is the index

**Examples:**

```bash
# Override WebUI port
QBITRR_WEBUI__PORT=8080

# Override qBittorrent host
QBITRR_SETTINGS__QBITTORRENT__HOST=192.168.1.100

# Override Radarr API key
QBITRR_RADARR__0__APIKEY=abc123def456

# Enable auto-restart
QBITRR_SETTINGS__AUTORESTARTPROCESSES=true
```

**Docker Compose Example:**

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    environment:
      - QBITRR_WEBUI__PORT=8080
      - QBITRR_WEBUI__HOST=0.0.0.0
      - QBITRR_SETTINGS__LOGLEVEL=DEBUG
      - QBITRR_SETTINGS__QBITTORRENT__HOST=qbittorrent
      - QBITRR_SETTINGS__QBITTORRENT__PORT=8080
    volumes:
      - ./config:/config
```

---

### Docker-Specific Variables

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `PUID` | User ID for file permissions | `1000` | Linux/Docker only |
| `PGID` | Group ID for file permissions | `1000` | Linux/Docker only |
| `TZ` | Timezone | `UTC` | e.g., `America/New_York` |
| `UMASK` | File creation mask | `022` | e.g., `002` for group write |

**Example:**

```bash
docker run -d \
  --name qbitrr \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=America/New_York \
  -e UMASK=002 \
  -v /path/to/config:/config \
  feramance/qbitrr:latest
```

---

## Exit Codes

qBitrr uses standard Unix exit codes to indicate success or failure.

| Code | Meaning | Description |
|------|---------|-------------|
| `0` | Success | qBitrr exited normally (graceful shutdown) |
| `1` | General error | Unspecified error occurred |
| `2` | Configuration error | Invalid or missing configuration |
| `3` | Connection error | Cannot connect to qBittorrent or Arr instance |
| `4` | Database error | Database corruption or access issue |
| `130` | SIGINT | User interrupted (Ctrl+C) |
| `143` | SIGTERM | Terminated by system (systemd, Docker) |

**Examples:**

```bash
# Check exit code
qbitrr
echo $?  # 0 = success, non-zero = error

# systemd (check status)
sudo systemctl status qbitrr
# ExitCode: 0 = normal, 2 = config error, etc.
```

---

## Signals

qBitrr responds to Unix signals for process control.

| Signal | Name | Behavior |
|--------|------|----------|
| `SIGTERM` | Terminate | Graceful shutdown (recommended) |
| `SIGINT` | Interrupt | Graceful shutdown (Ctrl+C) |
| `SIGHUP` | Hang up | Reload configuration (planned feature) |
| `SIGKILL` | Kill | Immediate termination (not recommended) |

**Examples:**

```bash
# Graceful shutdown
kill -TERM $(pidof qbitrr)

# Force quit (Ctrl+C)
# Press Ctrl+C in terminal

# systemd stop (sends SIGTERM)
sudo systemctl stop qbitrr
```

**Graceful Shutdown Process:**

1. Receive SIGTERM or SIGINT
2. Stop accepting new torrents
3. Complete ongoing operations
4. Flush database writes
5. Terminate Arr manager processes
6. Shutdown WebUI
7. Exit with code 0

**Timeout:** 30 seconds (after which SIGKILL is sent automatically by systemd/Docker)

---

## Configuration File Locations

qBitrr searches for `config.toml` in these locations (in order):

1. Path specified by `--config` option
2. Path specified by `QBITRR_CONFIG` environment variable
3. `/config/config.toml` (Docker)
4. `~/config/config.toml` (native)
5. `~/.config/qBitrr/config.toml` (pip install)

**Priority:** Earlier locations override later ones.

**Example:**

```bash
# Explicit path takes highest priority
qbitrr --config /custom/config.toml

# Environment variable is second priority
export QBITRR_CONFIG=/env/config.toml
qbitrr

# Default location is last resort
qbitrr  # Uses ~/config/config.toml
```

---

## Logging

### Log Output

qBitrr writes logs to both console (stdout/stderr) and files.

**Console Output:**

- **Docker:** `docker logs qbitrr`
- **systemd:** `journalctl -u qbitrr -f`
- **Direct:** Printed to terminal

**File Output:**

| File | Location | Content |
|------|----------|---------|
| `Main.log` | `~/config/logs/` or `/config/logs/` | Main qBitrr logs, process management |
| `WebUI.log` | `~/config/logs/` | WebUI and API requests |
| `{ArrName}.log` | `~/config/logs/` | Per-Arr instance logs (e.g., `Radarr-Movies.log`) |

### Log Levels

Control log verbosity with `Settings.LogLevel` in config.toml or environment variable:

```bash
# Environment variable
export QBITRR_SETTINGS__LOGLEVEL=DEBUG
qbitrr

# Or in config.toml
[Settings]
LogLevel = "DEBUG"
```

**Levels:**

- `DEBUG` - Verbose output (all operations)
- `INFO` - Normal operations (default)
- `WARNING` - Potential issues
- `ERROR` - Errors that don't stop execution
- `CRITICAL` - Fatal errors

---

## Advanced Usage

### Running Multiple Instances

Run multiple qBitrr instances with separate configs:

```bash
# Instance 1: 4K content
qbitrr --config /opt/qbitrr/4k-config.toml &

# Instance 2: Standard content
qbitrr --config /opt/qbitrr/hd-config.toml &
```

**Requirements:**

- Separate config files
- Different WebUI ports
- Different database files
- Non-overlapping categories

**Example configs:**

=== "4k-config.toml"

    ```toml
    [Settings]
    WebUIPort = 6969

    [[Radarr]]
    Name = "Radarr-4K"
    URI = "http://localhost:7879"
    Category = "radarr-4k"
    ```

=== "hd-config.toml"

    ```toml
    [Settings]
    WebUIPort = 6970

    [[Radarr]]
    Name = "Radarr-HD"
    URI = "http://localhost:7878"
    Category = "radarr-hd"
    ```

---

### Debugging

Enable debug logging and run in foreground:

```bash
# Set debug level
export QBITRR_SETTINGS__LOGLEVEL=DEBUG

# Run in foreground (not daemonized)
qbitrr

# Or with systemd
sudo systemctl stop qbitrr
sudo -u qbitrr QBITRR_SETTINGS__LOGLEVEL=DEBUG qbitrr
```

**Debug Output:**

- All API calls to qBittorrent and Arr instances
- Database queries
- Torrent processing steps
- Health check details
- Search activity

---

### Testing Configuration

Test configuration without starting processes:

```bash
# Generate config
qbitrr --gen-config

# Edit config
vim ~/config/config.toml

# Validate config (dry run)
qbitrr --config ~/config/config.toml
# Watch for configuration errors in output
# Press Ctrl+C to exit
```

**Look for:**

- `Configuration loaded successfully`
- `Connected to qBittorrent`
- `Registered Arr instance: {Name}`
- `WebUI started on http://{host}:{port}`

**Common Errors:**

- `Config key 'X' in 'Y' requires a value` - Missing required setting
- `Could not connect to qBittorrent` - Wrong host/port/credentials
- `Could not connect to Arr instance` - Wrong URI/API key

---

## Integration with System Services

### systemd

**Service File:** `/etc/systemd/system/qbitrr.service`

```ini
[Unit]
Description=qBitrr - qBittorrent and Arr Integration
After=network.target

[Service]
Type=simple
User=qbitrr
Group=qbitrr
WorkingDirectory=/home/qbitrr
ExecStart=/usr/local/bin/qbitrr
Restart=on-failure
RestartSec=10s
StartLimitBurst=5
StartLimitIntervalSec=300
Environment="QBITRR_CONFIG=/home/qbitrr/config/config.toml"

[Install]
WantedBy=multi-user.target
```

**Commands:**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable on boot
sudo systemctl enable qbitrr

# Start service
sudo systemctl start qbitrr

# Check status
sudo systemctl status qbitrr

# View logs
journalctl -u qbitrr -f

# Restart
sudo systemctl restart qbitrr

# Stop
sudo systemctl stop qbitrr
```

---

### Docker

**Docker Run:**

```bash
docker run -d \
  --name qbitrr \
  --restart unless-stopped \
  -v /path/to/config:/config \
  -v /path/to/downloads:/downloads \
  -p 6969:6969 \
  -e TZ=America/New_York \
  -e QBITRR_SETTINGS__LOGLEVEL=INFO \
  feramance/qbitrr:latest
```

**Docker Compose:**

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    restart: unless-stopped
    ports:
      - "6969:6969"
    volumes:
      - ./config:/config
      - /path/to/downloads:/downloads
    environment:
      - TZ=America/New_York
      - PUID=1000
      - PGID=1000
      - QBITRR_SETTINGS__LOGLEVEL=INFO
```

**Commands:**

```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f qbitrr

# Restart
docker-compose restart qbitrr

# Stop
docker-compose stop qbitrr

# Update
docker-compose pull qbitrr
docker-compose up -d qbitrr
```

---

## Troubleshooting CLI Issues

### Command Not Found

**Symptoms:** `qbitrr: command not found`

**Solutions:**

=== "pip Install"

    ```bash
    # Ensure pip bin directory is in PATH
    export PATH="$HOME/.local/bin:$PATH"

    # Add to .bashrc or .zshrc
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    source ~/.bashrc
    ```

=== "Binary Install"

    ```bash
    # Move to PATH location
    sudo mv qbitrr /usr/local/bin/
    sudo chmod +x /usr/local/bin/qbitrr
    ```

---

### Permission Denied

**Symptoms:** `Permission denied` when running qbitrr

**Solutions:**

```bash
# Make binary executable
chmod +x qbitrr

# Or run with python directly
python -m qBitrr.main

# For systemd, check service user permissions
sudo -u qbitrr qbitrr  # Test as service user
```

---

### Config Not Found

**Symptoms:** `Configuration file not found`

**Solutions:**

```bash
# Generate default config
qbitrr --gen-config

# Specify config location
qbitrr --config /path/to/config.toml

# Set environment variable
export QBITRR_CONFIG=/path/to/config.toml
qbitrr
```

---

## Next Steps

- [Configuration File Reference](../configuration/config-file.md)
- [Environment Variables](../configuration/environment.md)
- [Installation Guides](../getting-started/installation/index.md)
- [Troubleshooting](../troubleshooting/index.md)
