import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type JSX,
} from "react";
import {
  getArrList,
  getRadarrMovies,
  restartArr,
} from "../api/client";
import { StableTable } from "../components/StableTable";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
} from "@tanstack/react-table";
import type {
  ArrInfo,
  RadarrMovie,
  RadarrMoviesResponse,
} from "../api/types";
import { useToast } from "../context/ToastContext";
import { useSearch } from "../context/SearchContext";
import { useWebUI } from "../context/WebUIContext";
import { useInterval } from "../hooks/useInterval";
import { useDebounce } from "../hooks/useDebounce";
import { useDataSync } from "../hooks/useDataSync";
import { IconImage } from "../components/IconImage";
import RefreshIcon from "../icons/refresh-arrow.svg";
import RestartIcon from "../icons/refresh-arrow.svg";

interface RadarrAggRow extends RadarrMovie {
  __instance: string;
  [key: string]: unknown;
}

type RadarrSortKey = "title" | "year" | "monitored" | "hasFile";
type RadarrAggSortKey = "__instance" | RadarrSortKey;

const RADARR_PAGE_SIZE = 50;
const RADARR_AGG_PAGE_SIZE = 50;
const RADARR_AGG_FETCH_SIZE = 500;

interface RadarrAggregateViewProps {
  loading: boolean;
  rows: RadarrAggRow[];
  total: number;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  lastUpdated: string | null;
  sort: { key: RadarrAggSortKey; direction: "asc" | "desc" };
  onSort: (key: RadarrAggSortKey) => void;
  summary: { available: number; monitored: number; missing: number; total: number };
  instanceCount: number;
  isAggFiltered?: boolean;
}

const RadarrAggregateView = memo(function RadarrAggregateView({
  loading,
  rows,
  total,
  page,
  totalPages,
  onPageChange,
  onRefresh,
  lastUpdated,
  summary,
  instanceCount,
  isAggFiltered = false,
}: RadarrAggregateViewProps): JSX.Element {
  const columns = useMemo<ColumnDef<RadarrAggRow>[]>(
    () => [
      ...(instanceCount > 1 ? [{
        accessorKey: "__instance",
        header: "Instance",
        size: 150,
      }] : []),
      {
        accessorKey: "title",
        header: "Title",
        cell: (info) => info.getValue(),
      },
      {
        accessorKey: "year",
        header: "Year",
        size: 80,
      },
      {
        accessorKey: "monitored",
        header: "Monitored",
        cell: (info) => {
          const monitored = info.getValue() as boolean;
          return (
            <span className={`track-status ${monitored ? 'available' : 'missing'}`}>
              {monitored ? '✓' : '✗'}
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
            <span className={`track-status ${hasFile ? 'available' : 'missing'}`}>
              {hasFile ? '✓' : '✗'}
            </span>
          );
        },
        size: 100,
      },
      {
        accessorKey: "qualityProfileName",
        header: "Quality Profile",
        cell: (info) => {
          const profileName = info.getValue() as string | null | undefined;
          return profileName || "—";
        },
        size: 150,
      },
      {
        accessorKey: "reason",
        header: "Reason",
        cell: (info) => {
          const reason = info.getValue() as string | null;
          if (!reason) return <span className="table-badge table-badge-reason">Not being searched</span>;
          return <span className="table-badge table-badge-reason">{reason}</span>;
        },
        size: 120,
      },
    ],
    [instanceCount]
  );

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          Aggregated movies across all instances{" "}
          {lastUpdated ? `(updated ${lastUpdated})` : ""}
          <br />
          <strong>Available:</strong>{" "}
          {summary.available.toLocaleString(undefined, { maximumFractionDigits: 0 })} •{" "}
          <strong>Monitored:</strong>{" "}
          {summary.monitored.toLocaleString(undefined, { maximumFractionDigits: 0 })} •{" "}
          <strong>Missing:</strong>{" "}
          {summary.missing.toLocaleString(undefined, { maximumFractionDigits: 0 })} •{" "}
          <strong>Total:</strong>{" "}
          {summary.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          {isAggFiltered && total < summary.total && (
            <>
              {" "}• <strong>Filtered:</strong>{" "}
              {total.toLocaleString(undefined, { maximumFractionDigits: 0 })} of{" "}
              {summary.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </>
          )}
        </div>
        <button className="btn ghost" onClick={onRefresh} disabled={loading}>
          <IconImage src={RefreshIcon} />
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="loading">
          <span className="spinner" /> Loading Radarr library…
        </div>
      ) : total ? (
        <StableTable
          data={rows}
          columns={columns}
          getRowKey={(movie) => `${movie.__instance}-${movie.title}-${movie.year}`}
        />
      ) : (
        <div className="hint">No movies found.</div>
      )}

      {total > 0 && (
        <div className="pagination">
          <div>
            Page {page + 1} of {totalPages} ({total.toLocaleString()} items · page size{" "}
            {RADARR_AGG_PAGE_SIZE})
          </div>
          <div className="inline">
            <button
              className="btn"
              onClick={() => onPageChange(Math.max(0, page - 1))}
              disabled={page === 0 || loading}
            >
              Prev
            </button>
            <button
              className="btn"
              onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1 || loading}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
});

interface RadarrInstanceViewProps {
  loading: boolean;
  data: RadarrMoviesResponse | null;
  page: number;
  totalPages: number;
  pageSize: number;
  allMovies: RadarrMovie[];
  onlyMissing: boolean;
  reasonFilter: string;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  onRestart: () => void;
  lastUpdated: string | null;
}

const RadarrInstanceView = memo(function RadarrInstanceView({
  loading,
  data,
  page,
  totalPages,
  pageSize,
  allMovies,
  onlyMissing,
  reasonFilter,
  onPageChange,
  onRestart,
  lastUpdated,
}: RadarrInstanceViewProps): JSX.Element {
  const filteredMovies = useMemo(() => {
    let movies = allMovies;
    if (onlyMissing) {
      movies = movies.filter((m) => !m.hasFile);
    }
    return movies;
  }, [allMovies, onlyMissing]);

  const reasonFilteredMovies = useMemo(() => {
    if (reasonFilter === "all") return filteredMovies;
    if (reasonFilter === "Not being searched") {
      return filteredMovies.filter((m) => m.reason === "Not being searched" || !m.reason);
    }
    return filteredMovies.filter((m) => m.reason === reasonFilter);
  }, [filteredMovies, reasonFilter]);

  const totalMovies = useMemo(() => allMovies.length, [allMovies]);
  const isFiltered = reasonFilter !== "all" || onlyMissing;
  const filteredCount = reasonFilteredMovies.length;

  const columns = useMemo<ColumnDef<RadarrMovie>[]>(
    () => [
      {
        accessorKey: "title",
        header: "Title",
        cell: (info) => info.getValue(),
      },
      {
        accessorKey: "year",
        header: "Year",
        size: 80,
      },
      {
        accessorKey: "monitored",
        header: "Monitored",
        cell: (info) => {
          const monitored = info.getValue() as boolean;
          return (
            <span className={`track-status ${monitored ? 'available' : 'missing'}`}>
              {monitored ? '✓' : '✗'}
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
            <span className={`track-status ${hasFile ? 'available' : 'missing'}`}>
              {hasFile ? '✓' : '✗'}
            </span>
          );
        },
        size: 100,
      },
      {
        accessorKey: "qualityProfileName",
        header: "Quality Profile",
        cell: (info) => {
          const profileName = info.getValue() as string | null | undefined;
          return profileName || "—";
        },
        size: 150,
      },
      {
        accessorKey: "reason",
        header: "Reason",
        cell: (info) => {
          const reason = info.getValue() as string | null;
          if (!reason) return <span className="table-badge table-badge-reason">Not being searched</span>;
          return <span className="table-badge table-badge-reason">{reason}</span>;
        },
        size: 120,
      },
    ],
    []
  );

  const table = useReactTable({
    data: reasonFilteredMovies.slice(page * pageSize, page * pageSize + pageSize),
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          {data?.counts ? (
            <>
              <strong>Available:</strong>{" "}
              {(data.counts.available ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} •{" "}
              <strong>Monitored:</strong>{" "}
              {(data.counts.monitored ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} •{" "}
              <strong>Missing:</strong>{" "}
              {((data.counts.monitored ?? 0) - (data.counts.available ?? 0)).toLocaleString(undefined, { maximumFractionDigits: 0 })} •{" "}
              <strong>Total:</strong>{" "}
              {totalMovies.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              {isFiltered && filteredCount < totalMovies && (
                <>
                  {" "}• <strong>Filtered:</strong>{" "}
                  {filteredCount.toLocaleString(undefined, { maximumFractionDigits: 0 })} of{" "}
                  {totalMovies.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </>
              )}
            </>
          ) : (
            "Loading movie information..."
          )}
          {lastUpdated ? ` (updated ${lastUpdated})` : ""}
        </div>
        <button className="btn ghost" onClick={onRestart} disabled={loading}>
          <IconImage src={RestartIcon} />
          Restart
        </button>
      </div>

      {loading ? (
        <div className="loading">
          <span className="spinner" /> Loading…
        </div>
      ) : allMovies.length ? (
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
                const movie = row.original;
                const stableKey = `${movie.title}-${movie.year}`;
                return (
                  <tr key={stableKey}>
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} data-label={String(cell.column.columnDef.header)}>
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="hint">No movies found.</div>
      )}

      {reasonFilteredMovies.length > pageSize && (
        <div className="pagination">
          <div>
            Page {page + 1} of {totalPages} ({reasonFilteredMovies.length.toLocaleString()} items · page size{" "}
            {pageSize})
          </div>
          <div className="inline">
            <button
              className="btn"
              onClick={() => onPageChange(Math.max(0, page - 1))}
              disabled={page === 0 || loading}
            >
              Prev
            </button>
            <button
              className="btn"
              onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1 || loading}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
});

export function RadarrView({ active }: { active: boolean }): JSX.Element {
  const { push } = useToast();
  const {
    value: globalSearch,
    setValue: setGlobalSearch,
    register,
    clearHandler,
  } = useSearch();
  const { liveArr } = useWebUI();

  const [instances, setInstances] = useState<ArrInfo[]>([]);
  const [selection, setSelection] = useState<string | "aggregate">("");
  const [instanceData, setInstanceData] = useState<RadarrMoviesResponse | null>(null);
  const [instancePage, setInstancePage] = useState(0);
  const [instanceQuery, setInstanceQuery] = useState("");
  const [instanceLoading, setInstanceLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [instancePages, setInstancePages] = useState<Record<number, RadarrMovie[]>>({});
  const [instancePageSize, setInstancePageSize] = useState(RADARR_PAGE_SIZE);
  const [instanceTotalPages, setInstanceTotalPages] = useState(1);
  const instanceKeyRef = useRef<string>("");
  const instancePagesRef = useRef<Record<number, RadarrMovie[]>>({});
  const globalSearchRef = useRef(globalSearch);
  const backendReadyWarnedRef = useRef(false);

  // Smart data sync for instance movies
  const instanceMovieSync = useDataSync<RadarrMovie>({
    getKey: (movie) => `${movie.title}-${movie.year}`,
    hashFields: ['title', 'year', 'hasFile', 'monitored', 'reason'],
  });

  const [aggRows, setAggRows] = useState<RadarrAggRow[]>([]);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggPage, setAggPage] = useState(0);
  const [aggFilter, setAggFilter] = useState("");
  const [aggUpdated, setAggUpdated] = useState<string | null>(null);
  const debouncedAggFilter = useDebounce(aggFilter, 300);

  // Smart data sync for aggregate movies
  const aggMovieSync = useDataSync<RadarrAggRow>({
    getKey: (movie) => `${movie.__instance}-${movie.title}-${movie.year}`,
    hashFields: ['__instance', 'title', 'year', 'hasFile', 'monitored', 'reason'],
  });
  const [aggSort, setAggSort] = useState<{
    key: RadarrAggSortKey;
    direction: "asc" | "desc";
  }>({ key: "__instance", direction: "asc" });
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [reasonFilter, setReasonFilter] = useState<string>("all");
  const [aggSummary, setAggSummary] = useState<{
    available: number;
    monitored: number;
    missing: number;
    total: number;
  }>({ available: 0, monitored: 0, missing: 0, total: 0 });

  const loadInstances = useCallback(async () => {
    try {
      const data = await getArrList();
      if (data.ready === false && !backendReadyWarnedRef.current) {
        backendReadyWarnedRef.current = true;
        push("Radarr backend is still initialising. Check the logs if this persists.", "info");
      } else if (data.ready) {
        backendReadyWarnedRef.current = true;
      }
      const filtered = (data.arr || []).filter((arr) => arr.type === "radarr");
      setInstances(filtered);
      if (!filtered.length) {
        setSelection("aggregate");
        setInstanceData(null);
        setAggRows([]);
        setAggSummary({ available: 0, monitored: 0, missing: 0, total: 0 });
        return;
      }
      if (selection === "") {
        // If only 1 instance, select it directly; otherwise use aggregate
        setSelection(filtered.length === 1 ? filtered[0].category : "aggregate");
      } else if (
        selection !== "aggregate" &&
        !filtered.some((arr) => arr.category === selection)
      ) {
        setSelection(filtered[0].category);
      }
    } catch (error) {
      push(
        error instanceof Error
          ? error.message
          : "Unable to load Radarr instances",
        "error"
      );
    }
  }, [push, selection]);

  const preloadRemainingPages = useCallback(
    async (
      category: string,
      query: string,
      pageSize: number,
      pages: number[],
      key: string
    ) => {
      if (!pages.length) return;
      try {
        const results: { page: number; movies: RadarrMovie[] }[] = [];
        for (const pg of pages) {
          const res = await getRadarrMovies(category, pg, pageSize, query);
          const resolved = res.page ?? pg;
          results.push({ page: resolved, movies: res.movies ?? [] });
          if (instanceKeyRef.current !== key) {
            return;
          }
        }
        if (instanceKeyRef.current !== key) return;

        // Smart diffing: only update pages that actually changed
        setInstancePages((prev) => {
          const next = { ...prev };
          let hasChanges = false;
          for (const { page, movies } of results) {
            // Use hash-based comparison for each page
            const syncResult = instanceMovieSync.syncData(movies);
            if (syncResult.hasChanges) {
              next[page] = syncResult.data;
              hasChanges = true;
            }
          }
          instancePagesRef.current = next;
          return hasChanges ? next : prev;
        });
      } catch (error) {
        push(
          error instanceof Error
            ? error.message
            : `Failed to load additional pages for ${category}`,
          "error"
        );
      }
    },
    [push]
  );

  const fetchInstance = useCallback(
    async (
      category: string,
      page: number,
      query: string,
      options: { preloadAll?: boolean; showLoading?: boolean } = {}
    ) => {
      const preloadAll = options.preloadAll !== false;
      const showLoading = options.showLoading ?? true;
      if (showLoading) {
        setInstanceLoading(true);
      }
      try {
        const key = `${category}::${query}`;
        const keyChanged = instanceKeyRef.current !== key;
        if (keyChanged) {
          instanceKeyRef.current = key;
          setInstancePages(() => {
            instancePagesRef.current = {};
            return {};
          });
        }
        const response = await getRadarrMovies(
          category,
          page,
          RADARR_PAGE_SIZE,
          query
        );
        setInstanceData(response);
        const resolvedPage = response.page ?? page;
        setInstancePage(resolvedPage);
        setInstanceQuery(query);
        const pageSize = response.page_size ?? RADARR_PAGE_SIZE;
        const totalItems = response.total ?? (response.movies ?? []).length;
        const totalPages = Math.max(1, Math.ceil((totalItems || 0) / pageSize));
        setInstancePageSize(pageSize);
        setInstanceTotalPages(totalPages);
        const movies = response.movies ?? [];
        const existingPages = keyChanged ? {} : instancePagesRef.current;

        // Smart diffing using hash-based change detection
        const syncResult = instanceMovieSync.syncData(movies);
        const moviesChanged = syncResult.hasChanges;

        if (keyChanged) {
          // Reset sync state on key change
          instanceMovieSync.reset();
        }

        if (keyChanged || moviesChanged) {
          setInstancePages((prev) => {
            const base = keyChanged ? {} : prev;
            const next = { ...base, [resolvedPage]: syncResult.data };
            instancePagesRef.current = next;
            return next;
          });
          setLastUpdated(new Date().toLocaleTimeString());
        }

        if (preloadAll) {
          const pagesToFetch: number[] = [];
          for (let i = 0; i < totalPages; i += 1) {
            if (i === resolvedPage) continue;
            if (!existingPages[i]) {
              pagesToFetch.push(i);
            }
          }
          void preloadRemainingPages(
            category,
            query,
            pageSize,
            pagesToFetch,
            key
          );
        }
      } catch (error) {
        push(
          error instanceof Error
            ? error.message
            : `Failed to load ${category} movies`,
          "error"
        );
      } finally {
        setInstanceLoading(false);
      }
    },
    [push, preloadRemainingPages]
  );

  const loadAggregate = useCallback(async (options?: { showLoading?: boolean }) => {
    if (!instances.length) {
      setAggRows([]);
      setAggSummary({ available: 0, monitored: 0, missing: 0, total: 0 });
      return;
    }
    const showLoading = options?.showLoading ?? true;
    if (showLoading) {
      setAggLoading(true);
    }
    try {
      const aggregated: RadarrAggRow[] = [];
      let totalAvailable = 0;
      let totalMonitored = 0;
      for (const inst of instances) {
        let page = 0;
        let counted = false;
        const label = inst.name || inst.category;
        while (page < 100) {
          const res = await getRadarrMovies(
            inst.category,
            page,
            RADARR_AGG_FETCH_SIZE,
            ""
          );
          if (!counted) {
            const counts = res.counts;
            if (counts) {
              totalAvailable += counts.available ?? 0;
              totalMonitored += counts.monitored ?? 0;
            }
            counted = true;
          }
          const movies = res.movies ?? [];
          movies.forEach((movie) => {
            aggregated.push({ ...movie, __instance: label });
          });
          if (!movies.length || movies.length < RADARR_AGG_FETCH_SIZE) break;
          page += 1;
        }
      }

      // Smart diffing using hash-based change detection
      const syncResult = aggMovieSync.syncData(aggregated);
      const rowsChanged = syncResult.hasChanges;

      if (rowsChanged) {
        setAggRows(syncResult.data);
      }

      const newSummary = {
        available: totalAvailable,
        monitored: totalMonitored,
        missing: aggregated.length - totalAvailable,
        total: aggregated.length,
      };

      const summaryChanged = (
        aggSummary.available !== newSummary.available ||
        aggSummary.monitored !== newSummary.monitored ||
        aggSummary.missing !== newSummary.missing ||
        aggSummary.total !== newSummary.total
      );

      if (summaryChanged) {
        setAggSummary(newSummary);
      }

      // Only reset page if filter changed, not on refresh
      if (aggFilter !== globalSearch) {
        setAggPage(0);
        setAggFilter(globalSearch);
      }

      // Only update timestamp if data actually changed
      if (rowsChanged || summaryChanged) {
        setAggUpdated(new Date().toLocaleTimeString());
      }
    } catch (error) {
      setAggRows([]);
      setAggSummary({ available: 0, monitored: 0, missing: 0, total: 0 });
      push(
        error instanceof Error
          ? error.message
          : "Failed to load aggregated Radarr data",
        "error"
      );
    } finally {
      setAggLoading(false);
    }
  }, [instances, globalSearch, push, aggFilter]);

  // LiveArr is now loaded via WebUIContext, no need to load config here

  useEffect(() => {
    if (!active) return;
    void loadInstances();
  }, [active, loadInstances]);

  useEffect(() => {
    if (!active) return;
    if (!selection || selection === "aggregate") return;
    instancePagesRef.current = {};
    setInstancePages({});
    setInstanceTotalPages(1);
    setInstancePage(0);
    const query = globalSearchRef.current;
    void fetchInstance(selection, 0, query, {
      preloadAll: true,
      showLoading: true,
    });
  }, [active, selection, fetchInstance]); // Removed onlyMissing to prevent refresh

  useEffect(() => {
    if (!active) return;
    if (selection !== "aggregate") return;
    void loadAggregate();
  }, [active, selection, loadAggregate]);

  useInterval(() => {
    if (selection === "aggregate" && liveArr) {
      void loadAggregate({ showLoading: false });
    }
  }, selection === "aggregate" && liveArr ? 1000 : null);

  useEffect(() => {
    if (!active) return;
    const handler = (term: string) => {
      if (selection === "aggregate") {
        setAggFilter(term);
        setAggPage(0);
      } else if (selection) {
        setInstancePage(0);
        void fetchInstance(selection, 0, term, {
          preloadAll: true,
          showLoading: true,
        });
      }
    };
    register(handler);
    return () => {
      clearHandler(handler);
    };
  }, [active, selection, register, clearHandler, fetchInstance]);

  useInterval(
    () => {
      if (selection && selection !== "aggregate") {
        const activeFilter = globalSearchRef.current?.trim?.() || "";
        if (activeFilter) {
          return;
        }
        void fetchInstance(selection, instancePage, instanceQuery, {
          preloadAll: false,
          showLoading: false,
        });
      }
    },
    active && selection && selection !== "aggregate" && liveArr ? 1000 : null
  );

  // Removed: Don't reset page when filter changes - preserve scroll position

  useEffect(() => {
    globalSearchRef.current = globalSearch;
  }, [globalSearch]);

  useEffect(() => {
    if (selection === "aggregate") {
      setAggFilter(globalSearch);
    }
  }, [selection, globalSearch]);

  const filteredAggRows = useMemo(() => {
    // Combine all filters into a single pass for better performance
    const q = debouncedAggFilter ? debouncedAggFilter.toLowerCase() : "";
    const hasSearchFilter = Boolean(q);
    const hasReasonFilter = reasonFilter !== "all";

    return aggRows.filter((row) => {
      // Search filter
      if (hasSearchFilter) {
        const title = (row.title ?? "").toString().toLowerCase();
        const instance = (row.__instance ?? "").toLowerCase();
        if (!title.includes(q) && !instance.includes(q)) {
          return false;
        }
      }

      // Missing filter
      if (onlyMissing && row.hasFile) {
        return false;
      }

      // Reason filter
      if (hasReasonFilter) {
        if (reasonFilter === "Not being searched") {
          if (row.reason !== "Not being searched" && row.reason) {
            return false;
          }
        } else if (row.reason !== reasonFilter) {
          return false;
        }
      }

      return true;
    });
  }, [aggRows, debouncedAggFilter, onlyMissing, reasonFilter]);

  const isAggFiltered = Boolean(debouncedAggFilter) || reasonFilter !== "all";

  const sortedAggRows = useMemo(() => {
    const list = [...filteredAggRows];
    const getValue = (row: RadarrAggRow, key: RadarrAggSortKey) => {
      switch (key) {
        case "__instance":
          return (row.__instance || "").toLowerCase();
        case "title":
          return (row.title || "").toLowerCase();
        case "year":
          return row.year ?? 0;
        case "monitored":
          return row.monitored ? 1 : 0;
        case "hasFile":
          return row.hasFile ? 1 : 0;
        default:
          return "";
      }
    };
    list.sort((a, b) => {
      const valueA = getValue(a, aggSort.key);
      const valueB = getValue(b, aggSort.key);
      let comparison = 0;
      if (typeof valueA === "number" && typeof valueB === "number") {
        comparison = valueA - valueB;
      } else if (typeof valueA === "string" && typeof valueB === "string") {
        comparison = valueA.localeCompare(valueB);
      } else {
        comparison = String(valueA).localeCompare(String(valueB));
      }
      return aggSort.direction === "asc" ? comparison : -comparison;
    });
    return list;
  }, [filteredAggRows, aggSort]);

  const aggPages = Math.max(
    1,
    Math.ceil(sortedAggRows.length / RADARR_AGG_PAGE_SIZE)
  );
  const aggPageRows = useMemo(
    () => sortedAggRows.slice(
      aggPage * RADARR_AGG_PAGE_SIZE,
      aggPage * RADARR_AGG_PAGE_SIZE + RADARR_AGG_PAGE_SIZE
    ),
    [sortedAggRows, aggPage]
  );

  const allInstanceMovies = useMemo(() => {
    const pages = Object.keys(instancePages)
      .map(Number)
      .sort((a, b) => a - b);
    const rows: RadarrMovie[] = [];
    pages.forEach((pg) => {
      if (instancePages[pg]) {
        rows.push(...instancePages[pg]);
      }
    });
    return rows;
  }, [instancePages]);

  const handleRestart = useCallback(async () => {
    if (!selection || selection === "aggregate") return;
    try {
      await restartArr(selection);
      push(`Restarted ${selection}`, "success");
    } catch (error) {
      push(
        error instanceof Error ? error.message : `Failed to restart ${selection}`,
        "error"
      );
    }
  }, [selection, push]);

  const handleAggRefresh = useCallback(() => {
    void loadAggregate({ showLoading: true });
  }, [loadAggregate]);

  const handleAggSort = useCallback((key: RadarrAggSortKey) => {
    setAggSort((prev) =>
      prev.key === key
        ? {
            key,
            direction: prev.direction === "asc" ? "desc" : "asc",
          }
        : { key, direction: "asc" }
    );
  }, []);

  const handleInstanceRefresh = useCallback(() => {
    if (selection && selection !== "aggregate") {
      void fetchInstance(selection, instancePage, instanceQuery, {
        preloadAll: false,
        showLoading: true,
      });
    }
  }, [selection, instancePage, instanceQuery, fetchInstance]);

  const handleInstanceSelection = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      const next = (event.target.value || "aggregate") as string | "aggregate";
      setSelection(next);
      if (next !== "aggregate") {
        setGlobalSearch("");
      }
    },
    [setSelection, setGlobalSearch]
  );

  const isAggregate = selection === "aggregate";

  return (
    <section className="card">
      <div className="card-header">Radarr</div>
      <div className="card-body">
        <div className="split">
          <aside className="pane sidebar">
            {instances.length > 1 && (
              <button
                className={`btn ${isAggregate ? "active" : ""}`}
                onClick={() => setSelection("aggregate")}
              >
                All Radarr
              </button>
            )}
            {instances.map((inst) => (
              <button
                key={inst.category}
                className={`btn ghost ${
                  selection === inst.category ? "active" : ""
                }`}
                onClick={() => {
                  setSelection(inst.category);
                  setGlobalSearch("");
                }}
              >
                {inst.name || inst.category}
              </button>
            ))}
          </aside>
          <div className="pane">
            <div className="field mobile-instance-select">
              <label>Instance</label>
              <select
                value={selection || "aggregate"}
                onChange={handleInstanceSelection}
                disabled={!instances.length}
              >
                {instances.length > 1 && <option value="aggregate">All Radarr</option>}
                {instances.map((inst) => (
                  <option key={inst.category} value={inst.category}>
                    {inst.name || inst.category}
                  </option>
                ))}
              </select>
            </div>
            <div className="row" style={{ alignItems: "flex-end", gap: "12px", flexWrap: "wrap" }}>
              <div className="col field" style={{ flex: "1 1 200px" }}>
                <label>Search</label>
                <input
                  placeholder="Filter movies"
                  value={globalSearch}
                  onChange={(event) => setGlobalSearch(event.target.value)}
                />
              </div>
              <div className="field" style={{ flex: "0 0 auto", minWidth: "140px" }}>
                <label>Status</label>
                <select
                  onChange={(event) => {
                    const value = event.target.value;
                    setOnlyMissing(value === "missing");
                  }}
                  value={onlyMissing ? "missing" : "all"}
                >
                  <option value="all">All Movies</option>
                  <option value="missing">Missing Only</option>
                </select>
              </div>
              <div className="field" style={{ flex: "0 0 auto", minWidth: "140px" }}>
                <label>Search Reason</label>
                <select
                  onChange={(event) => setReasonFilter(event.target.value)}
                  value={reasonFilter}
                >
                  <option value="all">All Reasons</option>
                  <option value="Not being searched">Not Being Searched</option>
                  <option value="Missing">Missing</option>
                  <option value="Quality">Quality</option>
                  <option value="CustomFormat">Custom Format</option>
                  <option value="Upgrade">Upgrade</option>
                </select>
              </div>
            </div>

            {isAggregate ? (
              <RadarrAggregateView
                loading={aggLoading}
                rows={aggPageRows}
                total={sortedAggRows.length}
                page={aggPage}
                totalPages={aggPages}
                onPageChange={setAggPage}
                onRefresh={handleAggRefresh}
                lastUpdated={aggUpdated}
                sort={aggSort}
                onSort={handleAggSort}
                summary={aggSummary}
                instanceCount={instances.length}
                isAggFiltered={isAggFiltered}
              />
            ) : (
              <RadarrInstanceView
                loading={instanceLoading}
                data={instanceData}
                page={instancePage}
                totalPages={instanceTotalPages}
                pageSize={instancePageSize}
                allMovies={allInstanceMovies}
                onlyMissing={onlyMissing}
                reasonFilter={reasonFilter}
                onPageChange={(page) => {
                  setInstancePage(page);
                  void fetchInstance(selection as string, page, instanceQuery, {
                    preloadAll: true,
                  });
                }}
                onRefresh={handleInstanceRefresh}
                onRestart={() => void handleRestart()}
                lastUpdated={lastUpdated}
              />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
