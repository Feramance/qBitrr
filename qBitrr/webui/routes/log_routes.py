"""Log list / tail / download WebUI routes."""

from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import jsonify, request, send_file

from qBitrr.logger import reconfigure_logging_from_config
from qBitrr.webui.config_toml import _toml_set

if TYPE_CHECKING:
    from qBitrr.webui.app import WebUI


def register_log_routes(
    webui: WebUI,
    *,
    _dual_route: Callable[..., Any],
    _resolve_log_file: Callable[[str], Path | None],
    logs_root: Path,
    _webui_mod: Callable[[], Any],
) -> None:
    """Register log listing, tail, download, and loglevel routes."""

    def _handle_loglevel():
        body = request.get_json(silent=True) or {}
        level = str(body.get("level", "INFO")).upper()
        valid = {"CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"}
        if level not in valid:
            return jsonify({"error": f"invalid level {level}"}), 400
        try:
            _toml_set(_webui_mod().CONFIG.config, "Settings.ConsoleLevel", level)
            _webui_mod().CONFIG.save()
        except Exception:
            webui.logger.debug("Failed to persist log level to config", exc_info=True)
        reconfigure_logging_from_config()
        return jsonify({"status": "ok", "level": level})

    @_dual_route("/loglevel", methods=("POST",))
    def loglevel():
        return _handle_loglevel()

    def _list_logs() -> list[str]:
        if not logs_root.exists():
            return []
        log_files = sorted(f.name for f in logs_root.glob("*.log*"))
        return log_files

    @_dual_route("/logs")
    def logs():
        return jsonify({"files": _list_logs()})

    def _read_tail(path: Path, n: int, offset: int = 0) -> str:
        """Read n lines from the end of the file, optionally skipping the last `offset` lines.
        So offset=0 returns the last n lines; offset=2000 returns the n lines before that.
        """
        if n <= 0:
            return ""
        to_read = n + offset
        if to_read <= 0:
            return ""
        try:
            size = path.stat().st_size
        except OSError:
            return ""
        if size == 0:
            return ""
        chunk_size = 65536
        with path.open("rb") as f:
            buf = b""
            pos = size
            while pos > 0:
                read_size = min(chunk_size, pos)
                pos -= read_size
                f.seek(pos)
                buf = f.read(read_size) + buf
                text = buf.decode("utf-8", errors="ignore")
                if text.count("\n") + (1 if text.rstrip("\n") else 0) >= to_read:
                    break
            text = buf.decode("utf-8", errors="ignore")
        lines = text.splitlines()
        total = len(lines)
        if total <= offset:
            return ""
        # Return the n lines ending at (end - offset): lines[-(offset+n):-offset] or lines[-n:] when offset==0
        start = -(offset + n) if (offset + n) <= total else 0
        end = -offset if offset > 0 else total
        if start >= end:
            return ""
        return "\n".join(lines[start:end])

    def _serve_log_content(name: str):
        file = _resolve_log_file(name)
        if file is None or not file.exists():
            return jsonify({"error": "not found"}), 404
        lines_param = request.args.get("lines", type=int)
        offset_param = request.args.get("offset", default=0, type=int)
        try:
            if lines_param is not None and lines_param > 0:
                content = _read_tail(
                    file,
                    min(lines_param, 50000),
                    offset=max(0, offset_param),
                )
            else:
                content = file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            webui.logger.debug("Failed to read log file %s", file, exc_info=True)
            content = ""
        response = send_file(
            io.BytesIO(content.encode("utf-8")),
            mimetype="text/plain",
            as_attachment=False,
        )
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
        response.headers["Cache-Control"] = "no-cache"
        return response

    @_dual_route("/logs/<name>")
    def log(name: str):
        return _serve_log_content(name)

    def _log_download(name: str):
        file = _resolve_log_file(name)
        if file is None or not file.exists():
            return jsonify({"error": "not found"}), 404
        return send_file(file, as_attachment=True)

    @_dual_route("/logs/<name>/download")
    def log_download(name: str):
        return _log_download(name)
