"""Shared loaders for qBit CategorySeeding / tracker config sections."""

from __future__ import annotations

from typing import Any

from qBitrr.config import CONFIG

_SEEDING_KEYS = (
    "DownloadRateLimitPerTorrent",
    "UploadRateLimitPerTorrent",
    "MaxUploadRatio",
    "MaxSeedingTime",
    "RemoveTorrent",
)

_HNR_KEYS: dict[str, Any] = {
    "HitAndRunMode": "disabled",
    "MinSeedRatio": 1.0,
    "MinSeedingTimeDays": 0,
    "HitAndRunPartialSeedRatio": 1.0,
    "TrackerUpdateBuffer": 0,
}


def load_qbit_seeding_config(
    section: str,
    *,
    include_ignore_younger: bool = True,
) -> dict[str, Any]:
    """Load CategorySeeding, trackers, and stalled settings for a qBit config section.

    Used by ``main.py`` instance init/reload and ``PlaceHolderArr._apply_qbit_seeding_config``.
    ``PlaceHolderArr`` passes ``include_ignore_younger=False`` because it reads the global
    ``Settings.IgnoreTorrentsYoungerThan`` in ``__init__`` instead.
    """
    default_seeding: dict[str, Any] = {}
    for key in _SEEDING_KEYS:
        if key == "MaxSeedingTime":
            default_seeding[key] = CONFIG.get_duration(
                f"{section}.CategorySeeding.{key}", fallback=-1
            )
        else:
            default_seeding[key] = CONFIG.get(f"{section}.CategorySeeding.{key}", fallback=-1)
    for key, fallback in _HNR_KEYS.items():
        if key == "TrackerUpdateBuffer":
            default_seeding[key] = CONFIG.get_duration(
                f"{section}.CategorySeeding.{key}", fallback=fallback
            )
        else:
            default_seeding[key] = CONFIG.get(
                f"{section}.CategorySeeding.{key}", fallback=fallback
            )

    category_overrides: dict[str, dict] = {}
    for cat_config in CONFIG.get(f"{section}.CategorySeeding.Categories", fallback=[]):
        if isinstance(cat_config, dict) and "Name" in cat_config:
            category_overrides[cat_config["Name"]] = cat_config

    result: dict[str, Any] = {
        "default_seeding": default_seeding,
        "category_overrides": category_overrides,
        "trackers": CONFIG.get(f"{section}.Trackers", fallback=[]),
        "stalled_delay": CONFIG.get_duration(
            f"{section}.CategorySeeding.StalledDelay", fallback=-1, unit="minutes"
        ),
        "match_subcategories": bool(CONFIG.get(f"{section}.MatchSubcategories", fallback=False)),
    }
    if include_ignore_younger:
        result["ignore_torrents_younger_than"] = CONFIG.get_duration(
            f"{section}.CategorySeeding.IgnoreTorrentsYoungerThan",
            fallback=CONFIG.get_duration("Settings.IgnoreTorrentsYoungerThan", fallback=180),
        )
    return result
