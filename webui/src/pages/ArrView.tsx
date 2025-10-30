import {
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
  getSonarrSeries,
  restartArr,
} from "../api/client";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  getExpandedRowModel,
  flexRender,
  type ColumnDef,
} from "@tanstack/react-table";
import type {
  ArrInfo,
  RadarrMovie,
  RadarrMoviesResponse,
  SonarrEpisode,
  SonarrSeriesEntry,
  SonarrSeriesResponse,
  SonarrSeason,
} from "../api/types";
import { useToast } from "../context/ToastContext";
import { useSearch } from "../context/SearchContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
import RefreshIcon from "../icons/refresh-arrow.svg";
import RestartIcon from "../icons/refresh-arrow.svg";
import FilterIcon from "../icons/alert.svg";
import LiveIcon from "../icons/live-streaming.svg";

interface ArrViewProps {
  type: "radarr" | "sonarr";
  active: boolean;
}

interface RadarrAggRow extends RadarrMovie {
  __instance: string;
}

interface SonarrAggRow {
  __instance: string;
  series: string;
  season: number | string;
  episode: number | string;
  title: string;
  monitored: boolean;
  hasFile: boolean;
  airDate: string;
}

type RadarrSortKey = "title" | "year" | "monitored" | "hasFile";
type RadarrAggSortKey = "__instance" | RadarrSortKey;
type SonarrAggSortKey =
  | "__instance"
  | "series"
  | "season"
  | "episode"
  | "title"
  | "monitored"
  | "hasFile"
  | "airDate";

const RADARR_PAGE_SIZE = 50;
const RADARR_AGG_PAGE_SIZE = 50;
const RADARR_AGG_FETCH_SIZE = 500;
const SONARR_PAGE_SIZE = 25;
const SONARR_AGG_PAGE_SIZE = 50;
const SONARR_AGG_FETCH_SIZE = 200;

function filterSeriesEntriesForMissing(seriesEntries: SonarrSeriesEntry[], onlyMissing: boolean): SonarrSeriesEntry[] {
  if (!onlyMissing) return seriesEntries;
  const result: SonarrSeriesEntry[] = [];
  for (const entry of seriesEntries) {
    const seasons = entry.seasons ?? {};
    const filteredSeasons: Record<string, SonarrSeason> = {};
    for (const [seasonNumber, season] of Object.entries(seasons)) {
      const episodes = (season.episodes ?? []).filter((episode) => !episode.hasFile);
      if (!episodes.length) continue;
      filteredSeasons[seasonNumber] = { ...season, episodes };
    }
    if (Object.keys(filteredSeasons).length === 0) continue;
    result.push({
      ...entry,
      seasons: filteredSeasons,
    });
  }
  return result;
}

function createFilteredSignature(seriesEntries: SonarrSeriesEntry[], onlyMissing: boolean): string {
  return JSON.stringify(filterSeriesEntriesForMissing(seriesEntries, onlyMissing));
}


export function ArrView({ type, active }: ArrViewProps): JSX.Element {
  if (type === "radarr") {
    return <RadarrView active={active} />;
  }
  return <SonarrView active={active} />;
}

function RadarrView({ active }: { active: boolean }): JSX.Element {
  const { push } = useToast();
  const {
    value: globalSearch,
    setValue: setGlobalSearch,
    register,
    clearHandler,
  } = useSearch();

  const [instances, setInstances] = useState<ArrInfo[]>([]);
  const [selection, setSelection] = useState<string | "aggregate">("aggregate");
  const [instanceData, setInstanceData] = useState<RadarrMoviesResponse | null>(
    null
  );
  const [instancePage, setInstancePage] = useState(0);
  const [instanceQuery, setInstanceQuery] = useState("");
  const [instanceLoading, setInstanceLoading] = useState(false);
  const [live, setLive] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [instancePages, setInstancePages] = useState<Record<number, RadarrMovie[]>>({});
  const [instancePageSize, setInstancePageSize] = useState(RADARR_PAGE_SIZE);
  const [instanceTotalPages, setInstanceTotalPages] = useState(1);
  const instanceKeyRef = useRef<string>("");
  const instancePagesRef = useRef<Record<number, RadarrMovie[]>>({});
  const globalSearchRef = useRef(globalSearch);
  const backendReadyWarnedRef = useRef(false);

  const [aggRows, setAggRows] = useState<RadarrAggRow[]>([]);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggPage, setAggPage] = useState(0);
  const [aggFilter, setAggFilter] = useState("");
  const [aggUpdated, setAggUpdated] = useState<string | null>(null);
   const [aggSort, setAggSort] = useState<{
     key: RadarrAggSortKey;
     direction: "asc" | "desc";
    }>({ key: "__instance", direction: "asc" });
    const [onlyMissing, setOnlyMissing] = useState(false);
    const [liveAgg, setLiveAgg] = useState(true);
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
        setSelection("aggregate");
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
        setInstancePages((prev) => {
          const next = { ...prev };
          for (const { page, movies } of results) {
            next[page] = movies;
          }
          instancePagesRef.current = next;
          return next;
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
        setLastUpdated(new Date().toLocaleTimeString());
        const pageSize = response.page_size ?? RADARR_PAGE_SIZE;
        const totalItems = response.total ?? (response.movies ?? []).length;
        const totalPages = Math.max(1, Math.ceil((totalItems || 0) / pageSize));
        setInstancePageSize(pageSize);
        setInstanceTotalPages(totalPages);
        const movies = response.movies ?? [];
        const existingPages = keyChanged ? {} : instancePagesRef.current;
        setInstancePages((prev) => {
          const base = keyChanged ? {} : prev;
          const next = { ...base, [resolvedPage]: movies };
          instancePagesRef.current = next;
          return next;
        });
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

  const loadAggregate = useCallback(async () => {
    if (!instances.length) {
      setAggRows([]);
      setAggSummary({ available: 0, monitored: 0, missing: 0, total: 0 });
      return;
    }
    setAggLoading(true);
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
      setAggRows(aggregated);
      setAggSummary({
        available: totalAvailable,
        monitored: totalMonitored,
        missing: aggregated.length - totalAvailable,
        total: aggregated.length,
      });
      setAggPage(0);
      setAggFilter(globalSearch);
      setAggUpdated(new Date().toLocaleTimeString());
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
   }, [instances, globalSearch, push]);

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
  }, [active, selection, fetchInstance, onlyMissing]);

  useEffect(() => {
    if (!active) return;
    if (selection !== "aggregate") return;
    void loadAggregate();
   }, [active, selection, loadAggregate]);

   useInterval(() => {
     if (selection === "aggregate" && liveAgg) {
       void loadAggregate();
     }
   }, selection === "aggregate" && liveAgg ? 10000 : null);

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
    active && selection && selection !== "aggregate" && live ? 1000 : null
  );

  useEffect(() => {
    setAggPage(0);
    setInstancePage(0);
  }, [onlyMissing]);

  useEffect(() => {
    setAggPage(0);
    setInstancePage(0);
  }, [onlyMissing]);

  useEffect(() => {
    globalSearchRef.current = globalSearch;
  }, [globalSearch]);

  useEffect(() => {
    if (selection === "aggregate") {
      setAggFilter(globalSearch);
    }
  }, [selection, globalSearch]);

  const filteredAggRows = useMemo(() => {
    let rows = aggRows;
    if (aggFilter) {
      const q = aggFilter.toLowerCase();
      rows = rows.filter((row) => {
        const title = (row.title ?? "").toString().toLowerCase();
        const instance = (row.__instance ?? "").toLowerCase();
        return title.includes(q) || instance.includes(q);
      });
    }
    if (onlyMissing) {
      rows = rows.filter((row) => !row.hasFile);
    }
    return rows;
  }, [aggRows, aggFilter, onlyMissing]);

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
  const aggPageRows = sortedAggRows.slice(
    aggPage * RADARR_AGG_PAGE_SIZE,
    aggPage * RADARR_AGG_PAGE_SIZE + RADARR_AGG_PAGE_SIZE
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
            <button
              className={`btn ${isAggregate ? "active" : ""}`}
              onClick={() => setSelection("aggregate")}
            >
              All Radarr
            </button>
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
                <option value="aggregate">All Radarr</option>
                {instances.map((inst) => (
                  <option key={inst.category} value={inst.category}>
                    {inst.name || inst.category}
                  </option>
                ))}
              </select>
            </div>
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div className="col field">
                <label>Search</label>
                <input
                  placeholder="Filter movies"
                  value={globalSearch}
                  onChange={(event) => setGlobalSearch(event.target.value)}
                />
              </div>
              <label className="hint inline" style={{ marginBottom: 8 }}>
                <input
                  type="checkbox"
                  checked={onlyMissing}
                  onChange={(event) => setOnlyMissing(event.target.checked)}
                />
                <IconImage src={FilterIcon} />
                <span>Only Missing</span>
              </label>
              {isAggregate && (
                <label className="hint inline" style={{ marginBottom: 8 }}>
                  <input
                    type="checkbox"
                    checked={liveAgg}
                    onChange={(event) => setLiveAgg(event.target.checked)}
                  />
                  <IconImage src={LiveIcon} />
                  <span>Live</span>
                </label>
              )}
              {!isAggregate && (
                <label className="hint inline" style={{ marginBottom: 8 }}>
                  <input
                    type="checkbox"
                    checked={live}
                    onChange={(event) => setLive(event.target.checked)}
                  />
                  <IconImage src={LiveIcon} />
                  <span>Live</span>
                </label>
              )}
            </div>

            {isAggregate ? (
              <RadarrAggregateView
                loading={aggLoading}
                rows={aggPageRows}
                total={sortedAggRows.length}
                page={aggPage}
                totalPages={aggPages}
                onPageChange={setAggPage}
                onRefresh={() => void loadAggregate()}
                lastUpdated={aggUpdated}
                sort={aggSort}
                onSort={(key) =>
                  setAggSort((prev) =>
                    prev.key === key
                      ? {
                          key,
                          direction:
                            prev.direction === "asc" ? "desc" : "asc",
                        }
                      : { key, direction: "asc" }
                  )
                }
                summary={aggSummary}
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
                onPageChange={(page) => {
                  setInstancePage(page);
                  void fetchInstance(selection as string, page, instanceQuery, {
                    preloadAll: true,
                  });
                }}
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
}

function RadarrAggregateView({
  loading,
  rows,
  total,
  page,
  totalPages,
  onPageChange,
  onRefresh,
  lastUpdated,
  sort,
  onSort,
  summary,
}: RadarrAggregateViewProps): JSX.Element {
  const columns = useMemo<ColumnDef<RadarrAggRow>[]>(
    () => [
      {
        accessorKey: "__instance",
        header: "Instance",
      },
      {
        accessorKey: "title",
        header: "Title",
      },
      {
        accessorKey: "year",
        header: "Year",
      },
      {
        accessorKey: "monitored",
        header: "Monitored",
        cell: ({ getValue }) => (
          <span className="table-badge">{getValue() ? "Yes" : "No"}</span>
        ),
      },
      {
        accessorKey: "hasFile",
        header: "Has File",
        cell: ({ getValue }) => (
          <span className="table-badge">{getValue() ? "Yes" : "No"}</span>
        ),
      },
    ],
    []
  );

  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    state: {
      sorting: [{ id: sort.key, desc: sort.direction === "desc" }],
      pagination: {
        pageIndex: page,
        pageSize: 50,
      },
    },
    onSortingChange: (updater) => {
      const newSorting = typeof updater === "function" ? updater(table.getState().sorting) : updater;
      if (newSorting.length > 0) {
        const { id } = newSorting[0];
        onSort(id as RadarrAggSortKey);
      }
    },
    manualSorting: true,
    manualPagination: true,
    pageCount: totalPages,
  });

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          Aggregated movies across all instances{" "}
          {lastUpdated ? `(updated ${lastUpdated})` : ""}
          <br />
           <strong>Available:</strong>{" "}
           {summary.available.toLocaleString(undefined, {
             maximumFractionDigits: 0,
           })}{" "}
           • <strong>Monitored:</strong>{" "}
           {summary.monitored.toLocaleString(undefined, {
             maximumFractionDigits: 0,
           })}{" "}
           • <strong>Missing:</strong>{" "}
           {summary.missing.toLocaleString(undefined, {
             maximumFractionDigits: 0,
           })}
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
      ) : (
        <>
           <div className="table-wrapper">
             <table className="responsive-table">
                <thead>
                  <tr>
                    {table.getFlatHeaders().map((header) => (
                      <th
                        key={header.id}
                        className={header.column.getCanSort() ? "sortable" : ""}
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {header.isPlaceholder
                          ? null
                          : flexRender(
                              header.column.columnDef.header,
                              header.getContext()
                            )}
                        {header.column.getCanSort() && (
                          <span className="sort-arrow">
                            {{
                              asc: "▲",
                              desc: "▼",
                            }[header.column.getIsSorted() as string] ?? null}
                          </span>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
               <tbody>
                 {table.getRowModel().rows.map((row) => (
                   <tr key={row.id}>
                     {row.getVisibleCells().map((cell) => (
                       <td key={cell.id} data-label={cell.column.columnDef.header as string}>
                         {flexRender(cell.column.columnDef.cell, cell.getContext())}
                       </td>
                     ))}
                   </tr>
                 ))}
               </tbody>
             </table>
           </div>
           <div className="pagination">
             <div>
               Page {page + 1} of {totalPages} ({total} items)
             </div>
             <div className="inline">
               <button
                 className="btn"
                 onClick={() => onPageChange(Math.max(0, page - 1))}
                 disabled={page === 0}
               >
                 Prev
               </button>
               <button
                 className="btn"
                 onClick={() =>
                   onPageChange(Math.min(totalPages - 1, page + 1))
                 }
                 disabled={page >= totalPages - 1}
               >
                 Next
               </button>
             </div>
           </div>
         </>
      )}
    </div>
  );
}

interface RadarrInstanceViewProps {
  loading: boolean;
  data: RadarrMoviesResponse | null;
  page: number;
  totalPages: number;
  pageSize: number;
  allMovies: RadarrMovie[];
  onlyMissing: boolean;
  onPageChange: (page: number) => void;
  onRestart: () => void;
  lastUpdated: string | null;
}

function RadarrInstanceView({
  loading,
  data,
  page,
  totalPages,
  pageSize,
  allMovies,
  onlyMissing,
  onPageChange,
  onRestart,
  lastUpdated,
}: RadarrInstanceViewProps): JSX.Element {
  const counts = data?.counts;
  const refreshLabel = lastUpdated ? `Last updated ${lastUpdated}` : null;
  const [sort, setSort] = useState<{ key: RadarrSortKey; direction: "asc" | "desc" }>({ key: "title", direction: "asc" });

  const sourceMovies = useMemo(
    () => (onlyMissing ? allMovies.filter((movie) => !movie.hasFile) : allMovies),
    [allMovies, onlyMissing]
  );

  const totalItems = onlyMissing
    ? sourceMovies.length
    : data?.total ?? allMovies.length;

  const effectiveTotalPages = onlyMissing
    ? Math.max(1, Math.ceil(Math.max(sourceMovies.length, 1) / pageSize))
    : totalPages;

  const safePage = Math.min(page, Math.max(0, effectiveTotalPages - 1));

  useEffect(() => {
    if (safePage !== page) {
      onPageChange(safePage);
    }
  }, [safePage, page, onPageChange]);

  const sortedMovies = useMemo(() => {
    const list = [...sourceMovies];
    const getValue = (movie: RadarrMovie, key: RadarrSortKey) => {
      switch (key) {
        case "title":
          return (movie.title || "").toLowerCase();
        case "year":
          return movie.year ?? 0;
        case "monitored":
          return movie.monitored ? 1 : 0;
        case "hasFile":
          return movie.hasFile ? 1 : 0;
        default:
          return "";
      }
    };
    list.sort((a, b) => {
      const valueA = getValue(a, sort.key);
      const valueB = getValue(b, sort.key);
      let comparison = 0;
      if (typeof valueA === "number" && typeof valueB === "number") {
        comparison = valueA - valueB;
      } else if (typeof valueA === "string" && typeof valueB === "string") {
        comparison = valueA.localeCompare(valueB);
      } else {
        comparison = String(valueA).localeCompare(String(valueB));
      }
      return sort.direction === "asc" ? comparison : -comparison;
    });
    return list;
  }, [sourceMovies, sort]);

  const pageRows = useMemo(
    () =>
      sortedMovies.slice(
        safePage * pageSize,
        safePage * pageSize + pageSize
      ),
    [sortedMovies, safePage, pageSize]
  );

  const tableData = useMemo(() => pageRows.map(movie => ({ ...movie })), [pageRows]);

  const columns = useMemo<ColumnDef<RadarrMovie>[]>(() => [
    {
      accessorKey: "title",
      header: "Title",
    },
    {
      accessorKey: "year",
      header: "Year",
    },
    {
      accessorKey: "monitored",
      header: "Monitored",
      cell: ({ getValue }) => (
        <span className="table-badge">{getValue() ? "Yes" : "No"}</span>
      ),
    },
    {
      accessorKey: "hasFile",
      header: "Has File",
      cell: ({ getValue }) => (
        <span className="table-badge">{getValue() ? "Yes" : "No"}</span>
      ),
    },
  ], []);

  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: tableData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const handleSort = (key: RadarrSortKey) => {
    setSort((prev) =>
      prev.key === key
        ? { key, direction: prev.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" }
    );
  };

  const renderHeader = (key: RadarrSortKey, label: string) => (
    <th className="sortable" onClick={() => handleSort(key)}>
      {label}
      {sort.key === key ? (
        <span className="sort-arrow">{sort.direction === "asc" ? "▲" : "▼"}</span>
      ) : null}
    </th>
  );

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          {refreshLabel ? <span>{refreshLabel}</span> : null}
          <br />
          <strong>Available:</strong> {counts?.available ?? 0} • <strong>Monitored:</strong> {counts?.monitored ?? 0} • <strong>Missing:</strong> {(counts?.monitored ?? 0) - (counts?.available ?? 0)}
        </div>
        <button className="btn ghost" onClick={onRestart}>
          <IconImage src={RestartIcon} />
          Restart Instance
        </button>
      </div>
      <div className="table-wrapper">
        <table className="responsive-table">
          <thead>
            <tr>
              {renderHeader("title", "Title")}
              {renderHeader("year", "Year")}
              {renderHeader("monitored", "Monitored")}
              {renderHeader("hasFile", "Has File")}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((movie) => (
              <tr key={movie.id ?? `${movie.title}-${movie.year}`}>
                <td data-label="Title">{movie.title ?? ""}</td>
                <td data-label="Year">{movie.year ?? ""}</td>
                <td data-label="Monitored">
                  <span className="table-badge">{movie.monitored ? "Yes" : "No"}</span>
                </td>
                <td data-label="Has File">
                  <span className="table-badge">{movie.hasFile ? "Yes" : "No"}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination">
        <div>
          Page {safePage + 1} of {effectiveTotalPages} ({totalItems} items · page size{" "}
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
    </div>
  );
}

function SonarrView({ active }: { active: boolean }): JSX.Element {
  const { push } = useToast();
  const {
    value: globalSearch,
    setValue: setGlobalSearch,
    register,
    clearHandler,
  } = useSearch();

  const [instances, setInstances] = useState<ArrInfo[]>([]);
  const [selection, setSelection] = useState<string | "aggregate">("aggregate");
  const [instanceData, setInstanceData] =
    useState<SonarrSeriesResponse | null>(null);
  const [instancePage, setInstancePage] = useState(0);
  const [instanceQuery, setInstanceQuery] = useState("");
  const [instanceLoading, setInstanceLoading] = useState(false);
  const [live, setLive] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [instancePages, setInstancePages] = useState<
    Record<number, SonarrSeriesEntry[]>
  >({});
  const instancePagesRef = useRef<Record<number, SonarrSeriesEntry[]>>({});
  const instanceDataRef = useRef<SonarrSeriesResponse | null>(null);
  const instanceKeyRef = useRef<string>("");
  const [instancePageSize, setInstancePageSize] = useState(SONARR_PAGE_SIZE);
  const [instanceTotalPages, setInstanceTotalPages] = useState(1);
  const [instanceTotalItems, setInstanceTotalItems] = useState(0);
  const globalSearchRef = useRef(globalSearch);
  const backendReadyWarnedRef = useRef(false);

  const [aggRows, setAggRows] = useState<SonarrAggRow[]>([]);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggPage, setAggPage] = useState(0);
  const [aggFilter, setAggFilter] = useState("");
  const [aggUpdated, setAggUpdated] = useState<string | null>(null);
  const [aggSort, setAggSort] = useState<{
    key: SonarrAggSortKey;
    direction: "asc" | "desc";
   }>({ key: "__instance", direction: "asc" });
   const [onlyMissing, setOnlyMissing] = useState(false);
   const [liveAgg, setLiveAgg] = useState(false);
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
        push("Sonarr backend is still initialising. Check the logs if this persists.", "info");
      } else if (data.ready) {
        backendReadyWarnedRef.current = true;
      }
      const filtered = (data.arr || []).filter((arr) => arr.type === "sonarr");
      setInstances(filtered);
      if (!filtered.length) {
        setSelection("aggregate");
        setInstanceData(null);
        setAggRows([]);
        setAggSummary({ available: 0, monitored: 0, missing: 0, total: 0 });
        return;
      }
      if (selection === "") {
        setSelection("aggregate");
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
          : "Unable to load Sonarr instances",
        "error"
      );
    }
  }, [push, selection]);

  const fetchInstance = useCallback(
    async (
      category: string,
      page: number,
      query: string,
      options: { preloadAll?: boolean; showLoading?: boolean; missingOnly?: boolean } = {}
    ) => {
      const { preloadAll = true, showLoading = true, missingOnly } = options;
      const useMissing = missingOnly ?? onlyMissing;
      if (showLoading) {
        setInstanceLoading(true);
      }
      try {
        const key = `${category}::${query}::${useMissing ? "missing" : "all"}`;
        const keyChanged = instanceKeyRef.current !== key;
        if (keyChanged) {
          instanceKeyRef.current = key;
          setInstancePages(() => {
            instancePagesRef.current = {};
            return {};
          });
          setInstanceTotalItems(0);
          setInstanceTotalPages(1);
        }
        const response = await getSonarrSeries(
          category,
          page,
          SONARR_PAGE_SIZE,
          query,
          { missingOnly: useMissing }
        );
        const resolvedPage = response.page ?? page;
        const pageSize = response.page_size ?? SONARR_PAGE_SIZE;
        const totalItems = response.total ?? (response.series ?? []).length;
        const totalPages = Math.max(1, Math.ceil((totalItems || 0) / pageSize));
        const series = response.series ?? [];

        const prevPages = keyChanged ? {} : instancePagesRef.current;
        const nextPages = { ...prevPages, [resolvedPage]: series };
        const prevSignature = createFilteredSignature(prevPages[resolvedPage] ?? [], useMissing);
        const nextSignature = createFilteredSignature(series, useMissing);
        const shouldUpdateCurrentPage = keyChanged || prevSignature !== nextSignature;

        instancePagesRef.current = nextPages;
        if (shouldUpdateCurrentPage) {
          setInstancePages(nextPages);
        }

        setInstanceData((prev) => {
          const prevCounts = prev?.counts ?? null;
          const nextCounts = response.counts ?? null;
          const countsChanged =
            !prev ||
            prev.total !== response.total ||
            prev.page !== response.page ||
            prev.page_size !== response.page_size ||
            (prevCounts?.available ?? null) !== (nextCounts?.available ?? null) ||
            (prevCounts?.monitored ?? null) !== (nextCounts?.monitored ?? null) ||
            (prevCounts?.missing ?? null) !== (nextCounts?.missing ?? null);
          if (countsChanged || shouldUpdateCurrentPage) {
            instanceDataRef.current = response;
            return response;
          }
          return prev;
        });

        setInstancePage((prev) => (prev === resolvedPage ? prev : resolvedPage));
        setInstanceQuery((prev) => (prev === query ? prev : query));
        setInstancePageSize((prev) => (prev === pageSize ? prev : pageSize));
        setInstanceTotalPages((prev) => (prev === totalPages ? prev : totalPages));
        setInstanceTotalItems((prev) => (prev === totalItems ? prev : totalItems));

        if (shouldUpdateCurrentPage) {
          setLastUpdated(new Date().toLocaleTimeString());
        }

        if (preloadAll) {
          const pagesToFetch: number[] = [];
          for (let i = 0; i < totalPages; i += 1) {
            if (i === resolvedPage) continue;
            if (!nextPages[i]) {
              pagesToFetch.push(i);
            }
          }
          for (const targetPage of pagesToFetch) {
            try {
              const res = await getSonarrSeries(
                category,
                targetPage,
                pageSize,
                query,
                { missingOnly: useMissing }
              );
              if (instanceKeyRef.current !== key) {
                break;
              }
              const pageIndex = res.page ?? targetPage;
              const pageSeries = res.series ?? [];
              const currentPages = instancePagesRef.current;
              const prevSnapshot = createFilteredSignature(currentPages[pageIndex] ?? [], useMissing);
              const nextSnapshot = createFilteredSignature(pageSeries, useMissing);
              if (prevSnapshot === nextSnapshot) {
                instancePagesRef.current = { ...currentPages, [pageIndex]: pageSeries };
                continue;
              }
              setInstancePages((prev) => {
                const updated = { ...prev, [pageIndex]: pageSeries };
                instancePagesRef.current = updated;
                return updated;
              });
            } catch {
              break;
            }
          }
        }
      } catch (error) {
        push(
          error instanceof Error
            ? error.message
            : `Failed to load ${category} series`,
          "error"
        );
      } finally {
        if (showLoading) {
          setInstanceLoading(false);
        }
      }
    },
    [push, onlyMissing]
  );

  const loadAggregate = useCallback(async () => {
    if (!instances.length) {
      setAggRows([]);
      setAggSummary({ available: 0, monitored: 0, missing: 0, total: 0 });
      return;
    }
    setAggLoading(true);
    try {
      const aggregated: SonarrAggRow[] = [];
      let totalAvailable = 0;
      let totalMonitored = 0;
      let totalMissing = 0;
      for (const inst of instances) {
        let page = 0;
        let counted = false;
        const label = inst.name || inst.category;
        while (page < 200) {
          const res = await getSonarrSeries(
            inst.category,
            page,
            SONARR_AGG_FETCH_SIZE,
            "",
            { missingOnly: onlyMissing }
          );
          if (!counted) {
            const counts = res.counts;
            if (counts) {
              totalAvailable += counts.available ?? 0;
              totalMonitored += counts.monitored ?? 0;
              totalMissing += counts.missing ?? 0;
            }
            counted = true;
          }
          const series = res.series ?? [];
          series.forEach((entry: SonarrSeriesEntry) => {
            const title =
              (entry.series?.["title"] as string | undefined) || "";
            Object.entries(entry.seasons ?? {}).forEach(
              ([seasonNumber, season]) => {
                (season.episodes ?? []).forEach((episode: SonarrEpisode) => {
                  aggregated.push({
                    __instance: label,
                    series: title,
                    season: seasonNumber,
                    episode: episode.episodeNumber ?? "",
                    title: episode.title ?? "",
                    monitored: !!episode.monitored,
                    hasFile: !!episode.hasFile,
                    airDate: episode.airDateUtc ?? "",
                  });
                });
              }
            );
          });
          if (!series.length || series.length < SONARR_AGG_FETCH_SIZE) break;
          page += 1;
        }
      }
      setAggRows(aggregated);
      setAggSummary({
        available: totalAvailable,
        monitored: totalMonitored,
        missing: totalMissing,
        total: aggregated.length,
      });
      setAggPage(0);
      setAggFilter(globalSearch);
      setAggUpdated(new Date().toLocaleTimeString());
    } catch (error) {
      setAggRows([]);
      setAggSummary({ available: 0, monitored: 0, missing: 0, total: 0 });
       push(
         error instanceof Error
           ? error.message
           : "Failed to load aggregated Sonarr data",
         "error"
       );
     } finally {
       setAggLoading(false);
     }
   }, [instances, globalSearch, push, onlyMissing]);

  useEffect(() => {
    if (!active) return;
    void loadInstances();
  }, [active, loadInstances]);

  useEffect(() => {
    if (!active) return;
    if (!selection || selection === "aggregate") return;
    setInstancePage(0);
    const query = globalSearchRef.current;
    void fetchInstance(selection, 0, query, {
      preloadAll: true,
      showLoading: true,
      missingOnly: onlyMissing,
    });
  }, [active, selection, fetchInstance, onlyMissing]);

  useEffect(() => {
    if (!active) return;
    if (selection !== "aggregate") return;
    void loadAggregate();
   }, [active, selection, loadAggregate]);

   useInterval(() => {
     if (selection === "aggregate" && liveAgg) {
       void loadAggregate();
     }
   }, selection === "aggregate" && liveAgg ? 10000 : null);

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
      missingOnly: onlyMissing,
    });
      }
    };
    register(handler);
    return () => clearHandler(handler);
  }, [active, selection, register, clearHandler, fetchInstance, onlyMissing]);

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
          missingOnly: onlyMissing,
        });
      }
    },
    active && selection && selection !== "aggregate" && live ? 1000 : null
  );

  useEffect(() => {
    globalSearchRef.current = globalSearch;
  }, [globalSearch]);

  useEffect(() => {
    if (selection === "aggregate") {
      setAggFilter(globalSearch);
    }
  }, [selection, globalSearch]);

  const filteredAggRows = useMemo(() => {
    let rows = aggRows;
    if (aggFilter) {
      const q = aggFilter.toLowerCase();
      rows = rows.filter((row) => {
        return (
          row.series.toLowerCase().includes(q) ||
          row.title.toLowerCase().includes(q) ||
          row.__instance.toLowerCase().includes(q)
        );
      });
    }
    return rows;
  }, [aggRows, aggFilter]);

  const sortedAggRows = useMemo(() => {
    const list = [...filteredAggRows];
    const getValue = (row: SonarrAggRow, key: SonarrAggSortKey) => {
      switch (key) {
        case "__instance":
          return row.__instance.toLowerCase();
        case "series":
          return row.series.toLowerCase();
        case "season":
          return Number(row.season) || 0;
        case "episode":
          return Number(row.episode) || 0;
        case "title":
          return row.title.toLowerCase();
        case "monitored":
          return row.monitored ? 1 : 0;
        case "hasFile":
          return row.hasFile ? 1 : 0;
        case "airDate":
          return row.airDate || "";
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
    Math.ceil(sortedAggRows.length / SONARR_AGG_PAGE_SIZE)
  );
  const aggPageRows = sortedAggRows.slice(
    aggPage * SONARR_AGG_PAGE_SIZE,
    aggPage * SONARR_AGG_PAGE_SIZE + SONARR_AGG_PAGE_SIZE
  );

  const currentSeries = instancePages[instancePage] ?? [];

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
      <div className="card-header">Sonarr</div>
      <div className="card-body">
        <div className="split">
          <aside className="pane sidebar">
            <button
              className={`btn ${isAggregate ? "active" : ""}`}
              onClick={() => setSelection("aggregate")}
            >
              All Sonarr
            </button>
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
                <option value="aggregate">All Sonarr</option>
                {instances.map((inst) => (
                  <option key={inst.category} value={inst.category}>
                    {inst.name || inst.category}
                  </option>
                ))}
              </select>
            </div>
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div className="col field">
                <label>Search</label>
                <input
                   placeholder="Filter series or episodes"
                   value={globalSearch}
                   onChange={(event) => setGlobalSearch(event.target.value)}
                 />
               </div>
               <label className="hint inline" style={{ marginBottom: 8 }}>
                 <input
                   type="checkbox"
                   checked={onlyMissing}
                   onChange={(event) => setOnlyMissing(event.target.checked)}
                 />
                 <IconImage src={FilterIcon} />
                 <span>Only Missing</span>
               </label>
               {isAggregate && (
                 <label className="hint inline" style={{ marginBottom: 8 }}>
                   <input
                     type="checkbox"
                     checked={liveAgg}
                     onChange={(event) => setLiveAgg(event.target.checked)}
                   />
                   <IconImage src={LiveIcon} />
                   <span>Live</span>
                 </label>
               )}
               {!isAggregate && (
                <label className="hint inline" style={{ marginBottom: 8 }}>
                  <input
                    type="checkbox"
                    checked={live}
                    onChange={(event) => setLive(event.target.checked)}
                  />
                  <IconImage src={LiveIcon} />
                  <span>Live</span>
                </label>
              )}
            </div>

            {isAggregate ? (
              <SonarrAggregateView
                loading={aggLoading}
                rows={aggPageRows}
                total={sortedAggRows.length}
                page={aggPage}
                totalPages={aggPages}
                onPageChange={setAggPage}
                onRefresh={() => void loadAggregate()}
                lastUpdated={aggUpdated}
                sort={aggSort}
                onSort={(key) =>
                  setAggSort((prev) =>
                    prev.key === key
                      ? {
                          key,
                          direction:
                            prev.direction === "asc" ? "desc" : "asc",
                        }
                      : { key, direction: "asc" }
                  )
                }
                summary={aggSummary}
              />
            ) : (
              <SonarrInstanceView
                loading={instanceLoading}
                counts={instanceData?.counts ?? null}
                series={currentSeries}
                page={instancePage}
                pageSize={instancePageSize}
                totalPages={instanceTotalPages}
                totalItems={instanceTotalItems}
                onlyMissing={onlyMissing}
                onPageChange={(page) => {
                  setInstancePage(page);
                void fetchInstance(selection as string, page, instanceQuery, {
                  preloadAll: false,
                  showLoading: true,
                  missingOnly: onlyMissing,
                });
                }}
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

interface SonarrAggregateViewProps {
  loading: boolean;
  rows: SonarrAggRow[];
  total: number;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  lastUpdated: string | null;
  sort: { key: SonarrAggSortKey; direction: "asc" | "desc" };
  onSort: (key: SonarrAggSortKey) => void;
  summary: { available: number; monitored: number; missing: number; total: number };
}

function SonarrAggregateView({
  loading,
  rows,
  total,
  page,
  totalPages,
  onPageChange,
  onRefresh,
  lastUpdated,
  sort,
  onSort,
  summary,
}: SonarrAggregateViewProps): JSX.Element {
  // Group rows by series and season
  const tableData = useMemo(() => {
    const map = new Map<string, Map<string, SonarrAggRow[]>>();
    rows.forEach(row => {
      const seriesKey = `${row.__instance}-${row.series}`;
      if (!map.has(seriesKey)) map.set(seriesKey, new Map());
      const seasons = map.get(seriesKey)!;
      const seasonKey = String(row.season);
      if (!seasons.has(seasonKey)) seasons.set(seasonKey, []);
      seasons.get(seasonKey)!.push(row);
    });
    return Array.from(map.entries()).map(([seriesKey, seasons]) => {
      const [instance, series] = seriesKey.split('-', 2);
      return {
        series,
        instance,
        subRows: Array.from(seasons.entries()).map(([seasonNumber, episodes]) => ({
          seasonNumber,
          isSeason: true,
          subRows: episodes.map(ep => ({ ...ep, isEpisode: true }))
        }))
      };
    });
  }, [rows]);

  const columns = useMemo<ColumnDef<any>[]>(() => [
    {
      accessorKey: "title",
      header: "Title",
      cell: ({ row }) => {
        if (row.original.isEpisode) return row.original.title;
        if (row.original.isSeason) return `Season ${row.original.seasonNumber}`;
        return row.original.series;
      }
    },
    {
      accessorKey: "monitored",
      header: "Monitored",
      cell: ({ row }) => {
        const monitored = row.original.isEpisode ? row.original.monitored : row.original.monitored;
        return <span className="table-badge">{monitored ? "Yes" : "No"}</span>;
      }
    },
    {
      accessorKey: "hasFile",
      header: "Has File",
      cell: ({ row }) => {
        if (row.original.isEpisode) {
          return <span className="table-badge">{row.original.hasFile ? "Yes" : "No"}</span>;
        }
        return null;
      }
    },
    {
      accessorKey: "airDate",
      header: "Air Date",
      cell: ({ row }) => {
        if (row.original.isEpisode) {
          return row.original.airDate || "—";
        }
        return null;
      }
    },
  ], []);

  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: tableData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
  });

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          Aggregated episodes across all instances{" "}
          {lastUpdated ? `(updated ${lastUpdated})` : ""}
          <br />
          <strong>Available:</strong>{" "}
          {summary.available.toLocaleString(undefined, { maximumFractionDigits: 0 })} •{" "}
          <strong>Monitored:</strong>{" "}
          {summary.monitored.toLocaleString(undefined, { maximumFractionDigits: 0 })} •{" "}
          <strong>Missing:</strong>{" "}
          {summary.missing.toLocaleString(undefined, { maximumFractionDigits: 0 })} •{" "}
          <strong>Total Episodes:</strong>{" "}
          {summary.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </div>
        <button className="btn ghost" onClick={onRefresh} disabled={loading}>
          <IconImage src={RefreshIcon} />
          Refresh
        </button>
      </div>
      {loading ? (
        <div className="loading">
          <span className="spinner" /> Loading Sonarr library…
        </div>
      ) : (
        <>
          <div className="table-wrapper">
            <table className="responsive-table">
              <thead>
                <tr>
                  <th></th>
                  {table.getFlatHeaders().map(header => (
                    <th key={header.id}>
                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.getRowModel().rows.map(row => (
                  <tr key={row.id}>
                    <td>
                      {row.getCanExpand() && (
                        <button onClick={row.getToggleExpandedHandler()}>
                          {row.getIsExpanded() ? '▼' : '▶'}
                        </button>
                      )}
                    </td>
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <div>
              Page {page + 1} of {totalPages} ({total} items)
            </div>
            <div className="inline">
              <button
                className="btn"
                onClick={() => onPageChange(Math.max(0, page - 1))}
                disabled={page === 0}
              >
                Prev
              </button>
              <button
                className="btn"
                onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
                disabled={page >= totalPages - 1}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

interface SonarrInstanceViewProps {
  loading: boolean;
  counts: { available: number; monitored: number; missing?: number } | null;
  series: SonarrSeriesEntry[];
  page: number;
  pageSize: number;
  totalPages: number;
  totalItems: number;
  onlyMissing: boolean;
  onPageChange: (page: number) => void;
  onRestart: () => void;
  lastUpdated: string | null;
}

function SonarrInstanceView({
  loading,
  counts,
  series: seriesEntries,
  page,
  pageSize,
  totalPages,
  totalItems,
  onlyMissing,
  onPageChange,
  onRestart,
  lastUpdated,
}: SonarrInstanceViewProps): JSX.Element {
  const refreshLabel = lastUpdated ? `Last updated ${lastUpdated}` : null;
  const filteredSeries = useMemo(() => filterSeriesEntriesForMissing(seriesEntries, onlyMissing), [seriesEntries, onlyMissing]);
  const missingCount = useMemo(() => {
    if (counts?.missing !== undefined) {
      return counts.missing;
    }
    const monitored = counts?.monitored ?? 0;
    const available = counts?.available ?? 0;
    return Math.max(monitored - available, 0);
  }, [counts]);
  const totalItemsDisplay = onlyMissing
    ? filteredSeries.length
    : totalItems || seriesEntries.length;
  const effectiveTotalPages = onlyMissing
    ? Math.max(1, Math.ceil(Math.max(totalItemsDisplay, 1) / pageSize))
    : totalPages;
  const safePage = Math.min(page, Math.max(0, effectiveTotalPages - 1));
  const pageRows = useMemo(() => {
    const start = safePage * pageSize;
    return filteredSeries.slice(start, start + pageSize);
  }, [filteredSeries, safePage, pageSize]);

  const tableData = useMemo(() => pageRows.flatMap(series => [
    series,
    ...Object.entries(series.seasons ?? {}).flatMap(([seasonNumber, season]) => [
      { seasonNumber, ...season, isSeason: true },
      ...(season.episodes?.map(episode => ({ ...episode, isEpisode: true })) || [])
    ])
  ]), [pageRows]);

  const columns = useMemo<ColumnDef<any>[]>(() => [
    {
      accessorKey: "title",
      header: "Title",
      cell: ({ row }) => {
        if (row.original.isEpisode) return `  ${row.original.title}`;
        if (row.original.isSeason) return `Season ${row.original.seasonNumber}`;
        return row.original.series?.title || "Unknown";
      }
    },
    {
      accessorKey: "monitored",
      header: "Monitored",
      cell: ({ row }) => {
        const monitored = row.original.isEpisode ? row.original.monitored : row.original.monitored;
        return <span className="table-badge">{monitored ? "Yes" : "No"}</span>;
      }
    },
    {
      accessorKey: "hasFile",
      header: "Has File",
      cell: ({ row }) => {
        if (row.original.isEpisode) {
          return <span className="table-badge">{row.original.hasFile ? "Yes" : "No"}</span>;
        }
        return null;
      }
    },
    {
      accessorKey: "airDate",
      header: "Air Date",
      cell: ({ row }) => {
        if (row.original.isEpisode) {
          return row.original.airDate || "—";
        }
        return null;
      }
    },
  ], []);

  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: tableData,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  useEffect(() => {
    if (safePage !== page) {
      onPageChange(safePage);
    }
  }, [safePage, page, onPageChange]);

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          {refreshLabel ? <span>{refreshLabel}</span> : null}
          <br />
          <strong>Available:</strong> {counts?.available ?? 0} • <strong>Monitored:</strong> {counts?.monitored ?? 0} • <strong>Missing:</strong> {missingCount}
        </div>
        <button className="btn ghost" onClick={onRestart}>
          <IconImage src={RestartIcon} />
          Restart Instance
        </button>
      </div>
      <div className="stack">
        {loading ? (
          <div className="loading">
            <span className="spinner" /> Loading Sonarr library…
          </div>
        ) : tableData.length ? (
          <div className="table-wrapper">
            <table className="responsive-table">
              <thead>
                <tr>
                  {table.getFlatHeaders().map(header => (
                    <th key={header.id}>
                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.getRowModel().rows.map(row => (
                  <tr key={row.id}>
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="hint">No series found.</div>
        )}
      </div>
      <div className="pagination">
        <div>
          Page {safePage + 1} of {effectiveTotalPages} ({totalItemsDisplay} items ·
          page size {pageSize})
        </div>
        <div className="inline">
          <button
            className="btn"
            onClick={() => onPageChange(Math.max(0, safePage - 1))}
            disabled={safePage === 0 || loading}
          >
            Prev
          </button>
          <button
            className="btn"
            onClick={() => onPageChange(Math.min(effectiveTotalPages - 1, safePage + 1))}
            disabled={safePage >= effectiveTotalPages - 1 || loading}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
