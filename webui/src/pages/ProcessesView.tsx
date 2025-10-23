import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import {
  getProcesses,
  rebuildArrs,
  restartAllProcesses,
  restartProcess,
} from "../api/client";
import type { ProcessInfo } from "../api/types";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";

interface ProcessesViewProps {
  active: boolean;
}

export function ProcessesView({ active }: ProcessesViewProps): JSX.Element {
  const [processes, setProcesses] = useState<ProcessInfo[]>([]);
  const [loading, setLoading] = useState(false);
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

  const cards = useMemo(
    () =>
      processes.map((proc) => {
        const statusClass = proc.alive ? "status-pill status-pill--ok" : "status-pill status-pill--bad";
        const statusLabel = proc.alive ? "Running" : "Stopped";
        return (
          <div className="process-card" key={`${proc.category}:${proc.kind}`}>
            <div className="process-card__header">
              <div>
                <div className="process-card__name">{proc.name}</div>
                <div className="process-card__meta">
                  <span>{proc.kind}</span>
                  <span className="separator">|</span>
                  <span>{proc.category}</span>
                  {proc.pid ? (
                    <>
                      <span className="separator">|</span>
                      <span>PID {proc.pid}</span>
                    </>
                  ) : null}
                </div>
              </div>
              <span className={statusClass}>
                <span className="status-pill__dot" />
                {statusLabel}
              </span>
            </div>
            <div className="process-card__footer">
              <button
                className="btn"
                onClick={() => handleRestart(proc.category, proc.kind)}
              >
                Restart
              </button>
            </div>
          </div>
        );
      }),
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
        </div>
        <div className="process-grid">
          {processes.length ? cards : (
            <div className="empty-state">No processes available.</div>
          )}
        </div>
      </div>
    </section>
  );
}
