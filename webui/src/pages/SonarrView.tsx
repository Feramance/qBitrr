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
  getConfig,
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
import FilterIcon from "../icons/alert.svg";

interface SonarrViewProps {
  active: boolean;
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

export function SonarrView({ active }: SonarrViewProps): JSX.Element {
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
  const [liveArr, setLiveArr] = useState(true);
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

  const [onlyMissing, setOnlyMissing] = useState(false);
  const [aggSummary, setAggSummary] = useState<{
    available: number;
    monitored: number;
    missing: number;
    total: number;
  }>({ available: 0, monitored: 0, missing: 0, total: 0 });

  const [groupSonarr, setGroupSonarr] = useState(false);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await getConfig();
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const webUI = (config as any).WebUI ?? {};
        setGroupSonarr(webUI.GroupSonarr ?? false);
        setLiveArr(webUI.LiveArr ?? true);
      } catch (error) {
        console.error('Failed to load config', error);
      }
    };
    void loadConfig();
  }, []);

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

      // Smart diffing: only update if data actually changed
      setAggRows((prev) => {
        const prevJson = JSON.stringify(prev);
        const nextJson = JSON.stringify(aggregated);
        if (prevJson === nextJson) {
          return prev;
        }
        return aggregated;
      });

      const newSummary = {
        available: totalAvailable,
        monitored: totalMonitored,
        missing: totalMissing,
        total: aggregated.length,
      };

      setAggSummary((prev) => {
        if (
          prev.available === newSummary.available &&
          prev.monitored === newSummary.monitored &&
          prev.missing === newSummary.missing &&
          prev.total === newSummary.total
        ) {
          return prev;
        }
        return newSummary;
      });

      // Only reset page if filter changed, not on refresh
      if (aggFilter !== globalSearch) {
        setAggPage(0);
        setAggFilter(globalSearch);
      }
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
    if (selection === "aggregate" && liveArr) {
      void loadAggregate();
    }
  }, selection === "aggregate" && liveArr ? 10000 : null);

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
    active && selection && selection !== "aggregate" && liveArr ? 1000 : null
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

  const sortedAggRows = filteredAggRows;

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
                groupSonarr={groupSonarr}
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
                groupSonarr={groupSonarr}
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
  groupSonarr: boolean;
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
  groupSonarr,
  summary,
}: SonarrAggregateViewProps): JSX.Element {
  // Create fully grouped data from all rows
  const allGroupedData = useMemo(() => {
    const instanceMap = new Map<string, Map<string, Map<string, SonarrAggRow[]>>>();

    rows.forEach(row => {
      const instance = row.__instance;
      const series = row.series;
      const season = String(row.season);

      if (!instanceMap.has(instance)) {
        instanceMap.set(instance, new Map());
      }
      const instanceSeriesMap = instanceMap.get(instance)!;

      if (!instanceSeriesMap.has(series)) {
        instanceSeriesMap.set(series, new Map());
      }
      const seasonMap = instanceSeriesMap.get(series)!;

      if (!seasonMap.has(season)) {
        seasonMap.set(season, []);
      }
      seasonMap.get(season)!.push(row);
    });

    const result: Array<{
      instance: string;
      series: string;
      subRows: Array<{
        seasonNumber: string;
        isSeason: boolean;
        subRows: Array<SonarrAggRow & { isEpisode: boolean }>;
      }>;
    }> = [];

    instanceMap.forEach((seriesMap, instance) => {
      seriesMap.forEach((seasonMap, series) => {
        result.push({
          instance,
          series,
          subRows: Array.from(seasonMap.entries()).map(([seasonNumber, episodes]) => ({
            seasonNumber,
            isSeason: true,
            subRows: episodes.map(ep => ({ ...ep, isEpisode: true }))
          }))
        });
      });
    });

    return result;
  }, [rows]);

  // For grouped view, paginate the series groups (not individual episodes)
  // For flat view, use the already-paginated rows
  const groupedPageRows = useMemo(() => {
    const pageSize = 50;
    return allGroupedData.slice(page * pageSize, (page + 1) * pageSize);
  }, [allGroupedData, page]);

  const tableData = groupSonarr ? groupedPageRows : rows;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const groupedColumns = useMemo<ColumnDef<any>[]>(() => [
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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const flatColumns = useMemo<ColumnDef<any>[]>(() => [
    {
      accessorKey: "__instance",
      header: "Instance",
    },
    {
      accessorKey: "series",
      header: "Series",
    },
    {
      accessorKey: "season",
      header: "Season",
    },
    {
      accessorKey: "episode",
      header: "Episode",
    },
    {
      accessorKey: "title",
      header: "Title",
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
    {
      accessorKey: "airDate",
      header: "Air Date",
      cell: ({ getValue }) => getValue() || "—",
    },
  ], []);

  const columns = groupSonarr ? groupedColumns : flatColumns;

  // eslint-disable-next-line react-hooks/incompatible-library
  const groupedTable = useReactTable({
    data: tableData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
  });

  const flatTable = useReactTable({
    data: tableData,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    state: {
      pagination: {
        pageIndex: page,
        pageSize: 50,
      },
    },
    manualPagination: true,
    pageCount: totalPages,
  });

  const table = groupSonarr ? groupedTable : flatTable;

  const pageSize = 50;
  // For grouped view, paginate by series groups; for flat view, paginate by rows
  const effectiveTotalPages = groupSonarr
    ? Math.ceil(allGroupedData.length / pageSize)
    : Math.ceil(total / pageSize);
  const safePage = Math.min(page, Math.max(0, effectiveTotalPages - 1));
  const totalItemsDisplay = groupSonarr
    ? `${allGroupedData.length} series`
    : total.toLocaleString();

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
      ) : groupSonarr ? (
        <div className="sonarr-hierarchical-view">
          {groupedPageRows.map((seriesGroup: typeof groupedPageRows[number]) => (
            <details key={`${seriesGroup.instance}-${seriesGroup.series}`} className="series-details">
              <summary className="series-summary">
                <span className="series-title">{seriesGroup.series}</span>
                <span className="series-instance">({seriesGroup.instance})</span>
              </summary>
              <div className="series-content">
                {seriesGroup.subRows.map((season: typeof seriesGroup.subRows[number]) => (
                  <details key={`${seriesGroup.instance}-${seriesGroup.series}-${season.seasonNumber}`} className="season-details">
                    <summary className="season-summary">
                      <span className="season-title">Season {season.seasonNumber}</span>
                      <span className="season-count">({season.subRows.length} episodes)</span>
                    </summary>
                    <div className="season-content">
                      <div className="episodes-table-wrapper">
                        <table className="episodes-table">
                          <thead>
                            <tr>
                              <th>Episode</th>
                              <th>Title</th>
                              <th>Monitored</th>
                              <th>Has File</th>
                              <th>Air Date</th>
                            </tr>
                          </thead>
                          <tbody>
                            {season.subRows.map((episode) => (
                              <tr key={`${episode.__instance}-${episode.series}-${episode.season}-${episode.episode}`}>
                                <td>{episode.episode}</td>
                                <td>{episode.title}</td>
                                <td><span className="table-badge">{episode.monitored ? "Yes" : "No"}</span></td>
                                <td><span className="table-badge">{episode.hasFile ? "Yes" : "No"}</span></td>
                                <td>{episode.airDate || "—"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </details>
                ))}
              </div>
            </details>
          ))}
        </div>
      ) : tableData.length ? (
        <div className="table-wrapper">
          <table className="responsive-table">
            <thead>
              <tr>
                {table.getFlatHeaders().map(header => (
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
              {table.getRowModel().rows.map(row => {
                const episode = row.original;
                const stableKey = `${episode.__instance}-${episode.series}-${episode.season}-${episode.episode}`;
                return (
                  <tr key={stableKey}>
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id} data-label={cell.column.columnDef.header as string}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="hint">No series found.</div>
      )}
      {tableData.length > 0 && (
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
  groupSonarr: boolean;
}

function SonarrInstanceView({
  loading,
  counts,
  series,
  page,
  pageSize,
  totalPages,

  onPageChange,
  groupSonarr,
}: SonarrInstanceViewProps): JSX.Element {
  const safePage = Math.min(page, Math.max(0, totalPages - 1));

  // Transform series to SonarrAggRow[]
  const episodeRows = useMemo(() => {
    const rows: SonarrAggRow[] = [];
    for (const entry of series) {
      const title = (entry.series?.["title"] as string | undefined) || "";
      Object.entries(entry.seasons ?? {}).forEach(([seasonNumber, season]) => {
        (season.episodes ?? []).forEach((episode) => {
          rows.push({
            __instance: "Instance",
            series: title,
            season: seasonNumber,
            episode: episode.episodeNumber ?? "",
            title: episode.title ?? "",
            monitored: !!episode.monitored,
            hasFile: !!episode.hasFile,
            airDate: episode.airDateUtc ?? "",
          });
        });
      });
    }
    return rows;
  }, [series]);

  // Group for hierarchical view
  const groupedTableData = useMemo(() => {
    const map = new Map<string, Map<string, SonarrAggRow[]>>();
    episodeRows.forEach(row => {
      const seriesKey = row.series;
      if (!map.has(seriesKey)) map.set(seriesKey, new Map());
      const seasons = map.get(seriesKey)!;
      const seasonKey = String(row.season);
      if (!seasons.has(seasonKey)) seasons.set(seasonKey, []);
      seasons.get(seasonKey)!.push(row);
    });
    return Array.from(map.entries()).map(([series, seasons]) => ({
      series,
      subRows: Array.from(seasons.entries()).map(([seasonNumber, episodes]) => ({
        seasonNumber,
        isSeason: true,
        subRows: episodes.map(ep => ({ ...ep, isEpisode: true }))
      }))
    }));
  }, [episodeRows]);

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          {counts ? (
            <>
              <strong>Available:</strong> {counts.available.toLocaleString()} •{" "}
              <strong>Monitored:</strong> {counts.monitored.toLocaleString()} •{" "}
              <strong>Missing:</strong> {counts.missing?.toLocaleString() ?? 0}
            </>
          ) : (
            "Loading series information..."
          )}
        </div>
      </div>
      {loading ? (
        <div className="loading">
          <span className="spinner" /> Loading series…
        </div>
      ) : groupSonarr ? (
        <div className="sonarr-hierarchical-view">
          {groupedTableData.map((series) => (
            <details key={`${series.series}`} className="series-details">
              <summary className="series-summary">
                <span className="series-title">{series.series}</span>
              </summary>
              <div className="series-content">
                {series.subRows.map((season) => (
                  <details key={`${series.series}-${season.seasonNumber}`} className="season-details">
                    <summary className="season-summary">
                      <span className="season-title">Season {season.seasonNumber}</span>
                      <span className="season-count">({season.subRows.length} episodes)</span>
                    </summary>
                    <div className="season-content">
                      <div className="episodes-table-wrapper">
                        <table className="episodes-table">
                          <thead>
                            <tr>
                              <th>Episode</th>
                              <th>Title</th>
                              <th>Monitored</th>
                              <th>Has File</th>
                              <th>Air Date</th>
                            </tr>
                          </thead>
                          <tbody>
                            {season.subRows.map((episode: typeof season.subRows[number]) => (
                            <tr key={`${episode.series}-${episode.season}-${episode.episode}`}>
                              <td>{episode.episode}</td>
                              <td>{episode.title}</td>
                              <td><span className="table-badge">{episode.monitored ? "Yes" : "No"}</span></td>
                              <td><span className="table-badge">{episode.hasFile ? "Yes" : "No"}</span></td>
                              <td>{episode.airDate || "—"}</td>
                            </tr>
                          ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </details>
                ))}
              </div>
            </details>
          ))}
        </div>
      ) : episodeRows.length ? (
        <div className="table-wrapper">
          <table className="responsive-table">
            <thead>
              <tr>
                <th>Series</th>
                <th>Season</th>
                <th>Episode</th>
                <th>Title</th>
                <th>Monitored</th>
                <th>Has File</th>
                <th>Air Date</th>
              </tr>
            </thead>
            <tbody>
              {episodeRows.slice(safePage * pageSize, safePage * pageSize + pageSize).map((row, idx) => (
                <tr key={`${row.series}-${row.season}-${row.episode}-${idx}`}>
                  <td>{row.series}</td>
                  <td>{row.season}</td>
                  <td>{row.episode}</td>
                  <td>{row.title}</td>
                  <td><span className="table-badge">{row.monitored ? "Yes" : "No"}</span></td>
                  <td><span className="table-badge">{row.hasFile ? "Yes" : "No"}</span></td>
                  <td>{row.airDate || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pagination">
            <div>
              Page {safePage + 1} of {totalPages} ({episodeRows.length.toLocaleString()} items · page size {pageSize})
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
                onClick={() => onPageChange(Math.min(totalPages - 1, safePage + 1))}
                disabled={safePage >= totalPages - 1 || loading}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="hint">No series found.</div>
      )}
    </div>
  );
}
