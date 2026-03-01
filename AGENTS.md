# AGENTS.md – Agent Coding Guide

> **Purpose**: qBitrr orchestrates qBittorrent ↔ Radarr/Sonarr/Lidarr communication, handling torrent health checks, instant imports, smart cleanup, and request automation. This guide ensures AI agents/contributors maintain consistency across Python backend and React frontend.

## Project Overview
- **Language**: Python 3.12+ (backend), TypeScript + React 18 (WebUI)
- **Architecture**: Multi-threaded event loops per Arr instance; Flask/Waitress REST API; Peewee ORM (SQLite)
- **Entry Point**: `qBitrr.main:run` → spawns WebUI, ArrManager loops, auto-update watchers
- **Key Modules**:
  - `qBitrr/main.py` – orchestrates multiprocessing, launches arr managers and WebUI
  - `qBitrr/arss.py` – ArrManager classes (Radarr/Sonarr/Lidarr) with health checks & import logic
  - `qBitrr/config.py` – TOML config parsing, validation, migrations
  - `qBitrr/webui.py` – Flask routes for `/api/*` (token-protected) and `/web/*` (helpers)
  - `qBitrr/ffprobe.py` – media file verification via ffprobe
  - `qBitrr/tables.py` – Peewee models for persistent state (downloads, searches, expiry)
  - `webui/src/` – React dashboard with @mantine/core UI, react-hook-form, @tanstack/react-table
- **Config**: `~/config/config.toml` (native) or `/config/config.toml` (Docker). Generated on first run via `gen_config.py`
- **Logging**: Structured logs in `~/logs/` or `/config/logs`; `Main.log`, `WebUI.log`, per-Arr logs
- **Deployment**: PyPI package (`qBitrr2`), Docker image (`feramance/qbitrr:latest`), or source install

## Build/Lint/Test Workflow

### Python Backend
1. **Create Environment**: `make newenv` (or `python -m venv .venv && source .venv/bin/activate`)
2. **Install Dependencies**: `make syncenv` (installs `.[all]` from setup.cfg, includes dev deps + WebUI build)
3. **Format & Lint**: `make reformat` → runs pre-commit hooks:
   - `black` (99-char line length, py312 target)
   - `isort` (black profile, known_third_party listed in pyproject.toml)
   - `autoflake` (removes unused imports/variables)
   - `pyupgrade` (modernizes syntax to py38+)
   - `check-yaml`, `check-toml`, `check-json`, `detect-private-key`, `end-of-file-fixer`, `trailing-whitespace`, `mixed-line-ending`
4. **Manual Testing**: No pytest suite; test against live qBittorrent + Arr instances or use Docker Compose setup
5. **Version Bump**: `bump2version patch|minor|major` (updates `.bumpversion.cfg`, `setup.cfg`, `pyproject.toml`, tags commit)
6. **Build Package**: `python setup.py sdist bdist_wheel` → dist/qBitrr2-*.whl
7. **Docker Build**: `docker build -t feramance/qbitrr:test .` (multi-stage: Node build → Python install)

### TypeScript/React WebUI
1. **Install**: `cd webui && npm ci` (package-lock.json locked to exact versions)
2. **Dev Server**: `npm run dev` → http://localhost:5173 with HMR (Vite)
3. **Lint**: `npm run lint` → ESLint with `@eslint/js`, `typescript-eslint`, `react-hooks`, `react-refresh`
4. **Type Check**: `tsc -b` (tsconfig.app.json + tsconfig.node.json)
5. **Build**: `npm run build` → outputs to `webui/dist/`, copied to `qBitrr/static/` for bundling
6. **Preview**: `npm run preview` → serve production build locally

### CI/CD
- **pre-commit.ci**: Auto-formats PRs, runs weekly autoupdates
- **CodeQL**: `.github/workflows/codeql.yml` scans for security issues
- **Nightly**: `.github/workflows/nightly.yml` builds Docker image, publishes to `feramance/qbitrr:nightly`
- **Release**: `.github/workflows/release.yml` publishes PyPI package, Docker tags (`latest`, semver)
- **Dependabot**: `.github/dependabot.yml` updates GitHub Actions weekly

## Code Style

### Python (PEP 8 + Black)
- **Formatting**: Black (99-char max), isort (black profile), 4-space indentation
- **Type Hints**: Required for all function signatures; use `from __future__ import annotations` for forward refs
- **Naming**:
  - `snake_case` for functions, variables, module names
  - `PascalCase` for classes, exceptions
  - `SCREAMING_SNAKE_CASE` for module-level constants
- **Exceptions**: Inherit from `qBitManagerError` (qBitrr/errors.py). Common subclasses:
  - `ConfigException` – config parsing/validation
  - `ArrManagerException` – Arr API failures
  - `SkipException` – skip torrent processing without error
  - `NoConnectionrException` – connection failures (typo preserved for compatibility)
  - `DelayLoopException`, `RestartLoopException` – control flow for event loops
  - `RequireConfigValue` – missing required config key
- **Docstrings**: Required for all classes and public functions; use triple-quotes, describe purpose + params + return
- **Imports**: Absolute imports (`from qBitrr.config import CONFIG`), grouped by stdlib → third-party → local
- **Line Breaks**: LF only (enforced by pre-commit `mixed-line-ending --fix lf`)

### TypeScript/React
- **Style**: ESLint `recommended` + `typescript-eslint` strict, functional components only
- **Type Safety**: Explicit return types, interfaces for all component props, no `any` (use `unknown` if needed)
- **Naming**:
  - `camelCase` for variables, functions
  - `PascalCase` for components, interfaces, types
- **Import Order**: React → node_modules/@-scoped → local modules → local icons (SVGs)
- **Hooks**: Declare dependencies correctly; use `useCallback`/`useMemo` for expensive ops
- **State Management**: Context API (`SearchContext`, `ToastContext`, `WebUIContext`) for global state
- **UI Library**: @mantine/core v8 for components; follow Mantine conventions (e.g., `sx` prop for inline styles)

### General
- **Indentation**: 4 spaces (Python), 2 spaces (JS/TS/JSON/YAML)
- **Line Endings**: LF (`\n`) enforced by pre-commit
- **Trailing Whitespace**: None (auto-fixed by pre-commit)
- **EOF Newline**: Required (enforced by `end-of-file-fixer`)
- **Unused Code**: No unused imports, variables, or functions (autoflake removes them)

## Error Handling & Logging
- **Custom Exceptions**: Always inherit from `qBitManagerError`; include context in `__init__` (e.g., `RequireConfigValue(config_class, config_key)`)
- **Logging**: Use `logging.getLogger("qBitrr")` or subloggers (`qBitrr.arr`, `qBitrr.webui`); call `run_logs(logger, "ModuleName")` to write to file
- **Log Levels**: DEBUG (verbose state), INFO (user-facing), WARNING (recoverable issue), ERROR (failure), CRITICAL (fatal)
- **User Messages**: Provide actionable error messages; reference config keys, Arr instance names, torrent hashes

## Architecture & Patterns
- **Multiprocessing**: `pathos.multiprocessing` for cross-platform support; each Arr instance runs in a separate process
- **Threading**: WebUI runs in main thread; auto-update, network monitor, and FFprobe downloads in background threads
- **Database**: Peewee ORM with SQLite (thread-safe via `db_lock.py`); tables: `DownloadsModel`, `SearchModel`, `EntryExpiry`
- **Event Loops**: Each ArrManager has a main loop checking qBit torrents every N seconds, triggering health checks, imports, cleanup
- **Config Migrations**: `apply_config_migrations()` upgrades old configs; bump `CURRENT_CONFIG_VERSION` when schema changes
- **API Routes**:
  - `/api/*` – token-protected (check `Settings.WebUIToken`), returns JSON
  - `/web/*` – public helpers (serve UI, version info)
  - `/ui` → serves React SPA from `qBitrr/static/`

## Development Tips
- **Config Changes**: Edit `qBitrr/gen_config.py` (MyConfig class); regenerate example via `qbitrr --gen-config`
- **WebUI Changes**: Run `npm run dev` in webui/, API requests proxy to http://localhost:6969
- **Database Schema**: Modify `qBitrr/tables.py`, add migration logic in `config.py:apply_config_migrations()`
- **New Arr Type**: Subclass `ArrManagerBase` in `arss.py`, implement `_process_failed_individual()`, register in `main.py`
- **Pre-commit Bypass**: `git commit --no-verify` (discouraged; use for emergency hotfixes only)

## Testing & Validation
- **Manual Testing**: Launch qBittorrent + Radarr/Sonarr locally or via Docker Compose; trigger downloads, check logs
- **Health Checks**: Test stalled torrents (pause + resume), failed imports (bad file perms), blacklisting
- **Config Validation**: Test invalid TOML, missing required keys, edge cases (e.g., empty categories)
- **WebUI Testing**: Check all tabs (Processes, Logs, Radarr/Sonarr/Lidarr, Config), test CRUD ops

## Pre-Merge/Release Cleanup

**CRITICAL**: Before merging PRs or creating releases, clean up ALL temporary files to keep the repository tidy.

### Temporary Files to Remove

**Always remove these file patterns:**
- `*_TEST*.md` - Test plans, test results, test summaries
- `*_RESULTS*.md` - Test results, benchmark results
- `READY_FOR_*.md` - Merge checklists, release checklists
- `*_PLAN.md` - Implementation plans, migration plans
- `*_SUMMARY.md` - Development summaries, decision logs
- `*_NOTES.md` - Development notes, meeting notes
- `TODO.md`, `TASKS.md` - Temporary task lists (unless permanent project management)

**Files to KEEP:**
- `README.md` - Main project readme
- `CHANGELOG.md` - Release history
- `AGENTS.md` - AI agent coding guide
- `.github/*.md` - GitHub templates (PR, issue, discussion)
- `docs/**/*.md` - All permanent documentation (includes API docs, contribution guide, systemd guide)

### Cleanup Commands

```bash
# 1. Find all temporary markdown files
find . -name "*_TEST*.md" -o -name "*_RESULTS*.md" -o -name "READY_FOR_*.md" -o -name "*_PLAN.md" -o -name "*_SUMMARY.md" -o -name "*_NOTES.md"

# 2. Review the list to ensure no permanent docs are caught

# 3. Remove temporary files
find . -name "*_TEST*.md" -o -name "*_RESULTS*.md" -o -name "READY_FOR_*.md" -o -name "*_PLAN.md" | xargs git rm

# 4. Verify only permanent docs remain
git ls-files "*.md" | grep -v "^docs/"

# Expected output:
# AGENTS.md
# CHANGELOG.md
# README.md
# .github/pull_request_template.md
# (plus any other permanent root-level docs)

# 5. Commit cleanup
git commit -m "chore: Remove temporary documentation files"
```

### Why This Matters

1. **Repository Hygiene**: Keeps git history clean and focused on permanent documentation
2. **Release Quality**: Prevents shipping development artifacts to end users
3. **Search Clarity**: Reduces noise when searching documentation
4. **Professional Image**: Shows attention to detail and proper project management
5. **Storage Efficiency**: Reduces repository size over time

### When to Clean Up

- **Before merging feature branches to master**
- **Before creating release tags**
- **After completing major development work**
- **During code review** (reviewer should check for temporary files)

### Pre-Merge Checklist

Before submitting a PR for final merge:

- [ ] All temporary `*_TEST*.md`, `*_RESULTS*.md` files removed
- [ ] All `READY_FOR_*.md` checklists removed
- [ ] All `*_PLAN.md` planning docs removed
- [ ] Only permanent documentation remains in root
- [ ] `docs/` directory contains only user-facing documentation
- [ ] Commit message references cleanup: `chore: Remove temporary documentation files`

## Release Process

### Overview
qBitrr uses **semantic versioning** (MAJOR.MINOR.PATCH) and automated release workflows. Releases are triggered by **commit message prefixes** on the `master` branch — not by local version bumps or tags.

### How Releases Are Triggered

The `.github/workflows/release.yml` workflow runs on every push to `master`, but the release jobs **only execute** when the head commit message starts with one of these prefixes:

| Prefix | Bump | Example |
|--------|------|---------|
| `[patch]` | x.x.**X** | Bug fixes, minor improvements |
| `[minor]` | x.**X**.0 | New features, non-breaking changes |
| `[major]` | **X**.0.0 | Breaking changes |

The workflow can also be triggered manually via `workflow_dispatch` on GitHub Actions.

**Do NOT run `bump2version` locally.** The CI workflow runs `bump2version` itself, commits the version bump (with `[skip ci]`), updates the bundled git hash, generates the changelog, and publishes the release.

### Release Steps

1. Ensure all PRs are merged to `master` and CI checks pass
2. Create a commit on `master` with the appropriate prefix:
   ```bash
   git checkout master
   git pull origin master
   git commit --allow-empty -m "[patch] Short description of the release"
   git push origin master
   ```
3. The release workflow automatically:
   - Runs `bump2version` to update version in `setup.cfg`, `pyproject.toml`, `.bumpversion.cfg`, `bundled_data.py`, `Dockerfile`, `docs/index.md`
   - Commits the version bump and bundled git hash (`[skip ci]`)
   - Creates a draft GitHub release
   - Builds and pushes Docker images (`latest`, `nightly`, `v{version}`) to Docker Hub and GHCR
   - Builds platform binaries (Windows x64, macOS arm64, Linux x64) and uploads to the release
   - Builds and publishes the Python package to PyPI
   - Generates a changelog entry in `CHANGELOG.md` from commits since the last tag
   - Publishes the GitHub release with the changelog as release notes

### Version Numbering Guidelines

**MAJOR** (X.0.0) - Breaking changes:
- Config schema changes requiring migration
- Removed features or breaking API changes
- Python version requirement changes
- Database schema breaking changes

**MINOR** (x.X.0) - New features:
- New Arr instance types
- New search features
- New WebUI pages/features
- Non-breaking config additions

**PATCH** (x.x.X) - Bug fixes:
- Bug fixes
- Performance improvements
- Documentation updates
- Dependency updates (non-breaking)

### Hotfix Release Process

For urgent fixes to production:

1. **Create Hotfix Branch**
   ```bash
   git checkout master
   git checkout -b hotfix/fix-critical-bug
   ```

2. **Make Fix and Test**
   - Implement minimal fix
   - Test thoroughly

3. **Merge and Release**
   ```bash
   git checkout master
   git merge hotfix/fix-critical-bug
   git commit --allow-empty -m "[patch] Fix critical bug description"
   git push origin master
   ```

### Rollback Procedure

If a release has critical issues:

1. **Create Rollback Tag**
   ```bash
   # Revert to previous version
   git revert <commit-hash>
   git push origin master
   ```

2. **Notify Users**
   - Update GitHub Release with warning
   - Post in GitHub Discussions
   - Recommend downgrade: `pip install qBitrr2==5.8.0`

### CI/CD Workflows

- **`.github/workflows/release.yml`**: Triggered on tag push (v*)
- **`.github/workflows/nightly.yml`**: Builds `nightly` Docker tag daily
- **`.github/workflows/codeql.yml`**: Security scanning on push
- **`.github/dependabot.yml`**: Weekly dependency updates

### Release Artifacts

Each release produces:
- **PyPI Package**: `qBitrr2-{version}.tar.gz`, `qBitrr2-{version}-py3-none-any.whl`
- **Docker Images**: Multi-architecture (amd64, arm64, armv7)
- **GitHub Release**: Changelog + attachments
- **Git Tag**: `v{version}` (e.g., v5.8.1)

## Common Pitfalls
- **Qbittorrent API**: Both qBittorrent 4.x and 5.x are automatically detected and supported
- **Tagging**: Radarr/Sonarr downloads MUST have tags matching the category configured for qBitrr to track them
- **Paths**: qBit's "Save Path" must be accessible to Radarr/Sonarr (common issue in Docker with mismatched volumes)
- **WebUI Token**: If `Settings.WebUIToken` is set, all `/api/*` calls require `X-API-Token` header
- **Database Locks**: Use `db_lock.py:database_lock()` context manager for all Peewee queries to avoid conflicts

## Documentation Maintenance

**CRITICAL**: When implementing new features or modifying existing functionality, documentation MUST be updated simultaneously to maintain accuracy.

### Required Documentation Updates

When making code changes, update the following documentation as applicable:

#### 1. User-Facing Documentation (`docs/` directory)
- **Configuration files** (`docs/configuration/*.md`):
  - Add/update config option descriptions
  - Provide example values and use cases
  - Document defaults and valid ranges
  - Include troubleshooting tips

- **Feature documentation** (`docs/features/*.md`):
  - Explain how the feature works
  - Provide step-by-step setup instructions
  - Add FAQ entries for common questions
  - Include screenshots/examples where helpful

- **Specific files requiring updates**:
  - `docs/configuration/quality-profiles.md` – for temp profile changes
  - `docs/features/automated-search.md` – for search behavior changes
  - `docs/configuration/arr/radarr.md`, `sonarr.md`, `lidarr.md` – Arr-specific features

#### 2. Code Documentation
- **Docstrings**: Add/update for all new public functions and classes
- **Inline comments**: Explain complex logic, design decisions, edge cases
- **Type hints**: Required for all function signatures

#### 3. Configuration Examples
- **`config.example.toml`**: Update with new config options and examples
- **`qBitrr/gen_config.py`**: Add new config fields with descriptions

#### 4. API Documentation
- **`docs/reference/api.md`**: Update if adding/changing WebUI API endpoints
- **OpenAPI/Swagger**: Update specs if applicable

### Documentation Quality Standards

- **Accuracy**: Docs must reflect actual behavior (test before documenting)
- **Completeness**: Cover all config options, edge cases, and common scenarios
- **Clarity**: Use clear language; avoid jargon; provide examples
- **Maintenance**: Remove outdated info; mark deprecated features
- **Searchability**: Use consistent terminology; include keywords

### Documentation Workflow

1. **During Development**:
   - Draft documentation as you write code
   - Note design decisions and edge cases
   - Create examples for common use cases

2. **Before PR**:
   - Review all affected documentation files
   - Test examples and code snippets
   - Check for broken links or references
   - Ensure consistency with existing docs

3. **PR Review**:
   - Documentation changes are reviewed alongside code
   - Reviewers verify accuracy and completeness
   - Update based on feedback

### Examples of Required Updates

**Adding a new config option:**
```markdown
# In docs/configuration/quality-profiles.md

## ForceResetTempProfiles

**Type:** Boolean
**Default:** `false`
**Added in:** v5.x.x

Resets all items using temporary profiles back to their main profiles when qBitrr starts.

**Example:**
```toml
[Radarr.EntrySearch]
ForceResetTempProfiles = true
```

**Use Case:** Useful after testing temp profiles or resolving profile mapping issues.
```

**Updating feature behavior:**
```markdown
# In docs/features/automated-search.md

## Temporary Profile Switching

**How it works:**
- Items without files are automatically switched to a temporary quality profile
- This increases the chances of finding content (lower quality = more available releases)
- Once content is found, items are switched back to the main profile
- Supports timeout-based automatic resets and startup resets

**FAQ:**
Q: Why is my Sonarr series on a temp profile when some episodes have files?
A: Missing episodes take priority. If ANY episodes are missing, the entire series uses the temp profile to maximize chances of finding the missing content.
```

### Documentation Checklist

Before submitting changes, verify:

- [ ] All new config options documented in `docs/configuration/`
- [ ] Feature behavior explained in `docs/features/`
- [ ] Examples added to `config.example.toml`
- [ ] Docstrings added for new functions/classes
- [ ] Inline comments explain complex logic
- [ ] API changes documented in `docs/reference/api.md`
- [ ] README.md updated if user-visible changes
- [ ] CHANGELOG.md or release notes prepared

**Remember:** Outdated documentation is worse than no documentation. Keep it current!

---

> **Note**: Follow this guide for all contributions. Questions? Check the [documentation](https://feramance.github.io/qBitrr/), README.md, or open a [feature request](.github/ISSUE_TEMPLATE/feature_request.yml).
