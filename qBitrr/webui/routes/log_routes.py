"""Log list / tail / delta / stream / search / download WebUI routes."""

from __future__ import annotations

import io
import json
import re
import time
from collections import deque
from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Response, jsonify, request, send_file, stream_with_context

from qBitrr.logger import reconfigure_logging_from_config
from qBitrr.webui.config_toml import _toml_set

if TYPE_CHECKING:
    from qBitrr.webui.app import WebUI

_DEFAULT_TAIL_LINES = 2000
_MAX_TAIL_LINES = 50_000
_MAX_DELTA_BYTES = 2 * 1024 * 1024
_SSE_POLL_SECONDS = 0.35
_SSE_PING_SECONDS = 15.0
_SSE_MAX_SECONDS = 300.0
_SEARCH_MAX_MATCHES_DEFAULT = 200
_SEARCH_MAX_MATCHES_HARD = 1000
_SEARCH_MAX_BYTES = 80 * 1024 * 1024
_SEARCH_MAX_SECONDS = 8.0
_SEARCH_CONTEXT_HARD = 10
_REGEX_PATTERN_MAX = 256


def register_log_routes(
    webui: WebUI,
    *,
    _dual_route: Callable[..., Any],
    _resolve_log_file: Callable[[str], Path | None],
    logs_root: Path,
    _webui_mod: Callable[[], Any],
) -> None:
    """Register log listing, tail, stream, search, download, and loglevel routes."""

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
        return sorted(f.name for f in logs_root.glob("*.log*"))

    @_dual_route("/logs")
    def logs():
        return jsonify({"files": _list_logs()})

    def _stat_meta(path: Path) -> tuple[int, int]:
        """Return (size, inode) for a log file; inode 0 when unavailable."""
        try:
            st = path.stat()
        except OSError:
            return 0, 0
        inode = int(getattr(st, "st_ino", 0) or 0)
        return int(st.st_size), inode

    def _read_tail(path: Path, n: int, offset: int = 0) -> str:
        """Read n lines from the end, optionally skipping the last `offset` lines."""
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
        start = -(offset + n) if (offset + n) <= total else 0
        end = -offset if offset > 0 else total
        if start >= end:
            return ""
        return "\n".join(lines[start:end])

    def _read_around_line(path: Path, line_no: int, window: int) -> tuple[str, bool]:
        """Return a window of lines around 1-based line_no. truncated if file huge."""
        if line_no < 1 or window < 1:
            return "", False
        before = window // 2
        after = window - before
        start_idx = max(0, line_no - 1 - before)
        end_idx = line_no - 1 + after
        collected: list[str] = []
        truncated = False
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for idx, line in enumerate(f):
                    if idx < start_idx:
                        continue
                    if idx > end_idx:
                        break
                    collected.append(line.rstrip("\n"))
                else:
                    pass
                # If we never reached start_idx, file was shorter
        except OSError:
            return "", False
        # Detect truncation only when requesting a large window from a huge file
        if end_idx - start_idx + 1 > window and len(collected) >= window:
            truncated = True
        return "\n".join(collected), truncated

    def _read_delta(path: Path, since_bytes: int) -> tuple[str, int, bool]:
        """Read new bytes from since_bytes to EOF. Returns (text, next_bytes, truncated)."""
        size, _ = _stat_meta(path)
        if since_bytes < 0:
            since_bytes = 0
        if since_bytes >= size:
            return "", size, False
        to_read = size - since_bytes
        truncated = False
        if to_read > _MAX_DELTA_BYTES:
            # Prefer the newest bytes when capping
            since_bytes = size - _MAX_DELTA_BYTES
            to_read = _MAX_DELTA_BYTES
            truncated = True
        try:
            with path.open("rb") as f:
                f.seek(since_bytes)
                data = f.read(to_read)
        except OSError:
            return "", size, False
        text = data.decode("utf-8", errors="ignore")
        # Drop a partial first line when we truncated from the middle
        if truncated and text:
            nl = text.find("\n")
            if nl >= 0:
                text = text[nl + 1 :]
        return text, size, truncated

    def _tail_payload(
        path: Path,
        *,
        lines: int | None = None,
        offset: int = 0,
        since_bytes: int | None = None,
        inode: int | None = None,
        around_line: int | None = None,
    ) -> dict[str, Any]:
        size, current_inode = _stat_meta(path)
        lines_n = min(lines or _DEFAULT_TAIL_LINES, _MAX_TAIL_LINES)
        offset_n = max(0, offset)

        if since_bytes is not None:
            rotated = False
            if inode is not None and inode > 0 and current_inode > 0 and inode != current_inode:
                rotated = True
            elif since_bytes > size:
                rotated = True
            if rotated:
                content = _read_tail(path, lines_n, 0)
                return {
                    "content": content,
                    "next_bytes": size,
                    "size": size,
                    "inode": current_inode,
                    "rotated": True,
                    "truncated": False,
                }
            content, next_bytes, truncated = _read_delta(path, since_bytes)
            return {
                "content": content,
                "next_bytes": next_bytes,
                "size": size,
                "inode": current_inode,
                "rotated": False,
                "truncated": truncated,
            }

        if around_line is not None and around_line > 0:
            content, truncated = _read_around_line(path, around_line, lines_n)
            return {
                "content": content,
                "next_bytes": size,
                "size": size,
                "inode": current_inode,
                "rotated": False,
                "truncated": truncated,
            }

        content = _read_tail(path, lines_n, offset_n)
        return {
            "content": content,
            "next_bytes": size,
            "size": size,
            "inode": current_inode,
            "rotated": False,
            "truncated": False,
        }

    def _wants_json() -> bool:
        if request.args.get("format", "").lower() == "json":
            return True
        if request.args.get("since_bytes", type=int) is not None:
            return True
        accept = (request.headers.get("Accept") or "").lower()
        return "application/json" in accept and "text/plain" not in accept

    def _serve_log_content(name: str):
        file = _resolve_log_file(name)
        if file is None or not file.exists():
            return jsonify({"error": "not found"}), 404

        lines_param = request.args.get("lines", type=int)
        offset_param = request.args.get("offset", default=0, type=int)
        since_param = request.args.get("since_bytes", type=int)
        inode_param = request.args.get("inode", type=int)
        around_param = request.args.get("around_line", type=int)

        try:
            if _wants_json() or since_param is not None or around_param is not None:
                payload = _tail_payload(
                    file,
                    lines=lines_param,
                    offset=max(0, offset_param or 0),
                    since_bytes=since_param,
                    inode=inode_param,
                    around_line=around_param,
                )
                response = jsonify(payload)
                response.headers["Cache-Control"] = "no-cache"
                return response

            if lines_param is not None and lines_param > 0:
                content = _read_tail(
                    file,
                    min(lines_param, _MAX_TAIL_LINES),
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

    def _sse_format(event: str, payload: dict[str, Any] | None = None) -> str:
        data = json.dumps(payload if payload is not None else {}, separators=(",", ":"))
        return f"event: {event}\ndata: {data}\n\n"

    def _stream_log(name: str):
        file = _resolve_log_file(name)
        if file is None or not file.exists():
            return jsonify({"error": "not found"}), 404

        since_bytes = request.args.get("since_bytes", type=int)
        inode_param = request.args.get("inode", type=int)
        lines_param = request.args.get("lines", type=int) or _DEFAULT_TAIL_LINES

        if since_bytes is None:
            size, inode = _stat_meta(file)
            since_bytes = size
            inode_param = inode

        def generate() -> Generator[str]:
            cursor = int(since_bytes or 0)
            known_inode = int(inode_param or 0)
            started = time.monotonic()
            last_ping = started
            while time.monotonic() - started < _SSE_MAX_SECONDS:
                if not file.exists():
                    yield _sse_format(
                        "rotated",
                        {
                            "content": "",
                            "next_bytes": 0,
                            "size": 0,
                            "inode": 0,
                            "rotated": True,
                            "truncated": False,
                        },
                    )
                    return
                size, current_inode = _stat_meta(file)
                rotated = False
                if known_inode > 0 and current_inode > 0 and known_inode != current_inode:
                    rotated = True
                elif cursor > size:
                    rotated = True
                if rotated:
                    payload = _tail_payload(file, lines=lines_param, since_bytes=None)
                    cursor = int(payload["next_bytes"])
                    known_inode = int(payload["inode"])
                    yield _sse_format("rotated", payload)
                elif size > cursor:
                    payload = _tail_payload(
                        file,
                        lines=lines_param,
                        since_bytes=cursor,
                        inode=known_inode,
                    )
                    cursor = int(payload["next_bytes"])
                    known_inode = int(payload["inode"])
                    if payload.get("content"):
                        yield _sse_format("append", payload)
                now = time.monotonic()
                if now - last_ping >= _SSE_PING_SECONDS:
                    yield _sse_format("ping", {"ts": int(now)})
                    last_ping = now
                time.sleep(_SSE_POLL_SECONDS)
            yield _sse_format(
                "reconnect",
                {
                    "next_bytes": cursor,
                    "inode": known_inode,
                },
            )

        response = Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
        )
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        response.headers["Connection"] = "keep-alive"
        return response

    @_dual_route("/logs/<name>/stream")
    def log_stream(name: str):
        return _stream_log(name)

    def _sibling_log_files(name: str, *, include_rotated: bool) -> list[Path]:
        primary = _resolve_log_file(name)
        files: list[Path] = []
        seen: set[str] = set()
        if primary is not None and primary.exists():
            files.append(primary)
            seen.add(primary.name)
        if not include_rotated or not logs_root.exists():
            return files
        # Match Main.log, Main.log.old, Main.log.2025-01-01, etc.
        for candidate in logs_root.glob(f"{name}*"):
            if not candidate.is_file() or candidate.name in seen:
                continue
            resolved = _resolve_log_file(candidate.name)
            if resolved is None or not resolved.exists():
                continue
            files.append(resolved)
            seen.add(resolved.name)
        # Primary first, then newest mtime
        primary_name = primary.name if primary is not None else name

        def sort_key(path: Path) -> tuple[int, float, str]:
            is_primary = 0 if path.name == primary_name else 1
            try:
                mtime = -path.stat().st_mtime
            except OSError:
                mtime = 0.0
            return (is_primary, mtime, path.name)

        files.sort(key=sort_key)
        return files

    def _compile_matcher(
        query: str, *, case_sensitive: bool, use_regex: bool
    ) -> tuple[Callable[[str], bool] | None, str | None]:
        if not query:
            return None, "query is required"
        if use_regex:
            if len(query) > _REGEX_PATTERN_MAX:
                return None, "regex pattern too long"
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                pattern = re.compile(query, flags)
            except re.error as exc:
                return None, f"invalid regex: {exc}"
            return (lambda line: pattern.search(line) is not None), None
        needle = query if case_sensitive else query.lower()

        def literal_match(line: str) -> bool:
            hay = line if case_sensitive else line.lower()
            return needle in hay

        return literal_match, None

    def _search_files(
        files: list[Path],
        matcher: Callable[[str], bool],
        *,
        max_matches: int,
        context: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        matches: list[dict[str, Any]] = []
        truncated = False
        bytes_scanned = 0
        started = time.monotonic()
        context_n = max(0, min(context, _SEARCH_CONTEXT_HARD))

        for path in files:
            if len(matches) >= max_matches:
                truncated = True
                break
            if bytes_scanned >= _SEARCH_MAX_BYTES:
                truncated = True
                break
            if time.monotonic() - started >= _SEARCH_MAX_SECONDS:
                truncated = True
                break
            before_buf: deque[str] = deque(maxlen=context_n or 1)
            pending_after = 0
            last_match: dict[str, Any] | None = None
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as f:
                    for line_no, raw in enumerate(f, start=1):
                        if time.monotonic() - started >= _SEARCH_MAX_SECONDS:
                            truncated = True
                            break
                        line = raw.rstrip("\n")
                        bytes_scanned += len(raw.encode("utf-8", errors="ignore"))
                        if bytes_scanned >= _SEARCH_MAX_BYTES:
                            truncated = True
                            break

                        if pending_after > 0 and last_match is not None:
                            last_match["context_after"].append(line)
                            pending_after -= 1
                            if pending_after == 0:
                                last_match = None

                        if matcher(line):
                            if len(matches) >= max_matches:
                                truncated = True
                                break
                            entry: dict[str, Any] = {
                                "file": path.name,
                                "line": line_no,
                                "text": line,
                                "context_before": (
                                    list(before_buf)[-context_n:] if context_n else []
                                ),
                                "context_after": [],
                            }
                            matches.append(entry)
                            last_match = entry
                            pending_after = context_n
                        if context_n:
                            before_buf.append(line)
            except OSError:
                webui.logger.debug("Failed to search log file %s", path, exc_info=True)
                continue
        return matches, truncated

    def _search_log(name: str):
        file = _resolve_log_file(name)
        if file is None:
            return jsonify({"error": "not found"}), 404

        query = (request.args.get("q") or "").strip()
        case_sensitive = request.args.get("case", default="0") in {"1", "true", "True"}
        use_regex = request.args.get("regex", default="0") in {"1", "true", "True"}
        include_rotated = request.args.get("include_rotated", default="1") not in {
            "0",
            "false",
            "False",
        }
        max_matches = request.args.get("max_matches", type=int) or _SEARCH_MAX_MATCHES_DEFAULT
        max_matches = max(1, min(max_matches, _SEARCH_MAX_MATCHES_HARD))
        context = request.args.get("context", type=int)
        if context is None:
            context = 2
        context = max(0, min(context, _SEARCH_CONTEXT_HARD))

        matcher, err = _compile_matcher(query, case_sensitive=case_sensitive, use_regex=use_regex)
        if err or matcher is None:
            return jsonify({"error": err or "invalid query"}), 400

        files = _sibling_log_files(name, include_rotated=include_rotated)
        if not files:
            return jsonify({"error": "not found"}), 404

        matches, truncated = _search_files(
            files, matcher, max_matches=max_matches, context=context
        )
        return jsonify(
            {
                "query": query,
                "truncated": truncated,
                "matches": matches,
                "files_searched": [p.name for p in files],
            }
        )

    @_dual_route("/logs/<name>/search")
    def log_search(name: str):
        return _search_log(name)

    def _log_download(name: str):
        file = _resolve_log_file(name)
        if file is None or not file.exists():
            return jsonify({"error": "not found"}), 404
        return send_file(file, as_attachment=True)

    @_dual_route("/logs/<name>/download")
    def log_download(name: str):
        return _log_download(name)
