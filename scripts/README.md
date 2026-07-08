# qBitrr Database Recovery Scripts

This directory contains utility scripts for database maintenance, recovery, and deployment.

## Rebuild and deploy on git sync

To **rebuild and deploy qBitrr automatically after every `git pull`**, install the post-merge hook. The hook runs the Python rebuild script when available (works on Windows, Linux, macOS); otherwise it falls back to the bash script (requires bash, e.g. Git Bash on Windows).

```bash
# From repo root (Linux/macOS or Git Bash on Windows)
bash scripts/install-post-merge-hook.sh
```

After installation, each time you run `git pull` (and a merge happens), the hook will:

- **If `docker-compose.yml` exists:** run `docker compose build --no-cache` and `docker compose up -d`.
- **Otherwise:** run `make syncenv` (sync venv and build WebUI). Restart qBitrr manually if you use systemd.

**Override behaviour** with `DEPLOY_MODE`:

- `DEPLOY_MODE=docker` — force Docker Compose rebuild and deploy.
- `DEPLOY_MODE=native` — force `make syncenv` only (no Docker).

Example (before pulling):

```bash
export DEPLOY_MODE=native
git pull
```

**Manual run** (without git), any environment:

```bash
# Cross-platform (Windows, Linux, macOS) — use when bash is not available
python scripts/rebuild_and_deploy.py
# or
python3 scripts/rebuild_and_deploy.py
```

```bash
# Linux/macOS or Git Bash on Windows
bash scripts/rebuild-and-deploy.sh
```

**Files:**

- `scripts/rebuild_and_deploy.py` — Rebuild and deploy logic (Python; works in any environment).
- `scripts/rebuild-and-deploy.sh` — Same logic for bash (Linux/macOS/Git Bash).
- `scripts/post-merge.hook` — Hook content (installed into `.git/hooks/post-merge`; runs Python script when available, else bash).
- `scripts/install-post-merge-hook.sh` — One-time installer for the hook.

---

## Scripts

### repair_database.py

**Purpose:** General-purpose database repair using built-in recovery tools.

**What it does:**
1. Attempts WAL checkpoint (least invasive)
2. Verifies database integrity
3. If corrupted, performs full dump/restore
4. Creates backup before any changes

**Usage:**
```bash
python3 scripts/repair_database.py
```

**When to use:**
- General database corruption issues
- WAL-related problems
- When you want automatic recovery attempts

**Safety:** Creates backup automatically (`qbitrr.db.backup`)

---

### repair_database_targeted.py

**Purpose:** Targeted repair that rebuilds database schema and copies accessible data.

**What it does:**
1. Creates timestamped backup of corrupted database
2. Creates fresh database with correct schema
3. Copies all accessible table data
4. Skips corrupted tables (will be repopulated by app)
5. Verifies integrity of new database

**Usage:**
```bash
python3 scripts/repair_database_targeted.py
```

**When to use:**
- When specific tables are corrupted
- When standard repair tools fail
- When you need to salvage partial data

**Safety:** Creates timestamped backup (`qbitrr.db.corrupted_YYYYMMDD_HHMMSS`)

---

## Database Location

The scripts operate on the database at:
```
/home/qBitrr/.config/qBitManager/qbitrr.db
```

Or in Docker container:
```
/config/qBitManager/qbitrr.db
```

---

## Prevention

The database corruption issue was caused by `synchronous=0` (OFF) in SQLite configuration. This has been **fixed** in commit `465c306d`:

**Old (UNSAFE):**
```python
"synchronous": 0  # No fsync() - FAST but UNSAFE
```

**Current (SAFEST):**
```python
"synchronous": 2  # FULL - maximum durability with WAL mode
```

With the fix in place, corruption should be **rare** during normal operation. qBitrr also runs periodic WAL checkpoint + `quick_check` maintenance every 5 minutes and auto-repairs when corruption is detected.

---

## When Corruption Occurs

Despite the fix, corruption can still occur due to:
- Hardware failures (disk errors, RAM issues)
- Power loss or OOM kill during write (mitigated by `synchronous=2` and periodic checkpoint)
- Filesystem corruption
- Container/VM crashes or `docker kill` / `docker stop -t 0` (skips WAL checkpoint)

### Recovery Steps

1. **Stop qBitrr:**
   ```bash
   docker compose down
   # or
   systemctl stop qbitrr
   ```

2. **Check Database:**
   ```bash
   python3 -c "import sqlite3; conn = sqlite3.connect('.config/qBitManager/qbitrr.db');
   cursor = conn.cursor(); cursor.execute('PRAGMA integrity_check');
   print(cursor.fetchone()[0])"
   ```

3. **Run Repair (if needed):**
   ```bash
   # Try standard repair first
   python3 scripts/repair_database.py

   # If that fails, use targeted repair
   python3 scripts/repair_database_targeted.py
   ```

4. **Verify Fix:**
   ```bash
   python3 -c "import sqlite3; conn = sqlite3.connect('.config/qBitManager/qbitrr.db');
   cursor = conn.cursor(); cursor.execute('PRAGMA integrity_check');
   print(cursor.fetchone()[0])"
   ```

   Should print: `ok`

5. **Restart qBitrr:**
   ```bash
   docker compose up -d
   # or
   systemctl start qbitrr
   ```

---

## Backups

### Scheduled / online backup

[`backup_database.py`](backup_database.py) creates a consistent copy using the SQLite backup API while qBitrr is running:

```bash
# Docker
docker compose exec -T qbitrr python scripts/backup_database.py

# Native (from repo root)
python scripts/backup_database.py
```

Default output: `qBitManager/backups/qbitrr.db.YYYYMMDD`. Use in cron for daily backups (see [database troubleshooting](../docs/troubleshooting/database.md#scheduled-backups-recommended)).

### Repair backups

Repair scripts create backups before making changes:

- `repair_database.py` → `qbitrr.db.backup`
- `repair_database_targeted.py` → `qbitrr.db.corrupted_YYYYMMDD_HHMMSS`

To restore from backup:
```bash
cd /home/qBitrr/.config/qBitManager
cp qbitrr.db.backup qbitrr.db
# or
cp qbitrr.db.corrupted_YYYYMMDD_HHMMSS qbitrr.db
```

---

## Additional Resources

- [Database Corruption Fix Documentation](../docs/fixes/DATABASE_CORRUPTION_FIX.md) - Complete analysis and fix details
- [SQLite Documentation](https://www.sqlite.org/pragma.html#pragma_synchronous) - PRAGMA synchronous
- [qBitrr Issues](https://github.com/Drapersniper/Qbitrr/issues) - Report problems

---

## Maintenance

### Regular Health Checks

Check database health periodically:

```bash
# Quick check
python3 -c "import sqlite3; conn = sqlite3.connect('.config/qBitManager/qbitrr.db');
cursor = conn.cursor(); cursor.execute('PRAGMA quick_check');
print(cursor.fetchone()[0])"

# Full integrity check
python3 -c "import sqlite3; conn = sqlite3.connect('.config/qBitManager/qbitrr.db');
cursor = conn.cursor(); cursor.execute('PRAGMA integrity_check');
print(cursor.fetchone()[0])"
```

### WAL Maintenance

Check WAL file size:
```bash
ls -lh /home/qBitrr/.config/qBitManager/qbitrr.db-wal
```

If WAL is large (>10MB), checkpoint it:
```bash
python3 -c "import sqlite3; conn = sqlite3.connect('.config/qBitManager/qbitrr.db');
conn.execute('PRAGMA wal_checkpoint(TRUNCATE)');
print('WAL checkpointed successfully')"
```

**Note:** With `wal_autocheckpoint=100` and the 5-minute maintenance thread, WAL should checkpoint regularly. Use `backup_database.py` for scheduled backups.

---

## Technical Details

### Database Configuration

Current SQLite pragmas (see `qBitrr/database.py`):
```python
{
    "journal_mode": "wal",              # Write-Ahead Logging
    "synchronous": 2,                   # FULL - maximum durability
    "cache_size": -64_000,              # 64MB cache
    "foreign_keys": 1,                  # Enable FK constraints
    "read_uncommitted": 1,              # Reduce read lock contention (WebUI)
    "wal_autocheckpoint": 100,          # Auto checkpoint every 100 pages
    "journal_size_limit": 67108864,     # 64MB max WAL size
}
```

### Why synchronous=2 (FULL)?

- **0 (OFF):** No fsync() → FAST but UNSAFE (corruption on crash)
- **1 (NORMAL):** fsync() at critical moments → SAFE and reasonably fast
- **2 (FULL):** Extra fsync() calls → SAFEST (current default) ✓

With WAL mode, FULL trades a small write latency cost for the strongest protection against unclean shutdown corruption.

---

**Last Updated:** 2026-06-11
**Fix Commit:** 465c306d (synchronous); periodic maintenance added v5.12+
**Status:** Corruption risk **mitigated** — use graceful stops and daily backups
