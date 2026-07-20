# Release Process

qBitrr uses automated releases via GitHub Actions. This document describes the release workflow for maintainers.

## Version scheme

qBitrr versions are **`MAJOR.MINOR.PATCH-BUILD`** (build starts at **1**).

| Part | Meaning |
|------|---------|
| MAJOR | Breaking changes |
| MINOR | New features, backward-compatible |
| PATCH | Bug fixes |
| BUILD | Dependency / automation-only releases; resets to **1** on every major/minor/patch bump |

Examples:

- `[patch]` on `5.12.12-3` → `5.12.13-1`
- `[build]` on `5.12.12-1` → `5.12.12-2`

**ConfigVersion** (config schema) stays `MAJOR.MINOR.PATCH` only and is not rewritten on `[build]` bumps.

**Do not run `bump2version` locally.** CI bumps, commits (`[skip ci]`), tags, and publishes.

## How releases are triggered

Push to `master` with a commit message prefix, or run **Create a Release** via `workflow_dispatch`:

| Prefix | Bump | Use for |
|--------|------|---------|
| `[patch]` | patch (build → 1) | Bug fixes |
| `[minor]` | minor (build → 1) | Features |
| `[major]` | major (build → 1) | Breaking changes |
| `[build]` | build (+1) | Dependency / weekly automation only |

```bash
git checkout master
git pull origin master
git commit --allow-empty -m "[patch] Short description of the release"
git push origin master
```

### Dependabot

Merge Dependabot PRs **without** release prefixes (`[patch]` / `[minor]` / `[major]` / `[build]`). The weekly workflow merges green patch/minor Dependabot PRs and dispatches a `build` release when `master` has moved since the last tag.

## Docker channels

| Tag | Meaning | Updated by |
|-----|---------|------------|
| `stable` | Latest **patch/minor/major** release | `release.yml` (not `[build]`) |
| `latest` | Absolute newest published release (includes builds) | `release.yml` (every release type) |
| `nightly` | Per-commit tip of `master` | `nightly.yml` only |
| `vX.Y.Z-N` | Immutable version | `release.yml` |

`pip install -U qBitrr2` tracks the newest PyPI upload (including builds). There is no second PyPI package name.

## What a release publishes

1. `bump2version` updates `setup.cfg`, `.bumpversion.cfg`, `bundled_data.py`, `Dockerfile`, `docs/index.md` (and ConfigVersion-related files on major/minor/patch)
2. Signed `[skip ci]` version bump commit
3. Draft GitHub release `v{version}`
4. Docker images to Docker Hub + GHCR (`v…`, `latest`, and `stable` when applicable)
5. Platform binaries: `qBitrr-{version}-{os}-{arch}.tar.gz` / `.zip`
6. PyPI package `qBitrr2` (PEP 440 may normalize `5.12.12-1` → `5.12.12.post1`)
7. Changelog entry + published GitHub release notes

## Weekly build workflow

**File:** `.github/workflows/weekly-build.yml`

- Schedule: Monday 06:00 UTC (also `workflow_dispatch`)
- Auto-merges open Dependabot PRs with green checks (skips major/breaking)
- If commits exist since the latest `v*` tag, dispatches **Create a Release** with `release_type=build`

## Nightly workflow

**File:** `.github/workflows/nightly.yml`

- Trigger: push to `master` (non-release commits)
- Publishes **only** `feramance/qbitrr:nightly` (and GHCR equivalent)
- Skips commits starting with `[patch]` / `[minor]` / `[major]` / `[build]` / `[skip ci]`

## Hotfix

```bash
git checkout master
git checkout -b hotfix/fix-critical-bug
# … fix and test …
git checkout master
git merge hotfix/fix-critical-bug
git commit --allow-empty -m "[patch] Fix critical bug description"
git push origin master
```

## Rollback

1. Revert the bad commit on `master` and push (or cut a new `[patch]` with the fix)
2. Warn on the GitHub Release / Discussions
3. Users can pin: `pip install qBitrr2==X.Y.Z.postN` or Docker `feramance/qbitrr:vX.Y.Z-N` / `:stable`

## Files bump2version updates

| File | Notes |
|------|--------|
| `.bumpversion.cfg` | `current_version` |
| `setup.cfg` | Package version |
| `qBitrr/bundled_data.py` | Runtime `version` / `patched_version` |
| `Dockerfile` | `ARG VERSION` |
| `docs/index.md` | Latest release line |
| `qBitrr/config_version.py` | Schema only (`MAJOR.MINOR.PATCH`) |
| `qBitrr/gen_config/fields.py` | Default ConfigVersion (schema only) |
| `docs/configuration/config-file.md` | ConfigVersion example (schema only) |

## PyPI publishing

Releases publish package **`qBitrr2`** via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC). Version strings use `MAJOR.MINOR.PATCH-BUILD`; packaging may normalize `5.12.12-1` to `5.12.12.post1` on PyPI.

`pip install -U qBitrr2` always tracks the newest upload (including `[build]` releases). Docker `:stable` vs `:latest` is the opt-in split for dependency builds—not a second PyPI package.
