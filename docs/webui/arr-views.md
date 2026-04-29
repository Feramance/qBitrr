# Arr Views

The **Arr Views** provide a unified interface to browse and monitor your media library across all managed Radarr, Sonarr, and Lidarr instances. View movies, TV series, episodes, albums, and tracks directly from qBitrr's WebUI without switching between multiple Arr interfaces.

---

## Overview

qBitrr's Arr views offer:

- **Unified Library Browser**: View all media from multiple Arr instances in one place
- **Real-time Sync**: Data refreshes from Arr APIs with configurable intervals
- **Advanced Filtering**: Filter by monitored status, file availability, quality, requests
- **Search**: Full-text search across titles, years, artists
- **Quality Profile Display**: See which quality profile is assigned to each entry
- **Request Tracking**: Identify items added via Overseerr/Ombi integration
- **Pagination**: Handle large libraries with server-side pagination
- **List and Icon**: Toolbar **View** control on each Arr page — **List** is a text-only table (no poster column in the browse surface); **Icon** is a responsive tile grid with cached posters or cover art. The choice is stored in `localStorage` (default: Icon).
- **Detail modals**: Click a row/card to open a modal. Radarr shows a single movie payload. Sonarr groups **series → season → episode** in the modal. **Lidarr groups artist → albums → tracks** (each album is a section with track rows)—not nested tables on the main browse surface.
- **Posters**: Thumbnails are served by the WebUI (disk cache, Arr API source) at `/web/.../thumbnail` and mirrored under `/api/...` (see [WebUI API](api.md#arr-poster-thumbnails-cached)). Images may append `?token=` when the session cookie is not used.

Multi-level detail in the modal (browse row is the top level):

| Arr | Detail modal shape | Multi-level (collapses to episodes / tracks) |
|-----|-------------------|----------------------------------------------|
| **Radarr** | Single movie fields | No |
| **Sonarr** | Series → seasons → episodes | Yes |
| **Lidarr** | Artist → albums → tracks | Yes |

**Supported Arr Types**:
- **Radarr**: Movies with year, quality profile, file status
- **Sonarr**: TV series with seasons, episodes, air dates
- **Lidarr**: Artists on the browse surface; albums and tracks appear in the detail modal (artist → album → track)

### `available` vs `hasFile`: two different metrics

The Arr views surface availability at two different granularities and they have **different**
definitions — be careful when comparing the catalog header to a per-row badge.

| Field | Where it appears | Definition |
|-------|------------------|------------|
| `counts.available` | Header rollup (movies/episodes/albums) | `Monitored == true` **AND** the row has a file (`MovieFileId`/`EpisodeFileId`/`AlbumFileId` non-zero). Unmonitored rows with a file are excluded. |
| `<row>.hasFile` | Per-row payload | The row has a file regardless of monitored state. A row can be `hasFile=true` while contributing **zero** to the rollup `available`. |
| `seasons[].available` (Sonarr) | Per-season bucket | Same as the header rollup: counts only monitored episodes that also have a file. |

If you build a frontend control that reuses the rollup as a "browser-side" available count,
make sure you `&&` the row's `monitored` flag with `hasFile` before comparing — otherwise
totals will not match the header.

---

## Radarr View

### Features

**Movie Library Browser**:
- Title, year, monitored status, file availability
- Quality met indicator (cutoff reached)
- Custom format scores (if configured)
- Request tracking (Overseerr/Ombi)
- Quality profile name display

**Filtering Options**:

| Filter | Description | Values |
|--------|-------------|--------|
| **Monitored** | Show only monitored movies | All, Yes, No |
| **Has File** | Filter by file availability | All, Yes, No |
| **Quality Met** | Filter by quality cutoff status | All, Yes, No |
| **Is Request** | Show only Overseerr/Ombi requests | All, Yes, No |
| **Year Range** | Filter by release year | Min/Max year inputs |

**Instance vs aggregate**:
- **Per-instance**: Browse one Radarr at a time.
- **All Radarr (aggregate)**: Merged library across instances (instance column when multiple instances exist). Same **List** / **Icon** modes apply; row click opens the **movie** detail modal.

**Example Display**:
```plaintext
┌─────────────────────────────────────────────────────────────────┐
│ Radarr-Movies                                     [Refresh] [⚙] │
├─────────────────────────────────────────────────────────────────┤
│ Available: 1,234  Monitored: 1,500  Missing: 266               │
├─────────────────────────────────────────────────────────────────┤
│ Title              Year  Monitored  Has File  Quality Profile   │
├─────────────────────────────────────────────────────────────────┤
│ Inception          2010  ✓          ✓         Any               │
│ The Matrix         1999  ✓          ✓         HD-1080p          │
│ Interstellar       2014  ✓          ✗         Any               │
│ The Dark Knight    2008  ✓          ✓         Ultra-HD          │
└─────────────────────────────────────────────────────────────────┘
```

### API Integration

**Endpoint**: `GET /api/radarr/<category>/movies`

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | `int` | Page number (0-indexed) |
| `page_size` | `int` | Items per page (default: 50) |
| `q` | `string` | Search query (title) |
| `year_min` | `int` | Minimum release year |
| `year_max` | `int` | Maximum release year |
| `monitored` | `bool` | Filter by monitored status |
| `has_file` | `bool` | Filter by file availability |
| `quality_met` | `bool` | Filter by quality cutoff |
| `is_request` | `bool` | Filter by request status |

**Response**:
```json
{
  "category": "Radarr-Movies",
  "counts": {
    "available": 1234,
    "monitored": 1500,
    "missing": 266,
    "quality_met": 1100,
    "requests": 45
  },
  "total": 1500,
  "page": 0,
  "page_size": 50,
  "movies": [
    {
      "id": 1,
      "title": "Inception",
      "year": 2010,
      "monitored": true,
      "hasFile": true,
      "qualityMet": true,
      "isRequest": false,
      "upgrade": false,
      "customFormatScore": 1500,
      "minCustomFormatScore": 1000,
      "customFormatMet": true,
      "reason": null,
      "qualityProfileId": 1,
      "qualityProfileName": "Any"
    }
  ]
}
```

### Database Caching

**Purpose**: Reduce Arr API load by caching library data in local SQLite database.

**Behavior**:
- First page load triggers full library sync from Radarr API (`/api/v3/movie`)
- Data stored in `MoviesFilesModel` table (`qBitrr.db`)
- Subsequent page loads read from database (instant response)
- Library summary counts on browse responses (header `counts`, pagination totals) aggregate from SQLite on each request so they stay aligned with catalog updates performed by background workers
- Database refreshes on demand (Refresh button) or periodically

**Database Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `EntryId` | `int` | Radarr movie ID |
| `Title` | `string` | Movie title |
| `Year` | `int` | Release year |
| `Monitored` | `bool` | Monitoring status |
| `MovieFileId` | `int` | File ID (0 = no file) |
| `QualityMet` | `bool` | Quality cutoff reached |
| `IsRequest` | `bool` | Added via Overseerr/Ombi |
| `Upgrade` | `bool` | Searching for quality upgrade |
| `CustomFormatScore` | `int` | Current custom format score |
| `MinCustomFormatScore` | `int` | Minimum required score |
| `CustomFormatMet` | `bool` | Custom format requirements met |
| `Reason` | `string` | Why item is wanted/missing |
| `QualityProfileId` | `int` | Assigned quality profile ID |
| `QualityProfileName` | `string` | Quality profile name |

---

## Sonarr View

### Features

**Library browser**:
- **List**: One row per series (columns include episode count and quality profile as applicable); no posters in the browse table.
- **Icon**: One tile per series with a cached poster; metadata line shows episode count and profile.
- **Detail modal**: Click opens the series; seasons expand to the same per-episode fields as before (monitored, has file, air date, reason).

**Filtering Options**:

| Filter | Description | Values |
|--------|-------------|--------|
| **Missing Only** | Show only episodes without files | All, Missing Only |
| **Search** | Search series titles and episode names | Text input |

**Example (list mode)**:
```plaintext
┌─────────────────────────────────────────────────────────────────┐
│ Series              Episodes   Quality profile                    │
├─────────────────────────────────────────────────────────────────┤
│ Breaking Bad        62         HD-1080p                          │
│ Game of Thrones     73         Any                               │
└─────────────────────────────────────────────────────────────────┘
```

### API Integration

**Endpoint**: `GET /api/sonarr/<category>/series`

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | `int` | Page number (0-indexed) |
| `page_size` | `int` | Series per page (default: 25) |
| `q` | `string` | Search query (series title) |
| `missing` | `bool` | Show only series with missing episodes |

**Response**:
```json
{
  "category": "Sonarr-TV",
  "counts": {
    "available": 4532,
    "monitored": 5000,
    "missing": 468
  },
  "total": 150,
  "page": 0,
  "page_size": 25,
  "series": [
    {
      "series": {
        "id": 1,
        "title": "Breaking Bad",
        "qualityProfileId": 1,
        "qualityProfileName": "HD-1080p"
      },
      "totals": {
        "available": 62,
        "monitored": 62,
        "missing": 0
      },
      "seasons": {
        "1": {
          "monitored": 7,
          "available": 7,
          "missing": 0,
          "episodes": [
            {
              "episodeNumber": 1,
              "title": "Pilot",
              "monitored": true,
              "hasFile": true,
              "airDateUtc": "2008-01-20T02:00:00Z",
              "reason": null
            }
          ]
        }
      }
    }
  ]
}
```

### Database Caching

**Tables**:
1. **SeriesFilesModel**: Stores series metadata
2. **EpisodeFilesModel**: Stores episode data

**Episode Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `EntryId` | `int` | Sonarr episode ID |
| `SeriesId` | `int` | Parent series ID |
| `SeriesTitle` | `string` | Series name |
| `SeasonNumber` | `int` | Season number |
| `EpisodeNumber` | `int` | Episode number |
| `Title` | `string` | Episode title |
| `Monitored` | `bool` | Monitoring status |
| `EpisodeFileId` | `int` | File ID (0 = no file) |
| `AirDateUtc` | `datetime` | Original air date (UTC) |
| `Reason` | `string` | Why episode is wanted |
| `QualityProfileId` | `int` | Series quality profile ID |
| `QualityProfileName` | `string` | Quality profile name |

---

## Lidarr View

### Features

**Library browser**:
- **List**: One row per **artist** (album count, track count, monitored, quality profile).
- **Icon**: One tile per artist using a cached **artist** thumbnail; click opens a **detail modal** with albums and tracks (`LidarrAlbumDetailBody` per album).
- **Aggregate** ("All Lidarr"): Merged rows across instances; instance column when multiple instances exist.

**Filtering**: **Search** matches artist names (and instance labels in aggregate mode). **Artists** dropdown (per instance only): all artists or monitored artists only.

The separate **album** JSON API (`GET …/albums`) remains available for programmatic use; it is not used as the default browse surface in the WebUI anymore.

**Example (list mode)**:

```plaintext
┌──────────────────────────────────────────────────────────┐
│ Artist              Albums   Tracks   Monitored  Profile │
├──────────────────────────────────────────────────────────┤
│ Pink Floyd           12        180     ✓           Lossless │
└──────────────────────────────────────────────────────────┘
```

### API Integration

**Artist browse endpoint**: `GET /api/lidarr/<category>/artists` (and `/web/...` mirror).
**Artist detail (modal)**: `GET /api/lidarr/<category>/artist/<artist_id>` returning nested album rows with tracks.

See [WebUI API](api.md#lidarr-artists) for query parameters.

### Database Caching

**Tables**:
1. **AlbumFilesModel**: Stores album metadata
2. **TrackFilesModel**: Stores track data
3. **ArtistFilesModel**: Stores artist metadata

**Track Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `EntryId` | `int` | Lidarr track ID |
| `AlbumId` | `int` | Parent album ID |
| `TrackNumber` | `int` | Track number |
| `Title` | `string` | Track title |
| `Duration` | `int` | Track duration (seconds) |
| `HasFile` | `bool` | File availability |
| `TrackFileId` | `int` | File ID |
| `Monitored` | `bool` | Monitoring status |

---

## Configuration

### Live Arr Mode

**Path**: `Settings.WebUI.LiveArr`
**Type**: `bool`
**Default**: `false`

When enabled, bypasses database cache and fetches live data directly from Arr APIs on every page load.

**Pros**:
- Always up-to-date (no sync delay)
- Reflects immediate changes in Arr

**Cons**:
- Slower page loads (API latency)
- Higher load on Arr instances
- No offline browsing

**Example**:
```toml
[WebUI]
LiveArr = false  # Use database cache (recommended)
```

### WebUI.GroupSonarr / WebUI.GroupLidarr

**Paths**: `Settings.WebUI.GroupSonarr`, `Settings.WebUI.GroupLidarr`
**Type**: `bool` each
**Default**: `true` each

These keys remain in [`config.toml`](../configuration/config-file.md) for compatibility; the React WebUI does **not** branch on them. Sonarr browsing is series-row + modal (`series → seasons → episodes`). Lidarr browsing is artist-row + modal (`artist → albums → tracks`).

**Example**:
```toml
[WebUI]
GroupSonarr = true
GroupLidarr = true
```

---

## Troubleshooting

### "Arr manager is still initialising"

**Cause**: Arr instances not yet connected or database not loaded.

**Solutions**:
1. Wait 30-60 seconds after qBitrr startup
2. Check **Processes** tab shows instances running
3. Verify Arr API connectivity in logs

### Missing quality profile names

**Cause**: Database sync incomplete or quality profile not cached.

**Solutions**:
1. Click **Refresh** button to re-sync from Arr API
2. Verify quality profiles exist in Arr (`/settings/profiles`)
3. Check logs for API errors during sync

### Search not finding results

**Cause**: Database cache stale or search term too specific.

**Solutions**:
1. Click **Refresh** to update database
2. Try broader search terms (partial titles)
3. Enable `LiveArr = true` for real-time search

### Slow page loads

**Cause**: Large library (>10,000 items) or `LiveArr` enabled.

**Solutions**:
1. Disable `LiveArr` (use database cache)
2. Reduce `page_size` query parameter
3. Use filters to narrow results (monitored, missing only)
4. Enable pagination (default: 25-50 items per page)

### Episodes showing wrong air dates

**Cause**: Timezone mismatch or Sonarr database out of sync.

**Solutions**:
1. Verify Sonarr's timezone settings
2. Refresh database from Arr API
3. Check `AirDateUtc` field in database (should be UTC)

---

## Performance Optimization

### Database Indexing

qBitrr automatically creates indexes on frequently queried fields:

**Radarr**:
- `MoviesFilesModel.Title` (for search)
- `MoviesFilesModel.Monitored` (for filtering)
- `MoviesFilesModel.Year` (for year range)

**Sonarr**:
- `EpisodeFilesModel.SeriesTitle` (for search)
- `EpisodeFilesModel.SeriesId` (for grouping)
- `EpisodeFilesModel.AirDateUtc` (for sorting)

**Lidarr**:
- `AlbumFilesModel.ArtistTitle` (for search)
- `AlbumFilesModel.ArtistId` (for grouping)
- `AlbumFilesModel.ReleaseDate` (for sorting)

### Pagination Strategy

**Server-Side Pagination**:
- Database queries use `LIMIT` and `OFFSET` (Peewee `.paginate()`)
- Only requested page data transferred to WebUI
- Memory efficient for large libraries

**Client-Side Sorting**:
- Sorting happens in WebUI (TanStack Table)
- Only current page sorted (not entire library)
- Re-fetch data when changing sort column

### Caching Policy

**Initial Load**:
1. Check if database table exists and has data
2. If empty, fetch full library from Arr API
3. Store in SQLite with timestamp

**Subsequent Loads**:
1. Read from database (instant)
2. Auto-refresh every N minutes (configurable)
3. Manual refresh via button

**Cache Invalidation**:
- Rebuild Arrs (full re-sync)
- Manual refresh button
- Process restart
- Database schema change

---

## See Also

- [Processes View](processes.md) – Monitor Arr process status
- [Logs View](logs.md) – Debug Arr API communication
- [Configuration](../configuration/index.md) – Configure Arr instances
- [API Documentation](api.md) – Full API endpoint reference
