# Multi-qBittorrent v3.0 - User Guide

## 🎉 Overview

qBitrr now supports **multiple qBittorrent instances simultaneously**! Each Arr instance (Radarr/Sonarr/Lidarr) can monitor torrents across all your qBittorrent instances.

### What's New in v3.0

- ✅ **Equal Multi-Instance Monitoring**: All Arr instances monitor ALL qBit instances
- ✅ **Category-Based Management**: Torrents are managed based on their category, not their instance
- ✅ **Instance Health Monitoring**: Track the health status of each qBittorrent instance
- ✅ **Backward Compatible**: Existing single-instance configs work without changes
- ✅ **WebUI Support**: View, configure, add, and delete instances directly from the web interface

### Architecture

**Design Philosophy**: Each Arr instance monitors ALL qBittorrent instances. Categories determine torrent ownership, not the instance location.

**Example**:
- Radarr downloads can land on ANY qBit instance
- Radarr monitors ALL instances for torrents in its category (`radarr-movies`)
- If a Radarr torrent appears on instance "default" or "seedbox", Radarr manages it

---

## 📋 Configuration

### Single Instance (Default)

Existing configs continue to work without any changes:

```toml
[Settings]
ConfigVersion = 3

[qBit]
Host = "localhost"
Port = 8080
Username = "admin"
Password = "adminpass"

[Radarr]
URI = "http://localhost:7878"
APIKey = "your-api-key"
Category = "radarr-movies"
```

### Multiple Instances

Add additional qBittorrent instances using the `[qBit-NAME]` syntax:

```toml
[Settings]
ConfigVersion = 3

# Default instance (required)
[qBit]
Host = "localhost"
Port = 8080
Username = "admin"
Password = "adminpass"

# Additional instance #1
[qBit-seedbox]
Host = "192.168.1.100"
Port = 8080
Username = "admin"
Password = "seedboxpass"

# Additional instance #2
[qBit-remote]
Host = "remote.example.com"
Port = 8443
Username = "admin"
Password = "remotepass"

[Radarr]
URI = "http://localhost:7878"
APIKey = "your-api-key"
Category = "radarr-movies"  # Monitors this category on ALL instances

[Sonarr]
URI = "http://localhost:8989"
APIKey = "your-api-key"
Category = "sonarr-tv"  # Monitors this category on ALL instances
```

---

## 🔧 Configuration Syntax

### Instance Naming Rules

1. **Default instance**: Always named `[qBit]` (required)
2. **Additional instances**: Named `[qBit-NAME]` where NAME is your custom identifier
   - ✅ Correct: `[qBit-seedbox]`, `[qBit-remote]`, `[qBit-local]`
   - ❌ Wrong: `[qBit.seedbox]`, `[Seedbox]`, `[qbit-seedbox]`

### Instance Configuration Fields

Each `[qBit-*]` section supports all standard qBittorrent settings:

```toml
[qBit-example]
Host = "hostname"           # Required
Port = 8080                 # Required
Username = "admin"          # Optional
Password = "password"       # Optional
Version5 = true             # Optional (for qBit 5.x+)
```

### Arr Configuration (Unchanged)

Arr instances do NOT need to specify which qBit instance to use - they monitor ALL instances automatically:

```toml
[Radarr]
URI = "http://localhost:7878"
APIKey = "api-key"
Category = "radarr-movies"  # This category is monitored across ALL qBit instances
```

---

## 🌟 Usage Examples

### Example 1: Home + Seedbox Setup

**Use Case**: Local qBittorrent for fast downloads, remote seedbox for long-term seeding

```toml
[qBit]
Host = "localhost"
Port = 8080
Username = "admin"
Password = "adminpass"

[qBit-seedbox]
Host = "seedbox.example.com"
Port = 8080
Username = "admin"
Password = "seedboxpass"

[Radarr]
URI = "http://localhost:7878"
APIKey = "radarr-key"
Category = "radarr-movies"
```

**How it works**:
- Radarr can send downloads to either `default` or `seedbox` instance
- qBitrr monitors BOTH instances for `radarr-movies` category
- Health checks and imports work across both instances

### Example 2: Multiple VPN Endpoints

**Use Case**: Different qBittorrent instances behind different VPN endpoints

```toml
[qBit]  # US VPN
Host = "10.8.0.2"
Port = 8080

[qBit-eu]  # EU VPN
Host = "10.8.0.3"
Port = 8080

[qBit-asia]  # Asia VPN
Host = "10.8.0.4"
Port = 8080

[Sonarr]
URI = "http://localhost:8989"
APIKey = "sonarr-key"
Category = "sonarr-tv"
```

**How it works**:
- Sonarr can send downloads to any VPN endpoint
- qBitrr monitors ALL three instances simultaneously
- If one VPN goes down, torrents on other instances continue processing

### Example 3: Separate Instances for Different Quality Profiles

**Use Case**: 4K movies on high-bandwidth server, 1080p on local machine

```toml
[qBit]  # Local - 1080p
Host = "localhost"
Port = 8080

[qBit-4k]  # Remote - 4K
Host = "192.168.1.100"
Port = 8080

[Radarr]
URI = "http://localhost:7878"
APIKey = "radarr-key"
Category = "radarr-movies"

[Radarr-4K]
URI = "http://localhost:7879"
APIKey = "radarr-4k-key"
Category = "radarr-4k"
```

**How it works**:
- Both Radarr instances monitor BOTH qBittorrent instances
- Category determines which Radarr manages which torrent
- Torrents can be on any instance regardless of quality

### Example 4: Docker Multi-Container Setup

**Use Case**: Multiple qBittorrent containers for isolation

```toml
[qBit]
Host = "qbittorrent-main"  # Docker service name
Port = 8080

[qBit-public]
Host = "qbittorrent-public"
Port = 8080

[qBit-private]
Host = "qbittorrent-private"
Port = 8080

[Radarr]
URI = "http://radarr:7878"
APIKey = "radarr-key"
Category = "radarr-movies"

[Sonarr]
URI = "http://sonarr:8989"
APIKey = "sonarr-key"
Category = "sonarr-tv"
```

**Docker Compose snippet**:
```yaml
services:
  qbitrr:
    image: feramance/qbitrr:latest
    depends_on:
      - qbittorrent-main
      - qbittorrent-public
      - qbittorrent-private
      - radarr
      - sonarr
```

---

## 🔍 WebUI Support

### Configuration Management

The qBitrr WebUI provides a user-friendly interface for managing multiple qBittorrent instances:

**Features**:
- ✅ **View all instances**: See all configured qBit instances with their status, host, and version
- ✅ **Add instances**: Click "Add Instance" to create new qBittorrent connections
- ✅ **Configure instances**: Edit host, port, credentials, and version settings
- ✅ **Delete instances**: Remove secondary instances (default instance cannot be deleted)
- ✅ **Rename instances**: Change instance names while preserving configuration
- ✅ **Real-time validation**: Form validation ensures configuration correctness

**Accessing the Config Editor**:
1. Navigate to `http://your-qbitrr-host:6969/ui`
2. Click on "Config" in the navigation
3. Scroll to "qBittorrent Instances" section
4. Use "Add Instance", "Configure", or "Delete" buttons to manage instances

**Instance Cards**:
Each instance card displays:
- Instance name (e.g., "qBit", "qBit-seedbox")
- Status: Enabled/Disabled
- Host and port (e.g., "192.168.1.100:8080")
- qBittorrent version (v4.x or v5.x+)

**Adding a New Instance**:
1. Click "Add Instance" button
2. Configure the instance:
   - **Display Name**: Rename from default "qBit-1" to your custom name (e.g., "qBit-seedbox")
   - **Host**: qBittorrent WebUI host or IP
   - **Port**: qBittorrent WebUI port
   - **Username**: Optional authentication username
   - **Password**: Optional authentication password
   - **Version 5**: Check if using qBittorrent v5.x or later
   - **Disabled**: Check to temporarily disable this instance
3. Click "Done" to save

**Best Practices**:
- Use descriptive instance names (e.g., `qBit-seedbox`, `qBit-vpn`, `qBit-local`)
- Test connectivity by checking the status indicators after saving
- Enable "Version 5" checkbox for qBittorrent 5.x+ to ensure API compatibility
- Use "Disabled" checkbox to temporarily disable instances without deleting configuration

### Status Endpoint

**Endpoint**: `GET /api/status`

**Response** (v3.0+):
```json
{
  "qbit": {
    "alive": true,
    "host": "localhost",
    "port": 8080,
    "version": "4.6.0"
  },
  "qbitInstances": {
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
    "remote": {
      "alive": false,
      "host": "remote.example.com",
      "port": 8443,
      "version": null,
      "error": "Connection timeout"
    }
  },
  "arrs": [...],
  "ready": true
}
```

### Torrent Distribution Endpoint

**Endpoint**: `GET /api/torrents/distribution`

**Response**:
```json
{
  "distribution": {
    "radarr-movies": {
      "default": 25,
      "seedbox": 43,
      "remote": 0
    },
    "sonarr-tv": {
      "default": 15,
      "seedbox": 67,
      "remote": 12
    }
  }
}
```

---

## ⚠️ Important Notes

### Database Recreation

- **No migration required**: The database is automatically recreated on restart/update
- **Existing torrents**: Will be re-scanned and tracked with instance information
- **Backup**: Not required, but recommended before major updates

### Category Requirements

- **Categories must exist on ALL instances**: qBitrr automatically creates categories on all instances during startup
- **Case sensitive**: `radarr-movies` ≠ `Radarr-Movies`
- **No special characters**: Stick to `a-z`, `0-9`, `-`, `_`

### Instance Health

- **Offline instances**: qBitrr continues processing torrents on healthy instances
- **Health checks**: Run automatically every loop iteration
- **Error handling**: Transient errors (network blips) are retried, persistent errors are logged

### Backward Compatibility

- **Single-instance configs**: Work without ANY changes
- **Default instance**: Always named "default" internally
- **API compatibility**: WebUI maintains legacy `qbit` field for backward compatibility

---

## 🐛 Troubleshooting

### Issue: Instance not detected

**Symptoms**: Only `default` instance appears in status

**Solutions**:
1. Check section name: Must be `[qBit-NAME]` (dash, not dot)
2. Verify connectivity: `curl http://HOST:PORT/api/v2/app/version`
3. Check credentials: Username/password must be correct
4. Review logs: Look for "Failed to initialize instance" messages

### Issue: Torrents not processing on secondary instance

**Symptoms**: Torrents stuck on `seedbox` instance but processed on `default`

**Solutions**:
1. Verify category exists: Check qBit web UI → Categories
2. Check category spelling: Must match exactly (case-sensitive)
3. Verify Arr tags: Torrents must have appropriate tags for Arr tracking
4. Check instance health: Ensure instance is marked as "alive" in status endpoint

### Issue: Category creation fails

**Symptoms**: "Failed to create category on instance X" in logs

**Solutions**:
1. Check qBit permissions: User must have category creation rights
2. Verify qBit version: Some versions have category API bugs
3. Manual creation: Create category manually in qBit web UI
4. Check save paths: qBit must have write access to category save paths

### Issue: Database errors after upgrade

**Symptoms**: "no such column: QbitInstance" errors

**Solutions**:
1. **Stop qBitrr completely**
2. Delete database: `rm ~/config/qBitManager.db` (or `/config/qBitManager.db` in Docker)
3. Restart qBitrr: Database will be recreated automatically
4. Wait for re-scan: All torrents will be re-scanned and tracked

---

## 📊 Performance Considerations

### Scanning Overhead

- **Per-instance overhead**: ~50-200ms per instance per scan loop
- **Recommended max instances**: 5-7 instances
- **Loop timer adjustment**: Increase `LoopSleepTimer` if managing many instances

### Network Considerations

- **API calls**: Each scan loop makes N API calls per Arr (where N = number of instances)
- **Bandwidth**: Minimal (<1KB per API call)
- **Latency**: High-latency instances (>500ms) will slow down processing

### Database Size

- **Growth rate**: ~1KB per torrent per instance
- **Compound index**: Queries remain fast even with 10,000+ torrents across multiple instances

---

## 🚀 Best Practices

### 1. Instance Naming

Use descriptive names that reflect purpose or location:
- ✅ `[qBit-seedbox]`, `[qBit-vpn-us]`, `[qBit-4k]`
- ❌ `[qBit-1]`, `[qBit-a]`, `[qBit-test]`

### 2. Category Consistency

Use the same category naming scheme across all Arr instances:
- ✅ `radarr-movies`, `radarr-4k`, `sonarr-tv`, `sonarr-anime`
- ❌ `movies`, `4K`, `TV`, `Anime`

### 3. Health Monitoring

Monitor instance health via WebUI or `/api/status` endpoint:
- Set up alerts for instance failures
- Review health trends to identify unreliable instances

### 4. Loop Timer Tuning

Adjust based on instance count and responsiveness:
```toml
[Settings]
LoopSleepTimer = 5   # Default: 5 seconds (good for 1-3 instances)
LoopSleepTimer = 10  # Increase for 4-5 instances
LoopSleepTimer = 15  # Increase for 6+ instances or high-latency instances
```

### 5. Testing New Instances

Before adding to production:
1. Test connectivity manually
2. Create test category
3. Add single test torrent
4. Verify qBitrr detects and processes it
5. Remove test torrent and category
6. Add to production config

---

## 📚 Migration Guide

### From Single-Instance to Multi-Instance

**Step 1**: Backup current config
```bash
cp ~/config/config.toml ~/config/config.toml.backup
```

**Step 2**: Add new instance sections
```toml
[qBit-seedbox]
Host = "192.168.1.100"
Port = 8080
Username = "admin"
Password = "password"
```

**Step 3**: Restart qBitrr
```bash
systemctl restart qbitrr  # Systemd
# OR
docker restart qbitrr     # Docker
```

**Step 4**: Verify instances detected
```bash
curl http://localhost:6969/api/status | jq '.qbitInstances'
```

**Step 5**: Monitor logs for errors
```bash
tail -f ~/logs/Main.log
```

### Rolling Back

If you encounter issues:

**Step 1**: Stop qBitrr
```bash
systemctl stop qbitrr  # OR docker stop qbitrr
```

**Step 2**: Restore backup config
```bash
cp ~/config/config.toml.backup ~/config/config.toml
```

**Step 3**: Delete database (forces recreation)
```bash
rm ~/config/qBitManager.db
```

**Step 4**: Restart qBitrr
```bash
systemctl start qbitrr  # OR docker start qbitrr
```

---

## 🎯 FAQ

### Q: Do I need to configure which instance each Arr uses?

**A**: No! Each Arr monitors ALL instances automatically. Torrents are identified by category, not instance.

### Q: Can I use different credentials for each instance?

**A**: Yes! Each `[qBit-*]` section has its own `Username` and `Password` fields.

### Q: What happens if one instance goes offline?

**A**: qBitrr continues processing torrents on healthy instances. Offline instances are skipped until they come back online.

### Q: Can I have different categories on different instances?

**A**: Yes, but it's recommended to keep categories consistent. qBitrr creates all Arr categories on all instances automatically.

### Q: Does this work with qBittorrent 5.x?

**A**: Yes! Set `Version5 = true` in the instance configuration.

### Q: How many instances can I have?

**A**: Tested up to 7 instances. Performance may degrade beyond that depending on hardware and network latency.

### Q: Will this break my existing setup?

**A**: No! Existing single-instance configs work without any changes. Multi-instance is purely additive.

### Q: Do I need to migrate my database?

**A**: No! Databases are automatically recreated on restart/update.

---

## 📞 Support

### Documentation
- **Main README**: [Home](../index.md)
- **API Documentation**: [API Reference](../reference/api.md)
- **Implementation Progress**: [GitHub Repository](https://github.com/Feramance/qBitrr/blob/feature/multi-qbit-v3/IMPLEMENTATION_PROGRESS.md)

### Getting Help
- **GitHub Issues**: https://github.com/Feramance/qBitrr/issues
- **Discord**: Join the Arr community Discord

### Reporting Bugs
When reporting multi-instance issues, include:
1. Full config (redact passwords!)
2. Logs from `~/logs/Main.log`
3. Output of `/api/status` endpoint
4. qBittorrent versions for all instances

---

**Version**: Multi-qBittorrent v3.0
**Last Updated**: 2025-12-18
**Status**: ✅ Production Ready
