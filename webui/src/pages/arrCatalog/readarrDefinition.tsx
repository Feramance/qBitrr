import type { ColumnDef } from "@tanstack/react-table";
import { useCallback, useMemo, type JSX, type RefCallback } from "react";
import { getReadarrAuthors } from "../../api/client";
import type {
  ArrInfo,
  ReadarrAuthorBrowseEntry,
  ReadarrAuthorsResponse,
} from "../../api/types";
import { ArrMiniProgress } from "../../components/arr/ArrMiniProgress";
import {
  ArrListProgressCell,
  ArrMonitoredBadge,
  ArrReasonBadge,
} from "../../components/arr/ArrStatusCells";
import { ReadarrAuthorDetailBody } from "../../components/arr/ReadarrAuthorDetailBody";
import { readarrAuthorThumbnailUrl } from "../../utils/arrThumbnailUrl";
import { ArrCatalogIconTile } from "./ArrCatalogIconTile";
import { ArrCatalogStandardBody } from "./ArrCatalogStandardBody";
import { createStandardArrFilters } from "./createStandardArrFilters";
import type { ArrCatalogDefinition, ArrCatalogSummary, AnyArrCatalogDefinition } from "./definition";
import { useInstancePagedFetch } from "./useInstancePagedFetch";
import { categoryForInstanceLabel } from "./utils";
import type { RowsStore } from "../../utils/rowsStore";

const READARR_PAGE_SIZE = 50;

interface ReadarrFilters extends Record<string, unknown> {
  readonly onlyMissing: boolean;
  readonly reasonFilter: string;
}

type ReadarrInstanceRow = ReadarrAuthorBrowseEntry & Record<string, unknown>;

interface ReadarrAggRow extends ReadarrAuthorBrowseEntry {
  __instance: string;
  [key: string]: unknown;
}

interface ReadarrRollup {
  available: number;
  monitored: number;
  missing: number;
  rollupTotalBooksHint: number;
  // Tracks instances we've already accumulated to avoid double-counting on
  // multi-page loops (the loader calls `onInstanceFirstPage` exactly once per
  // instance, so we stamp on first call).
  seenInstances: ReadonlySet<string>;
}

const READARR_INSTANCE_HASH_FIELDS = ["author"] as const;
const READARR_AGG_HASH_FIELDS = ["__instance", "author"] as const;

/**
 * Ensure each browse row is `{ author: { id, name, ... } }` and coerce numeric ids.
 * Handles flat rows or legacy `Title` if the API shape ever diverges.
 */
function normalizeReadarrBrowseRows(raw: readonly unknown[]): ReadarrInstanceRow[] {
  const out: ReadarrInstanceRow[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const o = item as Record<string, unknown>;
    let author: Record<string, unknown>;
    const nested = o["author"];
    if (nested && typeof nested === "object") {
      author = { ...(nested as Record<string, unknown>) };
    } else if ("id" in o || "name" in o || "Title" in o) {
      author = { ...o };
      if (author["name"] === undefined && author["Title"] !== undefined) {
        author["name"] = author["Title"];
      }
    } else {
      continue;
    }
    const rid = author["id"];
    if (typeof rid === "string" && rid.trim() !== "") {
      const n = Number(rid);
      if (Number.isFinite(n)) {
        author["id"] = n;
      }
    }
    out.push({ author } as ReadarrInstanceRow);
  }
  return out;
}

function readarrAuthorKey(author: Record<string, unknown>): string {
  const rawId = author?.["id"];
  const name = (author?.["name"] as string | undefined) || "";
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

function readarrInstanceRowKey(row: ReadarrInstanceRow): string {
  const author = row.author as Record<string, unknown>;
  return readarrAuthorKey(author);
}

function readarrAggRowKey(row: ReadarrAggRow): string {
  const author = row.author as Record<string, unknown>;
  return `${row.__instance}::${readarrAuthorKey(author)}`;
}

function readarrAuthorTileStats(
  author: Record<string, unknown>,
): JSX.Element {
  const monB = author["booksMonitored"];
  const availB = author["booksAvailable"];
  const missB = author["booksMissing"];
  if (
    typeof monB === "number" &&
    typeof availB === "number" &&
    typeof missB === "number"
  ) {
    return (
      <div className="arr-movie-tile__stats arr-movie-tile__stats--lidarr-artist">
        <ArrMiniProgress label="Books" available={availB} missing={missB} />
      </div>
    );
  }
  const books = Number(author?.["bookCount"] ?? 0);
  return (
    <div className="arr-movie-tile__stats arr-movie-tile__stats--lidarr-artist">
      <div>{books.toLocaleString()} books</div>
    </div>
  );
}

/** Module-level column defs — stable identity across renders for StableTable memo. */
const READARR_INSTANCE_COLUMNS: ColumnDef<ReadarrInstanceRow>[] = [
  {
    id: "author",
    header: "Author",
    cell: ({ row }) => {
      const a = row.original.author as Record<string, unknown>;
      return String(a?.["name"] ?? "—");
    },
  },
  {
    id: "books",
    header: "Books",
    cell: ({ row }) => {
      const a = row.original.author as Record<string, unknown>;
      const avail = Number(a?.["booksAvailable"] ?? NaN);
      const miss = Number(a?.["booksMissing"] ?? NaN);
      if (Number.isFinite(avail) && Number.isFinite(miss)) {
        return (
          <ArrListProgressCell
            label="Books"
            available={avail}
            missing={miss}
          />
        );
      }
      return Number(a?.["bookCount"] ?? 0).toLocaleString();
    },
    size: 140,
  },
  {
    id: "monitored",
    header: "Monitored",
    cell: ({ row }) => {
      const a = row.original.author as Record<string, unknown>;
      return <ArrMonitoredBadge monitored={Boolean(a?.["monitored"])} />;
    },
    size: 120,
  },
  {
    id: "qualityProfileName",
    header: "Quality profile",
    cell: ({ row }) => {
      const a = row.original.author as Record<string, unknown>;
      return (
        (a?.["qualityProfileName"] as string | null | undefined) || "—"
      );
    },
  },
  {
    id: "reason",
    header: "Reason",
    cell: ({ row }) => {
      const a = row.original.author as Record<string, unknown>;
      const reason =
        typeof a?.["reason"] === "string" ? (a["reason"] as string) : null;
      return <ArrReasonBadge reason={reason} />;
    },
    size: 140,
  },
];

const READARR_AGG_COLUMNS_SINGLE =
  READARR_INSTANCE_COLUMNS as ColumnDef<ReadarrAggRow>[];

const READARR_AGG_COLUMNS_MULTI: ColumnDef<ReadarrAggRow>[] = [
  {
    id: "instance",
    header: "Instance",
    cell: ({ row }) => row.original.__instance,
  },
  ...READARR_AGG_COLUMNS_SINGLE,
];

function getReadarrAggColumns(instanceCount: number): ColumnDef<ReadarrAggRow>[] {
  return instanceCount > 1 ? READARR_AGG_COLUMNS_MULTI : READARR_AGG_COLUMNS_SINGLE;
}

const READARR_INITIAL_ROLLUP: ReadarrRollup = {
  available: 0,
  monitored: 0,
  missing: 0,
  rollupTotalBooksHint: 0,
  seenInstances: new Set<string>(),
};

export const READARR_DEFINITION: ArrCatalogDefinition<
  ReadarrInstanceRow,
  ReadarrAggRow,
  ReadarrFilters,
  ReadarrAuthorBrowseEntry,
  ReadarrAggRow,
  ReadarrInstanceRow | ReadarrAggRow,
  ReadarrAuthorsResponse,
  ReadarrRollup
> = {
  kind: "readarr",
  arrType: "readarr",
  cardTitle: "Readarr",
  allInstancesLabel: "All Readarr",
  searchPlaceholder: "Filter authors",
  initialFilters: { onlyMissing: false, reasonFilter: "all" },
  filterControls: createStandardArrFilters<ReadarrFilters>("All Authors"),
  aggregate: {
    basePageSize: READARR_PAGE_SIZE,
    initialRollup: READARR_INITIAL_ROLLUP,
    initialSummary: {
      available: 0,
      monitored: 0,
      missing: 0,
      total: 0,
      rollupTotalBooksHint: 0,
    },
    fetchPage: (category, pageIdx, chunk, filters) =>
      getReadarrAuthors(category, pageIdx, chunk, "", {
        missingOnly: filters.onlyMissing,
        reasonFilter:
          filters.reasonFilter !== "all" ? filters.reasonFilter : null,
      }),
    extractSlice: (response) => {
      const rows = normalizeReadarrBrowseRows(response.authors ?? []);
      return {
        slice: rows,
        batchLength: rows.length,
        total: response.total,
        pageSize: response.page_size,
      };
    },
    mapSlice: (response, instanceLabel, push) => {
      const rows = normalizeReadarrBrowseRows(response.authors ?? []);
      rows.forEach((entry) => {
        push({ ...entry, __instance: instanceLabel } as ReadarrAggRow);
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
        rollupTotalBooksHint:
          prev.rollupTotalBooksHint + (response.book_total ?? 0),
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
        rollupTotalBooksHint: rollup.rollupTotalBooksHint,
      };
    },
    getRowKey: readarrAggRowKey,
    hashFields: READARR_AGG_HASH_FIELDS as unknown as ReadonlyArray<
      keyof ReadarrAggRow & string
    >,
    filterRows: (rows, _filters, debouncedSearch) => {
      const q = debouncedSearch ? debouncedSearch.toLowerCase() : "";
      if (!q) return rows;
      return rows.filter((row) => {
        const a = row.author as Record<string, unknown>;
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
          (a.author as Record<string, unknown>)["name"] || "",
        ).toLowerCase();
        const bn = String(
          (b.author as Record<string, unknown>)["name"] || "",
        ).toLowerCase();
        return an.localeCompare(bn);
      });
    },
  },
  useInstancePipeline: (params) =>
    useInstancePagedFetch<
      ReadarrInstanceRow,
      ReadarrAuthorsResponse,
      ReadarrFilters
    >(params, {
      basePageSize: READARR_PAGE_SIZE,
      getRowKey: readarrInstanceRowKey,
      hashFields: READARR_INSTANCE_HASH_FIELDS as unknown as ReadonlyArray<
        keyof ReadarrInstanceRow & string
      >,
      buildKey: ({ category, query, filters }) =>
        `${category}::${query}::m:${filters.onlyMissing ? "1" : ""}::r:${
          filters.reasonFilter
        }`,
      fetchPage: (category, page, pageSize, query, filters) =>
        getReadarrAuthors(category, page, pageSize, query, {
          missingOnly: filters.onlyMissing,
          reasonFilter:
            filters.reasonFilter !== "all" ? filters.reasonFilter : null,
        }),
      extractPage: (response) => {
        const rows = normalizeReadarrBrowseRows(response.authors ?? []);
        return {
          rows,
          page: response.page ?? 0,
          pageSize: response.page_size ?? READARR_PAGE_SIZE,
          total: response.total ?? rows.length,
        };
      },
      isCatalogEmpty: (response) => {
        const rows = response.authors ?? [];
        const total = response.total ?? 0;
        if (rows.length === 0 && total === 0) {
          return true;
        }
        return (
          total === 0 &&
          (response.book_total ?? 0) === 0 &&
          (response.counts?.monitored ?? 0) === 0 &&
          (response.counts?.available ?? 0) === 0
        );
      },
      keepAllPages: false,
      errorMessage: (category) => `Failed to load ${category} authors`,
    }),
  buildAggregateSelection: (row, instances) => {
    const author = row.author as Record<string, unknown>;
    const rawId = author?.["id"];
    const aid =
      typeof rawId === "number"
        ? rawId
        : typeof rawId === "string" && rawId.trim() !== ""
          ? Number(rawId)
          : NaN;
    if (!Number.isFinite(aid)) return null;
    const name = String(author?.["name"] ?? "Author");
    const idKey = Number.isFinite(aid) ? `id:${aid}` : `n:${name}`;
    return {
      id: `${row.__instance}::${idKey}`,
      source: "aggregate",
      seed: row,
      extras: {
        authorId: aid,
        category: categoryForInstanceLabel([...instances], row.__instance),
        instanceLabel: row.__instance,
      },
    };
  },
  buildInstanceSelection: (row, selectionCategory, instanceLabel) => {
    const author = row.author as Record<string, unknown>;
    const rawId = author?.["id"];
    const aid =
      typeof rawId === "number"
        ? rawId
        : typeof rawId === "string" && rawId.trim() !== ""
          ? Number(rawId)
          : NaN;
    if (!Number.isFinite(aid)) return null;
    const name = String(author?.["name"] ?? "Author");
    const idKey = Number.isFinite(aid) ? `id:${aid}` : `n:${name}`;
    return {
      id: idKey,
      source: "instance",
      seed: row as ReadarrAuthorBrowseEntry,
      extras: {
        authorId: aid,
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
      return (instanceFresh ?? instanceSeed) as ReadarrInstanceRow;
    }
    return (aggregateFresh ?? aggregateSeed) as ReadarrAggRow;
  },
  getModalTitle: (liveRow, extras) => {
    const a =
      (liveRow as ReadarrInstanceRow | ReadarrAggRow).author as
        | Record<string, unknown>
        | undefined;
    return String(a?.["name"] ?? extras.authorId ?? "Author");
  },
  getModalMaxWidth: () => 720,
  renderModalBody: ({ extras }) => {
    const authorId = Number(extras.authorId ?? 0);
    return (
      <ReadarrAuthorDetailBody
        key={`${extras.category}-${authorId}`}
        category={String(extras.category ?? "")}
        authorId={authorId}
        instanceLabel={String(extras.instanceLabel ?? "")}
      />
    );
  },
  renderAggregateBody: (props) => <ReadarrAggregateBody {...props} />,
  renderInstanceBody: (props) => <ReadarrInstanceBody {...props} />,
};

export function getReadarrCatalogDefinition(): AnyArrCatalogDefinition {
  return READARR_DEFINITION;
}

interface ReadarrAggregateBodyProps {
  readonly rows: ReadonlyArray<ReadarrAggRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<ReadarrAggRow>;
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
  readonly onRowSelect: (row: ReadarrAggRow) => void;
  readonly browseMode: "list" | "icon";
  readonly iconGridRef: RefCallback<HTMLElement | null>;
  readonly instances: ReadonlyArray<ArrInfo>;
  readonly instanceCount: number;
}

function ReadarrAggregateBody({
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
}: ReadarrAggregateBodyProps): JSX.Element {
  const columns = useMemo(
    () => getReadarrAggColumns(instanceCount),
    [instanceCount],
  );
  const renderIconTile = useCallback(
    (row: ReadarrAggRow) => {
      const author = row.author as Record<string, unknown>;
      const id = author?.["id"];
      const name = (author?.["name"] as string | undefined) || "—";
      const cat = categoryForInstanceLabel([...instances], row.__instance);
      const thumb =
        typeof id === "number" ? readarrAuthorThumbnailUrl(cat, id) : "";
      return (
        <ArrCatalogIconTile
          key={readarrAggRowKey(row)}
          posterSrc={thumb}
          onClick={() => onRowSelect(row)}
        >
          {instanceCount > 1 ? (
            <div className="arr-movie-tile__instance">{row.__instance}</div>
          ) : null}
          <div className="arr-movie-tile__title">{name}</div>
          {readarrAuthorTileStats(author)}
        </ArrCatalogIconTile>
      );
    },
    [instances, instanceCount, onRowSelect],
  );
  const waitingForStableEmpty =
    instanceCount > 0 && !emptyStateReady && total === 0;
  const effectiveLoading = loading || waitingForStableEmpty;
  const summaryLine = (
    <>
      Author grid below: one tile or row per author (same idea as Lidarr artists).
      Book figures are catalog rollups, not the browse rows.{" "}
      {lastUpdated ? `(updated ${lastUpdated})` : ""}
      <br />
      <strong>Authors in catalog:</strong>{" "}
      {summary.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}{" "}
      • <strong>Book catalog — available:</strong>{" "}
      {summary.available.toLocaleString(undefined, {
        maximumFractionDigits: 0,
      })}{" "}
      • <strong>Monitored:</strong>{" "}
      {summary.monitored.toLocaleString(undefined, {
        maximumFractionDigits: 0,
      })}{" "}
      • <strong>Missing:</strong>{" "}
      {summary.missing.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      {typeof summary.rollupTotalBooksHint === "number" ? (
        <>
          {" "}• <strong>Book rows (SQLite):</strong>{" "}
          {summary.rollupTotalBooksHint.toLocaleString(undefined, {
            maximumFractionDigits: 0,
          })}
        </>
      ) : null}
      {isAggFiltered && total < summary.total ? (
        <>
          {" "}• <strong>Filtered authors:</strong>{" "}
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
    <ArrCatalogStandardBody
      summaryLine={summaryLine}
      onRefresh={onRefresh}
      loading={effectiveLoading}
      loadingHint="Loading Readarr library…"
      emptyOrder="syncFirst"
      showCatalogEmptyHint={showCatalogEmptyHint}
      hasRows={total > 0}
      catalogEmptyMessage="No authors found in the local catalog."
      noMatchMessage="No authors match the current filters."
      showPagination={totalPages > 1}
      page={page}
      totalPages={totalPages}
      total={total}
      itemNoun="authors"
      pageSize={aggregatePageSize}
      onPageChange={onPageChange}
      browseMode={browseMode}
      rows={rows}
      rowOrder={rowOrder}
      rowsStore={rowsStore}
      columns={columns}
      getRowKey={readarrAggRowKey}
      onRowSelect={onRowSelect}
      iconGridRef={iconGridRef}
      renderIconTile={renderIconTile}
    />
  );
}

interface ReadarrInstanceBodyProps {
  readonly visibleRows: ReadonlyArray<ReadarrInstanceRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<ReadarrInstanceRow>;
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
  readonly onRowSelect: (row: ReadarrInstanceRow) => void;
  readonly setPage: (page: number) => void;
  readonly refresh: () => void;
}

function ReadarrInstanceBody({
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
}: ReadarrInstanceBodyProps): JSX.Element {
  const columns = READARR_INSTANCE_COLUMNS;
  const renderIconTile = useCallback(
    (row: ReadarrInstanceRow) => {
      const author = row.author as Record<string, unknown>;
      const id = author?.["id"];
      const name = String(author?.["name"] ?? "—");
      const thumb =
        typeof id === "number" ? readarrAuthorThumbnailUrl(category, id) : "";
      return (
        <ArrCatalogIconTile
          key={readarrInstanceRowKey(row)}
          posterSrc={thumb}
          onClick={() => onRowSelect(row)}
        >
          <div className="arr-movie-tile__title">{name}</div>
          {readarrAuthorTileStats(author)}
        </ArrCatalogIconTile>
      );
    },
    [category, onRowSelect],
  );
  const waitingForStableEmpty =
    !emptyStateReady && visibleRows.length === 0;
  const effectiveLoading = loading || waitingForStableEmpty;
  const summaryLine = (
    <>
      <strong>Authors:</strong>{" "}
      {totalItems.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      {lastUpdated ? ` (updated ${lastUpdated})` : ""}
    </>
  );

  return (
    <ArrCatalogStandardBody
      summaryLine={summaryLine}
      onRefresh={refresh}
      loading={effectiveLoading}
      loadingHint="Loading…"
      emptyOrder="syncFirst"
      showCatalogEmptyHint={showCatalogEmptyHint}
      hasRows={visibleRows.length > 0}
      catalogEmptyMessage="No authors in the local catalog."
      noMatchMessage="No authors match the current filters."
      showPagination={totalPages > 1}
      page={page}
      totalPages={totalPages}
      total={totalItems}
      itemNoun="authors"
      pageSize={pageSize}
      onPageChange={setPage}
      browseMode={browseMode}
      rows={visibleRows}
      rowOrder={rowOrder}
      rowsStore={rowsStore}
      columns={columns}
      getRowKey={readarrInstanceRowKey}
      onRowSelect={onRowSelect}
      iconGridRef={iconGridRef}
      renderIconTile={renderIconTile}
    />
  );
}
