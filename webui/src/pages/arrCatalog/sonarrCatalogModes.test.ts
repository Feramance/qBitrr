import { describe, expect, it } from "vitest";
import type { SonarrSeriesEntry } from "../../api/types";
import {
  filterSeriesEntriesForMissing,
  filterSeriesEntryByReason,
} from "./sonarrCatalogModes";

const baseEntry: SonarrSeriesEntry = {
  series: { title: "Demo", id: 1 },
  totals: { available: 0, monitored: 2, missing: 2 },
  seasons: {
    "1": {
      monitored: 2,
      available: 0,
      episodes: [
        {
          episodeNumber: 1,
          title: "Pilot",
          monitored: true,
          hasFile: false,
          reason: "Missing",
        },
        {
          episodeNumber: 2,
          title: "Two",
          monitored: true,
          hasFile: true,
          reason: null,
        },
      ],
    },
  },
};

describe("filterSeriesEntriesForMissing", () => {
  it("returns all entries when onlyMissing is false", () => {
    expect(filterSeriesEntriesForMissing([baseEntry], false)).toHaveLength(1);
  });

  it("drops episodes with files and removes empty series", () => {
    const filtered = filterSeriesEntriesForMissing([baseEntry], true);
    expect(filtered).toHaveLength(1);
    const episodes = filtered[0]?.seasons?.["1"]?.episodes ?? [];
    expect(episodes).toHaveLength(1);
    expect(episodes[0]?.episodeNumber).toBe(1);
  });

  it("excludes series with no missing episodes", () => {
    const onlyAvailable: SonarrSeriesEntry = {
      ...baseEntry,
      seasons: {
        "1": {
          monitored: 1,
          available: 1,
          episodes: [
            {
              episodeNumber: 1,
              title: "Done",
              monitored: true,
              hasFile: true,
            },
          ],
        },
      },
    };
    expect(filterSeriesEntriesForMissing([onlyAvailable], true)).toHaveLength(0);
  });
});

describe("filterSeriesEntryByReason", () => {
  it("returns entry unchanged for reason all", () => {
    expect(filterSeriesEntryByReason(baseEntry, "all")).toEqual(baseEntry);
  });

  it("keeps episodes matching explicit reason", () => {
    const filtered = filterSeriesEntryByReason(baseEntry, "Missing");
    const episodes = filtered?.seasons?.["1"]?.episodes ?? [];
    expect(episodes).toHaveLength(1);
    expect(episodes[0]?.reason).toBe("Missing");
  });

  it("treats null reason as Not being searched", () => {
    const entry: SonarrSeriesEntry = {
      ...baseEntry,
      seasons: {
        "1": {
          monitored: 1,
          available: 0,
          episodes: [
            {
              episodeNumber: 1,
              title: "Idle",
              monitored: true,
              hasFile: false,
              reason: null,
            },
          ],
        },
      },
    };
    const filtered = filterSeriesEntryByReason(entry, "Not being searched");
    expect(filtered?.seasons?.["1"]?.episodes).toHaveLength(1);
  });

  it("returns null when no episodes match reason", () => {
    expect(filterSeriesEntryByReason(baseEntry, "Upgrade")).toBeNull();
  });
});
