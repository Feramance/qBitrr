"""Validate WebUI config updates before persist / live reload."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from qBitrr.duration_config import _DURATION_PATTERN, parse_duration
from qBitrr.gen_config.fields import QBIT_FIELDS, SETTINGS_FIELDS, WEBUI_FIELDS, ConfigField
from qBitrr.gen_config.fields_arr import ARR_FIELDS

_ARR_SECTION_RE = re.compile(r"^(Radarr|Sonarr|Lidarr)([-.].+)?$", re.IGNORECASE)
_QBIT_SECTION_RE = re.compile(r"^qBit([-].+)?$", re.IGNORECASE)
_ANIMARR_RE = re.compile(r"^Animarr", re.IGNORECASE)
_FREE_SPACE_RE = re.compile(r"^-?\d+(\.\d+)?[KMGTP]?$", re.IGNORECASE)
_CHANGE_ME = "CHANGE_ME"
# Public bind hosts that require AllowInsecureExposure when AuthDisabled.
_PUBLIC_BIND_HOSTS = frozenset({"0.0.0.0", "::"})


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


def _as_number(value: Any) -> float | None:
    """Parse a numeric config value; return None when not a finite number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _is_change_me(value: Any) -> bool:
    return isinstance(value, str) and value.strip().upper() == _CHANGE_ME


def _as_duration(value: Any, *, unit: str) -> float | None:
    """Parse a duration config value (number or suffixed string) into native units.

    Returns None when ``value`` is not a valid duration expression.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        s = value.strip()
        if _DURATION_PATTERN.match(s):
            return float(parse_duration(s, unit=unit, fallback=0))
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _check_bounds(field: ConfigField, num: float, label: str) -> str | None:
    """Enforce minimum/maximum and -1 sentinel floors."""
    if field.minimum is not None and num < field.minimum:
        return f"{label} must be >= {field.minimum}"
    if field.maximum is not None and num > field.maximum:
        return f"{label} must be <= {field.maximum}"
    if field.allow_negative and field.minimum is None and num < -1:
        return f"{label} must be -1 or greater"
    if not field.allow_negative and field.minimum is None and num < 0:
        return f"{label} must be >= 0"
    return None


def _validate_value(field: ConfigField, value: Any) -> str | None:
    """Return an error message when ``value`` is invalid for ``field``."""
    label = field.label or field.key
    if value is None:
        if field.required:
            return f"{label} is required"
        return None

    kind = field.kind
    if kind in ("text", "password"):
        if field.required and (not isinstance(value, str) or not value.strip()):
            return f"{label} is required"
        if isinstance(value, str):
            return None
        return f"{label} must be a string"

    if kind == "duration":
        unit = field.native_unit or "seconds"
        num = _as_duration(value, unit=unit)
        if num is None:
            if field.required:
                return f"{label} is required"
            return f"{label} must be a number"
        return _check_bounds(field, num, label)

    if kind == "number":
        if isinstance(value, bool):
            return f"{label} must be a number"
        num = _as_number(value)
        if num is None:
            if field.required:
                return f"{label} is required"
            return f"{label} must be a number"
        return _check_bounds(field, num, label)

    if kind == "checkbox":
        if isinstance(value, bool):
            return None
        return f"{label} must be true or false"

    if kind == "select":
        # Numeric enums stored in TOML (e.g. RemoveTorrent -1/1/2/3/4)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if field.options:
                as_str = str(int(value)) if float(value).is_integer() else str(value)
                if as_str not in field.options and str(value) not in field.options:
                    return f"{label} must be one of: {', '.join(field.options)}"
            return None
        if not isinstance(value, str) or not value.strip():
            return f"{label} is required" if field.required else f"{label} must be a string"
        if field.options and value not in field.options:
            # Accept display labels that embed the numeric option, e.g. "Do not remove (-1)"
            match = re.search(r"\((-?\d+)\)", value)
            if match and match.group(1) in field.options:
                return None
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


def _validate_path_specific(key: str, value: Any) -> str | None:
    """Comment/overlay-equivalent checks that are not fully expressed on ConfigField."""
    if key == "Settings.CompletedDownloadFolder":
        folder = str(value or "").strip()
        if not folder or folder.upper() == _CHANGE_ME:
            return "Completed Download Folder must be set to a valid path"
        return None

    if key == "Settings.FreeSpace":
        raw = str(value or "").strip()
        if not raw:
            return "Free Space must be provided"
        if raw == "-1":
            return None
        if not _FREE_SPACE_RE.match(raw):
            return "Free Space must be -1 or a number optionally suffixed with K, M, G, T, or P"
        return None

    if key == "Settings.AutoUpdateCron":
        cron = str(value or "").strip()
        parts = cron.split()
        if len(parts) < 5 or len(parts) > 6:
            return "Auto Update Cron must contain 5 or 6 space-separated fields"
        return None

    if key == "Settings.AutoUpdateChannel":
        channel = str(value or "").strip().lower()
        if channel not in {"latest", "stable", "nightly"}:
            return "Auto Update Channel must be one of: latest, stable, nightly"
        return None

    if key == "WebUI.UrlBase":
        raw = str(value or "").strip()
        if not raw:
            return None
        if not raw.startswith("/"):
            return "UrlBase must start with / (e.g. /qbitrr)"
        if raw.endswith("/"):
            return "UrlBase must not end with a trailing slash"
        if "//" in raw:
            return "UrlBase is invalid"
        return None

    return None


def _get_nested(config: Any, dotted: str) -> Any:
    """Read a dotted key from a MyConfig-like object."""
    get = getattr(config, "get", None)
    if callable(get):
        return get(dotted, fallback=None)
    return None


def _validate_free_space_folder(config: Any) -> list[dict[str, str]]:
    """Require FreeSpaceFolder when FreeSpace monitoring is enabled."""
    free_space = _get_nested(config, "Settings.FreeSpace")
    raw = str(free_space if free_space is not None else "-1").strip()
    if raw == "-1":
        return []
    folder = _get_nested(config, "Settings.FreeSpaceFolder")
    folder_str = str(folder or "").strip()
    if not folder_str or folder_str.upper() == _CHANGE_ME:
        return [
            {
                "path": "Settings.FreeSpaceFolder",
                "message": "Free Space Folder is required when Free Space monitoring is enabled",
            }
        ]
    return []


def _validate_webui_insecure_exposure(config: Any) -> list[dict[str, str]]:
    """Require AllowInsecureExposure when AuthDisabled on a public bind."""
    auth_disabled = _get_nested(config, "WebUI.AuthDisabled")
    if auth_disabled is not True:
        return []
    host = str(_get_nested(config, "WebUI.Host") or "").strip()
    if host not in _PUBLIC_BIND_HOSTS:
        return []
    allowed = _get_nested(config, "WebUI.AllowInsecureExposure")
    # Missing key: legacy warn-only at boot; on explicit WebUI saves require acknowledgment
    # when AuthDisabled is explicitly true (new-install semantics).
    if allowed is True:
        return []
    return [
        {
            "path": "WebUI.AllowInsecureExposure",
            "message": (
                "AllowInsecureExposure must be true when AuthDisabled is true and "
                "Host is 0.0.0.0 or ::"
            ),
        }
    ]


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
        if not uri or (isinstance(uri, str) and not uri.strip()) or _is_change_me(uri):
            errors.append(
                {
                    "path": f"{section}.URI",
                    "message": "URI must be set to a valid URL when the instance is managed",
                }
            )
        if (
            not api_key
            or (isinstance(api_key, str) and not str(api_key).strip())
            or _is_change_me(api_key)
        ):
            errors.append(
                {
                    "path": f"{section}.APIKey",
                    "message": "APIKey must be provided when the instance is managed",
                }
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
        if not host or (isinstance(host, str) and not host.strip()) or _is_change_me(host):
            errors.append(
                {"path": f"{section}.Host", "message": "Host is required when qBit is enabled"}
            )
        if port is None or port == "":
            errors.append(
                {"path": f"{section}.Port", "message": "Port is required when qBit is enabled"}
            )
        else:
            num = _as_number(port)
            if num is None or not float(num).is_integer():
                errors.append({"path": f"{section}.Port", "message": "Port must be a number"})
            elif num < 1 or num > 65535:
                errors.append(
                    {"path": f"{section}.Port", "message": "Port must be between 1 and 65535"}
                )
    return errors


_ARR_INVARIANT_SUFFIXES = frozenset({"Managed", "URI", "APIKey", "Category"})
_QBIT_INVARIANT_SUFFIXES = frozenset({"Disabled", "Host", "Port"})
_WEBUI_INSECURE_KEYS = frozenset(
    {"WebUI.AuthDisabled", "WebUI.Host", "WebUI.AllowInsecureExposure"}
)
_FREE_SPACE_KEYS = frozenset({"Settings.FreeSpace", "Settings.FreeSpaceFolder"})


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


def _config_has_section(config: Any, section: str) -> bool:
    """Return True when ``section`` still exists in the in-memory config."""
    sections = getattr(config, "sections", None)
    if callable(sections):
        try:
            return section in sections()
        except Exception:
            pass
    cfg = getattr(config, "config", None)
    if isinstance(cfg, Mapping):
        return section in cfg
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
        if field is not None:
            message = _validate_value(field, value)
            if message:
                errors.append({"path": key, "message": message})

        path_message = _validate_path_specific(key, value)
        if path_message:
            errors.append({"path": key, "message": path_message})

    for section in sorted(touched_sections):
        # Renames/deletes null out old leaves; skip invariants when the section is gone.
        if not _config_has_section(config, section):
            continue
        if _section_needs_invariant_check(section, changed_keys):
            errors.extend(_validate_section_invariants(config, section))

    if changed_keys & _FREE_SPACE_KEYS:
        errors.extend(_validate_free_space_folder(config))

    if changed_keys & _WEBUI_INSECURE_KEYS:
        errors.extend(_validate_webui_insecure_exposure(config))

    return errors
