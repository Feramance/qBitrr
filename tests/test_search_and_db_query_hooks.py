"""Tests for polymorphic search_handlers dispatch and db_queries series_search modes."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class TestMaybeDoSearchDispatch(unittest.TestCase):
    def test_dispatches_to_concrete_impl(self) -> None:
        from qBitrr.arss.search_handlers import maybe_do_search

        arr = MagicMock()
        arr.overseerr_requests = False
        arr.ombi_search_requests = False
        arr.search_missing = True
        arr.do_upgrade_search = False
        arr.quality_unmet_search = False
        arr.custom_format_unmet_search = False
        arr.is_alive = True
        arr.uri = "http://radarr:7878"
        arr._maybe_do_search_impl.return_value = True
        file_model = MagicMock()

        result = maybe_do_search(arr, file_model, commands=1)

        self.assertTrue(result)
        arr.refresh_download_queue.assert_called_once()
        arr._maybe_do_search_impl.assert_called_once()
        kwargs = arr._maybe_do_search_impl.call_args.kwargs
        self.assertEqual(kwargs["commands"], 1)
        self.assertFalse(kwargs["series_search"])

    def test_sonarr_impl_calls_search_sonarr(self) -> None:
        from qBitrr.arss.sonarr import SonarrArr

        arr = SonarrArr.__new__(SonarrArr)
        file_model = MagicMock()
        with patch("qBitrr.arss.sonarr.search_sonarr", return_value="ok") as search:
            result = arr._maybe_do_search_impl(
                file_model,
                request_tag="",
                request=False,
                todays=False,
                bypass_limit=False,
                series_search=False,
                commands=0,
            )
            search.assert_called_once()
            self.assertEqual(result, "ok")


class TestDbGetFilesImplHooks(unittest.TestCase):
    def test_db_get_files_delegates_to_impl(self) -> None:
        from qBitrr.arss.db_queries import db_get_files

        arr = MagicMock()
        arr._db_get_files_impl.return_value = iter([(MagicMock(), False, False, False, 1)])
        rows = list(db_get_files(arr))
        arr._db_get_files_impl.assert_called_once_with()
        self.assertEqual(len(rows), 1)

    def test_sonarr_series_search_true_uses_series_leaf(self) -> None:
        from qBitrr.arss.sonarr import SonarrArr

        arr = SonarrArr.__new__(SonarrArr)
        arr.series_search = True
        arr.logger = MagicMock()
        series_row = [MagicMock(), True, False]
        with (
            patch(
                "qBitrr.arss.db_queries.db_get_files_series", return_value=[series_row]
            ) as series,
            patch("qBitrr.arss.db_queries.db_get_files_episodes") as episodes,
        ):
            rows = list(arr._db_get_files_impl())
        series.assert_called_once_with(arr)
        episodes.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertIs(rows[0][0], series_row[0])

    def test_sonarr_series_search_false_uses_episode_leaf(self) -> None:
        from qBitrr.arss.sonarr import SonarrArr

        arr = SonarrArr.__new__(SonarrArr)
        arr.series_search = False
        arr.logger = MagicMock()
        episode_row = [MagicMock(), False, False]
        with (
            patch("qBitrr.arss.db_queries.db_get_files_series") as series,
            patch(
                "qBitrr.arss.db_queries.db_get_files_episodes", return_value=[episode_row]
            ) as episodes,
        ):
            rows = list(arr._db_get_files_impl())
        episodes.assert_called_once_with(arr)
        series.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertIs(rows[0][0], episode_row[0])

    def test_sonarr_series_search_smart_uses_episodes(self) -> None:
        from qBitrr.arss.sonarr import SonarrArr

        arr = SonarrArr.__new__(SonarrArr)
        arr.series_search = "smart"
        arr.logger = MagicMock()
        episode = MagicMock()
        episode.SeriesId = 7
        episode.SeriesTitle = "Show"
        episode.SeasonNumber = 1
        episode.EpisodeNumber = 1
        episode_row = [episode, False, False]
        with (
            patch("qBitrr.arss.db_queries.db_get_files_series") as series,
            patch(
                "qBitrr.arss.db_queries.db_get_files_episodes", return_value=[episode_row]
            ) as episodes,
        ):
            rows = list(arr._db_get_files_impl())
        episodes.assert_called_once_with(arr)
        series.assert_not_called()
        # Single episode in smart mode yields episode-level search
        self.assertEqual(len(rows), 1)
        self.assertIs(rows[0][0], episode)


class TestReadarrDbGetFilesHook(unittest.TestCase):
    def test_readarr_uses_books_leaf(self) -> None:
        from qBitrr.arss.readarr import ReadarrArr

        arr = ReadarrArr.__new__(ReadarrArr)
        book_row = [MagicMock(), False, False]
        with patch("qBitrr.arss.db_queries.db_get_files_books", return_value=[book_row]) as books:
            rows = list(arr._db_get_files_impl())
        books.assert_called_once_with(arr)
        self.assertEqual(len(rows), 1)
        self.assertIs(rows[0][0], book_row[0])

    def test_readarr_impl_calls_search_readarr(self) -> None:
        from qBitrr.arss.readarr import ReadarrArr

        arr = ReadarrArr.__new__(ReadarrArr)
        file_model = MagicMock()
        with patch("qBitrr.arss.readarr.search_readarr", return_value="ok") as search:
            result = arr._maybe_do_search_impl(
                file_model,
                request_tag="",
                request=False,
                todays=False,
                bypass_limit=False,
                series_search=False,
                commands=0,
            )
            search.assert_called_once()
            self.assertEqual(result, "ok")


class TestIsArrApiError(unittest.TestCase):
    def test_pyarr_typed_errors(self) -> None:
        from qBitrr.arss.arr_shared import PyarrConnectionError, PyarrError, is_arr_api_error

        self.assertTrue(is_arr_api_error(PyarrConnectionError("down")))
        self.assertTrue(is_arr_api_error(PyarrError("generic")))

    def test_unmapped_pyarr_http_status(self) -> None:
        from qBitrr.arss.arr_shared import is_arr_api_error

        self.assertTrue(is_arr_api_error(Exception(415, "")))
        self.assertTrue(is_arr_api_error(Exception(429, "too many requests")))
        self.assertTrue(is_arr_api_error(Exception(503, "unavailable")))

    def test_non_http_exceptions(self) -> None:
        from qBitrr.arss.arr_shared import is_arr_api_error

        self.assertFalse(is_arr_api_error(Exception(200, "ok")))
        self.assertFalse(is_arr_api_error(Exception("415")))
        self.assertFalse(is_arr_api_error(ValueError("nope")))
        self.assertFalse(is_arr_api_error(RuntimeError(415, "")))


class TestSearchLoopYearLoading(unittest.TestCase):
    def _run_year_search_outage(self, side_effect: BaseException):
        from qBitrr.arss.arr_base import ArrBase

        arr = ArrBase.__new__(ArrBase)
        arr._name = "Radarr.Test"
        arr.logger = MagicMock()
        arr.search_missing = True
        arr.do_upgrade_search = False
        arr.quality_unmet_search = False
        arr.custom_format_unmet_search = False
        arr.ombi_search_requests = False
        arr.overseerr_requests = False
        arr.search_by_year = True
        arr.loop_completed = False
        arr.manager = MagicMock()
        event = MagicMock()
        event.is_set.side_effect = [False, True]
        arr.manager.qbit_manager.shutdown_event = event

        with (
            patch("qBitrr.arss.arr_base.run_logs"),
            patch.object(arr, "_sync_loop_settings_from_config"),
            patch.object(arr, "get_year_search", side_effect=side_effect),
            patch.object(arr, "_handle_delay_loop_exception") as delay_handler,
        ):
            arr.run_search_loop()

        return arr, delay_handler

    def _assert_year_search_backed_off(self, arr, delay_handler) -> None:
        delay_handler.assert_called_once()
        delay_exc = delay_handler.call_args.args[0]
        self.assertEqual(delay_exc.error_type, "arr")
        self.assertEqual(delay_exc.length, 300)
        self.assertTrue(delay_handler.call_args.kwargs["reset_torrent_scan_delay"])
        arr.logger.critical.assert_not_called()

    def test_arr_outage_during_year_loading_does_not_kill_worker(self) -> None:
        """Regression: an Arr outage while loading years must back off inside the worker."""
        from qBitrr.arss.arr_shared import PyarrConnectionError

        arr, delay_handler = self._run_year_search_outage(PyarrConnectionError("Arr unavailable"))
        self._assert_year_search_backed_off(arr, delay_handler)

    def test_unmapped_http_415_during_year_loading_does_not_kill_worker(self) -> None:
        """pyarr raises Exception(415, '') for unmapped HTTP codes; must not kill the worker."""
        arr, delay_handler = self._run_year_search_outage(Exception(415, ""))
        self._assert_year_search_backed_off(arr, delay_handler)


class TestSonarrCollectYears(unittest.TestCase):
    def _arr(self):
        from qBitrr.arss.sonarr import SonarrArr

        arr = SonarrArr.__new__(SonarrArr)
        arr.search_in_reverse = False
        arr.search_specials = False
        arr.logger = MagicMock()
        arr.client = MagicMock()
        return arr

    def test_skips_series_that_return_http_415(self) -> None:
        arr = self._arr()
        arr.client.series.get.return_value = [
            {"id": 1, "title": "Bad Show"},
            {"id": 2, "title": "Good Show"},
        ]

        def episode_get(*, series_id=None, item_id=None):
            if series_id == 1:
                raise Exception(415, "")
            return [
                {
                    "airDateUtc": "2021-05-01T00:00:00Z",
                    "seasonNumber": 1,
                    "monitored": True,
                }
            ]

        arr.client.episode.get.side_effect = episode_get
        with patch("qBitrr.arss.sonarr.with_retry", side_effect=lambda fn, **_: fn()):
            years = arr.collect_years_for_search()
        self.assertEqual(years, [2021])
        arr.logger.warning.assert_called()

    def test_reraises_when_every_series_fails(self) -> None:
        arr = self._arr()
        arr.client.series.get.return_value = [{"id": 1, "title": "Bad Show"}]
        arr.client.episode.get.side_effect = Exception(415, "")
        with patch("qBitrr.arss.sonarr.with_retry", side_effect=lambda fn, **_: fn()):
            with self.assertRaises(Exception) as ctx:
                arr.collect_years_for_search()
        self.assertEqual(ctx.exception.args, (415, ""))
        self.assertIs(type(ctx.exception), Exception)


class TestPreserveVsLiveClassification(unittest.TestCase):
    def test_uri_is_preserve_not_live(self) -> None:
        from qBitrr.config_reload_policy import ReloadCategory, classify_config_key

        self.assertEqual(classify_config_key("Radarr-Movies.URI"), ReloadCategory.ARR_PRESERVE_DB)
        self.assertEqual(
            classify_config_key("Radarr-Movies.SkipTLSVerify"), ReloadCategory.ARR_PRESERVE_DB
        )
        self.assertEqual(
            classify_config_key("Radarr-Movies.EntrySearch.SearchMissing"), ReloadCategory.LIVE
        )


if __name__ == "__main__":
    unittest.main()
