/**
 * Arr catalog consolidation — typed registry of per-Arr definitions consumed by the
 * shared [`ArrCatalogShell`](./ArrCatalogShell.tsx). The shell is generic; each
 * definition supplies fetch / map / render slots specific to one Arr.
 */
import type { AnyArrCatalogDefinition } from "./definition";

export type ArrCatalogKind = "radarr" | "sonarr" | "lidarr";

/**
 * Registry is populated by definition modules importing this map and assigning their
 * own entry. The indirection keeps the registry free of import-cycle hazards while
 * still giving consumers a typed lookup.
 */
export const ARR_CATALOG_REGISTRY: Record<ArrCatalogKind, AnyArrCatalogDefinition> = {
  // populated by each per-Arr definition file (see `radarrDefinition.tsx`,
  // `sonarrDefinition.tsx`, `lidarrDefinition.tsx`).
} as Record<ArrCatalogKind, AnyArrCatalogDefinition>;
