import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type JSX,
} from "react";
import { getArrList } from "../../api/client";
import type { ArrInfo } from "../../api/types";
import { ArrBrowseModeToggle } from "../../components/arr/ArrBrowseModeToggle";
import { useSearch } from "../../context/SearchContext";
import { useToast } from "../../context/ToastContext";
import { useWebUI } from "../../context/WebUIContext";
import { useArrBrowseMode } from "../../hooks/useArrBrowseMode";
import { useArrIconGridPageSize } from "../../hooks/useArrIconGridPageSize";
import type { Hashable } from "../../utils/dataSync";
import { ArrCatalogDetailModalHost } from "./ArrCatalogDetailModalHost";
import type {
  ArrCatalogDefinition,
  ArrCatalogModalSelection,
} from "./definition";
import { reconcileArrCatalogSelection } from "./utils";
import { useAggregateCatalogLoader } from "./useAggregateCatalogLoader";

interface ArrCatalogShellProps<
  TInstRow extends Hashable,
  TAggRow extends Hashable,
  TFilters extends Record<string, unknown>,
  TInstSeed,
  TAggSeed,
  TLiveRow,
  TAggResp,
  TRollup,
> {
  readonly definition: ArrCatalogDefinition<
    TInstRow,
    TAggRow,
    TFilters,
    TInstSeed,
    TAggSeed,
    TLiveRow,
    TAggResp,
    TRollup
  >;
  readonly active: boolean;
}

/**
 * Shared shell for the Radarr / Sonarr / Lidarr catalog pages.
 *
 * Owns:
 * - Instances list + selection, sidebar + mobile select.
 * - Global search registration with a single ref-based handler (so toggling filters
 *   no longer re-registers — aligned across Arrs).
 * - Browse mode persisted via [`useArrBrowseMode`](../../hooks/useArrBrowseMode.ts).
 * - Icon-grid page-size measurement via
 *   [`useArrIconGridPageSize`](../../hooks/useArrIconGridPageSize.ts).
 * - Filter state (driven by the per-Arr filter spec).
 * - Aggregate state machine via [`useAggregateCatalogLoader`](./useAggregateCatalogLoader.ts).
 * - Per-Arr instance pipeline by calling `definition.useInstancePipeline` (each Arr
 *   chooses flat vs grouped strategy internally).
 * - Detail modal selection + routing to [`ArrCatalogDetailModalHost`](./ArrCatalogDetailModalHost.tsx).
 *
 * Per-Arr definition supplies: filter spec, aggregate adapter, instance pipeline hook,
 * body renderers (aggregate + instance), modal renderer, and search placeholder copy.
 */
export function ArrCatalogShell<
  TInstRow extends Hashable,
  TAggRow extends Hashable,
  TFilters extends Record<string, unknown>,
  TInstSeed,
  TAggSeed,
  TLiveRow,
  TAggResp,
  TRollup,
>({
  definition,
  active,
}: ArrCatalogShellProps<
  TInstRow,
  TAggRow,
  TFilters,
  TInstSeed,
  TAggSeed,
  TLiveRow,
  TAggResp,
  TRollup
>): JSX.Element {
  const { push } = useToast();
  const {
    value: globalSearch,
    setValue: setGlobalSearch,
    register,
    clearHandler,
  } = useSearch();
  const { liveArr } = useWebUI();

  const [instances, setInstances] = useState<ArrInfo[]>([]);
  const [selection, setSelection] = useState<string | "aggregate" | "">("");
  const [filters, setFilters] = useState<TFilters>(definition.initialFilters);
  const [modalSelection, setModalSelection] =
    useState<ArrCatalogModalSelection<TInstSeed | TAggSeed> | null>(null);

  const selectionRef = useRef<string | "aggregate" | "">(selection);
  selectionRef.current = selection;
  const globalSearchRef = useRef(globalSearch);
  globalSearchRef.current = globalSearch;
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const backendReadyWarnedRef = useRef(false);

  const { mode: browseMode, setMode: setBrowseMode } = useArrBrowseMode(
    definition.kind,
  );
  const { gridRef, roundPageSize } = useArrIconGridPageSize(
    browseMode === "icon",
  );

  const aggregatePageSize = useMemo(
    () => roundPageSize(definition.aggregate.basePageSize),
    [roundPageSize, definition.aggregate.basePageSize],
  );

  const iconInstancePageSize = useMemo(
    () => roundPageSize(definition.aggregate.basePageSize),
    [roundPageSize, definition.aggregate.basePageSize],
  );

  const pushToast = useCallback(
    (
      message: string,
      kind?: "info" | "success" | "warning" | "error",
    ) => push(message, kind ?? "info"),
    [push],
  );

  // Single search-handler registration whose closure reads filter / selection from
  // refs.  Aligned across Arrs (Sonarr previously re-registered when `onlyMissing`
  // toggled — this is harmless because the new handler reads the latest filter
  // value via ref).
  const registerSearchHandler = useCallback(
    (handler: (term: string) => void) => {
      register(handler);
      return () => clearHandler(handler);
    },
    [register, clearHandler],
  );

  const loadInstances = useCallback(async () => {
    try {
      const data = await getArrList();
      if (data.ready === false && !backendReadyWarnedRef.current) {
        backendReadyWarnedRef.current = true;
        pushToast(
          `${definition.cardTitle} backend is still initialising. Check the logs if this persists.`,
          "info",
        );
      } else if (data.ready) {
        backendReadyWarnedRef.current = true;
      }
      const filtered = (data.arr || []).filter(
        (arr) => arr.type === definition.arrType,
      );
      setInstances(filtered);
      if (!filtered.length) {
        setSelection("aggregate");
        return;
      }
      const sel = selectionRef.current;
      setSelection(reconcileArrCatalogSelection(filtered, sel));
    } catch (error) {
      pushToast(
        error instanceof Error
          ? error.message
          : `Unable to load ${definition.cardTitle} instances`,
        "error",
      );
    }
  }, [pushToast, definition.arrType, definition.cardTitle]);

  useEffect(() => {
    if (!active) return;
    void loadInstances();
  }, [active, loadInstances]);

  const isAggregate = selection === "aggregate";

  const aggLoader = useAggregateCatalogLoader<
    TAggRow,
    TAggResp,
    TFilters,
    TRollup
  >({
    active,
    selection: isAggregate ? "aggregate" : "",
    instances,
    liveArr,
    globalSearch,
    filters,
    adapter: definition.aggregate,
    aggregatePageSize,
    pushToast,
  });

  const instanceLabel = useMemo(() => {
    if (!selection || selection === "aggregate") return "";
    return (
      instances.find((i) => i.category === selection)?.name ||
      String(selection)
    );
  }, [instances, selection]);

  const instancePipeline = definition.useInstancePipeline({
    active,
    selection:
      !selection || selection === "aggregate" ? null : (selection as string),
    instanceLabel,
    filters,
    browseMode,
    polling:
      Boolean(active) &&
      Boolean(liveArr) &&
      Boolean(selection) &&
      selection !== "aggregate",
    roundPageSize,
    globalSearchRef,
    registerSearchHandler,
    pushToast,
    iconInstancePageSize,
  });

  const handleInstanceSelection = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      const next = (event.target.value || "aggregate") as string | "aggregate";
      setSelection(next);
      if (next !== "aggregate") {
        setGlobalSearch("");
      }
    },
    [setGlobalSearch],
  );

  const renderContext = useMemo(
    () => ({
      instances,
      instanceCount: instances.length,
      browseMode,
      iconGridRef: gridRef,
      filters,
      selection: (selection || "aggregate") as string | "aggregate",
    }),
    [instances, browseMode, gridRef, filters, selection],
  );

  const handleAggSelect = useCallback(
    (row: TAggRow) => {
      const sel = definition.buildAggregateSelection(row, instances);
      if (sel) setModalSelection(sel);
    },
    [definition, instances],
  );

  const handleInstanceSelect = useCallback(
    (row: TInstRow) => {
      if (!selection || selection === "aggregate") return;
      const sel = definition.buildInstanceSelection(
        row,
        selection,
        instanceLabel,
        instances,
      );
      if (sel) setModalSelection(sel);
    },
    [definition, selection, instanceLabel, instances],
  );

  return (
    <section className="card">
      <div className="card-header">{definition.cardTitle}</div>
      <div className="card-body">
        <div className="split">
          <aside className="pane sidebar">
            {instances.length > 1 && (
              <button
                type="button"
                className={`btn ${isAggregate ? "active" : ""}`}
                onClick={() => setSelection("aggregate")}
              >
                {definition.allInstancesLabel}
              </button>
            )}
            {instances.map((inst) => (
              <button
                type="button"
                key={inst.category}
                className={`btn ghost ${
                  selection === inst.category ? "active" : ""
                }`}
                onClick={() => {
                  setSelection(inst.category);
                  setGlobalSearch("");
                }}
              >
                {inst.name || inst.category}
              </button>
            ))}
          </aside>
          <div className="pane">
            <div className="field mobile-instance-select">
              <label>Instance</label>
              <select
                value={selection || "aggregate"}
                onChange={handleInstanceSelection}
                disabled={!instances.length}
              >
                {instances.length > 1 && (
                  <option value="aggregate">
                    {definition.allInstancesLabel}
                  </option>
                )}
                {instances.map((inst) => (
                  <option key={inst.category} value={inst.category}>
                    {inst.name || inst.category}
                  </option>
                ))}
              </select>
            </div>
            <div
              className="row"
              style={{
                alignItems: "flex-end",
                gap: "12px",
                flexWrap: "wrap",
              }}
            >
              <div className="col field" style={{ flex: "1 1 200px" }}>
                <label>Search</label>
                <input
                  placeholder={definition.searchPlaceholder}
                  value={globalSearch}
                  onChange={(event) => setGlobalSearch(event.target.value)}
                />
              </div>
              {definition.filterControls.map((control) => {
                if (control.mode === "instanceOnly" && isAggregate) {
                  return null;
                }
                return (
                  <div
                    key={control.id}
                    className="field"
                    style={{
                      flex: "0 0 auto",
                      minWidth: `${control.minWidth ?? 140}px`,
                    }}
                  >
                    <label>{control.label}</label>
                    <select
                      value={control.getValue(filters)}
                      onChange={(event) =>
                        setFilters((prev) =>
                          control.setValue(prev, event.target.value),
                        )
                      }
                    >
                      {control.options.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              })}
              <div className="field" style={{ flex: "0 0 auto" }}>
                <label>View</label>
                <ArrBrowseModeToggle
                  mode={browseMode}
                  onChange={setBrowseMode}
                  idPrefix={definition.kind}
                />
              </div>
            </div>

            {isAggregate
              ? definition.renderAggregateBody({
                  ...renderContext,
                  rows: aggLoader.visibleRows,
                  rowOrder: aggLoader.rowOrder,
                  rowsStore: aggLoader.rowsStore,
                  loading: aggLoader.loading,
                  total: aggLoader.total,
                  page: aggLoader.page,
                  totalPages: aggLoader.totalPages,
                  aggregatePageSize,
                  summary: aggLoader.summary,
                  lastUpdated: aggLoader.lastUpdated,
                  isAggFiltered: aggLoader.isAggFiltered,
                  onPageChange: aggLoader.setPage,
                  onRefresh: aggLoader.refresh,
                  onRowSelect: handleAggSelect,
                })
              : selection
                ? definition.renderInstanceBody({
                    ...renderContext,
                    ...instancePipeline,
                    category: selection as string,
                    instanceLabel,
                    onRowSelect: handleInstanceSelect,
                  })
                : null}
          </div>
        </div>
      </div>
      {modalSelection ? (
        <ArrCatalogDetailModalHost
          definition={definition}
          selection={modalSelection}
          instanceStore={instancePipeline.rowsStore}
          aggregateStore={aggLoader.rowsStore}
          onClose={() => setModalSelection(null)}
        />
      ) : null}
    </section>
  );
}
