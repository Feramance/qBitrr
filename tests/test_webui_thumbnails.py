"""Unit tests for MediaCover candidate order and Pillow thumbnail normalize."""

from __future__ import annotations

import io

from PIL import Image

from qBitrr.webui_thumbnails import (
    _CACHE_KEY_VERSION,
    _POSTER_MAX_EDGE,
    _cache_file_path,
    _lidarr_artist_mediacovers_candidates,
    _normalize_thumbnail_bytes,
    _radarr_sonarr_mediacovers_candidates,
)


def test_radarr_mediacovers_prefer_small_sizes() -> None:
    urls = _radarr_sonarr_mediacovers_candidates("http://radarr.local", 42)
    assert urls[0].endswith("/api/v3/mediacover/42/poster-250.jpg")
    assert urls[1].endswith("/api/v3/mediacover/42/poster-500.jpg")
    assert urls[2].endswith("/api/v3/mediacover/42/poster.jpg")


def test_rewrite_mediacover_for_api() -> None:
    from qBitrr.webui_thumbnails import _rewrite_mediacover_for_api

    u = _rewrite_mediacover_for_api(
        "https://radarr.local/MediaCover/9/poster.jpg?lastWrite=1", "radarr"
    )
    assert "/api/v3/mediacover/9/poster.jpg" in u
    assert "lastWrite=1" in u
    lid = _rewrite_mediacover_for_api(
        "https://lidarr.local/MediaCover/Artist/3/poster-250.jpg", "lidarr_artist"
    )
    assert "/api/v1/MediaCover/Artist/3/poster-250.jpg" in lid


def test_lidarr_mediacovers_prefer_small_sizes() -> None:
    urls = _lidarr_artist_mediacovers_candidates("http://lidarr.local", 7)
    assert urls[0].endswith("poster-250.jpg")
    assert urls[1].endswith("poster-500.jpg")
    assert "poster.jpg" in urls[2]
    assert urls.index(next(u for u in urls if u.endswith("poster-250.jpg"))) < urls.index(
        next(u for u in urls if u.endswith("/poster.jpg"))
    )


def test_cache_key_includes_v3() -> None:
    assert _CACHE_KEY_VERSION == "v3"
    a = _cache_file_path(kind="radarr", instance_name="Radarr", entry_id=1)
    # Different from a naive v1-style key: ensure version is part of the hash input
    # by checking two different kinds diverge and path ends with .bin.
    b = _cache_file_path(kind="sonarr", instance_name="Radarr", entry_id=1)
    assert a != b
    assert a.suffix == ".bin"


def test_normalize_thumbnail_resizes_and_webp() -> None:
    img = Image.new("RGB", (800, 1200), color=(20, 40, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    raw = buf.getvalue()
    out, mime = _normalize_thumbnail_bytes(raw)
    assert mime in ("image/webp", "image/jpeg")
    assert len(out) < len(raw)
    with Image.open(io.BytesIO(out)) as result:
        w, h = result.size
        assert max(w, h) <= _POSTER_MAX_EDGE
