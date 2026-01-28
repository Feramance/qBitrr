import { useCallback, useEffect, useRef, useState, type JSX } from "react";
import { LazyLog } from "@melloware/react-logviewer";
import { getConfig, getLogDownloadUrl, getLogs } from "../api/client";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
import { CopyButton } from "../components/CopyButton";
import Select, { type CSSObjectWithLabel, type OptionProps, type StylesConfig } from "react-select";

interface LogOption {
  value: string;
  label: string;
}

// Helper function for react-select theme-aware styles
const getSelectStyles = (): StylesConfig<LogOption, false> => {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
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

export function LogsView({ active }: LogsViewProps): JSX.Element {
  const [files, setFiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("All.log");
  const [logContent, setLogContent] = useState<string>("");
  const [follow, setFollow] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
  const [tokenReady, setTokenReady] = useState(false);
  const tokenRef = useRef<string>("");
  const lastLinesCountRef = useRef<number>(0);
  const { push } = useToast();

  const describeError = useCallback((reason: unknown, context: string): string => {
    if (reason instanceof Error && reason.message) {
      return `${context}: ${reason.message}`;
    }
    if (typeof reason === "string" && reason.trim().length) {
      return `${context}: ${reason}`;
    }
    return context;
  }, []);

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
  }, [describeError, push]);

  // Fetch and cache the WebUI token from config on mount
  useEffect(() => {
    const fetchToken = async () => {
      try {
        const config = await getConfig();
        // Extract token from WebUI.Token field
        const webui = config?.WebUI as { Token?: string } | undefined;
        tokenRef.current = webui?.Token || "";
      } catch (error) {
        console.error("Failed to fetch WebUI token from config:", error);
      } finally {
        setTokenReady(true);
      }
    };
    void fetchToken();
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  const fetchLogContent = useCallback(
    async (showLoading: boolean = false) => {
      if (!selected) return;

      if (showLoading) setLoadingContent(true);
      try {
        const params = new URLSearchParams();
        if (tokenRef.current) {
          params.set("token", tokenRef.current);
        }

        const response = await fetch(
          `/web/logs/${encodeURIComponent(selected)}?${params}`
        );
        if (!response.ok) {
          throw new Error(`${response.status} ${response.statusText}`);
        }

        const newContent = await response.text();
        const newLines = newContent.split('\n');
        const currentLinesCount = newLines.length;

        // Only update if content has changed (new lines added)
        if (currentLinesCount !== lastLinesCountRef.current) {
          setLogContent(newContent);
          lastLinesCountRef.current = currentLinesCount;
        }
      } catch (error) {
        push(describeError(error, `Failed to read ${selected}`), "error");
      } finally {
        if (showLoading) setLoadingContent(false);
      }
    },
    [selected, push, describeError]
  );

  useEffect(() => {
    if (selected && tokenReady) {
      lastLinesCountRef.current = 0;
      void fetchLogContent(true);
    }
  }, [selected, tokenReady, fetchLogContent]);

  // Refresh content periodically when tab is active
  useInterval(
    () => {
      if (tokenReady) {
        void fetchLogContent(false);
      }
    },
    active ? 1000 : null
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
                styles={getSelectStyles()}
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
                  checked={follow}
                  onChange={(event) => setFollow(event.target.checked)}
                />
                <IconImage src={LiveIcon} />
                <span>Auto-scroll</span>
              </label>
            </div>
          </div>
        </div>
        <div style={{
          flex: 1,
          minHeight: 0,
          overflow: 'hidden',
          borderRadius: '4px'
        }}>
          {loadingContent ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#666', backgroundColor: '#0a0e14' }}>
              <span className="spinner" style={{ marginRight: '8px' }} />
              Loading logs...
            </div>
          ) : logContent ? (
            <LazyLog
              text={logContent}
              follow={follow}
              enableSearch
              caseInsensitive
              selectableLines
              extraLines={1}
              style={{
                height: '100%',
                backgroundColor: '#0a0e14',
                color: '#e5e5e5',
                fontFamily: '"Cascadia Code", "Fira Code", "Consolas", "Monaco", monospace',
                fontSize: '13px',
                lineHeight: '1.5'
              }}
            />
          ) : (
            <div style={{ color: '#666', backgroundColor: '#0a0e14', padding: '16px' }}>Select a log file to view...</div>
          )}
        </div>
      </div>
    </section>
  );
}
