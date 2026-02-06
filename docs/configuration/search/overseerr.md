# Overseerr Integration

!!! tip "Requestrr Integration"
    Want Discord-based requests? Configure Requestrr to use Overseerr as its backend,
    then qBitrr will automatically process those requests.
    [**→ Requestrr Integration Guide**](requestrr.md)

Overseerr is a request management and media discovery tool. qBitrr can integrate with Overseerr to automatically search for user-requested content, ensuring your users get their requests fulfilled as quickly as possible.

## Overview

When Overseerr integration is enabled, qBitrr will:

- **Monitor Overseerr Requests**: Periodically check for new requests (movies/TV shows)
- **Trigger Automated Searches**: Tell Radarr/Sonarr to search for requested content
- **Respect Request Status**: Only process requests based on their approval/availability status
- **Support 4K Instances**: Separate handling for standard and 4K Radarr/Sonarr instances
- **Cache Release Dates**: Skip searches for content not yet released

---

## How It Works

### Request Flow

```mermaid
graph LR
    A[User Makes Request in Overseerr] --> B[Overseerr Marks as Approved/Pending]
    B --> C[qBitrr Polls Overseerr API]
    C --> D[qBitrr Filters by Status & Release Date]
    D --> E[qBitrr Triggers Search in Arr]
    E --> F[Arr Searches Indexers]
    F --> G[Torrent Downloaded to qBittorrent]
    G --> H[qBitrr Monitors & Imports]
    H --> I[Overseerr Marks as Available]
```

### Key Features

1. **Approved-Only Mode**: Only search for requests that have been approved by admins
2. **Unreleased Content**: Skip searching for movies/shows not yet released
3. **4K Support**: Separate handling for 4K requests using `Is4K` flag
4. **Status Filtering**: Only process requests in "processing" state (not already available)
5. **Efficient Polling**: Caches release dates to avoid redundant API calls

---

## Configuration

### Basic Setup (Movies)

```toml
[Radarr-Movies]
Managed = true
URI = "http://localhost:7878"
APIKey = "your-radarr-api-key"
Category = "radarr-movies"

[Radarr-Movies.EntrySearch]
SearchMissing = true  # Must be enabled for request integration
SearchLimit = 5
SearchRequestsEvery = 3  # Check requests every 3 loops

[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "your-overseerr-api-key"
ApprovedOnly = true  # Only search approved requests
Is4K = false  # Standard quality instance
```

### Basic Setup (TV Shows)

```toml
[Sonarr-Series]
Managed = true
URI = "http://localhost:8989"
APIKey = "your-sonarr-api-key"
Category = "sonarr-series"

[Sonarr-Series.EntrySearch]
SearchMissing = true
SearchLimit = 5
SearchRequestsEvery = 3

[Sonarr-Series.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "your-overseerr-api-key"
ApprovedOnly = true
Is4K = false
```

### 4K Instance Setup

For a dedicated 4K Radarr instance:

```toml
[Radarr-4K]
Managed = true
URI = "http://localhost:7879"  # Different port for 4K instance
APIKey = "your-4k-radarr-api-key"
Category = "radarr-4k"

[Radarr-4K.EntrySearch]
SearchMissing = true
SearchLimit = 3  # Lower limit for 4K (fewer releases)
DoUpgradeSearch = true  # Enable quality upgrades
CustomFormatUnmetSearch = true  # Enforce custom format requirements

[Radarr-4K.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "your-overseerr-api-key"
ApprovedOnly = true
Is4K = true  # IMPORTANT: Set to true for 4K instances
```

---

## Configuration Reference

### Required Settings

| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `SearchOverseerrRequests` | Boolean | Yes | Enable Overseerr integration |
| `OverseerrURI` | String | Yes | Full URL to Overseerr (e.g., `http://localhost:5055`) |
| `OverseerrAPIKey` | String | Yes | API key from Overseerr settings |

### Optional Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `ApprovedOnly` | Boolean | `true` | Only process approved requests (ignore pending) |
| `Is4K` | Boolean | `false` | Set to `true` for 4K instances, `false` for standard |

### Parent Settings (Required)

Overseerr integration **requires** these parent settings to be enabled:

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true  # REQUIRED: Enables search functionality
SearchRequestsEvery = 3  # Optional: How often to check (in loop iterations)
SearchLimit = 5  # Optional: Max concurrent searches
```

---

## Setup Instructions

### 1. Generate Overseerr API Key

1. Open Overseerr web interface (e.g., `http://localhost:5055`)
2. Navigate to **Settings** → **General**
3. Scroll down to **API Key** section
4. Copy the API key (or generate a new one)
5. Paste it into your qBitrr config as `OverseerrAPIKey`

### 2. Verify Overseerr Configuration

Ensure Overseerr is properly configured:

- **Radarr/Sonarr Integration**: Overseerr must be connected to your Arr instances
- **Quality Profiles**: Set default quality profiles for requests
- **Root Folders**: Configure root folders for Radarr/Sonarr
- **User Permissions**: Users should have permission to request content

### 3. Configure qBitrr

Add the `[EntrySearch.Overseerr]` section to each Arr instance that should process Overseerr requests:

```toml
[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "abc123def456"
ApprovedOnly = true
Is4K = false
```

### 4. Restart qBitrr

```bash
# Docker
docker restart qbitrr

# systemd
sudo systemctl restart qbitrr

# Direct
# Stop and restart the qbitrr process
```

### 5. Verify Integration

Check logs for Overseerr activity:

```bash
# Docker
docker logs -f qbitrr 2>&1 | grep -i overseerr

# Native
tail -f ~/logs/Radarr-Movies.log | grep -i overseerr
```

Expected log entries:
```
INFO - Overseerr requests: 5 pending, 2 approved
INFO - Triggering search for Overseerr request: Movie Title (2024)
DEBUG - Overseerr URI: http://localhost:5055
DEBUG - Overseerr API Key: ***
```

---

## Request Processing Behavior

### Approved-Only Mode (`ApprovedOnly = true`)

qBitrr will **only** search for requests that have been:
- Approved by an admin in Overseerr
- Not already available in your library
- Released (not scheduled for future release)

**Request States Processed:**
- ✅ **Approved** → qBitrr triggers search in Arr
- ❌ **Pending** → Ignored
- ❌ **Available** → Ignored (already in library)
- ❌ **Declined** → Ignored

### Unavailable Mode (`ApprovedOnly = false`)

qBitrr will search for **any** requests that are:
- Not yet available in your library
- Released (not scheduled for future release)

**Request States Processed:**
- ✅ **Approved** → qBitrr triggers search
- ✅ **Pending** → qBitrr triggers search
- ❌ **Available** → Ignored (already in library)
- ❌ **Declined** → Ignored

!!! warning "Automatic Approval"
    Setting `ApprovedOnly = false` effectively **auto-approves all requests**, as qBitrr will search for them immediately. Use with caution, especially on public instances.

---

## 4K Instance Configuration

### When to Use 4K Instances

Use separate 4K instances if:
- You maintain separate libraries for 4K and 1080p content
- You have different quality profiles for 4K content
- You want to control 4K access separately (e.g., Plex/Emby user restrictions)

### Overseerr 4K Setup

In Overseerr, configure separate Radarr/Sonarr instances for 4K:

1. **Settings** → **Radarr/Sonarr**
2. Add a new instance for 4K content
3. Set **Is 4K Server** to **Yes**
4. Configure quality profiles for 4K

### qBitrr 4K Configuration

Create a separate Arr section with `Is4K = true`:

```toml
# Standard instance
[Radarr-Movies]
Managed = true
URI = "http://localhost:7878"
APIKey = "standard-api-key"
Category = "radarr-movies"

[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "overseerr-api-key"
Is4K = false  # Standard quality

# 4K instance
[Radarr-4K]
Managed = true
URI = "http://localhost:7879"
APIKey = "4k-api-key"
Category = "radarr-4k"

[Radarr-4K.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "overseerr-api-key"
Is4K = true  # 4K quality
```

!!! tip "API Key Reuse"
    Both instances can use the **same Overseerr API key**. qBitrr filters requests based on the `Is4K` flag.

---

## Advanced Configuration

### Example 1: Public Instance with Manual Approval

For public Plex servers where admins review all requests:

```toml
[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "your-api-key"
ApprovedOnly = true  # Admins must approve first
Is4K = false

[Radarr-Movies.EntrySearch]
SearchMissing = true
SearchRequestsEvery = 5  # Check every 5 loops (slower polling)
SearchLimit = 3  # Limit concurrent searches
```

### Example 2: Private Instance with Auto-Approval

For family/friends servers where all requests are trusted:

```toml
[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "your-api-key"
ApprovedOnly = false  # Auto-approve all requests
Is4K = false

[Radarr-Movies.EntrySearch]
SearchMissing = true
SearchRequestsEvery = 2  # Check every 2 loops (faster polling)
SearchLimit = 10  # Higher concurrent search limit
```

### Example 3: Dual Instance (Standard + 4K)

For setups with both standard and 4K libraries:

```toml
# Standard Radarr
[Radarr-Movies]
Managed = true
URI = "http://localhost:7878"
APIKey = "standard-api-key"
Category = "radarr-movies"

[Radarr-Movies.EntrySearch]
SearchMissing = true
SearchRequestsEvery = 3

[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "shared-api-key"
ApprovedOnly = true
Is4K = false

# 4K Radarr
[Radarr-4K]
Managed = true
URI = "http://localhost:7879"
APIKey = "4k-api-key"
Category = "radarr-4k"

[Radarr-4K.EntrySearch]
SearchMissing = true
SearchRequestsEvery = 5  # Slower polling for 4K
SearchLimit = 2  # Fewer concurrent searches

[Radarr-4K.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "shared-api-key"
ApprovedOnly = true
Is4K = true  # Separate 4K flag
```

---

## Troubleshooting

### Requests Not Being Searched

**Symptoms:** Overseerr requests remain "Requested" or "Approved" but aren't searched

**Solutions:**

1. ✅ Verify `SearchMissing = true` in `[EntrySearch]` section
2. ✅ Check `SearchOverseerrRequests = true`
3. ✅ Ensure `OverseerrURI` is correct (include `http://` or `https://`)
4. ✅ Test API key manually:
   ```bash
   curl -H "X-Api-Key: your-api-key" http://localhost:5055/api/v1/request
   ```
5. ✅ Check qBitrr logs for Overseerr errors:
   ```bash
   tail -f ~/logs/Radarr-Movies.log | grep -i overseerr
   ```
6. ✅ Verify content has been **released** (not scheduled for future date)

---

### Connection Errors

**Symptoms:** "Couldn't connect to Overseerr" in logs

**Solutions:**

1. ✅ Verify Overseerr is running:
   ```bash
   curl http://localhost:5055
   ```
2. ✅ Check `OverseerrURI` uses correct protocol (`http://` vs `https://`)
3. ✅ Ensure no trailing slashes in URI (`http://localhost:5055`, not `http://localhost:5055/`)
4. ✅ Verify firewall rules if Overseerr is on a different machine
5. ✅ Check Docker network connectivity (if using containers):
   ```bash
   docker exec qbitrr ping overseerr
   ```

---

### Wrong Requests Processed (4K Issues)

**Symptoms:** 4K requests going to standard instance (or vice versa)

**Solutions:**

1. ✅ Verify `Is4K` setting matches your Radarr/Sonarr instance type:
   - Standard instance: `Is4K = false`
   - 4K instance: `Is4K = true`
2. ✅ Check Overseerr has separate 4K instances configured
3. ✅ Ensure Overseerr requests are marked correctly (4K flag set)
4. ✅ Review qBitrr logs for request filtering:
   ```bash
   tail -f ~/logs/Radarr-4K.log | grep -i "4k\|is4k"
   ```

---

### Release Date Caching Issues

**Symptoms:** qBitrr ignores requests for content not yet released

**Explanation:** qBitrr caches release dates from TMDB/TVDB via Overseerr API to avoid searching for unreleased content.

**Solutions:**

1. ✅ Verify release date in Overseerr matches actual release
2. ✅ Wait until release date passes
3. ✅ Restart qBitrr to clear cache:
   ```bash
   docker restart qbitrr  # Docker
   sudo systemctl restart qbitrr  # systemd
   ```
4. ✅ Check logs for release date detection:
   ```bash
   tail -f ~/logs/Radarr-Movies.log | grep -i "release"
   ```

---

### Approved Requests Not Triggering

**Symptoms:** Requests approved in Overseerr, but qBitrr doesn't search

**Solutions:**

1. ✅ Verify `ApprovedOnly = true` in config
2. ✅ Check request status in Overseerr (must be "Approved", not "Pending")
3. ✅ Ensure content is not already marked "Available" in Overseerr
4. ✅ Check Radarr/Sonarr has the content as "Monitored"
5. ✅ Review qBitrr search logs:
   ```bash
   tail -f ~/logs/Radarr-Movies.log | grep -i "search\|overseerr"
   ```

---

## API Rate Limiting

Overseerr has **no built-in rate limiting**, but qBitrr implements efficient polling:

- **Batch Requests**: Fetches all requests in paginated batches (100 per page)
- **Release Date Cache**: Avoids redundant API calls for release date lookups
- **Configurable Polling**: `SearchRequestsEvery` controls check frequency

### Recommended Polling Intervals

| Instance Size | `SearchRequestsEvery` | Effective Check Interval |
|---------------|------------------------|--------------------------|
| Small (<10 requests/day) | 5 | ~1-2 minutes |
| Medium (10-50 requests/day) | 3 | ~30-60 seconds |
| Large (50+ requests/day) | 2 | ~20-40 seconds |

!!! tip "Optimize Performance"
    Higher `SearchRequestsEvery` values reduce API calls but increase latency for request processing. Balance based on your request volume and user expectations.

---

## Integration with Other Features

### Combined with Missing Search

Overseerr requests work **alongside** regular missing content searches:

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true  # Search monitored missing content
SearchLimit = 10  # Total concurrent searches

[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true  # Also search Overseerr requests
ApprovedOnly = true
```

qBitrr will:
1. Search for monitored missing content in Radarr
2. Search for approved Overseerr requests
3. Respect total `SearchLimit` across both sources

---

### Quality Upgrades with Overseerr

Combine Overseerr requests with quality upgrades:

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
DoUpgradeSearch = true  # Enable quality upgrades
QualityUnmetSearch = true  # Search for unmet quality profiles

[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
ApprovedOnly = true
```

This ensures:
- New Overseerr requests are searched immediately
- Existing content is upgraded when better releases appear

---

### Custom Formats with Overseerr

Enforce custom format scores for Overseerr requests:

```toml
[Radarr-Movies.EntrySearch]
SearchMissing = true
CustomFormatUnmetSearch = true  # Search for CF score improvements
ForceMinimumCustomFormat = true  # Block releases below CF threshold

[Radarr-Movies.EntrySearch.Overseerr]
SearchOverseerrRequests = true
ApprovedOnly = true
```

This ensures Overseerr requests respect your custom format requirements (e.g., no hardcoded subs, proper codecs).

---

## Best Practices

### Security

- **Protect API Keys**: Never commit `OverseerrAPIKey` to public repositories
- **Use Environment Variables**: Store sensitive keys in environment variables:
  ```bash
  export QBITRR_RADARR_MOVIES__ENTRYSEARCH__OVERSEERR__OVERSEERRAPIKEY="abc123"
  ```
- **HTTPS**: Use HTTPS for Overseerr if exposed to the internet
- **Reverse Proxy**: Place Overseerr behind a reverse proxy (Nginx, Caddy, Traefik)

### Performance

- **Adjust Polling**: Set `SearchRequestsEvery` based on request volume
- **Limit Searches**: Keep `SearchLimit` reasonable to avoid overwhelming indexers
- **Monitor Logs**: Watch for rate limiting or connection errors

### User Experience

- **Approval Workflow**: Use `ApprovedOnly = true` for public servers to control content
- **Auto-Approval**: Use `ApprovedOnly = false` for trusted users/family
- **Request Notifications**: Configure Overseerr notifications to alert users when content is available

---

## Docker Compose Example

Complete Docker Compose setup with Overseerr integration:

```yaml
version: '3.8'
services:
  overseerr:
    image: sctx/overseerr:latest
    container_name: overseerr
    environment:
      - LOG_LEVEL=info
      - TZ=America/New_York
    ports:
      - "5055:5055"
    volumes:
      - /path/to/overseerr/config:/app/config
    restart: unless-stopped

  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    environment:
      - TZ=America/New_York
      # Overseerr integration via environment variables
      - QBITRR_RADARR_MOVIES__ENTRYSEARCH__OVERSEERR__SEARCHOVERSEERRQUESTS=true
      - QBITRR_RADARR_MOVIES__ENTRYSEARCH__OVERSEERR__OVERSEERRURI=http://overseerr:5055
      - QBITRR_RADARR_MOVIES__ENTRYSEARCH__OVERSEERR__OVERSEERRAPIKEY=your-api-key
      - QBITRR_RADARR_MOVIES__ENTRYSEARCH__OVERSEERR__APPROVEDONLY=true
      - QBITRR_RADARR_MOVIES__ENTRYSEARCH__OVERSEERR__IS4K=false
    volumes:
      - /path/to/qbitrr/config:/config
    depends_on:
      - overseerr
    restart: unless-stopped
```

---

## Comparison: Overseerr vs Ombi

| Feature | Overseerr | Ombi |
|---------|-----------|------|
| **User Interface** | Modern, React-based | Older, Angular-based |
| **Media Discovery** | Advanced (TMDB integration) | Basic |
| **Request Management** | Full workflow (approve/decline/comment) | Basic approval |
| **4K Support** | Native | Limited |
| **User Permissions** | Granular (per-user quotas, limits) | Basic roles |
| **Performance** | Fast, lightweight | Can be slow with many users |
| **qBitrr Support** | Full support (approved/unavailable modes, 4K) | Full support (approved mode only) |

**Recommendation:** Use **Overseerr** for new setups (better UX, modern codebase, active development). Ombi is suitable for existing setups or simpler use cases.

---

## Next Steps

- **Configure Ombi Integration:** [Ombi Configuration](ombi.md)
- **General Search Configuration:** [Search Configuration](index.md)
- **Radarr Setup:** [Radarr Configuration](../arr/radarr.md)
- **Sonarr Setup:** [Sonarr Configuration](../arr/sonarr.md)
- **Troubleshooting:** [Common Issues](../../troubleshooting/common-issues.md)
