import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useLayoutEffect,
  type ChangeEvent,
  type JSX,
} from "react";
import {
  getArrList,
  getLidarrArtists,
} from "../api/client";
import type {
  ArrInfo,
  LidarrArtistBrowseEntry,
  LidarrArtistsResponse,
} from "../api/types";
import { useToast } from "../context/ToastContext";
import { useSearch } from "../context/SearchContext";
import { useWebUI } from "../context/WebUIContext";
import { useArrBrowseMode } from "../hooks/useArrBrowseMode";
import { useInterval } from "../hooks/useInterval";
import { useDebounce } from "../hooks/useDebounce";
import { useDataSync } from "../hooks/useDataSync";
import { useRowSnapshot, useRowsStore } from "../hooks/useRowsStore";
import { StableTable } from "../components/StableTable";
import type { ColumnDef } from "@tanstack/react-table";
import { IconImage } from "../components/IconImage";
import { ArrBrowseModeToggle } from "../components/arr/ArrBrowseModeToggle";
import { ArrModal } from "../components/arr/ArrModal";
import { ArrPosterImage } from "../components/arr/ArrPosterImage";
import { LidarrArtistDetailBody } from "../components/arr/LidarrArtistDetailBody";
import { lidarrArtistThumbnailUrl } from "../utils/arrThumbnailUrl";
import RefreshIcon from "../icons/refresh-arrow.svg";
import {
  AGGREGATE_FETCH_CHUNK_SIZE,
  AGGREGATE_POLL_INTERVAL_MS,
  INSTANCE_VIEW_POLL_INTERVAL_MS,
  pagesFromAggregateTotal,
  type AggregateCatalogSummary,
  AGG_FALLBACK_AGGREGATE_PAGES_MAX,
} from "../constants/arrAggregateFetch";

interface LidarrAggRow extends LidarrArtistBrowseEntry {
  __instance: string;
}

/**
 * Row-store payloads.  The `& Record<string, unknown>` index signature is what makes the
 * value satisfy the `Hashable` constraint shared by `RowsStore` / `useRowsStore`.
 */
type LidarrInstanceRow = LidarrArtistBrowseEntry & Record<string, unknown>;
type LidarrAggRowHashable = LidarrAggRow & Record<string, unknown>;

const LIDARR_PAGE_SIZE = 50;
const LIDARR_AGG_PAGE_SIZE = 50;

function categoryForInstanceLabel(
  instances: ArrInfo[],
  label: string
): string {
  const inst = instances.find(
    (i) => (i.name || i.category) === label || i.category === label
  );
  return inst?.category ?? instances[0]?.category ?? "";
}

interface LidarrAggregateViewProps {
  loading: boolean;
  rows: LidarrAggRow[];
  rowOrder: readonly string[];
  rowsStore: import("../utils/rowsStore").RowsStore<LidarrAggRowHashable>;
  total: number;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  lastUpdated: string | null;
  summary: AggregateCatalogSummary & { rollupTotalAlbumsHint?: number };
  instanceCount: number;
  isAggFiltered?: boolean;
  browseMode: "list" | "icon";
  instances: ArrInfo[];
  onArtistSelect: (row: LidarrAggRow) => void;
}

const LidarrAggregateView = memo(function LidarrAggregateView({
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
  onArtistSelect,
}: LidarrAggregateViewProps): JSX.Element {
  const aggColumns = useMemo<ColumnDef<LidarrAggRowHashable>[]>(
    () => [
      ...(instanceCount > 1
        ? [
            {
              id: "instance",
              header: "Instance",
              cell: ({ row }: { row: { original: LidarrAggRowHashable } }) =>
                row.original.__instance,
            },
          ]
        : []),
      {
        id: "artist",
        header: "Artist",
        cell: ({ row }: { row: { original: LidarrAggRowHashable } }) => {
          const artist = row.original.artist as Record<string, unknown>;
          return (artist?.["name"] as string | undefined) || "—";
        },
      },
      {
        id: "albums",
        header: "Albums",
        cell: ({ row }: { row: { original: LidarrAggRowHashable } }) => {
          const artist = row.original.artist as Record<string, unknown>;
          return Number(artist?.["albumCount"] ?? 0).toLocaleString();
        },
      },
      {
        id: "tracks",
        header: "Tracks",
        cell: ({ row }: { row: { original: LidarrAggRowHashable } }) => {
          const artist = row.original.artist as Record<string, unknown>;
          return Number(artist?.["trackTotalCount"] ?? 0).toLocaleString();
        },
      },
      {
        id: "monitored",
        header: "Monitored",
        cell: ({ row }: { row: { original: LidarrAggRowHashable } }) => {
          const artist = row.original.artist as Record<string, unknown>;
          const monitored = Boolean(artist?.["monitored"]);
          return (
            <span className={`track-status ${monitored ? "available" : "missing"}`}>
              {monitored ? "✓" : "✗"}
            </span>
          );
        },
      },
      {
        id: "qualityProfileName",
        header: "Quality profile",
        cell: ({ row }: { row: { original: LidarrAggRowHashable } }) => {
          const artist = row.original.artist as Record<string, unknown>;
          return (
            (artist?.["qualityProfileName"] as string | null | undefined) || "—"
          );
        },
      },
    ],
    [instanceCount],
  );

  const handleAggRowClick = useCallback(
    (row: LidarrAggRowHashable) => {
      onArtistSelect(row as LidarrAggRow);
    },
    [onArtistSelect],
  );

  const aggGetRowKey = useCallback((row: LidarrAggRowHashable) => {
    const artist = row.artist as Record<string, unknown>;
    const id = artist?.["id"];
    const name = (artist?.["name"] as string | undefined) || "";
    const key =
      typeof id === "number" && Number.isFinite(id) ? `id:${id}` : `n:${name}`;
    return `${row.__instance}::${key}`;
  }, []);
  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          Aggregated artists across all instances{" "}
          {lastUpdated ? `(updated ${lastUpdated})` : ""}
          <br />
          <strong>Available albums:</strong>{" "}
          {summary.available.toLocaleString(undefined, {
            maximumFractionDigits: 0,
          })}{" "}
          • <strong>Monitored albums:</strong>{" "}
          {summary.monitored.toLocaleString(undefined, {
            maximumFractionDigits: 0,
          })}{" "}
          • <strong>Missing albums:</strong>{" "}
          {summary.missing.toLocaleString(undefined, {
            maximumFractionDigits: 0,
          })}
          {typeof summary.rollupTotalAlbumsHint === "number" && (
            <>
              {" "}
              • <strong>Album rows (SQLite):</strong>{" "}
              {summary.rollupTotalAlbumsHint.toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}
            </>
          )}
          {isAggFiltered && total < summary.total && (
            <>
              {" "}
              • <strong>Filtered artists:</strong>{" "}
              {total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
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
          <span className="spinner" /> Loading Lidarr library…
        </div>
      ) : !loading &&
        total === 0 &&
        summary.monitored === 0 &&
        instanceCount > 0 ? (
        <div className="hint">
          <p>No artists found in the local catalog.</p>
          <p>
            qBitrr may still be importing from your Lidarr instances into the SQLite database.
            Check logs or refresh in a moment.
          </p>
        </div>
      ) : total ? (
        browseMode === "list" ? (
          <StableTable<LidarrAggRowHashable>
            rowsStore={rowsStore}
            rowOrder={rowOrder}
            columns={aggColumns}
            getRowKey={aggGetRowKey}
            onRowClick={handleAggRowClick}
          />
        ) : (
          <div className="arr-icon-grid">
            {rows.map((row) => {
              const artist = row.artist as Record<string, unknown>;
              const id = artist?.["id"];
              const name = (artist?.["name"] as string | undefined) || "—";
              const cat = categoryForInstanceLabel(instances, row.__instance);
              const thumb =
                typeof id === "number"
                  ? lidarrArtistThumbnailUrl(cat, id)
                  : "";

              const rk = `${row.__instance}-${String(id ?? "")}-${name}`;

              return (
                <button
                  key={rk}
                  type="button"
                  className="arr-movie-tile card"
                  onClick={() => onArtistSelect(row)}
                >
                  {thumb ? (
                    <ArrPosterImage className="arr-movie-tile__poster" src={thumb} alt="" />
                  ) : (
                    <div
                      className="arr-movie-tile__poster arr-poster-fallback"
                      aria-hidden
                    />
                  )}
                  <div className="arr-movie-tile__meta">
                    {instanceCount > 1 && (
                      <div className="arr-movie-tile__instance">{row.__instance}</div>
                    )}
                    <div className="arr-movie-tile__title">{name}</div>
                    <div className="arr-movie-tile__stats">
                      {Number(artist?.["albumCount"] ?? 0)} alb. ·{" "}
                      {Number(artist?.["trackTotalCount"] ?? 0)} tr.
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )
      ) : (
        <div className="hint">No artists match the current filters.</div>
      )}

      {total > 0 && (
        <div className="pagination">
          <div>
            Page {page + 1} of {totalPages} ({total.toLocaleString()} items · page size{" "}
            {LIDARR_AGG_PAGE_SIZE})
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

interface LidarrInstanceViewProps {
  loading: boolean;
  data: LidarrArtistsResponse | null;
  page: number;
  totalPages: number;
  pageSize: number;
  allArtists: LidarrArtistBrowseEntry[];
  monitoredFilter: "all" | "yes";
  rowOrder: readonly string[];
  rowsStore: import("../utils/rowsStore").RowsStore<LidarrInstanceRow>;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  lastUpdated: string | null;
  category: string;
  browseMode: "list" | "icon";
  onArtistSelect: (entry: LidarrArtistBrowseEntry) => void;
  showCatalogEmptyHint?: boolean;
}

const LidarrInstanceView = memo(function LidarrInstanceView({
  loading,
  data,
  page,
  totalPages,
  pageSize,
  allArtists,
  monitoredFilter,
  rowOrder,
  rowsStore,
  onPageChange,
  onRefresh,
  lastUpdated,
  category,
  browseMode,
  onArtistSelect,
  showCatalogEmptyHint = false,
}: LidarrInstanceViewProps): JSX.Element {
  const totalArtists = useMemo(() => allArtists.length, [allArtists]);

  const instanceColumns = useMemo<ColumnDef<LidarrInstanceRow>[]>(
    () => [
      {
        id: "artist",
        header: "Artist",
        cell: ({ row }: { row: { original: LidarrInstanceRow } }) => {
          const artist = row.original.artist as Record<string, unknown>;
          return String(artist?.["name"] ?? "—");
        },
      },
      {
        id: "albums",
        header: "Albums",
        cell: ({ row }: { row: { original: LidarrInstanceRow } }) => {
          const artist = row.original.artist as Record<string, unknown>;
          return Number(artist?.["albumCount"] ?? 0).toLocaleString();
        },
      },
      {
        id: "tracks",
        header: "Tracks",
        cell: ({ row }: { row: { original: LidarrInstanceRow } }) => {
          const artist = row.original.artist as Record<string, unknown>;
          return Number(artist?.["trackTotalCount"] ?? 0).toLocaleString();
        },
      },
      {
        id: "monitored",
        header: "Monitored",
        cell: ({ row }: { row: { original: LidarrInstanceRow } }) => {
          const artist = row.original.artist as Record<string, unknown>;
          const monitored = Boolean(artist?.["monitored"]);
          return (
            <span className={`track-status ${monitored ? "available" : "missing"}`}>
              {monitored ? "✓" : "✗"}
            </span>
          );
        },
      },
      {
        id: "qualityProfileName",
        header: "Quality profile",
        cell: ({ row }: { row: { original: LidarrInstanceRow } }) => {
          const artist = row.original.artist as Record<string, unknown>;
          return (
            (artist?.["qualityProfileName"] as string | null | undefined) || "—"
          );
        },
      },
    ],
    [],
  );

  const handleInstanceRowClick = useCallback(
    (row: LidarrInstanceRow) => {
      onArtistSelect(row as LidarrArtistBrowseEntry);
    },
    [onArtistSelect],
  );

  const instanceGetRowKey = useCallback((row: LidarrInstanceRow) => {
    const artist = row.artist as Record<string, unknown>;
    const id = artist?.["id"];
    const name = (artist?.["name"] as string | undefined) || "";
    return typeof id === "number" && Number.isFinite(id) ? `id:${id}` : `n:${name}`;
  }, []);

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          {data?.counts ? (
            <>
              <strong>Albums:</strong> monitored {data.counts.monitored?.toLocaleString() ?? "0"},{" "}
              available {data.counts.available?.toLocaleString() ?? "0"},{" "}
              missing {((data.counts.monitored ?? 0) - (data.counts.available ?? 0)).toLocaleString()}{" "}
              • <strong>Artist total:</strong>{" "}
              {(data.total ?? totalArtists).toLocaleString()}
            </>
          ) : (
            "Loading…"
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
      ) : totalArtists > 0 ? (
        browseMode === "list" ? (
          <StableTable<LidarrInstanceRow>
            rowsStore={rowsStore}
            rowOrder={rowOrder}
            columns={instanceColumns}
            getRowKey={instanceGetRowKey}
            onRowClick={handleInstanceRowClick}
          />
        ) : (
          <div className="arr-icon-grid">
            {allArtists.map((entry) => {
              const artist = entry.artist as Record<string, unknown>;
              const id = artist?.["id"];
              const name = String(artist?.["name"] ?? "—");
              const thumb =
                typeof id === "number"
                  ? lidarrArtistThumbnailUrl(category, id)
                  : "";

              const rk = `${category}-${String(id ?? "")}-${name}`;

              return (
                <button
                  key={rk}
                  type="button"
                  className="arr-movie-tile card"
                  onClick={() => onArtistSelect(entry)}
                >
                  {thumb ? (
                    <ArrPosterImage className="arr-movie-tile__poster" src={thumb} alt="" />
                  ) : (
                    <div
                      className="arr-movie-tile__poster arr-poster-fallback"
                      aria-hidden
                    />
                  )}
                  <div className="arr-movie-tile__meta">
                    <div className="arr-movie-tile__title">{name}</div>
                    <div className="arr-movie-tile__stats">
                      {Number(artist?.["albumCount"] ?? 0)} alb. ·{" "}
                      {Number(artist?.["trackTotalCount"] ?? 0)} tr.
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )
      ) : showCatalogEmptyHint ? (
        <div className="hint">
          <p>No artists in the local catalog.</p>
          <p>
            qBitrr may still be syncing your Lidarr library. Check logs or try again shortly.
          </p>
        </div>
      ) : (
        <div className="hint">No artists match the current filters.</div>
      )}

      {totalArtists > pageSize && monitoredFilter === "all" ? (
        <div className="pagination">
          <div>
            Page {page + 1} of {totalPages} (
            {totalArtists.toLocaleString()} items · page size {pageSize})
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
      ) : null}
    </div>
  );
});

interface LidarrDetailModalProps {
  modal: {
    artistId: number;
    category: string;
    title: string;
    rowId: string;
    source: "instance" | "aggregate";
    instanceLabel: string;
  };
  instanceStore: import("../utils/rowsStore").RowsStore<LidarrInstanceRow>;
  aggregateStore: import("../utils/rowsStore").RowsStore<LidarrAggRowHashable>;
  onClose: () => void;
}

/**
 * Artist detail modal.
 *
 * The modal title subscribes to the relevant row store by id so refreshed artist data
 * (e.g. monitored toggle, album/track count) live-updates the title without closing the
 * modal.  The body — `LidarrArtistDetailBody` — does its own one-shot fetch against the
 * artist detail endpoint, which carries albums/tracks the row store does not.
 */
const LidarrDetailModal = memo(function LidarrDetailModal({
  modal,
  instanceStore,
  aggregateStore,
  onClose,
}: LidarrDetailModalProps): JSX.Element {
  const instanceFresh = useRowSnapshot(
    instanceStore,
    modal.source === "instance" ? modal.rowId : null,
  );
  const aggregateFresh = useRowSnapshot(
    aggregateStore,
    modal.source === "aggregate" ? modal.rowId : null,
  );
  const fresh = modal.source === "instance" ? instanceFresh : aggregateFresh;
  const liveTitle =
    fresh
      ? String(
          (fresh.artist as Record<string, unknown> | undefined)?.["name"] ??
            modal.title,
        )
      : modal.title;

  return (
    <ArrModal title={liveTitle} onClose={onClose} maxWidth={720}>
      <LidarrArtistDetailBody
        key={`${modal.category}-${modal.artistId}`}
        category={modal.category}
        artistId={modal.artistId}
        instanceLabel={modal.instanceLabel}
      />
    </ArrModal>
  );
});

export function LidarrView({ active }: { active: boolean }): JSX.Element {
  const { push } = useToast();
  const {
    value: globalSearch,
    setValue: setGlobalSearch,
    register,
    clearHandler,
  } = useSearch();
  const { liveArr } = useWebUI();
  const { mode: browseMode, setMode: setBrowseMode } = useArrBrowseMode("lidarr");

  type ModalState = {
    artistId: number;
    category: string;
    title: string;
    /** Row-store id (matches the table row that was clicked) so the modal title can
     *  subscribe to the artist row and live-update when polling brings in fresh data. */
    rowId: string;
    source: "instance" | "aggregate";
    instanceLabel: string;
  };

  const [lidarrModal, setLidarrModal] = useState<ModalState | null>(null);

  const [instances, setInstances] = useState<ArrInfo[]>([]);
  const [selection, setSelection] = useState<string | "">("");
  const [instanceData, setInstanceData] = useState<LidarrArtistsResponse | null>(
    null
  );
  const [instancePage, setInstancePage] = useState(0);
  const [instanceQuery, setInstanceQuery] = useState("");
  const [instanceLoading, setInstanceLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [instancePages, setInstancePages] = useState<
    Record<number, LidarrArtistBrowseEntry[]>
  >({});
  const [instancePageSize, setInstancePageSize] = useState(LIDARR_PAGE_SIZE);
  const [instanceTotalPages, setInstanceTotalPages] = useState(1);
  const instanceKeyRef = useRef<string>("");
  const instancePagesRef = useRef<Record<number, LidarrArtistBrowseEntry[]>>({});
  const globalSearchRef = useRef(globalSearch);
  globalSearchRef.current = globalSearch;
  const selectionRef = useRef(selection);
  selectionRef.current = selection;
  const backendReadyWarnedRef = useRef(false);
  const aggFetchGenRef = useRef(0);
  const aggActiveLoadsRef = useRef(0);
  const prevSelectionRef = useRef<string | "">(selection);

  const [monitoredArtistOnly, setMonitoredArtistOnly] = useState(false);

  const instanceArtistSync = useDataSync<LidarrArtistBrowseEntry>({
    getKey: (row) => {
      const a = row.artist as Record<string, unknown>;
      const id = a?.["id"];
      const name = (a?.["name"] as string | undefined) || "";
      return typeof id === "number" && Number.isFinite(id) ? `id:${id}` : `n:${name}`;
    },
    hashFields: ["artist"],
  });

  // Surgical row store for the per-instance artist browse list.  Keeps `rowOrder` stable
  // on update-only polls so the table doesn't re-render every cell on every tick.
  const instanceArtistRowsStoreOpts = useMemo(
    () => ({
      getKey: (row: LidarrInstanceRow) => {
        const a = row.artist as Record<string, unknown>;
        const id = a?.["id"];
        const name = (a?.["name"] as string | undefined) || "";
        return typeof id === "number" && Number.isFinite(id)
          ? `id:${id}`
          : `n:${name}`;
      },
      hashFields: ["artist"] as const,
    }),
    [],
  );
  const instanceArtistRowsStore = useRowsStore<LidarrInstanceRow>(
    instanceArtistRowsStoreOpts as never,
  );

  const [aggRows, setAggRows] = useState<LidarrAggRow[]>([]);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggPage, setAggPage] = useState(0);
  const [aggFilter, setAggFilter] = useState("");
  const [aggUpdated, setAggUpdated] = useState<string | null>(null);
  const debouncedAggFilter = useDebounce(aggFilter, 300);

  const aggArtistSync = useDataSync<LidarrAggRow>({
    getKey: (row) => {
      const a = row.artist as Record<string, unknown>;
      const id = a?.["id"];
      const name = (a?.["name"] as string | undefined) || "";
      const key =
        typeof id === "number" && Number.isFinite(id)
          ? `id:${id}`
          : `n:${name}`;
      return `${row.__instance}::${key}`;
    },
    hashFields: ["__instance", "artist"],
  });

  // Surgical row store for the aggregate artist list (same rationale as above).
  const aggArtistRowsStoreOpts = useMemo(
    () => ({
      getKey: (row: LidarrAggRowHashable) => {
        const a = row.artist as Record<string, unknown>;
        const id = a?.["id"];
        const name = (a?.["name"] as string | undefined) || "";
        const key =
          typeof id === "number" && Number.isFinite(id)
            ? `id:${id}`
            : `n:${name}`;
        return `${row.__instance}::${key}`;
      },
      hashFields: ["__instance", "artist"] as const,
    }),
    [],
  );
  const aggArtistRowsStore = useRowsStore<LidarrAggRowHashable>(
    aggArtistRowsStoreOpts as never,
  );

  const [aggSummary, setAggSummary] = useState<
    AggregateCatalogSummary & { rollupTotalAlbumsHint?: number }
  >({ available: 0, monitored: 0, missing: 0, total: 0, rollupTotalAlbumsHint: 0 });

  const loadInstances = useCallback(async () => {
    try {
      const data = await getArrList();
      if (data.ready === false && !backendReadyWarnedRef.current) {
        backendReadyWarnedRef.current = true;
        push("Lidarr backend is still initialising. Check the logs if this persists.", "info");
      } else if (data.ready) {
        backendReadyWarnedRef.current = true;
      }
      const filtered = (data.arr || []).filter((arr) => arr.type === "lidarr");
      setInstances(filtered);
      if (!filtered.length) {
        setSelection("aggregate");
        setInstanceData(null);
        setAggRows([]);
        setAggSummary({
          available: 0,
          monitored: 0,
          missing: 0,
          total: 0,
          rollupTotalAlbumsHint: 0,
        });
        return;
      }
      const sel = selectionRef.current;
      if (sel === "") {
        setSelection(filtered.length === 1 ? filtered[0].category : "aggregate");
      } else if (sel !== "aggregate" && !filtered.some((arr) => arr.category === sel)) {
        setSelection(filtered[0].category);
      }
    } catch (error) {
      push(
        error instanceof Error
          ? error.message
          : "Unable to load Lidarr instances",
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
      key: string,
      monitored: boolean | null
    ) => {
      if (!pages.length) return;
      try {
        const results: { page: number; rows: LidarrArtistBrowseEntry[] }[] = [];
        for (const pg of pages) {
          const res = await getLidarrArtists(category, pg, pageSize, query, {
            monitored,
          });
          const resolved = res.page ?? pg;
          results.push({ page: resolved, rows: res.artists ?? [] });
          if (instanceKeyRef.current !== key) {
            return;
          }
        }
        if (instanceKeyRef.current !== key) return;

        setInstancePages((prev) => {
          const next = { ...prev };
          let hasChanges = false;
          for (const { page, rows } of results) {
            const syncResult = instanceArtistSync.syncData(rows);
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
    [push, instanceArtistSync]
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
      const monitored = monitoredArtistOnly ? true : null;
      try {
        const key = `${category}::${query}::m:${monitored === null ? "" : monitored ? "1" : "0"}`;
        const keyChanged = instanceKeyRef.current !== key;
        if (keyChanged) {
          instanceKeyRef.current = key;
          setInstancePages(() => {
            instancePagesRef.current = {};
            return {};
          });
        }
        const response = await getLidarrArtists(category, page, LIDARR_PAGE_SIZE, query, {
          monitored,
        });
        const resolvedPage = response.page ?? page;
        const pageSize = response.page_size ?? LIDARR_PAGE_SIZE;
        const totalItems = response.total ?? (response.artists ?? []).length;
        const totalPages = Math.max(1, Math.ceil((totalItems || 0) / pageSize));
        const rows = response.artists ?? [];
        const existingPages = keyChanged ? {} : instancePagesRef.current;

        if (keyChanged) {
          instanceArtistSync.reset();
        }

        const syncResult = instanceArtistSync.syncData(rows);
        const artistsChanged = syncResult.hasChanges;

        if (keyChanged || artistsChanged) {
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
            artistsChanged ||
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
            key,
            monitored
          );
        }
      } catch (error) {
        push(
          error instanceof Error
            ? error.message
            : `Failed to load ${category} artists`,
          "error"
        );
      } finally {
        if (showLoading) {
          setInstanceLoading(false);
        }
      }
    },
    [push, preloadRemainingPages, instanceArtistSync, monitoredArtistOnly]
  );

  const fetchInstanceRef = useRef(fetchInstance);
  useLayoutEffect(() => {
    fetchInstanceRef.current = fetchInstance;
  }, [fetchInstance]);

  const loadAggregate = useCallback(async (options?: { showLoading?: boolean }) => {
    if (!instances.length) {
      setAggRows([]);
      setAggSummary({
        available: 0,
        monitored: 0,
        missing: 0,
        total: 0,
        rollupTotalAlbumsHint: 0,
      });
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
      const aggregated: LidarrAggRow[] = [];
      let progressFirstPaint = false;
      let rollupAcc: AggregateCatalogSummary & { rollupTotalAlbumsHint: number } = {
        available: 0,
        monitored: 0,
        missing: 0,
        total: 0,
        rollupTotalAlbumsHint: 0,
      };

      for (const inst of instances) {
        const label = inst.name || inst.category;
        let countedForInstance = false;
        let pagesPlanned: number | null = null;
        let rollupAddedThisInstance = false;
        let pageIdx = 0;

        while (true) {
          const res = await getLidarrArtists(inst.category, pageIdx, chunk, "", {
            monitored: null,
          });
          if (gen !== aggFetchGenRef.current) {
            return;
          }

          if (!countedForInstance) {
            countedForInstance = true;
            pagesPlanned = pagesFromAggregateTotal(res.total, res.page_size, chunk);
            if (showLoading && typeof res.total === "number" && res.total === 0) {
              setAggLoading(false);
              progressFirstPaint = true;
            }
          }

          if (!rollupAddedThisInstance && res.counts) {
            rollupAddedThisInstance = true;
            const ca = res.counts;
            rollupAcc = {
              available: rollupAcc.available + (ca.available ?? 0),
              monitored: rollupAcc.monitored + (ca.monitored ?? 0),
              missing: rollupAcc.missing + (ca.missing ?? 0),
              total: 0,
              rollupTotalAlbumsHint:
                rollupAcc.rollupTotalAlbumsHint + (res.album_total ?? 0),
            };
          }

          const artistRows = res.artists ?? [];
          artistRows.forEach((entry) => {
            aggregated.push({ ...entry, __instance: label });
          });

          if (showLoading && !progressFirstPaint && aggregated.length > 0) {
            setAggLoading(false);
            progressFirstPaint = true;
          }

          pageIdx += 1;

          if (pagesPlanned !== null) {
            if (pageIdx >= pagesPlanned) break;
          } else {
            if (!artistRows.length || artistRows.length < chunk) break;
            if (pageIdx >= AGG_FALLBACK_AGGREGATE_PAGES_MAX) break;
          }
        }
      }

      const syncResult = aggArtistSync.syncData(aggregated);
      const rowsChanged = syncResult.hasChanges;

      if (rowsChanged) {
        setAggRows(syncResult.data);
      }

      const mergedHint = rollupAcc.rollupTotalAlbumsHint ?? 0;
      const mergedRowFallback = rollupAcc.monitored;
      const nextTotal =
        aggregated.length > 0 ? aggregated.length : mergedRowFallback;
      const nextSummary: AggregateCatalogSummary & {
        rollupTotalAlbumsHint?: number;
      } = {
        available: rollupAcc.available,
        monitored: rollupAcc.monitored,
        missing: rollupAcc.missing,
        total: nextTotal,
        rollupTotalAlbumsHint: mergedHint,
      };

      setAggSummary((prev) => {
        const same =
          prev.available === nextSummary.available &&
          prev.monitored === nextSummary.monitored &&
          prev.missing === nextSummary.missing &&
          prev.total === nextSummary.total &&
          prev.rollupTotalAlbumsHint === nextSummary.rollupTotalAlbumsHint;
        return same ? prev : nextSummary;
      });

      if (aggFilter !== globalSearch) {
        setAggPage(0);
        setAggFilter(globalSearch);
      }

      setAggUpdated(new Date().toLocaleTimeString());
    } catch (error) {
      if (gen !== aggFetchGenRef.current) {
        return;
      }
      setAggRows([]);
      setAggSummary({
        available: 0,
        monitored: 0,
        missing: 0,
        total: 0,
        rollupTotalAlbumsHint: 0,
      });
      push(
        error instanceof Error ? error.message : "Failed to load aggregated Lidarr data",
        "error"
      );
    } finally {
      aggActiveLoadsRef.current -= 1;
      if (gen === aggFetchGenRef.current) {
        setAggLoading(false);
      }
    }
  }, [instances, globalSearch, push, aggFilter, aggArtistSync]);

  useEffect(() => {
    if (!active) return;
    void loadInstances();
  }, [active, loadInstances]);

  useEffect(() => {
    if (!active) return;
    if (!selection || selection === "aggregate") return;

    const selectionChanged = prevSelectionRef.current !== selection;

    if (selectionChanged) {
      instancePagesRef.current = {};
      setInstancePages({});
      setInstanceTotalPages(1);
      setInstancePage(0);
      prevSelectionRef.current = selection;
    }

    const query = globalSearchRef.current;
    void fetchInstanceRef.current(selection, selectionChanged ? 0 : instancePage, query, {
      preloadAll: false,
      showLoading: true,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- instancePage intentional; fetch identity via ref
  }, [active, selection, monitoredArtistOnly]);

  useEffect(() => {
    if (!active) return;
    if (selection !== "aggregate") return;
    void loadAggregate();
  }, [active, selection, loadAggregate]);

  useInterval(() => {
    if (document.visibilityState !== "visible") {
      return;
    }
    if (selection === "aggregate" && liveArr && aggActiveLoadsRef.current === 0) {
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
    return () => clearHandler(handler);
  }, [active, selection, register, clearHandler]);

  useInterval(
    () => {
      if (document.visibilityState !== "visible") return;
      if (selection && selection !== "aggregate") {
        const activeFilter = globalSearchRef.current?.trim?.() || "";
        if (activeFilter) return;
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

  useEffect(() => {
    if (selection === "aggregate") {
      setAggFilter(globalSearch);
    }
  }, [selection, globalSearch]);

  const filteredAggRows = useMemo(() => {
    const q = debouncedAggFilter ? debouncedAggFilter.toLowerCase() : "";
    const hasSearch = Boolean(q);

    return aggRows.filter((row) => {
      const artist = row.artist as Record<string, unknown>;
      if (hasSearch) {
        const name = ((artist?.["name"] as string | undefined) ?? "").toLowerCase();
        const inst = (row.__instance ?? "").toLowerCase();
        if (!name.includes(q) && !inst.includes(q)) {
          return false;
        }
      }
      return true;
    });
  }, [aggRows, debouncedAggFilter]);

  const sortedAggArtistRows = useMemo(() => {
    return [...filteredAggRows].sort((a, b) => {
      const aa = (a.artist as Record<string, unknown>) || {};
      const ba = (b.artist as Record<string, unknown>) || {};
      const ai = (a.__instance || "").toLowerCase();
      const bi = (b.__instance || "").toLowerCase();
      if (ai !== bi) return ai.localeCompare(bi);
      const an = String(aa["name"] || "").toLowerCase();
      const bn = String(ba["name"] || "").toLowerCase();
      return an.localeCompare(bn);
    });
  }, [filteredAggRows]);

  const isAggFiltered = Boolean(debouncedAggFilter);

  const aggPages = Math.max(1, Math.ceil(sortedAggArtistRows.length / LIDARR_AGG_PAGE_SIZE));
  const aggPageRows = useMemo(
    () =>
      sortedAggArtistRows.slice(
        aggPage * LIDARR_AGG_PAGE_SIZE,
        aggPage * LIDARR_AGG_PAGE_SIZE + LIDARR_AGG_PAGE_SIZE
      ),
    [sortedAggArtistRows, aggPage]
  );

  const allInstanceArtists = useMemo(() => {
    const pages = Object.keys(instancePages)
      .map(Number)
      .sort((a, b) => a - b);
    const rows: LidarrArtistBrowseEntry[] = [];
    pages.forEach((pg) => {
      if (instancePages[pg]) {
        rows.push(...instancePages[pg]);
      }
    });
    return rows;
  }, [instancePages]);

  // Visible page slice for the per-instance row store.  The instance browse view does
  // NOT paginate or filter client-side (server returns the page already), so we feed the
  // entire `allInstanceArtists` array into the store.  When the user changes selection or
  // monitored filter, the next fetch replaces it via the diff pipeline.
  useEffect(() => {
    instanceArtistRowsStore.store.sync(
      allInstanceArtists.map((row) => row as LidarrInstanceRow),
    );
  }, [allInstanceArtists, instanceArtistRowsStore.store]);

  useEffect(() => {
    instanceArtistRowsStore.store.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selection]);

  // Aggregate visible page sync: feed only the current page slice so the store mirrors
  // exactly what the table renders.  Page changes are an `add-remove` operation; live
  // polls inside the same page yield `update-only`.
  useEffect(() => {
    aggArtistRowsStore.store.sync(
      aggPageRows.map((row) => row as LidarrAggRowHashable),
    );
  }, [aggPageRows, aggArtistRowsStore.store]);

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
      <div className="card-header">Lidarr</div>
      <div className="card-body">
        <div className="split">
          <aside className="pane sidebar">
            {instances.length > 1 && (
              <button
                className={`btn ${isAggregate ? "active" : ""}`}
                onClick={() => setSelection("aggregate")}
              >
                All Lidarr
              </button>
            )}
            {instances.map((inst) => (
              <button
                key={inst.category}
                className={`btn ghost ${selection === inst.category ? "active" : ""}`}
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
                {instances.length > 1 && <option value="aggregate">All Lidarr</option>}
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
                  placeholder="Filter artists"
                  value={globalSearch}
                  onChange={(event) => setGlobalSearch(event.target.value)}
                />
              </div>
              {selection !== "aggregate" ? (
                <div className="field" style={{ flex: "0 0 auto", minWidth: "160px" }}>
                  <label>Artists</label>
                  <select
                    value={monitoredArtistOnly ? "monitored" : "all"}
                    onChange={(e) => setMonitoredArtistOnly(e.target.value === "monitored")}
                  >
                    <option value="all">All artists</option>
                    <option value="monitored">Monitored artists only</option>
                  </select>
                </div>
              ) : null}
              <div className="field" style={{ flex: "0 0 auto" }}>
                <label>View</label>
                <ArrBrowseModeToggle
                  mode={browseMode}
                  onChange={setBrowseMode}
                  idPrefix="lidarr"
                />
              </div>
            </div>

            {isAggregate ? (
              <LidarrAggregateView
                loading={aggLoading}
                rows={aggPageRows}
                rowOrder={aggArtistRowsStore.snapshot.rowOrder}
                rowsStore={aggArtistRowsStore.store}
                total={sortedAggArtistRows.length}
                page={aggPage}
                totalPages={aggPages}
                onPageChange={setAggPage}
                onRefresh={() => void loadAggregate({ showLoading: true })}
                lastUpdated={aggUpdated}
                summary={aggSummary}
                instanceCount={instances.length}
                isAggFiltered={isAggFiltered}
                browseMode={browseMode}
                instances={instances}
                onArtistSelect={(row) => {
                  const artist = row.artist as Record<string, unknown>;
                  const aid = artist?.["id"];
                  const name = String(artist?.["name"] ?? "Artist");
                  if (typeof aid !== "number") return;
                  const idKey = Number.isFinite(aid) ? `id:${aid}` : `n:${name}`;
                  setLidarrModal({
                    artistId: aid,
                    category: categoryForInstanceLabel(instances, row.__instance),
                    title: name,
                    rowId: `${row.__instance}::${idKey}`,
                    source: "aggregate",
                    instanceLabel: row.__instance,
                  });
                }}
              />
            ) : (
              <LidarrInstanceView
                loading={instanceLoading}
                data={instanceData}
                page={instancePage}
                totalPages={instanceTotalPages}
                pageSize={instancePageSize}
                allArtists={allInstanceArtists}
                monitoredFilter={monitoredArtistOnly ? "yes" : "all"}
                rowOrder={instanceArtistRowsStore.snapshot.rowOrder}
                rowsStore={instanceArtistRowsStore.store}
                onPageChange={(page) => {
                  setInstancePage(page);
                  void fetchInstanceRef.current(selection as string, page, instanceQuery, {
                    preloadAll: false,
                  });
                }}
                onRefresh={() => void handleInstanceRefresh()}
                lastUpdated={lastUpdated}
                showCatalogEmptyHint={
                  !instanceLoading &&
                  instanceData != null &&
                  (instanceData.total ?? 0) === 0 &&
                  allInstanceArtists.length === 0
                }
                category={selection as string}
                browseMode={browseMode}
                onArtistSelect={(entry) => {
                  const artist = entry.artist as Record<string, unknown>;
                  const aid = artist?.["id"];
                  const name = String(artist?.["name"] ?? "Artist");
                  if (typeof aid !== "number") return;
                  const idKey = Number.isFinite(aid) ? `id:${aid}` : `n:${name}`;
                  setLidarrModal({
                    artistId: aid,
                    category: selection as string,
                    title: name,
                    rowId: idKey,
                    source: "instance",
                    instanceLabel:
                      instances.find((i) => i.category === selection)?.name ??
                      String(selection),
                  });
                }}
              />
            )}
          </div>
        </div>
      </div>
      {lidarrModal ? (
        <LidarrDetailModal
          modal={lidarrModal}
          instanceStore={instanceArtistRowsStore.store}
          aggregateStore={aggArtistRowsStore.store}
          onClose={() => setLidarrModal(null)}
        />
      ) : null}
    </section>
  );
}
