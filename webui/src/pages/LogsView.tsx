import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type JSX,
} from "react";
import { getLogDownloadUrl, getLogTail, getLogs } from "../api/client";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";

interface LogsViewProps {
  active: boolean;
}

export function LogsView({ active }: LogsViewProps): JSX.Element {
  const [files, setFiles] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [content, setContent] = useState("");
  const [isLive, setIsLive] = useState(true);
  const [loadingList, setLoadingList] = useState(false);
  const logRef = useRef<HTMLPreElement | null>(null);
  const { push } = useToast();

  const loadList = useCallback(async () => {
    setLoadingList(true);
    try {
      const data = await getLogs();
      setFiles(data.files ?? []);
      if (data.files?.length) {
        setSelected((prev) => prev || data.files![0]);
      }
    } catch (error) {
      push(
        error instanceof Error ? error.message : "Failed to fetch logs",
        "error"
      );
    } finally {
      setLoadingList(false);
    }
  }, [push]);

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
        push(
          error instanceof Error ? error.message : `Failed to read ${name}`,
          "error"
        );
      }
    },
    [push]
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
                Reload List
              </button>
              <button
                className="btn"
                onClick={() =>
                  selected && window.open(getLogDownloadUrl(selected), "_blank")
                }
                disabled={!selected}
              >
                Download
              </button>
              <label className="hint inline" style={{ cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={isLive}
                  onChange={(event) => setIsLive(event.target.checked)}
                />
                Live
              </label>
            </div>
          </div>
        </div>
        <pre ref={logRef}>{content || "Select a log file to view its tail..."}</pre>
      </div>
    </section>
  );
}
