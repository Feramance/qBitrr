import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  isEmptyStateReady,
  useCatalogEmptyStateTracker,
  useCatalogPageCache,
  useCatalogSearchRegistration,
} from "./useCatalogFetchPrimitives";

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

describe("useCatalogEmptyStateTracker", () => {
  it("increments empty streak and resets on data", () => {
    const { result } = renderHook(() => useCatalogEmptyStateTracker());

    act(() => {
      result.current.noteCatalogData(false);
    });
    expect(result.current.stableEmptyStreakRef.current).toBe(1);
    expect(result.current.sawNonEmptyRef.current).toBe(false);

    act(() => {
      result.current.noteCatalogData(true);
    });
    expect(result.current.sawNonEmptyRef.current).toBe(true);
    expect(result.current.stableEmptyStreakRef.current).toBe(0);

    act(() => {
      result.current.resetEmptyState();
    });
    expect(result.current.sawNonEmptyRef.current).toBe(false);
    expect(result.current.stableEmptyStreakRef.current).toBe(0);
  });
});

describe("useCatalogPageCache", () => {
  it("wipes pages and returns empty map", () => {
    const { result } = renderHook(() => useCatalogPageCache<{ id: string }>());
    result.current.pagesRef.current = { 1: [{ id: "a" }] };
    result.current.keyRef.current = "old";

    let wiped: Record<number, readonly { id: string }[]> = {};
    act(() => {
      wiped = result.current.wipePages();
    });

    expect(wiped).toEqual({});
    expect(result.current.pagesRef.current).toEqual({});
  });
});

describe("useCatalogSearchRegistration", () => {
  it("registers handler only when active with selection", () => {
    const registerSearchHandler = vi.fn((handler: (term: string) => void) => {
      handler("query");
      return () => undefined;
    });
    const onSearch = vi.fn();

    renderHook(() =>
      useCatalogSearchRegistration(true, "Radarr", registerSearchHandler, onSearch),
    );
    expect(registerSearchHandler).toHaveBeenCalledTimes(1);
    expect(onSearch).toHaveBeenCalledWith("query");
  });

  it("does not search when selection is null", () => {
    const registerSearchHandler = vi.fn((handler: (term: string) => void) => {
      handler("query");
      return () => undefined;
    });
    const onSearch = vi.fn();

    renderHook(() =>
      useCatalogSearchRegistration(true, null, registerSearchHandler, onSearch),
    );
    expect(onSearch).not.toHaveBeenCalled();
  });

  it("skips registration when inactive", () => {
    const registerSearchHandler = vi.fn(() => () => undefined);
    renderHook(() =>
      useCatalogSearchRegistration(false, "Radarr", registerSearchHandler, vi.fn()),
    );
    expect(registerSearchHandler).not.toHaveBeenCalled();
  });
});
