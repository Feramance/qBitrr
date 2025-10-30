import { useCallback, useEffect, useRef, useState, type JSX } from "react";
import { getLogDownloadUrl, getLogTail, getLogs } from "../api/client";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
import Select from "react-select";

function ansiToHtml(text: string): string {
  // Simple ANSI to HTML converter for common colors
  const colorMap: Record<string, string> = {
    '30': 'black',
    '31': 'red',
    '32': 'green',
    '33': 'yellow',
    '34': 'blue',
    '35': 'magenta',
    '36': 'cyan',
    '37': 'white',
    '90': 'gray',
    '91': 'red',
    '92': 'green',
    '93': 'yellow',
    '94': 'blue',
    '95': 'magenta',
    '96': 'cyan',
    '97': 'white',
  };

  return text
    .replace(/\u001b\[0m/g, '</span>')
    .replace(/\u001b\[(\d+)m/g, (match, code) => {
      const color = colorMap[code];
      return color ? `<span style="color:${color}">` : '';
    })
    .replace(/\u001b\[39m/g, '</span>') // reset to default
    .replace(/\n/g, '<br>');
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
  const [isLive, setIsLive] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
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

  const loadTail = useCallback(
    async (name: string) => {
      if (!name) return;
      try {
        const text = await getLogTail(name);
        const wasAtBottom = logRef.current
          ? logRef.current.scrollTop + logRef.current.clientHeight >= logRef.current.scrollHeight - 50
          : true;
        setContent(text);
        window.requestAnimationFrame(() => {
          if (logRef.current && wasAtBottom) {
            logRef.current.scrollTop = logRef.current.scrollHeight;
          }
        });
      } catch (error) {
        push(describeError(error, `Failed to read ${name}`), "error");
      }
    },
    [describeError, push]
  );

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    if (selected) {
      void loadTail(selected);
    }
  }, [selected, loadTail]);

  useInterval(
    () => {
      if (selected) {
        void loadTail(selected);
      }
    },
    active && isLive ? 2000 : null
  );



  return (
    <section className="card" style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div className="card-header">Logs</div>
      <div className="card-body" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div className="row">
          <div className="col field">
            <div className="field">
              <label>Log File</label>
              <Select
                options={files.map(f => ({ value: f, label: f }))}
                value={selected ? { value: selected, label: selected } : null}
                onChange={(option) => setSelected(option?.value || "")}
                isDisabled={!files.length}
                styles={{
                  control: (base) => ({ ...base, background: '#0f131a', color: '#eaeef2', borderColor: '#2a2f36' }),
                  menu: (base) => ({ ...base, background: '#0f131a', borderColor: '#2a2f36' }),
                  option: (base, state) => ({ ...base, background: state.isFocused ? 'rgba(255,255,255,0.05)' : '#0f131a', color: '#eaeef2' }),
                  singleValue: (base) => ({ ...base, color: '#eaeef2' }),
                  input: (base) => ({ ...base, color: '#eaeef2' }),
                }}
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
                  checked={isLive}
                  onChange={(event) => setIsLive(event.target.checked)}
                />
                <IconImage src={LiveIcon} />
                <span>Live</span>
              </label>
            </div>
          </div>
        </div>
        <div ref={logRef} style={{ flex: 1, overflow: 'auto' }}>
          {content ? (
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'monospace', backgroundColor: 'var(--surface)', color: 'var(--on-surface)', padding: '10px', borderRadius: '4px' }} dangerouslySetInnerHTML={{ __html: ansiToHtml(content) }}>
            </pre>
          ) : (
            "Select a log file to view its tail..."
          )}
        </div>
      </div>
    </section>
  );
}
