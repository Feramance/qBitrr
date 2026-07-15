import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("api client URL helpers", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal("location", { pathname: "/qbitrr/ui", search: "", href: "http://localhost/qbitrr/ui" });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  async function loadClient() {
    const urlBase = await import("./urlBase");
    urlBase.setUrlBaseFromMeta("/qbitrr");
    return import("./client");
  }

  it("builds log download URLs with category encoding", async () => {
    const { getLogDownloadUrl } = await loadClient();
    expect(getLogDownloadUrl("Main.log")).toBe("/qbitrr/web/logs/Main.log/download");
    expect(getLogDownloadUrl("Radarr/foo.log")).toBe(
      "/qbitrr/web/logs/Radarr%2Ffoo.log/download",
    );
  });

  it("builds Arr open-item URLs for each kind", async () => {
    const {
      getArrOpenItemUrl,
      getRadarrOpenMovieUrl,
      getSonarrOpenSeriesUrl,
      getLidarrOpenArtistUrl,
    } = await loadClient();

    expect(getArrOpenItemUrl("My Radarr", "movie", 42)).toBe(
      "/qbitrr/web/arr/My%20Radarr/open/movie/42",
    );
    expect(getRadarrOpenMovieUrl("rad", 1)).toBe("/qbitrr/web/arr/rad/open/movie/1");
    expect(getSonarrOpenSeriesUrl("son", 7)).toBe("/qbitrr/web/arr/son/open/series/7");
    expect(getLidarrOpenArtistUrl("lid", 99)).toBe("/qbitrr/web/arr/lid/open/artist/99");
  });

  it("exports AuthError with optional code", async () => {
    const { AuthError } = await loadClient();
    const err = new AuthError("denied", "invalid_credentials");
    expect(err.name).toBe("AuthError");
    expect(err.message).toBe("denied");
    expect(err.code).toBe("invalid_credentials");
  });
});
