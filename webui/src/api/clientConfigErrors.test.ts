import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("api client config validation errors", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal("location", {
      pathname: "/ui",
      search: "",
      href: "http://localhost/ui",
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("throws ConfigApiError with validationErrors from 400 body", async () => {
    const body = {
      error: "Configuration validation failed",
      validationErrors: [
        {
          path: "Lidarr.Torrent.SeedingMode.RemoveTorrent",
          message: "Remove Torrent must be a string",
        },
        { path: "Lidarr.URI", message: "URI is required when Managed" },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        statusText: "Bad Request",
        headers: new Headers({ "Content-Type": "application/json" }),
        json: async () => body,
      })
    );

    const { updateConfig, ConfigApiError } = await import("./client");
    await expect(updateConfig({ changes: { "Lidarr.URI": "" } })).rejects.toSatisfy(
      (error: unknown) => {
        expect(error).toBeInstanceOf(ConfigApiError);
        const apiError = error as InstanceType<typeof ConfigApiError>;
        expect(apiError.message).toContain("Lidarr.Torrent.SeedingMode.RemoveTorrent");
        expect(apiError.message).toContain("Lidarr.URI");
        expect(apiError.validationErrors).toHaveLength(2);
        return true;
      }
    );
  });

  it("keeps generic Error when 400 has no validationErrors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        statusText: "Bad Request",
        headers: new Headers({ "Content-Type": "application/json" }),
        json: async () => ({ error: "changes must be an object" }),
      })
    );

    const { updateConfig, ConfigApiError } = await import("./client");
    await expect(updateConfig({ changes: {} })).rejects.toSatisfy((error: unknown) => {
      expect(error).toBeInstanceOf(Error);
      expect(error).not.toBeInstanceOf(ConfigApiError);
      expect((error as Error).message).toBe("changes must be an object");
      return true;
    });
  });
});
