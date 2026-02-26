# Process Management

qBitrr uses a multiprocessing architecture where each Arr instance (Radarr, Sonarr, Lidarr) runs in a separate process. This design ensures isolation, fault tolerance, and efficient resource utilization. The process management system automatically monitors and restarts failed processes to maintain high availability.

## Overview

qBitrr's process management provides:

- **Process Isolation**: Each Arr instance runs independently
- **Automatic Restart**: Failed processes are automatically restarted
- **Restart Limits**: Prevents infinite restart loops
- **Real-Time Monitoring**: Track process status via WebUI or logs
- **Graceful Shutdown**: Clean termination of all processes

---

## Architecture

### Process Structure

```
qBitrr Main Process
├── WebUI Process (Flask + Waitress)
├── Radarr Manager Process
│   └── Event Loop (health checks, imports, searches)
├── Sonarr Manager Process
│   └── Event Loop (health checks, imports, searches)
├── Lidarr Manager Process
│   └── Event Loop (health checks, imports, searches)
└── Background Threads
    ├── Auto-Update Thread
    ├── Network Monitor Thread
    └── FFprobe Downloader Thread
```

### Why Multiprocessing?

**Benefits:**
- ✅ **Isolation**: One Arr failure doesn't affect others
- ✅ **Parallelism**: True parallel execution on multi-core systems
- ✅ **Resource Management**: Each process has dedicated resources
- ✅ **Crash Recovery**: Individual processes can restart without affecting the main process

**Trade-offs:**
- ⚠️ Higher memory usage (each process has its own Python interpreter)
- ⚠️ Inter-process communication overhead (minimal in qBitrr's design)

---

## Auto-Restart Configuration

### Configuration Options

Add these settings to your `config.toml` under `[Settings]`:

```toml
[Settings]
# Enable automatic process restart (default: true)
AutoRestartProcesses = true

# Maximum restarts within the restart window (default: 5)
MaxProcessRestarts = 5

# Time window for counting restarts in seconds (default: 300 = 5 minutes)
ProcessRestartWindow = 300

# Delay before restarting a failed process in seconds (default: 5)
ProcessRestartDelay = 5
```

### How It Works

1. **Process Failure Detection**: qBitrr detects when an Arr process terminates unexpectedly
2. **Restart Attempt**: If `AutoRestartProcesses = true`, qBitrr waits `ProcessRestartDelay` seconds
3. **Restart Count Tracking**: Restart timestamp is recorded for the process
4. **Window Check**: qBitrr checks if restarts exceed `MaxProcessRestarts` within `ProcessRestartWindow`
5. **Decision**:
   - ✅ **Within Limits**: Process is restarted
   - ❌ **Exceeds Limits**: Auto-restart is disabled for that process (prevents infinite loops)

### Restart Window Explained

The restart window prevents infinite restart loops when a process has a persistent issue:

**Example:**
- `MaxProcessRestarts = 5`
- `ProcessRestartWindow = 300` (5 minutes)

**Scenario 1: Transient Failure (Restarts Allowed)**
```
00:00 - Process starts
00:05 - Process crashes → Restart #1
00:10 - Process crashes → Restart #2
00:15 - Process crashes → Restart #3
00:20 - Process stable (no more crashes)
Result: Restarts continue (within limits)
```

**Scenario 2: Persistent Failure (Restarts Disabled)**
```
00:00 - Process starts
00:05 - Process crashes → Restart #1
00:10 - Process crashes → Restart #2
00:15 - Process crashes → Restart #3
00:20 - Process crashes → Restart #4
00:25 - Process crashes → Restart #5
00:30 - Process crashes → Auto-restart DISABLED (5 restarts in 30 seconds)
Result: Process remains stopped to prevent loop
```

---

## Configuration Examples

### Example 1: Default Settings (Balanced)

```toml
[Settings]
AutoRestartProcesses = true
MaxProcessRestarts = 5
ProcessRestartWindow = 300  # 5 minutes
ProcessRestartDelay = 5     # 5 seconds
```

**Use Case:** General use, balances availability with protection against restart loops

---

### Example 2: High Availability (Aggressive Restart)

```toml
[Settings]
AutoRestartProcesses = true
MaxProcessRestarts = 10      # Allow more restarts
ProcessRestartWindow = 600   # 10-minute window
ProcessRestartDelay = 3      # Restart faster
```

**Use Case:** Critical setups where downtime must be minimized, even with frequent transient failures

---

### Example 3: Conservative (Prevents Loops)

```toml
[Settings]
AutoRestartProcesses = true
MaxProcessRestarts = 3       # Fewer restarts allowed
ProcessRestartWindow = 180   # 3-minute window
ProcessRestartDelay = 10     # Wait longer before restart
```

**Use Case:** Setups prone to configuration issues, prevents rapid restart loops

---

### Example 4: Manual Management (No Auto-Restart)

```toml
[Settings]
AutoRestartProcesses = false
```

**Use Case:** Debugging, development, or when using external process managers (systemd, Docker restart policies)

---

## Monitoring Processes

### Via WebUI

Navigate to the **Processes** tab in the WebUI:

- **Process Status**: Running, Stopped, or Restarting
- **Restart Count**: Number of restarts in the current window
- **Uptime**: How long the process has been running
- **Last Restart**: Timestamp of the last restart

[→ WebUI Processes View Documentation](../webui/processes.md)

---

### Via Logs

**Main Log (`Main.log`):**
```
INFO - Starting Radarr-Movies process (PID: 12345)
WARNING - Radarr-Movies process (PID: 12345) terminated unexpectedly
INFO - Restarting Radarr-Movies process (attempt 1/5)
INFO - Radarr-Movies process restarted successfully (PID: 12346)
```

**Category-Specific Logs (`Radarr-Movies.log`):**
```
INFO - Radarr-Movies manager starting
ERROR - Connection to Radarr failed: [Errno 111] Connection refused
INFO - Radarr-Movies manager shutting down
```

---

### Via CLI

**Check Process Status:**
```bash
# Docker
docker exec qbitrr ps aux | grep "qBitrr"

# Native (systemd)
systemctl status qbitrr

# Native (direct)
ps aux | grep "qBitrr"
```

---

## Restart Triggers

### Automatic Restart Triggers

qBitrr automatically restarts processes when:

1. **Unexpected Process Termination**: Process exits with non-zero code
2. **Segmentation Fault**: Process crashes due to memory error
3. **Unhandled Exception**: Python exception propagates to process level

**NOT Restarted For:**
- ❌ Manual stop via WebUI
- ❌ Graceful shutdown (SIGTERM)
- ❌ Configuration change requiring restart

---

### Manual Restart

**Via WebUI:**
1. Navigate to **Processes** tab
2. Click **Restart** next to the process name
3. Confirm restart action

**Via Docker:**
```bash
# Restart entire qBitrr container
docker restart qbitrr
```

**Via systemd:**
```bash
# Restart qBitrr service
sudo systemctl restart qbitrr
```

---

## Graceful Shutdown

qBitrr implements graceful shutdown to ensure data consistency:

### Shutdown Sequence

1. **Signal Received**: SIGTERM or SIGINT
2. **WebUI Shutdown**: Flask server stops accepting requests
3. **Arr Process Shutdown**: Each Arr process completes current operation
4. **Database Flush**: Pending database writes are committed
5. **Process Termination**: All processes exit cleanly

### Shutdown Timeout

If a process doesn't terminate within 30 seconds, it's forcefully killed (SIGKILL).

---

## Troubleshooting

### Process Won't Start

**Symptoms:** Process immediately crashes after start

**Common Causes:**
1. ✅ Invalid Arr API key or URI
2. ✅ Arr instance is down or unreachable
3. ✅ Port conflict (qBittorrent already connected by another client)
4. ✅ Missing dependencies (ffprobe, etc.)

**Solutions:**
1. Check category-specific log (`~/logs/Radarr-Movies.log`)
2. Verify Arr connectivity:
   ```bash
   curl -H "X-Api-Key: your-api-key" http://localhost:7878/api/v3/system/status
   ```
3. Test qBittorrent connection:
   ```bash
   curl -u "username:password" http://localhost:8080/api/v2/app/version
   ```

---

### Restart Loop (Auto-Restart Disabled)

**Symptoms:** Process stops restarting after several attempts

**Explanation:** `MaxProcessRestarts` limit reached within `ProcessRestartWindow`

**Solutions:**
1. ✅ Check logs for root cause:
   ```bash
   tail -f ~/logs/Radarr-Movies.log
   ```
2. ✅ Fix underlying issue (connectivity, configuration, etc.)
3. ✅ Manually restart qBitrr after fixing:
   ```bash
   docker restart qbitrr  # Docker
   sudo systemctl restart qbitrr  # systemd
   ```
4. ✅ Increase `MaxProcessRestarts` or `ProcessRestartWindow` if transient issues are expected

---

### High Memory Usage

**Symptoms:** qBitrr consuming excessive RAM

**Explanation:** Each Arr process runs a separate Python interpreter

**Memory Estimates:**
- Base process: ~100MB
- Per Arr process: ~50-100MB
- Total (3 Arr instances): ~250-400MB

**Solutions:**
1. ✅ Monitor per-process memory:
   ```bash
   docker stats qbitrr  # Docker
   ps aux | grep qBitrr  # Native
   ```
2. ✅ Disable unused Arr instances (`Managed = false` in config)
3. ✅ Reduce search limits (`SearchLimit`) to lower memory pressure

---

### Process Hangs (Unresponsive)

**Symptoms:** Process running but not processing torrents

**Common Causes:**
1. ✅ Event loop blocked by long-running operation
2. ✅ Database lock contention
3. ✅ Network timeout waiting for API response

**Solutions:**
1. ✅ Enable debug logging:
   ```toml
   [Settings]
   ConsoleLevel = "DEBUG"
   ```
2. ✅ Check for database locks:
   ```bash
   tail -f ~/logs/Main.log | grep -i "lock"
   ```
3. ✅ Restart process via WebUI or CLI

---

## Best Practices

### Production Deployments

1. **Enable Auto-Restart**: `AutoRestartProcesses = true`
2. **Set Reasonable Limits**: Default settings (5 restarts in 5 minutes) work for most cases
3. **Monitor Logs**: Set up log aggregation or alerts for restart events
4. **Use External Health Checks**: Monitor qBitrr's WebUI endpoint (`/health`) with Uptime Kuma, Healthchecks.io, etc.

---

### Development/Debugging

1. **Disable Auto-Restart**: `AutoRestartProcesses = false`
2. **Enable Debug Logging**: `ConsoleLevel = "DEBUG"`
3. **Run Single Arr Instance**: Simplify debugging by managing one Arr at a time
4. **Use `--no-detach` Flag**: Run in foreground for immediate feedback (systemd/native installs)

---

### Docker Considerations

**Restart Policy:**
```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    restart: unless-stopped  # Container-level restart
    environment:
      - QBITRR_SETTINGS__AUTORESTARTPROCESSES=true  # Process-level restart
```

**Layered Restart:**
- **Docker Restart Policy**: Restarts container if it crashes
- **qBitrr Auto-Restart**: Restarts individual Arr processes

**Recommendation:** Enable both for maximum availability.

---

## Integration with External Tools

### systemd

**qBitrr Service (`qbitrr.service`):**
```ini
[Unit]
Description=qBitrr - qBittorrent and Arr Integration
After=network.target

[Service]
Type=simple
User=qbitrr
WorkingDirectory=/home/qbitrr
ExecStart=/usr/local/bin/qbitrr
Restart=on-failure       # systemd restart on failure
RestartSec=10s           # Wait 10 seconds before restart
StartLimitBurst=5        # Max 5 restarts
StartLimitIntervalSec=300  # Within 5 minutes

[Install]
WantedBy=multi-user.target
```

**Combined with qBitrr Auto-Restart:**
- systemd restarts qBitrr if main process crashes
- qBitrr restarts individual Arr processes if they crash

---

### Docker Compose

**Health Check Example:**
```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6969/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    environment:
      - QBITRR_SETTINGS__AUTORESTARTPROCESSES=true
```

---

### Monitoring Tools

**Prometheus/Grafana:**
- Scrape qBitrr metrics endpoint (future feature)
- Alert on process restart count

**Uptime Kuma:**
```yaml
# Monitor qBitrr WebUI
- name: qBitrr
  type: HTTP
  url: http://localhost:6969/health
  interval: 60
```

**Healthchecks.io:**
```bash
# Cron job to ping healthchecks.io if qBitrr is running
*/5 * * * * curl -fsS --retry 3 http://localhost:6969/health && curl -fsS https://hc-ping.com/YOUR-UUID
```

---

## Advanced Configuration

### Per-Instance Restart Limits (Not Currently Supported)

**Future Feature:** Configure restart limits per Arr instance instead of globally.

**Workaround:** Run multiple qBitrr instances (one per Arr) with different restart settings.

---

### Custom Restart Delay

Adjust `ProcessRestartDelay` based on failure type:

```toml
[Settings]
# Fast restart for transient issues
ProcessRestartDelay = 3

# Slower restart if Arr startup is slow
ProcessRestartDelay = 15
```

---

## Logging

Process management events are logged to `Main.log`:

```
INFO - Starting Radarr-Movies process (category: radarr-movies, role: manager)
INFO - Radarr-Movies process started with PID 12345
WARNING - Radarr-Movies process (PID 12345) terminated with code 1
INFO - Scheduling restart for Radarr-Movies in 5 seconds (attempt 1/5)
INFO - Restarting Radarr-Movies process
INFO - Radarr-Movies process restarted successfully (PID 12346)
ERROR - Radarr-Movies process exceeded restart limit (5 restarts in 300 seconds)
ERROR - Auto-restart disabled for Radarr-Movies; manual intervention required
```

---

## API Endpoints

**Get Process Status:**
```http
GET /api/processes
```

**Response:**
```json
{
  "processes": [
    {
      "name": "Radarr-Movies",
      "category": "radarr-movies",
      "status": "running",
      "pid": 12345,
      "uptime": 3600,
      "restart_count": 2,
      "last_restart": "2024-01-15T10:30:00Z"
    }
  ]
}
```

[→ Full API Documentation](../webui/api.md)

---

## Next Steps

- **Monitor Processes**: [WebUI Processes View](../webui/processes.md)
- **View Logs**: [WebUI Logs View](../webui/logs.md)
- **Troubleshooting**: [Common Issues](../troubleshooting/common-issues.md)
- **Advanced Topics**: [Development Guide - Architecture](../development/index.md#architecture)
