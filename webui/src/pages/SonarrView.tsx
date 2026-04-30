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
  getSonarrSeries,
} from "../api/client";
import type { ColumnDef } from "@tanstack/react-table";
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
import { useRowSnapshot, useRowsStore } from "../hooks/useRowsStore";
import { arraysEqual } from "../utils/dataSync";
import { StableTable } from "../components/StableTable";

/** Matches `arraysEqual` / dataSync `Hashable` while keeping typed Sonarr API fields */
type SonarrSeriesComparable = SonarrSeriesEntry & Record<string, unknown>;

/**
 * Row-store payload for the Sonarr series-group browse table.
 *
 * The `& Record<string, unknown>` index signature is what makes the value satisfy the
 * `Hashable` constraint shared by `RowsStore` / `useRowsStore`.  Field-wise it is
 * identical to `SonarrSeriesGroup`.
 */
type SonarrSeriesGroupRow = SonarrSeriesGroup & Record<string, unknown>;
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
import {
  AGGREGATE_FETCH_CHUNK_SIZE,
  AGGREGATE_POLL_INTERVAL_MS,
  INSTANCE_VIEW_POLL_INTERVAL_MS,
  pagesFromAggregateTotal,
  summarizeAggregateMonitoredRows,
  AGG_FALLBACK_AGGREGATE_PAGES_MAX,
} from "../constants/arrAggregateFetch";

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

/** Stable key for incremental instance-page compares (arraysEqual order-invariant hashes). */
function getSonarrSeriesEntryKey(entry: SonarrSeriesComparable): string {
  const id = entry.series?.["id"];
  if (typeof id === "number" && Number.isFinite(id)) {
    return `id:${id}`;
  }
  return `t:${String(entry.series?.["title"] ?? "")}`;
}

const SONARR_INSTANCE_HASH_FIELDS: (keyof SonarrSeriesComparable)[] = [
  "seasons",
  "series",
  "totals",
];

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

interface SonarrDetailModalProps {
  detail: {
    id: string;
    source: "instance" | "aggregate";
    seedGroup: SonarrSeriesGroup;
  };
  instanceStore: import("../utils/rowsStore").RowsStore<SonarrSeriesGroupRow>;
  aggregateStore: import("../utils/rowsStore").RowsStore<SonarrSeriesGroupRow>;
  onClose: () => void;
}

/**
 * Series-group modal that lives outside the table render path.  Subscribes by id so
 * polls bring fresh episode states (hasFile / monitored / etc.) into the open modal
 * without closing it or rebuilding any sibling row.
 */
const SonarrDetailModal = memo(function SonarrDetailModal({
  detail,
  instanceStore,
  aggregateStore,
  onClose,
}: SonarrDetailModalProps): JSX.Element {
  const instanceFresh = useRowSnapshot(
    instanceStore,
    detail.source === "instance" ? detail.id : null,
  );
  const aggregateFresh = useRowSnapshot(
    aggregateStore,
    detail.source === "aggregate" ? detail.id : null,
  );
  const liveGroup =
    (detail.source === "instance" ? instanceFresh : aggregateFresh) ??
    detail.seedGroup;

  return (
    <ArrModal title={liveGroup.series} onClose={onClose} maxWidth={720}>
      <SonarrSeriesGroupDetailBody group={liveGroup} />
    </ArrModal>
  );
});

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
  globalSearchRef.current = globalSearch;
  const selectionRef = useRef(selection);
  selectionRef.current = selection;
  const backendReadyWarnedRef = useRef(false);
  const aggFetchGenRef = useRef(0);
  const aggActiveLoadsRef = useRef(0);
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

  // Surgical row stores: same rationale as RadarrView — keep `rowOrder` stable on
  // update-only polls so the series-group browse table doesn't re-render every cell on
  // every tick.  Hashing `episodes` JSON catches any deep change inside the group (e.g. an
  // episode flipping `hasFile`) so the row's version still bumps.
  const sonarrInstanceRowsStoreOpts = useMemo(
    () => ({
      getKey: (g: SonarrSeriesGroupRow) => `${g.instance}::${g.series}`,
      hashFields: [
        "instance",
        "series",
        "qualityProfileName",
        "seriesId",
        "episodes",
      ] as const,
    }),
    [],
  );
  const instanceGroupRowsStore = useRowsStore<SonarrSeriesGroupRow>(
    sonarrInstanceRowsStoreOpts as never,
  );
  const aggGroupRowsStore = useRowsStore<SonarrSeriesGroupRow>(
    sonarrInstanceRowsStoreOpts as never,
  );

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
  // Track id + source so the modal can subscribe to the correct row store and live-update
  // when polling brings in fresh episode data without closing the modal.  `seedGroup` is
  // the row at click-time so the modal has something to render before the first store
  // hit (and as a fallback if the row is filtered out / removed mid-view).
  const [sonarrGroupDetail, setSonarrGroupDetail] = useState<{
    id: string;
    source: "instance" | "aggregate";
    seedGroup: SonarrSeriesGroup;
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
          : "Unable to load Sonarr instances",
        "error"
      );
    }
  }, [push]);

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
        const prevSlice = prevPages[resolvedPage] ?? [];
        const pageChanged =
          keyChanged ||
          !arraysEqual<SonarrSeriesComparable>(
            prevSlice as SonarrSeriesComparable[],
            series as SonarrSeriesComparable[],
            getSonarrSeriesEntryKey,
            SONARR_INSTANCE_HASH_FIELDS,
          );

        const nextPages = { ...prevPages, [resolvedPage]: series };
        instancePagesRef.current = nextPages;
        if (pageChanged) {
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
          if (countsChanged || pageChanged) {
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

        if (pageChanged) {
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
              const prevPg = currentPages[pageIndex] ?? [];
              if (
                arraysEqual<SonarrSeriesComparable>(
                  prevPg as SonarrSeriesComparable[],
                  pageSeries as SonarrSeriesComparable[],
                  getSonarrSeriesEntryKey,
                  SONARR_INSTANCE_HASH_FIELDS,
                )
              ) {
                instancePagesRef.current = {
                  ...currentPages,
                  [pageIndex]: pageSeries,
                };
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
      const aggregated: SonarrAggRow[] = [];
      let progressFirstPaint = false;
      for (const inst of instances) {
        const label = inst.name || inst.category;
        let countedForInstance = false;
        let pagesPlanned: number | null = null;
        let pageIdx = 0;

        while (true) {
          const res = await getSonarrSeries(
            inst.category,
            pageIdx,
            chunk,
            "",
            { missingOnly: onlyMissing }
          );
          if (gen !== aggFetchGenRef.current) {
            return;
          }

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
          if (showLoading && !progressFirstPaint && aggregated.length > 0) {
            setAggLoading(false);
            progressFirstPaint = true;
          }

          pageIdx += 1;

          if (pagesPlanned !== null) {
            if (pageIdx >= pagesPlanned) break;
          } else {
            if (!series.length || series.length < chunk) break;
            if (pageIdx >= AGG_FALLBACK_AGGREGATE_PAGES_MAX) break;
          }
        }
      }

      const syncResult = aggEpisodeSync.syncData(aggregated);
      const rowsChanged = syncResult.hasChanges;

      if (rowsChanged) {
        setAggRows(syncResult.data);
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
          : "Failed to load aggregated Sonarr data",
        "error"
      );
    } finally {
      aggActiveLoadsRef.current -= 1;
      if (gen === aggFetchGenRef.current) {
        setAggLoading(false);
      }
    }
  }, [instances, globalSearch, push, onlyMissing, aggFilter]);

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
    void fetchInstanceRef.current(selection, selectionChanged ? 0 : instancePage, query, {
      preloadAll: false,
      showLoading: true,
      missingOnly: onlyMissing,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- instancePage excluded to prevent infinite loop; fetch identity via fetchInstanceRef
  }, [active, selection, onlyMissing]);

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
          missingOnly: onlyMissing,
        });
      }
    };
    register(handler);
    return () => clearHandler(handler);
  }, [active, selection, register, clearHandler, onlyMissing]);

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
          missingOnly: onlyMissing,
        });
      }
    },
    active && selection && selection !== "aggregate" && liveArr
      ? INSTANCE_VIEW_POLL_INTERVAL_MS
      : null
  );

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

  const instanceLabelForSelection = useMemo(
    () =>
      instances.find((i) => i.category === selection)?.name ||
      (selection as string),
    [instances, selection],
  );

  // Filter + paginate the instance series list at parent level so we can sync the visible
  // page slice into the surgical row store.  Mirrors the same logic that
  // `SonarrInstanceView` runs internally — keeping both in sync is what guarantees the
  // store sees the rows the user actually sees.
  const instanceSeriesGroupsVisiblePage = useMemo<SonarrSeriesGroupRow[]>(() => {
    const missingFiltered = filterSeriesEntriesForMissing(allSeries, onlyMissing);
    const withReason: SonarrSeriesEntry[] = [];
    for (const entry of missingFiltered) {
      const f = filterSeriesEntryByReason(entry, reasonFilter);
      if (f) withReason.push(f);
    }
    const q = globalSearch.trim().toLowerCase();
    const filtered = q
      ? withReason.filter((e) => {
          const t = (e.series?.["title"] as string | undefined) || "";
          return t.toLowerCase().includes(q);
        })
      : withReason;
    const groups = filtered.map((e) =>
      seriesEntryToGroup(e, instanceLabelForSelection),
    );
    return groups
      .slice(
        instancePage * instancePageSize,
        instancePage * instancePageSize + instancePageSize,
      )
      .map((g) => g as SonarrSeriesGroupRow);
  }, [
    allSeries,
    onlyMissing,
    reasonFilter,
    globalSearch,
    instanceLabelForSelection,
    instancePage,
    instancePageSize,
  ]);

  useEffect(() => {
    instanceGroupRowsStore.store.sync(instanceSeriesGroupsVisiblePage);
  }, [instanceSeriesGroupsVisiblePage, instanceGroupRowsStore.store]);

  // Reset the per-instance row store on selection change to avoid leaking groups from the
  // previous instance when the next fetch is still in flight.
  useEffect(() => {
    instanceGroupRowsStore.store.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);

  // Aggregate row-store sync.  Build per-series groups from the filtered episode list,
  // then slice to the current page exactly like SonarrAggregateView does.
  const aggSeriesGroupsVisiblePage = useMemo<SonarrSeriesGroupRow[]>(() => {
    const m = new Map<string, SonarrSeriesGroup>();
    for (const r of filteredAggRows) {
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
    const groups = Array.from(m.values());
    return groups
      .slice(
        aggPage * SONARR_AGG_PAGE_SIZE,
        aggPage * SONARR_AGG_PAGE_SIZE + SONARR_AGG_PAGE_SIZE,
      )
      .map((g) => g as SonarrSeriesGroupRow);
  }, [filteredAggRows, aggPage]);

  useEffect(() => {
    aggGroupRowsStore.store.sync(aggSeriesGroupsVisiblePage);
  }, [aggSeriesGroupsVisiblePage, aggGroupRowsStore.store]);

  const handleInstanceRefresh = useCallback(() => {
    if (!selection || selection === "aggregate") return;
    void fetchInstanceRef.current(selection, instancePage, instanceQuery, {
      preloadAll: false,
      showLoading: true,
    });
  }, [selection, instancePage, instanceQuery]);

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
                      void fetchInstanceRef.current(selection, 0, globalSearchRef.current || "", {
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
                rowOrder={aggGroupRowsStore.snapshot.rowOrder}
                rowsStore={aggGroupRowsStore.store}
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
                onSeriesSelect={(g) => {
                  const id = `${g.instance}::${g.series}`;
                  setSonarrGroupDetail({
                    id,
                    source: "aggregate",
                    seedGroup: g,
                  });
                }}
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
                rowOrder={instanceGroupRowsStore.snapshot.rowOrder}
                rowsStore={instanceGroupRowsStore.store}
                onPageChange={(page) => {
                  setInstancePage(page);
                  void fetchInstanceRef.current(selection as string, page, instanceQuery, {
                    preloadAll: false,
                    showLoading: true,
                    missingOnly: onlyMissing,
                  });
                }}
                onRefresh={() => void handleInstanceRefresh()}
                lastUpdated={lastUpdated}
                instanceLabel={instanceLabelForSelection}
                selectionCategory={selection as string}
                browseMode={sonarrBrowseMode}
                onSeriesSelect={(g) => {
                  const id = `${g.instance}::${g.series}`;
                  setSonarrGroupDetail({
                    id,
                    source: "instance",
                    seedGroup: g,
                  });
                }}
              />
            )}
          </div>
        </div>
      </div>
      {sonarrGroupDetail ? (
        <SonarrDetailModal
          detail={sonarrGroupDetail}
          instanceStore={instanceGroupRowsStore.store}
          aggregateStore={aggGroupRowsStore.store}
          onClose={() => setSonarrGroupDetail(null)}
        />
      ) : null}
    </section>
  );
}

interface SonarrAggregateViewProps {
  loading: boolean;
  rows: SonarrAggRow[];
  rowOrder: readonly string[];
  rowsStore: import("../utils/rowsStore").RowsStore<SonarrSeriesGroupRow>;
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
  onSeriesSelect: (group: SonarrSeriesGroup) => void;
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
  rowOrder,
  rowsStore,
  total,
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
  // Total/page metadata for the pagination footer + grid mode.  Note: the row store /
  // StableTable already drives the list-mode rendering, so this only computes counts and
  // the icon-grid slice — the list table no longer holds its own copy of pageSlice.
  const seriesGroups = useMemo(() => {
    const m = new Map<string, SonarrSeriesGroup>();
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

  const listColumns = useMemo<ColumnDef<SonarrSeriesGroupRow>[]>(
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
          row: { original: SonarrSeriesGroupRow };
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

  const handleListRowClick = useCallback(
    (group: SonarrSeriesGroupRow) => {
      onSeriesSelect(group);
    },
    [onSeriesSelect],
  );

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
      ) : !loading &&
        total === 0 &&
        summary.total === 0 &&
        instanceCount > 0 ? (
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
        <StableTable<SonarrSeriesGroupRow>
          rowsStore={rowsStore}
          rowOrder={rowOrder}
          columns={listColumns}
          getRowKey={(g) => `${g.instance}::${g.series}`}
          onRowClick={handleListRowClick}
        />
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
                key={`${g.instance}-${String(g.seriesId ?? "")}-${g.series}`}
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
                  <div className="arr-movie-tile__stats">
                    {g.episodes.length} ep.
                  </div>
                  <div className="arr-movie-tile__quality">
                    {g.qualityProfileName ?? "—"}
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
  rowOrder: readonly string[];
  rowsStore: import("../utils/rowsStore").RowsStore<SonarrSeriesGroupRow>;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
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
  totalItems,
  onlyMissing,
  reasonFilter,
  searchQuery,
  rowOrder,
  rowsStore,
  onPageChange,
  onRefresh,
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

  const listColumns = useMemo<ColumnDef<SonarrSeriesGroupRow>[]>(
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

  const handleListRowClick = useCallback(
    (group: SonarrSeriesGroupRow) => {
      onSeriesSelect(group);
    },
    [onSeriesSelect],
  );

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
          {series.length > 0 &&
          totalEpisodes === 0 &&
          !isFiltered &&
          seriesGroups.length > 0 ? (
            <>
              {" "}
              <span className="hint">
                Episode rows may fill in as the catalog syncs.
              </span>
            </>
          ) : null}
        </div>
        <button className="btn ghost" type="button" onClick={onRefresh} disabled={loading}>
          <IconImage src={RefreshIcon} />
          Refresh
        </button>
      </div>
      {loading ? (
        <div className="loading">
          <span className="spinner" /> Loading series…
        </div>
      ) : !loading && series.length === 0 && totalItems === 0 ? (
        <div className="hint">
          <p>No series rows in the local catalog yet.</p>
          <p>
            qBitrr may still be importing Sonarr metadata into SQLite. Check logs or retry shortly.
          </p>
        </div>
      ) : !loading && totalEpisodes > 0 && filteredEpCount === 0 ? (
        <div className="hint">No episodes match the current filter.</div>
      ) : series.length > 0 && seriesGroups.length > 0 ? (
        browseMode === "list" ? (
          <StableTable<SonarrSeriesGroupRow>
            rowsStore={rowsStore}
            rowOrder={rowOrder}
            columns={listColumns}
            getRowKey={(g) => `${g.instance}::${g.series}`}
            onRowClick={handleListRowClick}
          />
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
                  key={`${g.instance}-${String(g.seriesId ?? "")}-${g.series}`}
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
                    <div className="arr-movie-tile__stats">
                      {g.episodes.length} ep.
                    </div>
                    <div className="arr-movie-tile__quality">
                      {g.qualityProfileName ?? "—"}
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
