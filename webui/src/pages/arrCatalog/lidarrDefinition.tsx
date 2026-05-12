import type { ColumnDef } from "@tanstack/react-table";
import { type JSX, type RefCallback } from "react";
import { getLidarrArtists } from "../../api/client";
import type {
  ArrInfo,
  LidarrArtistBrowseEntry,
  LidarrArtistsResponse,
} from "../../api/types";
import { ArrMiniProgress } from "../../components/arr/ArrMiniProgress";
import { LidarrArtistDetailBody } from "../../components/arr/LidarrArtistDetailBody";
import { StableTable } from "../../components/StableTable";
import { ARR_CATALOG_SYNC_HINT } from "../../constants/arrCatalogMessages";
import { lidarrArtistThumbnailUrl } from "../../utils/arrThumbnailUrl";
import { ArrCatalogIconTile } from "./ArrCatalogIconTile";
import {
  ArrCatalogBodyChrome,
  ArrCatalogPagination,
} from "./ArrCatalogBodyChrome";
import type { ArrCatalogDefinition, ArrCatalogSummary } from "./definition";
import { ARR_CATALOG_REGISTRY } from "./registry";
import { useInstancePagedFetch } from "./useInstancePagedFetch";
import { categoryForInstanceLabel } from "./utils";
import type { RowsStore } from "../../utils/rowsStore";

const LIDARR_PAGE_SIZE = 50;

interface LidarrFilters extends Record<string, unknown> {
  readonly onlyMissing: boolean;
  readonly reasonFilter: string;
}

type LidarrInstanceRow = LidarrArtistBrowseEntry & Record<string, unknown>;

interface LidarrAggRow extends LidarrArtistBrowseEntry {
  __instance: string;
  [key: string]: unknown;
}

interface LidarrRollup {
  available: number;
  monitored: number;
  missing: number;
  rollupTotalAlbumsHint: number;
  // Tracks instances we've already accumulated to avoid double-counting on
  // multi-page loops (the loader calls `onInstanceFirstPage` exactly once per
  // instance, so we stamp on first call).
  seenInstances: ReadonlySet<string>;
}

const LIDARR_INSTANCE_HASH_FIELDS = ["artist"] as const;
const LIDARR_AGG_HASH_FIELDS = ["__instance", "artist"] as const;

/**
 * Ensure each browse row is `{ artist: { id, name, ... } }` and coerce numeric ids.
 * Handles flat rows or legacy `Title` if the API shape ever diverges.
 */
function normalizeLidarrBrowseRows(raw: readonly unknown[]): LidarrInstanceRow[] {
  const out: LidarrInstanceRow[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const o = item as Record<string, unknown>;
    let artist: Record<string, unknown>;
    const nested = o["artist"];
    if (nested && typeof nested === "object") {
      artist = { ...(nested as Record<string, unknown>) };
    } else if ("id" in o || "name" in o || "Title" in o) {
      artist = { ...o };
      if (artist["name"] === undefined && artist["Title"] !== undefined) {
        artist["name"] = artist["Title"];
      }
    } else {
      continue;
    }
    const rid = artist["id"];
    if (typeof rid === "string" && rid.trim() !== "") {
      const n = Number(rid);
      if (Number.isFinite(n)) {
        artist["id"] = n;
      }
    }
    out.push({ artist } as LidarrInstanceRow);
  }
  return out;
}

function lidarrArtistKey(artist: Record<string, unknown>): string {
  const rawId = artist?.["id"];
  const name = (artist?.["name"] as string | undefined) || "";
  if (typeof rawId === "number" && Number.isFinite(rawId)) {
    return `id:${rawId}`;
  }
  if (typeof rawId === "string" && rawId.trim() !== "") {
    const n = Number(rawId);
    if (Number.isFinite(n)) {
      return `id:${n}`;
    }
  }
  return `n:${name}`;
}

function lidarrInstanceRowKey(row: LidarrInstanceRow): string {
  const artist = row.artist as Record<string, unknown>;
  return lidarrArtistKey(artist);
}

function lidarrAggRowKey(row: LidarrAggRow): string {
  const artist = row.artist as Record<string, unknown>;
  return `${row.__instance}::${lidarrArtistKey(artist)}`;
}

function lidarrArtistTileStats(
  artist: Record<string, unknown>,
): JSX.Element {
  const monA = artist["albumsMonitored"];
  const availA = artist["albumsAvailable"];
  const missA = artist["albumsMissing"];
  const monT = artist["tracksMonitored"];
  const availT = artist["tracksAvailable"];
  const missT = artist["tracksMissing"];
  if (
    typeof monA === "number" &&
    typeof availA === "number" &&
    typeof missA === "number" &&
    typeof monT === "number" &&
    typeof availT === "number" &&
    typeof missT === "number"
  ) {
    return (
      <div className="arr-movie-tile__stats arr-movie-tile__stats--lidarr-artist">
        <ArrMiniProgress label="Albums" available={availA} missing={missA} />
        <ArrMiniProgress label="Tracks" available={availT} missing={missT} />
      </div>
    );
  }
  const albums = Number(artist?.["albumCount"] ?? 0);
  const tracks = Number(artist?.["trackTotalCount"] ?? 0);
  return (
    <div className="arr-movie-tile__stats arr-movie-tile__stats--lidarr-artist">
      <div>{albums.toLocaleString()} albums</div>
      <div>{tracks.toLocaleString()} tracks</div>
    </div>
  );
}

function buildLidarrInstanceColumns(): ColumnDef<LidarrInstanceRow>[] {
  return [
    {
      id: "artist",
      header: "Artist",
      cell: ({ row }) => {
        const a = row.original.artist as Record<string, unknown>;
        return String(a?.["name"] ?? "—");
      },
    },
    {
      id: "albums",
      header: "Albums",
      cell: ({ row }) => {
        const a = row.original.artist as Record<string, unknown>;
        return Number(a?.["albumCount"] ?? 0).toLocaleString();
      },
    },
    {
      id: "tracks",
      header: "Tracks",
      cell: ({ row }) => {
        const a = row.original.artist as Record<string, unknown>;
        return Number(a?.["trackTotalCount"] ?? 0).toLocaleString();
      },
    },
    {
      id: "monitored",
      header: "Monitored",
      cell: ({ row }) => {
        const a = row.original.artist as Record<string, unknown>;
        const monitored = Boolean(a?.["monitored"]);
        return (
          <span className={`track-status ${monitored ? "available" : "missing"}`}>
            {monitored ? "✓" : "✗"}
          </span>
        );
      },
    },
    {
      id: "qualityProfileName",
      header: "Quality profile",
      cell: ({ row }) => {
        const a = row.original.artist as Record<string, unknown>;
        return (
          (a?.["qualityProfileName"] as string | null | undefined) || "—"
        );
      },
    },
  ];
}

function buildLidarrAggColumns(
  instanceCount: number,
): ColumnDef<LidarrAggRow>[] {
  const cols: ColumnDef<LidarrAggRow>[] = [];
  if (instanceCount > 1) {
    cols.push({
      id: "instance",
      header: "Instance",
      cell: ({ row }) => row.original.__instance,
    });
  }
  cols.push(...(buildLidarrInstanceColumns() as ColumnDef<LidarrAggRow>[]));
  return cols;
}

const LIDARR_INITIAL_ROLLUP: LidarrRollup = {
  available: 0,
  monitored: 0,
  missing: 0,
  rollupTotalAlbumsHint: 0,
  seenInstances: new Set<string>(),
};

export const LIDARR_DEFINITION: ArrCatalogDefinition<
  LidarrInstanceRow,
  LidarrAggRow,
  LidarrFilters,
  LidarrArtistBrowseEntry,
  LidarrAggRow,
  LidarrInstanceRow | LidarrAggRow,
  LidarrArtistsResponse,
  LidarrRollup
> = {
  kind: "lidarr",
  arrType: "lidarr",
  cardTitle: "Lidarr",
  allInstancesLabel: "All Lidarr",
  searchPlaceholder: "Filter artists",
  initialFilters: { onlyMissing: false, reasonFilter: "all" },
  filterControls: [
    {
      id: "status",
      label: "Status",
      mode: "always",
      options: [
        { value: "all", label: "All Artists" },
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
    basePageSize: LIDARR_PAGE_SIZE,
    initialRollup: LIDARR_INITIAL_ROLLUP,
    initialSummary: {
      available: 0,
      monitored: 0,
      missing: 0,
      total: 0,
      rollupTotalAlbumsHint: 0,
    },
    fetchPage: (category, pageIdx, chunk, filters) =>
      getLidarrArtists(category, pageIdx, chunk, "", {
        missingOnly: filters.onlyMissing,
        reasonFilter:
          filters.reasonFilter !== "all" ? filters.reasonFilter : null,
      }),
    extractSlice: (response) => {
      const rows = normalizeLidarrBrowseRows(response.artists ?? []);
      return {
        slice: rows,
        batchLength: rows.length,
        total: response.total,
        pageSize: response.page_size,
      };
    },
    mapSlice: (response, instanceLabel, push) => {
      const rows = normalizeLidarrBrowseRows(response.artists ?? []);
      rows.forEach((entry) => {
        push({ ...entry, __instance: instanceLabel } as LidarrAggRow);
      });
    },
    accumulateRollup: (prev, response) => {
      const counts = response.counts;
      if (!counts) return prev;
      // Identify the instance via the response category (matches the label used by
      // `forEachInstanceChunkedPages` indirectly — the loader calls
      // onInstanceFirstPage at most once per instance).
      const instKey = response.category ?? "";
      if (prev.seenInstances.has(instKey)) return prev;
      const seen = new Set(prev.seenInstances);
      seen.add(instKey);
      return {
        available: prev.available + (counts.available ?? 0),
        monitored: prev.monitored + (counts.monitored ?? 0),
        missing: prev.missing + (counts.missing ?? 0),
        rollupTotalAlbumsHint:
          prev.rollupTotalAlbumsHint + (response.album_total ?? 0),
        seenInstances: seen,
      };
    },
    summarize: (rows, rollup) => {
      const total = rows.length > 0 ? rows.length : rollup.monitored;
      return {
        available: rollup.available,
        monitored: rollup.monitored,
        missing: rollup.missing,
        total,
        rollupTotalAlbumsHint: rollup.rollupTotalAlbumsHint,
      };
    },
    getRowKey: lidarrAggRowKey,
    hashFields: LIDARR_AGG_HASH_FIELDS as unknown as ReadonlyArray<
      keyof LidarrAggRow & string
    >,
    filterRows: (rows, _filters, debouncedSearch) => {
      const q = debouncedSearch ? debouncedSearch.toLowerCase() : "";
      if (!q) return rows;
      return rows.filter((row) => {
        const a = row.artist as Record<string, unknown>;
        const name = String(a?.["name"] ?? "").toLowerCase();
        const inst = String(row.__instance ?? "").toLowerCase();
        return name.includes(q) || inst.includes(q);
      });
    },
    sortRows: (rows) => {
      return [...rows].sort((a, b) => {
        const ai = (a.__instance || "").toLowerCase();
        const bi = (b.__instance || "").toLowerCase();
        if (ai !== bi) return ai.localeCompare(bi);
        const an = String(
          (a.artist as Record<string, unknown>)["name"] || "",
        ).toLowerCase();
        const bn = String(
          (b.artist as Record<string, unknown>)["name"] || "",
        ).toLowerCase();
        return an.localeCompare(bn);
      });
    },
  },
  useInstancePipeline: (params) =>
    useInstancePagedFetch<
      LidarrInstanceRow,
      LidarrArtistsResponse,
      LidarrFilters
    >(params, {
      basePageSize: LIDARR_PAGE_SIZE,
      getRowKey: lidarrInstanceRowKey,
      hashFields: LIDARR_INSTANCE_HASH_FIELDS as unknown as ReadonlyArray<
        keyof LidarrInstanceRow & string
      >,
      buildKey: ({ category, query, filters }) =>
        `${category}::${query}::m:${filters.onlyMissing ? "1" : ""}::r:${
          filters.reasonFilter
        }`,
      fetchPage: (category, page, pageSize, query, filters) =>
        getLidarrArtists(category, page, pageSize, query, {
          missingOnly: filters.onlyMissing,
          reasonFilter:
            filters.reasonFilter !== "all" ? filters.reasonFilter : null,
        }),
      extractPage: (response) => {
        const rows = normalizeLidarrBrowseRows(response.artists ?? []);
        return {
          rows,
          page: response.page ?? 0,
          pageSize: response.page_size ?? LIDARR_PAGE_SIZE,
          total: response.total ?? rows.length,
        };
      },
      isCatalogEmpty: (response) => {
        const rows = response.artists ?? [];
        const total = response.total ?? 0;
        if (rows.length === 0 && total === 0) {
          return true;
        }
        return (
          total === 0 &&
          (response.album_total ?? 0) === 0 &&
          (response.counts?.monitored ?? 0) === 0 &&
          (response.counts?.available ?? 0) === 0
        );
      },
      keepAllPages: false,
      errorMessage: (category) => `Failed to load ${category} artists`,
    }),
  buildAggregateSelection: (row, instances) => {
    const artist = row.artist as Record<string, unknown>;
    const rawId = artist?.["id"];
    const aid =
      typeof rawId === "number"
        ? rawId
        : typeof rawId === "string" && rawId.trim() !== ""
          ? Number(rawId)
          : NaN;
    if (!Number.isFinite(aid)) return null;
    const name = String(artist?.["name"] ?? "Artist");
    const idKey = Number.isFinite(aid) ? `id:${aid}` : `n:${name}`;
    return {
      id: `${row.__instance}::${idKey}`,
      source: "aggregate",
      seed: row,
      extras: {
        artistId: aid,
        category: categoryForInstanceLabel([...instances], row.__instance),
        instanceLabel: row.__instance,
      },
    };
  },
  buildInstanceSelection: (row, selectionCategory, instanceLabel) => {
    const artist = row.artist as Record<string, unknown>;
    const rawId = artist?.["id"];
    const aid =
      typeof rawId === "number"
        ? rawId
        : typeof rawId === "string" && rawId.trim() !== ""
          ? Number(rawId)
          : NaN;
    if (!Number.isFinite(aid)) return null;
    const name = String(artist?.["name"] ?? "Artist");
    const idKey = Number.isFinite(aid) ? `id:${aid}` : `n:${name}`;
    return {
      id: idKey,
      source: "instance",
      seed: row as LidarrArtistBrowseEntry,
      extras: {
        artistId: aid,
        category: selectionCategory,
        instanceLabel,
      },
    };
  },
  getModalLiveRow: ({
    source,
    instanceFresh,
    aggregateFresh,
    instanceSeed,
    aggregateSeed,
  }) => {
    if (source === "instance") {
      return (instanceFresh ?? instanceSeed) as LidarrInstanceRow;
    }
    return (aggregateFresh ?? aggregateSeed) as LidarrAggRow;
  },
  getModalTitle: (liveRow, extras) => {
    const a =
      (liveRow as LidarrInstanceRow | LidarrAggRow).artist as
        | Record<string, unknown>
        | undefined;
    return String(a?.["name"] ?? extras.artistId ?? "Artist");
  },
  getModalMaxWidth: () => 720,
  renderModalBody: ({ extras }) => {
    const artistId = Number(extras.artistId ?? 0);
    return (
      <LidarrArtistDetailBody
        key={`${extras.category}-${artistId}`}
        category={String(extras.category ?? "")}
        artistId={artistId}
        instanceLabel={String(extras.instanceLabel ?? "")}
      />
    );
  },
  buildAggregateColumns: buildLidarrAggColumns,
  buildInstanceColumns: buildLidarrInstanceColumns,
  renderAggregateBody: (props) => <LidarrAggregateBody {...props} />,
  renderInstanceBody: (props) => <LidarrInstanceBody {...props} />,
};

ARR_CATALOG_REGISTRY.lidarr = LIDARR_DEFINITION;

interface LidarrAggregateBodyProps {
  readonly rows: ReadonlyArray<LidarrAggRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<LidarrAggRow>;
  readonly loading: boolean;
  readonly emptyStateReady: boolean;
  readonly total: number;
  readonly page: number;
  readonly totalPages: number;
  readonly aggregatePageSize: number;
  readonly summary: ArrCatalogSummary;
  readonly lastUpdated: string | null;
  readonly isAggFiltered: boolean;
  readonly onPageChange: (page: number) => void;
  readonly onRefresh: () => void;
  readonly onRowSelect: (row: LidarrAggRow) => void;
  readonly browseMode: "list" | "icon";
  readonly iconGridRef: RefCallback<HTMLElement | null>;
  readonly instances: ReadonlyArray<ArrInfo>;
  readonly instanceCount: number;
}

function LidarrAggregateBody({
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
  instances,
  instanceCount,
}: LidarrAggregateBodyProps): JSX.Element {
  const columns = buildLidarrAggColumns(instanceCount);
  const waitingForStableEmpty =
    instanceCount > 0 && !emptyStateReady && total === 0;
  const effectiveLoading = loading || waitingForStableEmpty;
  const summaryLine = (
    <>
      Artist grid below: one tile or row per artist (same idea as Sonarr series).
      Album figures are catalog rollups, not the browse rows.{" "}
      {lastUpdated ? `(updated ${lastUpdated})` : ""}
      <br />
      <strong>Artists in catalog:</strong>{" "}
      {summary.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}{" "}
      • <strong>Album catalog — available:</strong>{" "}
      {summary.available.toLocaleString(undefined, {
        maximumFractionDigits: 0,
      })}{" "}
      • <strong>Monitored:</strong>{" "}
      {summary.monitored.toLocaleString(undefined, {
        maximumFractionDigits: 0,
      })}{" "}
      • <strong>Missing:</strong>{" "}
      {summary.missing.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      {typeof summary.rollupTotalAlbumsHint === "number" ? (
        <>
          {" "}• <strong>Album rows (SQLite):</strong>{" "}
          {summary.rollupTotalAlbumsHint.toLocaleString(undefined, {
            maximumFractionDigits: 0,
          })}
        </>
      ) : null}
      {isAggFiltered && total < summary.total ? (
        <>
          {" "}• <strong>Filtered artists:</strong>{" "}
          {total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </>
      ) : null}
    </>
  );

  const showCatalogEmptyHint =
    !effectiveLoading &&
    total === 0 &&
    summary.monitored === 0 &&
    instanceCount > 0;

  return (
    <ArrCatalogBodyChrome
      summaryLine={summaryLine}
      onRefresh={onRefresh}
      loading={effectiveLoading}
      loadingHint="Loading Lidarr library…"
      footer={
        total > 0 ? (
          <ArrCatalogPagination
            page={page}
            totalPages={totalPages}
            total={total}
            itemNoun="artists"
            pageSize={aggregatePageSize}
            loading={effectiveLoading}
            onPageChange={onPageChange}
          />
        ) : null
      }
    >
      {showCatalogEmptyHint ? (
        <div className="hint">
          <p>No artists found in the local catalog.</p>
          <p>{ARR_CATALOG_SYNC_HINT}</p>
        </div>
      ) : total ? (
        browseMode === "list" ? (
          <StableTable<LidarrAggRow>
            rowsStore={rowsStore}
            rowOrder={rowOrder}
            columns={columns}
            getRowKey={lidarrAggRowKey}
            onRowClick={onRowSelect}
          />
        ) : (
          <div className="arr-icon-grid" ref={iconGridRef}>
            {rows.map((row) => {
              const artist = row.artist as Record<string, unknown>;
              const id = artist?.["id"];
              const name = (artist?.["name"] as string | undefined) || "—";
              const cat = categoryForInstanceLabel(
                [...instances],
                row.__instance,
              );
              const thumb =
                typeof id === "number" ? lidarrArtistThumbnailUrl(cat, id) : "";
              return (
                <ArrCatalogIconTile
                  key={lidarrAggRowKey(row)}
                  posterSrc={thumb}
                  onClick={() => onRowSelect(row)}
                >
                  {instanceCount > 1 ? (
                    <div className="arr-movie-tile__instance">
                      {row.__instance}
                    </div>
                  ) : null}
                  <div className="arr-movie-tile__title">{name}</div>
                  {lidarrArtistTileStats(artist)}
                </ArrCatalogIconTile>
              );
            })}
          </div>
        )
      ) : (
        <div className="hint">No artists match the current filters.</div>
      )}
    </ArrCatalogBodyChrome>
  );
}

interface LidarrInstanceBodyProps {
  readonly visibleRows: ReadonlyArray<LidarrInstanceRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<LidarrInstanceRow>;
  readonly loading: boolean;
  readonly emptyStateReady: boolean;
  readonly page: number;
  readonly pageSize: number;
  readonly totalPages: number;
  readonly totalItems: number;
  readonly lastUpdated: string | null;
  readonly browseMode: "list" | "icon";
  readonly iconGridRef: RefCallback<HTMLElement | null>;
  readonly category: string;
  readonly showCatalogEmptyHint: boolean;
  readonly onRowSelect: (row: LidarrInstanceRow) => void;
  readonly setPage: (page: number) => void;
  readonly refresh: () => void;
}

function LidarrInstanceBody({
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
  category,
  showCatalogEmptyHint,
  onRowSelect,
  setPage,
  refresh,
}: LidarrInstanceBodyProps): JSX.Element {
  const columns = buildLidarrInstanceColumns();
  const waitingForStableEmpty =
    !emptyStateReady && visibleRows.length === 0;
  const effectiveLoading = loading || waitingForStableEmpty;
  const summaryLine = (
    <>
      <strong>Artists:</strong>{" "}
      {totalItems.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      {lastUpdated ? ` (updated ${lastUpdated})` : ""}
    </>
  );

  return (
    <ArrCatalogBodyChrome
      summaryLine={summaryLine}
      onRefresh={refresh}
      loading={effectiveLoading}
      loadingHint="Loading…"
      footer={
        totalPages > 1 ? (
          <ArrCatalogPagination
            page={page}
            totalPages={totalPages}
            total={totalItems}
            itemNoun="artists"
            pageSize={pageSize}
            loading={effectiveLoading}
            onPageChange={setPage}
          />
        ) : null
      }
    >
      {visibleRows.length ? (
        browseMode === "list" ? (
          <StableTable<LidarrInstanceRow>
            rowsStore={rowsStore}
            rowOrder={rowOrder}
            columns={columns}
            getRowKey={lidarrInstanceRowKey}
            onRowClick={onRowSelect}
          />
        ) : (
          <div className="arr-icon-grid" ref={iconGridRef}>
            {visibleRows.map((row) => {
              const artist = row.artist as Record<string, unknown>;
              const id = artist?.["id"];
              const name = String(artist?.["name"] ?? "—");
              const thumb =
                typeof id === "number"
                  ? lidarrArtistThumbnailUrl(category, id)
                  : "";
              return (
                <ArrCatalogIconTile
                  key={lidarrInstanceRowKey(row)}
                  posterSrc={thumb}
                  onClick={() => onRowSelect(row)}
                >
                  <div className="arr-movie-tile__title">{name}</div>
                  {lidarrArtistTileStats(artist)}
                </ArrCatalogIconTile>
              );
            })}
          </div>
        )
      ) : showCatalogEmptyHint ? (
        <div className="hint">
          <p>No artists in the local catalog.</p>
          <p>{ARR_CATALOG_SYNC_HINT}</p>
        </div>
      ) : (
        <div className="hint">No artists match the current filters.</div>
      )}
    </ArrCatalogBodyChrome>
  );
}
