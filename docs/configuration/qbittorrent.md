# qBittorrent Configuration

qBitrr connects to qBittorrent's Web UI to monitor and manage torrents. This page covers all qBittorrent-related settings and how to configure the connection.

---

## Basic Connection Settings

All qBittorrent settings are configured in the `[qBit]` section of your `config.toml` file.

### Required Settings

```toml
[qBit]
# qBittorrent WebUI URL/IP - Can be found in Options > Web UI > "IP Address"
Host = "192.168.1.100"

# qBittorrent WebUI Port - Can be found in Options > Web UI > "Port"
Port = 8080

# qBittorrent WebUI Authentication
UserName = "admin"
Password = "your-password"

# Optional: set true only if the Web UI uses HTTPS with a self-signed or untrusted certificate
SkipTLSVerify = false
```

When **`SkipTLSVerify`** is **`true`**, qBitrr does not verify the TLS certificate for the qBittorrent Web API. Use only on trusted networks; verification is disabled for that connection (MITM risk).

Additional qBittorrent instances use **`[qBit-<name>]`** with the same keys, including **`SkipTLSVerify`** per instance.

!!! tip "Finding qBittorrent Settings"
    Open qBittorrent → **Tools** → **Options** → **Web UI** tab to find your connection details.

---

## Web UI Location

### Finding Your qBittorrent Web UI Settings

1. Open qBittorrent
2. Go to **Tools** → **Options** (or press `Alt+O`)
3. Navigate to the **Web UI** tab
4. Check the following:
   - **IP Address** – Use this for `Host` (use `localhost` or `127.0.0.1` if qBitrr is on the same machine)
   - **Port** – Use this for `Port` (default: 8080)
   - **Authentication** section – Use these credentials for `UserName` and `Password`

### Example Values

| Setting | Example | Notes |
|---------|---------|-------|
| `Host` | `localhost` | Same machine as qBitrr |
| `Host` | `192.168.1.100` | Different machine on local network |
| `Host` | `qbittorrent` | Docker container name in same network |
| `Port` | `8080` | Default qBittorrent WebUI port |
| `UserName` | `admin` | Default username |
| `Password` | `adminadmin` | Default password (change this!) |

---

## Authentication

### Standard Authentication

qBittorrent's Web UI requires username/password authentication by default:

```toml
[qBit]
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "your-secure-password"
```

!!! warning "Security Best Practice"
    **Never** use the default password in production! Change it in qBittorrent's Web UI settings.

### Bypassed Authentication

If you've enabled "Bypass authentication for clients on localhost" in qBittorrent's Web UI settings:

```toml
[qBit]
Host = "localhost"
Port = 8080
UserName = ""      # Leave empty
Password = ""      # Leave empty
```

!!! danger "Security Warning"
    Bypassing authentication is **only safe** if qBittorrent's Web UI is not exposed to the internet or your local network. Only use this for single-machine setups.

---

## Headless Mode

qBitrr can run in "headless mode" where it **only processes searches** without managing qBittorrent torrents. This is useful if you use a different download client (like Sabnzbd/NZBGet) but still want qBitrr's automated search features.

### Enabling Headless Mode

```toml
[qBit]
Disabled = true  # Run without qBittorrent torrent management
```

When `Disabled = true`:

- ✅ **Enabled:** Automated searches for missing media
- ✅ **Enabled:** Overseerr/Ombi request processing
- ✅ **Enabled:** Quality upgrade searches
- ❌ **Disabled:** Torrent health monitoring
- ❌ **Disabled:** Instant imports
- ❌ **Disabled:** Stalled torrent detection
- ❌ **Disabled:** Seeding management
- ❌ **Disabled:** Disk space monitoring

!!! tip "When to Use Headless Mode"
    - You use Usenet (Sabnzbd/NZBGet) for downloads
    - You still want qBitrr's faster automated search features
    - You have a separate qBittorrent setup you don't want qBitrr to touch

---

## Docker Configuration

### Same Docker Network

If qBittorrent and qBitrr are in the same Docker network, use the **container name** as the host:

```toml
[qBit]
Host = "qbittorrent"  # Docker container name
Port = 8080
UserName = "admin"
Password = "password"
```

**Docker Compose example:**

```yaml
services:
  qbittorrent:
    image: linuxserver/qbittorrent:latest
    container_name: qbittorrent
    ports:
      - "8080:8080"
    networks:
      - media

  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    networks:
      - media
    volumes:
      - /path/to/config:/config

networks:
  media:
```

### Different Networks or Host Network

If qBittorrent is on the host network or a different Docker network, use the **host IP** or **domain name**:

```toml
[qBit]
Host = "192.168.1.100"  # Host machine IP
Port = 8080
UserName = "admin"
Password = "password"
```

---

## Troubleshooting Connection Issues

### Test Connection Manually

You can test if qBitrr can reach qBittorrent's API:

```bash
# Replace with your actual values
HOST="localhost"
PORT="8080"
USER="admin"
PASS="password"

# Test login (should return "Ok.")
curl -i --header "Referer: http://$HOST:$PORT" \
  --data "username=$USER&password=$PASS" \
  http://$HOST:$PORT/api/v2/auth/login
```

Expected response:
```
HTTP/1.1 200 OK
...
Ok.
```

### Common Issues

#### "Connection refused" or "Connection timeout"

**Causes:**

- qBittorrent is not running
- Wrong `Host` or `Port` in config
- Firewall blocking connection
- qBittorrent Web UI is disabled

**Solutions:**

1. ✅ Verify qBittorrent is running
2. ✅ Check **Tools** → **Options** → **Web UI** is enabled
3. ✅ Verify `Host` and `Port` match qBittorrent's settings
4. ✅ Check firewall rules allow connections to port 8080
5. ✅ Try `Host = "localhost"` if on the same machine

---

#### "Invalid username or password"

**Causes:**

- Wrong `UserName` or `Password`
- Authentication bypass is enabled but credentials still provided

**Solutions:**

1. ✅ Check credentials in qBittorrent **Web UI** settings
2. ✅ If using authentication bypass, set `UserName = ""` and `Password = ""`
3. ✅ Try logging into qBittorrent's Web UI manually with the same credentials

---



#### Docker: "Name or service not known"

**Causes:**

- Containers are not in the same Docker network
- Wrong container name used

**Solutions:**

1. ✅ Verify both containers are in the same network:
   ```bash
   docker network inspect <network-name>
   ```
2. ✅ Use the exact container name (check `docker ps`)
3. ✅ Try using host IP instead of container name
4. ✅ Ensure qBittorrent's port is exposed if accessing from different networks

---

#### "Unauthorized" errors

**Causes:**

- Session cookie expired
- qBittorrent restarted
- Ban due to too many failed login attempts

**Solutions:**

1. ✅ Restart qBitrr to establish a new session
2. ✅ Check qBittorrent logs for ban messages
3. ✅ Wait 30 minutes if IP is temporarily banned
4. ✅ Verify credentials are correct

---

## Multi-qBittorrent Support (v5.7.x+)

!!! success "New in v5.7.0"
    qBitrr now supports managing torrents across **multiple qBittorrent instances** simultaneously! This enables load balancing, redundancy, VPN isolation, and more.

### Overview

With multi-instance support, you can configure multiple qBittorrent instances and qBitrr will:

- ✅ Monitor torrents across **all instances** for each Arr category
- ✅ Track instance health and automatically skip offline instances
- ✅ Allow torrents to be managed regardless of which instance they're on
- ✅ Maintain 100% backward compatibility with single-instance setups

### How It Works

**Key Concept:** Each Arr instance (Radarr/Sonarr/Lidarr) monitors ALL qBittorrent instances. Torrents are identified by **category**, not by which instance they're on.

**Example:**
- Radarr can send downloads to ANY available qBit instance
- qBitrr monitors ALL instances for torrents in the `radarr-movies` category
- If a Radarr torrent appears on `default` or `seedbox`, qBitrr manages it the same way

### Configuration Syntax

The default instance is always `[qBit]` (required). Additional instances use the `[qBit-NAME]` syntax where NAME is your custom identifier:

```toml
[qBit]  # Default instance (REQUIRED)
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "adminpass"

[qBit-seedbox]  # Additional instance (OPTIONAL)
Host = "192.168.1.100"
Port = 8080
UserName = "admin"
Password = "seedboxpass"

[qBit-vpn]  # Another instance (OPTIONAL)
Host = "10.8.0.2"
Port = 8080
UserName = "admin"
Password = "vpnpass"
```

!!! warning "Important: Use Dash Notation"
    Additional instances MUST use dash (`-`) notation, NOT dot (`.`) notation:

    - ✅ **Correct:** `[qBit-seedbox]`, `[qBit-vpn]`, `[qBit-remote]`
    - ❌ **Wrong:** `[qBit.seedbox]`, `[Seedbox]`, `[qbit-seedbox]` (case-sensitive!)

### WebUI Configuration Management

!!! tip "Easy Instance Management"
    You can manage qBittorrent instances directly from the WebUI without manually editing the config file!

qBitrr's WebUI provides a graphical interface for managing multiple qBittorrent instances:

**Features:**
- ✅ View all configured instances with status indicators
- ✅ Add new instances with form validation
- ✅ Edit existing instance settings (host, port, credentials)
- ✅ Delete secondary instances (default instance cannot be deleted)
- ✅ Rename instances while preserving configuration
- ✅ Enable/disable instances without removing them

**Accessing the Config Editor:**
1. Navigate to `http://your-qbitrr-host:6969/ui`
2. Click "Config" in the navigation menu
3. Scroll to "qBittorrent Instances" section
4. Use "Add Instance", "Configure", or "Delete" buttons

**Adding a New Instance:**
1. Click "Add Instance" button
2. Fill in the form:
   - **Display Name**: Custom identifier (e.g., "qBit-seedbox")
   - **Host**: qBittorrent WebUI hostname or IP address
   - **Port**: qBittorrent WebUI port (usually 8080)
   - **Username**: qBittorrent authentication username (optional)
   - **Password**: qBittorrent authentication password (optional)
   - **Disabled**: Toggle to temporarily disable instance
3. Click "Save" to apply changes
4. Restart qBitrr to activate the new instance

For more details, see the [WebUI Configuration Editor](../webui/config-editor.md) documentation.

### Use Cases

#### 1. Home + Seedbox Setup

Combine local qBittorrent for fast downloads with remote seedbox for long-term seeding:

```toml
[qBit]
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "localpass"

[qBit-seedbox]
Host = "seedbox.example.com"
Port = 8080
UserName = "admin"
Password = "seedboxpass"
```

#### 2. Multiple VPN Endpoints

Run different qBittorrent instances behind different VPN connections:

```toml
[qBit]
Host = "10.8.0.2"  # US VPN
Port = 8080
UserName = "admin"
Password = "password"

[qBit-eu]
Host = "10.8.0.3"  # EU VPN
Port = 8080
UserName = "admin"
Password = "password"

[qBit-asia]
Host = "10.8.0.4"  # Asia VPN
Port = 8080
UserName = "admin"
Password = "password"
```

#### 3. Docker Multi-Container

Isolate different trackers or content types in separate containers:

```toml
[qBit]
Host = "qbittorrent-public"  # Docker container for public torrents
Port = 8080
UserName = "admin"
Password = "password"

[qBit-private]
Host = "qbittorrent-private"  # Docker container for private trackers
Port = 8080
UserName = "admin"
Password = "password"
```

**Docker Compose:**
```yaml
services:
  qbittorrent-public:
    image: linuxserver/qbittorrent:latest
    container_name: qbittorrent-public
    ports:
      - "8080:8080"
    networks:
      - media

  qbittorrent-private:
    image: linuxserver/qbittorrent:latest
    container_name: qbittorrent-private
    ports:
      - "8081:8080"
    networks:
      - media

  qbitrr:
    image: feramance/qbitrr:latest
    networks:
      - media
    volumes:
      - ./config:/config
```

### Instance Health Monitoring

qBitrr automatically monitors the health of each instance and handles failures gracefully:

- **Healthy instances:** Torrents are processed normally
- **Offline instances:** Skipped during each scan loop
- **Failed instances:** Logged but don't block processing of other instances

Check instance health via the WebUI or API:

```bash
curl http://localhost:6969/api/status | jq '.qbitInstances'
```

Response:
```json
{
  "default": {
    "alive": true,
    "host": "localhost",
    "port": 8080,
    "version": "4.6.0"
  },
  "seedbox": {
    "alive": true,
    "host": "192.168.1.100",
    "port": 8080,
    "version": "4.5.5"
  },
  "vpn": {
    "alive": false,
    "host": "10.8.0.2",
    "port": 8080,
    "version": null,
    "error": "Connection timeout"
  }
}
```

### Performance Considerations

Each instance adds ~50-200ms overhead per scan loop. Recommended settings:

| Instances | Recommended `LoopSleepTimer` |
|-----------|------------------------------|
| 1-3       | 5 (default)                  |
| 4-5       | 10                           |
| 6+        | 15                           |

Update in `[Settings]`:
```toml
[Settings]
LoopSleepTimer = 10  # Increase for multiple instances
```

### Troubleshooting Multi-Instance

#### Instance Not Detected

**Symptoms:** Only `default` instance appears in `/api/status`

**Solutions:**

1. ✅ Check section name uses dash: `[qBit-NAME]` not `[qBit.NAME]`
2. ✅ Verify connectivity: `curl http://HOST:PORT/api/v2/app/version`
3. ✅ Check credentials match qBittorrent settings
4. ✅ Review logs for "Failed to initialize instance" messages

#### Torrents Not Processing on Secondary Instance

**Symptoms:** Torrents on `seedbox` ignored, only `default` processed

**Solutions:**

1. ✅ Verify category exists on all instances (qBitrr creates them automatically)
2. ✅ Check category spelling is exact (case-sensitive)
3. ✅ Confirm torrents have correct Arr tags
4. ✅ Check instance is healthy in `/api/status`

#### Category Creation Fails

**Symptoms:** "Failed to create category on instance X" in logs

**Solutions:**

1. ✅ Verify qBittorrent user has category creation permissions
2. ✅ Check qBittorrent version compatibility
3. ✅ Create category manually in qBittorrent Web UI as workaround
4. ✅ Verify qBittorrent has write access to category save paths

### Migration from Single to Multi-Instance

Migrating from a single qBittorrent instance to multiple is seamless:

**Step 1:** Backup config
```bash
cp ~/config/config.toml ~/config/config.toml.backup
```

**Step 2:** Add new instance sections to `config.toml`
```toml
[qBit-seedbox]
Host = "192.168.1.100"
Port = 8080
UserName = "admin"
Password = "password"
```

**Step 3:** Restart qBitrr
```bash
systemctl restart qbitrr  # OR docker restart qbitrr
```

**Step 4:** Verify detection
```bash
curl http://localhost:6969/api/status | jq '.qbitInstances'
```

!!! info "No Database Migration Required"
    The database automatically recreates on restart with the new schema. All torrents will be re-scanned and tracked across all instances.

### Additional Resources

For related documentation, see:

- [API Documentation](../webui/api.md)

---

## Managed Categories & Seeding Settings

qBitrr can manage qBittorrent categories independently of Radarr/Sonarr/Lidarr. This is useful for torrents that aren't tracked by any Arr instance, such as manually added downloads, private tracker torrents, or long-term seeds.

### Overview

When you add categories to the `ManagedCategories` list, qBitrr spawns a dedicated worker process that:

- Monitors all torrents in those categories across all configured qBittorrent instances
- Applies download/upload rate limits per torrent
- Enforces ratio and seeding time limits
- Automatically removes torrents when conditions are met (keeps downloaded files)

### Configuration

Add `ManagedCategories` and `CategorySeeding` to your `[qBit]` section (or any `[qBit-NAME]` section for multi-instance setups):

```toml
[qBit]
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "adminpass"

# Categories managed directly by qBit (not by Arr instances)
ManagedCategories = ["downloads", "private-tracker", "manual"]

# Default seeding settings applied to all managed categories
[qBit.CategorySeeding]
DownloadRateLimitPerTorrent = -1   # KB/s (-1 = no limit)
UploadRateLimitPerTorrent = -1     # KB/s (-1 = no limit)
MaxUploadRatio = -1                # -1 = no limit (e.g. 2.0 = 200%)
MaxSeedingTime = -1                # Seconds (-1 = no limit, 604800 = 7 days)
RemoveTorrent = -1                 # Removal policy (see below)
```

### CategorySeeding Fields

| Field | Default | Unit | Description |
|-------|---------|------|-------------|
| `DownloadRateLimitPerTorrent` | `-1` | KB/s | Per-torrent download speed limit. `-1` disables the limit. |
| `UploadRateLimitPerTorrent` | `-1` | KB/s | Per-torrent upload speed limit. `-1` disables the limit. |
| `MaxUploadRatio` | `-1` | ratio | Maximum share ratio before removal action. `-1` disables. |
| `MaxSeedingTime` | `-1` | seconds | Maximum seeding duration before removal action. `-1` disables. |
| `RemoveTorrent` | `-1` | mode | When to remove the torrent (see table below). |

### RemoveTorrent Modes

| Value | Mode | Behavior |
|-------|------|----------|
| `-1` | Never | Do not remove torrents automatically |
| `1` | On Ratio | Remove when `MaxUploadRatio` is reached |
| `2` | On Time | Remove when `MaxSeedingTime` is reached |
| `3` | Ratio OR Time | Remove when **either** limit is reached (whichever comes first) |
| `4` | Ratio AND Time | Remove only when **both** limits are reached |

!!! note "Torrent Removal"
    When qBitrr removes a torrent, the torrent entry is removed from qBittorrent but **downloaded files are preserved** on disk (`delete_files=False`).

### Examples

#### Seed to 2:1 ratio, then remove

```toml
[qBit]
ManagedCategories = ["downloads"]

[qBit.CategorySeeding]
MaxUploadRatio = 2.0
RemoveTorrent = 1
```

#### Seed for 7 days or until 3:1 ratio

```toml
[qBit]
ManagedCategories = ["private-tracker"]

[qBit.CategorySeeding]
MaxUploadRatio = 3.0
MaxSeedingTime = 604800
RemoveTorrent = 3
```

#### Rate-limit uploads to 500 KB/s, no auto-removal

```toml
[qBit]
ManagedCategories = ["long-term-seed"]

[qBit.CategorySeeding]
UploadRateLimitPerTorrent = 500
RemoveTorrent = -1
```

#### Multi-instance with different seeding policies

```toml
[qBit]
ManagedCategories = ["downloads"]

[qBit.CategorySeeding]
MaxUploadRatio = 2.0
MaxSeedingTime = 604800
RemoveTorrent = 3

[qBit-seedbox]
Host = "192.168.1.100"
Port = 8080
UserName = "admin"
Password = "password"
ManagedCategories = ["long-term-seed"]

[qBit-seedbox.CategorySeeding]
MaxUploadRatio = 5.0
RemoveTorrent = 1
```

### Viewing Managed Categories in the WebUI

The **qBittorrent** tab in the WebUI displays all managed categories with live statistics:

- **Torrent and seeding counts** per category
- **Total size** of torrents in each category
- **Average ratio and seeding time**
- **Configured seeding limits** (max ratio, max time, removal mode)
- **Managed By** indicator showing whether each category is managed by qBit or an Arr instance

Categories refresh automatically — every 1 second when "Live Arr" is enabled, or every 30 seconds otherwise.

!!! warning "Category Conflicts"
    `ManagedCategories` cannot overlap with categories used by Arr instances. The WebUI configuration editor validates this automatically.

---

## Subcategories (qBittorrent 4.6+)

qBittorrent stores hierarchical categories as a single string with `/` as the separator (for example `seed/tleech`). The Web API's `torrents/info?category=` filter is **exact match** on that string — asking for `tleech` will never return torrents whose category is `seed/tleech`. qBitrr's behaviour is aligned with that semantics.

### Two ways to configure subcategories

#### 1. Use the exact path (default; works everywhere)

Set every category value (`Category = ...`, `ManagedCategories = [...]`, `Settings.FailedCategory`, `Settings.RecheckCategory`) to the **full qBittorrent string**. qBitrr will create any missing parent categories automatically and inherit each parent's `savePath`.

```toml
[Radarr-1]
Managed = true
URI = "http://radarr:7878"
APIKey = "..."
Category = "seed/movies"

[qBit]
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "..."
ManagedCategories = ["seed/tleech"]
```

The corresponding qBittorrent category tree (Tools → Options → Use subcategories enabled):

```text
seed/
├── tleech     ← qBit-managed (rate limits, ratio etc.)
└── movies     ← Radarr-managed
```

#### 2. Configure the parent and let qBitrr match descendants (`MatchSubcategories`)

When you'd rather configure `seed` once and have qBitrr manage every `seed/*`, opt in with `MatchSubcategories = true` on the `[qBit]` (or `[qBit-<name>]`) section:

```toml
[qBit]
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "..."
ManagedCategories = ["seed"]
MatchSubcategories = true
```

With this enabled:

- qBitrr fetches the full torrent list once per loop and dispatches torrents to the matching configured prefix in Python.
- A torrent whose qBit category is `seed/tleech`, `seed/longterm`, or any deeper child is dispatched to the owner registered for `seed`.
- An exact configured path always wins over a more general prefix (`seed/tleech` configured separately would shadow `seed`).
- Per-Arr override: add `MatchSubcategories = true` (or `false`) to a `[Radarr-N]` / `[Sonarr-N]` / `[Lidarr-N]` section to override the qBit-instance default for that Arr only.

`MatchSubcategories = false` is the default and preserves the previous exact-match behaviour bit-for-bit.

### Validator output to watch for

qBitrr surfaces a few subcategory-specific log lines at start-up:

| Log message | Meaning |
|-------------|---------|
| `Configured category overlap: 'seed/tleech' is a subcategory of 'seed'.` | Two configured owners overlap. With `MatchSubcategories=true` the more specific path wins; otherwise both owners coexist with exact-match semantics. |
| `qBit-managed category 'seed/tleech' contains '/'. Exact-match mode is in effect ...` | You configured a subcategory path but `MatchSubcategories` is off — qBitrr will only match torrents whose qBit category equals that string. |
| `Created parent category 'seed' on instance '<name>' (save_path=...)` | The parent chain was missing on a qBittorrent instance and was just created so `seed/tleech` could be added cleanly. |

### Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| qBitrr's "qBittorrent" tab shows the category but **no torrents**. | `Category` doesn't match the qBit string verbatim (you used the leaf only). | Either set `Category = "<parent>/<leaf>"` exactly, **or** enable `MatchSubcategories = true` and configure the parent. |
| WebUI returns **404** when opening a Radarr/Sonarr/Lidarr browse page. | Older qBitrr build (pre-subcategories) had `<string:category>` Flask routes that don't accept `/`. | Upgrade qBitrr — current routes use `<path:category>`. |
| `Failed to create parent category 'seed' on '<name>'` warning. | qBittorrent rejects the parent (existing rules, permissions, "Use subcategories" disabled). | Enable Tools → Options → "Use subcategories" in qBittorrent, or create the parent manually with the desired save path. |
| Torrents land in `<DownloadFolder>/seed/tleech` on disk even though qBit's saved path is something else. | qBit's category had no `savePath` set, so qBitrr fell back to `Settings.CompletedDownloadFolder`. | Set the desired `savePath` on the parent category in qBittorrent. qBitrr will inherit it for children. |

!!! warning "Backslashes are not subcategory separators"
    qBittorrent uses `/` as the separator on every platform (including Windows). qBitrr logs a warning if any configured category contains `\`, and treats the segments around backslashes as part of the literal name.

### Migrating an existing flat config to subcategories

1. In qBittorrent, enable **Tools → Options → Use subcategories**.
2. Decide which path each Arr/qBit-managed category should live under (`seed/movies`, `seed/tleech`, etc.).
3. Update each `Category` / `ManagedCategories` entry to the full path.
4. Restart qBitrr; the parent chain is created automatically on every connected qBittorrent instance.
5. Optional: enable `MatchSubcategories = true` on the relevant `[qBit*]` sections so future children get picked up automatically.

### qBittorrent Web API (v4.6+ and v5.x)

Behaviour relevant to subcategories (verified against qBittorrent Web API documentation):

| Topic | Behaviour |
|-------|-----------|
| `GET /api/v2/torrents/info` with `category=` | Filter is **exact** on the category string stored on the torrent (`seed/tleech` ≠ `tleech`). |
| `POST /api/v2/torrents/createCategory` | Creates one category; hierarchical names use `/`. Creating a child may require the parent to exist first depending on client settings and version. |
| **Use subcategories** (GUI: Tools → Options → Downloads) | When enabled, the UI and API expose nested categories as path strings with `/`. When disabled, category names are typically flat; mixing assumptions breaks paths. |

qBitrr uses `qbittorrent-api`, which maps these endpoints to `client.torrents.info(category=...)` and `client.torrent_categories.create_category(...)`.

---

## Advanced Configuration

### Custom TLS/SSL

If qBittorrent's Web UI uses HTTPS:

```toml
[qBit]
Host = "https://qbittorrent.example.com"  # Include https://
Port = 443
UserName = "admin"
Password = "password"
```

!!! info "Certificate Validation"
    qBitrr validates SSL certificates by default. Self-signed certificates may cause connection errors. Consider using a proper certificate or a reverse proxy with valid TLS.

### Reverse Proxy

If qBittorrent is behind a reverse proxy (like Nginx or Traefik):

```toml
[qBit]
Host = "qbit.mydomain.com"  # Full domain
Port = 443                   # Reverse proxy port
UserName = "admin"
Password = "password"
```

**Nginx example:**

```nginx
location /qbittorrent/ {
    proxy_pass http://localhost:8080/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Referer "";
}
```

Then configure qBitrr:

```toml
[qBit]
Host = "mydomain.com/qbittorrent"
Port = 443
UserName = "admin"
Password = "password"
```

---

## Complete Example

### Minimal Local Setup

```toml
[qBit]
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "my-secure-password"
```

### Docker Setup (Same Network)

```toml
[qBit]
Host = "qbittorrent"
Port = 8080
UserName = "admin"
Password = "my-secure-password"
```

### Headless Mode (Search Only)

```toml
[qBit]
Disabled = true
```

---

## Next Steps

Now that qBittorrent is configured, set up your Arr instances:

- [Radarr Configuration](arr/radarr.md)
- [Sonarr Configuration](arr/sonarr.md)
- [Lidarr Configuration](arr/lidarr.md)

Or explore other settings:

- [Configuration Overview](index.md)
- [Torrent Settings](torrents.md)
- [Search Settings](search/index.md)
