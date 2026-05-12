import type { ArrInfo } from "../../api/types";

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
