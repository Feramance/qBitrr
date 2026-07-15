import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("urlBase", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  async function loadUrlBase(pathname: string) {
    vi.stubGlobal("location", { pathname, search: "", href: `http://localhost${pathname}` });
    return import("./urlBase");
  }

  it("derives prefix from /qbitrr/ui pathname", async () => {
    const { pathnameUrlBase } = await loadUrlBase("/qbitrr/ui");
    expect(pathnameUrlBase()).toBe("/qbitrr");
  });

  it("derives prefix from static index.html path", async () => {
    const { pathnameUrlBase } = await loadUrlBase("/qbitrr/static/index.html");
    expect(pathnameUrlBase()).toBe("/qbitrr");
  });

  it("derives prefix from bare subpath before redirect", async () => {
    const { pathnameUrlBase } = await loadUrlBase("/qbitrr");
    expect(pathnameUrlBase()).toBe("/qbitrr");
  });

  it("returns empty prefix at root deployment paths", async () => {
    const { pathnameUrlBase, webPath } = await loadUrlBase("/web/docs");
    expect(pathnameUrlBase()).toBe("");
    expect(webPath("/web/meta")).toBe("/web/meta");
  });

  it("prefers meta url_base over pathname after setUrlBaseFromMeta", async () => {
    const mod = await loadUrlBase("/ui");
    mod.setUrlBaseFromMeta("/proxy");
    expect(mod.getUrlBase()).toBe("/proxy");
    expect(mod.webPath("/web/status")).toBe("/proxy/web/status");
  });

  it("throws when webPath receives a non-root-relative path", async () => {
    const { webPath } = await loadUrlBase("/ui");
    expect(() => webPath("web/meta")).toThrow("webPath expects a path starting with /");
  });
});
