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
