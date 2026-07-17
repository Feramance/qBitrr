import type { ArrInfo } from "../../api/types";

/**
 * Soft cap for instance pipelines that accumulate fetched pages (`keepAllPages`).
 * Keeps pages closest to the most recently touched index so flip-back stays warm
 * without unbounded memory growth.
 */
export const KEEP_ALL_PAGES_SOFT_CAP = 8;

/**
 * Cap a page-index → rows map, preferring pages nearest `touchedPage`.
 * Returns the same reference when already within the cap.
 */
export function softCapCachedPages<T>(
  pages: Record<number, ReadonlyArray<T>>,
  touchedPage: number,
  maxPages: number = KEEP_ALL_PAGES_SOFT_CAP,
): Record<number, ReadonlyArray<T>> {
  const keys = Object.keys(pages).map(Number);
  if (keys.length <= maxPages) {
    return pages;
  }
  const keep = new Set(
    keys
      .map((k) => ({ k, dist: Math.abs(k - touchedPage) }))
      .sort((a, b) => a.dist - b.dist || a.k - b.k)
      .slice(0, maxPages)
      .map((x) => x.k),
  );
  const next: Record<number, ReadonlyArray<T>> = {};
  for (const k of keys) {
    if (keep.has(k)) {
      next[k] = pages[k]!;
    }
  }
  return next;
}

/**
 * Resolve category key for API/thumbnail calls from aggregate row `__instance` label.
 */
export function categoryForInstanceLabel(
  instances: ArrInfo[],
  label: string
): string {
  const inst = instances.find(
    (i) => (i.name || i.category) === label || i.category === label
  );
  return inst?.category ?? instances[0]?.category ?? "";
}

/**
 * Pick instance vs aggregate after loading filtered Arr list.
 * Multi-instance: default aggregate; invalid selection falls back to aggregate (not first instance).
 */
export function reconcileArrCatalogSelection(
  filtered: ArrInfo[],
  current: string | "aggregate" | ""
): string | "aggregate" {
  if (!filtered.length) {
    return "aggregate";
  }
  if (filtered.length === 1) {
    return filtered[0].category;
  }
  if (current === "" || current === "aggregate") {
    return "aggregate";
  }
  if (!filtered.some((arr) => arr.category === current)) {
    return "aggregate";
  }
  return current;
}
