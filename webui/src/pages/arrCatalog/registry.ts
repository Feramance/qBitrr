/**
 * Arr catalog kinds used by the shared shell and dynamic definition loaders.
 * Per-Arr definitions live in `*Definition.tsx` and are resolved via
 * [`getArrCatalogDefinition`](./getArrCatalogDefinition.ts) or dynamic import in
 * [`ArrCatalogView`](../ArrCatalogView.tsx) — there is no runtime registry map.
 */
export type ArrCatalogKind = "radarr" | "sonarr" | "lidarr";
