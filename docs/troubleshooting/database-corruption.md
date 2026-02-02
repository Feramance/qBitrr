# Database Corruption Prevention

This guide covers how qBitrr prevents database corruption and what you can do to minimize the risk.

---

## Current Protection Mechanisms

qBitrr already implements several best practices to prevent database corruption:

### 1. Write-Ahead Logging (WAL Mode)
**Status**: ✅ Enabled by default

The database uses WAL mode instead of traditional rollback journaling:

```python
pragmas={
    "journal_mode": "wal",  # More robust than rollback journal
    "synchronous": 1,        # NORMAL mode - balances safety and performance
    "wal_autocheckpoint": 1000,  # Checkpoint every 1000 pages
    "journal_size_limit": 67108864,  # 64MB max WAL size
}
```

**Benefits**:
- Better concurrency (readers don't block writers)
- More resistant to corruption from power loss
- Atomic commits even during crashes

### 2. Automatic Recovery
**Status**: ✅ Implemented

When database errors are detected, qBitrr automatically attempts recovery:

1. **WAL Checkpoint**: Flush write-ahead log to main database
2. **VACUUM**: Rebuild database file to reclaim space
3. **Dump/Restore**: Extract recoverable data and rebuild database

These operations run automatically when corruption is detected during normal operations.

### 3. Connection Retry Logic
**Status**: ✅ Implemented

Database operations automatically retry with exponential backoff when encountering locks or temporary errors, preventing corruption from incomplete writes.

---

## Additional Prevention Strategies

### Storage Configuration

#### Use Local Storage (Not NFS/CIFS)
**Priority**: High

SQLite performs best on local filesystems. Network filesystems can cause corruption due to:
- File locking issues
- Delayed writes
- Cache coherency problems

**Recommendation**:
```yaml
# docker-compose.yml
volumes:
  - ./config:/config  # Local bind mount (GOOD)
  # NOT: - nfs-server:/config  # Network storage (RISKY)
```

#### Ensure Adequate Disk Space
**Priority**: High

Database operations require temporary space. Running out of disk space mid-write can cause corruption.

**Recommendation**:
- Monitor free space with qBitrr's built-in disk space guard
- Keep at least 5-10GB free for database operations
- Set `FreeSpace` in config to trigger alerts

```toml
[Settings]
FreeSpace = "10G"  # Warn when free space drops below 10GB
FreeSpaceFolder = "/config"
AutoPauseResume = true  # Pause torrents when space is low
```

### Docker Configuration

#### Use Proper Shutdown Signals
**Priority**: High

Avoid abrupt container termination:

```bash
# GOOD - Graceful shutdown
docker stop qbitrr  # Sends SIGTERM, waits for cleanup

# BAD - Abrupt termination
docker kill qbitrr  # Immediate termination, may corrupt database
```

**Docker Compose**:
```yaml
services:
  qbitrr:
    stop_grace_period: 30s  # Allow 30s for graceful shutdown
```

#### Avoid Host Path Issues
**Priority**: Medium

Ensure Docker has proper permissions on mounted volumes:

```bash
# Check ownership
ls -la /path/to/config

# Fix if needed (adjust UID/GID to match container)
chown -R 1000:1000 /path/to/config
```

### Proactive Maintenance

#### Regular Integrity Checks
**Priority**: Medium

While qBitrr automatically checks integrity on errors, you can add periodic checks.

**Manual Check**:
```bash
docker exec qbitrr python3 << 'EOF'
import sqlite3
from pathlib import Path

db_path = Path("/config/qBitManager/qbitrr.db")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()
cursor.execute("PRAGMA integrity_check")
result = cursor.fetchall()
conn.close()

if result[0][0] == "ok":
    print("✓ Database integrity: OK")
else:
    print("✗ Database corruption detected:")
    for row in result:
        print(f"  {row[0]}")
EOF
```

#### Periodic Backups
**Priority**: High

Automated backups are your safety net.

**Example Cron Job** (runs daily at 3 AM):
```bash
#!/bin/bash
# backup-qbitrr-db.sh

BACKUP_DIR="/path/to/backups"
DB_PATH="/path/to/config/qBitManager/qbitrr.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup main database
cp "$DB_PATH" "$BACKUP_DIR/qbitrr_$TIMESTAMP.db"

# Backup WAL files if they exist
if [ -f "$DB_PATH-wal" ]; then
    cp "$DB_PATH-wal" "$BACKUP_DIR/qbitrr_$TIMESTAMP.db-wal"
fi
if [ -f "$DB_PATH-shm" ]; then
    cp "$DB_PATH-shm" "$BACKUP_DIR/qbitrr_$TIMESTAMP.db-shm"
fi

# Keep only last 30 days of backups
find "$BACKUP_DIR" -name "qbitrr_*.db*" -mtime +30 -delete

echo "Backup completed: qbitrr_$TIMESTAMP.db"
```

Add to crontab:
```bash
0 3 * * * /path/to/backup-qbitrr-db.sh >> /var/log/qbitrr-backup.log 2>&1
```

#### WAL Checkpoint Before Shutdown
**Status**: ⚠️ Recommended Enhancement

Add a checkpoint operation to your shutdown routine.

**Docker Entrypoint Wrapper**:
```bash
#!/bin/bash
# entrypoint.sh

# Function to checkpoint WAL on shutdown
checkpoint_wal() {
    echo "Checkpointing WAL before shutdown..."
    python3 << 'EOF'
import sqlite3
from pathlib import Path

db_path = Path("/config/qBitManager/qbitrr.db")
try:
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    print("✓ WAL checkpoint completed")
except Exception as e:
    print(f"✗ WAL checkpoint failed: {e}")
EOF
}

# Trap shutdown signals
trap 'checkpoint_wal' SIGTERM SIGINT

# Start qBitrr (replace with actual command)
exec qBitrr "$@" &
PID=$!

# Wait for process
wait $PID
```

---

## Enhanced Configuration Options

### Increase Synchronous Level (More Safety, Less Performance)
**Use case**: Critical data, willing to sacrifice speed

```python
# In qBitrr/database.py - modify pragmas:
pragmas={
    "synchronous": 2,  # FULL mode - maximum safety (slower)
    # ... other pragmas
}
```

**Trade-off**: Writes are slower but less likely to corrupt on power loss.

### Reduce WAL Autocheckpoint (More Frequent Flushes)
**Use case**: Prefer smaller WAL files, more frequent writes to disk

```python
pragmas={
    "wal_autocheckpoint": 100,  # Checkpoint every 100 pages (more frequent)
    # ... other pragmas
}
```

**Trade-off**: More frequent disk writes, potentially slower performance.

---

## Recovery from Corruption

If corruption occurs despite preventive measures:

### 1. Automatic Recovery (Preferred)
qBitrr will attempt automatic recovery on next startup. Check logs:

```bash
docker logs qbitrr | grep -i "recovery\|corrupt\|checkpoint"
```

### 2. Manual Recovery
If automatic recovery fails:

```bash
# Stop qBitrr
docker stop qbitrr

# Backup current state
cp /path/to/config/qBitManager/qbitrr.db /path/to/backups/qbitrr_corrupt_$(date +%Y%m%d).db

# Attempt repair
docker run --rm -v /path/to/config:/config \
  --entrypoint python3 qbitrr-qbitrr << 'EOF'
from pathlib import Path
from qBitrr.db_recovery import repair_database

db_path = Path("/config/qBitManager/qbitrr.db")
try:
    repair_database(db_path, backup=True)
    print("✓ Repair successful")
except Exception as e:
    print(f"✗ Repair failed: {e}")
EOF

# Restart qBitrr
docker start qbitrr
```

### 3. Restore from Backup
If repair fails, restore from a recent backup:

```bash
docker stop qbitrr
cp /path/to/backups/qbitrr_<timestamp>.db /path/to/config/qBitManager/qbitrr.db
docker start qbitrr
```

**Note**: You may lose data since the backup was created.

### 4. Fresh Start (Last Resort)
Delete corrupted database and let qBitrr recreate:

```bash
docker stop qbitrr
rm /path/to/config/qBitManager/qbitrr.db*
docker start qbitrr
```

**Warning**: This loses all torrent tracking history. qBitrr will rescan from Arr instances on startup.

---

## Monitoring and Alerting

### Health Check Script
Add to your monitoring system:

```bash
#!/bin/bash
# check-qbitrr-db-health.sh

DB_PATH="/path/to/config/qBitManager/qbitrr.db"

# Check file exists
if [ ! -f "$DB_PATH" ]; then
    echo "CRITICAL: Database file missing"
    exit 2
fi

# Check integrity
RESULT=$(docker exec qbitrr python3 << 'EOF'
import sqlite3
from pathlib import Path

db_path = Path("/config/qBitManager/qbitrr.db")
try:
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA quick_check")
    result = cursor.fetchone()[0]
    conn.close()
    print(result)
except Exception as e:
    print(f"ERROR: {e}")
EOF
)

if [ "$RESULT" = "ok" ]; then
    echo "OK: Database healthy"
    exit 0
else
    echo "CRITICAL: Database corruption detected: $RESULT"
    exit 2
fi
```

### Metrics to Monitor
- Database file size (sudden drops indicate corruption)
- WAL file size (growing without checkpoint may indicate issues)
- Error rate in logs
- Connection timeout frequency

---

## Implementation Roadmap

### Immediate (Do Now)
1. ✅ Verify Docker has proper permissions on config directory
2. ✅ Set up automated daily backups
3. ✅ Configure graceful shutdown (`stop_grace_period: 30s`)
4. ✅ Ensure adequate disk space (set `FreeSpace` in config)

### Short-term (Within a Month)
5. ⚠️ Add health check script to monitoring
6. ⚠️ Implement periodic integrity checks (weekly cron job)
7. ⚠️ Test backup restoration procedure

### Long-term (Nice to Have)
8. ⚠️ Add custom entrypoint with WAL checkpoint on shutdown
9. ⚠️ Consider increasing `synchronous` level if performance allows
10. ⚠️ Implement automated alerts on corruption detection

---

## Related Documentation

- [Docker Installation](../getting-started/installation/docker.md) – Proper Docker setup
- [Configuration Reference](../configuration/index.md) – FreeSpace and storage settings
- [Troubleshooting Guide](index.md) – General troubleshooting

---

## Contributing

If you experience database corruption:
1. Save logs: `docker logs qbitrr > qbitrr-corruption-$(date +%Y%m%d).log`
2. Note your environment (Docker version, host OS, filesystem type)
3. Report at [GitHub Issues](https://github.com/Feramance/qBitrr/issues)
