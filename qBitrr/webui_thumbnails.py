from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

import requests

from qBitrr.config import HOME_PATH

logger = logging.getLogger("qBitrr.WebUI.Thumbnails")

# Radarr / Sonarr often use TMDB/CDN; Lidarr uses remote cover URLs. Keep a hard cap.
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_REQUEST_TIMEOUT = 20


def _cache_dir() -> Path:
    d = (HOME_PATH / "cache" / "thumbnails").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_file_path(*, kind: str, instance_name: str, entry_id: int) -> Path:
    h = hashlib.sha256(
        f"{kind}\0{instance_name}\0{entry_id}".encode("utf-8", "replace")
    ).hexdigest()[:40]
    return _cache_dir() / f"{h}.bin"


def _first_poster_url_from_radarr_sonarr(data: dict[str, Any]) -> str | None:
    u = data.get("remotePoster")
    if u and isinstance(u, str) and u.strip().startswith("http"):
        return u.strip()
    for img in data.get("images") or ():
        if not isinstance(img, dict):
            continue
        u = img.get("remoteUrl") or img.get("url")
        if u and str(u).strip().startswith("http"):
            return str(u).strip()
    return None


def _first_cover_lidarr(data: dict[str, Any]) -> str | None:
    u = data.get("images")
    if isinstance(u, list):
        for im in u:
            if not isinstance(im, dict):
                continue
            c = str(im.get("coverType", "")).lower()
            if c in ("cover", "poster", "disc"):
                url = im.get("url") or im.get("remoteUrl")
                if url and str(url).strip().startswith("http"):
                    return str(url).strip()
    for k in (
        "remoteCover",
        "remotePoster",
        "url",
    ):
        u = data.get(k)
        if u and str(u).strip().startswith("http"):
            return str(u).strip()
    return None


def _sniff_mime(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 3 and data[:3] == b"GIF":
        return "image/gif"
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _http_get_bytes(url: str) -> bytes | None:
    if not re.match(r"^https?://", url, re.IGNORECASE):
        logger.debug("Skip non-HTTP image URL: %r", url[:80])
        return None
    try:
        with requests.get(
            url,
            stream=True,
            timeout=_REQUEST_TIMEOUT,
            headers={"User-Agent": "qBitrr/1.0 (WebUI thumbnail)"},
        ) as r:
            r.raise_for_status()
            cl = r.headers.get("Content-Length")
            if cl and cl.isdigit() and int(cl) > _MAX_IMAGE_BYTES:
                logger.debug("Image too large (Content-Length): %s", cl)
                return None
            chunks: list[bytes] = []
            total = 0
            for ch in r.iter_content(chunk_size=64 * 1024):
                if not ch:
                    continue
                total += len(ch)
                if total > _MAX_IMAGE_BYTES:
                    logger.debug("Image exceeded max size while reading")
                    return None
                chunks.append(ch)
            if not chunks:
                return None
            return b"".join(chunks)
    except Exception as e:
        logger.debug("Thumbnail fetch failed: %s", e, exc_info=True)
        return None


def resolve_image_url(*, kind: str, arr: Any, entry_id: int) -> str | None:
    client = getattr(arr, "client", None)
    if not client:
        return None
    try:
        if kind == "radarr" and hasattr(client, "get_movie"):
            data = client.get_movie(entry_id)
        elif kind == "sonarr" and hasattr(client, "get_series"):
            data = client.get_series(entry_id)
        elif kind == "lidarr" and hasattr(client, "get_album"):
            data = client.get_album(entry_id)
        else:
            return None
    except Exception:
        logger.debug("Arr API get_* failed for %s %s", kind, entry_id, exc_info=True)
        return None
    if not isinstance(data, dict):
        return None
    if kind == "lidarr":
        return _first_cover_lidarr(data)
    return _first_poster_url_from_radarr_sonarr(data)


def get_or_fetch_thumbnail_bytes(
    *, kind: str, instance_name: str, arr: Any, entry_id: int
) -> tuple[bytes, str] | None:
    path = _cache_file_path(kind=kind, instance_name=instance_name, entry_id=entry_id)
    if path.is_file() and path.stat().st_size > 0:
        b = path.read_bytes()
        return b, _sniff_mime(b)

    url = resolve_image_url(kind=kind, arr=arr, entry_id=entry_id)
    if not url:
        return None
    u = url.strip()
    if "image.tmdb.org" in u and u.startswith("http://"):
        u = "https://" + u.removeprefix("http://")

    raw = _http_get_bytes(u)
    if not raw:
        return None
    mime = _sniff_mime(raw)
    try:
        path.write_bytes(raw)
    except OSError as e:
        logger.debug("Could not write thumbnail cache: %s", e)
    return raw, mime
