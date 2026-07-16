import type {
  SonarrSeason,
  SonarrSeriesEntry,
} from "../../api/types";

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
