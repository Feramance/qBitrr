# Logs View

The **Logs View** provides real-time streaming and searching of qBitrr log files. Select a log file, follow live appends over SSE (with poll fallback), filter by level, and search across the current file and rotated siblings.

---

## Overview

qBitrr generates structured logs for all major components:

- **All.log**: Aggregated events from the supervisor, WebUI, and Arr workers (default selection)
- **Main.log**: Core application events, initialization, shutdown
- **WebUI.log**: Flask/Waitress HTTP server logs, API requests
- **\<ArrName\>.log**: Per-instance logs (e.g., `Radarr-Movies.log`, `Sonarr-TV.log`)
- **Rotated logs**: Renamed on restart (e.g., `Main.log.old`) and other `*.log*` siblings

The Logs view provides:

- **Live streaming**: SSE byte-cursor stream when Live is on; falls back to JSON delta polling (~1.8s)
- **File selection** (required): Dropdown of all `*.log*` files under the logs directory
- **In-buffer search**: LazyLog find / next-prev on the loaded window
- **Server search**: Full-file (+ optional rotated) search with jump-to-context
- **Level chips**: Client-side filter of the loaded buffer (ERROR, WARNING, …)
- **Follow / Jump to latest**: Auto-scroll with pause-on-scroll-up
- **Download / Copy**: Export the selected file or copy the loaded buffer

---

## UI Components

### Log File Selector

**Location**: Top toolbar → dropdown (leftmost)

Selecting a file resets the live stream cursor, ring buffer, follow state, and search results.

**Default Selection**: `All.log` (falls back to the first available file)

### Live / Follow

| Control | Behavior |
|---------|----------|
| **Live** | Opens SSE to `/web/logs/<name>/stream` (session cookie). Status shows `Live (SSE)` or `Live (poll)` after fallback. |
| **Follow** | Auto-scrolls to bottom. Scrolling up turns Follow off. |
| **Jump to latest** | Reloads the live tail window and re-enables Follow. |
| **Load older logs** | Prepends the previous 2000-line window; pauses live until Jump/Refresh. |

Live updates only run when the Logs tab is active, Live is on, and you are at the live tail (not browsing older history).

### Level chips

Toggle one or more levels to filter the **in-memory** buffer before display. Clear filters restores the full buffer. Matching uses the logger's `LEVEL:` token (ANSI stripped).

### Server search

**Location**: Search row below the level chips

1. Enter a query and optionally enable **Include rotated**
2. Click **Search file** (or press Enter)
3. Results list file, line number, and snippet
4. Click a match to open a ~200-line window around that line (switches file if the hit is in a rotated sibling)

Use LazyLog's built-in search (Ctrl/Cmd-F style within the viewer) for fast find inside the current buffer only.

### Status line

Shows selected file · buffer line count · `Live (SSE)` / `Live (poll)` / `Paused` / `Paused (history)`.

---

## Live transport

```text
Select file → GET JSON tail (lines=2000)
           → EventSource /web/logs/<name>/stream?since_bytes=&inode=
           → on failure → GET JSON delta polling (same payload shape)
```

- Initial and delta responses are JSON (`format=json` or `since_bytes=`):

```json
{
  "content": "...",
  "next_bytes": 123456,
  "size": 123456,
  "inode": 42,
  "rotated": false,
  "truncated": false
}
```

- SSE events: `append`, `rotated`, `ping` (~15s), `reconnect` (~5 minutes — client reconnects with the last cursor).
- Client ring buffer caps at **20,000** lines while live (oldest dropped).
- **Auth**: EventSource uses the `/web/*` session cookie (cannot set `Authorization`). Prefer `/web/logs/.../stream` for the SPA.

---

## Log Format

qBitrr file handlers use ColoredFormatter with a pattern similar to:

```text
[%(asctime)-15s] %(levelname)-8s: %(name)s: %(message)s
```

Example (ANSI omitted):

```text
[2025-11-27 10:30:15] INFO    : qBitrr.Main: Starting qBitrr
```

Levels include TRACE, DEBUG, INFO, NOTICE, SUCCESS, WARNING, ERROR, CRITICAL. Configure via:

```toml
[Settings]
ConsoleLevel = "INFO"
```

On restart, active logs are renamed to `*.log.old` (not size-based `RotatingFileHandler` backups).

---

## API Endpoints

All routes below have `/api` and `/web` mirrors and require authentication when WebUI auth is enabled.

### GET /api/logs

List log filenames: `{ "files": ["All.log", "Main.log", ...] }`.

### GET /api/logs/\<name\>

| Query | Description |
|-------|-------------|
| `format=json` | Return `LogTailPayload` JSON |
| `lines` | Tail window size (default 2000, max 50000) |
| `offset` | Skip this many lines from the end (load older) |
| `since_bytes` | Incremental append from this byte offset |
| `inode` | Detect rotation when inode changes |
| `around_line` | Return a window centered on this 1-based line |

Without `format=json` / `since_bytes`, legacy plain-text responses remain available.

### GET /api/logs/\<name\>/stream

SSE live tail. Query: `since_bytes`, `inode`, `lines`. Prefer `/web/...` with a session for browsers.

### GET /api/logs/\<name\>/search

| Query | Description |
|-------|-------------|
| `q` | Search string (required) |
| `case` | `1` for case-sensitive |
| `regex` | `1` to treat `q` as regex |
| `max_matches` | Default 200, hard max 1000 |
| `context` | Context lines before/after (default 2) |
| `include_rotated` | `1` (default) to include `name*` siblings |

Response:

```json
{
  "query": "connection refused",
  "truncated": false,
  "matches": [
    {
      "file": "Main.log",
      "line": 10422,
      "text": "...",
      "context_before": ["..."],
      "context_after": ["..."]
    }
  ],
  "files_searched": ["Main.log", "Main.log.old"]
}
```

### GET /api/logs/\<name\>/download

Download the full file as an attachment.

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| Live stuck / no new lines | Confirm Live is on, Follow/Jump to latest, and status is not `Paused (history)` |
| Always `Live (poll)` | Proxy may buffer SSE; polling fallback is expected and still incremental |
| Stream 401 | Use session login for `/web/*`; do not put tokens in EventSource query strings |
| Search misses | Enable **Include rotated**; raise log level if messages were never written |
| Empty file list | Ensure the process can read `HOME_PATH/logs` (Docker: `/config/logs`) |

---

## Related

- [API reference](api.md) — endpoint details
- [Debug logging](../troubleshooting/debug-logging.md) — ConsoleLevel and verbose diagnostics
