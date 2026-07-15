"""Golden-master tests for pyarr v6 arr_client migration (Phase 2)."""

from __future__ import annotations

import unittest
from unittest import mock

from qBitrr.arr_client import (
    build_arr_client_kwargs,
    build_lidarr_client,
    execute_command,
)


class TestBuildArrClientKwargs(unittest.TestCase):
    def test_https_url_splits_host_port_tls(self) -> None:
        kwargs = build_arr_client_kwargs(
            "https://radarr.example:7878/radarr",
            "key",
            default_port=7878,
            api_ver="v3",
        )
        self.assertEqual(kwargs["host"], "radarr.example")
        self.assertEqual(kwargs["port"], 7878)
        self.assertTrue(kwargs["tls"])
        self.assertEqual(kwargs["base_path"], "/radarr")
        self.assertEqual(kwargs["api_ver"], "v3")

    def test_lidarr_uses_v1_api_ver(self) -> None:
        with mock.patch("qBitrr.arr_client.Lidarr") as lidarr_cls:
            build_lidarr_client("http://lidarr:8686", "k", verify_ssl=False)
            _, kwargs = lidarr_cls.call_args
            self.assertEqual(kwargs["api_ver"], "v1")
            self.assertEqual(kwargs["port"], 8686)


class TestExecuteCommandFallback(unittest.TestCase):
    def test_execute_command_uses_command_execute(self) -> None:
        client = mock.MagicMock()
        client.command.execute.return_value = {"status": "ok"}
        result = execute_command(client, "RefreshMonitoredDownloads")
        self.assertEqual(result, {"status": "ok"})
        client.command.execute.assert_called_once_with("RefreshMonitoredDownloads")

    def test_execute_command_falls_back_to_raw_post_on_list_response_error(self) -> None:
        client = mock.MagicMock()
        client.command.execute.side_effect = ValueError(
            "Expected a dictionary response from the 'command' endpoint"
        )

        class _HttpUtils:
            def request(self, endpoint: str, *, method: str = "POST", json: dict | None = None):
                assert endpoint == "command"
                assert method == "POST"
                assert json == {"name": "EpisodeSearch", "episodeIds": [1]}
                return [{"id": 1}]

        client.http_utils = _HttpUtils()
        result = execute_command(client, "EpisodeSearch", episodeIds=[1])
        self.assertEqual(result, [{"id": 1}])


class TestPyarrV6ResourceMapping(unittest.TestCase):
    """Document v5-name -> v6 API mapping used when rewriting arss.py call sites."""

    def test_movie_resource_group(self) -> None:
        client = mock.MagicMock()
        client.movie.get.return_value = [{"id": 1}]
        client.movie.update.return_value = {"id": 1}
        client.movie_file.get.return_value = {"id": 2}
        self.assertEqual(client.movie.get(), [{"id": 1}])
        client.movie.get(item_id=5)
        client.movie.get.assert_called_with(item_id=5)
        client.movie.update(data={"id": 1})
        client.movie_file.get(item_id=9)
        client.movie_file.get.assert_called_with(item_id=9)

    def test_queue_delete_uses_blocklist_kwarg(self) -> None:
        client = mock.MagicMock()
        client.queue.delete(item_id=3, remove_from_client=True, blocklist=False)
        client.queue.delete.assert_called_with(item_id=3, remove_from_client=True, blocklist=False)


@unittest.skipUnless(
    __import__("tests.support.branch_compat", fromlist=["HAS_ARR_CLIENT"]).HAS_ARR_CLIENT,
    "arr_client is refactor-only",
)
class TestBuildArrClientKwargsCombinations(unittest.TestCase):
    def test_bare_host_uses_default_port(self) -> None:
        kwargs = build_arr_client_kwargs("radarr.local", "key", default_port=7878, api_ver="v3")
        self.assertEqual(kwargs["host"], "radarr.local")
        self.assertEqual(kwargs["port"], 7878)

    def test_http_without_explicit_port_defaults_to_80(self) -> None:
        kwargs = build_arr_client_kwargs(
            "http://sonarr.local/sonarr",
            "key",
            default_port=8989,
            api_ver="v3",
        )
        self.assertEqual(kwargs["port"], 80)
        self.assertFalse(kwargs["tls"])

    def test_https_without_explicit_port_defaults_to_443(self) -> None:
        kwargs = build_arr_client_kwargs(
            "https://lidarr.local",
            "key",
            default_port=8686,
            api_ver="v1",
        )
        self.assertEqual(kwargs["port"], 443)
        self.assertTrue(kwargs["tls"])

    def test_build_radarr_client_uses_v3(self) -> None:
        with mock.patch("qBitrr.arr_client.Radarr") as radarr_cls:
            from qBitrr.arr_client import build_radarr_client

            build_radarr_client("http://radarr:7878", "k")
            self.assertEqual(radarr_cls.call_args.kwargs["api_ver"], "v3")

    def test_build_sonarr_client_uses_v3(self) -> None:
        with mock.patch("qBitrr.arr_client.Sonarr") as sonarr_cls:
            from qBitrr.arr_client import build_sonarr_client

            build_sonarr_client("http://sonarr:8989", "k")
            self.assertEqual(sonarr_cls.call_args.kwargs["api_ver"], "v3")


@unittest.skipUnless(
    __import__("tests.support.branch_compat", fromlist=["HAS_ARR_CLIENT"]).HAS_ARR_CLIENT,
    "arr_client is refactor-only",
)
class TestExecuteCommandEdgeCases(unittest.TestCase):
    def test_reraises_unrelated_value_error(self) -> None:
        client = mock.MagicMock()
        client.command.execute.side_effect = ValueError("other error")
        with self.assertRaises(ValueError):
            execute_command(client, "Test")

    def test_raw_post_uses_data_payload_when_supported(self) -> None:
        client = mock.MagicMock()
        client.command.execute.side_effect = ValueError(
            "Expected a dictionary response from the 'command' endpoint"
        )

        class _HttpUtils:
            def request(self, endpoint: str, *, method: str = "POST", data: dict | None = None):
                assert data == {"name": "Test", "foo": "bar"}
                return {"ok": True}

        client.http_utils = _HttpUtils()
        result = execute_command(client, "Test", foo="bar")
        self.assertEqual(result, {"ok": True})
