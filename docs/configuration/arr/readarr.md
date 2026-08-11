# Readarr Configuration

This guide covers how to configure Readarr instances in qBitrr for book library management, automated searching, and quality upgrades.

!!! note "Readarr upstream status"
    Readarr is largely unmaintained upstream. qBitrr targets the current **v1 API** as shipped by recent Readarr builds. Behavior may differ if your instance diverges from that API surface.

---

## Quick Start

Every Readarr instance in qBitrr requires a dedicated section in your `config.toml` file. The section name must follow the pattern `Readarr-<name>`.

### Basic Configuration

```toml
[Readarr-Books]
# Toggle whether to manage this Readarr instance
Managed = true

# The URL used to access Readarr (e.g., http://ip:port)
URI = "http://localhost:8787"

# Readarr API Key (Settings > General > Security)
APIKey = "your-readarr-api-key"

# Optional: set true only if Readarr uses HTTPS with a self-signed or untrusted certificate
SkipTLSVerify = false

# Category applied by Readarr to torrents in qBittorrent
# MUST match: Readarr > Settings > Download Clients > qBittorrent > Category
Category = "readarr-books"

# Toggle whether to re-search failed torrents
ReSearch = true

# Import mode (Auto, Move, or Copy)
importMode = "Auto"

# RSS sync timer in minutes (0 = disabled)
RssSyncTimer = 1

# Refresh downloads timer in minutes (0 = disabled)
RefreshDownloadsTimer = 1

# Error messages to automatically blacklist
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing book file(s)",
  "Not a preferred word upgrade for existing book file(s)",
  "Unable to determine if file is a sample"
]
```

---

## Connection Settings

### Finding Your Readarr Details

1. **URI**: Open Readarr in your browser and copy the URL (e.g., `http://192.168.1.100:8787`)
2. **APIKey**: In Readarr, go to **Settings** → **General** → **Security** → Copy the **API Key**
3. **Category**: Go to **Settings** → **Download Clients** → Click your qBittorrent client → Note the **Category** field

!!! warning "Category Mismatch"
    The `Category` value in qBitrr **must exactly match** the category configured in Readarr's qBittorrent download client settings. If they don't match, qBitrr won't process your Readarr torrents.

!!! info "qBittorrent Subcategories (4.6+)"
    For hierarchical qBit categories like `seed/books`, set `Category` to the **full path** (`Category = "seed/books"`). To configure a parent once and have qBitrr also manage every child, enable `MatchSubcategories = true` on the corresponding `[qBit]` / `[qBit-<name>]` section. See [Subcategories](../qbittorrent.md#subcategories-qbittorrent-46).

---

### Multiple Readarr Instances

You can configure multiple Readarr instances (e.g., separate ebook vs audiobook libraries):

```toml
[Readarr-Books]
URI = "http://localhost:8787"
APIKey = "api-key-1"
Category = "readarr-books"
# ... other settings

[Readarr-Comics]
URI = "http://localhost:8788"
APIKey = "api-key-2"
Category = "readarr-comics"
# ... other settings
```

!!! tip "Naming Convention"
    Instance names must start with `Readarr-` followed by any descriptive name. Examples:

    - ✅ `Readarr-Books`
    - ✅ `Readarr-Comics`
    - ✅ `Readarr-Audiobooks`
    - ❌ `Books` (missing prefix)
    - ❌ `readarr-books` (lowercase)

---

## Basic Settings

### Managed

```toml
Managed = true  # Enable management for this Readarr instance
```

When `Managed = false`, qBitrr will completely ignore this Readarr instance. Useful for temporarily disabling an instance without removing its configuration.

---

### Import Mode

```toml
importMode = "Auto"  # Auto | Move | Copy
```

| Mode | Behavior |
|------|----------|
| `Auto` | Let Readarr decide based on its own settings |
| `Move` | Move files from download folder to library (faster, frees disk space) |
| `Copy` | Copy files and leave original (preserves seeding torrents) |

---

### ReSearch

```toml
ReSearch = true
```

When enabled, qBitrr automatically triggers a new search in Readarr when:

- A torrent fails or stalls beyond configured thresholds
- A torrent is manually moved to the `failed` category
- An error code from `ArrErrorCodesToBlocklist` is encountered

Re-search uses Readarr's **`BookSearch`** command (search unit = book).

---

## Automation Settings

### RSS Sync Timer

```toml
RssSyncTimer = 1  # Minutes between RSS syncs (0 = disabled)
```

Periodically tells Readarr to refresh its RSS feeds from indexers.

**Recommended values:** `1` (responsive), `5` (balanced), `15` (conservative), or `0` (disabled).

---

### Refresh Downloads Timer

```toml
RefreshDownloadsTimer = 1  # Minutes between queue refreshes (0 = disabled)
```

Tells Readarr to update its download queue so it stays in sync with qBittorrent.

---

## Error Handling

### Arr Error Codes to Blacklist

```toml
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing book file(s)",
  "Not a preferred word upgrade for existing book file(s)",
  "Unable to determine if file is a sample"
]
```

When Readarr encounters these error messages during import, qBitrr will remove the failed files, mark the release as failed, blacklist it, and trigger a new search (if `ReSearch = true`).

```toml
ArrErrorCodesToBlocklist = []  # Empty list = disabled
```

---

## Author → Book Model

Readarr organizes content as **authors** containing **books**. qBitrr mirrors that model:

| Layer | Role in qBitrr |
|-------|----------------|
| **Author** | Browse unit in the WebUI; quality / temp profile switching target |
| **Book** | Search unit (`BookSearch`); DB rows for missing / upgrade searches |

Instant imports call Readarr's **`DownloadedBooksScan`** command when a download completes.

---

## Automated Search Configuration

Configure search in the `[Readarr-Books.EntrySearch]` subsection.

### Basic Search Settings

```toml
[Readarr-Books.EntrySearch]
# Enable automated search for missing books
SearchMissing = true

# Search unmonitored books
Unmonitored = false

# Cap concurrent searches
SearchLimit = 5

# Order searches by book release year
SearchByYear = true

# Reverse search order (true = oldest first, false = newest first)
SearchInReverse = false

# Restart search loop when all books are processed
SearchAgainOnSearchCompletion = true
```

!!! info "Readarr-Specific Settings"
    Compared with other Arr types:

    - ✅ **`SearchByYear`** is supported (book release year), unlike Lidarr
    - ✅ **`SearchLimit`** / **`Unmonitored`** are available
    - ❌ No `AlsoSearchSpecials` / `SearchBySeries` (not applicable to books)
    - ❌ No `SearchRequestsEvery` (Ombi/Overseerr request polling is Radarr/Sonarr only)
    - ❌ No Ombi / Overseerr (see [Request Integration](#request-integration))

---

### Quality Upgrade Searches

```toml
[Readarr-Books.EntrySearch]
DoUpgradeSearch = false
QualityUnmetSearch = false
CustomFormatUnmetSearch = false
ForceMinimumCustomFormat = false
```

Enable selectively when you want continuous upgrades or strict custom-format enforcement.

---

### Temporary Quality Profiles

Quality profiles are applied at the **author** level in Readarr. Temp-profile switching therefore updates authors (not individual books):

```toml
[Readarr-Books.EntrySearch]
UseTempForMissing = false
KeepTempProfile = false
QualityProfileMappings = { "Preferred" = "Any" }
ForceResetTempProfiles = false
TempProfileResetTimeoutMinutes = 0
ProfileSwitchRetryAttempts = 3
```

**How it works:**

1. An author has missing books and uses a preferred quality profile
2. qBitrr switches the **author** to the mapped temp profile
3. Readarr searches books under the lower requirements
4. After imports (unless `KeepTempProfile`), qBitrr switches the author back

---

## Request Integration

!!! warning "No Overseerr/Ombi Support"
    Overseerr and Ombi **do not support book requests**. These settings are not available for Readarr instances (same as Lidarr). Book request management must be handled through Readarr's built-in wanted list.

---

## Torrent Management

Configure torrent handling in the `[Readarr-Books.Torrent]` subsection.

### Ebook File Configuration

```toml
[Readarr-Books.Torrent]
CaseSensitiveMatches = false
FolderExclusionRegex = ["\\bextras?\\b", "\\bsamples?\\b", "\\bscreens?\\b"]
FileNameExclusionRegex = ["\\bsample\\b", "\\btrailer\\b"]
FileExtensionAllowlist = [".epub", ".mobi", ".azw", ".azw3", ".pdf", ".cbz", ".cbr", ".!qB", ".parts"]
AutoDelete = false
IgnoreTorrentsYoungerThan = 180
MaximumETA = -1
MaximumDeletablePercentage = 0.99
DoNotRemoveSlow = true
StalledDelay = 15
ReSearchStalled = false
```

!!! info "Ebook Extensions"
    Default allowlist targets common ebook/comic formats:

    - `.epub`, `.mobi`, `.azw`, `.azw3` – ebook readers
    - `.pdf` – portable documents
    - `.cbz`, `.cbr` – comic archives
    - `.!qB`, `.parts` – incomplete qBittorrent files (keep while downloading)

---

## Seeding Configuration

Configure seeding limits in `[Readarr-Books.Torrent.SeedingMode]`:

```toml
[Readarr-Books.Torrent.SeedingMode]
DownloadRateLimitPerTorrent = -1
UploadRateLimitPerTorrent = -1
MaxUploadRatio = -1
MaxSeedingTime = -1
RemoveTorrent = -1
RemoveDeadTrackers = false
RemoveTrackerWithMessage = [
  "skipping tracker announce (unreachable)",
  "No such host is known",
  "unsupported URL protocol",
  "info hash is not authorized with this tracker"
]
```

See [Seeding Settings](../seeding.md) for tracker-specific overrides.

---

## Complete Example

```toml
[Readarr-Books]
Managed = true
URI = "http://localhost:8787"
APIKey = "your-readarr-api-key"
Category = "readarr-books"
ReSearch = true
importMode = "Auto"
RssSyncTimer = 5
RefreshDownloadsTimer = 5
ArrErrorCodesToBlocklist = [
  "Not an upgrade for existing book file(s)",
  "Unable to determine if file is a sample"
]

[Readarr-Books.EntrySearch]
SearchMissing = true
Unmonitored = false
SearchLimit = 5
SearchByYear = true
SearchInReverse = false
SearchRequestsEvery = 300
DoUpgradeSearch = false
QualityUnmetSearch = false
CustomFormatUnmetSearch = false
ForceMinimumCustomFormat = false
SearchAgainOnSearchCompletion = true
UseTempForMissing = false
KeepTempProfile = false
QualityProfileMappings = {}
ForceResetTempProfiles = false
TempProfileResetTimeoutMinutes = 0
ProfileSwitchRetryAttempts = 3

[Readarr-Books.Torrent]
CaseSensitiveMatches = false
FolderExclusionRegex = ["\\bextras?\\b", "\\bsamples?\\b"]
FileNameExclusionRegex = ["\\bsample\\b"]
FileExtensionAllowlist = [".epub", ".mobi", ".azw", ".azw3", ".pdf", ".cbz", ".cbr", ".!qB", ".parts"]
AutoDelete = false
IgnoreTorrentsYoungerThan = 180
MaximumETA = -1
MaximumDeletablePercentage = 0.99
DoNotRemoveSlow = true
StalledDelay = 15
ReSearchStalled = false

[Readarr-Books.Torrent.SeedingMode]
DownloadRateLimitPerTorrent = -1
UploadRateLimitPerTorrent = -1
MaxUploadRatio = -1
MaxSeedingTime = -1
RemoveTorrent = -1
RemoveDeadTrackers = false
```

---

## WebUI: Open in Readarr

From the qBitrr WebUI author detail view, **Open in Readarr** uses:

`GET /web/arr/<category>/open/author/<author_id>`

qBitrr resolves your Readarr instance by `category` (the qBittorrent category / instance key, e.g. `readarr-books`), fetches the author from the Readarr API, and redirects (`302`) to the native Readarr UI. The route token prefers `foreignAuthorId`, then `titleSlug`, then the numeric id.

The same route is available under `/api/arr/...` when WebUI auth is enabled. See [WebUI API — Open Arr Item](../../webui/api.md#open-arr-item-in-arr-ui).

---

## Torrent: Ebook allowlist and AutoDelete

Readarr sections default `Torrent.FileExtensionAllowlist` to ebook/comic extensions (`.epub`, `.mobi`, `.azw`, `.azw3`, `.pdf`, `.cbz`, `.cbr`). When **`Torrent.AutoDelete`** is enabled, qBitrr validates allowlisted files before treating a download as complete.

Unlike video formats, ebooks are **not probed with ffprobe** — known ebook/comic suffixes are accepted without a media probe so AutoDelete does not mark entire downloads invalid when ffprobe is available.

---

## Troubleshooting

### Torrents Not Being Processed

1. ✅ Verify `Category` matches Readarr's download client category exactly
2. ✅ Check `Managed = true`
3. ✅ Ensure Readarr tags torrents with that category
4. ✅ Check category-specific log: `~/logs/Readarr-Books.log`

### Searches Not Triggering

1. ✅ Verify `SearchMissing = true` in `[Readarr-Books.EntrySearch]`
2. ✅ Ensure Readarr has working indexers
3. ✅ Review `Settings.SearchLoopDelay` (per-search pacing; not Ombi/Overseerr — Readarr has no request polling)
4. ✅ Confirm books are marked wanted/monitored in Readarr

### Files Not Importing

1. ✅ Check `FileExtensionAllowlist` includes your ebook formats
2. ✅ Verify path mapping between qBittorrent and Readarr
3. ✅ Confirm instant import / `DownloadedBooksScan` is reaching Readarr
4. ✅ Review Readarr import logs

### Connection Failures

```bash
curl -H "X-Api-Key: your-api-key" http://localhost:8787/api/v1/system/status
```

Verify `URI`, `APIKey`, and that Readarr is reachable from the qBitrr host.

---

## Next Steps

- **Configure Radarr:** [Radarr Configuration](radarr.md)
- **Configure Sonarr:** [Sonarr Configuration](sonarr.md)
- **Configure Lidarr:** [Lidarr Configuration](lidarr.md)
- **Advanced Torrent Settings:** [Torrent Configuration](../torrents.md)
- **Seeding Configuration:** [Seeding Settings](../seeding.md)
- **Troubleshooting:** [Common Issues](../../troubleshooting/common-issues.md)
