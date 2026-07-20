import type { JSX, ReactNode, RefCallback } from "react";
import React from "react";
import type { ColumnDef } from "@tanstack/react-table";
import { StableTable } from "../../components/StableTable";
import type { Hashable } from "../../utils/dataSync";
import type { RowsStore } from "../../utils/rowsStore";
import { ARR_CATALOG_SYNC_HINT } from "../../constants/arrCatalogMessages";

/** Renders the catalog sync-hint empty state (no rows in local DB). */
export function ArrCatalogSyncEmptyHint({
  message,
}: {
  readonly message: string;
}): JSX.Element {
  return (
    <div className="hint">
      <p>{message}</p>
      <p>{ARR_CATALOG_SYNC_HINT}</p>
    </div>
  );
}

/** Renders the filtered-empty / no-match copy. */
export function ArrCatalogNoMatchHint({
  message,
}: {
  readonly message: string;
}): JSX.Element {
  return <div className="hint">{message}</div>;
}

export type ArrCatalogEmptyBranchOrder = "syncFirst" | "noItemsFirst";

interface ArrCatalogEmptyBranchProps {
  readonly order: ArrCatalogEmptyBranchOrder;
  readonly loading: boolean;
  readonly showCatalogEmptyHint: boolean;
  readonly hasRows: boolean;
  readonly catalogEmptyMessage: string;
  readonly noMatchMessage: string;
  readonly children: ReactNode;
}

/**
 * Chooses between sync hint, no-match hint, and catalog content.
 * Sonarr aggregate/instance uses `noItemsFirst`; Radarr/Lidarr use `syncFirst`.
 * While loading with no rows, renders nothing so empty copy does not sit under the spinner.
 */
export function ArrCatalogEmptyBranch({
  order,
  loading,
  showCatalogEmptyHint,
  hasRows,
  catalogEmptyMessage,
  noMatchMessage,
  children,
}: ArrCatalogEmptyBranchProps): JSX.Element | null {
  if (loading && !hasRows) {
    return null;
  }
  if (showCatalogEmptyHint) {
    return <ArrCatalogSyncEmptyHint message={catalogEmptyMessage} />;
  }
  if (order === "noItemsFirst" && !hasRows) {
    return <ArrCatalogNoMatchHint message={noMatchMessage} />;
  }
  if (hasRows) {
    return <>{children}</>;
  }
  return <ArrCatalogNoMatchHint message={noMatchMessage} />;
}

interface ArrCatalogListOrGridProps<TRow extends Hashable> {
  readonly browseMode: "list" | "icon";
  readonly rows: ReadonlyArray<TRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<TRow>;
  readonly columns: ColumnDef<TRow, unknown>[];
  readonly getRowKey: (row: TRow) => string;
  readonly onRowSelect: (row: TRow) => void;
  readonly iconGridRef: RefCallback<HTMLElement | null>;
  readonly renderIconTile: (row: TRow) => ReactNode;
}

/** Shared list/grid fork used by all Arr catalog body renderers. */
export function ArrCatalogListOrGrid<TRow extends Hashable>({
  browseMode,
  rows,
  rowOrder,
  rowsStore,
  columns,
  getRowKey,
  onRowSelect,
  iconGridRef,
  renderIconTile,
}: ArrCatalogListOrGridProps<TRow>): JSX.Element | null {
  if (!rows.length) {
    return null;
  }
  if (browseMode === "list") {
    const StoreTable = StableTable as React.ComponentType<{
      rowsStore: RowsStore<TRow>;
      rowOrder: readonly string[];
      columns: ColumnDef<TRow, unknown>[];
      getRowKey: (row: TRow) => string;
      onRowClick: (row: TRow) => void;
    }>;
    return (
      <StoreTable
        rowsStore={rowsStore}
        rowOrder={rowOrder}
        columns={columns}
        getRowKey={getRowKey}
        onRowClick={onRowSelect}
      />
    );
  }
  return (
    <div className="arr-icon-grid" ref={iconGridRef}>
      {rows.map((row) => renderIconTile(row))}
    </div>
  );
}
