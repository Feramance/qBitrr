import type { JSX } from "react";
import { ArrMiniProgress } from "./ArrMiniProgress";

/** Idle search-state label used in filters, list cells, and detail modals. */
export const ARR_IDLE_REASON_LABEL = "Not being searched";

export function ArrMonitoredBadge({
  monitored,
}: {
  readonly monitored: boolean;
}): JSX.Element {
  return (
    <span
      className={`table-badge ${monitored ? "monitored" : "unmonitored"}`}
    >
      {monitored ? "Monitored" : "Unmonitored"}
    </span>
  );
}

export function ArrHasFileBadge({
  hasFile,
}: {
  readonly hasFile: boolean;
}): JSX.Element {
  return (
    <span className={`table-badge ${hasFile ? "has-file" : "missing"}`}>
      {hasFile ? "Has file" : "Missing"}
    </span>
  );
}

export function ArrReasonBadge({
  reason,
}: {
  readonly reason: string | null | undefined;
}): JSX.Element {
  const trimmed = typeof reason === "string" ? reason.trim() : "";
  if (!trimmed) {
    return (
      <span className="table-badge table-badge-reason table-badge-reason--idle">
        {ARR_IDLE_REASON_LABEL}
      </span>
    );
  }
  return <span className="table-badge table-badge-reason">{trimmed}</span>;
}

/** Compact monitored episode/track progress for list/icon rows. */
export function ArrListProgressCell({
  label,
  available,
  missing,
}: {
  readonly label: string;
  readonly available: number;
  readonly missing: number;
}): JSX.Element {
  return (
    <ArrMiniProgress label={label} available={available} missing={missing} />
  );
}
