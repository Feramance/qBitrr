# FFprobe Integration

qBitrr uses FFprobe to validate media files before importing them to Arr instances, preventing corrupt or invalid files from being added to your library.

## Overview

**FFprobe** is part of the FFmpeg project and provides detailed information about media files including:

- Video codec, resolution, bitrate
- Audio codec, channels, sample rate
- Container format
- Duration
- Stream information

## Configuration

### Basic Setup

Enable FFprobe validation:

```toml
[Settings]
FFprobeAutoUpdate = true
FFprobePath = "/usr/bin/ffprobe"  # Auto-detected if not specified
```

### Auto-Download

qBitrr can automatically download FFprobe if not found:

```toml
[Settings]
FFprobeAutoUpdate = true  # Default: true
```

**Supported Platforms:**
- Linux (x86_64, ARM, ARM64)
- Windows (x86, x64)
- macOS (x64)

**Download Source:** [FFBinaries](https://ffbinaries.com/)

### Manual Installation

If auto-download fails or you prefer manual installation:

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**Linux (RHEL/CentOS):**
```bash
sudo yum install ffmpeg
```

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Docker:**

FFprobe is pre-installed in the official qBitrr Docker image.

## Validation Rules

### Video Validation

Check video stream properties:

```toml
[Settings.FFprobe]
CheckVideoCodec = true
AllowedVideoCodecs = ["h264", "h265", "hevc", "av1", "mpeg4", "vp9"]

CheckVideoResolution = true
MinWidth = 720   # Minimum resolution width
MinHeight = 480  # Minimum resolution height

CheckVideoBitrate = true
MinVideoBitrate = 1000000  # 1 Mbps minimum
```

### Audio Validation

Check audio stream properties:

```toml
[Settings.FFprobe]
CheckAudioCodec = true
AllowedAudioCodecs = ["aac", "ac3", "eac3", "dts", "truehd", "flac", "opus"]

CheckAudioChannels = true
MinAudioChannels = 2  # Require stereo or better

RequireAudioTrack = true  # Fail if no audio track
```

### Duration Validation

Ensure files meet minimum duration:

```toml
[Settings.FFprobe]
CheckDuration = true
MinDuration = 60  # Reject files shorter than 1 minute
```

**Use Cases:**
- Filter out trailer files accidentally downloaded
- Detect truncated/incomplete downloads
- Ensure minimum content quality

### Container Format

Validate container format:

```toml
[Settings.FFprobe]
CheckContainer = true
AllowedContainers = ["matroska", "mp4", "avi", "mov"]
```

## Validation Process

### Workflow

```
1. Torrent Completes
   ↓
2. qBitrr Triggers Import
   ↓
3. FFprobe Validation
   │
   ├─ Find largest video file
   ├─ Run: ffprobe -v quiet -print_format json -show_format -show_streams file.mkv
   ├─ Parse JSON output
   ├─ Check against validation rules
   │
   ├─ PASS → Continue to import
   │
   └─ FAIL → Blacklist torrent
```

### Command Execution

**Command run by qBitrr:**

```bash
ffprobe \
  -v quiet \
  -print_format json \
  -show_format \
  -show_streams \
  -show_chapters \
  "/path/to/downloaded/file.mkv"
```

**Example output:**

```json
{
  "streams": [
    {
      "codec_name": "h264",
      "codec_type": "video",
      "width": 1920,
      "height": 1080,
      "bit_rate": "5000000"
    },
    {
      "codec_name": "aac",
      "codec_type": "audio",
      "channels": 6,
      "sample_rate": "48000"
    }
  ],
  "format": {
    "filename": "/path/to/file.mkv",
    "format_name": "matroska,webm",
    "duration": "7265.536000",
    "size": "4567123456",
    "bit_rate": "5020000"
  }
}
```

### File Selection

For torrents with multiple video files:

**Selection Logic:**

1. Filter to video files only (`.mkv`, `.mp4`, `.avi`, etc.)
2. Sort by file size (largest first)
3. Select the largest file for validation
4. Optionally validate all files if configured

```toml
[Settings.FFprobe]
ValidateAllFiles = false  # Only validate largest (default)
# ValidateAllFiles = true   # Validate every video file
```

## Error Handling

### Common Errors

#### FFprobe Not Found

**Error:**
```
FFprobe binary not found at /usr/bin/ffprobe
```

**Solutions:**
1. Enable auto-download: `FFprobeAutoUpdate = true`
2. Install manually: `apt-get install ffmpeg`
3. Specify custom path: `FFprobePath = "/custom/path/ffprobe"`

#### Invalid/Corrupt File

**Log:**
```
[WARNING] FFprobe validation failed for torrent abc123: Invalid data found when processing input
```

**Action:** Torrent is blacklisted, new search triggered (if AutoReSearch enabled)

#### Missing Streams

**Log:**
```
[WARNING] FFprobe validation failed for torrent abc123: No video stream found
```

**Common Causes:**
- Audio-only file (audiobook, music)
- Corrupt download
- Unsupported container format

### Timeout Configuration

Prevent FFprobe from hanging:

```toml
[Settings.FFprobe]
Timeout = 30  # Kill FFprobe after 30 seconds
```

## Performance Impact

### Typical Validation Times

| File Size | Format | Duration |
|-----------|--------|----------|
| 1 GB | MKV | 0.5s |
| 5 GB | MKV | 1-2s |
| 20 GB | MKV | 3-5s |
| 50 GB | MKV | 10-15s |

**Factors:**
- Disk speed (SSD vs HDD)
- File location (local vs network)
- Container complexity (many streams = slower)

### Optimization

**Reduce validation time:**

```toml
[Settings.FFprobe]
# Only check essential properties
CheckVideoCodec = true
CheckAudioCodec = true
CheckDuration = true

# Skip non-essential checks
CheckVideoBitrate = false
CheckVideoResolution = false
ValidateAllFiles = false  # Only check largest file
```

**Parallel validation:**

FFprobe runs in a background thread, so validation doesn't block other torrents from being processed.

## Advanced Usage

### Custom Validation Script

Run custom validation logic:

```toml
[Settings]
FFprobePostScript = "/path/to/custom-validator.sh"
```

**Script receives:**
- `$1` - Path to media file
- `$2` - FFprobe JSON output

**Example script:**

```bash
#!/bin/bash
FILE="$1"
FFPROBE_JSON="$2"

# Check for HDR metadata
if echo "$FFPROBE_JSON" | grep -q "color_transfer.*smpte2084"; then
  echo "HDR detected, accepting"
  exit 0
else
  echo "No HDR, rejecting"
  exit 1
fi
```

### Integration with Arr

FFprobe results can influence Arr quality matching:

```toml
[[Radarr]]
Name = "Radarr-4K"

# Only import 4K content to this instance
[Radarr.FFprobe]
MinWidth = 3840
MinHeight = 2160
```

## Troubleshooting

### Enable Debug Logging

```toml
[Settings]
LogLevel = "DEBUG"
```

**Look for:**
```
[DEBUG] FFprobe command: ffprobe -v quiet ...
[DEBUG] FFprobe output: {"streams": [...]}
[DEBUG] Validation result: PASS (h264, 1920x1080, 7265s)
```

### Test FFprobe Manually

```bash
# Test FFprobe is working
ffprobe -version

# Test on a specific file
ffprobe -v quiet -print_format json -show_format -show_streams /path/to/file.mkv
```

### Common Issues

**Issue:** FFprobe hangs on certain files

**Solution:**
```toml
[Settings.FFprobe]
Timeout = 10  # Lower timeout to prevent hangs
```

**Issue:** All files fail validation

**Solution:**
```toml
[Settings]
LogLevel = "DEBUG"
FFprobeAutoUpdate = false  # Temporarily disable to isolate issue
```

Check logs to see why validation is failing.

## Docker Considerations

### Volume Permissions

FFprobe needs read access to download files:

```yaml
services:
  qbitrr:
    volumes:
      - /path/to/downloads:/downloads:ro  # Read-only is sufficient
```

### Custom FFprobe Binary

Use custom FFprobe build:

```yaml
services:
  qbitrr:
    volumes:
      - /custom/ffprobe:/usr/local/bin/ffprobe:ro
    environment:
      - QBITRR_FFPROBE_PATH=/usr/local/bin/ffprobe
```

## Future Enhancements

**Planned for v6.0:**

- **Codec Priority** - Prefer certain codecs (e.g., AV1 > HEVC > H.264)
- **HDR Detection** - Auto-detect HDR/Dolby Vision
- **Subtitle Validation** - Check for required subtitle tracks
- **Quality Scoring** - Assign quality score based on multiple factors
- **Cached Results** - Cache validation results to avoid re-checking

## Related Documentation

- [Configuration: Torrents](../configuration/torrents.md) - Torrent handling configuration
- [Features: Health Monitoring](../features/health-monitoring.md) - Health check system
- [Troubleshooting: Common Issues](../troubleshooting/common-issues.md) - Debug validation failures
