import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ColumnDef } from "@tanstack/react-table";
import type { Hashable } from "../../utils/dataSync";
import type { RowsStore } from "../../utils/rowsStore";
import {
  ArrCatalogEmptyBranch,
  ArrCatalogListOrGrid,
  ArrCatalogNoMatchHint,
  ArrCatalogSyncEmptyHint,
} from "./ArrCatalogListOrGrid";

vi.mock("../../components/StableTable", () => ({
  StableTable: ({
    rowOrder,
    onRowClick,
  }: {
    rowOrder: readonly string[];
    onRowClick: (row: { id: string; title: string }) => void;
    rowsStore: unknown;
  }) => (
    <div data-testid="stable-table">
      {rowOrder.map((key) => (
        <button key={key} type="button" onClick={() => onRowClick({ id: key, title: key })}>
          {key}
        </button>
      ))}
    </div>
  ),
}));

afterEach(() => {
  cleanup();
});

interface TestRow extends Hashable {
  id: string;
  title: string;
}

function makeStore(rows: TestRow[]): RowsStore<TestRow> {
  const rowsById = new Map(rows.map((row) => [row.id, row]));
  return {
    getSnapshot: () => ({
      rowOrder: rows.map((r) => r.id),
      rowsById,
      rowVersionsById: new Map(rows.map((r) => [r.id, 1])),
      rowHashesById: new Map(rows.map((r) => [r.id, r.id])),
      lastUpdate: 0,
      lastChangeKind: "noop",
    }),
    subscribe: () => () => undefined,
    getRow: (id: string) => rowsById.get(id),
    getRowVersion: () => 1,
  } as unknown as RowsStore<TestRow>;
}

const columns: ColumnDef<TestRow, unknown>[] = [{ accessorKey: "title", header: "Title" }];
const sampleRows: TestRow[] = [
  { id: "a", title: "Alpha" },
  { id: "b", title: "Beta" },
];

describe("ArrCatalog empty hint components", () => {
  it("sync hint includes catalog sync guidance", () => {
    render(<ArrCatalogSyncEmptyHint message="No movies yet." />);
    expect(screen.getByText(/No movies yet\./i)).toBeInTheDocument();
    expect(screen.getByText(/may still be syncing/i)).toBeInTheDocument();
  });

  it("no-match hint renders message only", () => {
    render(<ArrCatalogNoMatchHint message="No matches for filter." />);
    expect(screen.getByText(/No matches for filter\./i)).toBeInTheDocument();
  });
});

describe("ArrCatalogEmptyBranch ordering", () => {
  it("syncFirst: prefers sync hint over no-match when catalog empty", () => {
    render(
      <ArrCatalogEmptyBranch
        order="syncFirst"
        loading={false}
        showCatalogEmptyHint
        hasRows={false}
        catalogEmptyMessage="Sync empty"
        noMatchMessage="No match"
      >
        <div>content</div>
      </ArrCatalogEmptyBranch>,
    );
    expect(screen.getByText(/Sync empty/i)).toBeInTheDocument();
  });

  it("noItemsFirst: shows no-match before sync when rows absent", () => {
    render(
      <ArrCatalogEmptyBranch
        order="noItemsFirst"
        loading={false}
        showCatalogEmptyHint={false}
        hasRows={false}
        catalogEmptyMessage="Sync empty"
        noMatchMessage="No items"
      >
        <div>content</div>
      </ArrCatalogEmptyBranch>,
    );
    expect(screen.getByText(/No items/i)).toBeInTheDocument();
  });

  it("renders children when rows exist", () => {
    render(
      <ArrCatalogEmptyBranch
        order="syncFirst"
        loading={false}
        showCatalogEmptyHint={false}
        hasRows
        catalogEmptyMessage="Sync empty"
        noMatchMessage="No match"
      >
        <div>catalog-body</div>
      </ArrCatalogEmptyBranch>,
    );
    expect(screen.getByText(/catalog-body/i)).toBeInTheDocument();
  });

  it("hides empty hints while loading with no rows", () => {
    const { container } = render(
      <ArrCatalogEmptyBranch
        order="syncFirst"
        loading
        showCatalogEmptyHint
        hasRows={false}
        catalogEmptyMessage="Sync empty"
        noMatchMessage="No match"
      >
        <div>content</div>
      </ArrCatalogEmptyBranch>,
    );
    expect(container.firstChild).toBeNull();
    expect(screen.queryByText(/Sync empty/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/No match/i)).not.toBeInTheDocument();
  });

  it("keeps children while loading when rows exist", () => {
    render(
      <ArrCatalogEmptyBranch
        order="syncFirst"
        loading
        showCatalogEmptyHint={false}
        hasRows
        catalogEmptyMessage="Sync empty"
        noMatchMessage="No match"
      >
        <div>catalog-body</div>
      </ArrCatalogEmptyBranch>,
    );
    expect(screen.getByText(/catalog-body/i)).toBeInTheDocument();
  });
});

describe("ArrCatalogListOrGrid", () => {
  it("returns null when rows array is empty", () => {
    const { container } = render(
      <ArrCatalogListOrGrid
        browseMode="list"
        rows={[]}
        rowOrder={[]}
        rowsStore={makeStore([])}
        columns={columns}
        getRowKey={(row) => row.id}
        onRowSelect={vi.fn()}
        iconGridRef={() => undefined}
        renderIconTile={() => null}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders StableTable in list mode", () => {
    render(
      <ArrCatalogListOrGrid
        browseMode="list"
        rows={sampleRows}
        rowOrder={["a", "b"]}
        rowsStore={makeStore(sampleRows)}
        columns={columns}
        getRowKey={(row) => row.id}
        onRowSelect={vi.fn()}
        iconGridRef={() => undefined}
        renderIconTile={() => null}
      />,
    );
    expect(screen.getByTestId("stable-table")).toBeInTheDocument();
  });

  it("renders icon grid tiles in icon mode", () => {
    render(
      <ArrCatalogListOrGrid
        browseMode="icon"
        rows={sampleRows}
        rowOrder={["a", "b"]}
        rowsStore={makeStore(sampleRows)}
        columns={columns}
        getRowKey={(row) => row.id}
        onRowSelect={vi.fn()}
        iconGridRef={() => undefined}
        renderIconTile={(row) => <div data-testid="tile">{row.title}</div>}
      />,
    );
    expect(screen.getAllByTestId("tile")).toHaveLength(2);
    expect(screen.queryByTestId("stable-table")).not.toBeInTheDocument();
  });
});
