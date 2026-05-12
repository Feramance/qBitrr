import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ArrInfo } from "../../api/types";
import {
  AGGREGATE_FETCH_CHUNK_SIZE,
  AGGREGATE_POLL_INTERVAL_MS,
} from "../../constants/arrAggregateFetch";
import { useDataSync } from "../../hooks/useDataSync";
import { useDebounce } from "../../hooks/useDebounce";
import { useInterval } from "../../hooks/useInterval";
import { useRowsStore } from "../../hooks/useRowsStore";
import type { Hashable } from "../../utils/dataSync";
import type { RowsStore } from "../../utils/rowsStore";
import type {
  ArrCatalogAggregateAdapter,
  ArrCatalogSummary,
} from "./definition";
import { forEachInstanceChunkedPages } from "./forEachInstanceChunkedPages";

interface UseAggregateCatalogLoaderParams<
  TAggRow extends Hashable,
  TAggResp,
  TFilters extends Record<string, unknown>,
  TRollup,
> {
  readonly active: boolean;
  readonly selection: string | "aggregate";
  readonly instances: ReadonlyArray<ArrInfo>;
  readonly liveArr: boolean;
  readonly globalSearch: string;
  readonly filters: TFilters;
  readonly adapter: ArrCatalogAggregateAdapter<TAggRow, TAggResp, TFilters, TRollup>;
  readonly aggregatePageSize: number;
  readonly pushToast: (
    message: string,
    kind?: "info" | "success" | "warning" | "error",
  ) => void;
}

/**
 * Aggregate catalog loader — owns the entire "All instances" data pipeline.
 *
 * Fully generic: the adapter supplies fetch / map / summarize / sort + filter helpers,
 * the loader owns state machinery (rows, page, summary, updated, loading, generation
 * cancellation, polling, page reset on filter change).
 *
 * Behaviour alignments (intentional, per consolidation plan):
 * - Timestamp updates only when rows or summary actually change (Lidarr previously
 *   bumped on every successful run; aligned to Radarr/Sonarr semantics).
 * - Page resets to 0 only when the debounced filter / search changed; refresh keeps
 *   the user on the current page.
 */
export interface UseAggregateCatalogLoaderResult<TAggRow extends Hashable> {
  readonly rows: ReadonlyArray<TAggRow>;
  readonly visibleRows: ReadonlyArray<TAggRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<TAggRow>;
  readonly loading: boolean;
  readonly emptyStateReady: boolean;
  readonly page: number;
  readonly totalPages: number;
  readonly total: number;
  readonly summary: ArrCatalogSummary;
  readonly lastUpdated: string | null;
  readonly debouncedSearch: string;
  readonly isAggFiltered: boolean;
  readonly setPage: (page: number) => void;
  readonly refresh: () => void;
  readonly hasActiveLoad: () => boolean;
}

export function useAggregateCatalogLoader<
  TAggRow extends Hashable,
  TAggResp,
  TFilters extends Record<string, unknown>,
  TRollup,
>(
  params: UseAggregateCatalogLoaderParams<TAggRow, TAggResp, TFilters, TRollup>,
): UseAggregateCatalogLoaderResult<TAggRow> {
  const {
    active,
    selection,
    instances,
    liveArr,
    globalSearch,
    filters,
    adapter,
    aggregatePageSize,
    pushToast,
  } = params;

  const [rows, setRows] = useState<TAggRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [emptyStateReady, setEmptyStateReady] = useState(false);
  const [page, setPage] = useState(0);
  const [aggFilter, setAggFilter] = useState("");
  const [updated, setUpdated] = useState<string | null>(null);
  const [summary, setSummary] = useState<ArrCatalogSummary>(adapter.initialSummary);
  const debouncedSearch = useDebounce(aggFilter, 300);

  const aggFetchGenRef = useRef(0);
  const aggActiveLoadsRef = useRef(0);
  const aggRequestKeyRef = useRef("");
  const sawNonEmptyRef = useRef(false);
  const stableEmptyStreakRef = useRef(0);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const globalSearchRef = useRef(globalSearch);
  globalSearchRef.current = globalSearch;
  const aggFilterRef = useRef(aggFilter);
  aggFilterRef.current = aggFilter;

  const dataSyncOpts = useMemo(
    () => ({
      getKey: adapter.getRowKey,
      hashFields: adapter.hashFields as ReadonlyArray<keyof TAggRow & string>,
    }),
    [adapter.getRowKey, adapter.hashFields],
  );
  const dataSync = useDataSync<TAggRow>(dataSyncOpts as never);

  const rowsStoreOpts = useMemo(
    () => ({
      getKey: adapter.getRowKey,
      hashFields: adapter.hashFields as ReadonlyArray<keyof TAggRow & string>,
    }),
    [adapter.getRowKey, adapter.hashFields],
  );
  const { snapshot, store } = useRowsStore<TAggRow>(rowsStoreOpts as never);

  const filteredRows = useMemo<ReadonlyArray<TAggRow>>(() => {
    const filterFn = adapter.filterRows;
    if (!filterFn) return rows;
    return filterFn(rows, filtersRef.current, debouncedSearch);
  }, [rows, debouncedSearch, adapter]);

  const sortedRows = useMemo<ReadonlyArray<TAggRow>>(() => {
    const sortFn = adapter.sortRows;
    if (!sortFn) return filteredRows;
    return sortFn(filteredRows);
  }, [filteredRows, adapter]);

  const total = sortedRows.length;
  const totalPages = Math.max(1, Math.ceil(total / aggregatePageSize));
  const safePage = Math.min(page, Math.max(0, totalPages - 1));

  const visibleRows = useMemo<ReadonlyArray<TAggRow>>(
    () =>
      sortedRows.slice(
        safePage * aggregatePageSize,
        safePage * aggregatePageSize + aggregatePageSize,
      ),
    [sortedRows, safePage, aggregatePageSize],
  );

  // Sync only the visible page slice into the row store.  Page changes are an
  // `add-remove` operation; live polls inside the same page yield `update-only`,
  // letting tanstack-table reuse the existing row model.
  useEffect(() => {
    store.sync([...visibleRows]);
  }, [visibleRows, store]);

  const loadAggregate = useCallback(
    async (options?: { showLoading?: boolean }) => {
      if (!instances.length) {
        setRows([]);
        setSummary(adapter.initialSummary);
        setEmptyStateReady(true);
        return;
      }
      const showLoading = options?.showLoading ?? true;
      const gen = ++aggFetchGenRef.current;
      aggActiveLoadsRef.current += 1;
      const requestKey = JSON.stringify({
        instances: [...instances]
          .map((instance) => instance.category)
          .sort((a, b) => a.localeCompare(b)),
        search: globalSearchRef.current,
        filters: filtersRef.current,
      });
      if (aggRequestKeyRef.current !== requestKey) {
        aggRequestKeyRef.current = requestKey;
        sawNonEmptyRef.current = false;
        stableEmptyStreakRef.current = 0;
        setEmptyStateReady(false);
      }
      if (showLoading) {
        setLoading(true);
      }
      const chunk = AGGREGATE_FETCH_CHUNK_SIZE;
      const currentFilters = filtersRef.current;
      try {
        const aggregated: TAggRow[] = [];
        let progressFirstPaint = false;
        let rollup = adapter.initialRollup;

        await forEachInstanceChunkedPages<TAggResp>({
          instances,
          chunk,
          gen,
          genRef: aggFetchGenRef,
          fetchSlice: async (category, pageIdx, chunkSize) => {
            const response = await adapter.fetchPage(
              category,
              pageIdx,
              chunkSize,
              currentFilters,
            );
            const extracted = adapter.extractSlice(response);
            return {
              slice: extracted.slice,
              batchLength: extracted.batchLength,
              total: extracted.total,
              page_size: extracted.pageSize,
              response,
            };
          },
          onInstanceFirstPage: (_instTotal, response) => {
            if (adapter.accumulateRollup) {
              rollup = adapter.accumulateRollup(rollup, response);
            }
            // Do not clear loading when the first instance has total===0: other instances
            // may still be fetching (multi-instance aggregate). Rely on first slice rows or
            // `finally` so we never flash an empty library while work is in flight.
          },
          onSlice: (_slice, instanceLabel, response) => {
            adapter.mapSlice(response, instanceLabel, (row) => {
              aggregated.push(row);
            });
            if (showLoading && !progressFirstPaint && aggregated.length > 0) {
              setLoading(false);
              progressFirstPaint = true;
            }
          },
        });

        if (gen !== aggFetchGenRef.current) {
          return;
        }

        const syncResult = dataSync.syncData(aggregated);
        const rowsChanged = syncResult.hasChanges;

        if (rowsChanged) {
          setRows(syncResult.data);
        }

        const newSummary = adapter.summarize(aggregated, rollup);
        const hasCatalogData =
          aggregated.length > 0 ||
          newSummary.total > 0 ||
          newSummary.monitored > 0 ||
          newSummary.available > 0 ||
          newSummary.missing > 0;

        if (hasCatalogData) {
          sawNonEmptyRef.current = true;
          stableEmptyStreakRef.current = 0;
          setEmptyStateReady((prev) => (prev ? prev : true));
        } else {
          stableEmptyStreakRef.current += 1;
          const ready = sawNonEmptyRef.current || stableEmptyStreakRef.current >= 2;
          setEmptyStateReady((prev) => (prev === ready ? prev : ready));
        }

        let summaryChanged = false;
        setSummary((prev) => {
          if (
            prev.available === newSummary.available &&
            prev.monitored === newSummary.monitored &&
            prev.missing === newSummary.missing &&
            prev.total === newSummary.total &&
            prev.rollupTotalAlbumsHint === newSummary.rollupTotalAlbumsHint
          ) {
            return prev;
          }
          summaryChanged = true;
          return newSummary;
        });

        const currentSearch = globalSearchRef.current;
        if (aggFilterRef.current !== currentSearch) {
          setPage(0);
          setAggFilter(currentSearch);
        }

        if (rowsChanged || summaryChanged) {
          setUpdated(new Date().toLocaleTimeString());
        }
      } catch (error) {
        if (gen !== aggFetchGenRef.current) {
          return;
        }
        setRows([]);
        setSummary(adapter.initialSummary);
        pushToast(
          error instanceof Error
            ? error.message
            : "Failed to load aggregated catalog data",
          "error",
        );
      } finally {
        aggActiveLoadsRef.current -= 1;
        if (gen === aggFetchGenRef.current) {
          setLoading(false);
        }
      }
    },
    // `aggFilter` is read via `aggFilterRef` so typing in global search does not
    // change this callback identity (which would retrigger the aggregate load effect).
    // Use `dataSync.syncData` only: `useDataSync` returns a fresh object each render,
    // so depending on `dataSync` would recreate this callback every render and re-fire
    // the aggregate `useEffect` in a tight loop (loading / empty flicker).
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stable syncData; whole `dataSync` object is unstable
    [adapter, instances, dataSync.syncData, pushToast],
  );

  // Trigger initial load when the user navigates to the aggregate view.
  useEffect(() => {
    if (!active) return;
    if (selection !== "aggregate") return;
    void loadAggregate();
  }, [active, selection, loadAggregate]);

  // Sync the aggregate filter with the global search whenever the user is on the
  // aggregate view.
  useEffect(() => {
    if (selection === "aggregate") {
      setAggFilter(globalSearch);
    }
  }, [selection, globalSearch]);

  // Polling on visible aggregate view (only when liveArr is enabled).
  useInterval(
    () => {
      if (document.visibilityState !== "visible") return;
      if (
        selection === "aggregate" &&
        liveArr &&
        aggActiveLoadsRef.current === 0
      ) {
        void loadAggregate({ showLoading: false });
      }
    },
    selection === "aggregate" && liveArr ? AGGREGATE_POLL_INTERVAL_MS : null,
  );

  const refresh = useCallback(() => {
    void loadAggregate({ showLoading: true });
  }, [loadAggregate]);

  const isAggFiltered = useMemo(() => {
    if (debouncedSearch) return true;
    if (!adapter.filterRows) return false;
    // Conservative: if a filter callback exists, treat any non-default filter set
    // as filtered. Definitions can override by checking summary mismatch instead.
    return total < rows.length;
  }, [debouncedSearch, adapter.filterRows, total, rows.length]);

  const hasActiveLoad = useCallback(() => aggActiveLoadsRef.current > 0, []);

  return {
    rows,
    visibleRows,
    rowOrder: snapshot.rowOrder,
    rowsStore: store,
    loading,
    emptyStateReady,
    page: safePage,
    totalPages,
    total,
    summary,
    lastUpdated: updated,
    debouncedSearch,
    isAggFiltered,
    setPage,
    refresh,
    hasActiveLoad,
  };
}
