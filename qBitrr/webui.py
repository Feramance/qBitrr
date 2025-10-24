from __future__ import annotations

import io
import logging
import secrets
import threading
from typing import Any

from flask import Flask, jsonify, redirect, request, send_file
from peewee import fn

from qBitrr.config import CONFIG, HOME_PATH
from qBitrr.logger import run_logs


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
        self._register_routes()
        self._thread: threading.Thread | None = None

    @staticmethod
    def _safe_bool(value: Any) -> bool:
        return bool(value) and str(value).lower() not in {"0", "false", "none"}

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
        self, arr, search: str | None, page: int, page_size: int
    ) -> dict[str, Any]:
        if not self._ensure_arr_db(arr):
            return {
                "counts": {"available": 0, "monitored": 0},
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
                "counts": {"available": 0, "monitored": 0},
                "total": 0,
                "page": max(page, 0),
                "page_size": max(page_size, 1),
                "series": [],
            }
        page = max(page, 0)
        page_size = max(page_size, 1)
        resolved_page = page
        with db.connection_context():
            monitored_count = (
                episodes_model.select(fn.COUNT(episodes_model.EntryId))
                .where(episodes_model.Monitored == True)  # noqa: E712
                .scalar()
                or 0
            )
            available_count = (
                episodes_model.select(fn.COUNT(episodes_model.EntryId))
                .where(episodes_model.EpisodeFileId.is_null(False))
                .scalar()
                or 0
            )
            payload: list[dict[str, Any]] = []
            total_series = 0

            if series_model is not None:
                series_query = series_model.select()
                if search:
                    series_query = series_query.where(series_model.Title.contains(search))
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
                        episodes = (
                            episodes_model.select()
                            .where(episodes_model.SeriesId == series.EntryId)
                            .order_by(
                                episodes_model.SeasonNumber.asc(),
                                episodes_model.EpisodeNumber.asc(),
                            )
                            .iterator()
                        )
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
                            season_bucket["episodes"].append(
                                {
                                    "episodeNumber": getattr(ep, "EpisodeNumber", None),
                                    "title": getattr(ep, "Title", "") or "",
                                    "monitored": is_monitored,
                                    "hasFile": has_file,
                                    "airDateUtc": air_value,
                                }
                            )
                        payload.append(
                            {
                                "series": {
                                    "id": getattr(series, "EntryId", None),
                                    "title": getattr(series, "Title", "") or "",
                                },
                                "totals": {
                                    "available": series_available,
                                    "monitored": series_monitored,
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
                            },
                            "seasons": seasons,
                        }
                    )

        return {
            "counts": {"available": available_count, "monitored": monitored_count},
            "total": total_series,
            "page": resolved_page,
            "page_size": page_size,
            "series": payload,
        }

    # Routes
    def _register_routes(self):
        app = self.app

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

        @app.get("/api/processes")
        def api_processes():
            procs = []
            for arr in self.manager.arr_manager.managed_objects.values():
                name = getattr(arr, "_name", "unknown")
                cat = getattr(arr, "category", name)
                for kind in ("search", "torrent"):
                    p = getattr(arr, f"process_{kind}_loop", None)
                    if p is None:
                        continue
                    try:
                        procs.append(
                            {
                                "category": cat,
                                "name": name,
                                "kind": kind,
                                "pid": getattr(p, "pid", None),
                                "alive": bool(p.is_alive()),
                            }
                        )
                    except Exception:
                        procs.append(
                            {
                                "category": cat,
                                "name": name,
                                "kind": kind,
                                "pid": getattr(p, "pid", None),
                                "alive": False,
                            }
                        )
            return jsonify({"processes": procs})

        # Unauthenticated UI endpoints (mirror of /api/* for first-party WebUI)
        @app.get("/web/processes")
        def web_processes():
            return api_processes()

        @app.post("/api/processes/<category>/<kind>/restart")
        def api_restart_process(category: str, kind: str):
            if (resp := require_token()) is not None:
                return resp
            kind = kind.lower()
            if kind not in ("search", "torrent", "all"):
                return jsonify({"error": "kind must be search, torrent or all"}), 400
            arr = self.manager.arr_manager.managed_objects.get(category)
            if arr is None:
                return jsonify({"error": f"Unknown category {category}"}), 404
            restarted = []
            for k in ("search", "torrent"):
                if kind != "all" and k != kind:
                    continue
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
                # Start a fresh process for this loop
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

        @app.post("/web/processes/<category>/<kind>/restart")
        def web_restart_process(category: str, kind: str):
            # Mirror restart without auth for UI
            return (
                api_restart_process.__wrapped__(category, kind)
                if hasattr(api_restart_process, "__wrapped__")
                else api_restart_process(category, kind)
            )

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

        @app.get("/api/logs")
        def api_logs():
            if (resp := require_token()) is not None:
                return resp
            logs_dir = HOME_PATH.joinpath("logs")
            files = []
            if logs_dir.exists():
                for f in logs_dir.glob("*.log*"):
                    files.append(f.name)
            return jsonify({"files": sorted(files)})

        @app.get("/web/logs")
        def web_logs():
            logs_dir = HOME_PATH.joinpath("logs")
            files = []
            if logs_dir.exists():
                for f in logs_dir.glob("*.log*"):
                    files.append(f.name)
            return jsonify({"files": sorted(files)})

        @app.get("/api/logs/<name>")
        def api_log(name: str):
            if (resp := require_token()) is not None:
                return resp
            logs_dir = HOME_PATH.joinpath("logs")
            file = logs_dir.joinpath(name)
            if not file.exists():
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
            logs_dir = HOME_PATH.joinpath("logs")
            file = logs_dir.joinpath(name)
            if not file.exists():
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
            logs_dir = HOME_PATH.joinpath("logs")
            file = logs_dir.joinpath(name)
            if not file.exists():
                return jsonify({"error": "not found"}), 404
            return send_file(file, as_attachment=True)

        @app.get("/web/logs/<name>/download")
        def web_log_download(name: str):
            logs_dir = HOME_PATH.joinpath("logs")
            file = logs_dir.joinpath(name)
            if not file.exists():
                return jsonify({"error": "not found"}), 404
            return send_file(file, as_attachment=True)

        @app.get("/api/radarr/<category>/movies")
        def api_radarr_movies(category: str):
            if (resp := require_token()) is not None:
                return resp
            arr = self.manager.arr_manager.managed_objects.get(category)
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
            # Mirror radarr movies without auth for UI
            arr = self.manager.arr_manager.managed_objects.get(category)
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
            arr = self.manager.arr_manager.managed_objects.get(category)
            if arr is None or getattr(arr, "type", None) != "sonarr":
                return jsonify({"error": f"Unknown sonarr category {category}"}), 404
            q = request.args.get("q", default=None, type=str)
            page = request.args.get("page", default=0, type=int)
            page_size = request.args.get("page_size", default=25, type=int)
            payload = self._sonarr_series_from_db(arr, q, page, page_size)
            payload["category"] = category
            return jsonify(payload)

        @app.get("/web/sonarr/<category>/series")
        def web_sonarr_series(category: str):
            arr = self.manager.arr_manager.managed_objects.get(category)
            if arr is None or getattr(arr, "type", None) != "sonarr":
                return jsonify({"error": f"Unknown sonarr category {category}"}), 404
            q = request.args.get("q", default=None, type=str)
            page = request.args.get("page", default=0, type=int)
            page_size = request.args.get("page_size", default=25, type=int)
            payload = self._sonarr_series_from_db(arr, q, page, page_size)
            payload["category"] = category
            return jsonify(payload)

        @app.get("/api/arr")
        def api_arr_list():
            items = []
            for k, arr in self.manager.arr_manager.managed_objects.items():
                t = getattr(arr, "type", None)
                if t in ("radarr", "sonarr"):
                    name = getattr(arr, "_name", k)
                    category = getattr(arr, "category", k)
                    items.append({"category": category, "name": name, "type": t})
            return jsonify({"arr": items})

        @app.get("/web/arr")
        def web_arr_list():
            return api_arr_list()

        @app.get("/api/status")
        def api_status():
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
            for k, arr in self.manager.arr_manager.managed_objects.items():
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
            return jsonify({"qbit": qb, "arrs": arrs})

        @app.get("/web/status")
        def web_status():
            return api_status()

        @app.get("/api/token")
        def api_token():
            # Expose token for API clients only; UI uses /web endpoints
            return jsonify({"token": self.token})

        @app.post("/api/arr/<section>/restart")
        def api_arr_restart(section: str):
            if (resp := require_token()) is not None:
                return resp
            # Section is the category key in managed_objects
            if section not in self.manager.arr_manager.managed_objects:
                return jsonify({"error": f"Unknown section {section}"}), 404
            arr = self.manager.arr_manager.managed_objects[section]
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
            if section not in self.manager.arr_manager.managed_objects:
                return jsonify({"error": f"Unknown section {section}"}), 404
            arr = self.manager.arr_manager.managed_objects[section]
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
        self._thread = threading.Thread(
            target=lambda: self.app.run(
                host=self.host, port=self.port, debug=False, use_reloader=False
            ),
            name="WebUI",
            daemon=True,
        )
        self._thread.start()
        self.logger.success("WebUI thread started (name=%s)", self._thread.name)
