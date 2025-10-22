import { useCallback, useEffect, useRef, useState, type JSX } from "react";
import { getStatus } from "../api/client";
import type { StatusResponse } from "../api/types";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";

export function StatusSummary(): JSX.Element {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const { push } = useToast();
  const lastError = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getStatus();
      setStatus(data);
      lastError.current = null;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to load status";
      if (lastError.current !== message) {
        push(message, "error");
        lastError.current = message;
      }
    }
  }, [push]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useInterval(refresh, 1000);

  const arrSummary =
    status?.arrs
      ?.map((arr) => `${arr.name || arr.category}:${arr.alive ? "OK" : "DOWN"}`)
      .join(" ") ?? "";

  return (
    <div className="inline hint" title="Status auto-refreshes every second">
      <span
        className={`status-pill ${
          status?.qbit?.alive ? "ok" : "bad"
        }`.trimEnd()}
      >
        qBit {status?.qbit?.alive ? "OK" : "DOWN"}
      </span>
      {arrSummary && <span>{arrSummary}</span>}
    </div>
  );
}
