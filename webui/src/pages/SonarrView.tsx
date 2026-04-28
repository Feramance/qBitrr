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
import { useWebUI } from "../context/WebUIContext";
import { useInterval } from "../hooks/useInterval";
import { useDebounce } from "../hooks/useDebounce";
import { useDataSync } from "../hooks/useDataSync";
import { useArrBrowseMode } from "../hooks/useArrBrowseMode";
import { IconImage } from "../components/IconImage";
import { ArrBrowseModeToggle } from "../components/arr/ArrBrowseModeToggle";
import { ArrModal } from "../components/arr/ArrModal";
import { ArrPosterImage } from "../components/arr/ArrPosterImage";
import { sonarrSeriesThumbnailUrl } from "../utils/arrThumbnailUrl";
import {
  type SonarrSeriesGroup,
  SonarrSeriesGroupDetailBody,
} from "../components/arr/SonarrSeriesGroupDetailBody";
import RefreshIcon from "../icons/refresh-arrow.svg";

interface SonarrViewProps {
  active: boolean;
}

export interface SonarrAggRow {
  __instance: string;
  series: string;
  season: number | string;
  episode: number | string;
  title: string;
  monitored: boolean;
  hasFile: boolean;
  airDate: string;
  reason?: string | null;
  qualityProfileId?: number | null;
  qualityProfileName?: string | null;
  seriesId?: number;
  [key: string]: unknown;
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
  const filtered = filterSeriesEntriesForMissing(seriesEntries, onlyMissing);
  if (filtered.length === 0) return "empty";
  const first = filtered[0];
  const last = filtered[filtered.length - 1];
  return `${filtered.length}:${first?.series?.["title"] ?? ''}:${last?.series?.["title"] ?? ''}:${onlyMissing}`;
}

function filterSeriesEntryByReason(
  entry: SonarrSeriesEntry,
  reasonFilter: string
): SonarrSeriesEntry | null {
  if (reasonFilter === "all") return entry;
  const seasons = entry.seasons ?? {};
  const next: Record<string, SonarrSeason> = {};
  for (const [sn, season] of Object.entries(seasons)) {
    const eps = (season.episodes ?? []).filter((ep) => {
      const r = ep.reason as string | null | undefined;
      if (reasonFilter === "Not being searched") {
        return r === "Not being searched" || !r;
      }
      return r === reasonFilter;
    });
    if (eps.length) {
      next[sn] = { ...season, episodes: eps };
    }
  }
  if (!Object.keys(next).length) return null;
  return { ...entry, seasons: next };
}

function seriesEntryToGroup(
  entry: SonarrSeriesEntry,
  instanceLabel: string
): SonarrSeriesGroup {
  const title = (entry.series?.["title"] as string | undefined) || "";
  const seriesId = entry.series?.["id"] as number | undefined;
  const qualityProfileName = entry.series?.qualityProfileName ?? null;
  const qid = entry.series?.qualityProfileId ?? null;
  const episodes: SonarrAggRow[] = [];
  Object.entries(entry.seasons ?? {}).forEach(([seasonNumber, season]) => {
    (season.episodes ?? []).forEach((episode) => {
      episodes.push({
        __instance: instanceLabel,
        series: title,
        season: seasonNumber,
        episode: episode.episodeNumber ?? "",
        title: episode.title ?? "",
        monitored: !!episode.monitored,
        hasFile: !!episode.hasFile,
        airDate: episode.airDateUtc ?? "",
        reason: (episode.reason as string | null | undefined) ?? null,
        qualityProfileId: qid,
        qualityProfileName,
        seriesId,
      });
    });
  });
  return {
    instance: instanceLabel,
    series: title,
    qualityProfileName,
    seriesId,
    episodes,
  };
}

function countEpisodesInSeriesList(entries: SonarrSeriesEntry[]): number {
  let n = 0;
  for (const e of entries) {
    for (const s of Object.values(e.seasons ?? {})) {
      n += (s.episodes ?? []).length;
    }
  }
  return n;
}

export function SonarrView({ active }: SonarrViewProps): JSX.Element {
  const { push } = useToast();
  const {
    value: globalSearch,
    setValue: setGlobalSearch,
    register,
    clearHandler,
  } = useSearch();
  const { liveArr } = useWebUI();

  const [instances, setInstances] = useState<ArrInfo[]>([]);
  const [selection, setSelection] = useState<string | "">("");
  const [instanceData, setInstanceData] =
    useState<SonarrSeriesResponse | null>(null);
  const [instancePage, setInstancePage] = useState(0);
  const [instanceQuery, setInstanceQuery] = useState("");
  const [instanceLoading, setInstanceLoading] = useState(false);
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
  const prevSelectionRef = useRef<string | "">(selection);

  const [aggRows, setAggRows] = useState<SonarrAggRow[]>([]);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggPage, setAggPage] = useState(0);
  const [aggFilter, setAggFilter] = useState("");
  const [aggUpdated, setAggUpdated] = useState<string | null>(null);
  const debouncedAggFilter = useDebounce(aggFilter, 300);

  // Smart data sync for aggregate episodes
  const aggEpisodeSync = useDataSync<SonarrAggRow>({
    getKey: (ep) => `${ep.__instance}-${ep.series}-${ep.season}-${ep.episode}`,
    hashFields: [
      "__instance",
      "series",
      "season",
      "episode",
      "title",
      "hasFile",
      "monitored",
      "airDate",
      "reason",
      "qualityProfileId",
      "qualityProfileName",
      "seriesId",
    ],
  });

  const [onlyMissing, setOnlyMissing] = useState(false);
  const prevOnlyMissingRef = useRef(onlyMissing);
  const [reasonFilter, setReasonFilter] = useState<string>("all");
  const [aggSummary, setAggSummary] = useState<{
    available: number;
    monitored: number;
    missing: number;
    total: number;
  }>({ available: 0, monitored: 0, missing: 0, total: 0 });

  const { mode: sonarrBrowseMode, setMode: setSonarrBrowseMode } =
    useArrBrowseMode("sonarr");
  const [sonarrGroupDetail, setSonarrGroupDetail] = useState<{
    instance: string;
    series: string;
    qualityProfileName?: string | null;
    seriesId?: number;
    episodes: SonarrAggRow[];
  } | null>(null);

  // LiveArr and GroupSonarr are now loaded via WebUIContext, no need to load config here

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
      const { preloadAll = false, showLoading = true, missingOnly } = options;
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
      const aggregated: SonarrAggRow[] = [];
      let totalAvailable = 0;
      let totalMonitored = 0;
      let totalMissing = 0;
      let progressFirstPaint = false;
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
            const seriesId = (entry.series?.["id"] as number | undefined) ?? undefined;
            const qualityProfileId = entry.series?.qualityProfileId ?? null;
            const qualityProfileName = entry.series?.qualityProfileName ?? null;
            Object.entries(entry.seasons ?? {}).forEach(
              ([seasonNumber, season]) => {
                (season.episodes ?? []).forEach((episode: SonarrEpisode) => {
                  const episodeReason = (episode.reason as string | null | undefined) ?? null;
                  aggregated.push({
                    __instance: label,
                    series: title,
                    season: seasonNumber,
                    episode: episode.episodeNumber ?? "",
                    title: episode.title ?? "",
                    monitored: !!episode.monitored,
                    hasFile: !!episode.hasFile,
                    airDate: episode.airDateUtc ?? "",
                    reason: episodeReason,
                    qualityProfileId,
                    qualityProfileName,
                    seriesId,
                  });
                });
              }
            );
          });
          const episodeSyncResult = aggEpisodeSync.syncData(aggregated);
          if (episodeSyncResult.hasChanges) {
            setAggRows(episodeSyncResult.data);
          }
          if (showLoading && !progressFirstPaint && episodeSyncResult.data.length > 0) {
            setAggLoading(false);
            progressFirstPaint = true;
          }
          if (!series.length || series.length < SONARR_AGG_FETCH_SIZE) {
            break;
          }
          page += 1;
        }
      }

      const syncResult = aggEpisodeSync.syncData(aggregated);
      const rowsChanged = syncResult.hasChanges;

      if (rowsChanged) {
        setAggRows(syncResult.data);
      }

      const newSummary = {
        available: totalAvailable,
        monitored: totalMonitored,
        missing: totalMissing,
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
          : "Failed to load aggregated Sonarr data",
        "error"
      );
    } finally {
      setAggLoading(false);
    }
  }, [instances, globalSearch, push, onlyMissing, aggFilter, aggSummary]);

  useEffect(() => {
    if (!active) return;
    void loadInstances();
  }, [active, loadInstances]);

  useEffect(() => {
    if (!active) return;
    if (!selection || selection === "aggregate") return;

    const selectionChanged = prevSelectionRef.current !== selection;
    const onlyMissingChanged = prevOnlyMissingRef.current !== onlyMissing;

    // Reset page only when selection changes, not when filters change
    if (selectionChanged) {
      setInstancePage(0);
      prevSelectionRef.current = selection;
    }

    // Update ref for next comparison
    if (onlyMissingChanged) {
      prevOnlyMissingRef.current = onlyMissing;
    }

    // Fetch data: use page 0 if selection changed, current page otherwise
    const query = globalSearchRef.current;
    void fetchInstance(selection, selectionChanged ? 0 : instancePage, query, {
      preloadAll: false,
      showLoading: true,
      missingOnly: onlyMissing,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- instancePage excluded to prevent infinite loop
  }, [active, selection, onlyMissing, fetchInstance]);

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
          preloadAll: false,
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
    // Combine all filters into a single pass for better performance
    const q = debouncedAggFilter ? debouncedAggFilter.toLowerCase() : "";
    const hasSearchFilter = Boolean(q);
    const hasReasonFilter = reasonFilter !== "all";

    return aggRows.filter((row) => {
      // Search filter
      if (hasSearchFilter) {
        const series = row.series.toLowerCase();
        const title = row.title.toLowerCase();
        const instance = row.__instance.toLowerCase();
        if (!series.includes(q) && !title.includes(q) && !instance.includes(q)) {
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

  const isAggFiltered = Boolean(debouncedAggFilter) || onlyMissing || reasonFilter !== "all";

  const aggPages = Math.max(
    1,
    Math.ceil(filteredAggRows.length / SONARR_AGG_PAGE_SIZE)
  );
  const allSeries = useMemo(() => {
    const pages = Object.keys(instancePages)
      .map(Number)
      .sort((a, b) => a - b);
    const rows: SonarrSeriesEntry[] = [];
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
      <div className="card-header">Sonarr</div>
      <div className="card-body">
        <div className="split">
          <aside className="pane sidebar">
            {instances.length > 1 && (
              <button
                className={`btn ${isAggregate ? "active" : ""}`}
                onClick={() => setSelection("aggregate")}
              >
                All Sonarr
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
                {instances.length > 1 && <option value="aggregate">All Sonarr</option>}
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
                  placeholder="Filter series or episodes"
                  value={globalSearch}
                  onChange={(event) => setGlobalSearch(event.target.value)}
                />
              </div>
              <div className="field" style={{ flex: "0 0 auto", minWidth: "140px" }}>
                <label>Status</label>
                <select
                  onChange={(event) => {
                    const value = event.target.value;
                    const newMissingState = value === "missing";
                    setOnlyMissing(newMissingState);
                    // Trigger refetch when filter changes for instance views
                    if (selection && selection !== "aggregate") {
                      void fetchInstance(selection, 0, globalSearchRef.current || "", {
                        preloadAll: false,
                        showLoading: true,
                        missingOnly: newMissingState,
                      });
                    }
                  }}
                  value={onlyMissing ? "missing" : "all"}
                >
                  <option value="all">All Episodes</option>
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
                  mode={sonarrBrowseMode}
                  onChange={setSonarrBrowseMode}
                  idPrefix="sonarr"
                />
              </div>
            </div>

            {isAggregate ? (
              <SonarrAggregateView
                loading={aggLoading}
                rows={filteredAggRows}
                total={filteredAggRows.length}
                page={aggPage}
                totalPages={aggPages}
                onPageChange={setAggPage}
                onRefresh={() => void loadAggregate({ showLoading: true })}
                lastUpdated={aggUpdated}
                summary={aggSummary}
                instanceCount={instances.length}
                isAggFiltered={isAggFiltered}
                browseMode={sonarrBrowseMode}
                instances={instances}
                onSeriesSelect={(g) => setSonarrGroupDetail(g)}
              />
            ) : (
              <SonarrInstanceView
                loading={instanceLoading}
                counts={instanceData?.counts ?? null}
                series={allSeries}
                page={instancePage}
                pageSize={instancePageSize}
                totalPages={instanceTotalPages}
                totalItems={instanceTotalItems}
                onlyMissing={onlyMissing}
                reasonFilter={reasonFilter}
                searchQuery={globalSearch}
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
                instanceLabel={
                  instances.find((i) => i.category === selection)?.name ||
                  (selection as string)
                }
                selectionCategory={selection as string}
                browseMode={sonarrBrowseMode}
                onSeriesSelect={(g) => setSonarrGroupDetail(g)}
              />
            )}
          </div>
        </div>
      </div>
      {sonarrGroupDetail ? (
        <ArrModal
          title={sonarrGroupDetail.series}
          onClose={() => setSonarrGroupDetail(null)}
          maxWidth={720}
        >
          <SonarrSeriesGroupDetailBody group={sonarrGroupDetail} />
        </ArrModal>
      ) : null}
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
  summary: { available: number; monitored: number; missing: number; total: number };
  instanceCount: number;
  isAggFiltered?: boolean;
  browseMode: "list" | "icon";
  instances: ArrInfo[];
  onSeriesSelect: (group: {
    instance: string;
    series: string;
    qualityProfileName?: string | null;
    seriesId?: number;
    episodes: SonarrAggRow[];
  }) => void;
}

function sonarrCategoryForInstance(instances: ArrInfo[], label: string): string {
  const inst = instances.find(
    (i) => (i.name || i.category) === label || i.category === label
  );
  return inst?.category ?? instances[0]?.category ?? "";
}

function SonarrAggregateView({
  loading,
  rows,
  page,
  totalPages: _totalPagesProp,
  onPageChange,
  onRefresh,
  lastUpdated,
  summary,
  instanceCount,
  isAggFiltered = false,
  browseMode,
  instances,
  onSeriesSelect,
}: SonarrAggregateViewProps): JSX.Element {
  const pageSize = 50;
  const seriesGroups = useMemo(() => {
    const m = new Map<
      string,
      {
        instance: string;
        series: string;
        qualityProfileName?: string | null;
        seriesId?: number;
        episodes: SonarrAggRow[];
      }
    >();
    for (const r of rows) {
      const k = `${r.__instance}::${r.series}`;
      const g = m.get(k);
      if (!g) {
        m.set(k, {
          instance: r.__instance,
          series: r.series,
          qualityProfileName: r.qualityProfileName,
          seriesId: r.seriesId,
          episodes: [r],
        });
      } else {
        g.episodes.push(r);
      }
    }
    return Array.from(m.values());
  }, [rows]);

  const totalSeries = seriesGroups.length;
  const seriesTotalPages = Math.max(1, Math.ceil(totalSeries / pageSize));
  const safePage = Math.min(page, seriesTotalPages - 1);
  const pageSlice = useMemo(
    () =>
      seriesGroups.slice(safePage * pageSize, safePage * pageSize + pageSize),
    [seriesGroups, safePage, pageSize]
  );

  const listColumns = useMemo<ColumnDef<(typeof pageSlice)[number]>[]>(
    () => [
      ...(instanceCount > 1
        ? [
            {
              accessorKey: "instance" as const,
              header: "Instance",
              cell: (info: { getValue: () => unknown }) =>
                String(info.getValue() ?? ""),
            },
          ]
        : []),
      {
        accessorKey: "series" as const,
        header: "Series",
        cell: (info: { getValue: () => unknown }) =>
          String(info.getValue() ?? ""),
      },
      {
        id: "episodes",
        header: "Episodes",
        cell: ({
          row,
        }: {
          row: { original: (typeof pageSlice)[number] };
        }) => row.original.episodes.length,
      },
      {
        accessorKey: "qualityProfileName" as const,
        header: "Quality profile",
        cell: (info: { getValue: () => unknown }) =>
          (info.getValue() as string | null | undefined) || "—",
      },
    ],
    [instanceCount]
  );

  const table = useReactTable({
    data: pageSlice,
    columns: listColumns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          Aggregated episodes across all instances{" "}
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
          })}{" "}
          • <strong>Total Episodes:</strong>{" "}
          {summary.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          {isAggFiltered && rows.length < summary.total && (
            <>
              {" "}
              • <strong>Filtered:</strong>{" "}
              {rows.length.toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}{" "}
              of{" "}
              {summary.total.toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}
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
          <span className="spinner" /> Loading Sonarr library…
        </div>
      ) : !loading && summary.total === 0 && instanceCount > 0 ? (
        <div className="hint">
          <p>No episodes found in the database.</p>
          <p>
            The backend may still be initializing and syncing data from your
            Sonarr instances. Please check the logs or wait a few moments and
            refresh.
          </p>
        </div>
      ) : !seriesGroups.length ? (
        <div className="hint">No series found.</div>
      ) : browseMode === "list" ? (
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
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={`${row.original.instance}-${row.original.series}`}
                  style={{ cursor: "pointer" }}
                  onClick={() => onSeriesSelect(row.original)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      data-label={String(cell.column.columnDef.header)}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="arr-icon-grid">
          {pageSlice.map((g) => {
            const cat = sonarrCategoryForInstance(instances, g.instance);
            const sid = g.seriesId;
            const thumb =
              sid != null && cat
                ? sonarrSeriesThumbnailUrl(cat, sid)
                : "";
            return (
              <button
                key={`${g.instance}-${g.series}`}
                type="button"
                className="arr-movie-tile card"
                onClick={() => onSeriesSelect(g)}
              >
                {thumb ? (
                  <ArrPosterImage
                    className="arr-movie-tile__poster"
                    src={thumb}
                    alt=""
                  />
                ) : (
                  <div
                    className="arr-movie-tile__poster arr-poster-fallback"
                    aria-hidden
                  />
                )}
                <div className="arr-movie-tile__meta">
                  {instanceCount > 1 && (
                    <div className="arr-movie-tile__instance">{g.instance}</div>
                  )}
                  <div className="arr-movie-tile__title">{g.series}</div>
                  <div className="arr-movie-tile__sub">
                    {g.episodes.length} ep. • {g.qualityProfileName ?? "—"}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
      {seriesGroups.length > 0 && (
        <div className="pagination">
          <div>
            Page {safePage + 1} of {seriesTotalPages} ({totalSeries} series · page
            size {pageSize})
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
              onClick={() =>
                onPageChange(Math.min(seriesTotalPages - 1, safePage + 1))
              }
              disabled={safePage >= seriesTotalPages - 1 || loading}
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
  reasonFilter: string;
  searchQuery: string;
  onPageChange: (page: number) => void;
  onRestart: () => void;
  lastUpdated: string | null;
  instanceLabel: string;
  selectionCategory: string;
  browseMode: "list" | "icon";
  onSeriesSelect: (group: SonarrSeriesGroup) => void;
}

const SonarrInstanceView = memo(function SonarrInstanceView({
  loading,
  counts,
  series,
  page,
  pageSize,
  totalPages,
  onlyMissing,
  reasonFilter,
  searchQuery,
  onPageChange,
  onRestart,
  lastUpdated,
  instanceLabel,
  selectionCategory,
  browseMode,
  onSeriesSelect,
}: SonarrInstanceViewProps): JSX.Element {
  const totalEpisodes = useMemo(
    () => countEpisodesInSeriesList(series),
    [series]
  );

  const filteredSeries = useMemo(() => {
    const missingFiltered = filterSeriesEntriesForMissing(series, onlyMissing);
    const withReason: SonarrSeriesEntry[] = [];
    for (const e of missingFiltered) {
      const f = filterSeriesEntryByReason(e, reasonFilter);
      if (f) {
        withReason.push(f);
      }
    }
    const q = searchQuery.trim().toLowerCase();
    if (!q) {
      return withReason;
    }
    return withReason.filter((e) => {
      const t = (e.series?.["title"] as string | undefined) || "";
      return t.toLowerCase().includes(q);
    });
  }, [series, onlyMissing, reasonFilter, searchQuery]);

  const seriesGroups = useMemo(
    () => filteredSeries.map((e) => seriesEntryToGroup(e, instanceLabel)),
    [filteredSeries, instanceLabel]
  );

  const paged = useMemo(
    () =>
      seriesGroups.slice(
        page * pageSize,
        page * pageSize + pageSize
      ),
    [seriesGroups, page, pageSize]
  );

  const filteredEpCount = useMemo(
    () => countEpisodesInSeriesList(filteredSeries),
    [filteredSeries]
  );

  const isFiltered =
    onlyMissing ||
    reasonFilter !== "all" ||
    searchQuery.trim().length > 0;

  const listColumns = useMemo<ColumnDef<SonarrSeriesGroup>[]>(
    () => [
      {
        accessorKey: "series" as const,
        header: "Series",
        cell: (info) => String(info.getValue() ?? ""),
      },
      {
        id: "episodes",
        header: "Episodes",
        cell: ({ row }) => row.original.episodes.length,
      },
      {
        accessorKey: "qualityProfileName" as const,
        header: "Quality profile",
        cell: (info) =>
          (info.getValue() as string | null | undefined) || "—",
      },
    ],
    []
  );

  const table = useReactTable({
    data: paged,
    columns: listColumns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          {counts ? (
            <>
              <strong>Available:</strong>{" "}
              {counts.available.toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}{" "}
              • <strong>Monitored:</strong>{" "}
              {counts.monitored.toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}{" "}
              • <strong>Missing:</strong>{" "}
              {(counts.missing ?? 0).toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}{" "}
              • <strong>Total Episodes:</strong>{" "}
              {totalEpisodes.toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}
              {isFiltered && filteredEpCount < totalEpisodes && (
                <>
                  {" "}
                  • <strong>Filtered:</strong>{" "}
                  {filteredEpCount.toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}{" "}
                  of{" "}
                  {totalEpisodes.toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}
                </>
              )}
            </>
          ) : (
            "Loading series information..."
          )}
          {lastUpdated ? ` (updated ${lastUpdated})` : ""}
        </div>
        <button className="btn ghost" onClick={onRestart} disabled={loading}>
          <IconImage src={RefreshIcon} />
          Restart
        </button>
      </div>
      {loading ? (
        <div className="loading">
          <span className="spinner" /> Loading series…
        </div>
      ) : !loading && series.length > 0 && totalEpisodes === 0 ? (
        <div className="hint">
          <p>No episodes found for these series.</p>
          <p>
            The backend may still be syncing episode data from Sonarr. Check the
            logs or wait a few moments and refresh.
          </p>
        </div>
      ) : !loading && totalEpisodes > 0 && filteredEpCount === 0 ? (
        <div className="hint">No episodes match the current filter.</div>
      ) : series.length > 0 && seriesGroups.length > 0 ? (
        browseMode === "list" ? (
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
                {table.getRowModel().rows.map((row) => (
                  <tr
                    key={`${row.original.instance}-${row.original.series}`}
                    style={{ cursor: "pointer" }}
                    onClick={() => onSeriesSelect(row.original)}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td
                        key={cell.id}
                        data-label={String(cell.column.columnDef.header)}
                      >
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="arr-icon-grid">
            {paged.map((g) => {
              const sid = g.seriesId;
              const thumb =
                sid != null && selectionCategory
                  ? sonarrSeriesThumbnailUrl(selectionCategory, sid)
                  : "";
              return (
                <button
                  key={`${g.series}-${g.seriesId ?? 0}`}
                  type="button"
                  className="arr-movie-tile card"
                  onClick={() => onSeriesSelect(g)}
                >
                  {thumb ? (
                    <ArrPosterImage
                      className="arr-movie-tile__poster"
                      src={thumb}
                      alt=""
                    />
                  ) : (
                    <div
                      className="arr-movie-tile__poster arr-poster-fallback"
                      aria-hidden
                    />
                  )}
                  <div className="arr-movie-tile__meta">
                    <div className="arr-movie-tile__title">{g.series}</div>
                    <div className="arr-movie-tile__sub">
                      {g.episodes.length} ep. • {g.qualityProfileName ?? "—"}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )
      ) : (
        <div className="hint">No series found.</div>
      )}
      {seriesGroups.length > pageSize && (
        <div className="pagination">
          <div>
            Page {page + 1} of {totalPages} (
            {seriesGroups.length.toLocaleString()} series · page size {pageSize})
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
              onClick={() =>
                onPageChange(Math.min(totalPages - 1, page + 1))
              }
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
