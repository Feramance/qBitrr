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

```bash
# 1. Set up test config
cp config.example.toml test-config.toml

# Edit test-config.toml with test service URLs

# 2. Run qBitrr with test config
qbitrr --config test-config.toml --foreground
```

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
- [ ] Config validation works (--validate-config)

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

Test against real services (Docker Compose):

```yaml
# docker-compose.test.yml
services:
  qbittorrent:
    image: linuxserver/qbittorrent
    # ...

  radarr:
    image: linuxserver/radarr
    # ...

  qbitrr:
    build: .
    depends_on:
      - qbittorrent
      - radarr
    # ...
```

```bash
# Run E2E tests
docker-compose -f docker-compose.test.yml up -d
python tests/e2e/test_real_services.py
docker-compose -f docker-compose.test.yml down
```

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
2. Edit config.toml (change CheckInterval)

**Expected Behavior:**
1. qBitrr detects config change
2. Reloads configuration
3. Event loops restart with new interval
4. No data loss in database

## Related Documentation

- [Development Guide](index.md) - Complete development setup
- [Contributing](contributing.md) - Contribution guidelines
- [Code Style](code-style.md) - Code formatting rules
