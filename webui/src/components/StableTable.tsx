import { memo, useCallback, useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type Row,
  type Table,
} from "@tanstack/react-table";
import {
  useRowSnapshot,
  useRowVersion,
} from "../hooks/useRowsStore";
import type { RowsStore } from "../utils/rowsStore";
import type { Hashable } from "../utils/dataSync";

/**
 * Two render modes:
 *
 * 1. **Legacy `data` mode** (existing call sites):
 *    Caller passes a `data` array.  Behaves exactly as before — tanstack-table is the source
 *    of truth and cells read `row.original`.
 *
 * 2. **Store mode** (new — used by Radarr / Sonarr / Lidarr browse views):
 *    Caller passes `rowOrder` + `rowsStore`.  StableTable subscribes per-row to the store so
 *    only the rows whose data actually ticked re-render their cells.  The outer table layout
 *    and DOM nodes for unchanged rows are preserved across update-only polls.
 *
 * In both modes a `getRowKey` function provides the stable React/tanstack-table id.
 */

type LegacyProps<TData> = {
  data: TData[];
  rowsStore?: undefined;
  rowOrder?: undefined;
  columns: ColumnDef<TData, unknown>[];
  getRowKey?: (row: TData) => string;
  onRowClick?: (row: TData) => void;
};

// Storeful mode requires `Hashable` because the underlying `RowsStore` carries that
// constraint (it diffs rows via the shared dataSync helpers).  Legacy mode does NOT —
// callers like QbitCategoriesView pass strict interfaces without index signatures, and
// the legacy branch only forwards the array to tanstack-table, which doesn't care.
type StorefulProps<TData extends Hashable> = {
  data?: undefined;
  rowsStore: RowsStore<TData>;
  rowOrder: readonly string[];
  columns: ColumnDef<TData, unknown>[];
  getRowKey?: (row: TData) => string;
  onRowClick?: (row: TData) => void;
};

type StableTableProps<TData> =
  | LegacyProps<TData>
  | (TData extends Hashable ? StorefulProps<TData> : never);

function isStorefulProps<TData>(
  props: StableTableProps<TData>,
): props is TData extends Hashable ? StorefulProps<TData> : never {
  return (props as { rowsStore?: unknown }).rowsStore !== undefined;
}

function StableTableInner<TData>(props: StableTableProps<TData>) {
  const { columns, getRowKey, onRowClick } = props;

  // Pass `getRowId` so tanstack-table keys row models against our stable id rather than
  // the array index — keeps cell DOM nodes stable across update-only polls.
  const tableGetRowId = useMemo(() => {
    if (!getRowKey) return undefined;
    return (row: TData) => getRowKey(row);
  }, [getRowKey]);

  // Build a phantom data array for tanstack-table when in storeful mode.
  //
  // Critically: this array's reference is memoised on the **rowOrder** slice only, so an
  // update-only poll (rowOrder unchanged) keeps the same array reference and tanstack-table
  // does not rebuild its row model.  Per-row freshness is delivered via the per-id store
  // subscriptions in <StableRow /> below.
  const isStoreful = isStorefulProps(props);
  const storefulRowOrder = isStoreful ? props.rowOrder : null;
  const storefulRowsStore = isStoreful
    ? (props.rowsStore as unknown as RowsStore<Hashable>)
    : null;
  const stableData = useMemo<TData[]>(() => {
    if (!isStoreful) return (props as LegacyProps<TData>).data;
    const out: TData[] = [];
    const store = storefulRowsStore!;
    for (const id of storefulRowOrder!) {
      const row = store.getRow(id);
      if (row !== undefined) out.push(row as TData);
    }
    return out;
    // We intentionally only depend on `rowOrder` here.  Update-only polls keep the same
    // `rowOrder` reference, so the memo stays fresh and tanstack-table is unbothered.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    storefulRowOrder ?? (props as LegacyProps<TData>).data,
    storefulRowsStore,
  ]);

  const table = useReactTable({
    data: stableData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    ...(tableGetRowId ? { getRowId: tableGetRowId } : {}),
  });

  return (
    <div className="table-wrapper">
      <table className="responsive-table">
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id}>
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const stableKey = getRowKey ? getRowKey(row.original) : row.id;
            if (isStoreful) {
              return (
                <StableRow<Hashable>
                  key={stableKey}
                  id={stableKey}
                  rowsStore={storefulRowsStore!}
                  table={table as unknown as Table<Hashable>}
                  rowProto={row as unknown as Row<Hashable>}
                  onRowClick={
                    onRowClick as unknown as
                      | ((row: Hashable) => void)
                      | undefined
                  }
                />
              );
            }
            return (
              <tr
                key={stableKey}
                onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                style={onRowClick ? { cursor: "pointer" } : undefined}
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    data-label={String(cell.column.columnDef.header)}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface StableRowProps<TData extends Hashable> {
  id: string;
  rowsStore: RowsStore<TData>;
  table: Table<TData>;
  rowProto: Row<TData>;
  onRowClick?: (row: TData) => void;
}

/**
 * Per-row body for store mode.
 *
 * Subscribes to the store by id (so update-only polls re-render this row only when its data
 * version ticks).  Renders cells via tanstack-table's column definitions to keep the cell API
 * the same as legacy mode.
 */
function StableRowInner<TData extends Hashable>({
  id,
  rowsStore,
  rowProto,
  onRowClick,
}: StableRowProps<TData>) {
  const fresh = useRowSnapshot(rowsStore, id);
  // Subscribe to the version too so we re-render even if the store decides to swap a row
  // payload to an object that compares ===-equal to the previous one (defensive).
  useRowVersion(rowsStore, id);

  const item = fresh ?? rowProto.original;
  const handleClick = useCallback(() => {
    if (onRowClick && item) onRowClick(item);
  }, [onRowClick, item]);

  if (!item) return null;

  return (
    <tr
      onClick={onRowClick ? handleClick : undefined}
      style={onRowClick ? { cursor: "pointer" } : undefined}
    >
      {rowProto.getVisibleCells().map((cell) => {
        // Build a context that uses the freshest row payload from the store.  We reuse the
        // tanstack-table context object to keep `cell.getValue()` etc. working, but the
        // `row.original` field points to our store's freshest item.
        const baseCtx = cell.getContext();
        const freshCtx = {
          ...baseCtx,
          row: { ...baseCtx.row, original: item } as typeof baseCtx.row,
        };
        return (
          <td key={cell.id} data-label={String(cell.column.columnDef.header)}>
            {flexRender(cell.column.columnDef.cell, freshCtx)}
          </td>
        );
      })}
    </tr>
  );
}

const StableRow = memo(StableRowInner) as typeof StableRowInner;

export const StableTable = memo(StableTableInner, (prevProps, nextProps) => {
  // L-2: include every relevant prop in the comparator. The previous version skipped
  // `getRowKey`, so swapping the row id function (e.g. switching from per-instance to
  // aggregate mode) used to silently keep the previous row identity.
  return (
    prevProps.data === nextProps.data &&
    prevProps.rowsStore === nextProps.rowsStore &&
    prevProps.rowOrder === nextProps.rowOrder &&
    prevProps.columns === nextProps.columns &&
    prevProps.onRowClick === nextProps.onRowClick &&
    prevProps.getRowKey === nextProps.getRowKey
  );
}) as typeof StableTableInner;
