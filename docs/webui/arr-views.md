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

**Supported Arr Types**:
- **Radarr**: Movies with year, quality profile, file status
- **Sonarr**: TV series with seasons, episodes, air dates
- **Lidarr**: Albums with artists, tracks, release dates

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

**Aggregation Mode**:
- **Per-Instance View**: Browse one Radarr instance at a time (default)
- **Aggregate View**: Combine all Radarr instances into a unified table

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

**TV Series Browser**:
- Series title, season/episode breakdown, air dates
- Monitored status per episode
- File availability per episode
- Quality profile name display
- Episode-level reason tracking (why missing)

**Grouping Modes**:

1. **Grouped by Series** (default):
   - Expandable rows showing seasons
   - Episode counts per season (available/monitored/missing)
   - Collapse/expand individual series

2. **Flat Episode List**:
   - All episodes in a single table
   - Sortable by series, season, episode number, air date

**Filtering Options**:

| Filter | Description | Values |
|--------|-------------|--------|
| **Missing Only** | Show only episodes without files | All, Missing Only |
| **Search** | Search series titles and episode names | Text input |

**Example Display** (Grouped Mode):
```plaintext
┌─────────────────────────────────────────────────────────────────┐
│ Sonarr-TV                                         [Refresh] [⚙] │
├─────────────────────────────────────────────────────────────────┤
│ Available: 4,532  Monitored: 5,000  Missing: 468               │
├─────────────────────────────────────────────────────────────────┤
│ Series                 Available  Monitored  Missing  Profile   │
├─────────────────────────────────────────────────────────────────┤
│ ▼ Breaking Bad         62         62         0         HD-1080p │
│   Season 1: 7/7                                                  │
│   Season 2: 13/13                                                │
│   Season 3: 13/13                                                │
│ ▶ Game of Thrones      73         80         7         Any      │
│ ▶ The Office           201        201        0         HD-720p  │
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

**Album Browser**:
- Artist name, album title, release date
- Track count and availability
- Monitored status per album
- Quality profile assignment
- Foreign album ID (MusicBrainz)

**Grouping Modes**:

1. **Grouped by Artist** (default):
   - Albums grouped under artist name
   - Track counts per album
   - Expandable to show individual tracks

2. **Flat Album List**:
   - All albums in a single table
   - Sortable by artist, album title, release date

**Filtering Options**:

| Filter | Description | Values |
|--------|-------------|--------|
| **Monitored** | Filter by monitored status | All, Yes, No |
| **Has File** | Filter by file availability | All, Yes, No |
| **Quality Met** | Filter by quality cutoff | All, Yes, No |
| **Is Request** | Show only requests | All, Yes, No |
| **Search** | Search artist/album names | Text input |

**Example Display** (Grouped Mode):
```plaintext
┌─────────────────────────────────────────────────────────────────┐
│ Lidarr-Music                                      [Refresh] [⚙] │
├─────────────────────────────────────────────────────────────────┤
│ Available: 523  Monitored: 600  Missing: 77                    │
├─────────────────────────────────────────────────────────────────┤
│ Artist / Album            Tracks    Release Date  Profile       │
├─────────────────────────────────────────────────────────────────┤
│ ▼ Pink Floyd                                                     │
│   The Dark Side of Moon   10/10     1973-03-01   Lossless      │
│   Wish You Were Here      5/5       1975-09-12   Lossless      │
│ ▼ The Beatles                                                    │
│   Abbey Road              17/17     1969-09-26   Any           │
│   Sgt. Pepper's...        13/13     1967-05-26   Any           │
└─────────────────────────────────────────────────────────────────┘
```

### API Integration

**Endpoint**: `GET /api/lidarr/<category>/albums`

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | `int` | Page number (0-indexed) |
| `page_size` | `int` | Albums per page (default: 50) |
| `q` | `string` | Search query (artist/album) |
| `monitored` | `bool` | Filter by monitored status |
| `has_file` | `bool` | Filter by file availability |
| `quality_met` | `bool` | Filter by quality cutoff |
| `is_request` | `bool` | Filter by request status |
| `flat_mode` | `bool` | Flat track view (default: false) |

**Response**:
```json
{
  "category": "Lidarr-Music",
  "counts": {
    "available": 523,
    "monitored": 600,
    "missing": 77,
    "quality_met": 500,
    "requests": 12
  },
  "total": 600,
  "page": 0,
  "page_size": 50,
  "albums": [
    {
      "album": {
        "id": 1,
        "title": "The Dark Side of the Moon",
        "artistId": 1,
        "artistName": "Pink Floyd",
        "monitored": true,
        "hasFile": true,
        "foreignAlbumId": "b84ee12a-09ef-421b-82de-0441a926375c",
        "releaseDate": "1973-03-01",
        "qualityMet": true,
        "isRequest": false,
        "upgrade": false,
        "customFormatScore": 0,
        "minCustomFormatScore": 0,
        "customFormatMet": true,
        "reason": null,
        "qualityProfileId": 1,
        "qualityProfileName": "Lossless"
      },
      "totals": {
        "available": 10,
        "monitored": 10,
        "missing": 0
      },
      "tracks": [
        {
          "id": 1,
          "trackNumber": 1,
          "title": "Speak to Me",
          "duration": 90,
          "hasFile": true,
          "trackFileId": 123,
          "monitored": true
        }
      ]
    }
  ]
}
```

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

### Group Sonarr by Series

**Path**: `Settings.WebUI.GroupSonarr`
**Type**: `bool`
**Default**: `true`

Controls default grouping mode for Sonarr view.

**Example**:
```toml
[WebUI]
GroupSonarr = true  # Group by series (default)
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
