# Plan: GitHub Release-Based Update Detection (Non-Draft Only)

**Created:** 2025-11-05
**Status:** Planning Phase
**Goal:** Ensure auto-update only triggers on published (non-draft) GitHub releases with version validation

---

## Current Behavior Analysis

### What Already Works ✅
- `qBitrr/main.py:184` - Already calls `fetch_latest_release()` to check for updates
- `qBitrr/versioning.py:39` - Uses GitHub API endpoint `/releases/latest`
- **The `/releases/latest` endpoint automatically excludes draft releases by default**

### The Problem ❌
The system has a **disconnect** between check and update phases:
1. **Check phase**: Uses GitHub API to detect if update is available
2. **Update phase**: Runs `git pull` or `pip install --upgrade` (doesn't verify the version)

**Result:** It checks GitHub releases but then updates blindly via git/pip without confirming the version matches.

---

## Objective

Ensure auto-update **only triggers when**:
1. A **non-draft** GitHub release exists (`draft: false`)
2. A **non-prerelease** exists (`prerelease: false`)
3. The release version is **greater than current version**
4. The actual update mechanism (git/pip) updates to **that specific version**
5. Post-update verification confirms the correct version is installed

---

## Implementation Plan

### Phase 1: Enhance Version Validation (Low Risk)

**Files to Modify:**
- `qBitrr/versioning.py`
- `qBitrr/auto_update.py`

**Changes:**

1. **Add explicit draft/prerelease checking to `fetch_latest_release()`**
   - GitHub API `/releases/latest` excludes drafts by default
   - Add explicit validation to check `draft: false` and `prerelease: false` in response
   - Return error if draft or prerelease detected
   - Log release status for transparency

2. **Create `fetch_latest_stable_release()` helper function**
   - Explicitly filters for stable releases only
   - Falls back to `/releases` endpoint if needed
   - Provides clear logging about what releases were found/skipped

3. **Add `verify_update_success()` function**
   - Verify installed version matches expected version after update
   - Re-import bundled_data to get fresh version
   - Compare with expected version
   - Return True if match, False otherwise

---

### Phase 2: Modify Auto-Update Logic (Medium Risk)

**File to Modify:**
- `qBitrr/main.py` (`_perform_auto_update()` method, lines 182-205)

**Changes:**

1. **Store target version before update**
   - Extract normalized version from GitHub API response
   - Pass this to `perform_self_update()` for version-specific update

2. **Verify update success**
   - After `perform_self_update()` returns
   - Reload `bundled_data` module to get new version
   - Check if installed version matches target version
   - If mismatch, log warning (Phase 1: allow restart anyway)

3. **Add configuration options**
   - `AllowPrerelease`: Whether to accept prerelease versions
   - `StrictVersionCheck`: Whether to block restart on version mismatch

---

### Phase 3: Update Mechanism Enhancement (Choose One)

#### **Option A: Strict Version Control (Recommended)**

**For Git Repositories:**
```bash
git fetch --tags
git checkout v5.4.3
```

**For Pip Installations:**
```bash
pip install qBitrr2==5.4.3
```

**Pros:**
- Guarantees exact version match
- Works even if PyPI/git is behind
- Most reliable approach

**Cons:**
- Changes update behavior
- Requires careful testing
- Git users need to handle detached HEAD state

---

#### **Option B: Verification Only (Safer)**

- Keep current update mechanism unchanged (`git pull` / `pip install --upgrade`)
- Only verify after update completes
- If version doesn't match, log error and optionally skip restart
- Retry update on next cron run

**Pros:**
- Minimal code changes
- Lower risk of breaking existing setups
- Easier to test and deploy

**Cons:**
- Wasted update attempt if version doesn't match
- Relies on git/PyPI being up-to-date
- May result in delayed updates

---

#### **Option C: GitHub Releases API with Assets (Most Reliable)**

- Download release assets directly from GitHub
- Install from downloaded wheel/tarball
- Bypass PyPI entirely

**Pros:**
- Most reliable and immediate
- Works even if PyPI delayed
- Full control over source

**Cons:**
- Most complex implementation
- Need to handle platform-specific assets
- Requires download/install logic

---

## Detailed Code Changes

### 1. qBitrr/versioning.py

```python
def fetch_latest_release(repo: str = DEFAULT_REPOSITORY, *, timeout: int = 10) -> dict[str, Any]:
    """Fetch latest non-draft, non-prerelease from GitHub.

    Note: The /releases/latest endpoint excludes drafts by default, but we
    explicitly check to be defensive and provide clear error messages.
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers = {"Accept": "application/vnd.github+json"}

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        message = str(exc)
        if len(message) > 200:
            message = f"{message[:197]}..."
        return {
            "raw_tag": None,
            "normalized": None,
            "changelog": "",
            "changelog_url": f"https://github.com/{repo}/releases",
            "update_available": False,
            "error": message,
        }

    # NEW: Validate release is not draft/prerelease
    is_draft = payload.get("draft", False)
    is_prerelease = payload.get("prerelease", False)

    if is_draft:
        return {
            "raw_tag": None,
            "normalized": None,
            "changelog": "",
            "changelog_url": f"https://github.com/{repo}/releases",
            "update_available": False,
            "error": "Latest release is a draft (not yet published)",
        }

    if is_prerelease:
        # Could make this configurable via settings
        return {
            "raw_tag": None,
            "normalized": None,
            "changelog": "",
            "changelog_url": f"https://github.com/{repo}/releases",
            "update_available": False,
            "error": "Latest release is a prerelease (beta/rc)",
        }

    raw_tag = (payload.get("tag_name") or payload.get("name") or "").strip()
    normalized = normalize_version(raw_tag)
    changelog = payload.get("body") or ""
    changelog_url = payload.get("html_url") or f"https://github.com/{repo}/releases"
    update_available = is_newer_version(normalized)

    return {
        "raw_tag": raw_tag or None,
        "normalized": normalized,
        "changelog": changelog,
        "changelog_url": changelog_url,
        "update_available": update_available,
        "error": None,
    }


def fetch_latest_stable_release(repo: str = DEFAULT_REPOSITORY, *, timeout: int = 10) -> dict[str, Any]:
    """Fetch latest stable (non-draft, non-prerelease) release.

    This is a more explicit version of fetch_latest_release that uses the
    /releases endpoint and filters client-side for maximum control.
    """
    url = f"https://api.github.com/repos/{repo}/releases"
    headers = {"Accept": "application/vnd.github+json"}

    try:
        response = requests.get(url, headers=headers, timeout=timeout, params={"per_page": 10})
        response.raise_for_status()
        releases = response.json()
    except Exception as exc:
        message = str(exc)
        if len(message) > 200:
            message = f"{message[:197]}..."
        return {
            "raw_tag": None,
            "normalized": None,
            "changelog": "",
            "changelog_url": f"https://github.com/{repo}/releases",
            "update_available": False,
            "error": message,
        }

    # Find first stable release
    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue

        raw_tag = (release.get("tag_name") or release.get("name") or "").strip()
        normalized = normalize_version(raw_tag)
        changelog = release.get("body") or ""
        changelog_url = release.get("html_url") or f"https://github.com/{repo}/releases"
        update_available = is_newer_version(normalized)

        return {
            "raw_tag": raw_tag or None,
            "normalized": normalized,
            "changelog": changelog,
            "changelog_url": changelog_url,
            "update_available": update_available,
            "error": None,
        }

    # No stable releases found
    return {
        "raw_tag": None,
        "normalized": None,
        "changelog": "",
        "changelog_url": f"https://github.com/{repo}/releases",
        "update_available": False,
        "error": "No stable releases found",
    }
```

---

### 2. qBitrr/auto_update.py

```python
def perform_self_update(logger: logging.Logger, target_version: str | None = None) -> bool:
    """Attempt to update qBitrr in-place using git or pip.

    Args:
        logger: Logger instance for output
        target_version: Optional specific version to update to (e.g., "5.4.3" or "v5.4.3")
                       If None, updates to latest available

    Returns:
        True when the update command completed successfully, False otherwise.
    """

    repo_root = Path(__file__).resolve().parent.parent
    git_dir = repo_root / ".git"

    if git_dir.exists():
        logger.debug("Detected git repository at %s", repo_root)

        if target_version:
            # Checkout specific tag (Option A: Strict Version Control)
            tag = target_version if target_version.startswith("v") else f"v{target_version}"

            try:
                # Fetch latest tags
                logger.debug("Fetching tags from remote")
                subprocess.run(
                    ["git", "fetch", "--tags", "--force"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Check if tag exists
                result = subprocess.run(
                    ["git", "rev-parse", tag],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    logger.error("Tag %s not found in repository", tag)
                    return False

                # Checkout specific tag
                result = subprocess.run(
                    ["git", "checkout", tag],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    check=True,
                )
                stdout = (result.stdout or "").strip()
                if stdout:
                    logger.info("git checkout output:\n%s", stdout)
                logger.info("Checked out tag %s", tag)
                return True

            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or "").strip()
                logger.error("Failed to checkout tag %s: %s", tag, stderr or exc)
                # Fallback to git pull if tag checkout fails
                logger.warning("Falling back to git pull")

        # Existing git pull behavior (default or fallback)
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=True,
            )
            stdout = (result.stdout or "").strip()
            if stdout:
                logger.info("git pull output:\n%s", stdout)
            return True
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            logger.error("Failed to update repository via git: %s", stderr or exc)
            return False

    # Pip install path
    package = "qBitrr2"
    if target_version:
        # Strip 'v' prefix if present
        version = target_version[1:] if target_version.startswith("v") else target_version
        package = f"{package}=={version}"

    logger.debug("Upgrading package: %s", package)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", package],
            capture_output=True,
            text=True,
            check=True,
        )
        stdout = (result.stdout or "").strip()
        if stdout:
            logger.info("pip upgrade output:\n%s", stdout)
        return True
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        logger.error("Failed to upgrade package via pip: %s", stderr or exc)
        return False


def verify_update_success(expected_version: str, logger: logging.Logger) -> bool:
    """Verify that the installed version matches the expected version.

    Args:
        expected_version: Expected version string (e.g., "5.4.3")
        logger: Logger instance for output

    Returns:
        True if version matches, False otherwise
    """
    try:
        # Re-import bundled_data to get fresh version
        import importlib
        import sys

        # Remove cached module
        if "qBitrr.bundled_data" in sys.modules:
            del sys.modules["qBitrr.bundled_data"]

        # Re-import
        from qBitrr import bundled_data
        from qBitrr.versioning import normalize_version

        current = normalize_version(bundled_data.version)
        expected = normalize_version(expected_version)

        if current == expected:
            logger.info("Update verified: version %s installed successfully", current)
            return True
        else:
            logger.warning(
                "Version mismatch after update: expected %s, got %s",
                expected,
                current,
            )
            return False

    except Exception as exc:
        logger.error("Failed to verify update: %s", exc)
        return False
```

---

### 3. qBitrr/main.py

```python
def _perform_auto_update(self) -> None:
    """Check for updates and apply if available."""
    self.logger.notice("Checking for updates...")

    # Fetch latest release info from GitHub
    release_info = fetch_latest_release()

    if release_info.get("error"):
        self.logger.error("Auto update skipped: %s", release_info["error"])
        return

    # Use normalized version for comparison, raw tag for display
    target_version = release_info.get("normalized")
    raw_tag = release_info.get("raw_tag")

    if not release_info.get("update_available"):
        if target_version:
            self.logger.info(
                "Auto update skipped: already running the latest release (%s).",
                raw_tag or target_version,
            )
        else:
            self.logger.info("Auto update skipped: no new release detected.")
        return

    self.logger.notice(
        "Update available: %s -> %s",
        patched_version,
        raw_tag or target_version,
    )

    # Perform the update with specific version
    updated = perform_self_update(self.logger, target_version=target_version)

    if not updated:
        self.logger.error("Auto update failed; manual intervention may be required.")
        return

    # Verify update success (optional based on config)
    # TODO: Add config option Settings.AutoUpdate.StrictVersionCheck
    strict_check = True  # Hardcoded for now, make configurable later

    if target_version and strict_check:
        from qBitrr.auto_update import verify_update_success

        if verify_update_success(target_version, self.logger):
            self.logger.notice("Update verified successfully")
        else:
            self.logger.warning(
                "Update completed but version verification failed. "
                "The system may not be running the expected version."
            )
            # Phase 1: Log warning but continue with restart
            # Phase 2: Optionally skip restart if strict mode enabled
            # return

    self.logger.notice("Update applied successfully; restarting to load the new version.")
    self.request_restart()
```

---

### 4. Configuration Changes (qBitrr/gen_config.py & config.py)

**Add new config options:**

```python
# In gen_config.py - MyConfig class

class AutoUpdate:
    """Auto-update configuration"""

    def __init__(self):
        self.enabled = MyConfigField(
            "Set to true to enable the auto-update worker.",
            bool,
            (
                ENVIRO_CONFIG.settings.auto_update_enabled
                if ENVIRO_CONFIG.settings.auto_update_enabled is not None
                else False
            ),
        )
        self.cron = MyConfigField(
            "Cron expression for auto-update schedule (default: weekly on Sunday at 3 AM)",
            str,
            ENVIRO_CONFIG.settings.auto_update_cron or "0 3 * * 0",
        )
        # NEW OPTIONS
        self.allow_prerelease = MyConfigField(
            "Allow updating to prerelease versions (beta, rc, etc)",
            bool,
            False,
        )
        self.strict_version_check = MyConfigField(
            "Require exact version match after update before restarting",
            bool,
            True,
        )
```

**Example config.toml:**

```toml
[Settings.AutoUpdate]
Enabled = true
Cron = "0 3 * * 0"  # Every Sunday at 3 AM
AllowPrerelease = false  # Only stable releases
StrictVersionCheck = true  # Verify version before restart
```

---

## Testing Plan

### Unit Tests

1. **Test `fetch_latest_release()` with mock responses:**
   - Draft release (draft=true) → Should return error
   - Prerelease (prerelease=true) → Should return error
   - Stable release (draft=false, prerelease=false) → Should succeed
   - API error → Should return error with message

2. **Test version comparison:**
   - Current: 5.4.0, Target: 5.4.1 → Should update
   - Current: 5.4.1, Target: 5.4.1 → Should skip
   - Current: 5.4.2, Target: 5.4.1 → Should skip (no downgrade)

3. **Test `perform_self_update()` with version:**
   - Git repo: Should checkout correct tag
   - Pip install: Should install exact version
   - Invalid version: Should fail gracefully

4. **Test `verify_update_success()`:**
   - Matching versions → Return True
   - Mismatched versions → Return False
   - Import errors → Return False with log

---

### Integration Tests

1. **Draft Release Test:**
   - Create draft release v5.99.0
   - Trigger auto-update
   - Verify: No update attempted, log shows "draft" message

2. **Prerelease Test:**
   - Create prerelease v5.99.0-beta.1
   - Trigger auto-update
   - Verify: No update attempted (if AllowPrerelease=false)

3. **Stable Release Test:**
   - Publish stable release v5.99.0
   - Trigger auto-update
   - Verify: Update performed, version matches, restart triggered

4. **Version Mismatch Test:**
   - Mock scenario where git/pip updates to wrong version
   - Verify: Warning logged, restart blocked (if StrictVersionCheck=true)

---

### Manual Testing

1. **Setup test environment:**
   ```bash
   # Set frequent cron for testing
   [Settings.AutoUpdate]
   Enabled = true
   Cron = "*/5 * * * *"  # Every 5 minutes
   StrictVersionCheck = true
   ```

2. **Test draft behavior:**
   - Create draft release on GitHub
   - Wait for auto-update to run
   - Check logs: Should see "draft (not yet published)" message
   - Verify no restart occurred

3. **Test publish behavior:**
   - Publish the draft release
   - Wait for auto-update to run
   - Check logs: Should see update + version verification + restart
   - Verify new version running

4. **Test rollback scenario (if implemented):**
   - Manually install wrong version
   - Trigger update
   - Verify system handles gracefully

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Git checkout breaks existing setup | Low | High | Add fallback to git pull if tag not found; test thoroughly |
| Pip version pinning breaks dependencies | Low | Medium | Use `--upgrade-strategy eager`; test with dependency matrix |
| Version mismatch after update | Medium | Low | Log warning; optional strict mode to block restart |
| GitHub API rate limiting | Low | Medium | Add exponential backoff; cache results; use conditional requests |
| Breaking running instance | Low | High | Phased rollout; test in development first; add config toggles |
| Users stuck on old version (draft blocks) | Low | Low | Clear logging; publish releases promptly |
| Git detached HEAD state | Medium | Medium | Document behavior; consider git pull as fallback |

---

## Deployment Strategy

### Phase 1: Safe Changes (Release 1) - Low Risk

**Changes:**
- Add explicit draft/prerelease validation to `fetch_latest_release()`
- Add `verify_update_success()` function
- Add version verification after update (log only, don't block restart)
- Add configuration options (but keep strict_check=False initially)

**Testing:**
- Deploy to development environment
- Monitor logs for draft/prerelease detection
- Verify no breaking changes
- Deploy to production after 1-2 weeks

**Rollback Plan:**
- No breaking changes, can rollback safely
- Version verification is passive (logging only)

---

### Phase 2: Version Pinning (Release 2) - Medium Risk

**Changes:**
- Add target version parameter to `perform_self_update()`
- Implement git checkout tag for git repos
- Implement pip version pinning for pip installs
- Keep strict_check=False (warnings only)

**Testing:**
- Test git checkout with multiple versions
- Test pip version pinning
- Verify fallback to git pull if tag missing
- Test with both git and pip installations

**Rollback Plan:**
- If issues occur, set `Enabled = false` in AutoUpdate
- Manual updates still work via existing mechanisms

---

### Phase 3: Strict Verification (Release 3) - Higher Risk

**Changes:**
- Enable `StrictVersionCheck` by default (block restart on mismatch)
- Add rollback capability (optional)
- Full monitoring and alerting

**Testing:**
- Test version mismatch scenarios
- Verify restart blocking works correctly
- Test with malformed versions
- Monitor production closely for 2-4 weeks

**Rollback Plan:**
- Set `StrictVersionCheck = false` in config
- Revert to Phase 2 behavior if needed

---

## Alternative Approaches

### Minimal Change Approach (Quick Win)

If full implementation is too complex, start with:

1. **Only add draft validation** to `fetch_latest_release()`
2. **Keep existing update mechanism** unchanged
3. **Log version after update** but don't verify

**Pros:**
- Very low risk
- Solves the draft release problem
- Quick to implement (1-2 hours)

**Cons:**
- Doesn't guarantee version match
- May update to wrong version if PyPI/git lags

---

### GitHub Actions Approach

Instead of checking from qBitrr itself:

1. **GitHub Action triggers on release publish**
2. **Action calls webhook on user instances**
3. **qBitrr receives webhook and updates**

**Pros:**
- No polling needed
- Instant updates
- Centralized control

**Cons:**
- Requires webhook endpoint (security concerns)
- Requires user firewall configuration
- More complex infrastructure

---

## Configuration Reference

### Current Config (Existing)

```toml
[Settings]
Enabled = true
Cron = "0 3 * * 0"
```

### Proposed Config (New)

```toml
[Settings.AutoUpdate]
Enabled = true
Cron = "0 3 * * 0"  # Every Sunday at 3 AM
AllowPrerelease = false  # NEW: Skip beta/rc releases
StrictVersionCheck = true  # NEW: Verify version before restart
```

### Environment Variables (Alternative)

```bash
QBITRR_AUTO_UPDATE_ENABLED=true
QBITRR_AUTO_UPDATE_CRON="0 3 * * 0"
QBITRR_AUTO_UPDATE_ALLOW_PRERELEASE=false
QBITRR_AUTO_UPDATE_STRICT_VERSION_CHECK=true
```

---

## Success Criteria

### Phase 1 Success:
- [ ] Draft releases are detected and skipped
- [ ] Prerelease releases are detected and skipped (or honored based on config)
- [ ] Version verification logs correct information
- [ ] No breaking changes to existing update mechanism
- [ ] Clear log messages explain why updates are skipped

### Phase 2 Success:
- [ ] Git repos checkout specific tags
- [ ] Pip installations install specific versions
- [ ] Fallback to original behavior if version-specific update fails
- [ ] Version verification works correctly
- [ ] Users can configure strict/permissive modes

### Phase 3 Success:
- [ ] Strict version check blocks restart on mismatch
- [ ] System recovers gracefully from failed updates
- [ ] Rollback capability works (if implemented)
- [ ] 99% of auto-updates succeed with correct version
- [ ] User reports confirm stability

---

## Timeline Estimate

| Phase | Development | Testing | Documentation | Total |
|-------|-------------|---------|---------------|-------|
| Phase 1 | 4 hours | 2 hours | 1 hour | 7 hours |
| Phase 2 | 6 hours | 4 hours | 2 hours | 12 hours |
| Phase 3 | 4 hours | 4 hours | 1 hour | 9 hours |
| **Total** | **14 hours** | **10 hours** | **4 hours** | **28 hours** |

**Recommended approach:** Implement Phase 1 immediately (7 hours), evaluate results, then proceed with Phase 2/3 if needed.

---

## Open Questions

1. **Should we support rollback?** If an update fails verification, should we attempt to roll back to the previous version?

2. **How to handle git detached HEAD?** After `git checkout <tag>`, the repo is in detached HEAD state. Should we create a branch or document this behavior?

3. **Rate limiting strategy?** GitHub API has rate limits (60 req/hour unauthenticated). Should we add a GitHub token option for authenticated requests (5000 req/hour)?

4. **Docker-specific handling?** Docker containers typically use image tags, not git/pip updates. Should we detect Docker and disable auto-update or add Docker-specific logic?

5. **Notification system?** Should we add webhook/notification support to alert users when updates are available but skipped (e.g., due to draft status)?

---

## References

- GitHub API Releases: https://docs.github.com/en/rest/releases/releases
- Python Packaging Version Spec: https://packaging.python.org/en/latest/specifications/version-specifiers/
- Git Checkout Tags: https://git-scm.com/book/en/v2/Git-Basics-Tagging
- Croniter Documentation: https://github.com/kiorky/croniter

---

## Conclusion

**Recommendation:** Start with **Phase 1** (draft/prerelease validation with passive verification) as it provides immediate value with minimal risk. The existing GitHub API endpoint already excludes drafts, so the main benefit is explicit validation and clear error messages.

After Phase 1 is stable in production, evaluate whether Phase 2 (version-specific updates) is needed based on:
- User feedback about update reliability
- Frequency of version mismatches in logs
- Issues with PyPI/git being out of sync

The full implementation (all 3 phases) provides the most robust solution but requires careful testing and monitoring to ensure stability.

---

## ADDENDUM: Binary Installation Handling

**Added:** 2025-11-05
**Context:** Binary users need different update logic than git/PyPI users

---

### Installation Type Detection

qBitrr can be installed in three ways:
1. **Git repository** - Source code with `.git` directory
2. **PyPI package** - Installed via `pip install qBitrr2`
3. **Binary executable** - PyInstaller-compiled standalone binary

**Detection Logic:**

```python
import sys
from pathlib import Path

def get_installation_type() -> str:
    """Detect how qBitrr is installed.

    Returns:
        "binary" - PyInstaller frozen executable
        "git" - Git repository installation
        "pip" - PyPI package installation
    """
    # Check if running as PyInstaller binary
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return "binary"

    # Check for git repository
    repo_root = Path(__file__).resolve().parent.parent
    git_dir = repo_root / ".git"
    if git_dir.exists():
        return "git"

    # Default to pip installation
    return "pip"
```

---

### Binary Update Implementation

**Challenge:** Binary executables can't use `git pull` or `pip install`. They must:
1. Download the correct binary asset from GitHub releases
2. Replace the running executable
3. Restart with the new binary

**Platform Detection:**

```python
import platform
import sys

def get_binary_asset_pattern() -> str:
    """Get the asset filename pattern for the current platform.

    Returns:
        Partial filename to match against release assets
        Examples: "ubuntu-latest-x64", "windows-latest-x64", "macOS-latest-arm64"
    """
    system = platform.system()
    machine = platform.machine()

    # Map platform to GitHub runner names (matching build.spec workflow)
    if system == "Linux":
        os_part = "ubuntu-latest"
        arch_part = "x64" if machine in ("x86_64", "AMD64") else "arm64"
    elif system == "Darwin":  # macOS
        os_part = "macOS-latest"
        arch_part = "arm64" if machine == "arm64" else "x64"
    elif system == "Windows":
        os_part = "windows-latest"
        arch_part = "x64" if machine in ("x86_64", "AMD64") else "arm64"
    else:
        raise RuntimeError(f"Unsupported platform: {system} {machine}")

    return f"{os_part}-{arch_part}"
```

**Asset Download & Replacement:**

```python
import requests
import tarfile
import zipfile
import shutil
import tempfile
from pathlib import Path

def download_binary_update(
    release_info: dict,
    logger: logging.Logger
) -> bool:
    """Download and install binary update from GitHub release.

    Args:
        release_info: Release information from fetch_latest_release()
        logger: Logger instance

    Returns:
        True if update successful, False otherwise
    """
    try:
        # Get asset pattern for current platform
        asset_pattern = get_binary_asset_pattern()
        logger.debug("Looking for binary asset matching: %s", asset_pattern)

        # Find matching asset in release
        tag_name = release_info.get("raw_tag")
        if not tag_name:
            logger.error("No tag name in release info")
            return False

        # Fetch release details with assets
        repo = "Feramance/qBitrr"
        url = f"https://api.github.com/repos/{repo}/releases/tags/{tag_name}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        release_data = response.json()

        # Find matching asset
        assets = release_data.get("assets", [])
        matching_asset = None
        for asset in assets:
            name = asset.get("name", "")
            if asset_pattern in name:
                matching_asset = asset
                break

        if not matching_asset:
            logger.error(
                "No binary asset found for platform %s in release %s",
                asset_pattern,
                tag_name,
            )
            logger.debug("Available assets: %s", [a.get("name") for a in assets])
            return False

        asset_name = matching_asset["name"]
        download_url = matching_asset["browser_download_url"]
        asset_size = matching_asset.get("size", 0)

        logger.info(
            "Downloading binary update: %s (%.2f MB)",
            asset_name,
            asset_size / (1024 * 1024),
        )

        # Download to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(asset_name).suffix) as tmp_file:
            tmp_path = Path(tmp_file.name)

            response = requests.get(download_url, stream=True, timeout=300)
            response.raise_for_status()

            # Download with progress
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
                downloaded += len(chunk)
                if asset_size > 0:
                    percent = (downloaded / asset_size) * 100
                    if downloaded % (1024 * 1024) == 0:  # Log every MB
                        logger.debug("Downloaded: %.1f%%", percent)

        logger.info("Download complete: %s", tmp_path)

        # Extract archive
        extract_dir = Path(tempfile.mkdtemp(prefix="qbitrr_update_"))
        logger.debug("Extracting to: %s", extract_dir)

        if asset_name.endswith(".tar.gz"):
            with tarfile.open(tmp_path, "r:gz") as tar:
                tar.extractall(extract_dir)
        elif asset_name.endswith(".zip"):
            with zipfile.ZipFile(tmp_path, "r") as zip_file:
                zip_file.extractall(extract_dir)
        else:
            logger.error("Unknown archive format: %s", asset_name)
            tmp_path.unlink()
            return False

        # Find extracted binary (should be in dist/ folder based on workflow)
        binary_candidates = list(extract_dir.rglob("qBitrr*"))
        binary_candidates = [
            p for p in binary_candidates
            if p.is_file() and not p.suffix in (".txt", ".md", ".json")
        ]

        if not binary_candidates:
            logger.error("No binary found in extracted archive")
            tmp_path.unlink()
            shutil.rmtree(extract_dir, ignore_errors=True)
            return False

        new_binary = binary_candidates[0]
        logger.debug("Found new binary: %s", new_binary)

        # Get current executable path
        current_binary = Path(sys.executable).resolve()
        logger.debug("Current binary: %s", current_binary)

        # Create backup of current binary
        backup_binary = current_binary.with_suffix(current_binary.suffix + ".backup")
        if backup_binary.exists():
            backup_binary.unlink()
        shutil.copy2(current_binary, backup_binary)
        logger.debug("Created backup: %s", backup_binary)

        # Replace current binary with new one
        # On Windows, can't replace running executable, so rename and schedule deletion
        if platform.system() == "Windows":
            # Rename current to .old
            old_binary = current_binary.with_suffix(current_binary.suffix + ".old")
            if old_binary.exists():
                old_binary.unlink()
            current_binary.rename(old_binary)

            # Copy new binary to original location
            shutil.copy2(new_binary, current_binary)

            # Schedule old binary deletion on next startup
            # (Windows will delete .old file on next run)
        else:
            # On Unix, can replace running executable
            shutil.copy2(new_binary, current_binary)
            current_binary.chmod(0o755)  # Ensure executable

        # Cleanup
        tmp_path.unlink()
        shutil.rmtree(extract_dir, ignore_errors=True)

        logger.notice("Binary update installed successfully")
        return True

    except Exception as exc:
        logger.exception("Failed to download/install binary update: %s", exc)
        return False
```

---

### Updated perform_self_update() Function

```python
def perform_self_update(logger: logging.Logger, target_version: str | None = None) -> bool:
    """Attempt to update qBitrr in-place using appropriate method for installation type.

    Args:
        logger: Logger instance for output
        target_version: Optional specific version to update to (e.g., "5.4.3")

    Returns:
        True when the update command completed successfully, False otherwise.
    """

    # Detect installation type
    install_type = get_installation_type()
    logger.debug("Installation type detected: %s", install_type)

    # BINARY INSTALLATION
    if install_type == "binary":
        logger.info("Binary installation detected, downloading update from GitHub releases")

        # Binary updates must use GitHub releases API
        if not target_version:
            logger.error("Binary updates require a target version from GitHub releases")
            return False

        # Need release info to get asset download URLs
        from qBitrr.versioning import fetch_release_by_tag
        release_info = fetch_release_by_tag(target_version)

        if release_info.get("error"):
            logger.error("Cannot fetch release info: %s", release_info["error"])
            return False

        # Download and install binary
        return download_binary_update(release_info, logger)

    # GIT INSTALLATION
    elif install_type == "git":
        repo_root = Path(__file__).resolve().parent.parent
        git_dir = repo_root / ".git"
        logger.debug("Git repository detected at %s", repo_root)

        if target_version:
            # Strict version: checkout specific tag
            tag = target_version if target_version.startswith("v") else f"v{target_version}"

            try:
                logger.debug("Fetching tags from remote")
                subprocess.run(
                    ["git", "fetch", "--tags", "--force"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    check=True,
                )

                result = subprocess.run(
                    ["git", "rev-parse", tag],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    logger.error("Tag %s not found in repository", tag)
                    return False

                result = subprocess.run(
                    ["git", "checkout", tag],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    check=True,
                )
                stdout = (result.stdout or "").strip()
                if stdout:
                    logger.info("git checkout output:\n%s", stdout)
                logger.info("Checked out tag %s", tag)
                return True

            except subprocess.CalledProcessError as exc:
                stderr = (exc.stderr or "").strip()
                logger.error("Failed to checkout tag %s: %s", tag, stderr or exc)
                logger.warning("Falling back to git pull")

        # Default: git pull
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=True,
            )
            stdout = (result.stdout or "").strip()
            if stdout:
                logger.info("git pull output:\n%s", stdout)
            return True
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            logger.error("Failed to update repository via git: %s", stderr or exc)
            return False

    # PIP INSTALLATION
    elif install_type == "pip":
        logger.debug("PyPI installation detected")

        package = "qBitrr2"
        if target_version:
            # Strict version: install exact version
            version = target_version[1:] if target_version.startswith("v") else target_version
            package = f"{package}=={version}"

        logger.debug("Upgrading package: %s", package)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", package],
                capture_output=True,
                text=True,
                check=True,
            )
            stdout = (result.stdout or "").strip()
            if stdout:
                logger.info("pip upgrade output:\n%s", stdout)
            return True
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            logger.error("Failed to upgrade package via pip: %s", stderr or exc)
            return False

    else:
        logger.error("Unknown installation type: %s", install_type)
        return False
```

---

### Updated main.py Auto-Update Logic

```python
def _perform_auto_update(self) -> None:
    """Check for updates and apply if available."""
    self.logger.notice("Checking for updates...")

    # Fetch latest release info from GitHub
    release_info = fetch_latest_release()

    if release_info.get("error"):
        self.logger.error("Auto update skipped: %s", release_info["error"])
        return

    target_version = release_info.get("normalized")
    raw_tag = release_info.get("raw_tag")

    if not release_info.get("update_available"):
        if target_version:
            self.logger.info(
                "Auto update skipped: already running the latest release (%s).",
                raw_tag or target_version,
            )
        else:
            self.logger.info("Auto update skipped: no new release detected.")
        return

    # Detect installation type
    from qBitrr.auto_update import get_installation_type
    install_type = get_installation_type()

    self.logger.notice(
        "Update available: %s -> %s (installation: %s)",
        patched_version,
        raw_tag or target_version,
        install_type,
    )

    # Binary installations REQUIRE GitHub releases with assets
    if install_type == "binary":
        if not target_version:
            self.logger.error(
                "Cannot update binary installation without valid release version"
            )
            return

        # Pass full release_info for asset URLs
        updated = perform_self_update(self.logger, target_version=target_version)
    else:
        # Git/Pip can use target version or fall back to latest
        updated = perform_self_update(self.logger, target_version=target_version)

    if not updated:
        self.logger.error("Auto update failed; manual intervention may be required.")
        return

    # Verify update success (all installation types)
    if target_version:
        from qBitrr.auto_update import verify_update_success

        if verify_update_success(target_version, self.logger):
            self.logger.notice("Update verified successfully")
        else:
            self.logger.warning(
                "Update completed but version verification failed. "
                "The system may not be running the expected version."
            )
            # For binaries, this is critical - don't restart if version doesn't match
            if install_type == "binary":
                self.logger.error("Binary update verification failed, skipping restart")
                return

    self.logger.notice("Update applied successfully; restarting to load the new version.")
    self.request_restart()
```

---

### Binary Update Workflow

1. **Detection Phase:**
   - Check if running as PyInstaller binary (`sys.frozen` and `sys._MEIPASS`)
   - Identify platform and architecture
   - Construct asset pattern (e.g., "ubuntu-latest-x64")

2. **Download Phase:**
   - Fetch release metadata from GitHub API
   - Find matching binary asset for platform
   - Download asset to temporary location
   - Verify download (checksum if available)

3. **Installation Phase:**
   - Extract archive (tar.gz for Unix, zip for Windows)
   - Locate binary executable in extracted files
   - Create backup of current executable
   - Replace current binary:
     - **Windows**: Rename current → .old, copy new → original location
     - **Unix**: Direct replace (running executable can be overwritten)
   - Set executable permissions (Unix only)

4. **Verification Phase:**
   - Verify new binary exists and is executable
   - For extra safety, could run `./qBitrr --version` check
   - Verify version matches expected

5. **Restart Phase:**
   - Trigger application restart
   - New process loads updated binary
   - Old binary cleanup (delete .backup files older than X days)

---

### Security Considerations for Binary Updates

1. **Asset Verification:**
   - Verify download URL is from github.com
   - Check file size matches metadata
   - Optional: Verify checksums if provided in release
   - Optional: Verify GPG signatures on assets

2. **Backup Strategy:**
   - Keep previous version as `.backup`
   - Auto-cleanup old backups after successful runs
   - Provide rollback command if new binary fails

3. **Permissions:**
   - Ensure new binary has execute permissions
   - Verify user has write access to binary location
   - Handle permission denied errors gracefully

4. **Atomic Updates:**
   - Use atomic operations where possible
   - Rename, don't delete-then-write
   - Maintain backup until new binary verified

---

### Error Handling for Binary Updates

```python
class BinaryUpdateError(Exception):
    """Base exception for binary update failures."""
    pass

class AssetNotFoundError(BinaryUpdateError):
    """No matching binary asset found for platform."""
    pass

class DownloadFailedError(BinaryUpdateError):
    """Failed to download binary asset."""
    pass

class ExtractionFailedError(BinaryUpdateError):
    """Failed to extract binary from archive."""
    pass

class ReplacementFailedError(BinaryUpdateError):
    """Failed to replace running binary."""
    pass

# Usage in download_binary_update():
try:
    # ... download logic ...
except requests.RequestException as exc:
    raise DownloadFailedError(f"Download failed: {exc}") from exc
except tarfile.TarError as exc:
    raise ExtractionFailedError(f"Extraction failed: {exc}") from exc
except (OSError, shutil.Error) as exc:
    raise ReplacementFailedError(f"Binary replacement failed: {exc}") from exc
```

---

### Testing Strategy for Binary Updates

1. **Unit Tests:**
   - Mock PyInstaller environment (`sys.frozen = True`)
   - Test platform detection on different OS/arch
   - Test asset pattern matching
   - Test archive extraction

2. **Integration Tests:**
   - Build actual binary with PyInstaller
   - Create mock GitHub release with test assets
   - Test full download → extract → replace → verify cycle
   - Test rollback on failure

3. **Platform Testing:**
   - Test on Windows x64
   - Test on macOS arm64 (Apple Silicon)
   - Test on macOS x64 (Intel)
   - Test on Linux x64
   - Test on Linux arm64 (Raspberry Pi)

4. **Edge Cases:**
   - No matching asset for platform
   - Corrupted download
   - Insufficient disk space
   - No write permission to binary location
   - Binary already running (Windows file lock)

---

### Configuration for Binary Updates

```toml
[Settings.AutoUpdate]
Enabled = true
Cron = "0 3 * * 0"
AllowPrerelease = false
StrictVersionCheck = true

# NEW: Binary-specific settings
[Settings.AutoUpdate.Binary]
KeepBackups = 2  # Number of backup binaries to keep
VerifyChecksums = true  # Verify asset checksums if available
AllowBetaAssets = false  # Allow downloading beta binary assets
```

---

### Updated Risk Assessment

| Risk | Installation Type | Likelihood | Impact | Mitigation |
|------|------------------|------------|--------|------------|
| Binary download fails | Binary | Medium | High | Retry logic, fallback to manual update |
| Wrong platform asset | Binary | Low | High | Strict platform detection, fallback on mismatch |
| Binary corrupted | Binary | Low | Critical | Checksum verification, keep backup |
| Permission denied | Binary | Medium | High | Check permissions before update, clear error messages |
| Windows file lock | Binary (Windows) | Medium | Medium | Rename-and-replace strategy, scheduled cleanup |
| Git checkout breaks | Git | Low | High | Fallback to git pull, test thoroughly |
| Pip version mismatch | PyPI | Low | Medium | Strict version pinning, verification |

---

### Timeline Update

| Phase | Development | Testing | Documentation | Total |
|-------|-------------|---------|---------------|-------|
| Phase 1 | 4 hours | 2 hours | 1 hour | 7 hours |
| Phase 2 | 6 hours | 4 hours | 2 hours | 12 hours |
| Phase 3 (Git/Pip) | 4 hours | 4 hours | 1 hour | 9 hours |
| **Phase 3 (Binary)** | **8 hours** | **6 hours** | **2 hours** | **16 hours** |
| **New Total** | **22 hours** | **16 hours** | **6 hours** | **44 hours** |

Binary update implementation adds significant complexity (+16 hours) due to:
- Platform detection and asset matching
- Archive extraction logic
- OS-specific binary replacement strategies
- Extensive cross-platform testing requirements

---

### Recommended Approach for Binary Users

**Option 1: Full Binary Update Support (Complete)**
- Implement download → extract → replace logic
- Support all platforms from workflow (Windows, macOS, Linux)
- Provide rollback capability
- **Best for:** Users who want seamless auto-updates

**Option 2: Binary Update Notification Only (Simpler)**
- Detect binary installation
- Notify user of available update via logs
- Provide download URL for manual update
- Skip auto-update for binary installations
- **Best for:** Conservative approach, lower risk

**Option 3: Hybrid Approach (Balanced)**
- Phase 3a: Git/Pip strict versioning (9 hours)
- Phase 3b: Binary notification only (2 hours)
- Phase 4: Full binary update support (16 hours) - optional future enhancement
- **Best for:** Incremental rollout, validate approach before full implementation

---

## Updated Conclusion

With binary installation support, the implementation becomes significantly more complex. **Recommended phased approach:**

1. **Phase 1** (7 hours): Draft/prerelease validation - ALL installation types
2. **Phase 2** (12 hours): Version verification - ALL installation types
3. **Phase 3a** (9 hours): Strict versioning for Git/Pip only
4. **Phase 3b** (2 hours): Binary update notification (manual download)
5. **Phase 4** (16 hours): Full binary auto-update - OPTIONAL

This allows binary users to benefit from update notifications (Phase 3b) while deferring the complex binary replacement logic (Phase 4) until git/pip implementations are proven stable.

**Critical for Binary Updates:**
- Must verify platform before download
- Must handle Windows file locking properly
- Must maintain executable permissions on Unix
- Must keep backup for rollback
- Must verify binary works before deleting backup

Binary updates are **high-risk, high-complexity** - recommend starting with notification-only approach and gathering user feedback before implementing full auto-update for binaries.
