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
import type {
  ArrInfo,
  SonarrSeason,
  SonarrSeriesEntry,
  SonarrSeriesResponse,
} from "../../api/types";
import { ArrMiniProgress } from "../../components/arr/ArrMiniProgress";
import {
  type SonarrSeriesGroup,
  SonarrSeriesGroupDetailBody,
} from "../../components/arr/SonarrSeriesGroupDetailBody";
import { StableTable } from "../../components/StableTable";
import { INSTANCE_VIEW_POLL_INTERVAL_MS } from "../../constants/arrAggregateFetch";
import { ARR_CATALOG_SYNC_HINT } from "../../constants/arrCatalogMessages";
import { useInterval } from "../../hooks/useInterval";
import { useRowsStore } from "../../hooks/useRowsStore";
import { arraysEqual } from "../../utils/dataSync";
import { sonarrSeriesThumbnailUrl } from "../../utils/arrThumbnailUrl";
import type { RowsStore } from "../../utils/rowsStore";
import { ArrCatalogIconTile } from "./ArrCatalogIconTile";
import {
  ArrCatalogBodyChrome,
  ArrCatalogPagination,
} from "./ArrCatalogBodyChrome";
import type {
  ArrCatalogDefinition,
  ArrCatalogInstancePipelineParams,
  ArrCatalogInstancePipelineState,
  ArrCatalogSummary,
} from "./definition";
import { ARR_CATALOG_REGISTRY } from "./registry";
import { categoryForInstanceLabel } from "./utils";

const SONARR_PAGE_SIZE = 25;

interface SonarrFilters extends Record<string, unknown> {
  readonly onlyMissing: boolean;
  readonly reasonFilter: string;
}

type SonarrSeriesGroupRow = SonarrSeriesGroup & Record<string, unknown>;

const SONARR_GROUP_HASH_FIELDS = [
  "instance",
  "series",
  "qualityProfileName",
  "seriesId",
  "episodes",
] as const;

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

function filterSeriesEntriesForMissing(
  seriesEntries: SonarrSeriesEntry[],
  onlyMissing: boolean,
): SonarrSeriesEntry[] {
  if (!onlyMissing) return seriesEntries;
  const result: SonarrSeriesEntry[] = [];
  for (const entry of seriesEntries) {
    const seasons = entry.seasons ?? {};
    const filteredSeasons: Record<string, SonarrSeason> = {};
    for (const [seasonNumber, season] of Object.entries(seasons)) {
      const episodes = (season.episodes ?? []).filter((ep) => !ep.hasFile);
      if (!episodes.length) continue;
      filteredSeasons[seasonNumber] = { ...season, episodes };
    }
    if (Object.keys(filteredSeasons).length === 0) continue;
    result.push({ ...entry, seasons: filteredSeasons });
  }
  return result;
}

function filterSeriesEntryByReason(
  entry: SonarrSeriesEntry,
  reasonFilter: string,
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

export function seriesEntryToGroup(
  entry: SonarrSeriesEntry,
  instanceLabel: string,
): SonarrSeriesGroup {
  const title = (entry.series?.["title"] as string | undefined) || "";
  const seriesId = entry.series?.["id"] as number | undefined;
  const qualityProfileName = entry.series?.qualityProfileName ?? null;
  const episodes: import("../../components/arr/SonarrSeriesGroupDetailBody").SonarrEpisodeRow[] =
    [];
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

function sonarrMonitoredEpisodeProgress(
  group: SonarrSeriesGroup,
): JSX.Element {
  const mon = group.episodes.filter((e) => e.monitored);
  const total = mon.length;
  const available = mon.filter((e) => e.hasFile).length;
  const missing = Math.max(0, total - available);
  return (
    <ArrMiniProgress label="Episodes" available={available} missing={missing} />
  );
}

function sonarrGroupRowKey(group: SonarrSeriesGroupRow): string {
  return `${group.instance}::${group.series}`;
}

function summarizeGroupEpisodes(
  groups: ReadonlyArray<SonarrSeriesGroupRow>,
): ArrCatalogSummary {
  let monitored = 0;
  let available = 0;
  let total = 0;
  for (const g of groups) {
    for (const ep of g.episodes) {
      total += 1;
      if (ep.monitored) {
        monitored += 1;
        if (ep.hasFile) available += 1;
      }
    }
  }
  const missing = Math.max(0, monitored - available);
  return { available, monitored, missing, total };
}

/**
 * Sonarr-specific instance pipeline.
 *
 * Mirrors the legacy fetch loop: paginated by series (not episode), uses
 * `arraysEqual` for page diffs (the rows are deeply nested seasons → episodes that
 * `useDataSync` cannot hash without exploding payloads).  Filters live client-side
 * over cached pages.
 */
function useSonarrInstancePipeline(
  params: ArrCatalogInstancePipelineParams<SonarrFilters>,
): ArrCatalogInstancePipelineState<SonarrSeriesGroupRow> {
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
  const [pageSize, setPageSize] = useState(SONARR_PAGE_SIZE);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [loading, setLoading] = useState(false);
  const [emptyStateReady, setEmptyStateReady] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const pagesRef = useRef<Record<number, SonarrSeriesEntry[]>>({});
  const keyRef = useRef<string>("");
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const prevSelectionRef = useRef<string | null>(selection);
  const prevOnlyMissingRef = useRef(filters.onlyMissing);
  const sawNonEmptyRef = useRef(false);
  const stableEmptyStreakRef = useRef(0);

  const rowsStoreOpts = useMemo(
    () => ({
      getKey: sonarrGroupRowKey,
      hashFields:
        SONARR_GROUP_HASH_FIELDS as unknown as ReadonlyArray<
          keyof SonarrSeriesGroupRow & string
        >,
    }),
    [],
  );
  const { snapshot, store } = useRowsStore<SonarrSeriesGroupRow>(
    rowsStoreOpts as never,
  );

  const fetchInstance = useCallback(
    async (
      category: string,
      pageIdx: number,
      requestQuery: string,
      options: { showLoading?: boolean; missingOnly?: boolean } = {},
    ) => {
      const showLoading = options.showLoading ?? true;
      const useMissing = options.missingOnly ?? filtersRef.current.onlyMissing;
      if (showLoading) setLoading(true);
      try {
        const key = `${category}::${requestQuery}::${
          useMissing ? "missing" : "all"
        }`;
        const keyChanged = keyRef.current !== key;
        if (keyChanged) {
          keyRef.current = key;
          pagesRef.current = {};
          setPages({});
          setTotalItems(0);
          setTotalPages(1);
          setPage(0);
          setEmptyStateReady(false);
          sawNonEmptyRef.current = false;
          stableEmptyStreakRef.current = 0;
        }
        const effectivePageIdx = keyChanged ? 0 : pageIdx;
        const ps = roundPageSize(SONARR_PAGE_SIZE);
        const res = await getSonarrSeries(
          category,
          effectivePageIdx,
          ps,
          requestQuery,
          {
            missingOnly: useMissing,
          },
        );
        const resolvedPage = res.page ?? effectivePageIdx;
        const resolvedPageSize = res.page_size ?? ps;
        const total = res.total ?? (res.series ?? []).length;
        const computedTotalPages = Math.max(
          1,
          Math.ceil((total || 0) / resolvedPageSize),
        );
        const series = res.series ?? [];
        const hasCatalogData = series.length > 0 || total > 0;

        if (hasCatalogData) {
          sawNonEmptyRef.current = true;
          stableEmptyStreakRef.current = 0;
          setEmptyStateReady((prev) => (prev ? prev : true));
        } else {
          stableEmptyStreakRef.current += 1;
          const ready = sawNonEmptyRef.current || stableEmptyStreakRef.current >= 2;
          setEmptyStateReady((prev) => (prev === ready ? prev : ready));
        }

        const prev = keyChanged ? {} : pagesRef.current;
        const prevSlice = prev[resolvedPage] ?? [];

        const pageChanged =
          keyChanged ||
          !arraysEqual<SonarrSeriesComparable>(
            prevSlice as SonarrSeriesComparable[],
            series as SonarrSeriesComparable[],
            getSonarrSeriesEntryKey,
            SONARR_INSTANCE_PAGE_HASH_FIELDS,
          );

        const next = { ...prev, [resolvedPage]: series };
        pagesRef.current = next;
        if (pageChanged) {
          setPages(next);
          setLastUpdated(new Date().toLocaleTimeString());
        }

        setResponse((prevResp) => {
          const prevCounts = prevResp?.counts ?? null;
          const nextCounts = res.counts ?? null;
          const countsChanged =
            !prevResp ||
            prevResp.total !== res.total ||
            prevResp.page !== res.page ||
            prevResp.page_size !== res.page_size ||
            (prevCounts?.available ?? null) !==
              (nextCounts?.available ?? null) ||
            (prevCounts?.monitored ?? null) !==
              (nextCounts?.monitored ?? null) ||
            (prevCounts?.missing ?? null) !== (nextCounts?.missing ?? null);
          return countsChanged || pageChanged ? res : prevResp;
        });

        setPage((p) => (p === resolvedPage ? p : resolvedPage));
        setQuery((q) => (q === requestQuery ? q : requestQuery));
        setPageSize((s) => (s === resolvedPageSize ? s : resolvedPageSize));
        setTotalPages((tp) =>
          tp === computedTotalPages ? tp : computedTotalPages,
        );
        setTotalItems((ti) => (ti === total ? ti : total));
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
    [pushToast, roundPageSize],
  );

  const fetchInstanceRef = useRef(fetchInstance);
  useLayoutEffect(() => {
    fetchInstanceRef.current = fetchInstance;
  }, [fetchInstance]);

  // Selection / filter change effect with aligned page-preservation rule.
  useEffect(() => {
    if (!active) return;
    if (!selection) return;

    const selectionChanged = prevSelectionRef.current !== selection;
    const onlyMissingChanged =
      prevOnlyMissingRef.current !== filters.onlyMissing;
    if (selectionChanged) {
      pagesRef.current = {};
      setPages({});
      setPage(0);
      setTotalPages(1);
      setEmptyStateReady(false);
      sawNonEmptyRef.current = false;
      stableEmptyStreakRef.current = 0;
      prevSelectionRef.current = selection;
    }
    if (onlyMissingChanged) {
      prevOnlyMissingRef.current = filters.onlyMissing;
    }

    const requestQuery = globalSearchRef.current;
    void fetchInstanceRef.current(
      selection,
      selectionChanged ? 0 : page,
      requestQuery,
      {
        showLoading: true,
        missingOnly: filters.onlyMissing,
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `page` excluded; refetch via setPage handler.
  }, [active, selection, filters.onlyMissing]);

  // Reset row store on selection change.
  useEffect(() => {
    store.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);

  // Search handler.
  useEffect(() => {
    if (!active) return;
    const handler = (term: string) => {
      if (!selection) return;
      setPage(0);
      void fetchInstanceRef.current(selection, 0, term, {
        showLoading: true,
        missingOnly: filtersRef.current.onlyMissing,
      });
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
        missingOnly: filtersRef.current.onlyMissing,
      });
    },
    active && polling && selection ? INSTANCE_VIEW_POLL_INTERVAL_MS : null,
  );

  // Re-fetch on icon-grid resize so per-page rows match the visible grid.
  useEffect(() => {
    if (!active) return;
    if (!selection) return;
    if (browseMode !== "icon") return;
    void fetchInstanceRef.current(selection, page, query, {
      showLoading: false,
      missingOnly: filtersRef.current.onlyMissing,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, selection, browseMode, iconInstancePageSize]);

  const allSeries = useMemo<SonarrSeriesEntry[]>(() => {
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

  const filteredGroups = useMemo<SonarrSeriesGroupRow[]>(() => {
    const missingFiltered = filterSeriesEntriesForMissing(
      allSeries,
      filters.onlyMissing,
    );
    const withReason: SonarrSeriesEntry[] = [];
    for (const entry of missingFiltered) {
      const f = filterSeriesEntryByReason(entry, filters.reasonFilter);
      if (f) withReason.push(f);
    }
    const q = (globalSearchRef.current || "").trim().toLowerCase();
    const filtered = q
      ? withReason.filter((e) => {
          const t = (e.series?.["title"] as string | undefined) || "";
          return t.toLowerCase().includes(q);
        })
      : withReason;
    return filtered.map(
      (e) => seriesEntryToGroup(e, instanceLabel) as SonarrSeriesGroupRow,
    );
  }, [
    allSeries,
    filters.onlyMissing,
    filters.reasonFilter,
    instanceLabel,
    globalSearchRef,
  ]);

  const visibleRows = useMemo<SonarrSeriesGroupRow[]>(
    () => filteredGroups.slice(page * pageSize, page * pageSize + pageSize),
    [filteredGroups, page, pageSize],
  );

  // Push the current page slice through the row store.
  useEffect(() => {
    store.sync(visibleRows);
  }, [visibleRows, store]);

  const showCatalogEmptyHint =
    !loading &&
    allSeries.length === 0 &&
    totalItems === 0 &&
    response != null;

  const setPagePublic = useCallback(
    (next: number) => {
      setPage(next);
      if (selection) {
        void fetchInstanceRef.current(selection, next, query, {
          showLoading: true,
          missingOnly: filtersRef.current.onlyMissing,
        });
      }
    },
    [selection, query],
  );

  const refresh = useCallback(() => {
    if (!selection) return;
    void fetchInstanceRef.current(selection, page, query, {
      showLoading: true,
      missingOnly: filtersRef.current.onlyMissing,
    });
  }, [selection, page, query]);

  return {
    loading,
    emptyStateReady,
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
  };
}

function buildSonarrInstanceColumns(): ColumnDef<SonarrSeriesGroupRow>[] {
  return [
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
  ];
}

function buildSonarrAggColumns(
  instanceCount: number,
): ColumnDef<SonarrSeriesGroupRow>[] {
  const base: ColumnDef<SonarrSeriesGroupRow>[] = [];
  if (instanceCount > 1) {
    base.push({
      accessorKey: "instance" as const,
      header: "Instance",
      cell: (info) => String(info.getValue() ?? ""),
    });
  }
  base.push(...buildSonarrInstanceColumns());
  return base;
}

export const SONARR_DEFINITION: ArrCatalogDefinition<
  SonarrSeriesGroupRow,
  SonarrSeriesGroupRow,
  SonarrFilters,
  SonarrSeriesGroup,
  SonarrSeriesGroup,
  SonarrSeriesGroup,
  SonarrSeriesResponse,
  null
> = {
  kind: "sonarr",
  arrType: "sonarr",
  cardTitle: "Sonarr",
  allInstancesLabel: "All Sonarr",
  searchPlaceholder: "Filter series or episodes",
  initialFilters: { onlyMissing: false, reasonFilter: "all" },
  filterControls: [
    {
      id: "status",
      label: "Status",
      mode: "always",
      options: [
        { value: "all", label: "All Episodes" },
        { value: "missing", label: "Missing Only" },
      ],
      getValue: (f) => (f.onlyMissing ? "missing" : "all"),
      setValue: (prev, next) => ({ ...prev, onlyMissing: next === "missing" }),
    },
    {
      id: "reason",
      label: "Search Reason",
      mode: "always",
      options: [
        { value: "all", label: "All Reasons" },
        { value: "Not being searched", label: "Not Being Searched" },
        { value: "Missing", label: "Missing" },
        { value: "Quality", label: "Quality" },
        { value: "CustomFormat", label: "Custom Format" },
        { value: "Upgrade", label: "Upgrade" },
      ],
      getValue: (f) => f.reasonFilter,
      setValue: (prev, next) => ({ ...prev, reasonFilter: next }),
    },
  ],
  aggregate: {
    basePageSize: SONARR_PAGE_SIZE,
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
      (response.series ?? []).forEach((entry) => {
        push(
          seriesEntryToGroup(entry, instanceLabel) as SonarrSeriesGroupRow,
        );
      });
    },
    summarize: (rows) => summarizeGroupEpisodes(rows),
    getRowKey: sonarrGroupRowKey,
    hashFields: SONARR_GROUP_HASH_FIELDS as unknown as ReadonlyArray<
      keyof SonarrSeriesGroupRow & string
    >,
    filterRows: (rows, filters, debouncedSearch) => {
      const q = debouncedSearch ? debouncedSearch.toLowerCase() : "";
      const hasSearch = Boolean(q);
      const hasReason = filters.reasonFilter !== "all";
      const hasMissing = filters.onlyMissing;
      if (!hasSearch && !hasReason && !hasMissing) return rows;
      const result: SonarrSeriesGroupRow[] = [];
      for (const group of rows) {
        if (hasSearch) {
          const matchesSeries = group.series.toLowerCase().includes(q);
          const matchesInstance = group.instance.toLowerCase().includes(q);
          if (!matchesSeries && !matchesInstance) {
            const matchesEp = group.episodes.some((ep) =>
              ep.title.toLowerCase().includes(q),
            );
            if (!matchesEp) continue;
          }
        }
        let episodes = group.episodes;
        if (hasMissing) {
          episodes = episodes.filter((ep) => !ep.hasFile);
        }
        if (hasReason) {
          if (filters.reasonFilter === "Not being searched") {
            episodes = episodes.filter(
              (ep) => ep.reason === "Not being searched" || !ep.reason,
            );
          } else {
            episodes = episodes.filter(
              (ep) => ep.reason === filters.reasonFilter,
            );
          }
        }
        if (episodes.length === 0 && (hasMissing || hasReason)) continue;
        if (episodes !== group.episodes) {
          result.push({ ...group, episodes } as SonarrSeriesGroupRow);
        } else {
          result.push(group);
        }
      }
      return result;
    },
  },
  useInstancePipeline: useSonarrInstancePipeline,
  buildAggregateSelection: (row) => ({
    id: sonarrGroupRowKey(row),
    source: "aggregate",
    seed: row,
  }),
  buildInstanceSelection: (row) => ({
    id: sonarrGroupRowKey(row),
    source: "instance",
    seed: row,
  }),
  getModalLiveRow: ({
    source,
    instanceFresh,
    aggregateFresh,
    instanceSeed,
    aggregateSeed,
  }) => {
    if (source === "instance") {
      return (instanceFresh ?? instanceSeed) as SonarrSeriesGroup;
    }
    return (aggregateFresh ?? aggregateSeed) as SonarrSeriesGroup;
  },
  getModalTitle: (liveRow) => liveRow.series,
  getModalMaxWidth: () => 720,
  renderModalBody: ({ liveRow }) => (
    <SonarrSeriesGroupDetailBody group={liveRow} />
  ),
  buildAggregateColumns: buildSonarrAggColumns,
  buildInstanceColumns: buildSonarrInstanceColumns,
  renderAggregateBody: (props) => <SonarrAggregateBody {...props} />,
  renderInstanceBody: (props) => <SonarrInstanceBody {...props} />,
};

ARR_CATALOG_REGISTRY.sonarr = SONARR_DEFINITION;

interface SonarrAggregateBodyProps {
  readonly rows: ReadonlyArray<SonarrSeriesGroupRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<SonarrSeriesGroupRow>;
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
  readonly onRowSelect: (row: SonarrSeriesGroupRow) => void;
  readonly browseMode: "list" | "icon";
  readonly iconGridRef: RefCallback<HTMLElement | null>;
  readonly instances: ReadonlyArray<ArrInfo>;
  readonly instanceCount: number;
}

function SonarrAggregateBody({
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
}: SonarrAggregateBodyProps): JSX.Element {
  const columns = buildSonarrAggColumns(instanceCount);
  const waitingForStableEmpty =
    instanceCount > 0 && !emptyStateReady && total === 0;
  const effectiveLoading = loading || waitingForStableEmpty;
  const summaryLine = (
    <>
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
      {isAggFiltered && total < summary.total ? (
        <>
          {" "}• <strong>Filtered series:</strong>{" "}
          {total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </>
      ) : null}
    </>
  );

  const showCatalogEmptyHint =
    !effectiveLoading && total === 0 && summary.total === 0 && instanceCount > 0;

  return (
    <ArrCatalogBodyChrome
      summaryLine={summaryLine}
      onRefresh={onRefresh}
      loading={effectiveLoading}
      loadingHint="Loading Sonarr library…"
      footer={
        total > 0 ? (
          <ArrCatalogPagination
            page={page}
            totalPages={totalPages}
            total={total}
            itemNoun="series"
            pageSize={aggregatePageSize}
            loading={effectiveLoading}
            onPageChange={onPageChange}
          />
        ) : null
      }
    >
      {showCatalogEmptyHint ? (
        <div className="hint">
          <p>No episodes found in the database.</p>
          <p>{ARR_CATALOG_SYNC_HINT}</p>
        </div>
      ) : !total ? (
        <div className="hint">No series found.</div>
      ) : browseMode === "list" ? (
        <StableTable<SonarrSeriesGroupRow>
          rowsStore={rowsStore}
          rowOrder={rowOrder}
          columns={columns}
          getRowKey={sonarrGroupRowKey}
          onRowClick={onRowSelect}
        />
      ) : (
        <div className="arr-icon-grid" ref={iconGridRef}>
          {rows.map((g) => {
            const cat = categoryForInstanceLabel([...instances], g.instance);
            const sid = g.seriesId;
            const thumb =
              sid != null && cat ? sonarrSeriesThumbnailUrl(cat, sid) : "";
            return (
              <ArrCatalogIconTile
                key={`${g.instance}-${String(g.seriesId ?? "")}-${g.series}`}
                posterSrc={thumb}
                onClick={() => onRowSelect(g)}
              >
                {instanceCount > 1 ? (
                  <div className="arr-movie-tile__instance">{g.instance}</div>
                ) : null}
                <div className="arr-movie-tile__title">{g.series}</div>
                <div className="arr-movie-tile__stats arr-movie-tile__stats--sonarr-episodes">
                  {sonarrMonitoredEpisodeProgress(g)}
                </div>
                <div className="arr-movie-tile__quality">
                  {g.qualityProfileName ?? "—"}
                </div>
              </ArrCatalogIconTile>
            );
          })}
        </div>
      )}
    </ArrCatalogBodyChrome>
  );
}

interface SonarrInstanceBodyProps {
  readonly visibleRows: ReadonlyArray<SonarrSeriesGroupRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<SonarrSeriesGroupRow>;
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
  readonly instanceLabel: string;
  readonly showCatalogEmptyHint: boolean;
  readonly onRowSelect: (row: SonarrSeriesGroupRow) => void;
  readonly setPage: (page: number) => void;
  readonly refresh: () => void;
  readonly filters: SonarrFilters;
}

function SonarrInstanceBody({
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
  filters,
}: SonarrInstanceBodyProps): JSX.Element {
  const waitingForStableEmpty =
    !emptyStateReady && visibleRows.length === 0;
  const effectiveLoading = loading || waitingForStableEmpty;
  const totalEpisodes = useMemo(
    () => visibleRows.reduce((acc, g) => acc + g.episodes.length, 0),
    [visibleRows],
  );
  const isFiltered = filters.onlyMissing || filters.reasonFilter !== "all";
  const summaryLine = (
    <>
      <strong>Series shown:</strong>{" "}
      {visibleRows.length.toLocaleString(undefined, {
        maximumFractionDigits: 0,
      })}{" "}
      • <strong>Episodes shown:</strong>{" "}
      {totalEpisodes.toLocaleString(undefined, { maximumFractionDigits: 0 })} •{" "}
      <strong>Series total:</strong>{" "}
      {totalItems.toLocaleString(undefined, { maximumFractionDigits: 0 })}
      {lastUpdated ? ` (updated ${lastUpdated})` : ""}
    </>
  );

  const columns = buildSonarrInstanceColumns();

  return (
    <ArrCatalogBodyChrome
      summaryLine={summaryLine}
      onRefresh={refresh}
      loading={effectiveLoading}
      loadingHint="Loading series…"
      footer={
        totalPages > 1 ? (
          <ArrCatalogPagination
            page={page}
            totalPages={totalPages}
            total={totalItems}
            itemNoun="series"
            pageSize={pageSize}
            loading={effectiveLoading}
            onPageChange={setPage}
          />
        ) : null
      }
    >
      {showCatalogEmptyHint ? (
        <div className="hint">
          <p>No series rows in the local catalog yet.</p>
          <p>{ARR_CATALOG_SYNC_HINT}</p>
        </div>
      ) : visibleRows.length === 0 && isFiltered ? (
        <div className="hint">No episodes match the current filter.</div>
      ) : visibleRows.length ? (
        browseMode === "list" ? (
          <StableTable<SonarrSeriesGroupRow>
            rowsStore={rowsStore}
            rowOrder={rowOrder}
            columns={columns}
            getRowKey={sonarrGroupRowKey}
            onRowClick={onRowSelect}
          />
        ) : (
          <div className="arr-icon-grid" ref={iconGridRef}>
            {visibleRows.map((g) => {
              const sid = g.seriesId;
              const thumb =
                sid != null && category
                  ? sonarrSeriesThumbnailUrl(category, sid)
                  : "";
              return (
                <ArrCatalogIconTile
                  key={`${g.instance}-${String(g.seriesId ?? "")}-${g.series}`}
                  posterSrc={thumb}
                  onClick={() => onRowSelect(g)}
                >
                  <div className="arr-movie-tile__title">{g.series}</div>
                  <div className="arr-movie-tile__stats arr-movie-tile__stats--sonarr-episodes">
                    {sonarrMonitoredEpisodeProgress(g)}
                  </div>
                  <div className="arr-movie-tile__quality">
                    {g.qualityProfileName ?? "—"}
                  </div>
                </ArrCatalogIconTile>
              );
            })}
          </div>
        )
      ) : (
        <div className="hint">No series found.</div>
      )}
    </ArrCatalogBodyChrome>
  );
}
