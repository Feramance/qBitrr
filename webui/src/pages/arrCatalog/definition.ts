import type { ColumnDef } from "@tanstack/react-table";
import type { ReactNode, RefCallback } from "react";
import type { ArrInfo, ArrType } from "../../api/types";
import type { Hashable } from "../../utils/dataSync";
import type { RowsStore } from "../../utils/rowsStore";
import type { ArrCatalogKind } from "./registry";

/**
 * Shared shape for the four-bucket summary line that lives above the catalog table.
 *
 * Radarr / Sonarr count rows; Lidarr inflates `available/monitored/missing` from the
 * SQLite rollup `counts` and overrides `total` to mean `aggregated.length` (artists).
 */
export interface ArrCatalogSummary {
  readonly available: number;
  readonly monitored: number;
  readonly missing: number;
  readonly total: number;
  /** Lidarr-only album-row catalog hint surfaced under the artist summary. */
  readonly rollupTotalAlbumsHint?: number;
}

/**
 * Per-instance fetch options the shell passes through to {@link ArrCatalogDefinition}.
 *
 * Definitions may extend this in their own narrowed types but the shell only knows
 * about the union below — preloads, show-loading, plus opaque per-Arr filter state.
 */
export interface ArrCatalogInstanceFetchOptions {
  readonly preloadAll?: boolean;
  readonly showLoading?: boolean;
}

/**
 * Aggregate per-instance first-page metadata callback shape. Returns true when the
 * loader should mark `aggLoading=false` immediately (matches Radarr/Sonarr empty-set
 * "first paint" behaviour).
 */
export interface AggregateFirstPageMeta {
  readonly total: number | undefined;
}

/**
 * Filter control spec — declarative description of an extra `<select>` rendered next
 * to the search input. The shell wires up the controlled-component plumbing so the
 * definition only declares which options exist + how they map to per-Arr filter
 * state.
 *
 * `mode` controls when the control is rendered:
 * - `always`: always visible.
 * - `instanceOnly`: only when the user is on a single instance (Lidarr "Monitored
 *   artists only").
 */
export interface ArrCatalogFilterSelectSpec<
  TFilters extends Record<string, unknown>,
> {
  readonly id: string;
  readonly label: string;
  readonly minWidth?: number;
  readonly mode: "always" | "instanceOnly";
  readonly options: ReadonlyArray<{
    readonly value: string;
    readonly label: string;
  }>;
  /** Convert filter state to the option string used by the `<select>` value. */
  readonly getValue: (filters: TFilters) => string;
  /** Apply the selected option back into the filter state. */
  readonly setValue: (
    prev: TFilters,
    nextOption: string,
  ) => TFilters;
}

/**
 * Aggregate adapter — owns "all instances" data pipeline.
 *
 * The shell drives `forEachInstanceChunkedPages` itself; the definition only supplies
 * fetch + mapping + summarization.
 */
export interface ArrCatalogAggregateAdapter<
  TAggRow extends Hashable,
  TAggResp,
  TFilters extends Record<string, unknown>,
  TRollup,
> {
  /** Page size used for icon-grid pagination. Shell rounds via `useArrIconGridPageSize`. */
  readonly basePageSize: number;
  /** Initial rollup state (e.g. Lidarr counts accumulator). `null` for none. */
  readonly initialRollup: TRollup;
  /** Initial summary used while loading and after errors. */
  readonly initialSummary: ArrCatalogSummary;
  /** Fetch one chunk of one instance. */
  readonly fetchPage: (
    category: string,
    pageIdx: number,
    chunkSize: number,
    filters: TFilters,
  ) => Promise<TAggResp>;
  /** Extract the array slice + metadata used by the chunked-page loop. */
  readonly extractSlice: (response: TAggResp) => {
    readonly slice: ReadonlyArray<unknown>;
    readonly batchLength: number;
    readonly total: number | undefined;
    readonly pageSize: number | undefined;
  };
  /** Push mapped rows from one slice into the accumulator. */
  readonly mapSlice: (
    response: TAggResp,
    instanceLabel: string,
    push: (row: TAggRow) => void,
  ) => void;
  /** Optional per-instance rollup update on the first page of each instance. */
  readonly accumulateRollup?: (
    prev: TRollup,
    response: TAggResp,
  ) => TRollup;
  /** Build the summary line from the merged row list + accumulated rollup. */
  readonly summarize: (
    rows: ReadonlyArray<TAggRow>,
    rollup: TRollup,
  ) => ArrCatalogSummary;
  /** Stable id for the row store + diff pipeline. */
  readonly getRowKey: (row: TAggRow) => string;
  /** Hash fields for the row store / `useDataSync`. */
  readonly hashFields: ReadonlyArray<keyof TAggRow & string>;
  /** Optional client-side filter applied after merging (e.g. monitored / reason). */
  readonly filterRows?: (
    rows: ReadonlyArray<TAggRow>,
    filters: TFilters,
    debouncedSearch: string,
  ) => ReadonlyArray<TAggRow>;
  /** Optional client-side sort (e.g. Lidarr instance->name asc). */
  readonly sortRows?: (
    rows: ReadonlyArray<TAggRow>,
  ) => ReadonlyArray<TAggRow>;
}

/**
 * Generic result state returned by an instance pipeline hook. Definitions can extend
 * this with their own per-row payloads but the shell only knows about the shared
 * fields below.
 */
export interface ArrCatalogInstancePipelineState<TInstRow extends Hashable> {
  readonly loading: boolean;
  /**
   * True when the loader has enough evidence to treat an empty slice as stable.
   * Used to avoid transient warm-up flashes (`Loading -> No items -> rows`).
   */
  readonly emptyStateReady: boolean;
  readonly lastUpdated: string | null;
  readonly page: number;
  readonly pageSize: number;
  readonly totalPages: number;
  /** Total items the backend reported for the current key. */
  readonly totalItems: number;
  /** Visible rows in the current page (already filtered + sliced). */
  readonly visibleRows: ReadonlyArray<TInstRow>;
  /** Surgical row store — drives the list table + modal subscriptions. */
  readonly rowsStore: RowsStore<TInstRow>;
  /** Stable row order from the same store. */
  readonly rowOrder: ReadonlyArray<string>;
  /**
   * True when the current visible slice is empty AND the response indicates the
   * catalog itself is empty (so the shell can swap copy from "no matches" → "no
   * rows in catalog" + sync hint).
   */
  readonly showCatalogEmptyHint: boolean;
  /** User-driven page change (the pipeline owns the fetch). */
  readonly setPage: (page: number) => void;
  /** Explicit refresh (preloadAll=false, showLoading=true). */
  readonly refresh: () => void;
}

/** Inputs passed by the shell to every instance pipeline hook. */
export interface ArrCatalogInstancePipelineParams<
  TFilters extends Record<string, unknown>,
> {
  readonly active: boolean;
  /** Selected category, or null when on aggregate / not yet loaded. */
  readonly selection: string | null;
  /** Display label for the selection (used in tile titles, etc.). */
  readonly instanceLabel: string;
  readonly filters: TFilters;
  readonly browseMode: "list" | "icon";
  /** True when liveArr polling is enabled and no global search is active. */
  readonly polling: boolean;
  /** Round a base page size to icon-grid rows (no-op in list mode). */
  readonly roundPageSize: (base: number) => number;
  /** Current global search term value (read once for "filter on Search box"). */
  readonly globalSearchRef: React.MutableRefObject<string>;
  /** Hook to register a search-input handler. */
  readonly registerSearchHandler: (
    handler: (term: string) => void,
  ) => () => void;
  /** Toast push for user-facing errors. */
  readonly pushToast: (
    message: string,
    kind?: "info" | "success" | "warning" | "error",
  ) => void;
  /** Re-render trigger when icon mode page-size changes. */
  readonly iconInstancePageSize: number;
}

/**
 * Render context passed to per-Arr render slots. Includes everything the slot might
 * need to display rows, run an action, or wire pagination.
 */
export interface ArrCatalogRenderContext<TFilters extends Record<string, unknown>> {
  readonly instances: ReadonlyArray<ArrInfo>;
  readonly instanceCount: number;
  readonly browseMode: "list" | "icon";
  readonly iconGridRef: RefCallback<HTMLElement | null>;
  readonly filters: TFilters;
  /** Current selection or `"aggregate"` when on the aggregate view. */
  readonly selection: string | "aggregate";
}

/**
 * Render-slot props for `renderAggregateBody`.
 *
 * The shell already filtered/sorted/sliced the rows; the definition only needs to
 * decide between list and icon mode + render the summary header.
 */
export interface ArrCatalogAggregateRenderProps<
  TAggRow extends Hashable,
  TFilters extends Record<string, unknown>,
> extends ArrCatalogRenderContext<TFilters> {
  readonly rows: ReadonlyArray<TAggRow>;
  readonly rowOrder: ReadonlyArray<string>;
  readonly rowsStore: RowsStore<TAggRow>;
  readonly loading: boolean;
  readonly emptyStateReady: boolean;
  readonly total: number;
  readonly page: number;
  readonly totalPages: number;
  readonly aggregatePageSize: number;
  readonly summary: ArrCatalogSummary;
  readonly lastUpdated: string | null;
  readonly isAggFiltered: boolean;
  readonly onPageChange: (page: number) => void;
  readonly onRefresh: () => void;
  readonly onRowSelect: (row: TAggRow) => void;
}

/** Render-slot props for `renderInstanceBody`. */
export interface ArrCatalogInstanceRenderProps<
  TInstRow extends Hashable,
  TFilters extends Record<string, unknown>,
> extends ArrCatalogRenderContext<TFilters>,
    ArrCatalogInstancePipelineState<TInstRow> {
  readonly category: string;
  readonly instanceLabel: string;
  readonly onRowSelect: (row: TInstRow) => void;
}

/**
 * Detail-modal selection — the shell stores this in state and routes it through
 * `<ArrCatalogDetailModalHost>`. `id` matches the row-store key for live updates.
 */
export interface ArrCatalogModalSelection<TSeed> {
  readonly id: string;
  readonly source: "instance" | "aggregate";
  readonly seed: TSeed;
  /** Free-form per-Arr extras (e.g. category, artistId). */
  readonly extras?: Record<string, unknown>;
}

/** Render-slot props for the modal body + title. Live row lookup happens in host. */
export interface ArrCatalogModalRenderProps<TLiveRow, TSeed> {
  /** Fresh row from the relevant store — falls back to the seed when not present. */
  readonly liveRow: TLiveRow;
  readonly seed: TSeed;
  readonly source: "instance" | "aggregate";
  readonly extras: Record<string, unknown>;
  readonly onClose: () => void;
}

/**
 * Per-Arr definition — the only thing that changes between Radarr/Sonarr/Lidarr.
 *
 * Generic over the row + response shapes for tight type-safety; the shell stays
 * fully generic and never reads concrete fields.
 */
export interface ArrCatalogDefinition<
  TInstRow extends Hashable,
  TAggRow extends Hashable,
  TFilters extends Record<string, unknown>,
  TInstSeed,
  TAggSeed,
  TLiveRow,
  TAggResp,
  TRollup,
> {
  readonly kind: ArrCatalogKind;
  readonly arrType: ArrType;
  readonly cardTitle: string;
  readonly allInstancesLabel: string;
  readonly searchPlaceholder: string;

  /** Initial values for filter state owned by the shell. */
  readonly initialFilters: TFilters;
  /** Toolbar filter controls in render order. */
  readonly filterControls: ReadonlyArray<ArrCatalogFilterSelectSpec<TFilters>>;

  /** Aggregate adapter (rows merged across all instances). */
  readonly aggregate: ArrCatalogAggregateAdapter<
    TAggRow,
    TAggResp,
    TFilters,
    TRollup
  >;

  /**
   * Hook driving the per-instance pipeline. Definitions choose between flat
   * (`useInstancePagedFetch`) and grouped (Sonarr's series → group transform) here.
   */
  readonly useInstancePipeline: (
    params: ArrCatalogInstancePipelineParams<TFilters>,
  ) => ArrCatalogInstancePipelineState<TInstRow>;

  /** Build aggregate-row → modal seed (e.g. movie/series-group/artist). */
  readonly buildAggregateSelection: (
    row: TAggRow,
    instances: ReadonlyArray<ArrInfo>,
  ) => ArrCatalogModalSelection<TAggSeed> | null;
  /** Build instance-row → modal seed. */
  readonly buildInstanceSelection: (
    row: TInstRow,
    selectionCategory: string,
    instanceLabel: string,
    instances: ReadonlyArray<ArrInfo>,
  ) => ArrCatalogModalSelection<TInstSeed> | null;

  /**
   * Modal subscriptions: each Arr exposes its own row stores so the host can call
   * `useRowSnapshot` against the right one. The host calls both unconditionally
   * (with one `null` id) to keep hook order stable.
   */
  readonly getModalLiveRow: (params: {
    readonly source: "instance" | "aggregate";
    readonly instanceFresh: TInstRow | null;
    readonly aggregateFresh: TAggRow | null;
    readonly instanceSeed: TInstSeed | null;
    readonly aggregateSeed: TAggSeed | null;
  }) => TLiveRow;
  readonly getModalTitle: (liveRow: TLiveRow, extras: Record<string, unknown>) => string;
  readonly getModalMaxWidth: () => number;
  readonly renderModalBody: (
    props: ArrCatalogModalRenderProps<TLiveRow, TInstSeed | TAggSeed>,
  ) => ReactNode;

  /** Aggregate body renderer — entire body below the toolbar. */
  readonly renderAggregateBody: (
    props: ArrCatalogAggregateRenderProps<TAggRow, TFilters>,
  ) => ReactNode;
  /** Instance body renderer. */
  readonly renderInstanceBody: (
    props: ArrCatalogInstanceRenderProps<TInstRow, TFilters>,
  ) => ReactNode;

  /** Optional shared columns helper exported for renderers. Not used by the shell. */
  readonly buildAggregateColumns?: (
    instanceCount: number,
  ) => ColumnDef<TAggRow>[];
  readonly buildInstanceColumns?: () => ColumnDef<TInstRow>[];
}

/** Convenience alias for the most-erased form of a definition (used by registry). */
export type AnyArrCatalogDefinition = ArrCatalogDefinition<
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  any
>;
