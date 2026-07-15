"""Route contract tests for WebUI helpers and representative /api+/web pairs."""

from __future__ import annotations

import unittest
from unittest import mock

from flask import Flask

from qBitrr.webui import dual_route, parse_catalog_filters, resolve_arr_handler


class TestParseCatalogFilters(unittest.TestCase):
    def test_parses_page_and_missing_only(self) -> None:
        req = mock.MagicMock()
        req.args.get.side_effect = lambda key, default=None, type=str: {
            "q": "test",
            "page": 2,
            "page_size": 25,
            "missing": "1",
        }.get(key, default)
        filters = parse_catalog_filters(req, default_page_size=50, include_missing_only=True)
        self.assertEqual(filters["page"], 2)
        self.assertTrue(filters["missing_only"])


class TestResolveArrHandler(unittest.TestCase):
    def test_returns_503_when_manager_not_ready(self) -> None:
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

    def test_returns_arr_when_category_matches(self) -> None:
        managed = {"movies": mock.MagicMock(type="radarr")}
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
