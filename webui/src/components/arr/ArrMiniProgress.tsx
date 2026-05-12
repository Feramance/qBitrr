import type { JSX } from "react";

export interface ArrMiniProgressProps {
  label: string;
  available: number;
  missing: number;
}

/**
 * Compact segmented bar for browse tiles: monitored scope = available + missing.
 */
export function ArrMiniProgress({
  label,
  available,
  missing,
}: ArrMiniProgressProps): JSX.Element {
  const total = available + missing;
  const availPct = total > 0 ? (available / total) * 100 : 0;
  const missPct = total > 0 ? (missing / total) * 100 : 0;
  const title = `${label}: ${available.toLocaleString()} available, ${missing.toLocaleString()} missing (${total.toLocaleString()} monitored)`;

  return (
    <div className="arr-mini-progress" title={title}>
      <div className="arr-mini-progress__label-row">
        <span className="arr-mini-progress__label">{label}</span>
        <span className="arr-mini-progress__nums">
          {available.toLocaleString()} / {total.toLocaleString()}
        </span>
      </div>
      <div
        className="arr-mini-progress__track"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={available}
        aria-label={title}
      >
        {total > 0 ? (
          <>
            <div
              className="arr-mini-progress__seg arr-mini-progress__seg--avail"
              style={{ width: `${availPct}%` }}
            />
            <div
              className="arr-mini-progress__seg arr-mini-progress__seg--miss"
              style={{ width: `${missPct}%` }}
            />
          </>
        ) : (
          <div className="arr-mini-progress__seg arr-mini-progress__seg--empty" />
        )}
      </div>
    </div>
  );
}
