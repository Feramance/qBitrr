"""Behavioral tests for Readarr review remediation (#539 follow-up)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from qBitrr.arss.db_update_handlers import (
    _parse_readarr_release_date,
    _readarr_release_is_future,
    _readarr_release_year,
    update_readarr_author,
    update_readarr_book,
)
from qBitrr.arss.readarr import ReadarrArr
from qBitrr.webui.arr_open import (
    build_arr_open_url,
    open_arr_item_or_error,
    resolve_open_route_token,
)


class TestParseReadarrReleaseDate(unittest.TestCase):
    def test_parses_iso_zulu(self) -> None:
        parsed = _parse_readarr_release_date("2020-06-15T00:00:00Z")
        self.assertEqual(parsed, datetime(2020, 6, 15, tzinfo=timezone.utc))

    def test_parses_date_only(self) -> None:
        parsed = _parse_readarr_release_date("2019-01-01")
        self.assertEqual(parsed, datetime(2019, 1, 1, tzinfo=timezone.utc))

    def test_none_for_empty(self) -> None:
        self.assertIsNone(_parse_readarr_release_date(None))
        self.assertIsNone(_parse_readarr_release_date(""))

    def test_release_year_from_date_only(self) -> None:
        self.assertEqual(_readarr_release_year("2019-01-01"), 2019)

    def test_release_is_future(self) -> None:
        self.assertFalse(_readarr_release_is_future("2019-01-01"))
        self.assertFalse(_readarr_release_is_future(None))


class TestReadarrCollectYears(unittest.TestCase):
    def test_collect_years_from_release_date(self) -> None:
        arr = ReadarrArr.__new__(ReadarrArr)
        arr.search_in_reverse = False
        arr.client = MagicMock()
        arr.client.book.get.return_value = [
            {"monitored": True, "releaseDate": "2021-05-01T00:00:00Z"},
            {"monitored": True, "releaseDate": "2020-01-01"},
            {"monitored": False, "releaseDate": "2019-01-01T00:00:00Z"},
        ]
        with patch("qBitrr.arss.readarr.with_retry", side_effect=lambda fn, **_: fn()):
            years = arr.collect_years_for_search()
        self.assertEqual(years, [2020, 2021])


class TestDbGetFilesBooksYearFilter(unittest.TestCase):
    def test_adds_release_date_bounds_when_search_by_year(self) -> None:
        from qBitrr.arss.db_queries import db_get_files_books

        arr = MagicMock()
        arr.search_missing = True
        arr.do_upgrade_search = False
        arr.search_by_year = True
        arr.search_current_year = 2021
        arr._name = "Readarr-Books"
        arr.model_file.ArrInstance = MagicMock()
        arr.model_file.ReleaseDate = MagicMock()
        arr.model_file.ReleaseDate.is_null.return_value = MagicMock()
        arr.model_file.ReleaseDate.__ge__ = MagicMock(return_value=MagicMock())
        arr.model_file.ReleaseDate.__le__ = MagicMock(return_value=MagicMock())
        arr.model_file.BookFileId = MagicMock()
        arr.model_file.Reason = MagicMock()
        arr.model_file.select.return_value.where.return_value.order_by.return_value.execute.return_value = (
            []
        )

        with patch(
            "qBitrr.arss.db_queries._db_search_quality_cf_condition", return_value=MagicMock()
        ):
            db_get_files_books(arr)

        self.assertTrue(arr.model_file.ReleaseDate.is_null.called)


class TestUpdateReadarrBook(unittest.TestCase):
    def _make_arr(self) -> MagicMock:
        arr = MagicMock()
        arr._name = "Readarr-Books"
        arr.search_unmonitored = False
        arr.quality_unmet_search = False
        arr.custom_format_unmet_search = False
        arr._quality_profile_cache = {}
        arr._invalid_quality_profiles = set()
        arr._readarr_author_profile_cache = {
            7: {"id": 7, "qualityProfileId": 3, "authorName": "A"}
        }
        arr.client = MagicMock()
        arr.model_file.get_or_none.return_value = None
        arr.model_queue = MagicMock()
        return arr

    def test_maps_book_file_count_and_quality_cutoff(self) -> None:
        arr = self._make_arr()
        db_entry = {
            "id": 42,
            "monitored": True,
            "title": "Book",
            "authorId": 7,
            "authorTitle": "Author",
            "foreignBookId": None,
            "releaseDate": "2021-01-01T00:00:00Z",
            "statistics": {"bookFileCount": 1},
            "author": {"id": 7, "qualityProfileId": 3},
        }
        with (
            patch(
                "qBitrr.arss.db_update_handlers.get_readarr_book_files",
                return_value=[{"id": 99, "qualityCutoffNotMet": True, "customFormatScore": 10}],
            ),
            patch("qBitrr.arss.db_update_handlers.resolve_min_format_score", return_value=0),
            patch(
                "qBitrr.arss.db_update_handlers.get_profile_name_cached", return_value="Standard"
            ),
            patch("qBitrr.arss.db_update_handlers.should_mark_searched", return_value=False),
            patch("qBitrr.arss.db_update_handlers.refresh_rollups_after_db_update"),
        ):
            update_readarr_book(arr, db_entry, request=False)

        insert_call = arr.model_file.insert.call_args
        self.assertEqual(insert_call.kwargs["ForeignBookId"], "")
        self.assertEqual(insert_call.kwargs["BookFileId"], 99)
        self.assertIsInstance(insert_call.kwargs["ReleaseDate"], datetime)

    def test_uses_author_prefetch_cache(self) -> None:
        arr = self._make_arr()
        db_entry = {
            "id": 42,
            "monitored": True,
            "title": "Book",
            "authorId": 7,
            "statistics": {"bookFileCount": 0},
            "author": {},
        }
        with (
            patch("qBitrr.arss.db_update_handlers.resolve_min_format_score", return_value=0),
            patch("qBitrr.arss.db_update_handlers.refresh_rollups_after_db_update"),
        ):
            update_readarr_book(arr, db_entry, request=False)
        arr.client.author.get.assert_not_called()

    def test_empty_book_files_despite_stats_marks_missing(self) -> None:
        """Stats bookFileCount>0 with empty file fetch must not invent BookFileId=1."""
        arr = self._make_arr()
        db_entry = {
            "id": 42,
            "monitored": True,
            "title": "Book",
            "authorId": 7,
            "authorTitle": "Author",
            "foreignBookId": None,
            "releaseDate": "2021-01-01T00:00:00Z",
            "statistics": {"bookFileCount": 1},
            "author": {"id": 7, "qualityProfileId": 3},
        }
        with (
            patch(
                "qBitrr.arss.db_update_handlers.get_readarr_book_files",
                return_value=[],
            ),
            patch("qBitrr.arss.db_update_handlers.resolve_min_format_score", return_value=0),
            patch(
                "qBitrr.arss.db_update_handlers.get_profile_name_cached", return_value="Standard"
            ),
            patch("qBitrr.arss.db_update_handlers.should_mark_searched", return_value=False),
            patch("qBitrr.arss.db_update_handlers.refresh_rollups_after_db_update"),
        ):
            update_readarr_book(arr, db_entry, request=False)

        insert_call = arr.model_file.insert.call_args
        self.assertEqual(insert_call.kwargs["BookFileId"], 0)
        self.assertEqual(insert_call.kwargs["Reason"], "Missing")


class TestReadarrReSearchQueue(unittest.TestCase):
    def test_re_search_persists_queue_with_execute(self) -> None:
        arr = ReadarrArr.__new__(ReadarrArr)
        arr._name = "Readarr-Books"
        arr.logger = MagicMock()
        arr.client = MagicMock()
        arr.client.book.get.return_value = {"title": "Book", "authorTitle": "Author"}
        arr.queue_file_ids = {42}
        insert_chain = MagicMock()
        arr.persistent_queue = MagicMock()
        arr.persistent_queue.insert.return_value = insert_chain
        insert_chain.on_conflict_ignore.return_value = insert_chain

        with (
            patch("qBitrr.arss.readarr.with_retry", side_effect=lambda fn, **_: fn()),
            patch("qBitrr.arss.readarr.execute_command"),
        ):
            arr._re_search_failed_media(42)

        arr.persistent_queue.insert.assert_called_once_with(
            EntryId=42, ArrInstance="Readarr-Books"
        )
        insert_chain.on_conflict_ignore.assert_called_once_with()
        insert_chain.execute.assert_called_once_with()
        self.assertNotIn(42, arr.queue_file_ids)


class TestUpdateReadarrAuthor(unittest.TestCase):
    def test_stats_without_size_on_disk_marks_not_searched(self) -> None:
        """bookFileCount/percentOfBooks alone must not mark author searched."""
        arr = MagicMock()
        arr._name = "Readarr-Books"
        arr.search_unmonitored = False
        arr.use_temp_for_missing = False
        arr._quality_profile_cache = {}
        arr.artists_file_model.get_or_none.return_value = None
        insert_chain = MagicMock()
        arr.artists_file_model.insert.return_value = insert_chain
        insert_chain.on_conflict.return_value = insert_chain
        author_payload = {
            "authorName": "Author",
            "qualityProfileId": 3,
            "statistics": {
                "bookCount": 5,
                "sizeOnDisk": 0,
                "bookFileCount": 2,
                "percentOfBooks": 40.0,
            },
        }
        with (
            patch(
                "qBitrr.arss.db_update_handlers.arr_with_retry",
                side_effect=lambda fn, **_: fn(),
            ),
            patch("qBitrr.arss.db_update_handlers.resolve_min_format_score", return_value=0),
            patch(
                "qBitrr.arss.db_update_handlers.get_profile_name_cached", return_value="Standard"
            ),
        ):
            arr.client.author.get.return_value = author_payload
            update_readarr_author(arr, {"id": 7, "monitored": True})

        insert_call = arr.artists_file_model.insert.call_args
        self.assertEqual(insert_call.kwargs["Searched"], False)


class TestReadarrRefreshDownloads(unittest.TestCase):
    def test_api_calls_includes_readarr_in_refresh_supported_types(self) -> None:
        from datetime import timedelta
        from unittest.mock import PropertyMock

        from qBitrr.arss.arr_base import ArrBase

        arr = ArrBase.__new__(ArrBase)
        arr._name = "Readarr-Books"
        arr.type = "readarr"
        arr.uri = "http://readarr"
        arr.logger = MagicMock()
        now = datetime.now()
        arr.rss_sync_timer_last_checked = now
        arr.refresh_downloads_timer_last_checked = now - timedelta(hours=1)
        arr._get_rss_sync_timer = MagicMock(return_value=15)
        arr._get_refresh_downloads_timer = MagicMock(return_value=1)

        with (
            patch.object(ArrBase, "is_alive", new_callable=PropertyMock, return_value=True),
            patch.object(arr, "_run_periodic_command", return_value=True) as run_cmd,
        ):
            arr.api_calls()

        run_cmd.assert_called_once_with(
            "RefreshMonitoredDownloads",
            supported_types={"radarr", "sonarr", "readarr"},
        )

    def test_refresh_command_runs_for_readarr_type(self) -> None:
        from qBitrr.arss.arr_base import ArrBase

        arr = ArrBase.__new__(ArrBase)
        arr._name = "Readarr-Books"
        arr.type = "readarr"
        arr.logger = MagicMock()
        arr.client = MagicMock()
        with (
            patch(
                "qBitrr.arss.arr_base.execute_command", return_value={"status": "ok"}
            ) as execute,
            patch("qBitrr.arss.arr_base.with_retry", side_effect=lambda fn, **_: fn()),
        ):
            result = arr._run_periodic_command(
                "RefreshMonitoredDownloads",
                supported_types={"radarr", "sonarr", "readarr"},
            )
        self.assertTrue(result)
        execute.assert_called_once_with(arr.client, "RefreshMonitoredDownloads")


class TestSearchReadarr(unittest.TestCase):
    def test_issues_book_search_command(self) -> None:
        from qBitrr.arss.search_handlers import search_readarr

        arr = MagicMock()
        arr._name = "Readarr-Books"
        arr.queue_file_ids = set()
        arr._get_search_command_limit.return_value = 5
        arr.arr_db_query_commands_count.return_value = 0
        file_model = SimpleNamespace(
            EntryId=55,
            AuthorTitle="Author",
            Title="Book",
            ForeignBookId="fb-1",
            Reason="Missing",
        )
        with patch("qBitrr.arss.search_handlers.execute_command") as execute:
            search_readarr(
                arr,
                file_model,
                request_tag="",
                request=False,
                todays=False,
                bypass_limit=False,
                series_search=False,
                commands=5,
            )
        execute.assert_called_once()
        self.assertEqual(execute.call_args.args[1], "BookSearch")
        self.assertEqual(execute.call_args.kwargs["bookIds"], [55])


class TestEbookProbeable(unittest.TestCase):
    def test_epub_skips_ffprobe(self) -> None:
        from pathlib import Path

        from qBitrr.arss.arr_base import ArrBase

        arr = ArrBase.__new__(ArrBase)
        arr.manager = MagicMock()
        arr.manager.ffprobe_available = True
        arr.files_probed = set()
        arr.logger = MagicMock()
        path = Path("/tmp/book.epub")
        self.assertTrue(arr.file_is_probeable(path))
        self.assertIn(path, arr.files_probed)


class TestArrOpenRoute(unittest.TestCase):
    def test_resolve_author_prefers_foreign_author_id(self) -> None:
        token = resolve_open_route_token(
            "author",
            {"foreignAuthorId": "abc-123", "titleSlug": "slug", "id": 1},
        )
        self.assertEqual(token, "abc-123")

    def test_build_readarr_author_open_url(self) -> None:
        arr = MagicMock()
        arr.uri = "http://readarr:8787"
        arr.client.author.get.return_value = {
            "foreignAuthorId": "author-slug",
            "id": 5,
        }
        with patch("qBitrr.webui.arr_open.with_retry", side_effect=lambda fn, **_: fn()):
            url = build_arr_open_url(arr, "author", 5)
        self.assertEqual(url, "http://readarr:8787/author/author-slug")

    def test_open_unknown_kind(self) -> None:
        url, err = open_arr_item_or_error(MagicMock(), "album", 1)
        self.assertIsNone(url)
        self.assertIn("Unknown item kind", err or "")


class TestReadarrAuthorDetailFallback(unittest.TestCase):
    def test_synthesizes_author_when_author_row_missing(self) -> None:
        from qBitrr.webui.catalog.queries import Catalog

        catalog = Catalog.__new__(Catalog)
        catalog.logger = MagicMock()

        arm = MagicMock()
        book_m = MagicMock()
        db = MagicMock()
        arr = MagicMock()
        arr.db = db
        arr.artists_file_model = arm
        arr.model_file = book_m
        arr.category = "readarr-books"

        book_row = SimpleNamespace(
            EntryId=10,
            Title="Book A",
            AuthorTitle="Fallback Author",
            Monitored=True,
            Searched=False,
            BookFileId=0,
            AuthorId=99,
            ForeignBookId="fb",
            ReleaseDate=None,
            QualityMet=False,
            CustomFormatScore=0,
            MinCustomFormatScore=0,
            CustomFormatMet=False,
            Reason="Missing",
            QualityProfileId=None,
            QualityProfileName=None,
        )

        arm.get_or_none.return_value = None
        book_m.select.return_value.where.return_value.order_by.return_value = [book_row]

        with (
            patch.object(catalog, "_ensure_arr_db", return_value=True),
            patch.object(catalog, "_readarr_instance_keys", return_value=["Readarr-Books"]),
            patch(
                "qBitrr.webui.catalog.queries.get_readarr_book_counts_total",
                return_value=({"available": 0}, 1),
            ),
            patch("qBitrr.webui.catalog.queries.database_lock"),
            patch.object(
                catalog, "_readarr_book_row_payload", return_value={"book": {"title": "Book A"}}
            ),
        ):
            detail = catalog._readarr_author_detail_from_db(arr, 99)

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["author"]["name"], "Fallback Author")
        self.assertEqual(detail["author"]["id"], 99)

    def test_synthesized_author_searched_false_when_no_monitored_books(self) -> None:
        from qBitrr.webui.catalog.queries import Catalog

        catalog = Catalog.__new__(Catalog)
        catalog.logger = MagicMock()

        arm = MagicMock()
        book_m = MagicMock()
        db = MagicMock()
        arr = MagicMock()
        arr.db = db
        arr.artists_file_model = arm
        arr.model_file = book_m

        book_row = SimpleNamespace(
            EntryId=10,
            Title="Book A",
            AuthorTitle="Author",
            Monitored=False,
            Searched=False,
            BookFileId=0,
            AuthorId=99,
        )

        arm.get_or_none.return_value = None
        book_m.select.return_value.where.return_value.order_by.return_value = [book_row]

        with (
            patch.object(catalog, "_ensure_arr_db", return_value=True),
            patch.object(catalog, "_readarr_instance_keys", return_value=["Readarr-Books"]),
            patch(
                "qBitrr.webui.catalog.queries.get_readarr_book_counts_total",
                return_value=({"available": 0}, 1),
            ),
            patch("qBitrr.webui.catalog.queries.database_lock"),
            patch.object(catalog, "_readarr_book_row_payload", return_value={"book": {}}),
        ):
            detail = catalog._readarr_author_detail_from_db(arr, 99)

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertFalse(detail["author"]["searched"])


class TestReadarrTypeFeatureGatesLive(unittest.TestCase):
    """Readarr LIVE reload must keep Ombi/Overseerr disabled."""

    def test_live_sync_keeps_request_gates_off_for_readarr(self) -> None:
        from tests.test_live_reload_characterization import _bare_arr_for_refresh, _live_config_get

        arr = _bare_arr_for_refresh()
        arr.__class__ = ReadarrArr
        arr._name = "Readarr-Books"
        arr.search_by_year = True
        arr.ombi_search_requests = False
        arr.overseerr_requests = False

        with (
            patch("qBitrr.arss.arr_base.CONFIG") as mock_config,
            patch("qBitrr.arss.arr_base.PROCESS_ONLY", False),
            patch("qBitrr.arss.arr_base.SEARCH_ONLY", True),
            patch("qBitrr.arss.arr_base.sync_config_from_disk"),
            patch.object(arr, "_get_ignore_torrents_younger_than", return_value=180),
            patch.object(arr, "_get_maximum_eta", return_value=86400),
            patch.object(arr, "_get_search_command_limit", return_value=5),
            patch.object(arr, "_get_rss_sync_timer", return_value=15),
            patch.object(arr, "_get_refresh_downloads_timer", return_value=1),
            patch.object(arr, "_merge_trackers", return_value=[]),
            patch.object(arr, "_install_tracker_index"),
            patch("qBitrr.arss.arr_base.build_tracker_index", return_value=MagicMock()),
        ):
            mock_config.get.side_effect = _live_config_get
            mock_config.get_duration.side_effect = lambda key, fallback=0, unit=None: fallback
            arr._apply_arr_live_attrs_from_config()

        self.assertFalse(arr.ombi_search_requests)
        self.assertFalse(arr.overseerr_requests)
        self.assertIsNone(arr.ombi_uri)
        self.assertIsNone(arr.overseerr_uri)


if __name__ == "__main__":
    unittest.main()
