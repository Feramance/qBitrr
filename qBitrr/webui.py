from __future__ import annotations

import io
import logging
import os
import re
import secrets
import threading
import time
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, request, send_file
from peewee import fn

from qBitrr.arss import FreeSpaceManager, PlaceHolderArr
from qBitrr.bundled_data import patched_version, tagged_version
from qBitrr.config import CONFIG, HOME_PATH
from qBitrr.logger import run_logs
from qBitrr.search_activity_store import (
    clear_search_activity,
    fetch_search_activities,
)
from qBitrr.versioning import fetch_latest_release, fetch_release_by_tag


def _toml_set(doc, dotted_key: str, value: Any):
    from tomlkit import inline_table, table

    keys = dotted_key.split(".")
    cur = doc
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = table()
        cur = cur[k]

    # Convert plain Python dicts to inline tables for proper TOML serialization
    # This ensures dicts are rendered as inline {key = "value"} not as sections [key]
    if isinstance(value, dict) and not hasattr(value, "as_string"):
        inline = inline_table()
        inline.update(value)
        cur[keys[-1]] = inline
    else:
        cur[keys[-1]] = value


def _toml_delete(doc, dotted_key: str) -> None:
    keys = dotted_key.split(".")
    cur = doc
    parents = []
    for k in keys[:-1]:
        next_cur = cur.get(k)
        if not isinstance(next_cur, dict):
            return
        parents.append((cur, k))
        cur = next_cur
    cur.pop(keys[-1], None)
    for parent, key in reversed(parents):
        node = parent.get(key)
        if isinstance(node, dict) and not node:
            parent.pop(key, None)
        else:
            break


def _toml_to_jsonable(obj: Any) -> Any:
    try:
        if hasattr(obj, "unwrap"):
            return _toml_to_jsonable(obj.unwrap())
        if isinstance(obj, dict):
            return {k: _toml_to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_toml_to_jsonable(v) for v in obj]
        return obj
    except Exception:
        return obj


class WebUI:
    def __init__(self, manager, host: str = "0.0.0.0", port: int = 6969):
        self.manager = manager
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.logger = logging.getLogger("qBitrr.WebUI")
        run_logs(self.logger, "WebUI")
        self.logger.info("Initialising WebUI on %s:%s", self.host, self.port)
        if self.host in {"0.0.0.0", "::"}:
            self.logger.warning(
                "WebUI configured to listen on %s. Expose this only behind a trusted reverse proxy.",
                self.host,
            )
        self.app.logger.handlers.clear()
        self.app.logger.propagate = True
        self.app.logger.setLevel(self.logger.level)
        werkzeug_logger = logging.getLogger("werkzeug")
        werkzeug_logger.handlers.clear()
        werkzeug_logger.propagate = True
        werkzeug_logger.setLevel(self.logger.level)

        # Add cache control for static files to support config reload
        @self.app.after_request
        def add_cache_headers(response):
            # Prevent caching of index.html and service worker to ensure fresh config loads
            if request.path in ("/static/index.html", "/ui", "/static/sw.js", "/sw.js"):
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
            return response

        # Security token (optional) - auto-generate and persist if empty
        self.token = CONFIG.get("WebUI.Token", fallback=None)
        if not self.token:
            self.token = secrets.token_hex(32)
            try:
                _toml_set(CONFIG.config, "WebUI.Token", self.token)
                CONFIG.save()
            except Exception:
                pass
            else:
                self.logger.notice("Generated new WebUI token")
        self._github_repo = "Feramance/qBitrr"
        self._version_lock = threading.Lock()
        self._version_cache = {
            "current_version": patched_version,
            "latest_version": None,
            "changelog": "",  # Latest version changelog
            "current_version_changelog": "",  # Current version changelog
            "changelog_url": f"https://github.com/{self._github_repo}/releases",
            "repository_url": f"https://github.com/{self._github_repo}",
            "homepage_url": f"https://github.com/{self._github_repo}",
            "update_available": False,
            "last_checked": None,
            "error": None,
            "installation_type": "unknown",
            "binary_download_url": None,
            "binary_download_name": None,
            "binary_download_size": None,
            "binary_download_error": None,
        }
        self._version_cache_expiry = datetime.utcnow() - timedelta(seconds=1)
        self._update_state = {
            "in_progress": False,
            "last_result": None,
            "last_error": None,
            "completed_at": None,
        }
        self._update_thread: threading.Thread | None = None
        self._rebuilding_arrs = False
        self._register_routes()
        static_root = Path(__file__).with_name("static")
        if not (static_root / "index.html").exists():
            self.logger.warning(
                "WebUI static bundle is missing. Install npm and run "
                "'npm ci && npm run build' inside the 'webui' folder before packaging."
            )
        self._thread: threading.Thread | None = None
        self._use_dev_server: bool | None = None

        # Shutdown control for graceful restart
        self._shutdown_event = threading.Event()
        self._restart_requested = False
        self._server = None  # Will hold Waitress server reference

    def _fetch_version_info(self) -> dict[str, Any]:
        info = fetch_latest_release(self._github_repo)
        if info.get("error"):
            self.logger.debug("Failed to fetch latest release information: %s", info["error"])
            return {"error": info["error"]}
        latest_display = info.get("raw_tag") or info.get("normalized")
        return {
            "latest_version": latest_display,
            "update_available": bool(info.get("update_available")),
            "changelog": info.get("changelog") or "",
            "changelog_url": info.get("changelog_url"),
            "error": None,
        }

    def _fetch_current_version_changelog(self) -> dict[str, Any]:
        """Fetch changelog for the current running version."""
        current_ver = tagged_version
        if not current_ver:
            return {
                "changelog": "",
                "changelog_url": f"https://github.com/{self._github_repo}/releases",
                "error": "No current version",
            }

        info = fetch_release_by_tag(current_ver, self._github_repo)
        if info.get("error"):
            self.logger.debug("Failed to fetch current version changelog: %s", info["error"])
            # Fallback to generic releases page
            return {
                "changelog": "",
                "changelog_url": f"https://github.com/{self._github_repo}/releases",
                "error": info["error"],
            }

        return {
            "changelog": info.get("changelog") or "",
            "changelog_url": info.get("changelog_url")
            or f"https://github.com/{self._github_repo}/releases/tag/v{current_ver}",
            "error": None,
        }

    def _ensure_version_info(self, force: bool = False) -> dict[str, Any]:
        now = datetime.utcnow()
        with self._version_lock:
            if not force and now < self._version_cache_expiry:
                snapshot = dict(self._version_cache)
                snapshot["update_state"] = dict(self._update_state)
                return snapshot
            # optimistic expiry to avoid concurrent fetches
            self._version_cache_expiry = now + timedelta(minutes=5)

        latest_info = self._fetch_version_info()
        current_ver_info = self._fetch_current_version_changelog()

        with self._version_lock:
            if latest_info:
                if latest_info.get("latest_version") is not None:
                    self._version_cache["latest_version"] = latest_info["latest_version"]
                if latest_info.get("changelog") is not None:
                    self._version_cache["changelog"] = latest_info.get("changelog") or ""
                if latest_info.get("changelog_url"):
                    self._version_cache["changelog_url"] = latest_info["changelog_url"]
                if "update_available" in latest_info:
                    self._version_cache["update_available"] = bool(latest_info["update_available"])
                if "error" in latest_info:
                    self._version_cache["error"] = latest_info["error"]
            # Store current version changelog
            if current_ver_info and not current_ver_info.get("error"):
                self._version_cache["current_version_changelog"] = (
                    current_ver_info.get("changelog") or ""
                )

            self._version_cache["current_version"] = patched_version
            self._version_cache["last_checked"] = now.isoformat()

            # Add installation type and binary download info
            from qBitrr.auto_update import get_binary_download_url, get_installation_type

            install_type = get_installation_type()
            self._version_cache["installation_type"] = install_type

            # If binary and update available, get download URL
            if install_type == "binary" and self._version_cache.get("update_available"):
                latest_version = self._version_cache.get("latest_version")
                if latest_version:
                    binary_info = get_binary_download_url(latest_version, self.logger)
                    self._version_cache["binary_download_url"] = binary_info.get("url")
                    self._version_cache["binary_download_name"] = binary_info.get("name")
                    self._version_cache["binary_download_size"] = binary_info.get("size")
                    if binary_info.get("error"):
                        self._version_cache["binary_download_error"] = binary_info["error"]

            # Extend cache validity if fetch succeeded; otherwise allow quick retry.
            if not latest_info or latest_info.get("error"):
                self._version_cache_expiry = now + timedelta(minutes=5)
            else:
                self._version_cache_expiry = now + timedelta(hours=1)
            snapshot = dict(self._version_cache)
            snapshot["update_state"] = dict(self._update_state)
            return snapshot

    def _trigger_manual_update(self) -> tuple[bool, str]:
        with self._version_lock:
            if self._update_state["in_progress"]:
                return False, "An update is already in progress."
            update_thread = threading.Thread(
                target=self._run_manual_update, name="ManualUpdater", daemon=True
            )
            self._update_state["in_progress"] = True
            self._update_state["last_error"] = None
            self._update_state["last_result"] = None
            self._update_thread = update_thread
        update_thread.start()
        return True, "started"

    def _run_manual_update(self) -> None:
        result = "success"
        error_message: str | None = None
        try:
            self.logger.notice("Manual update triggered from WebUI")
            try:
                self.manager._perform_auto_update()
            except AttributeError:
                from qBitrr.auto_update import perform_self_update

                if not perform_self_update(self.manager.logger):
                    raise RuntimeError("pip upgrade did not complete successfully")
                try:
                    self.manager.request_restart()
                except Exception:
                    self.logger.warning(
                        "Update applied but restart request failed; exiting manually."
                    )
        except Exception as exc:
            result = "error"
            error_message = str(exc)
            self.logger.exception("Manual update failed")
        finally:
            completed_at = datetime.utcnow().isoformat()
            with self._version_lock:
                self._update_state.update(
                    {
                        "in_progress": False,
                        "last_result": result,
                        "last_error": error_message,
                        "completed_at": completed_at,
                    }
                )
                self._update_thread = None
                self._version_cache_expiry = datetime.utcnow() - timedelta(seconds=1)
            try:
                self.manager.configure_auto_update()
            except Exception:
                self.logger.exception("Failed to reconfigure auto update after manual update")
            try:
                self._ensure_version_info(force=True)
            except Exception:
                self.logger.debug("Version metadata refresh after update failed", exc_info=True)

    @staticmethod
    def _safe_str(value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    def _ensure_arr_db(self, arr) -> bool:
        if not getattr(arr, "search_setup_completed", False):
            try:
                arr.register_search_mode()
            except Exception:
                return False
        if not getattr(arr, "search_setup_completed", False):
            return False
        if not getattr(arr, "_webui_db_loaded", False):
            try:
                arr.db_update()
                arr._webui_db_loaded = True
            except Exception:
                arr._webui_db_loaded = False
        return True

    @staticmethod
    def _safe_bool(value: Any) -> bool:
        return bool(value) and str(value).lower() not in {"0", "false", "none"}

    def _radarr_movies_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        year_min: int | None = None,
        year_max: int | None = None,
        monitored: bool | None = None,
        has_file: bool | None = None,
        quality_met: bool | None = None,
        is_request: bool | None = None,
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                    "quality_met": 0,
                    "requests": 0,
                },
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "movies": [],
            }
        model = getattr(arr, "model_file", None)
        db = getattr(arr, "db", None)
        if model is None or db is None:
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                    "quality_met": 0,
                    "requests": 0,
                },
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "movies": [],
            }
        page = max(page, 0)
        page_size = max(page_size, 1)
        arr_instance = getattr(arr, "_name", "")
        with db.connection_context():
            # Filter by ArrInstance
            base_query = model.select().where(model.ArrInstance == arr_instance)

            # Calculate counts
            monitored_count = (
                model.select(fn.COUNT(model.EntryId))
                .where(
                    (model.ArrInstance == arr_instance) & (model.Monitored == True)
                )  # noqa: E712
                .scalar()
                or 0
            )
            available_count = (
                model.select(fn.COUNT(model.EntryId))
                .where(
                    (model.ArrInstance == arr_instance)
                    & (model.Monitored == True)  # noqa: E712
                    & (model.MovieFileId.is_null(False))
                    & (model.MovieFileId != 0)
                )
                .scalar()
                or 0
            )
            missing_count = max(monitored_count - available_count, 0)
            quality_met_count = (
                model.select(fn.COUNT(model.EntryId))
                .where(
                    (model.ArrInstance == arr_instance) & (model.QualityMet == True)
                )  # noqa: E712
                .scalar()
                or 0
            )
            request_count = (
                model.select(fn.COUNT(model.EntryId))
                .where(
                    (model.ArrInstance == arr_instance) & (model.IsRequest == True)
                )  # noqa: E712
                .scalar()
                or 0
            )

            # Build filtered query
            query = base_query
            if search:
                query = query.where(model.Title.contains(search))
            if year_min is not None:
                query = query.where(model.Year >= year_min)
            if year_max is not None:
                query = query.where(model.Year <= year_max)
            if monitored is not None:
                query = query.where(model.Monitored == monitored)
            if has_file is not None:
                if has_file:
                    query = query.where(
                        (model.MovieFileId.is_null(False)) & (model.MovieFileId != 0)
                    )
                else:
                    query = query.where(
                        (model.MovieFileId.is_null(True)) | (model.MovieFileId == 0)
                    )
            if quality_met is not None:
                query = query.where(model.QualityMet == quality_met)
            if is_request is not None:
                query = query.where(model.IsRequest == is_request)

            # Total should be ALL items for this instance, not filtered results
            total = base_query.count()
            page_items = query.order_by(model.Title.asc()).paginate(page + 1, page_size).iterator()
            movies = []
            for movie in page_items:
                # Read quality profile from database
                quality_profile_id = (
                    getattr(movie, "QualityProfileId", None)
                    if hasattr(model, "QualityProfileId")
                    else None
                )
                quality_profile_name = (
                    getattr(movie, "QualityProfileName", None)
                    if hasattr(model, "QualityProfileName")
                    else None
                )

                movies.append(
                    {
                        "id": movie.EntryId,
                        "title": movie.Title or "",
                        "year": movie.Year,
                        "monitored": self._safe_bool(movie.Monitored),
                        "hasFile": self._safe_bool(movie.MovieFileId),
                        "qualityMet": self._safe_bool(movie.QualityMet),
                        "isRequest": self._safe_bool(movie.IsRequest),
                        "upgrade": self._safe_bool(movie.Upgrade),
                        "customFormatScore": movie.CustomFormatScore,
                        "minCustomFormatScore": movie.MinCustomFormatScore,
                        "customFormatMet": self._safe_bool(movie.CustomFormatMet),
                        "reason": movie.Reason,
                        "qualityProfileId": quality_profile_id,
                        "qualityProfileName": quality_profile_name,
                    }
                )
        return {
            "counts": {
                "available": available_count,
                "monitored": monitored_count,
                "missing": missing_count,
                "quality_met": quality_met_count,
                "requests": request_count,
            },
            "total": total,
            "page": page,
            "page_size": page_size,
            "movies": movies,
        }

    def _lidarr_albums_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        monitored: bool | None = None,
        has_file: bool | None = None,
        quality_met: bool | None = None,
        is_request: bool | None = None,
        group_by_artist: bool = True,
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                    "quality_met": 0,
                    "requests": 0,
                },
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "albums": [],
            }
        model = getattr(arr, "model_file", None)
        db = getattr(arr, "db", None)
        if model is None or db is None:
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                    "quality_met": 0,
                    "requests": 0,
                },
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "albums": [],
            }
        page = max(page, 0)
        page_size = max(page_size, 1)
        arr_instance = getattr(arr, "_name", "")

        # Quality profiles are now stored in the database
        # No need to fetch from API

        with db.connection_context():
            # Filter by ArrInstance
            base_query = model.select().where(model.ArrInstance == arr_instance)

            # Calculate counts
            monitored_count = (
                model.select(fn.COUNT(model.EntryId))
                .where(
                    (model.ArrInstance == arr_instance) & (model.Monitored == True)
                )  # noqa: E712
                .scalar()
                or 0
            )
            available_count = (
                model.select(fn.COUNT(model.EntryId))
                .where(
                    (model.ArrInstance == arr_instance)
                    & (model.Monitored == True)  # noqa: E712
                    & (model.AlbumFileId.is_null(False))
                    & (model.AlbumFileId != 0)
                )
                .scalar()
                or 0
            )
            missing_count = max(monitored_count - available_count, 0)
            quality_met_count = (
                model.select(fn.COUNT(model.EntryId))
                .where(
                    (model.ArrInstance == arr_instance) & (model.QualityMet == True)
                )  # noqa: E712
                .scalar()
                or 0
            )
            request_count = (
                model.select(fn.COUNT(model.EntryId))
                .where(
                    (model.ArrInstance == arr_instance) & (model.IsRequest == True)
                )  # noqa: E712
                .scalar()
                or 0
            )

            # Build filtered query
            query = base_query
            if search:
                query = query.where(model.Title.contains(search))
            if monitored is not None:
                query = query.where(model.Monitored == monitored)
            if has_file is not None:
                if has_file:
                    query = query.where(
                        (model.AlbumFileId.is_null(False)) & (model.AlbumFileId != 0)
                    )
                else:
                    query = query.where(
                        (model.AlbumFileId.is_null(True)) | (model.AlbumFileId == 0)
                    )
            if quality_met is not None:
                query = query.where(model.QualityMet == quality_met)
            if is_request is not None:
                query = query.where(model.IsRequest == is_request)

            albums = []

            # Total should be ALL albums for this instance, not filtered results
            total = base_query.count()

            if group_by_artist:
                # Paginate by artists: Two-pass approach with Peewee
                # First, get all distinct artist names from the filtered query
                # Use a subquery to get distinct artists efficiently
                artists_subquery = (
                    query.select(model.ArtistTitle).distinct().order_by(model.ArtistTitle)
                )

                # Convert to list to avoid multiple iterations
                all_artists = [row.ArtistTitle for row in artists_subquery]
                len(all_artists)

                # Paginate the artist list in Python
                start_idx = page * page_size
                end_idx = start_idx + page_size
                paginated_artists = all_artists[start_idx:end_idx]

                # Fetch all albums for these paginated artists
                if paginated_artists:
                    album_results = list(
                        query.where(model.ArtistTitle.in_(paginated_artists)).order_by(
                            model.ArtistTitle, model.ReleaseDate
                        )
                    )
                else:
                    album_results = []
            else:
                # Flat mode: paginate by albums as before
                # Note: total is already set to base_query.count() above
                album_results = list(query.order_by(model.Title).paginate(page + 1, page_size))

            for album in album_results:
                # Always fetch tracks from database (Lidarr only)
                track_model = getattr(arr, "track_file_model", None)
                tracks_list = []
                track_monitored_count = 0
                track_available_count = 0

                if track_model:
                    try:
                        # Query tracks from database for this album
                        track_query = (
                            track_model.select()
                            .where(track_model.AlbumId == album.EntryId)
                            .order_by(track_model.TrackNumber)
                        )
                        track_count = track_query.count()
                        self.logger.debug(
                            f"Album {album.EntryId} ({album.Title}): Found {track_count} tracks in database"
                        )

                        for track in track_query:
                            is_monitored = self._safe_bool(track.Monitored)
                            has_file = self._safe_bool(track.HasFile)

                            if is_monitored:
                                track_monitored_count += 1
                            if has_file:
                                track_available_count += 1

                            tracks_list.append(
                                {
                                    "id": track.EntryId,
                                    "trackNumber": track.TrackNumber,
                                    "title": track.Title,
                                    "duration": track.Duration,
                                    "hasFile": has_file,
                                    "trackFileId": track.TrackFileId,
                                    "monitored": is_monitored,
                                }
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to fetch tracks for album {album.EntryId} ({album.Title}): {e}"
                        )

                track_missing_count = max(track_monitored_count - track_available_count, 0)

                # Get quality profile from database model
                quality_profile_id = getattr(album, "QualityProfileId", None)
                quality_profile_name = getattr(album, "QualityProfileName", None)

                # Build album data in Sonarr-like structure
                album_item = {
                    "album": {
                        "id": album.EntryId,
                        "title": album.Title,
                        "artistId": album.ArtistId,
                        "artistName": album.ArtistTitle,
                        "monitored": self._safe_bool(album.Monitored),
                        "hasFile": bool(album.AlbumFileId and album.AlbumFileId != 0),
                        "foreignAlbumId": album.ForeignAlbumId,
                        "releaseDate": (
                            album.ReleaseDate.isoformat()
                            if album.ReleaseDate and hasattr(album.ReleaseDate, "isoformat")
                            else album.ReleaseDate if isinstance(album.ReleaseDate, str) else None
                        ),
                        "qualityMet": self._safe_bool(album.QualityMet),
                        "isRequest": self._safe_bool(album.IsRequest),
                        "upgrade": self._safe_bool(album.Upgrade),
                        "customFormatScore": album.CustomFormatScore,
                        "minCustomFormatScore": album.MinCustomFormatScore,
                        "customFormatMet": self._safe_bool(album.CustomFormatMet),
                        "reason": album.Reason,
                        "qualityProfileId": quality_profile_id,
                        "qualityProfileName": quality_profile_name,
                    },
                    "totals": {
                        "available": track_available_count,
                        "monitored": track_monitored_count,
                        "missing": track_missing_count,
                    },
                    "tracks": tracks_list,
                }

                albums.append(album_item)
        return {
            "counts": {
                "available": available_count,
                "monitored": monitored_count,
                "missing": missing_count,
                "quality_met": quality_met_count,
                "requests": request_count,
            },
            "total": total,
            "page": page,
            "page_size": page_size,
            "albums": albums,
        }

    def _lidarr_tracks_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        monitored: bool | None = None,
        has_file: bool | None = None,
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                },
                "total": 0,
                "page": page,
                "page_size": page_size,
                "tracks": [],
            }

        track_model = getattr(arr, "track_file_model", None)
        album_model = getattr(arr, "model_file", None)

        if not track_model or not album_model:
            return {
                "counts": {
                    "available": 0,
                    "monitored": 0,
                    "missing": 0,
                },
                "total": 0,
                "page": page,
                "page_size": page_size,
                "tracks": [],
            }

        arr_instance = getattr(arr, "_name", "")

        try:
            # Join tracks with albums to get artist/album info
            # Filter by ArrInstance on both models
            query = (
                track_model.select(
                    track_model,
                    album_model.Title.alias("AlbumTitle"),
                    album_model.ArtistTitle,
                    album_model.ArtistId,
                )
                .join(album_model, on=(track_model.AlbumId == album_model.EntryId))
                .where(
                    (track_model.ArrInstance == arr_instance)
                    & (album_model.ArrInstance == arr_instance)
                )
            )

            # Apply filters
            if monitored is not None:
                query = query.where(track_model.Monitored == monitored)
            if has_file is not None:
                query = query.where(track_model.HasFile == has_file)
            if search:
                query = query.where(
                    (track_model.Title.contains(search))
                    | (album_model.Title.contains(search))
                    | (album_model.ArtistTitle.contains(search))
                )

            # Get counts with ArrInstance filter
            available_count = (
                track_model.select()
                .join(album_model, on=(track_model.AlbumId == album_model.EntryId))
                .where(
                    (track_model.ArrInstance == arr_instance)
                    & (album_model.ArrInstance == arr_instance)
                    & (track_model.HasFile == True)
                )
                .count()
            )
            monitored_count = (
                track_model.select()
                .join(album_model, on=(track_model.AlbumId == album_model.EntryId))
                .where(
                    (track_model.ArrInstance == arr_instance)
                    & (album_model.ArrInstance == arr_instance)
                    & (track_model.Monitored == True)
                )
                .count()
            )
            missing_count = (
                track_model.select()
                .join(album_model, on=(track_model.AlbumId == album_model.EntryId))
                .where(track_model.HasFile == False)
                .count()
            )

            total = query.count()

            # Apply pagination
            query = query.order_by(
                album_model.ArtistTitle, album_model.Title, track_model.TrackNumber
            ).paginate(page + 1, page_size)

            tracks = []
            for track in query:
                tracks.append(
                    {
                        "id": track.EntryId,
                        "trackNumber": track.TrackNumber,
                        "title": track.Title,
                        "duration": track.Duration,
                        "hasFile": track.HasFile,
                        "trackFileId": track.TrackFileId,
                        "monitored": track.Monitored,
                        "albumId": track.AlbumId,
                        "albumTitle": track.AlbumTitle,
                        "artistTitle": track.ArtistTitle,
                        "artistId": track.ArtistId,
                    }
                )

            return {
                "counts": {
                    "available": available_count,
                    "monitored": monitored_count,
                    "missing": missing_count,
                },
                "total": total,
                "page": page,
                "page_size": page_size,
                "tracks": tracks,
            }
        except Exception as e:
            self.logger.error(f"Error fetching Lidarr tracks: {e}")
            return {
                "counts": {"available": 0, "monitored": 0, "missing": 0},
                "total": 0,
                "page": page,
                "page_size": page_size,
                "tracks": [],
            }

    def _sonarr_series_from_db(
        self,
        arr,
        search: str | None,
        page: int,
        page_size: int,
        *,
        missing_only: bool = False,
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return {
                "counts": {"available": 0, "monitored": 0, "missing": 0},
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "series": [],
            }
        episodes_model = getattr(arr, "model_file", None)
        series_model = getattr(arr, "series_file_model", None)
        db = getattr(arr, "db", None)
        if episodes_model is None or db is None:
            return {
                "counts": {"available": 0, "monitored": 0, "missing": 0},
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "series": [],
            }
        page = max(page, 0)
        page_size = max(page_size, 1)
        resolved_page = page
        arr_instance = getattr(arr, "_name", "")
        missing_condition = episodes_model.EpisodeFileId.is_null(True) | (
            episodes_model.EpisodeFileId == 0
        )

        with db.connection_context():
            monitored_count = (
                episodes_model.select(fn.COUNT(episodes_model.EntryId))
                .where(
                    (episodes_model.ArrInstance == arr_instance)
                    & (episodes_model.Monitored == True)  # noqa: E712
                )
                .scalar()
                or 0
            )
            available_count = (
                episodes_model.select(fn.COUNT(episodes_model.EntryId))
                .where(
                    (episodes_model.ArrInstance == arr_instance)
                    & (episodes_model.Monitored == True)  # noqa: E712
                    & (episodes_model.EpisodeFileId.is_null(False))
                    & (episodes_model.EpisodeFileId != 0)
                )
                .scalar()
                or 0
            )
            missing_count = max(monitored_count - available_count, 0)
            missing_series_ids: list[int] = []
            if missing_only:
                missing_series_ids = [
                    row.SeriesId
                    for row in episodes_model.select(episodes_model.SeriesId)
                    .where(
                        (episodes_model.ArrInstance == arr_instance)
                        & (episodes_model.Monitored == True)  # noqa: E712
                        & missing_condition
                    )
                    .distinct()
                    if getattr(row, "SeriesId", None) is not None
                ]
                if not missing_series_ids:
                    return {
                        "counts": {
                            "available": available_count,
                            "monitored": monitored_count,
                            "missing": missing_count,
                        },
                        "total": 0,
                        "page": resolved_page,
                        "page_size": page_size,
                        "series": [],
                    }
            payload: list[dict[str, Any]] = []
            total_series = 0

            if series_model is not None:
                # Base query for ALL series in this instance (unfiltered)
                base_series_query = series_model.select().where(
                    series_model.ArrInstance == arr_instance
                )
                # Total should be ALL series for this instance, not filtered results
                total_series = base_series_query.count()

                # Now build the filtered query for pagination
                series_query = base_series_query
                if search:
                    series_query = series_query.where(series_model.Title.contains(search))
                if missing_only and missing_series_ids:
                    series_query = series_query.where(series_model.EntryId.in_(missing_series_ids))
                filtered_series_count = series_query.count()
                if filtered_series_count:
                    max_pages = (filtered_series_count + page_size - 1) // page_size
                    if max_pages:
                        resolved_page = min(resolved_page, max_pages - 1)
                    resolved_page = max(resolved_page, 0)
                    series_rows = (
                        series_query.order_by(series_model.Title.asc())
                        .paginate(resolved_page + 1, page_size)
                        .iterator()
                    )
                    for series in series_rows:
                        episodes_query = episodes_model.select().where(
                            (episodes_model.ArrInstance == arr_instance)
                            & (episodes_model.SeriesId == series.EntryId)
                        )
                        if missing_only:
                            episodes_query = episodes_query.where(missing_condition)
                        episodes_query = episodes_query.order_by(
                            episodes_model.SeasonNumber.asc(),
                            episodes_model.EpisodeNumber.asc(),
                        )
                        episodes = episodes_query.iterator()
                        episodes_list = list(episodes)
                        self.logger.debug(
                            f"[Sonarr Series] Series {getattr(series, 'Title', 'unknown')} (ID {getattr(series, 'EntryId', '?')}) has {len(episodes_list)} episodes (missing_only={missing_only})"
                        )
                        seasons: dict[str, dict[str, Any]] = {}
                        series_monitored = 0
                        series_available = 0
                        for ep in episodes_list:
                            season_value = getattr(ep, "SeasonNumber", None)
                            season_key = (
                                str(season_value) if season_value is not None else "unknown"
                            )
                            season_bucket = seasons.setdefault(
                                season_key,
                                {"monitored": 0, "available": 0, "episodes": []},
                            )
                            is_monitored = self._safe_bool(getattr(ep, "Monitored", None))
                            has_file = self._safe_bool(getattr(ep, "EpisodeFileId", None))
                            if is_monitored:
                                season_bucket["monitored"] += 1
                                series_monitored += 1
                            if has_file:
                                season_bucket["available"] += 1
                                if is_monitored:
                                    series_available += 1
                            air_date = getattr(ep, "AirDateUtc", None)
                            if hasattr(air_date, "isoformat"):
                                try:
                                    air_value = air_date.isoformat()
                                except Exception:
                                    air_value = str(air_date)
                            elif isinstance(air_date, str):
                                air_value = air_date
                            else:
                                air_value = ""
                            if (not missing_only) or (not has_file):
                                season_bucket["episodes"].append(
                                    {
                                        "episodeNumber": getattr(ep, "EpisodeNumber", None),
                                        "title": getattr(ep, "Title", "") or "",
                                        "monitored": is_monitored,
                                        "hasFile": has_file,
                                        "airDateUtc": air_value,
                                        "reason": getattr(ep, "Reason", None),
                                    }
                                )
                        for bucket in seasons.values():
                            monitored_eps = int(bucket.get("monitored", 0) or 0)
                            available_eps = int(bucket.get("available", 0) or 0)
                            bucket["missing"] = max(
                                monitored_eps - min(available_eps, monitored_eps), 0
                            )
                        series_missing = max(series_monitored - series_available, 0)
                        if missing_only:
                            seasons = {
                                key: data for key, data in seasons.items() if data["episodes"]
                            }
                            if not seasons:
                                continue

                        # Get quality profile for this series from database
                        series_id = getattr(series, "EntryId", None)
                        quality_profile_id = (
                            getattr(series, "QualityProfileId", None)
                            if hasattr(series_model, "QualityProfileId")
                            else None
                        )
                        quality_profile_name = (
                            getattr(series, "QualityProfileName", None)
                            if hasattr(series_model, "QualityProfileName")
                            else None
                        )

                        payload.append(
                            {
                                "series": {
                                    "id": series_id,
                                    "title": getattr(series, "Title", "") or "",
                                    "qualityProfileId": quality_profile_id,
                                    "qualityProfileName": quality_profile_name,
                                },
                                "totals": {
                                    "available": series_available,
                                    "monitored": series_monitored,
                                    "missing": series_missing,
                                },
                                "seasons": seasons,
                            }
                        )

            if not payload:
                # Fallback: construct series payload from episode data (episode mode)
                base_episode_query = episodes_model.select().where(
                    episodes_model.ArrInstance == arr_instance
                )
                if search:
                    search_filters = []
                    if hasattr(episodes_model, "SeriesTitle"):
                        search_filters.append(episodes_model.SeriesTitle.contains(search))
                    search_filters.append(episodes_model.Title.contains(search))
                    expr = search_filters[0]
                    for extra in search_filters[1:]:
                        expr |= extra
                    base_episode_query = base_episode_query.where(expr)
                if missing_only:
                    base_episode_query = base_episode_query.where(missing_condition)

                series_id_field = (
                    getattr(episodes_model, "SeriesId", None)
                    if hasattr(episodes_model, "SeriesId")
                    else None
                )
                series_title_field = (
                    getattr(episodes_model, "SeriesTitle", None)
                    if hasattr(episodes_model, "SeriesTitle")
                    else None
                )

                distinct_fields = []
                field_names: list[str] = []
                if series_id_field is not None:
                    distinct_fields.append(series_id_field)
                    field_names.append("SeriesId")
                if series_title_field is not None:
                    distinct_fields.append(series_title_field)
                    field_names.append("SeriesTitle")
                if not distinct_fields:
                    # Fall back to title only to avoid empty select
                    distinct_fields.append(episodes_model.Title.alias("SeriesTitle"))
                    field_names.append("SeriesTitle")

                distinct_query = (
                    base_episode_query.select(*distinct_fields)
                    .distinct()
                    .order_by(
                        series_title_field.asc()
                        if series_title_field is not None
                        else episodes_model.Title.asc()
                    )
                )
                series_key_rows = list(distinct_query.tuples())
                total_series = len(series_key_rows)
                if total_series:
                    max_pages = (total_series + page_size - 1) // page_size
                    resolved_page = min(resolved_page, max_pages - 1)
                    resolved_page = max(resolved_page, 0)
                    start = resolved_page * page_size
                    end = start + page_size
                    page_keys = series_key_rows[start:end]
                else:
                    resolved_page = 0
                    page_keys = []

                payload = []
                for key in page_keys:
                    key_data = dict(zip(field_names, key))
                    series_id = key_data.get("SeriesId")
                    series_title = key_data.get("SeriesTitle")
                    episode_conditions = []
                    if series_id is not None:
                        episode_conditions.append(episodes_model.SeriesId == series_id)
                    if series_title is not None:
                        episode_conditions.append(episodes_model.SeriesTitle == series_title)
                    episodes_query = episodes_model.select().where(
                        episodes_model.ArrInstance == arr_instance
                    )
                    if episode_conditions:
                        condition = episode_conditions[0]
                        for extra in episode_conditions[1:]:
                            condition &= extra
                        episodes_query = episodes_query.where(condition)
                    if missing_only:
                        episodes_query = episodes_query.where(missing_condition)
                    episodes_query = episodes_query.order_by(
                        episodes_model.SeasonNumber.asc(),
                        episodes_model.EpisodeNumber.asc(),
                    )
                    seasons: dict[str, dict[str, Any]] = {}
                    series_monitored = 0
                    series_available = 0
                    # Track quality profile from first episode (all episodes in a series share the same profile)
                    quality_profile_id = None
                    quality_profile_name = None
                    for ep in episodes_query.iterator():
                        # Capture quality profile from first episode if available
                        if quality_profile_id is None and hasattr(ep, "QualityProfileId"):
                            quality_profile_id = getattr(ep, "QualityProfileId", None)
                        if quality_profile_name is None and hasattr(ep, "QualityProfileName"):
                            quality_profile_name = getattr(ep, "QualityProfileName", None)
                        season_value = getattr(ep, "SeasonNumber", None)
                        season_key = str(season_value) if season_value is not None else "unknown"
                        season_bucket = seasons.setdefault(
                            season_key,
                            {"monitored": 0, "available": 0, "episodes": []},
                        )
                        is_monitored = self._safe_bool(getattr(ep, "Monitored", None))
                        has_file = self._safe_bool(getattr(ep, "EpisodeFileId", None))
                        if is_monitored:
                            season_bucket["monitored"] += 1
                            series_monitored += 1
                        if has_file:
                            season_bucket["available"] += 1
                            if is_monitored:
                                series_available += 1
                        air_date = getattr(ep, "AirDateUtc", None)
                        if hasattr(air_date, "isoformat"):
                            try:
                                air_value = air_date.isoformat()
                            except Exception:
                                air_value = str(air_date)
                        elif isinstance(air_date, str):
                            air_value = air_date
                        else:
                            air_value = ""
                        season_bucket["episodes"].append(
                            {
                                "episodeNumber": getattr(ep, "EpisodeNumber", None),
                                "title": getattr(ep, "Title", "") or "",
                                "monitored": is_monitored,
                                "hasFile": has_file,
                                "airDateUtc": air_value,
                                "reason": getattr(ep, "Reason", None),
                            }
                        )
                    for bucket in seasons.values():
                        monitored_eps = int(bucket.get("monitored", 0) or 0)
                        available_eps = int(bucket.get("available", 0) or 0)
                        bucket["missing"] = max(
                            monitored_eps - min(available_eps, monitored_eps), 0
                        )
                    series_missing = max(series_monitored - series_available, 0)
                    if missing_only:
                        seasons = {key: data for key, data in seasons.items() if data["episodes"]}
                        if not seasons:
                            continue

                    # If quality profile is still None, fetch from Sonarr API
                    if quality_profile_id is None and series_id is not None:
                        try:
                            client = getattr(arr, "client", None)
                            if client and hasattr(client, "get_series"):
                                series_data = client.get_series(series_id)
                                if series_data:
                                    quality_profile_id = series_data.get("qualityProfileId")
                                    # Get quality profile name from cache or API
                                    if quality_profile_id:
                                        quality_cache = getattr(arr, "_quality_profile_cache", {})
                                        if quality_profile_id in quality_cache:
                                            quality_profile_name = quality_cache[
                                                quality_profile_id
                                            ].get("name")
                                        elif hasattr(client, "get_quality_profile"):
                                            try:
                                                profile = client.get_quality_profile(
                                                    quality_profile_id
                                                )
                                                quality_profile_name = (
                                                    profile.get("name") if profile else None
                                                )
                                            except Exception:
                                                pass
                        except Exception:
                            pass

                    payload.append(
                        {
                            "series": {
                                "id": series_id,
                                "title": (
                                    series_title
                                    or (
                                        f"Series {len(payload) + 1}"
                                        if series_id is None
                                        else str(series_id)
                                    )
                                ),
                                "qualityProfileId": quality_profile_id,
                                "qualityProfileName": quality_profile_name,
                            },
                            "totals": {
                                "available": series_available,
                                "monitored": series_monitored,
                                "missing": series_missing,
                            },
                            "seasons": seasons,
                        }
                    )

            result = {
                "counts": {
                    "available": available_count,
                    "monitored": monitored_count,
                    "missing": missing_count,
                },
                "total": total_series,
                "page": resolved_page,
                "page_size": page_size,
                "series": payload,
            }
            if payload:
                first_series = payload[0]
                first_seasons = first_series.get("seasons", {})
                total_episodes_in_response = sum(
                    len(season.get("episodes", [])) for season in first_seasons.values()
                )
                self.logger.info(
                    f"[Sonarr API] Returning {len(payload)} series, "
                    f"first series '{first_series.get('series', {}).get('title', '?')}' has "
                    f"{len(first_seasons)} seasons, {total_episodes_in_response} episodes "
                    f"(missing_only={missing_only})"
                )
            return result

    # Routes
    def _register_routes(self):
        app = self.app
        logs_root = (HOME_PATH / "logs").resolve()

        def _resolve_log_file(name: str) -> Path | None:
            try:
                candidate = (logs_root / name).resolve(strict=False)
            except Exception:
                return None
            try:
                candidate.relative_to(logs_root)
            except ValueError:
                return None
            return candidate

        def _managed_objects() -> dict[str, Any]:
            arr_manager = getattr(self.manager, "arr_manager", None)
            return getattr(arr_manager, "managed_objects", {}) if arr_manager else {}

        def _ensure_arr_manager_ready() -> bool:
            return getattr(self.manager, "arr_manager", None) is not None

        @app.get("/health")
        def health():
            return jsonify({"status": "ok"})

        @app.get("/")
        def index():
            return redirect("/ui")

        def _authorized():
            if not self.token:
                return True
            supplied = request.headers.get("Authorization", "").removeprefix(
                "Bearer "
            ) or request.args.get("token")
            return supplied == self.token

        def require_token():
            if not _authorized():
                return jsonify({"error": "unauthorized"}), 401
            return None

        @app.get("/ui")
        def ui_index():
            # Serve UI without requiring a token; API remains protected
            # Add cache-busting parameter based on config reload timestamp
            from flask import make_response

            response = make_response(redirect("/static/index.html"))
            # Prevent caching of the UI entry point
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

        @app.get("/sw.js")
        def service_worker():
            # Service worker must be served directly (not redirected) for PWA support
            # This allows the endpoint to be whitelisted in auth proxies (e.g., Authentik)
            import os

            from flask import send_from_directory

            static_dir = os.path.join(os.path.dirname(__file__), "static")
            response = send_from_directory(static_dir, "sw.js")
            # Prevent caching of the service worker to ensure updates are picked up
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

        def _processes_payload() -> dict[str, Any]:
            procs = []
            search_activity_map = fetch_search_activities()

            def _parse_timestamp(raw_value):
                if not raw_value:
                    return None
                try:
                    if isinstance(raw_value, (int, float)):
                        return datetime.fromtimestamp(raw_value, timezone.utc).isoformat()
                    if isinstance(raw_value, str):
                        trimmed = raw_value.rstrip("Z")
                        dt = datetime.fromisoformat(trimmed)
                        if raw_value.endswith("Z"):
                            dt = dt.replace(tzinfo=timezone.utc)
                        elif dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        return dt.astimezone(timezone.utc).isoformat()
                except Exception:
                    return None
                return None

            def _format_queue_summary(arr_obj, record):
                if not isinstance(record, dict):
                    return None
                pieces = []
                arr_type = (getattr(arr_obj, "type", "") or "").lower()
                if arr_type == "radarr":
                    movie_info = record.get("movie") or {}
                    title = movie_info.get("title")
                    year = movie_info.get("year")
                    release_title = record.get("title") or ""
                    release_name = ""
                    release_year = None
                    if release_title:
                        cleaned = release_title.split("/")[-1]
                        cleaned = re.sub(r"\.[^.]+$", "", cleaned)
                        cleaned = re.sub(r"[-_.]+", " ", cleaned).strip()
                        release_name = cleaned
                        match = re.match(
                            r"(?P<name>.+?)\s+(?P<year>(?:19|20)\d{2})(?:\s|$)",
                            cleaned,
                        )
                        if match:
                            extracted_name = (match.group("name") or "").strip(" .-_")
                            if extracted_name:
                                release_name = re.sub(r"[-_.]+", " ", extracted_name).strip()
                            release_year = match.group("year")
                    if not title and release_name:
                        title = release_name
                    elif title and release_title and title == release_title and release_name:
                        title = release_name
                    if not year:
                        year = release_year or record.get("year")
                    if title:
                        pieces.append(title)
                    if year:
                        pieces.append(str(year))
                elif arr_type == "sonarr":
                    series = (record.get("series") or {}).get("title")
                    episode = record.get("episode")
                    if series:
                        pieces.append(series)
                    season = None
                    episode_number = None
                    if isinstance(episode, dict):
                        season = episode.get("seasonNumber")
                        episode_number = episode.get("episodeNumber")
                    if season is not None and episode_number is not None:
                        pieces.append(f"S{int(season):02d}E{int(episode_number):02d}")
                    # Intentionally omit individual episode titles/status values
                else:
                    title = record.get("title")
                    if title:
                        pieces.append(title)
                cleaned = [str(part) for part in pieces if part]
                return " | ".join(cleaned) if cleaned else None

            def _collect_metrics(arr_obj):
                metrics = {
                    "queue": None,
                    "category": None,
                    "summary": None,
                    "timestamp": None,
                    "metric_type": None,
                }
                manager_ref = getattr(arr_obj, "manager", None)
                if manager_ref and hasattr(manager_ref, "qbit_manager"):
                    qbit_manager = manager_ref.qbit_manager
                else:
                    qbit_manager = getattr(self.manager, "qbit_manager", self.manager)
                qbit_client = getattr(qbit_manager, "client", None)
                category = getattr(arr_obj, "category", None)

                if isinstance(arr_obj, FreeSpaceManager):
                    metrics["metric_type"] = "free-space"
                    if qbit_client:
                        try:
                            torrents = qbit_client.torrents_info(status_filter="all")
                            count = 0
                            for torrent in torrents:
                                tags = getattr(torrent, "tags", "") or ""
                                if "qBitrr-free_space_paused" in str(tags):
                                    count += 1
                            metrics["category"] = count
                            metrics["queue"] = count
                        except Exception:
                            pass
                    return metrics

                if isinstance(arr_obj, PlaceHolderArr):
                    metrics["metric_type"] = "category"
                    if qbit_client and category:
                        try:
                            torrents = qbit_client.torrents_info(
                                status_filter="all", category=category
                            )
                            count = sum(
                                1
                                for torrent in torrents
                                if getattr(torrent, "category", None) == category
                            )
                            metrics["queue"] = count
                            metrics["category"] = count
                        except Exception:
                            pass
                    return metrics

                # Standard Arr (Radarr/Sonarr)
                records = []
                client = getattr(arr_obj, "client", None)
                if client is not None:
                    try:
                        raw_queue = arr_obj.get_queue(
                            page=1, page_size=50, sort_direction="descending"
                        )
                        if isinstance(raw_queue, dict):
                            records = raw_queue.get("records", []) or []
                        else:
                            records = list(raw_queue or [])
                    except Exception:
                        records = []
                queue_count = len(records)
                if queue_count:
                    metrics["queue"] = queue_count
                    records[0]
                if qbit_client and category:
                    try:
                        torrents = qbit_client.torrents_info(
                            status_filter="all", category=category
                        )
                        metrics["category"] = sum(
                            1
                            for torrent in torrents
                            if getattr(torrent, "category", None) == category
                        )
                    except Exception:
                        pass
                category_key = getattr(arr_obj, "category", None)
                if category_key:
                    entry = search_activity_map.get(str(category_key))
                    if isinstance(entry, Mapping):
                        summary = entry.get("summary")
                        timestamp = entry.get("timestamp")
                        if summary:
                            metrics["summary"] = summary
                        if timestamp:
                            metrics["timestamp"] = timestamp
                if metrics["summary"] is None and not getattr(arr_obj, "_webui_db_loaded", True):
                    metrics["summary"] = "Updating database"
                return metrics

            metrics_cache: dict[int, dict[str, object]] = {}

            def _populate_process_metadata(arr_obj, proc_kind, payload_dict):
                metrics = metrics_cache.get(id(arr_obj))
                if metrics is None:
                    metrics = _collect_metrics(arr_obj)
                metrics_cache[id(arr_obj)] = metrics
                if proc_kind == "search":
                    category_key = getattr(arr_obj, "category", None)
                    entry = None
                    if category_key:
                        entry = search_activity_map.get(str(category_key))
                    summary = None
                    timestamp = None
                    if isinstance(entry, Mapping):
                        summary = entry.get("summary")
                        timestamp = entry.get("timestamp")
                    if summary is None:
                        summary = getattr(arr_obj, "last_search_description", None)
                        timestamp = getattr(arr_obj, "last_search_timestamp", None)
                    if summary is None:
                        metrics_summary = metrics.get("summary")
                        if metrics_summary:
                            summary = metrics_summary
                            metrics_timestamp = metrics.get("timestamp")
                            if metrics_timestamp:
                                timestamp = metrics_timestamp
                    if summary:
                        payload_dict["searchSummary"] = summary
                        if timestamp:
                            if isinstance(timestamp, datetime):
                                payload_dict["searchTimestamp"] = timestamp.astimezone(
                                    timezone.utc
                                ).isoformat()
                            else:
                                payload_dict["searchTimestamp"] = str(timestamp)
                    elif category_key:
                        key = str(category_key)
                        clear_search_activity(key)
                        search_activity_map.pop(key, None)
                elif proc_kind == "torrent":
                    queue_count = metrics.get("queue")
                    if queue_count is None:
                        queue_count = getattr(arr_obj, "queue_active_count", None)
                    category_count = metrics.get("category")
                    if category_count is None:
                        category_count = getattr(arr_obj, "category_torrent_count", None)
                    metric_type = metrics.get("metric_type")
                    if queue_count is not None:
                        payload_dict["queueCount"] = queue_count
                    if category_count is not None:
                        payload_dict["categoryCount"] = category_count
                    if metric_type:
                        payload_dict["metricType"] = metric_type

            for arr in _managed_objects().values():
                name = getattr(arr, "_name", "unknown")
                cat = getattr(arr, "category", name)
                for kind in ("search", "torrent"):
                    p = getattr(arr, f"process_{kind}_loop", None)
                    if p is None:
                        continue
                    try:
                        payload = {
                            "category": cat,
                            "name": name,
                            "kind": kind,
                            "pid": getattr(p, "pid", None),
                            "alive": bool(p.is_alive()),
                            "rebuilding": self._rebuilding_arrs,
                        }
                        _populate_process_metadata(arr, kind, payload)
                        procs.append(payload)
                    except Exception:
                        payload = {
                            "category": cat,
                            "name": name,
                            "kind": kind,
                            "pid": getattr(p, "pid", None),
                            "alive": False,
                            "rebuilding": self._rebuilding_arrs,
                        }
                        _populate_process_metadata(arr, kind, payload)
                        procs.append(payload)
            return {"processes": procs}

        @app.get("/api/processes")
        def api_processes():
            if (resp := require_token()) is not None:
                return resp
            return jsonify(_processes_payload())

        # UI endpoints (mirror of /api/* for first-party WebUI clients)
        @app.get("/web/processes")
        def web_processes():
            return jsonify(_processes_payload())

        def _restart_process(category: str, kind: str):
            kind_normalized = kind.lower()
            if kind_normalized not in ("search", "torrent", "all"):
                return jsonify({"error": "kind must be search, torrent or all"}), 400
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            arr = managed.get(category)
            if arr is None:
                return jsonify({"error": f"Unknown category {category}"}), 404
            restarted: list[str] = []
            for loop_kind in ("search", "torrent"):
                if kind_normalized != "all" and loop_kind != kind_normalized:
                    continue
                proc_attr = f"process_{loop_kind}_loop"
                process = getattr(arr, proc_attr, None)
                if process is not None:
                    try:
                        process.kill()
                    except Exception:
                        pass
                    try:
                        process.terminate()
                    except Exception:
                        pass
                    try:
                        self.manager.child_processes.remove(process)
                    except Exception:
                        pass
                target = getattr(arr, f"run_{loop_kind}_loop", None)
                if target is None:
                    continue
                import pathos

                new_process = pathos.helpers.mp.Process(target=target, daemon=False)
                setattr(arr, proc_attr, new_process)
                self.manager.child_processes.append(new_process)
                new_process.start()
                restarted.append(loop_kind)
            return jsonify({"status": "ok", "restarted": restarted})

        @app.post("/api/processes/<category>/<kind>/restart")
        def api_restart_process(category: str, kind: str):
            if (resp := require_token()) is not None:
                return resp
            return _restart_process(category, kind)

        @app.post("/web/processes/<category>/<kind>/restart")
        def web_restart_process(category: str, kind: str):
            return _restart_process(category, kind)

        @app.post("/api/processes/restart_all")
        def api_restart_all():
            if (resp := require_token()) is not None:
                return resp
            self._reload_all()
            return jsonify({"status": "ok"})

        @app.post("/web/processes/restart_all")
        def web_restart_all():
            self._reload_all()
            return jsonify({"status": "ok"})

        @app.post("/api/loglevel")
        def api_loglevel():
            if (resp := require_token()) is not None:
                return resp
            body = request.get_json(silent=True) or {}
            level = str(body.get("level", "INFO")).upper()
            valid = {"CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"}
            if level not in valid:
                return jsonify({"error": f"invalid level {level}"}), 400
            target_level = getattr(logging, level, logging.INFO)
            logging.getLogger().setLevel(target_level)
            for name, lg in logging.root.manager.loggerDict.items():
                if isinstance(lg, logging.Logger) and str(name).startswith("qBitrr"):
                    lg.setLevel(target_level)
            try:
                _toml_set(CONFIG.config, "Settings.ConsoleLevel", level)
                CONFIG.save()
            except Exception:
                pass
            return jsonify({"status": "ok", "level": level})

        @app.post("/web/loglevel")
        def web_loglevel():
            body = request.get_json(silent=True) or {}
            level = str(body.get("level", "INFO")).upper()
            valid = {"CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"}
            if level not in valid:
                return jsonify({"error": f"invalid level {level}"}), 400
            target_level = getattr(logging, level, logging.INFO)
            logging.getLogger().setLevel(target_level)
            for name, lg in logging.root.manager.loggerDict.items():
                if isinstance(lg, logging.Logger) and str(name).startswith("qBitrr"):
                    lg.setLevel(target_level)
            try:
                _toml_set(CONFIG.config, "Settings.ConsoleLevel", level)
                CONFIG.save()
            except Exception:
                pass
            return jsonify({"status": "ok", "level": level})

        @app.post("/api/arr/rebuild")
        def api_arr_rebuild():
            if (resp := require_token()) is not None:
                return resp
            self._reload_all()
            return jsonify({"status": "ok"})

        @app.post("/web/arr/rebuild")
        def web_arr_rebuild():
            self._reload_all()
            return jsonify({"status": "ok"})

        def _list_logs() -> list[str]:
            if not logs_root.exists():
                return []
            log_files = sorted(f.name for f in logs_root.glob("*.log*"))
            return log_files

        @app.get("/api/logs")
        def api_logs():
            if (resp := require_token()) is not None:
                return resp
            return jsonify({"files": _list_logs()})

        @app.get("/web/logs")
        def web_logs():
            return jsonify({"files": _list_logs()})

        @app.get("/api/logs/<name>")
        def api_log(name: str):
            if (resp := require_token()) is not None:
                return resp
            file = _resolve_log_file(name)
            if file is None or not file.exists():
                return jsonify({"error": "not found"}), 404

            # Stream full log file to support dynamic loading in LazyLog
            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                content = ""
            response = send_file(
                io.BytesIO(content.encode("utf-8")),
                mimetype="text/plain",
                as_attachment=False,
            )
            response.headers["Content-Type"] = "text/plain; charset=utf-8"
            response.headers["Cache-Control"] = "no-cache"
            return response

        @app.get("/web/logs/<name>")
        def web_log(name: str):
            # Public endpoint for Authentik bypass - no token required
            file = _resolve_log_file(name)
            if file is None or not file.exists():
                return jsonify({"error": "not found"}), 404

            # Stream full log file to support dynamic loading in LazyLog
            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                content = ""
            response = send_file(
                io.BytesIO(content.encode("utf-8")),
                mimetype="text/plain",
                as_attachment=False,
            )
            response.headers["Content-Type"] = "text/plain; charset=utf-8"
            response.headers["Cache-Control"] = "no-cache"
            return response

        @app.get("/api/logs/<name>/download")
        def api_log_download(name: str):
            if (resp := require_token()) is not None:
                return resp
            file = _resolve_log_file(name)
            if file is None or not file.exists():
                return jsonify({"error": "not found"}), 404
            return send_file(file, as_attachment=True)

        @app.get("/web/logs/<name>/download")
        def web_log_download(name: str):
            file = _resolve_log_file(name)
            if file is None or not file.exists():
                return jsonify({"error": "not found"}), 404
            return send_file(file, as_attachment=True)

        @app.get("/api/radarr/<category>/movies")
        def api_radarr_movies(category: str):
            if (resp := require_token()) is not None:
                return resp
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            arr = managed.get(category)
            if arr is None or getattr(arr, "type", None) != "radarr":
                return jsonify({"error": f"Unknown radarr category {category}"}), 404
            q = request.args.get("q", default=None, type=str)
            page = request.args.get("page", default=0, type=int)
            page_size = request.args.get("page_size", default=50, type=int)
            year_min = request.args.get("year_min", default=None, type=int)
            year_max = request.args.get("year_max", default=None, type=int)
            monitored = (
                self._safe_bool(request.args.get("monitored"))
                if "monitored" in request.args
                else None
            )
            has_file = (
                self._safe_bool(request.args.get("has_file"))
                if "has_file" in request.args
                else None
            )
            quality_met = (
                self._safe_bool(request.args.get("quality_met"))
                if "quality_met" in request.args
                else None
            )
            is_request = (
                self._safe_bool(request.args.get("is_request"))
                if "is_request" in request.args
                else None
            )
            payload = self._radarr_movies_from_db(
                arr,
                q,
                page,
                page_size,
                year_min=year_min,
                year_max=year_max,
                monitored=monitored,
                has_file=has_file,
                quality_met=quality_met,
                is_request=is_request,
            )
            payload["category"] = category
            return jsonify(payload)

        @app.get("/web/radarr/<category>/movies")
        def web_radarr_movies(category: str):
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            arr = managed.get(category)
            if arr is None or getattr(arr, "type", None) != "radarr":
                return jsonify({"error": f"Unknown radarr category {category}"}), 404
            q = request.args.get("q", default=None, type=str)
            page = request.args.get("page", default=0, type=int)
            page_size = request.args.get("page_size", default=50, type=int)
            year_min = request.args.get("year_min", default=None, type=int)
            year_max = request.args.get("year_max", default=None, type=int)
            monitored = (
                self._safe_bool(request.args.get("monitored"))
                if "monitored" in request.args
                else None
            )
            has_file = (
                self._safe_bool(request.args.get("has_file"))
                if "has_file" in request.args
                else None
            )
            quality_met = (
                self._safe_bool(request.args.get("quality_met"))
                if "quality_met" in request.args
                else None
            )
            is_request = (
                self._safe_bool(request.args.get("is_request"))
                if "is_request" in request.args
                else None
            )
            payload = self._radarr_movies_from_db(
                arr,
                q,
                page,
                page_size,
                year_min=year_min,
                year_max=year_max,
                monitored=monitored,
                has_file=has_file,
                quality_met=quality_met,
                is_request=is_request,
            )
            payload["category"] = category
            return jsonify(payload)

        @app.get("/api/sonarr/<category>/series")
        def api_sonarr_series(category: str):
            if (resp := require_token()) is not None:
                return resp
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            arr = managed.get(category)
            if arr is None or getattr(arr, "type", None) != "sonarr":
                return jsonify({"error": f"Unknown sonarr category {category}"}), 404
            q = request.args.get("q", default=None, type=str)
            page = request.args.get("page", default=0, type=int)
            page_size = request.args.get("page_size", default=25, type=int)
            missing_only = self._safe_bool(
                request.args.get("missing") or request.args.get("only_missing")
            )
            payload = self._sonarr_series_from_db(
                arr, q, page, page_size, missing_only=missing_only
            )
            payload["category"] = category
            return jsonify(payload)

        @app.get("/web/sonarr/<category>/series")
        def web_sonarr_series(category: str):
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            arr = managed.get(category)
            if arr is None or getattr(arr, "type", None) != "sonarr":
                return jsonify({"error": f"Unknown sonarr category {category}"}), 404
            q = request.args.get("q", default=None, type=str)
            page = request.args.get("page", default=0, type=int)
            page_size = request.args.get("page_size", default=25, type=int)
            missing_only = self._safe_bool(
                request.args.get("missing") or request.args.get("only_missing")
            )
            payload = self._sonarr_series_from_db(
                arr, q, page, page_size, missing_only=missing_only
            )
            payload["category"] = category
            return jsonify(payload)

        @app.get("/web/lidarr/<category>/albums")
        def web_lidarr_albums(category: str):
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            arr = managed.get(category)
            if arr is None or getattr(arr, "type", None) != "lidarr":
                return jsonify({"error": f"Unknown lidarr category {category}"}), 404
            q = request.args.get("q", default=None, type=str)
            page = request.args.get("page", default=0, type=int)
            page_size = request.args.get("page_size", default=50, type=int)
            monitored = (
                self._safe_bool(request.args.get("monitored"))
                if "monitored" in request.args
                else None
            )
            has_file = (
                self._safe_bool(request.args.get("has_file"))
                if "has_file" in request.args
                else None
            )
            quality_met = (
                self._safe_bool(request.args.get("quality_met"))
                if "quality_met" in request.args
                else None
            )
            is_request = (
                self._safe_bool(request.args.get("is_request"))
                if "is_request" in request.args
                else None
            )
            flat_mode = self._safe_bool(request.args.get("flat_mode", False))

            if flat_mode:
                # Flat mode: return tracks directly
                payload = self._lidarr_tracks_from_db(
                    arr,
                    q,
                    page,
                    page_size,
                    monitored=monitored,
                    has_file=has_file,
                )
            else:
                # Grouped mode: return albums with tracks, paginated by artist
                payload = self._lidarr_albums_from_db(
                    arr,
                    q,
                    page,
                    page_size,
                    monitored=monitored,
                    has_file=has_file,
                    quality_met=quality_met,
                    is_request=is_request,
                    group_by_artist=True,
                )
            payload["category"] = category
            return jsonify(payload)

        def _arr_list_payload() -> dict[str, Any]:
            items = []
            for k, arr in _managed_objects().items():
                t = getattr(arr, "type", None)
                if t in ("radarr", "sonarr", "lidarr"):
                    name = getattr(arr, "_name", k)
                    category = getattr(arr, "category", k)
                    items.append({"category": category, "name": name, "type": t})
            return {"arr": items, "ready": _ensure_arr_manager_ready()}

        @app.get("/api/arr")
        def api_arr_list():
            if (resp := require_token()) is not None:
                return resp
            return jsonify(_arr_list_payload())

        @app.get("/web/arr")
        def web_arr_list():
            return jsonify(_arr_list_payload())

        @app.get("/web/qbit/categories")
        def web_qbit_categories():
            """Get all qBit-managed and Arr-managed categories with seeding statistics."""
            categories_data = []

            # Add qBit-managed categories
            if self.manager.qbit_category_managers:
                for instance_name, manager in self.manager.qbit_category_managers.items():
                    client = self.manager.get_client(instance_name)
                    if not client:
                        continue

                    for category in manager.managed_categories:
                        try:
                            torrents = client.torrents_info(category=category)

                            # Calculate statistics
                            total_count = len(torrents)
                            seeding_count = len(
                                [t for t in torrents if t.state in ("uploading", "stalledUP")]
                            )
                            total_size = sum(t.size for t in torrents)
                            avg_ratio = (
                                sum(t.ratio for t in torrents) / total_count if total_count else 0
                            )
                            avg_seeding_time = (
                                sum(t.seeding_time for t in torrents) / total_count
                                if total_count
                                else 0
                            )

                            # Get seeding config for this category
                            seeding_config = manager.get_seeding_config(category)

                            categories_data.append(
                                {
                                    "category": category,
                                    "instance": instance_name,
                                    "managedBy": "qbit",
                                    "torrentCount": total_count,
                                    "seedingCount": seeding_count,
                                    "totalSize": total_size,
                                    "avgRatio": round(avg_ratio, 2),
                                    "avgSeedingTime": avg_seeding_time,
                                    "seedingConfig": {
                                        "maxRatio": seeding_config.get("MaxUploadRatio", -1),
                                        "maxTime": seeding_config.get("MaxSeedingTime", -1),
                                        "removeMode": seeding_config.get("RemoveTorrent", -1),
                                        "downloadLimit": seeding_config.get(
                                            "DownloadRateLimitPerTorrent", -1
                                        ),
                                        "uploadLimit": seeding_config.get(
                                            "UploadRateLimitPerTorrent", -1
                                        ),
                                    },
                                }
                            )
                        except Exception as e:
                            self.logger.debug(
                                "Error fetching qBit category '%s' stats for instance '%s': %s",
                                category,
                                instance_name,
                                e,
                            )
                            continue

            # Add Arr-managed categories
            if hasattr(self.manager, "arr_manager") and self.manager.arr_manager:
                for arr in self.manager.arr_manager.managed_objects.values():
                    try:
                        # Get the qBit instance for this Arr (use default for now)
                        client = self.manager.client
                        if not client:
                            continue

                        category = arr.category
                        torrents = client.torrents_info(category=category)

                        # Calculate statistics
                        total_count = len(torrents)
                        seeding_count = len(
                            [t for t in torrents if t.state in ("uploading", "stalledUP")]
                        )
                        total_size = sum(t.size for t in torrents)
                        avg_ratio = (
                            sum(t.ratio for t in torrents) / total_count if total_count else 0
                        )
                        avg_seeding_time = (
                            sum(t.seeding_time for t in torrents) / total_count
                            if total_count
                            else 0
                        )

                        categories_data.append(
                            {
                                "category": category,
                                "instance": arr._name,
                                "managedBy": "arr",
                                "torrentCount": total_count,
                                "seedingCount": seeding_count,
                                "totalSize": total_size,
                                "avgRatio": round(avg_ratio, 2),
                                "avgSeedingTime": avg_seeding_time,
                                "seedingConfig": {
                                    "maxRatio": arr.seeding_mode_global_max_upload_ratio,
                                    "maxTime": arr.seeding_mode_global_max_seeding_time,
                                    "removeMode": arr.seeding_mode_global_remove_torrent,
                                    "downloadLimit": arr.seeding_mode_global_download_limit,
                                    "uploadLimit": arr.seeding_mode_global_upload_limit,
                                },
                            }
                        )
                    except Exception as e:
                        self.logger.debug(
                            "Error fetching Arr category '%s' stats for instance '%s': %s",
                            getattr(arr, "category", "unknown"),
                            getattr(arr, "_name", "unknown"),
                            e,
                        )
                        continue

            return jsonify({"categories": categories_data, "ready": True})

        @app.get("/api/meta")
        def api_meta():
            if (resp := require_token()) is not None:
                return resp
            force = self._safe_bool(request.args.get("force"))
            return jsonify(self._ensure_version_info(force=force))

        @app.get("/web/meta")
        def web_meta():
            force = self._safe_bool(request.args.get("force"))
            return jsonify(self._ensure_version_info(force=force))

        @app.post("/api/update")
        def api_update():
            if (resp := require_token()) is not None:
                return resp
            ok, message = self._trigger_manual_update()
            if not ok:
                return jsonify({"error": message}), 409
            return jsonify({"status": "started"})

        @app.post("/web/update")
        def web_update():
            ok, message = self._trigger_manual_update()
            if not ok:
                return jsonify({"error": message}), 409
            return jsonify({"status": "started"})

        @app.get("/api/download-update")
        def api_download_update():
            """Redirect to binary download URL for current platform."""
            if (resp := require_token()) is not None:
                return resp

            from qBitrr.auto_update import get_installation_type

            install_type = get_installation_type()

            if install_type != "binary":
                return jsonify({"error": "Download only available for binary installations"}), 400

            # Get latest version info
            version_info = self._ensure_version_info()

            if not version_info.get("update_available"):
                return jsonify({"error": "No update available"}), 404

            download_url = version_info.get("binary_download_url")
            if not download_url:
                error = version_info.get(
                    "binary_download_error", "No binary available for your platform"
                )
                return jsonify({"error": error}), 404

            # Redirect to GitHub download URL
            from flask import redirect

            return redirect(download_url)

        @app.get("/web/download-update")
        def web_download_update():
            """Redirect to binary download URL for current platform."""
            from qBitrr.auto_update import get_installation_type

            install_type = get_installation_type()

            if install_type != "binary":
                return jsonify({"error": "Download only available for binary installations"}), 400

            # Get latest version info
            version_info = self._ensure_version_info()

            if not version_info.get("update_available"):
                return jsonify({"error": "No update available"}), 404

            download_url = version_info.get("binary_download_url")
            if not download_url:
                error = version_info.get(
                    "binary_download_error", "No binary available for your platform"
                )
                return jsonify({"error": error}), 404

            # Redirect to GitHub download URL
            from flask import redirect

            return redirect(download_url)

        def _status_payload() -> dict[str, Any]:
            # Legacy single-instance qBit info (for backward compatibility)
            qb = {
                "alive": bool(self.manager.is_alive),
                "host": self.manager.qBit_Host,
                "port": self.manager.qBit_Port,
                "version": (
                    str(self.manager.current_qbit_version)
                    if self.manager.current_qbit_version
                    else None
                ),
            }

            # Multi-instance qBit info
            qbit_instances = {}
            for instance_name in self.manager.get_all_instances():
                info = self.manager.get_instance_info(instance_name)
                qbit_instances[instance_name] = {
                    "alive": self.manager.is_instance_alive(instance_name),
                    "host": info.get("host", ""),
                    "port": info.get("port", 0),
                    "version": info.get("version", None),
                }

            arrs = []
            for k, arr in _managed_objects().items():
                t = getattr(arr, "type", None)
                if t in ("radarr", "sonarr", "lidarr"):
                    # Determine liveness based on child search/torrent processes
                    alive = False
                    for loop in ("search", "torrent"):
                        p = getattr(arr, f"process_{loop}_loop", None)
                        if p is not None:
                            try:
                                if p.is_alive():
                                    alive = True
                                    break
                            except Exception:
                                pass
                    name = getattr(arr, "_name", k)
                    category = getattr(arr, "category", k)
                    arrs.append({"category": category, "name": name, "type": t, "alive": alive})
            return {
                "qbit": qb,  # Legacy single-instance (default) for backward compatibility
                "qbitInstances": qbit_instances,  # Multi-instance info
                "arrs": arrs,
                "ready": _ensure_arr_manager_ready(),
            }

        @app.get("/api/status")
        def api_status():
            if (resp := require_token()) is not None:
                return resp
            return jsonify(_status_payload())

        @app.get("/web/status")
        def web_status():
            return jsonify(_status_payload())

        @app.get("/api/torrents/distribution")
        def api_torrents_distribution():
            """Get torrent distribution across qBit instances grouped by category"""
            if (resp := require_token()) is not None:
                return resp

            distribution = {}
            for instance_name in self.manager.get_all_instances():
                if not self.manager.is_instance_alive(instance_name):
                    continue

                try:
                    client = self.manager.get_client(instance_name)
                    torrents = client.torrents.info()

                    # Group by category
                    for torrent in torrents:
                        category = getattr(torrent, "category", "uncategorized")
                        if category not in distribution:
                            distribution[category] = {}
                        if instance_name not in distribution[category]:
                            distribution[category][instance_name] = 0
                        distribution[category][instance_name] += 1
                except Exception:
                    # Skip instances that fail
                    pass

            return jsonify({"distribution": distribution})

        @app.get("/api/token")
        def api_token():
            if (resp := require_token()) is not None:
                return resp
            # Expose token for API clients only; UI uses /web endpoints
            return jsonify({"token": self.token})

        @app.post("/api/arr/<section>/restart")
        def api_arr_restart(section: str):
            if (resp := require_token()) is not None:
                return resp
            # Section is the category key in managed_objects
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            if section not in managed:
                return jsonify({"error": f"Unknown section {section}"}), 404
            arr = managed[section]
            # Restart both loops for this arr
            restarted = []
            for k in ("search", "torrent"):
                proc_attr = f"process_{k}_loop"
                p = getattr(arr, proc_attr, None)
                if p is not None:
                    try:
                        p.kill()
                    except Exception:
                        pass
                    try:
                        p.terminate()
                    except Exception:
                        pass
                    try:
                        self.manager.child_processes.remove(p)
                    except Exception:
                        pass
                import pathos

                target = getattr(arr, f"run_{k}_loop", None)
                if target is None:
                    continue
                new_p = pathos.helpers.mp.Process(target=target, daemon=False)
                setattr(arr, proc_attr, new_p)
                self.manager.child_processes.append(new_p)
                new_p.start()
                restarted.append(k)
            return jsonify({"status": "ok", "restarted": restarted})

        @app.post("/web/arr/<section>/restart")
        def web_arr_restart(section: str):
            managed = _managed_objects()
            if not managed:
                if not _ensure_arr_manager_ready():
                    return jsonify({"error": "Arr manager is still initialising"}), 503
            if section not in managed:
                return jsonify({"error": f"Unknown section {section}"}), 404
            arr = managed[section]
            restarted = []
            for k in ("search", "torrent"):
                proc_attr = f"process_{k}_loop"
                p = getattr(arr, proc_attr, None)
                if p is not None:
                    try:
                        p.kill()
                    except Exception:
                        pass
                    try:
                        p.terminate()
                    except Exception:
                        pass
                    try:
                        self.manager.child_processes.remove(p)
                    except Exception:
                        pass
                import pathos

                target = getattr(arr, f"run_{k}_loop", None)
                if target is None:
                    continue
                new_p = pathos.helpers.mp.Process(target=target, daemon=False)
                setattr(arr, proc_attr, new_p)
                self.manager.child_processes.append(new_p)
                new_p.start()
                restarted.append(k)
            return jsonify({"status": "ok", "restarted": restarted})

        @app.get("/api/config")
        def api_get_config():
            if (resp := require_token()) is not None:
                return resp
            try:
                # Reload config from disk to reflect latest file
                try:
                    CONFIG.load()
                except Exception:
                    pass
                # Render current config as a JSON-able dict via tomlkit
                data = _toml_to_jsonable(CONFIG.config)
                return jsonify(data)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @app.get("/web/config")
        def web_get_config():
            try:
                try:
                    CONFIG.load()
                except Exception:
                    pass
                data = _toml_to_jsonable(CONFIG.config)

                # Check config version and add warning if mismatch
                from qBitrr.config_version import get_config_version, validate_config_version

                is_valid, validation_result = validate_config_version(CONFIG)
                if not is_valid:
                    # Add version mismatch warning to response
                    response_data = {
                        "config": data,
                        "warning": {
                            "type": "config_version_mismatch",
                            "message": validation_result,
                            "currentVersion": get_config_version(CONFIG),
                        },
                    }
                    return jsonify(response_data)

                return jsonify(data)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        def _handle_config_update():
            """Common handler for config updates with intelligent reload detection."""
            body = request.get_json(silent=True) or {}
            changes: dict[str, Any] = body.get("changes", {})
            if not isinstance(changes, dict):
                return jsonify({"error": "changes must be an object"}), 400

            # Prevent ConfigVersion from being modified by user
            protected_keys = {"Settings.ConfigVersion"}
            for key in protected_keys:
                if key in changes:
                    return (
                        jsonify({"error": f"Cannot modify protected configuration key: {key}"}),
                        403,
                    )

            # Define key categories
            frontend_only_keys = {
                "WebUI.LiveArr",
                "WebUI.GroupSonarr",
                "WebUI.GroupLidarr",
                "WebUI.Theme",
            }
            webui_restart_keys = {
                "WebUI.Host",
                "WebUI.Port",
                "WebUI.Token",
            }

            # Analyze changes to determine reload strategy
            affected_arr_instances = set()
            has_global_changes = False
            has_webui_changes = False
            has_frontend_only_changes = False

            for key in changes.keys():
                if key in frontend_only_keys:
                    has_frontend_only_changes = True
                elif key in webui_restart_keys:
                    has_webui_changes = True
                elif key.startswith("WebUI."):
                    # Unknown WebUI key, treat as webui change for safety
                    has_webui_changes = True
                elif match := re.match(
                    r"^(Radarr|Sonarr|Lidarr|Animarr)[^.]*\.(.+)$", key, re.IGNORECASE
                ):
                    # Arr instance specific change
                    instance_name = key.split(".")[0]
                    affected_arr_instances.add(instance_name)
                else:
                    # Settings.*, qBit.*, or unknown - requires full reload
                    has_global_changes = True

            # Apply all changes to config
            for key, val in changes.items():
                if val is None:
                    _toml_delete(CONFIG.config, key)
                    if key == "WebUI.Token":
                        self.token = ""
                    continue
                _toml_set(CONFIG.config, key, val)
                if key == "WebUI.Token":
                    # Update in-memory token immediately
                    self.token = str(val) if val is not None else ""

            # Persist config
            try:
                CONFIG.save()
            except Exception as e:
                return jsonify({"error": f"Failed to save config: {e}"}), 500

            # Determine reload strategy
            reload_type = "none"
            affected_instances_list = []

            if has_global_changes:
                # Global settings changed - full reload required
                # This affects ALL instances (qBit settings, loop timers, etc.)
                reload_type = "full"
                self.logger.notice("Global settings changed, performing full reload")
                try:
                    self.manager.configure_auto_update()
                except Exception:
                    self.logger.exception("Failed to refresh auto update configuration")
                self._reload_all()

            elif len(affected_arr_instances) >= 1:
                # One or more Arr instances changed - reload each individually
                # NEVER trigger global reload for Arr-only changes
                reload_type = "multi_arr" if len(affected_arr_instances) > 1 else "single_arr"
                affected_instances_list = sorted(affected_arr_instances)

                self.logger.notice(
                    f"Reloading {len(affected_instances_list)} Arr instance(s): {', '.join(affected_instances_list)}"
                )

                # Reload each affected instance in sequence
                for instance_name in affected_instances_list:
                    self._reload_arr_instance(instance_name)

            elif has_webui_changes:
                # Only WebUI settings changed - restart WebUI
                reload_type = "webui"
                self.logger.notice("WebUI settings changed, restarting WebUI server")
                # Run restart in background thread to avoid blocking response
                restart_thread = threading.Thread(
                    target=self._restart_webui, name="WebUIRestart", daemon=True
                )
                restart_thread.start()

            elif has_frontend_only_changes:
                # Only frontend settings changed - no reload
                reload_type = "frontend"
                self.logger.debug("Frontend-only settings changed, no reload required")

            # Build response
            response_data = {
                "status": "ok",
                "configReloaded": reload_type not in ("none", "frontend"),
                "reloadType": reload_type,
                "affectedInstances": affected_instances_list,
            }

            response = jsonify(response_data)

            # Add headers for cache control
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

            # Legacy header for compatibility
            if reload_type in ("full", "single_arr", "multi_arr", "webui"):
                response.headers["X-Config-Reloaded"] = "true"

            return response

        @app.post("/api/config")
        def api_update_config():
            if (resp := require_token()) is not None:
                return resp
            return _handle_config_update()

        @app.post("/web/config")
        def web_update_config():
            return _handle_config_update()

        @app.post("/api/arr/test-connection")
        def api_arr_test_connection():
            """
            Test connection to Arr instance without saving config.
            Accepts temporary URI/APIKey and returns connection status + quality profiles.
            """
            if (resp := require_token()) is not None:
                return resp

            try:
                data = request.get_json()
                if not data:
                    return jsonify({"success": False, "message": "Missing request body"}), 400

                arr_type = data.get("arrType")  # "radarr" | "sonarr" | "lidarr"
                uri = data.get("uri")
                api_key = data.get("apiKey")

                # Validate inputs
                if not all([arr_type, uri, api_key]):
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": "Missing required fields: arrType, uri, or apiKey",
                            }
                        ),
                        400,
                    )

                # Try to find existing Arr instance with matching URI
                existing_arr = None
                managed = _managed_objects()
                for group_name, arr_instance in managed.items():
                    if hasattr(arr_instance, "uri") and hasattr(arr_instance, "apikey"):
                        if arr_instance.uri == uri and arr_instance.apikey == api_key:
                            existing_arr = arr_instance
                            self.logger.info(f"Using existing Arr instance: {group_name}")
                            break

                # Use existing client if available, otherwise create temporary one
                if existing_arr and hasattr(existing_arr, "client"):
                    client = existing_arr.client
                    self.logger.info(f"Reusing existing client for {existing_arr._name}")
                else:
                    # Create temporary Arr API client
                    self.logger.info(f"Creating temporary {arr_type} client for {uri}")
                    if arr_type == "radarr":
                        from pyarr import RadarrAPI

                        client = RadarrAPI(uri, api_key)
                    elif arr_type == "sonarr":
                        from pyarr import SonarrAPI

                        client = SonarrAPI(uri, api_key)
                    elif arr_type == "lidarr":
                        from pyarr import LidarrAPI

                        client = LidarrAPI(uri, api_key)
                    else:
                        return (
                            jsonify({"success": False, "message": f"Invalid arrType: {arr_type}"}),
                            400,
                        )

                # Test connection (no timeout - Flask/Waitress handles this)
                try:
                    self.logger.info(f"Testing connection to {arr_type} at {uri}")

                    # Get system info to verify connection
                    system_info = client.get_system_status()
                    self.logger.info(
                        f"System status retrieved: {system_info.get('version', 'unknown')}"
                    )

                    # Fetch quality profiles with retry logic (same as backend)
                    from json import JSONDecodeError

                    import requests
                    from pyarr.exceptions import PyarrServerError

                    max_retries = 3
                    retry_count = 0
                    quality_profiles = []

                    while retry_count < max_retries:
                        try:
                            quality_profiles = client.get_quality_profile()
                            self.logger.info(
                                f"Quality profiles retrieved: {len(quality_profiles)} profiles"
                            )
                            break
                        except (
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                        ) as e:
                            retry_count += 1
                            self.logger.warning(
                                f"Transient error fetching quality profiles (attempt {retry_count}/{max_retries}): {e}"
                            )
                            if retry_count >= max_retries:
                                self.logger.error("Failed to fetch quality profiles after retries")
                                quality_profiles = []
                                break
                            time.sleep(1)
                        except PyarrServerError as e:
                            self.logger.error(f"Server error fetching quality profiles: {e}")
                            quality_profiles = []
                            break
                        except Exception as e:
                            self.logger.error(f"Unexpected error fetching quality profiles: {e}")
                            quality_profiles = []
                            break

                    # Format response
                    return jsonify(
                        {
                            "success": True,
                            "message": "Connected successfully",
                            "systemInfo": {
                                "version": system_info.get("version", "unknown"),
                                "branch": system_info.get("branch"),
                            },
                            "qualityProfiles": [
                                {"id": p["id"], "name": p["name"]} for p in quality_profiles
                            ],
                        }
                    )

                except Exception as e:
                    # Handle specific error types
                    error_msg = str(e)
                    # Log full error for debugging but sanitize user-facing message
                    self.logger.error(f"Connection test failed: {error_msg}")

                    if "401" in error_msg or "Unauthorized" in error_msg:
                        return (
                            jsonify(
                                {"success": False, "message": "Unauthorized: Invalid API key"}
                            ),
                            401,
                        )
                    elif "404" in error_msg:
                        return (
                            jsonify(
                                {"success": False, "message": f"Not found: Check URI ({uri})"}
                            ),
                            404,
                        )
                    elif "Connection refused" in error_msg or "ConnectionError" in error_msg:
                        return (
                            jsonify(
                                {
                                    "success": False,
                                    "message": f"Connection refused: Cannot reach {uri}",
                                }
                            ),
                            503,
                        )
                    else:
                        # Generic error message - details logged above
                        return (
                            jsonify({"success": False, "message": "Connection test failed"}),
                            500,
                        )

            except Exception as e:
                self.logger.error("Test connection error: %s", e)
                return jsonify({"success": False, "message": "Connection test failed"}), 500

        @app.post("/web/arr/test-connection")
        def web_arr_test_connection():
            """
            Test connection to Arr instance without saving config.
            Accepts temporary URI/APIKey and returns connection status + quality profiles.
            Public endpoint (mirrors /api/arr/test-connection).
            """
            try:
                data = request.get_json()
                if not data:
                    return jsonify({"success": False, "message": "Missing request body"}), 400

                arr_type = data.get("arrType")  # "radarr" | "sonarr" | "lidarr"
                uri = data.get("uri")
                api_key = data.get("apiKey")

                # Validate inputs
                if not all([arr_type, uri, api_key]):
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": "Missing required fields: arrType, uri, or apiKey",
                            }
                        ),
                        400,
                    )

                # Try to find existing Arr instance with matching URI
                existing_arr = None
                managed = _managed_objects()
                for group_name, arr_instance in managed.items():
                    if hasattr(arr_instance, "uri") and hasattr(arr_instance, "apikey"):
                        if arr_instance.uri == uri and arr_instance.apikey == api_key:
                            existing_arr = arr_instance
                            self.logger.info(f"Using existing Arr instance: {group_name}")
                            break

                # Use existing client if available, otherwise create temporary one
                if existing_arr and hasattr(existing_arr, "client"):
                    client = existing_arr.client
                    self.logger.info(f"Reusing existing client for {existing_arr._name}")
                else:
                    # Create temporary Arr API client
                    self.logger.info(f"Creating temporary {arr_type} client for {uri}")
                    if arr_type == "radarr":
                        from pyarr import RadarrAPI

                        client = RadarrAPI(uri, api_key)
                    elif arr_type == "sonarr":
                        from pyarr import SonarrAPI

                        client = SonarrAPI(uri, api_key)
                    elif arr_type == "lidarr":
                        from pyarr import LidarrAPI

                        client = LidarrAPI(uri, api_key)
                    else:
                        return (
                            jsonify({"success": False, "message": f"Invalid arrType: {arr_type}"}),
                            400,
                        )

                # Test connection (no timeout - Flask/Waitress handles this)
                try:
                    self.logger.info(f"Testing connection to {arr_type} at {uri}")

                    # Get system info to verify connection
                    system_info = client.get_system_status()
                    self.logger.info(
                        f"System status retrieved: {system_info.get('version', 'unknown')}"
                    )

                    # Fetch quality profiles with retry logic (same as backend)
                    from json import JSONDecodeError

                    import requests
                    from pyarr.exceptions import PyarrServerError

                    max_retries = 3
                    retry_count = 0
                    quality_profiles = []

                    while retry_count < max_retries:
                        try:
                            quality_profiles = client.get_quality_profile()
                            self.logger.info(
                                f"Quality profiles retrieved: {len(quality_profiles)} profiles"
                            )
                            break
                        except (
                            requests.exceptions.ChunkedEncodingError,
                            requests.exceptions.ContentDecodingError,
                            requests.exceptions.ConnectionError,
                            JSONDecodeError,
                        ) as e:
                            retry_count += 1
                            self.logger.warning(
                                f"Transient error fetching quality profiles (attempt {retry_count}/{max_retries}): {e}"
                            )
                            if retry_count >= max_retries:
                                self.logger.error("Failed to fetch quality profiles after retries")
                                quality_profiles = []
                                break
                            time.sleep(1)
                        except PyarrServerError as e:
                            self.logger.error(f"Server error fetching quality profiles: {e}")
                            quality_profiles = []
                            break
                        except Exception as e:
                            self.logger.error(f"Unexpected error fetching quality profiles: {e}")
                            quality_profiles = []
                            break

                    # Format response
                    return jsonify(
                        {
                            "success": True,
                            "message": "Connected successfully",
                            "systemInfo": {
                                "version": system_info.get("version", "unknown"),
                                "branch": system_info.get("branch"),
                            },
                            "qualityProfiles": [
                                {"id": p["id"], "name": p["name"]} for p in quality_profiles
                            ],
                        }
                    )

                except Exception as e:
                    # Handle specific error types
                    error_msg = str(e)
                    # Log full error for debugging but sanitize user-facing message
                    self.logger.error(f"Connection test failed: {error_msg}")

                    if "401" in error_msg or "Unauthorized" in error_msg:
                        return (
                            jsonify(
                                {"success": False, "message": "Unauthorized: Invalid API key"}
                            ),
                            401,
                        )
                    elif "404" in error_msg:
                        return (
                            jsonify(
                                {"success": False, "message": f"Not found: Check URI ({uri})"}
                            ),
                            404,
                        )
                    elif "Connection refused" in error_msg or "ConnectionError" in error_msg:
                        return (
                            jsonify(
                                {
                                    "success": False,
                                    "message": f"Connection refused: Cannot reach {uri}",
                                }
                            ),
                            503,
                        )
                    else:
                        # Generic error message - details logged above
                        return (
                            jsonify({"success": False, "message": "Connection test failed"}),
                            500,
                        )

            except Exception as e:
                self.logger.error("Test connection error: %s", e)
                return jsonify({"success": False, "message": "Connection test failed"}), 500

    def _reload_all(self):
        # Set rebuilding flag
        self._rebuilding_arrs = True
        try:
            # Stop current processes
            for p in list(self.manager.child_processes):
                try:
                    p.kill()
                except Exception:
                    pass
                try:
                    p.terminate()
                except Exception:
                    pass
            self.manager.child_processes.clear()

            # Delete database files for all arr instances before rebuilding
            if hasattr(self.manager, "arr_manager") and self.manager.arr_manager:
                for arr in self.manager.arr_manager.managed_objects.values():
                    try:
                        if hasattr(arr, "search_db_file") and arr.search_db_file:
                            # Delete main database file
                            if arr.search_db_file.exists():
                                self.logger.info(f"Deleting database file: {arr.search_db_file}")
                                arr.search_db_file.unlink()
                                self.logger.success(f"Deleted database file for {arr._name}")
                            # Delete WAL file (Write-Ahead Log)
                            wal_file = arr.search_db_file.with_suffix(".db-wal")
                            if wal_file.exists():
                                self.logger.info(f"Deleting WAL file: {wal_file}")
                                wal_file.unlink()
                            # Delete SHM file (Shared Memory)
                            shm_file = arr.search_db_file.with_suffix(".db-shm")
                            if shm_file.exists():
                                self.logger.info(f"Deleting SHM file: {shm_file}")
                                shm_file.unlink()
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to delete database files for {arr._name}: {e}"
                        )

            # Rebuild arr manager from config and spawn fresh
            from qBitrr.arss import ArrManager

            self.manager.arr_manager = ArrManager(self.manager).build_arr_instances()
            self.manager.configure_auto_update()
            # Spawn and start new processes
            for arr in self.manager.arr_manager.managed_objects.values():
                _, procs = arr.spawn_child_processes()
                for p in procs:
                    try:
                        p.start()
                    except Exception:
                        pass
        finally:
            # Clear rebuilding flag
            self._rebuilding_arrs = False

    def _restart_webui(self):
        """
        Gracefully restart the WebUI server without affecting Arr processes.
        This is used when WebUI.Host, WebUI.Port, or WebUI.Token changes.
        """
        self.logger.notice("WebUI restart requested (config changed)")

        # Reload config values
        try:
            CONFIG.load()
        except Exception as e:
            self.logger.warning(f"Failed to reload config: {e}")

        # Update in-memory values
        new_host = CONFIG.get("WebUI.Host", fallback="0.0.0.0")
        new_port = CONFIG.get("WebUI.Port", fallback=6969)
        new_token = CONFIG.get("WebUI.Token", fallback=None)

        # Check if restart is actually needed
        needs_restart = new_host != self.host or new_port != self.port

        # Token can be updated without restart
        if new_token != self.token:
            self.token = new_token
            self.logger.info("WebUI token updated")

        if not needs_restart:
            self.logger.info("WebUI Host/Port unchanged, restart not required")
            return

        # Update host/port
        self.host = new_host
        self.port = new_port

        # Signal restart
        self._restart_requested = True
        self._shutdown_event.set()

        self.logger.info(f"WebUI will restart on {self.host}:{self.port}")

    def _stop_arr_instance(self, arr, category: str):
        """Stop and cleanup a single Arr instance."""
        self.logger.info(f"Stopping Arr instance: {category}")

        # Stop processes
        for loop_kind in ("search", "torrent"):
            proc_attr = f"process_{loop_kind}_loop"
            process = getattr(arr, proc_attr, None)
            if process is not None:
                try:
                    process.kill()
                except Exception:
                    pass
                try:
                    process.terminate()
                except Exception:
                    pass
                try:
                    self.manager.child_processes.remove(process)
                except Exception:
                    pass
                self.logger.debug(f"Stopped {loop_kind} process for {category}")

        # Delete database files
        try:
            if hasattr(arr, "search_db_file") and arr.search_db_file:
                if arr.search_db_file.exists():
                    self.logger.info(f"Deleting database file: {arr.search_db_file}")
                    arr.search_db_file.unlink()
                    self.logger.success(
                        f"Deleted database file for {getattr(arr, '_name', category)}"
                    )
                # Delete WAL and SHM files
                for suffix in (".db-wal", ".db-shm"):
                    aux_file = arr.search_db_file.with_suffix(suffix)
                    if aux_file.exists():
                        self.logger.debug(f"Deleting auxiliary file: {aux_file}")
                        aux_file.unlink()
        except Exception as e:
            self.logger.warning(
                f"Failed to delete database files for {getattr(arr, '_name', category)}: {e}"
            )

        # Remove from managed_objects
        self.manager.arr_manager.managed_objects.pop(category, None)
        self.manager.arr_manager.groups.discard(getattr(arr, "_name", ""))
        self.manager.arr_manager.uris.discard(getattr(arr, "uri", ""))
        self.manager.arr_manager.arr_categories.discard(category)

        self.logger.success(f"Stopped and cleaned up Arr instance: {category}")

    def _start_arr_instance(self, instance_name: str):
        """Create and start a single Arr instance."""
        self.logger.info(f"Starting Arr instance: {instance_name}")

        # Check if instance is managed
        if not CONFIG.get(f"{instance_name}.Managed", fallback=False):
            self.logger.info(f"Instance {instance_name} is not managed, skipping")
            return

        # Determine client class based on name
        client_cls = None
        if re.match(r"^(Rad|rad)arr", instance_name):
            from pyarr import RadarrAPI

            client_cls = RadarrAPI
        elif re.match(r"^(Son|son|Anim|anim)arr", instance_name):
            from pyarr import SonarrAPI

            client_cls = SonarrAPI
        elif re.match(r"^(Lid|lid)arr", instance_name):
            from pyarr import LidarrAPI

            client_cls = LidarrAPI
        else:
            self.logger.error(f"Unknown Arr type for instance: {instance_name}")
            return

        try:
            # Create new Arr instance
            from qBitrr.arss import Arr
            from qBitrr.errors import SkipException

            new_arr = Arr(instance_name, self.manager.arr_manager, client_cls=client_cls)

            # Register in manager
            self.manager.arr_manager.groups.add(instance_name)
            self.manager.arr_manager.uris.add(new_arr.uri)
            self.manager.arr_manager.managed_objects[new_arr.category] = new_arr
            self.manager.arr_manager.arr_categories.add(new_arr.category)

            # Spawn and start processes
            _, procs = new_arr.spawn_child_processes()
            for p in procs:
                try:
                    p.start()
                    self.logger.debug(f"Started process (PID: {p.pid}) for {instance_name}")
                except Exception as e:
                    self.logger.error(f"Failed to start process for {instance_name}: {e}")

            self.logger.success(
                f"Started Arr instance: {instance_name} (category: {new_arr.category})"
            )

        except SkipException:
            self.logger.info(f"Instance {instance_name} skipped (not managed or disabled)")
        except Exception as e:
            self.logger.error(f"Failed to start Arr instance {instance_name}: {e}", exc_info=True)

    def _reload_arr_instance(self, instance_name: str):
        """Reload a single Arr instance without affecting others."""
        self.logger.notice(f"Reloading Arr instance: {instance_name}")

        if not hasattr(self.manager, "arr_manager") or not self.manager.arr_manager:
            self.logger.warning("Cannot reload Arr instance: ArrManager not initialized")
            return

        managed_objects = self.manager.arr_manager.managed_objects

        # Find the instance by name (key is category, so search by _name attribute)
        old_arr = None
        old_category = None
        for category, arr in list(managed_objects.items()):
            if getattr(arr, "_name", None) == instance_name:
                old_arr = arr
                old_category = category
                break

        # Check if instance exists in config
        instance_exists_in_config = instance_name in CONFIG.sections()

        # Handle deletion case
        if not instance_exists_in_config:
            if old_arr:
                self.logger.info(f"Instance {instance_name} removed from config, stopping...")
                self._stop_arr_instance(old_arr, old_category)
            else:
                self.logger.debug(f"Instance {instance_name} not found in config or memory")
            return

        # Handle update/addition
        if old_arr:
            # Update existing - stop old processes first
            self.logger.info(f"Updating existing Arr instance: {instance_name}")
            self._stop_arr_instance(old_arr, old_category)
        else:
            self.logger.info(f"Adding new Arr instance: {instance_name}")

        # Small delay to ensure cleanup completes
        time.sleep(0.5)

        # Create new instance
        self._start_arr_instance(instance_name)

        self.logger.success(f"Successfully reloaded Arr instance: {instance_name}")

    def start(self):
        if self._thread and self._thread.is_alive():
            self.logger.debug("WebUI already running on %s:%s", self.host, self.port)
            return
        self.logger.notice("Starting WebUI on %s:%s", self.host, self.port)
        self._thread = threading.Thread(target=self._serve, name="WebUI", daemon=True)
        self._thread.start()
        self.logger.success("WebUI thread started (name=%s)", self._thread.name)

    def _serve(self):
        try:
            # Reset shutdown event at start
            self._shutdown_event.clear()

            if self._should_use_dev_server():
                self.logger.info("Using Flask development server for WebUI")
                # Flask dev server - will exit on KeyboardInterrupt
                try:
                    self.app.run(
                        host=self.host,
                        port=self.port,
                        debug=False,
                        use_reloader=False,
                        threaded=True,
                    )
                except (KeyboardInterrupt, SystemExit):
                    pass
                return

            try:
                from waitress import serve as waitress_serve
            except Exception:
                self.logger.warning(
                    "Waitress is unavailable; falling back to Flask development server. "
                    "Install the 'waitress' extra or set QBITRR_USE_DEV_SERVER=1 to silence this message."
                )
                self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
                return

            self.logger.info("Using Waitress WSGI server for WebUI")

            # For graceful restart capability, we need to use waitress_serve with channels
            # However, for now we'll use the simpler approach and just run the server
            # Restart capability will require stopping the entire process
            # Use poll() instead of select() to avoid file descriptor limit issues
            waitress_serve(
                self.app,
                host=self.host,
                port=self.port,
                ident="qBitrr-WebUI",
                asyncore_use_poll=True,
            )

        except KeyboardInterrupt:
            self.logger.info("WebUI interrupted")
        except Exception:
            self.logger.exception("WebUI server terminated unexpectedly")
        finally:
            self._server = None

            # If restart was requested, start a new server
            if self._restart_requested:
                self._restart_requested = False
                self.logger.info("Restarting WebUI server...")
                time.sleep(0.5)  # Brief pause
                self.start()  # Restart

    def _should_use_dev_server(self) -> bool:
        if self._use_dev_server is not None:
            return self._use_dev_server
        override = os.environ.get("QBITRR_USE_DEV_SERVER", "")
        if override:
            self._use_dev_server = override.strip().lower() not in {"0", "false", "no", "off"}
            return self._use_dev_server
        self._use_dev_server = False
        return self._use_dev_server
