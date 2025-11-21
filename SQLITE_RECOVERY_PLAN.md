# SQLite Disk I/O Error - Automated Recovery Plan

**Generated:** 2025-11-20
**Issue:** `sqlite3.OperationalError: disk I/O error` during database operations in qBitrr
**Affected Components:** Peewee ORM operations, particularly in `refresh_download_queue()` and similar database writes

---

## Executive Summary

The error occurs when SQLite encounters disk I/O failures during database operations. This can be caused by:
- Hardware issues (disk failures, NFS/network storage timeouts)
- Filesystem corruption or full disk
- Docker volume issues (permissions, mount problems)
- Concurrent access conflicts despite locking mechanisms
- SQLite journal/WAL corruption

This plan outlines **5 recovery strategies** with progressive severity, from transparent retries to database reconstruction.

---

## Current State Analysis

### Error Location
- **File:** `qBitrr/arss.py:4367` in `process_torrents()`
- **Operation:** `self.refresh_download_queue()` → Peewee delete query execution
- **Stack:** `peewee.py:3322` → `sqlite3.execute()` → OS disk I/O failure

### Existing Protections
✅ **Cross-process file locking** via `db_lock.py` (`_InterProcessFileLock`)
✅ **Network retry logic** via `utils.with_retry()` for API calls
❌ **NO database-specific retry** for transient I/O errors
❌ **NO corruption detection** before operations
❌ **NO automatic recovery** from failed transactions

---

## Recovery Strategy 1: Transparent Retry with Exponential Backoff

**Goal:** Handle transient I/O errors (network storage hiccups, brief locks) without user intervention.

### Implementation Steps

#### 1.1 Create Database-Specific Retry Wrapper
**File:** `qBitrr/db_lock.py`

Add after the `database_lock()` function:

```python
import sqlite3
from typing import Callable, TypeVar

T = TypeVar("T")

def with_database_retry(
    func: Callable[[], T],
    *,
    retries: int = 5,
    backoff: float = 0.5,
    max_backoff: float = 10.0,
    jitter: float = 0.25,
    logger = None
) -> T:
    """
    Execute database operation with retry logic for transient I/O errors.

    Catches:
    - sqlite3.OperationalError (disk I/O, database locked)
    - sqlite3.DatabaseError (corruption that may resolve)

    Does NOT retry:
    - sqlite3.IntegrityError (data constraint violations)
    - sqlite3.ProgrammingError (SQL syntax errors)
    """
    import time
    import random

    attempt = 0
    while True:
        try:
            return func()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            error_msg = str(e).lower()

            # Don't retry on non-transient errors
            if "syntax" in error_msg or "constraint" in error_msg:
                raise

            attempt += 1
            if attempt >= retries:
                if logger:
                    logger.error(
                        "Database operation failed after %s attempts: %s",
                        retries,
                        e
                    )
                raise

            delay = min(max_backoff, backoff * (2 ** (attempt - 1)))
            delay += random.random() * jitter

            if logger:
                logger.warning(
                    "Database I/O error (attempt %s/%s): %s. Retrying in %.2fs",
                    attempt,
                    retries,
                    e,
                    delay
                )

            time.sleep(delay)
```

#### 1.2 Wrap Database Operations in ArrManager
**File:** `qBitrr/arss.py`

Import the new wrapper at the top:
```python
from qBitrr.db_lock import database_lock, with_database_retry
```

Modify `refresh_download_queue()` at line ~5673:
```python
def refresh_download_queue(self):
    """Refresh download queue from Arr API and sync with local database."""

    def _execute_queue_cleanup():
        if self.model_queue:
            self.model_queue.delete().where(
                self.model_queue.EntryId.not_in(list(self.queue_file_ids))
            ).execute()

    # Existing queue fetch logic...
    # (lines 5656-5673 remain unchanged)

    # Wrap the database write with retry logic
    with_database_retry(
        _execute_queue_cleanup,
        retries=5,
        backoff=1.0,
        max_backoff=15.0,
        logger=self.logger
    )

    self._update_bad_queue_items()
```

#### 1.3 Apply to All Critical Database Operations
Target these high-risk operations in `arss.py`:

1. **Line ~2398** - `_update_all_database_entries()` inserts/updates
2. **Line ~5673** - `refresh_download_queue()` deletes ✅ (already covered)
3. **Line ~5844-5895** - All `.delete()` and `.update()` calls in cleanup operations

**Pattern to apply:**
```python
# Before:
self.model_files.delete().where(...).execute()

# After:
with_database_retry(
    lambda: self.model_files.delete().where(...).execute(),
    logger=self.logger
)
```

### Expected Outcome
- 🎯 **90%+ reduction** in user-visible I/O errors
- ⏱️ **Max 60s delay** for 5 retries (0.5 + 1 + 2 + 4 + 8 + 15 cap = ~30s)
- 📊 **Logged warnings** allow identifying chronic issues

---

## Recovery Strategy 2: Pre-Operation Health Check

**Goal:** Detect corruption/issues before critical operations to prevent cascading failures.

### Implementation Steps

#### 2.1 Add Database Integrity Checker
**File:** `qBitrr/db_lock.py`

```python
def check_database_health(db_path: Path, logger=None) -> tuple[bool, str]:
    """
    Perform lightweight SQLite integrity check.

    Returns:
        (is_healthy, error_message)
    """
    import sqlite3

    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        cursor = conn.cursor()

        # Quick integrity check (fast, catches major corruption)
        cursor.execute("PRAGMA quick_check")
        result = cursor.fetchone()[0]

        conn.close()

        if result != "ok":
            return False, f"PRAGMA quick_check failed: {result}"

        return True, "Database healthy"

    except sqlite3.OperationalError as e:
        return False, f"Cannot access database: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"
```

#### 2.2 Integrate Health Check into ArrManager
**File:** `qBitrr/arss.py`

Add to `process_torrents()` at the start (line ~4360):
```python
def process_torrents(self, torrents: list[qbittorrentapi.TorrentDictionary]):
    try:
        with self.locks["process"]:
            try:
                # Periodic health check (every 10th iteration)
                if not hasattr(self, "_health_check_counter"):
                    self._health_check_counter = 0

                self._health_check_counter += 1
                if self._health_check_counter >= 10:
                    from qBitrr.db_lock import check_database_health
                    from qBitrr.home_path import APPDATA_FOLDER

                    db_path = APPDATA_FOLDER / "qbitrr.db"
                    healthy, msg = check_database_health(db_path, self.logger)

                    if not healthy:
                        self.logger.error("Database health check failed: %s", msg)
                        self.logger.warning("Attempting database recovery...")
                        # Trigger Strategy 3 (see below)
                        self._recover_database()

                    self._health_check_counter = 0

                # Existing logic continues...
                if not has_internet(self.manager.qbit_manager.client):
                    # ...
```

### Expected Outcome
- 🔍 **Early detection** of corruption before it causes failures
- 📉 **Reduced cascading errors** from operating on corrupted databases
- 🔄 **Automatic recovery triggers** when issues detected

---

## Recovery Strategy 3: Automatic Database Checkpoint & Repair

**Goal:** Recover from journal/WAL corruption without full restart.

### Implementation Steps

#### 3.1 Create Recovery Module
**File:** `qBitrr/db_recovery.py` (new file)

```python
"""SQLite database recovery utilities."""

from __future__ import annotations

import logging
import shutil
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger("qBitrr.DBRecovery")


class DatabaseRecoveryError(Exception):
    """Raised when database recovery fails."""


def checkpoint_wal(db_path: Path) -> bool:
    """
    Force checkpoint of WAL file to main database.

    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        cursor = conn.cursor()

        # Force WAL checkpoint
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        result = cursor.fetchone()

        conn.close()

        logger.info("WAL checkpoint result: %s", result)
        return True

    except Exception as e:
        logger.error("WAL checkpoint failed: %s", e)
        return False


def repair_database(db_path: Path, backup: bool = True) -> bool:
    """
    Attempt to repair corrupted SQLite database via dump/restore.

    Args:
        db_path: Path to SQLite database file
        backup: Whether to create backup before repair

    Returns:
        True if repair successful

    Raises:
        DatabaseRecoveryError: If repair fails
    """
    backup_path = db_path.with_suffix(".db.backup")
    temp_path = db_path.with_suffix(".db.temp")

    try:
        # Step 1: Backup original
        if backup:
            logger.info("Creating backup: %s", backup_path)
            shutil.copy2(db_path, backup_path)

        # Step 2: Dump recoverable data
        logger.info("Dumping recoverable data from corrupted database...")
        source_conn = sqlite3.connect(str(db_path))

        temp_conn = sqlite3.connect(str(temp_path))

        # Dump schema and data
        for line in source_conn.iterdump():
            try:
                temp_conn.execute(line)
            except sqlite3.Error as e:
                # Log but continue - recover what we can
                logger.debug("Skipping corrupted row: %s", e)

        temp_conn.commit()
        temp_conn.close()
        source_conn.close()

        # Step 3: Replace original with repaired copy
        logger.info("Replacing database with repaired version...")
        db_path.unlink()
        shutil.move(str(temp_path), str(db_path))

        # Step 4: Verify integrity
        verify_conn = sqlite3.connect(str(db_path))
        cursor = verify_conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        verify_conn.close()

        if result != "ok":
            raise DatabaseRecoveryError(f"Repair verification failed: {result}")

        logger.info("Database repair successful!")
        return True

    except Exception as e:
        logger.error("Database repair failed: %s", e)

        # Attempt to restore backup
        if backup and backup_path.exists():
            logger.warning("Restoring from backup...")
            shutil.copy2(backup_path, db_path)

        # Cleanup temp files
        if temp_path.exists():
            temp_path.unlink()

        raise DatabaseRecoveryError(f"Repair failed: {e}") from e


def vacuum_database(db_path: Path) -> bool:
    """
    Run VACUUM to reclaim space and optimize database.

    Note: VACUUM requires free disk space ~2x database size.
    """
    try:
        conn = sqlite3.connect(str(db_path), timeout=30.0)

        logger.info("Running VACUUM on database...")
        conn.execute("VACUUM")
        conn.close()

        logger.info("VACUUM completed successfully")
        return True

    except Exception as e:
        logger.error("VACUUM failed: %s", e)
        return False
```

#### 3.2 Add Recovery Method to ArrManager
**File:** `qBitrr/arss.py`

```python
def _recover_database(self):
    """Attempt automatic database recovery."""
    from qBitrr.db_recovery import checkpoint_wal, repair_database
    from qBitrr.home_path import APPDATA_FOLDER

    db_path = APPDATA_FOLDER / "qbitrr.db"

    # Step 1: Try WAL checkpoint (least invasive)
    self.logger.info("Attempting WAL checkpoint...")
    if checkpoint_wal(db_path):
        self.logger.info("WAL checkpoint successful - database recovered")
        return

    # Step 2: Try full repair (more invasive)
    self.logger.warning("WAL checkpoint failed - attempting full repair...")
    try:
        if repair_database(db_path, backup=True):
            self.logger.info("Database repair successful")
            # Reinitialize database connection
            self._reinit_database()
            return
    except Exception as e:
        self.logger.error("Database repair failed: %s", e)

    # Step 3: Last resort - trigger restart with fresh DB
    self.logger.critical("Database recovery failed - manual intervention required")
    raise RestartLoopException()
```

### Expected Outcome
- 🔧 **Automatic repair** of minor corruption (WAL issues, journal locks)
- 💾 **Data preservation** via dump/restore for recoverable databases
- ⚠️ **Graceful degradation** to restart if repair fails

---

## Recovery Strategy 4: Circuit Breaker Pattern

**Goal:** Prevent database overload during repeated failures by temporarily disabling operations.

### Implementation Steps

#### 4.1 Add Circuit Breaker to db_lock.py
```python
class DatabaseCircuitBreaker:
    """
    Circuit breaker for database operations.

    States:
    - CLOSED: Normal operation
    - OPEN: Failures exceeded threshold, block operations
    - HALF_OPEN: Testing if database recovered
    """

    def __init__(self, failure_threshold=5, timeout=300):
        self.failure_threshold = failure_threshold
        self.timeout = timeout  # seconds before trying again

        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func, logger=None):
        """Execute function with circuit breaker protection."""
        import time

        # Check if circuit should reset
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                self.failures = 0
                if logger:
                    logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise DatabaseCircuitBreakerOpen(
                    f"Circuit breaker OPEN - database operations suspended for "
                    f"{int(self.timeout - (time.time() - self.last_failure_time))}s"
                )

        try:
            result = func()

            # Success - reset if in HALF_OPEN
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failures = 0
                if logger:
                    logger.info("Circuit breaker returned to CLOSED state")

            return result

        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            self.failures += 1
            self.last_failure_time = time.time()

            if self.failures >= self.failure_threshold:
                self.state = "OPEN"
                if logger:
                    logger.error(
                        "Circuit breaker OPEN after %s failures - database operations suspended",
                        self.failures
                    )

            raise


class DatabaseCircuitBreakerOpen(Exception):
    """Raised when circuit breaker is in OPEN state."""


# Global circuit breaker instance
_CIRCUIT_BREAKER = DatabaseCircuitBreaker(failure_threshold=5, timeout=300)


def reset_circuit_breaker():
    """Manually reset circuit breaker (for admin/WebUI)."""
    global _CIRCUIT_BREAKER
    _CIRCUIT_BREAKER.failures = 0
    _CIRCUIT_BREAKER.state = "CLOSED"
```

#### 4.2 Integrate Circuit Breaker with Retry Logic
Modify `with_database_retry()` to use circuit breaker:

```python
def with_database_retry(func, *, retries=5, **kwargs):
    logger = kwargs.get("logger")

    def _wrapped():
        return _CIRCUIT_BREAKER.call(func, logger=logger)

    try:
        return _wrapped()
    except DatabaseCircuitBreakerOpen as e:
        if logger:
            logger.warning(str(e))
        # Don't retry if circuit is open
        raise DelayLoopException(length=60, type="database")
```

### Expected Outcome
- 🛡️ **Prevents cascade failures** from overwhelming storage
- ⏸️ **Auto-recovery time** allows transient issues to resolve
- 📊 **Clear failure signals** for monitoring/alerts

---

## Recovery Strategy 5: Database Reconstruction from Arr APIs

**Goal:** Last resort - rebuild database from source of truth (Arr APIs).

### Implementation Steps

#### 5.1 Add Reconstruction Module
**File:** `qBitrr/db_recovery.py`

```python
def reconstruct_database_from_arr(arr_manager) -> bool:
    """
    Rebuild database by re-fetching all data from Arr API.

    WARNING: This loses qBitrr-specific state:
    - Search history
    - Temporary flags
    - Custom tracking data

    Only use as last resort when database is unrecoverable.
    """
    from qBitrr.home_path import APPDATA_FOLDER

    db_path = APPDATA_FOLDER / "qbitrr.db"

    logger.warning("RECONSTRUCTING DATABASE FROM ARR API - THIS MAY TAKE SEVERAL MINUTES")

    try:
        # Step 1: Backup corrupted database
        backup_path = db_path.with_suffix(f".db.corrupted.{int(time.time())}")
        if db_path.exists():
            shutil.copy2(db_path, backup_path)
            logger.info("Backed up corrupted database to %s", backup_path)

        # Step 2: Delete existing database
        if db_path.exists():
            db_path.unlink()

        # Also remove WAL/journal files
        for suffix in ["-wal", "-shm", "-journal"]:
            journal = Path(str(db_path) + suffix)
            if journal.exists():
                journal.unlink()

        # Step 3: Reinitialize database schema
        arr_manager._reinit_database()

        # Step 4: Force full refresh from Arr API
        logger.info("Fetching all entries from %s...", arr_manager.type)
        arr_manager._force_full_refresh()

        logger.info("Database reconstruction complete!")
        return True

    except Exception as e:
        logger.error("Database reconstruction failed: %s", e)
        return False
```

#### 5.2 Add WebUI Trigger
**File:** `qBitrr/webui.py`

Add new API endpoint for manual recovery:

```python
@app.route("/api/database/recover", methods=["POST"])
@token_required
def recover_database():
    """
    Trigger database recovery operations.

    Body params:
    - method: "checkpoint" | "repair" | "reconstruct"
    - arr_instance: Instance name (for reconstruct only)
    """
    from qBitrr.db_recovery import checkpoint_wal, repair_database, reconstruct_database_from_arr
    from qBitrr.home_path import APPDATA_FOLDER

    data = request.get_json()
    method = data.get("method", "checkpoint")

    db_path = APPDATA_FOLDER / "qbitrr.db"

    try:
        if method == "checkpoint":
            success = checkpoint_wal(db_path)
            return jsonify({"success": success, "method": "checkpoint"})

        elif method == "repair":
            success = repair_database(db_path, backup=True)
            return jsonify({"success": success, "method": "repair"})

        elif method == "reconstruct":
            arr_instance = data.get("arr_instance")
            if not arr_instance:
                return jsonify({"error": "arr_instance required"}), 400

            # Find the manager instance
            # (Implementation depends on how managers are stored globally)
            # For now, return error
            return jsonify({"error": "Not implemented yet"}), 501

        else:
            return jsonify({"error": "Invalid method"}), 400

    except Exception as e:
        logger.error("Recovery failed: %s", e)
        return jsonify({"error": str(e)}), 500
```

### Expected Outcome
- 🔄 **Complete recovery** from unrecoverable corruption
- 📱 **User-triggered** via WebUI when automatic recovery fails
- ⚠️ **Data loss warning** - loses qBitrr-specific tracking state

---

## Implementation Priority

### Phase 1: Quick Wins (1-2 hours)
✅ **Strategy 1** - Add retry wrapper and apply to critical operations
✅ **Error logging** - Add structured logging for I/O errors

### Phase 2: Proactive Detection (2-3 hours)
✅ **Strategy 2** - Health checks before operations
✅ **Monitoring** - Add metrics for DB operation failures

### Phase 3: Advanced Recovery (4-6 hours)
✅ **Strategy 3** - Automatic repair mechanisms
✅ **Strategy 4** - Circuit breaker implementation

### Phase 4: Nuclear Option (2-3 hours)
✅ **Strategy 5** - Full reconstruction capability
✅ **WebUI integration** - Manual recovery triggers

---

## Configuration Options

Add to `config.toml`:

```toml
[Settings.Database]
# Database retry configuration
RetryAttempts = 5
RetryBackoff = 1.0
RetryMaxBackoff = 15.0

# Circuit breaker configuration
CircuitBreakerThreshold = 5
CircuitBreakerTimeout = 300  # seconds

# Health check configuration
HealthCheckInterval = 10  # check every Nth iteration
AutoRepairEnabled = true

# Recovery options
AutoCheckpointWAL = true
CreateBackupsBeforeRepair = true
MaxBackupAge = 604800  # 7 days in seconds
```

---

## Testing Plan

### Unit Tests
```python
# tests/test_db_recovery.py

def test_retry_wrapper_succeeds_after_transient_failure():
    """Test that retry wrapper succeeds after temporary I/O error."""
    # Mock database operation that fails twice then succeeds
    pass

def test_circuit_breaker_opens_after_threshold():
    """Test circuit breaker opens after failure threshold."""
    pass

def test_database_repair_preserves_data():
    """Test that repair operation preserves existing data."""
    pass
```

### Integration Tests
1. **Simulate I/O error** - Use `LD_PRELOAD` to inject I/O errors on Linux
2. **Full disk scenario** - Test behavior when disk is 100% full
3. **Network storage timeout** - Delay NFS responses to trigger timeouts
4. **Concurrent write conflicts** - Spawn multiple processes writing to DB

### Manual Testing
1. **Corrupt database manually** - Use `sqlite3` to corrupt journal
2. **Monitor logs** during recovery operations
3. **Verify WebUI** recovery endpoints work correctly

---

## Monitoring & Alerting

### Metrics to Track
- `db_io_errors_total` - Counter of I/O errors
- `db_recovery_attempts_total` - Counter of recovery attempts
- `db_recovery_success_rate` - Ratio of successful recoveries
- `db_circuit_breaker_state` - Current circuit breaker state
- `db_operation_duration_seconds` - Histogram of DB operation latency

### Alert Conditions
⚠️ **Warning** - Circuit breaker enters OPEN state
🚨 **Critical** - Database repair failed
🔥 **Emergency** - Reconstruction required

### Log Patterns to Watch
```
ERROR   : qBitrr.* : disk I/O error
WARNING : qBitrr.DBRecovery : Database health check failed
ERROR   : qBitrr.* : Circuit breaker OPEN
CRITICAL: qBitrr.* : Database recovery failed
```

---

## Rollback Plan

If automated recovery causes issues:

1. **Disable retry logic** - Set `RetryAttempts = 0` in config
2. **Disable auto-repair** - Set `AutoRepairEnabled = false`
3. **Restore from backup** - Use timestamped `.db.backup` files
4. **Manual intervention** - Use `sqlite3` CLI to inspect/repair

---

## Future Enhancements

### Short Term
- Add Prometheus metrics endpoint for monitoring
- Create Grafana dashboard for database health
- Email/webhook alerts on circuit breaker open

### Long Term
- **PostgreSQL migration** - Eliminate SQLite limitations
- **Read replicas** - Separate read/write operations
- **Distributed locking** - Use Redis/etcd for better coordination
- **Event sourcing** - Store operations as events for perfect reconstruction

---

## References

- SQLite Documentation: https://www.sqlite.org/recovery.html
- Peewee ORM: http://docs.peewee-orm.com/en/latest/
- Circuit Breaker Pattern: https://martinfowler.com/bliki/CircuitBreaker.html
- qBitrr Database Architecture: `qBitrr/tables.py`, `qBitrr/db_lock.py`

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2025-11-20 | 1.0 | Initial plan created based on disk I/O error analysis |

---

**END OF RECOVERY PLAN**
