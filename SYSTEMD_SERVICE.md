# qBitrr Systemd Service Setup Guide

This guide explains how to set up qBitrr as a systemd service on Linux systems for automatic startup and restart management.

## Prerequisites

- Linux system with systemd (most modern distributions)
- qBitrr installed via pip: `pip install qBitrr2`
- Python 3.12 or higher
- Non-root user account for running qBitrr (recommended for security)

## Installation Steps

### 1. Create qBitrr User (Recommended)

Create a dedicated user for running qBitrr:

```bash
sudo useradd -r -s /bin/bash -d /opt/qbitrr -m qbitrr
```

### 2. Install qBitrr

Install qBitrr for the qbitrr user:

```bash
sudo -u qbitrr pip install qBitrr2
```

Or install system-wide:

```bash
sudo pip install qBitrr2
```

### 3. Create Configuration Directory

```bash
sudo mkdir -p /opt/qbitrr/config
sudo mkdir -p /opt/qbitrr/logs
sudo chown -R qbitrr:qbitrr /opt/qbitrr
```

### 4. Generate Initial Configuration

```bash
sudo -u qbitrr qbitrr --gen-config
```

Edit the generated configuration file at `/opt/qbitrr/config/config.toml` with your settings.

### 5. Install Systemd Service File

Copy the service file to systemd directory:

```bash
sudo cp qbitrr.service /etc/systemd/system/qbitrr.service
```

Or create it manually:

```bash
sudo nano /etc/systemd/system/qbitrr.service
```

Paste the following content:

```ini
[Unit]
Description=qBitrr - Radarr/Sonarr/Lidarr Torrent Manager
Documentation=https://github.com/Feramance/qBitrr
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=qbitrr
Group=qbitrr
WorkingDirectory=/opt/qbitrr

# Main process
ExecStart=/usr/bin/python3 -m qBitrr.main

# Restart policy
# always: Restart on any exit (crash, update, manual restart)
# on-failure: Only restart on error exit codes
Restart=always
RestartSec=5

# Resource limits (adjust as needed)
# LimitNOFILE=65536
# MemoryMax=2G

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=qbitrr

# Security hardening (optional, adjust as needed)
# NoNewPrivileges=true
# PrivateTmp=true
# ProtectSystem=strict
# ProtectHome=true
# ReadWritePaths=/opt/qbitrr /config

[Install]
WantedBy=multi-user.target
```

**Important:** Adjust the `ExecStart` path if Python is installed elsewhere:
- Find Python path: `which python3`
- Update ExecStart accordingly

### 6. Reload Systemd and Enable Service

```bash
# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable qBitrr to start on boot
sudo systemctl enable qbitrr

# Start qBitrr immediately
sudo systemctl start qbitrr
```

## Managing the Service

### Check Service Status

```bash
sudo systemctl status qbitrr
```

### View Logs

```bash
# Real-time logs
sudo journalctl -u qbitrr -f

# Last 100 lines
sudo journalctl -u qbitrr -n 100

# Logs since boot
sudo journalctl -u qbitrr -b

# Logs for specific time range
sudo journalctl -u qbitrr --since "2025-01-01 00:00:00" --until "2025-01-01 23:59:59"
```

### Start/Stop/Restart Service

```bash
# Start service
sudo systemctl start qbitrr

# Stop service
sudo systemctl stop qbitrr

# Restart service
sudo systemctl restart qbitrr

# Reload configuration without restart (if supported)
sudo systemctl reload qbitrr
```

### Disable Service

```bash
# Stop service and disable auto-start
sudo systemctl stop qbitrr
sudo systemctl disable qbitrr
```

## Auto-Update Behavior

When qBitrr performs an auto-update or manual update via WebUI:

1. **With systemd**: The service will **automatically restart** after update
   - qBitrr calls `os.execv()` to replace itself with the new version
   - Process maintains same PID, systemd continues monitoring
   - No interruption in service availability

2. **Restart Policy**: The `Restart=always` directive ensures:
   - Service restarts after updates
   - Service restarts after crashes
   - Service restarts after manual stops (unless disabled)

3. **Restart Delay**: `RestartSec=5` adds a 5-second delay between restart attempts
   - Prevents rapid restart loops if there's a configuration issue
   - Adjust as needed for your environment

## Troubleshooting

### Service Fails to Start

```bash
# Check service status for errors
sudo systemctl status qbitrr

# View detailed logs
sudo journalctl -u qbitrr -n 50 --no-pager

# Check configuration file
sudo -u qbitrr qbitrr --check-config
```

Common issues:
- **Permission denied**: Ensure qbitrr user has read/write access to config and log directories
- **Python not found**: Update `ExecStart` path in service file
- **Config errors**: Check `/opt/qbitrr/config/config.toml` for syntax errors

### Service Restarts Repeatedly

```bash
# Check for crash logs
sudo journalctl -u qbitrr -p err -n 100

# Temporarily stop service to investigate
sudo systemctl stop qbitrr

# Test qBitrr manually
sudo -u qbitrr python3 -m qBitrr.main
```

### Update Not Working

If auto-update fails:

```bash
# Update manually via pip
sudo -u qbitrr pip install --upgrade qBitrr2

# Restart service
sudo systemctl restart qbitrr
```

### Permission Issues After Update

```bash
# Fix ownership
sudo chown -R qbitrr:qbitrr /opt/qbitrr

# Fix permissions
sudo chmod -R 755 /opt/qbitrr
sudo chmod -R 644 /opt/qbitrr/config/*.toml
```

## Security Hardening

For enhanced security, uncomment and configure these options in the service file:

```ini
# Prevent privilege escalation
NoNewPrivileges=true

# Use private /tmp
PrivateTmp=true

# Protect system directories
ProtectSystem=strict
ProtectHome=true

# Only allow writes to specific directories
ReadWritePaths=/opt/qbitrr /config

# Restrict network access (if not needed)
# RestrictAddressFamilies=AF_INET AF_INET6

# Resource limits
LimitNOFILE=65536
MemoryMax=2G
CPUQuota=50%
```

## Alternative Configuration Locations

If you prefer a different config location, update the service file:

```ini
[Service]
Environment="QBITRR_CONFIG_DIR=/etc/qbitrr"
WorkingDirectory=/etc/qbitrr
ExecStart=/usr/bin/python3 -m qBitrr.main
```

Then create the directory:

```bash
sudo mkdir -p /etc/qbitrr
sudo chown qbitrr:qbitrr /etc/qbitrr
```

## Running as Root (Not Recommended)

If you must run as root (not recommended for security):

```ini
[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/qbitrr
ExecStart=/usr/bin/python3 -m qBitrr.main
```

**Security Warning**: Running as root is a security risk. Use a dedicated user account instead.

## Multiple Instances

To run multiple qBitrr instances (e.g., for different configurations):

1. Create separate service files:
   ```bash
   sudo cp /etc/systemd/system/qbitrr.service /etc/systemd/system/qbitrr-movies.service
   sudo cp /etc/systemd/system/qbitrr.service /etc/systemd/system/qbitrr-tv.service
   ```

2. Update each service file with different:
   - User/Group
   - WorkingDirectory
   - WebUI Port (via environment variable)

3. Enable and start each instance:
   ```bash
   sudo systemctl enable qbitrr-movies qbitrr-tv
   sudo systemctl start qbitrr-movies qbitrr-tv
   ```

## Additional Resources

- [qBitrr GitHub Repository](https://github.com/Feramance/qBitrr)
- [qBitrr Documentation](https://github.com/Feramance/qBitrr/blob/master/README.md)
- [Systemd Service Documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Systemd Hardening Guide](https://www.freedesktop.org/software/systemd/man/systemd.exec.html#Sandboxing)

## Support

For issues and support:
- GitHub Issues: https://github.com/Feramance/qBitrr/issues
- Documentation: https://github.com/Feramance/qBitrr/wiki
