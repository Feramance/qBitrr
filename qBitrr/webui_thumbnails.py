from __future__ import annotations

import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from qBitrr.config import HOME_PATH

logger = logging.getLogger("qBitrr.WebUI.Thumbnails")

# Only use images served by the same host as the Arr base URL (e.g. MediaCover).
# No external metadata CDNs. Keep a hard cap on downloaded size.
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_REQUEST_TIMEOUT = 20
# requests only strips Authorization on cross-host redirects; X-Api-Key would leak — follow manually.
_MAX_THUMB_REDIRECTS = 10
# Wall-clock budget across all redirect hops (per single thumbnail fetch).
_THUMB_TOTAL_TIMEOUT = 30.0

# Cache directory resolution is idempotent; memoise to skip the per-request ``mkdir`` syscall.
_CACHE_DIR_PATH: Path | None = None


def _cache_dir() -> Path:
    global _CACHE_DIR_PATH
    if _CACHE_DIR_PATH is None:
        d = (HOME_PATH / "cache" / "thumbnails").resolve()
        d.mkdir(parents=True, exist_ok=True)
        _CACHE_DIR_PATH = d
    return _CACHE_DIR_PATH


def _cache_file_path(*, kind: str, instance_name: str, entry_id: int) -> Path:
    h = hashlib.sha256(
        f"{kind}\0{instance_name}\0{entry_id}".encode("utf-8", "replace")
    ).hexdigest()[:40]
    return _cache_dir() / f"{h}.bin"


def _cache_etag_path(bin_path: Path) -> Path:
    """Sidecar with 64-char hex SHA256 (no quotes), matching ``Response`` ETag derivation."""

    return bin_path.with_suffix(".etag")


_DIGEST_HEX64_RE = re.compile(r"^[a-fA-F0-9]{64}\s*$")


def sha256_digest_file(bin_path: Path) -> str:
    """Streamed SHA256 of file bytes; lowercase hex."""

    digest = hashlib.sha256()
    with open(bin_path, "rb") as f:
        while True:
            chunk = f.read(256 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_etag_sidecar(bin_path: Path, digest_hex: str) -> None:
    _cache_etag_path(bin_path).write_text(
        f"{digest_hex.lower()}\n", encoding="ascii", newline="\n"
    )


def thumbnail_quoted_etag(kind: str, instance_name: str, entry_id: int) -> str | None:
    """
    Strong ETag for a cached thumbnail when a ``.etag`` sidecar exists (64 hex chars).
    Does not read the large ``.bin`` file. Legacy caches without a sidecar return
    ``None`` until :func:`get_or_fetch_thumbnail_bytes` migrates the etag on read.

    Returned value matches strong ETags: quoted lowercase hex SHA256 digest of image bytes.
    """

    bin_path = _cache_file_path(kind=kind, instance_name=instance_name, entry_id=entry_id)
    if not bin_path.is_file():
        return None
    try:
        if bin_path.stat().st_size == 0:
            return None
    except OSError:
        return None
    ep = _cache_etag_path(bin_path)
    if not ep.is_file():
        return None
    try:
        txt = ep.read_text(encoding="ascii")
    except OSError:
        return None
    stripped = txt.strip()
    if not _DIGEST_HEX64_RE.match(stripped):
        return None
    return f'"{stripped.lower()}"'


def _netloc_key(base_uri: str) -> str:
    try:
        return urlparse(base_uri).netloc.lower()
    except Exception:
        return ""


def _scheme_for_base_uri(base_uri: str) -> str:
    """Use the Arr ``base_uri`` scheme for protocol-relative links (``//host/...``)."""

    t = base_uri.strip()
    if not t:
        return "http"
    try:
        parsed = urlparse(t)
        sch = (parsed.scheme or "").lower()
        if sch in ("http", "https"):
            return sch
    except Exception:
        pass
    return "http"


def _absolute_image_url(raw: str, base_uri: str) -> str | None:
    s = raw.strip()
    if not s:
        return None
    if s.startswith("//"):
        return _scheme_for_base_uri(base_uri) + ":" + s
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if s.startswith("/"):
        if not base_uri:
            return None
        base = base_uri if base_uri.endswith("/") else base_uri + "/"
        return urljoin(base, s)
    return None


def _is_arr_served_url(absolute_url: str, base_uri: str) -> bool:
    if not base_uri or not absolute_url:
        return False
    want = _netloc_key(base_uri)
    if not want:
        return False
    try:
        got = urlparse(absolute_url).netloc.lower()
    except Exception:
        return False
    return bool(got) and got == want


def _cover_type_order(cover_type: str) -> int:
    ct = cover_type.lower()
    if ct == "poster":
        return 0
    if ct == "cover":
        return 0
    if ct == "banner":
        return 1
    if ct == "clearlogo":
        return 2
    if ct == "fanart":
        return 3
    if ct == "disc":
        return 4
    return 5


def _first_poster_url_from_radarr_sonarr(data: dict[str, Any], base_uri: str) -> str | None:
    images = [x for x in (data.get("images") or ()) if isinstance(x, dict)]
    images.sort(
        key=lambda im: _cover_type_order(str(im.get("coverType") or "")),
    )
    for img in images:
        for key in ("url", "remoteUrl"):
            raw = img.get(key)
            if not raw or not isinstance(raw, str):
                continue
            abs_u = _absolute_image_url(raw, base_uri)
            if not abs_u:
                continue
            if _is_arr_served_url(abs_u, base_uri):
                return abs_u
    rp = data.get("remotePoster")
    if isinstance(rp, str) and rp.strip().startswith("http"):
        u = _absolute_image_url(rp.strip(), base_uri)
        if u and _is_arr_served_url(u, base_uri):
            return u
    return None


_ALLOWED_COVER_TYPES = ("cover", "poster", "disc", "banner", "fanart", "clearlogo")


def _first_cover_lidarr(data: dict[str, Any], base_uri: str) -> str | None:
    images = [x for x in (data.get("images") or ()) if isinstance(x, dict)]
    # If at least one entry has an explicit allowed coverType, ignore unlabeled entries
    # so an unsorted "" doesn't accidentally outrank a real "poster" after _cover_type_order.
    has_explicit_cover = any(
        str(im.get("coverType") or "").lower() in _ALLOWED_COVER_TYPES for im in images
    )
    images.sort(
        key=lambda im: _cover_type_order(str(im.get("coverType") or "")),
    )
    for im in images:
        c = str(im.get("coverType", "")).lower()
        if not c:
            if has_explicit_cover:
                continue
        elif c not in _ALLOWED_COVER_TYPES:
            continue
        for key in ("url", "remoteUrl"):
            raw = im.get(key)
            if not raw or not isinstance(raw, str):
                continue
            abs_u = _absolute_image_url(raw, base_uri)
            if not abs_u:
                continue
            if _is_arr_served_url(abs_u, base_uri):
                return abs_u
    for k in ("remoteCover", "remotePoster", "url"):
        raw = data.get(k)
        if not raw or not isinstance(raw, str):
            continue
        abs_u = _absolute_image_url(raw, base_uri)
        if abs_u and _is_arr_served_url(abs_u, base_uri):
            return abs_u
    return None


def _sniff_mime(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 3 and data[:3] == b"GIF":
        return "image/gif"
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _url_has_apikey_query(url: str) -> bool:
    try:
        q = urlparse(url).query.lower()
    except Exception:
        return False
    return "apikey=" in q


def _thumbnail_request_headers(
    request_url: str,
    *,
    arr_uri: str | None,
    api_key: str | None,
) -> dict[str, str]:
    """Build headers for a single GET. API key is only sent when the URL is the Arr host."""
    h: dict[str, str] = {"User-Agent": "qBitrr/1.0 (WebUI thumbnail)"}
    if (
        arr_uri
        and api_key
        and not _url_has_apikey_query(request_url)
        and _is_arr_served_url(request_url, arr_uri)
    ):
        h["X-Api-Key"] = api_key
    return h


def _read_limited_response_body(r: requests.Response) -> bytes | None:
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


def _http_get_bytes(
    url: str,
    *,
    arr_uri: str | None = None,
    api_key: str | None = None,
) -> bytes | None:
    if not re.match(r"^https?://", url, re.IGNORECASE):
        logger.debug("Skip non-HTTP image URL: %r", url[:80])
        return None
    current = url
    deadline = time.monotonic() + _THUMB_TOTAL_TIMEOUT
    for _ in range(_MAX_THUMB_REDIRECTS + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.debug("Thumbnail fetch exceeded total timeout (%.1fs)", _THUMB_TOTAL_TIMEOUT)
            return None
        # Per-hop timeout is the lesser of the configured per-request value and what's left
        # of the wall-clock budget; never exceeds the cumulative deadline across all hops.
        per_hop_timeout = min(_REQUEST_TIMEOUT, max(remaining, 1.0))
        headers = _thumbnail_request_headers(current, arr_uri=arr_uri, api_key=api_key)
        try:
            with requests.get(
                current,
                stream=True,
                timeout=per_hop_timeout,
                headers=headers,
                allow_redirects=False,
            ) as r:
                if r.is_redirect:
                    loc = r.headers.get("Location")
                    if not loc or not loc.strip():
                        return None
                    next_url = urljoin(r.url, loc.strip())
                    if not re.match(r"^https?://", next_url, re.IGNORECASE):
                        return None
                    if not arr_uri or not _is_arr_served_url(next_url, arr_uri):
                        logger.debug(
                            "Thumbnail redirect to non-Arr host rejected: %r", next_url[:120]
                        )
                        return None
                    current = next_url
                    continue
                r.raise_for_status()
                return _read_limited_response_body(r)
        except Exception as e:
            logger.debug("Thumbnail fetch failed: %s", e, exc_info=True)
            return None
    logger.debug("Thumbnail fetch exceeded max redirects (%s)", _MAX_THUMB_REDIRECTS)
    return None


def _get_entity_dict(client: Any, kind: str, entry_id: int) -> dict[str, Any] | None:
    if kind == "radarr" and hasattr(client, "get_movie"):
        try:
            out = client.get_movie(entry_id, includeLocalCovers=True)
        except TypeError:
            out = client.get_movie(entry_id)
    elif kind == "sonarr" and hasattr(client, "get_series"):
        try:
            out = client.get_series(entry_id, includeLocalCovers=True)
        except TypeError:
            out = client.get_series(entry_id)
    elif kind == "lidarr_artist" and hasattr(client, "get_artist"):
        try:
            out = client.get_artist(entry_id, includeLocalCovers=True)
        except TypeError:
            try:
                out = client.get_artist(entry_id)
            except TypeError:
                out = client.get_artist(id_=entry_id)
    else:
        return None
    return out if isinstance(out, dict) else None


def _resolve_image_url(*, kind: str, arr: Any, entry_id: int) -> str | None:
    client = getattr(arr, "client", None)
    if not client:
        return None
    raw_uri = getattr(arr, "uri", None)
    if not isinstance(raw_uri, str) or not raw_uri.strip():
        return None
    base_uri = raw_uri.strip()
    try:
        data = _get_entity_dict(client, kind, entry_id)
    except Exception:
        logger.debug("Arr API get_* failed for %s %s", kind, entry_id, exc_info=True)
        return None
    if not data:
        return None
    if kind == "lidarr_artist":
        return _first_cover_lidarr(data, base_uri)
    return _first_poster_url_from_radarr_sonarr(data, base_uri)


def _lidarr_artist_mediacovers_candidates(base_uri: str, artist_id: int) -> list[str]:
    """Deterministic same-host URLs under Lidarr's MediaCover API (fallback when JSON has no usable URL)."""

    base = base_uri.rstrip("/")
    rels = (
        f"/api/v1/MediaCover/Artist/{artist_id}/poster.jpg",
        f"/api/v1/MediaCover/Artist/{artist_id}/poster-250.jpg",
        f"/api/v1/MediaCover/Artist/{artist_id}/poster-500.jpg",
        f"/api/v1/MediaCover/Artist/{artist_id}/fanart.jpg",
        f"/api/v1/MediaCover/Artist/{artist_id}/clearlogo.png",
        f"/api/v1/MediaCover/{artist_id}/poster.jpg",
    )
    return [base + r for r in rels]


def _fetch_first_lidarr_artist_mediacovers(arr: Any, artist_id: int) -> bytes | None:
    raw_uri = getattr(arr, "uri", None)
    if not isinstance(raw_uri, str) or not raw_uri.strip():
        return None
    api_key = getattr(arr, "apikey", None)
    base_uri = raw_uri.strip()
    for url in _lidarr_artist_mediacovers_candidates(base_uri, artist_id):
        raw = _http_get_bytes(
            url,
            arr_uri=base_uri,
            api_key=api_key if isinstance(api_key, str) else None,
        )
        if raw:
            return raw
    return None


def get_or_fetch_thumbnail_bytes(
    *, kind: str, instance_name: str, arr: Any, entry_id: int
) -> tuple[bytes, str] | None:
    path = _cache_file_path(kind=kind, instance_name=instance_name, entry_id=entry_id)
    if path.is_file() and path.stat().st_size > 0:
        ep = _cache_etag_path(path)
        if not ep.is_file():
            try:
                digest_hex = sha256_digest_file(path)
                _write_etag_sidecar(path, digest_hex)
            except OSError as e:
                logger.debug("Could not write thumbnail etag (cache hit): %s", e)
        b = path.read_bytes()
        return b, _sniff_mime(b)

    arr_uri = getattr(arr, "uri", None)
    api_key = getattr(arr, "apikey", None)
    arr_uri_s = arr_uri if isinstance(arr_uri, str) else None

    url = _resolve_image_url(kind=kind, arr=arr, entry_id=entry_id)
    raw: bytes | None = None
    if url:
        raw = _http_get_bytes(
            url.strip(),
            arr_uri=arr_uri_s,
            api_key=api_key,
        )
    if not raw and kind == "lidarr_artist":
        raw = _fetch_first_lidarr_artist_mediacovers(arr, entry_id)
    if not raw:
        return None
    mime = _sniff_mime(raw)
    try:
        path.write_bytes(raw)
        dh = sha256_digest_bytes(raw)
        _write_etag_sidecar(path, dh)
    except OSError as e:
        logger.debug("Could not write thumbnail cache: %s", e)
    return raw, mime
