from __future__ import annotations

from typing import Any

import requests
from packaging import version as version_parser

from qBitrr.bundled_data import patched_version

DEFAULT_REPOSITORY = "Feramance/qBitrr"


def normalize_version(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip()
    if cleaned.startswith(("v", "V")):
        cleaned = cleaned[1:]
    if "-" in cleaned:
        cleaned = cleaned.split("-", 1)[0]
    return cleaned or None


def is_newer_version(candidate: str | None, current: str | None = None) -> bool:
    if not candidate:
        return False
    normalized_current = normalize_version(current or patched_version)
    if not normalized_current:
        return True
    try:
        latest_version = version_parser.parse(candidate)
        current_version = version_parser.parse(normalized_current)
        return latest_version > current_version
    except Exception:
        return candidate != normalized_current


def fetch_latest_release(repo: str = DEFAULT_REPOSITORY, *, timeout: int = 10) -> dict[str, Any]:
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
