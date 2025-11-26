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
```

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

## qBittorrent Version Configuration

qBittorrent made significant API changes in version 5.x. qBitrr needs to know which version you're running to use the correct API endpoints.

### qBittorrent 4.x (Default)

qBitrr assumes qBittorrent 4.x by default. No additional configuration needed.

```toml
[qBit]
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "password"
# Version5 is not set - defaults to false (qBittorrent 4.x)
```

!!! info "Last Validated 4.x Version"
    qBitrr has been tested with qBittorrent **4.6.7**. Newer 4.x versions should work but may have untested edge cases.

### qBittorrent 5.x

If you're running qBittorrent 5.0.0 or newer, **you must set** `Version5 = true`:

```toml
[qBit]
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "password"
Version5 = true  # Required for qBittorrent 5.x
```

!!! warning "API Compatibility"
    Using the wrong `Version5` setting will cause API errors. Check your qBittorrent version:

    - **qBittorrent → Help → About** to see your version
    - Set `Version5 = true` if version is ≥ 5.0.0
    - Leave it unset or `false` for versions < 5.0.0

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

#### "API version mismatch" or "Invalid request"

**Causes:**

- qBittorrent version doesn't match `Version5` setting
- API endpoint changes between versions

**Solutions:**

1. ✅ Check qBittorrent version: **Help** → **About**
2. ✅ Set `Version5 = true` if running qBittorrent 5.x
3. ✅ Remove or set `Version5 = false` if running qBittorrent 4.x
4. ✅ Check qBitrr logs for specific API errors

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
Version5 = true  # If using qBittorrent 5.x
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
- [Search Settings](search.md)
