import type { ColumnDef } from "@tanstack/react-table";
import type { JSX, ReactNode, RefCallback } from "react";
import type { Hashable } from "../../utils/dataSync";
import type { RowsStore } from "../../utils/rowsStore";
import {
  ArrCatalogBodyChrome,
  ArrCatalogPagination,
} from "./ArrCatalogBodyChrome";
import {
  ArrCatalogEmptyBranch,
  ArrCatalogListOrGrid,
  type ArrCatalogEmptyBranchOrder,
} from "./ArrCatalogListOrGrid";

export interface ArrCatalogStandardBodyProps<TRow extends Hashable> {
  readonly summaryLine: ReactNode;
  readonly onRefresh: () => void;
  readonly loading: boolean;
  readonly loadingHint: string;
  readonly emptyOrder: ArrCatalogEmptyBranchOrder;
  readonly showCatalogEmptyHint: boolean;
  readonly hasRows: boolean;
  readonly catalogEmptyMessage: string;
  readonly noMatchMessage: string;
  /** When false, pagination footer is omitted. */
  readonly showPagination: boolean;
  readonly page: number;
  readonly totalPages: number;
  readonly total: number;
  readonly itemNoun: string;
  readonly pageSize: number;
  readonly onPageChange: (page: number) => void;
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

/**
 * Shared catalog body: chrome + empty branch + list/grid + optional pagination.
 * Per-Arr definitions supply row types, columns, and tile renderers only.
 */
export function ArrCatalogStandardBody<TRow extends Hashable>({
  summaryLine,
  onRefresh,
  loading,
  loadingHint,
  emptyOrder,
  showCatalogEmptyHint,
  hasRows,
  catalogEmptyMessage,
  noMatchMessage,
  showPagination,
  page,
  totalPages,
  total,
  itemNoun,
  pageSize,
  onPageChange,
  browseMode,
  rows,
  rowOrder,
  rowsStore,
  columns,
  getRowKey,
  onRowSelect,
  iconGridRef,
  renderIconTile,
}: ArrCatalogStandardBodyProps<TRow>): JSX.Element {
  return (
    <ArrCatalogBodyChrome
      summaryLine={summaryLine}
      onRefresh={onRefresh}
      loading={loading}
      loadingHint={loadingHint}
      footer={
        showPagination ? (
          <ArrCatalogPagination
            page={page}
            totalPages={totalPages}
            total={total}
            itemNoun={itemNoun}
            pageSize={pageSize}
            loading={loading}
            onPageChange={onPageChange}
          />
        ) : null
      }
    >
      <ArrCatalogEmptyBranch
        order={emptyOrder}
        showCatalogEmptyHint={showCatalogEmptyHint}
        hasRows={hasRows}
        catalogEmptyMessage={catalogEmptyMessage}
        noMatchMessage={noMatchMessage}
      >
        <ArrCatalogListOrGrid
          browseMode={browseMode}
          rows={rows}
          rowOrder={rowOrder}
          rowsStore={rowsStore}
          columns={columns}
          getRowKey={getRowKey}
          onRowSelect={onRowSelect}
          iconGridRef={iconGridRef}
          renderIconTile={renderIconTile}
        />
      </ArrCatalogEmptyBranch>
    </ArrCatalogBodyChrome>
  );
}
