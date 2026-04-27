import { memo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from "@tanstack/react-table";

interface StableTableProps<TData> {
  data: TData[];
  columns: ColumnDef<TData, unknown>[];
  getRowKey?: (row: TData) => string;
  onRowClick?: (row: TData) => void;
}

function StableTableInner<TData>({
  data,
  columns,
  getRowKey,
  onRowClick,
}: StableTableProps<TData>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
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
                        header.getContext()
                      )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const stableKey = getRowKey ? getRowKey(row.original) : row.id;
            return (
              <tr
                key={stableKey}
                onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                style={onRowClick ? { cursor: "pointer" } : undefined}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} data-label={String(cell.column.columnDef.header)}>
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

export const StableTable = memo(StableTableInner, (prevProps, nextProps) => {
  return (
    prevProps.data === nextProps.data &&
    prevProps.columns === nextProps.columns &&
    prevProps.onRowClick === nextProps.onRowClick
  );
}) as typeof StableTableInner;
