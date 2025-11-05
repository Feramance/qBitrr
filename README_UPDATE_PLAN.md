# README Update Plan: Auto-Update Feature Changes

**Created:** 2025-11-05
**Status:** Planning Phase (READ-ONLY)
**Goal:** Document the new GitHub release-based auto-update behavior with non-draft validation

---

## Current State in README

The README currently describes auto-updates at:
- **Line 78-83**: Feature overview (core features section)
- **Line 116-121**: pip installation auto-update config example
- **Line 457-488**: Detailed auto-update section

### Current Description (Lines 457-488):

```markdown
### 🔄 Auto-Updates & Restarts

**Scheduled Updates:**
```toml
[Settings]
AutoUpdateEnabled = true
AutoUpdateCron = "0 3 * * 0"  # Cron expression (default: Sunday 3 AM)
```

**Manual Updates:**
- Click "Update Now" in WebUI Config tab
- Automatically downloads latest version
- Performs graceful restart

**Restart Mechanism:**
- Uses `os.execv()` for in-place process replacement
- Maintains same PID (systemd-friendly)
- Works in Docker, systemd, native installs
- Cross-platform: Linux, macOS, Windows
- Graceful shutdown: closes databases, flushes logs, terminates child processes
```

**Issues with current documentation:**
- ❌ Doesn't explain HOW updates are determined (GitHub releases)
- ❌ Doesn't mention draft/prerelease handling
- ❌ Doesn't clarify different behavior for git/pip/binary installations
- ❌ Doesn't explain version verification
- ❌ No mention of GitHub API dependency

---

## Proposed Changes

### 1. Update Core Features Section (Lines 78-83)

**Current:**
```markdown
### 🔄 Auto-Updates & Self-Healing
- **Scheduled auto-updates** – update qBitrr on a cron schedule (default: weekly Sunday 3 AM)
- **Manual update trigger** – one-click updates from WebUI
- **Smart restart mechanism** – uses `os.execv()` for true in-place restarts (no supervisor needed)
- **Cross-platform compatibility** – works in Docker, systemd, native installs, Windows, Linux, macOS
- **Graceful shutdown** – cleanly closes databases, flushes logs, terminates child processes
```

**Proposed:**
```markdown
### 🔄 Auto-Updates & Self-Healing
- **GitHub release-based updates** – automatically checks for published (non-draft) releases via GitHub API
- **Scheduled auto-updates** – update qBitrr on a cron schedule (default: weekly Sunday 3 AM)
- **Manual update trigger** – one-click updates from WebUI
- **Installation-aware updates** – detects git/pip/binary installs and uses appropriate update method
- **Version verification** – confirms installed version matches target before restart
- **Smart restart mechanism** – uses `os.execv()` for true in-place restarts (no supervisor needed)
- **Cross-platform compatibility** – works in Docker, systemd, native installs, Windows, Linux, macOS
- **Graceful shutdown** – cleanly closes databases, flushes logs, terminates child processes
```

---

### 2. Update Auto-Update Configuration Examples

**Current pip example (Lines 116-121):**
```markdown
**Or enable auto-updates** in `config.toml`:
```toml
[Settings]
AutoUpdateEnabled = true
AutoUpdateCron = "0 3 * * 0"  # Weekly on Sunday at 3 AM
```
```

**Proposed enhancement:**
```markdown
**Or enable auto-updates** in `config.toml`:
```toml
[Settings]
AutoUpdateEnabled = true
AutoUpdateCron = "0 3 * * 0"  # Weekly on Sunday at 3 AM

# Advanced options (optional)
# AllowPrerelease = false  # Skip beta/rc releases (default: false)
# StrictVersionCheck = true  # Verify version before restart (default: true)
```

> 📝 Auto-updates check GitHub releases for new versions. Only published (non-draft, non-prerelease) releases trigger updates.
```

---

### 3. Replace Entire Auto-Update Section (Lines 457-488)

**NEW comprehensive section:**

```markdown
### 🔄 Auto-Updates & Restarts

qBitrr can automatically update itself by checking GitHub releases for new versions. The update behavior varies by installation type.

#### 🔍 How Updates Work

**Update Detection:**
1. 📡 Queries GitHub API for latest **published** (non-draft) release
2. 🔢 Compares release version with current version using semantic versioning
3. ⏩ Skips prereleases (beta, rc, alpha) unless explicitly enabled
4. 📦 Only updates when a newer **stable** version is available

**Installation Types:**

| Type | Detection | Update Method | Version Control |
|------|-----------|---------------|-----------------|
| **Git** | `.git` directory exists | `git checkout <tag>` or `git pull` | Checks out specific release tag |
| **PyPI** | Installed via pip | `pip install qBitrr2==<version>` | Installs exact version from PyPI |
| **Binary** | PyInstaller executable | Manual notification only | Logs download URL for manual update |

**Why different methods?**
- **Git installations** can checkout specific tags for precise version control
- **PyPI installations** can pin to exact versions for reliability
- **Binary installations** cannot self-update (would require replacing running executable), so qBitrr logs the download URL and version info for manual update

---

#### ⚙️ Configuration

**Basic Setup:**
```toml
[Settings]
AutoUpdateEnabled = true
AutoUpdateCron = "0 3 * * 0"  # Cron expression (default: Sunday 3 AM)
```

**Advanced Options:**
```toml
[Settings.AutoUpdate]
Enabled = true
Cron = "0 3 * * 0"              # Cron schedule (uses croniter)
AllowPrerelease = false          # Allow updating to beta/rc releases
StrictVersionCheck = true        # Verify installed version matches target before restart
```

**Cron Expression Examples:**
```toml
"0 3 * * 0"     # Every Sunday at 3:00 AM
"0 */6 * * *"   # Every 6 hours
"0 0 * * *"     # Daily at midnight
"0 2 * * 1-5"   # Weekdays at 2:00 AM
```

---

#### 📋 Update Process Flow

**For Git & PyPI Installations:**

1. **Check Phase:**
   - Fetch latest release from GitHub API
   - Validate release is not draft or prerelease
   - Compare versions (semantic versioning)
   - Skip if already on latest version

2. **Download Phase:**
   - **Git:** `git fetch --tags && git checkout v<version>`
   - **PyPI:** `pip install --upgrade qBitrr2==<version>`

3. **Verification Phase:**
   - Reload version information
   - Verify installed version matches target
   - Log warning if mismatch (configurable to block restart)

4. **Restart Phase:**
   - Gracefully shutdown (close DBs, flush logs)
   - Terminate child processes
   - Execute in-place restart via `os.execv()`
   - Maintain same PID (systemd-friendly)

**For Binary Installations:**

1. **Check Phase:** Same as above
2. **Notification:** Logs message with download URL and instructions
3. **Manual Update:** User downloads new binary from GitHub releases
4. **No Auto-Restart:** User manually restarts after replacing binary

Example binary update log:
```
[INFO] Update available: v5.4.2 -> v5.4.3
[INFO] Binary installation detected - manual update required
[INFO] Download: https://github.com/Feramance/qBitrr/releases/download/v5.4.3/qBitrr-<hash>-<platform>.tar.gz
[INFO] Instructions:
  1. Download the binary for your platform
  2. Extract the archive
  3. Replace current executable with new binary
  4. Restart qBitrr
```

---

#### 🔧 Manual Updates

**Via WebUI:**
- Navigate to **Config tab**
- Click **"Check for Updates"** to see available version
- Click **"Update Now"** button
- Confirm when prompted
- Application restarts automatically (git/pip only)

**Via Command Line:**

```bash
# Git installation
cd /path/to/qBitrr
git fetch --tags
git checkout v5.4.3  # or: git pull
qBitrr2  # restart

# PyPI installation
pip install --upgrade qBitrr2
# or: pip install qBitrr2==5.4.3  # specific version
qBitrr2  # restart

# Binary installation
# Download from: https://github.com/Feramance/qBitrr/releases/latest
# Extract and replace binary, then restart

# Docker installation
docker pull feramance/qbitrr:latest
docker restart qbitrr
# or: docker-compose pull && docker-compose up -d
```

---

#### 🔐 Security & Reliability

**GitHub API Dependency:**
- Auto-update requires GitHub API access
- Rate limit: 60 requests/hour (unauthenticated)
- Cron schedule should account for rate limits
- Failures are logged but don't crash the application

**Version Verification:**
- After update, qBitrr verifies installed version
- If `StrictVersionCheck = true`, restart is blocked on mismatch
- Helps catch failed updates or PyPI lag issues

**Draft & Prerelease Handling:**
- Draft releases are **always skipped** (unpublished)
- Prereleases (beta/rc/alpha) are skipped by default
- Enable with `AllowPrerelease = true` for bleeding-edge updates
- Useful for testing but not recommended for production

**Rollback:**
- Git installations: `git checkout <previous-tag>`
- PyPI installations: `pip install qBitrr2==<previous-version>`
- Binary installations: Keep backup of previous binary
- No automatic rollback (manual intervention required)

---

#### 🚀 Restart Mechanism

**How it Works:**
```python
os.execv(sys.executable, [sys.executable] + sys.argv)
```

**Benefits:**
- ✅ **Same PID** – systemd doesn't detect a restart
- ✅ **No supervisor** – doesn't require external process manager
- ✅ **Clean state** – fresh Python interpreter, no memory leaks
- ✅ **Fast** – near-instant restart (< 1 second)

**Supported Environments:**
- 🐳 **Docker** – container stays running, process restarts
- ⚙️ **systemd** – service remains "active", no restart count increment
- 💻 **Native** – works on Linux, macOS, Windows
- 🪟 **Windows** – handles different executable extensions (.exe, .cmd)

**Graceful Shutdown:**
1. Stop all Arr manager child processes
2. Close database connections
3. Flush log buffers to disk
4. Release file locks
5. Execute in-place restart

---

#### 🛠️ Restart via API

**Restart entire application:**
```bash
curl -X POST http://localhost:6969/api/restart

# With authentication
curl -X POST http://localhost:6969/api/restart \
  -H "Authorization: Bearer your-token"
```

**Restart specific Arr manager:**
```bash
curl -X POST http://localhost:6969/api/arr/radarr-movies/restart
```

**Check version info:**
```bash
curl http://localhost:6969/api/version
```

Response:
```json
{
  "current": "5.4.2-eb7a9ae5",
  "latest": "5.4.3",
  "update_available": true,
  "installation_type": "pip",
  "changelog_url": "https://github.com/Feramance/qBitrr/releases/tag/v5.4.3"
}
```

---

#### ⚠️ Troubleshooting Updates

**Update not triggering:**
- ✅ Check `AutoUpdateEnabled = true` in config
- ✅ Verify cron expression is valid (use [crontab.guru](https://crontab.guru))
- ✅ Check `Main.log` for GitHub API errors
- ✅ Ensure internet connectivity to api.github.com
- ✅ Check if already on latest version

**Version mismatch after update:**
- ✅ Review logs for pip/git errors
- ✅ Manually verify installation: `pip show qBitrr2` or `git describe`
- ✅ Check if PyPI is behind GitHub releases (can take hours)
- ✅ Try manual update to force correct version

**Binary updates not working:**
- ℹ️ **Expected behavior** – binaries cannot auto-update
- ✅ Check logs for download URL
- ✅ Download matching binary for your platform
- ✅ Extract and replace current executable
- ✅ Ensure new binary has execute permissions (Unix)

**Restart fails:**
- ✅ Check file permissions on qBitrr installation
- ✅ Review systemd journal if using systemd
- ✅ Verify no file locks preventing restart
- ✅ Check disk space for logs and databases
- ✅ Manual restart: Stop service, start again

**For systemd users:** See [SYSTEMD_SERVICE.md](SYSTEMD_SERVICE.md) for automatic restart configuration with `Restart=always`.

---
```

---

## Summary of Changes

### What's Being Added:

1. **Installation type awareness** - Documents different behavior for git/pip/binary
2. **GitHub release dependency** - Clarifies update source and draft handling
3. **Version verification** - Explains post-update validation
4. **Binary installation behavior** - Notification-only approach with manual steps
5. **Security considerations** - GitHub API rate limits, version verification
6. **Troubleshooting section** - Specific guidance for update issues
7. **Configuration examples** - Advanced options like AllowPrerelease
8. **API endpoints** - Version check and update trigger endpoints

### What's Being Improved:

1. **Clarity** - Much more explicit about how updates work
2. **Installation types** - Clear table showing differences
3. **Manual update guides** - Separate instructions for each type
4. **Restart mechanism** - Better explanation of `os.execv()` approach
5. **Rollback** - Mentions rollback options (though not automated)

### What's Staying the Same:

1. Configuration location and basic syntax
2. Cron expression format
3. WebUI update button functionality
4. API endpoints (just better documented)

---

## Implementation Checklist

When implementing these changes (after exiting read-only mode):

### Phase 1: Core Features Section
- [ ] Update lines 78-83 with new bullet points
- [ ] Add mention of GitHub release-based detection
- [ ] Add version verification point

### Phase 2: Quick Start Examples
- [ ] Update line 116-121 with new config example
- [ ] Add note about GitHub releases
- [ ] Add commented advanced options

### Phase 3: Main Auto-Update Section
- [ ] Replace lines 457-488 entirely
- [ ] Add "How Updates Work" subsection
- [ ] Add installation types table
- [ ] Add configuration section with advanced options
- [ ] Add update process flow (separate for each type)
- [ ] Add manual update instructions
- [ ] Add security & reliability section
- [ ] Add restart mechanism details
- [ ] Add API endpoints documentation
- [ ] Add troubleshooting subsection

### Phase 4: Cross-References
- [ ] Verify all internal links work
- [ ] Update table of contents if needed
- [ ] Check for consistency with other docs (API_DOCUMENTATION.md)

### Phase 5: Review
- [ ] Proofread for clarity
- [ ] Check formatting (Markdown rendering)
- [ ] Verify code blocks render correctly
- [ ] Test example commands
- [ ] Validate all URLs

---

## Estimated Changes

- **Lines added:** ~250-300
- **Lines removed:** ~30
- **Net addition:** ~220-270 lines
- **Sections affected:** 3 (core features, quickstart, auto-update details)
- **New sections:** 6 (installation types, update flow, security, troubleshooting, API)

---

## Related Files to Update

When implementing the full auto-update feature:

1. **README.md** (this plan) - User-facing documentation
2. **API_DOCUMENTATION.md** - Add `/api/version` endpoint details
3. **config.example.toml** - Add `[Settings.AutoUpdate]` section with comments
4. **SYSTEMD_SERVICE.md** - Mention interaction with auto-updates
5. **CONTRIBUTION.md** - Add note about testing updates in PRs

---

## Notes for Implementation

1. **Don't break existing configs** - New settings should be optional with sane defaults
2. **Keep backward compatibility** - Old `AutoUpdateEnabled` should still work
3. **Progressive disclosure** - Start with simple example, show advanced options later
4. **Platform awareness** - Mention Docker gets updates via image pulls, not auto-update
5. **Safety first** - Emphasize `StrictVersionCheck` and draft skipping

---

## Example Before/After

### BEFORE (Current - Line 457-488):
```markdown
### 🔄 Auto-Updates & Restarts

**Scheduled Updates:**
```toml
[Settings]
AutoUpdateEnabled = true
AutoUpdateCron = "0 3 * * 0"
```

**Manual Updates:**
- Click "Update Now" in WebUI Config tab
- Automatically downloads latest version
- Performs graceful restart
```

**Character count:** ~500 characters
**Clarity score:** 6/10 (vague about mechanism)

### AFTER (Proposed):
```markdown
### 🔄 Auto-Updates & Restarts

qBitrr can automatically update itself by checking GitHub releases...

[Full section as detailed above]
```

**Character count:** ~8,000 characters
**Clarity score:** 9/10 (comprehensive, actionable)

---

## Conclusion

This update transforms the auto-update documentation from a basic feature description into a comprehensive guide that:

1. ✅ Explains the underlying mechanism (GitHub releases)
2. ✅ Differentiates behavior across installation types
3. ✅ Provides troubleshooting guidance
4. ✅ Documents security considerations
5. ✅ Offers manual fallback instructions
6. ✅ Clarifies binary user experience (notification-only)

The documentation now matches the planned implementation from `GITHUB_RELEASE_UPDATE_PLAN.md` and sets accurate user expectations for each installation type.
