import type {
  SonarrSeason,
  SonarrSeriesEntry,
} from "../../api/types";
import type { SonarrEpisodeRow } from "../../components/arr/SonarrSeriesGroupDetailBody";
import type { ArrCatalogSummary } from "./definition";

export interface SonarrEpisodeFlatRow extends SonarrEpisodeRow {
  readonly __instance: string;
  readonly seriesId?: number;
  readonly qualityProfileId?: number | null;
  readonly qualityProfileName?: string | null;
  [key: string]: unknown;
}

export const SONARR_FLAT_HASH_FIELDS = [
  "__instance",
  "series",
  "season",
  "episode",
  "title",
  "monitored",
  "hasFile",
  "airDate",
  "reason",
  "qualityProfileName",
] as const;

/** Flatten one series API entry into episode browse rows. */
export function seriesEntryToFlatEpisodes(
  entry: SonarrSeriesEntry,
  instanceLabel: string,
): SonarrEpisodeFlatRow[] {
  const title = (entry.series?.["title"] as string | undefined) || "";
  const seriesId = entry.series?.["id"] as number | undefined;
  const qualityProfileId = entry.series?.qualityProfileId ?? null;
  const qualityProfileName = entry.series?.qualityProfileName ?? null;
  const rows: SonarrEpisodeFlatRow[] = [];
  Object.entries(entry.seasons ?? {}).forEach(([seasonNumber, season]) => {
    (season.episodes ?? []).forEach((episode) => {
      rows.push({
        __instance: instanceLabel,
        series: title,
        seriesId,
        season: seasonNumber,
        episode: episode.episodeNumber ?? "",
        title: episode.title ?? "",
        monitored: !!episode.monitored,
        hasFile: !!episode.hasFile,
        airDate: episode.airDateUtc ?? "",
        reason: (episode.reason as string | null | undefined) ?? null,
        qualityProfileId,
        qualityProfileName,
      });
    });
  });
  return rows;
}

export function sonarrFlatEpisodeRowKey(row: SonarrEpisodeFlatRow): string {
  return `${row.__instance}::${row.series}::${row.season}::${row.episode}`;
}

export function summarizeFlatEpisodes(
  rows: ReadonlyArray<SonarrEpisodeFlatRow>,
): ArrCatalogSummary {
  let monitored = 0;
  let available = 0;
  for (const row of rows) {
    if (row.monitored) {
      monitored += 1;
      if (row.hasFile) available += 1;
    }
  }
  const missing = Math.max(0, monitored - available);
  return { available, monitored, missing, total: rows.length };
}

export interface SonarrCatalogFilters extends Record<string, unknown> {
  readonly onlyMissing: boolean;
  readonly reasonFilter: string;
}

export function filterSeriesEntriesForMissing(
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

export function filterSeriesEntryByReason(
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

export function filterSonarrFlatEpisodes(
  rows: ReadonlyArray<SonarrEpisodeFlatRow>,
  filters: { readonly onlyMissing: boolean; readonly reasonFilter: string },
  debouncedSearch: string,
): SonarrEpisodeFlatRow[] {
  const q = debouncedSearch ? debouncedSearch.toLowerCase() : "";
  const hasSearch = Boolean(q);
  const hasReason = filters.reasonFilter !== "all";
  const hasMissing = filters.onlyMissing;
  if (!hasSearch && !hasReason && !hasMissing) {
    return [...rows];
  }
  return rows.filter((row) => {
    if (hasMissing && row.hasFile) return false;
    if (hasReason) {
      if (filters.reasonFilter === "Not being searched") {
        if (row.reason !== "Not being searched" && row.reason) return false;
      } else if (row.reason !== filters.reasonFilter) {
        return false;
      }
    }
    if (hasSearch) {
      const haystack = [
        row.series,
        row.title,
        row.__instance,
        String(row.season),
        String(row.episode),
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });
}
