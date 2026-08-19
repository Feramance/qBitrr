#!/usr/bin/env python3
"""
Build-time codegen: emit ``webui/src/pages/config/configFields.generated.ts``
from the Python field registry AST (no qBitrr runtime import).

Custom validators/editors stay in FE overlays (``configFieldOverlays.ts``).

Usage::

    python scripts/generate_config_fields_ts.py
    make generate-config-fields
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIELDS_PY = REPO_ROOT / "qBitrr" / "gen_config" / "fields.py"
FIELDS_ARR_PY = REPO_ROOT / "qBitrr" / "gen_config" / "fields_arr.py"
RELOAD_POLICY_PY = REPO_ROOT / "qBitrr" / "config_reload_policy.py"
OUT = REPO_ROOT / "webui" / "src" / "pages" / "config" / "configFields.generated.ts"

_REGISTRY_PREFIX = {
    "SETTINGS_FIELDS": "Settings",
    "WEBUI_FIELDS": "WebUI",
    "QBIT_FIELDS": "qBit",
    "ARR_FIELDS": "Arr",
}
_FROZENSET_RE = re.compile(
    r"^(?P<name>[A-Z][A-Z0-9_]*)\s*=\s*frozenset\(\s*\{(?P<body>.*?)\}\s*\)",
    re.MULTILINE | re.DOTALL,
)
_STRING_RE = re.compile(r'["\']([^"\']+)["\']')


def _ts_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _const(node: ast.AST):
    if isinstance(node, ast.Constant):
        return node.value
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
    ):
        return -node.operand.value
    if isinstance(node, ast.Tuple):
        return tuple(_const(e) for e in node.elts)
    if isinstance(node, ast.List):
        return [_const(e) for e in node.elts]
    if isinstance(node, ast.Set):
        return frozenset(_const(e) for e in node.elts)
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        if node.id == "None":
            return None
    return None


def _parse_config_fields(source: str) -> dict[str, list[dict]]:
    tree = ast.parse(source)
    sections: dict[str, list[dict]] = {v: [] for v in _REGISTRY_PREFIX.values()}

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.prefix: str | None = None

        def visit_Assign(self, node: ast.Assign) -> None:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _REGISTRY_PREFIX:
                    prev = self.prefix
                    self.prefix = _REGISTRY_PREFIX[target.id]
                    self.visit(node.value)
                    self.prefix = prev
                    return
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if (
                isinstance(node.target, ast.Name)
                and node.target.id in _REGISTRY_PREFIX
                and node.value is not None
            ):
                prev = self.prefix
                self.prefix = _REGISTRY_PREFIX[node.target.id]
                self.visit(node.value)
                self.prefix = prev
                return
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name == "ConfigField" and self.prefix and node.args:
                path = _const(node.args[0])
                if not isinstance(path, tuple):
                    self.generic_visit(node)
                    return
                entry: dict = {
                    "path": list(path),
                    "key": ".".join(path),
                    "label": path[-1] if path else "",
                    "kind": "text",
                    "uiExpose": True,
                    "required": False,
                    "secure": False,
                    "applyLive": False,
                    "requiresRestart": False,
                }
                for kw in node.keywords:
                    if kw.arg == "label":
                        entry["label"] = _const(kw.value) or entry["label"]
                    elif kw.arg == "kind":
                        entry["kind"] = _const(kw.value) or "text"
                    elif kw.arg == "options":
                        opts = _const(kw.value)
                        if isinstance(opts, tuple):
                            entry["options"] = list(opts)
                    elif kw.arg == "required":
                        entry["required"] = bool(_const(kw.value))
                    elif kw.arg == "secure":
                        entry["secure"] = bool(_const(kw.value))
                    elif kw.arg == "ui_expose":
                        entry["uiExpose"] = bool(_const(kw.value))
                    elif kw.arg == "placeholder":
                        entry["placeholder"] = _const(kw.value)
                    elif kw.arg == "description":
                        entry["description"] = _const(kw.value)
                    elif kw.arg == "native_unit":
                        entry["nativeUnit"] = _const(kw.value)
                    elif kw.arg == "allow_negative":
                        entry["allowNegative"] = bool(_const(kw.value))
                    elif kw.arg == "minimum":
                        entry["minimum"] = _const(kw.value)
                    elif kw.arg == "maximum":
                        entry["maximum"] = _const(kw.value)
                sections[self.prefix].append(entry)
            self.generic_visit(node)

    Visitor().visit(tree)
    return sections


def _parse_frozensets(source: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for match in _FROZENSET_RE.finditer(source):
        out[match.group("name")] = set(_STRING_RE.findall(match.group("body")))
    return out


def _enrich_reload(sections: dict[str, list[dict]], policy_source: str) -> None:
    frozen = _parse_frozensets(policy_source)
    settings_live = frozen.get("SETTINGS_LIVE_KEYS", set())
    settings_full = frozen.get("SETTINGS_FULL_RESTART_KEYS", set())
    webui_restart = frozen.get("WEBUI_RESTART_KEYS", set())
    frontend_only = frozen.get("FRONTEND_ONLY_KEYS", set())
    for section, entries in sections.items():
        for entry in entries:
            key = f"{section}.{entry['key']}"
            entry["applyLive"] = key in settings_live or key in frontend_only
            entry["requiresRestart"] = key in settings_full or key in webui_restart


def _emit_field(section: str, entry: dict) -> str | None:
    if not entry.get("uiExpose", True):
        return None
    if entry.get("kind") in ("mapping", "trackers"):
        return None
    path = entry["path"]
    abs_path = [section, *path] if section in ("Settings", "WebUI") else list(path)
    path_lit = "[" + ", ".join(_ts_string(p) for p in abs_path) + "]"
    lines = [
        "  {",
        f"    label: {_ts_string(entry.get('label') or entry['key'])},",
        f"    path: {path_lit},",
        f"    type: {_ts_string(entry.get('kind') or 'text')},",
    ]
    if entry.get("options"):
        opts = ", ".join(_ts_string(o) for o in entry["options"])
        lines.append(f"    options: [{opts}],")
    if entry.get("required"):
        lines.append("    required: true,")
    if entry.get("secure"):
        lines.append("    secure: true,")
    if entry.get("placeholder"):
        lines.append(f"    placeholder: {_ts_string(entry['placeholder'])},")
    if entry.get("description"):
        lines.append(f"    description: {_ts_string(entry['description'])},")
    if entry.get("nativeUnit"):
        lines.append(f"    nativeUnit: {_ts_string(entry['nativeUnit'])},")
    if entry.get("allowNegative"):
        lines.append("    allowNegative: true,")
    if entry.get("minimum") is not None:
        lines.append(f"    minimum: {entry['minimum']},")
    if entry.get("maximum") is not None:
        lines.append(f"    maximum: {entry['maximum']},")
    if entry.get("applyLive"):
        lines.append("    applyLive: true,")
    if entry.get("requiresRestart"):
        lines.append("    requiresRestart: true,")
    lines.append("  },")
    return "\n".join(lines)


def main() -> int:
    if not FIELDS_PY.is_file():
        print(f"generate-config-fields: missing {FIELDS_PY}", file=sys.stderr)
        return 2

    sections: dict[str, list[dict]] = {v: [] for v in _REGISTRY_PREFIX.values()}
    for path in (FIELDS_PY, FIELDS_ARR_PY):
        if path.is_file():
            parsed = _parse_config_fields(path.read_text(encoding="utf-8"))
            for key, entries in parsed.items():
                sections[key].extend(entries)

    if RELOAD_POLICY_PY.is_file():
        _enrich_reload(sections, RELOAD_POLICY_PY.read_text(encoding="utf-8"))

    chunks: list[str] = [
        "/**",
        " * AUTO-GENERATED by scripts/generate_config_fields_ts.py — do not edit.",
        " * Source of truth: qBitrr/gen_config/fields.py (+ fields_arr.py).",
        " * Custom validators/editors live in configFieldOverlays.ts.",
        " */",
        'import type { FieldDefinition } from "./configTypes";',
        "",
    ]
    export_map = {
        "Settings": "GENERATED_SETTINGS_FIELDS",
        "WebUI": "GENERATED_WEBUI_FIELDS",
        "qBit": "GENERATED_QBIT_FIELDS",
        "Arr": "GENERATED_ARR_FIELDS",
    }
    for section, export_name in export_map.items():
        fields_ts = []
        for entry in sections.get(section, []):
            emitted = _emit_field(section, entry)
            if emitted:
                fields_ts.append(emitted)
        chunks.append(f"export const {export_name}: FieldDefinition[] = [")
        chunks.extend(fields_ts)
        chunks.append("];")
        chunks.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(chunks) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
