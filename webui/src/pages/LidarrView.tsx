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
  LidarrAlbum,
  LidarrAlbumsResponse,
} from "../api/types";
import { useToast } from "../context/ToastContext";
import { useSearch } from "../context/SearchContext";
import { useWebUI } from "../context/WebUIContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
import RefreshIcon from "../icons/refresh-arrow.svg";
import RestartIcon from "../icons/refresh-arrow.svg";

interface LidarrAggRow extends LidarrAlbum {
  __instance: string;
}

type LidarrSortKey = "title" | "artistName" | "releaseDate" | "monitored" | "hasFile";
type LidarrAggSortKey = "__instance" | LidarrSortKey;

const LIDARR_PAGE_SIZE = 50;
const LIDARR_AGG_PAGE_SIZE = 50;
const LIDARR_AGG_FETCH_SIZE = 500;

interface LidarrAggregateViewProps {
  loading: boolean;
  rows: LidarrAggRow[];
  total: number;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  lastUpdated: string | null;
  onSort: (key: LidarrAggSortKey) => void;
  summary: { available: number; monitored: number; missing: number; total: number };
  instanceCount: number;
}

function LidarrAggregateView({
  loading,
  rows,
  total,
  page,
  totalPages,
  onPageChange,
  onRefresh,
  lastUpdated,
  onSort,
  summary,
  instanceCount,
}: LidarrAggregateViewProps): JSX.Element {
  const columns = useMemo<ColumnDef<LidarrAggRow>[]>(
    () => [
      ...(instanceCount > 1 ? [{
        accessorKey: "__instance",
        header: "Instance",
        size: 150,
      },] : []),
      {
        accessorKey: "title",
        header: "Album",
        cell: (info) => info.getValue(),
      },
      {
        accessorKey: "artistName",
        header: "Artist",
        size: 150,
      },
      {
        accessorKey: "releaseDate",
        header: "Release Date",
        cell: (info) => {
          const date = info.getValue() as string | undefined;
          if (!date) return <span className="hint">—</span>;
          return new Date(date).toLocaleDateString();
        },
        size: 120,
      },
      {
        accessorKey: "monitored",
        header: "Monitored",
        cell: (info) =>
          (info.getValue() as boolean) ? <span className="table-badge">Yes</span> : <span>No</span>,
        size: 100,
      },
      {
        accessorKey: "hasFile",
        header: "Has File",
        cell: (info) =>
          (info.getValue() as boolean) ? <span className="table-badge">Yes</span> : <span>No</span>,
        size: 100,
      },
      {
        accessorKey: "reason",
        header: "Reason",
        cell: (info) => {
          const reason = info.getValue() as string | null;
          if (!reason) return <span className="hint">—</span>;
          return <span className="table-badge table-badge-reason">{reason}</span>;
        },
        size: 120,
      },
    ],
    [instanceCount]
  );

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          Aggregated albums across all instances{" "}
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
      ) : total ? (
        <div className="table-wrapper">
          <table className="responsive-table">
            <thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className={header.column.getCanSort() ? "sortable" : ""}
                      onClick={() => {
                        const sortKey = header.id as LidarrAggSortKey;
                        onSort(sortKey);
                      }}
                    >
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
                const album = row.original;
                const stableKey = `${album.__instance}-${album.title}-${album.artistName}`;
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
        <div className="hint">No albums found.</div>
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
}

interface LidarrInstanceViewProps {
  loading: boolean;
  data: LidarrAlbumsResponse | null;
  page: number;
  totalPages: number;
  pageSize: number;
  allAlbums: LidarrAlbum[];
  onlyMissing: boolean;
  reasonFilter: string;
  onPageChange: (page: number) => void;
  onRestart: () => void;
  lastUpdated: string | null;
}

function LidarrInstanceView({
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
}: LidarrInstanceViewProps): JSX.Element {
  const filteredAlbums = useMemo(() => {
    let albums = allAlbums;
    if (onlyMissing) {
      albums = albums.filter((a) => !a.hasFile);
    }
    return albums;
  }, [allAlbums, onlyMissing]);

  const reasonFilteredAlbums = useMemo(() => {
    if (reasonFilter === "all") return filteredAlbums;
    if (reasonFilter === "none") {
      return filteredAlbums.filter((a) => !a.reason);
    }
    return filteredAlbums.filter((a) => a.reason === reasonFilter);
  }, [filteredAlbums, reasonFilter]);

  const columns = useMemo<ColumnDef<LidarrAlbum>[]>(
    () => [
      {
        accessorKey: "title",
        header: "Album",
        cell: (info) => info.getValue(),
      },
      {
        accessorKey: "artistName",
        header: "Artist",
        size: 150,
      },
      {
        accessorKey: "releaseDate",
        header: "Release Date",
        cell: (info) => {
          const date = info.getValue() as string | undefined;
          if (!date) return <span className="hint">—</span>;
          return new Date(date).toLocaleDateString();
        },
        size: 120,
      },
      {
        accessorKey: "monitored",
        header: "Monitored",
        cell: (info) =>
          (info.getValue() as boolean) ? <span className="table-badge">Yes</span> : <span>No</span>,
        size: 100,
      },
      {
        accessorKey: "hasFile",
        header: "Has File",
        cell: (info) =>
          (info.getValue() as boolean) ? <span className="table-badge">Yes</span> : <span>No</span>,
        size: 100,
      },
      {
        accessorKey: "reason",
        header: "Reason",
        cell: (info) => {
          const reason = info.getValue() as string | null;
          if (!reason) return <span className="hint">—</span>;
          return <span className="table-badge table-badge-reason">{reason}</span>;
        },
        size: 120,
      },
    ],
    []
  );

  const table = useReactTable({
    data: reasonFilteredAlbums.slice(page * pageSize, page * pageSize + pageSize),
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          {data?.counts
            ? `Available: ${data.counts.available ?? 0} • Monitored: ${
                data.counts.monitored ?? 0
              }`
            : ""}
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
      ) : allAlbums.length ? (
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
                const album = row.original;
                const stableKey = `${album.title}-${album.artistName}`;
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
        <div className="hint">No albums found.</div>
      )}

      {reasonFilteredAlbums.length > pageSize && (
        <div className="pagination">
          <div>
            Page {page + 1} of {totalPages} ({reasonFilteredAlbums.length.toLocaleString()} items · page size{" "}
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
}

export function LidarrView({ active }: { active: boolean }): JSX.Element {
  const { push } = useToast();
  const {
    value: globalSearch,
    setValue: setGlobalSearch,
    register,
    clearHandler,
  } = useSearch();
  const { liveArr } = useWebUI();

  const [instances, setInstances] = useState<ArrInfo[]>([]);
  const [selection, setSelection] = useState<string | "">("aggregate");
  const [instanceData, setInstanceData] = useState<LidarrAlbumsResponse | null>(null);
  const [instancePage, setInstancePage] = useState(0);
  const [instanceQuery, setInstanceQuery] = useState("");
  const [instanceLoading, setInstanceLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [instancePages, setInstancePages] = useState<Record<number, LidarrAlbum[]>>({});
  const [instancePageSize, setInstancePageSize] = useState(LIDARR_PAGE_SIZE);
  const [instanceTotalPages, setInstanceTotalPages] = useState(1);
  const instanceKeyRef = useRef<string>("");
  const instancePagesRef = useRef<Record<number, LidarrAlbum[]>>({});
  const globalSearchRef = useRef(globalSearch);
  const backendReadyWarnedRef = useRef(false);

  const [aggRows, setAggRows] = useState<LidarrAggRow[]>([]);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggPage, setAggPage] = useState(0);
  const [aggFilter, setAggFilter] = useState("");
  const [aggUpdated, setAggUpdated] = useState<string | null>(null);
  const [aggSort, setAggSort] = useState<{
    key: LidarrAggSortKey;
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
          : "Unable to load Lidarr instances",
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
        const results: { page: number; albums: LidarrAlbum[] }[] = [];
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
            const existingAlbums = prev[page] ?? [];
            if (JSON.stringify(existingAlbums) !== JSON.stringify(albums)) {
              next[page] = albums;
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

        // Smart diffing: only update if data actually changed
        const existingAlbums = instancePagesRef.current[resolvedPage] ?? [];
        const albumsChanged = JSON.stringify(existingAlbums) !== JSON.stringify(albums);

        if (keyChanged || albumsChanged) {
          setInstancePages((prev) => {
            const base = keyChanged ? {} : prev;
            const next = { ...base, [resolvedPage]: albums };
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
    if (showLoading) {
      setAggLoading(true);
    }
    try {
      const aggregated: LidarrAggRow[] = [];
      let totalAvailable = 0;
      let totalMonitored = 0;
      for (const inst of instances) {
        let page = 0;
        let counted = false;
        const label = inst.name || inst.category;
        while (page < 100) {
          const res = await getLidarrAlbums(
            inst.category,
            page,
            LIDARR_AGG_FETCH_SIZE,
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
          const albums = res.albums ?? [];
          albums.forEach((album) => {
            aggregated.push({ ...album, __instance: label });
          });
          if (!albums.length || albums.length < LIDARR_AGG_FETCH_SIZE) break;
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
        missing: aggregated.length - totalAvailable,
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
          : "Failed to load aggregated Lidarr data",
        "error"
      );
    } finally {
      setAggLoading(false);
    }
  }, [instances, globalSearch, push]);

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
    let rows = aggRows;
    if (aggFilter) {
      const q = aggFilter.toLowerCase();
      rows = rows.filter((row) => {
        const title = (row.title ?? "").toString().toLowerCase();
        const artist = (row.artistName ?? "").toString().toLowerCase();
        const instance = (row.__instance ?? "").toLowerCase();
        return title.includes(q) || artist.includes(q) || instance.includes(q);
      });
    }
    if (onlyMissing) {
      rows = rows.filter((row) => !row.hasFile);
    }
    if (reasonFilter !== "all") {
      if (reasonFilter === "none") {
        rows = rows.filter((row) => !row.reason);
      } else {
        rows = rows.filter((row) => row.reason === reasonFilter);
      }
    }
    return rows;
  }, [aggRows, aggFilter, onlyMissing, reasonFilter]);

  const sortedAggRows = useMemo(() => {
    const list = [...filteredAggRows];
    const getValue = (row: LidarrAggRow, key: LidarrAggSortKey) => {
      switch (key) {
        case "__instance":
          return (row.__instance || "").toLowerCase();
        case "title":
          return (row.title || "").toLowerCase();
        case "artistName":
          return (row.artistName || "").toLowerCase();
        case "releaseDate":
          return row.releaseDate ?? "";
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
    Math.ceil(sortedAggRows.length / LIDARR_AGG_PAGE_SIZE)
  );
  const aggPageRows = sortedAggRows.slice(
    aggPage * LIDARR_AGG_PAGE_SIZE,
    aggPage * LIDARR_AGG_PAGE_SIZE + LIDARR_AGG_PAGE_SIZE
  );

  const allInstanceAlbums = useMemo(() => {
    const pages = Object.keys(instancePages)
      .map(Number)
      .sort((a, b) => a - b);
    const rows: LidarrAlbum[] = [];
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
                  <option value="none">Not Being Searched</option>
                  <option value="Missing">Missing</option>
                  <option value="Quality">Quality</option>
                  <option value="CustomFormat">Custom Format</option>
                  <option value="Upgrade">Upgrade</option>
                  <option value="Scheduled search">Scheduled Search</option>
                </select>
              </div>
            </div>

            {isAggregate ? (
              <LidarrAggregateView
                loading={aggLoading}
                rows={aggPageRows}
                total={sortedAggRows.length}
                page={aggPage}
                totalPages={aggPages}
                onPageChange={setAggPage}
                onRefresh={() => void loadAggregate({ showLoading: true })}
                lastUpdated={aggUpdated}
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
                instanceCount={instances.length}
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
