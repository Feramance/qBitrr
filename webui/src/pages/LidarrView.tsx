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
  getLidarrAlbums,
  restartArr,
} from "../api/client";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
} from "@tanstack/react-table";
import type {
  ArrInfo,
  LidarrAlbumEntry,
  LidarrAlbumsResponse,
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
import { LidarrAlbumDetailBody } from "../components/arr/LidarrAlbumDetailBody";
import { StableTable } from "../components/StableTable";
import { lidarrAlbumThumbnailUrl } from "../utils/arrThumbnailUrl";
import RefreshIcon from "../icons/refresh-arrow.svg";
import {
  AGGREGATE_FETCH_CHUNK_SIZE,
  AGGREGATE_POLL_INTERVAL_MS,
  pagesFromAggregateTotal,
  summarizeLidarrAlbumAggRows,
  AGG_FALLBACK_AGGREGATE_PAGES_MAX,
} from "../constants/arrAggregateFetch";

interface LidarrAggRow extends LidarrAlbumEntry {
  __instance: string;
  [key: string]: unknown;
}

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
  onAlbumSelect: (row: LidarrAggRow) => void;
}

const LidarrAggregateView = memo(function LidarrAggregateView({
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
  browseMode,
  instances,
  onAlbumSelect,
}: LidarrAggregateViewProps): JSX.Element {
  const columns = useMemo<ColumnDef<LidarrAggRow>[]>(
    () => [
      ...(instanceCount > 1
        ? [
            {
              id: "instance",
              header: "Instance",
              cell: (info: { row: { original: LidarrAggRow } }) =>
                info.row.original.__instance,
            },
          ]
        : []),
      {
        id: "album",
        header: "Album",
        cell: (info: { row: { original: LidarrAggRow } }) => {
          const d = info.row.original.album as Record<string, unknown>;
          return (d?.["title"] as string | undefined) || "—";
        },
      },
      {
        id: "artist",
        header: "Artist",
        cell: (info: { row: { original: LidarrAggRow } }) => {
          const d = info.row.original.album as Record<string, unknown>;
          return (d?.["artistName"] as string | undefined) || "—";
        },
      },
      {
        id: "releaseDate",
        header: "Release Date",
        cell: (info: { row: { original: LidarrAggRow } }) => {
          const d = info.row.original.album as Record<string, unknown>;
          const date = d?.["releaseDate"] as string | undefined;
          if (!date) return <span className="hint">—</span>;
          return new Date(date).toLocaleDateString();
        },
        size: 120,
      },
      {
        id: "monitored",
        header: "Monitored",
        cell: (info: { row: { original: LidarrAggRow } }) => {
          const d = info.row.original.album as Record<string, unknown>;
          const monitored = d?.["monitored"] as boolean | undefined;
          return (
            <span
              className={`track-status ${monitored ? "available" : "missing"}`}
            >
              {monitored ? "✓" : "✗"}
            </span>
          );
        },
        size: 100,
      },
      {
        id: "hasFile",
        header: "Has File",
        cell: (info: { row: { original: LidarrAggRow } }) => {
          const d = info.row.original.album as Record<string, unknown>;
          const hasFile = d?.["hasFile"] as boolean | undefined;
          return (
            <span
              className={`track-status ${hasFile ? "available" : "missing"}`}
            >
              {hasFile ? "✓" : "✗"}
            </span>
          );
        },
        size: 100,
      },
      {
        id: "qualityProfileName",
        header: "Quality Profile",
        cell: (info: { row: { original: LidarrAggRow } }) => {
          const d = info.row.original.album as Record<string, unknown>;
          return (d?.["qualityProfileName"] as string | null | undefined) || "—";
        },
        size: 150,
      },
      {
        id: "reason",
        header: "Reason",
        cell: (info: { row: { original: LidarrAggRow } }) => {
          const d = info.row.original.album as Record<string, unknown>;
          const reason = d?.["reason"] as string | null | undefined;
          if (!reason) {
            return (
              <span className="table-badge table-badge-reason">
                Not being searched
              </span>
            );
          }
          return (
            <span className="table-badge table-badge-reason">{reason}</span>
          );
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
          Aggregated albums across all instances{" "}
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
          • <strong>Total:</strong>{" "}
          {summary.total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          {isAggFiltered && total < summary.total && (
            <>
              {" "}
              • <strong>Filtered:</strong>{" "}
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
          <span className="spinner" /> Loading Lidarr library…
        </div>
      ) : !loading &&
        total === 0 &&
        summary.total === 0 &&
        instanceCount > 0 ? (
        <div className="hint">
          <p>No albums found in the local catalog.</p>
          <p>
            qBitrr may still be importing from your Lidarr instances into the SQLite database.
            Check logs or refresh in a moment.
          </p>
        </div>
      ) : total ? (
        browseMode === "list" ? (
          <StableTable
            data={rows}
            columns={columns}
            getRowKey={(row) => {
              const a = row.album as Record<string, unknown>;
              return `${row.__instance}-${String(a?.["title"])}-${String(a?.["artistName"])}`;
            }}
            onRowClick={onAlbumSelect}
          />
        ) : (
          <div className="arr-icon-grid">
            {rows.map((row) => {
              const cat = categoryForInstanceLabel(instances, row.__instance);
              const album = row.album as Record<string, unknown>;
              const id = album?.["id"] as number | undefined;
              const title = (album?.["title"] as string | undefined) || "—";
              const artist = (album?.["artistName"] as string | undefined) || "—";
              const thumb =
                id != null && cat ? lidarrAlbumThumbnailUrl(cat, id) : "";
              return (
                <button
                  key={`${row.__instance}-${title}-${artist}`}
                  type="button"
                  className="arr-movie-tile card"
                  onClick={() => onAlbumSelect(row)}
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
                      <div className="arr-movie-tile__instance">
                        {row.__instance}
                      </div>
                    )}
                    <div className="arr-movie-tile__title">{title}</div>
                    <div className="arr-movie-tile__sub">{artist}</div>
                  </div>
                </button>
              );
            })}
          </div>
        )
      ) : (
        <div className="hint">No albums found.</div>
      )}

      {total > 0 && (
        <div className="pagination">
          <div>
            Page {page + 1} of {totalPages} ({total.toLocaleString()} items ·
            page size {LIDARR_AGG_PAGE_SIZE})
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

interface LidarrInstanceViewProps {
  loading: boolean;
  data: LidarrAlbumsResponse | null;
  page: number;
  totalPages: number;
  pageSize: number;
  allAlbums: LidarrAlbumEntry[];
  onlyMissing: boolean;
  reasonFilter: string;
  onPageChange: (page: number) => void;
  onRestart: () => void;
  lastUpdated: string | null;
  category: string;
  browseMode: "list" | "icon";
  onAlbumSelect: (entry: LidarrAlbumEntry) => void;
  /** True when API reports zero albums and catalog may still be syncing. */
  showCatalogEmptyHint?: boolean;
}

const LidarrInstanceView = memo(function LidarrInstanceView({
  loading,
  data,
  page,
  totalPages,
  pageSize,
  allAlbums,
  onlyMissing,
  reasonFilter,
  onPageChange,
  onRestart,
  lastUpdated,
  category,
  browseMode,
  onAlbumSelect,
  showCatalogEmptyHint = false,
}: LidarrInstanceViewProps): JSX.Element {
  const filteredAlbums = useMemo(() => {
    let albums = allAlbums;
    if (onlyMissing) {
      albums = albums.filter((entry) => {
        const albumData = entry.album as Record<string, unknown>;
        return !(albumData?.["hasFile"] as boolean | undefined);
      });
    }
    return albums;
  }, [allAlbums, onlyMissing]);

  const reasonFilteredAlbums = useMemo(() => {
    if (reasonFilter === "all") return filteredAlbums;
    if (reasonFilter === "Not being searched") {
      return filteredAlbums.filter((entry) => {
        const albumData = entry.album as Record<string, unknown>;
        return (
          albumData?.["reason"] === "Not being searched" ||
          !albumData?.["reason"]
        );
      });
    }
    return filteredAlbums.filter((entry) => {
      const albumData = entry.album as Record<string, unknown>;
      return albumData?.["reason"] === reasonFilter;
    });
  }, [filteredAlbums, reasonFilter]);

  const totalAlbums = useMemo(() => allAlbums.length, [allAlbums]);
  const isFiltered = reasonFilter !== "all" || onlyMissing;
  const filteredCount = reasonFilteredAlbums.length;

  const columns = useMemo<ColumnDef<LidarrAlbumEntry>[]>(
    () => [
      {
        id: "title",
        header: "Album",
        cell: (info) => {
          const albumData = info.row.original.album as Record<string, unknown>;
          return (albumData?.["title"] as string | undefined) || "Unknown Album";
        },
      },
      {
        id: "artistName",
        header: "Artist",
        cell: (info) => {
          const albumData = info.row.original.album as Record<string, unknown>;
          return (albumData?.["artistName"] as string | undefined) || "Unknown Artist";
        },
        size: 150,
      },
      {
        id: "releaseDate",
        header: "Release Date",
        cell: (info) => {
          const albumData = info.row.original.album as Record<string, unknown>;
          const date = albumData?.["releaseDate"] as string | undefined;
          if (!date) return <span className="hint">—</span>;
          return new Date(date).toLocaleDateString();
        },
        size: 120,
      },
      {
        id: "monitored",
        header: "Monitored",
        cell: (info) => {
          const albumData = info.row.original.album as Record<string, unknown>;
          const monitored = albumData?.["monitored"] as boolean | undefined;
          return (
            <span
              className={`track-status ${monitored ? "available" : "missing"}`}
            >
              {monitored ? "✓" : "✗"}
            </span>
          );
        },
        size: 100,
      },
      {
        id: "hasFile",
        header: "Has File",
        cell: (info) => {
          const albumData = info.row.original.album as Record<string, unknown>;
          const hasFile = albumData?.["hasFile"] as boolean | undefined;
          return (
            <span
              className={`track-status ${hasFile ? "available" : "missing"}`}
            >
              {hasFile ? "✓" : "✗"}
            </span>
          );
        },
        size: 100,
      },
      {
        id: "qualityProfileName",
        header: "Quality Profile",
        cell: (info) => {
          const albumData = info.row.original.album as Record<string, unknown>;
          const profileName = albumData?.["qualityProfileName"] as
            | string
            | null
            | undefined;
          return profileName || "—";
        },
        size: 150,
      },
      {
        id: "reason",
        header: "Reason",
        cell: (info) => {
          const albumData = info.row.original.album as Record<string, unknown>;
          const reason = albumData?.["reason"] as string | null | undefined;
          if (!reason) {
            return (
              <span className="table-badge table-badge-reason">
                Not being searched
              </span>
            );
          }
          return (
            <span className="table-badge table-badge-reason">{reason}</span>
          );
        },
        size: 120,
      },
    ],
    []
  );

  const paged = useMemo(
    () =>
      reasonFilteredAlbums.slice(
        page * pageSize,
        page * pageSize + pageSize
      ),
    [reasonFilteredAlbums, page, pageSize]
  );

  const table = useReactTable({
    data: paged,
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
              {(data.counts.available ?? 0).toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}{" "}
              • <strong>Monitored:</strong>{" "}
              {(data.counts.monitored ?? 0).toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}{" "}
              • <strong>Missing:</strong>{" "}
              {(
                (data.counts.monitored ?? 0) - (data.counts.available ?? 0)
              ).toLocaleString(undefined, { maximumFractionDigits: 0 })}{" "}
              • <strong>Total:</strong>{" "}
              {totalAlbums.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              {isFiltered && filteredCount < totalAlbums && (
                <>
                  {" "}
                  • <strong>Filtered:</strong>{" "}
                  {filteredCount.toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}{" "}
                  of{" "}
                  {totalAlbums.toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}
                </>
              )}
            </>
          ) : (
            "Loading album information..."
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
          <span className="spinner" /> Loading…
        </div>
      ) : allAlbums.length ? (
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
                {table.getRowModel().rows.map((row) => {
                  const albumEntry = row.original;
                  const albumData = albumEntry.album as Record<string, unknown>;
                  const title = (albumData?.["title"] as string | undefined) || "Unknown";
                  const artistName =
                    (albumData?.["artistName"] as string | undefined) || "Unknown";
                  const stableKey = `${title}-${artistName}`;
                  return (
                    <tr
                      key={stableKey}
                      onClick={() => onAlbumSelect(albumEntry)}
                      style={{ cursor: "pointer" }}
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
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="arr-icon-grid">
            {paged.map((entry) => {
              const ad = entry.album as Record<string, unknown>;
              const id = ad?.["id"] as number | undefined;
              const title = (ad?.["title"] as string | undefined) || "—";
              const artist = (ad?.["artistName"] as string | undefined) || "—";
              const thumb =
                id != null && category
                  ? lidarrAlbumThumbnailUrl(category, id)
                  : "";
              return (
                <button
                  key={`${title}-${artist}-${id}`}
                  type="button"
                  className="arr-movie-tile card"
                  onClick={() => onAlbumSelect(entry)}
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
                    <div className="arr-movie-tile__title">{title}</div>
                    <div className="arr-movie-tile__sub">{artist}</div>
                  </div>
                </button>
              );
            })}
          </div>
        )
      ) : showCatalogEmptyHint ? (
        <div className="hint">
          <p>No albums in the local catalog.</p>
          <p>
            qBitrr may still be syncing your Lidarr library. Check logs or try again shortly.
          </p>
        </div>
      ) : (
        <div className="hint">No albums match the current filters.</div>
      )}

      {reasonFilteredAlbums.length > pageSize && (
        <div className="pagination">
          <div>
            Page {page + 1} of {totalPages} (
            {reasonFilteredAlbums.length.toLocaleString()} items · page size{" "}
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
  const [lidarrDetail, setLidarrDetail] = useState<{
    entry: LidarrAlbumEntry | LidarrAggRow;
    category: string;
  } | null>(null);

  const [instances, setInstances] = useState<ArrInfo[]>([]);
  const [selection, setSelection] = useState<string | "">("");
  const [instanceData, setInstanceData] = useState<LidarrAlbumsResponse | null>(null);
  const [instancePage, setInstancePage] = useState(0);
  const [instanceQuery, setInstanceQuery] = useState("");
  const [instanceLoading, setInstanceLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [instancePages, setInstancePages] = useState<Record<number, LidarrAlbumEntry[]>>({});
  const [instancePageSize, setInstancePageSize] = useState(LIDARR_PAGE_SIZE);
  const [instanceTotalPages, setInstanceTotalPages] = useState(1);
  const instanceKeyRef = useRef<string>("");
  const instancePagesRef = useRef<Record<number, LidarrAlbumEntry[]>>({});
  const globalSearchRef = useRef(globalSearch);
  globalSearchRef.current = globalSearch;
  const selectionRef = useRef(selection);
  selectionRef.current = selection;
  const backendReadyWarnedRef = useRef(false);
  const aggFetchGenRef = useRef(0);
  const aggActiveLoadsRef = useRef(0);
  const prevSelectionRef = useRef<string | "">(selection);

  // Smart data sync for instance albums
  const instanceAlbumSync = useDataSync<LidarrAlbumEntry>({
    getKey: (album) => {
      const albumData = album.album as Record<string, unknown>;
      const artistName = (albumData?.["artistName"] as string | undefined) || "";
      const title = (albumData?.["title"] as string | undefined) || "";
      return `${artistName}-${title}`;
    },
    hashFields: ['album', 'tracks', 'totals'],
  });

  const [aggRows, setAggRows] = useState<LidarrAggRow[]>([]);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggPage, setAggPage] = useState(0);
  const [aggFilter, setAggFilter] = useState("");
  const [aggUpdated, setAggUpdated] = useState<string | null>(null);
  const debouncedAggFilter = useDebounce(aggFilter, 300);

  // Smart data sync for aggregate albums
  const aggAlbumSync = useDataSync<LidarrAggRow>({
    getKey: (album) => {
      const albumData = album.album as Record<string, unknown>;
      const artistName = (albumData?.["artistName"] as string | undefined) || "";
      const title = (albumData?.["title"] as string | undefined) || "";
      return `${album.__instance}-${artistName}-${title}`;
    },
    hashFields: ['__instance', 'album', 'tracks', 'totals'],
  });

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
      key: string
    ) => {
      if (!pages.length) return;
      try {
        const results: { page: number; albums: LidarrAlbumEntry[] }[] = [];
        for (const pg of pages) {
          const res = await getLidarrAlbums(category, pg, pageSize, query);
          const resolved = res.page ?? pg;
          results.push({ page: resolved, albums: res.albums ?? [] });
          if (instanceKeyRef.current !== key) {
            return;
          }
        }
        if (instanceKeyRef.current !== key) return;

        // Smart diffing: only update pages that actually changed
        setInstancePages((prev) => {
          const next = { ...prev };
          let hasChanges = false;
          for (const { page, albums } of results) {
            // Use hash-based comparison for each page
            const syncResult = instanceAlbumSync.syncData(albums);
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
        const response = await getLidarrAlbums(
          category,
          page,
          LIDARR_PAGE_SIZE,
          query
        );
        setInstanceData(response);
        const resolvedPage = response.page ?? page;
        setInstancePage(resolvedPage);
        setInstanceQuery(query);
        const pageSize = response.page_size ?? LIDARR_PAGE_SIZE;
        const totalItems = response.total ?? (response.albums ?? []).length;
        const totalPages = Math.max(1, Math.ceil((totalItems || 0) / pageSize));
        setInstancePageSize(pageSize);
        setInstanceTotalPages(totalPages);
        const albums = response.albums ?? [];
        const existingPages = keyChanged ? {} : instancePagesRef.current;

        if (keyChanged) {
          instanceAlbumSync.reset();
        }

        // Smart diffing using hash-based change detection
        const syncResult = instanceAlbumSync.syncData(albums);
        const albumsChanged = syncResult.hasChanges;

        if (keyChanged || albumsChanged) {
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
            : `Failed to load ${category} albums`,
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
    const gen = ++aggFetchGenRef.current;
    aggActiveLoadsRef.current += 1;
    if (showLoading) {
      setAggLoading(true);
    }
    const chunk = AGGREGATE_FETCH_CHUNK_SIZE;
    try {
      const aggregated: LidarrAggRow[] = [];
      let progressFirstPaint = false;
      for (const inst of instances) {
        const label = inst.name || inst.category;
        let countedForInstance = false;
        let pagesPlanned: number | null = null;
        let pageIdx = 0;

        while (true) {
          const res = await getLidarrAlbums(
            inst.category,
            pageIdx,
            chunk,
            ""
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
          const albumEntries = res.albums ?? [];
          albumEntries.forEach((entry) => {
            aggregated.push({ ...entry, __instance: label });
          });

          const albumSyncResult = aggAlbumSync.syncData(aggregated);
          if (albumSyncResult.hasChanges) {
            setAggRows(albumSyncResult.data);
            const next = summarizeLidarrAlbumAggRows(aggregated);
            setAggSummary((prev) => {
              if (
                prev.available === next.available &&
                prev.monitored === next.monitored &&
                prev.missing === next.missing &&
                prev.total === next.total
              ) {
                return prev;
              }
              return next;
            });
          }
          if (showLoading && !progressFirstPaint && albumSyncResult.data.length > 0) {
            setAggLoading(false);
            progressFirstPaint = true;
          }

          pageIdx += 1;

          if (pagesPlanned !== null) {
            if (pageIdx >= pagesPlanned) break;
          } else {
            if (!albumEntries.length || albumEntries.length < chunk) break;
            if (pageIdx >= AGG_FALLBACK_AGGREGATE_PAGES_MAX) break;
          }
        }
      }

      const albumSyncResult = aggAlbumSync.syncData(aggregated);
      const rowsChanged = albumSyncResult.hasChanges;

      if (rowsChanged) {
        setAggRows(albumSyncResult.data);
      }

      const newSummary = summarizeLidarrAlbumAggRows(aggregated);

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
          : "Failed to load aggregated Lidarr data",
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

    const selectionChanged = prevSelectionRef.current !== selection;

    // Reset page and cache only when selection changes
    if (selectionChanged) {
      instancePagesRef.current = {};
      setInstancePages({});
      setInstanceTotalPages(1);
      setInstancePage(0);
      prevSelectionRef.current = selection;
    }

    // Fetch data: use page 0 if selection changed, current page otherwise
    const query = globalSearchRef.current;
    void fetchInstance(selection, selectionChanged ? 0 : instancePage, query, {
      preloadAll: false,
      showLoading: true,
    });
  }, [active, selection, fetchInstance, instancePage]);

  useEffect(() => {
    if (!active) return;
    if (selection !== "aggregate") return;
    void loadAggregate();
  }, [active, selection, loadAggregate]);

  useInterval(() => {
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
        void fetchInstance(selection, 0, term, {
          preloadAll: false,
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
      const albumData = row.album as Record<string, unknown>;

      // Search filter
      if (hasSearchFilter) {
        const title = ((albumData?.["title"] as string | undefined) ?? "").toString().toLowerCase();
        const artist = ((albumData?.["artistName"] as string | undefined) ?? "").toString().toLowerCase();
        const instance = (row.__instance ?? "").toLowerCase();
        if (!title.includes(q) && !artist.includes(q) && !instance.includes(q)) {
          return false;
        }
      }

      // Missing filter
      if (onlyMissing && (albumData?.["hasFile"] as boolean | undefined)) {
        return false;
      }

      // Reason filter
      if (hasReasonFilter) {
        const reason = albumData?.["reason"];
        if (reasonFilter === "Not being searched") {
          if (reason !== "Not being searched" && reason) {
            return false;
          }
        } else if (reason !== reasonFilter) {
          return false;
        }
      }

      return true;
    });
  }, [aggRows, debouncedAggFilter, onlyMissing, reasonFilter]);

  const isAggFiltered =
    Boolean(debouncedAggFilter) ||
    reasonFilter !== "all" ||
    onlyMissing;

  const sortedAggAlbums = useMemo(() => {
    return [...filteredAggRows].sort((a, b) => {
      const ad = (a.album as Record<string, unknown>) || {};
      const bd = (b.album as Record<string, unknown>) || {};
      const ai = (a.__instance || "").toLowerCase();
      const bi = (b.__instance || "").toLowerCase();
      if (ai !== bi) return ai.localeCompare(bi);
      const ar = String(ad["artistName"] || "").toLowerCase();
      const br = String(bd["artistName"] || "").toLowerCase();
      if (ar !== br) return ar.localeCompare(br);
      return String(ad["title"] || "").localeCompare(
        String(bd["title"] || "")
      );
    });
  }, [filteredAggRows]);

  const aggPages = Math.max(
    1,
    Math.ceil(sortedAggAlbums.length / LIDARR_AGG_PAGE_SIZE)
  );
  const aggPageRows = useMemo(
    () =>
      sortedAggAlbums.slice(
        aggPage * LIDARR_AGG_PAGE_SIZE,
        aggPage * LIDARR_AGG_PAGE_SIZE + LIDARR_AGG_PAGE_SIZE
      ),
    [sortedAggAlbums, aggPage]
  );

  const allInstanceAlbums = useMemo(() => {
    const pages = Object.keys(instancePages)
      .map(Number)
      .sort((a, b) => a - b);
    const rows: LidarrAlbumEntry[] = [];
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
                  placeholder="Filter albums"
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
                  <option value="all">All Albums</option>
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
                  idPrefix="lidarr"
                />
              </div>
            </div>

            {isAggregate ? (
              <LidarrAggregateView
                loading={aggLoading}
                rows={aggPageRows}
                total={sortedAggAlbums.length}
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
                onAlbumSelect={(row) =>
                  setLidarrDetail({
                    entry: row,
                    category: categoryForInstanceLabel(
                      instances,
                      row.__instance
                    ),
                  })
                }
              />
            ) : (
              <LidarrInstanceView
                loading={instanceLoading}
                data={instanceData}
                page={instancePage}
                totalPages={instanceTotalPages}
                pageSize={instancePageSize}
                allAlbums={allInstanceAlbums}
                onlyMissing={onlyMissing}
                reasonFilter={reasonFilter}
                onPageChange={(page) => {
                  setInstancePage(page);
                  void fetchInstance(selection as string, page, instanceQuery, {
                    preloadAll: false,
                  });
                }}
                onRestart={() => void handleRestart()}
                lastUpdated={lastUpdated}
                showCatalogEmptyHint={
                  !instanceLoading &&
                  instanceData != null &&
                  (instanceData.total ?? 0) === 0 &&
                  allInstanceAlbums.length === 0
                }
                category={selection as string}
                browseMode={browseMode}
                onAlbumSelect={(entry) =>
                  setLidarrDetail({
                    entry,
                    category: selection as string,
                  })
                }
              />
            )}
          </div>
        </div>
      </div>
      {lidarrDetail ? (
        <ArrModal
          title={String(
            (lidarrDetail.entry.album as Record<string, unknown>)?.["title"] ??
              "Album"
          )}
          onClose={() => setLidarrDetail(null)}
          maxWidth={720}
        >
          <LidarrAlbumDetailBody
            entry={lidarrDetail.entry}
            category={lidarrDetail.category}
          />
        </ArrModal>
      ) : null}
    </section>
  );
}
