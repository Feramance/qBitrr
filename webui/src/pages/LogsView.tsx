import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import { getLogDownloadUrl, getLogTail, getLogs } from "../api/client";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";
import { IconDownload, IconPulse, IconRefresh } from "../components/Icons";

interface LogsViewProps {
  active: boolean;
}

export function LogsView({ active }: LogsViewProps): JSX.Element {
  const [files, setFiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("Main.log");
  const [content, setContent] = useState("");
  const [isLive, setIsLive] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
  const logRef = useRef<HTMLPreElement | null>(null);
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
        setContent(text);
        window.requestAnimationFrame(() => {
          if (logRef.current) {
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

  const options = useMemo(
    () =>
      files.map((file) => (
        <option key={file} value={file}>
          {file}
        </option>
      )),
    [files]
  );

  return (
    <section className="card">
      <div className="card-header">Logs</div>
      <div className="card-body stack">
        <div className="row">
          <div className="col field">
            <label htmlFor="logSelect">Log File</label>
            <select
              id="logSelect"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
              disabled={!files.length}
            >
              {options}
            </select>
          </div>
          <div className="col field">
            <label>&nbsp;</label>
            <div className="row" style={{ alignItems: "center" }}>
              <button className="btn" onClick={() => void loadList()} disabled={loadingList}>
                <IconRefresh />
                Reload List
              </button>
              <button
                className="btn"
                onClick={() =>
                  selected && window.open(getLogDownloadUrl(selected), "_blank")
                }
                disabled={!selected}
              >
                <IconDownload />
                Download
              </button>
              <label className="hint inline" style={{ cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={isLive}
                  onChange={(event) => setIsLive(event.target.checked)}
                />
                <IconPulse />
                <span>Live</span>
              </label>
            </div>
          </div>
        </div>
        <pre ref={logRef}>{content || "Select a log file to view its tail..."}</pre>
      </div>
    </section>
  );
}
