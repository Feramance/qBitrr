# WebUI Configuration

Configure qBitrr's modern React-based web interface for monitoring and managing your qBitrr instance.

---

## Overview

The qBitrr WebUI provides:

- **Real-time monitoring** - Live process status and logs
- **Media browsing** - View movies, shows, and albums from Arr instances
- **Configuration management** - Edit config.toml from the web
- **System information** - Version, uptime, and health metrics
- **Responsive design** - Works on desktop, tablet, and mobile

**Access:** `http://localhost:6969/ui` (default)

---

## Configuration Section

WebUI settings are configured in the `[WebUI]` section:

```toml
[WebUI]
# Listen address
Host = "0.0.0.0"

# Listen port
Port = 6969

# Optional authentication token
Token = ""

# Live updates
LiveArr = true

# Group settings
GroupSonarr = true
GroupLidarr = true

# Default theme
Theme = "Dark"
```

---

## Host

```toml
Host = "0.0.0.0"
```

**Type:** String (IP address)
**Default:** `"0.0.0.0"`

IP address the WebUI server listens on.

**Options:**

- `"0.0.0.0"` - **(Default)** Listen on all network interfaces
- `"127.0.0.1"` - Localhost only (secure, but can't access remotely)
- `"192.168.1.100"` - Specific network interface

**Use cases:**

| Host | Use Case | Security | Remote Access |
|------|----------|----------|---------------|
| `0.0.0.0` | Docker, network access | Medium | ✅ Yes |
| `127.0.0.1` | Localhost only | High | ❌ No |
| Specific IP | Bind to one interface | Medium | ✅ Limited |

**Recommendations:**

```toml
# Docker (with reverse proxy)
Host = "0.0.0.0"

# Native (with reverse proxy)
Host = "127.0.0.1"

# Native (direct access)
Host = "0.0.0.0"  # Use with Token for security
```

---

## Port

```toml
Port = 6969
```

**Type:** Integer
**Default:** `6969`

TCP port the WebUI listens on.

**Access URL:** `http://<host>:<port>/ui`

**Common ports:**

```toml
Port = 6969   # Default
Port = 8080   # Alternative
Port = 443    # HTTPS (with reverse proxy)
```

**Port conflicts:**

If port 6969 is in use:

```bash
# Check what's using the port
sudo lsof -i :6969
sudo netstat -tulpn | grep 6969

# Change to alternative
Port = 6970
```

---

## Token

```toml
Token = ""
```

**Type:** String
**Default:** `""` (empty, no authentication)

Bearer token for API authentication.

**When empty:**
- WebUI and API are publicly accessible
- No authentication required
- Anyone with network access can use the WebUI

**When set:**
- All `/api/*` endpoints require authentication
- Must include `X-API-Token` header in API requests
- WebUI automatically handles token for you

**Setting up authentication:**

```toml
[WebUI]
Token = "my-secure-token-12345"
```

**Generating secure tokens:**

```bash
# Linux/macOS
openssl rand -hex 32

# Or
python3 -c "import secrets; print(secrets.token_hex(32))"

# Output: a1b2c3d4e5f6...
```

**Using authenticated API:**

```bash
curl -H "X-API-Token: my-secure-token-12345" \
  http://localhost:6969/api/processes
```

!!! warning "Security Recommendation"
    **Always set a token if:**

    - qBitrr is accessible from the internet
    - You're not using a reverse proxy with authentication
    - Multiple users have network access

    **Token can be omitted if:**

    - Behind reverse proxy with its own authentication
    - Only accessible from localhost
    - Running in a trusted private network

---

## LiveArr

```toml
LiveArr = true
```

**Type:** Boolean
**Default:** `true`

Enable live updates for Arr instance views (Radarr/Sonarr/Lidarr tabs).

**When true:**
- Real-time status updates
- Progress bars update automatically
- No manual page refresh needed
- Uses polling every few seconds

**When false:**
- Static snapshots
- Must manually refresh page
- Lower resource usage
- Reduced API calls to Arr instances

**Recommendation:** `true` for best user experience.

**Performance consideration:**

```toml
# High-resource system
LiveArr = true  # Enable real-time updates

# Low-resource system (Raspberry Pi, etc.)
LiveArr = false  # Reduce load
```

---

## GroupSonarr

```toml
GroupSonarr = true
```

**Type:** Boolean
**Default:** `true`

Group Sonarr episodes by series in the WebUI.

**When true (grouped):**

```
└─ Breaking Bad
   ├─ S01E01 - Pilot
   ├─ S01E02 - Cat's in the Bag
   └─ S01E03 - ...and the Bag's in the River
```

**When false (flat list):**

```
├─ Breaking Bad S01E01 - Pilot
├─ Breaking Bad S01E02 - Cat's in the Bag
└─ Breaking Bad S01E03 - ...and the Bag's in the River
```

**Recommendation:** `true` for better organization.

---

## GroupLidarr

```toml
GroupLidarr = true
```

**Type:** Boolean
**Default:** `true`

Group Lidarr albums by artist in the WebUI.

**When true (grouped):**

```
└─ Pink Floyd
   ├─ The Dark Side of the Moon
   ├─ The Wall
   └─ Wish You Were Here
```

**When false (flat list):**

```
├─ Pink Floyd - The Dark Side of the Moon
├─ Pink Floyd - The Wall
└─ Pink Floyd - Wish You Were Here
```

**Recommendation:** `true` for better navigation.

---

## ViewDensity

```toml
ViewDensity = "Comfortable"
```

**Type:** String
**Default:** `"Comfortable"`
**Options:** `"Comfortable"`, `"Compact"`

UI density setting for tables and lists.

- `"Comfortable"` - More spacing, easier to read
- `"Compact"` - Denser layout, shows more data per screen

**Note:** Users can toggle this in the WebUI settings. This sets the initial default.

---

## Theme

```toml
Theme = "Dark"
```

**Type:** String
**Default:** `"Dark"`
**Options:** `"Dark"`, `"Light"`

Default color theme for the WebUI.

- `"Dark"` - Dark mode (easier on eyes, lower power consumption)
- `"Light"` - Light mode (better in bright environments)

**Note:** Users can toggle theme in the WebUI itself. This sets the initial default.

---

## Complete Configuration Examples

### Example 1: Default (Public Access)

```toml
[WebUI]
Host = "0.0.0.0"
Port = 6969
Token = ""  # No authentication
LiveArr = true
GroupSonarr = true
GroupLidarr = true
Theme = "Dark"
ViewDensity = "Comfortable"
```

**Access:** `http://localhost:6969/ui`

**Use case:** Local network, trusted environment.

---

### Example 2: Secured with Token

```toml
[WebUI]
Host = "0.0.0.0"
Port = 6969
Token = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
LiveArr = true
GroupSonarr = true
GroupLidarr = true
Theme = "Dark"
ViewDensity = "Comfortable"
```

**Access:** `http://localhost:6969/ui` (token handled automatically by WebUI)

**Use case:** Exposed to internet or untrusted network.

---

### Example 3: Localhost Only (with Reverse Proxy)

```toml
[WebUI]
Host = "127.0.0.1"
Port = 6969
Token = ""  # Reverse proxy handles auth
LiveArr = true
GroupSonarr = true
GroupLidarr = true
Theme = "Dark"
ViewDensity = "Comfortable"
```

**Nginx reverse proxy:**

```nginx
location /qbitrr/ {
    proxy_pass http://127.0.0.1:6969/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

**Access:** `https://yourdomain.com/qbitrr/ui`

---

### Example 4: Low Resource System

```toml
[WebUI]
Host = "0.0.0.0"
Port = 6969
Token = ""
LiveArr = false  # Disable auto-refresh
GroupSonarr = false  # Flat lists
GroupLidarr = false  # Flat lists
Theme = "Dark"
```

**Use case:** Raspberry Pi, low-power devices.

---

## Reverse Proxy Configuration

### Nginx

```nginx
server {
    listen 80;
    server_name qbitrr.example.com;

    location / {
        proxy_pass http://localhost:6969;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

**qBitrr config:**

```toml
[WebUI]
Host = "127.0.0.1"  # Only listen on localhost
Port = 6969
```

---

### Apache

```apache
<VirtualHost *:80>
    ServerName qbitrr.example.com

    ProxyPreserveHost On
    ProxyPass / http://localhost:6969/
    ProxyPassReverse / http://localhost:6969/

    <Location />
        Require all granted
    </Location>
</VirtualHost>
```

**Enable required modules:**

```bash
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo systemctl restart apache2
```

---

### Traefik (Docker)

```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.qbitrr.rule=Host(`qbitrr.example.com`)"
      - "traefik.http.services.qbitrr.loadbalancer.server.port=6969"
      - "traefik.http.routers.qbitrr.entrypoints=websecure"
      - "traefik.http.routers.qbitrr.tls.certresolver=letsencrypt"
```

---

### Caddy

```caddyfile
qbitrr.example.com {
    reverse_proxy localhost:6969
}
```

---

## Docker Port Mapping

**Docker Run:**

```bash
docker run -d \
  --name qbitrr \
  -p 6969:6969 \
  -v /path/to/config:/config \
  feramance/qbitrr:latest
```

**Docker Compose:**

```yaml
version: '3'
services:
  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    ports:
      - "6969:6969"  # External:Internal
    volumes:
      - /path/to/config:/config
```

**Alternative port mapping:**

```yaml
ports:
  - "8080:6969"  # Access on port 8080 externally
```

**Access:** `http://localhost:8080/ui`

---

## Environment Variable Overrides

Override WebUI settings with environment variables:

```bash
# Docker
docker run -d \
  -e QBITRR_WEBUI_HOST="127.0.0.1" \
  -e QBITRR_WEBUI_PORT="8080" \
  -e QBITRR_WEBUI_TOKEN="my-token" \
  feramance/qbitrr:latest

# Docker Compose
environment:
  - QBITRR_WEBUI_HOST=127.0.0.1
  - QBITRR_WEBUI_PORT=8080
  - QBITRR_WEBUI_TOKEN=my-token
```

**Format:** `QBITRR_<SECTION>_<KEY>=value`

---

## Troubleshooting

### WebUI Not Loading

**Symptom:** Cannot access `http://localhost:6969/ui`

**Solutions:**

1. **Check qBitrr is running:**
   ```bash
   # Docker
   docker ps | grep qbitrr

   # Systemd
   systemctl status qbitrr

   # Process
   ps aux | grep qbitrr
   ```

2. **Verify port:**
   ```bash
   # Check if port is listening
   sudo netstat -tulpn | grep 6969
   sudo lsof -i :6969
   ```

3. **Check logs:**
   ```bash
   # Docker
   docker logs qbitrr | grep -i webui

   # Native
   tail -f ~/logs/WebUI.log
   ```

4. **Verify configuration:**
   ```toml
   [WebUI]
   Host = "0.0.0.0"
   Port = 6969
   ```

---

### 401 Unauthorized

**Symptom:** API requests return 401 errors

**Solutions:**

1. **Check token is set:**
   ```toml
   [WebUI]
   Token = "your-token"
   ```

2. **Include token in requests:**
   ```bash
   curl -H "X-API-Token: your-token" \
     http://localhost:6969/api/processes
   ```

3. **Clear browser cache and cookies**

4. **Check WebUI logs:**
   ```bash
   tail -f ~/logs/WebUI.log | grep -i "401\|auth"
   ```

---

### Connection Refused

**Symptom:** Browser shows "Connection refused"

**Solutions:**

1. **Check Host binding:**
   ```toml
   # If accessing remotely, must not be 127.0.0.1
   Host = "0.0.0.0"
   ```

2. **Check firewall:**
   ```bash
   # UFW
   sudo ufw allow 6969

   # Firewalld
   sudo firewall-cmd --add-port=6969/tcp --permanent
   sudo firewall-cmd --reload
   ```

3. **Docker: Check port mapping:**
   ```bash
   docker port qbitrr
   ```

---

### Slow Performance

**Symptom:** WebUI is slow or unresponsive

**Solutions:**

1. **Disable live updates:**
   ```toml
   LiveArr = false
   ```

2. **Disable grouping:**
   ```toml
   GroupSonarr = false
   GroupLidarr = false
   ```

3. **Check resource usage:**
   ```bash
   docker stats qbitrr
   htop
   ```

4. **Clear browser cache**

5. **Reduce log retention:**
   - Fewer logs = faster log view
   - Consider log rotation

---

### CORS Errors

**Symptom:** Browser console shows CORS errors

**Solutions:**

1. **Access via correct URL:**
   - Use `http://localhost:6969/ui`
   - Not `http://127.0.0.1:6969/ui` (different origin)

2. **Configure reverse proxy correctly:**
   - Set proper headers
   - See reverse proxy examples above

---

## Security Best Practices

### 1. Use a Strong Token

```bash
# Generate secure token
openssl rand -hex 32
```

```toml
[WebUI]
Token = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6"
```

---

### 2. Bind to Localhost with Reverse Proxy

```toml
[WebUI]
Host = "127.0.0.1"  # Only localhost
```

Use Nginx/Apache/Caddy for external access with HTTPS.

---

### 3. Use HTTPS

Never expose WebUI over HTTP on the internet.

**Options:**

- Reverse proxy with Let's Encrypt
- Cloudflare Tunnel
- VPN (Tailscale, WireGuard)

---

### 4. Restrict Network Access

**Docker:**

```yaml
services:
  qbitrr:
    networks:
      - internal  # Private network only

networks:
  internal:
    internal: true  # No external access
```

**Firewall:**

```bash
# Only allow from specific IP
sudo ufw allow from 192.168.1.0/24 to any port 6969
```

---

### 5. Regular Updates

Keep qBitrr updated for security patches:

```bash
# Docker
docker pull feramance/qbitrr:latest
docker restart qbitrr

# PyPI
pip install -U qbitrr2
```

---

## Performance Tuning

### For Large Libraries

```toml
[WebUI]
LiveArr = false  # Disable auto-refresh
GroupSonarr = false  # Faster rendering
GroupLidarr = false  # Faster rendering
```

**In WebUI:**
- Use search/filters to reduce displayed items
- Limit log entries shown

---

### For Low-Resource Systems

```toml
[WebUI]
Host = "127.0.0.1"
Port = 6969
Token = ""
LiveArr = false
GroupSonarr = false
GroupLidarr = false
Theme = "Dark"  # Lower power on OLED
```

---

## See Also

- [WebUI Usage Guide](../webui/index.md) - Using the WebUI
- [Config File Reference](config-file.md) - All configuration options
- [Getting Started](../getting-started/index.md) - Initial setup
- [Troubleshooting](../troubleshooting/index.md) - Common issues
