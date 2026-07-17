"""Unit tests for scripts/config_fields_check.py inventory helpers."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "config_fields_check.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("config_fields_check", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ConfigFieldsCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_module()

    def test_inventory_gen_config_includes_settings_and_arr(self) -> None:
        sections = (REPO_ROOT / "qBitrr" / "gen_config" / "sections.py").read_text(
            encoding="utf-8"
        )
        fields = (REPO_ROOT / "qBitrr" / "gen_config" / "fields.py").read_text(encoding="utf-8")
        fields_arr = (REPO_ROOT / "qBitrr" / "gen_config" / "fields_arr.py").read_text(
            encoding="utf-8"
        )
        keys = self.mod.inventory_gen_config(sections, fields, fields_arr)
        self.assertIn("Settings.ConsoleLevel", keys)
        self.assertIn("WebUI.Host", keys)
        self.assertIn("qBit.ManagedCategories", keys)
        self.assertIn("Arr.EntrySearch.SearchMissing", keys)

    def test_inventory_fe_fields_by_block(self) -> None:
        source = (REPO_ROOT / "webui" / "src" / "pages" / "config" / "configFields.ts").read_text(
            encoding="utf-8"
        )
        generated = (
            REPO_ROOT / "webui" / "src" / "pages" / "config" / "configFields.generated.ts"
        ).read_text(encoding="utf-8")
        keys = self.mod.inventory_fe_fields(source)
        keys |= self.mod.inventory_fe_generated_fields(generated)
        self.assertIn("Settings.ConsoleLevel", keys)
        self.assertIn("Arr.MatchSubcategories", keys)
        self.assertIn("qBit.MatchSubcategories", keys)
        self.assertIn("Arr.Torrent.Trackers[].Name", keys)

    def test_allowlist_prefix(self) -> None:
        self.assertTrue(
            self.mod._allowlisted("Arr.Torrent.Trackers[].Name", {"Arr.Torrent.Trackers[].*"})
        )
        self.assertFalse(self.mod._allowlisted("Arr.Managed", {"Arr.Torrent.Trackers[].*"}))

    def test_main_passes_on_repo(self) -> None:
        self.assertEqual(self.mod.main(["--check-reload"]), 0)


if __name__ == "__main__":
    unittest.main()
