"""
Parse duration values from config: integers (legacy) or suffixed strings (e.g. "1w", "60m").

Used by MyConfig.get_duration() so time-related keys can be stored as human-readable
strings (s/m/h/d/w/M) while remaining backwards compatible with plain numbers.
"""

from __future__ import annotations

import re
from typing import Any

# Multipliers for suffix -> seconds
SUFFIX_TO_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
    "M": 2592000,  # 30 days
}

# Same suffixes -> minutes (for keys that use minutes as base unit)
SUFFIX_TO_MINUTES = {
    "s": 1 / 60,
    "m": 1,
    "h": 60,
    "d": 1440,
    "w": 10080,
    "M": 43200,  # 30 days
}

_DURATION_PATTERN = re.compile(r"^\s*(-?\d+)\s*([sSmMhHdDwWM]?)\s*$")


def parse_duration_to_seconds(value: Any, fallback: int = -1) -> int:
    """
    Parse a config value to seconds. Accepts int (return as-is) or str with optional suffix.

    Suffixes: s=seconds, m=minutes, h=hours, d=days, w=weeks, M=months (30 days).
    Plain number or unsuffixed string is treated as seconds (backwards compatibility).
    -1 / "-1" is allowed for "disabled" semantics.
    """
    if value is None:
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    s = str(value).strip()
    if not s:
        return fallback
    m = _DURATION_PATTERN.match(s)
    if not m:
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return fallback
    num = int(m.group(1))
    raw_suffix = (m.group(2) or "s").strip()
    # Uppercase M = month (30 days); lowercase m = minute
    if raw_suffix == "M":
        mult = SUFFIX_TO_SECONDS["M"]
    else:
        mult = SUFFIX_TO_SECONDS.get(raw_suffix.lower(), 1)
    return num * mult


def parse_duration_to_minutes(value: Any, fallback: int = -1) -> int:
    """
    Parse a config value to minutes. Same rules as parse_duration_to_seconds but
    returns minutes (for keys like StalledDelay, RssSyncTimer).
    """
    if value is None:
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    s = str(value).strip()
    if not s:
        return fallback
    m = _DURATION_PATTERN.match(s)
    if not m:
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return fallback
    num = int(m.group(1))
    raw_suffix = (m.group(2) or "m").strip()
    if raw_suffix == "M":
        mult = SUFFIX_TO_MINUTES["M"]
    else:
        mult = SUFFIX_TO_MINUTES.get(raw_suffix.lower(), 1)
    minutes = num * mult
    if 0 < minutes < 1:
        return 1
    return int(minutes)
