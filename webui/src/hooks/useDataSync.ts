import { useCallback, useRef, useState } from "react";
import {
  type NormalizedData,
  type ChangeDetectionResult,
  type Hashable,
  createEmptyNormalized,
  detectChanges,
  mergeChanges,
  denormalize,
} from "../utils/dataSync";

export interface DataSyncOptions<T extends Hashable> {
  getKey: (item: T) => string;
  hashFields: (keyof T)[];
}

export interface DataSyncResult<T extends Hashable> {
  data: T[];
  hasChanges: boolean;
  changes: ChangeDetectionResult<T> | null;
  lastUpdate: number;
}

/**
 * Hook for managing incremental data synchronization
 * Automatically detects changes and prevents unnecessary re-renders
 */
export function useDataSync<T extends Hashable>(
  options: DataSyncOptions<T>
): {
  syncData: (newData: T[]) => DataSyncResult<T>;
  getData: () => T[];
  reset: () => void;
  lastUpdate: number;
} {
  const { getKey, hashFields } = options;

  const normalizedRef = useRef<NormalizedData<T>>(createEmptyNormalized<T>());
  const [lastUpdate, setLastUpdate] = useState(0);

  const syncData = useCallback(
    (newData: T[]): DataSyncResult<T> => {
      const changes = detectChanges(
        normalizedRef.current,
        newData,
        getKey,
        hashFields
      );

      if (!changes.hasChanges) {
        // No changes detected, return existing data
        return {
          data: denormalize(normalizedRef.current),
          hasChanges: false,
          changes: null,
          lastUpdate: normalizedRef.current.lastUpdate,
        };
      }

      // Merge changes into normalized data
      const merged = mergeChanges(
        normalizedRef.current,
        changes,
        getKey,
        hashFields
      );

      normalizedRef.current = merged;
      setLastUpdate(merged.lastUpdate);

      return {
        data: denormalize(merged),
        hasChanges: true,
        changes,
        lastUpdate: merged.lastUpdate,
      };
    },
    [getKey, hashFields]
  );

  const getData = useCallback((): T[] => {
    return denormalize(normalizedRef.current);
  }, []);

  const reset = useCallback(() => {
    normalizedRef.current = createEmptyNormalized<T>();
    setLastUpdate(0);
  }, []);

  return {
    syncData,
    getData,
    reset,
    lastUpdate,
  };
}
