"""Characterization tests for Arr ``generate_doc`` registry emission."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

# Writable data path before importing qBitrr (logger / config side effects).
_TEST_DATA = Path(os.environ.get("QBITRR_OVERRIDES_DATA_PATH", "/tmp/qbitrr-test-data"))
_TEST_DATA.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("QBITRR_OVERRIDES_DATA_PATH", str(_TEST_DATA))

from qBitrr.gen_config.fields import filter_arr_fields  # noqa: E402
from qBitrr.gen_config.fields_arr import ARR_FIELDS  # noqa: E402
from qBitrr.gen_config.sections import generate_doc  # noqa: E402


def _plain(obj):
    """Unwrap tomlkit containers to plain Python values for comparison."""
    if hasattr(obj, "unwrap"):
        try:
            return _plain(obj.unwrap())
        except Exception:
            pass
    if isinstance(obj, dict) or (hasattr(obj, "items") and not isinstance(obj, (str, bytes))):
        try:
            return {str(k): _plain(v) for k, v in dict(obj).items() if not str(k).startswith("#")}
        except Exception:
            return str(obj)
    if isinstance(obj, (list, tuple)):
        return [_plain(x) for x in obj]
    return obj


class GenerateDocArrRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = generate_doc()

    def test_representative_categories_present(self) -> None:
        for cat in (
            "Sonarr-TV",
            "Sonarr-Anime",
            "Radarr-1080",
            "Radarr-4K",
            "Lidarr-Music",
            "Readarr-Books",
        ):
            self.assertIn(cat, self.doc)

    def test_category_defaults_match_overrides(self) -> None:
        self.assertEqual(self.doc["Sonarr-TV"]["Category"], "sonarr-tv")
        self.assertEqual(self.doc["Radarr-4K"]["Category"], "radarr-4k")
        self.assertEqual(self.doc["Readarr-Books"]["Category"], "readarr-books")
        self.assertTrue(self.doc["Radarr-4K"]["EntrySearch"]["Overseerr"]["Is4K"])
        self.assertFalse(self.doc["Radarr-1080"]["EntrySearch"]["Overseerr"]["Is4K"])
        self.assertFalse(self.doc["Sonarr-TV"]["EntrySearch"]["Overseerr"]["Is4K"])

    def test_lidarr_omits_ombi_overseerr_and_year_search(self) -> None:
        es = self.doc["Lidarr-Music"]["EntrySearch"]
        self.assertNotIn("Ombi", es)
        self.assertNotIn("Overseerr", es)
        self.assertNotIn("SearchByYear", es)
        self.assertNotIn("Unmonitored", es)
        self.assertNotIn("SearchLimit", es)

    def test_readarr_omits_ombi_overseerr_keeps_year_search(self) -> None:
        es = self.doc["Readarr-Books"]["EntrySearch"]
        self.assertNotIn("Ombi", es)
        self.assertNotIn("Overseerr", es)
        self.assertIn("SearchByYear", es)
        self.assertTrue(es["SearchByYear"])
        self.assertIn("Unmonitored", es)
        self.assertIn("SearchLimit", es)

    def test_sonarr_includes_series_fields(self) -> None:
        es = self.doc["Sonarr-TV"]["EntrySearch"]
        self.assertIn("AlsoSearchSpecials", es)
        self.assertEqual(es["SearchBySeries"], "smart")
        self.assertTrue(es["PrioritizeTodaysReleases"])

    def test_filter_arr_fields_respects_kinds(self) -> None:
        sonarr = {f.dotted for f in filter_arr_fields(ARR_FIELDS, "Sonarr-TV")}
        lidarr = {f.dotted for f in filter_arr_fields(ARR_FIELDS, "Lidarr-Music")}
        readarr = {f.dotted for f in filter_arr_fields(ARR_FIELDS, "Readarr-Books")}
        self.assertIn("EntrySearch.AlsoSearchSpecials", sonarr)
        self.assertNotIn("EntrySearch.AlsoSearchSpecials", lidarr)
        self.assertNotIn("EntrySearch.AlsoSearchSpecials", readarr)
        self.assertIn("EntrySearch.Ombi.OmbiURI", sonarr)
        self.assertNotIn("EntrySearch.Ombi.OmbiURI", lidarr)
        self.assertNotIn("EntrySearch.Ombi.OmbiURI", readarr)
        self.assertNotIn("EntrySearch.SearchByYear", lidarr)
        self.assertIn("EntrySearch.SearchByYear", readarr)
        self.assertNotIn("EntrySearch.SearchRequestsEvery", readarr)

    def test_torrent_key_order_trackers_before_seeding(self) -> None:
        keys = list(self.doc["Sonarr-TV"]["Torrent"].keys())
        self.assertLess(keys.index("Trackers"), keys.index("SeedingMode"))

    def test_anime_folder_exclusions_include_ova(self) -> None:
        folders = list(self.doc["Sonarr-Anime"]["Torrent"]["FolderExclusionRegex"])
        self.assertTrue(any("ova" in f for f in folders))

    def test_generate_doc_stable_across_calls(self) -> None:
        a = _plain(generate_doc())
        b = _plain(generate_doc())
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
