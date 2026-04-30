"""Helpers for normalising and matching qBittorrent category paths.

qBittorrent 4.6+ exposes hierarchical categories as a single string with ``/`` as
the separator (for example ``seed/tleech``). The Web API ``torrents/info`` filter
matches that string **exactly** — there is no parent/recursive lookup. These
helpers centralise the rules used across torrent fetch, queue sort, qBit-managed
category processing, and the Arr ``managed_objects`` lookup so that every site
treats subcategory strings identically.

See ``docs/configuration/qbittorrent.md`` for the user-facing reference.
"""

from __future__ import annotations

from collections.abc import Iterable

CATEGORY_SEPARATOR = "/"


def normalize_category(value: object) -> str:
    """Return a canonical form of ``value`` suitable for matching.

    - strips surrounding whitespace
    - drops leading and trailing separators (``/seed/tleech/`` → ``seed/tleech``)
    - collapses repeated separators (``seed//tleech`` → ``seed/tleech``)
    - trims whitespace from each segment

    Non-string input is coerced via ``str``; ``None`` → ``""``.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    parts = [seg.strip() for seg in s.split(CATEGORY_SEPARATOR)]
    parts = [seg for seg in parts if seg]
    return CATEGORY_SEPARATOR.join(parts)


def split_category(value: str) -> list[str]:
    """Return the segments of a normalised category path."""
    norm = normalize_category(value)
    if not norm:
        return []
    return norm.split(CATEGORY_SEPARATOR)


def category_parents(value: str) -> list[str]:
    """Return all proper parent prefixes of ``value`` (innermost-last).

    ``"seed/tleech/foo"`` -> ``["seed", "seed/tleech"]``.  An empty / single
    segment returns ``[]``.
    """
    parts = split_category(value)
    if len(parts) < 2:
        return []
    return [CATEGORY_SEPARATOR.join(parts[:i]) for i in range(1, len(parts))]


def is_subcategory_of(child: str, parent: str) -> bool:
    """Return ``True`` when ``child`` lives under ``parent`` (strict descendant).

    ``is_subcategory_of("seed/tleech", "seed")`` → ``True``.
    Equality returns ``False`` (use exact comparison for that case).
    """
    c = normalize_category(child)
    p = normalize_category(parent)
    if not c or not p or c == p:
        return False
    return c.startswith(p + CATEGORY_SEPARATOR)


def has_subcategory_separator(value: object) -> bool:
    """Return ``True`` when the (raw) value contains the qBit separator."""
    return CATEGORY_SEPARATOR in str(value or "")


def matches_configured(
    category: str,
    configured: Iterable[str],
    *,
    prefix: bool,
) -> str | None:
    """Return the configured key that owns ``category`` (or ``None``).

    - With ``prefix=False`` (default qBitrr behaviour) this is a plain exact
      membership check after normalisation.
    - With ``prefix=True`` an exact match still wins; otherwise the **longest**
      configured prefix that is an ancestor of ``category`` wins.

    The returned value is the **original** configured string (post-normalise)
    so callers can use it as a stable lookup key against ``managed_objects``.
    """
    target = normalize_category(category)
    if not target:
        return None
    normalised: list[tuple[str, str]] = []
    for raw in configured:
        n = normalize_category(raw)
        if n:
            normalised.append((n, n))
    if not normalised:
        return None
    for norm, original in normalised:
        if norm == target:
            return original
    if not prefix:
        return None
    best: tuple[int, str] | None = None
    for norm, original in normalised:
        if is_subcategory_of(target, norm):
            depth = norm.count(CATEGORY_SEPARATOR) + 1
            if best is None or depth > best[0]:
                best = (depth, original)
    return best[1] if best is not None else None


def find_overlap_conflicts(configured: Iterable[str]) -> list[tuple[str, str]]:
    """Return ``(parent, child)`` pairs in ``configured`` that overlap.

    Used by validators that disallow ambiguous prefix relationships across
    different owners (for example ``seed`` configured for one Arr while
    ``seed/tleech`` is configured for a different Arr).
    """
    items: list[str] = []
    for raw in configured:
        n = normalize_category(raw)
        if n and n not in items:
            items.append(n)
    out: list[tuple[str, str]] = []
    for parent in items:
        for child in items:
            if parent == child:
                continue
            if is_subcategory_of(child, parent):
                out.append((parent, child))
    return out
