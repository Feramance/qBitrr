import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import {
  getProcesses,
  rebuildArrs,
  restartAllProcesses,
  restartProcess,
  setLogLevel,
} from "../api/client";
import type { ProcessInfo } from "../api/types";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";

const LOG_LEVELS = [
  "CRITICAL",
  "ERROR",
  "WARNING",
  "NOTICE",
  "INFO",
  "DEBUG",
  "TRACE",
] as const;

interface ProcessesViewProps {
  active: boolean;
}

export function ProcessesView({ active }: ProcessesViewProps): JSX.Element {
  const [processes, setProcesses] = useState<ProcessInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [logLevel, setLogLevelState] = useState<(typeof LOG_LEVELS)[number]>(
    "INFO"
  );
  const { push } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getProcesses();
      setProcesses(data.processes ?? []);
    } catch (error) {
      push(
        error instanceof Error
          ? error.message
          : "Failed to load processes list",
        "error"
      );
    } finally {
      setLoading(false);
    }
  }, [push]);

  useEffect(() => {
    void load();
  }, [load]);

  useInterval(
    () => {
      void load();
    },
    active ? 1000 : null
  );

  const handleRestart = useCallback(
    async (category: string, kind: string) => {
      try {
        await restartProcess(category, kind);
        push(`Restarted ${category}:${kind}`, "success");
        void load();
      } catch (error) {
        push(
          error instanceof Error
            ? error.message
            : `Failed to restart ${category}:${kind}`,
          "error"
        );
      }
    },
    [load, push]
  );

  const handleRestartAll = useCallback(async () => {
    try {
      await restartAllProcesses();
      push("Restarted all processes", "success");
      void load();
    } catch (error) {
      push(
        error instanceof Error ? error.message : "Failed to restart all",
        "error"
      );
    }
  }, [load, push]);

  const handleRebuildArrs = useCallback(async () => {
    try {
      await rebuildArrs();
      push("Requested Arr rebuild", "success");
      void load();
    } catch (error) {
      push(
        error instanceof Error ? error.message : "Failed to rebuild Arrs",
        "error"
      );
    }
  }, [load, push]);

  const handleApplyLogLevel = useCallback(async () => {
    try {
      await setLogLevel(logLevel);
      push(`Log level set to ${logLevel}`, "success");
    } catch (error) {
      push(
        error instanceof Error ? error.message : "Failed to set log level",
        "error"
      );
    }
  }, [logLevel, push]);

  const rows = useMemo(
    () =>
      processes.map((proc) => (
        <tr key={`${proc.category}:${proc.kind}`}>
          <td>{proc.category}</td>
          <td>{proc.name}</td>
          <td>{proc.kind}</td>
          <td>{proc.pid ?? ""}</td>
          <td>
            <span className={proc.alive ? "ok" : "bad"}>
              {proc.alive ? "Yes" : "No"}
            </span>
          </td>
          <td>
            <button
              className="btn"
              onClick={() => handleRestart(proc.category, proc.kind)}
            >
              Restart
            </button>
          </td>
        </tr>
      )),
    [processes, handleRestart]
  );

  return (
    <section className="card">
      <div className="card-header">Processes</div>
      <div className="card-body stack">
        <div className="row">
          <div className="col inline">
            <button className="btn" onClick={() => void load()} disabled={loading}>
              Refresh
            </button>
            <button className="btn" onClick={() => void handleRestartAll()}>
              Restart All
            </button>
            <button className="btn" onClick={() => void handleRebuildArrs()}>
              Rebuild Arrs
            </button>
          </div>
          <div className="col">
            <div className="field">
              <label htmlFor="logLevel">Log Level</label>
              <div className="row" style={{ alignItems: "flex-end" }}>
                <select
                  id="logLevel"
                  value={logLevel}
                  onChange={(event) =>
                    setLogLevelState(event.target.value as typeof LOG_LEVELS[number])
                  }
                >
                  {LOG_LEVELS.map((level) => (
                    <option key={level} value={level}>
                      {level}
                    </option>
                  ))}
                </select>
                <button className="btn" onClick={() => void handleApplyLogLevel()}>
                  Apply
                </button>
              </div>
            </div>
          </div>
        </div>
        <div>
          <table>
            <thead>
              <tr>
                <th>Category</th>
                <th>Name</th>
                <th>Kind</th>
                <th>PID</th>
                <th>Alive</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
