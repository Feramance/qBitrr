import type { ColumnDef } from "@tanstack/react-table";
import { type JSX } from "react";
import { getRadarrMovies } from "../../api/client";
import type {
  ArrInfo,
  RadarrMovie,
  RadarrMoviesResponse,
} from "../../api/types";
import { RadarrMovieDetailBody } from "../../components/arr/RadarrMovieDetailBody";
import { StableTable } from "../../components/StableTable";
import { summarizeAggregateMonitoredRows } from "../../constants/arrAggregateFetch";
import { ARR_CATALOG_SYNC_HINT } from "../../constants/arrCatalogMessages";
import { radarrMovieThumbnailUrl } from "../../utils/arrThumbnailUrl";
import { ArrCatalogIconTile } from "./ArrCatalogIconTile";
import {
  ArrCatalogBodyChrome,
  ArrCatalogPagination,
} from "./ArrCatalogBodyChrome";
import type { ArrCatalogDefinition } from "./definition";
import { ARR_CATALOG_REGISTRY } from "./registry";
import { useInstancePagedFetch } from "./useInstancePagedFetch";
import { categoryForInstanceLabel } from "./utils";

const RADARR_PAGE_SIZE = 50;

interface RadarrFilters extends Record<string, unknown> {
  readonly onlyMissing: boolean;
  readonly reasonFilter: string;
}

type RadarrInstanceRow = RadarrMovie & Record<string, unknown>;

interface RadarrAggRow extends RadarrMovie {
  __instance: string;
  [key: string]: unknown;
}

const RADARR_HASH_FIELDS = [
  "title",
  "year",
  "hasFile",
  "monitored",
  "reason",
] as const;

const RADARR_AGG_HASH_FIELDS = [
  "__instance",
  "title",
  "year",
  "hasFile",
  "monitored",
  "reason",
] as const;

function radarrFilterRows<T extends RadarrMovie>(
  rows: ReadonlyArray<T>,
  filters: RadarrFilters,
): ReadonlyArray<T> {
  let out: ReadonlyArray<T> = rows;
  if (filters.onlyMissing) {
    out = out.filter((m) => !m.hasFile);
  }
  if (filters.reasonFilter !== "all") {
    if (filters.reasonFilter === "Not being searched") {
      out = out.filter(
        (m) => m.reason === "Not being searched" || !m.reason,
      );
    } else {
      out = out.filter((m) => m.reason === filters.reasonFilter);
    }
  }
  return out;
}

function buildRadarrInstanceColumns(): ColumnDef<RadarrInstanceRow>[] {
  return [
    { accessorKey: "title", header: "Title", cell: (info) => info.getValue() },
    { accessorKey: "year", header: "Year", size: 80 },
    {
      accessorKey: "monitored",
      header: "Monitored",
      cell: (info) => {
        const monitored = info.getValue() as boolean;
        return (
          <span className={`track-status ${monitored ? "available" : "missing"}`}>
            {monitored ? "✓" : "✗"}
          </span>
        );
      },
      size: 100,
    },
    {
      accessorKey: "hasFile",
      header: "Has File",
      cell: (info) => {
        const hasFile = info.getValue() as boolean;
        return (
          <span className={`track-status ${hasFile ? "available" : "missing"}`}>
            {hasFile ? "✓" : "✗"}
          </span>
        );
      },
      size: 100,
    },
    {
      accessorKey: "qualityProfileName",
      header: "Quality Profile",
      cell: (info) => {
        const name = info.getValue() as string | null | undefined;
        return name || "—";
      },
      size: 150,
    },
    {
      accessorKey: "reason",
      header: "Reason",
      cell: (info) => {
        const reason = info.getValue() as string | null;
        if (!reason) {
          return (
            <span className="table-badge table-badge-reason">
              Not being searched
            </span>
          );
        }
        return (
          <span className="table-badge table-badge-reason">{reason}</span>
        );
      },
      size: 120,
    },
  ];
}

function buildRadarrAggColumns(
  instanceCount: number,
): ColumnDef<RadarrAggRow>[] {
  const cols: ColumnDef<RadarrAggRow>[] = [];
  if (instanceCount > 1) {
    cols.push({
      accessorKey: "__instance",
      header: "Instance",
      size: 150,
    });
  }
  cols.push(...(buildRadarrInstanceColumns() as ColumnDef<RadarrAggRow>[]));
  return cols;
}

function radarrInstanceRowKey(row: RadarrInstanceRow): string {
  return `${row.title}-${row.year}`;
}

function radarrAggRowKey(row: RadarrAggRow): string {
  return `${row.__instance}-${row.title}-${row.year}`;
}

function radarrAggThumbnail(
  row: RadarrAggRow,
  instances: ReadonlyArray<ArrInfo>,
): string {
  const cat = categoryForInstanceLabel([...instances], row.__instance);
  return row.id != null && cat ? radarrMovieThumbnailUrl(cat, row.id) : "";
}

export const RADARR_DEFINITION: ArrCatalogDefinition<
  RadarrInstanceRow,
  RadarrAggRow,
  RadarrFilters,
  RadarrMovie,
  RadarrAggRow,
  RadarrMovie | RadarrAggRow,
  RadarrMoviesResponse,
  null
> = {
  kind: "radarr",
  arrType: "radarr",
  cardTitle: "Radarr",
  allInstancesLabel: "All Radarr",
  searchPlaceholder: "Filter movies",
  initialFilters: { onlyMissing: false, reasonFilter: "all" },
  filterControls: [
    {
      id: "status",
      label: "Status",
      mode: "always",
      options: [
        { value: "all", label: "All Movies" },
        { value: "missing", label: "Missing Only" },
      ],
      getValue: (f) => (f.onlyMissing ? "missing" : "all"),
      setValue: (prev, next) => ({ ...prev, onlyMissing: next === "missing" }),
    },
    {
      id: "reason",
      label: "Search Reason",
      mode: "always",
      options: [
        { value: "all", label: "All Reasons" },
        { value: "Not being searched", label: "Not Being Searched" },
        { value: "Missing", label: "Missing" },
        { value: "Quality", label: "Quality" },
        { value: "CustomFormat", label: "Custom Format" },
        { value: "Upgrade", label: "Upgrade" },
      ],
      getValue: (f) => f.reasonFilter,
      setValue: (prev, next) => ({ ...prev, reasonFilter: next }),
    },
  ],
  aggregate: {
    basePageSize: RADARR_PAGE_SIZE,
    initialRollup: null,
    initialSummary: { available: 0, monitored: 0, missing: 0, total: 0 },
    fetchPage: (category, pageIdx, chunk) =>
      getRadarrMovies(category, pageIdx, chunk, ""),
    extractSlice: (response) => ({
      slice: response.movies ?? [],
      batchLength: (response.movies ?? []).length,
      total: response.total,
      pageSize: response.page_size,
    }),
    mapSlice: (response, instanceLabel, push) => {
      (response.movies ?? []).forEach((movie) => {
        push({ ...movie, __instance: instanceLabel } as RadarrAggRow);
      });
    },
    summarize: (rows) => summarizeAggregateMonitoredRows([...rows]),
    getRowKey: radarrAggRowKey,
    hashFields: RADARR_AGG_HASH_FIELDS as unknown as ReadonlyArray<
      keyof RadarrAggRow & string
    >,
    filterRows: (rows, filters, debouncedSearch) => {
      const q = debouncedSearch ? debouncedSearch.toLowerCase() : "";
      const hasSearch = Boolean(q);
      const filtered = rows.filter((row) => {
        if (hasSearch) {
          const title = String(row.title ?? "").toLowerCase();
          const inst = String(row.__instance ?? "").toLowerCase();
          if (!title.includes(q) && !inst.includes(q)) return false;
        }
        return true;
      });
      return radarrFilterRows<RadarrAggRow>(filtered, filters);
    },
  },
  useInstancePipeline: (params) =>
    useInstancePagedFetch<RadarrInstanceRow, RadarrMoviesResponse, RadarrFilters>(
      params,
      {
        basePageSize: RADARR_PAGE_SIZE,
        getRowKey: radarrInstanceRowKey,
        hashFields: RADARR_HASH_FIELDS as unknown as ReadonlyArray<
          keyof RadarrInstanceRow & string
        >,
        buildKey: ({ category, query }) => `${category}::${query}`,
        fetchPage: (category, page, pageSize, query) =>
          getRadarrMovies(category, page, pageSize, query),
        extractPage: (response) => ({
          rows: (response.movies ?? []) as ReadonlyArray<RadarrInstanceRow>,
          page: response.page ?? 0,
          pageSize: response.page_size ?? RADARR_PAGE_SIZE,
          total: response.total ?? (response.movies ?? []).length,
        }),
        keepAllPages: true,
        filterRows: (rows, filters) => radarrFilterRows(rows, filters),
        errorMessage: (category) => `Failed to load ${category} movies`,
      },
    ),
  buildAggregateSelection: (row, instances) => ({
    id: radarrAggRowKey(row),
    source: "aggregate",
    seed: row,
    extras: {
      category: categoryForInstanceLabel([...instances], row.__instance),
    },
  }),
  buildInstanceSelection: (row, selectionCategory) => ({
    id: radarrInstanceRowKey(row),
    source: "instance",
    seed: row as RadarrMovie,
    extras: { category: selectionCategory },
  }),
  getModalLiveRow: ({
    source,
    instanceFresh,
    aggregateFresh,
    instanceSeed,
    aggregateSeed,
  }) =>
    (source === "instance"
      ? instanceFresh ?? instanceSeed
      : aggregateFresh ?? aggregateSeed) as RadarrMovie | RadarrAggRow,
  getModalTitle: (liveRow) => String(liveRow.title ?? "Movie"),
  getModalMaxWidth: () => 520,
  renderModalBody: ({ liveRow, extras }) => (
    <RadarrMovieDetailBody
      movie={liveRow as RadarrMovie}
      category={String(extras.category ?? "")}
    />
  ),
  buildAggregateColumns: buildRadarrAggColumns,
  buildInstanceColumns: buildRadarrInstanceColumns,
  renderAggregateBody: (props) => (
    <RadarrAggregateBody {...props} />
  ),
  renderInstanceBody: (props) => (
    <RadarrInstanceBody {...props} />
  ),
};

ARR_CATALOG_REGISTRY.radarr = RADARR_DEFINITION;

interface RadarrAggregateBodyProps {
  readonly rows: ReadonlyArray<RadarrAggRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: import("../../utils/rowsStore").RowsStore<RadarrAggRow>;
  readonly loading: boolean;
  readonly total: number;
  readonly page: number;
  readonly totalPages: number;
  readonly aggregatePageSize: number;
  readonly summary: import("./definition").ArrCatalogSummary;
  readonly lastUpdated: string | null;
  readonly isAggFiltered: boolean;
  readonly onPageChange: (page: number) => void;
  readonly onRefresh: () => void;
  readonly onRowSelect: (row: RadarrAggRow) => void;
  readonly browseMode: "list" | "icon";
  readonly iconGridRef: React.RefCallback<HTMLElement | null>;
  readonly instances: ReadonlyArray<ArrInfo>;
  readonly instanceCount: number;
}

function RadarrAggregateBody({
  rows,
  rowOrder,
  rowsStore,
  loading,
  total,
  page,
  totalPages,
  aggregatePageSize,
  summary,
  lastUpdated,
  isAggFiltered,
  onPageChange,
  onRefresh,
  onRowSelect,
  browseMode,
  iconGridRef,
  instances,
  instanceCount,
}: RadarrAggregateBodyProps): JSX.Element {
  const columns = buildRadarrAggColumns(instanceCount);
  const summaryLine = (
    <>
      Aggregated movies across all instances{" "}
      {lastUpdated ? `(updated ${lastUpdated})` : ""}
      <br />
      <strong>Available:</strong>{" "}
      {summary.available.toLocaleString(undefined, { maximumFractionDigits: 0 })}{" "}
      • <strong>Monitored:</strong>{" "}
      {summary.monitored.toLocaleString(undefined, { maximumFractionDigits: 0 })}{" "}
      • <strong>Missing:</strong>{" "}
      {summary.missing.toLocaleString(undefined, { maximumFractionDigits: 0 })}{" "}
      • <strong>Total:</strong>{" "}
      {summary.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      {isAggFiltered && total < summary.total ? (
        <>
          {" "}• <strong>Filtered:</strong>{" "}
          {total.toLocaleString(undefined, { maximumFractionDigits: 0 })} of{" "}
          {summary.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </>
      ) : null}
    </>
  );

  const showCatalogEmptyHint =
    !loading && total === 0 && summary.total === 0 && instanceCount > 0;

  return (
    <ArrCatalogBodyChrome
      summaryLine={summaryLine}
      onRefresh={onRefresh}
      loading={loading}
      loadingHint="Loading Radarr library…"
      footer={
        total > 0 ? (
          <ArrCatalogPagination
            page={page}
            totalPages={totalPages}
            total={total}
            itemNoun="items"
            pageSize={aggregatePageSize}
            loading={loading}
            onPageChange={onPageChange}
          />
        ) : null
      }
    >
      {showCatalogEmptyHint ? (
        <div className="hint">
          <p>No movies found in the local catalog.</p>
          <p>{ARR_CATALOG_SYNC_HINT}</p>
        </div>
      ) : total ? (
        browseMode === "list" ? (
          <StableTable<RadarrAggRow>
            rowsStore={rowsStore}
            rowOrder={rowOrder}
            columns={columns}
            getRowKey={radarrAggRowKey}
            onRowClick={onRowSelect}
          />
        ) : (
          <div className="arr-icon-grid" ref={iconGridRef}>
            {rows.map((row) => {
              const thumb = radarrAggThumbnail(row, instances);
              return (
                <ArrCatalogIconTile
                  key={radarrAggRowKey(row)}
                  posterSrc={thumb}
                  onClick={() => onRowSelect(row)}
                >
                  {instanceCount > 1 ? (
                    <div className="arr-movie-tile__instance">
                      {row.__instance}
                    </div>
                  ) : null}
                  <div className="arr-movie-tile__title">{row.title}</div>
                  <div className="arr-movie-tile__sub">
                    {row.year != null ? String(row.year) : ""}
                  </div>
                </ArrCatalogIconTile>
              );
            })}
          </div>
        )
      ) : (
        <div className="hint">No movies found.</div>
      )}
    </ArrCatalogBodyChrome>
  );
}

interface RadarrInstanceBodyProps {
  readonly visibleRows: ReadonlyArray<RadarrInstanceRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: import("../../utils/rowsStore").RowsStore<RadarrInstanceRow>;
  readonly loading: boolean;
  readonly page: number;
  readonly pageSize: number;
  readonly totalPages: number;
  readonly totalItems: number;
  readonly lastUpdated: string | null;
  readonly browseMode: "list" | "icon";
  readonly iconGridRef: React.RefCallback<HTMLElement | null>;
  readonly category: string;
  readonly showCatalogEmptyHint: boolean;
  readonly onRowSelect: (row: RadarrInstanceRow) => void;
  readonly setPage: (page: number) => void;
  readonly refresh: () => void;
}

function RadarrInstanceBody({
  visibleRows,
  rowOrder,
  rowsStore,
  loading,
  page,
  pageSize,
  totalPages,
  totalItems,
  lastUpdated,
  browseMode,
  iconGridRef,
  category,
  showCatalogEmptyHint,
  onRowSelect,
  setPage,
  refresh,
}: RadarrInstanceBodyProps): JSX.Element {
  const columns = buildRadarrInstanceColumns();
  const summaryLine = (
    <>
      <strong>Total:</strong>{" "}
      {totalItems.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      {lastUpdated ? ` (updated ${lastUpdated})` : ""}
    </>
  );

  return (
    <ArrCatalogBodyChrome
      summaryLine={summaryLine}
      onRefresh={refresh}
      loading={loading}
      loadingHint="Loading…"
      footer={
        totalPages > 1 ? (
          <ArrCatalogPagination
            page={page}
            totalPages={totalPages}
            total={totalItems}
            itemNoun="items"
            pageSize={pageSize}
            loading={loading}
            onPageChange={setPage}
          />
        ) : null
      }
    >
      {visibleRows.length ? (
        browseMode === "list" ? (
          <StableTable<RadarrInstanceRow>
            rowsStore={rowsStore}
            rowOrder={rowOrder}
            columns={columns}
            getRowKey={radarrInstanceRowKey}
            onRowClick={onRowSelect}
          />
        ) : (
          <div className="arr-icon-grid" ref={iconGridRef}>
            {visibleRows.map((row) => {
              const thumb =
                row.id != null && category
                  ? radarrMovieThumbnailUrl(category, row.id)
                  : "";
              return (
                <ArrCatalogIconTile
                  key={radarrInstanceRowKey(row)}
                  posterSrc={thumb}
                  onClick={() => onRowSelect(row)}
                >
                  <div className="arr-movie-tile__title">{row.title}</div>
                  <div className="arr-movie-tile__sub">
                    {row.year != null ? String(row.year) : ""}
                  </div>
                </ArrCatalogIconTile>
              );
            })}
          </div>
        )
      ) : showCatalogEmptyHint ? (
        <div className="hint">
          <p>No movies in the local catalog.</p>
          <p>{ARR_CATALOG_SYNC_HINT}</p>
        </div>
      ) : (
        <div className="hint">No movies match the current filters.</div>
      )}
    </ArrCatalogBodyChrome>
  );
}
