import { describe, expect, it } from "vitest";
import { pagesFromAggregateTotal } from "./arrAggregateFetch";

describe("pagesFromAggregateTotal", () => {
  it("plans artist pages from artist total (not album rollup)", () => {
    // Regression: Lidarr albums API used to return album_total (~20k) while paging
    // by artist (~395). Aggregate clients then planned ~200 pages and hung.
    expect(pagesFromAggregateTotal(395, 100)).toBe(4);
    expect(pagesFromAggregateTotal(19896, 100)).toBe(199);
  });

  it("returns a single page for empty catalogs", () => {
    expect(pagesFromAggregateTotal(0, 50)).toBe(1);
  });
});
