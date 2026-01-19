# Logs View

The **Logs View** provides real-time streaming and viewing of qBitrr's log files. Monitor application activity, debug issues, and track system events through an intuitive interface with auto-refresh and log file selection capabilities.

---

## Overview

qBitrr generates structured logs for all major components:

- **Main.log**: Core application events, initialization, shutdown
- **WebUI.log**: Flask/Waitress HTTP server logs, API requests
- **<ArrName>.log**: Per-instance logs (e.g., `Radarr-Movies.log`, `Sonarr-TV.log`)
- **Rotated logs**: Timestamped backups (e.g., `Main.log.2025-11-27`)

The Logs view provides:

- **Real-time streaming**: Auto-refresh every 2 seconds when active
- **Full log display**: Tail of log files with ANSI color support
- **Log file selection**: Dropdown to switch between available logs
- **Download capability**: Export logs for offline analysis or bug reports
- **Auto-scroll control**: Toggle automatic scrolling to bottom

---

## UI Components

### Log File Selector

**Location**: Top toolbar → Dropdown menu

Select which log file to view from all available `.log` files in the logs directory.

**Available Logs**:

| Log File | Description |
|----------|-------------|
| `Main.log` | Core application events, process management, config loading |
| `WebUI.log` | HTTP server logs, API requests, authentication failures |
| `<ArrName>.log` | Per-instance logs for each managed Arr (e.g., `Radarr-Movies.log`) |
| `<ArrName>.log.<date>` | Rotated log archives (timestamped backups) |

**Default Selection**: `Main.log` (falls back to first available log if Main.log doesn't exist)

### Log Viewer

**Location**: Main content area

Displays the full content of the selected log file with:

- **ANSI Color Support**: Preserves terminal colors (red errors, green success, blue info)
- **Monospace Font**: `Cascadia Code`, `Fira Code`, `Consolas`, `Monaco`
- **Dark Background**: `#0a0e14` for readability
- **Line Wrapping**: Pre-wrap style for long log lines
- **Scroll Container**: Full-height with independent scrolling

**Example Display**:
```plaintext
2025-11-27 10:30:15 | INFO     | qBitrr.Main | Starting qBitrr 5.0.3
2025-11-27 10:30:15 | INFO     | qBitrr.Main | Loading config from /config/config.toml
2025-11-27 10:30:16 | NOTICE   | qBitrr.Main | Connected to qBittorrent v5.0.2
2025-11-27 10:30:17 | SUCCESS  | qBitrr.Main | Radarr-Movies: API connection successful
2025-11-27 10:30:18 | ERROR    | qBitrr.Main | Sonarr-TV: Connection refused (Host: http://sonarr:8989)
```

### Action Buttons

#### Reload List
**Location**: Top toolbar → **Reload List** button

**Function**: Refresh the list of available log files without reloading the current log content.

**Use Cases**:
- After log rotation (new `.log.<date>` files appear)
- When new Arr instances are added (new per-instance logs)
- After logs are manually cleared

**Endpoint**: `GET /api/logs`

#### Download
**Location**: Top toolbar → **Download** button

**Function**: Download the currently selected log file for offline analysis.

**Use Cases**:
- Attach to GitHub issues or bug reports
- Archive logs before rotation
- Share with support team

**Endpoint**: `GET /api/logs/<name>/download`

**Filename**: Uses original log filename (e.g., `Main.log`, `Radarr-Movies.log.2025-11-27`)

#### Auto-scroll Toggle
**Location**: Top toolbar → Checkbox with live icon

**Function**: Enable/disable automatic scrolling to bottom when new log entries appear.

**Behavior**:
- **Enabled** (default): Scroll to bottom every 2 seconds when new content loads
- **Disabled**: Scroll position locked, allows manual navigation of historical logs
- **Auto-disable**: Automatically disables when user scrolls up manually

**Use Cases**:
- **Enable**: Monitor real-time activity (search loops, torrent processing)
- **Disable**: Review historical errors, search for specific log entries

---

## Refresh Behavior

### Auto-Refresh Intervals

| Condition | Refresh Interval | Description |
|-----------|------------------|-------------|
| **Tab Active** + Auto-scroll ON | 2 seconds | Real-time streaming mode |
| **Tab Active** + Auto-scroll OFF | Paused | No automatic updates |
| **Tab Inactive** | Paused | Conserves resources when tab is not visible |

**Manual Refresh**: Click **Reload List** or switch log files to force immediate update.

### Scroll Position Management

**Auto-scroll Enabled**:
1. Log content loads via `/api/logs/<name>`
2. DOM updated with new content
3. `scrollTop` set to `scrollHeight` (scroll to bottom)
4. Process repeats every 2 seconds

**Auto-scroll Disabled**:
- Scroll position frozen at current location
- User can manually scroll through historical logs
- Re-enabling auto-scroll immediately jumps to bottom

**User Scroll Detection**:
- Scroll event listener monitors scroll position
- If user scrolls away from bottom (>10px threshold), auto-scroll disables
- Prevents scroll fighting during manual navigation

---

## Log Format

### Structured Logging

qBitrr uses Python's `logging` module with custom formatters:

**Format Pattern**:
```
%(asctime)s | %(levelname)-8s | %(name)s | %(message)s
```

**Example**:
```
2025-11-27 10:30:15 | INFO     | qBitrr.Main | Starting qBitrr 5.0.3
```

**Components**:

| Field | Description | Example |
|-------|-------------|---------|
| `asctime` | ISO 8601 timestamp (local timezone) | `2025-11-27 10:30:15` |
| `levelname` | Log level (8 characters, left-padded) | `INFO`, `WARNING`, `ERROR` |
| `name` | Logger name (module path) | `qBitrr.Main`, `qBitrr.arr.Radarr-Movies` |
| `message` | Log message | `Starting qBitrr 5.0.3` |

### Log Levels

qBitrr supports standard Python log levels plus custom levels:

| Level | Numeric Value | Color (ANSI) | Use Case |
|-------|---------------|--------------|----------|
| **TRACE** | 5 | Dim gray | Detailed debugging (function calls, variable states) |
| **DEBUG** | 10 | Gray | Development diagnostics (API responses, loop iterations) |
| **INFO** | 20 | White | Standard operational messages (startup, config load) |
| **NOTICE** | 25 | Cyan | Important user-facing events (Arr connections, searches) |
| **SUCCESS** | 25 | Green | Successful operations (imports, deletions) |
| **WARNING** | 30 | Yellow | Recoverable issues (retries, fallbacks, deprecations) |
| **ERROR** | 40 | Red | Failures requiring attention (API errors, file I/O) |
| **CRITICAL** | 50 | Bold red | Fatal errors (database corruption, unhandled exceptions) |

**Custom Levels**:
- **NOTICE**: Custom level at 25 (between INFO and WARNING)
- **SUCCESS**: Custom level at 25 (between INFO and WARNING)
- **TRACE**: Custom level at 5 (below DEBUG)

**Setting Log Level**:
```toml
[Settings]
ConsoleLevel = "INFO"  # CRITICAL, ERROR, WARNING, NOTICE, INFO, DEBUG, TRACE
```

### ANSI Color Codes

The Logs view preserves ANSI color codes from terminal output:

**Foreground Colors**:
```plaintext
\033[31m  → Red (errors)
\033[32m  → Green (success)
\033[33m  → Yellow (warnings)
\033[34m  → Blue (info)
\033[36m  → Cyan (notice)
\033[90m  → Dim gray (debug)
```

**Background Colors**:
```plaintext
\033[41m  → Red background
\033[42m  → Green background
```

**Styles**:
```plaintext
\033[1m   → Bold
\033[3m   → Italic
\033[4m   → Underline
\033[0m   → Reset all styles
```

**Rendering**:
- ANSI codes converted to inline HTML `<span style="...">` tags
- Colors mapped to hex values (e.g., `\033[31m` → `color:#cd3131`)
- Newlines converted to `<br>` tags
- Final HTML rendered with `dangerouslySetInnerHTML` (safe, server-controlled content)

---

## API Endpoints

### GET /api/logs

**Description**: List all available log files in the logs directory.

**Authentication**: Requires `X-API-Token` header (if `WebUI.Token` is set)

**Response**:
```json
{
  "files": [
    "Main.log",
    "WebUI.log",
    "Radarr-Movies.log",
    "Sonarr-TV.log",
    "Main.log.2025-11-27",
    "Radarr-Movies.log.2025-11-26"
  ]
}
```

**Sorting**: Files sorted alphabetically (`.log` files appear before `.log.<date>`)

### GET /api/logs/:name

**Description**: Stream the full content of a specific log file.

**Authentication**: Requires `X-API-Token` header (if `WebUI.Token` is set)

**Path Parameters**:
- `name`: Log filename (e.g., `Main.log`, `Radarr-Movies.log.2025-11-27`)

**Response**:
- **Content-Type**: `text/plain; charset=utf-8`
- **Body**: Full log file content (raw text)

**Example**:
```http
GET /api/logs/Main.log HTTP/1.1
Authorization: Bearer <token>

HTTP/1.1 200 OK
Content-Type: text/plain; charset=utf-8
Cache-Control: no-cache

2025-11-27 10:30:15 | INFO     | qBitrr.Main | Starting qBitrr 5.0.3
2025-11-27 10:30:15 | INFO     | qBitrr.Main | Loading config from /config/config.toml
...
```

**Error Handling**:
- **404 Not Found**: Log file does not exist
- **401 Unauthorized**: Invalid or missing token

**Performance**:
- Reads entire file into memory (use cautiously with large logs)
- Encoding errors ignored (`errors="ignore"`)
- No partial reads or byte-range support

### GET /api/logs/:name/download

**Description**: Download a log file as an attachment.

**Authentication**: Requires `X-API-Token` header (if `WebUI.Token` is set)

**Path Parameters**:
- `name`: Log filename

**Response**:
- **Content-Disposition**: `attachment; filename="<name>"`
- **Body**: Full log file content

**Example**:
```http
GET /api/logs/Main.log/download HTTP/1.1
Authorization: Bearer <token>

HTTP/1.1 200 OK
Content-Disposition: attachment; filename="Main.log"
Content-Type: application/octet-stream

<log file contents>
```

**Use Cases**:
- Attach to bug reports
- Archive before log rotation
- Share with support team

---

## Log Rotation

qBitrr uses Python's `RotatingFileHandler` for automatic log rotation:

**Rotation Policy**:
- **Max Size**: 10 MB per log file
- **Backup Count**: 5 (keeps 5 rotated copies)
- **Naming**: `<log_name>.log.<index>` → timestamped on next rotation

**Example Lifecycle**:
```
Main.log              → Active log (current writes)
Main.log.1            → Yesterday's log (first rotation)
Main.log.2            → 2 days ago
Main.log.3            → 3 days ago
Main.log.4            → 4 days ago
Main.log.5            → 5 days ago (oldest, deleted on next rotation)
```

**Manual Rotation**:
Logs rotate automatically when size exceeds 10 MB. To force rotation:
1. Stop qBitrr
2. Rename `Main.log` → `Main.log.manual`
3. Restart qBitrr (creates new `Main.log`)

**Viewing Rotated Logs**:
1. Click **Reload List** to refresh log file dropdown
2. Select `Main.log.1` (or other rotated file)
3. Download for offline viewing (rotated logs are read-only)

---

## Configuration

### Log Level

**Path**: `Settings.ConsoleLevel`
**Type**: `string`
**Default**: `INFO`
**Valid Values**: `CRITICAL`, `ERROR`, `WARNING`, `NOTICE`, `INFO`, `DEBUG`, `TRACE`

Controls the minimum log level written to console and log files.

**Example** (`config.toml`):
```toml
[Settings]
ConsoleLevel = "DEBUG"  # Show all DEBUG and higher messages
```

**Runtime Change** (via WebUI):
1. Navigate to **Config** tab
2. Open **Settings** section
3. Change **Console Level** dropdown
4. Click **Save + Live Reload**

**Or via API**:
```bash
curl -X POST http://localhost:6969/api/loglevel \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"level": "DEBUG"}'
```

### Log Directory

**Native Install**:
```
~/logs/
├── Main.log
├── WebUI.log
├── Radarr-Movies.log
└── ...
```

**Docker Install**:
```
/config/logs/
├── Main.log
├── WebUI.log
├── Radarr-Movies.log
└── ...
```

**Custom Path**: Not configurable (hardcoded to `HOME_PATH / "logs"`)

### Logging Toggle

**Path**: `Settings.Logging`
**Type**: `bool`
**Default**: `true`

Enable/disable file logging entirely (console output continues).

**Example** (`config.toml`):
```toml
[Settings]
Logging = false  # Disable file logging
```

**⚠️ Warning**: Disabling logging removes all audit trail and makes debugging impossible.

---

## Troubleshooting

### "Select a log file to view its tail..."

**Cause**: No log file selected or selected file is empty.

**Solution**:
1. Check **Log File** dropdown has a selection
2. Click **Reload List** to refresh available logs
3. Verify logs directory exists (`~/logs` or `/config/logs`)
4. Check `Settings.Logging = true` in config

### Log viewer shows "Loading logs..." indefinitely

**Cause**: API request to `/api/logs/<name>` is failing.

**Solutions**:
1. Check browser console for HTTP errors (F12 → Console)
2. Verify log file exists in logs directory
3. Check file permissions (qBitrr must have read access)
4. Test endpoint manually:
   ```bash
   curl http://localhost:6969/api/logs/Main.log
   ```

### ANSI colors not displaying

**Cause**: Log file missing ANSI escape codes (plain text).

**Solutions**:
- Increase `Settings.ConsoleLevel` to `DEBUG` or `TRACE` (more colorful output)
- Check logger configuration in `qBitrr/logger.py` (color formatter may be disabled)
- Verify terminal emulator supports ANSI colors (if running qBitrr manually)

### Auto-scroll not working

**Cause**: User scrolled away from bottom, disabling auto-scroll.

**Solution**:
1. Re-enable **Auto-scroll** checkbox in toolbar
2. Scroll manually to bottom (auto-scroll re-enables automatically)
3. Refresh page to reset scroll state

### Log file too large (slow loading)

**Cause**: Log file exceeds 10 MB before rotation.

**Solutions**:
1. Wait for automatic rotation (happens at 10 MB)
2. Download log and clear:
   ```bash
   mv ~/logs/Main.log ~/logs/Main.log.backup
   # qBitrr creates new Main.log automatically
   ```
3. Reduce `Settings.ConsoleLevel` to `INFO` or `WARNING` (less verbose)

### Missing per-instance logs (e.g., Radarr-Movies.log)

**Cause**: Instance not managed (`Managed = false`) or not yet started.

**Solutions**:
1. Verify `Managed = true` in config for the Arr instance
2. Check **Processes** tab shows instance is running
3. Wait 30-60 seconds after instance starts (log file created on first write)
4. Restart qBitrr to reinitialize loggers

---

## Performance Considerations

### Large Log Files

**Problem**: Reading 100+ MB logs causes high memory usage and slow response times.

**Solutions**:
1. **Enable Log Rotation**: Logs automatically rotate at 10 MB (hardcoded)
2. **Manually Archive**: Move old logs out of logs directory
3. **Reduce Log Level**: Change `Settings.ConsoleLevel` to `INFO` or `WARNING`
4. **Download and Clear**: Download log, then delete original file

**Future Enhancement**: Implement server-side tail (last N lines only) to avoid full-file reads.

### Auto-Refresh Overhead

**Problem**: Fetching full log every 2 seconds with large logs.

**Current Behavior**:
- Full file read on every refresh (no delta/diff)
- 2-second interval when auto-scroll enabled
- Pauses when tab inactive (Page Visibility API)

**Optimization Tips**:
1. Disable auto-scroll when not actively monitoring
2. Close Logs tab when not in use (pauses refresh)
3. Use `tail -f` directly on server for long-term monitoring:
   ```bash
   tail -f ~/logs/Main.log
   ```

---

## Best Practices

### Debugging Arr Connections

1. Navigate to **Logs** tab
2. Select `<ArrName>.log` (e.g., `Radarr-Movies.log`)
3. Enable **Auto-scroll**
4. Watch for:
   - `Connection refused` → Check URI and port
   - `401 Unauthorized` → Check API key
   - `404 Not Found` → Verify Arr is running

### Monitoring Search Activity

1. Navigate to **Logs** tab
2. Select instance log (e.g., `Sonarr-TV.log`)
3. Enable **Auto-scroll**
4. Watch for:
   - `[NOTICE] Searching for: <Title>` → Search initiated
   - `[SUCCESS] Found X results` → Search completed
   - `[ERROR] No results found` → Missing indexers or releases

### Capturing Crash Logs

1. **Before Crash**:
   - Set `Settings.ConsoleLevel = "DEBUG"`
   - Enable `Settings.Logging = true`
2. **After Crash**:
   - Navigate to **Logs** → Select `Main.log`
   - Scroll to bottom (crash traceback)
   - Click **Download** → Attach to GitHub issue

### Reducing Log Noise

1. Set `Settings.ConsoleLevel = "INFO"` (default)
2. Avoid `DEBUG` or `TRACE` in production (generates 10x more logs)
3. Enable log rotation (automatic at 10 MB)
4. Archive old logs monthly:
   ```bash
   tar -czf logs-$(date +%Y-%m).tar.gz ~/logs/*.log.*
   rm ~/logs/*.log.*
   ```

---

## See Also

- [Processes View](processes.md) – Monitor process status and restart instances
- [WebUI Configuration](../configuration/webui.md) – WebUI settings and authentication
- [Troubleshooting Common Issues](../troubleshooting/common-issues.md) – Debugging guide
- [API Documentation](api.md) – Full API endpoint reference
