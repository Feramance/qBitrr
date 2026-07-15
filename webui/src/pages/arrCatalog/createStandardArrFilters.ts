import type { ArrCatalogFilterSelectSpec } from "./definition";

const REASON_FILTER_OPTIONS = [
  { value: "all", label: "All Reasons" },
  { value: "Not being searched", label: "Not Being Searched" },
  { value: "Missing", label: "Missing" },
  { value: "Quality", label: "Quality" },
  { value: "CustomFormat", label: "Custom Format" },
  { value: "Upgrade", label: "Upgrade" },
] as const;

export interface StandardArrFilterState extends Record<string, unknown> {
  readonly onlyMissing: boolean;
  readonly reasonFilter: string;
}

/**
 * Shared Status + Search Reason filter controls used by Radarr, Sonarr, and Lidarr.
 * Filter application differs per Arr type; this only unifies the toolbar UI spec.
 */
export function createStandardArrFilters<TFilters extends StandardArrFilterState>(
  allItemsLabel: string,
): ReadonlyArray<ArrCatalogFilterSelectSpec<TFilters>> {
  return [
    {
      id: "status",
      label: "Status",
      mode: "always",
      options: [
        { value: "all", label: allItemsLabel },
        { value: "missing", label: "Missing Only" },
      ],
      getValue: (f) => (f.onlyMissing ? "missing" : "all"),
      setValue: (prev, next) =>
        ({ ...prev, onlyMissing: next === "missing" }) as TFilters,
    },
    {
      id: "reason",
      label: "Search Reason",
      mode: "always",
      options: [...REASON_FILTER_OPTIONS],
      getValue: (f) => f.reasonFilter,
      setValue: (prev, next) => ({ ...prev, reasonFilter: next }) as TFilters,
    },
  ];
}
