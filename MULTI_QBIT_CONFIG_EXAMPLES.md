# Multi-qBittorrent Configuration Examples

## Notation Convention

All additional qBittorrent instances use **dash notation** (`-`) instead of dot notation (`.`) to avoid TOML nested table confusion.

### Section Naming

```toml
[qBit]              # Primary instance (always named "qBit")
[qBit-Seedbox]      # Additional instance (dash, not dot)
[qBit-Private]      # Another additional instance
[qBit-Backup]       # Yet another instance
```

### Instance Referencing

In Arr configurations, reference the instance name **without** the `qBit-` prefix:

```toml
[Radarr-Movies]
qBitInstance = "default"    # References [qBit]

[Radarr-4K]
qBitInstance = "Seedbox"    # References [qBit-Seedbox]

[Sonarr-Anime]
qBitInstance = "Private"    # References [qBit-Private]
```

---

## Example 1: Single Instance (Backward Compatible)

```toml
[Settings]
ConfigVersion = 4
CompletedDownloadFolder = "/downloads"
# ... other settings ...

[WebUI]
Host = "0.0.0.0"
Port = 6969

[qBit]
Disabled = false
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "adminpass"

[Radarr-Movies]
Managed = true
URI = "http://localhost:7878"
APIKey = "abc123..."
Category = "radarr"
# qBitInstance = "default"  # Optional - defaults to "default"

[Sonarr-TV]
Managed = true
URI = "http://localhost:8989"
APIKey = "def456..."
Category = "sonarr"
# qBitInstance = "default"  # Optional - defaults to "default"
```

---

## Example 2: Local + Remote Seedbox

```toml
[Settings]
ConfigVersion = 4
CompletedDownloadFolder = "/downloads"
# ... other settings ...

[WebUI]
Host = "0.0.0.0"
Port = 6969

# Local qBittorrent for standard downloads
[qBit]
Disabled = false
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "localpass"

# Remote seedbox for 4K content
[qBit-Seedbox]
Host = "seedbox.example.com"
Port = 8080
UserName = "seedbox_user"
Password = "seedbox_pass"

# 1080p content on local qBit
[Radarr-Movies]
Managed = true
URI = "http://localhost:7878"
APIKey = "radarr_api_key"
Category = "radarr-1080p"
qBitInstance = "default"

# 4K content on seedbox (faster downloads)
[Radarr-4K]
Managed = true
URI = "http://localhost:7879"
APIKey = "radarr4k_api_key"
Category = "radarr-4k"
qBitInstance = "Seedbox"

# TV shows on local qBit
[Sonarr-TV]
Managed = true
URI = "http://localhost:8989"
APIKey = "sonarr_api_key"
Category = "sonarr"
qBitInstance = "default"
```

---

## Example 3: Public vs Private Trackers

```toml
[Settings]
ConfigVersion = 4
CompletedDownloadFolder = "/downloads"
# ... other settings ...

[WebUI]
Host = "0.0.0.0"
Port = 6969

# Public tracker qBittorrent
[qBit]
Disabled = false
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "public_pass"

# Private tracker qBittorrent (separate for ratio management)
[qBit-Private]
Host = "localhost"
Port = 8090
UserName = "admin"
Password = "private_pass"

# Public tracker movies
[Radarr-Public]
Managed = true
URI = "http://localhost:7878"
APIKey = "radarr_api_key"
Category = "radarr-public"
qBitInstance = "default"

# Private tracker movies
[Radarr-Private]
Managed = true
URI = "http://localhost:7879"
APIKey = "radarr_private_api_key"
Category = "radarr-private"
qBitInstance = "Private"

# Anime from private trackers
[Sonarr-Anime]
Managed = true
URI = "http://localhost:8990"
APIKey = "sonarr_anime_api_key"
Category = "sonarr-anime"
qBitInstance = "Private"
```

---

## Example 4: Three Instances (Complex Setup)

```toml
[Settings]
ConfigVersion = 4
CompletedDownloadFolder = "/downloads"
# ... other settings ...

[WebUI]
Host = "0.0.0.0"
Port = 6969

# Primary local instance
[qBit]
Disabled = false
Host = "localhost"
Port = 8080
UserName = "admin"
Password = "local_pass"

# Dedicated 4K seedbox
[qBit-Seedbox4K]
Host = "seedbox-4k.example.com"
Port = 8080
UserName = "seedbox_user"
Password = "seedbox_4k_pass"

# Private tracker optimized instance
[qBit-Private]
Host = "192.168.1.100"
Port = 8090
UserName = "admin"
Password = "private_pass"

# Standard movies on local
[Radarr-Movies]
Managed = true
URI = "http://localhost:7878"
APIKey = "radarr_api_key"
Category = "radarr-1080p"
qBitInstance = "default"

# 4K movies on seedbox
[Radarr-4K]
Managed = true
URI = "http://localhost:7879"
APIKey = "radarr_4k_api_key"
Category = "radarr-4k"
qBitInstance = "Seedbox4K"

# TV shows on local
[Sonarr-TV]
Managed = true
URI = "http://localhost:8989"
APIKey = "sonarr_api_key"
Category = "sonarr-tv"
qBitInstance = "default"

# Anime from private trackers
[Sonarr-Anime]
Managed = true
URI = "http://localhost:8990"
APIKey = "sonarr_anime_api_key"
Category = "sonarr-anime"
qBitInstance = "Private"

# Music on local
[Lidarr-Music]
Managed = true
URI = "http://localhost:8686"
APIKey = "lidarr_api_key"
Category = "lidarr"
qBitInstance = "default"
```

---

## Example 5: Docker Environment Variables

When using Docker, you can configure additional instances via environment variables:

```yaml
version: '3.8'

services:
  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    environment:
      # Primary instance
      - QBITRR_QBIT_HOST=qbittorrent
      - QBITRR_QBIT_PORT=8080
      - QBITRR_QBIT_USERNAME=admin
      - QBITRR_QBIT_PASSWORD=adminpass

      # Additional instance (seedbox)
      # Note: Env var uses underscore, creates [qBit-Seedbox] section
      - QBITRR_QBIT_SEEDBOX_HOST=seedbox.example.com
      - QBITRR_QBIT_SEEDBOX_PORT=8080
      - QBITRR_QBIT_SEEDBOX_USERNAME=seedbox_user
      - QBITRR_QBIT_SEEDBOX_PASSWORD=seedbox_pass
    volumes:
      - ./config:/config
      - /downloads:/downloads
    ports:
      - "6969:6969"
    restart: unless-stopped
```

Then in your `config.toml`, reference the instance:

```toml
[Radarr-4K]
qBitInstance = "Seedbox"  # References env vars QBITRR_QBIT_SEEDBOX_*
```

---

## Validation

After configuring multiple instances, verify your setup:

1. **Check config syntax**:
   ```bash
   qbitrr --gen-config  # Generates example to compare
   ```

2. **Start qBitrr and check logs**:
   ```bash
   qbitrr
   # Look for:
   # "Initialized qBit instance 'Seedbox' at seedbox.example.com:8080"
   # "Radarr-4K will use qBittorrent instance: Seedbox"
   ```

3. **Check WebUI**:
   - Navigate to http://localhost:6969
   - Go to "qBittorrent" tab
   - Verify all instances show as "Connected"

---

## Common Mistakes

### ❌ Wrong: Using dot notation
```toml
[qBit.Seedbox]  # Creates nested table - WRONG!
```

### ✅ Correct: Using dash notation
```toml
[qBit-Seedbox]  # Flat section name - CORRECT!
```

### ❌ Wrong: Including qBit- prefix in reference
```toml
[Radarr-4K]
qBitInstance = "qBit-Seedbox"  # WRONG!
```

### ✅ Correct: Using instance name only
```toml
[Radarr-4K]
qBitInstance = "Seedbox"  # CORRECT!
```

### ❌ Wrong: Referencing non-existent instance
```toml
[Radarr-4K]
qBitInstance = "NonExistent"  # No [qBit-NonExistent] section - WRONG!
```

### ✅ Correct: Referencing existing section
```toml
[qBit-Seedbox]
Host = "..."

[Radarr-4K]
qBitInstance = "Seedbox"  # Matches [qBit-Seedbox] - CORRECT!
```

---

## Quick Reference

| What You Want | Section Name | Reference In Arr |
|---------------|--------------|------------------|
| Primary instance | `[qBit]` | `qBitInstance = "default"` (or omit) |
| Seedbox instance | `[qBit-Seedbox]` | `qBitInstance = "Seedbox"` |
| Private tracker | `[qBit-Private]` | `qBitInstance = "Private"` |
| Backup instance | `[qBit-Backup]` | `qBitInstance = "Backup"` |
| Custom name | `[qBit-YourName]` | `qBitInstance = "YourName"` |

**Rule**: Section name = `qBit-` + instance name, reference = instance name only
