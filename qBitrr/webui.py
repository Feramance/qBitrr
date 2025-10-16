from __future__ import annotations

import io
import logging
import threading
from typing import Any

from flask import Flask, jsonify, redirect, request, send_file

from qBitrr.config import CONFIG, HOME_PATH


def _toml_set(doc, dotted_key: str, value: Any):
    keys = dotted_key.split(".")
    cur = doc
    for k in keys[:-1]:
        if k not in cur or not isinstance(cur[k], dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value


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
        # Security token (optional)
        self.token = CONFIG.get("Settings.WebUIToken", fallback=None)
        self._register_routes()
        self._thread: threading.Thread | None = None

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

        @app.post("/api/processes/restart_all")
        def api_restart_all():
            if (resp := require_token()) is not None:
                return resp
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

        @app.post("/api/arr/rebuild")
        def api_arr_rebuild():
            if (resp := require_token()) is not None:
                return resp
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
            movies = arr.client.get_movie()
            # Compute availability
            total_monitored = sum(1 for m in movies if m.get("monitored"))
            total_available = sum(1 for m in movies if m.get("monitored") and m.get("hasFile"))
            if q:
                ql = q.lower()
                movies = [m for m in movies if (m.get("title") or "").lower().find(ql) != -1]
            total = len(movies)
            start = max(0, page * page_size)
            end = start + page_size
            page_items = movies[start:end]
            return jsonify(
                {
                    "category": category,
                    "counts": {"available": total_available, "monitored": total_monitored},
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "movies": page_items,
                }
            )

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
            series = arr.client.get_series()
            if q:
                ql = q.lower()
                series = [s for s in series if (s.get("title") or "").lower().find(ql) != -1]
            payload = []
            total_mon = 0
            total_avail = 0
            total = len(series)
            start = max(0, page * page_size)
            end = start + page_size
            for s in series[start:end]:
                sid = s.get("id")
                eps = arr.client.get_episode(sid, includeAll=True)
                # Build seasons
                seasons = {}
                for e in eps:
                    if not e.get("monitored"):
                        continue
                    season = e.get("seasonNumber")
                    seasons.setdefault(season, {"monitored": 0, "available": 0, "episodes": []})
                    seasons[season]["monitored"] += 1
                    if e.get("hasFile"):
                        seasons[season]["available"] += 1
                    seasons[season]["episodes"].append(e)
                # aggregate per series
                s_mon = sum(v["monitored"] for v in seasons.values())
                s_avail = sum(v["available"] for v in seasons.values())
                total_mon += s_mon
                total_avail += s_avail
                payload.append(
                    {
                        "series": s,
                        "totals": {"available": s_avail, "monitored": s_mon},
                        "seasons": seasons,
                    }
                )
            return jsonify(
                {
                    "category": category,
                    "counts": {"available": total_avail, "monitored": total_mon},
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "series": payload,
                }
            )

        @app.get("/api/arr")
        def api_arr_list():
            items = []
            for k, arr in self.manager.arr_manager.managed_objects.items():
                t = getattr(arr, "type", None)
                if t in ("radarr", "sonarr"):
                    items.append({"category": k, "type": t})
            return jsonify({"arr": items})

        @app.get("/api/status")
        def api_status():
            qb = {
                "alive": bool(self.manager.is_alive),
                "host": self.manager.qBit_Host,
                "port": self.manager.qBit_Port,
                "version": str(self.manager.current_qbit_version)
                if self.manager.current_qbit_version
                else None,
            }
            arrs = []
            for k, arr in self.manager.arr_manager.managed_objects.items():
                t = getattr(arr, "type", None)
                if t in ("radarr", "sonarr"):
                    alive = False
                    try:
                        alive = (
                            bool(arr.is_alive())
                            if callable(getattr(arr, "is_alive", None))
                            else False
                        )
                    except Exception:
                        alive = False
                    arrs.append({"category": k, "type": t, "alive": alive})
            return jsonify({"qbit": qb, "arrs": arrs})

        @app.get("/api/token")
        def api_token():
            # Only allow local requests to read the token
            ra = request.remote_addr or ""
            if ra not in ("127.0.0.1", "::1"):
                return jsonify({"error": "forbidden"}), 403
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

        @app.get("/api/config")
        def api_get_config():
            if (resp := require_token()) is not None:
                return resp
            try:
                # Render current config as a JSON-able dict via tomlkit
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
                _toml_set(CONFIG.config, key, val)
                if key == "Settings.WebUIToken":
                    # Update in-memory token immediately
                    self.token = str(val) if val is not None else ""
            # Persist
            CONFIG.save()
            # Live-reload: rebuild Arr instances and restart processes
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
            return
        self._thread = threading.Thread(
            target=lambda: self.app.run(
                host=self.host, port=self.port, debug=False, use_reloader=False
            ),
            name="WebUI",
            daemon=True,
        )
        self._thread.start()
