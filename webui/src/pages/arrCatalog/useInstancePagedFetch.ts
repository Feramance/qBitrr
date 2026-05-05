import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { INSTANCE_VIEW_POLL_INTERVAL_MS } from "../../constants/arrAggregateFetch";
import { useDataSync } from "../../hooks/useDataSync";
import { useInterval } from "../../hooks/useInterval";
import { useRowsStore } from "../../hooks/useRowsStore";
import type { Hashable } from "../../utils/dataSync";
import type {
  ArrCatalogInstancePipelineParams,
  ArrCatalogInstancePipelineState,
} from "./definition";

/**
 * Flat-strategy instance pipeline used by Radarr + Lidarr.
 *
 * Owns: page cache, key invalidation on filter change, surgical row store, polling
 * (when liveArr is on and no global search is active), search registration, and
 * page reset on selection change. Filter-only changes preserve the current page.
 */
export interface UseInstancePagedFetchAdapter<
  TInstRow extends Hashable,
  TResp,
  TFilters extends Record<string, unknown>,
> {
  readonly basePageSize: number;
  /** Stable id used by the row store + diff pipeline. */
  readonly getRowKey: (row: TInstRow) => string;
  /** Hash fields fed into `useDataSync` and the row store. */
  readonly hashFields: ReadonlyArray<keyof TInstRow & string>;
  /** Build the request key — when this string changes, the page cache is wiped. */
  readonly buildKey: (params: {
    readonly category: string;
    readonly query: string;
    readonly filters: TFilters;
  }) => string;
  /** Single-page fetch. */
  readonly fetchPage: (
    category: string,
    page: number,
    pageSize: number,
    query: string,
    filters: TFilters,
  ) => Promise<TResp>;
  /** Extract metadata + rows from the response. */
  readonly extractPage: (response: TResp) => {
    readonly rows: ReadonlyArray<TInstRow>;
    readonly page: number;
    readonly pageSize: number;
    readonly total: number;
  };
  /**
   * True when the response indicates the catalog itself is empty (all rollup zero +
   * empty rows). Lidarr inspects extra fields; Radarr does not.
   */
  readonly isCatalogEmpty?: (response: TResp) => boolean;
  /**
   * Optional client-side filter applied after fetch (Radarr applies status / reason
   * to the cached pages before pagination). When omitted, all rows are surfaced.
   */
  readonly filterRows?: (
    rows: ReadonlyArray<TInstRow>,
    filters: TFilters,
  ) => ReadonlyArray<TInstRow>;
  /**
   * When `true`, the cache keeps every fetched page (Radarr) so the user can flip
   * between pages without refetching. When `false`, only the active page is kept
   * (Lidarr — server is fast and most users never preload).
   */
  readonly keepAllPages: boolean;
  /** Generic toast message factory for fetch errors. */
  readonly errorMessage: (category: string) => string;
}

export interface UseInstancePagedFetchResult<TInstRow extends Hashable>
  extends ArrCatalogInstancePipelineState<TInstRow> {
  /** Diagnostic: latest server response (used by Lidarr's empty-state copy). */
  readonly latestResponse: unknown;
}

export function useInstancePagedFetch<
  TInstRow extends Hashable,
  TResp,
  TFilters extends Record<string, unknown>,
>(
  shellParams: ArrCatalogInstancePipelineParams<TFilters>,
  adapter: UseInstancePagedFetchAdapter<TInstRow, TResp, TFilters>,
): UseInstancePagedFetchResult<TInstRow> {
  const {
    active,
    selection,
    filters,
    polling,
    roundPageSize,
    globalSearchRef,
    registerSearchHandler,
    pushToast,
    iconInstancePageSize,
  } = shellParams;

  const [pages, setPages] = useState<Record<number, ReadonlyArray<TInstRow>>>(
    {},
  );
  const [latestResponse, setLatestResponse] = useState<TResp | null>(null);
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [pageSize, setPageSize] = useState(adapter.basePageSize);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);

  const pagesRef = useRef<Record<number, ReadonlyArray<TInstRow>>>({});
  const keyRef = useRef<string>("");
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const prevSelectionRef = useRef<string | null>(selection);

  const dataSyncOpts = useMemo(
    () => ({
      getKey: adapter.getRowKey,
      hashFields: adapter.hashFields as ReadonlyArray<keyof TInstRow & string>,
    }),
    [adapter.getRowKey, adapter.hashFields],
  );
  const dataSync = useDataSync<TInstRow>(dataSyncOpts as never);

  const rowsStoreOpts = useMemo(
    () => ({
      getKey: adapter.getRowKey,
      hashFields: adapter.hashFields as ReadonlyArray<keyof TInstRow & string>,
    }),
    [adapter.getRowKey, adapter.hashFields],
  );
  const { snapshot, store } = useRowsStore<TInstRow>(rowsStoreOpts as never);

  const fetchInstance = useCallback(
    async (
      category: string,
      pageIdx: number,
      requestQuery: string,
      options: { showLoading?: boolean } = {},
    ) => {
      const showLoading = options.showLoading ?? true;
      if (showLoading) setLoading(true);
      try {
        const currentFilters = filtersRef.current;
        const key = adapter.buildKey({
          category,
          query: requestQuery,
          filters: currentFilters,
        });
        const keyChanged = keyRef.current !== key;
        if (keyChanged) {
          keyRef.current = key;
          pagesRef.current = {};
          setPages({});
          setTotalItems(0);
          setTotalPages(1);
          setPage(0);
          dataSync.reset();
        }
        // After a filter/query key change, always request page 0 — the caller may still
        // pass a stale page index from React state, which would otherwise fetch an empty
        // slice and leave `pages` cleared (Lidarr/Radarr looked "empty" until a later poll).
        const effectivePageIdx = keyChanged ? 0 : pageIdx;
        const ps = roundPageSize(adapter.basePageSize);
        const response = await adapter.fetchPage(
          category,
          effectivePageIdx,
          ps,
          requestQuery,
          currentFilters,
        );
        setLatestResponse(response);
        const extracted = adapter.extractPage(response);
        const resolvedPage = Math.max(
          0,
          Math.floor(
            Number.isFinite(Number(extracted.page))
              ? Number(extracted.page)
              : Number.parseInt(String(extracted.page ?? "0"), 10) || 0,
          ),
        );
        const resolvedPageSize = extracted.pageSize;
        const total = extracted.total;
        const rows = extracted.rows;
        const computedTotalPages = Math.max(
          1,
          Math.ceil((total || 0) / resolvedPageSize),
        );

        const syncResult = dataSync.syncData([...rows]);
        const rowsChanged = syncResult.hasChanges;

        // Always persist `pages` when the cache key changed — even if `rowsChanged` is
        // false (e.g. sync edge cases), otherwise `pages` stays `{}` after the wipe above.
        if (keyChanged) {
          setPages(() => {
            const next: Record<number, ReadonlyArray<TInstRow>> = {
              [resolvedPage]: syncResult.data,
            };
            pagesRef.current = next;
            return next;
          });
          setLastUpdated(new Date().toLocaleTimeString());
        } else if (rowsChanged) {
          setPages((prev) => {
            let next: Record<number, ReadonlyArray<TInstRow>>;
            if (adapter.keepAllPages) {
              next = { ...prev, [resolvedPage]: syncResult.data };
            } else {
              next = { [resolvedPage]: syncResult.data };
            }
            pagesRef.current = next;
            return next;
          });
          setLastUpdated(new Date().toLocaleTimeString());
        }

        setPage((p) => (p === resolvedPage ? p : resolvedPage));
        setQuery((q) => (q === requestQuery ? q : requestQuery));
        setPageSize((s) => (s === resolvedPageSize ? s : resolvedPageSize));
        setTotalPages((tp) =>
          tp === computedTotalPages ? tp : computedTotalPages,
        );
        setTotalItems((ti) => (ti === total ? ti : total));
      } catch (error) {
        pushToast(
          error instanceof Error ? error.message : adapter.errorMessage(category),
          "error",
        );
      } finally {
        if (showLoading) setLoading(false);
      }
    },
    // `useDataSync` returns a new object each render; depend on stable callbacks only.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stable syncData/reset; whole `dataSync` object is unstable
    [adapter, dataSync.syncData, dataSync.reset, pushToast, roundPageSize],
  );

  const fetchInstanceRef = useRef(fetchInstance);
  useLayoutEffect(() => {
    fetchInstanceRef.current = fetchInstance;
  }, [fetchInstance]);

  // Selection / filter change effect: reset page only on selection change, otherwise
  // preserve the current page (aligned across Arrs per consolidation plan).
  useEffect(() => {
    if (!active) return;
    if (!selection) return;

    const selectionChanged = prevSelectionRef.current !== selection;
    if (selectionChanged) {
      pagesRef.current = {};
      setPages({});
      setTotalPages(1);
      setPage(0);
      prevSelectionRef.current = selection;
    }

    const requestQuery = globalSearchRef.current;
    void fetchInstanceRef.current(
      selection,
      selectionChanged ? 0 : page,
      requestQuery,
      { showLoading: true },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `page` intentionally excluded; pagination triggers fetch via setPage handler.
  }, [active, selection, filters]);

  // Reset row store on selection change to avoid leaking rows from prev instance.
  useEffect(() => {
    store.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);

  // Search handler — registered once per shell mount with a ref-based closure.
  useEffect(() => {
    if (!active) return;
    const handler = (term: string) => {
      if (!selection) return;
      setPage(0);
      void fetchInstanceRef.current(selection, 0, term, { showLoading: true });
    };
    return registerSearchHandler(handler);
  }, [active, selection, registerSearchHandler]);

  // Background polling.
  useInterval(
    () => {
      if (document.visibilityState !== "visible") return;
      if (!selection) return;
      const activeFilter = globalSearchRef.current?.trim?.() || "";
      if (activeFilter) return;
      void fetchInstanceRef.current(selection, page, query, {
        showLoading: false,
      });
    },
    active && polling && selection ? INSTANCE_VIEW_POLL_INTERVAL_MS : null,
  );

  // Re-fetch on icon-grid resize so the page-size matches the grid columns.
  useEffect(() => {
    if (!active) return;
    if (!selection) return;
    if (shellParams.browseMode !== "icon") return;
    void fetchInstanceRef.current(selection, page, query, {
      showLoading: false,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, selection, shellParams.browseMode, iconInstancePageSize]);

  // Build "all cached rows" view used by Radarr's filter-then-paginate pattern.  When
  // `keepAllPages` is false, this is just the current page (Lidarr).
  const allRows = useMemo<ReadonlyArray<TInstRow>>(() => {
    if (!adapter.keepAllPages) {
      return pages[page] ?? [];
    }
    const sortedKeys = Object.keys(pages)
      .map(Number)
      .sort((a, b) => a - b);
    const out: TInstRow[] = [];
    for (const k of sortedKeys) {
      const slice = pages[k];
      if (slice) out.push(...slice);
    }
    return out;
  }, [pages, page, adapter.keepAllPages]);

  const filteredRows = useMemo<ReadonlyArray<TInstRow>>(() => {
    const f = adapter.filterRows;
    if (!f) return allRows;
    return f(allRows, filtersRef.current);
    // `filters` is intentional: the memo reads the latest filter state via the
    // ref, but we still want to recompute when any filter actually changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allRows, adapter, filters]);

  const visibleRows = useMemo<ReadonlyArray<TInstRow>>(() => {
    if (!adapter.keepAllPages) {
      return filteredRows;
    }
    return filteredRows.slice(page * pageSize, page * pageSize + pageSize);
  }, [filteredRows, page, pageSize, adapter.keepAllPages]);

  // Push the visible slice through the row store for surgical updates.
  useEffect(() => {
    store.sync([...visibleRows]);
  }, [visibleRows, store]);

  const isCatalogEmpty = adapter.isCatalogEmpty;
  const showCatalogEmptyHint = useMemo(() => {
    if (loading) return false;
    if (allRows.length > 0) return false;
    if (!latestResponse) return false;
    if (isCatalogEmpty) return isCatalogEmpty(latestResponse);
    return totalItems === 0;
  }, [loading, allRows.length, latestResponse, isCatalogEmpty, totalItems]);

  const setPagePublic = useCallback(
    (next: number) => {
      setPage(next);
      if (selection) {
        void fetchInstanceRef.current(selection, next, query, {
          showLoading: false,
        });
      }
    },
    [selection, query],
  );

  const refresh = useCallback(() => {
    if (!selection) return;
    void fetchInstanceRef.current(selection, page, query, {
      showLoading: true,
    });
  }, [selection, page, query]);

  return {
    loading,
    lastUpdated,
    page,
    pageSize,
    totalPages,
    totalItems,
    visibleRows,
    rowsStore: store,
    rowOrder: snapshot.rowOrder,
    showCatalogEmptyHint,
    setPage: setPagePublic,
    refresh,
    latestResponse,
  };
}
