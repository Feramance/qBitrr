# Testing

qBitrr testing strategies and guidelines. Currently, qBitrr relies on manual testing with plans for automated testing in the future.

## Current Testing Approach

### Manual Testing

qBitrr uses manual testing against real services:

**Requirements:**
- qBittorrent instance (v4.3+ or v5.0+)
- At least one Arr instance (Radarr, Sonarr, or Lidarr)
- Test torrents with various states
- Test media files for FFprobe validation

**Test Environment Setup:**

Use a dedicated config directory so qBitrr loads your test config:

```bash
# Option 1: Run from a directory that has your test config as config.toml
mkdir -p test-env/.config
cp config.example.toml test-env/.config/config.toml
# Edit test-env/.config/config.toml with test service URLs
cd test-env && qbitrr

# Option 2: Override the config/data path with an environment variable
cp config.example.toml /path/to/test-config/config.toml
# Edit /path/to/test-config/config.toml
export QBITRR_OVERRIDES_DATA_PATH=/path/to/test-config
qbitrr
```

There is no `--config` or `--foreground` CLI flag; qBitrr runs in the foreground by default when started from the command line.

### Testing Checklist

When making changes, test these scenarios:

#### Core Functionality
- [ ] qBitrr starts successfully
- [ ] Connects to qBittorrent
- [ ] Connects to all configured Arr instances
- [ ] WebUI accessible at configured port
- [ ] Logs written to correct location

#### Torrent Processing
- [ ] Detects new torrents added by Arr
- [ ] Tracks torrent download progress
- [ ] Detects torrent completion
- [ ] Triggers import to Arr
- [ ] Updates torrent state in database

#### Health Monitoring
- [ ] Detects stalled torrents
- [ ] Marks torrents with ETA > MaxETA as stalled
- [ ] Handles failed trackers
- [ ] FFprobe validation (if enabled)
- [ ] Blacklists failed torrents

#### Seeding Management
- [ ] Continues seeding after import
- [ ] Tracks seed ratio and time
- [ ] Deletes torrents when seed goals met
- [ ] Respects tracker-specific rules (if configured)

#### Search Features
- [ ] Auto-search for missing content (if enabled)
- [ ] Re-search after blacklisting (if enabled)
- [ ] Search cooldown works correctly
- [ ] Search history recorded in database

#### Configuration
- [ ] Config file changes detected
- [ ] Environment variables override TOML
- [ ] Invalid config generates helpful errors
- [ ] Config validation works (e.g. on save in WebUI or at startup)

#### WebUI
- [ ] Dashboard loads correctly
- [ ] Processes page shows all Arr instances
- [ ] Logs page displays recent logs
- [ ] Arr-specific pages show torrents
- [ ] API endpoints return correct data
- [ ] API authentication works (if token set)

### Docker Testing

```bash
# Build test image
docker build -t qbitrr:test .

# Run with test config
docker run -d \
  --name qbitrr-test \
  -p 6969:6969 \
  -v $(pwd)/test-config.toml:/config/config.toml \
  -v /path/to/downloads:/downloads \
  qbitrr:test

# Check logs
docker logs -f qbitrr-test

# Clean up
docker stop qbitrr-test
docker rm qbitrr-test
```

## Live smoke (compose)

Use the **test-only** stack in [`docker-compose.test.yml`](../../docker-compose.test.yml) (linuxserver qBittorrent + Radarr + qBitrr built from this branch). Data lands under `.compose-test/` (gitignored). Do not use this compose for production.

Host ports (to avoid clashing with local Arr/qBit installs):

| Service | Host | In-compose |
|---------|------|------------|
| qBittorrent WebUI | http://localhost:18080 | `qbittorrent:8080` |
| Radarr | http://localhost:17878 | `radarr:7878` |
| qBitrr WebUI | http://localhost:16969 | `qbitrr:6969` |

### Build

```bash
docker compose -f docker-compose.test.yml build
```

### Checklist (finite; record pass/fail in the PR)

Record results in the PR description (or review notes). Do **not** add a permanent `*_TEST*.md` in the repo root.

1. **Cold start / first-boot (Phase A)** — empty data dir generates `config.toml` and exits cleanly (no `NameError`).
2. **Configured start** — WebUI up; qBit + Arr connected.
3. **Live: `Settings.AutoPauseResume`** — WebUI save changes pause/resume behavior without a full process restart.
4. **Live: Arr LIVE key** — e.g. `EntrySearch.SearchMissing`; worker picks up via live refresh.
5. **Live: FreeSpace** — WebUI save; policy loop reflects the new threshold.
6. **Torrent path (optional fixtures)** — detect / failed or recheck category handling if you can add a torrent.
7. **`RadarrArr` spawn** — after the per-type hierarchy, manager builds `RadarrArr` (and Sonarr/Lidarr if configured).

### Phase A — first-boot (empty config)

```bash
mkdir -p .compose-test/qbitrr-firstboot
docker compose -f docker-compose.test.yml run --rm --no-deps \
  -v "$(pwd)/.compose-test/qbitrr-firstboot:/config" \
  qbitrr
# Expect: exit code 0, message that config.toml was generated, file present under
# .compose-test/qbitrr-firstboot/config.toml, no NameError in logs.
```

Local equivalent (no Docker):

```bash
# Uses the same contract as tests/test_config_first_boot.py
python -m unittest tests.test_config_first_boot -v
```

### Bring up qBit + Radarr

```bash
mkdir -p .compose-test/{qbittorrent,radarr,qbitrr,downloads,media}
docker compose -f docker-compose.test.yml up -d qbittorrent radarr
```

Bootstrap notes:

1. **qBittorrent** — open http://localhost:18080. Username is `admin`; the temporary password is printed in `docker logs qbitrr-test-qbittorrent`. Set a persistent password in the WebUI, set default save path to `/downloads`, and create category `radarr-movies` (save path `/downloads/radarr-movies` is fine).
2. **Radarr** — open http://localhost:17878, complete the wizard (root folder `/movies`). Add a qBittorrent download client pointing at host `qbittorrent`, port `8080`, with category `radarr-movies`. Copy the API key from **Settings → General**.
3. **qBitrr config** — copy the generated `config.toml` into `.compose-test/qbitrr/` (or run Phase A into that directory), then set at least:

```toml
[Settings]
CompletedDownloadFolder = "/downloads"
FreeSpaceFolder = "/downloads"
FreeSpace = "-1"
AutoPauseResume = true

[qBit]
Host = "qbittorrent"
Port = 8080
UserName = "admin"
Password = "<persistent qBit password>"

[Radarr-Movies]
Managed = true
URI = "http://radarr:7878"
APIKey = "<radarr api key>"
Category = "radarr-movies"

[Radarr-Movies.EntrySearch]
SearchMissing = false
```

Disable or leave unmanaged any other Arr sections that still say `CHANGE_ME`.

Generated configs often set `WebUI.AuthDisabled = false` and a random `WebUI.Token`. Use that token for API calls:

```bash
TOKEN=$(rg -oP '(?m)^Token = "\K[^"]+' .compose-test/qbitrr/config.toml)
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:16969/api/processes
```

```bash
docker compose -f docker-compose.test.yml up -d qbitrr
docker logs -f qbitrr-test-qbitrr
# WebUI: http://localhost:16969/ui → /static/index.html
```

### Confirming `RadarrArr`

With a configured stack:

```bash
# Factory wiring (works without live Arr credentials)
docker compose -f docker-compose.test.yml exec qbitrr \
  python -c "from qBitrr.arss.factory import arr_class_for_section as f; print(f('Radarr-Movies').__name__)"
# Expect: RadarrArr

# Live spawn: Arr worker log should show the instance starting
docker logs qbitrr-test-qbitrr 2>&1 | grep -E 'Starting Arr instance: Radarr-Movies|Starting Radarr-Movies monitor|qBitrr\.Radarr-Movies'
```

Unit coverage of the same factory mapping: `tests/test_arss_startup.py`.

### Live-reload checks (items 3–5)

Use the WebUI or `POST /api/config` with `{"changes":{...}}` and a Bearer token:

1. Toggle **Settings.AutoPauseResume** — expect `reloadType: live` and WebUI.log `Live settings changed (no worker restart): Settings.AutoPauseResume` (same worker PIDs).
2. Toggle **Radarr-Movies.EntrySearch.SearchMissing** — expect `Applying live Arr config refresh for: Radarr-Movies` and Radarr-Movies.log `Applied in-place config refresh`.
3. Set **Settings.FreeSpace** / **FreeSpaceFolder** — expect live settings notice; policy loop reads effective FreeSpace on subsequent iterations.

### Tear down

```bash
docker compose -f docker-compose.test.yml down
# Optional: wipe local state
# rm -rf .compose-test
```

### If Docker / images are unavailable

Run Phase A via `tests/test_config_first_boot.py`, run live-reload characterization tests under `tests/`, and exercise the checklist against any existing local qBit + Arr instances. Note in the PR which checklist rows could not be live-smoked.

## Future: Automated Testing

**Planned for v6.0:**

### Unit Tests

Test individual functions and classes:

```python
# tests/test_torrent_processing.py
import pytest
from qBitrr.arss import RadarrManager

def test_torrent_health_check():
    manager = RadarrManager(test_config)

    # Test healthy torrent
    healthy_torrent = {'eta': 1800, 'progress': 0.5}
    assert manager.check_health(healthy_torrent) == 'healthy'

    # Test stalled torrent
    stalled_torrent = {'eta': 7200, 'progress': 0.1}
    assert manager.check_health(stalled_torrent) == 'stalled'
```

**Run with pytest:**

```bash
pytest tests/ -v
pytest tests/test_torrent_processing.py::test_torrent_health_check
```

### Integration Tests

Test components working together:

```python
# tests/integration/test_import_flow.py
def test_full_import_flow(qbit_mock, radarr_mock):
    """Test complete torrent → import → seeding flow."""
    # 1. Add torrent to qBittorrent (mock)
    torrent = qbit_mock.add_torrent(movie_torrent)

    # 2. Wait for completion
    qbit_mock.complete_torrent(torrent.hash)

    # 3. Run qBitrr event loop
    manager.run_once()

    # 4. Verify import triggered
    assert radarr_mock.import_called_with(torrent.hash)

    # 5. Verify database updated
    db_entry = DownloadsModel.get(hash=torrent.hash)
    assert db_entry.state == 'imported'
```

### End-to-End Tests

Prefer the manual finite checklist under [Live smoke (compose)](#live-smoke-compose) with `docker-compose.test.yml`. Automated E2E scripts under `tests/e2e/` are not required for the confidence-hardening smoke.

### Performance Tests

Test performance under load:

```python
# tests/performance/test_event_loop.py
def test_event_loop_with_many_torrents():
    """Ensure event loop completes in reasonable time with 100 torrents."""
    torrents = generate_test_torrents(count=100)

    start = time.time()
    manager.process_torrents(torrents)
    duration = time.time() - start

    assert duration < 10.0, f"Event loop took {duration}s (expected < 10s)"
```

### CI/CD Integration

**GitHub Actions workflow (planned):**

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install -e ".[test]"
      - name: Run unit tests
        run: pytest tests/unit -v
      - name: Run integration tests
        run: pytest tests/integration -v
```

## Test Data

### Sample Configurations

Located in `tests/fixtures/`:

- `valid_config.toml` - Valid configuration
- `invalid_config.toml` - Invalid configuration (for error testing)
- `minimal_config.toml` - Minimal required fields

### Mock Data

```python
# tests/fixtures/torrents.py
SAMPLE_TORRENTS = {
    'downloading': {
        'hash': 'abc123',
        'name': 'Test Movie 2024',
        'progress': 0.5,
        'eta': 1800,
        'state': 'downloading'
    },
    'completed': {
        'hash': 'def456',
        'name': 'Another Movie 2024',
        'progress': 1.0,
        'eta': 0,
        'state': 'uploading'
    },
    'stalled': {
        'hash': 'ghi789',
        'name': 'Stalled Movie',
        'progress': 0.1,
        'eta': 7200,
        'state': 'stalledDL'
    }
}
```

## Debugging Tests

### Enable Debug Logging

```python
# conftest.py
import logging

@pytest.fixture(autouse=True)
def enable_debug_logging():
    logging.basicConfig(level=logging.DEBUG)
```

### Run Single Test

```bash
# Run specific test
pytest tests/test_torrent.py::test_health_check -v

# Run with print statements
pytest tests/test_torrent.py::test_health_check -v -s

# Stop on first failure
pytest tests/ -x
```

### Test Coverage

```bash
# Run tests with coverage
pytest --cov=qBitrr tests/

# Generate HTML coverage report
pytest --cov=qBitrr --cov-report=html tests/
open htmlcov/index.html
```

## Manual Test Scenarios

### Scenario 1: Failed Download

**Setup:**
1. Add movie to Radarr
2. Radarr grabs torrent with no seeders

**Expected Behavior:**
1. qBitrr detects torrent
2. ETA exceeds MaximumETA after StallTimeout
3. Torrent marked as stalled
4. Torrent blacklisted in Radarr
5. New search triggered (if AutoReSearch enabled)

### Scenario 2: Successful Import

**Setup:**
1. Add movie to Radarr
2. Radarr grabs popular torrent

**Expected Behavior:**
1. qBitrr tracks download progress
2. Download completes
3. FFprobe validates file (if enabled)
4. Import triggered in Radarr
5. Torrent continues seeding
6. Deleted when seed goals met

### Scenario 3: Configuration Change

**Setup:**
1. qBitrr running
2. Edit config.toml (e.g. change LoopSleepTimer)

**Expected Behavior:**
1. qBitrr detects config change
2. Reloads configuration
3. Event loops restart with new interval
4. No data loss in database

## Related Documentation

- [Development Guide](index.md) - Complete development setup
- [Contributing](contributing.md) - Contribution guidelines
- [Code Style](code-style.md) - Code formatting rules
