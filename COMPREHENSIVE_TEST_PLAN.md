# Comprehensive Test Plan - Database Consolidation Branch

## Test Objectives

Verify that after database consolidation, all functionality works as it did prior to changes:

1. ✅ Database persistence across restarts
2. ✅ Data isolation between Arr instances
3. ✅ Search functionality
4. ✅ Torrent health monitoring
5. ✅ Import functionality
6. ✅ WebUI accessibility and features
7. ✅ Configuration management
8. ✅ Process management
9. ✅ Logging and error handling
10. ✅ Auto-update functionality

---

## Test Environment

- **Docker**: Using docker-compose
- **Arr Instances**: 7 total (Sonarr-TV, Sonarr-4K, Sonarr-Anime, Radarr-1080, Radarr-4K, Radarr-Anime, Lidarr)
- **Database**: Single consolidated qbitrr.db
- **WebUI**: Port 6969

---

## Test Execution

### Test 1: Clean Build and Startup ✅

**Steps:**
1. Rebuild Docker image
2. Start container
3. Check logs for errors
4. Verify database creation

**Commands:**
```bash
docker compose build
docker compose up -d
sleep 10
docker compose logs qbitrr --tail=100
```

**Expected Results:**
- ✅ Build successful
- ✅ Container starts
- ✅ Database created: /config/qBitManager/qbitrr.db
- ✅ All Arr instances initialize
- ✅ No ERROR messages related to database

---

### Test 2: Database Persistence ✅

**Steps:**
1. Check database exists
2. Verify data is being written
3. Restart container
4. Verify database still exists
5. Verify data persists

**Commands:**
```bash
docker compose exec qbitrr ls -lh /config/qBitManager/qbitrr.db
docker compose restart qbitrr
sleep 10
docker compose exec qbitrr ls -lh /config/qBitManager/qbitrr.db
```

**Expected Results:**
- ✅ Database file exists
- ✅ Database grows over time
- ✅ Database persists after restart
- ✅ No "Deleted database files" message on subsequent restarts

---

### Test 3: Multi-Instance Data Isolation ✅

**Steps:**
1. Check logs for multiple Arr instances
2. Verify each instance is updating database
3. Check that data is tagged with ArrInstance

**Commands:**
```bash
docker compose logs qbitrr | grep "Started updating database"
docker compose logs qbitrr | grep "Updating database entry"
```

**Expected Results:**
- ✅ All 7 Arr instances active
- ✅ Each instance writing to database
- ✅ No cross-contamination of data

---

### Test 4: WebUI Accessibility ✅

**Steps:**
1. Access WebUI at http://localhost:6969/ui
2. Navigate to all tabs
3. Check for console errors
4. Verify data displays correctly

**Tabs to Test:**
- Processes
- Logs
- Radarr (all instances)
- Sonarr (all instances)
- Lidarr
- Config

**Expected Results:**
- ✅ WebUI loads successfully
- ✅ All tabs accessible
- ✅ No JavaScript errors
- ✅ Data displays correctly
- ✅ RemoveTorrent dropdown works

---

### Test 5: Configuration Management ✅

**Steps:**
1. Open Config tab in WebUI
2. Navigate to RemoveTorrent setting
3. Verify dropdown displays correctly
4. Change value
5. Save configuration
6. Reload and verify change persisted

**Expected Results:**
- ✅ RemoveTorrent shows as dropdown
- ✅ Options display correctly
- ✅ Can select different options
- ✅ Save works
- ✅ Config persists after reload

---

### Test 6: Search Functionality ✅

**Steps:**
1. Check search loop processes are running
2. Monitor logs for search activity
3. Verify search database entries

**Commands:**
```bash
docker compose logs qbitrr | grep "search_loop"
docker compose logs qbitrr | grep "Searched"
```

**Expected Results:**
- ✅ Search processes running for all instances
- ✅ Search activity logged
- ✅ Database tracks search state

---

### Test 7: Torrent Health Monitoring ✅

**Steps:**
1. Check torrent loop processes
2. Monitor health check activity
3. Verify torrent tracking

**Commands:**
```bash
docker compose logs qbitrr | grep "torrent_loop"
docker compose logs qbitrr | grep "health"
```

**Expected Results:**
- ✅ Torrent processes running
- ✅ Health checks executing
- ✅ Torrents tracked in database

---

### Test 8: Import Functionality ✅

**Steps:**
1. Check for import activity in logs
2. Verify completed torrents are processed
3. Check import queue tracking

**Commands:**
```bash
docker compose logs qbitrr | grep -i "import"
docker compose logs qbitrr | grep "queue"
```

**Expected Results:**
- ✅ Import activity detected
- ✅ Queue tracking working
- ✅ Completed items processed

---

### Test 9: Process Management ✅

**Steps:**
1. Check all processes started
2. Verify process count matches expected
3. Check for process crashes

**Commands:**
```bash
docker compose logs qbitrr | grep "Started.*worker process"
docker compose logs qbitrr | grep -i "crash\|died\|failed"
```

**Expected Results:**
- ✅ All worker processes started
- ✅ 17 processes: 7 Arr instances × 2 (search + torrent) + 3 special
- ✅ No process crashes

---

### Test 10: Error Handling ✅

**Steps:**
1. Check logs for ERROR messages
2. Verify error recovery mechanisms
3. Check database error handling

**Commands:**
```bash
docker compose logs qbitrr | grep "ERROR" | grep -v "qBittorrent API" | head -20
docker compose logs qbitrr | grep -i "recovery\|retry"
```

**Expected Results:**
- ✅ No database-related ERRORs
- ✅ Transient errors handled gracefully
- ✅ Retry mechanisms working

---

### Test 11: Logging System ✅

**Steps:**
1. Verify log files created
2. Check log rotation
3. Verify log levels working

**Commands:**
```bash
docker compose exec qbitrr ls -lh /config/logs/
docker compose logs qbitrr | grep -E "DEBUG|INFO|WARNING|ERROR" | tail -20
```

**Expected Results:**
- ✅ Log files created
- ✅ Main.log exists
- ✅ Per-Arr logs exist
- ✅ Log levels correct

---

### Test 12: Database Schema Verification ✅

**Steps:**
1. Check database tables exist
2. Verify ArrInstance field present
3. Check data integrity

**Commands:**
```bash
docker compose exec qbitrr sqlite3 /config/qBitManager/qbitrr.db ".tables" 2>/dev/null || echo "sqlite3 not available"
docker compose exec qbitrr ls -lh /config/qBitManager/qbitrr.db*
```

**Expected Results:**
- ✅ Database file exists
- ✅ WAL and SHM files present
- ✅ Database growing with activity

---

### Test 13: Memory and Performance ✅

**Steps:**
1. Check container memory usage
2. Verify CPU usage reasonable
3. Check database size

**Commands:**
```bash
docker stats qbitrr --no-stream
docker compose exec qbitrr du -h /config/qBitManager/qbitrr.db*
```

**Expected Results:**
- ✅ Memory usage stable
- ✅ CPU usage reasonable
- ✅ Database size growing normally

---

### Test 14: Auto-Update Check ✅

**Steps:**
1. Verify auto-update scheduler running
2. Check update check frequency
3. Verify version detection

**Commands:**
```bash
docker compose logs qbitrr | grep -i "auto update\|version"
```

**Expected Results:**
- ✅ Auto-update scheduler active
- ✅ Cron schedule configured
- ✅ Version checks working

---

### Test 15: Network Connectivity ✅

**Steps:**
1. Check qBittorrent connection
2. Check Arr instance connections
3. Verify internet connectivity checks

**Commands:**
```bash
docker compose logs qbitrr | grep -i "connect\|alive"
docker compose logs qbitrr | grep "ping"
```

**Expected Results:**
- ✅ qBittorrent connected
- ✅ All Arr instances connected
- ✅ Network checks passing

---

## Regression Tests

### Regression 1: Old Database Migration ✅

**Test:** Start with old per-instance databases

**Steps:**
1. Stop container
2. Create fake old database files
3. Start container
4. Verify old databases deleted
5. Verify new database created

**Expected Results:**
- ✅ Old databases deleted on startup
- ✅ New consolidated database created
- ✅ Migration message logged

---

### Regression 2: Database Corruption Recovery ✅

**Test:** Verify database recovery mechanisms work

**Steps:**
1. Monitor for database errors
2. Check auto-recovery triggers
3. Verify backup creation

**Expected Results:**
- ✅ Recovery mechanisms active
- ✅ Backups created when needed
- ✅ No data loss

---

### Regression 3: Multiple Restarts ✅

**Test:** Verify stability across multiple restarts

**Steps:**
1. Restart container 5 times
2. Check database consistency
3. Verify no data corruption

**Expected Results:**
- ✅ Database persists across all restarts
- ✅ Data remains consistent
- ✅ No corruption detected

---

## Summary Template

```
═══════════════════════════════════════════════════════════
COMPREHENSIVE TEST RESULTS - Database Consolidation Branch
═══════════════════════════════════════════════════════════

Total Tests: 18
Passed: __/__
Failed: __/__
Skipped: __/__

Critical Tests:
✅/❌ Database Persistence
✅/❌ Multi-Instance Isolation
✅/❌ WebUI Functionality
✅/❌ Configuration Management
✅/❌ Search Functionality
✅/❌ Torrent Health Monitoring
✅/❌ Import Functionality
✅/❌ Process Management
✅/❌ Error Handling
✅/❌ Logging System

Regression Tests:
✅/❌ Old Database Migration
✅/❌ Database Corruption Recovery
✅/❌ Multiple Restarts

Performance:
Memory Usage: ___ MB
CPU Usage: ____%
Database Size: ___ MB

Issues Found: ___
- [ ] Issue 1: Description
- [ ] Issue 2: Description

Overall Status: ✅ PASS / ❌ FAIL
Ready for Merge: YES / NO

═══════════════════════════════════════════════════════════
```

---

## Test Execution Log

**Date**: January 26, 2026
**Branch**: feature/db-consolidation
**Tester**: Claude Code (AI)
**Environment**: Docker Compose

Tests will be executed in order below...
