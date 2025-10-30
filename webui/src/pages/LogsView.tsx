import { useCallback, useEffect, useRef, useState, type JSX } from "react";
import { getLogDownloadUrl, getLogTail, getLogs } from "../api/client";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
import { Select } from "@mantine/core";

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
    <section className="card">
      <div className="card-header">Logs</div>
      <div className="card-body stack">
        <div className="row">
          <div className="col field">
            <Select
              label="Log File"
              data={files}
              value={selected}
              onChange={(value) => setSelected(value || "")}
              disabled={!files.length}
            />
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
        <div ref={logRef} style={{ height: '400px', overflow: 'auto' }}>
          {content ? (
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'monospace', backgroundColor: 'var(--surface)', color: 'var(--on-surface)', padding: '10px', borderRadius: '4px' }}>
              {content}
            </pre>
          ) : (
            "Select a log file to view its tail..."
          )}
        </div>
      </div>
    </section>
  );
}
