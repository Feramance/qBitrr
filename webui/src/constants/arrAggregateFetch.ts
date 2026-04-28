/** Page size used when iterating the full Arr library for aggregate ("All instances") merge. Kept small for responsive API responses. */
export const AGGREGATE_FETCH_CHUNK_SIZE = 10;

/** Fallback max page iterations when API omits reliable `total`. */
export const AGG_FALLBACK_AGGREGATE_PAGES_MAX = 100000;

/**
 * Resolve how many backend pages (0-indexed inclusive count) to request for aggregate merge.
 * When `total` is missing but `moviesLength`/`batchLength` is provided, callers use legacy shortening.
 */
export function pagesFromAggregateTotal(
  totalUnknown: unknown,
  pageSizeFromResponse?: unknown,
  chunkFallback: number = AGGREGATE_FETCH_CHUNK_SIZE
): number | null {
  if (typeof totalUnknown !== "number" || Number.isNaN(totalUnknown)) return null;
  const psRaw =
    typeof pageSizeFromResponse === "number" && pageSizeFromResponse > 0
      ? pageSizeFromResponse
      : chunkFallback;
  const ps = Math.max(1, psRaw);
  if (totalUnknown <= 0) return 1;
  return Math.ceil(totalUnknown / ps);
}

/** Polling interval when live-updates are enabled (aggregate merge is heavy — avoid 1s churn). */
export const AGGREGATE_POLL_INTERVAL_MS = 15_000;

/** Single-instance Radarr/Sonarr browse: same cadence as aggregate to reduce unnecessary refetches. */
export const INSTANCE_VIEW_POLL_INTERVAL_MS = AGGREGATE_POLL_INTERVAL_MS;

/** Row-based stats for merged All-Radarr / All-Sonarr views (aligns with SQLite rollup semantics). */
export interface AggregateCatalogSummary {
  readonly available: number;
  readonly monitored: number;
  readonly missing: number;
  readonly total: number;
}

/** Counts monitored rows with/without files; `available` is monitored && hasFile (per catalog rollups). */
export function summarizeAggregateMonitoredRows<
  Row extends { monitored?: boolean | null; hasFile?: boolean | null },
>(rows: ReadonlyArray<Row>): AggregateCatalogSummary {
  let monitored = 0;
  let available = 0;
  for (const r of rows) {
    if (r.monitored) {
      monitored += 1;
      if (r.hasFile) {
        available += 1;
      }
    }
  }
  const total = rows.length;
  const missing = Math.max(0, monitored - available);
  return { available, monitored, missing, total };
}

/** Lidarr merged rows store `monitored` / `hasFile` on nested `album`. */
export function summarizeLidarrAlbumAggRows(
  rows: ReadonlyArray<{ album?: Record<string, unknown> }>
): AggregateCatalogSummary {
  let monitored = 0;
  let available = 0;
  for (const r of rows) {
    const a = r.album;
    const m = Boolean(a?.monitored);
    const h = Boolean(a?.hasFile);
    if (m) {
      monitored += 1;
      if (h) {
        available += 1;
      }
    }
  }
  const total = rows.length;
  const missing = Math.max(0, monitored - available);
  return { available, monitored, missing, total };
}
