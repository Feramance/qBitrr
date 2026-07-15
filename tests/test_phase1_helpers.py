"""Golden-master tests for Phase 1 backend helpers (pre/post refactor behavior)."""

from __future__ import annotations

import unittest
from unittest import mock

from tests.support.branch_compat import (
    HAS_ARR_SECTION_HELPERS,
    HAS_AUTO_UPDATE_PLATFORM_FIX,
    HAS_COERCE_BOOL,
    HAS_PARSE_DURATION,
    HAS_QBIT_SEEDING_CONFIG,
    HAS_URL_BASE_HELPERS,
)

from qBitrr.duration_config import (
    parse_duration_to_minutes,
    parse_duration_to_seconds,
)

if HAS_PARSE_DURATION:
    from qBitrr.duration_config import parse_duration

from qBitrr.gen_config import (
    _normalize_theme_value,
    _normalize_view_density_value,
)

if HAS_ARR_SECTION_HELPERS:
    from qBitrr.gen_config import ARR_SECTION_PREFIXES, iter_arr_sections
if HAS_QBIT_SEEDING_CONFIG:
    from qBitrr.qbit_seeding_config import load_qbit_seeding_config
if HAS_COERCE_BOOL:
    from qBitrr.utils import coerce_bool
if HAS_URL_BASE_HELPERS:
    from qBitrr.utils import normalize_url_base, qbit_sections

from qBitrr.tables import AlbumFilesModel, EpisodeFilesModel, MoviesFilesModel


@unittest.skipUnless(HAS_COERCE_BOOL, "coerce_bool is refactor-only")
class TestCoerceBoolGoldenMaster(unittest.TestCase):
    def test_falsy_strings(self) -> None:
        for value in ("0", "false", "none", "False", "NONE"):
            with self.subTest(value=value):
                self.assertFalse(coerce_bool(value))

    def test_truthy_values(self) -> None:
        self.assertTrue(coerce_bool("1"))
        self.assertTrue(coerce_bool("true"))
        self.assertTrue(coerce_bool(True))
        self.assertFalse(coerce_bool(None))
        self.assertFalse(coerce_bool(""))

    def test_numeric_and_whitespace_edge_cases(self) -> None:
        self.assertTrue(coerce_bool(1))
        self.assertFalse(coerce_bool(0))
        self.assertTrue(coerce_bool(" yes "))
        self.assertTrue(coerce_bool("off"))
        self.assertFalse(coerce_bool([]))
        self.assertTrue(coerce_bool([1]))


@unittest.skipUnless(HAS_URL_BASE_HELPERS, "normalize_url_base is refactor-only")
class TestNormalizeUrlBaseGoldenMaster(unittest.TestCase):
    def test_empty_and_none(self) -> None:
        self.assertEqual(normalize_url_base(None), "")
        self.assertEqual(normalize_url_base(""), "")
        self.assertEqual(normalize_url_base("   "), "")

    def test_leading_slash_and_strip_trailing(self) -> None:
        self.assertEqual(normalize_url_base("ui"), "/ui")
        self.assertEqual(normalize_url_base("/ui/"), "/ui")
        self.assertEqual(normalize_url_base("/ui/v2/"), "/ui/v2")


@unittest.skipUnless(HAS_URL_BASE_HELPERS, "qbit_sections is refactor-only")
class TestQbitSections(unittest.TestCase):
    def test_returns_qbit_sections_only(self) -> None:
        config = mock.MagicMock()
        config.sections.return_value = ["Settings", "qBit", "qBit-Seedbox", "Radarr-Movies"]
        self.assertEqual(qbit_sections(config), ["qBit", "qBit-Seedbox"])


@unittest.skipUnless(HAS_PARSE_DURATION, "parse_duration unified helper is refactor-only")
class TestParseDurationGoldenMaster(unittest.TestCase):
    def test_seconds_default_suffix(self) -> None:
        self.assertEqual(parse_duration_to_seconds("60"), 60)
        self.assertEqual(parse_duration("60", unit="seconds"), 60)
        self.assertEqual(parse_duration("2m", unit="seconds"), 120)
        self.assertEqual(parse_duration_to_seconds(None, fallback=99), 99)

    def test_minutes_default_suffix_and_sub_one_rounding(self) -> None:
        self.assertEqual(parse_duration_to_minutes("5"), 5)
        self.assertEqual(parse_duration("30s", unit="minutes"), 1)
        self.assertEqual(parse_duration("2h", unit="minutes"), 120)


class TestNormalizeEnumGoldenMaster(unittest.TestCase):
    def test_theme_normalization(self) -> None:
        self.assertEqual(_normalize_theme_value("light"), "Light")
        self.assertEqual(_normalize_theme_value("DARK"), "Dark")
        self.assertEqual(_normalize_theme_value("invalid"), "Dark")
        self.assertEqual(_normalize_theme_value(None), "Dark")

    def test_view_density_normalization(self) -> None:
        self.assertEqual(_normalize_view_density_value("compact"), "Compact")
        self.assertEqual(_normalize_view_density_value("COMFORTABLE"), "Comfortable")
        self.assertEqual(_normalize_view_density_value("bad"), "Comfortable")
        self.assertEqual(_normalize_view_density_value(None), "Comfortable")


@unittest.skipUnless(HAS_ARR_SECTION_HELPERS, "iter_arr_sections is refactor-only")
class TestIterArrSections(unittest.TestCase):
    def test_yields_arr_instance_sections(self) -> None:
        config = mock.MagicMock()
        config.sections.return_value = ["Settings", "Radarr-Movies", "Sonarr-TV", "qBit"]
        self.assertEqual(list(iter_arr_sections(config)), ["Radarr-Movies", "Sonarr-TV"])
        self.assertEqual(len(ARR_SECTION_PREFIXES), 4)


SHARED_ARR_FILE_FIELDS = (
    "EntryId",
    "ArrInstance",
    "Searched",
    "IsRequest",
    "QualityMet",
    "Upgrade",
    "CustomFormatScore",
    "MinCustomFormatScore",
    "CustomFormatMet",
    "Reason",
    "QualityProfileId",
    "QualityProfileName",
    "LastProfileSwitchTime",
    "CurrentProfileId",
    "OriginalProfileId",
)


class TestTablesFieldGoldenMaster(unittest.TestCase):
    """Snapshot shared field types/nullability before/after mixin extraction."""

    def _field_snapshot(self, model: type) -> dict[str, tuple[type, bool]]:
        return {
            name: (type(model._meta.fields[name]), model._meta.fields[name].null)
            for name in SHARED_ARR_FILE_FIELDS
            if name in model._meta.fields
        }

    def test_movies_episode_album_shared_fields_match(self) -> None:
        movie_snap = self._field_snapshot(MoviesFilesModel)
        episode_snap = self._field_snapshot(EpisodeFilesModel)
        album_snap = self._field_snapshot(AlbumFilesModel)
        for name in SHARED_ARR_FILE_FIELDS:
            with self.subTest(name=name):
                self.assertEqual(movie_snap[name], album_snap[name])
                if name not in ("Title", "Monitored"):
                    self.assertEqual(movie_snap[name], episode_snap[name])


@unittest.skipUnless(HAS_QBIT_SEEDING_CONFIG, "qbit_seeding_config is refactor-only")
class TestLoadQbitSeedingConfig(unittest.TestCase):
    @mock.patch("qBitrr.qbit_seeding_config.CONFIG")
    def test_loads_section_keys_and_category_overrides(self, mock_config: mock.MagicMock) -> None:
        mock_config.get_duration.side_effect = lambda key, fallback=-1, unit="seconds": {
            "qBit.CategorySeeding.MaxSeedingTime": 3600,
            "qBit.CategorySeeding.StalledDelay": 15,
            "qBit.CategorySeeding.IgnoreTorrentsYoungerThan": 300,
            "Settings.IgnoreTorrentsYoungerThan": 180,
        }.get(key, fallback)
        mock_config.get.side_effect = lambda key, fallback=None: {
            "qBit.CategorySeeding.DownloadRateLimitPerTorrent": 100,
            "qBit.CategorySeeding.UploadRateLimitPerTorrent": 50,
            "qBit.CategorySeeding.MaxUploadRatio": 2.0,
            "qBit.CategorySeeding.RemoveTorrent": 1,
            "qBit.CategorySeeding.HitAndRunMode": "ratio",
            "qBit.CategorySeeding.MinSeedRatio": 1.5,
            "qBit.CategorySeeding.MinSeedingTimeDays": 7,
            "qBit.CategorySeeding.HitAndRunPartialSeedRatio": 0.5,
            "qBit.CategorySeeding.TrackerUpdateBuffer": 30,
            "qBit.CategorySeeding.Categories": [{"Name": "radarr", "MaxUploadRatio": 3.0}],
            "qBit.Trackers": [{"URI": "https://tracker.example/announce"}],
            "qBit.MatchSubcategories": True,
        }.get(key, fallback)
        result = load_qbit_seeding_config("qBit")
        self.assertEqual(result["stalled_delay"], 15)
        self.assertTrue(result["match_subcategories"])
        self.assertEqual(result["ignore_torrents_younger_than"], 300)
        self.assertIn("radarr", result["category_overrides"])
        result_ph = load_qbit_seeding_config("qBit", include_ignore_younger=False)
        self.assertNotIn("ignore_torrents_younger_than", result_ph)


@unittest.skipUnless(
    HAS_AUTO_UPDATE_PLATFORM_FIX,
    "unsupported-platform error message fixed on refactor (9de1e0b1)",
)
class TestAutoUpdateUnsupportedPlatformMessageFixedOnRefactor(unittest.TestCase):
    @mock.patch("qBitrr.auto_update.requests.get")
    @mock.patch("qBitrr.auto_update.get_binary_asset_patterns")
    @mock.patch("qBitrr.auto_update.platform.system", return_value="Windows")
    @mock.patch("qBitrr.auto_update.platform.machine", return_value="ARM64")
    def test_unsupported_platform_error_names_first_matching_pattern(
        self,
        _machine: mock.MagicMock,
        _system: mock.MagicMock,
        mock_patterns: mock.MagicMock,
        mock_get: mock.MagicMock,
    ) -> None:
        from qBitrr.auto_update import get_binary_download_url

        mock_patterns.return_value = [
            "windows-2025-vs2026-arm64",
            "windows-2025-arm64",
            "windows-latest-arm64",
        ]
        mock_get.return_value = mock.MagicMock(
            raise_for_status=mock.MagicMock(),
            json=mock.MagicMock(return_value={"assets": []}),
        )
        logger = mock.MagicMock()
        result = get_binary_download_url("v1.0.0", logger)
        error = result["error"]
        self.assertIsNotNone(error)
        self.assertIn("windows-2025-vs2026-arm64", error)
        self.assertIn("not built by release workflow", error)


if __name__ == "__main__":
    unittest.main()
