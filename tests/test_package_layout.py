"""Regression tests for setuptools package discovery after arss.py split."""

from __future__ import annotations

import importlib.util
import unittest

from setuptools import find_namespace_packages


class TestPackageLayout(unittest.TestCase):
    """Ensure pip-installable layout includes the arss subpackage."""

    def test_find_namespace_packages_includes_arss(self) -> None:
        packages = find_namespace_packages(include=["qBitrr", "qBitrr.arss"])
        self.assertIn("qBitrr", packages)
        self.assertIn("qBitrr.arss", packages)

    def test_arss_module_is_importable_from_source_tree(self) -> None:
        spec = importlib.util.find_spec("qBitrr.arss")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.submodule_search_locations)

    def test_arss_arr_submodule_importable(self) -> None:
        spec = importlib.util.find_spec("qBitrr.arss.arr")
        self.assertIsNotNone(spec)
