# Release Process

qBitrr uses automated releases via GitHub Actions. This document describes the release workflow for maintainers.

## Release Workflow

### 1. Version Bumping

qBitrr uses **bump2version** for version management:

```bash
# Patch release (5.5.4 → 5.5.5)
bump2version patch

# Minor release (5.5.5 → 5.6.0)
bump2version minor

# Major release (5.6.0 → 6.0.0)
bump2version major
```

**What bump2version updates:**
- `setup.cfg` - Package version
- `pyproject.toml` - Project metadata
- `.bumpversion.cfg` - Version tracker
- Git tag created automatically

### 2. Changelog Generation

qBitrr uses **gren** (GitHub Release Notes generator):

```bash
# Generate release notes from commits
gren release --override

# Or manually edit CHANGELOG.md
```

**Changelog format:**

```markdown
## [5.6.0] - 2024-12-09

### Added
- New feature X
- New feature Y

### Changed
- Updated behavior of Z
- Improved performance of W

### Fixed
- Bug fix A
- Bug fix B

### Security
- Security fix C
```

### 3. Create Release

#### Option A: Automated (Recommended)

```bash
# 1. Bump version
bump2version minor  # or patch/major

# 2. Push tags
git push origin master --tags

# 3. GitHub Actions automatically:
#    - Builds Python package
#    - Publishes to PyPI
#    - Builds Docker image
#    - Pushes to Docker Hub
#    - Creates GitHub Release
```

#### Option B: Manual

```bash
# 1. Create tag
git tag -a v5.6.0 -m "Release v5.6.0"
git push origin v5.6.0

# 2. Build package
python setup.py sdist bdist_wheel

# 3. Upload to PyPI
twine upload dist/*

# 4. Build Docker image
docker build -t feramance/qbitrr:5.6.0 .
docker build -t feramance/qbitrr:latest .

# 5. Push to Docker Hub
docker push feramance/qbitrr:5.6.0
docker push feramance/qbitrr:latest

# 6. Create GitHub Release manually
```

## Release Types

### Patch Release (5.5.4 → 5.5.5)

**When:** Bug fixes only, no new features

**Process:**
1. Merge bug fix PRs to `master`
2. `bump2version patch`
3. Push tags

**Example commits:**
- `fix(radarr): resolve import path issue`
- `fix(webui): correct API token validation`

### Minor Release (5.5.5 → 5.6.0)

**When:** New features, backward-compatible changes

**Process:**
1. Merge feature PRs to `master`
2. `bump2version minor`
3. Update documentation
4. Push tags

**Example commits:**
- `feat(lidarr): add Lidarr v2.0 support`
- `feat(webui): add dark mode toggle`

### Major Release (5.6.0 → 6.0.0)

**When:** Breaking changes, major features

**Process:**
1. Create `v6-dev` branch for development
2. Merge all v6 features
3. Update documentation
4. Test thoroughly
5. Merge to `master`
6. `bump2version major`
7. Push tags
8. Write migration guide

**Example commits:**
- `feat!: replace SQLite with PostgreSQL`
- `refactor!: new configuration schema`

## CI/CD Pipelines

### Release Workflow

**File:** `.github/workflows/release.yml`

**Triggers:**
- Push tags matching `v*.*.*`

**Steps:**
1. Checkout code
2. Set up Python 3.12
3. Install build dependencies
4. Build WebUI (`npm run build`)
5. Build Python package (`python setup.py sdist bdist_wheel`)
6. Publish to PyPI (`twine upload`)
7. Build Docker image (multi-platform: amd64, arm64)
8. Push to Docker Hub with tags:
   - `feramance/qbitrr:5.6.0`
   - `feramance/qbitrr:5.6`
   - `feramance/qbitrr:5`
   - `feramance/qbitrr:latest`
9. Create GitHub Release with changelog

### Nightly Builds

**File:** `.github/workflows/nightly.yml`

**Trigger:** Daily at 00:00 UTC

**Output:** `feramance/qbitrr:nightly`

**Purpose:** Test bleeding-edge changes

## Version Numbering

qBitrr follows **Semantic Versioning** (semver):

```
MAJOR.MINOR.PATCH

5.6.2
│ │ │
│ │ └─ Patch: Bug fixes, security fixes
│ └─── Minor: New features, backward-compatible
└───── Major: Breaking changes
```

### Pre-release Versions

```
5.6.0-alpha.1  # Alpha release
5.6.0-beta.1   # Beta release
5.6.0-rc.1     # Release candidate
```

**Create pre-release:**

```bash
# Tag manually
git tag v5.6.0-rc.1
git push origin v5.6.0-rc.1
```

## Docker Image Tags

### Tag Strategy

| Tag | Description | Example |
|-----|-------------|---------|
| `latest` | Latest stable release | `5.6.2` |
| `nightly` | Daily build from master | Today's date |
| `X.Y.Z` | Specific version | `5.6.2` |
| `X.Y` | Latest patch in minor | `5.6` → `5.6.2` |
| `X` | Latest minor in major | `5` → `5.6.2` |

### Multi-Platform Builds

qBitrr supports multiple architectures:

- `linux/amd64` - x86_64 (most common)
- `linux/arm64` - ARM 64-bit (Raspberry Pi 4, Apple Silicon)
- `linux/arm/v7` - ARM 32-bit (older Raspberry Pi)

**Build command:**

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/arm/v7 \
  -t feramance/qbitrr:5.6.0 \
  --push \
  .
```

## PyPI Publishing

### Package Metadata

**File:** `setup.cfg`

```ini
[metadata]
name = qBitrr2
version = 5.6.0
description = Automate qBittorrent and *arr integration
author = Feramance
url = https://github.com/Feramance/qBitrr
```

### Publishing

Automated via GitHub Actions when tags are pushed.

**Manual publishing:**

```bash
# Build
python setup.py sdist bdist_wheel

# Check
twine check dist/*

# Upload (requires PyPI credentials)
twine upload dist/*
```

## Post-Release

### 1. Verify Release

```bash
# Check PyPI
pip install qBitrr2==5.6.0

# Check Docker Hub
docker pull feramance/qbitrr:5.6.0

# Check GitHub Release
# Visit: https://github.com/Feramance/qBitrr/releases
```

### 2. Update Documentation

Ensure docs are deployed:

- GitHub Pages: https://feramance.github.io/qBitrr/
- Docker Hub: Update description if needed

### 3. Announce Release

- GitHub Discussions: Post announcement
- Discord/Community: Share release notes
- Reddit: Post in relevant subreddits (r/radarr, r/sonarr)

### 4. Monitor Issues

Watch for issues related to new release:
- GitHub Issues
- Discord messages
- Reddit comments

## Hotfix Process

For critical bugs in production:

**1. Create hotfix branch:**

```bash
git checkout -b hotfix/5.6.1 v5.6.0
```

**2. Fix the bug:**

```bash
# Make minimal changes
git commit -m "fix(critical): resolve data loss issue"
```

**3. Test thoroughly**

**4. Release:**

```bash
bump2version patch  # 5.6.0 → 5.6.1
git push origin hotfix/5.6.1 --tags
```

**5. Merge back:**

```bash
# Merge to master
git checkout master
git merge --no-ff hotfix/5.6.1
git push origin master
```

## Release Checklist

Before releasing:

- [ ] All tests pass (once implemented)
- [ ] Documentation updated
- [ ] Changelog generated
- [ ] Version bumped
- [ ] Tag created
- [ ] No open critical issues

After releasing:

- [ ] PyPI package available
- [ ] Docker images pushed
- [ ] GitHub Release created
- [ ] Documentation deployed
- [ ] Announcement posted
- [ ] Monitor for issues

## Rollback Procedure

If a release has critical issues:

**1. Pull Docker images:**

```bash
# Users can rollback
docker pull feramance/qbitrr:5.5.5
```

**2. Yank PyPI package:**

```bash
# Marks package as unavailable (requires PyPI maintainer)
# Contact Feramance to yank if needed
```

**3. Create hotfix release:**

```bash
# Fix issue and release 5.6.1
```

## Related Documentation

- [Contributing](contributing.md) - Contribution guidelines
- [Development Guide](index.md) - Development setup
- [GitHub Actions Workflows](../../.github/workflows/) - CI/CD configuration
