/**
 * Data synchronization utilities for efficient change detection and incremental updates
 */

/**
 * Fast hash function using FNV-1a algorithm
 */
function fnv1aHash(str: string): string {
  let hash = 2166136261;
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i);
    hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
  }
  return (hash >>> 0).toString(36);
}

/**
 * Generic interface for items that can be hashed
 */
export interface Hashable {
  [key: string]: unknown;
}

/**
 * Result of change detection
 */
export interface ChangeDetectionResult<T> {
  added: T[];
  updated: T[];
  removed: string[];
  unchanged: number;
  hasChanges: boolean;
}

/**
 * Normalized data structure for efficient lookups
 */
export interface NormalizedData<T> {
  byId: Map<string, T>;
  byHash: Map<string, string>;
  allIds: string[];
  lastUpdate: number;
}

/**
 * Create hash from item based on specified fields
 */
export function createItemHash<T extends Hashable>(
  item: T,
  fields: (keyof T)[]
): string {
  const values = fields.map(field => {
    const value = item[field];
    if (value === null || value === undefined) return '';
    if (typeof value === 'boolean') return value ? '1' : '0';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  });
  return fnv1aHash(values.join('|'));
}

/**
 * Detect changes between existing and incoming data
 */
export function detectChanges<T extends Hashable>(
  existing: NormalizedData<T>,
  incoming: T[],
  getKey: (item: T) => string,
  hashFields: (keyof T)[]
): ChangeDetectionResult<T> {
  const added: T[] = [];
  const updated: T[] = [];
  const removed: string[] = [];
  const seenIds = new Set<string>();

  // Check incoming items
  for (const item of incoming) {
    const id = getKey(item);
    const hash = createItemHash(item, hashFields);
    seenIds.add(id);

    const existingItem = existing.byId.get(id);
    const existingHash = existing.byHash.get(id);

    if (!existingItem) {
      // New item
      added.push(item);
    } else if (existingHash !== hash) {
      // Item exists but data changed
      updated.push(item);
    }
  }

  // Find removed items
  for (const id of existing.allIds) {
    if (!seenIds.has(id)) {
      removed.push(id);
    }
  }

  const unchanged = incoming.length - added.length - updated.length;
  const hasChanges = added.length > 0 || updated.length > 0 || removed.length > 0;

  return { added, updated, removed, unchanged, hasChanges };
}

/**
 * Merge changes into normalized data
 */
export function mergeChanges<T extends Hashable>(
  existing: NormalizedData<T>,
  changes: ChangeDetectionResult<T>,
  getKey: (item: T) => string,
  hashFields: (keyof T)[]
): NormalizedData<T> {
  if (!changes.hasChanges) {
    return existing;
  }

  const newById = new Map(existing.byId);
  const newByHash = new Map(existing.byHash);
  const newIds = [...existing.allIds];

  // Add new items
  for (const item of changes.added) {
    const id = getKey(item);
    const hash = createItemHash(item, hashFields);
    newById.set(id, item);
    newByHash.set(id, hash);
    newIds.push(id);
  }

  // Update existing items
  for (const item of changes.updated) {
    const id = getKey(item);
    const hash = createItemHash(item, hashFields);
    newById.set(id, item);
    newByHash.set(id, hash);
  }

  // Remove deleted items
  for (const id of changes.removed) {
    newById.delete(id);
    newByHash.delete(id);
    const index = newIds.indexOf(id);
    if (index !== -1) {
      newIds.splice(index, 1);
    }
  }

  return {
    byId: newById,
    byHash: newByHash,
    allIds: newIds,
    lastUpdate: Date.now(),
  };
}

/**
 * Convert normalized data to array
 */
export function denormalize<T>(data: NormalizedData<T>): T[] {
  return data.allIds.map(id => data.byId.get(id)!).filter(Boolean);
}

/**
 * Create normalized data from array
 */
export function normalize<T extends Hashable>(
  items: T[],
  getKey: (item: T) => string,
  hashFields: (keyof T)[]
): NormalizedData<T> {
  const byId = new Map<string, T>();
  const byHash = new Map<string, string>();
  const allIds: string[] = [];

  for (const item of items) {
    const id = getKey(item);
    const hash = createItemHash(item, hashFields);
    byId.set(id, item);
    byHash.set(id, hash);
    allIds.push(id);
  }

  return {
    byId,
    byHash,
    allIds,
    lastUpdate: Date.now(),
  };
}

/**
 * Create empty normalized data
 */
export function createEmptyNormalized<T>(): NormalizedData<T> {
  return {
    byId: new Map(),
    byHash: new Map(),
    allIds: [],
    lastUpdate: 0,
  };
}

/**
 * Check if two arrays have the same content (order-independent)
 * Uses fast hash comparison instead of deep equality
 */
export function arraysEqual<T extends Hashable>(
  a: T[],
  b: T[],
  getKey: (item: T) => string,
  hashFields: (keyof T)[]
): boolean {
  if (a.length !== b.length) return false;

  const aHashes = new Map<string, string>();
  for (const item of a) {
    const id = getKey(item);
    const hash = createItemHash(item, hashFields);
    aHashes.set(id, hash);
  }

  for (const item of b) {
    const id = getKey(item);
    const hash = createItemHash(item, hashFields);
    if (aHashes.get(id) !== hash) return false;
  }

  return true;
}
