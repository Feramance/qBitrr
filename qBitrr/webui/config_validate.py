"""Validate WebUI config updates before persist / live reload."""

from __future__ import annotations

import re
from typing import Any

from qBitrr.gen_config.fields import QBIT_FIELDS, SETTINGS_FIELDS, WEBUI_FIELDS, ConfigField
from qBitrr.gen_config.fields_arr import ARR_FIELDS

_ARR_SECTION_RE = re.compile(r"^(Radarr|Sonarr|Lidarr)([-.].+)?$", re.IGNORECASE)
_QBIT_SECTION_RE = re.compile(r"^qBit([-].+)?$", re.IGNORECASE)
_ANIMARR_RE = re.compile(r"^Animarr", re.IGNORECASE)


def _field_index() -> dict[str, ConfigField]:
    """Map relative dotted paths to registry fields for each section type."""
    index: dict[str, ConfigField] = {}
    for field in SETTINGS_FIELDS:
        index[f"Settings.{field.dotted}"] = field
    for field in WEBUI_FIELDS:
        index[f"WebUI.{field.dotted}"] = field
    for field in QBIT_FIELDS:
        index[f"qBit.{field.dotted}"] = field
    for field in ARR_FIELDS:
        index[f"Arr.{field.dotted}"] = field
    return index


_FIELD_INDEX = _field_index()


def _resolve_field(dotted_key: str) -> ConfigField | None:
    """Resolve a dotted change key to a ConfigField, if known."""
    if dotted_key in _FIELD_INDEX:
        return _FIELD_INDEX[dotted_key]
    parts = dotted_key.split(".", 1)
    if len(parts) != 2:
        return None
    section, rest = parts
    if _QBIT_SECTION_RE.match(section):
        return _FIELD_INDEX.get(f"qBit.{rest}")
    if _ARR_SECTION_RE.match(section):
        return _FIELD_INDEX.get(f"Arr.{rest}")
    return None


def _validate_value(field: ConfigField, value: Any) -> str | None:
    """Return an error message when ``value`` is invalid for ``field``."""
    label = field.label or field.key
    if value is None:
        if field.required:
            return f"{label} is required"
        return None

    kind = field.kind
    if kind in ("text", "password", "duration"):
        if field.required and (not isinstance(value, str) or not value.strip()):
            # Allow non-string numbers for duration-like values that arrived as ints
            if kind == "duration" and isinstance(value, (int, float)):
                return None
            return f"{label} is required"
        if isinstance(value, str) or kind == "duration":
            return None
        return f"{label} must be a string"

    if kind == "number":
        if isinstance(value, bool):
            return f"{label} must be a number"
        if isinstance(value, (int, float)):
            if not field.allow_negative and value < 0:
                return f"{label} must be >= 0"
            return None
        if isinstance(value, str) and value.strip():
            try:
                num = float(value)
            except ValueError:
                return f"{label} must be a number"
            if not field.allow_negative and num < 0:
                return f"{label} must be >= 0"
            return None
        if field.required:
            return f"{label} is required"
        return f"{label} must be a number"

    if kind == "checkbox":
        if isinstance(value, bool):
            return None
        return f"{label} must be true or false"

    if kind == "select":
        if not isinstance(value, str) or not value.strip():
            return f"{label} is required" if field.required else f"{label} must be a string"
        if field.options and value not in field.options:
            return f"{label} must be one of: {', '.join(field.options)}"
        return None

    if kind == "tags":
        if isinstance(value, list):
            return None
        if isinstance(value, str):
            return None
        return f"{label} must be a list of tags"

    # mapping / trackers / unknown: structural checks only when clearly wrong
    if kind == "mapping" and value is not None and not isinstance(value, dict):
        return f"{label} must be a mapping"
    if kind == "trackers" and value is not None and not isinstance(value, list):
        return f"{label} must be a list"

    return None


def _get_nested(config: Any, dotted: str) -> Any:
    """Read a dotted key from a MyConfig-like object."""
    get = getattr(config, "get", None)
    if callable(get):
        return get(dotted, fallback=None)
    return None


def _validate_section_invariants(config: Any, section: str) -> list[dict[str, str]]:
    """Validate section-level invariants (managed Arr, enabled qBit)."""
    errors: list[dict[str, str]] = []
    if _ARR_SECTION_RE.match(section):
        managed = _get_nested(config, f"{section}.Managed")
        if managed is False:
            return errors
        uri = _get_nested(config, f"{section}.URI")
        api_key = _get_nested(config, f"{section}.APIKey")
        category = _get_nested(config, f"{section}.Category")
        if not uri or (isinstance(uri, str) and not uri.strip()):
            errors.append({"path": f"{section}.URI", "message": "URI is required when Managed"})
        if not api_key or (isinstance(api_key, str) and not str(api_key).strip()):
            errors.append(
                {"path": f"{section}.APIKey", "message": "APIKey is required when Managed"}
            )
        if not category or (isinstance(category, str) and not category.strip()):
            errors.append(
                {"path": f"{section}.Category", "message": "Category is required when Managed"}
            )
    elif _QBIT_SECTION_RE.match(section):
        disabled = _get_nested(config, f"{section}.Disabled")
        if disabled is True:
            return errors
        host = _get_nested(config, f"{section}.Host")
        port = _get_nested(config, f"{section}.Port")
        if not host or (isinstance(host, str) and not host.strip()):
            errors.append(
                {"path": f"{section}.Host", "message": "Host is required when qBit is enabled"}
            )
        if port is None or port == "":
            errors.append(
                {"path": f"{section}.Port", "message": "Port is required when qBit is enabled"}
            )
        elif isinstance(port, bool) or (
            not isinstance(port, (int, float))
            and not (isinstance(port, str) and str(port).strip().isdigit())
        ):
            errors.append({"path": f"{section}.Port", "message": "Port must be a number"})
    return errors


_ARR_INVARIANT_SUFFIXES = frozenset({"Managed", "URI", "APIKey", "Category"})
_QBIT_INVARIANT_SUFFIXES = frozenset({"Disabled", "Host", "Port"})


def _section_needs_invariant_check(section: str, changed_keys: set[str]) -> bool:
    """Return True when changes touch fields that affect section invariants."""
    if _ARR_SECTION_RE.match(section):
        suffixes = _ARR_INVARIANT_SUFFIXES
    elif _QBIT_SECTION_RE.match(section):
        suffixes = _QBIT_INVARIANT_SUFFIXES
    else:
        return False
    prefix = f"{section}."
    for key in changed_keys:
        if not key.startswith(prefix):
            continue
        leaf = key[len(prefix) :]
        if leaf in suffixes:
            return True
    return False


def validate_config_update(config: Any, changes: dict[str, Any]) -> list[dict[str, str]]:
    """Validate ``changes`` against the in-memory config after they were applied.

    Returns a list of ``{path, message}`` errors. An empty list means the update
    may be persisted and live-reloaded.
    """
    errors: list[dict[str, str]] = []
    touched_sections: set[str] = set()
    changed_keys = set(changes)

    for key, value in changes.items():
        if not isinstance(key, str) or not key.strip():
            errors.append({"path": str(key), "message": "Invalid configuration key"})
            continue
        if _ANIMARR_RE.match(key):
            errors.append(
                {
                    "path": key,
                    "message": "Animarr sections are no longer supported; use Sonarr",
                }
            )
            continue
        section = key.split(".", 1)[0]
        touched_sections.add(section)

        if value is None:
            # Deletion — skip type checks
            continue

        field = _resolve_field(key)
        if field is None:
            continue
        message = _validate_value(field, value)
        if message:
            errors.append({"path": key, "message": message})

    for section in sorted(touched_sections):
        if _section_needs_invariant_check(section, changed_keys):
            errors.extend(_validate_section_invariants(config, section))

    return errors
