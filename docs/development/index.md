# Development

Contribute to qBitrr development! This guide covers setting up a development environment and contributing code.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Feramance/qBitrr.git
cd qBitrr

# Create virtual environment
make newenv

# Install dependencies
make syncenv

# Run qBitrr
source .venv/bin/activate
python -m qBitrr.main
```

## Development Setup

### Prerequisites

- **Python 3.11+** - Required for qBitrr
- **Node.js 18+** - For WebUI development
- **Git** - Version control
- **Make** - Build automation (optional but recommended)

### Repository Structure

```
qBitrr/
├── qBitrr/          # Python backend
│   ├── __init__.py
│   ├── main.py      # Entry point
│   ├── arss.py      # Arr managers
│   ├── config.py    # Configuration
│   └── webui.py     # Flask API
├── webui/           # React frontend
│   ├── src/
│   ├── public/
│   └── package.json
├── docs/            # MkDocs documentation
├── tests/           # Test suite (manual testing currently)
├── setup.py         # Package setup
├── Makefile         # Build commands
└── pyproject.toml   # Project metadata
```

### Environment Setup

#### Backend Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install in development mode
pip install -e ".[all]"

# Install pre-commit hooks
pre-commit install
```

#### WebUI Development

```bash
# Navigate to WebUI directory
cd webui

# Install dependencies
npm ci

# Start development server
npm run dev

# WebUI will be at http://localhost:5173
```

## Code Style

### Python

qBitrr follows PEP 8 with these tools:

- **Black** - Code formatting (99-char line length)
- **isort** - Import sorting
- **autoflake** - Remove unused imports
- **pyupgrade** - Modernize syntax

**Format code:**
```bash
make reformat
```

**Key conventions:**
- 4-space indentation
- Type hints required
- Docstrings for all public functions
- `snake_case` for functions/variables
- `PascalCase` for classes

### TypeScript/React

WebUI follows these standards:

- **ESLint** - Linting with TypeScript rules
- **Prettier** - Code formatting (via ESLint)
- **2-space indentation**
- **Functional components only**
- **Explicit return types**

**Lint code:**
```bash
cd webui
npm run lint
```

## Making Changes

### Workflow

1. **Create a branch:**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes** - Follow code style guidelines

3. **Test changes:**
   ```bash
   # Run qBitrr locally
   python -m qBitrr.main
   ```

4. **Commit:**
   ```bash
   git add .
   git commit -m "feat: Add my feature"
   ```

5. **Push and create PR:**
   ```bash
   git push origin feature/my-feature
   ```

### Commit Messages

Follow conventional commits:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes
- `refactor:` - Code refactoring
- `test:` - Test additions/changes
- `chore:` - Maintenance tasks

**Examples:**
```
feat: Add support for Lidarr v2.0
fix: Resolve stalled torrent detection issue
docs: Update installation guide for Docker
```

## Testing

### Manual Testing

Currently, qBitrr uses manual testing:

1. **Set up test environment:**
   - qBittorrent instance
   - Arr instance (Radarr/Sonarr/Lidarr)
   - Test torrents

2. **Test scenarios:**
   - Torrent import
   - Health monitoring
   - Failed download handling
   - Configuration changes

### Future: Automated Testing

Planned additions:

- Unit tests with pytest
- Integration tests
- E2E tests for WebUI
- CI/CD test automation

## Building

### Python Package

```bash
# Build wheel
python setup.py sdist bdist_wheel

# Output: dist/qBitrr2-*.whl
```

### WebUI

```bash
cd webui

# Production build
npm run build

# Output: webui/dist/
```

### Docker Image

```bash
# Build Docker image
docker build -t qbitrr:test .

# Test the image
docker run -d \
  --name qbitrr-test \
  -p 6969:6969 \
  -v $(pwd)/config:/config \
  qbitrr:test
```

## Documentation

### Writing Documentation

Documentation uses MkDocs with Material theme:

```bash
# Install docs dependencies
make docs-install

# Serve locally
make docs-serve
# Visit http://127.0.0.1:8000

# Build
make docs-build
```

**Guidelines:**
- Use clear, concise language
- Include code examples
- Add screenshots where helpful
- Test all commands/examples
- Link to related pages

### Documentation Structure

See [docs/README.md](../README.md) for full guidelines.

## Debugging

### Debug Mode

Enable debug logging:

```toml
[Settings]
LogLevel = "DEBUG"
```

### IDE Setup

#### VSCode

Recommended extensions:

- Python
- Pylance
- ESLint
- Prettier
- Docker

**launch.json:**
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: qBitrr",
      "type": "python",
      "request": "launch",
      "module": "qBitrr.main",
      "console": "integratedTerminal"
    }
  ]
}
```

#### PyCharm

1. Create run configuration
2. Script path: `qBitrr/main.py`
3. Enable "Emulate terminal"

## Contributing Guidelines

### Before Submitting

- [ ] Code follows style guidelines
- [ ] Pre-commit hooks pass
- [ ] Changes tested locally
- [ ] Documentation updated
- [ ] Commit messages follow convention

### Pull Request Process

1. **Create descriptive PR:**
   - Clear title
   - Description of changes
   - Related issues (if any)

2. **Code review:**
   - Address review comments
   - Keep PR focused and atomic

3. **CI/CD:**
   - Ensure all checks pass
   - Fix any failing builds

4. **Merge:**
   - Squash commits if needed
   - Delete branch after merge

## Architecture

### Python Backend

qBitrr's backend is built with Python 3.11+ and follows a multiprocessing architecture:

#### Core Components

**Flask/Waitress** - REST API Server
- Flask provides the API routes (`/api/*`, `/web/*`)
- Waitress serves as the production WSGI server
- Token-based authentication for API security
- CORS support for WebUI integration

**Peewee** - SQLite ORM
- Models: `TorrentLibrary`, `MoviesFilesModel`, `SeriesFilesModel`, `AlbumFilesModel`
- WAL mode for concurrent access
- Automatic migrations via `apply_config_migrations()`
- Per-Arr search databases for activity tracking

**Pathos** - Multiprocessing
- Cross-platform multiprocessing support (Windows, Linux, macOS)
- Each Arr instance runs in a separate process
- Inter-process communication via queues
- Automatic process restart on crashes

**Requests** - HTTP Client
- Communication with qBittorrent API
- Communication with Radarr/Sonarr/Lidarr APIs
- Retry logic with exponential backoff
- Session pooling for performance

#### Backend Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         Main Process                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ WebUI Server │  │ Auto-Update  │  │ Network      │     │
│  │ (Flask)      │  │ Watcher      │  │ Monitor      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
          │                    │                   │
          │                    │                   │
┌─────────▼─────────┐  ┌───────▼────────┐  ┌──────▼──────┐
│ Radarr Process 1  │  │ Sonarr Process │  │ Lidarr Proc │
│ ┌───────────────┐ │  │ ┌────────────┐ │  │ ┌─────────┐ │
│ │ Event Loop    │ │  │ │ Event Loop │ │  │ │ Event   │ │
│ │ - Check       │ │  │ │ - Check    │ │  │ │ Loop    │ │
│ │   Torrents    │ │  │ │   Torrents │ │  │ │         │ │
│ │ - Health      │ │  │ │ - Health   │ │  │ │         │ │
│ │   Checks      │ │  │ │   Checks   │ │  │ │         │ │
│ │ - Import      │ │  │ │ - Import   │ │  │ │         │ │
│ │ - Search      │ │  │ │ - Search   │ │  │ │         │ │
│ └───────────────┘ │  │ └────────────┘ │  │ └─────────┘ │
└───────────────────┘  └────────────────┘  └─────────────┘
          │                    │                   │
          └────────────────────┴───────────────────┘
                             │
                    ┌────────▼─────────┐
                    │ SQLite Database  │
                    │ - qbitrr.db      │
                    │ - radarr.db      │
                    │ - sonarr.db      │
                    └──────────────────┘
```

### React Frontend

The WebUI is a modern React SPA built with TypeScript and Mantine components:

#### Frontend Stack

**React 18** - UI Framework
- Functional components with hooks
- Context API for global state (`SearchContext`, `ToastContext`, `WebUIContext`)
- React Router for navigation
- Strict mode enabled

**TypeScript** - Type Safety
- Strict type checking enabled
- Interfaces for all API responses
- Type-safe API client
- No `any` types (use `unknown` if needed)

**Mantine** - Component Library
- v8 with dark/light theme support
- Responsive layout components
- Form validation with `react-hook-form`
- Notifications via `@mantine/notifications`

**Vite** - Build Tool
- Fast HMR (Hot Module Replacement)
- ESBuild for transpilation
- Code splitting and lazy loading
- Environment variable support

**TanStack Table** - Data Tables
- Sorting, filtering, pagination
- Virtual scrolling for large datasets
- Customizable column rendering
- Export functionality

#### Frontend Architecture

```
webui/src/
├── api/
│   ├── client.ts          # Axios client with auth
│   └── types.ts           # TypeScript interfaces
├── components/
│   ├── ConfirmDialog.tsx  # Reusable confirmation
│   ├── LogViewer.tsx      # Log display component
│   ├── ProcessCard.tsx    # Process status card
│   └── ...
├── context/
│   ├── SearchContext.tsx  # Search state management
│   ├── ToastContext.tsx   # Notification system
│   └── WebUIContext.tsx   # Global settings
├── hooks/
│   ├── useDataSync.ts     # Auto-refresh hook
│   ├── useWebSocket.ts    # WebSocket connection
│   └── ...
├── pages/
│   ├── Dashboard.tsx      # Main dashboard
│   ├── Processes.tsx      # Process management
│   ├── Logs.tsx           # Log viewer
│   ├── Radarr.tsx         # Radarr view
│   ├── Sonarr.tsx         # Sonarr view
│   ├── Lidarr.tsx         # Lidarr view
│   └── Config.tsx         # Config editor
└── App.tsx                # Root component
```

### Key Concepts

#### 1. Multiprocessing

Each Arr instance runs in a separate process to:
- Isolate failures (crash in one doesn't affect others)
- Utilize multiple CPU cores
- Allow independent event loop timing
- Simplify state management (each process has own DB connection)

**Implementation:**
```python
# qBitrr/main.py
from pathos.multiprocessing import ProcessingPool

pool = ProcessingPool(nodes=len(arr_instances))
for arr in arr_instances:
    pool.apipe(arr.run)  # Start async process
```

#### 2. Event Loops

Each Arr manager runs an infinite event loop:

```python
# Pseudocode
while True:
    try:
        # 1. Fetch torrents from qBittorrent
        torrents = qbit_client.get_torrents(category=self.category)

        # 2. Check each torrent's health
        for torrent in torrents:
            self.check_torrent_health(torrent)

        # 3. Trigger imports for completed torrents
        self.process_completed_torrents()

        # 4. Search for missing content (if enabled)
        if self.search_enabled:
            self.search_missing_content()

        # 5. Clean up old torrents (seeding limits)
        self.cleanup_completed_torrents()

    except DelayLoopException as e:
        time.sleep(e.delay)
    except RestartLoopException:
        continue

    # Wait before next iteration
    time.sleep(self.loop_delay)
```

#### 3. Health Monitoring

Torrents are monitored for multiple failure conditions:

**Stalled Detection:**
- No download progress for `StalledDelay` seconds
- ETA exceeds `MaximumETA`
- Speed below `MinimumSpeed`

**File Validation:**
- FFprobe checks for playable media
- Detects fake/sample files
- Validates codec support

**Tracker Monitoring:**
- Dead tracker detection
- Timeout handling
- Peer availability checks

**Implementation:**
```python
def check_torrent_health(self, torrent):
    # Stalled check
    if torrent.progress < 1.0 and torrent.eta > self.max_eta:
        self.mark_as_failed(torrent, "ETA exceeded")
        return

    # FFprobe validation
    if torrent.progress == 1.0:
        if not self.validate_with_ffprobe(torrent):
            self.mark_as_failed(torrent, "Invalid media")
            return

    # Tracker check
    if not torrent.trackers or all(t.status == 4 for t in torrent.trackers):
        self.mark_as_failed(torrent, "Dead trackers")
        return
```

#### 4. Instant Import

When a torrent completes, qBitrr immediately triggers import:

```python
def process_completed_torrents(self):
    completed = self.get_completed_torrents()

    for torrent in completed:
        # Skip if already imported
        if self.db.is_imported(torrent.hash):
            continue

        # Validate files
        if not self.validate_files(torrent):
            self.mark_as_failed(torrent)
            continue

        # Trigger import in Arr
        self.arr_client.command("DownloadedMoviesScan", {
            "path": torrent.content_path
        })

        # Mark as imported
        self.db.mark_imported(torrent.hash)
```

#### 5. Database Locking

Multiple processes access the database, so locking is critical:

```python
# qBitrr/db_lock.py
from contextlib import contextmanager

@contextmanager
def locked_database():
    """Thread-safe database access"""
    lock_file = Path(config_dir) / "qbitrr.db.lock"

    with FileLock(lock_file):
        yield
```

**Usage:**
```python
from qBitrr.db_lock import locked_database

with locked_database():
    torrent = TorrentLibrary.get_or_none(Hash=torrent_hash)
    if torrent:
        torrent.Imported = True
        torrent.save()
```

#### 6. Configuration System

Config is loaded from TOML and validated:

```python
# qBitrr/config.py
class MyConfig:
    """Pydantic model for config validation"""

    class Settings:
        LogLevel: str = "INFO"
        FreeSpace: str = "10G"
        AutoPauseResume: bool = True

    class Radarr:
        URL: str
        APIKey: str
        Managed: bool = True
        Category: str = "radarr-movies"

# Load and validate
config = MyConfig.from_toml("config.toml")
```

#### 7. Error Handling

Custom exceptions control event loop flow:

```python
# qBitrr/errors.py
class qBitManagerError(Exception):
    """Base exception"""

class DelayLoopException(qBitManagerError):
    """Delay next loop iteration"""
    def __init__(self, delay: int):
        self.delay = delay

class RestartLoopException(qBitManagerError):
    """Restart loop immediately"""

class SkipException(qBitManagerError):
    """Skip current torrent, continue loop"""
```

**Usage:**
```python
try:
    process_torrent(torrent)
except ConnectionError:
    raise DelayLoopException(30)  # Wait 30s, retry
except InvalidTorrentError:
    raise SkipException()  # Skip this torrent
```

## Common Development Tasks

### Adding a New Feature

**Example: Add email notifications**

1. **Create module:**
   ```python
   # qBitrr/notifications.py
   from email.mime.text import MIMEText
   import smtplib

   class EmailNotifier:
       def __init__(self, smtp_host, smtp_port, from_addr):
           self.smtp_host = smtp_host
           self.smtp_port = smtp_port
           self.from_addr = from_addr

       def send(self, to_addr, subject, body):
           msg = MIMEText(body)
           msg['Subject'] = subject
           msg['From'] = self.from_addr
           msg['To'] = to_addr

           with smtplib.SMTP(self.smtp_host, self.smtp_port) as smtp:
               smtp.send_message(msg)
   ```

2. **Add config options:**
   ```python
   # qBitrr/gen_config.py
   class MyConfig:
       class Notifications:
           Enabled: bool = False
           SMTPHost: str = "smtp.gmail.com"
           SMTPPort: int = 587
           FromEmail: str = ""
           ToEmail: str = ""
   ```

3. **Integrate into event loop:**
   ```python
   # qBitrr/arss.py
   def process_completed_torrents(self):
       for torrent in completed:
           # ... existing import logic ...

           if CONFIG.Notifications.Enabled:
               self.notifier.send(
                   CONFIG.Notifications.ToEmail,
                   f"Import Complete: {torrent.name}",
                   f"Successfully imported {torrent.name}"
               )
   ```

4. **Add WebUI support:**
   ```typescript
   // webui/src/api/types.ts
   export interface NotificationSettings {
     enabled: boolean;
     smtpHost: string;
     smtpPort: number;
     fromEmail: string;
     toEmail: string;
   }
   ```

5. **Update documentation:**
   - Add to `docs/features/notifications.md`
   - Update `docs/configuration/config-file.md`
   - Add example to `docs/getting-started/quickstart.md`

### Adding a New Arr Type

**Example: Add Whisparr support**

1. **Create Arr manager class:**
   ```python
   # qBitrr/arss.py
   class WhisparrManager(ArrManagerBase):
       arr_type = "Whisparr"
       arr_label = "whisparr-movies"

       def _process_failed_individual(self, torrent):
           # Whisparr-specific failure handling
           pass

       def get_missing_content(self):
           # Fetch missing movies from Whisparr
           response = self.client.get("/api/v3/wanted/missing")
           return response.json()
   ```

2. **Add config section:**
   ```python
   # qBitrr/gen_config.py
   class Whisparr:
       URL: str = "http://localhost:6969"
       APIKey: str = ""
       Managed: bool = True
       Category: str = "whisparr-movies"
       # ... rest of Arr config options
   ```

3. **Register in main:**
   ```python
   # qBitrr/main.py
   def start_arr_managers():
       managers = []

       for whisparr_name, whisparr_config in CONFIG.Whisparr.items():
           if whisparr_config.Managed:
               manager = WhisparrManager(whisparr_name, whisparr_config)
               managers.append(manager)

       # ... start managers
   ```

4. **Add WebUI view:**
   ```typescript
   // webui/src/pages/Whisparr.tsx
   export function WhisparrPage() {
     const { data } = useQuery(['whisparr'], () =>
       apiClient.get('/api/whisparr/movies')
     );

     return <MovieTable movies={data} />;
   }
   ```

### Modifying the Database Schema

**Example: Add custom format tracking**

1. **Update model:**
   ```python
   # qBitrr/tables.py
   class MoviesFilesModel(Model):
       # ... existing fields ...
       CustomFormatScore = IntegerField(default=0)
       MinCustomFormatScore = IntegerField(default=0)
       CustomFormatMet = BooleanField(default=False)
   ```

2. **Create migration:**
   ```python
   # qBitrr/config.py
   def apply_config_migrations():
       # ... existing migrations ...

       if current_version < 16:
           # Add new columns
           migrator = SqliteMigrator(database)
           migrate(
               migrator.add_column('moviesfilesmodel', 'CustomFormatScore',
                                 IntegerField(default=0)),
               migrator.add_column('moviesfilesmodel', 'MinCustomFormatScore',
                                 IntegerField(default=0)),
               migrator.add_column('moviesfilesmodel', 'CustomFormatMet',
                                 BooleanField(default=False))
           )
           current_version = 16
   ```

3. **Update config version:**
   ```python
   # qBitrr/config_version.py
   CURRENT_CONFIG_VERSION = 16
   ```

4. **Use new fields:**
   ```python
   # qBitrr/arss.py
   def check_custom_format_score(self, movie):
       movie_db = MoviesFilesModel.get(EntryId=movie.id)

       if movie.customFormatScore >= movie_db.MinCustomFormatScore:
           movie_db.CustomFormatMet = True
           movie_db.save()
   ```

### Adding a WebUI Feature

**Example: Add torrent speed chart**

1. **Create API endpoint:**
   ```python
   # qBitrr/webui.py
   @app.route("/api/stats/speeds", methods=["GET"])
   @token_required
   def get_torrent_speeds():
       speeds = []
       torrents = qbit_client.torrents_info()

       for torrent in torrents:
           speeds.append({
               'name': torrent.name,
               'dlspeed': torrent.dlspeed,
               'upspeed': torrent.upspeed
           })

       return jsonify(speeds)
   ```

2. **Create React component:**
   ```tsx
   // webui/src/components/SpeedChart.tsx
   import { LineChart } from '@mantine/charts';

   export function SpeedChart() {
     const { data } = useQuery(['speeds'],
       () => apiClient.get('/api/stats/speeds'),
       { refetchInterval: 5000 }
     );

     return (
       <LineChart
         data={data}
         dataKey="name"
         series={[
           { name: 'dlspeed', color: 'blue' },
           { name: 'upspeed', color: 'green' }
         ]}
       />
     );
   }
   ```

3. **Add to dashboard:**
   ```tsx
   // webui/src/pages/Dashboard.tsx
   import { SpeedChart } from '../components/SpeedChart';

   export function Dashboard() {
     return (
       <Stack>
         <Title>Dashboard</Title>
         <SpeedChart />
         {/* other components */}
       </Stack>
     );
   }
   ```

### Debugging a Complex Issue

**Example: Torrents not importing**

1. **Enable debug logging:**
   ```toml
   [Settings]
   LogLevel = "DEBUG"
   ```

2. **Check relevant logs:**
   ```bash
   tail -f ~/config/logs/Radarr-Movies.log | grep -i import
   ```

3. **Add debug statements:**
   ```python
   # qBitrr/arss.py
   def process_completed_torrents(self):
       logger.debug(f"Found {len(completed)} completed torrents")

       for torrent in completed:
           logger.debug(f"Processing torrent: {torrent.name}")
           logger.debug(f"Content path: {torrent.content_path}")

           if self.db.is_imported(torrent.hash):
               logger.debug(f"Already imported, skipping")
               continue
   ```

4. **Check database state:**
   ```bash
   sqlite3 ~/config/qbitrr.db << EOF
   SELECT Hash, Category, Imported, AllowedSeeding
   FROM torrentlibrary
   WHERE Hash = 'abc123...';
   EOF
   ```

5. **Test API calls:**
   ```python
   # Test script
   from qBitrr.config import CONFIG
   import requests

   response = requests.post(
       f"{CONFIG.Radarr.URL}/api/v3/command",
       headers={"X-Api-Key": CONFIG.Radarr.APIKey},
       json={"name": "DownloadedMoviesScan", "path": "/downloads/movie"}
   )

   print(response.status_code)
   print(response.json())
   ```

## Performance Optimization

### Database Optimization

**Problem: Slow queries on large libraries**

```python
# Add indexes for frequent queries
from peewee import SQL

# Index for monitored + quality lookups
MoviesFilesModel.add_index(
    SQL('CREATE INDEX IF NOT EXISTS idx_movies_quality '
        'ON moviesfilesmodel(Monitored, QualityMet, CustomFormatMet)')
)

# Index for series + episode lookups
EpisodeFilesModel.add_index(
    SQL('CREATE INDEX IF NOT EXISTS idx_episodes_series '
        'ON episodefilesmodel(SeriesId, SeasonNumber, EpisodeNumber)')
)
```

### API Call Reduction

**Problem: Too many Arr API calls**

```python
# Before: Multiple calls
for movie in movies:
    details = arr_client.get(f"/api/v3/movie/{movie.id}")
    # Process details

# After: Bulk fetch
all_movies = arr_client.get("/api/v3/movie")
movie_map = {m['id']: m for m in all_movies}

for movie in movies:
    details = movie_map[movie.id]
    # Process details
```

### Memory Optimization

**Problem: High memory usage with large libraries**

```python
# Use generators instead of lists
def get_missing_movies(self):
    page = 1
    while True:
        response = self.client.get(f"/api/v3/wanted/missing?page={page}")
        movies = response.json()['records']

        if not movies:
            break

        for movie in movies:
            yield movie  # Generator, not list

        page += 1

# Usage
for movie in self.get_missing_movies():
    # Process one at a time, not all in memory
    self.search_for_movie(movie)
```

## Testing Strategies

### Unit Testing (Future)

```python
# tests/test_torrent_health.py
import pytest
from qBitrr.arss import RadarrManager

def test_stalled_detection():
    """Test that stalled torrents are detected"""
    manager = RadarrManager("test", config)

    torrent = MockTorrent(
        hash="abc123",
        progress=0.5,
        eta=999999,  # Very high ETA
        dlspeed=0
    )

    result = manager.check_torrent_health(torrent)
    assert result == "stalled"

def test_ffprobe_validation():
    """Test FFprobe validates valid files"""
    manager = RadarrManager("test", config)

    # Mock FFprobe response
    with patch('qBitrr.ffprobe.validate') as mock_ffprobe:
        mock_ffprobe.return_value = True

        result = manager.validate_files("/path/to/movie.mkv")
        assert result is True
```

### Integration Testing

```python
# tests/integration/test_import_flow.py
import pytest
from qBitrr import main
from qBitrr.config import CONFIG

@pytest.mark.integration
def test_full_import_flow():
    """Test complete import workflow"""
    # 1. Add torrent to qBittorrent
    qbit_client.add_torrent(test_torrent_url, category="radarr-movies")

    # 2. Wait for completion (mock or fast torrent)
    time.sleep(10)

    # 3. Check that qBitrr triggered import
    imports = radarr_client.get("/api/v3/queue")
    assert len(imports) > 0

    # 4. Verify database state
    torrent_db = TorrentLibrary.get(Hash=test_hash)
    assert torrent_db.Imported is True
```

### Manual Testing Checklist

When testing changes manually:

- [ ] **Fresh install** - Test with new config
- [ ] **Migration** - Test upgrading from previous version
- [ ] **Multiple Arr instances** - Test with 2+ of each type
- [ ] **Failed torrents** - Test stalled, corrupted, dead trackers
- [ ] **Successful imports** - Test movies, TV shows, music
- [ ] **Search automation** - Test missing content search
- [ ] **WebUI** - Test all pages and actions
- [ ] **API** - Test all endpoints with/without token
- [ ] **Edge cases** - Empty libraries, network errors, disk full

## Resources

### Official Resources

- **Repository:** [github.com/Feramance/qBitrr](https://github.com/Feramance/qBitrr)
- **Issues:** [github.com/Feramance/qBitrr/issues](https://github.com/Feramance/qBitrr/issues)
- **Discussions:** [github.com/Feramance/qBitrr/discussions](https://github.com/Feramance/qBitrr/discussions)
- **PyPI:** [pypi.org/project/qBitrr2/](https://pypi.org/project/qBitrr2/)
- **Docker Hub:** [hub.docker.com/r/feramance/qbitrr](https://hub.docker.com/r/feramance/qbitrr)

### Development Guides

- **AGENTS.md** - Comprehensive development guidelines for AI agents
- **CONTRIBUTION.md** - Contribution guidelines and code of conduct
- **API_DOCUMENTATION.md** - Complete API reference with examples

### External Documentation

- **qBittorrent API:** [github.com/qbittorrent/qBittorrent/wiki/WebUI-API](https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1))
- **Radarr API:** [radarr.video/docs/api/](https://radarr.video/docs/api/)
- **Sonarr API:** [sonarr.tv/docs/api/](https://sonarr.tv/docs/api/)
- **Lidarr API:** [lidarr.audio/docs/api/](https://lidarr.audio/docs/api/)
- **Peewee ORM:** [docs.peewee-orm.com](http://docs.peewee-orm.com/)
- **Flask:** [flask.palletsprojects.com](https://flask.palletsprojects.com/)
- **React:** [react.dev](https://react.dev/)
- **Mantine:** [mantine.dev](https://mantine.dev/)

## Community

### Getting Help

- **GitHub Discussions** - Ask questions, share ideas
- **GitHub Issues** - Report bugs, request features
- **Discord** - Real-time chat with community and maintainers
- **Reddit** - r/qBitrr for community support

### Contributing

We welcome contributions of all types:

- **Code** - Bug fixes, new features, performance improvements
- **Documentation** - Guides, examples, typo fixes
- **Testing** - Manual testing, bug reports, edge case discovery
- **Design** - WebUI improvements, icons, themes
- **Translations** - Internationalization support (future)

### Recognition

Contributors are recognized in:

- **README.md** - Contributors section with avatars
- **Release Notes** - Feature/fix attribution
- **GitHub Contributors Graph** - Automatic tracking
- **Special Thanks** - Major contributors get shoutouts

### Code of Conduct

We follow the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/):

- Be respectful and inclusive
- Accept constructive criticism
- Focus on what's best for the community
- Show empathy towards others

## Release Process

### Versioning

qBitrr follows [Semantic Versioning](https://semver.org/):

- **MAJOR** - Breaking changes (e.g., 5.0.0 → 6.0.0)
- **MINOR** - New features, backwards compatible (e.g., 5.1.0 → 5.2.0)
- **PATCH** - Bug fixes (e.g., 5.1.1 → 5.1.2)

### Release Workflow

1. **Prepare release:**
   ```bash
   # Update version
   bump2version minor  # or major/patch

   # Generate changelog
   make changelog
   ```

2. **Create release:**
   ```bash
   # Tag and push
   git push origin master --tags
   ```

3. **Automated CI/CD:**
   - Build Python package → publish to PyPI
   - Build Docker image → publish to Docker Hub
   - Generate GitHub release notes
   - Update documentation

4. **Announce:**
   - GitHub Releases
   - Discord announcement
   - Reddit post
   - Update documentation site

## License

qBitrr is licensed under the **MIT License**. See [LICENSE](https://github.com/Feramance/qBitrr/blob/master/LICENSE) for full details.

### What This Means

✅ Commercial use allowed
✅ Modification allowed
✅ Distribution allowed
✅ Private use allowed
❌ Liability - Software provided "as is"
❌ Warranty - No warranty provided

## Next Steps

Ready to contribute? Here's how to get started:

1. **⭐ Star the repository** - Show your support!
2. **🍴 Fork the repository** - Create your own copy
3. **💻 Set up development environment** - Follow the setup guide above
4. **🔍 Pick an issue** - Look for "good first issue" label
5. **🚀 Submit a pull request** - Share your contribution!

### Good First Issues

Looking for something to work on? Check out issues labeled:

- `good first issue` - Beginner-friendly tasks
- `help wanted` - Community input needed
- `documentation` - Docs improvements
- `enhancement` - Feature requests
- `bug` - Bug fixes needed

### Questions?

- 💬 **Ask in Discussions** - [github.com/Feramance/qBitrr/discussions](https://github.com/Feramance/qBitrr/discussions)
- 📧 **Email maintainers** - See CONTRIBUTION.md for contact info
- 🐛 **Report bugs** - [github.com/Feramance/qBitrr/issues/new](https://github.com/Feramance/qBitrr/issues/new)

---

Thank you for contributing to qBitrr! Every contribution, big or small, helps make qBitrr better for everyone. 🚀

---

## Related Documentation

- [Installation Guide](../getting-started/installation/index.md) - Install qBitrr for development
- [Configuration Reference](../configuration/config-file.md) - All config options
- [API Reference](../reference/api.md) - REST API documentation
- [Troubleshooting](../troubleshooting/index.md) - Common development issues
- [FAQ](../faq.md) - Frequently asked questions
