import { describe, expect, it } from "vitest";
import { getArrCatalogDefinition } from "./getArrCatalogDefinition";
import { getLidarrCatalogDefinition } from "./lidarrDefinition";
import { getRadarrCatalogDefinition } from "./radarrDefinition";
import { getReadarrCatalogDefinition } from "./readarrDefinition";
import { getSonarrCatalogDefinition } from "./sonarrDefinition";

describe("getSonarrCatalogDefinition", () => {
  it("returns the series-grouped Sonarr definition", () => {
    const def = getSonarrCatalogDefinition();
    expect(def.searchPlaceholder).toBe("Filter series or episodes");
    expect(def.buildAggregateSelection({} as never, [])).not.toBeNull();
  });
});

describe("getLidarrCatalogDefinition", () => {
  it("returns the artist-grouped Lidarr definition", () => {
    const def = getLidarrCatalogDefinition();
    expect(def.searchPlaceholder).toBe("Filter artists");
  });
});

describe("getReadarrCatalogDefinition", () => {
  it("returns the author-grouped Readarr definition", () => {
    const def = getReadarrCatalogDefinition();
    expect(def.searchPlaceholder).toBe("Filter authors");
    expect(def.kind).toBe("readarr");
  });
});

describe("getRadarrCatalogDefinition", () => {
  it("returns the radarr catalog definition", () => {
    const def = getRadarrCatalogDefinition();
    expect(def.searchPlaceholder).toBe("Filter movies");
    expect(def.kind).toBe("radarr");
  });
});

describe("getArrCatalogDefinition", () => {
  it("routes sonarr to the series-grouped definition", () => {
    expect(getArrCatalogDefinition("sonarr")).toBe(getSonarrCatalogDefinition());
    expect(getArrCatalogDefinition("sonarr").searchPlaceholder).toBe(
      "Filter series or episodes",
    );
  });

  it("routes lidarr to the artist-grouped definition", () => {
    expect(getArrCatalogDefinition("lidarr")).toBe(getLidarrCatalogDefinition());
    expect(getArrCatalogDefinition("lidarr").searchPlaceholder).toBe("Filter artists");
  });

  it("routes readarr to the author-grouped definition", () => {
    expect(getArrCatalogDefinition("readarr")).toBe(getReadarrCatalogDefinition());
    expect(getArrCatalogDefinition("readarr").searchPlaceholder).toBe("Filter authors");
  });

  it("routes radarr to getRadarrCatalogDefinition", () => {
    expect(getArrCatalogDefinition("radarr")).toBe(getRadarrCatalogDefinition());
  });
});
