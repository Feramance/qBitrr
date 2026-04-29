import {
  useCallback,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import {
  RowsStore,
  type RowsStoreOptions,
  type RowsStoreSnapshot,
  type RowsSyncResult,
} from "../utils/rowsStore";
import type { Hashable } from "../utils/dataSync";

export interface UseRowsStoreResult<T extends Hashable> {
  /** Current snapshot. Reference changes whenever any row mutates. */
  snapshot: RowsStoreSnapshot<T>;
  /** Push the latest poll result through the diff pipeline; returns the change kind. */
  sync: (incoming: T[]) => RowsSyncResult<T>;
  /** Drop all state — used on instance / category change to avoid cross-contamination. */
  reset: () => void;
  /**
   * Replace the entire row set in one shot (returns the same change-kind shape as
   * {@link sync}).  Used by aggregate views that rebuild the row list from many sources.
   */
  replace: (incoming: T[]) => RowsSyncResult<T>;
  /** The store instance — pass to {@link useRowSnapshot} for per-id subscriptions. */
  store: RowsStore<T>;
}

/**
 * Hook entry-point for the row-store pattern. Owns a single `RowsStore` per mount and
 * exposes React-friendly bindings.  See {@link RowsStore} for design notes.
 */
export function useRowsStore<T extends Hashable>(
  options: RowsStoreOptions<T>,
): UseRowsStoreResult<T> {
  // Lazy-initialise the store via `useState` so it's created exactly once per mount and
  // we never read/write a ref during render (which the project's react-hooks lint guard
  // forbids).  Callers are expected to memoise their `options` object so the store keeps
  // a stable identity across renders; if they pass a fresh object every render, the
  // store is still kept alive — we just never re-bind `getKey` / `hashFields` after
  // construction.  In practice every consumer in this codebase wraps options in
  // `useMemo`.
  const [store] = useState(
    () =>
      new RowsStore<T>({
        getKey: options.getKey,
        hashFields: options.hashFields,
      }),
  );

  const snapshot = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getSnapshot,
  );

  const sync = useCallback((incoming: T[]) => store.sync(incoming), [store]);
  const reset = useCallback(() => store.reset(), [store]);
  const replace = useCallback((incoming: T[]) => store.replace(incoming), [store]);

  return { snapshot, sync, reset, replace, store };
}

/**
 * Hook returning a stable array reference for the current row order.
 *
 * The reference only changes when rows are added or removed; update-only polls reuse the
 * same array, so consumers that pass it to tanstack-table see exactly one rebuild.
 */
export function useStableRowArray<T extends Hashable>(
  snapshot: RowsStoreSnapshot<T>,
): T[] {
  return useMemo(() => {
    const out: T[] = [];
    for (const id of snapshot.rowOrder) {
      const row = snapshot.rowsById.get(id);
      if (row !== undefined) out.push(row);
    }
    return out;
    // Intentionally only `rowOrder` (and indirectly `rowsById`) — rebuilding when
    // `rowsById` changes is required for update-only polls so the array hands out the
    // freshest row references when other consumers iterate it.  In practice tanstack-
    // table compares row identity via `getRowId`, so the per-row update propagates without
    // forcing a full row-model recomputation when `rowOrder` is stable.
  }, [snapshot.rowOrder, snapshot.rowsById]);
}

/**
 * Subscribe to a single row by id; returns the latest row data, or `undefined` if removed.
 *
 * Used by detail modals so that polling the open page surfaces fresh fields without
 * closing the modal or rebuilding any sibling row.
 */
export function useRowSnapshot<T extends Hashable>(
  store: RowsStore<T>,
  id: string | null | undefined,
): T | undefined {
  const subscribe = useCallback(
    (listener: () => void) => {
      if (id === null || id === undefined) return () => {};
      return store.subscribeRow(id, listener);
    },
    [store, id],
  );
  const getSnapshot = useCallback(() => {
    if (id === null || id === undefined) return undefined;
    return store.getRow(id);
  }, [store, id]);

  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

/**
 * Subscribe to a row's version counter only.
 *
 * Useful when a component needs to know "did this row's data tick?" without subscribing
 * to the row payload itself (e.g. analytics, animations).
 */
export function useRowVersion<T extends Hashable>(
  store: RowsStore<T>,
  id: string | null | undefined,
): number {
  const subscribe = useCallback(
    (listener: () => void) => {
      if (id === null || id === undefined) return () => {};
      return store.subscribeRow(id, listener);
    },
    [store, id],
  );
  const getSnapshot = useCallback(() => {
    if (id === null || id === undefined) return 0;
    return store.getRowVersion(id);
  }, [store, id]);

  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
