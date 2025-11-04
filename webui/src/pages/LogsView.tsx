import { useCallback, useEffect, useState, type JSX } from "react";
import { LazyLog } from "@melloware/react-logviewer";
import { getLogDownloadUrl, getLogTail, getLogs } from "../api/client";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
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
  const [selected, setSelected] = useState<string>("All Logs");
  const [content, setContent] = useState("");
  const [follow, setFollow] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
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
          if (prev && list.includes(prev)) {
            return prev;
          }
          // Default to "All Logs" if available, otherwise Main.log, otherwise first file
          const allLogs = list.find((file) => file === "All Logs") ?? null;
          if (allLogs) return allLogs;
          const mainLog =
            list.find((file) => file.toLowerCase() === "main.log") ?? null;
          return mainLog ?? list[0];
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

  const loadTail = useCallback(
    async (name: string, showLoading: boolean = false) => {
      if (!name) return;
      if (showLoading) setLoadingContent(true);
      try {
        const text = await getLogTail(name);
        setContent(text);
      } catch (error) {
        push(describeError(error, `Failed to read ${name}`), "error");
      } finally {
        if (showLoading) setLoadingContent(false);
      }
    },
    [describeError, push]
  );



  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    if (selected) {
      void loadTail(selected, true);
    }
  }, [selected, loadTail]);

  useInterval(
    () => {
      if (selected) {
        void loadTail(selected, false);
      }
    },
    active ? 2000 : null
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
          ) : content ? (
            <LazyLog
              text={content}
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
            <div style={{ color: '#666', backgroundColor: '#0a0e14', padding: '16px' }}>Select a log file to view its tail...</div>
          )}
        </div>
      </div>
    </section>
  );
}
