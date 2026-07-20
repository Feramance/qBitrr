import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import { LazyLog } from "@melloware/react-logviewer";
import {
  getLogDelta,
  getLogDownloadUrl,
  getLogStreamUrl,
  getLogTailJson,
  getLogs,
  searchLogs,
} from "../api/client";
import type { LogSearchMatch, LogTailPayload } from "../api/types";
import { useToast } from "../context/ToastContext";
import { useWebUI } from "../context/WebUIContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
import { CopyButton } from "../components/CopyButton";
import Select from "react-select";
import { getSelectStyles } from "../config/reactSelectTheme";
import RefreshIcon from "../icons/refresh-arrow.svg";
import DownloadIcon from "../icons/download.svg";
import LiveIcon from "../icons/live-streaming.svg";

interface LogsViewProps {
  active: boolean;
}

type LiveTransport = "sse" | "poll";

const DEFAULT_LOG_TAIL_LINES = 2000;
const RING_BUFFER_MAX_LINES = 20_000;
const POLL_INTERVAL_MS = 1800;
const ANSI_CSI = new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, "g");
const LEVEL_OPTIONS = [
  "ERROR",
  "WARNING",
  "NOTICE",
  "INFO",
  "DEBUG",
  "TRACE",
  "CRITICAL",
  "SUCCESS",
] as const;

function describeError(reason: unknown, context: string): string {
  if (reason instanceof Error && reason.message) {
    return `${context}: ${reason.message}`;
  }
  if (typeof reason === "string" && reason.trim().length) {
    return `${context}: ${reason}`;
  }
  return context;
}

function splitLogLines(content: string): string[] {
  if (!content) {
    return [];
  }
  const lines = content.split("\n");
  if (lines.length > 0 && lines[lines.length - 1] === "") {
    lines.pop();
  }
  return lines;
}

function trimRingBuffer(lines: string[]): string[] {
  if (lines.length <= RING_BUFFER_MAX_LINES) {
    return lines;
  }
  return lines.slice(lines.length - RING_BUFFER_MAX_LINES);
}

/** Strip ANSI CSI sequences so level filters work on colored log files. */
function stripAnsi(text: string): string {
  return text.replace(ANSI_CSI, "");
}

function lineMatchesLevel(line: string, levels: Set<string>): boolean {
  if (levels.size === 0) {
    return true;
  }
  // Format: "[asctime] LEVEL   : logger: message"
  const plain = stripAnsi(line);
  for (const level of levels) {
    const re = new RegExp(`\\b${level}\\s*:`);
    if (re.test(plain)) {
      return true;
    }
  }
  return false;
}

export function LogsView({ active }: LogsViewProps): JSX.Element {
  const [files, setFiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("All.log");
  const [lines, setLines] = useState<string[]>([]);
  const [follow, setFollow] = useState(true);
  const [liveUpdates, setLiveUpdates] = useState(true);
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [transport, setTransport] = useState<LiveTransport>("sse");
  /** When true, use delta polling instead of SSE (after stream failures). */
  const [forcePoll, setForcePoll] = useState(false);
  const [offsetFromEnd, setOffsetFromEnd] = useState(0);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMoreAbove, setHasMoreAbove] = useState(true);
  const [levelFilters, setLevelFilters] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [includeRotated, setIncludeRotated] = useState(true);
  const [searching, setSearching] = useState(false);
  const [searchMatches, setSearchMatches] = useState<LogSearchMatch[]>([]);
  const [searchTruncated, setSearchTruncated] = useState(false);
  const [showSearchPanel, setShowSearchPanel] = useState(false);
  const [pendingScrollLine, setPendingScrollLine] = useState<number | null>(null);
  /** True after the initial JSON tail for the current file has loaded. */
  const [tailReady, setTailReady] = useState(false);

  const nextBytesRef = useRef(0);
  const inodeRef = useRef(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const sseFailCountRef = useRef(0);
  const selectedRef = useRef(selected);
  const liveUpdatesRef = useRef(liveUpdates);
  const activeRef = useRef(active);
  const offsetFromEndRef = useRef(offsetFromEnd);
  const forcePollRef = useRef(forcePoll);
  const openStreamRef = useRef<() => void>(() => {});
  const pendingMatchRef = useRef<LogSearchMatch | null>(null);

  const { push } = useToast();
  const { theme } = useWebUI();
  const isDark = theme === "dark";
  const selectStyles = useMemo(() => getSelectStyles(isDark), [isDark]);
  const [lazyLogEpoch, setLazyLogEpoch] = useState(0);
  const prevActiveRef = useRef(active);

  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);

  useEffect(() => {
    liveUpdatesRef.current = liveUpdates;
  }, [liveUpdates]);

  useEffect(() => {
    activeRef.current = active;
  }, [active]);

  useEffect(() => {
    offsetFromEndRef.current = offsetFromEnd;
  }, [offsetFromEnd]);

  useEffect(() => {
    forcePollRef.current = forcePoll;
  }, [forcePoll]);

  useEffect(() => {
    if (active && !prevActiveRef.current) {
      setLazyLogEpoch((prev) => prev + 1);
    }
    prevActiveRef.current = active;
  }, [active]);

  const atTailWindow = offsetFromEnd === 0;
  const liveActive =
    active && liveUpdates && atTailWindow && !!selected && tailReady;

  const closeStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const applyPayload = useCallback(
    (payload: LogTailPayload, mode: "replace" | "append") => {
      nextBytesRef.current = payload.next_bytes;
      inodeRef.current = payload.inode;
      const incoming = splitLogLines(payload.content);
      if (mode === "replace" || payload.rotated) {
        setLines(trimRingBuffer(incoming));
        setOffsetFromEnd(0);
        setHasMoreAbove(true);
        return;
      }
      if (incoming.length === 0) {
        return;
      }
      setLines((prev) => {
        // Handle partial first line continuation: if prev last line incomplete
        // and delta doesn't start with newline semantics — append as new lines.
        return trimRingBuffer([...prev, ...incoming]);
      });
    },
    []
  );

  const loadList = useCallback(async () => {
    setLoadingList(true);
    try {
      const data = await getLogs();
      const list = data.files ?? [];
      setFiles(list);
      if (list.length) {
        setSelected((prev) => {
          if (prev && list.includes(prev)) {
            return prev;
          }
          return list.find((file) => file === "All.log") ?? list[0];
        });
      } else {
        setSelected("");
      }
    } catch (error) {
      push(describeError(error, "Failed to refresh log list"), "error");
    } finally {
      setLoadingList(false);
    }
  }, [push]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void loadList();
    }, 0);
    return () => window.clearTimeout(id);
  }, [loadList]);

  const fetchTail = useCallback(
    async (showLoading: boolean = false) => {
      if (!selected) return;
      if (showLoading) setLoadingContent(true);
      try {
        const pending = pendingMatchRef.current;
        if (pending && pending.file === selected) {
          pendingMatchRef.current = null;
          const around = await getLogTailJson(selected, {
            lines: 200,
            aroundLine: pending.line,
          });
          applyPayload(around, "replace");
          setOffsetFromEnd(1);
          setFollow(false);
          setHasMoreAbove(true);
          setPendingScrollLine(100);
          setTailReady(true);
          closeStream();
        } else {
          const payload = await getLogTailJson(selected, {
            lines: DEFAULT_LOG_TAIL_LINES,
            offset: 0,
          });
          applyPayload(payload, "replace");
          setOffsetFromEnd(0);
          setHasMoreAbove(true);
          setPendingScrollLine(null);
          setTailReady(true);
        }
      } catch (error) {
        setTailReady(false);
        push(describeError(error, `Failed to read ${selected}`), "error");
      } finally {
        if (showLoading) setLoadingContent(false);
      }
    },
    [selected, applyPayload, push, closeStream]
  );

  const loadMoreAbove = useCallback(async () => {
    if (!selected || loadingMore || !hasMoreAbove) return;
    const nextOffset = offsetFromEnd + DEFAULT_LOG_TAIL_LINES;
    setLoadingMore(true);
    try {
      const payload = await getLogTailJson(selected, {
        lines: DEFAULT_LOG_TAIL_LINES,
        offset: nextOffset,
      });
      const older = splitLogLines(payload.content);
      if (older.length === 0) {
        setHasMoreAbove(false);
      } else {
        setLines((prev) => [...older, ...prev]);
        setOffsetFromEnd(nextOffset);
        // Pause live while browsing history
        closeStream();
      }
    } catch (error) {
      push(
        describeError(error, `Failed to load older logs for ${selected}`),
        "error"
      );
    } finally {
      setLoadingMore(false);
    }
  }, [
    selected,
    offsetFromEnd,
    loadingMore,
    hasMoreAbove,
    push,
    closeStream,
  ]);

  const pollDelta = useCallback(async () => {
    if (!selected || !atTailWindow) return;
    try {
      const payload = await getLogDelta(
        selected,
        nextBytesRef.current,
        inodeRef.current,
        DEFAULT_LOG_TAIL_LINES
      );
      applyPayload(payload, payload.rotated ? "replace" : "append");
      setTransport("poll");
    } catch {
      // Background delta polls must stay silent — transient failures spam toasts.
    }
  }, [selected, atTailWindow, applyPayload]);

  const openStream = useCallback(() => {
    if (!selected || offsetFromEndRef.current > 0) return;
    closeStream();
    if (forcePollRef.current) {
      setTransport("poll");
      return;
    }
    const fileName = selected;
    const url = getLogStreamUrl(
      fileName,
      nextBytesRef.current,
      inodeRef.current,
      DEFAULT_LOG_TAIL_LINES
    );
    const es = new EventSource(url, { withCredentials: true });
    eventSourceRef.current = es;
    setTransport("sse");

    const onPayload = (event: MessageEvent, mode: "append" | "replace") => {
      try {
        const payload = JSON.parse(String(event.data)) as LogTailPayload;
        if (selectedRef.current !== fileName) return;
        applyPayload(payload, mode);
        sseFailCountRef.current = 0;
        setTransport("sse");
      } catch {
        // ignore malformed events
      }
    };

    es.addEventListener("append", (event) => {
      onPayload(event as MessageEvent, "append");
    });
    es.addEventListener("rotated", (event) => {
      onPayload(event as MessageEvent, "replace");
    });
    es.addEventListener("reconnect", (event) => {
      try {
        const data = JSON.parse(String((event as MessageEvent).data)) as {
          next_bytes?: number;
          inode?: number;
        };
        if (typeof data.next_bytes === "number") {
          nextBytesRef.current = data.next_bytes;
        }
        if (typeof data.inode === "number") {
          inodeRef.current = data.inode;
        }
      } catch {
        // ignore
      }
      closeStream();
      window.setTimeout(() => {
        if (
          selectedRef.current === fileName &&
          liveUpdatesRef.current &&
          activeRef.current &&
          offsetFromEndRef.current === 0 &&
          !forcePollRef.current
        ) {
          openStreamRef.current();
        }
      }, 250);
    });
    es.onerror = () => {
      sseFailCountRef.current += 1;
      closeStream();
      if (sseFailCountRef.current >= 2) {
        setForcePoll(true);
        setTransport("poll");
      } else {
        window.setTimeout(() => {
          if (
            selectedRef.current === fileName &&
            liveUpdatesRef.current &&
            activeRef.current &&
            offsetFromEndRef.current === 0
          ) {
            openStreamRef.current();
          }
        }, 1000);
      }
    };
  }, [selected, closeStream, applyPayload]);

  useEffect(() => {
    openStreamRef.current = openStream;
  }, [openStream]);

  // Load content when file changes (defer setState out of the effect body)
  useEffect(() => {
    if (!selected) return;
    closeStream();
    nextBytesRef.current = 0;
    inodeRef.current = 0;
    sseFailCountRef.current = 0;
    const id = window.setTimeout(() => {
      setForcePoll(false);
      setTailReady(false);
      setLines([]);
      setSearchMatches([]);
      setPendingScrollLine(null);
      setOffsetFromEnd(0);
      setHasMoreAbove(true);
      void fetchTail(true);
    }, 0);
    return () => {
      window.clearTimeout(id);
      closeStream();
    };
  }, [selected, fetchTail, closeStream]);

  // Manage live transport (wait for initial tail so since_bytes is correct)
  useEffect(() => {
    if (!liveActive) {
      closeStream();
      return;
    }
    if (forcePoll) {
      return;
    }
    openStream();
    return () => {
      closeStream();
    };
  }, [liveActive, forcePoll, openStream, closeStream]);

  useInterval(
    () => {
      void pollDelta();
    },
    liveActive && (transport === "poll" || forcePoll) ? POLL_INTERVAL_MS : null
  );

  const handleRefreshLogs = useCallback(() => {
    setForcePoll(false);
    sseFailCountRef.current = 0;
    void fetchTail(true);
  }, [fetchTail]);

  const handleJumpToLatest = useCallback(() => {
    setFollow(true);
    setPendingScrollLine(null);
    setForcePoll(false);
    sseFailCountRef.current = 0;
    setOffsetFromEnd(0);
    void fetchTail(false);
  }, [fetchTail]);

  const handleScroll = useCallback(
    (args: { scrollTop: number; scrollHeight: number; clientHeight: number }) => {
      const distanceFromBottom =
        args.scrollHeight - args.scrollTop - args.clientHeight;
      if (distanceFromBottom > 80) {
        if (follow) setFollow(false);
      } else if (distanceFromBottom <= 24) {
        if (!follow) setFollow(true);
      }
    },
    [follow]
  );

  const toggleLevel = useCallback((level: string) => {
    setLevelFilters((prev) => {
      const next = new Set(prev);
      if (next.has(level)) {
        next.delete(level);
      } else {
        next.add(level);
      }
      return next;
    });
  }, []);

  const filteredText = useMemo(() => {
    const filtered =
      levelFilters.size === 0
        ? lines
        : lines.filter((line) => lineMatchesLevel(line, levelFilters));
    return filtered.join("\n");
  }, [lines, levelFilters]);

  const runServerSearch = useCallback(async () => {
    if (!selected || !searchQuery.trim()) return;
    setSearching(true);
    setShowSearchPanel(true);
    try {
      const result = await searchLogs(selected, {
        q: searchQuery.trim(),
        includeRotated,
        context: 2,
        maxMatches: 200,
      });
      setSearchMatches(result.matches);
      setSearchTruncated(result.truncated);
      if (result.matches.length === 0) {
        push("No matches found", "info");
      }
    } catch (error) {
      push(describeError(error, "Search failed"), "error");
    } finally {
      setSearching(false);
    }
  }, [selected, searchQuery, includeRotated, push]);

  const openSearchMatch = useCallback(
    async (match: LogSearchMatch) => {
      try {
        if (match.file !== selected) {
          pendingMatchRef.current = match;
          setSelected(match.file);
          return;
        }
        const payload = await getLogTailJson(selected, {
          lines: 200,
          aroundLine: match.line,
        });
        applyPayload(payload, "replace");
        setOffsetFromEnd(1);
        setFollow(false);
        setHasMoreAbove(true);
        setPendingScrollLine(100);
        closeStream();
      } catch (error) {
        push(describeError(error, "Failed to open match"), "error");
      }
    },
    [selected, applyPayload, closeStream, push]
  );

  const liveButtonLabel = liveUpdates
    ? atTailWindow
      ? "Live"
      : "Paused"
    : "Paused";

  const viewerText = filteredText || " ";

  return (
    <section className="card logs-view">
      <div className="card-header">Logs</div>
      <div className="card-body logs-view__body">
        <div className="logs-toolbar">
          <div className="logs-toolbar__file field">
            <label htmlFor="logs-file-select">Log File</label>
            <Select
              inputId="logs-file-select"
              options={files.map((f) => ({ value: f, label: f }))}
              value={selected ? { value: selected, label: selected } : null}
              onChange={(option) => {
                const next = option?.value || "";
                if (next !== selected) {
                  setSelected(next);
                }
              }}
              isDisabled={!files.length}
              styles={selectStyles}
            />
          </div>
          <div className="logs-toolbar__actions">
            <button
              type="button"
              className={`btn ${liveUpdates ? "" : "ghost"}`}
              onClick={() => setLiveUpdates((v) => !v)}
              title="Toggle live updates"
              aria-pressed={liveUpdates}
            >
              <IconImage src={LiveIcon} />
              <span
                className={`logs-live-dot ${
                  liveUpdates && atTailWindow ? "logs-live-dot--on" : ""
                }`}
              />
              {liveButtonLabel}
            </button>
            <label className="hint inline logs-toolbar__check">
              <input
                type="checkbox"
                checked={follow}
                onChange={(event) => setFollow(event.target.checked)}
              />
              <span>Follow</span>
            </label>
            <button
              type="button"
              className="btn ghost"
              onClick={() =>
                selected && window.open(getLogDownloadUrl(selected), "_blank")
              }
              disabled={!selected}
            >
              <IconImage src={DownloadIcon} />
              Download
            </button>
            <CopyButton
              text={filteredText}
              label="Copy Logs"
              onCopy={() => push("Logs copied to clipboard", "success")}
            />
            <div className="logs-toolbar__more">
              <button
                type="button"
                className="btn ghost"
                aria-expanded={showMoreMenu}
                aria-haspopup="menu"
                onClick={() => setShowMoreMenu((v) => !v)}
              >
                More
              </button>
              {showMoreMenu ? (
                <div className="logs-toolbar__more-menu" role="menu">
                  {!follow ? (
                    <button
                      type="button"
                      className="btn small ghost"
                      role="menuitem"
                      onClick={() => {
                        handleJumpToLatest();
                        setShowMoreMenu(false);
                      }}
                    >
                      Jump to latest
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="btn small ghost"
                    role="menuitem"
                    onClick={() => {
                      void loadList();
                      setShowMoreMenu(false);
                    }}
                    disabled={loadingList}
                  >
                    <IconImage src={RefreshIcon} />
                    Reload List
                  </button>
                  <button
                    type="button"
                    className="btn small ghost"
                    role="menuitem"
                    onClick={() => {
                      handleRefreshLogs();
                      setShowMoreMenu(false);
                    }}
                    disabled={!selected || loadingContent}
                  >
                    <IconImage src={RefreshIcon} />
                    Refresh
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </div>

        <div className="logs-toolbar__meta hint">
          <span>{selected || "No file"}</span>
          <span>·</span>
          <span>
            {lines.length.toLocaleString()} lines
            {levelFilters.size > 0 ? " (filtered)" : ""}
          </span>
        </div>

        <div className="logs-level-chips" role="group" aria-label="Log level filters">
          {LEVEL_OPTIONS.map((level) => {
            const activeChip = levelFilters.has(level);
            return (
              <button
                key={level}
                type="button"
                className={`logs-chip ${activeChip ? "logs-chip--active" : ""} logs-chip--${level.toLowerCase()}`}
                onClick={() => toggleLevel(level)}
                aria-pressed={activeChip}
              >
                {level}
              </button>
            );
          })}
          {levelFilters.size > 0 && (
            <button
              type="button"
              className="btn ghost logs-chip-clear"
              onClick={() => setLevelFilters(new Set())}
            >
              Clear filters
            </button>
          )}
        </div>

        <div className="logs-search-bar">
          <input
            className="logs-search-input"
            type="search"
            placeholder="Search log file on server…"
            title="Server-side search across the selected log file (and rotated files if enabled). Use the viewer's find control to search loaded lines only."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                void runServerSearch();
              }
            }}
            disabled={!selected}
          />
          <label className="hint inline logs-toolbar__check">
            <input
              type="checkbox"
              checked={includeRotated}
              onChange={(e) => setIncludeRotated(e.target.checked)}
            />
            <span>Include rotated</span>
          </label>
          <button
            type="button"
            className="btn"
            onClick={() => void runServerSearch()}
            disabled={!selected || !searchQuery.trim() || searching}
          >
            {searching ? "Searching…" : "Search file"}
          </button>
          <button
            type="button"
            className="btn ghost"
            onClick={() => setShowSearchPanel((v) => !v)}
            disabled={searchMatches.length === 0 && !showSearchPanel}
          >
            {showSearchPanel ? "Hide results" : "Show results"}
            {searchMatches.length > 0 ? ` (${searchMatches.length})` : ""}
          </button>
        </div>

        {showSearchPanel && (
          <div className="logs-search-results">
            {searchMatches.length === 0 ? (
              <div className="hint">No search results</div>
            ) : (
              <>
                {searchTruncated && (
                  <div className="hint logs-search-truncated">
                    Results truncated — refine your query for more precision.
                  </div>
                )}
                <ul className="logs-search-list">
                  {searchMatches.map((match) => (
                    <li key={`${match.file}:${match.line}:${match.text.slice(0, 40)}`}>
                      <button
                        type="button"
                        className="logs-search-match"
                        onClick={() => void openSearchMatch(match)}
                      >
                        <span className="logs-search-match__meta">
                          {match.file}:{match.line}
                        </span>
                        <code className="logs-search-match__text">{match.text}</code>
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}

        <div className="logs-viewer">
          {loadingContent && (
            <div className="logs-viewer__overlay">
              <span className="spinner" />
              Loading logs…
            </div>
          )}
          {hasMoreAbove && lines.length > 0 && (
            <div className="logs-viewer__older">
              <button
                type="button"
                className="btn ghost"
                onClick={() => void loadMoreAbove()}
                disabled={loadingMore}
              >
                {loadingMore ? (
                  <>
                    <span className="spinner" />
                    Loading…
                  </>
                ) : (
                  "Load older logs"
                )}
              </button>
            </div>
          )}
          {lines.length > 0 || loadingContent ? (
            <div className="logs-viewer__lazy">
              <LazyLog
                key={`${lazyLogEpoch}-${selected}`}
                text={viewerText}
                follow={follow}
                enableSearch
                enableSearchNavigation
                caseInsensitive
                selectableLines
                extraLines={1}
                scrollToLine={pendingScrollLine ?? undefined}
                onScroll={handleScroll}
                style={{
                  height: "100%",
                  backgroundColor: isDark ? "#0a0e14" : "#fafafa",
                  color: isDark ? "#e5e5e5" : "#1d1d1f",
                  fontFamily:
                    '"Cascadia Code", "Fira Code", "Consolas", "Monaco", monospace',
                  fontSize: "13px",
                  lineHeight: "1.5",
                }}
              />
            </div>
          ) : (
            <div className="logs-viewer__empty">
              {selected
                ? "This log file is empty."
                : "Select a log file to view…"}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
