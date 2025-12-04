# Path Mapping Troubleshooting

This guide covers path mapping issues between qBittorrent, Arr instances (Radarr/Sonarr/Lidarr), and qBitrr, focusing on Docker volume mapping and file accessibility.

## Overview

Path mapping is one of the most common sources of confusion and errors in qBitrr deployments. When qBittorrent, Arr instances, and qBitrr run in separate containers (or a mix of containers and host installs), they each see the file system differently.

!!! danger "Critical Concept"
    **All containers must see the same physical files at the same path.**

    If qBittorrent saves a file to `/downloads/Movie.mkv` (inside its container), but Radarr expects to find it at `/data/media/Movie.mkv` (inside its container), imports will fail even though both paths point to the same physical file on your host.

---

## Path Mapping Basics

### The Problem

Consider this common misconfiguration:

```yaml
# ❌ WRONG: Inconsistent paths across containers
services:
  qbittorrent:
    volumes:
      - /mnt/storage/torrents:/downloads

  radarr:
    volumes:
      - /mnt/storage/torrents:/data/torrents

  qbitrr:
    volumes:
      - /mnt/storage/torrents:/completed
```

**What happens:**

1. Radarr tells qBittorrent: "Download this movie to `/data/torrents/Movie (2024)/`"
2. qBittorrent doesn't recognize `/data/torrents` (it only knows about `/downloads`)
3. Download fails or gets saved to wrong location
4. qBitrr can't find the file at `/completed` when it tries to verify
5. Import never happens

### The Solution

```yaml
# ✅ CORRECT: Consistent paths across all containers
services:
  qbittorrent:
    volumes:
      - /mnt/storage/torrents:/data/torrents

  radarr:
    volumes:
      - /mnt/storage/torrents:/data/torrents

  sonarr:
    volumes:
      - /mnt/storage/torrents:/data/torrents

  qbitrr:
    volumes:
      - /mnt/storage/torrents:/data/torrents
```

**Key principle:** Use the **same container path** (`/data/torrents`) across all services.

---

## Docker Volume Mapping

### Volume Syntax

```yaml
volumes:
  - <host_path>:<container_path>:<options>
```

- **host_path**: Physical directory on your server
- **container_path**: Path inside the container
- **options**: `ro` (read-only), `rw` (read-write, default)

### Common Patterns

#### Single Root Mount (Recommended)

```yaml
# Map entire storage tree to all containers
services:
  qbittorrent:
    volumes:
      - /mnt/storage:/data

  radarr:
    volumes:
      - /mnt/storage:/data

  sonarr:
    volumes:
      - /mnt/storage:/data

  qbitrr:
    volumes:
      - /mnt/storage:/data
```

**Benefits:**

- ✅ Simplest to configure
- ✅ No path translation needed
- ✅ Easy to troubleshoot
- ✅ Atomic moves work (instant imports)

**Directory structure:**

```
/mnt/storage/           (host)
├── torrents/           → /data/torrents (all containers)
├── movies/             → /data/movies
├── tv/                 → /data/tv
└── music/              → /data/music
```

#### Multiple Mount Points (Advanced)

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/storage/torrents:/data/torrents
      - /mnt/storage/movies:/data/movies
      - /mnt/storage/tv:/data/tv

  radarr:
    volumes:
      - /mnt/storage/torrents:/data/torrents
      - /mnt/storage/movies:/data/movies

  sonarr:
    volumes:
      - /mnt/storage/torrents:/data/torrents
      - /mnt/storage/tv:/data/tv

  qbitrr:
    volumes:
      - /mnt/storage/torrents:/data/torrents
```

**When to use:**

- Different physical disks for torrents vs. media
- NFS/network mounts with different mount points
- Quota/permission requirements per directory

---

## Arr Configuration

### Download Client Settings

In Radarr/Sonarr/Lidarr, configure qBittorrent download client:

**Settings → Download Clients → Add → qBittorrent**

```
Host: qbittorrent
Port: 8080
Username: admin
Password: ********
Category: radarr-movies
```

**Important: Remote Path Mappings**

If you **must** use different paths (not recommended), configure remote path mappings:

**Settings → Download Clients → Remote Path Mappings**

```
Host: qbittorrent
Remote Path: /downloads/
Local Path: /data/torrents/
```

This tells Radarr: "When qBittorrent says `/downloads/Movie.mkv`, I can find it at `/data/torrents/Movie.mkv`"

!!! warning "Avoid Remote Path Mappings"
    Remote path mappings add complexity and are prone to errors. Use consistent paths instead.

### Root Folders

**Settings → Media Management → Root Folders**

Radarr example:

```
/data/movies
```

Sonarr example:

```
/data/tv
```

Lidarr example:

```
/data/music
```

These paths must exist inside the container and be writable.

---

## qBitrr Configuration

### CompletedDownloadFolder

In `config.toml`, set the path where qBittorrent saves completed downloads **as seen by qBitrr's container**:

```toml
[Settings]
CompletedDownloadFolder = "/data/torrents"
```

**How qBitrr uses this:**

1. Monitors this folder for new files
2. Triggers FFprobe verification on files in this path
3. Sends scan commands to Arr instances with paths relative to this folder

### Category-Specific Paths

qBittorrent can save different categories to different paths:

**qBittorrent WebUI → Options → Downloads → Saving Management**

```
Default Save Path: /data/torrents

Category Paths:
  radarr-movies    → /data/torrents/movies
  sonarr-tv        → /data/torrents/tv
  lidarr-music     → /data/torrents/music
```

**Matching qBitrr config:**

```toml
[Radarr-Movies]
Category = "radarr-movies"

[Sonarr-TV]
Category = "sonarr-tv"

[Lidarr-Music]
Category = "lidarr-music"

[Settings]
CompletedDownloadFolder = "/data/torrents"
```

qBitrr automatically detects category-specific save paths from qBittorrent's API.

---

## Common Path Mapping Scenarios

### Scenario 1: All Containers on Same Host

**Setup:**

- qBittorrent, Radarr, Sonarr, qBitrr all in Docker on one server
- Downloads saved to `/mnt/storage/torrents`
- Media library at `/mnt/storage/media`

**docker-compose.yml:**

```yaml
version: "3.8"

services:
  qbittorrent:
    image: lscr.io/linuxserver/qbittorrent:latest
    container_name: qbittorrent
    volumes:
      - ./qbittorrent/config:/config
      - /mnt/storage:/data  # Single root mount
    ports:
      - "8080:8080"

  radarr:
    image: lscr.io/linuxserver/radarr:latest
    container_name: radarr
    volumes:
      - ./radarr/config:/config
      - /mnt/storage:/data  # Same path
    ports:
      - "7878:7878"

  sonarr:
    image: lscr.io/linuxserver/sonarr:latest
    container_name: sonarr
    volumes:
      - ./sonarr/config:/config
      - /mnt/storage:/data  # Same path
    ports:
      - "8989:8989"

  qbitrr:
    image: feramance/qbitrr:latest
    container_name: qbitrr
    volumes:
      - ./qbitrr/config:/config
      - /mnt/storage:/data  # Same path
    ports:
      - "6969:6969"
```

**config.toml:**

```toml
[qBit]
Host = "qbittorrent"
Port = 8080

[Radarr-Movies]
URI = "http://radarr:7878"
Category = "radarr-movies"

[Sonarr-TV]
URI = "http://sonarr:8989"
Category = "sonarr-tv"

[Settings]
CompletedDownloadFolder = "/data/torrents"
```

**Directory structure:**

```
/mnt/storage/               (host)
├── torrents/               → /data/torrents (all containers)
│   ├── movies/
│   └── tv/
├── media/                  → /data/media
│   ├── Movies/
│   └── TV Shows/
```

---

### Scenario 2: Mixed Docker + Native Install

**Setup:**

- qBittorrent and Arr instances in Docker
- qBitrr runs natively (systemd, not Docker)
- Downloads at `/mnt/storage/torrents`

**docker-compose.yml:**

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/storage:/data

  radarr:
    volumes:
      - /mnt/storage:/data
```

**config.toml (native qBitrr):**

```toml
[Settings]
CompletedDownloadFolder = "/mnt/storage/torrents"  # Host path
```

**Why this works:** Native qBitrr sees the host file system directly, while containers see `/data` → `/mnt/storage` mapping.

**Path perspective:**

| Service | Sees Path | Physical Path |
|---------|-----------|---------------|
| qBittorrent (Docker) | `/data/torrents/Movie.mkv` | `/mnt/storage/torrents/Movie.mkv` |
| Radarr (Docker) | `/data/torrents/Movie.mkv` | `/mnt/storage/torrents/Movie.mkv` |
| qBitrr (Native) | `/mnt/storage/torrents/Movie.mkv` | `/mnt/storage/torrents/Movie.mkv` |

---

### Scenario 3: Remote Path Mapping (Not Recommended)

**Setup:**

- qBittorrent saves to `/downloads`
- Radarr expects `/data/torrents`
- qBitrr sees `/completed`

**docker-compose.yml:**

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/storage/torrents:/downloads  # Different path

  radarr:
    volumes:
      - /mnt/storage/torrents:/data/torrents  # Different path

  qbitrr:
    volumes:
      - /mnt/storage/torrents:/completed  # Different path
```

**Radarr Remote Path Mapping:**

```
Host: qbittorrent
Remote Path: /downloads/
Local Path: /data/torrents/
```

**config.toml:**

```toml
[Settings]
CompletedDownloadFolder = "/completed"
```

**Why this is problematic:**

- ❌ Complex to configure
- ❌ Hard to debug
- ❌ Path translation errors common
- ❌ No atomic moves (copies instead of instant renames)
- ❌ qBitrr may not see files at expected paths

**Solution: Standardize paths**

Change all containers to use `/data/torrents` and remove remote path mappings.

---

## Diagnosing Path Issues

### Symptoms of Path Mismatch

1. **Import Failures**
   ```
   [Radarr] No files found eligible for import
   ```

2. **Path Not Found Errors**
   ```
   [qBitrr] FileNotFoundError: /data/torrents/Movie.mkv
   ```

3. **Instant Import Not Triggering**
   ```
   [qBitrr] Torrent completed but no import triggered
   ```

4. **Copy Instead of Move**
   ```
   [Radarr] Importing (Copy): /data/torrents/Movie.mkv → /data/movies/Movie.mkv
   ```
   (Should be "Importing (Hardlink)" or "Importing (Move)")

### Diagnostic Commands

#### Check Container Mounts

```bash
# Inspect qBittorrent container
docker inspect qbittorrent | grep -A 10 Mounts

# Inspect Radarr container
docker inspect radarr | grep -A 10 Mounts

# Inspect qBitrr container
docker inspect qbitrr | grep -A 10 Mounts
```

Look for inconsistent `Destination` paths.

#### Verify File Visibility

```bash
# From host: Create test file
touch /mnt/storage/torrents/test.txt

# Check qBittorrent sees it
docker exec qbittorrent ls -lh /data/torrents/test.txt

# Check Radarr sees it
docker exec radarr ls -lh /data/torrents/test.txt

# Check qBitrr sees it
docker exec qbitrr ls -lh /data/torrents/test.txt

# Cleanup
rm /mnt/storage/torrents/test.txt
```

All three should succeed if paths are correct.

#### Check qBittorrent Save Path

```bash
# Query qBittorrent API for save path
docker exec qbittorrent cat /config/qBittorrent/qBittorrent.conf | grep "Downloads\\\SavePath"
```

Compare to your volume mapping.

#### Check Radarr Root Folder

```bash
# Query Radarr API
curl -H "X-Api-Key: YOUR_API_KEY" http://localhost:7878/api/v3/rootfolder
```

Verify root folder path matches container mount.

---

## Fixing Path Mismatches

### Step 1: Document Current Setup

Create a table of current paths:

| Service | Host Path | Container Path |
|---------|-----------|----------------|
| qBittorrent | `/mnt/storage/torrents` | `/downloads` |
| Radarr | `/mnt/storage/torrents` | `/data/torrents` |
| qBitrr | `/mnt/storage/torrents` | `/completed` |

### Step 2: Choose Target Path

Pick a consistent container path for all services. Common choices:

- `/data` (single root)
- `/data/torrents` (specific to torrents)
- `/downloads` (legacy, less flexible)

**Recommended:** `/data` (single root mount)

### Step 3: Update docker-compose.yml

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/storage:/data  # Changed from /downloads

  radarr:
    volumes:
      - /mnt/storage:/data  # No change needed

  sonarr:
    volumes:
      - /mnt/storage:/data

  qbitrr:
    volumes:
      - /mnt/storage:/data  # Changed from /completed
```

### Step 4: Update qBittorrent Settings

**WebUI → Options → Downloads**

```
Default Save Path: /data/torrents
Temp Save Path: /data/torrents/incomplete
```

**Category paths:**

```
radarr-movies → /data/torrents/movies
sonarr-tv     → /data/torrents/tv
```

### Step 5: Update Radarr Root Folder

**Settings → Media Management → Root Folders**

```
Old: /data/torrents/movies
New: /data/movies
```

**Remove Remote Path Mappings:**

Settings → Download Clients → Remote Path Mappings → Delete all entries

### Step 6: Update config.toml

```toml
[Settings]
CompletedDownloadFolder = "/data/torrents"
```

### Step 7: Restart All Services

```bash
docker-compose down
docker-compose up -d
```

### Step 8: Verify

```bash
# Test file visibility
touch /mnt/storage/torrents/test.txt

docker exec qbittorrent ls /data/torrents/test.txt
docker exec radarr ls /data/torrents/test.txt
docker exec qbitrr ls /data/torrents/test.txt

rm /mnt/storage/torrents/test.txt
```

All commands should succeed.

---

## Testing Path Accessibility

### Manual Test Workflow

1. **Add a test movie in Radarr**
   - Use a small, public domain movie
   - Monitor download in qBittorrent

2. **Check qBittorrent save path**
   ```bash
   docker exec qbittorrent ls -lh /data/torrents/
   ```

3. **Check qBitrr sees the download**
   ```bash
   docker exec qbitrr ls -lh /data/torrents/
   ```

4. **Monitor qBitrr logs**
   ```bash
   docker logs -f qbitrr
   ```

   Expected output:
   ```
   [Radarr-Movies] Torrent completed: Movie (2024)
   [Radarr-Movies] Triggering DownloadedMoviesScan: /data/torrents/Movie (2024)
   [Radarr-Movies] Import successful: Movie (2024)
   ```

5. **Check Radarr import**
   - Activity → Queue → Should show "Completed"
   - Movies → Should show "Downloaded"

### Automated Test Script

```bash
#!/bin/bash
# test-paths.sh

HOST_PATH="/mnt/storage/torrents"
CONTAINER_PATH="/data/torrents"
TEST_FILE="qbitrr-path-test-$(date +%s).txt"

echo "Creating test file at $HOST_PATH/$TEST_FILE"
touch "$HOST_PATH/$TEST_FILE"

echo "Testing qBittorrent..."
docker exec qbittorrent ls -lh "$CONTAINER_PATH/$TEST_FILE" || echo "❌ qBittorrent FAIL"

echo "Testing Radarr..."
docker exec radarr ls -lh "$CONTAINER_PATH/$TEST_FILE" || echo "❌ Radarr FAIL"

echo "Testing Sonarr..."
docker exec sonarr ls -lh "$CONTAINER_PATH/$TEST_FILE" || echo "❌ Sonarr FAIL"

echo "Testing qBitrr..."
docker exec qbitrr ls -lh "$CONTAINER_PATH/$TEST_FILE" || echo "❌ qBitrr FAIL"

echo "Cleaning up..."
rm "$HOST_PATH/$TEST_FILE"

echo "✅ All tests passed!"
```

```bash
chmod +x test-paths.sh
./test-paths.sh
```

---

## Advanced Topics

### Atomic Moves vs. Copies

**Atomic Move (Instant):**

- File is renamed, not copied
- Happens in milliseconds
- Requires source and destination on same file system
- qBitrr triggers instant import

**Copy (Slow):**

- File is duplicated byte-by-byte
- Takes time proportional to file size
- Works across different file systems
- qBitrr may not detect completion

**How to ensure atomic moves:**

1. Use consistent paths across all containers
2. Ensure downloads and media library are on same mount point
3. Avoid remote path mappings

**Example:**

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/storage:/data  # Both torrents and media on /mnt/storage

  radarr:
    volumes:
      - /mnt/storage:/data
```

```toml
[Settings]
CompletedDownloadFolder = "/data/torrents"
```

**Radarr Settings:**

```
Root Folder: /data/movies
Download Folder: /data/torrents
```

Both `/data/torrents` and `/data/movies` map to `/mnt/storage`, so Radarr can do instant moves.

### Network Storage (NFS, SMB)

**Challenge:** NFS/SMB mounts may not support atomic moves or hardlinks.

**Solution:**

1. **Use Docker volumes for NFS:**

   ```yaml
   volumes:
     nfs_data:
       driver: local
       driver_opts:
         type: nfs
         o: addr=192.168.1.100,rw,nfsvers=4
         device: ":/mnt/storage"

   services:
     qbittorrent:
       volumes:
         - nfs_data:/data

     radarr:
       volumes:
         - nfs_data:/data
   ```

2. **Test atomic moves:**

   ```bash
   # Inside container
   docker exec qbittorrent sh -c 'touch /data/test1.txt && mv /data/test1.txt /data/test2.txt && ls /data/test2.txt'
   ```

   If this succeeds instantly, atomic moves work.

3. **Fallback to copies:**

   If atomic moves fail, Radarr will copy. qBitrr will still work but imports will be slower.

### Permissions Issues

**Symptom:** "Permission denied" errors when accessing files

**Diagnosis:**

```bash
# Check file ownership
docker exec qbitrr ls -lh /data/torrents/

# Check process user
docker exec qbitrr id
docker exec radarr id
```

**Solution: Match UID/GID**

```yaml
services:
  qbittorrent:
    user: "1000:1000"  # Match your host user

  radarr:
    user: "1000:1000"

  sonarr:
    user: "1000:1000"

  qbitrr:
    user: "1000:1000"
```

**Fix existing files:**

```bash
# On host
sudo chown -R 1000:1000 /mnt/storage/torrents
sudo chmod -R 755 /mnt/storage/torrents
```

### SELinux Context Issues (Linux)

**Symptom:** Permission denied despite correct ownership

**Diagnosis:**

```bash
ls -Z /mnt/storage/torrents
```

**Solution: Add SELinux label to volume:**

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/storage:/data:z  # :z for private, :Z for shared
```

**Or disable SELinux (not recommended):**

```bash
sudo setenforce 0
```

---

## Real-World Examples

### Example 1: TRaSH Guides Setup

Based on TRaSH Guides recommendations:

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/storage:/data

  radarr:
    volumes:
      - /mnt/storage:/data

  sonarr:
    volumes:
      - /mnt/storage:/data

  qbitrr:
    volumes:
      - /mnt/storage:/data
```

**Directory structure:**

```
/mnt/storage/
├── torrents/
│   ├── movies/           # qBittorrent category: radarr-movies
│   ├── tv/               # qBittorrent category: sonarr-tv
│   └── music/            # qBittorrent category: lidarr-music
└── media/
    ├── Movies/           # Radarr root folder
    ├── TV Shows/         # Sonarr root folder
    └── Music/            # Lidarr root folder
```

**config.toml:**

```toml
[Settings]
CompletedDownloadFolder = "/data/torrents"

[Radarr-Movies]
Category = "radarr-movies"

[Sonarr-TV]
Category = "sonarr-tv"

[Lidarr-Music]
Category = "lidarr-music"
```

### Example 2: Separate Disks for Torrents and Media

**Setup:**

- SSD for active torrents: `/mnt/ssd/torrents`
- HDD for media library: `/mnt/hdd/media`

**docker-compose.yml:**

```yaml
services:
  qbittorrent:
    volumes:
      - /mnt/ssd/torrents:/data/torrents
      - /mnt/hdd/media:/data/media

  radarr:
    volumes:
      - /mnt/ssd/torrents:/data/torrents
      - /mnt/hdd/media:/data/media

  qbitrr:
    volumes:
      - /mnt/ssd/torrents:/data/torrents
      - /mnt/hdd/media:/data/media  # May not need, but good for verification
```

**config.toml:**

```toml
[Settings]
CompletedDownloadFolder = "/data/torrents"
```

**Note:** Radarr will **copy** files from `/data/torrents` to `/data/media` because they're on different file systems (no atomic moves possible).

---

## Quick Reference

### Path Mapping Checklist

- [ ] All containers use same container path for torrents
- [ ] qBittorrent save path matches container mount
- [ ] Radarr/Sonarr root folders exist inside container
- [ ] No remote path mappings configured (unless absolutely necessary)
- [ ] Test file visible from all containers
- [ ] Atomic moves work (same file system)
- [ ] Permissions correct (all containers run as same UID/GID)
- [ ] CompletedDownloadFolder in config.toml matches container path

### Common Fixes

```bash
# Fix 1: Standardize all containers to /data
# In docker-compose.yml:
volumes:
  - /mnt/storage:/data

# Fix 2: Update qBittorrent save path
# WebUI → Options → Downloads → Default Save Path → /data/torrents

# Fix 3: Update Radarr root folder
# Settings → Media Management → Root Folders → /data/movies

# Fix 4: Update config.toml
# [Settings]
CompletedDownloadFolder = "/data/torrents"

# Fix 5: Restart all services
docker-compose down && docker-compose up -d
```

---

## Related Documentation

- [Docker Troubleshooting](docker.md) - Docker-specific issues
- [Common Issues](common-issues.md) - General troubleshooting
- [qBittorrent Configuration](../configuration/qbittorrent.md) - qBit setup guide
- [Arr Configuration](../configuration/arr/index.md) - Radarr/Sonarr/Lidarr setup

---

## External Resources

- [TRaSH Guides - Hardlinks](https://trash-guides.info/Hardlinks/Hardlinks-and-Instant-Moves/) - Comprehensive hardlink guide
- [TRaSH Guides - Docker Guide](https://trash-guides.info/File-and-Folder-Structure/) - Recommended folder structure
- [Radarr - Remote Path Mappings](https://wiki.servarr.com/radarr/settings#remote-path-mappings) - Official Radarr docs
