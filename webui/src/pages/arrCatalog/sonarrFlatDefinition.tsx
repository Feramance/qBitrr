import type { ColumnDef } from "@tanstack/react-table";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type JSX,
  type RefCallback,
} from "react";
import { getSonarrSeries } from "../../api/client";
import type { ArrInfo, SonarrSeriesEntry, SonarrSeriesResponse } from "../../api/types";
import { ArrCatalogStandardBody } from "./ArrCatalogStandardBody";
import { useInterval } from "../../hooks/useInterval";
import { useRowsStore } from "../../hooks/useRowsStore";
import { arraysEqual } from "../../utils/dataSync";
import type { RowsStore } from "../../utils/rowsStore";
import { createStandardArrFilters } from "./createStandardArrFilters";
import { INSTANCE_VIEW_POLL_INTERVAL_MS } from "../../constants/arrAggregateFetch";
import type {
  ArrCatalogDefinition,
  ArrCatalogInstancePipelineParams,
  ArrCatalogInstancePipelineState,
} from "./definition";
import {
  isEmptyStateReady,
  useCatalogEmptyStateTracker,
  useCatalogIconGridRefetch,
  useCatalogPageCache,
  useCatalogSearchRegistration,
} from "./useCatalogFetchPrimitives";
import {
  filterSeriesEntriesForMissing,
  filterSeriesEntryByReason,
  filterSonarrFlatEpisodes,
  seriesEntryToFlatEpisodes,
  sonarrFlatEpisodeRowKey,
  SONARR_FLAT_HASH_FIELDS,
  summarizeFlatEpisodes,
  type SonarrCatalogFilters,
  type SonarrEpisodeFlatRow,
} from "./sonarrCatalogModes";

const SONARR_FLAT_PAGE_SIZE = 50;

type SonarrSeriesComparable = SonarrSeriesEntry & Record<string, unknown>;

const SONARR_INSTANCE_PAGE_HASH_FIELDS: (keyof SonarrSeriesComparable)[] = [
  "seasons",
  "series",
  "totals",
];

function getSonarrSeriesEntryKey(entry: SonarrSeriesComparable): string {
  const id = entry.series?.["id"];
  if (typeof id === "number" && Number.isFinite(id)) {
    return `id:${id}`;
  }
  return `t:${String(entry.series?.["title"] ?? "")}`;
}

function buildSonarrFlatColumns(
  instanceCount: number,
): ColumnDef<SonarrEpisodeFlatRow>[] {
  const cols: ColumnDef<SonarrEpisodeFlatRow>[] = [];
  if (instanceCount > 1) {
    cols.push({
      id: "instance",
      header: "Instance",
      cell: ({ row }) => row.original.__instance,
    });
  }
  cols.push(
    {
      accessorKey: "series",
      header: "Series",
      cell: (info) => String(info.getValue() ?? ""),
    },
    {
      accessorKey: "season",
      header: "Season",
      cell: (info) => String(info.getValue() ?? ""),
    },
    {
      accessorKey: "episode",
      header: "Episode",
      cell: (info) => String(info.getValue() ?? ""),
    },
    {
      accessorKey: "title",
      header: "Title",
      cell: (info) => String(info.getValue() ?? ""),
    },
    {
      id: "monitored",
      header: "Monitored",
      cell: ({ row }) => (
        <span
          className={`track-status ${row.original.monitored ? "available" : "missing"}`}
        >
          {row.original.monitored ? "✓" : "✗"}
        </span>
      ),
    },
    {
      id: "hasFile",
      header: "Has File",
      cell: ({ row }) => (
        <span
          className={`track-status ${row.original.hasFile ? "available" : "missing"}`}
        >
          {row.original.hasFile ? "✓" : "✗"}
        </span>
      ),
    },
    {
      accessorKey: "airDate",
      header: "Air Date",
      cell: (info) => String(info.getValue() || "—"),
    },
    {
      accessorKey: "qualityProfileName",
      header: "Quality profile",
      cell: (info) => String(info.getValue() || "—"),
    },
    {
      accessorKey: "reason",
      header: "Reason",
      cell: ({ row }) =>
        row.original.reason ? (
          <span className="table-badge table-badge-reason">{row.original.reason}</span>
        ) : (
          <span className="table-badge table-badge-reason">Not being searched</span>
        ),
    },
  );
  return cols;
}

function useSonarrFlatInstancePipeline(
  params: ArrCatalogInstancePipelineParams<SonarrCatalogFilters>,
): ArrCatalogInstancePipelineState<SonarrEpisodeFlatRow> {
  const {
    active,
    selection,
    instanceLabel,
    filters,
    polling,
    roundPageSize,
    globalSearchRef,
    registerSearchHandler,
    pushToast,
    iconInstancePageSize,
    browseMode,
  } = params;

  const [pages, setPages] = useState<Record<number, SonarrSeriesEntry[]>>({});
  const [response, setResponse] = useState<SonarrSeriesResponse | null>(null);
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const [pageSize, setPageSize] = useState(SONARR_FLAT_PAGE_SIZE);
  const [loading, setLoading] = useState(false);
  const [emptyStateReady, setEmptyStateReady] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const { pagesRef, keyRef, wipePages } = useCatalogPageCache<SonarrSeriesEntry>();
  const emptyTracker = useCatalogEmptyStateTracker();
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const rowsStoreOpts = useMemo(
    () => ({
      getKey: sonarrFlatEpisodeRowKey,
      hashFields: SONARR_FLAT_HASH_FIELDS as unknown as ReadonlyArray<
        keyof SonarrEpisodeFlatRow & string
      >,
    }),
    [],
  );
  const { snapshot, store } = useRowsStore<SonarrEpisodeFlatRow>(
    rowsStoreOpts as never,
  );

  const fetchInstance = useCallback(
    async (
      category: string,
      pageIdx: number,
      requestQuery: string,
      options: { showLoading?: boolean; missingOnly?: boolean; preloadAll?: boolean } = {},
    ) => {
      const showLoading = options.showLoading ?? true;
      const preloadAll = options.preloadAll ?? true;
      const useMissing = options.missingOnly ?? filtersRef.current.onlyMissing;
      if (showLoading) setLoading(true);
      try {
        const key = `${category}::${requestQuery}::${
          useMissing ? "missing" : "all"
        }`;
        const keyChanged = keyRef.current !== key;
        if (keyChanged) {
          keyRef.current = key;
          const wiped = wipePages();
          pagesRef.current = wiped;
          setPages({});
          setPage(0);
          setEmptyStateReady(false);
          emptyTracker.resetEmptyState();
        }
        const effectivePageIdx = keyChanged ? 0 : pageIdx;
        const ps = roundPageSize(25);

        const loadSeriesPage = async (targetPage: number) => {
          const res = await getSonarrSeries(
            category,
            targetPage,
            ps,
            requestQuery,
            { missingOnly: useMissing },
          );
          const series = res.series ?? [];
          const prev = pagesRef.current;
          const prevSlice = prev[targetPage] ?? [];
          const pageChanged =
            keyChanged ||
            !arraysEqual<SonarrSeriesComparable>(
              prevSlice as SonarrSeriesComparable[],
              series as SonarrSeriesComparable[],
              getSonarrSeriesEntryKey,
              SONARR_INSTANCE_PAGE_HASH_FIELDS,
            );
          const next = { ...pagesRef.current, [targetPage]: series };
          pagesRef.current = next;
          if (pageChanged) {
            setPages({ ...next } as Record<number, SonarrSeriesEntry[]>);
            setLastUpdated(new Date().toLocaleTimeString());
          }
          return res;
        };

        const res = await loadSeriesPage(effectivePageIdx);
        const total = res.total ?? (res.series ?? []).length;
        const computedSeriesPages = Math.max(1, Math.ceil((total || 0) / ps));
        setQuery(requestQuery);
        setPageSize(roundPageSize(SONARR_FLAT_PAGE_SIZE));

        const hasCatalogData = (res.series ?? []).length > 0 || total > 0;
        if (hasCatalogData) {
          emptyTracker.noteCatalogData(true);
          setEmptyStateReady(true);
        } else {
          emptyTracker.noteCatalogData(false);
          setEmptyStateReady(isEmptyStateReady(emptyTracker, false));
        }

        setResponse(res);

        if (preloadAll && computedSeriesPages > 1) {
          for (let i = 0; i < computedSeriesPages; i += 1) {
            if (i === effectivePageIdx || pagesRef.current[i]) continue;
            await loadSeriesPage(i);
          }
        }
      } catch (error) {
        pushToast(
          error instanceof Error
            ? error.message
            : `Failed to load ${category} series`,
          "error",
        );
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    [pushToast, roundPageSize, emptyTracker, keyRef, pagesRef, wipePages],
  );

  const fetchInstanceRef = useRef(fetchInstance);
  useLayoutEffect(() => {
    fetchInstanceRef.current = fetchInstance;
  }, [fetchInstance]);

  useEffect(() => {
    if (!active || !selection) return;
    void fetchInstanceRef.current(selection, 0, globalSearchRef.current, {
      showLoading: true,
      missingOnly: filters.onlyMissing,
      preloadAll: true,
    });
    store.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, selection, filters.onlyMissing]);

  useCatalogSearchRegistration(active, selection, registerSearchHandler, (term) => {
    setPage(0);
    void fetchInstanceRef.current(selection!, 0, term, {
      showLoading: true,
      missingOnly: filtersRef.current.onlyMissing,
      preloadAll: true,
    });
  });

  useInterval(
    () => {
      if (document.visibilityState !== "visible" || !selection) return;
      if (globalSearchRef.current?.trim?.()) return;
      void fetchInstanceRef.current(selection, 0, query, {
        showLoading: false,
        missingOnly: filtersRef.current.onlyMissing,
        preloadAll: true,
      });
    },
    active && polling && selection ? INSTANCE_VIEW_POLL_INTERVAL_MS : null,
  );

  useCatalogIconGridRefetch(
    active,
    selection,
    browseMode,
    iconInstancePageSize,
    () => {
      void fetchInstanceRef.current(selection!, 0, query, {
        showLoading: false,
        missingOnly: filtersRef.current.onlyMissing,
        preloadAll: true,
      });
    },
  );

  const allSeries = useMemo(() => {
    const sortedKeys = Object.keys(pages)
      .map(Number)
      .sort((a, b) => a - b);
    const out: SonarrSeriesEntry[] = [];
    for (const k of sortedKeys) {
      const slice = pages[k];
      if (slice) out.push(...slice);
    }
    return out;
  }, [pages]);

  const filteredEpisodes = useMemo(() => {
    const missingFiltered = filterSeriesEntriesForMissing(
      allSeries,
      filters.onlyMissing,
    );
    const withReason: SonarrSeriesEntry[] = [];
    for (const entry of missingFiltered) {
      const f = filterSeriesEntryByReason(entry, filters.reasonFilter);
      if (f) withReason.push(f);
    }
    const flat: SonarrEpisodeFlatRow[] = [];
    for (const entry of withReason) {
      flat.push(...seriesEntryToFlatEpisodes(entry, instanceLabel));
    }
    return filterSonarrFlatEpisodes(
      flat,
      filters,
      globalSearchRef.current || "",
    );
  }, [allSeries, filters, instanceLabel, globalSearchRef]);

  const totalPages = Math.max(
    1,
    Math.ceil(filteredEpisodes.length / pageSize),
  );
  const visibleRows = useMemo(
    () => filteredEpisodes.slice(page * pageSize, page * pageSize + pageSize),
    [filteredEpisodes, page, pageSize],
  );

  useEffect(() => {
    store.sync(visibleRows);
  }, [visibleRows, store]);

  const showCatalogEmptyHint =
    !loading &&
    allSeries.length === 0 &&
    (response?.total ?? 0) === 0 &&
    response != null;

  return {
    loading,
    emptyStateReady,
    lastUpdated,
    page,
    pageSize,
    totalPages,
    totalItems: filteredEpisodes.length,
    visibleRows,
    rowsStore: store,
    rowOrder: snapshot.rowOrder,
    showCatalogEmptyHint,
    setPage,
    refresh: () => {
      if (!selection) return;
      void fetchInstanceRef.current(selection, 0, query, {
        showLoading: true,
        missingOnly: filtersRef.current.onlyMissing,
        preloadAll: true,
      });
    },
  };
}

export const SONARR_FLAT_DEFINITION: ArrCatalogDefinition<
  SonarrEpisodeFlatRow,
  SonarrEpisodeFlatRow,
  SonarrCatalogFilters,
  SonarrEpisodeFlatRow,
  SonarrEpisodeFlatRow,
  SonarrEpisodeFlatRow,
  SonarrSeriesResponse,
  null
> = {
  kind: "sonarr",
  arrType: "sonarr",
  cardTitle: "Sonarr",
  allInstancesLabel: "All Sonarr",
  searchPlaceholder: "Filter episodes",
  initialFilters: { onlyMissing: false, reasonFilter: "all" },
  filterControls: createStandardArrFilters<SonarrCatalogFilters>("All Episodes"),
  aggregate: {
    basePageSize: SONARR_FLAT_PAGE_SIZE,
    initialRollup: null,
    initialSummary: { available: 0, monitored: 0, missing: 0, total: 0 },
    fetchPage: (category, pageIdx, chunk, filters) =>
      getSonarrSeries(category, pageIdx, chunk, "", {
        missingOnly: filters.onlyMissing,
      }),
    extractSlice: (response) => ({
      slice: response.series ?? [],
      batchLength: (response.series ?? []).length,
      total: response.total,
      pageSize: response.page_size,
    }),
    mapSlice: (response, instanceLabel, push) => {
      for (const entry of response.series ?? []) {
        for (const row of seriesEntryToFlatEpisodes(entry, instanceLabel)) {
          push(row);
        }
      }
    },
    summarize: (rows) => summarizeFlatEpisodes(rows),
    getRowKey: sonarrFlatEpisodeRowKey,
    hashFields: SONARR_FLAT_HASH_FIELDS as unknown as ReadonlyArray<
      keyof SonarrEpisodeFlatRow & string
    >,
    filterRows: (rows, filters, debouncedSearch) =>
      filterSonarrFlatEpisodes(rows, filters, debouncedSearch),
  },
  useInstancePipeline: useSonarrFlatInstancePipeline,
  buildAggregateSelection: () => null,
  buildInstanceSelection: () => null,
  getModalLiveRow: ({ instanceFresh, aggregateFresh, instanceSeed, aggregateSeed, source }) => {
    if (source === "instance") {
      return (instanceFresh ?? instanceSeed) as SonarrEpisodeFlatRow;
    }
    return (aggregateFresh ?? aggregateSeed) as SonarrEpisodeFlatRow;
  },
  getModalTitle: (liveRow) =>
    `${liveRow.series} S${liveRow.season}E${liveRow.episode}`,
  getModalMaxWidth: () => 720,
  renderModalBody: () => null,
  renderAggregateBody: (props) => <SonarrFlatAggregateBody {...props} />,
  renderInstanceBody: (props) => <SonarrFlatInstanceBody {...props} />,
};

function SonarrFlatAggregateBody({
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
  browseMode,
  iconGridRef,
  instanceCount,
}: {
  readonly rows: ReadonlyArray<SonarrEpisodeFlatRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<SonarrEpisodeFlatRow>;
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
  readonly browseMode: "list" | "icon";
  readonly iconGridRef: RefCallback<HTMLElement | null>;
  readonly instances: ReadonlyArray<ArrInfo>;
  readonly instanceCount: number;
}): JSX.Element {
  const columns = buildSonarrFlatColumns(instanceCount);
  const effectiveLoading =
    loading || (instanceCount > 0 && !emptyStateReady && total === 0);
  return (
    <ArrCatalogStandardBody
      summaryLine={
        <>
          Flat episode list across all instances{" "}
          {lastUpdated ? `(updated ${lastUpdated})` : ""}
          <br />
          <strong>Available:</strong> {summary.available.toLocaleString()} •{" "}
          <strong>Monitored:</strong> {summary.monitored.toLocaleString()} •{" "}
          <strong>Missing:</strong> {summary.missing.toLocaleString()} •{" "}
          <strong>Episodes:</strong> {summary.total.toLocaleString()}
          {isAggFiltered && total < summary.total ? (
            <> • <strong>Filtered:</strong> {total.toLocaleString()}</>
          ) : null}
        </>
      }
      onRefresh={onRefresh}
      loading={effectiveLoading}
      loadingHint="Loading Sonarr episodes…"
      emptyOrder="noItemsFirst"
      showCatalogEmptyHint={
        !effectiveLoading && total === 0 && summary.total === 0 && instanceCount > 0
      }
      hasRows={total > 0}
      catalogEmptyMessage="No episodes found in the database."
      noMatchMessage="No episodes match the current filters."
      showPagination={total > 0}
      page={page}
      totalPages={totalPages}
      total={total}
      itemNoun="episodes"
      pageSize={aggregatePageSize}
      onPageChange={onPageChange}
      browseMode={browseMode}
      rows={rows}
      rowOrder={rowOrder}
      rowsStore={rowsStore}
      columns={columns}
      getRowKey={sonarrFlatEpisodeRowKey}
      onRowSelect={() => undefined}
      iconGridRef={iconGridRef}
      renderIconTile={(row) => (
        <div className="arr-movie-tile arr-movie-tile--text" key={sonarrFlatEpisodeRowKey(row)}>
          <div className="arr-movie-tile__title">{row.series}</div>
          <div className="arr-movie-tile__meta">
            S{row.season}E{row.episode} — {row.title}
          </div>
        </div>
      )}
    />
  );
}

function SonarrFlatInstanceBody({
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
  setPage,
  refresh,
  filters,
}: {
  readonly visibleRows: ReadonlyArray<SonarrEpisodeFlatRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<SonarrEpisodeFlatRow>;
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
  readonly setPage: (page: number) => void;
  readonly refresh: () => void;
  readonly filters: SonarrCatalogFilters;
}): JSX.Element {
  const effectiveLoading = loading || (!emptyStateReady && visibleRows.length === 0);
  const isFiltered = filters.onlyMissing || filters.reasonFilter !== "all";
  const columns = buildSonarrFlatColumns(1);
  return (
    <ArrCatalogStandardBody
      summaryLine={
        <>
          <strong>Episodes shown:</strong> {visibleRows.length.toLocaleString()} •{" "}
          <strong>Episodes total:</strong> {totalItems.toLocaleString()}
          {lastUpdated ? ` (updated ${lastUpdated})` : ""}
        </>
      }
      onRefresh={refresh}
      loading={effectiveLoading}
      loadingHint="Loading episodes…"
      emptyOrder="noItemsFirst"
      showCatalogEmptyHint={showCatalogEmptyHint}
      hasRows={visibleRows.length > 0 || !isFiltered}
      catalogEmptyMessage="No episodes in the local catalog yet."
      noMatchMessage="No episodes match the current filters."
      showPagination={totalPages > 1}
      page={page}
      totalPages={totalPages}
      total={totalItems}
      itemNoun="episodes"
      pageSize={pageSize}
      onPageChange={setPage}
      browseMode={browseMode}
      rows={visibleRows}
      rowOrder={rowOrder}
      rowsStore={rowsStore}
      columns={columns}
      getRowKey={sonarrFlatEpisodeRowKey}
      onRowSelect={() => undefined}
      iconGridRef={iconGridRef}
      renderIconTile={(row) => (
        <div className="arr-movie-tile arr-movie-tile--text" key={sonarrFlatEpisodeRowKey(row)}>
          <div className="arr-movie-tile__title">{row.series}</div>
          <div className="arr-movie-tile__meta">
            S{row.season}E{row.episode} — {row.title}
          </div>
        </div>
      )}
    />
  );
}
