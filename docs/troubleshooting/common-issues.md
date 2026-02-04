# Common Issues & Solutions

This page covers the most frequently encountered issues with qBitrr and their solutions.

---

## Connection Issues

### qBittorrent Connection Failures

#### Symptom: "Connection refused" or "Connection timeout"

**Possible Causes:**

- qBittorrent is not running
- Wrong `Host` or `Port` in config
- Firewall blocking connection
- qBittorrent Web UI is disabled

**Solutions:**

1. **Verify qBittorrent is running:**
   ```bash
   # Check if qBittorrent process is active
   ps aux | grep qbittorrent
   ```

2. **Check Web UI is enabled:**
   - Open qBittorrent
   - Go to **Tools** → **Options** → **Web UI**
   - Ensure **"Web User Interface (Remote control)"** is checked
   - Note the IP address and port

3. **Test connection manually:**
   ```bash
   # Replace with your actual values
   curl -i http://localhost:8080/api/v2/app/version
   ```
   Expected: HTTP 200 response with version number

4. **Check firewall rules:**
   ```bash
   # Linux (ufw)
   sudo ufw allow 8080/tcp

   # Linux (firewalld)
   sudo firewall-cmd --add-port=8080/tcp --permanent
   sudo firewall-cmd --reload
   ```

5. **Docker: Use correct host:**
   - Same network: Use container name (e.g., `qbittorrent`)
   - Different network: Use host IP or `host.docker.internal` (macOS/Windows)

---

#### Symptom: "Invalid username or password"

**Possible Causes:**

- Wrong credentials in config
- Authentication bypass enabled but credentials still provided
- Recent password change not reflected in config

**Solutions:**

1. **Verify credentials:**
   - Open qBittorrent Web UI manually
   - Try logging in with the same credentials from `config.toml`
   - If login fails, update credentials in qBittorrent settings

2. **Check authentication bypass:**
   - In qBittorrent: **Tools** → **Options** → **Web UI** → **Authentication**
   - If "Bypass authentication for clients on localhost" is enabled:
     ```toml
     [qBit]
     UserName = ""
     Password = ""
     ```

3. **Test login manually:**
   ```bash
   curl -i --header "Referer: http://localhost:8080" \
     --data "username=admin&password=yourpass" \
     http://localhost:8080/api/v2/auth/login
   ```
   Expected: `Ok.` response

---

#### Symptom: Connection errors or API failures

**Possible Causes:**

- Incorrect host or port configuration
- Authentication credentials are wrong
- qBittorrent WebUI is not enabled
- Network connectivity issues

**Solutions:**

1. **Verify qBittorrent is running and accessible:**
   - Open qBittorrent WebUI in a browser: `http://localhost:8080`
   - Check **Tools** → **Options** → **Web UI** is enabled

2. **Check configuration:**
   ```toml
   [qBit]
   Host = "localhost"
   Port = 8080
   UserName = "admin"
   Password = "password"
   ```

3. **Test connectivity manually:**
   ```bash
   curl http://localhost:8080/api/v2/app/version
   ```

4. **Restart qBitrr after config change**

---

### Arr Instance Connection Failures

#### Symptom: "Connection refused" when connecting to Radarr/Sonarr/Lidarr

**Solutions:**

1. **Test Arr API manually:**
   ```bash
   # Radarr
   curl -H "X-Api-Key: your-api-key" http://localhost:7878/api/v3/system/status

   # Sonarr
   curl -H "X-Api-Key: your-api-key" http://localhost:8989/api/v3/system/status

   # Lidarr
   curl -H "X-Api-Key: your-api-key" http://localhost:8686/api/v1/system/status
   ```

2. **Verify URI format:**
   ```toml
   # ✅ Correct
   URI = "http://localhost:7878"

   # ❌ Incorrect (missing http://)
   URI = "localhost:7878"

   # ❌ Incorrect (trailing slash)
   URI = "http://localhost:7878/"
   ```

3. **Check API key:**
   - Copy API key from Arr instance: **Settings** → **General** → **Security**
   - Paste into `config.toml` (no extra spaces!)
   - API keys are case-sensitive

4. **Docker networking:**
   - If Arr and qBitrr are in the same Docker network, use service name:
     ```toml
     URI = "http://radarr:7878"  # Not "localhost"
     ```

---

## Torrent Processing Issues

### Torrents Not Being Monitored

#### Symptom: qBitrr starts but doesn't process any torrents

**Common Cause: Category Mismatch**

The #1 reason qBitrr doesn't process torrents is **mismatched categories**.

**How to Fix:**

1. **Check Arr download client category:**
   - Radarr/Sonarr/Lidarr → **Settings** → **Download Clients**
   - Click your qBittorrent client
   - Note the **Category** field (e.g., `radarr-movies`)

2. **Check qBitrr config:**
   ```toml
   [Radarr-Movies]
   Category = "radarr-movies"  # Must EXACTLY match!
   ```

3. **Check existing torrents in qBittorrent:**
   - Open qBittorrent
   - Look at the **Category** column for your Arr torrents
   - Categories must match between qBittorrent, Arr, and qBitrr

4. **Enable debug logging to verify:**
   ```toml
   [Settings]
   ConsoleLevel = "DEBUG"
   ```
   Look for: `Processing category: radarr-movies` in logs

**Other Causes:**

- **Missing tags:** Arr instances need to tag torrents. Check `Settings.Tagless` if you don't use tags.
- **Instance disabled:** Verify `Managed = true` in the Arr section
- **qBit disabled:** Check `[qBit] Disabled = false`

---

### Torrents Instantly Marked as Failed

#### Symptom: Torrents are added but immediately fail

**Possible Causes:**

1. **Too young:** qBitrr ignores torrents younger than `IgnoreTorrentsYoungerThan` (default: 180 seconds)

   **Solution:** Wait 3 minutes, or lower the value:
   ```toml
   [Settings]
   IgnoreTorrentsYoungerThan = 60  # 1 minute
   ```

2. **File extension not allowed:**

   **Solution:** Add missing extensions to allowlist:
   ```toml
   [Radarr-Movies.Torrent]
   FileExtensionAllowlist = [".mp4", ".mkv", ".avi", ".!qB", ".parts"]
   ```

3. **FFprobe validation failure:**

   **Solution:** Check FFprobe logs or disable validation temporarily

4. **ETA exceeds maximum:**

   **Solution:** Increase or disable MaxETA:
   ```toml
   [Radarr-Movies.Torrent]
   MaximumETA = -1  # Disable
   # Or increase: MaximumETA = 86400  # 24 hours
   ```

---

### Stalled Torrents Not Being Handled

#### Symptom: Torrents stall but qBitrr doesn't remove them

**Solutions:**

1. **Check stalled delay setting:**
   ```toml
   [Radarr-Movies.Torrent]
   StalledDelay = 15  # Wait 15 minutes before removal
   ```
   - `-1` = Disabled (never remove stalled)
   - `0` = Immediate removal
   - `>0` = Wait N minutes before removal

2. **Verify torrent is actually stalled:**
   - In qBittorrent, check torrent status
   - "Stalled" means no peers and no progress

3. **Enable re-search for stalled:**
   ```toml
   [Radarr-Movies.Torrent]
   ReSearchStalled = true  # Search before removing
   ```

4. **Check logs for stall detection:**
   ```bash
   tail -f ~/logs/Radarr-Movies.log | grep -i stall
   ```

---

## Search Issues

### Automated Searches Not Running

#### Symptom: qBitrr runs but doesn't search for missing media

**Root Cause:** SearchMissing is the master switch for all search features.

**Solutions:**

1. **Enable SearchMissing (required):**
   ```toml
   [Radarr-Movies.EntrySearch]
   SearchMissing = true  # REQUIRED - master switch for all search features
   ```

   **Important:** DoUpgradeSearch, QualityUnmetSearch, CustomFormatUnmetSearch, and request processing (Overseerr/Ombi) will ONLY work if SearchMissing is enabled.

2. **Check search loop startup in logs:**
   ```bash
   grep "Search loop starting\|Search loop initialized" ~/logs/Radarr-Movies.log
   ```

   You should see:
   ```
   Search loop starting for Radarr-Movies (SearchMissing=True, ...)
   Search loop initialized successfully, entering main loop
   ```

3. **If search loop crashes or exits unexpectedly:**
   ```bash
   grep "Search loop crashed\|Search loop terminated" ~/logs/Radarr-Movies.log
   ```

   If you see "Search loop crashed", check the full traceback above that line.

4. **Common mistake - SearchLoopDelay:**

   Note: `SearchLoopDelay` controls the delay **between individual searches** in a batch, not whether searches run.
   ```toml
   [Settings]
   SearchLoopDelay = -1  # -1 = uses default 30s between each search
   ```

5. **Verify Arr has missing media:**
   - Open Radarr/Sonarr → **Wanted** → **Missing**
   - If empty, there's nothing to search for

6. **Check indexer connectivity:**
   - In Arr instance: **System** → **Status**
   - Ensure indexers are enabled and reachable

---

### Overseerr/Ombi Requests Not Processing

#### Symptom: User requests aren't being searched

**Solutions:**

1. **Enable request processing:**
   ```toml
   [Radarr-Movies.EntrySearch.Overseerr]
   SearchOverseerrRequests = true
   ```

2. **Verify connection details:**
   ```toml
   OverseerrURI = "http://localhost:5055"  # Correct URI?
   OverseerrAPIKey = "your-api-key"         # Valid API key?
   ```

3. **Test API manually:**
   ```bash
   curl -H "X-Api-Key: your-api-key" \
     http://localhost:5055/api/v1/request
   ```

4. **Check approval status:**
   ```toml
   ApprovedOnly = true  # Only processes approved requests
   ```
   - If `true`, make sure requests are approved in Overseerr
   - Set to `false` to process all requests

5. **Verify 4K instance flag:**
   ```toml
   Is4K = true  # For 4K Radarr instances
   ```
   Must match your Overseerr configuration

---

### Searches Trigger But Find Nothing

#### Symptom: qBitrr searches but Arr reports "No results"

**This is usually an Arr/indexer issue, not qBitrr.**

**Solutions:**

1. **Test search in Arr directly:**
   - Go to **Wanted** → **Missing**
   - Click **Search** for a specific item
   - Check if Arr finds results

2. **Check indexer configuration:**
   - **Settings** → **Indexers**
   - Test each indexer
   - Review indexer logs for errors

3. **Check indexer rate limits:**
   - Some indexers have API rate limits
   - qBitrr's searches count against your limit
   - Review indexer stats/logs

4. **Verify quality profile settings:**
   - Overly strict quality profiles may filter out all results
   - Temporarily lower standards to test

5. **Check custom format scores:**
   - If using custom formats, high minimum scores may block releases
   - Temporarily disable CF scoring to test

---

## Import Issues

### Files Not Importing After Download

#### Symptom: Torrent completes but Arr doesn't import files

**Solutions:**

1. **Check path mapping:**
   - qBittorrent's save path must be accessible to Arr
   - Common Docker issue: mismatched volume paths

   **Example (Docker):**
   ```yaml
   qbittorrent:
     volumes:
       - /mnt/data/torrents:/downloads

   radarr:
     volumes:
       - /mnt/data/torrents:/downloads  # Must match!
   ```

2. **Verify CompletedDownloadFolder:**
   ```toml
   [Settings]
   CompletedDownloadFolder = "/downloads"  # Must be accessible to qBitrr
   ```

3. **Check file permissions:**
   ```bash
   # All files must be readable by Arr instance
   ls -l /path/to/completed/downloads
   ```

4. **Enable instant import:**
   - qBitrr triggers instant imports automatically
   - Check logs for import triggers:
     ```bash
     tail -f ~/logs/Main.log | grep -i import
     ```

5. **Manual import test in Arr:**
   - **Activity** → **Queue**
   - Click **Manual Import** for the download
   - Check error messages

---

### Import Succeeds But Quality Is Wrong

#### Symptom: Files import but don't match expected quality

**This is usually an Arr quality profile issue.**

**Solutions:**

1. **Review quality profile:**
   - **Settings** → **Profiles**
   - Check which qualities are allowed
   - Verify upgrade conditions

2. **Check custom formats:**
   - **Settings** → **Custom Formats**
   - Review scoring and minimum scores
   - Ensure downloaded file meets requirements

3. **Use quality upgrade search:**
   ```toml
   [Radarr-Movies.EntrySearch]
   DoUpgradeSearch = true
   QualityUnmetSearch = true
   ```

4. **Enable temp profile switching:**
   ```toml
   UseTempForMissing = true
   QualityProfileMappings = { "Ultra-HD" = "HD-1080p" }
   ```
   This grabs *something* initially, then upgrades later

---

## Performance Issues

### High CPU Usage

**Possible Causes:**

1. **Too frequent loop processing:**
   ```toml
   [Settings]
   LoopSleepTimer = 1  # Very aggressive
   ```
   **Solution:** Increase to 5-10 seconds:
   ```toml
   LoopSleepTimer = 5
   ```

2. **Too many concurrent searches:**
   ```toml
   [Radarr-Movies.EntrySearch]
   SearchLimit = 10  # Too high
   ```
   **Solution:** Lower to 3-5:
   ```toml
   SearchLimit = 3
   ```

3. **Database locked:**
   - Multiple qBitrr instances accessing same database
   - **Solution:** Use separate config directories for multiple instances

---

### High Memory Usage

**Possible Causes:**

1. **Large torrent libraries:**
   - Processing thousands of torrents uses significant RAM
   - **Solution:** Split libraries across multiple Arr instances

2. **Extensive logging:**
   ```toml
   [Settings]
   ConsoleLevel = "TRACE"  # Very verbose
   ```
   **Solution:** Use INFO or WARNING:
   ```toml
   ConsoleLevel = "INFO"
   ```

3. **WebUI live updates:**
   ```toml
   [WebUI]
   LiveArr = true  # Increases memory usage
   ```
   **Solution:** Disable if not needed:
   ```toml
   LiveArr = false
   ```

---

## Disk Space Issues

### qBitrr Doesn't Pause Torrents When Disk Is Full

**Solutions:**

1. **Enable AutoPauseResume:**
   ```toml
   [Settings]
   AutoPauseResume = true
   ```

2. **Set FreeSpace threshold:**
   ```toml
   FreeSpace = "50G"  # Pause when <50GB free
   ```
   Supported units: K (KB), M (MB), G (GB), T (TB)

3. **Set FreeSpaceFolder:**
   ```toml
   FreeSpaceFolder = "/downloads"  # Path to check
   ```
   Must be the mount point or directory to monitor

4. **Verify path is correct:**
   ```bash
   df -h /downloads  # Check available space
   ```

---

### Torrents Removed But Disk Space Not Freed

**Possible Causes:**

1. **Files copied, not moved:**
   ```toml
   [Radarr-Movies]
   importMode = "Copy"  # Leaves files in download folder
   ```
   **Solution:** Use Move to free space:
   ```toml
   importMode = "Move"
   ```

2. **Seeding torrents:**
   - Files remain until seeding goals met
   - **Solution:** Adjust seeding limits:
     ```toml
     [Radarr-Movies.Torrent.SeedingMode]
     MaxUploadRatio = 1.0  # Lower ratio
     MaxSeedingTime = 86400  # 1 day
     RemoveTorrent = 1  # Remove when ratio met
     ```

3. **MaximumDeletablePercentage protection:**
   ```toml
   [Radarr-Movies.Torrent]
   MaximumDeletablePercentage = 0.99  # Won't delete nearly-complete
   ```

---

## Configuration Issues

### Config Changes Not Taking Effect

**Solutions:**

1. **Restart qBitrr:**
   - Config is loaded only at startup
   - Changes require restart to apply

2. **Check config syntax:**
   - TOML syntax errors prevent loading
   - Test with online TOML validator

3. **Check config location:**
   - **Docker:** `/config/config.toml`
   - **Native:** `~/config/config.toml`
   - Verify qBitrr is reading the correct file

4. **Enable debug logging:**
   ```toml
   [Settings]
   ConsoleLevel = "DEBUG"
   ```
   Look for config loading messages

---

### Config File Regenerates or Resets

**Possible Causes:**

1. **File permissions:**
   - qBitrr can't write to config file
   - **Solution:** Fix permissions:
     ```bash
     chmod 644 ~/config/config.toml
     chown qbitrr:qbitrr ~/config/config.toml
     ```

2. **Invalid syntax:**
   - qBitrr detected invalid TOML and regenerated defaults
   - **Solution:** Restore from backup, fix syntax errors

3. **Config migration:**
   - qBitrr auto-migrates old configs
   - Check logs for migration messages
   - Backups created at `/config/config.toml.backup_*`

---

## WebUI Issues

### Can't Access WebUI

**Solutions:**

1. **Check WebUI settings:**
   ```toml
   [WebUI]
   Host = "0.0.0.0"  # Listen on all interfaces
   Port = 6969        # Default port
   ```

2. **Test connection:**
   ```bash
   curl http://localhost:6969/api/health
   ```

3. **Check firewall:**
   ```bash
   # Allow port 6969
   sudo ufw allow 6969/tcp
   ```

4. **Docker port mapping:**
   ```yaml
   services:
     qbitrr:
       ports:
         - "6969:6969"  # host:container
   ```

---

### WebUI Requires Token But I Don't Have One

**Solution:**

1. **Token is optional:**
   ```toml
   [WebUI]
   Token = ""  # Empty = no authentication required
   ```

2. **If Token is set but lost:**
   - Edit `/config/config.toml`
   - Set `Token = ""`
   - Restart qBitrr

3. **Access logs without WebUI:**
   ```bash
   # Docker
   docker logs qbitrr

   # Native
   tail -f ~/logs/Main.log
   ```

---

## Logging Issues

### Logs Not Being Created

**Solutions:**

1. **Enable logging:**
   ```toml
   [Settings]
   Logging = true
   ```

2. **Check log directory:**
   - **Docker:** `/config/logs/`
   - **Native:** `~/logs/`
   - Verify directory exists and is writable

3. **Check permissions:**
   ```bash
   chmod 755 /config/logs
   chown -R qbitrr:qbitrr /config/logs
   ```

---

### Logs Too Verbose or Too Quiet

**Adjust logging level:**

```toml
[Settings]
ConsoleLevel = "INFO"  # CRITICAL, ERROR, WARNING, NOTICE, INFO, DEBUG, TRACE
```

**Recommendations:**

- **Production:** `INFO` or `WARNING`
- **Troubleshooting:** `DEBUG`
- **Development:** `TRACE` (very verbose!)

---

## Getting More Help

If your issue isn't covered here:

1. **Enable debug logging:**
   ```toml
   [Settings]
   ConsoleLevel = "DEBUG"
   ```

2. **Collect relevant logs:**
   - `Main.log` – Core qBitrr operations
   - `Radarr-Movies.log` – Arr-specific processing
   - `WebUI.log` – WebUI-related issues

3. **Check FAQ:** [Frequently Asked Questions](../faq.md)

4. **Report issue on GitHub:** [github.com/Feramance/qBitrr/issues](https://github.com/Feramance/qBitrr/issues)
   - Include config (redact API keys!)
   - Include relevant log excerpts
   - Describe expected vs. actual behavior

---

## Error Reference

### Exception Hierarchy

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

### Python Exceptions

| Exception | Purpose | Common Causes |
|-----------|---------|---------------|
| `qBitManagerError` | Base exception for all qBitrr errors | Catch-all for qBitrr exceptions |
| `UnhandledError` | Unhandled edge case encountered | Unexpected API response, unknown torrent state |
| `ConfigException` | Configuration parsing/validation error | Invalid TOML syntax, missing required fields |
| `RequireConfigValue` | Specific config value missing | Missing API key, missing host |
| `ArrManagerException` | Arr-related error | API connection failure, invalid response, instance offline |
| `RestartLoopException` | Signal event loop to restart | Config changed, manual restart requested |
| `DelayLoopException` | Delay next event loop iteration | Network failure, temporary API unavailability |
| `NoConnectionrException` | Connection failure with retry logic | Cannot connect to qBittorrent or Arr instance |
| `SkipException` | Skip current torrent, continue next | Torrent doesn't match criteria, already processed |

### Exit Codes

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

### HTTP Status Codes

qBitrr WebUI API returns standard HTTP status codes:

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request succeeded |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid API token |
| 404 | Not Found | Endpoint or resource not found |
| 500 | Internal Server Error | Server error |

---

## Related Documentation

- [Docker Troubleshooting](docker.md)
- [qBittorrent Configuration](../configuration/qbittorrent.md)
- [Radarr Configuration](../configuration/arr/radarr.md)
- [Sonarr Configuration](../configuration/arr/sonarr.md)
