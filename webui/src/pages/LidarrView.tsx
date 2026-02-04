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
  LidarrAlbumEntry,
  LidarrAlbumsResponse,
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

interface LidarrAggRow extends LidarrAlbumEntry {
  __instance: string;
  [key: string]: unknown;
}

interface LidarrTrackRow {
  __instance: string;
  artistName: string;
  albumTitle: string;
  trackNumber: number;
  title: string;
  duration?: number;
  hasFile: boolean;
  monitored: boolean;
  reason?: string | null;
  qualityProfileId?: number | null;
  qualityProfileName?: string | null;
  [key: string]: unknown;
}



const LIDARR_PAGE_SIZE = 50;
const LIDARR_AGG_FETCH_SIZE = 500;

interface LidarrAggregateViewProps {
  loading: boolean;
  rows: LidarrAggRow[];
  trackRows: LidarrTrackRow[];
  page: number;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  lastUpdated: string | null;
  summary: { available: number; monitored: number; missing: number; total: number };
  instanceCount: number;
  groupLidarr: boolean;
  isAggFiltered?: boolean;
}

function LidarrAggregateView({
  loading,
  rows,
  trackRows,
  page,
  onPageChange,
  onRefresh,
  lastUpdated,
  summary,
  instanceCount,
  groupLidarr,
  isAggFiltered = false,
}: LidarrAggregateViewProps): JSX.Element {
  const prevRowsRef = useRef<LidarrAggRow[]>([]);
  const groupedDataCache = useRef<Array<{
    instance: string;
    artist: string;
    qualityProfileId?: number | null;
    qualityProfileName?: string | null;
    albums: LidarrAggRow[];
  }>>([]);
  const artistGroupCache = useRef<Map<string, {
    instance: string;
    artist: string;
    qualityProfileId?: number | null;
    qualityProfileName?: string | null;
    albums: LidarrAggRow[];
    albumKeys: Set<string>;
  }>>(new Map());

  // Create grouped data structure: instance > artist > albums - only rebuild if rows actually changed
  const groupedData = useMemo(() => {
    // Quick reference check - if same array reference, return cached
    if (rows === prevRowsRef.current) {
      return groupedDataCache.current;
    }

    // Build instance > artist > albums map
    const instanceMap = new Map<string, Map<string, LidarrAggRow[]>>();

    rows.forEach(row => {
      const instance = row.__instance;
      const artist = (row.album?.["artistName"] as string | undefined) || "Unknown Artist";

      if (!instanceMap.has(instance)) {
        instanceMap.set(instance, new Map());
      }
      const artistMap = instanceMap.get(instance)!;

      if (!artistMap.has(artist)) {
        artistMap.set(artist, []);
      }
      artistMap.get(artist)!.push(row);
    });

    const result: Array<{
      instance: string;
      artist: string;
      qualityProfileId?: number | null;
      qualityProfileName?: string | null;
      albums: LidarrAggRow[];
    }> = [];

    const newArtistGroupCache = new Map<string, {
      instance: string;
      artist: string;
      qualityProfileId?: number | null;
      qualityProfileName?: string | null;
      albums: LidarrAggRow[];
      albumKeys: Set<string>;
    }>();

    instanceMap.forEach((artistMap, instance) => {
      artistMap.forEach((albums, artist) => {
        const artistKey = `${instance}-${artist}`;

        // Build set of album keys for this artist
        const albumKeys = new Set<string>();
        albums.forEach(album => {
          const albumData = album.album as Record<string, unknown>;
          const albumKey = `${albumData?.["title"]}`;
          albumKeys.add(albumKey);
        });

        // Check if this artist group is in cache and unchanged
        const cached = artistGroupCache.current.get(artistKey);
        if (cached && cached.albumKeys.size === albumKeys.size) {
          let unchanged = true;
          for (const key of albumKeys) {
            if (!cached.albumKeys.has(key)) {
              unchanged = false;
              break;
            }
          }
          if (unchanged) {
            // Reuse cached artist group (prevents count flickering)
            result.push(cached);
            newArtistGroupCache.set(artistKey, cached);
            return;
          }
        }

        // Build new artist group
        const firstAlbum = albums[0];
        const albumData = firstAlbum?.album as Record<string, unknown> | undefined;
        const artistGroup = {
          instance,
          artist,
          qualityProfileId: (albumData?.["qualityProfileId"] as number | null | undefined) ?? null,
          qualityProfileName: (albumData?.["qualityProfileName"] as string | null | undefined) ?? null,
          albums,
          albumKeys,
        };
        result.push(artistGroup);
        newArtistGroupCache.set(artistKey, artistGroup);
      });
    });

    // Update caches
    prevRowsRef.current = rows;
    groupedDataCache.current = result;
    artistGroupCache.current = newArtistGroupCache;

    return result;
  }, [rows]);

  // For grouped view, paginate the artist groups (not individual albums)
  // For flat view, paginate the album rows
  const groupedPageRows = useMemo(() => {
    const pageSize = 50;
    return groupedData.slice(page * pageSize, (page + 1) * pageSize);
  }, [groupedData, page]);

  const flatPageRows = useMemo(() => {
    const pageSize = 50;
    const start = page * pageSize;
    const end = start + pageSize;
    return trackRows.slice(start, end);
  }, [trackRows, page]);

  const flatColumns = useMemo<ColumnDef<LidarrTrackRow>[]>(
    () => [
      ...(instanceCount > 1 ? [{
        accessorKey: "__instance",
        header: "Instance",
        size: 120,
      }] : []),
      {
        accessorKey: "artistName",
        header: "Artist",
        size: 150,
      },
      {
        accessorKey: "albumTitle",
        header: "Album",
        size: 150,
      },
      {
        accessorKey: "trackNumber",
        header: "#",
        size: 50,
      },
      {
        accessorKey: "title",
        header: "Track",
      },
      {
        accessorKey: "duration",
        header: "Duration",
        cell: (info) => {
          const dur = info.getValue() as number | undefined;
          if (!dur) return <span className="hint">—</span>;
          return `${Math.floor(dur / 60)}:${String(dur % 60).padStart(2, '0')}`;
        },
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
          const reason = info.getValue() as string | null | undefined;
          if (!reason) return <span className="table-badge table-badge-reason">Not being searched</span>;
          return <span className="table-badge table-badge-reason">{reason}</span>;
        },
        size: 120,
      },
    ],
    [instanceCount]
  );

  const flatTable = useReactTable({
    data: flatPageRows,
    columns: flatColumns,
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
          {isAggFiltered && (groupLidarr ? rows.length : trackRows.length) < summary.total && (
            <>
              {" "}• <strong>Filtered:</strong>{" "}
              {(groupLidarr ? rows.length : trackRows.length).toLocaleString(undefined, { maximumFractionDigits: 0 })} of{" "}
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
      ) : groupLidarr ? (
        <div className="lidarr-hierarchical-view">
          {groupedPageRows.map((artistGroup) => (
            <details key={`${artistGroup.instance}-${artistGroup.artist}`} className="artist-details">
              <summary className="artist-summary">
                <span className="artist-title">{artistGroup.artist}</span>
                <span className="artist-instance">({artistGroup.instance})</span>
                <span className="artist-count">({artistGroup.albums.length} albums)</span>
                {artistGroup.qualityProfileName ? (
                  <span className="artist-quality">• {artistGroup.qualityProfileName}</span>
                ) : null}
              </summary>
              <div className="artist-content">
                {artistGroup.albums.map((albumEntry) => {
                  const albumData = albumEntry.album as Record<string, unknown>;
                  const albumTitle = (albumData?.["title"] as string | undefined) || "Unknown Album";
                  const albumId = (albumData?.["id"] as number | undefined) || 0;
                  const artistName = (albumData?.["artistName"] as string | undefined) || "";
                  const releaseDate = albumData?.["releaseDate"] as string | undefined;
                  const monitored = albumData?.["monitored"] as boolean | undefined;
                  const hasFile = albumData?.["hasFile"] as boolean | undefined;
                  const reason = albumData?.["reason"] as string | null | undefined;
                  const tracks = albumEntry.tracks || [];
                  const totals = albumEntry.totals;

                  return (
                  <details key={`${albumEntry.__instance}-${artistName}-${albumTitle}`} className="album-details">
                    <summary className="album-summary">
                      <span className="album-title">{albumTitle}</span>
                      {releaseDate && (
                        <span className="album-date">{new Date(releaseDate).toLocaleDateString()}</span>
                      )}
                      {tracks && tracks.length > 0 && (
                        <span className="album-track-count">({totals.available || 0}/{totals.monitored || tracks.length} tracks)</span>
                      )}
                      <span className={`album-status ${hasFile ? 'has-file' : 'missing'}`}>
                        {hasFile ? '✓' : '✗'}
                      </span>
                    </summary>
                    <div className="album-content">
                      {tracks && tracks.length > 0 ? (
                        <div className="tracks-table-wrapper">
                          <table className="tracks-table">
                            <thead>
                              <tr>
                                <th>#</th>
                                <th>Title</th>
                                <th>Duration</th>
                                <th>Has File</th>
                                <th>Reason</th>
                              </tr>
                            </thead>
                            <tbody>
                              {tracks.map((track) => (
                                <tr key={`${albumId}-${track.id}`} className={track.hasFile ? 'track-available' : 'track-missing'}>
                                  <td data-label="#">{track.trackNumber}</td>
                                  <td data-label="Title">{track.title}</td>
                                  <td data-label="Duration">{track.duration ? `${Math.floor(track.duration / 60)}:${String(track.duration % 60).padStart(2, '0')}` : '—'}</td>
                                  <td data-label="Has File">
                                    <span className={`track-status ${track.hasFile ? 'available' : 'missing'}`}>
                                      {track.hasFile ? '✓' : '✗'}
                                    </span>
                                  </td>
                                  <td data-label="Reason">
                                    {reason ? (
                                      <span className="table-badge table-badge-reason">{reason}</span>
                                    ) : (
                                      <span className="table-badge table-badge-reason">Not being searched</span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div className="album-info">
                          <p>
                            <strong>Monitored:</strong> {monitored ? 'Yes' : 'No'}
                            {' | '}
                            <strong>Has File:</strong> {hasFile ? 'Yes' : 'No'}
                          </p>
                          <p>
                            <strong>Reason:</strong>{' '}
                            {reason ? (
                              <span className="table-badge table-badge-reason">{reason}</span>
                            ) : (
                              <span className="table-badge table-badge-reason">Not being searched</span>
                            )}
                          </p>
                        </div>
                      )}
                    </div>
                  </details>
                  );
                })}
              </div>
            </details>
          ))}
        </div>
      ) : trackRows.length ? (
        <div className="table-wrapper">
          <table className="responsive-table">
            <thead>
              {flatTable.getHeaderGroups().map((headerGroup) => (
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
              {flatTable.getRowModel().rows.map((row) => {
                const track = row.original;
                const stableKey = `${track.__instance}-${track.artistName}-${track.albumTitle}-${track.trackNumber}`;
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
        <div className="hint">No tracks found.</div>
      )}

      {(groupLidarr ? groupedPageRows.length > 0 : flatPageRows.length > 0) && (
        <div className="pagination">
          <div>
            {groupLidarr ? (
              <>Page {page + 1} of {Math.ceil(groupedData.length / 50)} ({groupedData.length} artists · page size 50)</>
            ) : (
              <>Page {page + 1} of {Math.ceil(trackRows.length / 50)} ({trackRows.length.toLocaleString()} tracks · page size 50)</>
            )}
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
              onClick={() => onPageChange(Math.min((groupLidarr ? Math.ceil(groupedData.length / 50) : Math.ceil(trackRows.length / 50)) - 1, page + 1))}
              disabled={page >= (groupLidarr ? Math.ceil(groupedData.length / 50) : Math.ceil(trackRows.length / 50)) - 1 || loading}
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
  allAlbums: LidarrAlbumEntry[];
  onlyMissing: boolean;
  reasonFilter: string;
  onPageChange: (page: number) => void;
  onRestart: () => void;
  lastUpdated: string | null;
  groupLidarr: boolean;
  instances: ArrInfo[];
  selection: string;
}

function LidarrInstanceView({
  loading,
  data,
  allAlbums,
  onlyMissing,
  reasonFilter,
  onRestart,
  lastUpdated,
  groupLidarr,
  instances,
  selection,
}: LidarrInstanceViewProps): JSX.Element {
  // Separate pagination state for flat (album) view
  const [flatPage, setFlatPage] = useState(0);
  const FLAT_PAGE_SIZE = 50;

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
        return albumData?.["reason"] === "Not being searched" || !albumData?.["reason"];
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

  // Count total tracks for instance view
  // Track counts (for potential future use)
  // const totalTracks = useMemo(() => {
  //   let count = 0;
  //   allAlbums.forEach(entry => {
  //     const tracks = entry.tracks || [];
  //     count += tracks.length;
  //   });
  //   return count;
  // }, [allAlbums]);

  // const filteredTracks = useMemo(() => {
  //   let count = 0;
  //   reasonFilteredAlbums.forEach(entry => {
  //     const tracks = entry.tracks || [];
  //     count += tracks.length;
  //   });
  //   return count;
  // }, [reasonFilteredAlbums]);

  // Reset flat page when filters change
  useEffect(() => {
    setFlatPage(0);
  }, [onlyMissing, reasonFilter]);

  const prevFilteredAlbumsRef = useRef<LidarrAlbumEntry[]>([]);
  const groupedAlbumsCache = useRef<Array<{
    artist: string;
    albums: LidarrAlbumEntry[];
    qualityProfileName?: string | null;
  }>>([]);

  // Group albums by artist for hierarchical view - only rebuild if filtered albums changed
  const groupedAlbums = useMemo(() => {
    // Quick reference check
    if (reasonFilteredAlbums === prevFilteredAlbumsRef.current) {
      return groupedAlbumsCache.current;
    }

    const artistMap = new Map<string, LidarrAlbumEntry[]>();
    reasonFilteredAlbums.forEach(albumEntry => {
      const albumData = albumEntry.album as Record<string, unknown>;
      const artist = (albumData?.["artistName"] as string | undefined) || "Unknown Artist";
      if (!artistMap.has(artist)) {
        artistMap.set(artist, []);
      }
      artistMap.get(artist)!.push(albumEntry);
    });

    const result = Array.from(artistMap.entries()).map(([artist, albums]) => {
      // Get quality profile from first album (all albums by same artist typically share quality profile)
      const firstAlbum = albums[0]?.album as Record<string, unknown> | undefined;
      const qualityProfileName = (firstAlbum?.["qualityProfileName"] as string | null | undefined) ?? null;
      return {
        artist,
        albums,
        qualityProfileName,
      };
    });

    prevFilteredAlbumsRef.current = reasonFilteredAlbums;
    groupedAlbumsCache.current = result;
    return result;
  }, [reasonFilteredAlbums]);

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
            <span className={`track-status ${monitored ? 'available' : 'missing'}`}>
              {monitored ? '✓' : '✗'}
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
            <span className={`track-status ${hasFile ? 'available' : 'missing'}`}>
              {hasFile ? '✓' : '✗'}
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
          const profileName = albumData?.["qualityProfileName"] as string | null | undefined;
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
          if (!reason) return <span className="table-badge table-badge-reason">Not being searched</span>;
          return <span className="table-badge table-badge-reason">{reason}</span>;
        },
        size: 120,
      },
    ],
    []
  );

  // Pagination for flat view
  const flatTotalPages = Math.max(1, Math.ceil(reasonFilteredAlbums.length / FLAT_PAGE_SIZE));
  const flatSafePage = Math.min(flatPage, Math.max(0, flatTotalPages - 1));
  const paginatedAlbums = useMemo(() => {
    return reasonFilteredAlbums.slice(flatSafePage * FLAT_PAGE_SIZE, (flatSafePage + 1) * FLAT_PAGE_SIZE);
  }, [reasonFilteredAlbums, flatSafePage]);

  // Pagination for grouped view (paginate by artist groups, not backend pages)
  const GROUPED_PAGE_SIZE = 50;
  const [groupedPage, setGroupedPage] = useState(0);
  const groupedTotalPages = Math.max(1, Math.ceil(groupedAlbums.length / GROUPED_PAGE_SIZE));
  const groupedSafePage = Math.min(groupedPage, Math.max(0, groupedTotalPages - 1));
  const paginatedGroupedAlbums = useMemo(() => {
    return groupedAlbums.slice(groupedSafePage * GROUPED_PAGE_SIZE, (groupedSafePage + 1) * GROUPED_PAGE_SIZE);
  }, [groupedAlbums, groupedSafePage]);

  // Reset grouped page when filters change
  useEffect(() => {
    setGroupedPage(0);
  }, [onlyMissing, reasonFilter]);

  const table = useReactTable({
    data: paginatedAlbums,
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
              {totalAlbums.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              {isFiltered && filteredCount < totalAlbums && (
                <>
                  {" "}• <strong>Filtered:</strong>{" "}
                  {filteredCount.toLocaleString(undefined, { maximumFractionDigits: 0 })} of{" "}
                  {totalAlbums.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </>
              )}
            </>
          ) : (
            "Loading album information..."
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
      ) : groupLidarr ? (
        <div className="lidarr-hierarchical-view">
          {paginatedGroupedAlbums.map((artistGroup) => {
            // Get instance name from selection
            const instanceName = instances.find(i => i.category === selection)?.name || selection;
            return (
            <details key={artistGroup.artist} className="artist-details">
              <summary className="artist-summary">
                <span className="artist-title">{artistGroup.artist}</span>
                <span className="artist-instance">({instanceName})</span>
                <span className="artist-count">({artistGroup.albums.length} albums)</span>
                {artistGroup.qualityProfileName ? (
                  <span className="artist-quality">• {artistGroup.qualityProfileName}</span>
                ) : null}
              </summary>
              <div className="artist-content">
                {artistGroup.albums.map((albumEntry) => {
                  const albumData = albumEntry.album as Record<string, unknown>;
                  const albumTitle = (albumData?.["title"] as string | undefined) || "Unknown Album";
                  const albumId = (albumData?.["id"] as number | undefined) || 0;
                  const artistName = (albumData?.["artistName"] as string | undefined) || "";
                  const releaseDate = albumData?.["releaseDate"] as string | undefined;
                  const monitored = albumData?.["monitored"] as boolean | undefined;
                  const hasFile = albumData?.["hasFile"] as boolean | undefined;
                  const reason = albumData?.["reason"] as string | null | undefined;
                  const tracks = albumEntry.tracks || [];
                  const totals = albumEntry.totals;

                  return (
                  <details key={`${artistName}-${albumTitle}`} className="album-details">
                    <summary className="album-summary">
                      <span className="album-title">{albumTitle}</span>
                      {releaseDate && (
                        <span className="album-date">{new Date(releaseDate).toLocaleDateString()}</span>
                      )}
                      {tracks && tracks.length > 0 && (
                        <span className="album-track-count">({totals.available || 0}/{totals.monitored || tracks.length} tracks)</span>
                      )}
                      <span className={`album-status ${hasFile ? 'has-file' : 'missing'}`}>
                        {hasFile ? '✓' : '✗'}
                      </span>
                    </summary>
                    <div className="album-content">
                      {tracks && tracks.length > 0 ? (
                        <div className="tracks-table-wrapper">
                          <table className="tracks-table">
                            <thead>
                              <tr>
                                <th>#</th>
                                <th>Title</th>
                                <th>Duration</th>
                                <th>Has File</th>
                                <th>Reason</th>
                              </tr>
                            </thead>
                            <tbody>
                              {tracks.map((track) => (
                                <tr key={`${albumId}-${track.id}`} className={track.hasFile ? 'track-available' : 'track-missing'}>
                                  <td data-label="#">{track.trackNumber}</td>
                                  <td data-label="Title">{track.title}</td>
                                  <td data-label="Duration">{track.duration ? `${Math.floor(track.duration / 60)}:${String(track.duration % 60).padStart(2, '0')}` : '—'}</td>
                                  <td data-label="Has File">
                                    <span className={`track-status ${track.hasFile ? 'available' : 'missing'}`}>
                                      {track.hasFile ? '✓' : '✗'}
                                    </span>
                                  </td>
                                  <td data-label="Reason">
                                    {reason ? (
                                      <span className="table-badge table-badge-reason">{reason}</span>
                                    ) : (
                                      <span className="table-badge table-badge-reason">Not being searched</span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div className="album-info">
                          <p>
                            <strong>Monitored:</strong> {monitored ? 'Yes' : 'No'}
                            {' | '}
                            <strong>Has File:</strong> {hasFile ? 'Yes' : 'No'}
                          </p>
                          <p>
                            <strong>Reason:</strong>{' '}
                            {reason ? (
                              <span className="table-badge table-badge-reason">{reason}</span>
                            ) : (
                              <span className="table-badge table-badge-reason">Not being searched</span>
                            )}
                          </p>
                        </div>
                      )}
                    </div>
                  </details>
                   );
                })}
              </div>
            </details>
            );
          })}
        </div>
      ) : !groupLidarr && allAlbums.length ? (
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
                const artistName = (albumData?.["artistName"] as string | undefined) || "Unknown";
                const stableKey = `${title}-${artistName}`;
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
          {flatTotalPages > 1 && (
            <div className="pagination">
              <div>
                Page {flatSafePage + 1} of {flatTotalPages} ({reasonFilteredAlbums.length.toLocaleString()} albums · page size {FLAT_PAGE_SIZE})
              </div>
              <div className="inline">
                <button
                  className="btn"
                  onClick={() => setFlatPage(Math.max(0, flatSafePage - 1))}
                  disabled={flatSafePage === 0 || loading}
                >
                  Prev
                </button>
                <button
                  className="btn"
                  onClick={() => setFlatPage(Math.min(flatTotalPages - 1, flatSafePage + 1))}
                  disabled={flatSafePage >= flatTotalPages - 1 || loading}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="hint">No albums found.</div>
      )}

      {groupLidarr && groupedAlbums.length > 0 && (
        <div className="pagination">
          <div>
            Page {groupedSafePage + 1} of {groupedTotalPages} ({groupedAlbums.length.toLocaleString()} artists · page size {GROUPED_PAGE_SIZE})
          </div>
          <div className="inline">
            <button
              className="btn"
              onClick={() => setGroupedPage(Math.max(0, groupedSafePage - 1))}
              disabled={groupedSafePage === 0 || loading}
            >
              Prev
            </button>
            <button
              className="btn"
              onClick={() => setGroupedPage(Math.min(groupedTotalPages - 1, groupedSafePage + 1))}
              disabled={groupedSafePage >= groupedTotalPages - 1 || loading}
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
  const { liveArr, groupLidarr } = useWebUI();

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
  const backendReadyWarnedRef = useRef(false);
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
  const [aggTrackRows, setAggTrackRows] = useState<LidarrTrackRow[]>([]);
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

  // Smart data sync for track rows
  const aggTrackSync = useDataSync<LidarrTrackRow>({
    getKey: (track) => `${track.__instance}-${track.artistName}-${track.albumTitle}-${track.trackNumber}`,
    hashFields: ['__instance', 'artistName', 'albumTitle', 'trackNumber', 'title', 'hasFile', 'monitored', 'reason'],
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

        // Smart diffing using hash-based change detection
        const syncResult = instanceAlbumSync.syncData(albums);
        const albumsChanged = syncResult.hasChanges;

        if (keyChanged) {
          // Reset sync state on key change
          instanceAlbumSync.reset();
        }

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
          const albumEntries = res.albums ?? [];
          albumEntries.forEach((entry) => {
            aggregated.push({ ...entry, __instance: label });
          });
          if (!albumEntries.length || albumEntries.length < LIDARR_AGG_FETCH_SIZE) break;
          page += 1;
        }
      }

      // Flatten tracks from all albums for flat mode
      const trackRows: LidarrTrackRow[] = [];
      aggregated.forEach((albumEntry) => {
        const albumData = albumEntry.album as Record<string, unknown>;
        const artistName = (albumData?.["artistName"] as string | undefined) || "Unknown Artist";
        const albumTitle = (albumData?.["title"] as string | undefined) || "Unknown Album";
        const reason = albumData?.["reason"] as string | null | undefined;
        const qualityProfileId = albumData?.["qualityProfileId"] as number | null | undefined;
        const qualityProfileName = albumData?.["qualityProfileName"] as string | null | undefined;
        const tracks = albumEntry.tracks || [];

        if (tracks && tracks.length > 0) {
          tracks.forEach((track) => {
            trackRows.push({
              __instance: albumEntry.__instance,
              artistName,
              albumTitle,
              trackNumber: track.trackNumber || 0,
              title: track.title || "Unknown Track",
              duration: track.duration,
              hasFile: track.hasFile || false,
              monitored: track.monitored || false,
              reason,
              qualityProfileId,
              qualityProfileName,
            });
          });
        }
      });

      // Smart diffing using hash-based change detection
      const albumSyncResult = aggAlbumSync.syncData(aggregated);
      const rowsChanged = albumSyncResult.hasChanges;

      const trackSyncResult = aggTrackSync.syncData(trackRows);
      const trackRowsChanged = trackSyncResult.hasChanges;

      if (rowsChanged) {
        setAggRows(albumSyncResult.data);
      }

      if (trackRowsChanged) {
        setAggTrackRows(trackSyncResult.data);
      }

      const newSummary = groupLidarr
        ? {
            available: totalAvailable,
            monitored: totalMonitored,
            missing: aggregated.length - totalAvailable,
            total: aggregated.length,
          }
        : {
            available: trackRows.filter(t => t.hasFile).length,
            monitored: trackRows.filter(t => t.monitored).length,
            missing: trackRows.filter(t => !t.hasFile).length,
            total: trackRows.length,
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
          : "Failed to load aggregated Lidarr data",
        "error"
      );
    } finally {
      setAggLoading(false);
    }
  }, [instances, globalSearch, push, aggFilter, groupLidarr]);

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
      preloadAll: true,
      showLoading: true,
    });
  }, [active, selection, fetchInstance, instancePage]);

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

  const isAggFiltered = Boolean(debouncedAggFilter) || reasonFilter !== "all";

  const filteredAggTrackRows = useMemo(() => {
    // Combine all filters into a single pass for better performance
    const q = debouncedAggFilter ? debouncedAggFilter.toLowerCase() : "";
    const hasSearchFilter = Boolean(q);
    const hasReasonFilter = reasonFilter !== "all";

    return aggTrackRows.filter((row) => {
      // Search filter
      if (hasSearchFilter) {
        const artist = row.artistName.toLowerCase();
        const album = row.albumTitle.toLowerCase();
        const title = row.title.toLowerCase();
        const instance = row.__instance.toLowerCase();
        if (!artist.includes(q) && !album.includes(q) && !title.includes(q) && !instance.includes(q)) {
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
  }, [aggTrackRows, debouncedAggFilter, onlyMissing, reasonFilter]);

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

  const currentPageAlbums = useMemo(() => {
    return instancePages[instancePage] ?? [];
  }, [instancePages, instancePage]);

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
            </div>

            {isAggregate ? (
              <LidarrAggregateView
                loading={aggLoading}
                rows={filteredAggRows}
                trackRows={filteredAggTrackRows}
                page={aggPage}
                onPageChange={setAggPage}
                onRefresh={() => void loadAggregate({ showLoading: true })}
                lastUpdated={aggUpdated}
                summary={aggSummary}
                instanceCount={instances.length}
                groupLidarr={groupLidarr}
                isAggFiltered={isAggFiltered}
              />
            ) : (
              <LidarrInstanceView
                loading={instanceLoading}
                data={instanceData}
                page={instancePage}
                totalPages={instanceTotalPages}
                pageSize={instancePageSize}
                allAlbums={groupLidarr ? currentPageAlbums : allInstanceAlbums}
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
                groupLidarr={groupLidarr}
                instances={instances}
                selection={selection as string}
              />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
