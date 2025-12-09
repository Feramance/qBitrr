# Error Codes

Complete reference for qBitrr error codes, exceptions, and troubleshooting.

## Exception Hierarchy

qBitrr uses a custom exception hierarchy for error handling:

```
qBitManagerError (base)
├── UnhandledError
├── ConfigException
├── ArrManagerException
│   └── RestartLoopException
├── SkipException
├── RequireConfigValue
├── NoConnectionrException
└── DelayLoopException
```

## Python Exceptions

### qBitManagerError

**Base exception** for all qBitrr-specific errors.

**Source:** `qBitrr/errors.py:1`

```python
class qBitManagerError(Exception):
    """Base Exception"""
```

**Usage:** Catch all qBitrr exceptions

```python
try:
    process_torrent(torrent)
except qBitManagerError as e:
    logger.error(f"qBitrr error: {e}")
```

### UnhandledError

**Purpose:** Raised when an unhandled edge case is encountered.

**Source:** `qBitrr/errors.py:5`

```python
class UnhandledError(qBitManagerError):
    """Use to raise when there an unhandled edge case"""
```

**Common Causes:**
- Unexpected API response format
- Unknown torrent state
- Unsupported Arr version

**Example:**

```python
if response_format not in ['json', 'xml']:
    raise UnhandledError(f"Unexpected response format: {response_format}")
```

### ConfigException

**Purpose:** Configuration parsing or validation errors.

**Source:** `qBitrr/errors.py:9`

```python
class ConfigException(qBitManagerError):
    """Base Exception for Config related exceptions"""
```

**Common Causes:**
- Invalid TOML syntax
- Missing required fields
- Invalid data types
- Failed validation rules

**Example Log:**

```
[ERROR] ConfigException: Invalid URL for Radarr.URI: 'not-a-url'
[ERROR] ConfigException: Missing required field: Settings.Qbittorrent.Host
```

**Resolution:**
1. Validate config: `qbitrr --validate-config`
2. Check TOML syntax
3. Ensure all required fields are present

### RequireConfigValue

**Purpose:** Specific configuration value is missing.

**Source:** `qBitrr/errors.py:21`

```python
class RequireConfigValue(qBitManagerError):
    """Exception raised when a config value requires a value."""

    def __init__(self, config_class: str, config_key: str):
        self.message = f"Config key '{config_key}' in '{config_class}' requires a value."
```

**Example:**

```python
if not config.Radarr.APIKey:
    raise RequireConfigValue("Radarr", "APIKey")
```

**Log Output:**

```
[ERROR] Config key 'APIKey' in 'Radarr' requires a value.
```

**Resolution:**
- Add missing value to config.toml
- Check environment variable spelling

### ArrManagerException

**Purpose:** Base exception for Arr-related errors.

**Source:** `qBitrr/errors.py:13`

```python
class ArrManagerException(qBitManagerError):
    """Base Exception for Arr related Exceptions"""
```

**Common Causes:**
- Arr API connection failure
- Invalid API response
- Arr instance offline
- API rate limiting

**Example:**

```
[ERROR] ArrManagerException: Failed to connect to Radarr at http://localhost:7878
[ERROR] ArrManagerException: Radarr returned 401 Unauthorized (check API key)
```

### RestartLoopException

**Purpose:** Signal event loop to restart immediately.

**Source:** `qBitrr/errors.py:40`

```python
class RestartLoopException(ArrManagerException):
    """Exception to trigger a loop restart"""
```

**When Raised:**
- Configuration file changed
- Arr instance configuration updated
- Manual restart requested

**Handling:**

```python
while not shutdown_event.is_set():
    try:
        run_event_loop()
    except RestartLoopException:
        logger.info("Restarting event loop...")
        reload_config()
        continue  # Restart from beginning
```

**Log Output:**

```
[INFO] Configuration changed, restarting loop
[INFO] Restarting event loop...
```

### DelayLoopException

**Purpose:** Delay the next event loop iteration.

**Source:** `qBitrr/errors.py:34`

```python
class DelayLoopException(qBitManagerError):
    def __init__(self, length: int, type: str):
        self.type = type      # Reason for delay
        self.length = length  # Seconds to delay
```

**When Raised:**
- Network connection failure
- Temporary API unavailability
- Rate limiting

**Handling:**

```python
try:
    fetch_torrents()
except ConnectionError:
    raise DelayLoopException(length=60, type="connection_failure")
```

**Log Output:**

```
[WARNING] Delaying loop for 60s: connection_failure
[INFO] qBittorrent connection restored, resuming normal operation
```

### NoConnectionrException

**Purpose:** Handle connection failures with retry logic.

*Note: The typo "Connectionr" is preserved for backward compatibility.*

**Source:** `qBitrr/errors.py:28`

```python
class NoConnectionrException(qBitManagerError):
    def __init__(self, message: str, type: str = "delay"):
        self.message = message
        self.type = type  # "delay" or "fatal"
```

**When Raised:**
- Cannot connect to qBittorrent
- Cannot connect to Arr instance
- Network timeout

**Types:**
- `delay` - Temporary failure, will retry
- `fatal` - Permanent failure, stop trying

**Handling:**

```python
try:
    connect_to_arr()
except requests.exceptions.RequestException:
    if retry_count < MAX_RETRIES:
        raise NoConnectionrException("Failed to connect to Radarr", type="delay")
    else:
        raise NoConnectionrException("Max retries exceeded", type="fatal")
```

**Log Output:**

```
[WARNING] Failed to connect to Radarr: Connection refused
[INFO] Retrying connection in 5 seconds... (attempt 1/3)
[ERROR] Max retries exceeded, giving up
```

### SkipException

**Purpose:** Skip processing the current torrent and continue with the next one.

**Source:** `qBitrr/errors.py:17`

```python
class SkipException(qBitManagerError):
    """Dummy error to skip actions"""
```

**When Raised:**
- Torrent doesn't match criteria
- Already processed
- Invalid torrent data

**Handling:**

```python
for torrent in torrents:
    try:
        process_torrent(torrent)
    except SkipException:
        continue  # Skip to next torrent
```

**Example:**

```python
if torrent['category'] not in self.managed_categories:
    raise SkipException("Not our category")
```

**Log Output:**

```
[DEBUG] Skipping torrent abc123: Not our category
[DEBUG] Skipping torrent def456: Already imported
```

## HTTP Status Codes

### API Endpoints

qBitrr WebUI API returns standard HTTP status codes:

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 204 | No Content | Success, no response body |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid API token |
| 403 | Forbidden | Valid token but insufficient permissions |
| 404 | Not Found | Endpoint or resource not found |
| 409 | Conflict | Resource conflict (e.g., duplicate entry) |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 502 | Bad Gateway | Upstream service unavailable |
| 503 | Service Unavailable | qBitrr is starting or shutting down |

### Common API Errors

#### 401 Unauthorized

```json
{
  "error": "Unauthorized",
  "message": "Missing or invalid API token"
}
```

**Cause:** `X-API-Token` header missing or incorrect

**Resolution:**
```bash
# Include token in requests
curl -H "X-API-Token: your-token" http://localhost:6969/api/torrents
```

#### 422 Validation Error

```json
{
  "error": "Validation Error",
  "details": {
    "field": "quality_profile",
    "message": "Quality profile 'HD-1080p' not found in Radarr"
  }
}
```

**Resolution:** Check field value, consult API documentation

#### 500 Internal Server Error

```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred",
  "trace_id": "abc123def456"
}
```

**Resolution:** Check logs for full error, report issue with trace_id

## Exit Codes

### CLI Exit Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 0 | Success | qBitrr exited normally |
| 1 | General Error | Unspecified error |
| 2 | Config Error | Configuration file error |
| 3 | Connection Error | Cannot connect to required service |
| 4 | Permission Error | Insufficient file/directory permissions |
| 5 | Database Error | Database initialization or access error |
| 130 | SIGINT | User interrupted (Ctrl+C) |
| 143 | SIGTERM | Terminated by system or user |

### Exit Code Examples

**Normal exit:**

```bash
qbitrr
# ... runs successfully, user stops with Ctrl+C
# Exit code: 130
```

**Config error:**

```bash
qbitrr --config /path/to/invalid.toml
# [ERROR] ConfigException: Invalid TOML syntax at line 42
# Exit code: 2
```

**Connection error:**

```bash
qbitrr
# [ERROR] NoConnectionrException: Cannot connect to qBittorrent
# Exit code: 3
```

## Common Error Scenarios

### Scenario 1: Database Locked

**Error:**

```
[ERROR] database is locked
```

**Cause:** Multiple processes trying to write simultaneously

**Resolution:**

```bash
# Check for multiple qBitrr instances
ps aux | grep qbitrr

# Kill all instances
pkill -f qbitrr

# Remove lock file
rm ~/config/qBitrr.db.lock

# Restart qBitrr
qbitrr
```

### Scenario 2: Arr API Key Invalid

**Error:**

```
[ERROR] ArrManagerException: Radarr returned 401 Unauthorized
```

**Cause:** API key is incorrect or expired

**Resolution:**

1. Get API key from Arr instance:
   - Open Radarr web interface
   - Settings → General → Security → API Key

2. Update config.toml:
   ```toml
   [[Radarr]]
   APIKey = "correct-api-key-here"
   ```

3. Restart qBitrr

### Scenario 3: FFprobe Validation Fails

**Error:**

```
[WARNING] FFprobe validation failed for torrent abc123: Invalid data found
```

**Cause:**
- Corrupt video file
- Unsupported codec
- Incomplete download

**Resolution:**

1. Check file manually:
   ```bash
   ffprobe /path/to/file.mkv
   ```

2. If file is valid, disable FFprobe temporarily:
   ```toml
   [Settings]
   EnableFFprobe = false
   ```

3. If file is corrupt, torrent will be blacklisted and re-searched (if enabled)

### Scenario 4: Max ETA Exceeded

**Error:**

```
[INFO] Torrent abc123 marked as stalled: ETA 7200s exceeds MaximumETA 3600s
```

**Cause:** Download is progressing too slowly

**Resolution:**

1. Increase ETA threshold:
   ```toml
   [[Radarr]]
   MaximumETA = 14400  # 4 hours
   ```

2. Or check if torrent has seeders:
   - Open qBittorrent
   - Check torrent details
   - If no seeders, blacklist and search for alternative

### Scenario 5: Import Fails

**Error:**

```
[ERROR] Failed to import torrent abc123 to Radarr
```

**Cause:**
- File permissions
- Path not accessible to Arr
- Arr instance offline

**Resolution:**

1. Check file permissions:
   ```bash
   ls -la /path/to/download/
   ```

2. Ensure Arr can access path:
   - Docker: Check volume mounts match
   - Native: Check Arr user permissions

3. Check Arr logs for details

## Debugging

### Enable Debug Logging

```toml
[Settings]
LogLevel = "DEBUG"
```

### Log Locations

```
~/config/logs/
├── Main.log              # Main process errors
├── WebUI.log            # API/WebUI errors
├── Radarr-<name>.log    # Radarr-specific errors
├── Sonarr-<name>.log    # Sonarr-specific errors
└── Lidarr-<name>.log    # Lidarr-specific errors
```

### Search Logs for Errors

```bash
# Find all errors
grep -i "ERROR" ~/config/logs/*.log

# Find specific error
grep "abc123" ~/config/logs/*.log

# Recent errors (last hour)
find ~/config/logs -name "*.log" -mmin -60 -exec grep -H "ERROR" {} \;
```

## Reporting Bugs

When reporting issues, include:

1. **qBitrr version:**
   ```bash
   qbitrr --version
   ```

2. **Error message** from logs

3. **Configuration** (redact API keys):
   ```bash
   qbitrr --show-config
   ```

4. **Steps to reproduce**

5. **Environment:**
   - OS (Linux/Windows/macOS/Docker)
   - Python version
   - qBittorrent version
   - Arr versions

## Related Documentation

- [Troubleshooting: Common Issues](../troubleshooting/common-issues.md) - Common problems and solutions
- [Troubleshooting: Debug Logging](../troubleshooting/debug-logging.md) - Enable verbose logging
- [Reference: CLI](cli.md) - Command-line options
- [Reference: API](api.md) - API error responses
