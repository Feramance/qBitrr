# WebUI Overview

qBitrr includes a modern, React-based web interface for real-time monitoring, configuration management, and system control. Built with TypeScript and Mantine UI components, the WebUI provides a responsive, intuitive interface for managing your qBitrr instance.

---

## Accessing the WebUI

### Default URL

The WebUI is available at:

```
http://localhost:6969/ui
```

Or if you've changed the port in your configuration:

```
http://YOUR_SERVER_IP:YOUR_PORT/ui
```

### Configuration

WebUI settings are configured in `config.toml`:

```toml
[WebUI]
# Bind address (0.0.0.0 for all interfaces, 127.0.0.1 for localhost only)
Host = "0.0.0.0"

# Port number
Port = 6969

# Optional authentication token
Token = ""

# WebUI-specific display settings
LiveArr = true        # Enable live Arr instance views
GroupSonarr = true    # Group Sonarr series by show
GroupLidarr = true    # Group Lidarr albums by artist
Theme = "Dark"        # Dark | Light | Auto
```

### Remote Access

To access the WebUI remotely:

**Option 1: Direct Access (Not Recommended for Public)**

```toml
[WebUI]
Host = "0.0.0.0"  # Listen on all interfaces
Port = 6969
Token = "your-secure-random-token-here"  # Require authentication
```

**Option 2: Reverse Proxy (Recommended)**

Use Nginx, Caddy, or Traefik to proxy requests:

=== "Nginx"

    ```nginx
    location /qbitrr/ {
        proxy_pass http://localhost:6969/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    ```

=== "Caddy"

    ```caddy
    qbitrr.example.com {
        reverse_proxy localhost:6969
    }
    ```

=== "Traefik (Docker)"

    ```yaml
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.qbitrr.rule=Host(`qbitrr.example.com`)"
      - "traefik.http.services.qbitrr.loadbalancer.server.port=6969"
    ```

**Option 3: SSH Tunnel**

```bash
# Forward remote port 6969 to local
ssh -L 6969:localhost:6969 user@your-server

# Access via http://localhost:6969/ui
```

---

## Core Features

### 🔄 Process Management

Monitor and control all qBitrr processes from a unified dashboard.

**Features:**

- **Real-time Status** - Live process state updates (Running, Stopped, Crashed)
- **Health Indicators** - Connection status to qBittorrent and Arr instances
- **Resource Monitoring** - CPU, memory, and uptime statistics per process
- **Process Control** - Start, stop, or restart individual Arr manager processes
- **Auto-restart Status** - See if auto-restart is enabled and restart counts
- **Process Logs** - Quick access to process-specific logs

**Use Cases:**

- Restart a specific Arr instance without restarting qBitrr
- Check if an Arr instance is properly connected
- Monitor which processes are consuming resources
- Verify auto-restart is working after failures

[**Detailed Process Management Guide →**](processes.md)

---

### 📋 Live Log Viewer

Tail and search logs in real-time directly from your browser.

**Features:**

- **Multiple Log Sources**
  - Main.log - qBitrr core application logs
  - WebUI.log - Web interface and API logs
  - Per-Arr logs - Radarr-Movies.log, Sonarr-TV.log, etc.

- **Advanced Filtering**
  - By log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  - By search term (regex supported)
  - By time range
  - By source/category

- **Real-time Streaming** - Auto-scroll and live updates via WebSocket
- **Export** - Download logs as text files
- **Syntax Highlighting** - Color-coded log levels
- **Pagination** - Load more logs on demand

**Keyboard Shortcuts:**

- ++ctrl+f++ - Focus search box
- ++esc++ - Clear search
- ++space++ - Pause/resume auto-scroll

**Use Cases:**

- Debug torrent processing issues in real-time
- Monitor search activity across all Arr instances
- Track down errors without SSH access
- Share log excerpts with support

[**Detailed Log Viewer Guide →**](logs.md)

---

### 🎬 Arr Instance Views

Browse and manage your media libraries directly from qBitrr.

#### Radarr View

**Features:**

- **Movie Library Table**
  - Title, year, quality profile, monitored status
  - File information (size, codec, resolution)
  - Custom format scores
  - Download status (queued, downloading, imported)
  - Missing vs. downloaded indicators

- **Sorting & Filtering**
  - Sort by title, year, date added, quality, file size
  - Filter by monitored status
  - Filter by quality profile
  - Filter by custom format score
  - Search by title

- **Quick Actions**
  - Trigger manual search
  - Toggle monitoring
  - View in Radarr (direct link)
  - Refresh metadata

**Statistics:**

- Total movies: X
- Monitored: X
- Missing: X
- Downloaded: X
- Disk space used: X GB

[**Detailed Radarr View Guide →**](arr-views.md#radarr-view)

#### Sonarr View

**Features:**

- **Series Library Table**
  - Show title, seasons, episodes
  - Monitored status per series/season
  - Episode file information
  - Next airing episode
  - Download progress

- **Grouping**
  - Group episodes by series (default)
  - Flat view (all episodes)
  - Group by season

- **Episode Filtering**
  - Missing episodes
  - Unmonitored episodes
  - Aired vs. future episodes
  - Episode quality

- **Quick Actions**
  - Search for missing episodes
  - Search for entire series
  - Toggle series monitoring
  - View in Sonarr

**Statistics:**

- Total series: X
- Monitored: X
- Episodes missing: X
- Episodes downloaded: X
- Next airing: [Show Name] - S01E05

[**Detailed Sonarr View Guide →**](arr-views.md#sonarr-view)

#### Lidarr View

**Features:**

- **Album Library Table**
  - Artist, album title, release year
  - Monitored status
  - Track count and duration
  - Quality (FLAC, MP3, etc.)
  - Download status

- **Grouping**
  - Group albums by artist (default)
  - Flat view (all albums)

- **Filtering**
  - By artist
  - By quality
  - By monitored status
  - Missing vs. downloaded

- **Quick Actions**
  - Search for missing albums
  - Search for artist discography
  - Toggle monitoring
  - View in Lidarr

**Statistics:**

- Total artists: X
- Total albums: X
- Monitored albums: X
- Missing albums: X
- Disk space used: X GB

[**Detailed Lidarr View Guide →**](arr-views.md#lidarr-view)

---

### ⚙️ Configuration Editor

Edit your qBitrr configuration without leaving the browser.

**Features:**

- **Live TOML Editor**
  - Syntax highlighting
  - Line numbers
  - Auto-indentation
  - Bracket matching

- **Validation**
  - Real-time syntax validation
  - Error highlighting with line numbers
  - Helpful error messages
  - Schema validation

- **Configuration Testing**
  - Test connection to qBittorrent
  - Test connection to Arr instances
  - Validate API keys
  - Check path accessibility

- **Backup & Restore**
  - Automatic backup before saving
  - Manual backup creation
  - Restore from previous backups
  - Download configuration file

- **Apply Changes**
  - Save configuration
  - Restart qBitrr with new config
  - Restart specific Arr instances only
  - Rollback on failure

**Safety Features:**

- ✅ Validation before saving
- ✅ Automatic backup creation
- ✅ Rollback on invalid config
- ✅ Confirmation dialogs for destructive actions

**Use Cases:**

- Adjust settings without SSH/terminal access
- Test configuration changes safely
- Quick fixes without text editor
- Manage qBitrr from mobile devices

[**Detailed Configuration Editor Guide →**](config-editor.md)

---

### 📊 System Dashboard

Overview of qBitrr's health and performance.

**Metrics Displayed:**

- **Version Information**
  - qBitrr version
  - Python version
  - qBittorrent version
  - Arr instance versions

- **Uptime & Performance**
  - qBitrr uptime
  - Total torrents processed
  - Successful imports
  - Failed downloads handled
  - Average processing time

- **Storage & Resources**
  - Disk space on download folder
  - Database size
  - Log file sizes
  - Memory usage (if available)

- **Connection Status**
  - qBittorrent: ✅ Connected / ❌ Disconnected
  - Radarr instances: ✅/❌
  - Sonarr instances: ✅/❌
  - Lidarr instances: ✅/❌
  - Overseerr/Ombi: ✅/❌

- **Recent Activity**
  - Last 10 imports
  - Last 5 searches triggered
  - Recent errors
  - Latest processed torrents

**Refresh Rates:**

- Connection status: Every 30 seconds
- Metrics: Every 60 seconds
- Activity: Real-time (WebSocket)

---

## Navigation & Interface

### Main Navigation

The WebUI uses a tab-based navigation system:

| Tab | Icon | Purpose |
|-----|------|---------|
| **Processes** | 🔄 | Process management and control |
| **Logs** | 📋 | Live log viewer with filtering |
| **Radarr** | 🎬 | Radarr movie library views |
| **Sonarr** | 📺 | Sonarr TV series views |
| **Lidarr** | 🎵 | Lidarr music library views |
| **Config** | ⚙️ | Configuration editor |
| **API** | 🔌 | API documentation and testing |

### Header Bar

- **Logo & Title** - Click to return to Processes tab
- **Theme Toggle** - Switch between Dark/Light/Auto
- **Refresh Indicator** - Shows when data is being fetched
- **Connection Status** - Icon indicates connection to backend
- **Version Badge** - Current qBitrr version

### Footer Bar

- **Status Messages** - Success/error notifications
- **Active Processes** - Count of running Arr instances
- **Last Update** - Timestamp of last data refresh

---

## Authentication & Security

### Token-Based Authentication

Protect your WebUI with token authentication:

```toml
[WebUI]
Token = "your-secure-random-token-here"
```

**Generate a secure token:**

```bash
# Using openssl
openssl rand -base64 32

# Using Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Using the token:**

When configured, all API requests require the `X-API-Token` header:

```bash
curl http://localhost:6969/api/processes \
  -H "X-API-Token: your-token-here"
```

The WebUI automatically includes the token if you access it through the main interface.

### Network Security

**Localhost Only (Recommended for Local Use):**

```toml
[WebUI]
Host = "127.0.0.1"  # Only accessible from localhost
Port = 6969
Token = ""  # Optional for localhost
```

**All Interfaces (Requires Token):**

```toml
[WebUI]
Host = "0.0.0.0"  # Accessible from network
Port = 6969
Token = "your-secure-token"  # REQUIRED for security
```

**Best Practices:**

- ✅ Always use HTTPS via reverse proxy for internet access
- ✅ Set a strong token if binding to 0.0.0.0
- ✅ Use firewall rules to restrict access
- ✅ Consider VPN access for remote management
- ❌ Never expose without authentication to the internet

---

## Themes & Appearance

### Theme Options

The WebUI supports three theme modes:

**Dark Mode (Default)**

- Easy on the eyes for extended monitoring
- Reduced eye strain in low-light environments
- Better for OLED displays

**Light Mode**

- High contrast for bright environments
- Traditional appearance
- Better for daytime use

**Auto Mode**

- Follows system/browser preference
- Automatically switches based on time of day (if system supports)
- Best for users who toggle system themes

### Customization

Theme preference is stored in browser local storage and persists across sessions.

**Manual Theme Toggle:**

Click the sun/moon icon in the top-right corner of the navigation bar.

**Keyboard Shortcut:**

- ++ctrl+shift+t++ - Toggle theme

---

## Performance & Optimization

### Data Refresh Rates

Different components refresh at different intervals:

| Component | Refresh Rate | Configurable |
|-----------|-------------|--------------|
| Process Status | 10 seconds | No |
| Arr Library Views | 30 seconds | No |
| System Metrics | 60 seconds | No |
| Live Logs | Real-time (WebSocket) | No |
| Config Changes | Manual only | N/A |

### Performance Tips

**For Large Libraries (1000+ items):**

- Enable pagination in table settings
- Use search/filter instead of scrolling
- Limit log entries shown (default: 100)

**For Slow Connections:**

- Disable auto-refresh temporarily
- Reduce page size in tables
- Use search to find specific items

**For Low-Resource Systems:**

- Close unused tabs
- Limit concurrent log streams
- Disable live updates when not needed

---

## Mobile & Tablet Support

The WebUI is fully responsive and optimized for all screen sizes.

### Desktop (1200px+)

- Full-width tables with all columns
- Side-by-side layouts
- Keyboard shortcuts enabled
- Multi-column forms

### Tablet (768px - 1199px)

- Adjusted table column widths
- Collapsible sidebars
- Touch-optimized controls
- Two-column forms

### Mobile (< 768px)

- Single-column layouts
- Hamburger menu navigation
- Card-based views (alternative to tables)
- Swipe gestures for navigation
- Bottom navigation bar

### Touch Gestures

- **Swipe Left/Right** - Navigate between tabs
- **Pull to Refresh** - Refresh current view
- **Long Press** - Show context menu
- **Pinch to Zoom** - Zoom tables (where applicable)

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| ++ctrl+slash++ | Show shortcuts help |
| ++1++ - ++7++ | Switch to tab 1-7 |
| ++ctrl+r++ | Refresh current view |
| ++ctrl+f++ | Focus search box |
| ++esc++ | Clear search / Close modals |
| ++ctrl+comma++ | Open settings |
| ++ctrl+shift+d++ | Toggle dark mode |

---

## API Integration

The WebUI is built on qBitrr's REST API. All functionality is accessible programmatically.

### Base URL

```
http://localhost:6969/api
```

### Common Endpoints

```http
GET  /api/processes           # List all processes
POST /api/processes/:name/restart  # Restart process
GET  /api/logs                # Get logs
GET  /api/radarr/movies       # List Radarr movies
GET  /api/sonarr/series       # List Sonarr series
GET  /api/lidarr/albums       # List Lidarr albums
GET  /api/config              # Get configuration
POST /api/config              # Update configuration
GET  /api/health              # Health check
```

### Authentication

Include the token in the header:

```bash
curl http://localhost:6969/api/processes \
  -H "X-API-Token: your-token"
```

### Response Format

All responses are JSON:

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "2025-12-08T12:00:00Z"
}
```

[**Full API Reference →**](api.md)

---

## Troubleshooting

### WebUI Not Loading

**Symptoms:** Can't access WebUI at http://localhost:6969/ui

**Solutions:**

1. **Check qBitrr is running:**

    === "Docker"

        ```bash
        docker ps | grep qbitrr
        # If not running:
        docker-compose up -d qbitrr
        ```

    === "Systemd"

        ```bash
        systemctl status qbitrr
        # If not running:
        sudo systemctl start qbitrr
        ```

    === "Native/pip"

        ```bash
        ps aux | grep qbitrr
        # If not running:
        qbitrr
        ```

2. **Verify port configuration:**

    ```toml
    [WebUI]
    Port = 6969  # Check your config.toml
    Host = "0.0.0.0"  # Or "127.0.0.1"
    ```

3. **Check port mapping (Docker):**

    ```bash
    docker run -p 6969:6969 ...
    # Ensure host port matches container port
    ```

4. **Test port accessibility:**

    ```bash
    # From server
    curl http://localhost:6969/api/health

    # From remote machine
    curl http://SERVER_IP:6969/api/health
    ```

5. **Check firewall rules:**

    ```bash
    # Ubuntu/Debian
    sudo ufw allow 6969
    sudo ufw status

    # CentOS/RHEL
    sudo firewall-cmd --add-port=6969/tcp --permanent
    sudo firewall-cmd --reload
    ```

6. **Check logs for errors:**

    ```bash
    # Docker
    docker logs qbitrr | grep -i webui

    # Native
    tail -f ~/config/logs/WebUI.log
    ```

---

### Authentication Errors

**Symptoms:** API requests return 401 Unauthorized

**Solutions:**

1. **Check if token is configured:**

    ```toml
    [WebUI]
    Token = "your-token-here"  # If set, token is required
    ```

2. **Verify token in requests:**

    ```bash
    # Correct
    curl http://localhost:6969/api/processes \
      -H "X-API-Token: your-token-here"

    # Incorrect (missing header)
    curl http://localhost:6969/api/processes
    ```

3. **Check token hasn't changed:**

    - If you updated the token in config, restart qBitrr
    - Clear browser cache/cookies
    - Re-access the WebUI

4. **Test without token:**

    Temporarily disable token to test:

    ```toml
    [WebUI]
    Token = ""  # Empty = no authentication
    ```

    Restart qBitrr and test. Re-enable token afterward.

---

### Blank Page / White Screen

**Symptoms:** WebUI loads but shows blank/white page

**Solutions:**

1. **Clear browser cache:**

    - ++ctrl+shift+delete++ → Clear cache and reload
    - Or try incognito/private mode

2. **Check browser console for errors:**

    - Open Developer Tools (++f12++)
    - Go to Console tab
    - Look for JavaScript errors

3. **Verify WebUI files exist:**

    ```bash
    # Check static files
    ls -la /path/to/qBitrr/static/
    # Should contain index.html, assets/, etc.
    ```

4. **Try a different browser:**

    - Supported: Chrome, Firefox, Edge, Safari (latest versions)
    - Unsupported: IE11 and older

5. **Check for reverse proxy issues:**

    If using Nginx/Caddy/Traefik, verify:
    - WebSocket support is enabled
    - Headers are properly forwarded
    - No URL rewriting conflicts

---

### Slow Performance / Lag

**Symptoms:** WebUI is slow, unresponsive, or freezes

**Solutions:**

1. **Reduce data load:**

    - **Logs tab:** Limit to 50-100 entries
    - **Arr views:** Use search/filter instead of loading all
    - **Disable auto-refresh:** Manually refresh when needed

2. **Check system resources:**

    ```bash
    # Docker
    docker stats qbitrr

    # Native
    htop
    top -p $(pidof qbitrr)
    ```

3. **Browser performance:**

    - Close unused tabs
    - Disable browser extensions
    - Update to latest browser version
    - Check for high CPU/memory usage

4. **Network latency:**

    ```bash
    # Test API response time
    time curl http://localhost:6969/api/health
    ```

5. **Database size:**

    ```bash
    # Check database size
    ls -lh ~/config/qBitrr.db

    # If over 100MB, consider cleaning old data
    sqlite3 ~/config/qBitrr.db "VACUUM;"
    ```

---

### Real-Time Updates Not Working

**Symptoms:** Logs/data don't update automatically

**Solutions:**

1. **Check WebSocket connection:**

    - Open browser Developer Tools (++f12++)
    - Go to Network tab
    - Filter by "WS" (WebSocket)
    - Should see an active WebSocket connection

2. **Verify reverse proxy supports WebSocket:**

    === "Nginx"

        ```nginx
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        ```

    === "Caddy"

        WebSocket support is automatic in Caddy v2+

    === "Traefik"

        ```yaml
        # No special config needed for WebSocket
        ```

3. **Check firewall/network:**

    - Some corporate firewalls block WebSocket
    - Try accessing from a different network

4. **Manual refresh as fallback:**

    If WebSocket can't be enabled, manually refresh the page

---

### Config Editor Not Saving

**Symptoms:** Changes to config.toml don't persist

**Solutions:**

1. **Check file permissions:**

    ```bash
    # Ensure qBitrr can write to config
    ls -la ~/config/config.toml
    chmod 644 ~/config/config.toml
    ```

2. **Verify config syntax:**

    - Use the built-in validator before saving
    - Look for TOML syntax errors (quotes, brackets, etc.)

3. **Check disk space:**

    ```bash
    df -h /path/to/config
    # Ensure sufficient free space
    ```

4. **Review logs:**

    ```bash
    tail -f ~/config/logs/WebUI.log
    # Look for permission denied or write errors
    ```

5. **Restart required:**

    - Some changes require qBitrr restart
    - Check if "Restart Required" message appears

---

### Connection Status Shows Disconnected

**Symptoms:** Dashboard shows Arr instances as disconnected despite working

**Solutions:**

1. **Test connections manually:**

    ```bash
    # Test Radarr
    curl -H "X-Api-Key: YOUR_KEY" http://localhost:7878/api/v3/system/status

    # Test Sonarr
    curl -H "X-Api-Key: YOUR_KEY" http://localhost:8989/api/v3/system/status
    ```

2. **Check API keys:**

    - Verify API keys are correct in config
    - Ensure no extra spaces or quotes

3. **Verify URIs:**

    ```toml
    [Radarr-Movies]
    URI = "http://localhost:7878"  # Correct
    # NOT: "http://localhost:7878/" (trailing slash)
    # NOT: "localhost:7878" (missing protocol)
    ```

4. **Check network connectivity:**

    - Ensure qBitrr can reach Arr instances
    - Check Docker network (if using containers)

5. **Review Arr logs:**

    - Check Arr instances are running
    - Look for rate limiting or authentication errors

---

### Data Not Updating

**Symptoms:** Movie/series lists show outdated information

**Solutions:**

1. **Force refresh:**

    - Click refresh button in the WebUI
    - Or reload the page (++ctrl+r++)

2. **Check cache settings:**

    - WebUI caches data for 30 seconds by default
    - Wait 30s and refresh

3. **Verify Arr instances are syncing:**

    - Check Arr instance logs
    - Ensure Arr has indexers configured

4. **Clear browser cache:**

    - ++ctrl+shift+delete++
    - Select "Cached images and files"

---

### Mobile Display Issues

**Symptoms:** WebUI looks broken or unresponsive on mobile

**Solutions:**

1. **Update to latest version:**

    - Mobile support improved in recent versions
    - Update qBitrr to latest release

2. **Try landscape mode:**

    - Some views work better in landscape

3. **Use desktop site mode:**

    - In mobile browser, enable "Desktop site"
    - Better for tablets

4. **Check screen size:**

    - Minimum supported width: 320px
    - Some features hidden on very small screens

5. **Report layout issues:**

    - Include device model and browser version
    - Screenshot of the issue

---

## Browser Compatibility

### Supported Browsers

| Browser | Minimum Version | Notes |
|---------|----------------|-------|
| **Chrome** | 90+ | ✅ Fully supported |
| **Firefox** | 88+ | ✅ Fully supported |
| **Edge** | 90+ | ✅ Fully supported (Chromium) |
| **Safari** | 14+ | ✅ Fully supported (macOS/iOS) |
| **Opera** | 76+ | ✅ Supported |
| **Brave** | 1.25+ | ✅ Supported |

### Unsupported Browsers

- ❌ Internet Explorer (all versions)
- ❌ Legacy Edge (pre-Chromium)
- ⚠️ Older mobile browsers (Android < 7, iOS < 14)

### Required Browser Features

- ES6 JavaScript support
- WebSocket support (for real-time updates)
- LocalStorage (for preferences)
- Flexbox and CSS Grid
- SVG support

---

## Advanced Usage

### Custom Reverse Proxy Headers

When using a reverse proxy, configure these headers for optimal experience:

```nginx
# Nginx example
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host $host;
proxy_set_header X-Forwarded-Port $server_port;

# WebSocket support
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

### CORS Configuration

If accessing WebUI from a different domain:

```toml
[WebUI]
# Allow specific origins (comma-separated)
CORSOrigins = "https://myapp.com,https://admin.myapp.com"

# Or allow all (not recommended for production)
CORSOrigins = "*"
```

### Rate Limiting

Protect against abuse with built-in rate limiting:

```toml
[WebUI]
# Max requests per minute per IP
RateLimit = 60

# Burst allowance
RateLimitBurst = 10
```

---

## Accessibility

### Keyboard Navigation

The WebUI supports full keyboard navigation:

- ++tab++ - Navigate between interactive elements
- ++shift+tab++ - Navigate backwards
- ++enter++ - Activate buttons/links
- ++space++ - Toggle checkboxes
- ++arrow-keys++ - Navigate within tables/lists
- ++esc++ - Close modals/dialogs

### Screen Reader Support

- ARIA labels on all interactive elements
- Semantic HTML structure
- Skip navigation links
- Alt text on images/icons
- Descriptive button labels

### Visual Accessibility

- High contrast mode compatible
- Minimum 4.5:1 contrast ratio (WCAG AA)
- No color-only information
- Resizable text (up to 200%)
- Focus indicators on all interactive elements

---

## Future Features

Planned WebUI enhancements:

### Coming in Next Release

- ✅ **Interactive Configuration Wizard** - Step-by-step setup for first-time users
- ✅ **Torrent Management Interface** - View and control torrents directly
- ✅ **Search Triggering** - Manually trigger searches from WebUI

### Under Development

- ⚙️ **Real-time Notifications** - Toast notifications for imports, errors, etc.
- ⚙️ **Multi-language Support** - i18n for multiple languages
- ⚙️ **Custom Dashboard Layouts** - Drag-and-drop widget customization
- ⚙️ **Dark/Light Theme Per-Section** - Mixed themes

### Planned Features

- 📅 **Calendar View** - Visual calendar for upcoming releases
- 📊 **Advanced Statistics** - Charts and graphs for download trends
- 🔔 **Alert Configuration** - Set up custom alerts for events
- 📱 **Progressive Web App** - Install as native app
- 🎨 **Theme Customization** - Custom color schemes
- 📤 **Export Reports** - Generate PDF/CSV reports

**Want to contribute?** Check out the [Development Guide](../development/index.md)!

---

## Development & Technical Details

### Technology Stack

#### Frontend

- **React 18.2** - UI framework with concurrent rendering
- **TypeScript 5.3** - Type-safe JavaScript
- **Mantine UI 7.x** - Component library and design system
- **Vite 5.x** - Build tool and dev server
- **TanStack Table v8** - Powerful data tables
- **React Query** - Data fetching and caching
- **React Router v6** - Client-side routing

#### Backend (API)

- **Flask 3.x** - Lightweight web framework
- **Waitress** - Production WSGI server
- **Flask-CORS** - Cross-Origin Resource Sharing
- **Peewee** - ORM for database access

### Project Structure

```
webui/
├── src/
│   ├── api/              # API client functions
│   ├── components/       # React components
│   ├── context/          # React context providers
│   ├── hooks/            # Custom React hooks
│   ├── pages/            # Page components (routes)
│   ├── utils/            # Utility functions
│   ├── App.tsx           # Root component
│   ├── main.tsx          # Entry point
│   └── styles.css        # Global styles
├── public/               # Static assets
├── dist/                 # Build output
├── package.json          # Dependencies
├── tsconfig.json         # TypeScript config
└── vite.config.ts        # Vite build config
```

### Local Development

```bash
# Navigate to WebUI directory
cd webui

# Install dependencies
npm ci

# Start development server
npm run dev
# WebUI will be at http://localhost:5173

# Build for production
npm run build

# Preview production build
npm run preview
```

### API Endpoints Used

The WebUI communicates with these qBitrr API endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/processes` | GET | List processes |
| `/api/processes/:name/restart` | POST | Restart process |
| `/api/logs` | GET | Fetch logs |
| `/api/logs/stream` | WebSocket | Stream logs |
| `/api/radarr/movies` | GET | List movies |
| `/api/sonarr/series` | GET | List series |
| `/api/lidarr/albums` | GET | List albums |
| `/api/config` | GET | Get config |
| `/api/config` | POST | Update config |
| `/api/qbittorrent/torrents` | GET | List torrents |

[**Full API Documentation →**](api.md)

---

## Related Documentation

### Configuration

- [WebUI Configuration](../configuration/webui.md) - Detailed WebUI settings
- [Configuration File](../configuration/config-file.md) - Complete config reference
- [Environment Variables](../configuration/environment.md) - WebUI env vars

### Features

- [Process Management](../features/process-management.md) - Managing Arr processes
- [Health Monitoring](../features/health-monitoring.md) - Torrent health checks
- [Automated Search](../features/automated-search.md) - Search automation

### Reference

- [API Reference](api.md) - Complete API documentation
- [CLI Reference](../reference/cli.md) - Command-line options
- [Glossary](../reference/glossary.md) - Terms and definitions

### Support

- [Troubleshooting](../troubleshooting/index.md) - General troubleshooting
- [Common Issues](../troubleshooting/common-issues.md) - Known problems
- [FAQ](../faq.md) - Frequently asked questions

---

## Getting Help

### Community Support

- **GitHub Discussions** - [Ask questions, share tips](https://github.com/Feramance/qBitrr/discussions)
- **GitHub Issues** - [Report bugs, request features](https://github.com/Feramance/qBitrr/issues)
- **Discord** - Real-time community chat

### Bug Reports

When reporting WebUI issues, include:

1. **Browser & Version** - e.g., Chrome 120, Firefox 121
2. **Operating System** - e.g., Windows 11, macOS 14, Ubuntu 22.04
3. **qBitrr Version** - Found in WebUI header
4. **Console Errors** - From browser Developer Tools (++f12++)
5. **Steps to Reproduce** - How to trigger the issue
6. **Screenshots** - Visual representation helps

### Feature Requests

Have an idea for the WebUI? [Open a discussion](https://github.com/Feramance/qBitrr/discussions/categories/ideas) with:

- **Use Case** - Why is this feature needed?
- **Proposed Solution** - How should it work?
- **Alternatives** - Other ways to achieve the same goal

---

## Credits

The qBitrr WebUI is built and maintained by the qBitrr development team with contributions from the community.

**Technologies:**

- [React](https://react.dev/) - UI framework
- [Mantine](https://mantine.dev/) - Component library
- [Vite](https://vitejs.dev/) - Build tool
- [TanStack Table](https://tanstack.com/table) - Data tables

**Special Thanks:**

- Contributors who provided feedback and bug reports
- The Arr community for feature suggestions
- Open source maintainers of the libraries we use

Want to contribute? See the [Development Guide](../development/index.md)!
