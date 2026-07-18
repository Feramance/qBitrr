#!/usr/bin/env python3
"""
Static drift check between gen_config field inventory and
``webui/src/pages/config/configFields.ts`` field paths.

Mirrors :mod:`scripts.openapi_check`: text/AST based, no Flask/WebUI runtime,
and no import of ``qBitrr`` (avoids logger/HOME side effects).

Inventory sources (union):

- ``ConfigField`` registry paths in ``qBitrr/gen_config/fields.py`` /
  ``fields_arr.py`` (primary)
- Legacy ``sections.py`` AST defaults still scanned for residual keys

Drift directions (non-zero exit unless allowlisted):

1. **Missing in FE** — a gen_config inventory leaf has no matching path in
   ``configFields.ts``.
2. **Missing in gen_config** — a FE field path has no matching inventory entry
   (except allowlisted extras such as tracker AoT schemas).

Optional (``--check-reload``): compare FE ``applyLive`` / ``requiresRestart``
hints against the static key sets in ``qBitrr/config_reload_policy.py``.

Usage::

    python scripts/config_fields_check.py
    python scripts/config_fields_check.py --check-reload
    make config-fields-check
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SECTIONS_PY = REPO_ROOT / "qBitrr" / "gen_config" / "sections.py"
FIELDS_PY = REPO_ROOT / "qBitrr" / "gen_config" / "fields.py"
FIELDS_ARR_PY = REPO_ROOT / "qBitrr" / "gen_config" / "fields_arr.py"
CONFIG_FIELDS_TS = REPO_ROOT / "webui" / "src" / "pages" / "config" / "configFields.ts"
CONFIG_FIELDS_GENERATED_TS = (
    REPO_ROOT / "webui" / "src" / "pages" / "config" / "configFields.generated.ts"
)
RELOAD_POLICY_PY = REPO_ROOT / "qBitrr" / "config_reload_policy.py"
ALLOWLIST_FILE = REPO_ROOT / "scripts" / "config_fields_allowlist.txt"

# export const NAME → inventory namespace for relative FE paths
_FE_BLOCK_PREFIX: dict[str, str] = {
    "SETTINGS_FIELDS": "Settings",
    "WEB_SETTINGS_FIELDS": "WebUI",
    "AUTH_SETTINGS_FIELDS": "WebUI",
    "QBIT_FIELDS": "qBit",
    "ARR_GENERAL_FIELDS": "Arr",
    "ARR_ENTRY_SEARCH_FIELDS": "Arr",
    "ARR_ENTRY_SEARCH_OMBI_FIELDS": "Arr",
    "ARR_ENTRY_SEARCH_OVERSEERR_FIELDS": "Arr",
    "ARR_TORRENT_FIELDS": "Arr",
    "ARR_SEEDING_FIELDS": "Arr",
    "ARR_TRACKER_FIELDS": "Tracker",
    "ARR_FE_ONLY_FIELDS": "Arr",
    "GENERATED_SETTINGS_FIELDS": "Settings",
    "GENERATED_WEBUI_FIELDS": "WebUI",
    "GENERATED_QBIT_FIELDS": "qBit",
    "GENERATED_ARR_FIELDS": "Arr",
}

_ROOT_TABLES: dict[tuple[str, str], str] = {
    ("_add_settings_section", "settings"): "Settings",
    ("_add_web_settings_section", "web_settings"): "WebUI",
    ("_add_qbit_section", "qbit"): "qBit",
    ("_gen_default_cat", "cat_default"): "Arr",
}

_PATH_RE = re.compile(r"path:\s*\[([^\]]+)\]")
_BLOCK_RE = re.compile(r"export const (\w+_FIELDS)\s*[:=]")
_FROZENSET_RE = re.compile(
    r"^(?P<name>[A-Z][A-Z0-9_]*)\s*=\s*frozenset\(\s*\{(?P<body>.*?)\}\s*\)",
    re.MULTILINE | re.DOTALL,
)
_STRING_RE = re.compile(r'["\']([^"\']+)["\']')


def _load_allowlist(path: Path) -> tuple[set[str], set[str]]:
    """Return ``(gen_only_ok, fe_only_ok)`` path sets from the allowlist file."""
    gen_only: set[str] = set()
    fe_only: set[str] = set()
    if not path.is_file():
        return gen_only, fe_only
    section: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            if "gen_config only" in line.lower() or "missing in fe" in line.lower():
                section = "gen"
            elif "fe only" in line.lower() or "missing in gen" in line.lower():
                section = "fe"
            continue
        if section == "gen":
            gen_only.add(line)
        elif section == "fe":
            fe_only.add(line)
    return gen_only, fe_only


def _allowlisted(path: str, patterns: set[str]) -> bool:
    """True when ``path`` equals or matches a trailing-``*`` allowlist pattern."""
    if path in patterns:
        return True
    for pattern in patterns:
        if pattern.endswith("*") and path.startswith(pattern[:-1]):
            return True
    return False


class _SectionsCollector(ast.NodeVisitor):
    """Collect legacy sections.py default-line fields and ``table.add`` edges."""

    def __init__(self) -> None:
        self.func: str | None = None
        self.fields: list[tuple[str | None, str | None, str]] = []
        self.adds: list[tuple[str | None, str | None, str, str | None]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev, self.func = self.func, node.name
        self.generic_visit(node)
        self.func = prev

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "add"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            key = node.args[0].value
            child = node.args[1].id if isinstance(node.args[1], ast.Name) else None
            parent = node.func.value.id if isinstance(node.func.value, ast.Name) else None
            self.adds.append((self.func, parent, key, child))
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "_gen_default_line"
            and len(node.args) >= 3
        ):
            table = node.args[0]
            field = node.args[2]
            tname = table.id if isinstance(table, ast.Name) else None
            fname = field.value if isinstance(field, ast.Constant) else None
            if isinstance(fname, str):
                self.fields.append((self.func, tname, fname))
        self.generic_visit(node)


_REGISTRY_PREFIX: dict[str, str] = {
    "SETTINGS_FIELDS": "Settings",
    "WEBUI_FIELDS": "WebUI",
    "QBIT_FIELDS": "qBit",
    "ARR_FIELDS": "Arr",
}


def inventory_registry_fields(source: str) -> set[str]:
    """Return dotted paths from ``ConfigField((...path...), ...)`` in registry modules."""
    tree = ast.parse(source)
    out: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.current_prefix: str | None = None

        def visit_Assign(self, node: ast.Assign) -> None:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _REGISTRY_PREFIX:
                    prev = self.current_prefix
                    self.current_prefix = _REGISTRY_PREFIX[target.id]
                    self.visit(node.value)
                    self.current_prefix = prev
                    return
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if (
                isinstance(node.target, ast.Name)
                and node.target.id in _REGISTRY_PREFIX
                and node.value is not None
            ):
                prev = self.current_prefix
                self.current_prefix = _REGISTRY_PREFIX[node.target.id]
                self.visit(node.value)
                self.current_prefix = prev
                return
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name == "ConfigField" and node.args and self.current_prefix:
                path_node = node.args[0]
                parts: list[str] = []
                if isinstance(path_node, ast.Tuple):
                    for elt in path_node.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            parts.append(elt.value)
                if parts:
                    out.add(f"{self.current_prefix}.{'.'.join(parts)}")
            self.generic_visit(node)

    Visitor().visit(tree)
    return out


def inventory_gen_config(sections_source: str, *registry_sources: str) -> set[str]:
    """Combine registry ``ConfigField`` paths with residual sections.py defaults."""
    keys = _inventory_sections_ast(sections_source)
    for source in registry_sources:
        if source:
            keys |= inventory_registry_fields(source)
    return keys


def _inventory_sections_ast(source: str) -> set[str]:
    """Return dotted inventory paths from legacy default-line calls in sections.py."""
    tree = ast.parse(source)
    collector = _SectionsCollector()
    collector.visit(tree)

    table_paths: dict[tuple[str | None, str], str] = dict(_ROOT_TABLES)
    changed = True
    while changed:
        changed = False
        for func, parent, key, child in collector.adds:
            if child is None or parent is None:
                continue
            parent_path = table_paths.get((func, parent))
            if parent_path is None:
                for (_f, p), path in list(table_paths.items()):
                    if p == parent:
                        parent_path = path
                        break
            if parent_path is None:
                continue
            new_path = f"{parent_path}.{key}"
            if table_paths.get((func, child)) != new_path:
                table_paths[(func, child)] = new_path
                changed = True

    out: set[str] = set()
    for func, tname, fname in collector.fields:
        path = table_paths.get((func, tname)) if tname else None
        if path is None and tname is not None:
            for (_f, p), pth in table_paths.items():
                if p == tname:
                    path = pth
                    break
        if path is None:
            path = f"?{func}.{tname}"
        out.add(f"{path}.{fname}")
    return out


def inventory_fe_fields(source: str) -> set[str]:
    """Return dotted inventory paths from ``configFields.ts`` field ``path`` arrays."""
    blocks = list(_BLOCK_RE.finditer(source))
    out: set[str] = set()
    for i, match in enumerate(blocks):
        name = match.group(1)
        prefix = _FE_BLOCK_PREFIX.get(name)
        if prefix is None:
            continue
        start = match.end()
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(source)
        body = source[start:end]
        for path_match in _PATH_RE.finditer(body):
            parts = _STRING_RE.findall(path_match.group(1))
            if not parts:
                continue
            if prefix in ("Settings", "WebUI") and parts[0] == prefix:
                out.add(".".join(parts))
            elif prefix == "Tracker":
                joined = ".".join(parts)
                out.add(f"Arr.Torrent.Trackers[].{joined}")
                out.add(f"qBit.Trackers[].{joined}")
            else:
                out.add(f"{prefix}.{'.'.join(parts)}")
    return out


_GENERATED_BLOCK_RE = re.compile(r"export const (GENERATED_(\w+)_FIELDS)\s*[:=]")
_GENERATED_PREFIX = {
    "SETTINGS": "Settings",
    "WEBUI": "WebUI",
    "QBIT": "qBit",
    "ARR": "Arr",
}


def inventory_fe_generated_fields(source: str) -> set[str]:
    """Inventory paths from ``configFields.generated.ts`` GENERATED_* exports."""
    blocks = list(_GENERATED_BLOCK_RE.finditer(source))
    out: set[str] = set()
    for i, match in enumerate(blocks):
        kind = match.group(2)
        prefix = _GENERATED_PREFIX.get(kind)
        if prefix is None:
            continue
        start = match.end()
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(source)
        body = source[start:end]
        for path_match in _PATH_RE.finditer(body):
            parts = _STRING_RE.findall(path_match.group(1))
            if not parts:
                continue
            if prefix in ("Settings", "WebUI") and parts[0] == prefix:
                out.add(".".join(parts))
            else:
                out.add(f"{prefix}.{'.'.join(parts)}")
    return out


def _enclosing_object(source: str, index: int) -> str | None:
    """Return the nearest brace-balanced `{...}` that contains ``index``, or None."""
    start = None
    depth = 0
    i = index
    while i >= 0:
        ch = source[i]
        if ch == "}":
            depth += 1
        elif ch == "{":
            if depth == 0:
                start = i
                break
            depth -= 1
        i -= 1
    if start is None:
        return None
    depth = 0
    for j in range(start, len(source)):
        ch = source[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : j + 1]
    return None


def inventory_fe_reload_hints(source: str) -> tuple[set[str], set[str]]:
    """Return ``(apply_live_keys, requires_restart_keys)`` from FE field objects."""
    blocks = list(_BLOCK_RE.finditer(source))
    apply_live: set[str] = set()
    requires_restart: set[str] = set()
    for i, match in enumerate(blocks):
        name = match.group(1)
        prefix = _FE_BLOCK_PREFIX.get(name)
        if prefix is None or prefix == "Tracker":
            continue
        start = match.end()
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(source)
        body = source[start:end]
        for path_match in _PATH_RE.finditer(body):
            parts = _STRING_RE.findall(path_match.group(1))
            if not parts:
                continue
            if prefix in ("Settings", "WebUI") and parts[0] == prefix:
                key = ".".join(parts)
            else:
                key = f"{prefix}.{'.'.join(parts)}"
            obj = _enclosing_object(body, path_match.start())
            if obj is None:
                continue
            if re.search(r"applyLive\s*:\s*true", obj):
                apply_live.add(key)
            if re.search(r"requiresRestart\s*:\s*true", obj):
                requires_restart.add(key)
    return apply_live, requires_restart


def _parse_frozensets(source: str) -> dict[str, set[str]]:
    """Parse top-level ``NAME = frozenset({...})`` string members from a Python file."""
    out: dict[str, set[str]] = {}
    for match in _FROZENSET_RE.finditer(source):
        out[match.group("name")] = set(_STRING_RE.findall(match.group("body")))
    return out


def check_reload_hints(fe_source: str, policy_source: str) -> list[str]:
    """Return human-readable reload-hint mismatches (empty when aligned)."""
    apply_live, requires_restart = inventory_fe_reload_hints(fe_source)
    frozen = _parse_frozensets(policy_source)
    settings_live = frozen.get("SETTINGS_LIVE_KEYS", set())
    settings_full = frozen.get("SETTINGS_FULL_RESTART_KEYS", set())
    webui_restart = frozen.get("WEBUI_RESTART_KEYS", set())
    frontend_only = frozen.get("FRONTEND_ONLY_KEYS", set())

    problems: list[str] = []
    for key in sorted(apply_live):
        if not key.startswith(("Settings.", "WebUI.")):
            continue
        if key in settings_live or key in frontend_only:
            continue
        if key in settings_full or key in webui_restart:
            problems.append(
                f"FE applyLive=true for {key} but config_reload_policy classifies restart"
            )
            continue
        # Arr / other prefixes are out of scope for this optional check
        if key.startswith("Settings.") and key not in settings_live:
            problems.append(
                f"FE applyLive=true for {key} but not in SETTINGS_LIVE_KEYS / FRONTEND_ONLY_KEYS"
            )

    for key in sorted(requires_restart):
        if key.startswith("Settings.") and key not in settings_full:
            problems.append(
                f"FE requiresRestart=true for {key} but not in SETTINGS_FULL_RESTART_KEYS"
            )
        if key.startswith("WebUI.") and key not in webui_restart:
            problems.append(f"FE requiresRestart=true for {key} but not in WEBUI_RESTART_KEYS")

    # Policy LIVE keys that exist in FE inventory but lack applyLive hint
    fe_keys = inventory_fe_fields(fe_source)
    for key in sorted(settings_live):
        if key in fe_keys and key not in apply_live:
            problems.append(f"SETTINGS_LIVE_KEYS has {key} but FE field lacks applyLive=true")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-reload",
        action="store_true",
        help="Also compare FE applyLive/requiresRestart hints to config_reload_policy",
    )
    args = parser.parse_args(argv)

    if not SECTIONS_PY.is_file():
        print(f"config-fields-check: cannot find {SECTIONS_PY}", file=sys.stderr)
        return 2
    if not CONFIG_FIELDS_TS.is_file():
        print(f"config-fields-check: cannot find {CONFIG_FIELDS_TS}", file=sys.stderr)
        return 2

    registry_sources = []
    if FIELDS_PY.is_file():
        registry_sources.append(FIELDS_PY.read_text(encoding="utf-8"))
    if FIELDS_ARR_PY.is_file():
        registry_sources.append(FIELDS_ARR_PY.read_text(encoding="utf-8"))

    gen_keys = inventory_gen_config(
        SECTIONS_PY.read_text(encoding="utf-8"),
        *registry_sources,
    )
    fe_sources = [CONFIG_FIELDS_TS.read_text(encoding="utf-8")]
    if CONFIG_FIELDS_GENERATED_TS.is_file():
        fe_sources.append(CONFIG_FIELDS_GENERATED_TS.read_text(encoding="utf-8"))
    fe_keys: set[str] = set()
    for src in fe_sources:
        fe_keys |= inventory_fe_fields(src)
    # Also accept generated export const GENERATED_*_FIELDS blocks
    if CONFIG_FIELDS_GENERATED_TS.is_file():
        fe_keys |= inventory_fe_generated_fields(
            CONFIG_FIELDS_GENERATED_TS.read_text(encoding="utf-8")
        )
    gen_only_ok, fe_only_ok = _load_allowlist(ALLOWLIST_FILE)

    missing_in_fe = sorted(k for k in (gen_keys - fe_keys) if not _allowlisted(k, gen_only_ok))
    missing_in_gen = sorted(k for k in (fe_keys - gen_keys) if not _allowlisted(k, fe_only_ok))

    reload_problems: list[str] = []
    if args.check_reload:
        if not RELOAD_POLICY_PY.is_file():
            print(
                f"config-fields-check: cannot find {RELOAD_POLICY_PY}",
                file=sys.stderr,
            )
            return 2
        reload_problems = check_reload_hints(
            "\n".join(fe_sources),
            RELOAD_POLICY_PY.read_text(encoding="utf-8"),
        )

    if not missing_in_fe and not missing_in_gen and not reload_problems:
        extra = f", reload hints OK" if args.check_reload else ""
        print(
            f"config-fields-check: OK ({len(gen_keys)} gen_config keys, "
            f"{len(fe_keys)} FE paths{extra})"
        )
        return 0

    if missing_in_fe:
        print("config-fields-check: keys in gen_config/sections.py missing from configFields.ts:")
        for key in missing_in_fe:
            print(f"  + {key}")
    if missing_in_gen:
        print("config-fields-check: paths in configFields.ts with no gen_config default:")
        for key in missing_in_gen:
            print(f"  - {key}")
    if reload_problems:
        print("config-fields-check: applyLive / requiresRestart drift vs config_reload_policy:")
        for problem in reload_problems:
            print(f"  ! {problem}")
    print(
        "\nFix by updating configFields.ts / gen_config, or add an intentional "
        f"exception to {ALLOWLIST_FILE.name}."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
