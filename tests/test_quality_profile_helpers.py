"""Combination coverage for quality_profile_helpers (refactor-only module)."""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest import mock

from qBitrr.quality_profile_helpers import (
    compute_quality_met,
    compute_search_reason,
    get_profile_name_cached,
    plan_temp_profile_switch,
    resolve_custom_format_score,
    resolve_min_format_score,
    should_mark_searched,
)


class TestShouldMarkSearchedCombinations(unittest.TestCase):
    def test_all_search_gates_must_pass(self) -> None:
        cases = [
            (False, True, True, True, 0, 10, False),
            (True, True, True, False, 0, 10, False),
            (True, False, True, True, 5, 10, False),
            (True, True, False, True, 5, 10, False),
            (True, False, False, True, 3, 10, False),
            (True, True, True, True, 5, 10, False),
            (True, False, True, True, 3, 10, False),
            (True, False, False, True, 12, 10, True),
        ]
        for has_content, q_unmet_s, q_unmet, cf_unmet_s, cf, min_cf, expected in cases:
            with self.subTest(
                has_content=has_content,
                quality_unmet_search=q_unmet_s,
                custom_format_unmet_search=cf_unmet_s,
            ):
                self.assertEqual(
                    should_mark_searched(
                        has_content=has_content,
                        quality_unmet_search=q_unmet_s,
                        quality_unmet=q_unmet,
                        custom_format_unmet_search=cf_unmet_s,
                        custom_format=cf,
                        min_custom_format=min_cf,
                    ),
                    expected,
                )


class TestComputeSearchReasonCombinations(unittest.TestCase):
    def test_reason_matrix(self) -> None:
        self.assertEqual(
            compute_search_reason(
                has_content=False,
                quality_unmet_search=True,
                quality_unmet=True,
                custom_format_unmet_search=True,
                custom_format_met=False,
                do_upgrade_search=True,
                searched=True,
            ),
            "Missing",
        )
        self.assertEqual(
            compute_search_reason(
                has_content=True,
                quality_unmet_search=True,
                quality_unmet=True,
                custom_format_unmet_search=False,
                custom_format_met=True,
                do_upgrade_search=False,
                searched=False,
            ),
            "Quality",
        )
        self.assertEqual(
            compute_search_reason(
                has_content=True,
                quality_unmet_search=False,
                quality_unmet=False,
                custom_format_unmet_search=True,
                custom_format_met=False,
                do_upgrade_search=False,
                searched=False,
            ),
            "CustomFormat",
        )
        self.assertEqual(
            compute_search_reason(
                has_content=True,
                quality_unmet_search=False,
                quality_unmet=False,
                custom_format_unmet_search=False,
                custom_format_met=True,
                do_upgrade_search=True,
                searched=False,
            ),
            "Upgrade",
        )
        self.assertEqual(
            compute_search_reason(
                has_content=True,
                quality_unmet_search=False,
                quality_unmet=False,
                custom_format_unmet_search=False,
                custom_format_met=True,
                do_upgrade_search=False,
                searched=True,
            ),
            "Not being searched",
        )


class TestPlanTempProfileSwitchCombinations(unittest.TestCase):
    def test_upgrade_from_temp_when_searched(self) -> None:
        data, ts, orig, current = plan_temp_profile_switch(
            searched=True,
            has_file=True,
            quality_profile_id=2,
            main_quality_profile_ids={2: 1},
            temp_quality_profile_ids={1: 2},
            keep_temp_profile=False,
        )
        self.assertEqual(data, {"qualityProfileId": 1})
        self.assertIsInstance(ts, datetime)
        self.assertIsNone(orig)
        self.assertIsNone(current)

    def test_no_switch_when_keep_temp_profile(self) -> None:
        data, ts, orig, current = plan_temp_profile_switch(
            searched=True,
            has_file=False,
            quality_profile_id=2,
            main_quality_profile_ids={2: 1},
            temp_quality_profile_ids={1: 2},
            keep_temp_profile=True,
        )
        self.assertIsNone(data)
        self.assertIsNone(ts)
        self.assertIsNone(orig)
        self.assertIsNone(current)

    def test_downgrade_to_temp_when_missing(self) -> None:
        data, ts, orig, current = plan_temp_profile_switch(
            searched=False,
            has_file=False,
            quality_profile_id=1,
            main_quality_profile_ids={2: 1},
            temp_quality_profile_ids={1: 2},
            keep_temp_profile=False,
        )
        self.assertEqual(data, {"qualityProfileId": 2})
        self.assertEqual(orig, 1)
        self.assertEqual(current, 2)

    def test_no_switch_when_main_mapping_missing(self) -> None:
        data, ts, orig, current = plan_temp_profile_switch(
            searched=True,
            has_file=True,
            quality_profile_id=99,
            main_quality_profile_ids={2: 1},
            temp_quality_profile_ids={1: 2},
            keep_temp_profile=False,
        )
        self.assertIsNone(data)
        self.assertIsNone(ts)


class TestResolveMinFormatScore(unittest.TestCase):
    def test_uses_stored_score_first(self) -> None:
        score = resolve_min_format_score(
            stored_score=15,
            quality_profile_id=1,
            fetch_profile=mock.MagicMock(),
            logger=mock.MagicMock(),
            label="Movie",
            entry_id=1,
        )
        self.assertEqual(score, 15)

    def test_fetches_profile_when_no_stored_score(self) -> None:
        fetch = mock.MagicMock(return_value={"minFormatScore": 20})
        score = resolve_min_format_score(
            stored_score=0,
            quality_profile_id=3,
            fetch_profile=fetch,
            logger=mock.MagicMock(),
            label="Episode",
            entry_id=5,
        )
        self.assertEqual(score, 20)
        fetch.assert_called_once_with(3)

    def test_warns_and_defaults_when_profile_id_missing(self) -> None:
        logger = mock.MagicMock()
        score = resolve_min_format_score(
            stored_score=0,
            quality_profile_id=None,
            fetch_profile=mock.MagicMock(),
            logger=logger,
            label="Album",
            entry_id=7,
        )
        self.assertEqual(score, 0)
        logger.warning.assert_called_once()


class TestResolveCustomFormatScore(unittest.TestCase):
    def test_zero_when_no_content(self) -> None:
        self.assertEqual(
            resolve_custom_format_score(
                has_content=False,
                content_file_id=99,
                stored_file_id=99,
                stored_score=10,
                fetch_file_score=mock.MagicMock(),
            ),
            0,
        )

    def test_uses_cached_score_when_file_id_matches(self) -> None:
        fetch = mock.MagicMock()
        self.assertEqual(
            resolve_custom_format_score(
                has_content=True,
                content_file_id=42,
                stored_file_id=42,
                stored_score=11,
                fetch_file_score=fetch,
            ),
            11,
        )
        fetch.assert_not_called()

    def test_fetches_when_cache_miss(self) -> None:
        fetch = mock.MagicMock(return_value=7)
        self.assertEqual(
            resolve_custom_format_score(
                has_content=True,
                content_file_id=42,
                stored_file_id=None,
                stored_score=None,
                fetch_file_score=fetch,
            ),
            7,
        )
        fetch.assert_called_once_with(42)


class TestComputeQualityMet(unittest.TestCase):
    def test_matrix(self) -> None:
        self.assertFalse(compute_quality_met(has_content=False, quality_unmet=False))
        self.assertFalse(compute_quality_met(has_content=True, quality_unmet=True))
        self.assertTrue(compute_quality_met(has_content=True, quality_unmet=False))


class TestGetProfileNameCached(unittest.TestCase):
    def test_caches_fetched_profile(self) -> None:
        cache: dict = {}
        fetch = mock.MagicMock(return_value={"name": "HD-720p"})
        name = get_profile_name_cached(
            quality_profile_id=4,
            cache=cache,
            fetch_profile=fetch,
        )
        self.assertEqual(name, "HD-720p")
        self.assertEqual(cache[4]["name"], "HD-720p")
        get_profile_name_cached(quality_profile_id=4, cache=cache, fetch_profile=fetch)
        fetch.assert_called_once()

    def test_returns_none_on_fetch_failure(self) -> None:
        fetch = mock.MagicMock(side_effect=RuntimeError("offline"))
        name = get_profile_name_cached(
            quality_profile_id=1,
            cache={},
            fetch_profile=fetch,
        )
        self.assertIsNone(name)


if __name__ == "__main__":
    unittest.main()
