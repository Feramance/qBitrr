import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import {
  getProcesses,
  getQbitCategories,
  getStatus,
  rebuildArrs,
  restartAllProcesses,
  restartProcess,
} from "../api/client";
import type { ProcessInfo, QbitCategory, StatusResponse } from "../api/types";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { requestNavigateTab } from "../utils/navigateTab";

import RefreshIcon from "../icons/refresh-arrow.svg";
import ToolsIcon from "../icons/build.svg";

const QUALITY_TOKEN_REGEX =
  /\b(480p|576p|720p|1080p|2160p|4k|8k|web[-_. ]?(?:dl|rip)|hdrip|hdtv|bluray|bd(?:rip)?|brrip|webrip|remux|x264|x265|hevc|dts|truehd|atmos|proper|repack|dvdrip|hdr|amzn|nf)\b/i;
const EPISODE_TOKEN_REGEX = /\bS\d{1,3}E\d{1,3}\b/i;
const SEASON_TOKEN_REGEX = /\bSeason\s+\d+\b/i;

function sanitizeSearchSummary(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";

  // Keep "X queued items" messages as-is (don't filter them out)
  if (/^\d+\s+queued item/i.test(trimmed)) {
    return trimmed;
  }

  const normalized = trimmed.replace(/\s+/g, " ");
  const releaseMatch = normalized.match(
    /^(?<title>.+?)\s+(?<year>(?:19|20)\d{2})(?:\s+(?<rest>.*))?$/
  );

  if (releaseMatch) {
    const rest = releaseMatch.groups?.rest ?? "";
    const looksLikeEpisode =
      EPISODE_TOKEN_REGEX.test(rest) || SEASON_TOKEN_REGEX.test(rest);
    if (rest && !looksLikeEpisode && QUALITY_TOKEN_REGEX.test(rest)) {
      const rawTitle = releaseMatch.groups?.title ?? "";
      const cleanedTitle = rawTitle
        .replace(/[-_.]/g, " ")
        .replace(/\s{2,}/g, " ")
        .trim();
      const year = releaseMatch.groups?.year ?? "";
      if (cleanedTitle) {
        return year ? `${cleanedTitle} (${year})` : cleanedTitle;
      }
    }
  }

  return normalized;
}

function isProcessEqual(a: ProcessInfo, b: ProcessInfo): boolean {
  return (
    a.category === b.category &&
    a.name === b.name &&
    a.kind === b.kind &&
    a.pid === b.pid &&
    a.alive === b.alive &&
    (a.rebuilding ?? false) === (b.rebuilding ?? false) &&
    (a.searchSummary ?? "") === (b.searchSummary ?? "") &&
    (a.searchTimestamp ?? "") === (b.searchTimestamp ?? "") &&
    (a.queueCount ?? null) === (b.queueCount ?? null) &&
    (a.categoryCount ?? null) === (b.categoryCount ?? null) &&
    (a.freeSpacePaused ?? null) === (b.freeSpacePaused ?? null) &&
    (a.metricType ?? "") === (b.metricType ?? "")
  );
}

function areProcessListsEqual(a: ProcessInfo[], b: ProcessInfo[]): boolean {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  for (let index = 0; index < a.length; index += 1) {
    if (!isProcessEqual(a[index], b[index])) {
      return false;
    }
  }
  return true;
}

function getRefreshDelay(active: boolean): number | null {
  if (!active) return null;
  return 2000;
}

function formatKind(kind: string): string {
  return kind ? kind.charAt(0).toUpperCase() + kind.slice(1) : kind;
}

function formatRelativeTime(iso: string): string | null {
  const ts = Date.parse(iso);
  if (Number.isNaN(ts)) return null;
  const deltaSec = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (deltaSec < 45) return "just now";
  if (deltaSec < 3600) {
    const mins = Math.max(1, Math.round(deltaSec / 60));
    return `${mins}m ago`;
  }
  if (deltaSec < 86400) {
    const hours = Math.max(1, Math.round(deltaSec / 3600));
    return `${hours}h ago`;
  }
  const days = Math.max(1, Math.round(deltaSec / 86400));
  return `${days}d ago`;
}

type StatusTone = "ok" | "bad" | "partial" | "neutral" | "";

function statusToneClass(tone: StatusTone): string {
  if (tone === "ok") return "process-status process-status--ok";
  if (tone === "bad") return "process-status process-status--bad";
  if (tone === "partial") return "process-status process-status--partial";
  return "process-status process-status--neutral";
}

/** Plain-language activity line for a process chip. */
function buildProcessActivity(item: ProcessInfo): {
  text: string;
  warn?: boolean;
} {
  const kindLower = item.kind.toLowerCase();

  if (item.rebuilding) {
    return { text: "Rebuilding…", warn: true };
  }

  if (kindLower === "search") {
    const summary = (item.searchSummary ?? "").trim();
    if (/^updating database$/i.test(summary)) {
      return { text: "Updating library…" };
    }
    if (!summary) {
      return { text: "No active search" };
    }
    const relative = item.searchTimestamp
      ? formatRelativeTime(item.searchTimestamp)
      : null;
    const line = `Searching: ${summary}`;
    return {
      text: relative ? `${line} · ${relative}` : line,
    };
  }

  if (kindLower === "category") {
    const count =
      typeof item.categoryCount === "number" ? item.categoryCount : null;
    if (count === null) {
      return { text: "Managing categories" };
    }
    return {
      text: `Managing ${count} ${count === 1 ? "category" : "categories"}`,
    };
  }

  if (kindLower === "torrent") {
    const metricType = item.metricType?.toLowerCase() ?? "";
    const categoryTotal =
      typeof item.categoryCount === "number" ? item.categoryCount : null;
    const queueTotal =
      typeof item.queueCount === "number" ? item.queueCount : null;
    const freeSpacePaused =
      typeof item.freeSpacePaused === "number" ? item.freeSpacePaused : null;

    const parts: string[] = [];
    if (queueTotal !== null) {
      parts.push(
        queueTotal === 0 ? "None in progress" : `${queueTotal} in progress`,
      );
    }
    if (categoryTotal !== null) {
      parts.push(`${categoryTotal} tracked`);
    }
    if (freeSpacePaused !== null && freeSpacePaused > 0) {
      parts.push(`${freeSpacePaused} paused for free space`);
    } else if (metricType === "free-space" && queueTotal !== null) {
      parts.push("free-space pause");
    }

    if (parts.length === 0) {
      return { text: "No torrent activity" };
    }
    return {
      text: parts.join(" · "),
      warn: Boolean(freeSpacePaused && freeSpacePaused > 0),
    };
  }

  return { text: "" };
}

function ProcessChipView({
  item,
  onRestart,
}: {
  item: ProcessInfo;
  onRestart: (category: string, kind: string) => void;
}): JSX.Element {
  const aliveLabel = item.alive ? "Running" : "Stopped";
  const activity = buildProcessActivity(item);
  return (
    <div className="process-chip">
      <div className="process-chip__row">
        <span
          className={`process-status__dot ${
            item.alive ? "process-status__dot--ok" : "process-status__dot--bad"
          }`}
          title={aliveLabel}
          aria-label={aliveLabel}
        />
        <span className="process-chip__name">{formatKind(item.kind)}</span>
        <div className="process-chip__actions">
          <button
            className="btn small ghost process-action-btn"
            type="button"
            onClick={() => onRestart(item.category, item.kind)}
          >
            Restart
          </button>
        </div>
      </div>
      {activity.text ? (
        <div
          className={`process-chip__summary${
            activity.warn ? " process-chip__summary--warn" : ""
          }`}
          title={activity.text}
        >
          {activity.text}
        </div>
      ) : null}
    </div>
  );
}

function QbitCategoryChip({
  cat,
  instanceAlive,
  onOpen,
}: {
  cat: QbitCategory;
  instanceAlive: boolean;
  onOpen: () => void;
}): JSX.Element {
  const aliveLabel = instanceAlive ? "Online" : "Offline";
  const parts = [`${cat.torrentCount.toLocaleString()} torrents`];
  if (cat.seedingCount > 0) {
    parts.push(`${cat.seedingCount.toLocaleString()} seeding`);
  }
  const summary = parts.join(" · ");
  return (
    <button
      type="button"
      className="process-chip process-chip--info process-chip--link"
      title={`Open ${cat.category} in qBittorrent`}
      onClick={onOpen}
    >
      <div className="process-chip__row">
        <span
          className={`process-status__dot ${
            instanceAlive
              ? "process-status__dot--ok"
              : "process-status__dot--bad"
          }`}
          title={aliveLabel}
          aria-label={aliveLabel}
        />
        <span className="process-chip__name">{cat.category}</span>
      </div>
      <div className="process-chip__summary" title={summary}>
        {summary}
      </div>
    </button>
  );
}

interface ProcessesViewProps {
  active: boolean;
}

export function ProcessesView({ active }: ProcessesViewProps): JSX.Element {
  const [processes, setProcesses] = useState<ProcessInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [restartingAll, setRestartingAll] = useState(false);
  const [rebuildingArrs, setRebuildingArrs] = useState(false);
  const [statusData, setStatusData] = useState<StatusResponse | null>(null);
  const [qbitCategories, setQbitCategories] = useState<QbitCategory[]>([]);
  const [confirmAction, setConfirmAction] = useState<{
    title: string;
    message: string;
    onConfirm: () => void;
    danger?: boolean;
  } | null>(null);
  const { push } = useToast();
  const isFetching = useRef(false);

  const load = useCallback(async (showLoading = true) => {
    if (isFetching.current) {
      return;
    }
    isFetching.current = true;
    if (showLoading) {
      setLoading(true);
    }
    try {
      const [processData, status, categoriesData] = await Promise.all([
        getProcesses(),
        getStatus(),
        getQbitCategories().catch(() => null),
      ]);
      const next = (processData.processes ?? []).map((process) => {
        if (typeof process.searchSummary === "string") {
          const sanitized = sanitizeSearchSummary(process.searchSummary);
          return {
            ...process,
            searchSummary: sanitized,
          };
        }
        return process;
      });
      setProcesses((prev) =>
        areProcessListsEqual(prev, next) ? prev : next
      );
      setStatusData(status);
      if (categoriesData?.categories) {
        setQbitCategories(categoriesData.categories);
      }
    } catch (error) {
      // Background polls must stay silent — transient network blips spam toasts otherwise.
      if (showLoading) {
        push(
          error instanceof Error
            ? error.message
            : "Failed to load processes list",
          "error"
        );
      }
    } finally {
      isFetching.current = false;
      setHasLoaded(true);
      if (showLoading) {
        setLoading(false);
      }
    }
  }, [push]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(id);
  }, [load]);

  useEffect(() => {
    if (active) {
      const id = window.setTimeout(() => {
        void load();
      }, 0);
      return () => window.clearTimeout(id);
    }
  }, [active, load]);

  const refreshDelay = useMemo(
    () => getRefreshDelay(active),
    [active]
  );

  useInterval(() => {
    void load(false);
  }, refreshDelay);

  const handleRestart = useCallback(
    async (category: string, kind: string) => {
      try {
        await restartProcess(category, kind);
        push(`Restarted ${category}:${kind}`, "success");
        void load();
      } catch (error) {
        push(
          error instanceof Error
            ? error.message
            : `Failed to restart ${category}:${kind}`,
          "error"
        );
      }
    },
    [load, push]
  );

  const handleRestartAll = useCallback(() => {
    setConfirmAction({
      title: "Restart All Processes",
      message:
        "Are you sure you want to restart all processes? This will temporarily interrupt all operations.",
      danger: true,
      onConfirm: async () => {
        setConfirmAction(null);
        setRestartingAll(true);
        try {
          await restartAllProcesses();
          push("Restarted all processes", "success");
          void load();
        } catch (error) {
          push(
            error instanceof Error ? error.message : "Failed to restart all",
            "error"
          );
        } finally {
          setRestartingAll(false);
        }
      },
    });
  }, [load, push]);

  const handleRebuildArrs = useCallback(() => {
    setConfirmAction({
      title: "Rebuild Arrs",
      message:
        "Are you sure you want to rebuild all Arr instances? This will refresh all connections and may take some time.",
      danger: true,
      onConfirm: async () => {
        setConfirmAction(null);
        setRebuildingArrs(true);
        try {
          await rebuildArrs();
          push("Requested Arr rebuild", "success");
          void load();
        } catch (error) {
          push(
            error instanceof Error ? error.message : "Failed to rebuild Arrs",
            "error"
          );
        } finally {
          setRebuildingArrs(false);
        }
      },
    });
  }, [load, push]);

  const handleRestartGroup = useCallback(
    (items: ProcessInfo[]) => {
      const label = items[0]?.name ?? "group";
      setConfirmAction({
        title: "Restart All Processes",
        message: `Restart all processes for ${label}?`,
        danger: true,
        onConfirm: async () => {
          setConfirmAction(null);
          try {
            await Promise.all(
              items.map((item) => restartProcess(item.category, item.kind))
            );
            push(`Restarted ${label}`, "success");
            void load();
          } catch (error) {
            push(
              error instanceof Error
                ? error.message
                : "Failed to restart process group",
              "error"
            );
          }
        },
      });
    },
    [load, push]
  );

  const groupedProcesses = useMemo(() => {
    interface Instance {
      name: string;
      items: ProcessInfo[];
    }
    interface AppGroup {
      app: string;
      instances: Instance[];
    }
    const appBuckets = new Map<string, Map<string, ProcessInfo[]>>();

    const classifyApp = (proc: ProcessInfo): string => {
      const category = (proc.category ?? "").toLowerCase();
      const name = (proc.name ?? "").toLowerCase();
      if (category.includes("radarr") || name.includes("radarr")) return "Radarr";
      if (category.includes("sonarr") || name.includes("sonarr")) return "Sonarr";
      if (category.includes("lidarr") || name.includes("lidarr")) return "Lidarr";
      if (category.includes("readarr") || name.includes("readarr")) return "Readarr";
      if (
        category.includes("qbit") ||
        category.includes("qbittorrent") ||
        name.includes("qbit") ||
        name.includes("qbittorrent")
      ) {
        return "qBittorrent";
      }
      return "Other";
    };

    const arrs = statusData?.arrs ?? [];
    const hasRadarr = arrs.some((arr) => arr.type === "radarr");
    const hasSonarr = arrs.some((arr) => arr.type === "sonarr");
    const hasLidarr = arrs.some((arr) => arr.type === "lidarr");
    const hasReadarr = arrs.some((arr) => arr.type === "readarr");

    const qbitInstanceNames = statusData?.qbitInstances
      ? Object.keys(statusData.qbitInstances)
      : [];
    const qbitCategoryNames = new Set(
      qbitCategories.map((c) => c.category.toLowerCase())
    );

    processes.forEach((proc) => {
      const app = classifyApp(proc);

      if (app === "Radarr" && !hasRadarr) return;
      if (app === "Sonarr" && !hasSonarr) return;
      if (app === "Lidarr" && !hasLidarr) return;
      if (app === "Readarr" && !hasReadarr) return;

      const kindLower = (proc.kind ?? "").toLowerCase();
      const procCategoryLower = (proc.category ?? "").toLowerCase();
      if (app === "Other" && qbitInstanceNames.length > 0) {
        const isQbitCategoryKind = kindLower === "category";
        const matchesQbitInstance =
          isQbitCategoryKind &&
          qbitInstanceNames.some((inst) => {
            const instLower = inst.toLowerCase();
            return (
              procCategoryLower === instLower ||
              procCategoryLower === `qbit-${instLower}` ||
              procCategoryLower.endsWith(`-${instLower}`) ||
              procCategoryLower.endsWith(`_${instLower}`)
            );
          });
        const isConfiguredQbitCategory =
          qbitCategoryNames.has(procCategoryLower);
        if (matchesQbitInstance || isConfiguredQbitCategory) return;
      }

      if (!appBuckets.has(app)) appBuckets.set(app, new Map());
      const instances = appBuckets.get(app)!;
      const instanceKey =
        proc.name || proc.category || `${proc.category}:${proc.kind}`;
      if (!instances.has(instanceKey)) instances.set(instanceKey, []);
      instances.get(instanceKey)!.push(proc);
    });

    if (qbitInstanceNames.length > 0) {
      if (!appBuckets.has("qBittorrent")) {
        appBuckets.set("qBittorrent", new Map());
      }
      const qbitInstances = appBuckets.get("qBittorrent")!;
      for (const instanceName of qbitInstanceNames) {
        const displayName = instanceName.toLowerCase().startsWith("qbit")
          ? instanceName
          : `qBit-${instanceName}`;
        if (!qbitInstances.has(displayName)) {
          qbitInstances.set(displayName, []);
        }
      }
    }

    const appOrder = ["Radarr", "Sonarr", "Lidarr", "Readarr", "qBittorrent", "Other"];

    const result: AppGroup[] = Array.from(appBuckets.entries())
      .map(([app, instances]) => {
        const sortedInstances = Array.from(instances.entries())
          .map(([name, items]) => ({
            name,
            items: items.sort((a, b) => a.kind.localeCompare(b.kind)),
          }))
          .sort((a, b) => a.name.localeCompare(b.name));
        return { app, instances: sortedInstances };
      })
      .filter((group) => group.instances.length);

    result.sort((a, b) => {
      const order = (label: string) => {
        const index = appOrder.indexOf(label);
        return index === -1 ? Number.MAX_SAFE_INTEGER : index;
      };
      return order(a.app) - order(b.app) || a.app.localeCompare(b.app);
    });

    return result;
  }, [processes, statusData, qbitCategories]);

  const cardsByApp = groupedProcesses.map(({ app, instances }) => {
    const cards = instances.map(({ name: instanceName, items }) => {
      const instanceCategories =
        app === "qBittorrent"
          ? qbitCategories.filter((cat) => {
              const nameLower = instanceName.toLowerCase();
              const instLower = cat.instance.toLowerCase();
              return (
                nameLower === instLower ||
                nameLower.endsWith(`-${instLower}`) ||
                nameLower.endsWith(`_${instLower}`)
              );
            })
          : [];
      const name = instanceName;
      const runningCount = items.filter((item) => item.alive).length;
      const totalCount = items.length;
      const qbitInstanceKey =
        app === "qBittorrent" && totalCount === 0
          ? instanceName.toLowerCase().startsWith("qbit-")
            ? instanceName.slice(5)
            : instanceName
          : null;
      const qbitInstanceAlive =
        qbitInstanceKey != null
          ? (statusData?.qbitInstances?.[qbitInstanceKey]?.alive ?? false)
          : null;

      const tone: StatusTone =
        totalCount === 0 && qbitInstanceAlive !== null
          ? qbitInstanceAlive
            ? "ok"
            : "bad"
          : totalCount === 0
            ? "neutral"
            : runningCount === totalCount
              ? "ok"
              : runningCount === 0
                ? "bad"
                : "partial";

      const statusLabel =
        totalCount === 0 && qbitInstanceAlive !== null
          ? qbitInstanceAlive
            ? "Instance running"
            : "Instance stopped"
          : totalCount === 0
            ? "No processes"
            : runningCount === totalCount
              ? "All running"
              : runningCount === 0
                ? "Stopped"
                : `${runningCount}/${totalCount} running`;
      const statusCountLabel =
        totalCount === 0 && qbitInstanceAlive !== null
          ? qbitInstanceAlive
            ? "up"
            : "down"
          : totalCount === 0
            ? "—"
            : `${runningCount}/${totalCount}`;
      const displayName =
        name === "FreeSpaceManager"
          ? "Free Space Manager"
          : name === "TorrentPolicyManager"
            ? "Torrent Policy Manager"
            : name;
      const uniqueKinds = Array.from(new Set(items.map((item) => item.kind)));
      const filteredKinds = uniqueKinds.filter((kind) => {
        const lower = kind.toLowerCase();
        return lower !== "search" && lower !== "torrent";
      });

      const listClass =
        app === "qBittorrent" && instanceCategories.length > 1
          ? "process-card__list process-card__list--grid"
          : "process-card__list process-card__list--stack";

      return (
        <div className="process-card" key={name}>
          <div className="process-card__header">
            <div className="process-card__title">
              <div className="process-card__name">{displayName}</div>
              {app !== "qBittorrent" && filteredKinds.length ? (
                <div className="process-card__badges">
                  {filteredKinds.map((kind) => (
                    <span
                      key={`${name}:${kind}:badge`}
                      className="process-card__badge"
                    >
                      {formatKind(kind)}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="process-card__header-actions">
              <div
                className={statusToneClass(tone)}
                title={statusLabel}
                aria-label={statusLabel}
              >
                <span className="process-status__dot" aria-hidden="true" />
                <span className="process-status__count">{statusCountLabel}</span>
              </div>
              {items.length > 0 ? (
                <button
                  className="btn small ghost process-action-btn"
                  type="button"
                  onClick={() => {
                    handleRestartGroup(items);
                  }}
                >
                  Restart All
                </button>
              ) : null}
            </div>
          </div>
          <div className={listClass}>
            {items.map((item) => (
              <ProcessChipView
                key={`${item.category}:${item.kind}`}
                item={item}
                onRestart={(category, kind) => {
                  void handleRestart(category, kind);
                }}
              />
            ))}
            {instanceCategories.map((cat) => (
              <QbitCategoryChip
                key={`cat:${cat.instance}:${cat.category}`}
                cat={cat}
                instanceAlive={
                  statusData?.qbitInstances?.[cat.instance]?.alive ?? false
                }
                onOpen={() =>
                  requestNavigateTab({
                    tab: "qbittorrent",
                    qbitCategory: cat.category,
                  })
                }
              />
            ))}
          </div>
        </div>
      );
    });
    return { app, cards };
  });

  return (
    <>
      <section className="card">
        <div className="card-header">Processes</div>
        <div className="card-body stack">
          <div className="row">
            <div className="col inline">
              <button
                className="btn ghost"
                type="button"
                onClick={() => void load()}
                disabled={loading}
              >
                {loading && <span className="spinner" />}
                <IconImage src={RefreshIcon} />
                {loading ? "Refreshing..." : "Refresh"}
              </button>
              <button
                className="btn ghost"
                type="button"
                onClick={() => void handleRestartAll()}
                disabled={restartingAll}
              >
                {restartingAll && <span className="spinner" />}
                <IconImage src={RefreshIcon} />
                {restartingAll ? "Restarting..." : "Restart All"}
              </button>
              <button
                className="btn ghost"
                type="button"
                onClick={() => void handleRebuildArrs()}
                disabled={rebuildingArrs}
              >
                {rebuildingArrs && <span className="spinner" />}
                <IconImage src={ToolsIcon} />
                {rebuildingArrs ? "Rebuilding..." : "Rebuild Arrs"}
              </button>
            </div>
          </div>
          {!hasLoaded && loading ? (
            <div className="loading">
              <span className="spinner" /> Loading processes…
            </div>
          ) : cardsByApp.length ? (
            cardsByApp.map(({ app, cards }) => (
              <div className="process-section" key={app}>
                <div className="process-section__title">{app}</div>
                <div className="process-grid">{cards}</div>
              </div>
            ))
          ) : (
            <div className="empty-state">No processes available.</div>
          )}
        </div>
      </section>
      {confirmAction && (
        <ConfirmDialog
          title={confirmAction.title}
          message={confirmAction.message}
          confirmLabel="Confirm"
          cancelLabel="Cancel"
          danger={confirmAction.danger ?? true}
          onConfirm={confirmAction.onConfirm}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </>
  );
}
