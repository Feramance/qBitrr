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

**OpenAPI / Swagger UI:** Interactive HTTP API documentation is served at [`/web/docs`](../webui/api.md#openapi-and-swagger-ui) (and `/api/docs`), with the machine-readable spec at `/web/openapi.json`. When authentication is enabled, open the docs after logging in or use a Bearer token. Details: [WebUI API Reference — OpenAPI](../webui/api.md#openapi-and-swagger-ui).

---

## Authentication and first-run

On **new installs**, authentication is required by default. When you open the WebUI for the first time, you will see a **create credentials** screen: choose a username and password to secure qBitrr. After you set them, you are logged in and local username/password login is enabled. You can change the password later via **Set Password** in WebUI settings.

- **First-run flow:** Open `/ui` → create username and password → set password & sign in → use the WebUI.
- **Existing configs:** If your config file was created before this behavior (or does not set `AuthDisabled`), the app continues to treat auth as disabled for backward compatibility until you set `AuthDisabled = false` or configure a password.
- **Disable auth:** To run without login (e.g. behind your own reverse proxy or in a fully trusted environment), set `AuthDisabled = true` in the `[WebUI]` section of `config.toml`. See [AuthDisabled](#authdisabled) below.

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

# Reserved (no effect today; kept for compatibility)
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
- Must include `Authorization: Bearer` header in API requests
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
curl -H "Authorization: Bearer my-secure-token-12345" \
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

## AuthDisabled

```toml
AuthDisabled = false
```

**Type:** Boolean
**Default (new installs):** `false` (auth required; user is prompted to create credentials)
**Default (configs without this key):** Treated as `true` for backward compatibility (auth disabled)

When `false`, the WebUI requires authentication. On first run with no password set, the user sees the create-credentials screen. When `true`, no login is required and the WebUI is open to anyone with network access.

**Use cases:**

| Value  | Use case |
|--------|----------|
| `false` | New installs; require username/password (default for newly generated configs). |
| `true`  | Disable auth (e.g. behind reverse proxy with its own auth, or trusted network). |

**Example (disable auth):**

```toml
[WebUI]
AuthDisabled = true
```

---

## BehindHttpsProxy

```toml
BehindHttpsProxy = false
```

**Type:** Boolean
**Default:** `false`

Set to `true` when the WebUI is reached over HTTPS (e.g. behind a reverse proxy such as Nginx, Caddy, or Traefik).

**When `true`:**

- The app trusts the `X-Forwarded-Proto` header so `request.is_secure` and generated URLs (e.g. OIDC redirect) reflect the client-facing HTTPS.
- Werkzeug's ProxyFix middleware is applied (`x_proto=1`).
- The session cookie is set with the `Secure` flag so browsers only send it over HTTPS.

**When `false` (default):**

- No proxy headers are trusted; suitable for plain HTTP or when qBitrr is not behind a proxy.
- Session cookie is not marked Secure, so login works over HTTP.

!!! tip "When to enable"
    Enable **BehindHttpsProxy** when you access the WebUI via `https://` and your reverse proxy sets `X-Forwarded-Proto: https`. Leave `false` for local `http://localhost` or plain HTTP to avoid login/session issues.

**Example (HTTPS behind Nginx):**

```toml
[WebUI]
Host = "127.0.0.1"
Port = 6969
BehindHttpsProxy = true
```

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

**Reserved.** The React WebUI does not read this flag today. Browse is **one row per series** (List or Icon mode); seasons and episodes open in the detail modal (`series → seasons → episodes`). The key remains for backwards compatibility.

---

## GroupLidarr

```toml
GroupLidarr = true
```

**Type:** Boolean
**Default:** `true`

**Reserved.** The React WebUI does not read this flag today. Browse is **one row per artist** (List or Icon mode); albums and tracks open in the detail modal (`artist → albums → tracks`). The key remains for backwards compatibility.

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
GroupSonarr = false  # Reserved; no perf effect
GroupLidarr = false  # Reserved; no perf effect
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
BehindHttpsProxy = true  # When using HTTPS reverse proxy; trusts X-Forwarded-Proto and sets Secure cookie
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

## WebUI Settings

WebUI host, port, and token are configured in `config.toml` under the `[WebUI]` section. They are **not** currently overridable via environment variables; use the config file or the in-app config editor.

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
   curl -H "Authorization: Bearer your-token" \
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

2. **Check resource usage:**
   ```bash
   docker stats qbitrr
   htop
   ```

3. **Clear browser cache**

4. **Reduce log retention:**
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
Theme = "Dark"  # Lower power on OLED
```

---

## See Also

- [WebUI Usage Guide](../webui/index.md) - Using the WebUI
- [Config File Reference](config-file.md) - All configuration options
- [Getting Started](../getting-started/index.md) - Initial setup
- [Troubleshooting](../troubleshooting/index.md) - Common issues
