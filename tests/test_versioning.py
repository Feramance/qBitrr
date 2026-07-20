"""Tests for version normalization and comparison with MAJOR.MINOR.PATCH-BUILD."""

from __future__ import annotations

from qBitrr.bundled_data import patched_version, tagged_version, version
from qBitrr.versioning import is_newer_version, normalize_version


def test_bundled_version_has_no_git_hash_suffix() -> None:
    assert version == "5.12.12-1"
    assert patched_version == version
    assert tagged_version == version
    assert "+" not in patched_version


def test_normalize_version_strips_v_prefix() -> None:
    assert normalize_version("v5.12.12-1") == "5.12.12-1"
    assert normalize_version("V5.12.12-2") == "5.12.12-2"


def test_normalize_version_keeps_build_segment() -> None:
    assert normalize_version("5.12.12-3") == "5.12.12-3"
    assert normalize_version("v5.12.12-3") == "5.12.12-3"


def test_normalize_version_strips_local_metadata() -> None:
    assert normalize_version("5.12.12-1+abc12345") == "5.12.12-1"


def test_build_bump_is_newer() -> None:
    assert is_newer_version("5.12.12-2", "5.12.12-1") is True
    assert is_newer_version("5.12.12-1", "5.12.12-2") is False


def test_patch_bump_is_newer_than_prior_builds() -> None:
    assert is_newer_version("5.12.13-1", "5.12.12-9") is True
    assert is_newer_version("5.12.12-9", "5.12.13-1") is False
