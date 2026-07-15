import type { LidarrAlbumEntry } from "../../api/types";
import { summarizeAggregateMonitoredRows } from "../../constants/arrAggregateFetch";
import type { ArrCatalogSummary } from "./definition";

export interface LidarrAlbumFlatRow extends LidarrAlbumEntry {
  readonly __instance: string;
  [key: string]: unknown;
}

export const LIDARR_FLAT_HASH_FIELDS = [
  "__instance",
  "album",
  "tracks",
  "totals",
] as const;

export function lidarrAlbumFlatRowKey(row: LidarrAlbumFlatRow): string {
  const album = row.album as Record<string, unknown>;
  const rawId = album?.["id"];
  const title = String(album?.["title"] ?? "");
  const artist = String(album?.["artistName"] ?? "");
  const idPart =
    typeof rawId === "number" && Number.isFinite(rawId)
      ? `id:${rawId}`
      : `t:${title}`;
  return `${row.__instance}::${artist}::${idPart}`;
}

export function summarizeLidarrAlbumRows(
  rows: ReadonlyArray<LidarrAlbumFlatRow>,
): ArrCatalogSummary {
  const base = summarizeAggregateMonitoredRows(
    rows.map((row) => {
      const album = row.album as Record<string, unknown>;
      return {
        monitored: Boolean(album?.["monitored"]),
        hasFile: Boolean(album?.["hasFile"]),
      };
    }),
  );
  return { ...base, total: rows.length };
}

export function filterLidarrAlbumRows(
  rows: ReadonlyArray<LidarrAlbumFlatRow>,
  filters: { readonly onlyMissing: boolean; readonly reasonFilter: string },
  debouncedSearch: string,
): LidarrAlbumFlatRow[] {
  let out = [...rows];
  if (filters.onlyMissing) {
    out = out.filter((row) => {
      const album = row.album as Record<string, unknown>;
      return !album?.["hasFile"];
    });
  }
  if (filters.reasonFilter !== "all") {
    if (filters.reasonFilter === "Not being searched") {
      out = out.filter((row) => {
        const album = row.album as Record<string, unknown>;
        return album?.["reason"] === "Not being searched" || !album?.["reason"];
      });
    } else {
      out = out.filter((row) => {
        const album = row.album as Record<string, unknown>;
        return album?.["reason"] === filters.reasonFilter;
      });
    }
  }
  const q = debouncedSearch ? debouncedSearch.toLowerCase() : "";
  if (!q) return out;
  return out.filter((row) => {
    const album = row.album as Record<string, unknown>;
    const title = String(album?.["title"] ?? "").toLowerCase();
    const artist = String(album?.["artistName"] ?? "").toLowerCase();
    const inst = String(row.__instance ?? "").toLowerCase();
    return title.includes(q) || artist.includes(q) || inst.includes(q);
  });
}
