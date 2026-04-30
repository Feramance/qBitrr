import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type JSX,
} from "react";
import {
  getArrList,
  getRadarrMovies,
} from "../api/client";
import { StableTable } from "../components/StableTable";
import type { ColumnDef } from "@tanstack/react-table";
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
import { useRowSnapshot, useRowsStore } from "../hooks/useRowsStore";
import { useArrBrowseMode } from "../hooks/useArrBrowseMode";
import { IconImage } from "../components/IconImage";
import { ArrBrowseModeToggle } from "../components/arr/ArrBrowseModeToggle";
import { ArrModal } from "../components/arr/ArrModal";
import { ArrPosterImage } from "../components/arr/ArrPosterImage";
import { RadarrMovieDetailBody } from "../components/arr/RadarrMovieDetailBody";
import { radarrMovieThumbnailUrl } from "../utils/arrThumbnailUrl";
import RefreshIcon from "../icons/refresh-arrow.svg";
import {
  AGGREGATE_FETCH_CHUNK_SIZE,
  AGGREGATE_POLL_INTERVAL_MS,
  INSTANCE_VIEW_POLL_INTERVAL_MS,
  pagesFromAggregateTotal,
  summarizeAggregateMonitoredRows,
  AGG_FALLBACK_AGGREGATE_PAGES_MAX,
} from "../constants/arrAggregateFetch";

interface RadarrAggRow extends RadarrMovie {
  __instance: string;
  [key: string]: unknown;
}

type RadarrSortKey = "title" | "year" | "monitored" | "hasFile";
type RadarrAggSortKey = "__instance" | RadarrSortKey;

const RADARR_PAGE_SIZE = 50;
const RADARR_AGG_PAGE_SIZE = 50;

function categoryForInstanceLabel(
  instances: ArrInfo[],
  label: string
): string {
  const inst = instances.find(
    (i) => (i.name || i.category) === label || i.category === label
  );
  return inst?.category ?? instances[0]?.category ?? "";
}

interface RadarrAggregateViewProps {
  loading: boolean;
  rows: RadarrAggRow[];
  rowOrder: readonly string[];
  rowsStore: import("../utils/rowsStore").RowsStore<RadarrAggRow>;
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
  browseMode: "list" | "icon";
  instances: ArrInfo[];
  onMovieSelect: (movie: RadarrAggRow) => void;
}

const RadarrAggregateView = memo(function RadarrAggregateView({
  loading,
  rows,
  rowOrder,
  rowsStore,
  total,
  page,
  totalPages,
  onPageChange,
  onRefresh,
  lastUpdated,
  summary,
  instanceCount,
  isAggFiltered = false,
  browseMode,
  instances,
  onMovieSelect,
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
      ) : !loading &&
        total === 0 &&
        summary.total === 0 &&
        instanceCount > 0 ? (
        <div className="hint">
          <p>No movies found in the local catalog.</p>
          <p>
            qBitrr may still be importing from your Radarr instances into the SQLite
            database. Check logs or refresh in a moment.
          </p>
        </div>
      ) : total ? (
        browseMode === "list" ? (
          <StableTable
            rowsStore={rowsStore}
            rowOrder={rowOrder}
            columns={columns}
            getRowKey={(movie) => `${movie.__instance}-${movie.title}-${movie.year}`}
            onRowClick={onMovieSelect}
          />
        ) : (
          <div className="arr-icon-grid">
            {rows.map((row) => {
              const cat = categoryForInstanceLabel(instances, row.__instance);
              const id = row.id;
              const thumb =
                id != null && cat
                  ? radarrMovieThumbnailUrl(cat, id)
                  : "";
              return (
                <button
                  key={`${row.__instance}-${row.title}-${row.year}`}
                  type="button"
                  className="arr-movie-tile card"
                  onClick={() => onMovieSelect(row)}
                >
                  {thumb ? (
                    <ArrPosterImage
                      className="arr-movie-tile__poster"
                      src={thumb}
                      alt=""
                    />
                  ) : (
                    <div className="arr-movie-tile__poster arr-poster-fallback" aria-hidden />
                  )}
                  <div className="arr-movie-tile__meta">
                    {instanceCount > 1 && (
                      <div className="arr-movie-tile__instance">{row.__instance}</div>
                    )}
                    <div className="arr-movie-tile__title">{row.title}</div>
                    <div className="arr-movie-tile__sub">
                      {row.year != null ? String(row.year) : ""}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )
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
  lastUpdated: string | null;
  category: string;
  browseMode: "list" | "icon";
  onMovieSelect: (movie: RadarrMovie) => void;
  /** True when API reports zero movies and catalog may still be syncing. */
  showCatalogEmptyHint?: boolean;
  rowOrder: readonly string[];
  rowsStore: import("../utils/rowsStore").RowsStore<RadarrMovie>;
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
  onRefresh,
  lastUpdated,
  category,
  browseMode,
  onMovieSelect,
  showCatalogEmptyHint = false,
  rowOrder,
  rowsStore,
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
        <button className="btn ghost" type="button" onClick={onRefresh} disabled={loading}>
          <IconImage src={RefreshIcon} />
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="loading">
          <span className="spinner" /> Loading…
        </div>
      ) : allMovies.length ? (
        browseMode === "list" ? (
          <StableTable
            rowsStore={rowsStore}
            rowOrder={rowOrder}
            columns={columns}
            getRowKey={(movie) => `${movie.title}-${movie.year}`}
            onRowClick={onMovieSelect}
          />
        ) : (
          <div className="arr-icon-grid">
            {reasonFilteredMovies
              .slice(page * pageSize, page * pageSize + pageSize)
              .map((movie) => {
                const id = movie.id;
                const thumb =
                  id != null && category
                    ? radarrMovieThumbnailUrl(category, id)
                    : "";
                return (
                  <button
                    key={`${movie.title}-${movie.year}`}
                    type="button"
                    className="arr-movie-tile card"
                    onClick={() => onMovieSelect(movie)}
                  >
                    {thumb ? (
                      <ArrPosterImage
                        className="arr-movie-tile__poster"
                        src={thumb}
                        alt=""
                      />
                    ) : (
                      <div className="arr-movie-tile__poster arr-poster-fallback" aria-hidden />
                    )}
                    <div className="arr-movie-tile__meta">
                      <div className="arr-movie-tile__title">{movie.title}</div>
                      <div className="arr-movie-tile__sub">
                        {movie.year != null ? String(movie.year) : ""}
                      </div>
                    </div>
                  </button>
                );
              })}
          </div>
        )
      ) : showCatalogEmptyHint ? (
        <div className="hint">
          <p>No movies in the local catalog.</p>
          <p>
            qBitrr may still be syncing your Radarr library. Check logs or try again shortly.
          </p>
        </div>
      ) : (
        <div className="hint">No movies match the current filters.</div>
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

interface RadarrDetailModalProps {
  detail: {
    id: string;
    category: string;
    source: "instance" | "aggregate";
    seedMovie: RadarrMovie | RadarrAggRow;
  };
  instanceStore: import("../utils/rowsStore").RowsStore<RadarrMovie>;
  aggregateStore: import("../utils/rowsStore").RowsStore<RadarrAggRow>;
  onClose: () => void;
}

/**
 * Detail modal that lives outside the table render path.
 *
 * Subscribes by id (`useRowSnapshot`) so update-only polls bring fresh fields into the
 * open modal without closing it or re-rendering any sibling row.  Falls back to the seed
 * payload (the row that was clicked) if the store doesn't have a hit yet — covers the
 * brief gap between mount and the first sync, plus the case where the row was filtered
 * out / removed while the modal is open.
 */
const RadarrDetailModal = memo(function RadarrDetailModal({
  detail,
  instanceStore,
  aggregateStore,
  onClose,
}: RadarrDetailModalProps): JSX.Element {
  const instanceFresh = useRowSnapshot(
    instanceStore,
    detail.source === "instance" ? detail.id : null,
  );
  const aggregateFresh = useRowSnapshot(
    aggregateStore,
    detail.source === "aggregate" ? detail.id : null,
  );
  const liveMovie =
    (detail.source === "instance" ? instanceFresh : aggregateFresh) ??
    detail.seedMovie;

  return (
    <ArrModal
      title={String(liveMovie.title ?? "Movie")}
      onClose={onClose}
      maxWidth={520}
    >
      <RadarrMovieDetailBody
        movie={liveMovie}
        category={detail.category}
      />
    </ArrModal>
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
  globalSearchRef.current = globalSearch;
  const selectionRef = useRef(selection);
  selectionRef.current = selection;
  const backendReadyWarnedRef = useRef(false);
  const aggFetchGenRef = useRef(0);
  const aggActiveLoadsRef = useRef(0);

  // Smart data sync for instance movies
  const instanceMovieSync = useDataSync<RadarrMovie>({
    getKey: (movie) => `${movie.title}-${movie.year}`,
    hashFields: ['title', 'year', 'hasFile', 'monitored', 'reason'],
  });

  // Surgical row store: keeps `rowOrder` reference stable on update-only polls so the
  // browse table does not "reload" between ticks (see plan: WebUI surgical row updates).
  // The legacy `useDataSync` still drives the multi-page array cache; this hook owns the
  // currently-displayed page.
  const instanceMovieRowsStoreOpts = useMemo(
    () => ({
      getKey: (movie: RadarrMovie) => `${movie.title}-${movie.year}`,
      hashFields: ["title", "year", "hasFile", "monitored", "reason"] as const,
    }),
    [],
  );
  const instanceMovieRowsStore = useRowsStore<RadarrMovie>(
    instanceMovieRowsStoreOpts as never,
  );

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

  // Surgical row store for the aggregate browse view: same rationale as the per-instance
  // store above — keep `rowOrder` stable on update-only polls so the table does not
  // re-render every cell on every tick.
  const aggMovieRowsStoreOpts = useMemo(
    () => ({
      getKey: (movie: RadarrAggRow) =>
        `${movie.__instance}-${movie.title}-${movie.year}`,
      hashFields: [
        "__instance",
        "title",
        "year",
        "hasFile",
        "monitored",
        "reason",
      ] as const,
    }),
    [],
  );
  const aggMovieRowsStore = useRowsStore<RadarrAggRow>(
    aggMovieRowsStoreOpts as never,
  );
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

  const { mode: browseMode, setMode: setBrowseMode } = useArrBrowseMode("radarr");
  // Modal selection: track id + category + which store owns it so the modal can subscribe
  // by id (`useRowSnapshot`) and live-update when polling brings in fresh fields.  We keep
  // `seedMovie` for the initial render so the modal has something to show before the first
  // store hit (and as a fallback if the row gets removed mid-view).
  const [radarrDetail, setRadarrDetail] = useState<{
    id: string;
    category: string;
    source: "instance" | "aggregate";
    seedMovie: RadarrMovie | RadarrAggRow;
  } | null>(null);

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
      const sel = selectionRef.current;
      if (sel === "") {
        // If only 1 instance, select it directly; otherwise use aggregate
        setSelection(filtered.length === 1 ? filtered[0].category : "aggregate");
      } else if (
        sel !== "aggregate" &&
        !filtered.some((arr) => arr.category === sel)
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
  }, [push]);

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
      const preloadAll = options.preloadAll === true;
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
        const resolvedPage = response.page ?? page;
        const pageSize = response.page_size ?? RADARR_PAGE_SIZE;
        const totalItems = response.total ?? (response.movies ?? []).length;
        const totalPages = Math.max(1, Math.ceil((totalItems || 0) / pageSize));
        const movies = response.movies ?? [];
        const existingPages = keyChanged ? {} : instancePagesRef.current;

        if (keyChanged) {
          instanceMovieSync.reset();
        }

        // Smart diffing using hash-based change detection
        const syncResult = instanceMovieSync.syncData(movies);
        const moviesChanged = syncResult.hasChanges;

        if (keyChanged || moviesChanged) {
          setInstancePages((prev) => {
            const base = keyChanged ? {} : prev;
            const next = { ...base, [resolvedPage]: syncResult.data };
            instancePagesRef.current = next;
            return next;
          });
          setLastUpdated(new Date().toLocaleTimeString());
        }

        setInstanceData((prev) => {
          const prevCounts = prev?.counts ?? null;
          const nextCounts = response.counts ?? null;
          const countsOrMetaChanged =
            !prev ||
            keyChanged ||
            moviesChanged ||
            prev.category !== response.category ||
            prev.total !== response.total ||
            prev.page !== response.page ||
            prev.page_size !== response.page_size ||
            (prevCounts?.available ?? null) !== (nextCounts?.available ?? null) ||
            (prevCounts?.monitored ?? null) !== (nextCounts?.monitored ?? null);
          return countsOrMetaChanged ? response : prev;
        });

        setInstancePage((p) => (p === resolvedPage ? p : resolvedPage));
        setInstanceQuery((q) => (q === query ? q : query));
        setInstancePageSize((ps) => (ps === pageSize ? ps : pageSize));
        setInstanceTotalPages((tp) => (tp === totalPages ? tp : totalPages));

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
        if (showLoading) {
          setInstanceLoading(false);
        }
      }
    },
    [push, preloadRemainingPages]
  );

  const fetchInstanceRef = useRef(fetchInstance);
  useLayoutEffect(() => {
    fetchInstanceRef.current = fetchInstance;
  }, [fetchInstance]);

  const loadAggregate = useCallback(async (options?: { showLoading?: boolean }) => {
    if (!instances.length) {
      setAggRows([]);
      setAggSummary({ available: 0, monitored: 0, missing: 0, total: 0 });
      return;
    }
    const showLoading = options?.showLoading ?? true;
    const gen = ++aggFetchGenRef.current;
    aggActiveLoadsRef.current += 1;
    if (showLoading) {
      setAggLoading(true);
    }
    const chunk = AGGREGATE_FETCH_CHUNK_SIZE;
    try {
      const aggregated: RadarrAggRow[] = [];
      let progressFirstPaint = false;
      for (const inst of instances) {
        const label = inst.name || inst.category;
        let countedForInstance = false;
        let pagesPlanned: number | null = null;
        let pageIdx = 0;

        while (true) {
          const res = await getRadarrMovies(inst.category, pageIdx, chunk, "");
          if (gen !== aggFetchGenRef.current) {
            return;
          }
          const movies = res.movies ?? [];

          if (!countedForInstance) {
            countedForInstance = true;
            pagesPlanned = pagesFromAggregateTotal(res.total, res.page_size, chunk);
            if (
              showLoading &&
              typeof res.total === "number" &&
              res.total === 0
            ) {
              setAggLoading(false);
              progressFirstPaint = true;
            }
          }

          movies.forEach((movie) => {
            aggregated.push({ ...movie, __instance: label });
          });

          if (showLoading && !progressFirstPaint && aggregated.length > 0) {
            setAggLoading(false);
            progressFirstPaint = true;
          }

          pageIdx += 1;

          if (pagesPlanned !== null) {
            if (pageIdx >= pagesPlanned) break;
          } else {
            if (!movies.length || movies.length < chunk) break;
            if (pageIdx >= AGG_FALLBACK_AGGREGATE_PAGES_MAX) break;
          }
        }
      }

      const syncFinal = aggMovieSync.syncData(aggregated);
      const rowsChanged = syncFinal.hasChanges;

      if (rowsChanged) {
        setAggRows(syncFinal.data);
      }

      const newSummary = summarizeAggregateMonitoredRows(aggregated);

      let summaryChanged = false;
      setAggSummary((prev) => {
        if (
          prev.available === newSummary.available &&
          prev.monitored === newSummary.monitored &&
          prev.missing === newSummary.missing &&
          prev.total === newSummary.total
        ) {
          return prev;
        }
        summaryChanged = true;
        return newSummary;
      });

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
      if (gen !== aggFetchGenRef.current) {
        return;
      }
      setAggRows([]);
      setAggSummary({ available: 0, monitored: 0, missing: 0, total: 0 });
      push(
        error instanceof Error
          ? error.message
          : "Failed to load aggregated Radarr data",
        "error"
      );
    } finally {
      aggActiveLoadsRef.current -= 1;
      if (gen === aggFetchGenRef.current) {
        setAggLoading(false);
      }
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
    void fetchInstanceRef.current(selection, 0, query, {
      preloadAll: false,
      showLoading: true,
    });
    // Intentionally omit fetchInstance: identity changes would refetch and wipe pagination.
  }, [active, selection]);

  useEffect(() => {
    if (!active) return;
    if (selection !== "aggregate") return;
    void loadAggregate();
  }, [active, selection, loadAggregate]);

  useInterval(() => {
    if (document.visibilityState !== "visible") {
      return;
    }
    if (
      selection === "aggregate" &&
      liveArr &&
      aggActiveLoadsRef.current === 0
    ) {
      void loadAggregate({ showLoading: false });
    }
  }, selection === "aggregate" && liveArr ? AGGREGATE_POLL_INTERVAL_MS : null);

  useEffect(() => {
    if (!active) return;
    const handler = (term: string) => {
      if (selection === "aggregate") {
        setAggFilter(term);
        setAggPage(0);
      } else if (selection) {
        setInstancePage(0);
        void fetchInstanceRef.current(selection, 0, term, {
          preloadAll: false,
          showLoading: true,
        });
      }
    };
    register(handler);
    return () => {
      clearHandler(handler);
    };
  }, [active, selection, register, clearHandler]);

  useInterval(
    () => {
      if (document.visibilityState !== "visible") {
        return;
      }
      if (selection && selection !== "aggregate") {
        const activeFilter = globalSearchRef.current?.trim?.() || "";
        if (activeFilter) {
          return;
        }
        void fetchInstanceRef.current(selection, instancePage, instanceQuery, {
          preloadAll: false,
          showLoading: false,
        });
      }
    },
    active && selection && selection !== "aggregate" && liveArr
      ? INSTANCE_VIEW_POLL_INTERVAL_MS
      : null
  );

  // Removed: Don't reset page when filter changes - preserve scroll position

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
      const comparison = (typeof valueA === "number" && typeof valueB === "number")
        ? valueA - valueB
        : (typeof valueA === "string" && typeof valueB === "string")
          ? valueA.localeCompare(valueB)
          : String(valueA).localeCompare(String(valueB));
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

  // Filtered slice that the per-instance view is about to render.  Mirrors the same
  // filter logic used inside `RadarrInstanceView` so the row store stays in lockstep
  // with what the user sees and we don't waste work on filtered-out rows.
  const instanceVisiblePage = useMemo<RadarrMovie[]>(() => {
    let movies = allInstanceMovies;
    if (onlyMissing) {
      movies = movies.filter((m) => !m.hasFile);
    }
    if (reasonFilter !== "all") {
      if (reasonFilter === "Not being searched") {
        movies = movies.filter(
          (m) => m.reason === "Not being searched" || !m.reason,
        );
      } else {
        movies = movies.filter((m) => m.reason === reasonFilter);
      }
    }
    return movies.slice(
      instancePage * instancePageSize,
      instancePage * instancePageSize + instancePageSize,
    );
  }, [
    allInstanceMovies,
    onlyMissing,
    reasonFilter,
    instancePage,
    instancePageSize,
  ]);

  // Push the visible slice into the surgical row store on every change.  The store's diff
  // pipeline returns `update-only` when nothing but row fields changed — the table's
  // `rowOrder` reference stays stable and tanstack-table reuses the existing row model.
  useEffect(() => {
    instanceMovieRowsStore.store.sync(instanceVisiblePage);
  }, [instanceVisiblePage, instanceMovieRowsStore.store]);

  // Reset the per-instance row store whenever the user switches instance: avoids leaking
  // rows from the previous instance when the table re-renders before the first fetch.
  useEffect(() => {
    instanceMovieRowsStore.store.reset();
    // Intentionally only depends on `selection` — `instanceMovieRowsStore.store` is stable
    // for the lifetime of the component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);

  // Sync the aggregate visible page through its own row store (same rationale).
  useEffect(() => {
    aggMovieRowsStore.store.sync(aggPageRows);
  }, [aggPageRows, aggMovieRowsStore.store]);

  const handleInstanceRefresh = useCallback(() => {
    if (!selection || selection === "aggregate") return;
    void fetchInstanceRef.current(selection, instancePage, instanceQuery, {
      preloadAll: false,
      showLoading: true,
    });
  }, [selection, instancePage, instanceQuery]);

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
              <div className="field" style={{ flex: "0 0 auto" }}>
                <label>View</label>
                <ArrBrowseModeToggle
                  mode={browseMode}
                  onChange={setBrowseMode}
                  idPrefix="radarr"
                />
              </div>
            </div>

            {isAggregate ? (
              <RadarrAggregateView
                loading={aggLoading}
                rows={aggPageRows}
                rowOrder={aggMovieRowsStore.snapshot.rowOrder}
                rowsStore={aggMovieRowsStore.store}
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
                browseMode={browseMode}
                instances={instances}
                onMovieSelect={(m) => {
                  const id = `${m.__instance}-${m.title}-${m.year}`;
                  setRadarrDetail({
                    id,
                    category: categoryForInstanceLabel(instances, m.__instance),
                    source: "aggregate",
                    seedMovie: m,
                  });
                }}
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
                rowOrder={instanceMovieRowsStore.snapshot.rowOrder}
                rowsStore={instanceMovieRowsStore.store}
                onPageChange={(page) => {
                  setInstancePage(page);
                  void fetchInstanceRef.current(selection as string, page, instanceQuery, {
                    preloadAll: false,
                  });
                }}
                onRefresh={() => void handleInstanceRefresh()}
                lastUpdated={lastUpdated}
                category={selection as string}
                browseMode={browseMode}
                showCatalogEmptyHint={
                  !instanceLoading &&
                  instanceData != null &&
                  (instanceData.total ?? 0) === 0 &&
                  allInstanceMovies.length === 0
                }
                onMovieSelect={(m) => {
                  const id = `${m.title}-${m.year}`;
                  setRadarrDetail({
                    id,
                    category: selection as string,
                    source: "instance",
                    seedMovie: m,
                  });
                }}
              />
            )}
          </div>
        </div>
      </div>
      {radarrDetail ? (
        <RadarrDetailModal
          detail={radarrDetail}
          instanceStore={instanceMovieRowsStore.store}
          aggregateStore={aggMovieRowsStore.store}
          onClose={() => setRadarrDetail(null)}
        />
      ) : null}
    </section>
  );
}
