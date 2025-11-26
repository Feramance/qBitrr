# Instant Imports

qBitrr's instant import feature triggers media imports in your Arr instances immediately upon download completion, eliminating the wait for periodic scans.

---

## Overview

Traditional workflow (without qBitrr):

1. qBittorrent finishes downloading
2. **Wait for Arr's periodic scan** (usually 1-5 minutes)
3. Arr detects completed download
4. Arr imports to library

With qBitrr's instant imports:

1. qBittorrent finishes downloading
2. **qBitrr detects completion instantly** (within seconds)
3. qBitrr validates files (optional FFprobe check)
4. **qBitrr tells Arr to import immediately**
5. Media appears in library within seconds

---

## How It Works

### Detection Process

```mermaid
graph TD
    A[qBittorrent completes download] --> B{qBitrr Loop Check}
    B -->|Every 5s default| C[Torrent status = Complete]
    C --> D{Managed by Arr?}
    D -->|Yes| E{FFprobe enabled?}
    D -->|No| Z[Skip]
    E -->|Yes| F[Validate media files]
    E -->|No| G[Trigger import command]
    F -->|Valid| G
    F -->|Invalid| H[Mark as failed]
    G --> I[Arr imports immediately]
    H --> J[Re-search if enabled]
```

---

### Key Components

**1. Loop-based Detection**

qBitrr checks torrent status every `LoopSleepTimer` seconds (default: 5):

```toml
[Settings]
LoopSleepTimer = 5  # Check every 5 seconds
```

**2. Completion Detection**

Torrent is considered complete when:

- Progress = 100%
- State = "uploading" or "seeding"
- Not in a special category (`failed`, `recheck`)
- Files are accessible

**3. File Validation (Optional)**

If FFprobe is enabled, qBitrr validates files before import:

```toml
[Settings]
FFprobeAutoUpdate = true
```

**Validation checks:**

- File is playable
- Codecs are valid
- Duration is reasonable
- No corruption detected

**4. Import Trigger**

qBitrr sends an API command to Arr:

```http
POST /api/v3/command
{
  "name": "DownloadsRefresh"
}
```

This forces Arr to immediately check its download queue and import completed items.

---

## Benefits

### Faster Media Availability

**Without qBitrr:**

- Download completes: `00:00:00`
- Arr scan interval: `5 minutes`
- Media available: `00:05:00`

**With qBitrr (LoopSleepTimer=5):**

- Download completes: `00:00:00`
- qBitrr detects: `00:00:05` (max)
- Media available: `00:00:10`

**Improvement:** From 5 minutes to ~10 seconds = **30x faster**

---

### Lower API Load

Traditional approach:

- Arr polls download client every minute
- Checks ALL torrents every scan
- High API call volume

qBitrr approach:

- qBitrr monitors torrents continuously
- Sends targeted import commands
- Arr only processes when needed

**Result:** Reduced API calls, lower resource usage

---

### Better User Experience

For media request systems (Overseerr/Ombi):

1. User requests a movie
2. Radarr searches and downloads
3. **qBitrr imports instantly**
4. User gets notification within seconds
5. Movie appears in Plex/Jellyfin/Emby immediately

**No more:** "Where's my movie? It finished downloading 5 minutes ago!"

---

## Configuration

Instant imports are **automatic** when qBitrr manages an Arr instance. No special configuration needed.

### Basic Setup

```toml
[Radarr-Movies]
# Enable qBitrr management
Managed = true

# Connection details
URI = "http://localhost:7878"
APIKey = "your-radarr-api-key"
Category = "radarr-movies"

# Import mode
importMode = "Auto"
```

That's it! Instant imports are now active.

---

### Tuning Responsiveness

Adjust `LoopSleepTimer` for faster detection:

```toml
[Settings]
# Check every 3 seconds (more responsive)
LoopSleepTimer = 3

# Check every 10 seconds (lower resource usage)
LoopSleepTimer = 10

# Check every 1 second (very responsive, higher CPU)
LoopSleepTimer = 1
```

**Trade-off:** Lower values = faster detection but higher CPU usage.

---

### Import Modes

Control how Arr imports files:

```toml
[Radarr-Movies]
# Let Arr decide based on its settings
importMode = "Auto"

# Move files (faster, frees disk space)
importMode = "Move"

# Copy files (preserves torrents for seeding)
importMode = "Copy"
```

**Recommendation:**

- `Copy` for private trackers (preserve seeding)
- `Move` for public trackers (save space)
- `Auto` to defer to Arr's configuration

---

### FFprobe Validation

Enable pre-import file validation:

```toml
[Settings]
# Auto-download FFprobe binary
FFprobeAutoUpdate = true
```

**When enabled:**

- qBitrr validates media files before triggering import
- Invalid/corrupt files are rejected
- Automatic re-search for valid releases

**When disabled:**

- Files imported without validation
- Faster imports (no validation delay)
- Risk of importing fake/corrupt files

**Recommendation:** Keep enabled for quality assurance.

---

## Import Workflow Examples

### Example 1: Movie Download (Radarr)

```toml
[Radarr-Movies]
Managed = true
URI = "http://localhost:7878"
APIKey = "abc123"
Category = "radarr-movies"
importMode = "Auto"
```

**Process:**

1. User adds "The Matrix (1999)" to Radarr
2. Radarr searches and sends torrent to qBittorrent
3. qBittorrent downloads `The.Matrix.1999.1080p.mkv`
4. Download completes
5. **qBitrr detects completion** (within 5 seconds)
6. qBitrr validates file with FFprobe (2-3 seconds)
7. **qBitrr triggers Radarr import**
8. Radarr imports to `/movies/The Matrix (1999)/`
9. **Total time: ~10 seconds after download**

---

### Example 2: TV Episode (Sonarr)

```toml
[Sonarr-TV]
Managed = true
URI = "http://localhost:8989"
APIKey = "def456"
Category = "sonarr-tv"
importMode = "Copy"
```

**Process:**

1. Sonarr monitors "Breaking Bad" for new episodes
2. S05E16 releases, Sonarr downloads torrent
3. qBittorrent downloads episode
4. Download completes
5. **qBitrr detects completion**
6. qBitrr validates file
7. **qBitrr triggers Sonarr import**
8. Sonarr **copies** file to `/tv/Breaking Bad/Season 5/`
9. Torrent continues seeding (because `importMode = "Copy"`)
10. Episode available immediately

---

### Example 3: Album Download (Lidarr)

```toml
[Lidarr-Music]
Managed = true
URI = "http://localhost:8686"
APIKey = "ghi789"
Category = "lidarr-music"
importMode = "Copy"
```

**Process:**

1. User adds "Pink Floyd - Dark Side of the Moon" to Lidarr
2. Lidarr searches, downloads FLAC torrent
3. qBittorrent downloads 11 tracks
4. Download completes
5. **qBitrr detects completion**
6. qBitrr validates all 11 FLAC files
7. **qBitrr triggers Lidarr import**
8. Lidarr copies album to `/music/Pink Floyd/The Dark Side of the Moon/`
9. Album available in music player within seconds
10. Torrent continues seeding

---

## Integration with Other Features

### Health Monitoring

If a file fails validation:

1. qBitrr marks torrent as failed
2. Removes torrent and files
3. Blacklists release in Arr
4. **Triggers re-search** (if enabled)
5. Arr downloads alternative release
6. Process repeats until valid file is found

See: [Health Monitoring](health-monitoring.md)

---

### Automated Re-searching

When imports fail:

```toml
[Radarr-Movies]
ReSearch = true
```

qBitrr automatically:

- Detects import failure
- Tells Radarr to search again
- Downloads new release
- Triggers instant import for new release

---

### Request Integration

For Overseerr/Ombi setups:

```toml
[Radarr-Movies.Overseerr]
OverseerrURL = "http://localhost:5055"
OverseerrAPIKey = "overseerr-key"
ApprovedOnly = true
```

**Workflow:**

1. User requests movie in Overseerr
2. Admin approves request
3. Radarr downloads movie
4. **qBitrr imports instantly**
5. **Overseerr detects availability**
6. **User gets notification** (within seconds)
7. Movie ready to watch

**Result:** Nearly instant gratification for media requests!

---

## Timing Breakdown

### Fast Connection (100 Mbps)

| Step | Time | Cumulative |
|------|------|------------|
| Search & select release | 5s | 5s |
| qBittorrent starts download | 2s | 7s |
| Download 5GB movie | 400s | 407s (6m 47s) |
| **qBitrr detects completion** | **5s** | **412s (6m 52s)** |
| **FFprobe validation** | **3s** | **415s (6m 55s)** |
| **qBitrr triggers import** | **1s** | **416s (6m 56s)** |
| **Arr imports file** | **4s** | **420s (7m)** |

**Without qBitrr:** +5 minutes wait for Arr scan = **12 minutes total**
**With qBitrr:** **7 minutes total**

**Savings:** 5 minutes per download

---

### Slow Connection (10 Mbps)

| Step | Time | Cumulative |
|------|------|------------|
| Search & select release | 5s | 5s |
| Download 5GB movie | 4000s | 4005s (66m 45s) |
| **qBitrr detects** | **5s** | **4010s (66m 50s)** |
| **Validation + Import** | **5s** | **4015s (66m 55s)** |

**Without qBitrr:** +5 minutes = **72 minutes total**
**With qBitrr:** **67 minutes total**

**Savings:** Still 5 minutes, regardless of download speed!

---

## Monitoring Imports

### WebUI

View import status in real-time:

1. Open WebUI: `http://localhost:6969/ui`
2. Navigate to Arr tab (Radarr/Sonarr/Lidarr)
3. Watch progress bars and status updates

**Status indicators:**

- 🟢 **Downloading** - Torrent actively downloading
- 🟡 **Complete** - Download finished, waiting for import
- 🔵 **Importing** - Arr is importing the file
- ✅ **Imported** - Successfully imported to library

---

### Logs

Monitor imports in log files:

```bash
# Main log
tail -f ~/logs/Main.log

# Specific Arr instance
tail -f ~/logs/Radarr-Movies.log

# Filter for import events
grep -i "import" ~/logs/Radarr-Movies.log
```

**Example log output:**

```
2025-11-26 15:30:45 - INFO - Detected completed download: The Matrix (1999)
2025-11-26 15:30:48 - INFO - FFprobe validation passed
2025-11-26 15:30:49 - INFO - Triggering import command in Radarr
2025-11-26 15:30:53 - INFO - Import successful: The Matrix (1999)
```

---

## Troubleshooting

### Imports Not Triggering

**Symptom:** Download completes but Arr doesn't import immediately

**Solutions:**

1. **Verify Arr is managed:**
   ```toml
   [Radarr-Movies]
   Managed = true  # Must be true
   ```

2. **Check category match:**
   ```toml
   # qBitrr config
   [Radarr-Movies]
   Category = "radarr-movies"

   # Must match Radarr's qBittorrent download client category
   ```

3. **Check LoopSleepTimer:**
   ```toml
   [Settings]
   LoopSleepTimer = 5  # Lower for faster detection
   ```

4. **Review logs:**
   ```bash
   grep -i "import\|complete" ~/logs/Radarr-Movies.log
   ```

---

### Slow Imports

**Symptom:** qBitrr detects but import takes a long time

**Causes:**

1. **FFprobe validation delay**
   - Large files take longer to validate
   - Solution: Disable FFprobe for faster imports (less safe)

2. **Arr is busy**
   - Arr processing many imports
   - Solution: Increase Arr's task concurrency

3. **Network latency**
   - High latency to Arr API
   - Solution: Optimize network, use Docker networking

4. **Disk I/O bottleneck**
   - Slow disk write speeds
   - Solution: Upgrade storage, use SSD

---

### Imports Failing

**Symptom:** qBitrr triggers import but Arr rejects it

**Solutions:**

1. **Check Arr logs:**
   - Radarr → System → Logs
   - Look for import errors

2. **Verify path mapping (Docker):**
   - Ensure Arr and qBittorrent see same path
   - Radarr → Settings → Download Clients → Remote Path Mappings

3. **Check file permissions:**
   ```bash
   ls -l /path/to/download
   ```

4. **Verify quality profile:**
   - File must meet Arr's quality requirements

---

### Duplicate Imports

**Symptom:** Arr imports the same file multiple times

**Solutions:**

1. **Check for duplicate Arr instances:**
   - Only one instance should manage each category

2. **Verify category uniqueness:**
   ```toml
   [Radarr-Movies]
   Category = "radarr-movies"  # Unique per instance

   [Radarr-4K]
   Category = "radarr-4k"  # Different category
   ```

3. **Check Arr's import mode:**
   - Use "Move" instead of "Copy" if duplicates persist

---

## Performance Optimization

### Low-Resource Systems

For systems with limited CPU/RAM:

```toml
[Settings]
# Slower polling (lower CPU)
LoopSleepTimer = 10

# Disable FFprobe (saves CPU)
FFprobeAutoUpdate = false
```

---

### High-Throughput Systems

For systems handling many downloads:

```toml
[Settings]
# Faster polling (higher CPU, more responsive)
LoopSleepTimer = 2

# Enable FFprobe for quality assurance
FFprobeAutoUpdate = true

# Lower queue size in Arr settings
# Prevents import queue backlog
```

---

### Docker Networking

Optimize Docker container communication:

```yaml
services:
  qbitrr:
    networks:
      - media

  radarr:
    networks:
      - media

  qbittorrent:
    networks:
      - media

networks:
  media:
    driver: bridge
```

**Then use container names in config:**

```toml
[Radarr-Movies]
URI = "http://radarr:7878"  # Container name, not localhost

[qBit]
Host = "qbittorrent"  # Container name
```

**Benefit:** Lower latency, faster imports

---

## Comparison: With vs Without qBitrr

### Traditional Setup (No qBitrr)

```
User requests movie
↓ (30s search)
Radarr sends to qBittorrent
↓ (400s download)
Download completes
↓ ⏰ (300s WAITING for Arr scan)
Arr scans queue
↓ (5s import)
Movie available
━━━━━━━━━━━━━━━━
TOTAL: ~735s (12 minutes 15 seconds)
```

### With qBitrr

```
User requests movie
↓ (30s search)
Radarr sends to qBittorrent
↓ (400s download)
Download completes
↓ ⚡ (5s qBitrr detects)
↓ (3s FFprobe validates)
↓ (1s qBitrr triggers import)
↓ (5s Arr imports)
Movie available
━━━━━━━━━━━━━━━━
TOTAL: ~444s (7 minutes 24 seconds)
```

**Improvement:** 5 minutes faster (40% reduction)

---

## Best Practices

### 1. Tune LoopSleepTimer for Your Needs

```toml
# High-traffic server (many downloads)
LoopSleepTimer = 3

# Personal setup (few downloads)
LoopSleepTimer = 5

# Low-power device (Raspberry Pi)
LoopSleepTimer = 10
```

---

### 2. Use FFprobe for Quality Assurance

```toml
# Recommended for all setups
FFprobeAutoUpdate = true
```

Prevents importing fake/corrupt files.

---

### 3. Match Import Modes to Use Case

```toml
# Private trackers (must seed)
importMode = "Copy"

# Public trackers (save space)
importMode = "Move"

# Mixed trackers
importMode = "Auto"
```

---

### 4. Monitor Logs Initially

Watch logs for the first few days to ensure imports work correctly:

```bash
tail -f ~/logs/Main.log ~/logs/Radarr-Movies.log ~/logs/Sonarr-TV.log
```

---

### 5. Coordinate with Request Systems

For Overseerr/Ombi:

```toml
[Radarr-Movies.Overseerr]
OverseerrURL = "http://overseerr:5055"
OverseerrAPIKey = "your-key"
ApprovedOnly = true
```

Ensures users get instant notifications.

---

## See Also

- [Health Monitoring](health-monitoring.md) - Torrent health checks
- [Automated Search](automated-search.md) - Missing content search
- [Configuration Reference](../configuration/config-file.md) - All config options
- [Radarr Configuration](../configuration/arr/radarr.md) - Radarr setup
- [Sonarr Configuration](../configuration/arr/sonarr.md) - Sonarr setup
- [Lidarr Configuration](../configuration/arr/lidarr.md) - Lidarr setup
