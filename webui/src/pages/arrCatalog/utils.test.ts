import { describe, expect, it } from "vitest";
import {
  KEEP_ALL_PAGES_SOFT_CAP,
  softCapCachedPages,
  visibleRowsForCachedPage,
} from "./utils";

describe("softCapCachedPages", () => {
  it("keeps pages nearest the touched index when over the soft cap", () => {
    const pages: Record<number, readonly string[]> = {};
    for (let i = 0; i < KEEP_ALL_PAGES_SOFT_CAP + 4; i++) {
      pages[i] = [`p${i}`];
    }
    const capped = softCapCachedPages(pages, 10);
    expect(Object.keys(capped).map(Number).sort((a, b) => a - b)).toEqual([
      4, 5, 6, 7, 8, 9, 10, 11,
    ]);
  });
});

describe("visibleRowsForCachedPage", () => {
  it("returns the server page without absolute re-slice after soft-cap drops early pages", () => {
    const pages: Record<number, readonly string[]> = {};
    for (let i = 0; i < 12; i++) {
      pages[i] = Array.from({ length: 10 }, (_, j) => `r${i}-${j}`);
    }
    const capped = softCapCachedPages(pages, 10);
    // Bug regression: concat + slice(page * pageSize) would be empty for page 10
    // because only 8 pages remain in the cache.
    const concat = Object.keys(capped)
      .map(Number)
      .sort((a, b) => a - b)
      .flatMap((k) => capped[k] ?? []);
    expect(concat.slice(10 * 10, 10 * 10 + 10)).toEqual([]);

    expect(visibleRowsForCachedPage(capped, 10)).toEqual(
      Array.from({ length: 10 }, (_, j) => `r10-${j}`),
    );
  });

  it("applies an optional filter to the current page only", () => {
    const pages = {
      2: ["a", "bb", "ccc"],
    };
    expect(
      visibleRowsForCachedPage(pages, 2, (rows) =>
        rows.filter((r) => r.length > 1),
      ),
    ).toEqual(["bb", "ccc"]);
  });
});
