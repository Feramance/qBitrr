import type { ColumnDef } from "@tanstack/react-table";
import { type JSX, type RefCallback } from "react";
import { getLidarrAlbums } from "../../api/client";
import type {
  ArrInfo,
  LidarrAlbumEntry,
  LidarrAlbumsResponse,
} from "../../api/types";
import { LidarrAlbumDetailBody } from "../../components/arr/LidarrAlbumDetailBody";
import {
  ArrCatalogBodyChrome,
  ArrCatalogPagination,
} from "./ArrCatalogBodyChrome";
import {
  ArrCatalogEmptyBranch,
  ArrCatalogListOrGrid,
} from "./ArrCatalogListOrGrid";
import { createStandardArrFilters } from "./createStandardArrFilters";
import type { ArrCatalogDefinition } from "./definition";
import { useInstancePagedFetch } from "./useInstancePagedFetch";
import { categoryForInstanceLabel } from "./utils";
import type { RowsStore } from "../../utils/rowsStore";
import {
  filterLidarrAlbumRows,
  lidarrAlbumFlatRowKey,
  LIDARR_FLAT_HASH_FIELDS,
  summarizeLidarrAlbumRows,
  type LidarrAlbumFlatRow,
} from "./lidarrCatalogModes";

const LIDARR_FLAT_PAGE_SIZE = 50;

interface LidarrFlatFilters extends Record<string, unknown> {
  readonly onlyMissing: boolean;
  readonly reasonFilter: string;
}

function buildLidarrFlatColumns(
  instanceCount: number,
): ColumnDef<LidarrAlbumFlatRow>[] {
  const cols: ColumnDef<LidarrAlbumFlatRow>[] = [];
  if (instanceCount > 1) {
    cols.push({
      id: "instance",
      header: "Instance",
      cell: ({ row }) => row.original.__instance,
    });
  }
  cols.push(
    {
      id: "album",
      header: "Album",
      cell: ({ row }) => {
        const album = row.original.album as Record<string, unknown>;
        return String(album?.["title"] ?? "—");
      },
    },
    {
      id: "artistName",
      header: "Artist",
      cell: ({ row }) => {
        const album = row.original.album as Record<string, unknown>;
        return String(album?.["artistName"] ?? "—");
      },
    },
    {
      id: "releaseDate",
      header: "Release",
      cell: ({ row }) => {
        const album = row.original.album as Record<string, unknown>;
        const date = album?.["releaseDate"] as string | undefined;
        return date ? new Date(date).toLocaleDateString() : "—";
      },
    },
    {
      id: "monitored",
      header: "Monitored",
      cell: ({ row }) => {
        const album = row.original.album as Record<string, unknown>;
        const monitored = Boolean(album?.["monitored"]);
        return (
          <span className={`track-status ${monitored ? "available" : "missing"}`}>
            {monitored ? "✓" : "✗"}
          </span>
        );
      },
    },
    {
      id: "hasFile",
      header: "Has File",
      cell: ({ row }) => {
        const album = row.original.album as Record<string, unknown>;
        const hasFile = Boolean(album?.["hasFile"]);
        return (
          <span className={`track-status ${hasFile ? "available" : "missing"}`}>
            {hasFile ? "✓" : "✗"}
          </span>
        );
      },
    },
    {
      id: "qualityProfileName",
      header: "Quality profile",
      cell: ({ row }) => {
        const album = row.original.album as Record<string, unknown>;
        return String(album?.["qualityProfileName"] ?? "—");
      },
    },
    {
      id: "reason",
      header: "Reason",
      cell: ({ row }) => {
        const album = row.original.album as Record<string, unknown>;
        const reason = album?.["reason"] as string | null | undefined;
        return reason ? (
          <span className="table-badge table-badge-reason">{reason}</span>
        ) : (
          <span className="table-badge table-badge-reason">Not being searched</span>
        );
      },
    },
  );
  return cols;
}

export const LIDARR_FLAT_DEFINITION: ArrCatalogDefinition<
  LidarrAlbumFlatRow,
  LidarrAlbumFlatRow,
  LidarrFlatFilters,
  LidarrAlbumEntry,
  LidarrAlbumFlatRow,
  LidarrAlbumFlatRow,
  LidarrAlbumsResponse,
  null
> = {
  kind: "lidarr",
  arrType: "lidarr",
  cardTitle: "Lidarr",
  allInstancesLabel: "All Lidarr",
  searchPlaceholder: "Filter albums",
  initialFilters: { onlyMissing: false, reasonFilter: "all" },
  filterControls: createStandardArrFilters<LidarrFlatFilters>("All Albums"),
  aggregate: {
    basePageSize: LIDARR_FLAT_PAGE_SIZE,
    initialRollup: null,
    initialSummary: { available: 0, monitored: 0, missing: 0, total: 0 },
    fetchPage: (category, pageIdx, chunk, filters) =>
      getLidarrAlbums(category, pageIdx, chunk, "", {
        missingOnly: filters.onlyMissing,
        reasonFilter:
          filters.reasonFilter !== "all" ? filters.reasonFilter : null,
      }),
    extractSlice: (response) => ({
      slice: response.albums ?? [],
      batchLength: (response.albums ?? []).length,
      total: response.total,
      pageSize: response.page_size,
    }),
    mapSlice: (response, instanceLabel, push) => {
      for (const entry of response.albums ?? []) {
        push({ ...entry, __instance: instanceLabel } as LidarrAlbumFlatRow);
      }
    },
    summarize: (rows) => summarizeLidarrAlbumRows(rows),
    getRowKey: lidarrAlbumFlatRowKey,
    hashFields: LIDARR_FLAT_HASH_FIELDS as unknown as ReadonlyArray<
      keyof LidarrAlbumFlatRow & string
    >,
    filterRows: (rows, filters, debouncedSearch) =>
      filterLidarrAlbumRows(rows, filters, debouncedSearch),
    sortRows: (rows) =>
      [...rows].sort((a, b) => {
        const ai = (a.__instance || "").toLowerCase();
        const bi = (b.__instance || "").toLowerCase();
        if (ai !== bi) return ai.localeCompare(bi);
        const an = String(
          (a.album as Record<string, unknown>)["title"] || "",
        ).toLowerCase();
        const bn = String(
          (b.album as Record<string, unknown>)["title"] || "",
        ).toLowerCase();
        return an.localeCompare(bn);
      }),
  },
  useInstancePipeline: (params) =>
    useInstancePagedFetch<
      LidarrAlbumFlatRow,
      LidarrAlbumsResponse,
      LidarrFlatFilters
    >(params, {
      basePageSize: LIDARR_FLAT_PAGE_SIZE,
      getRowKey: lidarrAlbumFlatRowKey,
      hashFields: LIDARR_FLAT_HASH_FIELDS as unknown as ReadonlyArray<
        keyof LidarrAlbumFlatRow & string
      >,
      buildKey: ({ category, query, filters }) =>
        `${category}::${query}::m:${filters.onlyMissing ? "1" : ""}::r:${filters.reasonFilter}`,
      fetchPage: (category, page, pageSize, query, filters) =>
        getLidarrAlbums(category, page, pageSize, query, {
          missingOnly: filters.onlyMissing,
          reasonFilter:
            filters.reasonFilter !== "all" ? filters.reasonFilter : null,
        }),
      extractPage: (response) => {
        const rows = (response.albums ?? []).map(
          (entry) => entry as LidarrAlbumFlatRow,
        );
        return {
          rows,
          page: response.page ?? 0,
          pageSize: response.page_size ?? LIDARR_FLAT_PAGE_SIZE,
          total: response.total ?? rows.length,
        };
      },
      isCatalogEmpty: (response) =>
        (response.albums ?? []).length === 0 && (response.total ?? 0) === 0,
      keepAllPages: false,
      errorMessage: (category) => `Failed to load ${category} albums`,
    }),
  buildAggregateSelection: (row, instances) => ({
    id: lidarrAlbumFlatRowKey(row),
    source: "aggregate",
    seed: row,
    extras: {
      category: categoryForInstanceLabel([...instances], row.__instance),
    },
  }),
  buildInstanceSelection: (row, selectionCategory) => ({
    id: lidarrAlbumFlatRowKey(row),
    source: "instance",
    seed: row,
    extras: { category: selectionCategory },
  }),
  getModalLiveRow: ({
    source,
    instanceFresh,
    aggregateFresh,
    instanceSeed,
    aggregateSeed,
  }) => {
    if (source === "instance") {
      return (instanceFresh ?? instanceSeed) as LidarrAlbumFlatRow;
    }
    return (aggregateFresh ?? aggregateSeed) as LidarrAlbumFlatRow;
  },
  getModalTitle: (liveRow) => {
    const album = liveRow.album as Record<string, unknown>;
    return String(album?.["title"] ?? "Album");
  },
  getModalMaxWidth: () => 720,
  renderModalBody: ({ liveRow, extras }) => (
    <LidarrAlbumDetailBody
      entry={liveRow}
      category={String(extras.category ?? "")}
    />
  ),
  renderAggregateBody: (props) => <LidarrFlatAggregateBody {...props} />,
  renderInstanceBody: (props) => <LidarrFlatInstanceBody {...props} />,
};

function LidarrFlatAggregateBody({
  rows,
  rowOrder,
  rowsStore,
  loading,
  emptyStateReady,
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
  instanceCount,
}: {
  readonly rows: ReadonlyArray<LidarrAlbumFlatRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<LidarrAlbumFlatRow>;
  readonly loading: boolean;
  readonly emptyStateReady: boolean;
  readonly total: number;
  readonly page: number;
  readonly totalPages: number;
  readonly aggregatePageSize: number;
  readonly summary: { available: number; monitored: number; missing: number; total: number };
  readonly lastUpdated: string | null;
  readonly isAggFiltered: boolean;
  readonly onPageChange: (page: number) => void;
  readonly onRefresh: () => void;
  readonly onRowSelect: (row: LidarrAlbumFlatRow) => void;
  readonly browseMode: "list" | "icon";
  readonly iconGridRef: RefCallback<HTMLElement | null>;
  readonly instances: ReadonlyArray<ArrInfo>;
  readonly instanceCount: number;
}): JSX.Element {
  const columns = buildLidarrFlatColumns(instanceCount);
  const effectiveLoading =
    loading || (instanceCount > 0 && !emptyStateReady && total === 0);
  return (
    <ArrCatalogBodyChrome
      summaryLine={
        <>
          Flat album list across all instances{" "}
          {lastUpdated ? `(updated ${lastUpdated})` : ""}
          <br />
          <strong>Albums:</strong> {summary.total.toLocaleString()} •{" "}
          <strong>Available:</strong> {summary.available.toLocaleString()} •{" "}
          <strong>Monitored:</strong> {summary.monitored.toLocaleString()} •{" "}
          <strong>Missing:</strong> {summary.missing.toLocaleString()}
          {isAggFiltered && total < summary.total ? (
            <> • <strong>Filtered:</strong> {total.toLocaleString()}</>
          ) : null}
        </>
      }
      onRefresh={onRefresh}
      loading={effectiveLoading}
      loadingHint="Loading Lidarr albums…"
      footer={
        total > 0 ? (
          <ArrCatalogPagination
            page={page}
            totalPages={totalPages}
            total={total}
            itemNoun="albums"
            pageSize={aggregatePageSize}
            loading={effectiveLoading}
            onPageChange={onPageChange}
          />
        ) : null
      }
    >
      <ArrCatalogEmptyBranch
        order="syncFirst"
        showCatalogEmptyHint={!effectiveLoading && total === 0 && summary.total === 0 && instanceCount > 0}
        hasRows={total > 0}
        catalogEmptyMessage="No albums found in the local catalog."
        noMatchMessage="No albums match the current filters."
      >
        <ArrCatalogListOrGrid
          browseMode={browseMode}
          rows={rows}
          rowOrder={rowOrder}
          rowsStore={rowsStore}
          columns={columns}
          getRowKey={lidarrAlbumFlatRowKey}
          onRowSelect={onRowSelect}
          iconGridRef={iconGridRef}
          renderIconTile={(row) => {
            const album = row.album as Record<string, unknown>;
            const title = String(album?.["title"] ?? "—");
            const artist = String(album?.["artistName"] ?? "—");
            return (
              <div className="arr-movie-tile arr-movie-tile--text" key={lidarrAlbumFlatRowKey(row)}>
                {instanceCount > 1 ? (
                  <div className="arr-movie-tile__instance">{row.__instance}</div>
                ) : null}
                <div className="arr-movie-tile__title">{title}</div>
                <div className="arr-movie-tile__meta">{artist}</div>
              </div>
            );
          }}
        />
      </ArrCatalogEmptyBranch>
    </ArrCatalogBodyChrome>
  );
}

function LidarrFlatInstanceBody({
  visibleRows,
  rowOrder,
  rowsStore,
  loading,
  emptyStateReady,
  page,
  pageSize,
  totalPages,
  totalItems,
  lastUpdated,
  browseMode,
  iconGridRef,
  showCatalogEmptyHint,
  onRowSelect,
  setPage,
  refresh,
}: {
  readonly visibleRows: ReadonlyArray<LidarrAlbumFlatRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<LidarrAlbumFlatRow>;
  readonly loading: boolean;
  readonly emptyStateReady: boolean;
  readonly page: number;
  readonly pageSize: number;
  readonly totalPages: number;
  readonly totalItems: number;
  readonly lastUpdated: string | null;
  readonly browseMode: "list" | "icon";
  readonly iconGridRef: RefCallback<HTMLElement | null>;
  readonly showCatalogEmptyHint: boolean;
  readonly onRowSelect: (row: LidarrAlbumFlatRow) => void;
  readonly setPage: (page: number) => void;
  readonly refresh: () => void;
}): JSX.Element {
  const effectiveLoading = loading || (!emptyStateReady && visibleRows.length === 0);
  const columns = buildLidarrFlatColumns(1);
  return (
    <ArrCatalogBodyChrome
      summaryLine={
        <>
          <strong>Albums shown:</strong> {visibleRows.length.toLocaleString()} •{" "}
          <strong>Albums total:</strong> {totalItems.toLocaleString()}
          {lastUpdated ? ` (updated ${lastUpdated})` : ""}
        </>
      }
      onRefresh={refresh}
      loading={effectiveLoading}
      loadingHint="Loading albums…"
      footer={
        totalPages > 1 ? (
          <ArrCatalogPagination
            page={page}
            totalPages={totalPages}
            total={totalItems}
            itemNoun="albums"
            pageSize={pageSize}
            loading={effectiveLoading}
            onPageChange={setPage}
          />
        ) : null
      }
    >
      {showCatalogEmptyHint ? (
        <div className="hint catalog-sync-hint">No albums in the local catalog yet.</div>
      ) : visibleRows.length ? (
        <ArrCatalogListOrGrid
          browseMode={browseMode}
          rows={visibleRows}
          rowOrder={rowOrder}
          rowsStore={rowsStore}
          columns={columns}
          getRowKey={lidarrAlbumFlatRowKey}
          onRowSelect={onRowSelect}
          iconGridRef={iconGridRef}
          renderIconTile={(row) => {
            const album = row.album as Record<string, unknown>;
            return (
              <div className="arr-movie-tile arr-movie-tile--text" key={lidarrAlbumFlatRowKey(row)}>
                <div className="arr-movie-tile__title">
                  {String(album?.["title"] ?? "—")}
                </div>
                <div className="arr-movie-tile__meta">
                  {String(album?.["artistName"] ?? "—")}
                </div>
              </div>
            );
          }}
        />
      ) : (
        <div className="hint">No albums match the current filters.</div>
      )}
    </ArrCatalogBodyChrome>
  );
}
