import {
  columnSizingFeature,
  columnVisibilityFeature,
  tableFeatures,
  type ColumnDef,
  type RowData,
} from "@tanstack/react-table";

/**
 * Shared features for app tables.
 * Includes visibility (`getVisibleCells`) and sizing (`size` on column defs).
 */
export const coreTableFeatures = tableFeatures({
  columnVisibilityFeature,
  columnSizingFeature,
});

export type CoreTableFeatures = typeof coreTableFeatures;

/** Column def typed against the shared feature set. */
export type AppColumnDef<TData extends RowData, TValue = unknown> = ColumnDef<
  CoreTableFeatures,
  TData,
  TValue
>;
