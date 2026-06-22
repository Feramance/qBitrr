# Open PR Validation Report — 2026-06-22

Audit of all open pull requests and unmerged remote branches against `origin/master` (HEAD: `e11da2c6`).

## Executive Summary

| Verdict | Count | Items |
|---------|-------|-------|
| **Implement** | 1 | #469 |
| **Implement after fixes** | 1 | #468 |
| **Defer** | 1 | #473 |
| **Reject** | 1 | `chore/self-hosted-workflows` |
| **Reject bulk merge / re-evaluate individually** | 1 | `chore/codebase-review-fixes` |

**Bottom line:** Merge #469 now. Mark #468 ready-for-review and merge after human sign-off. Rebase #473 before considering. Do **not** merge `chore/codebase-review-fixes` — it would regress `master` by deleting `arr_tracker_index.py`, `category_paths.py`, and `scripts/openapi_check.py`, and reverting multi-instance routing work already shipped in #464/#467. Delete the empty `chore/self-hosted-workflows` branch.

---

## Priority Queue

1. **#469** — Safe routine CI dependency bump; all checks green; automerge enabled.
2. **#468** — Valid bug fix with regression tests; mark draft → ready, then merge.
3. **#473** — Blocked on lockfile conflicts; defer until rebased.
4. **`chore/codebase-review-fixes`** — Reject as bulk merge; audit individual commits only if specific gaps remain.
5. **`chore/self-hosted-workflows`** — Reject; branch is behind master with no unique commits.

---

## Per-Item Dossiers

### #468 — fix: only mark torrents imported after successful Arr scan

| Field | Value |
|-------|-------|
| **URL** | https://github.com/Feramance/qBitrr/pull/468 |
| **Branch** | `cursor/deep-bug-finding-automation-fc78` |
| **Author** | Cursor (app/cursor) |
| **Draft** | Yes |
| **Mergeable** | MERGEABLE |
| **Diff** | 2 files, +68 / −3 |

**Verdict: Implement after fixes**

**Why:** On current `master`, `_process_imports()` in `qBitrr/arss.py` adds `sent_to_scan_hashes` before the Arr scan attempt and always tags `qBitrr-imported` even when `post_command` fails after retries. On the next loop the torrent is skipped as already imported, leaving completed files on disk without library import. The PR gates tag/hash/path updates on `scan_succeeded = True` only after a successful scan — correct fix with minimal scope.

**Tests:** Two new regression tests in `tests/test_arss_multi_instance.py` (`TestProcessImportsScanFailure`). All 18 unit tests pass locally on the PR branch (`QBITRR_OVERRIDES_DATA_PATH=/tmp/qbitrr-test python3 -m unittest discover -s tests`).

**Risks / open questions:**
- When `scan_cmd` is `None` (unknown Arr type), neither master nor the PR tags the torrent — behavior unchanged; acceptable.
- Draft status skips the full `package` matrix job in CI (by design in `pull_requests.yml`); mark ready-for-review to run platform builds before merge.

**Required follow-ups:**
1. Mark PR as ready for review (not draft).
2. Confirm full PR Build Checks pass after marking ready.
3. Merge via squash.

**Duplication check:** Not on `master`. Unrelated to merged multi-instance fixes (#464, #467, #451).

---

### #469 — Build(deps): Bump actions/checkout from 6 to 7

| Field | Value |
|-------|-------|
| **URL** | https://github.com/Feramance/qBitrr/pull/469 |
| **Branch** | `dependabot/github_actions/actions/checkout-7` |
| **Author** | Dependabot |
| **Draft** | No |
| **Mergeable** | MERGEABLE |
| **Diff** | 7 workflow files, +15 / −15 |

**Verdict: Implement**

**Why:** Mechanical bump of `actions/checkout@v6` → `@v7` across all workflows. All CI checks pass: pre-commit, PR Build Checks (Windows/macOS/Linux packages + Docker amd64/arm64), CodeQL, pre-commit.ci. Dependabot automerge job succeeded (minor/major actions bump treated as eligible).

**Risks:** v7 blocks fork PR checkout in `pull_request_target`/`workflow_run` — low risk for this repo (same-repo PRs only). ESM migration is internal to the action.

**Required follow-ups:** Merge when convenient (automerge may handle it).

**Automerge eligibility:** Yes — `enable-automerge` passed.

---

### #473 — Build(deps-dev): Bump @types/node from 25.9.3 to 26.0.0

| Field | Value |
|-------|-------|
| **URL** | https://github.com/Feramance/qBitrr/pull/473 |
| **Branch** | `dependabot/npm_and_yarn/webui/types/node-26.0.0` |
| **Author** | Dependabot |
| **Draft** | No |
| **Mergeable** | **CONFLICTING** |
| **Diff** | 2 files (`webui/package.json`, `webui/package-lock.json`) |

**Verdict: Defer**

**Why:** Major devDependency bump (`@types/node` 25 → 26). `package-lock.json` conflicts with `master` (recent Mantine/react-hook-form bumps #470–#475 changed lockfile structure). `pre-commit.ci` reports ERROR during mergeable check. PR Build Checks did not run (conflict). Automerge skipped (major version excluded by `.github/workflows/dependabot-auto-merge.yml`).

**Risks:** Type definition changes may surface new TS errors after rebase.

**Required follow-ups:**
1. Comment `@dependabot rebase` or manually rebase onto `master`.
2. Run `cd webui && npm ci && npm run lint && tsc -b` after rebase.
3. Re-evaluate only if CI is fully green.

**Automerge eligibility:** No (major version + conflicts).

---

### `chore/codebase-review-fixes` (no PR)

| Field | Value |
|-------|-------|
| **Branch** | `origin/chore/codebase-review-fixes` |
| **Commits ahead** | 52 (merge-base: `7d5a32d3`, stale) |
| **Diff** | 87 files, +5808 / −5165 |
| **Merge conflicts** | ~56 files (`git merge-tree` analysis) |

**Verdict: Reject bulk merge — re-evaluate individual commits only**

**Why:** This branch diverged from an old base before significant `master` work landed:
- **Would delete** `qBitrr/arr_tracker_index.py` (86 lines) and `qBitrr/category_paths.py` (137 lines) — modules added/refined on `master`.
- **Would delete** `scripts/openapi_check.py` (163 lines) present on `master`.
- **Would revert** multi-instance routing (`pause_by_instance`, `delete_by_instance`, per-instance DB queries) already fixed in #464/#467.
- **Would remove** `match_subcategories` and `normalize_category` usage in `qbit_category_manager.py`.

Many branch features are **already on `master`**: `qBitrr/duration_config.py`, `webui/src/config/durationUtils.ts`, `docker-compose.yml`, `scripts/rebuild_and_deploy.py`, `_TAGLESS_FIELD_MAP` / `register_search_mode()` in `arss.py`.

**Cherry-pick candidates (only after fresh diff vs current master):**
- None identified as clearly missing and safe without manual re-implementation. Any remaining unique fixes (e.g. db_recovery WAL tweaks, compose log caps) need line-by-line comparison — not worth bulk porting.

**Required follow-ups:**
1. Do not open a PR from this branch as-is.
2. Close or delete the branch after confirming no unique work remains.
3. If specific bugs are still open, file new focused PRs against current `master`.

---

### `chore/self-hosted-workflows` (no PR)

| Field | Value |
|-------|-------|
| **Branch** | `origin/chore/self-hosted-workflows` |
| **Commits ahead of master** | 0 |
| **Commits behind master** | Many (including v5.12.6 dependency bumps) |

**Verdict: Reject**

**Why:** No unique commits. Branch is obsolete — all work either merged elsewhere or abandoned.

**Required follow-ups:** Delete remote branch.

---

## Branches Without PRs (summary)

| Branch | Ahead | Verdict | Notes |
|--------|-------|---------|-------|
| `chore/codebase-review-fixes` | 52 | Reject bulk / split | Regresses master; stale base |
| `chore/self-hosted-workflows` | 0 | Reject | Empty; delete |

Stale `cursor/critical-bug-investigation-*` branches remain on remote but have no open PRs and were superseded by #464 — safe to delete.

---

## Recommended Actions

1. **Merge #469** — `actions/checkout` v7 bump; CI clean.
2. **Mark #468 ready-for-review** → verify full package matrix → merge.
3. **Defer #473** — `@dependabot rebase`, then validate WebUI build.
4. **Do not merge `chore/codebase-review-fixes`** — would cause regressions.
5. **Delete stale branches:** `chore/self-hosted-workflows`, duplicate `cursor/critical-bug-investigation-*` branches.
6. **No action on closed duplicate PRs** (#461–#466) — already triaged June 15.

---

## Appendix

### CI status snapshot

| Item | pre-commit | PR Build | Docker | pre-commit.ci | automerge |
|------|------------|----------|--------|---------------|-----------|
| #468 | pass | package skipped (draft) | pass | pass | skipped |
| #469 | pass | pass (3 platforms) | pass | pass | **pass** |
| #473 | — | not run | not run | **ERROR** (conflict) | skipped |

### Local validation commands run

```bash
git fetch origin master
gh pr list --state open --json ...
git diff master...origin/<branch> --stat
git merge-tree $(git merge-base master origin/<branch>) master origin/<branch>

# PR #468 tests (branch checkout)
QBITRR_OVERRIDES_DATA_PATH=/tmp/qbitrr-test python3 -m unittest discover -s tests -p 'test_*.py'
# Result: 18 tests OK (includes 2 new import-scan tests)

# Master baseline
QBITRR_OVERRIDES_DATA_PATH=/tmp/qbitrr-test python3 -m unittest discover -s tests -p 'test_*.py'
# Result: 16 tests OK
```

### Related merged PRs (context, not re-audited)

- #464 — multi-instance delete/pause routing and queue scoping (merged 2026-06-15)
- #467 — pause/resume_by_instance defaultdict retention (merged 2026-06-15)
- #451 — per-instance delete retry and recheck routing (merged 2026-06-10)
- #308 — HnR clear mode / premature removals (already on master)

### Master bug confirmed for #468

```python
# qBitrr/arss.py _process_imports() on master (lines 1765–1799)
self.sent_to_scan_hashes.add(torrent.hash)  # before scan
try:
    if scan_cmd:
        with_retry(lambda: self.client.post_command(...))
except Exception:
    ...
self.add_tags(torrent, ["qBitrr-imported"], instance_name)  # always runs
self.sent_to_scan.add(path)  # always runs
```
