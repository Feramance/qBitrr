# Code Style

qBitrr follows strict code style guidelines to ensure consistency and maintainability.

## Python Code Style

### PEP 8 + Black

qBitrr uses **Black** code formatter with **99-character line length**:

```bash
# Format all Python code
make reformat

# Or manually
black --line-length 99 qBitrr/
```

### Import Sorting

**isort** with Black profile:

```python
# Stdlib imports
import json
import logging
from pathlib import Path

# Third-party imports
import requests
from peewee import Model, CharField

# Local imports
from qBitrr.config import CONFIG
from qBitrr.errors import qBitManagerError
```

**Configuration:**

```toml
# pyproject.toml
[tool.isort]
profile = "black"
line_length = 99
known_third_party = ["requests", "peewee", "flask", ...]
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Variables | `snake_case` | `torrent_hash`, `arr_instance` |
| Functions | `snake_case` | `process_torrent()`, `check_health()` |
| Classes | `PascalCase` | `ArrManager`, `RadarrManager` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Private methods | `_snake_case` | `_internal_helper()` |
| Module names | `snake_case` | `arr_manager.py`, `config.py` |

### Type Hints

**Required** for all function signatures:

```python
from typing import Optional, List, Dict

def process_torrent(
    torrent_hash: str,
    arr_name: str,
    retry_count: int = 0
) -> bool:
    """Process a torrent for import.

    Args:
        torrent_hash: The torrent hash
        arr_name: Name of Arr instance
        retry_count: Number of retries attempted

    Returns:
        True if processed successfully, False otherwise

    Raises:
        SkipException: If torrent should be skipped
        ArrManagerException: If Arr communication fails
    """
    pass
```

**Use forward references for circular dependencies:**

```python
from __future__ import annotations

class ArrManager:
    def get_torrent(self, hash: str) -> Torrent:
        ...
```

### Docstrings

**Required** for all public classes and functions:

```python
def check_torrent_health(torrent: Dict) -> str:
    """Check if torrent is healthy and downloading properly.

    Performs multiple health checks:
    - ETA vs maximum allowed ETA
    - Stall time vs stall threshold
    - Tracker status

    Args:
        torrent: Torrent dictionary from qBittorrent API

    Returns:
        Health status: 'healthy', 'stalled', 'failed', or 'completed'

    Raises:
        SkipException: If torrent doesn't match our criteria
    """
    pass
```

### Error Handling

**Always** inherit from `qBitManagerError`:

```python
# qBitrr/errors.py
class CustomException(qBitManagerError):
    """Exception for custom error case."""

    def __init__(self, torrent_hash: str, reason: str):
        self.torrent_hash = torrent_hash
        self.reason = reason
        super().__init__(f"Torrent {torrent_hash} failed: {reason}")
```

**Provide context in exceptions:**

```python
# Bad
raise ValueError("Invalid value")

# Good
raise ConfigException(
    f"Invalid CheckInterval: {value}. Must be between 10 and 3600 seconds."
)
```

### Line Breaks

**Unix line endings (LF) only:**

Pre-commit hook enforces:
```yaml
# .pre-commit-config.yaml
- id: mixed-line-ending
  args: ['--fix=lf']
```

### Indentation

**4 spaces** (no tabs):

```python
def example():
    if condition:
        do_something()
        if nested:
            do_more()
```

## TypeScript/React Code Style

### ESLint Configuration

```bash
# Lint WebUI code
cd webui
npm run lint

# Auto-fix issues
npm run lint -- --fix
```

### TypeScript Standards

**Strict mode enabled:**

```typescript
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true
  }
}
```

**Explicit return types:**

```typescript
// Bad
function fetchTorrents() {
  return api.get('/torrents')
}

// Good
function fetchTorrents(): Promise<Torrent[]> {
  return api.get<Torrent[]>('/torrents')
}
```

**Interfaces over types (unless needed):**

```typescript
// Preferred
interface Torrent {
  hash: string
  name: string
  progress: number
}

// Only use type for unions/intersections
type TorrentState = 'downloading' | 'completed' | 'failed'
```

### React Component Style

**Functional components only:**

```typescript
import { FC } from 'react'

interface Props {
  torrent: Torrent
  onDelete: (hash: string) => void
}

const TorrentCard: FC<Props> = ({ torrent, onDelete }) => {
  return (
    <Card>
      <Text>{torrent.name}</Text>
      <Button onClick={() => onDelete(torrent.hash)}>Delete</Button>
    </Card>
  )
}

export default TorrentCard
```

**Hooks naming:**

```typescript
// Custom hooks start with 'use'
function useDataSync(interval: number) {
  const [data, setData] = useState(null)

  useEffect(() => {
    const timer = setInterval(() => fetchData(), interval)
    return () => clearInterval(timer)
  }, [interval])

  return data
}
```

### Naming Conventions (TypeScript)

| Element | Convention | Example |
|---------|------------|---------|
| Variables | `camelCase` | `torrentHash`, `arrInstance` |
| Functions | `camelCase` | `processTorrent()`, `checkHealth()` |
| Components | `PascalCase` | `TorrentCard`, `LogViewer` |
| Interfaces | `PascalCase` | `Torrent`, `ArrConfig` |
| Types | `PascalCase` | `TorrentState`, `ApiResponse` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_RETRIES`, `API_BASE_URL` |

### Import Order (TypeScript)

```typescript
// React imports
import { FC, useState, useEffect } from 'react'

// Third-party libraries
import { Button, Card, Text } from '@mantine/core'
import axios from 'axios'

// Local modules
import { api } from '@/api/client'
import { Torrent } from '@/api/types'

// Local components
import TorrentCard from '@/components/TorrentCard'

// Icons/assets
import DeleteIcon from '@/icons/Delete.svg'
```

### Indentation (TypeScript)

**2 spaces:**

```typescript
function example() {
  if (condition) {
    doSomething()
    if (nested) {
      doMore()
    }
  }
}
```

## General Guidelines

### Comments

**When to comment:**

- Complex algorithms that aren't immediately obvious
- Business logic rationale
- Workarounds for bugs in dependencies
- TODO items with issue numbers

**When NOT to comment:**

- Obvious code (`i++  # increment i`)
- Outdated comments
- Commented-out code (use git history instead)

**Good comments:**

```python
# Workaround for qBittorrent API v4.3.9 bug where category is null
# for torrents with uppercase tags. Fixed in v4.4.0.
# See: https://github.com/qbittorrent/qBittorrent/issues/12345
if torrent.get('category') is None and torrent.get('tags'):
    torrent['category'] = self.default_category
```

### Logging

**Use appropriate log levels:**

```python
logger.debug("Checking torrent %s", torrent_hash)  # Verbose details
logger.info("Imported torrent %s to Radarr", torrent_hash)  # User-facing
logger.warning("ETA exceeds threshold for %s", torrent_hash)  # Potential issue
logger.error("Failed to connect to qBittorrent")  # Error occurred
logger.critical("Database corrupted, shutting down")  # Fatal error
```

**Use lazy formatting:**

```python
# Good - string formatting only if log level enabled
logger.debug("Processing %s with config %s", torrent_hash, config)

# Bad - always formats string
logger.debug(f"Processing {torrent_hash} with config {config}")
```

## Automated Enforcement

### Pre-commit Hooks

Install pre-commit hooks:

```bash
pre-commit install
```

**Hooks run automatically on commit:**

- `black` - Code formatting
- `isort` - Import sorting
- `autoflake` - Remove unused imports/variables
- `pyupgrade` - Modernize Python syntax
- `check-yaml` - Validate YAML files
- `check-toml` - Validate TOML files
- `check-json` - Validate JSON files
- `detect-private-key` - Prevent committing secrets
- `end-of-file-fixer` - Ensure files end with newline
- `trailing-whitespace` - Remove trailing whitespace
- `mixed-line-ending` - Enforce LF line endings

### Run Manually

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files

# Skip hooks (emergency only)
git commit --no-verify
```

### CI/CD Enforcement

**pre-commit.ci** runs on all pull requests:

- Auto-fixes formatting issues
- Pushes fixes to your branch
- Fails if unfixable issues found

## IDE Configuration

### VS Code

**Recommended extensions:**

- Python (Microsoft)
- Pylance
- Black Formatter
- ESLint
- Prettier
- Better Comments

**settings.json:**

```json
{
  "python.linting.enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "python.linting.pylintEnabled": false,
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```

### PyCharm

1. Settings → Tools → Black
   - Enable "On save"
   - Path: `.venv/bin/black`
   - Arguments: `--line-length 99`

2. Settings → Tools → isort
   - Enable on save

3. Settings → Editor → Code Style → Python
   - Set line length to 99

## Style Exceptions

Sometimes rules need to be broken. Use sparingly:

```python
# fmt: off
matrix = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9]
]
# fmt: on

# noqa: E501 - Ignore line too long for this line only
very_long_url = "https://example.com/very/long/url/that/exceeds/line/limit"  # noqa: E501

# type: ignore - Ignore type checking for this line
result = untyped_library_function()  # type: ignore
```

## Related Documentation

- [Contributing](contributing.md) - Contribution guidelines
- [Development Guide](index.md) - Complete development setup
- [Testing](testing.md) - Testing your code
- [AGENTS.md](https://github.com/Feramance/qBitrr/blob/master/AGENTS.md) - AI agent coding guidelines
