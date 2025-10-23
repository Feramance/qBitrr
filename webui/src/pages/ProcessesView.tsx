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

  const groupedProcesses = useMemo(() => {
    const buckets = new Map<string, ProcessInfo[]>();
    processes.forEach((proc) => {
      const key = proc.name || `${proc.category}:${proc.kind}`;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key)!.push(proc);
    });
    return Array.from(buckets.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([name, items]) => ({
        name,
        items: items.sort((a, b) => a.kind.localeCompare(b.kind)),
      }));
  }, [processes]);

  const handleRestartGroup = useCallback(
    async (items: ProcessInfo[]) => {
      try {
        await Promise.all(
          items.map((item) => restartProcess(item.category, item.kind))
        );
        push(`Restarted ${items[0]?.name ?? "group"}`, "success");
        void load();
      } catch (error) {
        push(
          error instanceof Error
            ? error.message
            : "Failed to restart process group",
          "error"
        );
      }
    },
    [load, push]
  );

  const cards = useMemo(
    () =>
      groupedProcesses.map(({ name, items }) => {
        const runningCount = items.filter((item) => item.alive).length;
        const statusClass =
          runningCount === items.length
            ? "status-pill status-pill--ok"
            : runningCount === 0
            ? "status-pill status-pill--bad"
            : "status-pill";
        const statusLabel =
          runningCount === items.length
            ? "All Running"
            : runningCount === 0
            ? "Stopped"
            : `${runningCount}/${items.length} Running`;

        return (
          <div className="process-card" key={name}>
            <div className="process-card__header">
              <div>
                <div className="process-card__name">{name}</div>
                <div className="process-card__meta">
                  {items.map((item, index) => (
                    <span key={`${item.category}:${item.kind}`}>
                      {index > 0 ? <span className="separator">| </span> : null}
                      {item.kind} <span className="separator">·</span>{" "}
                      {item.category}
                    </span>
                  ))}
                </div>
              </div>
              <span className={statusClass}>
                <span className="status-pill__dot" />
                {statusLabel}
              </span>
            </div>
            <div className="process-card__list">
              {items.map((item) => (
                <div className="process-card__row" key={`${item.category}:${item.kind}`}>
                  <div className="process-card__row-info">
                    <strong>{item.kind}</strong>
                    <span className="hint">
                      {item.category}
                      {item.pid ? ` · PID ${item.pid}` : ""}
                    </span>
                  </div>
                  <div className="process-card__row-actions">
                    <span className={item.alive ? "status-pill status-pill--ok" : "status-pill status-pill--bad"}>
                      <span className="status-pill__dot" />
                      {item.alive ? "Running" : "Stopped"}
                    </span>
                    <button
                      className="btn"
                      onClick={() => handleRestart(item.category, item.kind)}
                    >
                      Restart
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <div className="process-card__footer">
              <button
                className="btn ghost"
                onClick={() => void handleRestartGroup(items)}
              >
                Restart All
              </button>
            </div>
          </div>
        );
      }),
    [groupedProcesses, handleRestart, handleRestartGroup]
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
