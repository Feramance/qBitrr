from __future__ import annotations

"""Compatibility layer for pyarr v5/v6 API differences."""

from typing import Any
from urllib.parse import urlparse

try:
    # pyarr <= v5
    from pyarr import LidarrAPI as _LegacyLidarrAPI
    from pyarr import RadarrAPI as _LegacyRadarrAPI
    from pyarr import SonarrAPI as _LegacySonarrAPI
except ImportError:  # pragma: no cover - import path only differs by installed pyarr version
    _LegacyLidarrAPI = None
    _LegacyRadarrAPI = None
    _LegacySonarrAPI = None

try:
    # pyarr >= v6
    from pyarr import Lidarr as _Lidarr
    from pyarr import Radarr as _Radarr
    from pyarr import Sonarr as _Sonarr
except ImportError:  # pragma: no cover - import path only differs by installed pyarr version
    _Lidarr = None
    _Radarr = None
    _Sonarr = None

try:
    from pyarr.exceptions import PyarrResourceNotFound, PyarrServerError
except ImportError:  # pragma: no cover
    # Last-resort fallback keeps importers working even if pyarr reshuffles modules.
    class PyarrResourceNotFound(Exception):
        """Fallback pyarr resource-not-found exception type."""

    class PyarrServerError(Exception):
        """Fallback pyarr server-error exception type."""


try:
    from pyarr.exceptions import PyarrConnectionError
except ImportError:  # pragma: no cover

    class PyarrConnectionError(ConnectionError):
        """Placeholder when pyarr does not expose connection errors."""


try:
    from pyarr.types import JsonObject
except ImportError:  # pragma: no cover
    JsonObject = dict[str, Any]


class _CompatArrClient:
    """Adapter that preserves qBitrr's legacy pyarr call surface."""

    def __init__(self, client: Any):
        self._client = client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def _legacy_call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        return getattr(self._client, method)(*args, **kwargs)

    def _has_legacy(self, method: str) -> bool:
        return hasattr(self._client, method)

    def get_update(self) -> Any:
        if self._has_legacy("get_update"):
            return self._legacy_call("get_update")
        return self._client.update.get()

    def get_command(self, item_id: int | None = None) -> Any:
        if self._has_legacy("get_command"):
            if item_id is None:
                return self._legacy_call("get_command")
            return self._legacy_call("get_command", item_id)
        return self._client.command.get(item_id=item_id)

    def post_command(self, command: str, **kwargs: Any) -> Any:
        if self._has_legacy("post_command"):
            return self._legacy_call("post_command", command, **kwargs)
        return self._client.command.execute(command, **kwargs)

    def get_queue(self, **kwargs: Any) -> JsonObject:
        if self._has_legacy("get_queue"):
            return self._legacy_call("get_queue", **kwargs)
        return self._client.queue.get(**kwargs)

    def del_queue(
        self,
        item_id: int,
        remove_from_client: bool | None = None,
        blacklist: bool | None = None,
        **kwargs: Any,
    ) -> Any:
        if self._has_legacy("del_queue"):
            blocklist = kwargs.pop("blocklist", blacklist)
            return self._legacy_call("del_queue", item_id, remove_from_client, blocklist, **kwargs)
        blocklist = kwargs.pop("blocklist", blacklist)
        return self._client.queue.delete(
            item_id=item_id, remove_from_client=remove_from_client, blocklist=blocklist, **kwargs
        )

    def get_system_status(self) -> JsonObject:
        if self._has_legacy("get_system_status"):
            return self._legacy_call("get_system_status")
        return self._client.system.get_status()

    def get_quality_profile(self, item_id: int | None = None) -> Any:
        if self._has_legacy("get_quality_profile"):
            if item_id is None:
                return self._legacy_call("get_quality_profile")
            return self._legacy_call("get_quality_profile", item_id)
        return self._client.quality_profile.get(item_id=item_id)

    def get_series(self, item_id: int | None = None, **kwargs: Any) -> Any:
        if self._has_legacy("get_series"):
            if item_id is None and "id_" in kwargs:
                item_id = kwargs.pop("id_")
            if item_id is None:
                return self._legacy_call("get_series", **kwargs)
            return self._legacy_call("get_series", item_id, **kwargs)
        if item_id is None:
            item_id = kwargs.pop("id_", None)
        return self._client.series.get(item_id=item_id, **kwargs)

    def get_episode(self, item_id: int | None = None, series: bool = False, **kwargs: Any) -> Any:
        if self._has_legacy("get_episode"):
            if item_id is None:
                item_id = kwargs.pop("id_", None)
            if item_id is None:
                return self._legacy_call("get_episode", **kwargs)
            return self._legacy_call("get_episode", item_id, series, **kwargs)
        if item_id is None:
            item_id = kwargs.pop("id_", None)
        if series:
            return self._client.episode.get(series_id=item_id)
        return self._client.episode.get(item_id=item_id, **kwargs)

    def get_episode_file(self, item_id: int | None = None, **kwargs: Any) -> Any:
        if self._has_legacy("get_episode_file"):
            if item_id is None:
                return self._legacy_call("get_episode_file", **kwargs)
            return self._legacy_call("get_episode_file", item_id, **kwargs)
        if item_id is None:
            item_id = kwargs.pop("id_", None)
        return self._client.episode_file.get(item_id=item_id, **kwargs)

    def upd_episode(self, item_id: int, data: JsonObject) -> JsonObject:
        if self._has_legacy("upd_episode"):
            return self._legacy_call("upd_episode", item_id, data)
        return self._client.episode.update(item_id=item_id, data=data)

    def upd_series(self, data: JsonObject) -> JsonObject:
        if self._has_legacy("upd_series"):
            return self._legacy_call("upd_series", data)
        return self._client.series.update(data=data)

    def get_movie(self, item_id: int | None = None, **kwargs: Any) -> Any:
        if self._has_legacy("get_movie"):
            if item_id is None:
                return self._legacy_call("get_movie", **kwargs)
            return self._legacy_call("get_movie", item_id, **kwargs)
        if item_id is None:
            item_id = kwargs.pop("id_", None)
        return self._client.movie.get(item_id=item_id, **kwargs)

    def get_movie_file(self, item_id: int | None = None, **kwargs: Any) -> Any:
        if self._has_legacy("get_movie_file"):
            if item_id is None:
                return self._legacy_call("get_movie_file", **kwargs)
            return self._legacy_call("get_movie_file", item_id, **kwargs)
        if item_id is None:
            item_id = kwargs.pop("id_", None)
        return self._client.movie_file.get(item_id=item_id, **kwargs)

    def upd_movie(self, data: JsonObject, move_files: bool | None = None) -> JsonObject:
        if self._has_legacy("upd_movie"):
            if move_files is None:
                return self._legacy_call("upd_movie", data)
            return self._legacy_call("upd_movie", data, move_files)
        return self._client.movie.update(data=data, move_files=move_files)

    def get_artist(self, item_id: int | None = None, **kwargs: Any) -> Any:
        if self._has_legacy("get_artist"):
            if item_id is None and "id_" in kwargs:
                item_id = kwargs.pop("id_")
            if item_id is None:
                return self._legacy_call("get_artist", **kwargs)
            return self._legacy_call("get_artist", item_id, **kwargs)
        if item_id is None:
            item_id = kwargs.pop("id_", None)
        return self._client.artist.get(item_id=item_id, **kwargs)

    def get_album(self, item_id: int | None = None, **kwargs: Any) -> Any:
        if self._has_legacy("get_album"):
            if item_id is None:
                return self._legacy_call("get_album", **kwargs)
            return self._legacy_call("get_album", item_id, **kwargs)
        if item_id is None:
            item_id = kwargs.pop("id_", None)
        artist_id = kwargs.pop("artistId", kwargs.pop("artist_id", None))
        return self._client.album.get(item_id=item_id, artist_id=artist_id, **kwargs)

    def get_tracks(self, **kwargs: Any) -> Any:
        if self._has_legacy("get_tracks"):
            return self._legacy_call("get_tracks", **kwargs)
        album_id = kwargs.pop("albumId", kwargs.pop("album_id", None))
        artist_id = kwargs.pop("artistId", kwargs.pop("artist_id", None))
        return self._client.track.get(album_id=album_id, artist_id=artist_id, **kwargs)

    def get_track_file(self, item_id: int | None = None, **kwargs: Any) -> Any:
        if self._has_legacy("get_track_file"):
            if item_id is None:
                return self._legacy_call("get_track_file", **kwargs)
            return self._legacy_call("get_track_file", item_id, **kwargs)
        if item_id is not None:
            kwargs["track_file_ids"] = [item_id]
        return self._client.track_file.get(**kwargs)

    def upd_artist(self, data: JsonObject) -> JsonObject:
        if self._has_legacy("upd_artist"):
            return self._legacy_call("upd_artist", data)
        return self._client.artist.update(data=data)


def _normalize_v6_client_args(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    default_port: int,
    *,
    default_api_ver: str | None = None,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Map legacy qBitrr constructor args into pyarr v6 constructor shape."""
    new_args = list(args)
    new_kwargs = dict(kwargs)

    host_url = new_kwargs.pop("host_url", None)
    if host_url and "host" not in new_kwargs:
        new_kwargs["host"] = host_url

    # qBitrr frequently passes a full URL as first positional argument.
    if new_args and isinstance(new_args[0], str) and "host" not in new_kwargs:
        new_kwargs["host"] = new_args.pop(0)
        if new_args and "api_key" not in new_kwargs:
            new_kwargs["api_key"] = new_args.pop(0)

    host_value = new_kwargs.get("host")
    if isinstance(host_value, str):
        parsed = urlparse(host_value)
        if parsed.scheme and parsed.netloc:
            if parsed.hostname:
                new_kwargs["host"] = parsed.hostname
            if "port" not in new_kwargs:
                if parsed.port is not None:
                    new_kwargs["port"] = parsed.port
                else:
                    scheme = parsed.scheme.lower()
                    if scheme == "https":
                        new_kwargs["port"] = 443
                    elif scheme == "http":
                        new_kwargs["port"] = 80
                    else:
                        new_kwargs["port"] = default_port
            if "tls" not in new_kwargs:
                new_kwargs["tls"] = parsed.scheme.lower() == "https"
            if "base_path" not in new_kwargs and parsed.path not in ("", "/"):
                new_kwargs["base_path"] = parsed.path.rstrip("/")

    if "port" not in new_kwargs:
        new_kwargs["port"] = default_port

    if default_api_ver is not None and "api_ver" not in new_kwargs:
        new_kwargs["api_ver"] = default_api_ver

    return tuple(new_args), new_kwargs


class RadarrAPI(_CompatArrClient):
    def __init__(self, *args: Any, **kwargs: Any):
        if _LegacyRadarrAPI is not None:
            super().__init__(_LegacyRadarrAPI(*args, **kwargs))
            return
        if _Radarr is None:
            raise ImportError("pyarr Radarr client not found")
        call_args, call_kwargs = _normalize_v6_client_args(
            args, kwargs, default_port=7878, default_api_ver="v3"
        )
        super().__init__(_Radarr(*call_args, **call_kwargs))


class SonarrAPI(_CompatArrClient):
    def __init__(self, *args: Any, **kwargs: Any):
        if _LegacySonarrAPI is not None:
            super().__init__(_LegacySonarrAPI(*args, **kwargs))
            return
        if _Sonarr is None:
            raise ImportError("pyarr Sonarr client not found")
        call_args, call_kwargs = _normalize_v6_client_args(
            args, kwargs, default_port=8989, default_api_ver="v3"
        )
        super().__init__(_Sonarr(*call_args, **call_kwargs))


class LidarrAPI(_CompatArrClient):
    def __init__(self, *args: Any, **kwargs: Any):
        if _LegacyLidarrAPI is not None:
            super().__init__(_LegacyLidarrAPI(*args, **kwargs))
            return
        if _Lidarr is None:
            raise ImportError("pyarr Lidarr client not found")
        call_args, call_kwargs = _normalize_v6_client_args(
            args, kwargs, default_port=8686, default_api_ver="v1"
        )
        super().__init__(_Lidarr(*call_args, **call_kwargs))


__all__ = [
    "JsonObject",
    "LidarrAPI",
    "PyarrConnectionError",
    "PyarrResourceNotFound",
    "PyarrServerError",
    "RadarrAPI",
    "SonarrAPI",
]
