import { describe, expect, it } from "vitest";
import { isEmptyStateReady } from "./useCatalogFetchPrimitives";

describe("isEmptyStateReady", () => {
  it("returns true immediately when catalog data exists", () => {
    const tracker = {
      sawNonEmptyRef: { current: false },
      stableEmptyStreakRef: { current: 0 },
    };
    expect(isEmptyStateReady(tracker, true)).toBe(true);
  });

  it("requires two consecutive empty responses before ready when never non-empty", () => {
    const tracker = {
      sawNonEmptyRef: { current: false },
      stableEmptyStreakRef: { current: 1 },
    };
    expect(isEmptyStateReady(tracker, false)).toBe(false);

    tracker.stableEmptyStreakRef.current = 2;
    expect(isEmptyStateReady(tracker, false)).toBe(true);
  });

  it("stays ready after catalog had data then goes empty", () => {
    const tracker = {
      sawNonEmptyRef: { current: true },
      stableEmptyStreakRef: { current: 5 },
    };
    expect(isEmptyStateReady(tracker, false)).toBe(true);
  });
});
