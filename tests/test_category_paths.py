"""Combination coverage for category_paths normalization."""

from __future__ import annotations

import unittest

from qBitrr.category_paths import (
    CATEGORY_SEPARATOR,
    category_parents,
    find_overlap_conflicts,
    has_subcategory_separator,
    is_subcategory_of,
    matches_configured,
    normalize_category,
    split_category,
)


class TestNormalizeCategoryCombinations(unittest.TestCase):
    def test_normalization_matrix(self) -> None:
        cases = [
            (None, ""),
            ("", ""),
            ("   ", ""),
            ("radarr", "radarr"),
            ("/seed/tleech/", "seed/tleech"),
            ("seed//tleech", "seed/tleech"),
            (" seed / tleech ", "seed/tleech"),
            (123, "123"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_category(raw), expected)


class TestSplitCategory(unittest.TestCase):
    def test_splits_normalized_segments(self) -> None:
        self.assertEqual(split_category("/a/b/"), ["a", "b"])


class TestIsSubcategoryOf(unittest.TestCase):
    def test_subcategory_matrix(self) -> None:
        self.assertTrue(is_subcategory_of("radarr/hd", "radarr"))
        self.assertFalse(is_subcategory_of("radarr", "radarr"))
        self.assertFalse(is_subcategory_of("radarr", "radarr/hd"))
        self.assertFalse(is_subcategory_of("", "radarr"))


class TestCategoryParents(unittest.TestCase):
    def test_returns_innermost_last_prefixes(self) -> None:
        self.assertEqual(category_parents("seed/tleech/foo"), ["seed", "seed/tleech"])
        self.assertEqual(category_parents("radarr"), [])


class TestMatchesConfigured(unittest.TestCase):
    def test_exact_match_without_prefix(self) -> None:
        self.assertEqual(
            matches_configured("radarr", ["radarr", "sonarr"], prefix=False), "radarr"
        )
        self.assertIsNone(matches_configured("radarr/hd", ["radarr"], prefix=False))

    def test_longest_prefix_wins_with_prefix_mode(self) -> None:
        configured = ["seed", "seed/tleech"]
        self.assertEqual(
            matches_configured("seed/tleech/foo", configured, prefix=True),
            "seed/tleech",
        )


class TestFindOverlapConflicts(unittest.TestCase):
    def test_detects_parent_child_pairs(self) -> None:
        conflicts = find_overlap_conflicts(["seed", "seed/tleech", "sonarr"])
        self.assertIn(("seed", "seed/tleech"), conflicts)


class TestHasSubcategorySeparator(unittest.TestCase):
    def test_detects_separator(self) -> None:
        self.assertTrue(has_subcategory_separator(f"parent{CATEGORY_SEPARATOR}child"))
        self.assertFalse(has_subcategory_separator("flat"))


if __name__ == "__main__":
    unittest.main()
