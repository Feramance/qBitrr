#!/usr/bin/env python3
"""Deterministically classify GitHub issues and pull requests.

The module deliberately uses only the Python standard library.  PR classification is
intended to run from ``pull_request_target`` after checking out the base revision; it
never downloads or executes files from the pull-request head.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import fnmatch
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

CLASSIFIER_VERSION = "github-classifier-v1"
SCHEMA_VERSION = 1
MARKER_PREFIX = "<!-- automation-classification:v1:"
CHECK_NAME = "automation/classification"
MANAGED_PREFIXES = ("automation/", "codex/")

ISSUE_CATEGORIES = (
    "bug",
    "feature",
    "docs",
    "refactor",
    "test",
    "ci",
    "maintenance",
    "process_change",
    "support",
    "other",
    "ambiguous",
)
PR_CATEGORIES = (
    "package_update",
    "bug_fix",
    "feature",
    "docs",
    "refactor",
    "test",
    "ci",
    "maintenance",
    "other",
    "ambiguous",
)
FLAGS = (
    "security_sensitive",
    "breaking_change",
    "migration_required",
    "public_api_change",
    "workflow_permissions_change",
    "generated_code",
    "large_change",
    "managed_n8n_app",
    "fork_head",
)
CATEGORY_LABEL = {
    "bug": "automation/type:bug",
    "bug_fix": "automation/type:bug-fix",
    "feature": "automation/type:feature",
    "package_update": "automation/type:package-update",
    "docs": "automation/type:docs",
    "refactor": "automation/type:refactor",
    "test": "automation/type:test",
    "ci": "automation/type:ci",
    "maintenance": "automation/type:maintenance",
    "process_change": "automation/type:process-change",
    "support": "automation/type:support",
    "other": "automation/type:other",
    "ambiguous": "automation/type:ambiguous",
}
LABEL_CATEGORY = {value: key for key, value in CATEGORY_LABEL.items()}
OVERRIDE_CATEGORY = {
    "automation/override:" + label.removeprefix("automation/type:"): category
    for category, label in CATEGORY_LABEL.items()
}


def compact_json(value: Any) -> str:
    """Return canonical compact JSON with recursive key ordering."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    """Return the canonical SHA-256 digest for *value*."""
    return hashlib.sha256(compact_json(value).encode("utf-8")).hexdigest()


def policy_digest(policy: Mapping[str, Any]) -> str:
    """Return the digest of a classification policy."""
    return digest(policy)


def encode_contract(contract: Mapping[str, Any]) -> str:
    """Encode a contract as unpadded base64url JSON."""
    raw = compact_json(contract).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_contract(encoded: str) -> dict[str, Any]:
    """Decode an unpadded base64url contract."""
    padding = "=" * (-len(encoded) % 4)
    return json.loads(base64.urlsafe_b64decode(encoded + padding))


def non_automation_labels(labels: Iterable[str]) -> list[str]:
    """Return stable human-owned labels used in source digests."""
    return sorted({label for label in labels if not label.startswith(MANAGED_PREFIXES)})


def path_matches(path: str, patterns: Sequence[str]) -> bool:
    """Return whether a repository-relative path matches any policy glob."""
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def all_paths_match(paths: Sequence[str], patterns: Sequence[str]) -> bool:
    """Return true when a non-empty path set is entirely covered by patterns."""
    return bool(paths) and all(path_matches(path, patterns) for path in paths)


def issue_form_identity(title: str, body: str, labels: Sequence[str]) -> str:
    """Infer the stable issue-form identity from labels and rendered headings."""
    lower = f"{title}\n{body}".lower()
    label_set = {label.lower() for label in labels}
    if "bug" in label_set and "steps to reproduce" in lower:
        return "bug_report"
    if "enhancement" in label_set and "proposed solution" in lower:
        return "feature_request"
    if "documentation" in label_set and "documentation request" in lower:
        return "documentation_request"
    if "question" in label_set and "support request" in lower:
        return "support_request"
    if "requested change category" in lower:
        return "repository_change"
    return "api_or_unknown"


def material_scope_comments(comments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Select human comments that explicitly change scope or acceptance criteria."""
    selected: list[dict[str, Any]] = []
    marker = re.compile(r"(?im)^\s*(scope|requirements?|acceptance criteria|updated scope)\s*:")
    for comment in comments:
        user = comment.get("user") or {}
        login = str(user.get("login") or "")
        if user.get("type") == "Bot" or login.endswith("[bot]"):
            continue
        body = str(comment.get("body") or "")
        if marker.search(body):
            selected.append({"id": int(comment["id"]), "body": body.strip()})
    return sorted(selected, key=lambda item: item["id"])


def issue_digest_input(
    repository: str,
    issue: Mapping[str, Any],
    comments: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the canonical issue digest payload."""
    labels = [str(item["name"]) for item in issue.get("labels", [])]
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    return {
        "repository": repository,
        "issue_number": int(issue["number"]),
        "title": title,
        "body": body,
        "state": str(issue.get("state") or ""),
        "issue_form_identity": issue_form_identity(title, body, labels),
        "labels": non_automation_labels(labels),
        "scope_comments": material_scope_comments(comments),
    }


def pr_digest_input(
    repository: str,
    pull: Mapping[str, Any],
    files: Sequence[Mapping[str, Any]],
    labels: Sequence[str],
    linked_issues: Sequence[Mapping[str, Any]],
    classification_policy_digest: str,
) -> dict[str, Any]:
    """Build the canonical pull-request digest payload."""
    normalized_files = [
        {
            "filename": str(item["filename"]),
            "status": str(item.get("status") or ""),
            "additions": int(item.get("additions") or 0),
            "deletions": int(item.get("deletions") or 0),
        }
        for item in files
    ]
    normalized_links = [
        {"number": int(item["number"]), "category": str(item["category"])}
        for item in linked_issues
    ]
    return {
        "repository": repository,
        "pr_number": int(pull["number"]),
        "title": str(pull.get("title") or ""),
        "body": str(pull.get("body") or ""),
        "author": {
            "login": str((pull.get("user") or {}).get("login") or ""),
            "type": str((pull.get("user") or {}).get("type") or ""),
        },
        "base": {
            "ref": str((pull.get("base") or {}).get("ref") or ""),
            "sha": str((pull.get("base") or {}).get("sha") or ""),
        },
        "head": {
            "ref": str((pull.get("head") or {}).get("ref") or ""),
            "sha": str((pull.get("head") or {}).get("sha") or ""),
        },
        "files": sorted(normalized_files, key=lambda item: item["filename"]),
        "linked_issues": sorted(normalized_links, key=lambda item: item["number"]),
        "labels": non_automation_labels(labels),
        "classification_policy_digest": classification_policy_digest,
    }


def parse_repository_change(body: str) -> str | None:
    """Read the category selected in the repository-change issue form."""
    match = re.search(
        r"(?is)###\s+Requested change category\s*\n+\s*(Refactor|Test|CI|Maintenance|Process change|Other)\b",
        body,
    )
    if not match:
        return None
    return match.group(1).lower().replace(" ", "_")


def classify_issue(issue: Mapping[str, Any], override: str | None = None) -> tuple[str, list[str]]:
    """Classify an issue conservatively and return evidence codes."""
    if override in ISSUE_CATEGORIES:
        return override, ["authorized_override"]
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    labels = {str(item["name"]).lower() for item in issue.get("labels", [])}
    form = issue_form_identity(title, body, list(labels))
    form_map = {
        "bug_report": "bug",
        "feature_request": "feature",
        "documentation_request": "docs",
        "support_request": "support",
    }
    if form in form_map:
        return form_map[form], [f"issue_form:{form}"]
    selected = parse_repository_change(body)
    if selected:
        return selected, ["issue_form:repository_change"]
    label_evidence = {
        "bug": "bug",
        "enhancement": "feature",
        "documentation": "docs",
        "question": "support",
        "dependencies": "maintenance",
    }
    found = {category for label, category in label_evidence.items() if label in labels}
    if len(found) == 1:
        category = found.pop()
        return category, [f"repository_label:{category}"]
    return "ambiguous", ["insufficient_or_conflicting_evidence"]


def _exclusive_path_category(paths: Sequence[str], policy: Mapping[str, Any]) -> str | None:
    categories = (
        ("docs", "documentation_paths"),
        ("test", "test_paths"),
        ("ci", "ci_paths"),
        ("maintenance", "tooling_paths"),
    )
    matches = [category for category, key in categories if all_paths_match(paths, policy[key])]
    return matches[0] if len(matches) == 1 else None


def _workflow_action_version_only(file: Mapping[str, Any]) -> bool:
    """Accept a workflow diff only when every changed content line is an action ref."""
    patch = str(file.get("patch") or "")
    if not patch:
        return False
    changed_lines = [
        line
        for line in patch.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    return bool(changed_lines) and all(
        re.match(r"^[+-]\s*-?\s*uses:\s*[^\s@]+@[^\s#]+(?:\s*#.*)?$", line) is not None
        for line in changed_lines
    )


def dependency_only(
    paths: Sequence[str],
    policy: Mapping[str, Any],
    files: Sequence[Mapping[str, Any]] | None = None,
) -> bool:
    """Return whether all changes are narrowly-scoped dependency updates."""
    patterns = list(policy["dependency_files"]) + list(policy["dependency_companion_files"])
    workflow_files = [
        item
        for item in (files or ())
        if str(item.get("filename") or "").startswith(".github/workflows/")
    ]
    workflow_refs_only = bool(workflow_files) and all(
        _workflow_action_version_only(item) for item in workflow_files
    )
    return (
        all_paths_match(paths, patterns)
        and (
            any(path_matches(path, policy["dependency_files"]) for path in paths)
            or workflow_refs_only
        )
        and (not workflow_files or workflow_refs_only)
    )


def classify_pr(
    pull: Mapping[str, Any],
    files: Sequence[Mapping[str, Any]],
    labels: Sequence[str],
    linked_issues: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    override: str | None = None,
) -> tuple[str, list[str]]:
    """Classify a pull request using conservative precedence."""
    if override in PR_CATEGORIES:
        return override, ["authorized_override"]
    paths = [str(item["filename"]) for item in files]
    author = str((pull.get("user") or {}).get("login") or "")
    body = str(pull.get("body") or "")
    head_ref = str((pull.get("head") or {}).get("ref") or "")
    managed = (
        author == policy["managed_app_bot_login"]
        and "<!-- codex-issue-pr -->" in body
        and re.fullmatch(r"codex/issue-\d+-automated-fix", head_ref) is not None
    )
    linked_categories = {str(item["category"]) for item in linked_issues}
    if managed and len(linked_categories) == 1:
        linked = linked_categories.pop()
        mapped = "bug_fix" if linked == "bug" else linked
        if mapped in PR_CATEGORIES:
            return mapped, ["trusted_n8n_issue_handoff"]
    if author in policy["trusted_dependency_bots"] and dependency_only(paths, policy, files):
        return "package_update", ["trusted_dependency_bot", "dependency_only_files"]
    lower_labels = {label.lower() for label in labels}
    if dependency_only(paths, policy, files):
        if "dependencies" in lower_labels:
            return "package_update", ["maintainer_dependency_label", "dependency_only_files"]
        return "ambiguous", ["human_dependency_update_requires_label"]
    exclusive = _exclusive_path_category(paths, policy)
    if exclusive:
        return exclusive, [f"exclusive_paths:{exclusive}"]
    if len(linked_categories) == 1:
        linked = linked_categories.pop()
        mapped = "bug_fix" if linked == "bug" else linked
        if mapped in PR_CATEGORIES:
            return mapped, [f"linked_issue:{linked}"]
    conventional = re.match(r"^([a-z]+)(?:\([^)]*\))?!?:", str(pull.get("title") or ""), re.I)
    conventional_map = {
        "feat": "feature",
        "docs": "docs",
        "refactor": "refactor",
        "test": "test",
        "ci": "ci",
        "chore": "maintenance",
    }
    if conventional and conventional.group(1).lower() in conventional_map:
        category = conventional_map[conventional.group(1).lower()]
        return category, [f"conventional_title:{category}"]
    return "ambiguous", ["insufficient_or_conflicting_evidence"]


def determine_flags(
    pull: Mapping[str, Any] | None,
    files: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    text: str,
) -> list[str]:
    """Calculate independent risk and provenance flags."""
    paths = [str(item["filename"]) for item in files]
    lowered = text.lower()
    flags: set[str] = set()
    if any(path_matches(path, policy["security_sensitive_paths"]) for path in paths):
        flags.add("security_sensitive")
    if re.search(r"\bbreaking(?: change)?\b|!:|migration required", lowered):
        flags.add("breaking_change")
    if "migration" in lowered or any("migration" in path.lower() for path in paths):
        flags.add("migration_required")
    if any(path_matches(path, policy["public_api_paths"]) for path in paths):
        flags.add("public_api_change")
    if any(path.startswith(".github/workflows/") for path in paths):
        flags.add("workflow_permissions_change")
    if any(path_matches(path, policy["generated_file_patterns"]) for path in paths):
        flags.add("generated_code")
    if len(paths) > int(policy["large_change_file_count"]):
        flags.add("large_change")
    if pull:
        author = str((pull.get("user") or {}).get("login") or "")
        if author == policy["managed_app_bot_login"]:
            flags.add("managed_n8n_app")
        if (pull.get("head") or {}).get("repo", {}).get("full_name") != (
            pull.get("base") or {}
        ).get("repo", {}).get("full_name"):
            flags.add("fork_head")
    return sorted(flags)


class GitHubAPIError(RuntimeError):
    """GitHub REST failure with a machine-readable status and response body."""

    def __init__(self, method: str, url: str, status: int, detail: str) -> None:
        super().__init__(f"GitHub API {method} {url} failed: {status} {detail}")
        self.status = status
        self.detail = detail


class GitHubAPI:
    """Small authenticated GitHub REST client with pagination."""

    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.token = token
        self.root = f"https://api.github.com/repos/{repository}"

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        """Send one GitHub REST request and decode JSON."""
        url = path if path.startswith("https://") else self.root + path
        data = compact_json(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise GitHubAPIError(method, url, error.code, detail) from error

    def pages(self, path: str) -> list[Any]:
        """Read all pages from a list endpoint."""
        values: list[Any] = []
        separator = "&" if "?" in path else "?"
        for page in range(1, 101):
            batch = self.request("GET", f"{path}{separator}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise RuntimeError(f"Expected list from {path}")
            values.extend(batch)
            if len(batch) < 100:
                return values
        raise RuntimeError(f"Pagination limit exceeded for {path}")


def labels_from_item(item: Mapping[str, Any]) -> list[str]:
    """Extract label names from an issue or pull request."""
    return [str(label["name"]) for label in item.get("labels", [])]


def authorized_override(
    api: GitHubAPI, number: int, labels: Sequence[str], allowed: Sequence[str]
) -> str | None:
    """Return an override category only when its latest label event is authorized."""
    present = [label for label in labels if label in OVERRIDE_CATEGORY]
    if len(present) != 1:
        return None
    target = present[0]
    events = api.pages(f"/issues/{number}/events")
    matching = [
        event
        for event in events
        if event.get("event") == "labeled" and (event.get("label") or {}).get("name") == target
    ]
    if not matching:
        return None
    actor = str((matching[-1].get("actor") or {}).get("login") or "")
    permission = api.request("GET", f"/collaborators/{urllib.parse.quote(actor)}/permission")
    if str(permission.get("permission")) not in {"write", "maintain", "admin"}:
        return None
    category = OVERRIDE_CATEGORY[target]
    return category if category in allowed else None


def linked_issue_numbers(title: str, body: str, current_number: int) -> list[int]:
    """Extract same-repository issue references from PR text."""
    text = f"{title}\n{body}"
    matches: set[int] = set()
    keywords = re.compile(
        r"(?i)\b(?:close[sd]?|fix(?:es|ed)?|resolve[sd]?|refs?|references?|related\s+to|issue)\s*:?\s*"
    )
    for keyword in keywords.finditer(text):
        line_end = text.find("\n", keyword.end())
        segment = text[keyword.end() : line_end if line_end >= 0 else len(text)]
        matches.update(int(value) for value in re.findall(r"(?<![\w/])#(\d+)\b", segment))
    matches.discard(current_number)
    return sorted(matches)


def current_issue_classification(api: GitHubAPI, number: int) -> dict[str, Any] | None:
    """Return a linked issue's current type-label classification."""
    try:
        issue = api.request("GET", f"/issues/{number}")
    except GitHubAPIError as error:
        # Release notes copied into dependency PRs can reference upstream issue
        # numbers. A missing local issue is not a classifier failure.
        if error.status == 404:
            return None
        raise
    categories = [
        LABEL_CATEGORY[label] for label in labels_from_item(issue) if label in LABEL_CATEGORY
    ]
    if len(categories) == 1 and "automation/classification:ready" in labels_from_item(issue):
        return {"number": number, "category": categories[0]}
    return None


def ensure_labels(api: GitHubAPI) -> None:
    """Idempotently create or update every canonical automation label."""
    definitions = {
        "automation/classification:pending": ("D4C5F9", "Classification is pending"),
        "automation/classification:ready": ("0E8A16", "Classification contract is current"),
    }
    for label in CATEGORY_LABEL.values():
        definitions[label] = ("1D76DB", "GitHub-owned automation category")
        definitions[label.replace("automation/type:", "automation/override:")] = (
            "B60205",
            "Maintainer classification override",
        )
    existing = {str(item["name"]): item for item in api.pages("/labels")}
    for name, (color, description) in definitions.items():
        payload = {"name": name, "color": color, "description": description}
        if name in existing:
            api.request("PATCH", f"/labels/{urllib.parse.quote(name, safe='')}", payload)
        else:
            try:
                api.request("POST", "/labels", payload)
            except GitHubAPIError as error:
                # Concurrent runs can all observe a missing label. If another
                # run wins creation, converge by updating the created label.
                if error.status != 422 or '"already_exists"' not in error.detail:
                    raise
                api.request("PATCH", f"/labels/{urllib.parse.quote(name, safe='')}", payload)


def update_classification_labels(
    api: GitHubAPI, number: int, existing: Sequence[str], category: str, ready: bool
) -> None:
    """Replace prior managed type/state labels while preserving all other labels."""
    retained = [
        label
        for label in existing
        if not label.startswith("automation/type:")
        and label not in {"automation/classification:pending", "automation/classification:ready"}
    ]
    retained.append(CATEGORY_LABEL[category])
    retained.append(
        "automation/classification:ready" if ready else "automation/classification:pending"
    )
    # PUT is GitHub's set-labels operation. POST only adds labels and leaves
    # stale managed state behind, which can produce both pending/ready or
    # multiple type labels after reclassification.
    api.request("PUT", f"/issues/{number}/labels", {"labels": sorted(set(retained))})


def upsert_contract_comment(api: GitHubAPI, number: int, contract: Mapping[str, Any]) -> None:
    """Upsert the single bot-owned classification contract comment."""
    visible = f"Classified as {str(contract['category']).replace('_', ' ')}. Contract is current."
    body = f"{MARKER_PREFIX}{encode_contract(contract)} -->\n{visible}"
    comments = api.pages(f"/issues/{number}/comments")
    owned = [
        comment
        for comment in comments
        if str((comment.get("user") or {}).get("login")) == "github-actions[bot]"
        and MARKER_PREFIX in str(comment.get("body") or "")
    ]
    if owned:
        api.request("PATCH", f"/issues/comments/{owned[-1]['id']}", {"body": body})
    else:
        api.request("POST", f"/issues/{number}/comments", {"body": body})


def now_iso() -> str:
    """Return an RFC3339 UTC timestamp."""
    return (
        dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def contract(
    kind: str,
    category: str,
    flags: Sequence[str],
    source: str,
    policy: str,
    base_sha: str | None,
    head_sha: str | None,
    evidence: Sequence[str],
) -> dict[str, Any]:
    """Create the canonical contract object."""
    return {
        "schema_version": SCHEMA_VERSION,
        "classifier_version": CLASSIFIER_VERSION,
        "object_kind": kind,
        "category": category,
        "flags": sorted(set(flags)),
        "source_digest": source,
        "policy_digest": policy,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "evidence_codes": sorted(set(evidence)),
        "generated_at": now_iso(),
    }


def load_policy(path: str) -> dict[str, Any]:
    """Load and minimally validate classification policy JSON."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {
        "default_branch",
        "trusted_dependency_bots",
        "managed_app_bot_login",
        "documentation_paths",
        "test_paths",
        "ci_paths",
        "source_paths",
        "tooling_paths",
        "dependency_files",
        "dependency_companion_files",
        "generated_file_patterns",
        "security_sensitive_paths",
        "public_api_paths",
        "large_change_file_count",
    }
    missing = sorted(required - value.keys())
    if missing:
        raise ValueError(f"classification policy missing keys: {', '.join(missing)}")
    return value


def classify_live_issue(api: GitHubAPI, number: int, policy: Mapping[str, Any]) -> None:
    """Fetch, classify, and persist one issue contract."""
    issue = api.request("GET", f"/issues/{number}")
    if "pull_request" in issue:
        raise ValueError(f"#{number} is a pull request, not an issue")
    comments = api.pages(f"/issues/{number}/comments")
    labels = labels_from_item(issue)
    override = authorized_override(api, number, labels, ISSUE_CATEGORIES)
    category, evidence = classify_issue(issue, override)
    source = digest(issue_digest_input(api.repository, issue, comments))
    policy_hash = policy_digest(policy)
    result = contract("issue", category, [], source, policy_hash, None, None, evidence)
    upsert_contract_comment(api, number, result)
    update_classification_labels(api, number, labels, category, True)


def create_check(api: GitHubAPI, head_sha: str, source_hint: str) -> int:
    """Create the in-progress PR classification check."""
    value = api.request(
        "POST",
        "/check-runs",
        {
            "name": CHECK_NAME,
            "head_sha": head_sha,
            "status": "in_progress",
            "external_id": f"{CLASSIFIER_VERSION}:{source_hint}",
            "output": {
                "title": "Classifying pull request",
                "summary": "Using base-branch policy.",
            },
        },
    )
    return int(value["id"])


def finish_check(api: GitHubAPI, check_id: int, conclusion: str, title: str, summary: str) -> None:
    """Finalize a check run so an in-progress check is never orphaned."""
    api.request(
        "PATCH",
        f"/check-runs/{check_id}",
        {
            "status": "completed",
            "conclusion": conclusion,
            "completed_at": now_iso(),
            "output": {"title": title, "summary": summary[:65000]},
        },
    )


def classify_live_pr(api: GitHubAPI, number: int, policy: Mapping[str, Any]) -> None:
    """Fetch, classify, and persist one pull-request contract and head check."""
    pull = api.request("GET", f"/pulls/{number}")
    head_sha = str((pull.get("head") or {}).get("sha") or "")
    check_id = create_check(api, head_sha, "pending")
    try:
        files = api.pages(f"/pulls/{number}/files")
        labels = labels_from_item(pull)
        links = []
        for linked_number in linked_issue_numbers(
            str(pull.get("title") or ""), str(pull.get("body") or ""), number
        ):
            linked = current_issue_classification(api, linked_number)
            if linked:
                links.append(linked)
        override = authorized_override(api, number, labels, PR_CATEGORIES)
        category, evidence = classify_pr(pull, files, labels, links, policy, override)
        policy_hash = policy_digest(policy)
        source = digest(pr_digest_input(api.repository, pull, files, labels, links, policy_hash))
        flags = determine_flags(
            pull, files, policy, f"{pull.get('title') or ''}\n{pull.get('body') or ''}"
        )
        result = contract(
            "pull_request",
            category,
            flags,
            source,
            policy_hash,
            str((pull.get("base") or {}).get("sha") or ""),
            head_sha,
            evidence,
        )
        upsert_contract_comment(api, number, result)
        update_classification_labels(api, number, labels, category, True)
        api.request(
            "PATCH", f"/check-runs/{check_id}", {"external_id": f"{CLASSIFIER_VERSION}:{source}"}
        )
        finish_check(api, check_id, "success", f"Classified as {category}", compact_json(result))
    except Exception as error:
        update_classification_labels(api, number, labels_from_item(pull), "ambiguous", False)
        finish_check(api, check_id, "failure", "Classification failed", str(error))
        raise


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=("issue", "pr", "ensure-labels"))
    parser.add_argument("--number", type=int)
    parser.add_argument("--policy", default=".github/automation/classification-policy.json")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the live GitHub classifier."""
    args = parse_args(argv or sys.argv[1:])
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not repository or not token:
        raise RuntimeError("GITHUB_REPOSITORY and GITHUB_TOKEN are required")
    api = GitHubAPI(repository, token)
    ensure_labels(api)
    if args.kind == "ensure-labels":
        return 0
    if not args.number or args.number < 1:
        raise ValueError("--number must be a positive integer")
    policy = load_policy(args.policy)
    if args.kind == "issue":
        classify_live_issue(api, args.number, policy)
    else:
        classify_live_pr(api, args.number, policy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
