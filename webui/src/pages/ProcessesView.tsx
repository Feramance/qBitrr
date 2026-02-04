import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import {
  getProcesses,
  getStatus,
  rebuildArrs,
  restartAllProcesses,
  restartProcess,
} from "../api/client";
import type { ProcessInfo, StatusResponse } from "../api/types";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
import { ConfirmDialog } from "../components/ConfirmDialog";

import RefreshIcon from "../icons/refresh-arrow.svg";
import RestartIcon from "../icons/refresh-arrow.svg";
import ToolsIcon from "../icons/build.svg";

const RELEASE_TOKEN_REGEX =
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
    if (rest && !looksLikeEpisode && RELEASE_TOKEN_REGEX.test(rest)) {
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
  // Refresh every 1 second when active
  return 1000;
}

interface ProcessesViewProps {
  active: boolean;
}

export function ProcessesView({ active }: ProcessesViewProps): JSX.Element {
  const [processes, setProcesses] = useState<ProcessInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [restartingAll, setRestartingAll] = useState(false);
  const [rebuildingArrs, setRebuildingArrs] = useState(false);
  const [statusData, setStatusData] = useState<StatusResponse | null>(null);
  const [confirmAction, setConfirmAction] = useState<{
    title: string;
    message: string;
    onConfirm: () => void;
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
      const [processData, status] = await Promise.all([
        getProcesses(),
        getStatus(),
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
    } catch (error) {
      push(
        error instanceof Error
          ? error.message
          : "Failed to load processes list",
        "error"
      );
    } finally {
      isFetching.current = false;
      if (showLoading) {
        setLoading(false);
      }
    }
  }, [push]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (active) {
      void load();
    }
  }, [active, load]);

  const refreshDelay = useMemo(
    () => getRefreshDelay(active),
    [active]
  );

  useInterval(() => {
    void load(false); // Auto-refresh without showing loading spinner
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

  const handleRestartAll = useCallback(async () => {
    setConfirmAction({
      title: "Restart All Processes",
      message: "Are you sure you want to restart all processes? This will temporarily interrupt all operations.",
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
      }
    });
  }, [load, push]);

  const handleRebuildArrs = useCallback(async () => {
    setConfirmAction({
      title: "Rebuild Arrs",
      message: "Are you sure you want to rebuild all Arr instances? This will refresh all connections and may take some time.",
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
      }
    });
  }, [load, push]);

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

    // Check which Arr types are configured
    const arrs = statusData?.arrs ?? [];
    const hasRadarr = arrs.some((arr) => arr.type === "radarr");
    const hasSonarr = arrs.some((arr) => arr.type === "sonarr");
    const hasLidarr = arrs.some((arr) => arr.type === "lidarr");

    processes.forEach((proc) => {
      const app = classifyApp(proc);

      // Skip Arr processes if that Arr type is not configured
      if (app === "Radarr" && !hasRadarr) return;
      if (app === "Sonarr" && !hasSonarr) return;
      if (app === "Lidarr" && !hasLidarr) return;

      if (!appBuckets.has(app)) appBuckets.set(app, new Map());
      const instances = appBuckets.get(app)!;
      const instanceKey =
        proc.name || proc.category || `${proc.category}:${proc.kind}`;
      if (!instances.has(instanceKey)) instances.set(instanceKey, []);
      instances.get(instanceKey)!.push(proc);
    });

    const appOrder = ["Radarr", "Sonarr", "Lidarr", "qBittorrent", "Other"];

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
  }, [processes, statusData]);

  const handleRestartGroup = useCallback(
    async (items: ProcessInfo[]) => {
      try {
        await Promise.all(
          items.map((item) => restartProcess(item.category, item.kind))
        );
        push(`Restarted ${items[0]?.name ?? "group"}`, "success");
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
    [load, push]
  );

  const cardsByApp = groupedProcesses.map(({ app, instances }) => {
        const cards = instances.map(({ name, items }) => {
          const runningCount = items.filter((item) => item.alive).length;
          const totalCount = items.length;
          const tone =
            totalCount === 0
              ? ""
              : runningCount === totalCount
              ? "status-indicator--ok"
              : runningCount === 0
              ? "status-indicator--bad"
              : "";
          const statusClass = ["status-indicator"];
          if (tone) statusClass.push(tone);
          const statusLabel =
            totalCount === 0
              ? "No processes"
              : runningCount === totalCount
              ? "All running"
              : runningCount === 0
              ? "Stopped"
              : `${runningCount}/${totalCount} running`;
          const summaryLabel = totalCount === 1 ? "1 process" : `${totalCount} processes`;
          const displayName = name === "FreeSpaceManager" ? "Free Space Manager" : name;
          const uniqueKinds = Array.from(new Set(items.map((item) => item.kind)));
          const filteredKinds = uniqueKinds.filter((kind) => {
            const lower = kind.toLowerCase();
            return lower !== "search" && lower !== "torrent";
          });
          const formatKind = (kind: string) =>
            kind ? kind.charAt(0).toUpperCase() + kind.slice(1) : kind;

          return (
            <div className="process-card" key={name}>
              <div className="process-card__header">
                <div className="process-card__title">
                  <div className="process-card__name">{displayName}</div>
                  <div className="process-card__summary">{summaryLabel}</div>
                  {filteredKinds.length ? (
                    <div className="process-card__badges">
                      {filteredKinds.map((kind) => (
                        <span key={`${name}:${kind}:badge`} className="process-card__badge">
                          {formatKind(kind)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <div className={statusClass.join(" ")} title={statusLabel} />
              </div>
              <div className="process-card__list">
                {items.map((item) => (
                  <div className="process-chip" key={`${item.category}:${item.kind}`}>
                    <div className="process-chip__top">
                      <div className="process-chip__name">{formatKind(item.kind)}</div>
                      <div className={`status-pill__dot ${item.alive ? "text-success" : "text-danger"}`} />
                    </div>
                    <div className="process-chip__detail">
                      {(() => {
                        if (item.rebuilding) {
                          return "Rebuilding";
                        }
                        const kindLower = item.kind.toLowerCase();
                        if (kindLower === "search") {
                          const summary = item.searchSummary ?? "";
                          return summary || "No searches recorded";
                        }
                        if (kindLower === "category") {
                          const count =
                            typeof item.categoryCount === "number" ? item.categoryCount : null;
                          return count !== null
                            ? `Managing ${count} ${count === 1 ? "category" : "categories"}`
                            : "Category manager";
                        }
                        if (kindLower === "torrent") {
                          const metricType = item.metricType?.toLowerCase();
                          const categoryTotal =
                            typeof item.categoryCount === "number" ? item.categoryCount : null;
                          const queueTotal =
                            typeof item.queueCount === "number" ? item.queueCount : null;

                          if (!metricType) {
                            const queueLabel = queueTotal !== null ? queueTotal : "?";
                            const categoryLabel = categoryTotal !== null ? categoryTotal : "?";
                            return `Torrents in queue ${queueLabel} / total ${categoryLabel}`;
                          }

                          if (metricType === "category" && categoryTotal !== null) {
                            return `Torrent count ${categoryTotal}`;
                          }

                          if (metricType === "free-space" && queueTotal !== null) {
                            return `Torrent count ${queueTotal}`;
                          }

                          return "Torrent count unavailable";
                        }
                        return "";
                      })()}
                    </div>
                    <div className="process-chip__actions">
                      <button
                        className="btn small"
                        onClick={() => handleRestart(item.category, item.kind)}
                      >
                        Restart
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="process-card__footer">
                <button
                  className="btn small"
                  onClick={() => void handleRestartGroup(items)}
                >
                  Restart All
                </button>
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
              <button className="btn ghost" onClick={() => void load()} disabled={loading}>
                {loading && <span className="spinner" />}
                <IconImage src={RefreshIcon} />
                {loading ? 'Refreshing...' : 'Refresh'}
              </button>
              <button className="btn" onClick={() => void handleRestartAll()} disabled={restartingAll}>
                {restartingAll && <span className="spinner" />}
                <IconImage src={RestartIcon} />
                {restartingAll ? 'Restarting...' : 'Restart All'}
              </button>
              <button className="btn" onClick={() => void handleRebuildArrs()} disabled={rebuildingArrs}>
                {rebuildingArrs && <span className="spinner" />}
                <IconImage src={ToolsIcon} />
                {rebuildingArrs ? 'Rebuilding...' : 'Rebuild Arrs'}
              </button>
            </div>
          </div>
          {cardsByApp.length ? (
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
          danger={true}
          onConfirm={confirmAction.onConfirm}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </>
  );
}
