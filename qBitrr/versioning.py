from __future__ import annotations

import os
from typing import Any

import requests
from packaging import version as version_parser

from qBitrr.bundled_data import patched_version

DEFAULT_REPOSITORY = "Feramance/qBitrr"
VALID_UPDATE_CHANNELS = frozenset({"latest", "stable", "nightly"})
DEFAULT_UPDATE_CHANNEL = "latest"
NIGHTLY_GIT_REF = "master"
NIGHTLY_PIP_URL = f"git+https://github.com/{DEFAULT_REPOSITORY}.git@{NIGHTLY_GIT_REF}"


def normalize_version(raw: str | None) -> str | None:
    """Normalize a version string for comparison.

    Strips a leading ``v``/``V`` and any ``+local`` metadata. Keeps the
    ``MAJOR.MINOR.PATCH-BUILD`` build segment so build bumps compare correctly.
    """
    if not raw:
        return None
    cleaned = raw.strip()
    if cleaned.startswith(("v", "V")):
        cleaned = cleaned[1:]
    if "+" in cleaned:
        cleaned = cleaned.split("+", 1)[0]
    return cleaned or None


def version_build_segment(normalized: str | None) -> int:
    """Return the build segment for a normalized ``MAJOR.MINOR.PATCH-BUILD`` version.

    Missing build segments are treated as ``1`` (stable).
    """
    if not normalized:
        return 1
    parts = normalized.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return int(parts[1])
    return 1


def is_stable_release_version(normalized: str | None) -> bool:
    """True when the version is a non-build release (build segment == 1)."""
    return version_build_segment(normalized) == 1


def normalize_update_channel(raw: str | None) -> str:
    """Normalize a channel name to ``latest``, ``stable``, or ``nightly``."""
    if not raw:
        return DEFAULT_UPDATE_CHANNEL
    cleaned = str(raw).strip().lower()
    if cleaned in VALID_UPDATE_CHANNELS:
        return cleaned
    return DEFAULT_UPDATE_CHANNEL


def github_request_headers() -> dict[str, str]:
    """Build GitHub API headers, including optional bearer token for rate limits."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = (
        os.environ.get("QBITRR_SETTINGS_GITHUB_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or ""
    ).strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def is_newer_version(candidate: str | None, current: str | None = None) -> bool:
    if not candidate:
        return False
    normalized_candidate = normalize_version(candidate)
    normalized_current = normalize_version(current or patched_version)
    if not normalized_current:
        return True
    if not normalized_candidate:
        return False
    try:
        latest_version = version_parser.parse(normalized_candidate)
        current_version = version_parser.parse(normalized_current)
        return latest_version > current_version
    except Exception:
        return normalized_candidate != normalized_current


def _release_payload_to_info(
    payload: dict[str, Any],
    *,
    repo: str,
    update_available: bool | None = None,
) -> dict[str, Any]:
    """Convert a GitHub release JSON object into the updater info dict."""
    raw_tag = (payload.get("tag_name") or payload.get("name") or "").strip()
    normalized = normalize_version(raw_tag)
    changelog = payload.get("body") or ""
    changelog_url = payload.get("html_url") or f"https://github.com/{repo}/releases"
    available = (
        bool(update_available) if update_available is not None else is_newer_version(normalized)
    )
    return {
        "raw_tag": raw_tag or None,
        "normalized": normalized,
        "changelog": changelog,
        "changelog_url": changelog_url,
        "update_available": available,
        "channel": None,
        "nightly_sha": None,
        "error": None,
    }


def _error_info(repo: str, message: str, *, channel: str | None = None) -> dict[str, Any]:
    if len(message) > 200:
        message = f"{message[:197]}..."
    return {
        "raw_tag": None,
        "normalized": None,
        "changelog": "",
        "changelog_url": f"https://github.com/{repo}/releases",
        "update_available": False,
        "channel": channel,
        "nightly_sha": None,
        "error": message,
    }


def fetch_latest_release(repo: str = DEFAULT_REPOSITORY, *, timeout: int = 10) -> dict[str, Any]:
    """Fetch latest non-draft, non-prerelease from GitHub (``latest`` channel)."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        response = requests.get(url, headers=github_request_headers(), timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return _error_info(repo, str(exc), channel="latest")

    if payload.get("draft", False):
        return _error_info(repo, "Latest release is a draft (not yet published)", channel="latest")

    if payload.get("prerelease", False):
        return _error_info(repo, "Latest release is a prerelease (beta/rc)", channel="latest")

    info = _release_payload_to_info(payload, repo=repo)
    info["channel"] = "latest"
    return info


def fetch_stable_release(repo: str = DEFAULT_REPOSITORY, *, timeout: int = 15) -> dict[str, Any]:
    """Fetch newest non-build GitHub release (build segment == 1)."""
    url = f"https://api.github.com/repos/{repo}/releases"
    try:
        response = requests.get(
            url,
            headers=github_request_headers(),
            params={"per_page": 30},
            timeout=timeout,
        )
        response.raise_for_status()
        releases = response.json()
    except Exception as exc:
        return _error_info(repo, str(exc), channel="stable")

    if not isinstance(releases, list):
        return _error_info(repo, "Unexpected GitHub releases response", channel="stable")

    for payload in releases:
        if not isinstance(payload, dict):
            continue
        if payload.get("draft") or payload.get("prerelease"):
            continue
        raw_tag = (payload.get("tag_name") or payload.get("name") or "").strip()
        normalized = normalize_version(raw_tag)
        if not is_stable_release_version(normalized):
            continue
        info = _release_payload_to_info(payload, repo=repo)
        info["channel"] = "stable"
        return info

    return _error_info(repo, "No stable (non-build) release found", channel="stable")


def fetch_nightly_commit(
    repo: str = DEFAULT_REPOSITORY,
    *,
    ref: str = NIGHTLY_GIT_REF,
    current_sha: str | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    """Fetch tip-of-branch commit info for the nightly channel."""
    url = f"https://api.github.com/repos/{repo}/commits/{ref}"
    try:
        response = requests.get(url, headers=github_request_headers(), timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return _error_info(repo, str(exc), channel="nightly")

    sha = (payload.get("sha") or "").strip()
    if not sha:
        return _error_info(
            repo, "Nightly commit SHA missing from GitHub response", channel="nightly"
        )

    commit = payload.get("commit") or {}
    message = ""
    if isinstance(commit, dict):
        message = (commit.get("message") or "").strip()
    short_sha = sha[:7]
    update_available = True
    if current_sha and current_sha.strip().lower() == sha.lower():
        update_available = False

    return {
        "raw_tag": f"nightly-{short_sha}",
        "normalized": f"nightly-{short_sha}",
        "changelog": message,
        "changelog_url": f"https://github.com/{repo}/commits/{ref}",
        "update_available": update_available,
        "channel": "nightly",
        "nightly_sha": sha,
        "error": None,
    }


def fetch_channel_release(
    channel: str | None = None,
    repo: str = DEFAULT_REPOSITORY,
    *,
    current_nightly_sha: str | None = None,
    timeout: int = 15,
) -> dict[str, Any]:
    """Resolve update target metadata for the configured release channel."""
    resolved = normalize_update_channel(channel)
    if resolved == "stable":
        return fetch_stable_release(repo, timeout=timeout)
    if resolved == "nightly":
        return fetch_nightly_commit(repo, current_sha=current_nightly_sha, timeout=timeout)
    return fetch_latest_release(repo, timeout=min(timeout, 10))


def fetch_release_by_tag(
    tag: str, repo: str = DEFAULT_REPOSITORY, *, timeout: int = 10
) -> dict[str, Any]:
    """Fetch a specific release by tag name."""
    if not tag.startswith(("v", "V")):
        tag = f"v{tag}"

    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    try:
        response = requests.get(url, headers=github_request_headers(), timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        message = str(exc)
        if len(message) > 200:
            message = f"{message[:197]}..."
        return {
            "changelog": "",
            "changelog_url": f"https://github.com/{repo}/releases/tag/{tag}",
            "error": message,
        }

    changelog = payload.get("body") or ""
    changelog_url = payload.get("html_url") or f"https://github.com/{repo}/releases/tag/{tag}"
    return {
        "changelog": changelog,
        "changelog_url": changelog_url,
        "error": None,
    }
