"""Unit tests for MediaCover candidate order and Pillow thumbnail normalize."""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import MagicMock

from PIL import Image

from qBitrr.webui_thumbnails import (
    _CACHE_KEY_VERSION,
    _POSTER_MAX_EDGE,
    _cache_file_path,
    _get_entity_dict,
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


def test_get_entity_dict_uses_pyarr_v6_movie_get() -> None:
    """Pyarr v6 clients expose ``movie.get``, not flat ``get_movie``."""
    client = MagicMock(spec=["movie"])
    client.movie.get.return_value = {"id": 9, "images": []}
    assert _get_entity_dict(client, "radarr", 9) == {"id": 9, "images": []}
    client.movie.get.assert_called_once_with(item_id=9, includeLocalCovers=True)


def test_get_entity_dict_uses_pyarr_v6_series_get() -> None:
    client = MagicMock(spec=["series"])
    client.series.get.return_value = {"id": 42}
    assert _get_entity_dict(client, "sonarr", 42) == {"id": 42}
    client.series.get.assert_called_once_with(item_id=42, includeLocalCovers=True)


def test_get_entity_dict_uses_pyarr_v6_artist_get() -> None:
    client = MagicMock(spec=["artist"])
    client.artist.get.return_value = {"id": 3}
    assert _get_entity_dict(client, "lidarr_artist", 3) == {"id": 3}
    client.artist.get.assert_called_once_with(item_id=3, includeLocalCovers=True)


def test_get_entity_dict_falls_back_when_include_local_covers_unsupported() -> None:
    client = MagicMock(spec=["movie"])
    # First call with includeLocalCovers raises; second without succeeds.
    client.movie.get.side_effect = [
        TypeError("unexpected kw"),
        {"id": 5},
    ]
    assert _get_entity_dict(client, "radarr", 5) == {"id": 5}
    assert client.movie.get.call_args_list[0].kwargs == {
        "item_id": 5,
        "includeLocalCovers": True,
    }
    assert client.movie.get.call_args_list[1].kwargs == {"item_id": 5}


def test_get_entity_dict_legacy_flat_api_fallback() -> None:
    client = SimpleNamespace(get_movie=MagicMock(return_value={"id": 1}))
    assert _get_entity_dict(client, "radarr", 1) == {"id": 1}
    client.get_movie.assert_called_once_with(1, includeLocalCovers=True)


def test_get_entity_dict_returns_none_for_non_dict() -> None:
    client = MagicMock(spec=["series"])
    client.series.get.return_value = [{"id": 1}]
    assert _get_entity_dict(client, "sonarr", 1) is None


def test_get_entity_dict_returns_none_for_unknown_kind() -> None:
    assert _get_entity_dict(MagicMock(), "unknown", 1) is None
