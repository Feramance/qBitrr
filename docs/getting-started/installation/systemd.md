# Systemd Service Setup

Run qBitrr as a systemd service on Linux for automatic startup, restart management, and proper logging.

## Prerequisites

- Linux system with systemd (most modern distributions)
- qBitrr installed via pip (`pip install qBitrr2`)
- Python 3.11 or higher
- Non-root user account (recommended for security)

## Quick Start

```bash
# Create qBitrr user
sudo useradd -r -s /bin/bash -d /opt/qbitrr -m qbitrr

# Install qBitrr
sudo -u qbitrr pip install qBitrr2

# Create directories
sudo mkdir -p /opt/qbitrr/{config,logs}
sudo chown -R qbitrr:qbitrr /opt/qbitrr

# Create service file
sudo nano /etc/systemd/system/qbitrr.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now qbitrr
```

## Installation Steps

### 1. Create Dedicated User

Create a dedicated user for running qBitrr (recommended for security):

```bash
sudo useradd -r -s /bin/bash -d /opt/qbitrr -m qbitrr
```

!!! tip "Why a dedicated user?"
    Running qBitrr as a dedicated user improves security by limiting access to system resources and isolating potential issues.

### 2. Install qBitrr

Install for the qbitrr user:

```bash
sudo -u qbitrr pip install qBitrr2
```

Or install system-wide:

```bash
sudo pip install qBitrr2
```

### 3. Create Directory Structure

```bash
sudo mkdir -p /opt/qbitrr/config
sudo mkdir -p /opt/qbitrr/logs
sudo chown -R qbitrr:qbitrr /opt/qbitrr
```

### 4. Generate Configuration

Run qBitrr once to generate the default configuration:

```bash
sudo -u qbitrr QBITRR_CONFIG_PATH=/opt/qbitrr/config qbitrr
```

Press ++ctrl+c++ to stop, then edit:

```bash
sudo nano /opt/qbitrr/config/config.toml
```

See the [First Run Guide](../quickstart.md) for configuration details.

### 5. Create Systemd Service File

Create the service file:

```bash
sudo nano /etc/systemd/system/qbitrr.service
```

Paste this content:

```ini
[Unit]
Description=qBitrr - Radarr/Sonarr/Lidarr Torrent Manager
Documentation=https://feramance.github.io/qBitrr/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=qbitrr
Group=qbitrr
WorkingDirectory=/opt/qbitrr

# Main process
ExecStart=/usr/bin/python3 -m qBitrr.main

# Environment variables
Environment="QBITRR_CONFIG_PATH=/opt/qbitrr/config"

# Restart policy
Restart=always
RestartSec=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=qbitrr

# Security hardening (optional)
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

!!! warning "Adjust Python Path"
    Find your Python path with `which python3` and update `ExecStart` if needed.

### 6. Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable qbitrr

# Start immediately
sudo systemctl start qbitrr

# Check status
sudo systemctl status qbitrr
```

## Managing the Service

### Check Status

```bash
sudo systemctl status qbitrr
```

Example output:
```
● qbitrr.service - qBitrr - Radarr/Sonarr/Lidarr Torrent Manager
     Loaded: loaded (/etc/systemd/system/qbitrr.service; enabled)
     Active: active (running) since Mon 2025-11-25 10:00:00 UTC
   Main PID: 1234 (python3)
```

### View Logs

=== "Real-time"

    ```bash
    sudo journalctl -u qbitrr -f
    ```

=== "Last 100 lines"

    ```bash
    sudo journalctl -u qbitrr -n 100
    ```

=== "Since boot"

    ```bash
    sudo journalctl -u qbitrr -b
    ```

=== "Specific time range"

    ```bash
    sudo journalctl -u qbitrr \
      --since "2025-01-01 00:00:00" \
      --until "2025-01-01 23:59:59"
    ```

=== "Errors only"

    ```bash
    sudo journalctl -u qbitrr -p err -n 50
    ```

### Start/Stop/Restart

```bash
# Start
sudo systemctl start qbitrr

# Stop
sudo systemctl stop qbitrr

# Restart
sudo systemctl restart qbitrr

# Reload config (if supported)
sudo systemctl reload qbitrr
```

### Enable/Disable Auto-Start

```bash
# Enable auto-start on boot
sudo systemctl enable qbitrr

# Disable auto-start
sudo systemctl disable qbitrr

# Enable and start in one command
sudo systemctl enable --now qbitrr
```

## Auto-Update Behavior

When qBitrr performs an auto-update or manual update via WebUI:

1. **Process replacement**: qBitrr calls `os.execv()` to replace itself with the new version
2. **PID maintained**: The process keeps the same PID
3. **Systemd continues monitoring**: No service interruption
4. **Automatic restart**: `Restart=always` ensures service continues

The `RestartSec=5` setting adds a 5-second delay between restart attempts to prevent rapid restart loops.

## Configuration Options

### Custom Config Location

To use a different config location, update the service file:

```ini
[Service]
Environment="QBITRR_CONFIG_PATH=/etc/qbitrr"
WorkingDirectory=/etc/qbitrr
ExecStart=/usr/bin/python3 -m qBitrr.main
```

Then create the directory:

```bash
sudo mkdir -p /etc/qbitrr
sudo chown qbitrr:qbitrr /etc/qbitrr
```

### Environment Variables

Add environment variables to the service file:

```ini
[Service]
Environment="QBITRR_CONFIG_PATH=/opt/qbitrr/config"
Environment="QBITRR_LOG_LEVEL=DEBUG"
Environment="TZ=America/New_York"
```

### Resource Limits

Limit CPU and memory usage:

```ini
[Service]
# Limit to 2GB RAM
MemoryMax=2G

# Limit to 50% CPU
CPUQuota=50%

# Limit open files
LimitNOFILE=65536
```

## Security Hardening

For enhanced security, add these options to the `[Service]` section:

```ini
[Service]
# Prevent privilege escalation
NoNewPrivileges=true

# Use private /tmp
PrivateTmp=true

# Protect system directories
ProtectSystem=strict
ProtectHome=true

# Only allow writes to specific directories
ReadWritePaths=/opt/qbitrr

# Restrict network access
RestrictAddressFamilies=AF_INET AF_INET6

# Disable other namespaces
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
```

!!! warning "Test Before Enabling"
    Some hardening options may interfere with qBitrr's operation. Test thoroughly before deploying.

## Multiple Instances

Run multiple qBitrr instances for different configurations:

### 1. Create Service Files

```bash
sudo cp /etc/systemd/system/qbitrr.service \
        /etc/systemd/system/qbitrr-movies.service

sudo cp /etc/systemd/system/qbitrr.service \
        /etc/systemd/system/qbitrr-tv.service
```

### 2. Modify Each Service

Edit `qbitrr-movies.service`:

```ini
[Service]
User=qbitrr-movies
WorkingDirectory=/opt/qbitrr-movies
Environment="QBITRR_CONFIG_PATH=/opt/qbitrr-movies/config"
```

Edit `qbitrr-tv.service`:

```ini
[Service]
User=qbitrr-tv
WorkingDirectory=/opt/qbitrr-tv
Environment="QBITRR_CONFIG_PATH=/opt/qbitrr-tv/config"
```

### 3. Create Users and Directories

```bash
# Movies instance
sudo useradd -r -s /bin/bash -d /opt/qbitrr-movies -m qbitrr-movies
sudo mkdir -p /opt/qbitrr-movies/{config,logs}
sudo chown -R qbitrr-movies:qbitrr-movies /opt/qbitrr-movies

# TV instance
sudo useradd -r -s /bin/bash -d /opt/qbitrr-tv -m qbitrr-tv
sudo mkdir -p /opt/qbitrr-tv/{config,logs}
sudo chown -R qbitrr-tv:qbitrr-tv /opt/qbitrr-tv
```

### 4. Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable qbitrr-movies qbitrr-tv
sudo systemctl start qbitrr-movies qbitrr-tv
```

!!! tip "Different WebUI Ports"
    Configure different WebUI ports in each instance's `config.toml`:
    ```toml
    [Settings]
    WebUIPort = 6969  # movies
    WebUIPort = 6970  # tv
    ```

## Troubleshooting

### Service Fails to Start

Check status and logs:

```bash
sudo systemctl status qbitrr
sudo journalctl -u qbitrr -n 50 --no-pager
```

Common issues:

| Issue | Solution |
|-------|----------|
| Permission denied | `sudo chown -R qbitrr:qbitrr /opt/qbitrr` |
| Python not found | Update `ExecStart` path in service file |
| Config errors | Check syntax in `config.toml` |
| Port already in use | Change `WebUIPort` in config |

### Service Restarts Repeatedly

Check for crash logs:

```bash
sudo journalctl -u qbitrr -p err -n 100
```

Temporarily stop to investigate:

```bash
sudo systemctl stop qbitrr
sudo -u qbitrr python3 -m qBitrr.main
```

### Update Not Working

Manual update:

```bash
sudo -u qbitrr pip install --upgrade qBitrr2
sudo systemctl restart qbitrr
```

### Permission Issues

Fix ownership and permissions:

```bash
sudo chown -R qbitrr:qbitrr /opt/qbitrr
sudo chmod -R 755 /opt/qbitrr
sudo chmod 644 /opt/qbitrr/config/*.toml
```

### Can't Connect to WebUI

Check if qBitrr is listening:

```bash
sudo netstat -tlnp | grep 6969
```

Check firewall:

```bash
sudo ufw allow 6969/tcp
```

## Complete Service File Example

Here's a production-ready service file with security hardening:

```ini
[Unit]
Description=qBitrr - Radarr/Sonarr/Lidarr Torrent Manager
Documentation=https://feramance.github.io/qBitrr/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=qbitrr
Group=qbitrr
WorkingDirectory=/opt/qbitrr

# Main process
ExecStart=/usr/bin/python3 -m qBitrr.main

# Environment
Environment="QBITRR_CONFIG_PATH=/opt/qbitrr/config"
Environment="TZ=America/New_York"

# Restart policy
Restart=always
RestartSec=5

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=qbitrr

# Resource limits
MemoryMax=2G
CPUQuota=50%
LimitNOFILE=65536

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/qbitrr
RestrictAddressFamilies=AF_INET AF_INET6
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

[Install]
WantedBy=multi-user.target
```

## Next Steps

- [Configure qBittorrent](../../configuration/qbittorrent.md)
- [Configure Arr Instances](../../configuration/arr/index.md)
- [First Run Guide](../quickstart.md)
- [Troubleshooting Guide](../../troubleshooting/index.md)
