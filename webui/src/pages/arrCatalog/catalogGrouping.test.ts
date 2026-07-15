import { describe, expect, it } from "vitest";
import {
  filterLidarrAlbumRows,
  lidarrAlbumFlatRowKey,
  summarizeLidarrAlbumRows,
  type LidarrAlbumFlatRow,
} from "./lidarrCatalogModes";
import {
  filterSonarrFlatEpisodes,
  seriesEntryToFlatEpisodes,
  sonarrFlatEpisodeRowKey,
  summarizeFlatEpisodes,
  type SonarrEpisodeFlatRow,
} from "./sonarrCatalogModes";
import { getLidarrCatalogDefinition } from "./lidarrDefinition";
import { getSonarrCatalogDefinition } from "./sonarrDefinition";

describe("getSonarrCatalogDefinition", () => {
  it("returns grouped definition when groupSonarr is true", () => {
    const grouped = getSonarrCatalogDefinition(true);
    expect(grouped.searchPlaceholder).toBe("Filter series or episodes");
    expect(grouped.buildAggregateSelection({} as never, [])).not.toBeNull();
  });

  it("returns flat definition when groupSonarr is false", () => {
    const flat = getSonarrCatalogDefinition(false);
    expect(flat.searchPlaceholder).toBe("Filter episodes");
    expect(flat.buildAggregateSelection({} as never, [])).toBeNull();
    expect(flat.buildInstanceSelection({} as never, "cat", "Inst", [])).toBeNull();
  });
});

describe("getLidarrCatalogDefinition", () => {
  it("returns grouped definition when groupLidarr is true", () => {
    const grouped = getLidarrCatalogDefinition(true);
    expect(grouped.searchPlaceholder).toBe("Filter artists");
  });

  it("returns flat definition when groupLidarr is false", () => {
    const flat = getLidarrCatalogDefinition(false);
    expect(flat.searchPlaceholder).toBe("Filter albums");
    expect(flat.buildAggregateSelection({} as never, [])).not.toBeNull();
  });
});

describe("seriesEntryToFlatEpisodes", () => {
  it("flattens nested seasons into episode rows", () => {
    const rows = seriesEntryToFlatEpisodes(
      {
        series: {
          title: "Test Show",
          id: 7,
          qualityProfileName: "HD",
        },
        totals: { available: 0, monitored: 1, missing: 1 },
        seasons: {
          "1": {
            monitored: 1,
            available: 0,
            episodes: [
              {
                episodeNumber: 1,
                title: "Pilot",
                monitored: true,
                hasFile: false,
                airDateUtc: "2020-01-01",
                reason: "Missing",
              },
            ],
          },
        },
      },
      "Sonarr-1",
    );
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      __instance: "Sonarr-1",
      series: "Test Show",
      season: "1",
      episode: 1,
      title: "Pilot",
      qualityProfileName: "HD",
    });
    expect(sonarrFlatEpisodeRowKey(rows[0])).toBe("Sonarr-1::Test Show::1::1");
  });
});

describe("filterSonarrFlatEpisodes", () => {
  const sample: SonarrEpisodeFlatRow[] = [
    {
      __instance: "A",
      series: "Show",
      season: "1",
      episode: "1",
      title: "One",
      monitored: true,
      hasFile: false,
      airDate: "",
      reason: "Missing",
    },
    {
      __instance: "A",
      series: "Show",
      season: "1",
      episode: "2",
      title: "Two",
      monitored: true,
      hasFile: true,
      airDate: "",
      reason: null,
    },
  ];

  it("filters missing-only episodes", () => {
    const out = filterSonarrFlatEpisodes(
      sample,
      { onlyMissing: true, reasonFilter: "all" },
      "",
    );
    expect(out).toHaveLength(1);
    expect(out[0]?.episode).toBe("1");
  });

  it("filters by search term on title", () => {
    const out = filterSonarrFlatEpisodes(
      sample,
      { onlyMissing: false, reasonFilter: "all" },
      "two",
    );
    expect(out).toHaveLength(1);
    expect(out[0]?.title).toBe("Two");
  });
});

describe("summarizeFlatEpisodes", () => {
  it("counts monitored availability buckets", () => {
    const summary = summarizeFlatEpisodes([
      {
        __instance: "A",
        series: "S",
        season: "1",
        episode: "1",
        title: "E1",
        monitored: true,
        hasFile: true,
        airDate: "",
      },
      {
        __instance: "A",
        series: "S",
        season: "1",
        episode: "2",
        title: "E2",
        monitored: true,
        hasFile: false,
        airDate: "",
      },
      {
        __instance: "A",
        series: "S",
        season: "1",
        episode: "3",
        title: "E3",
        monitored: false,
        hasFile: false,
        airDate: "",
      },
    ]);
    expect(summary).toEqual({
      available: 1,
      monitored: 2,
      missing: 1,
      total: 3,
    });
  });
});

describe("filterLidarrAlbumRows", () => {
  const rows: LidarrAlbumFlatRow[] = [
    {
      __instance: "L1",
      album: {
        title: "Album A",
        artistName: "Artist One",
        hasFile: false,
        monitored: true,
        reason: "Missing",
      },
      totals: { available: 0, monitored: 1 },
      tracks: [],
    },
    {
      __instance: "L1",
      album: {
        title: "Album B",
        artistName: "Artist Two",
        hasFile: true,
        monitored: true,
        reason: null,
      },
      totals: { available: 1, monitored: 1 },
      tracks: [],
    },
  ];

  it("filters albums without files when onlyMissing is set", () => {
    const out = filterLidarrAlbumRows(
      rows,
      { onlyMissing: true, reasonFilter: "all" },
      "",
    );
    expect(out).toHaveLength(1);
    expect((out[0]?.album as Record<string, unknown>)["title"]).toBe("Album A");
  });

  it("builds stable album row keys", () => {
    expect(lidarrAlbumFlatRowKey(rows[0]!)).toContain("Artist One");
  });

  it("summarizes album rows", () => {
    const summary = summarizeLidarrAlbumRows(rows);
    expect(summary.total).toBe(2);
    expect(summary.monitored).toBe(2);
    expect(summary.available).toBe(1);
  });
});
