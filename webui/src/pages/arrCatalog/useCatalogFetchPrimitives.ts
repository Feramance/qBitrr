import { useEffect, useRef } from "react";

/** Tracks whether the catalog has ever returned data and stabilizes empty-state UI. */
export interface CatalogEmptyStateTracker {
  readonly sawNonEmptyRef: React.MutableRefObject<boolean>;
  readonly stableEmptyStreakRef: React.MutableRefObject<number>;
  /** Call when a fetch response includes rows or a positive total. */
  readonly noteCatalogData: (hasCatalogData: boolean) => void;
  /** Reset streak counters (e.g. on selection or cache-key change). */
  readonly resetEmptyState: () => void;
}

export function useCatalogEmptyStateTracker(): CatalogEmptyStateTracker {
  const sawNonEmptyRef = useRef(false);
  const stableEmptyStreakRef = useRef(0);

  const noteCatalogData = (hasCatalogData: boolean): void => {
    if (hasCatalogData) {
      sawNonEmptyRef.current = true;
      stableEmptyStreakRef.current = 0;
    } else {
      stableEmptyStreakRef.current += 1;
    }
  };

  const resetEmptyState = (): void => {
    sawNonEmptyRef.current = false;
    stableEmptyStreakRef.current = 0;
  };

  return { sawNonEmptyRef, stableEmptyStreakRef, noteCatalogData, resetEmptyState };
}

/** Returns true once empty responses look stable (not a warm-up flash). */
export function isEmptyStateReady(
  tracker: Pick<CatalogEmptyStateTracker, "sawNonEmptyRef" | "stableEmptyStreakRef">,
  hasCatalogData: boolean,
): boolean {
  if (hasCatalogData) {
    return true;
  }
  return tracker.sawNonEmptyRef.current || tracker.stableEmptyStreakRef.current >= 2;
}

/** Page cache keyed by resolved page index — shared by flat + Sonarr pipelines. */
export function useCatalogPageCache<T>(): {
  readonly pagesRef: React.MutableRefObject<Record<number, ReadonlyArray<T>>>;
  readonly keyRef: React.MutableRefObject<string>;
  readonly wipePages: () => Record<number, ReadonlyArray<T>>;
} {
  const pagesRef = useRef<Record<number, ReadonlyArray<T>>>({});
  const keyRef = useRef<string>("");

  const wipePages = (): Record<number, ReadonlyArray<T>> => {
    const empty: Record<number, ReadonlyArray<T>> = {};
    pagesRef.current = empty;
    return empty;
  };

  return { pagesRef, keyRef, wipePages };
}

/** Register a global search handler; re-runs when `selection` changes. */
export function useCatalogSearchRegistration(
  active: boolean,
  selection: string | null,
  registerSearchHandler: (handler: (term: string) => void) => () => void,
  onSearch: (term: string) => void,
): void {
  useEffect(() => {
    if (!active) return;
    const handler = (term: string) => {
      if (!selection) return;
      onSearch(term);
    };
    return registerSearchHandler(handler);
  }, [active, selection, registerSearchHandler, onSearch]);
}

/** Refetch when icon-grid page size changes (resize-driven column count). */
export function useCatalogIconGridRefetch(
  active: boolean,
  selection: string | null,
  browseMode: "list" | "icon",
  iconInstancePageSize: number,
  refetch: () => void,
): void {
  useEffect(() => {
    if (!active) return;
    if (!selection) return;
    if (browseMode !== "icon") return;
    refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- iconInstancePageSize is the trigger
  }, [active, selection, browseMode, iconInstancePageSize]);
}
