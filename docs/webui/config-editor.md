# Configuration Editor

The Configuration Editor provides a user-friendly interface for managing qBitrr's configuration through the WebUI. All changes are saved to the `config.toml` file and can trigger live reloads of affected components without requiring a full application restart.

---

## Overview

The Configuration Editor replaces manual TOML editing with a structured form interface featuring:

- **Organized Sections**: Core settings, WebUI, qBittorrent, and per-instance Arr configurations
- **Live Validation**: Real-time field validation with helpful error messages
- **Intelligent Reload**: Automatic detection of which components need reloading after save
- **Visual Feedback**: Dirty state tracking, save confirmation, and unsaved changes warnings
- **Theme Support**: Live theme switching without page reload

---

## Accessing the Configuration Editor

Navigate to the **Config** page via the WebUI sidebar:

```
http://<host>:6969/ui → Config
```

**Authentication**: If `WebUI.Token` is set, you must authenticate before accessing this page (Bearer token in Authorization header or cookie).

---

## Configuration Structure

### Core Configuration Sections

The editor is organized into three primary sections accessible via summary cards:

#### 1. Settings
**Core application configuration** including logging, disk space management, loop timers, and auto-update settings.

**Key Fields**:

- **Console Level**: Log verbosity (CRITICAL, ERROR, WARNING, NOTICE, INFO, DEBUG, TRACE)
- **Logging**: Enable writing logs to files (`~/logs/` or `/config/logs`)
- **Completed Download Folder**: Path where qBit completes downloads (must match Arr's path)
- **Free Space**: Desired free space threshold (e.g., `50G`, `-1` to disable)
- **Free Space Folder**: Directory to monitor for free space checks
- **Auto Pause/Resume**: Automatically pause torrents when disk space is low
- **No Internet Sleep Timer (s)**: Delay before retrying when connectivity is lost
- **Loop Sleep Timer (s)**: Interval between torrent processing passes
- **Search Loop Delay (s)**: Delay between automated search requests
- **Failed Category**: qBit category for marking failed torrents
- **Recheck Category**: qBit category triggering force recheck
- **Tagless**: Enable operation without relying on Arr tags
- **Ignore Torrents Younger Than (s)**: Grace period for new torrents before evaluation
- **Ping URLs**: Comma-separated hostnames for connectivity checks (e.g., `one.one.one.one, dns.google.com`)
- **FFprobe Auto Update**: Automatically download/update bundled ffprobe binary
- **Auto Update Enabled**: Enable background auto-update worker
- **Auto Update Cron**: Cron expression for update checks (default: `0 3 * * 0` = Sundays at 3 AM)

**Example**:
```toml
[Settings]
ConsoleLevel = "INFO"
Logging = true
CompletedDownloadFolder = "/mnt/downloads"
FreeSpace = "100G"
FreeSpaceFolder = "/mnt/downloads"
AutoPauseResume = true
NoInternetSleepTimer = 300
LoopSleepTimer = 30
SearchLoopDelay = 60
FailedCategory = "failed"
RecheckCategory = "recheck"
Tagless = false
IgnoreTorrentsYoungerThan = 600
PingURLS = ["one.one.one.one", "dns.google.com"]
FFprobeAutoUpdate = true
AutoUpdateEnabled = true
AutoUpdateCron = "0 3 * * 0"
```

**Validation**:

- `CompletedDownloadFolder` must not be empty or `CHANGE_ME`
- `FreeSpace` must be `-1` or a number with optional suffix (K, M, G, T, P)
- `FreeSpaceFolder` required when `FreeSpace != "-1"`
- All timer fields must be non-negative numbers
- `AutoUpdateCron` must contain 5 or 6 space-separated fields

---

#### 2. Web Settings
**WebUI server configuration** including host, port, token, theme, and view preferences.

**Key Fields**:

- **WebUI Host**: Bind address (default: `0.0.0.0` for all interfaces)
- **WebUI Port**: Port number (default: `6969`, range: 1-65535)
- **WebUI Token**: Optional bearer token for API/UI authentication (auto-generated if empty)
- **Live Arr**: Enable real-time Arr data (bypasses database cache, increases API load)
- **Group Sonarr by Series**: Group episodes by series and seasons in collapsible sections
- **Theme**: Visual theme (`Light` or `Dark`) — **changes apply immediately**

**Example**:
```toml
[WebUI]
Host = "0.0.0.0"
Port = 6969
Token = "abc123def456..."
LiveArr = false
GroupSonarr = true
Theme = "Dark"
```

**Validation**:

- `Host` must not be empty
- `Port` must be between 1 and 65535
- `Token` accepts any string (empty = no authentication)

**Special Behavior**:

- **Theme**: Changes apply immediately via JavaScript (no save required)
- **Host/Port/Token**: Trigger WebUI restart after save

---

#### 3. qBit
**qBittorrent connection details and qBit-managed categories**.

**Key Fields**:

- **Disabled**: Disable qBitrr's qBittorrent integration (headless search-only mode)
- **Host**: qBittorrent WebUI host or IP address
- **Port**: qBittorrent WebUI port (default: 8080)
- **UserName**: qBittorrent WebUI username (optional if auth bypassed)
- **Password**: qBittorrent WebUI password (optional if auth bypassed)
- **Managed Categories**: Tag-based input for categories managed directly by qBit (independent of Arr instances)

**Managed Categories**:

This field allows qBittorrent to manage categories with custom seeding settings, independent of Radarr/Sonarr/Lidarr. Use this for torrents not managed by Arr instances (e.g., manually added torrents, private tracker downloads).

- **Tag Input UI**: Add categories by typing and pressing Enter or comma
- **Visual Tags**: Categories display as removable chips/tags
- **Quick Removal**: Click × on any tag to remove it
- **Category Validation**: System prevents conflicts between Arr-managed and qBit-managed categories

**Example**:
```toml
[qBit]
Disabled = false
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "adminpass"
ManagedCategories = ["downloads", "private-tracker", "manual"]
```

**Validation**:

- `Host` must not be empty
- `Port` must be between 1 and 65535
- `ManagedCategories` cannot overlap with Arr instance categories

---

### Arr Instance Configuration

Each Radarr, Sonarr, or Lidarr instance is configured independently via dedicated modal dialogs.

#### Instance Management

**Adding Instances**:

1. Click **Add Instance** button under "Radarr Instances" or "Sonarr Instances"
2. New instance created with default name (e.g., `Radarr-1`, `Sonarr-2`)
3. Instance opens automatically for configuration

**Deleting Instances**:

1. Click **Delete** button on instance card
2. Confirm deletion (cannot be undone)
3. Instance removed from config and UI

**Renaming Instances**:

1. Open instance modal
2. Edit **Display Name** field
3. Press Enter or blur field to apply
4. Instance key updated in config (e.g., `Radarr-1` → `Radarr-4K`)
5. **Automatic Cleanup**: Old section and all subsections are automatically removed when you save

**Important**: The system now explicitly tracks renamed instances to ensure complete cleanup:
- All old configuration keys are marked for deletion
- Subsections (EntrySearch, Torrent, SeedingMode, Trackers) are automatically removed
- No orphaned config sections remain after rename

---

#### General Settings

**Key Fields**:

- **Display Name**: Friendly name for this instance (also used as config key)
- **Managed**: Toggle whether qBitrr actively manages this instance
- **URI**: Arr instance URL (e.g., `http://localhost:7878`)
- **API Key**: Arr API key from Settings → General → Security
- **Category**: qBittorrent category applied by this Arr instance
- **Re-search**: Re-run searches for failed torrents after qBitrr removes them
- **Import Mode**: Preferred import mode (`Move`, `Copy`, or `Auto`)
- **RSS Sync Timer (min)**: Interval between RSS sync requests (0 = disabled)
- **Refresh Downloads Timer (min)**: Interval between queue refresh requests (0 = disabled)
- **Arr Error Codes To Blocklist**: Comma-separated list of Arr error messages triggering blocklist

**Example**:
```toml
[Radarr-4K]
Managed = true
URI = "http://localhost:7878"
APIKey = "abc123..."
Category = "radarr-4k"
ReSearch = true
importMode = "Auto"
RssSyncTimer = 5
RefreshDownloadsTimer = 5
ArrErrorCodesToBlocklist = [
    "Not an upgrade for existing movie file(s)",
    "Not a preferred word upgrade for existing movie file(s)",
    "Unable to determine if file is a sample"
]
```

**Validation**:

- `URI` and `APIKey` required when `Managed = true`
- `Category` must not be empty
- Timer fields must be non-negative numbers

---

#### Entry Search Settings

Configure automated searching for missing media, quality upgrades, and request integrations.

**Search Behavior**:

- **Search Missing**: Search for missing media items
- **Also Search Specials** *(Sonarr only)*: Include season 0 specials
- **Unmonitored**: Include unmonitored items in searches
- **Do Upgrade Search**: Search for improved releases even if file exists
- **Quality Unmet Search**: Re-search when quality requirements not met
- **Custom Format Unmet Search**: Re-search when custom format score too low
- **Force Minimum Custom Format**: Auto-remove torrents not meeting minimum custom format score

**Search Configuration**:

- **Search Limit**: Maximum concurrent search tasks (default: 5)
- **Search By Year**: Order searches by release year
- **Search In Reverse**: Reverse search order (oldest → newest)
- **Search Requests Every (s)**: Delay between individual search requests (default: 300)
- **Search Again On Completion**: Restart search loop after exhausting year range

**Quality Profiles**:

- **Use Temp Profile For Missing**: Switch to temporary profiles when searching
- **Keep Temp Profile**: Don't revert to main profile after using temp profile
- **Main Quality Profile**: Comma-separated primary profile names
- **Temp Quality Profile**: Comma-separated temporary profile names (paired with main profiles)

**Sonarr-Specific**:

- **Search By Series**: Strategy for episode searches (`smart`, `true`, `false`)
    - `smart` = auto (series search for multiple episodes, episode search for single)
    - `true` = always search entire series
    - `false` = always search individual episodes
- **Prioritize Today's Releases**: Prioritize items released today (RSS-style)

**Example**:
```toml
[Radarr-4K.EntrySearch]
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
MainQualityProfile = []
TempQualityProfile = []
```

**Validation**:

- `SearchLimit` must be at least 1
- `SearchRequestsEvery` must be at least 1 second

---

#### Request Integration: Ombi

Integrate Ombi to automatically search for pending requests.

**Key Fields**:

- **Search Ombi Requests**: Enable Ombi integration
- **Ombi URI**: Ombi server URL (e.g., `http://localhost:5000`)
- **Ombi API Key**: Ombi API key
- **Approved Only**: Only process approved requests
- **Is 4K Instance**: Treat this config as 4K-specific

**Example**:
```toml
[Radarr-4K.EntrySearch.Ombi]
SearchOmbiRequests = true
OmbiURI = "http://localhost:5000"
OmbiAPIKey = "ombi_key_here"
ApprovedOnly = true
Is4K = true
```

---

#### Request Integration: Overseerr

Integrate Overseerr/Jellyseerr to automatically search for pending requests.

**Key Fields**:

- **Search Overseerr Requests**: Enable Overseerr integration
- **Overseerr URI**: Overseerr server URL (e.g., `http://localhost:5055`)
- **Overseerr API Key**: Overseerr API key
- **Approved Only**: Only process approved requests
- **Is 4K Instance**: Treat this config as 4K-specific

**Example**:
```toml
[Radarr-4K.EntrySearch.Overseerr]
SearchOverseerrRequests = true
OverseerrURI = "http://localhost:5055"
OverseerrAPIKey = "overseerr_key_here"
ApprovedOnly = true
Is4K = true
```

---

#### Torrent Management Settings

Configure how qBitrr evaluates and manages torrents.

**File Filtering**:

- **Case Sensitive Matches**: Enable case-sensitive regex matching
- **Folder Exclusion Regex**: Comma-separated regex patterns to exclude folders (e.g., `\bextras?\b, \bsamples?\b`)
- **File Name Exclusion Regex**: Comma-separated regex patterns to exclude files (e.g., `\bsample\b, \btrailer\b`)
- **File Extension Allowlist**: Comma-separated allowed extensions (e.g., `.mp4, .mkv, .srt`) — empty = allow all

**Torrent Health**:

- **Auto Delete**: Automatically delete unrecognized files
- **Ignore Torrents Younger Than (s)**: Grace period before evaluating torrents (default: 600)
- **Maximum ETA (s)**: Torrents with ETA above this are considered stalled (default: 604800 = 7 days)
- **Maximum Deletable Percentage**: Upper bound completion % for deletion (0.99 = 99%)
- **Do Not Remove Slow**: Ignore slow torrents when pruning
- **Stalled Delay (min)**: Minutes to allow stalled torrents before action (-1 = disabled, 0 = infinite)
- **Re-search Stalled**: Re-run searches for stalled torrents

**Tracker Management**:

- **Remove Dead Trackers**: Remove trackers flagged as dead
- **Remove Tracker Messages**: Comma-separated tracker status messages triggering removal (e.g., `skipping tracker announce (unreachable)`)

**Example**:
```toml
[Radarr-4K.Torrent]
CaseSensitiveMatches = false
FolderExclusionRegex = ["\\bextras?\\b", "\\bsamples?\\b"]
FileNameExclusionRegex = ["\\bsample\\b", "\\btrailer\\b"]
FileExtensionAllowlist = [".mp4", ".mkv", ".sub", ".srt"]
AutoDelete = false
IgnoreTorrentsYoungerThan = 600
MaximumETA = 604800
MaximumDeletablePercentage = 0.99
DoNotRemoveSlow = true
StalledDelay = 15
ReSearchStalled = false
RemoveDeadTrackers = false
RemoveTrackerWithMessage = ["skipping tracker announce (unreachable)", "No such host is known"]
```

**Validation**:

- All numeric fields must be non-negative
- `MaximumDeletablePercentage` must be between 0 and 100

---

#### Seeding Mode Settings

Configure per-instance seeding policies.

**Key Fields**:

- **Download Rate Limit Per Torrent**: Bytes/s download limit (-1 = unlimited)
- **Upload Rate Limit Per Torrent**: Bytes/s upload limit (-1 = unlimited)
- **Max Upload Ratio**: Maximum upload ratio (-1 = unlimited)
- **Max Seeding Time (s)**: Maximum seeding duration (-1 = unlimited)
- **Remove Torrent (policy)**: Removal policy:
    - `-1` = do not remove
    - `1` = remove on ratio
    - `2` = remove on time
    - `3` = remove on ratio OR time
    - `4` = remove on ratio AND time

**Example**:
```toml
[Radarr-4K.Torrent.SeedingMode]
DownloadRateLimitPerTorrent = -1
UploadRateLimitPerTorrent = -1
MaxUploadRatio = 2.0
MaxSeedingTime = 604800
RemoveTorrent = 3
```

**Validation**:

- All fields must be -1 or greater
- `RemoveTorrent` must be -1, 1, 2, 3, or 4

---

#### Tracker-Specific Settings

Define custom per-tracker seeding policies and tagging rules.

**Key Fields**:

- **Name**: Tracker name (for display purposes)
- **URI**: Tracker URL (used for matching)
- **Priority**: Tracker priority (higher = preferred)
- **Maximum ETA (s)**: Override global ETA limit for this tracker
- **Download Rate Limit**: Override global download limit
- **Upload Rate Limit**: Override global upload limit
- **Max Upload Ratio**: Override global upload ratio
- **Max Seeding Time (s)**: Override global seeding time
- **Add Tracker If Missing**: Automatically add this tracker to matching torrents
- **Remove If Exists**: Remove torrents from this tracker
- **Super Seed Mode**: Enable super seeding for this tracker
- **Add Tags**: Comma-separated tags to apply to torrents from this tracker

**Example**:
```toml
[[Radarr-4K.Torrent.Trackers]]
Name = "Premium Tracker"
URI = "https://premium.tracker.com/announce"
Priority = 10
MaximumETA = 86400
DownloadRateLimit = -1
UploadRateLimit = -1
MaxUploadRatio = 3.0
MaxSeedingTime = 1209600
AddTrackerIfMissing = false
RemoveIfExists = false
SuperSeedMode = false
AddTags = ["premium"]
```

**Validation**:

- `Name` and `URI` required
- All numeric fields must be non-negative or -1

**UI Features**:

- **Add Tracker**: Click "+ Add Tracker" to create new tracker config
- **Delete Tracker**: Click trash icon on tracker card to remove
- **Collapsible Cards**: Each tracker is a collapsible card showing name in header

---

## Field Types and Widgets

### Text Input
Standard text field for strings.

```html
<input type="text" value="..." />
```

### Number Input
Numeric field with spinner controls.

```html
<input type="number" value="42" />
```

### Checkbox
Toggle boolean values.

```html
<input type="checkbox" checked />
```

### Password
Masked text field (shows bullets).

```html
<input type="password" value="***" />
```

### Secure Field
Special field for API keys and tokens with:

- **Visibility Toggle**: Show/hide value
- **Refresh Button**: Generate new random key (32-character hex)

**Example**: `WebUI.Token`, `Arr.APIKey`, `Ombi.OmbiAPIKey`

### Select Dropdown
Dropdown for predefined options (using `react-select` with theme-aware styling).

**Examples**:

- **Console Level**: `CRITICAL`, `ERROR`, `WARNING`, `NOTICE`, `INFO`, `DEBUG`, `TRACE`
- **Import Mode**: `Move`, `Copy`, `Auto`
- **Theme**: `Light`, `Dark`
- **Search By Series** *(Sonarr)*: `smart`, `true`, `false`

### Tag Input
Interactive chip/tag-based input for managing arrays of strings.

**Features**:

- **Visual Tags**: Values display as styled chips with × remove buttons
- **Quick Add**: Type and press Enter or comma to add new tags
- **Backspace Delete**: Press Backspace on empty input to remove last tag
- **Duplicate Prevention**: Automatically prevents adding duplicate values
- **Theme Support**: Tags styled according to current theme

**Examples**:

- **Managed Categories** *(qBit)*: `["downloads", "private-tracker", "manual"]`
- **Arr Error Codes To Blocklist**: `["Not an upgrade", "Unable to determine if sample"]`

**Usage**:
1. Click in the input field
2. Type a category name (e.g., `downloads`)
3. Press **Enter** or **comma** to add the tag
4. Click **×** on any tag to remove it
5. Press **Backspace** with empty input to remove the last tag

---

## Validation System

### Real-Time Validation

The editor validates fields **on change** and **before save**, displaying inline error messages.

**Validation Types**:

1. **Type Validation**: Ensure value matches expected type (string, number, boolean)
2. **Range Validation**: Check numeric fields fall within valid ranges (e.g., port 1-65535)
3. **Conditional Validation**: Some fields required only when related fields are set
4. **Custom Validation**: Field-specific logic (e.g., cron expression format)

### Common Validation Rules

| Field | Rule |
|-------|------|
| `CompletedDownloadFolder` | Must not be empty or `CHANGE_ME` |
| `FreeSpace` | Must be `-1` or number with optional K/M/G/T/P suffix |
| `FreeSpaceFolder` | Required when `FreeSpace != "-1"` |
| `WebUI.Port`, `qBit.Port` | Must be 1-65535 |
| `Arr.URI` | Required when `Arr.Managed = true` |
| `Arr.APIKey` | Required when `Arr.Managed = true` |
| `Arr.Category` | Must not be empty |
| `EntrySearch.SearchLimit` | Must be ≥ 1 |
| `AutoUpdateCron` | Must contain 5 or 6 space-separated fields |
| `Torrent.MaximumDeletablePercentage` | Must be 0-100 |
| `Torrent.SeedingMode.RemoveTorrent` | Must be -1, 1, 2, 3, or 4 |

### Error Display

Validation errors are displayed:

1. **Inline**: Below affected field with red text
2. **On Save**: Modal alert with all errors listed

**Example Error**:
```
WebUI.Port: WebUI Port must be between 1 and 65535.
Radarr-4K.URI: URI must be set to a valid URL when the instance is managed.
```

---

## Save Behavior and Live Reload

### Save Process

When you click **Save + Live Reload**:

1. **Client-Side Validation**: All fields validated; save blocked if errors exist
2. **Change Detection**: Compares current form state vs. original config
3. **Diff Calculation**: Generates minimal change set (only modified fields)
4. **API Request**: `POST /api/config` with `{"changes": {...}}`
5. **Server-Side Validation**: Backend validates and persists to `config.toml`
6. **Reload Detection**: Server determines which components need reloading
7. **Reload Execution**: Server reloads affected components
8. **Response**: Success message with reload type

### Reload Strategies

The backend uses **intelligent reload detection** to minimize disruption:

| Change Type | Reload Type | Behavior |
|-------------|-------------|----------|
| **Frontend-only** (`WebUI.Theme`, `WebUI.LiveArr`, `WebUI.GroupSonarr`) | `frontend` | No reload (changes apply in browser) |
| **WebUI Server** (`WebUI.Host`, `WebUI.Port`, `WebUI.Token`) | `webui` | Restart WebUI server (brief downtime) |
| **Single Arr Instance** (e.g., `Radarr-4K.*`) | `single_arr` | Reload only that Arr instance |
| **Multiple Arr Instances** (e.g., `Radarr-4K.*` + `Sonarr-TV.*`) | `multi_arr` | Reload each affected instance sequentially |
| **Global Settings** (`Settings.*`, `qBit.*`) | `full` | Reload all components (entire manager) |

### API Response

```json
{
  "status": "ok",
  "configReloaded": true,
  "reloadType": "single_arr",
  "affectedInstances": ["Radarr-4K"]
}
```

**Response Headers**:
```
X-Config-Reloaded: true
Cache-Control: no-cache, no-store, must-revalidate
```

### Protected Keys

The following keys **cannot** be modified via the WebUI:

- `Settings.ConfigVersion` (managed automatically by migration system)

Attempts to modify protected keys return `403 Forbidden`.

---

## Modal State Persistence

Configuration modals now preserve their state when you switch tabs or windows:

**Persistent State**:

- **Open Modals**: Remain open when switching between tabs or minimizing the browser
- **Entered Data**: All field values are preserved across tab switches
- **Unsaved Changes**: Maintained even if you switch to another application

**Benefits**:

- Fill out long configuration forms without losing progress
- Reference other applications while configuring
- Switch tabs to check settings in other systems
- Resume configuration exactly where you left off

**Note**: Modal state is preserved only within the Config tab. Navigating to a different WebUI page (Processes, Logs, etc.) will close modals as expected.

---

## Dirty State Tracking

The editor tracks whether unsaved changes exist:

**Indicators**:

- **Save Button State**: Enabled when changes exist, disabled when clean
- **Browser Warning**: "You have unsaved changes" prompt if navigating away
- **Visual Feedback**: No explicit "unsaved changes" banner (rely on button state)

**Change Detection**:

- Compares flattened current state vs. original state
- Detects added, modified, and removed keys
- Array fields compared via JSON serialization

**Escape Routes**:

- **Save**: Apply changes and clear dirty state
- **Reload**: Refresh page to discard changes (browser prompts confirmation)

---

## Keyboard Shortcuts

### Global

- **Escape**: Close any open modal

### Text Fields

- **Enter**: Commit changes (on rename fields)
- **Escape**: Revert to original value (on rename fields)

---

## Tooltips and Descriptions

### Field Tooltips

Hover over field labels to see tooltips with detailed descriptions (defined in `webui/src/config/tooltips.ts`).

**Example**:
```typescript
"Settings.FreeSpace": "Desired free space threshold (use K, M, G, T suffix). Set to -1 to disable the free space guard."
```

### Field Descriptions

Below each field is a short auto-generated description:

- **Checkbox**: "Enable or disable {label}."
- **Other**: "Set the {label} value."

For complex fields, custom descriptions override the default (e.g., `EntrySearch.SearchBySeries` shows strategy options).

---

## API Endpoints

### Get Configuration

Fetch current configuration from disk.

**Endpoint**: `GET /api/config`

**Authentication**: Required (Bearer token)

**Response**:
```json
{
  "Settings": {
    "ConsoleLevel": "INFO",
    "Logging": true,
    "CompletedDownloadFolder": "/mnt/downloads",
    ...
  },
  "WebUI": {
    "Host": "0.0.0.0",
    "Port": 6969,
    ...
  },
  "qBit": {
    "Host": "localhost",
    "Port": 8080,
    ...
  },
  "Radarr-4K": {
    "Managed": true,
    "URI": "http://localhost:7878",
    ...
  },
  ...
}
```

**Error**:
```json
{
  "error": "Failed to load configuration"
}
```

### Update Configuration

Apply changes to configuration and trigger reload.

**Endpoint**: `POST /api/config`

**Authentication**: Required (Bearer token)

**Request Body**:
```json
{
  "changes": {
    "Settings.LoopSleepTimer": 60,
    "Radarr-4K.EntrySearch.SearchLimit": 10,
    "WebUI.Theme": "Dark"
  }
}
```

**Dotted Key Format**: Use dot notation for nested keys (e.g., `Radarr-4K.Torrent.AutoDelete`).

**Deletion**: Set value to `null` to delete key (e.g., `{"WebUI.Token": null}`).

**Response**:
```json
{
  "status": "ok",
  "configReloaded": true,
  "reloadType": "multi_arr",
  "affectedInstances": ["Radarr-4K"]
}
```

**Validation Error**:
```json
{
  "error": "Please resolve the following issues:\nWebUI.Port: WebUI Port must be between 1 and 65535."
}
```

**Protected Key Error**:
```json
{
  "error": "Cannot modify protected configuration key: Settings.ConfigVersion"
}
```

### Test Arr Connection

Test connection to Arr instance without saving configuration.

**Endpoint**: `POST /api/arr/test-connection`

**Authentication**: Required (Bearer token)

**Request Body**:
```json
{
  "arrType": "radarr",
  "uri": "http://localhost:7878",
  "apiKey": "abc123..."
}
```

**Response** (Success):
```json
{
  "success": true,
  "version": "4.3.2.6857",
  "qualityProfiles": [
    {"id": 1, "name": "HD-1080p"},
    {"id": 4, "name": "Ultra-HD"}
  ]
}
```

**Response** (Failure):
```json
{
  "success": false,
  "message": "Connection refused"
}
```

---

## Common Workflows

### Adding a New Radarr Instance

1. Navigate to **Config** page
2. Scroll to **Radarr Instances** section
3. Click **Add Instance**
4. Instance modal opens with default name (`Radarr-1`, `Radarr-2`, etc.)
5. Configure fields:
    - Rename instance (e.g., `Radarr-4K`)
    - Set **URI** (e.g., `http://localhost:7878`)
    - Set **API Key** (copy from Radarr Settings → General → Security)
    - Set **Category** (e.g., `radarr-4k`)
6. Configure optional settings (Entry Search, Torrent, Seeding, Trackers)
7. Close modal
8. Click **Save + Live Reload**
9. New Radarr instance starts managing downloads

### Changing Global Loop Timer

1. Navigate to **Config** page
2. Click **Configure** on **Settings** card
3. Change **Loop Sleep Timer (s)** (e.g., `30` → `60`)
4. Close modal
5. Click **Save + Live Reload**
6. Backend performs **full reload** (all instances restart)

### Updating WebUI Port

1. Navigate to **Config** page
2. Click **Configure** on **Web Settings** card
3. Change **WebUI Port** (e.g., `6969` → `8080`)
4. Close modal
5. Click **Save + Live Reload**
6. WebUI server restarts on new port
7. Browser redirects to `http://<host>:8080/ui`

### Switching Theme

1. Navigate to **Config** page
2. Click **Configure** on **Web Settings** card
3. Change **Theme** dropdown (`Light` / `Dark`)
4. Theme applies **immediately** (no save required)
5. Close modal
6. Optional: Click **Save + Live Reload** to persist theme preference

### Configuring Ombi Integration

1. Open Radarr/Sonarr instance modal
2. Scroll to **Request Integration: Ombi** section
3. Enable **Search Ombi Requests**
4. Set **Ombi URI** (e.g., `http://localhost:5000`)
5. Set **Ombi API Key** (copy from Ombi Settings → API)
6. Enable **Approved Only** (recommended)
7. Set **Is 4K Instance** (if applicable)
8. Close modal
9. Click **Save + Live Reload**
10. qBitrr begins polling Ombi for pending requests

### Adding Custom Tracker Rules

1. Open Radarr/Sonarr instance modal
2. Scroll to **Trackers** section
3. Click **Add Tracker**
4. New tracker card appears
5. Configure tracker:
    - **Name**: `IPTorrents`
    - **URI**: `https://iptorrents.com/announce.php`
    - **Priority**: `10`
    - **Max Upload Ratio**: `2.0`
    - **Add Tags**: `ipt`
6. Repeat for additional trackers
7. Close modal
8. Click **Save + Live Reload**
9. Tracker rules apply to matching torrents

---

## Troubleshooting

### Config Not Loading

**Symptom**: Loading spinner never disappears

**Causes**:

1. **Invalid TOML Syntax**: Config file has syntax errors
2. **Permission Issues**: qBitrr cannot read `config.toml`
3. **WebUI Token**: Token mismatch or missing authentication

**Solutions**:

- Check browser console for API errors
- Verify `config.toml` syntax: `toml-lint ~/config/config.toml`
- Check file permissions: `ls -la ~/config/config.toml`
- Regenerate token: Remove `WebUI.Token` from config, restart qBitrr

### Changes Not Saving

**Symptom**: Save button completes but changes not reflected after reload

**Causes**:

1. **Validation Errors**: Silent validation failures
2. **Write Permissions**: qBitrr cannot write to `config.toml`
3. **Config Version Mismatch**: Automatic migration overwrites changes

**Solutions**:

- Check for validation error messages on page
- Verify write permissions: `touch ~/config/config.toml && rm ~/config/config.toml`
- Check logs for migration warnings: `tail -f ~/logs/Main.log`

### Reload Not Triggering

**Symptom**: Save succeeds but components don't reload

**Causes**:

1. **Wrong Reload Type**: Frontend-only changes don't reload backend
2. **Instance Not Found**: Renamed instance doesn't exist in manager
3. **Process Crashed**: Arr instance crashed during reload

**Solutions**:

- Check response JSON for `reloadType` and `affectedInstances`
- Verify instance exists: Check Processes page
- Check logs: `tail -f ~/logs/Main.log` and `~/logs/<ArrName>.log`

### Modal Won't Close

**Symptom**: Clicking outside modal doesn't close it

**Causes**:

1. **Unsaved Changes**: No warning but modal remains open
2. **JavaScript Error**: React component error prevents close

**Solutions**:

- Press **Escape** key to force close
- Check browser console for React errors
- Refresh page to reset state

### Validation Errors Won't Clear

**Symptom**: Field shows error even after correcting value

**Causes**:

1. **Dependent Fields**: Another field still invalid
2. **Cache Issue**: React state not updating
3. **Conditional Validation**: Related field triggers validation

**Solutions**:

- Review all error messages (may be multiple)
- Refresh page to reset validation state
- Check related fields (e.g., `FreeSpace` → `FreeSpaceFolder`)

### Port Change Breaks Connection

**Symptom**: After changing `WebUI.Port`, cannot access WebUI

**Causes**:

1. **Port Already In Use**: Another service using target port
2. **Firewall Blocking**: Firewall blocks new port
3. **WebUI Restart Failed**: Server crashed during restart

**Solutions**:

- Check logs: `tail -f ~/logs/WebUI.log`
- Verify port availability: `netstat -tulpn | grep <port>`
- Edit config manually: `nano ~/config/config.toml`, revert port
- Restart qBitrr: `systemctl restart qbitrr` (systemd) or restart Docker container

---

## Best Practices

1. **Test Arr Connections**: Use `/api/arr/test-connection` endpoint (future feature) before saving
2. **Incremental Changes**: Make small changes and test before bulk updates
3. **Backup Config**: Keep a backup copy of `config.toml` before major changes
4. **Monitor Logs**: Watch logs during/after config changes to catch issues
5. **Avoid Direct Edits**: Use WebUI instead of manual TOML editing (prevents syntax errors)
6. **Theme Changes**: Theme is the only setting that applies without save
7. **Global vs. Instance**: Understand which changes trigger full reload vs. instance reload
8. **Secure Fields**: Use refresh button to generate strong random keys
9. **Tracker Priorities**: Higher priority trackers preferred when multiple matches exist
10. **Validation First**: Fix all validation errors before attempting save

---

## Related Pages

- [Configuration File Reference](../configuration/config-file.md) – Manual TOML editing guide
- [Environment Variables](../configuration/environment.md) – Environment-based configuration
- [Quality Profiles](../configuration/quality-profiles.md) – Setting up quality profiles
- [Processes Page](processes.md) – Monitor Arr instance health
- [Logs Page](logs.md) – View configuration reload logs

---

## See Also

- [WebUI Overview](index.md) – Introduction to the WebUI
- [Arr Views](arr-views.md) – Browse Radarr/Sonarr/Lidarr libraries
- [First Run Guide](../getting-started/quickstart.md) – Initial configuration walkthrough
- [Migration Guide](../getting-started/migration.md) – Upgrading from older configs
