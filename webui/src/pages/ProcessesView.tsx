import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import {
  getProcesses,
  rebuildArrs,
  restartAllProcesses,
  restartProcess,
} from "../api/client";
import type { ProcessInfo } from "../api/types";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";
import { IconImage } from "../components/IconImage";
import RefreshIcon from "../icons/ddns-updater.svg";
import RestartIcon from "../icons/resiliosync.svg";
import ToolsIcon from "../icons/immich-power-tools.svg";

const RELEASE_TOKEN_REGEX =
  /\b(480p|576p|720p|1080p|2160p|4k|8k|web[-_. ]?(?:dl|rip)|hdrip|hdtv|bluray|bd(?:rip)?|brrip|webrip|remux|x264|x265|hevc|dts|truehd|atmos|proper|repack|dvdrip|hdr|amzn|nf)\b/i;
const EPISODE_TOKEN_REGEX = /\bS\d{1,3}E\d{1,3}\b/i;
const SEASON_TOKEN_REGEX = /\bSeason\s+\d+\b/i;

function sanitizeSearchSummary(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";
  if (/^\d+\s+queued item/i.test(trimmed)) return "";
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

function getRefreshDelay(active: boolean, processes: ProcessInfo[]): number | null {
  if (!active) return null;
  const hasActiveSearch = processes.some(
    (proc) => proc.alive && proc.kind.toLowerCase() === "search"
  );
  if (hasActiveSearch) return 5000;
  const hasQueueActivity = processes.some(
    (proc) =>
      typeof proc.queueCount === "number" && proc.queueCount > 0
  );
  if (hasQueueActivity) return 10000;
  return 20000;
}

interface ProcessesViewProps {
  active: boolean;
}

export function ProcessesView({ active }: ProcessesViewProps): JSX.Element {
  const [processes, setProcesses] = useState<ProcessInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const { push } = useToast();
  const isFetching = useRef(false);

  const load = useCallback(async () => {
    if (isFetching.current) {
      return;
    }
    isFetching.current = true;
    setLoading((prev) => (prev ? prev : true));
    try {
      const data = await getProcesses();
      const next = (data.processes ?? []).map((process) => {
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
    } catch (error) {
      push(
        error instanceof Error
          ? error.message
          : "Failed to load processes list",
        "error"
      );
    } finally {
      isFetching.current = false;
      setLoading(false);
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
    () => getRefreshDelay(active, processes),
    [active, processes]
  );

  useInterval(() => {
    void load();
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
    try {
      await restartAllProcesses();
      push("Restarted all processes", "success");
      void load();
    } catch (error) {
      push(
        error instanceof Error ? error.message : "Failed to restart all",
        "error"
      );
    }
  }, [load, push]);

  const handleRebuildArrs = useCallback(async () => {
    try {
      await rebuildArrs();
      push("Requested Arr rebuild", "success");
      void load();
    } catch (error) {
      push(
        error instanceof Error ? error.message : "Failed to rebuild Arrs",
        "error"
      );
    }
  }, [load, push]);

  const groupedProcesses = useMemo(() => {
    type InstanceGroup = { name: string; items: ProcessInfo[] };
    type AppGroup = { app: string; instances: InstanceGroup[] };

    const appBuckets = new Map<string, Map<string, ProcessInfo[]>>();

    const classifyApp = (proc: ProcessInfo): string => {
      const category = (proc.category ?? "").toLowerCase();
      const name = (proc.name ?? "").toLowerCase();
      if (category.includes("radarr") || name.includes("radarr")) return "Radarr";
      if (category.includes("sonarr") || name.includes("sonarr")) return "Sonarr";
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

    processes.forEach((proc) => {
      const app = classifyApp(proc);
      if (!appBuckets.has(app)) appBuckets.set(app, new Map());
      const instances = appBuckets.get(app)!;
      const instanceKey =
        proc.name || proc.category || `${proc.category}:${proc.kind}`;
      if (!instances.has(instanceKey)) instances.set(instanceKey, []);
      instances.get(instanceKey)!.push(proc);
    });

    const appOrder = ["Radarr", "Sonarr", "qBittorrent", "Other"];

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
  }, [processes]);

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
                        <span
                          className="process-card__badge"
                          key={`${name}:${kind}:badge`}
                        >
                          {formatKind(kind)}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <span
                  className={statusClass.join(" ")}
                  title={statusLabel}
                  aria-label={statusLabel}
                  role="img"
                />
              </div>
              <div className="process-card__list">
                {items.map((item) => (
                  <div className="process-chip" key={`${item.category}:${item.kind}`}>
                    <div className="process-chip__top">
                      <span className="process-chip__name">{formatKind(item.kind)}</span>
                      <span className={item.alive ? "status-pill status-pill--ok" : "status-pill status-pill--bad"}>
                        <span className="status-pill__dot" />
                        {item.alive ? "Running" : "Stopped"}
                      </span>
                    </div>
                    {(() => {
                      const kindLower = item.kind.toLowerCase();
                      if (kindLower === "search") {
                        const summary = item.searchSummary ?? "";
                        let content: JSX.Element | string;
                        if (summary) {
                          content = summary;
                        } else {
                          content = "No searches recorded";
                        }
                        return <div className="process-chip__detail">{content}</div>;
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
                          return (
                            <div className="process-chip__detail">
                              {`Torrents in queue ${queueLabel} / total ${categoryLabel}`}
                            </div>
                          );
                        }

                        if (metricType === "category" && categoryTotal !== null) {
                          return (
                            <div className="process-chip__detail">
                              {`Torrent count ${categoryTotal}`}
                            </div>
                          );
                        }

                        if (metricType === "free-space" && queueTotal !== null) {
                          return (
                            <div className="process-chip__detail">
                              {`Torrent count ${queueTotal}`}
                            </div>
                          );
                        }

                        return <div className="process-chip__detail">Torrent count unavailable</div>;
                      }
                      return null;
                    })()}
                    <div className="process-chip__actions">
                      <button
                        className="btn ghost"
                        onClick={() => handleRestart(item.category, item.kind)}
                      >
                        <IconImage src={RestartIcon} />
                        Restart
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="process-card__footer">
                <button
                  className="btn ghost"
                  onClick={() => void handleRestartGroup(items)}
                >
                  <IconImage src={RestartIcon} />
                  Restart All
                </button>
              </div>
            </div>
          );
        });
        return { app, cards };
      });

  return (
    <section className="card">
      <div className="card-header">Processes</div>
      <div className="card-body stack">
        <div className="row">
          <div className="col inline">
            <button className="btn" onClick={() => void load()} disabled={loading}>
              <IconImage src={RefreshIcon} />
              Refresh
            </button>
            <button className="btn" onClick={() => void handleRestartAll()}>
              <IconImage src={RestartIcon} />
              Restart All
            </button>
            <button className="btn" onClick={() => void handleRebuildArrs()}>
              <IconImage src={ToolsIcon} />
              Rebuild Arrs
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
  );
}
