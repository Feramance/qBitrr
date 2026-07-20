"""Regression tests for setuptools package discovery after arss.py split."""

from __future__ import annotations

import importlib.util
import unittest

from setuptools import find_namespace_packages


class TestPackageLayout(unittest.TestCase):
    """Ensure pip-installable layout includes the arss subpackage."""

    def test_find_namespace_packages_includes_arss(self) -> None:
        packages = find_namespace_packages(
            where=str(__file__).rsplit("/tests/", 1)[0],
            include=[
                "qBitrr",
                "qBitrr.arss",
                "qBitrr.gen_config",
                "qBitrr.webui",
                "qBitrr.webui.catalog",
                "qBitrr.webui.routes",
            ],
        )
        self.assertIn("qBitrr", packages)
        self.assertIn("qBitrr.arss", packages)
        self.assertIn("qBitrr.gen_config", packages)
        self.assertIn("qBitrr.webui", packages)
        self.assertIn("qBitrr.webui.catalog", packages)
        self.assertIn("qBitrr.webui.routes", packages)

    def test_arss_module_is_importable_from_source_tree(self) -> None:
        spec = importlib.util.find_spec("qBitrr.arss")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.submodule_search_locations)

    def test_arss_arr_submodule_importable(self) -> None:
        for name in (
            "qBitrr.arss.arr",
            "qBitrr.arss.arr_base",
            "qBitrr.arss.arr_shared",
            "qBitrr.arss.placeholder_arr",
            "qBitrr.arss.radarr",
            "qBitrr.arss.sonarr",
            "qBitrr.arss.lidarr",
            "qBitrr.arss.factory",
            "qBitrr.arss.torrent_dispatch",
            "qBitrr.arss.torrent_limits",
            "qBitrr.arss.torrent_inspect",
            "qBitrr.arss.torrent_batch",
        ):
            spec = importlib.util.find_spec(name)
            self.assertIsNotNone(spec, name)
