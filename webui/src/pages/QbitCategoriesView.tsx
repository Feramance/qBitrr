import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type JSX,
} from "react";
import { getQbitOverview, getStatus } from "../api/client";
import type { QbitOverviewCategory, QbitTorrentOverview } from "../api/types";
import { QbitTorrentListRow } from "../components/QbitTorrentListRow";
import { useToast } from "../context/ToastContext";
import { useWebUI } from "../context/WebUIContext";
import { useInterval } from "../hooks/useInterval";
import { isSeedingState } from "../utils/qbitTorrentDisplay";
import { ArrCatalogBodyChrome } from "./arrCatalog/ArrCatalogBodyChrome";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / k ** i).toFixed(2)} ${sizes[i]}`;
}

function formatTime(seconds: number): string {
  const totalSeconds = Math.round(seconds);
  if (totalSeconds === 0) return "0s";

  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);

  return parts.join(" ");
}

function getRemoveModeText(mode: number): string {
  switch (mode) {
    case -1:
      return "Never";
    case 1:
      return "On Ratio";
    case 2:
      return "On Time";
    case 3:
      return "Ratio OR Time";
    case 4:
      return "Ratio AND Time";
    default:
      return "Unknown";
  }
}

function reconcileQbitSelection(
  instances: string[],
  current: string | "aggregate" | ""
): string | "aggregate" {
  if (!instances.length) {
    return "aggregate";
  }
  if (instances.length === 1) {
    return instances[0]!;
  }
  if (current === "" || current === "aggregate") {
    return "aggregate";
  }
  if (!instances.includes(current)) {
    return "aggregate";
  }
  return current;
}

function categorySectionKey(cat: QbitOverviewCategory): string {
  const arrPart = cat.arrName ?? "";
  return `${cat.qbitInstance}:${cat.category}:${cat.managedBy}:${arrPart}`;
}

function seedingSummary(cat: QbitOverviewCategory): string {
  const { maxRatio, maxTime, removeMode } = cat.seedingConfig;
  const ratio =
    maxRatio === -1 ? "ratio off" : `max ratio ${maxRatio.toFixed(2)}`;
  const time = maxTime === -1 ? "time off" : `max time ${formatTime(maxTime)}`;
  return `${ratio} · ${time} · ${getRemoveModeText(removeMode)}`;
}

function torrentMatchesQuery(torrent: QbitTorrentOverview, q: string): boolean {
  if (torrent.name.toLowerCase().includes(q)) {
    return true;
  }
  return torrent.tags.some((tag) => tag.toLowerCase().includes(q));
}

interface FilteredCategory extends QbitOverviewCategory {
  /** Torrents after search filter (same as torrents when no search). */
  visibleTorrents: QbitTorrentOverview[];
}

function filterCategories(
  categories: QbitOverviewCategory[],
  search: string
): FilteredCategory[] {
  const q = search.trim().toLowerCase();
  const sorted = [...categories].sort((a, b) => {
    const inst = a.qbitInstance.localeCompare(b.qbitInstance);
    if (inst !== 0) return inst;
    return a.category.localeCompare(b.category);
  });

  if (!q) {
    return sorted.map((cat) => ({ ...cat, visibleTorrents: cat.torrents }));
  }

  const filtered: FilteredCategory[] = [];
  for (const cat of sorted) {
    const categoryHit =
      cat.category.toLowerCase().includes(q) ||
      (cat.arrName?.toLowerCase().includes(q) ?? false) ||
      cat.qbitInstance.toLowerCase().includes(q);
    const matchingTorrents = cat.torrents.filter((t) =>
      torrentMatchesQuery(t, q)
    );
    if (!categoryHit && matchingTorrents.length === 0) {
      continue;
    }
    const visibleTorrents = categoryHit ? cat.torrents : matchingTorrents;
    const seedingCount = visibleTorrents.filter((t) => isSeedingState(t.state)).length;
    const totalSize = visibleTorrents.reduce((sum, t) => sum + t.size, 0);
    filtered.push({
      ...cat,
      torrentCount: visibleTorrents.length,
      seedingCount,
      totalSize,
      visibleTorrents,
    });
  }
  return filtered;
}

interface QbitCategoriesViewProps {
  active: boolean;
}

export function QbitCategoriesView({ active }: QbitCategoriesViewProps): JSX.Element {
  const [instances, setInstances] = useState<string[]>([]);
  const [selection, setSelection] = useState<string | "aggregate" | "">("");
  const [categories, setCategories] = useState<QbitOverviewCategory[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [instancesLoaded, setInstancesLoaded] = useState(false);
  const [overviewLoaded, setOverviewLoaded] = useState(false);
  const { push } = useToast();
  const { liveArr } = useWebUI();
  const isFetching = useRef(false);

  const isAggregate = selection === "aggregate";

  const loadInstances = useCallback(async () => {
    try {
      const status = await getStatus();
      const names = Object.keys(status.qbitInstances ?? {}).sort((a, b) =>
        a.localeCompare(b)
      );
      setInstances(names);
      setSelection((prev) => reconcileQbitSelection(names, prev));
    } catch (error) {
      push(
        error instanceof Error ? error.message : "Failed to load qBit instances",
        "error"
      );
    } finally {
      setInstancesLoaded(true);
    }
  }, [push]);

  const loadOverview = useCallback(
    async (showLoading = true) => {
      if (isFetching.current || !selection) {
        return;
      }
      isFetching.current = true;
      if (showLoading) {
        setLoading(true);
      }
      try {
        const instanceArg =
          selection === "aggregate" ? undefined : selection;
        const data = await getQbitOverview(instanceArg);
        setCategories(data.categories);
        if (data.instances.length) {
          setInstances((prev) => {
            const merged = Array.from(
              new Set([...prev, ...data.instances])
            ).sort((a, b) => a.localeCompare(b));
            return merged.length === prev.length &&
              merged.every((name, i) => name === prev[i])
              ? prev
              : merged;
          });
        }
      } catch (error) {
        // Background Live polls must stay silent — avoid network-error toast spam.
        if (showLoading) {
          push(
            error instanceof Error
              ? error.message
              : "Failed to load qBit overview",
            "error"
          );
        }
      } finally {
        isFetching.current = false;
        setOverviewLoaded(true);
        if (showLoading) {
          setLoading(false);
        }
      }
    },
    [push, selection]
  );

  useEffect(() => {
    const id = window.setTimeout(() => {
      setOverviewLoaded(false);
    }, 0);
    return () => window.clearTimeout(id);
  }, [selection]);

  useEffect(() => {
    if (!active) {
      return;
    }
    const id = window.setTimeout(() => {
      void loadInstances();
    }, 0);
    return () => window.clearTimeout(id);
  }, [active, loadInstances]);

  useEffect(() => {
    if (!active || !selection) {
      return;
    }
    const id = window.setTimeout(() => {
      void loadOverview();
    }, 0);
    return () => window.clearTimeout(id);
  }, [active, selection, loadOverview]);

  useInterval(
    () => {
      void loadOverview(false);
    },
    active && liveArr && selection ? 5000 : null
  );

  const handleRefresh = useCallback(() => {
    void loadInstances();
    void loadOverview();
  }, [loadInstances, loadOverview]);

  const selectInstance = useCallback((value: string | "aggregate") => {
    setSelection(value);
    setSearch("");
  }, []);

  const handleInstanceSelection = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      selectInstance(event.target.value as string | "aggregate");
    },
    [selectInstance]
  );

  const toggleSection = useCallback((key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const filteredCategories = useMemo(
    () => filterCategories(categories, search),
    [categories, search]
  );

  // Honor Processes deep-link focus (expand that category only).
  useEffect(() => {
    if (!active || !filteredCategories.length) {
      return;
    }
    const focusCategory = sessionStorage.getItem("qbitrr:focusQbitCategory");
    if (!focusCategory) {
      return;
    }
    sessionStorage.removeItem("qbitrr:focusQbitCategory");
    const id = window.setTimeout(() => {
      setExpanded((prev) => {
        let changed = false;
        const next = { ...prev };
        for (const cat of filteredCategories) {
          const key = categorySectionKey(cat);
          if (cat.category === focusCategory && next[key] !== true) {
            next[key] = true;
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    }, 0);
    return () => window.clearTimeout(id);
  }, [active, filteredCategories]);

  const summary = useMemo(() => {
    const totalTorrents = filteredCategories.reduce(
      (sum, cat) => sum + cat.torrentCount,
      0
    );
    const totalSeeding = filteredCategories.reduce(
      (sum, cat) => sum + cat.seedingCount,
      0
    );
    const totalSize = filteredCategories.reduce(
      (sum, cat) => sum + cat.totalSize,
      0
    );
    const qbitCount = filteredCategories.filter(
      (cat) => cat.managedBy === "qbit"
    ).length;
    const arrCount = filteredCategories.filter(
      (cat) => cat.managedBy === "arr"
    ).length;

    return {
      totalTorrents,
      totalSeeding,
      totalSize,
      qbitCount,
      arrCount,
      categoryCount: filteredCategories.length,
    };
  }, [filteredCategories]);

  const summaryLine = (
    <>
      <div>
        Monitored-category torrent overview
        {selection && selection !== "aggregate"
          ? ` · ${selection}`
          : instances.length > 1
            ? " · All qBittorrent"
            : ""}
      </div>
      <div className="qbit-summary-stats">
        <div className="qbit-summary-stat">
          <span className="qbit-summary-stat__label">Categories</span>
          <span className="qbit-summary-stat__value">
            {summary.categoryCount}
          </span>
        </div>
        <div className="qbit-summary-stat">
          <span className="qbit-summary-stat__label">qBit-managed</span>
          <span className="qbit-summary-stat__value">{summary.qbitCount}</span>
        </div>
        <div className="qbit-summary-stat">
          <span className="qbit-summary-stat__label">Arr-managed</span>
          <span className="qbit-summary-stat__value">{summary.arrCount}</span>
        </div>
        <div className="qbit-summary-stat">
          <span className="qbit-summary-stat__label">Torrents</span>
          <span className="qbit-summary-stat__value">
            {summary.totalTorrents.toLocaleString()}
          </span>
        </div>
        <div className="qbit-summary-stat">
          <span className="qbit-summary-stat__label">Seeding</span>
          <span className="qbit-summary-stat__value">
            {summary.totalSeeding.toLocaleString()}
          </span>
        </div>
        <div className="qbit-summary-stat">
          <span className="qbit-summary-stat__label">Total size</span>
          <span className="qbit-summary-stat__value">
            {formatBytes(summary.totalSize)}
          </span>
        </div>
      </div>
    </>
  );

  const showInitialLoading =
    !instancesLoaded ||
    (Boolean(selection) && !overviewLoaded && categories.length === 0) ||
    (loading && categories.length === 0);

  let body: JSX.Element;
  if (showInitialLoading) {
    body = <></>;
  } else if (!instances.length) {
    body = (
      <div className="hint">
        No qBittorrent instances found. Configure a `[qBit]` section to use this
        view.
      </div>
    );
  } else if (categories.length === 0) {
    body = (
      <div className="hint">
        No monitored categories found. Configure ManagedCategories in your qBit
        config sections or add Arr instances.
      </div>
    );
  } else if (filteredCategories.length === 0) {
    body = (
      <div className="hint">No categories or torrents match your search.</div>
    );
  } else {
    body = (
      <div className="qbit-category-sections">
        {filteredCategories.map((cat) => {
          const key = categorySectionKey(cat);
          const isOpen = Boolean(expanded[key]);
          return (
            <section key={key} className="qbit-category-section">
              <button
                type="button"
                className="qbit-category-section__header"
                aria-expanded={isOpen}
                onClick={() => toggleSection(key)}
              >
                <span
                  className={`qbit-category-section__chevron${
                    isOpen ? " is-open" : ""
                  }`}
                  aria-hidden
                />
                <span className="qbit-category-section__title">
                  <span className="qbit-category-section__name">
                    {cat.category}
                  </span>
                  {cat.managedBy === "qbit" ? (
                    <span className="badge badge-qbit">qBit</span>
                  ) : (
                    <span className="badge badge-arr">
                      Arr
                      {cat.arrName ? ` · ${cat.arrName}` : ""}
                    </span>
                  )}
                  {isAggregate && (
                    <span className="badge">{cat.qbitInstance}</span>
                  )}
                </span>
                <span className="qbit-category-section__meta">
                  {cat.torrentCount.toLocaleString()} torrents ·{" "}
                  {cat.seedingCount.toLocaleString()} seeding ·{" "}
                  {formatBytes(cat.totalSize)}
                </span>
                <span className="qbit-category-section__policy hint">
                  {seedingSummary(cat)}
                </span>
              </button>
              {isOpen && (
                <div className="qbit-category-section__body">
                  {cat.visibleTorrents.length === 0 ? (
                    <div className="hint">
                      No torrents in this category on {cat.qbitInstance}.
                    </div>
                  ) : (
                    <div className="qbit-torrent-list">
                      {cat.torrentsTruncated ? (
                        <div className="hint">
                          Showing first {cat.visibleTorrents.length.toLocaleString()}{" "}
                          of {cat.torrentCount.toLocaleString()} torrents.
                        </div>
                      ) : null}
                      {cat.visibleTorrents.map((torrent) => (
                        <QbitTorrentListRow
                          key={torrent.hash || torrent.name}
                          torrent={torrent}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </section>
          );
        })}
      </div>
    );
  }

  return (
    <section className="card">
      <div className="card-header">qBittorrent</div>
      <div className="card-body">
        <div className="split">
          <aside className="pane sidebar">
            {instances.length > 1 && (
              <button
                type="button"
                className={`btn ${isAggregate ? "active" : ""}`}
                onClick={() => selectInstance("aggregate")}
              >
                All qBittorrent
              </button>
            )}
            {instances.map((name) => (
              <button
                type="button"
                key={name}
                className={`btn ghost ${selection === name ? "active" : ""}`}
                onClick={() => selectInstance(name)}
              >
                {name}
              </button>
            ))}
          </aside>

          <div className="pane">
            <div className="field mobile-instance-select">
              <label htmlFor="qbit-instance-select">Instance</label>
              <select
                id="qbit-instance-select"
                value={selection || "aggregate"}
                onChange={handleInstanceSelection}
                disabled={!instances.length}
              >
                {instances.length > 1 && (
                  <option value="aggregate">All qBittorrent</option>
                )}
                {instances.map((name) => (
                  <option key={name} value={name}>
                    {name}
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
                <label htmlFor="qbit-search">Search</label>
                <input
                  id="qbit-search"
                  placeholder="Filter categories or torrents…"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  disabled={!instances.length}
                />
              </div>
            </div>

            <ArrCatalogBodyChrome
              summaryLine={summaryLine}
              onRefresh={handleRefresh}
              loading={showInitialLoading}
              loadingHint="Loading overview…"
              hasRows={categories.length > 0}
            >
              {body}
            </ArrCatalogBodyChrome>
          </div>
        </div>
      </div>
    </section>
  );
}
