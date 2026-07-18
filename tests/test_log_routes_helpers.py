"""Unit tests for log tail/delta/search helpers via the register_log_routes module."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from flask import Flask

from qBitrr.webui.routes.log_routes import register_log_routes


class TestLogRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.logs_root = Path(self.tmp.name)
        self.app = Flask(__name__)
        self.webui = MagicMock()
        self.webui.logger = MagicMock()

        def dual_route(rule: str, **options):
            def decorator(fn):
                self.app.add_url_rule(f"/api{rule}", f"api_{fn.__name__}", fn, **options)
                self.app.add_url_rule(f"/web{rule}", f"web_{fn.__name__}", fn, **options)
                return fn

            return decorator

        def resolve(name: str) -> Path | None:
            if ".." in name or "/" in name or "\\" in name:
                return None
            candidate = (self.logs_root / name).resolve(strict=False)
            try:
                candidate.relative_to(self.logs_root.resolve())
            except ValueError:
                return None
            return candidate

        register_log_routes(
            self.webui,
            _dual_route=dual_route,
            _resolve_log_file=resolve,
            logs_root=self.logs_root,
            _webui_mod=MagicMock,
        )
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, name: str, text: str) -> Path:
        path = self.logs_root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_json_tail_and_delta(self) -> None:
        self._write("Main.log", "line1\nline2\nline3\nline4\n")
        resp = self.client.get("/web/logs/Main.log?format=json&lines=2")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("line3", data["content"])
        self.assertIn("line4", data["content"])
        self.assertNotIn("line1", data["content"])
        self.assertFalse(data["rotated"])
        next_bytes = data["next_bytes"]
        inode = data["inode"]

        # No growth → empty delta
        resp2 = self.client.get(
            f"/web/logs/Main.log?format=json&since_bytes={next_bytes}&inode={inode}"
        )
        data2 = resp2.get_json()
        self.assertEqual(data2["content"], "")
        self.assertEqual(data2["next_bytes"], next_bytes)

        # Append and delta
        path = self.logs_root / "Main.log"
        with path.open("a", encoding="utf-8") as f:
            f.write("line5\n")
        resp3 = self.client.get(
            f"/web/logs/Main.log?format=json&since_bytes={next_bytes}&inode={inode}"
        )
        data3 = resp3.get_json()
        self.assertIn("line5", data3["content"])
        self.assertGreater(data3["next_bytes"], next_bytes)

    def test_search_includes_rotated(self) -> None:
        self._write("Main.log", "current ERROR boom\n")
        self._write("Main.log.old", "old WARNING noise\nold ERROR archived\n")
        resp = self.client.get("/web/logs/Main.log/search?q=ERROR&include_rotated=1&context=0")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        files = {m["file"] for m in data["matches"]}
        self.assertIn("Main.log", files)
        self.assertIn("Main.log.old", files)
        self.assertGreaterEqual(len(data["matches"]), 2)

    def test_sse_stream_emits_append_then_reconnect(self) -> None:
        self._write("Main.log", "hello\n")
        import qBitrr.webui.routes.log_routes as log_routes

        # Force a single-iteration stream so the test cannot hang on sleep.
        original_max = log_routes._SSE_MAX_SECONDS
        original_sleep = log_routes.time.sleep
        log_routes._SSE_MAX_SECONDS = 0.0
        log_routes.time.sleep = lambda _s: None
        try:
            resp = self.client.get("/web/logs/Main.log/stream?since_bytes=0")
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.mimetype.startswith("text/event-stream"))
            body = b"".join(resp.response).decode("utf-8")
            self.assertIn("event: reconnect", body)
        finally:
            log_routes._SSE_MAX_SECONDS = original_max
            log_routes.time.sleep = original_sleep


if __name__ == "__main__":
    unittest.main()
