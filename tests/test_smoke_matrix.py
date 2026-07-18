"""Characterization smoke matrix for Arr LIVE, Overseerr/Ombi, and queue delete.

These cover the P0 checklist rows that can be asserted without a live Docker stack.
Live compose checks remain documented in docs/development/testing.md.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestPackageImportSmoke(unittest.TestCase):
    """Import every arss leaf module (catches missing-name extraction bugs)."""

    def test_import_all_arss_modules(self) -> None:
        arss_dir = REPO_ROOT / "qBitrr" / "arss"
        modules = sorted(p.stem for p in arss_dir.glob("*.py") if p.stem != "__init__")
        for name in modules:
            with self.subTest(module=name):
                __import__(f"qBitrr.arss.{name}")


class TestQueueDeleteBlocklistKwarg(unittest.TestCase):
    """pyarr v6 queue.delete uses blocklist= (not blacklist=)."""

    def test_delete_from_queue_passes_blocklist(self) -> None:
        from qBitrr.arss.base import ArrBase

        arr = ArrBase.__new__(ArrBase)
        arr.client = MagicMock()
        arr.logger = MagicMock()
        arr.client.queue.delete.return_value = {"ok": True}

        with patch("qBitrr.arss.base.with_retry", side_effect=lambda fn, **_: fn()):
            ArrBase.delete_from_queue(arr, id_=99, remove_from_client=True, blacklist=True)

        arr.client.queue.delete.assert_called_once_with(
            item_id=99, remove_from_client=True, blocklist=True
        )


class TestOverseerrApprovedOnlyPaths(unittest.TestCase):
    """Overseerr ApprovedOnly=true and false both resolve _is_media_available."""

    def test_approved_only_false_uses_is_media_available(self) -> None:
        from qBitrr.arss import request_providers

        source = Path(request_providers.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        names: set[str] = set()
        for node in imports:
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    names.add(alias.asname or alias.name)
        self.assertIn(
            "_is_media_available",
            names,
            "_is_media_available must be imported for ApprovedOnly=false path",
        )

    def test_get_oversee_requests_all_approved_only_false_skips_available(self) -> None:
        from qBitrr.arss.request_providers import _get_oversee_requests_all

        arr = MagicMock()
        arr.overseerr_approved_only = False
        arr.overseerr_uri = "http://overseerr:5055"
        arr.overseerr_api_key = "key"
        arr.skip_tls_verify_overseerr = False
        arr.overseerr_is_4k = False
        arr._overseerr_request_media_type.return_value = "movie"
        arr._add_overseerr_type_ids.side_effect = lambda media, data: (
            data["TmdbId"].add(media["tmdbId"]) if media.get("tmdbId") else None
        )
        arr.logger = MagicMock()
        arr.overseerr_requests_release_cache = {}
        list_resp = MagicMock()
        list_resp.raise_for_status = MagicMock()
        list_resp.json.return_value = {
            "results": [
                {
                    "type": "movie",
                    "is4k": False,
                    "media": {"status": 5, "tmdbId": 42, "imdbId": "tt1"},
                }
            ]
        }
        detail_resp = MagicMock()
        detail_resp.raise_for_status = MagicMock()
        detail_resp.json.return_value = {"releaseDate": "2020-01-01"}
        arr.session = MagicMock()
        arr.session.get.side_effect = [list_resp, detail_resp]

        with patch(
            "qBitrr.arss.request_providers._is_media_available", return_value=True
        ) as avail:
            result = _get_oversee_requests_all(arr)

        avail.assert_called()
        # Available media is skipped when ApprovedOnly=false.
        self.assertEqual(result.get("TmdbId", set()), set())

    def test_get_oversee_requests_all_approved_only_true_keeps_processing(self) -> None:
        from qBitrr.arss.request_providers import _get_oversee_requests_all

        arr = MagicMock()
        arr.overseerr_approved_only = True
        arr.overseerr_uri = "http://overseerr:5055"
        arr.overseerr_api_key = "key"
        arr.skip_tls_verify_overseerr = False
        arr.overseerr_is_4k = False
        arr._overseerr_request_media_type.return_value = "movie"
        arr._add_overseerr_type_ids.side_effect = lambda media, data: (
            data["TmdbId"].add(media["tmdbId"]) if media.get("tmdbId") else None
        )
        arr.logger = MagicMock()
        arr.overseerr_requests_release_cache = {}
        list_resp = MagicMock()
        list_resp.raise_for_status = MagicMock()
        list_resp.json.return_value = {
            "results": [
                {
                    "type": "movie",
                    "is4k": False,
                    "media": {"status": 3, "tmdbId": 99, "imdbId": "tt9"},
                }
            ]
        }
        detail_resp = MagicMock()
        detail_resp.raise_for_status = MagicMock()
        detail_resp.json.return_value = {"releaseDate": "2020-01-01"}
        arr.session = MagicMock()
        arr.session.get.side_effect = [list_resp, detail_resp]

        with patch("qBitrr.arss.request_providers._is_media_processing", return_value=True):
            result = _get_oversee_requests_all(arr)

        self.assertIn(99, result.get("TmdbId", set()))


class TestOmbiUpdateCallable(unittest.TestCase):
    def test_db_ombi_update_is_callable(self) -> None:
        from qBitrr.arss.request_providers import db_ombi_update

        arr = MagicMock()
        arr.ombi_search_requests = False
        # Early-return path when Ombi disabled should not raise.
        self.assertIsNone(db_ombi_update(arr))


class TestSonarrOmbiPartialApprove(unittest.TestCase):
    """Sonarr Ombi ApprovedOnly: partial approvals are searchable when any child is approved."""

    def test_ombi_should_include_when_any_child_approved(self) -> None:
        from qBitrr.arss.sonarr import SonarrArr

        arr = MagicMock()
        arr.ombi_approved_only = True
        self.assertTrue(
            SonarrArr._ombi_should_include_request(
                arr,
                {
                    "childRequests": [
                        {"denied": True},
                        {"denied": False},
                    ]
                },
            )
        )

    def test_ombi_should_exclude_when_all_children_denied(self) -> None:
        from qBitrr.arss.sonarr import SonarrArr

        arr = MagicMock()
        arr.ombi_approved_only = True
        self.assertFalse(
            SonarrArr._ombi_should_include_request(
                arr,
                {"childRequests": [{"denied": True}, {"denied": True}]},
            )
        )

    def test_process_ombi_requests_keeps_partial_approve(self) -> None:
        from qBitrr.arss.request_providers import _process_ombi_requests
        from qBitrr.arss.sonarr import SonarrArr

        arr = MagicMock()
        arr.ombi_approved_only = True
        arr._ombi_should_include_request.side_effect = (
            lambda request: SonarrArr._ombi_should_include_request(arr, request)
        )
        arr._add_ombi_request_ids.side_effect = lambda request, data: (
            data["TvdbId"].add(request["tvDbId"]) if request.get("tvDbId") else None
        )

        with patch(
            "qBitrr.arss.request_providers._get_ombi_requests",
            return_value=[
                {
                    "imdbId": "tt123",
                    "tvDbId": 42,
                    "childRequests": [{"denied": True}, {"denied": False}],
                }
            ],
        ):
            result = _process_ombi_requests(arr)

        self.assertIn("tt123", result.get("ImdbId", set()))
        self.assertIn(42, result.get("TvdbId", set()))


class TestPolymorphicDbUpdateDispatch(unittest.TestCase):
    def test_db_update_single_series_calls_concrete_hook(self) -> None:
        from qBitrr.arss.db_update_handlers import db_update_single_series

        arr = MagicMock()
        arr.search_missing = True
        arr.do_upgrade_search = False
        arr.quality_unmet_search = False
        arr.custom_format_unmet_search = False
        arr._name = "Radarr-Movies"
        arr.logger = MagicMock()
        db_entry = {"id": 1, "title": "Test"}

        with patch("qBitrr.arss.db_update_handlers.refresh_rollups_after_db_update") as refresh:
            db_update_single_series(arr, db_entry=db_entry, request=False)

        arr._db_update_single_entry.assert_called_once_with(
            db_entry, request=False, series=False, artist=False
        )
        refresh.assert_called_once()


class TestLidarrAlbumCollectParity(unittest.TestCase):
    def test_collect_album_ids_uses_all_artist_albums(self) -> None:
        source = (REPO_ROOT / "qBitrr" / "arss" / "db_queries.py").read_text(encoding="utf-8")
        self.assertIn(
            "all_artist_albums=True",
            source,
            "_collect_album_ids must request all_artist_albums like LidarrArr._db_update_media",
        )


if __name__ == "__main__":
    unittest.main()
