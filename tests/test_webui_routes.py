"""Route contract tests for WebUI /api+/web pairs and divergent endpoints."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from qBitrr.webui import (
    WebUI,
    dual_route,
    empty_catalog_payload,
    parse_catalog_filters,
    resolve_arr_handler,
)

# 31 JSON-identical /api + /web pairs via @_dual_route (SSE stream tested separately;
# 3 divergent pairs tested in TestDivergentRoutePairs). Total dual_route registrations: 32.
IDENTICAL_ROUTE_PAIRS: list[tuple[str, str, str]] = [
    ("get", "/openapi.json", ""),
    ("get", "/docs", ""),
    ("get", "/processes", ""),
    ("post", "/processes/movies/search/restart", ""),
    ("post", "/processes/restart_all", ""),
    ("post", "/loglevel", '{"level":"INFO"}'),
    ("post", "/arr/rebuild", ""),
    ("get", "/logs", ""),
    ("get", "/logs/test.log", ""),
    ("get", "/logs/test.log/search?q=test", ""),
    ("get", "/logs/test.log/download", ""),
    ("get", "/radarr/movies/movies", ""),
    ("get", "/radarr/movies/movie/1/thumbnail", ""),
    ("get", "/sonarr/tv/series", ""),
    ("get", "/sonarr/tv/series/1/thumbnail", ""),
    ("get", "/lidarr/music/albums", ""),
    ("get", "/lidarr/music/artists", ""),
    ("get", "/lidarr/music/artist/1", ""),
    ("get", "/lidarr/music/artist/1/thumbnail", ""),
    ("get", "/readarr/books/authors", ""),
    ("get", "/readarr/books/author/1", ""),
    ("get", "/readarr/books/author/1/thumbnail", ""),
    ("get", "/arr/books/open/author/1", ""),
    ("get", "/arr", ""),
    ("post", "/update", ""),
    ("get", "/download-update", ""),
    ("get", "/status", ""),
    ("post", "/arr/movies/restart", ""),
    ("get", "/config/schema", ""),
    ("post", "/config", '{"changes":{}}'),
    ("post", "/arr/test-connection", '{"type":"radarr","uri":"http://x","apiKey":"k"}'),
]

DIVERGENT_PAIRS = (
    ("/meta",),
    ("/config",),
    ("/token",),
)

_DUAL_ROUTE_RE = re.compile(
    r"^\s*@_dual_route\(\s*"
    r"(?P<quote>[\"'])(?P<path>[^\"']+)(?P=quote)"
    r"(?:\s*,\s*methods\s*=\s*\((?P<methods>[^\)]+)\))?",
    re.MULTILINE,
)


def _config_get(key: str, fallback: Any = None) -> Any:
    values = {
        "WebUI.AuthDisabled": True,
        "WebUI.Token": "test-token",
        "WebUI.BehindHttpsProxy": False,
        "WebUI.LocalAuthEnabled": False,
        "WebUI.PasswordHash": "",
        "WebUI.Username": "",
        "WebUI.OIDC.CallbackPath": "/signin-oidc",
        "Settings.ConfigVersion": "5.12.11",
    }
    return values.get(key, fallback)


class _WebUIClientTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = MagicMock()
        self.manager.is_alive = True
        self.manager.qBit_Host = "127.0.0.1"
        self.manager.qBit_Port = 8080
        self.manager.current_qbit_version = "5.0"
        self.manager.get_all_instances.return_value = []
        self.manager.is_instance_alive.return_value = False
        self.manager.get_instance_info.return_value = {}
        self.manager.qbit_category_managers = {}
        self.manager._process_registry = {}
        self.manager.child_processes = []
        self.manager.managed_objects = {}

        patches = [
            patch("qBitrr.webui.CONFIG.get", side_effect=_config_get),
            patch("qBitrr.webui.CONFIG.config", {}),
            patch("qBitrr.webui.CONFIG.save"),
            patch("qBitrr.webui.CONFIG.load"),
            patch("qBitrr.webui.run_logs"),
            patch("qBitrr.webui.fetch_search_activities", return_value={}),
            patch.object(WebUI, "_ensure_version_info", return_value={"current_version": "0.0.0"}),
            patch.object(WebUI, "_reload_all"),
            patch.object(WebUI, "_trigger_manual_update", return_value=(True, "started")),
        ]
        self._patchers = patches
        for p in patches:
            p.start()
        self.webui = WebUI(self.manager)
        self.client = self.webui.app.test_client()

    def tearDown(self) -> None:
        for p in reversed(self._patchers):
            p.stop()


class TestEmptyCatalogPayload(unittest.TestCase):
    def test_radarr_shape(self) -> None:
        payload = empty_catalog_payload("radarr", page=1, page_size=25)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["movies"], [])

    def test_lidarr_albums_shape(self) -> None:
        payload = empty_catalog_payload("lidarr_albums")
        self.assertIn("counts_tracks", payload)
        self.assertEqual(payload["albums"], [])

    def test_readarr_authors_shape(self) -> None:
        payload = empty_catalog_payload("readarr_authors")
        self.assertIn("book_total", payload)
        self.assertEqual(payload["authors"], [])


class TestDualRouteRegistration(unittest.TestCase):
    def test_webui_declares_thirty_one_dual_route_pairs(self) -> None:
        webui_pkg = Path(__file__).resolve().parents[1].joinpath("qBitrr", "webui")
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(webui_pkg.rglob("*.py"))
        )
        paths = [match.group("path") for match in _DUAL_ROUTE_RE.finditer(source)]
        self.assertEqual(len(paths), 32, msg=f"dual_route paths: {paths}")


class TestIdenticalRoutePairs(_WebUIClientTestCase):
    def test_all_identical_json_pairs_match(self) -> None:
        self.assertEqual(len(IDENTICAL_ROUTE_PAIRS), 31)
        for method, path, body in IDENTICAL_ROUTE_PAIRS:
            with self.subTest(method=method, path=path):
                api_resp = getattr(self.client, method)(
                    f"/api{path}", data=body, content_type="application/json"
                )
                web_resp = getattr(self.client, method)(
                    f"/web{path}", data=body, content_type="application/json"
                )
                self.assertEqual(api_resp.status_code, web_resp.status_code)
                self.assertEqual(api_resp.get_json(), web_resp.get_json())

    def test_log_stream_pair_matches_headers(self) -> None:
        """SSE pairs match on status/mimetype; body is a long-lived stream."""
        import qBitrr.webui.routes.log_routes as log_routes

        original_max = log_routes._SSE_MAX_SECONDS
        original_sleep = log_routes.time.sleep
        log_routes._SSE_MAX_SECONDS = 0.0
        log_routes.time.sleep = lambda _s: None
        try:
            api_resp = self.client.get("/api/logs/test.log/stream?since_bytes=0")
            web_resp = self.client.get("/web/logs/test.log/stream?since_bytes=0")
            self.assertEqual(api_resp.status_code, web_resp.status_code)
            self.assertEqual(api_resp.mimetype, web_resp.mimetype)
            self.assertTrue(
                (api_resp.mimetype or "").startswith("text/event-stream")
                or api_resp.status_code == 404
            )
        finally:
            log_routes._SSE_MAX_SECONDS = original_max
            log_routes.time.sleep = original_sleep


class TestDivergentRoutePairs(_WebUIClientTestCase):
    def test_meta_web_adds_auth_fields(self) -> None:
        api = self.client.get("/api/meta").get_json()
        web = self.client.get("/web/meta").get_json()
        self.assertNotIn("auth_required", api)
        self.assertIn("auth_required", web)
        self.assertIn("url_base", web)

    def test_config_get_web_wraps_version_warning(self) -> None:
        with (
            patch("qBitrr.webui._toml_to_jsonable", return_value={"Settings": {}}),
            patch("qBitrr.webui._strip_sensitive_keys", side_effect=lambda x: x),
            patch(
                "qBitrr.config_version.validate_config_version",
                return_value=(False, "Config version mismatch"),
            ),
            patch("qBitrr.config_version.get_config_version", return_value="0.0.1"),
        ):
            api = self.client.get("/api/config").get_json()
            web = self.client.get("/web/config").get_json()
        self.assertNotIn("warning", api)
        self.assertIn("warning", web)

    def test_token_endpoints_differ_when_auth_enabled(self) -> None:
        with patch(
            "qBitrr.webui.CONFIG.get",
            side_effect=lambda key, fallback=None: {
                "WebUI.AuthDisabled": False,
                "WebUI.Token": "test-token",
                "WebUI.BehindHttpsProxy": False,
                "WebUI.LocalAuthEnabled": True,
                "WebUI.PasswordHash": "x",
                "WebUI.Username": "u",
                "WebUI.OIDC.CallbackPath": "/signin-oidc",
            }.get(key, fallback),
        ):
            webui = WebUI(self.manager)
            client = webui.app.test_client()
            api = client.get("/api/token")
            web = client.get("/web/token")
        self.assertEqual(api.status_code, 401)
        self.assertEqual(web.status_code, 401)

    def test_token_returns_when_auth_disabled(self) -> None:
        """AuthDisabled short-circuits auth; token endpoints remain fully supported."""
        api = self.client.get("/api/token")
        web = self.client.get("/web/token")
        self.assertEqual(api.status_code, 200)
        self.assertEqual(web.status_code, 200)
        self.assertEqual(api.get_json(), {"token": "test-token"})
        self.assertEqual(web.get_json(), {"token": "test-token"})

    def test_token_accepts_bearer_when_auth_enabled(self) -> None:
        with patch(
            "qBitrr.webui.CONFIG.get",
            side_effect=lambda key, fallback=None: {
                "WebUI.AuthDisabled": False,
                "WebUI.Token": "test-token",
                "WebUI.BehindHttpsProxy": False,
                "WebUI.LocalAuthEnabled": True,
                "WebUI.PasswordHash": "x",
                "WebUI.Username": "u",
                "WebUI.OIDC.CallbackPath": "/signin-oidc",
            }.get(key, fallback),
        ):
            webui = WebUI(self.manager)
            client = webui.app.test_client()
            api = client.get("/api/token", headers={"Authorization": "Bearer test-token"})
            web = client.get("/web/token", headers={"Authorization": "Bearer test-token"})
        self.assertEqual(api.status_code, 200)
        self.assertEqual(web.status_code, 200)
        self.assertEqual(api.get_json(), {"token": "test-token"})
        self.assertEqual(web.get_json(), {"token": "test-token"})

    def test_qbit_overview_requires_auth_when_enabled(self) -> None:
        # Avoid MagicMock auto-attrs (client/default_instance) poisoning overview JSON.
        self.manager.get_all_instances.return_value = []
        self.manager.client = None
        self.manager.default_instance = None
        self.manager.get_client = None
        self.manager.qbit_category_managers = {}
        self.manager.arr_manager = None
        with patch(
            "qBitrr.webui.CONFIG.get",
            side_effect=lambda key, fallback=None: {
                "WebUI.AuthDisabled": False,
                "WebUI.Token": "test-token",
                "WebUI.BehindHttpsProxy": False,
                "WebUI.LocalAuthEnabled": True,
                "WebUI.PasswordHash": "x",
                "WebUI.Username": "u",
                "WebUI.OIDC.CallbackPath": "/signin-oidc",
            }.get(key, fallback),
        ):
            webui = WebUI(self.manager)
            client = webui.app.test_client()
            unauthorized = client.get("/web/qbit/overview")
            authorized = client.get(
                "/web/qbit/overview",
                headers={"Authorization": "Bearer test-token"},
            )
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(authorized.status_code, 200)
        payload = authorized.get_json()
        self.assertEqual(payload["instances"], [])
        self.assertEqual(payload["categories"], [])

    def test_qbit_categories_requires_auth_when_enabled(self) -> None:
        self.manager.qbit_category_managers = {}
        self.manager.arr_manager = None
        with patch(
            "qBitrr.webui.CONFIG.get",
            side_effect=lambda key, fallback=None: {
                "WebUI.AuthDisabled": False,
                "WebUI.Token": "test-token",
                "WebUI.BehindHttpsProxy": False,
                "WebUI.LocalAuthEnabled": True,
                "WebUI.PasswordHash": "x",
                "WebUI.Username": "u",
                "WebUI.OIDC.CallbackPath": "/signin-oidc",
            }.get(key, fallback),
        ):
            webui = WebUI(self.manager)
            client = webui.app.test_client()
            unauthorized = client.get("/web/qbit/categories")
        self.assertEqual(unauthorized.status_code, 401)


class TestParseCatalogFilters(unittest.TestCase):
    def test_parses_page_and_missing_only(self) -> None:
        req = MagicMock()
        req.args.get.side_effect = lambda key, default=None, type=str: {
            "q": "test",
            "page": 2,
            "page_size": 25,
            "missing": "1",
        }.get(key, default)
        filters = parse_catalog_filters(req, default_page_size=50, include_missing_only=True)
        self.assertEqual(filters["page"], 2)
        self.assertTrue(filters["missing_only"])

    def test_defaults_page_size_and_missing_only_false(self) -> None:
        req = MagicMock()
        req.args.get.side_effect = lambda key, default=None, type=str: default
        filters = parse_catalog_filters(req, default_page_size=50, include_missing_only=True)
        self.assertEqual(filters["page"], 0)
        self.assertEqual(filters["page_size"], 50)
        self.assertFalse(filters["missing_only"])

    def test_omits_missing_only_when_disabled(self) -> None:
        req = MagicMock()
        req.args.get.side_effect = lambda key, default=None, type=str: {"missing": "1"}.get(
            key, default
        )
        filters = parse_catalog_filters(req, include_missing_only=False)
        self.assertNotIn("missing_only", filters)


class TestResolveArrHandler(unittest.TestCase):
    def test_returns_503_when_manager_not_ready(self) -> None:
        from flask import Flask

        app = Flask(__name__)
        with app.app_context():
            arr, err = resolve_arr_handler(
                "movies",
                "radarr",
                {},
                arr_manager_ready=False,
            )
        self.assertIsNone(arr)
        self.assertIsNotNone(err)
        self.assertEqual(err[1], 503)

    def test_returns_404_when_category_missing(self) -> None:
        from flask import Flask

        app = Flask(__name__)
        with app.app_context():
            arr, err = resolve_arr_handler(
                "missing",
                "radarr",
                {"movies": MagicMock(type="radarr")},
                arr_manager_ready=True,
            )
        self.assertIsNone(arr)
        self.assertIsNotNone(err)
        self.assertEqual(err[1], 404)

    def test_returns_404_when_arr_type_mismatch(self) -> None:
        from flask import Flask

        app = Flask(__name__)
        with app.app_context():
            managed = {"tv": MagicMock(type="sonarr")}
            arr, err = resolve_arr_handler(
                "tv",
                "radarr",
                managed,
                arr_manager_ready=True,
            )
        self.assertIsNone(arr)
        self.assertEqual(err[1], 404)

    def test_returns_arr_when_category_matches(self) -> None:
        managed = {"movies": MagicMock(type="radarr")}
        arr, err = resolve_arr_handler(
            "movies",
            "radarr",
            managed,
            arr_manager_ready=True,
        )
        self.assertIs(err, None)
        self.assertIs(arr, managed["movies"])


class TestDualRoute(unittest.TestCase):
    def test_registers_api_and_web_endpoints(self) -> None:
        from flask import Flask

        app = Flask(__name__)

        @dual_route(app, "/health-check-test")
        def _health_check_test():
            return {"ok": True}

        rules = {rule.rule for rule in app.url_map.iter_rules()}
        self.assertIn("/api/health-check-test", rules)
        self.assertIn("/web/health-check-test", rules)
        client = app.test_client()
        self.assertEqual(client.get("/api/health-check-test").json, {"ok": True})
        self.assertEqual(client.get("/web/health-check-test").json, {"ok": True})


class TestArrOpenRedirect(_WebUIClientTestCase):
    def _set_managed(self, category: str, arr: MagicMock) -> None:
        arr_manager = MagicMock()
        arr_manager.managed_objects = {category: arr}
        self.manager.arr_manager = arr_manager

    def test_readarr_author_returns_302(self) -> None:
        arr = MagicMock()
        arr.type = "readarr"
        arr.uri = "http://readarr:8787"
        arr.client.author.get.return_value = {
            "foreignAuthorId": "author-slug",
            "id": 5,
        }
        self._set_managed("readarr-books", arr)
        resp = self.client.get("/web/arr/readarr-books/open/author/5")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.location, "http://readarr:8787/author/author-slug")

    def test_radarr_movie_returns_302(self) -> None:
        arr = MagicMock()
        arr.type = "radarr"
        arr.uri = "http://radarr:7878"
        arr.client.movie.get.return_value = {"titleSlug": "the-matrix", "id": 42}
        self._set_managed("radarr-movies", arr)
        resp = self.client.get("/web/arr/radarr-movies/open/movie/42")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.location, "http://radarr:7878/movie/the-matrix")

    def test_sonarr_series_returns_302(self) -> None:
        arr = MagicMock()
        arr.type = "sonarr"
        arr.uri = "http://sonarr:8989"
        arr.client.series.get.return_value = {"titleSlug": "breaking-bad", "id": 7}
        self._set_managed("sonarr-tv", arr)
        resp = self.client.get("/web/arr/sonarr-tv/open/series/7")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.location, "http://sonarr:8989/series/breaking-bad")

    def test_lidarr_artist_returns_302(self) -> None:
        arr = MagicMock()
        arr.type = "lidarr"
        arr.uri = "http://lidarr:8686"
        arr.client.artist.get.return_value = {
            "foreignArtistId": "artist-guid",
            "titleSlug": "slug",
            "id": 99,
        }
        self._set_managed("lidarr-music", arr)
        resp = self.client.get("/web/arr/lidarr-music/open/artist/99")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.location, "http://lidarr:8686/artist/artist-guid")


if __name__ == "__main__":
    unittest.main()
