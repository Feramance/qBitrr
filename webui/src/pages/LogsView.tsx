import { useCallback, useEffect, useRef, useState, type JSX } from "react";
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

function ansiToHtml(text: string): string {
  // Enhanced ANSI to HTML converter with full TTY support
  const fgColorMap: Record<string, string> = {
    '30': '#000000', '31': '#cd3131', '32': '#0dbc79', '33': '#e5e510',
    '34': '#2472c8', '35': '#bc3fbc', '36': '#11a8cd', '37': '#e5e5e5',
    '90': '#666666', '91': '#f14c4c', '92': '#23d18b', '93': '#f5f543',
    '94': '#3b8eea', '95': '#d670d6', '96': '#29b8db', '97': '#ffffff',
  };

  const bgColorMap: Record<string, string> = {
    '40': '#000000', '41': '#cd3131', '42': '#0dbc79', '43': '#e5e510',
    '44': '#2472c8', '45': '#bc3fbc', '46': '#11a8cd', '47': '#e5e5e5',
    '100': '#666666', '101': '#f14c4c', '102': '#23d18b', '103': '#f5f543',
    '104': '#3b8eea', '105': '#d670d6', '106': '#29b8db', '107': '#ffffff',
  };

  let result = text;
  let styles: string[] = [];

  // Replace ANSI sequences with HTML
  // eslint-disable-next-line no-control-regex
  result = result.replace(/\u001b\[([0-9;]+)m/g, (match, codes) => {
    const codeList = codes.split(';');
    let html = '';

    for (const code of codeList) {
      if (code === '0' || code === '') {
        // Reset all styles
        html += '</span>'.repeat(styles.length);
        styles = [];
      } else if (code === '1') {
        // Bold
        styles.push('font-weight:bold');
        html += `<span style="${styles.join(';')}">`;
      } else if (code === '3') {
        // Italic
        styles.push('font-style:italic');
        html += `<span style="${styles.join(';')}">`;
      } else if (code === '4') {
        // Underline
        styles.push('text-decoration:underline');
        html += `<span style="${styles.join(';')}">`;
      } else if (code === '22') {
        // Normal intensity
        styles = styles.filter(s => !s.includes('font-weight'));
      } else if (code === '23') {
        // Not italic
        styles = styles.filter(s => !s.includes('font-style'));
      } else if (code === '24') {
        // Not underlined
        styles = styles.filter(s => !s.includes('text-decoration'));
      } else if (fgColorMap[code]) {
        // Foreground color
        styles = styles.filter(s => !s.startsWith('color:'));
        styles.push(`color:${fgColorMap[code]}`);
        html += `<span style="${styles.join(';')}">`;
      } else if (bgColorMap[code]) {
        // Background color
        styles = styles.filter(s => !s.startsWith('background-color:'));
        styles.push(`background-color:${bgColorMap[code]}`);
        html += `<span style="${styles.join(';')}">`;
      } else if (code === '39') {
        // Default foreground color
        styles = styles.filter(s => !s.startsWith('color:'));
      } else if (code === '49') {
        // Default background color
        styles = styles.filter(s => !s.startsWith('background-color:'));
      }
    }

    return html;
  });

  // Close any remaining open spans
  result += '</span>'.repeat(styles.length);

  // Keep newlines as-is for pre-wrap (don't convert to <br>)
  // The pre element with white-space: pre-wrap will handle them correctly

  return result;
}

import RefreshIcon from "../icons/refresh-arrow.svg";
import DownloadIcon from "../icons/download.svg";
import LiveIcon from "../icons/live-streaming.svg";

interface LogsViewProps {
  active: boolean;
}

export function LogsView({ active }: LogsViewProps): JSX.Element {
  const [files, setFiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("Main.log");
  const [content, setContent] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
  const logRef = useRef<HTMLDivElement | null>(null);
  const preRef = useRef<HTMLPreElement | null>(null);
  const bottomMarkerRef = useRef<HTMLDivElement | null>(null);
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

  // Auto-scroll to bottom when content changes and autoscroll is enabled
  useEffect(() => {
    if (!autoScroll || !content || !logRef.current) return;

    const scrollToBottom = () => {
      if (logRef.current) {
        const el = logRef.current;
        const before = {
          scrollTop: el.scrollTop,
          scrollHeight: el.scrollHeight,
          clientHeight: el.clientHeight
        };

        // Force scroll to absolute bottom - use a very large number to ensure we reach bottom
        el.scrollTop = 999999999;

        const after = {
          scrollTop: el.scrollTop,
          scrollHeight: el.scrollHeight,
          clientHeight: el.clientHeight
        };

        console.log('[LogsView Auto-scroll]', {
          before,
          after,
          scrolledToBottom: (after.scrollHeight - after.scrollTop - after.clientHeight) < 5
        });
      }
    };

    // Use timeouts to ensure the dangerouslySetInnerHTML has fully rendered
    // The ANSI conversion creates complex nested HTML that takes time to layout
    const timeouts: number[] = [];

    // Try at multiple intervals to handle delayed layout, with one very late attempt
    [0, 50, 100, 200, 500, 1000].forEach(delay => {
      timeouts.push(window.setTimeout(scrollToBottom, delay));
    });

    return () => {
      timeouts.forEach(t => window.clearTimeout(t));
    };
  }, [content, autoScroll]);

  // Handle user scroll - disable autoscroll if user scrolls up manually
  useEffect(() => {
    const logElement = logRef.current;
    if (!logElement) return;

    let lastKnownScrollTop = logElement.scrollTop;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = logElement;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 50;

      // Only disable autoscroll if user manually scrolls up (not down)
      if (scrollTop < lastKnownScrollTop && !isNearBottom) {
        setAutoScroll(false);
      }

      lastKnownScrollTop = scrollTop;
    };

    logElement.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      logElement.removeEventListener('scroll', handleScroll);
    };
  }, []);

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
                  checked={autoScroll}
                  onChange={(event) => setAutoScroll(event.target.checked)}
                />
                <IconImage src={LiveIcon} />
                <span>Auto-scroll</span>
              </label>
            </div>
          </div>
        </div>
        <div ref={logRef} style={{
          flex: 1,
          minHeight: 0,
          overflow: 'auto',
          backgroundColor: '#0a0e14',
          borderRadius: '4px',
          padding: '16px'
        }}>
          {loadingContent ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#666' }}>
              <span className="spinner" style={{ marginRight: '8px' }} />
              Loading logs...
            </div>
          ) : content ? (
            <>
              <pre
                ref={preRef}
                style={{
                  margin: 0,
                  whiteSpace: 'pre-wrap',
                  fontFamily: '"Cascadia Code", "Fira Code", "Consolas", "Monaco", monospace',
                  fontSize: '13px',
                  lineHeight: '1.5',
                  color: '#e5e5e5',
                  tabSize: 4
                }}
                dangerouslySetInnerHTML={{ __html: ansiToHtml(content) }}
              />
              <div ref={bottomMarkerRef} style={{ height: '1px', width: '1px' }} />
            </>
          ) : (
            <div style={{ color: '#666' }}>Select a log file to view its tail...</div>
          )}
        </div>
      </div>
    </section>
  );
}
