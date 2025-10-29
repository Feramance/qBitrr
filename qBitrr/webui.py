from __future__ import annotations

import io
import logging
import os
import re
import secrets
import threading
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, redirect, request, send_file
from peewee import fn

from qBitrr.arss import FreeSpaceManager, PlaceHolderArr
from qBitrr.bundled_data import patched_version
from qBitrr.config import CONFIG, HOME_PATH
from qBitrr.logger import run_logs
from qBitrr.search_activity_store import (
    clear_search_activity,
    fetch_search_activities,
)
from qBitrr.versioning import fetch_latest_release


def _toml_set(doc, dotted_key: str, value: Any):
    keys = dotted_key.split(".")
    cur = doc
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
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
        # Security token (optional) - auto-generate and persist if empty
        self.token = CONFIG.get("Settings.WebUIToken", fallback=None)
        if not self.token:
            self.token = secrets.token_hex(32)
            try:
                _toml_set(CONFIG.config, "Settings.WebUIToken", self.token)
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
            "changelog": "",
            "changelog_url": f"https://github.com/{self._github_repo}/releases",
            "repository_url": f"https://github.com/{self._github_repo}",
            "homepage_url": f"https://github.com/{self._github_repo}",
            "update_available": False,
            "last_checked": None,
            "error": None,
        }
        self._version_cache_expiry = datetime.utcnow() - timedelta(seconds=1)
        self._update_state = {
            "in_progress": False,
            "last_result": None,
            "last_error": None,
            "completed_at": None,
        }
        self._update_thread: threading.Thread | None = None
        self._register_routes()
        static_root = Path(__file__).with_name("static")
        if not (static_root / "index.html").exists():
            self.logger.warning(
                "WebUI static bundle is missing. Install npm and run "
                "'npm ci && npm run build' inside the 'webui' folder before packaging."
            )
        self._thread: threading.Thread | None = None
        self._use_dev_server: bool | None = None

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

    def _ensure_version_info(self, force: bool = False) -> dict[str, Any]:
        now = datetime.utcnow()
        fetch_required = force
        with self._version_lock:
            if not force and now < self._version_cache_expiry:
                snapshot = dict(self._version_cache)
                snapshot["update_state"] = dict(self._update_state)
                return snapshot
            if not force:
                fetch_required = True
            # optimistic expiry to avoid concurrent fetches
            self._version_cache_expiry = now + timedelta(minutes=5)

        if fetch_required:
            latest_info = self._fetch_version_info()
        else:
            latest_info = {}

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
            self._version_cache["current_version"] = patched_version
            self._version_cache["last_checked"] = now.isoformat()
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
        self, arr, search: str | None, page: int, page_size: int
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return {
                "counts": {"available": 0, "monitored": 0},
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "movies": [],
            }
        model = getattr(arr, "model_file", None)
        db = getattr(arr, "db", None)
        if model is None or db is None:
            return {
                "counts": {"available": 0, "monitored": 0},
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "movies": [],
            }
        page = max(page, 0)
        page_size = max(page_size, 1)
        with db.connection_context():
            base_query = model.select()
            monitored_count = (
                model.select(fn.COUNT(model.EntryId))
                .where(model.Monitored == True)  # noqa: E712
                .scalar()
                or 0
            )
            available_count = (
                model.select(fn.COUNT(model.EntryId))
                .where(
                    (model.Monitored == True)  # noqa: E712
                    & (model.MovieFileId.is_null(False))
                    & (model.MovieFileId != 0)
                )
                .scalar()
                or 0
            )
            query = base_query
            if search:
                query = query.where(model.Title.contains(search))
            total = query.count()
            page_items = query.order_by(model.Title.asc()).paginate(page + 1, page_size).iterator()
            movies = []
            for movie in page_items:
                movies.append(
                    {
                        "id": movie.EntryId,
                        "title": movie.Title or "",
                        "year": movie.Year,
                        "monitored": self._safe_bool(movie.Monitored),
                        "hasFile": self._safe_bool(movie.MovieFileId),
                    }
                )
        return {
            "counts": {"available": available_count, "monitored": monitored_count},
            "total": total,
            "page": page,
            "page_size": page_size,
            "movies": movies,
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
        missing_condition = episodes_model.EpisodeFileId.is_null(True) | (
            episodes_model.EpisodeFileId == 0
        )
        with db.connection_context():
            monitored_count = (
                episodes_model.select(fn.COUNT(episodes_model.EntryId))
                .where(episodes_model.Monitored == True)  # noqa: E712
                .scalar()
                or 0
            )
            available_count = (
                episodes_model.select(fn.COUNT(episodes_model.EntryId))
                .where(
                    (episodes_model.Monitored == True)  # noqa: E712
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
                    .where((episodes_model.Monitored == True) & missing_condition)  # noqa: E712
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
                series_query = series_model.select()
                if search:
                    series_query = series_query.where(series_model.Title.contains(search))
                if missing_only and missing_series_ids:
                    series_query = series_query.where(series_model.EntryId.in_(missing_series_ids))
                total_series = series_query.count()
                if total_series:
                    max_pages = (total_series + page_size - 1) // page_size
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
                            episodes_model.SeriesId == series.EntryId
                        )
                        if missing_only:
                            episodes_query = episodes_query.where(missing_condition)
                        episodes_query = episodes_query.order_by(
                            episodes_model.SeasonNumber.asc(),
                            episodes_model.EpisodeNumber.asc(),
                        )
                        episodes = episodes_query.iterator()
                        seasons: dict[str, dict[str, Any]] = {}
                        series_monitored = 0
                        series_available = 0
                        for ep in episodes:
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
                        payload.append(
                            {
                                "series": {
                                    "id": getattr(series, "EntryId", None),
                                    "title": getattr(series, "Title", "") or "",
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
                base_episode_query = episodes_model.select()
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
                    episodes_query = episodes_model.select()
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
                    for ep in episodes_query.iterator():
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
                            },
                            "totals": {
                                "available": series_available,
                                "monitored": series_monitored,
                                "missing": series_missing,
                            },
                            "seasons": seasons,
                        }
                    )

        return {
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
            return redirect("/static/index.html")

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
            return sorted(f.name for f in logs_root.glob("*.log*"))

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
            # Return last 2000 lines
            try:
                content = file.read_text(encoding="utf-8", errors="ignore").splitlines()
                tail = "\n".join(content[-2000:])
            except Exception:
                tail = ""
            return send_file(io.BytesIO(tail.encode("utf-8")), mimetype="text/plain")

        @app.get("/web/logs/<name>")
        def web_log(name: str):
            file = _resolve_log_file(name)
            if file is None or not file.exists():
                return jsonify({"error": "not found"}), 404
            try:
                content = file.read_text(encoding="utf-8", errors="ignore").splitlines()
                tail = "\n".join(content[-2000:])
            except Exception:
                tail = ""
            return send_file(io.BytesIO(tail.encode("utf-8")), mimetype="text/plain")

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
            payload = self._radarr_movies_from_db(arr, q, page, page_size)
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
            payload = self._radarr_movies_from_db(arr, q, page, page_size)
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

        def _arr_list_payload() -> dict[str, Any]:
            items = []
            for k, arr in _managed_objects().items():
                t = getattr(arr, "type", None)
                if t in ("radarr", "sonarr"):
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

        def _status_payload() -> dict[str, Any]:
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
            arrs = []
            for k, arr in _managed_objects().items():
                t = getattr(arr, "type", None)
                if t in ("radarr", "sonarr"):
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
            return {"qbit": qb, "arrs": arrs, "ready": _ensure_arr_manager_ready()}

        @app.get("/api/status")
        def api_status():
            if (resp := require_token()) is not None:
                return resp
            return jsonify(_status_payload())

        @app.get("/web/status")
        def web_status():
            return jsonify(_status_payload())

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
                return jsonify(data)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @app.post("/api/config")
        def api_update_config():
            if (resp := require_token()) is not None:
                return resp
            body = request.get_json(silent=True) or {}
            changes: dict[str, Any] = body.get("changes", {})
            if not isinstance(changes, dict):
                return jsonify({"error": "changes must be an object"}), 400
            # Apply changes
            for key, val in changes.items():
                if val is None:
                    _toml_delete(CONFIG.config, key)
                    if key == "Settings.WebUIToken":
                        self.token = ""
                    continue
                _toml_set(CONFIG.config, key, val)
                if key == "Settings.WebUIToken":
                    # Update in-memory token immediately
                    self.token = str(val) if val is not None else ""
            # Persist
            CONFIG.save()
            try:
                self.manager.configure_auto_update()
            except Exception:
                self.logger.exception("Failed to refresh auto update configuration")
            # Live-reload: rebuild Arr instances and restart processes
            self._reload_all()
            return jsonify({"status": "ok"})

        @app.post("/web/config")
        def web_update_config():
            body = request.get_json(silent=True) or {}
            changes: dict[str, Any] = body.get("changes", {})
            if not isinstance(changes, dict):
                return jsonify({"error": "changes must be an object"}), 400
            for key, val in changes.items():
                if val is None:
                    _toml_delete(CONFIG.config, key)
                    if key == "Settings.WebUIToken":
                        self.token = ""
                    continue
                _toml_set(CONFIG.config, key, val)
                if key == "Settings.WebUIToken":
                    self.token = str(val) if val is not None else ""
            CONFIG.save()
            try:
                self.manager.configure_auto_update()
            except Exception:
                self.logger.exception("Failed to refresh auto update configuration")
            self._reload_all()
            return jsonify({"status": "ok"})

    def _reload_all(self):
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
            if self._should_use_dev_server():
                self.logger.info("Using Flask development server for WebUI")
                self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
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
            waitress_serve(
                self.app,
                host=self.host,
                port=self.port,
                ident="qBitrr-WebUI",
            )
        except Exception:  # pragma: no cover - defensive logging
            self.logger.exception("WebUI server terminated unexpectedly")

    def _should_use_dev_server(self) -> bool:
        if self._use_dev_server is not None:
            return self._use_dev_server
        override = os.environ.get("QBITRR_USE_DEV_SERVER", "")
        if override:
            self._use_dev_server = override.strip().lower() not in {"0", "false", "no", "off"}
            return self._use_dev_server
        self._use_dev_server = False
        return self._use_dev_server
