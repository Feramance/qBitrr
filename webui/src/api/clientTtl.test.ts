import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("api client GET TTL cache", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.useFakeTimers();
    vi.stubGlobal("location", {
      pathname: "/ui",
      search: "",
      href: "http://localhost/ui",
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  async function loadClient() {
    return import("./client");
  }

  function mockFetch(sequentialResponses: unknown[]) {
    const fetchMock = vi.fn();
    for (const body of sequentialResponses) {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "Content-Type": "application/json" }),
        json: async () => body,
        text: async () => JSON.stringify(body),
      });
    }
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  it("reuses /web/status within TTL and refetches after expiry", async () => {
    const fetchMock = mockFetch([{ ok: true }, { ok: true, refreshed: true }]);
    const { getStatus } = await loadClient();

    const first = await getStatus();
    const second = await getStatus();
    expect(first).toEqual({ ok: true });
    expect(second).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(2_001);
    const third = await getStatus();
    expect(third).toEqual({ ok: true, refreshed: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("never TTL-caches Arr catalog paths", async () => {
    const fetchMock = mockFetch([{ rows: [1] }, { rows: [2] }]);
    const { getRadarrMovies } = await loadClient();
    await getRadarrMovies("movies", 1, 10, "");
    await getRadarrMovies("movies", 1, 10, "");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("invalidateGetCache drops matching entries", async () => {
    const fetchMock = mockFetch([{ Settings: {} }, { Settings: { LoopSleepTimer: 5 } }]);
    const { getConfig, invalidateGetCache } = await loadClient();

    await getConfig();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await getConfig();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    invalidateGetCache(["/web/config"]);
    await getConfig();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("updateConfig invalidates config cache", async () => {
    const fetchMock = mockFetch([
      { Settings: {} },
      { configReloaded: true, reloadType: "live" },
      { Settings: { LoopSleepTimer: 10 } },
    ]);
    const { getConfig, updateConfig } = await loadClient();

    await getConfig();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await updateConfig({ changes: { "Settings.LoopSleepTimer": 10 } });
    await getConfig();
    // POST + second GET (cache invalidated)
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
