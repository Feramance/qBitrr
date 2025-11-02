import { useCallback, useEffect, useRef, useState, type JSX } from "react";
import { getLogDownloadUrl, getLogTail, getLogs } from "../api/client";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
import Select from "react-select";

// Helper function for react-select theme-aware styles
const getSelectStyles = () => {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  return {
    control: (base: any) => ({
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
    menu: (base: any) => ({
      ...base,
      background: isDark ? '#0f131a' : '#ffffff',
      borderColor: isDark ? '#2a2f36' : '#d2d2d7',
      border: `1px solid ${isDark ? '#2a2f36' : '#d2d2d7'}`,
    }),
    option: (base: any, state: any) => ({
      ...base,
      background: state.isFocused
        ? (isDark ? 'rgba(122, 162, 247, 0.15)' : 'rgba(0, 113, 227, 0.1)')
        : (isDark ? '#0f131a' : '#ffffff'),
      color: isDark ? '#eaeef2' : '#1d1d1f',
      '&:active': {
        background: isDark ? 'rgba(122, 162, 247, 0.25)' : 'rgba(0, 113, 227, 0.2)',
      }
    }),
    singleValue: (base: any) => ({
      ...base,
      color: isDark ? '#eaeef2' : '#1d1d1f',
    }),
    input: (base: any) => ({
      ...base,
      color: isDark ? '#eaeef2' : '#1d1d1f',
    }),
    placeholder: (base: any) => ({
      ...base,
      color: isDark ? '#9aa3ac' : '#6e6e73',
    }),
    menuList: (base: any) => ({
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

  // Convert newlines to <br> tags
  result = result.replace(/\n/g, '<br>');

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

  const scrollToBottom = useCallback(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, []);

  const loadTail = useCallback(
    async (name: string, shouldAutoScroll: boolean, showLoading: boolean = false) => {
      if (!name) return;
      if (showLoading) setLoadingContent(true);
      try {
        const text = await getLogTail(name);
        setContent(text);
        // Scroll to bottom after content loads if autoscroll is enabled
        if (shouldAutoScroll) {
          // Use multiple RAF calls to ensure DOM has fully updated
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              scrollToBottom();
            });
          });
        }
      } catch (error) {
        push(describeError(error, `Failed to read ${name}`), "error");
      } finally {
        if (showLoading) setLoadingContent(false);
      }
    },
    [describeError, push, scrollToBottom]
  );

  // Handle user scroll - disable autoscroll if user scrolls up manually
  useEffect(() => {
    const logElement = logRef.current;
    if (!logElement) return;

    let scrollTimeout: number | null = null;
    let isUserScroll = false;
    let lastScrollHeight = logElement.scrollHeight;

    const handleScroll = () => {
      // Clear any pending timeout
      if (scrollTimeout !== null) {
        window.clearTimeout(scrollTimeout);
      }

      // Check if scroll height changed (content update) vs user scroll
      const currentScrollHeight = logElement.scrollHeight;
      if (currentScrollHeight !== lastScrollHeight) {
        // Content changed, not a user scroll
        lastScrollHeight = currentScrollHeight;
        return;
      }

      // Mark as user-initiated scroll
      isUserScroll = true;

      // Debounce scroll detection
      scrollTimeout = window.setTimeout(() => {
        if (!isUserScroll || !autoScroll) return;

        const { scrollTop, scrollHeight, clientHeight } = logElement;
        const isAtBottom = Math.abs(scrollHeight - scrollTop - clientHeight) < 10;

        // If user scrolled away from bottom, disable autoscroll
        if (!isAtBottom) {
          setAutoScroll(false);
        }

        isUserScroll = false;
      }, 150);
    };

    logElement.addEventListener('scroll', handleScroll, { passive: true });
    return () => {
      logElement.removeEventListener('scroll', handleScroll);
      if (scrollTimeout !== null) {
        window.clearTimeout(scrollTimeout);
      }
    };
  }, [autoScroll]);

  // Scroll to bottom when autoscroll is re-enabled or content changes
  useEffect(() => {
    if (autoScroll && logRef.current && content) {
      // Double RAF to ensure DOM has updated
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          scrollToBottom();
        });
      });
    }
  }, [autoScroll, content, scrollToBottom]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    if (selected) {
      void loadTail(selected, autoScroll, true);
    }
  }, [selected, autoScroll, loadTail]);

  useInterval(
    () => {
      if (selected) {
        void loadTail(selected, autoScroll);
      }
    },
    active && autoScroll ? 2000 : null
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
            <pre style={{
              margin: 0,
              whiteSpace: 'pre-wrap',
              fontFamily: '"Cascadia Code", "Fira Code", "Consolas", "Monaco", monospace',
              fontSize: '13px',
              lineHeight: '1.5',
              color: '#e5e5e5',
              tabSize: 4,
              minHeight: '100%'
            }} dangerouslySetInnerHTML={{ __html: ansiToHtml(content) }}>
            </pre>
          ) : (
            <div style={{ color: '#666' }}>Select a log file to view its tail...</div>
          )}
        </div>
      </div>
    </section>
  );
}
