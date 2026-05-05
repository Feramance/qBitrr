import type { ArrInfo } from "../../api/types";
import {
  AGG_FALLBACK_AGGREGATE_PAGES_MAX,
  pagesFromAggregateTotal,
} from "../../constants/arrAggregateFetch";

export interface InstanceChunkPageResult {
  readonly batchLength: number;
  readonly total?: number;
  readonly page_size?: number;
}

/**
 * Iterate every backend page for each instance (chunk-sized), calling `onSlice` per chunk.
 * Stops early when `gen !== genRef.current`. Matches Radarr/Sonarr/Lidarr aggregate merge loops.
 *
 * `onInstanceFirstPage` receives both the parsed first-page metadata (`total`) **and**
 * the raw response so callers can fold rollup counts (Lidarr's `counts` / `album_total`)
 * into their state without an extra call.
 */
export async function forEachInstanceChunkedPages<TResp = unknown>(
  options: {
    readonly instances: readonly ArrInfo[];
    readonly chunk: number;
    readonly gen: number;
    readonly genRef: { readonly current: number };
    fetchSlice: (
      category: string,
      pageIdx: number,
      chunkSize: number
    ) => Promise<
      InstanceChunkPageResult & {
        readonly slice: readonly unknown[];
        readonly response: TResp;
      }
    >;
    onSlice: (
      slice: readonly unknown[],
      instanceLabel: string,
      response: TResp,
    ) => void;
    /**
     * Called once per instance when the first page metadata is known. Receives
     * `total` (may be undefined) and the raw response (for rollup callbacks).
     */
    onInstanceFirstPage?: (
      total: number | undefined,
      response: TResp,
      instanceLabel: string,
    ) => void;
  }
): Promise<void> {
  const {
    instances,
    chunk,
    gen,
    genRef,
    fetchSlice,
    onSlice,
    onInstanceFirstPage,
  } = options;

  for (const inst of instances) {
    const label = inst.name || inst.category;
    let countedForInstance = false;
    let pagesPlanned: number | null = null;
    let pageIdx = 0;

    while (true) {
      const res = await fetchSlice(inst.category, pageIdx, chunk);
      if (gen !== genRef.current) {
        return;
      }

      if (!countedForInstance) {
        countedForInstance = true;
        pagesPlanned = pagesFromAggregateTotal(res.total, res.page_size, chunk);
        onInstanceFirstPage?.(
          typeof res.total === "number" ? res.total : undefined,
          res.response,
          label,
        );
      }

      onSlice(res.slice, label, res.response);

      pageIdx += 1;

      if (pagesPlanned !== null) {
        if (pageIdx >= pagesPlanned) break;
      } else {
        if (!res.batchLength || res.batchLength < chunk) break;
        if (pageIdx >= AGG_FALLBACK_AGGREGATE_PAGES_MAX) break;
      }
    }
  }
}
