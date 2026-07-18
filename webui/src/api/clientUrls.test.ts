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

  it("builds log SSE stream URLs with cursor params", async () => {
    const { getLogStreamUrl } = await loadClient();
    expect(getLogStreamUrl("Main.log", 100, 42, 2000)).toBe(
      "/qbitrr/web/logs/Main.log/stream?since_bytes=100&inode=42&lines=2000",
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

  it("refreshUrlBaseFromMeta clears cache and re-fetches meta", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ url_base: "/new-base", current_version: "1.0.0" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const urlBase = await import("./urlBase");
    urlBase.setUrlBaseFromMeta("/old-base");
    const { refreshUrlBaseFromMeta } = await import("./client");

    const meta = await refreshUrlBaseFromMeta();
    expect(meta.url_base).toBe("/new-base");
    expect(urlBase.getUrlBase()).toBe("/new-base");
    expect(fetchMock).toHaveBeenCalledWith(
      "/qbitrr/web/meta?force=1",
      expect.objectContaining({ credentials: "include" }),
    );
  });
});
