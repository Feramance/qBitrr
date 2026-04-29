/**
 * Surgical row updates for Arr browse views (Radarr / Sonarr / Lidarr).
 *
 * The previous implementation rebuilt the entire data array on every poll, so even an
 * update-only sync forced tanstack-table to recompute its row model and any non-memoised
 * cell to re-render. The visible result was "list reload" jitter on every poll tick.
 *
 * `RowsStore` keeps three pieces of state in lockstep:
 *
 * - `rowOrder: string[]`   — reference changes only when rows are added or removed.
 * - `rowsById: Map<id, T>` — replaced on every change so React reconciles, but consumers
 *                            that only read `rowOrder` (table layout, virtualisation) skip
 *                            the work.
 * - `rowVersionsById`      — bumped per id when the row's data changes; row components
 *                            subscribe by id and re-render only when their version ticks.
 *
 * Cleanly separates the "set of rows" concern (rowOrder) from "what's inside each row".
 *
 * The store is intentionally framework-light: the React bindings live in
 * `webui/src/hooks/useRowsStore.ts` and use `useSyncExternalStore` so external listeners
 * can subscribe to a single id without rerunning the diff for every update.
 */

import {
  createItemHash,
  detectChanges,
  type Hashable,
} from "./dataSync";

export type RowsChangeKind = "noop" | "update-only" | "add-remove";

export interface RowsStoreSnapshot<T extends Hashable> {
  rowOrder: string[];
  rowsById: Map<string, T>;
  rowVersionsById: Map<string, number>;
  rowHashesById: Map<string, string>;
  lastUpdate: number;
  lastChangeKind: RowsChangeKind;
}

export interface RowsStoreOptions<T extends Hashable> {
  getKey: (item: T) => string;
  hashFields: (keyof T)[];
}

export interface RowsSyncResult<T extends Hashable> {
  snapshot: RowsStoreSnapshot<T>;
  changeKind: RowsChangeKind;
  added: T[];
  updated: T[];
  removed: string[];
}

export function createEmptyRowsSnapshot<T extends Hashable>(): RowsStoreSnapshot<T> {
  return {
    rowOrder: [],
    rowsById: new Map<string, T>(),
    rowVersionsById: new Map<string, number>(),
    rowHashesById: new Map<string, string>(),
    lastUpdate: 0,
    lastChangeKind: "noop",
  };
}

/**
 * Pure helper: compute a new snapshot from the previous one and an incoming row list.
 *
 * Contract:
 * - `noop`        → returns the previous snapshot reference (same object).
 * - `update-only` → returns a NEW snapshot but keeps the same `rowOrder` reference; only
 *                   updated ids get a new entry in `rowsById` and a bumped version.
 * - `add-remove`  → returns a NEW snapshot with a fresh `rowOrder` array. Updated ids that
 *                   coincide with the same poll still get version bumps.
 */
export function syncRowsSnapshot<T extends Hashable>(
  prev: RowsStoreSnapshot<T>,
  incoming: T[],
  options: RowsStoreOptions<T>,
): RowsSyncResult<T> {
  const { getKey, hashFields } = options;

  // Reuse the existing detectChanges() implementation so the diff semantics stay the same
  // as the legacy useDataSync hook (added/updated/removed buckets).
  const detectInput = {
    byId: prev.rowsById as Map<string, T>,
    byHash: prev.rowHashesById,
    allIds: prev.rowOrder,
    lastUpdate: prev.lastUpdate,
  };
  const changes = detectChanges(detectInput, incoming, getKey, hashFields);

  if (!changes.hasChanges) {
    return {
      snapshot: prev,
      changeKind: "noop",
      added: [],
      updated: [],
      removed: [],
    };
  }

  const hasAddRemove =
    changes.added.length > 0 || changes.removed.length > 0;

  // We always rebuild the maps so React sees a new reference on `rowsById` /
  // `rowVersionsById` / `rowHashesById` (those are the things the row-level subscribers
  // consult).  `rowOrder` is the surgical bit: keep its reference when only rows changed.
  const nextRowsById = new Map(prev.rowsById);
  const nextVersions = new Map(prev.rowVersionsById);
  const nextHashes = new Map(prev.rowHashesById);

  for (const item of changes.added) {
    const id = getKey(item);
    const hash = createItemHash(item, hashFields);
    nextRowsById.set(id, item);
    nextHashes.set(id, hash);
    // New rows always start at version 1 so memoised row components mount cleanly.
    nextVersions.set(id, (nextVersions.get(id) ?? 0) + 1);
  }
  for (const item of changes.updated) {
    const id = getKey(item);
    const hash = createItemHash(item, hashFields);
    nextRowsById.set(id, item);
    nextHashes.set(id, hash);
    nextVersions.set(id, (nextVersions.get(id) ?? 0) + 1);
  }
  for (const id of changes.removed) {
    nextRowsById.delete(id);
    nextHashes.delete(id);
    nextVersions.delete(id);
  }

  let nextRowOrder = prev.rowOrder;
  if (hasAddRemove) {
    // Use the incoming order so the table shows the same ordering the API returned.
    nextRowOrder = incoming.map((item) => getKey(item));
  }

  const snapshot: RowsStoreSnapshot<T> = {
    rowOrder: nextRowOrder,
    rowsById: nextRowsById,
    rowVersionsById: nextVersions,
    rowHashesById: nextHashes,
    lastUpdate: Date.now(),
    lastChangeKind: hasAddRemove ? "add-remove" : "update-only",
  };

  return {
    snapshot,
    changeKind: snapshot.lastChangeKind,
    added: changes.added,
    updated: changes.updated,
    removed: changes.removed,
  };
}

/**
 * Bare-bones external store: holds a snapshot and notifies subscribers when it changes.
 *
 * The React layer (see `useRowsStore`) wires this up via `useSyncExternalStore`.
 *
 * Two subscription channels:
 * - global: fires for every snapshot change (used by table re-render path).
 * - per-row: fires when only that id's data version ticks (used by detail modals).
 */
export class RowsStore<T extends Hashable> {
  private snapshot: RowsStoreSnapshot<T>;
  private readonly options: RowsStoreOptions<T>;
  private readonly globalListeners = new Set<() => void>();
  private readonly rowListeners = new Map<string, Set<() => void>>();

  constructor(options: RowsStoreOptions<T>) {
    this.options = options;
    this.snapshot = createEmptyRowsSnapshot<T>();
  }

  getSnapshot = (): RowsStoreSnapshot<T> => this.snapshot;

  sync = (incoming: T[]): RowsSyncResult<T> => {
    const result = syncRowsSnapshot(this.snapshot, incoming, this.options);
    if (result.changeKind === "noop") return result;

    this.snapshot = result.snapshot;

    // Fire per-row listeners only for ids whose version actually ticked.
    const touchedIds = new Set<string>();
    for (const item of result.added) touchedIds.add(this.options.getKey(item));
    for (const item of result.updated) touchedIds.add(this.options.getKey(item));
    for (const id of result.removed) touchedIds.add(id);
    if (touchedIds.size > 0) this.notifyRows(touchedIds);

    this.notifyGlobal();
    return result;
  };

  reset = (): void => {
    if (this.snapshot.rowOrder.length === 0 && this.snapshot.lastUpdate === 0) {
      return;
    }
    const previousIds = new Set(this.snapshot.rowOrder);
    this.snapshot = createEmptyRowsSnapshot<T>();
    if (previousIds.size > 0) this.notifyRows(previousIds);
    this.notifyGlobal();
  };

  /** Replace state with a fresh snapshot (used by aggregate views that rebuild from many sources). */
  replace = (incoming: T[]): RowsSyncResult<T> => {
    this.snapshot = createEmptyRowsSnapshot<T>();
    return this.sync(incoming);
  };

  getRow = (id: string): T | undefined => this.snapshot.rowsById.get(id);

  getRowVersion = (id: string): number =>
    this.snapshot.rowVersionsById.get(id) ?? 0;

  subscribe = (listener: () => void): (() => void) => {
    this.globalListeners.add(listener);
    return () => {
      this.globalListeners.delete(listener);
    };
  };

  subscribeRow = (id: string, listener: () => void): (() => void) => {
    let bucket = this.rowListeners.get(id);
    if (!bucket) {
      bucket = new Set<() => void>();
      this.rowListeners.set(id, bucket);
    }
    bucket.add(listener);
    return () => {
      const b = this.rowListeners.get(id);
      if (!b) return;
      b.delete(listener);
      if (b.size === 0) this.rowListeners.delete(id);
    };
  };

  private notifyGlobal(): void {
    for (const listener of this.globalListeners) listener();
  }

  private notifyRows(ids: Iterable<string>): void {
    for (const id of ids) {
      const bucket = this.rowListeners.get(id);
      if (!bucket || bucket.size === 0) continue;
      for (const listener of bucket) listener();
    }
  }
}
