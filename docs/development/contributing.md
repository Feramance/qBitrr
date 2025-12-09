# Contributing

Thank you for contributing to qBitrr! This guide covers how to contribute effectively.

## Quick Start

1. **Fork the repository** on GitHub
2. **Clone your fork:**
   ```bash
   git clone https://github.com/your-username/qBitrr.git
   cd qBitrr
   ```
3. **Set up development environment:**
   ```bash
   make newenv    # Create virtual environment
   make syncenv   # Install dependencies
   ```
4. **Create a branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```
5. **Make your changes** (see [Code Style](code-style.md))
6. **Test your changes** locally
7. **Commit using conventional commits** (see below)
8. **Push and create a pull request**

## Before Submitting

Ensure your contribution meets these requirements:

- [ ] Code follows [style guidelines](code-style.md)
- [ ] Pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] Changes tested locally with live qBittorrent + Arr instances
- [ ] Documentation updated (if adding features)
- [ ] Commit messages follow conventional commits format

## Commit Message Format

Use conventional commits format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, no logic change)
- `refactor:` - Code refactoring (no behavior change)
- `perf:` - Performance improvements
- `test:` - Test additions or changes
- `chore:` - Maintenance tasks (dependencies, build, etc.)
- `ci:` - CI/CD changes

### Examples

```bash
# Good commit messages
feat(radarr): add support for custom quality profiles
fix(webui): resolve API token validation error
docs(advanced): add FFprobe integration guide
refactor(arss): simplify event loop error handling
test(tables): add unit tests for database models

# Bad commit messages
fix bug
update stuff
WIP
changes
```

### Scope

Optional, but helpful for large projects:

- `radarr`, `sonarr`, `lidarr` - Arr-specific changes
- `webui` - Web interface changes
- `config` - Configuration system changes
- `db` - Database changes
- `api` - API changes
- `docs` - Documentation changes

## Pull Request Process

### 1. Create Descriptive PR

**Title:**
- Clear and concise
- Follows conventional commits format
- Example: `feat(radarr): add support for custom formats`

**Description template:**

```markdown
## Description
Brief description of what this PR does.

## Motivation
Why is this change needed? What problem does it solve?

## Changes
- Change 1
- Change 2
- Change 3

## Testing
How was this tested?
- [ ] Tested with qBittorrent v4.6.0
- [ ] Tested with Radarr v5.0.0
- [ ] Tested in Docker
- [ ] Tested native install

## Screenshots (if applicable)
Add screenshots for WebUI changes.

## Related Issues
Closes #123
Fixes #456
```

### 2. Code Review

**Be responsive:**
- Address reviewer comments promptly
- Explain your reasoning if you disagree
- Be open to suggestions

**Keep PR focused:**
- One feature/fix per PR
- Don't mix unrelated changes
- Split large changes into multiple PRs

**Update as needed:**
- Rebase on latest `master` if requested
- Fix merge conflicts
- Add requested changes

### 3. CI/CD Checks

All checks must pass:

- **pre-commit.ci** - Code formatting and linting
- **CodeQL** - Security analysis (for Python changes)

If checks fail:
1. Review the error logs
2. Fix issues locally
3. Push fixes
4. Wait for checks to re-run

### 4. Merge

Once approved:
- Maintainer will merge your PR
- Squash commits if needed for clean history
- Your contribution will be in the next release!

## What to Contribute

### Good First Issues

Look for issues labeled `good first issue`:

- Simple bug fixes
- Documentation improvements
- Code formatting/cleanup
- Test additions

### Feature Requests

Before implementing a feature:
1. Check if there's an existing feature request issue
2. If not, create one to discuss the feature
3. Wait for maintainer feedback before starting work
4. Large features may need a design document

### Bug Fixes

1. Search existing issues to see if bug is reported
2. If not, create a bug report with reproduction steps
3. Reference the issue number in your PR

### Documentation

Documentation improvements are always welcome:

- Fix typos, grammar, clarity
- Add examples
- Improve explanations
- Add troubleshooting tips
- Translate to other languages (future)

### WebUI Improvements

- UI/UX improvements
- New features
- Performance optimizations
- Accessibility improvements

## Development Workflow

See the [Development Guide](index.md) for comprehensive development documentation including:

- [Development Setup](index.md#development-setup)
- [Code Style Guidelines](code-style.md)
- [Building and Testing](testing.md)
- [Release Process](release-process.md)

## Community Guidelines

### Be Respectful

- Be patient with new contributors
- Provide constructive feedback
- Assume good intentions
- Follow the [Code of Conduct](https://github.com/Feramance/qBitrr/blob/master/CODE_OF_CONDUCT.md)

### Communication Channels

- **GitHub Issues** - Bug reports, feature requests
- **GitHub Discussions** - General questions, ideas
- **Pull Requests** - Code contributions

### Getting Help

- Check [documentation](../index.md)
- Search existing issues and discussions
- Ask in GitHub Discussions
- Join community chat (link in README)

## Recognition

Contributors are recognized in:

- CHANGELOG.md
- GitHub releases
- Contributors page (planned)

Thank you for making qBitrr better!

## Related Documentation

- [Code Style](code-style.md) - Coding standards
- [Testing](testing.md) - How to test your changes
- [Development Guide](index.md) - Complete development documentation
- [Release Process](release-process.md) - How releases work
