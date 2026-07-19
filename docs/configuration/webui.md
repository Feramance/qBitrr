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

On **new installs**, authentication is required by default. When you open the WebUI for the first time, you will see a **create credentials** screen: choose a username and password to secure qBitrr. First-time credential creation requires a setup token so that someone who can merely reach the WebUI port cannot claim the account before you do. Use either the `QBITRR_SETUP_TOKEN` environment variable value, or the generated `WebUI.Token` value from `config.toml`. After you set credentials, you are logged in and local username/password login is enabled. You can change the password later via **Set Password** in WebUI settings.

- **First-run flow:** Open `/ui` → enter a setup token → create username and password → set password & sign in → use the WebUI.
- **Existing configs:** If your config file was created before this behavior (or does not set `AuthDisabled`), the app continues to treat auth as disabled for backward compatibility until you set `AuthDisabled = false` or configure a password.
- **Disable auth:** To run without login (e.g. behind your own reverse proxy or in a fully trusted environment), set `AuthDisabled = true` in the `[WebUI]` section of `config.toml`. This opens the **entire** admin API (including `/api/token`, `/web/token`, config writes, and self-update) to anyone who can reach the port. On a public bind (`0.0.0.0` / `::`), you must also set `AllowInsecureExposure = true`. See [AuthDisabled](#authdisabled) and [AllowInsecureExposure](#allowinsecureexposure) below.

---

## Configuration Section

WebUI settings are configured in the `[WebUI]` section:

```toml
[WebUI]
# Listen address
Host = "0.0.0.0"

# Listen port
Port = 6969

# Bearer token (used when auth is enabled; does not enable auth by itself)
Token = ""

# Require login on new installs (set true only for trusted/proxy setups)
AuthDisabled = false

# Live updates
LiveArr = true

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

# Native (direct access) — require AuthDisabled = false (login)
Host = "0.0.0.0"
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
**Default:** `""` (auto-generated and persisted on first start if empty)

Bearer token used when authentication is **enabled** (`AuthDisabled = false`). Setting a token does **not** enable auth by itself.

When authorized (session login, valid Bearer token, or `AuthDisabled = true`), clients can retrieve it from `GET /api/token` and `GET /web/token`. The WebUI SPA uses these endpoints after login.

**Using authenticated API (when auth is enabled):**

```bash
curl -H "Authorization: Bearer my-secure-token-12345" \
  http://localhost:6969/api/processes
```

**Generating secure tokens:**

```bash
openssl rand -hex 32
# Or
python3 -c "import secrets; print(secrets.token_hex(32))"
```

!!! warning "Security Recommendation"
    Prefer `AuthDisabled = false` with a password or OIDC when the WebUI is reachable beyond a fully trusted network. Token alone does not close the API while `AuthDisabled = true`.

---

## AuthDisabled

```toml
AuthDisabled = false
```

**Type:** Boolean
**Default (new installs):** `false` (auth required; user is prompted to create credentials)
**Default (configs without this key):** Treated as `true` for backward compatibility (auth disabled)

When `false`, the WebUI requires authentication. On first run with no password set, the user sees the create-credentials screen. When `true`, **no login is required** and the full admin surface is open to anyone who can reach the port, including:

- Token retrieval (`/api/token`, `/web/token`)
- Config read/write
- Process restart / Arr rebuild
- Self-update (`POST /update`)

**Use cases:**

| Value  | Use case |
|--------|----------|
| `false` | New installs; require username/password (default for newly generated configs). |
| `true`  | Disable auth (e.g. behind reverse proxy with its own auth, or trusted network). |

**Example (disable auth on a public bind — requires acknowledgment):**

```toml
[WebUI]
Host = "0.0.0.0"
AuthDisabled = true
AllowInsecureExposure = true
```

---

## AllowInsecureExposure

```toml
AllowInsecureExposure = false
```

**Type:** Boolean
**Default (new installs):** `false`
**Default (configs without this key):** Warn-only (startup continues) for backward compatibility

When `AuthDisabled = true` and `Host` is `0.0.0.0` or `::`, qBitrr refuses to start the WebUI unless this is set to `true`. Use it only when you intentionally expose an unauthenticated admin UI (typically behind a reverse proxy that already authenticates clients).

---

## AllowInsecureTokenQuery

```toml
AllowInsecureTokenQuery = false
```

**Type:** Boolean
**Default (new installs):** `false`
**Default (configs without this key):** Treated as `true` (query tokens still accepted) for backward compatibility

When `true`, `?token=` may be used for API auth. This is insecure (token appears in logs and browser history). Prefer `Authorization: Bearer`. New installs default to header-only.

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
- Werkzeug's ProxyFix middleware is applied (`x_for=1`, `x_proto=1`).
- The session cookie is set with the `Secure` flag so browsers only send it over HTTPS.

**When `false` (default):**

- No proxy headers are trusted; suitable for plain HTTP or when qBitrr is not behind a proxy.
- Session cookie is not marked Secure, so login works over HTTP.

!!! warning "Trusted proxy only"
    Enable **BehindHttpsProxy** only when a trusted reverse proxy **overwrites** `X-Forwarded-*` headers. If clients can reach qBitrr directly while this is true, they can spoof `X-Forwarded-For` and bypass login rate limits.

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

## UrlBase

```toml
UrlBase = ""
```

**Type:** String (URL path)
**Default:** `""` (site root)

Public path prefix when qBitrr is served behind a reverse proxy on a subpath instead of a dedicated subdomain.

**Examples:**

| UrlBase | UI URL |
|---------|--------|
| `""` | `https://host/ui` |
| `"/qbitrr"` | `https://host/qbitrr/ui` |

**Rules:**

- Must start with `/` when set (e.g. `/qbitrr`, not `qbitrr`)
- Must **not** end with a trailing slash
- Set this to match the path your reverse proxy exposes publicly

When `UrlBase` is set, qBitrr prefixes redirects, session cookies, OIDC callback URLs, and WebUI API calls accordingly. The React app reads the prefix from the page URL and `/web/meta`.

!!! tip "OIDC under a subpath"
    Register the redirect URI as `https://your-host<UrlBase><CallbackPath>` — for example `https://example.com/qbitrr/signin-oidc` when `UrlBase = "/qbitrr"` and `CallbackPath = "/signin-oidc"`.

---

## LiveArr

```toml
LiveArr = true
```

**Type:** Boolean
**Default:** `true`
**Label:** Live (app-bar switch)

Enable live updates for Arr catalogs (Radarr/Sonarr/Lidarr) and the qBittorrent overview.

**When true:**
- Auto-refresh while the Arr or qBittorrent tab is active
- Progress and status update without a full page reload
- Uses polling every few seconds on the active tab

**When false:**
- No auto-refresh on Arr or qBittorrent views
- Use the in-page Refresh button
- Lower resource usage and fewer Arr / qBittorrent API calls

**Recommendation:** `true` for best user experience.

**Performance consideration:**

```toml
# High-resource system
LiveArr = true  # Enable real-time updates

# Low-resource system (Raspberry Pi, etc.)
LiveArr = false  # Reduce load
```

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

### Example 1: Default (auth required)

```toml
[WebUI]
Host = "0.0.0.0"
Port = 6969
AuthDisabled = false
LiveArr = true
Theme = "Dark"
ViewDensity = "Comfortable"
```

**Access:** `http://localhost:6969/ui` (create credentials on first run)

**Use case:** Typical install; login required.

---

### Example 2: Secured with login (recommended for exposed hosts)

```toml
[WebUI]
Host = "0.0.0.0"
Port = 6969
AuthDisabled = false
LocalAuthEnabled = true
LiveArr = true
Theme = "Dark"
ViewDensity = "Comfortable"
```

**Access:** `http://localhost:6969/ui` (username/password or OIDC)

**Use case:** Exposed to internet or untrusted network.

---

### Example 3: Subpath Behind Reverse Proxy

```toml
[WebUI]
Host = "127.0.0.1"
Port = 6969
UrlBase = "/qbitrr"
BehindHttpsProxy = true
AuthDisabled = true
AllowInsecureExposure = false  # loopback bind; ack not required
LiveArr = true
Theme = "Dark"
ViewDensity = "Comfortable"
```

**Nginx reverse proxy** (prefix-stripping `proxy_pass` — most common):

```nginx
location /qbitrr/ {
    proxy_pass http://127.0.0.1:6969/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Access:** `https://yourdomain.com/qbitrr/ui`

`UrlBase` must match the public path (`/qbitrr`). Nginx strips the prefix before forwarding to qBitrr; the app still generates browser-facing URLs under `/qbitrr/...`.

---

### Example 4: Low Resource System

```toml
[WebUI]
Host = "0.0.0.0"
Port = 6969
AuthDisabled = false
LiveArr = false  # Disable auto-refresh
Theme = "Dark"
```

**Use case:** Raspberry Pi, low-power devices.

---

## Reverse Proxy Configuration

### Subpath vs dedicated host

| Deployment | `UrlBase` | Typical proxy |
|------------|-----------|---------------|
| Dedicated host (`qbitrr.example.com`) | `""` | `location / { proxy_pass http://127.0.0.1:6969; }` |
| Shared host subpath (`example.com/qbitrr`) | `"/qbitrr"` | `location /qbitrr/ { proxy_pass http://127.0.0.1:6969/; }` |

### Nginx (dedicated host)

```nginx
server {
    listen 80;
    server_name qbitrr.example.com;

    # Keep WebUI and static/PWA paths behind one auth-protected location.
    location / {
        include /config/nginx/authentik-location.conf;
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

    # Optional: bypass proxy auth for API clients only.
    location ~ ^/(qbitrr/)?api/ {
        proxy_pass http://localhost:6969;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
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

### 1. Keep authentication enabled

```toml
[WebUI]
AuthDisabled = false
```

Create a strong username/password (or OIDC) on first run. Token alone does not enable auth.

---

### 2. Bind to Localhost with Reverse Proxy

```toml
[WebUI]
Host = "127.0.0.1"  # Only localhost
```

Use Nginx/Apache/Caddy for external access with HTTPS. If you must use `AuthDisabled = true` on `0.0.0.0`, set `AllowInsecureExposure = true` only when the proxy already authenticates clients.

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
