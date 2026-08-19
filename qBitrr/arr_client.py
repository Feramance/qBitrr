"""qBitrr config-shape adapter for pyarr v6 clients."""

from __future__ import annotations

import inspect
from typing import Any
from urllib.parse import urlparse

from pyarr import Lidarr, Radarr, Readarr, Sonarr
from pyarr.exceptions import (
    PyarrConnectionError,
    PyarrError,
    PyarrResourceNotFound,
    PyarrServerError,
)
from pyarr.types import JsonObject


def build_arr_client_kwargs(
    url: str,
    api_key: str,
    *,
    default_port: int,
    api_ver: str,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """Map qBitrr's single URL string into pyarr v6 constructor kwargs."""
    parsed = urlparse(url)
    kwargs: dict[str, Any] = {"api_key": api_key, "verify_ssl": verify_ssl, "api_ver": api_ver}
    if parsed.scheme and parsed.netloc:
        if parsed.hostname:
            kwargs["host"] = parsed.hostname
        if parsed.port is not None:
            kwargs["port"] = parsed.port
        elif parsed.scheme.lower() == "https":
            kwargs["port"] = 443
        elif parsed.scheme.lower() == "http":
            kwargs["port"] = 80
        else:
            kwargs["port"] = default_port
        kwargs["tls"] = parsed.scheme.lower() == "https"
        if parsed.path not in ("", "/"):
            kwargs["base_path"] = parsed.path.rstrip("/")
    else:
        kwargs["host"] = url
        kwargs["port"] = default_port
    if "host" not in kwargs:
        kwargs["host"] = url
    if "port" not in kwargs:
        kwargs["port"] = default_port
    return kwargs


def build_radarr_client(url: str, api_key: str, *, verify_ssl: bool = True) -> Radarr:
    """Construct a pyarr Radarr client from qBitrr config fields."""
    return Radarr(
        **build_arr_client_kwargs(
            url, api_key, default_port=7878, api_ver="v3", verify_ssl=verify_ssl
        )
    )


def build_sonarr_client(url: str, api_key: str, *, verify_ssl: bool = True) -> Sonarr:
    """Construct a pyarr Sonarr client from qBitrr config fields."""
    return Sonarr(
        **build_arr_client_kwargs(
            url, api_key, default_port=8989, api_ver="v3", verify_ssl=verify_ssl
        )
    )


def build_lidarr_client(url: str, api_key: str, *, verify_ssl: bool = True) -> Lidarr:
    """Construct a pyarr Lidarr client from qBitrr config fields."""
    return Lidarr(
        **build_arr_client_kwargs(
            url, api_key, default_port=8686, api_ver="v1", verify_ssl=verify_ssl
        )
    )


def build_readarr_client(url: str, api_key: str, *, verify_ssl: bool = True) -> Readarr:
    """Construct a pyarr Readarr client from qBitrr config fields."""
    return Readarr(
        **build_arr_client_kwargs(
            url, api_key, default_port=8787, api_ver="v1", verify_ssl=verify_ssl
        )
    )


def get_readarr_book_files(
    client: Any,
    *,
    book_id: int | None = None,
    author_id: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch Readarr book files via raw HTTP (pyarr has no book_file module)."""
    if book_id is None and author_id is None:
        raise ValueError("get_readarr_book_files requires book_id or author_id")
    http_utils = getattr(client, "http_utils", None)
    if http_utils is None or not hasattr(http_utils, "request"):
        raise ValueError("Expected Readarr client with http_utils.request")
    params: dict[str, int] = {}
    if book_id is not None:
        params["bookId"] = book_id
    if author_id is not None:
        params["authorId"] = author_id
    response = http_utils.request("bookfile", params=params)
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if response is None:
        return []
    raise ValueError("Expected a list response from the 'bookfile' endpoint")


def execute_command(client: Any, command: str, **kwargs: Any) -> Any:
    """Run an Arr command, falling back to raw POST when pyarr rejects list responses."""
    try:
        return client.command.execute(command, **kwargs)
    except ValueError as exc:
        if str(exc) != "Expected a dictionary response from the 'command' endpoint":
            raise
        return _raw_command_post(client, command, **kwargs)


def _raw_command_post(client: Any, command: str, **kwargs: Any) -> Any:
    """Direct command POST fallback preserved from legacy pyarr_compat."""
    data: dict[str, Any] = {"name": command}
    if kwargs:
        data |= kwargs
    http_utils = getattr(client, "http_utils", None)
    if http_utils is None or not hasattr(http_utils, "request"):
        raise ValueError("Expected a dictionary response from the 'command' endpoint")
    request = http_utils.request
    request_signature = inspect.signature(request)
    request_kwargs: dict[str, Any] = {}
    if "method" in request_signature.parameters:
        request_kwargs["method"] = "POST"
    if "data" in request_signature.parameters:
        request_kwargs["data"] = data
    elif "json" in request_signature.parameters:
        request_kwargs["json"] = data
    else:
        raise ValueError("pyarr http_utils.request does not accept command payloads")
    return request("command", **request_kwargs)


__all__ = [
    "JsonObject",
    "Lidarr",
    "PyarrConnectionError",
    "PyarrError",
    "PyarrResourceNotFound",
    "PyarrServerError",
    "Radarr",
    "Readarr",
    "Sonarr",
    "build_arr_client_kwargs",
    "build_lidarr_client",
    "build_radarr_client",
    "build_readarr_client",
    "build_sonarr_client",
    "execute_command",
    "get_readarr_book_files",
]
