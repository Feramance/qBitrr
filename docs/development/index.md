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
├── tests/           # Test suite (coming soon)
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

- **Flask/Waitress** - REST API server
- **Peewee** - SQLite ORM
- **Pathos** - Multiprocessing
- **Requests** - HTTP client

### React Frontend

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Mantine** - Component library
- **Vite** - Build tool
- **TanStack Table** - Data tables

### Key Concepts

1. **Multiprocessing** - Each Arr instance runs in separate process
2. **Event Loops** - Periodic torrent checking
3. **Health Monitoring** - FFprobe validation, stall detection
4. **Instant Import** - Trigger imports on completion

## Resources

- **Repository:** https://github.com/Feramance/qBitrr
- **Issues:** https://github.com/Feramance/qBitrr/issues
- **Discussions:** https://github.com/Feramance/qBitrr/discussions
- **AGENTS.md:** Development guidelines for AI agents

## Community

### Getting Help

- **Discord** - Real-time chat
- **GitHub Discussions** - Q&A and ideas
- **GitHub Issues** - Bug reports and feature requests

### Recognition

Contributors are recognized in:

- README.md contributors section
- Release notes
- GitHub contributor graph

## License

qBitrr is licensed under the MIT License. See [LICENSE](https://github.com/Feramance/qBitrr/blob/master/LICENSE) for details.

## Next Steps

Ready to contribute?

1. Fork the repository
2. Set up development environment
3. Pick an issue or feature
4. Submit a pull request!

Thank you for contributing to qBitrr! 🚀
