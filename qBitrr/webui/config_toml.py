from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any


def _toml_set(doc, dotted_key: str, value: Any):
    from tomlkit import inline_table, table

    keys = dotted_key.split(".")
    cur = doc
    for k in keys[:-1]:
        # Reuse existing node if it is a dict or a dict-like container (e.g. tomlkit
        # Table/InlineTable), so we do not replace CategorySeeding and lose other keys
        # when only one dotted key (e.g. qBit.CategorySeeding.MaxSeedingTime) is set.
        existing = cur.get(k) if k in cur else None
        is_nested_container = isinstance(existing, Mapping)
        if k not in cur or not is_nested_container:
            cur[k] = table()
        cur = cur[k]

    # Convert plain Python dicts to inline tables for proper TOML serialization
    # This ensures dicts are rendered as inline {key = "value"} not as sections [key]
    if isinstance(value, dict) and not hasattr(value, "as_string"):
        inline = inline_table()
        inline.update(value)
        cur[keys[-1]] = inline
    else:
        cur[keys[-1]] = value


def _toml_delete(doc, dotted_key: str) -> None:
    keys = dotted_key.split(".")
    cur = doc
    parents = []
    for k in keys[:-1]:
        if not isinstance(cur, Mapping):
            return
        next_cur = cur.get(k)
        if not isinstance(next_cur, Mapping):
            return
        parents.append((cur, k))
        cur = next_cur
    if not isinstance(cur, Mapping):
        return
    cur.pop(keys[-1], None)
    for parent, key in reversed(parents):
        node = parent.get(key)
        if isinstance(node, Mapping) and not node:
            parent.pop(key, None)
        else:
            break


_SENSITIVE_KEY_PATTERNS = re.compile(
    r"(apikey|api_key|token|password|secret|passkey|credential)", re.IGNORECASE
)

# Placeholder returned by API/Web UI for sensitive values; never send real secrets.
# When config update sends this value for a sensitive key, the existing secret is left unchanged.
REDACTED_PLACEHOLDER = "[redacted]"


def _is_sensitive_dotted_key(dotted_key: str) -> bool:
    """Return True if the config key is considered sensitive (e.g. qBit.Password, Radarr-x.APIKey)."""
    if not dotted_key or "." not in dotted_key:
        return bool(_SENSITIVE_KEY_PATTERNS.search(dotted_key))
    return bool(_SENSITIVE_KEY_PATTERNS.search(dotted_key.split(".")[-1]))


def materialize_redacted_rename_secrets(config: Any, changes: dict[str, Any]) -> dict[str, Any]:
    """Fill ``[redacted]`` secrets on new section paths from deleted matching old paths.

    When renaming Arr/qBit sections, the client sends the redaction placeholder for
    secrets on the new name and ``null`` deletes for the old name. Applying that
    naively would skip the redacted write and then delete the only stored secret.
    """
    if not changes:
        return changes

    out = dict(changes)
    get = getattr(config, "get", None)

    for key, val in changes.items():
        if val is None or not isinstance(key, str) or "." not in key:
            continue
        if not (_is_sensitive_dotted_key(key) and str(val).strip() == REDACTED_PLACEHOLDER):
            continue
        new_section, relative = key.split(".", 1)
        for del_key, del_val in changes.items():
            if del_val is not None or not isinstance(del_key, str) or "." not in del_key:
                continue
            old_section, del_relative = del_key.split(".", 1)
            if old_section == new_section or del_relative != relative:
                continue
            stored = None
            if callable(get):
                stored = get(del_key, fallback=None)
            if (
                stored is not None
                and str(stored).strip()
                and str(stored).strip() != REDACTED_PLACEHOLDER
            ):
                out[key] = stored
            break
    return out


def _strip_sensitive_keys(obj: Any, _parent_key: str = "") -> Any:
    """Recursively redact values whose keys look like secrets."""
    if isinstance(obj, dict):
        return {
            k: (
                REDACTED_PLACEHOLDER
                if isinstance(v, str) and _SENSITIVE_KEY_PATTERNS.search(k)
                else _strip_sensitive_keys(v, k)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_strip_sensitive_keys(v, _parent_key) for v in obj]
    return obj


def _toml_to_jsonable(obj: Any) -> Any:
    try:
        if hasattr(obj, "unwrap"):
            return _toml_to_jsonable(obj.unwrap())
        if isinstance(obj, dict):
            return {k: _toml_to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_toml_to_jsonable(v) for v in obj]
        return obj
    except Exception:
        logging.getLogger("qBitrr.WebUI").debug("_toml_to_jsonable failed", exc_info=True)
        return obj
