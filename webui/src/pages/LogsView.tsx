import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import { LazyLog } from "@melloware/react-logviewer";
import { getLogDownloadUrl, getLogTail, getLogs } from "../api/client";
import { useToast } from "../context/ToastContext";
import { useWebUI } from "../context/WebUIContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
import { CopyButton } from "../components/CopyButton";
import Select, { type CSSObjectWithLabel, type OptionProps, type StylesConfig } from "react-select";

interface LogOption {
  value: string;
  label: string;
}

const getSelectStyles = (isDark: boolean): StylesConfig<LogOption, false> => {
  return {
    control: (base: CSSObjectWithLabel) => ({
      ...base,
      background: isDark ? '#0f131a' : '#ffffff',
      color: isDark ? '#eaeef2' : '#1d1d1f',
      borderColor: isDark ? '#2a2f36' : '#d2d2d7',
      minHeight: '38px',
      boxShadow: 'none',
      '&:hover': {
        borderColor: isDark ? '#3a4149' : '#b8b8bd',
      }
    }),
    menu: (base: CSSObjectWithLabel) => ({
      ...base,
      background: isDark ? '#0f131a' : '#ffffff',
      borderColor: isDark ? '#2a2f36' : '#d2d2d7',
      border: `1px solid ${isDark ? '#2a2f36' : '#d2d2d7'}`,
    }),
    option: (base: CSSObjectWithLabel, state: OptionProps<LogOption, false>) => ({
      ...base,
      background: state.isFocused
        ? (isDark ? 'rgba(122, 162, 247, 0.15)' : 'rgba(0, 113, 227, 0.1)')
        : (isDark ? '#0f131a' : '#ffffff'),
      color: isDark ? '#eaeef2' : '#1d1d1f',
      '&:active': {
        background: isDark ? 'rgba(122, 162, 247, 0.25)' : 'rgba(0, 113, 227, 0.2)',
      }
    }),
    singleValue: (base: CSSObjectWithLabel) => ({
      ...base,
      color: isDark ? '#eaeef2' : '#1d1d1f',
    }),
    input: (base: CSSObjectWithLabel) => ({
      ...base,
      color: isDark ? '#eaeef2' : '#1d1d1f',
    }),
    placeholder: (base: CSSObjectWithLabel) => ({
      ...base,
      color: isDark ? '#9aa3ac' : '#6e6e73',
    }),
    menuList: (base: CSSObjectWithLabel) => ({
      ...base,
      padding: '4px',
    }),
  };
};

import RefreshIcon from "../icons/refresh-arrow.svg";
import DownloadIcon from "../icons/download.svg";
import LiveIcon from "../icons/live-streaming.svg";

interface LogsViewProps {
  active: boolean;
}

function describeError(reason: unknown, context: string): string {
  if (reason instanceof Error && reason.message) {
    return `${context}: ${reason.message}`;
  }
  if (typeof reason === "string" && reason.trim().length) {
    return `${context}: ${reason}`;
  }
  return context;
}

/** Number of lines to fetch per chunk for the log viewer; keeps load fast. */
const DEFAULT_LOG_TAIL_LINES = 2000;

export function LogsView({ active }: LogsViewProps): JSX.Element {
  const [files, setFiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("All.log");
  const [logContent, setLogContent] = useState<string>("");
  const [follow, setFollow] = useState(true);
  /** When true, poll for new log content every second; when false, only refresh on manual Refresh. */
  const [liveUpdates, setLiveUpdates] = useState(true);
  /** Number of lines we've loaded "above" the tail (for load-more). When 0, we only have the tail. */
  const [offsetFromEnd, setOffsetFromEnd] = useState(0);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMoreAbove, setHasMoreAbove] = useState(true);
  const lastLinesCountRef = useRef<number>(0);
  const { push } = useToast();
  const { theme } = useWebUI();
  const isDark = theme === 'dark';
  const selectStyles = useMemo(() => getSelectStyles(isDark), [isDark]);

  const loadList = useCallback(async () => {
    setLoadingList(true);
    try {
      const data = await getLogs();
      const list = data.files ?? [];
      setFiles(list);
      if (list.length) {
        setSelected((prev) => {
          // Keep current selection if it's still valid
          if (prev && list.includes(prev)) {
            return prev;
          }
          // Default to "All.log", fallback to first file if not available
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
    void loadList();
  }, [loadList]);

  const fetchLogContent = useCallback(
    async (showLoading: boolean = false, onlyIfTail: boolean = false) => {
      if (!selected) return;
      if (onlyIfTail && offsetFromEnd > 0) return;

      if (showLoading) setLoadingContent(true);
      try {
        const newContent = await getLogTail(selected, DEFAULT_LOG_TAIL_LINES, 0);
        const newLines = newContent.split("\n");
        const currentLinesCount = newLines.length;

        if (currentLinesCount !== lastLinesCountRef.current || !onlyIfTail) {
          setLogContent(newContent);
          lastLinesCountRef.current = currentLinesCount;
          if (!onlyIfTail) {
            setOffsetFromEnd(0);
            setHasMoreAbove(true);
          }
        }
      } catch (error) {
        push(describeError(error, `Failed to read ${selected}`), "error");
      } finally {
        if (showLoading) setLoadingContent(false);
      }
    },
    [selected, push, offsetFromEnd]
  );

  const loadMoreAbove = useCallback(async () => {
    if (!selected || loadingMore || !hasMoreAbove) return;
    const nextOffset = offsetFromEnd + DEFAULT_LOG_TAIL_LINES;
    setLoadingMore(true);
    try {
      const olderContent = await getLogTail(
        selected,
        DEFAULT_LOG_TAIL_LINES,
        nextOffset
      );
      if (olderContent.length === 0) {
        setHasMoreAbove(false);
      } else {
        setLogContent((prev) =>
          prev ? `${olderContent}\n${prev}` : olderContent
        );
        setOffsetFromEnd(nextOffset);
      }
    } catch (error) {
      push(
        describeError(error, `Failed to load older logs for ${selected}`),
        "error"
      );
    } finally {
      setLoadingMore(false);
    }
  }, [selected, offsetFromEnd, loadingMore, hasMoreAbove, push]);

  const handleRefreshLogs = useCallback(() => {
    void fetchLogContent(true, false);
  }, [fetchLogContent]);

  useEffect(() => {
    if (selected) {
      lastLinesCountRef.current = 0;
      setOffsetFromEnd(0);
      setHasMoreAbove(true);
      void fetchLogContent(true);
    }
  }, [selected, fetchLogContent]);

  useInterval(
    () => {
      void fetchLogContent(false, true);
    },
    active && liveUpdates ? 1000 : null
  );



  return (
    <section className="card" style={{ height: 'calc(100vh - 140px)', display: 'flex', flexDirection: 'column', margin: 0, padding: 0 }}>
      <div className="card-header" style={{ flexShrink: 0 }}>Logs</div>
      <div className="card-body" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: '12px' }}>
        <div className="row" style={{ flexShrink: 0, marginBottom: '12px' }}>
          <div className="col field">
            <div className="field">
              <label>Log File</label>
              <Select
                options={files.map(f => ({ value: f, label: f }))}
                value={selected ? { value: selected, label: selected } : null}
                onChange={(option) => setSelected(option?.value || "")}
                isDisabled={!files.length}
                styles={selectStyles}
              />
            </div>
          </div>
          <div className="col field">
            <label>&nbsp;</label>
            <div className="row" style={{ alignItems: "center" }}>
              <button className="btn ghost" onClick={() => void loadList()} disabled={loadingList}>
                <IconImage src={RefreshIcon} />
                Reload List
              </button>
              <button
                className="btn ghost"
                onClick={handleRefreshLogs}
                disabled={!selected || loadingContent}
              >
                <IconImage src={RefreshIcon} />
                Refresh
              </button>
              <button
                className="btn"
                onClick={() =>
                  selected && window.open(getLogDownloadUrl(selected), "_blank")
                }
                disabled={!selected}
              >
                <IconImage src={DownloadIcon} />
                Download
              </button>
              <CopyButton
                text={logContent}
                label="Copy Logs"
                onCopy={() => push("Logs copied to clipboard", "success")}
              />
              <label className="hint inline" style={{ cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={liveUpdates}
                  onChange={(e) => setLiveUpdates(e.target.checked)}
                />
                <IconImage src={LiveIcon} />
                <span>Live</span>
              </label>
              <label className="hint inline" style={{ cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={follow}
                  onChange={(event) => setFollow(event.target.checked)}
                />
                <span>Auto-scroll</span>
              </label>
            </div>
          </div>
        </div>
        <div style={{
          flex: 1,
          minHeight: 0,
          overflow: 'hidden',
          borderRadius: '4px',
          display: 'flex',
          flexDirection: 'column'
        }}>
          {loadingContent ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: isDark ? '#666' : '#999', backgroundColor: isDark ? '#0a0e14' : '#fafafa' }}>
              <span className="spinner" style={{ marginRight: '8px' }} />
              Loading logs...
            </div>
          ) : logContent ? (
            <>
              {hasMoreAbove && (
                <div style={{ flexShrink: 0, padding: '8px 12px', borderBottom: `1px solid ${isDark ? '#2a2f36' : '#e5e5e5'}`, backgroundColor: isDark ? '#0f131a' : '#f5f5f5' }}>
                  <button
                    type="button"
                    className="btn ghost"
                    onClick={() => void loadMoreAbove()}
                    disabled={loadingMore}
                  >
                    {loadingMore ? (
                      <>
                        <span className="spinner" style={{ marginRight: '6px' }} />
                        Loading…
                      </>
                    ) : (
                      'Load older logs'
                    )}
                  </button>
                </div>
              )}
              <div style={{ flex: 1, minHeight: 0 }}>
                <LazyLog
              text={logContent}
              follow={follow}
              enableSearch
              caseInsensitive
              selectableLines
              extraLines={1}
              style={{
                height: '100%',
                backgroundColor: isDark ? '#0a0e14' : '#fafafa',
                color: isDark ? '#e5e5e5' : '#1d1d1f',
                fontFamily: '"Cascadia Code", "Fira Code", "Consolas", "Monaco", monospace',
                fontSize: '13px',
                lineHeight: '1.5'
              }}
                />
              </div>
            </>
          ) : (
            <div style={{ color: isDark ? '#666' : '#999', backgroundColor: isDark ? '#0a0e14' : '#fafafa', padding: '16px' }}>Select a log file to view...</div>
          )}
        </div>
      </div>
    </section>
  );
}
