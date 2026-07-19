import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  startTransition,
  type JSX,
  lazy,
  Suspense,
} from "react";
import { formatVersionLabel } from "./utils/formatVersionLabel";
import { useToast } from "./context/ToastContext";
import { useSearch } from "./context/SearchContext";
import { useWebUI } from "./context/WebUIContext";
import { useNetworkStatus } from "./hooks/useNetworkStatus";
import { getMeta, getStatus, triggerUpdate } from "./api/client";
import { webPath } from "./api/urlBase";
import type { ArrInfo, MetaResponse } from "./api/types";
import { IconImage } from "./components/IconImage";
import ExternalIcon from "./icons/github.svg";
import RefreshIcon from "./icons/refresh-arrow.svg";
import UpdateIcon from "./icons/up-arrow.svg";
import ProcessesIcon from "./icons/process.svg";
import LogsIcon from "./icons/log.svg";
import RadarrIcon from "./icons/radarr.svg";
import SonarrIcon from "./icons/sonarr.svg";
import LidarrIcon from "./icons/lidarr.svg";
import QbitIcon from "./icons/qbittorrent.svg";
import ConfigIcon from "./icons/gear.svg";
import logoUrl from "./assets/logo-64.png";
import { safeClick } from "./utils/safeClick";
import {
  NAVIGATE_TAB_EVENT,
  type NavigateTabDetail,
  type NavigableTab,
} from "./utils/navigateTab";

type Tab = "processes" | "logs" | "radarr" | "sonarr" | "lidarr" | "qbittorrent" | "config";

const loadProcessesView = () =>
  import("./pages/ProcessesView").then((module) => ({ default: module.ProcessesView }));
const loadLogsView = () =>
  import("./pages/LogsView").then((module) => ({ default: module.LogsView }));
const loadArrCatalogView = () =>
  import("./pages/ArrCatalogView").then((module) => ({ default: module.ArrCatalogView }));
const loadQbitCategoriesView = () =>
  import("./pages/QbitCategoriesView").then((module) => ({ default: module.QbitCategoriesView }));
const loadConfigView = () =>
  import("./pages/ConfigView").then((module) => ({ default: module.ConfigView }));

const ProcessesView = lazy(loadProcessesView);
const LogsView = lazy(loadLogsView);
const ArrCatalogView = lazy(loadArrCatalogView);
const QbitCategoriesView = lazy(loadQbitCategoriesView);
const ConfigView = lazy(loadConfigView);
const ChangelogModal = lazy(() =>
  import("./components/ChangelogModal").then((module) => ({ default: module.ChangelogModal }))
);

const TAB_PREFETCHERS: Record<Tab, () => Promise<unknown>> = {
  processes: loadProcessesView,
  logs: loadLogsView,
  radarr: loadArrCatalogView,
  sonarr: loadArrCatalogView,
  lidarr: loadArrCatalogView,
  qbittorrent: loadQbitCategoriesView,
  config: loadConfigView,
};

function prefetchTab(tabId: Tab): void {
  void TAB_PREFETCHERS[tabId]();
}

interface NavTab {
  id: Tab;
  label: string;
  icon: string;
}

function AppShell({
  authRequired,
  onSignOut,
  initialMeta = null,
}: {
  authRequired: boolean;
  onSignOut: () => void;
  initialMeta?: MetaResponse | null;
}): JSX.Element {
  const [activeTab, setActiveTab] = useState<Tab>("processes");
  const [visitedTabs, setVisitedTabs] = useState<ReadonlySet<Tab>>(
    () => new Set<Tab>(["processes"]),
  );
  const [configuredTabs, setConfiguredTabs] = useState<{
    radarr: boolean;
    sonarr: boolean;
    lidarr: boolean;
    qbittorrent: boolean;
  }>({
    radarr: false,
    sonarr: false,
    lidarr: false,
    qbittorrent: false,
  });
  const [configDirty, setConfigDirty] = useState(false);
  const [configKey, setConfigKey] = useState(0);
  const { push } = useToast();
  const { setValue: setSearchValue } = useSearch();

  const markTabVisited = useCallback((tabId: Tab) => {
    setVisitedTabs((prev) => {
      if (prev.has(tabId)) {
        return prev;
      }
      const next = new Set(prev);
      next.add(tabId);
      return next;
    });
  }, []);

  const switchTab = useCallback(
    (tabId: Tab) => {
      if (activeTab === "config" && tabId !== "config" && configDirty) {
        const shouldLeave = window.confirm(
          "You have unsaved configuration changes. Leave without saving?"
        );
        if (!shouldLeave) {
          return;
        }
        // Remount Config so discarded drafts match previous leave-without-saving semantics.
        setConfigKey((prev) => prev + 1);
        setConfigDirty(false);
      }
      startTransition(() => {
        setActiveTab(tabId);
        markTabVisited(tabId);
      });
      setSearchValue("");
    },
    [activeTab, configDirty, markTabVisited, setSearchValue]
  );
  const { viewDensity, setViewDensity, liveArr, setLiveArr } = useWebUI();
  const isOnline = useNetworkStatus();
  const [meta, setMeta] = useState<MetaResponse | null>(initialMeta);
  const [metaLoading, setMetaLoading] = useState(false);
  const [showChangelog, setShowChangelog] = useState(false);
  const [showAlreadyUpToDateModal, setShowAlreadyUpToDateModal] = useState(false);
  const [updateBusy, setUpdateBusy] = useState(false);
  const [backendRestarting, setBackendRestarting] = useState(false);
  const restartPollCount = useRef(0);
  const prevUpdateResult = useRef<string | null>(null);
  const backendReadyRef = useRef(false);
  const backendWarnedRef = useRef(false);
  const backendTimerRef = useRef<number | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [showWelcomeChangelog, setShowWelcomeChangelog] = useState(false);

  // Idle-prefetch lazy route chunks so first visits after cold start are cheaper.
  useEffect(() => {
    const run = () => {
      for (const tabId of Object.keys(TAB_PREFETCHERS) as Tab[]) {
        prefetchTab(tabId);
      }
    };
    if (typeof window.requestIdleCallback === "function") {
      const id = window.requestIdleCallback(run, { timeout: 4000 });
      return () => window.cancelIdleCallback(id);
    }
    const timer = window.setTimeout(run, 2000);
    return () => window.clearTimeout(timer);
  }, []);

  // Theme is now managed by WebUIContext and applied automatically

  const refreshMeta = useCallback(
    async (options?: { force?: boolean; silent?: boolean }): Promise<MetaResponse | null> => {
      const force = options?.force ?? false;
      const silent = options?.silent ?? !force;
      if (!silent) {
        setMetaLoading(true);
      }
      try {
        const data = await getMeta({ force });
        setMeta(data);
        return data;
      } catch (error) {
        if (!silent) {
          const message =
            error instanceof Error ? error.message : "Failed to fetch version information";
          push(message, "error");
        }
        return null;
      } finally {
        if (!silent) {
          setMetaLoading(false);
        }
      }
    },
    [push]
  );

  // Soft-reuse AuthGate meta when present; only fetch if we mounted without it.
  // Reserve force for update UI / visibility — quiet 5-min poll covers freshness.
  useEffect(() => {
    if (initialMeta) {
      return;
    }
    const id = window.setTimeout(() => {
      void refreshMeta({ force: false, silent: true });
    }, 0);
    return () => window.clearTimeout(id);
  }, [initialMeta, refreshMeta]);

  // Check for new version on first launch - show welcome popup with changelog
  useEffect(() => {
    if (!meta?.current_version) {
      return;
    }

    const lastSeenVersion = localStorage.getItem("lastSeenVersion");
    const currentVersion = meta.current_version;

    // Show welcome popup if this is a new version (but not on very first install)
    if (lastSeenVersion && lastSeenVersion !== currentVersion) {
      // Ensure we have changelog data before showing popup
      if (!meta.current_version_changelog && !meta.changelog) {
        window.setTimeout(() => {
          void refreshMeta({ force: true, silent: true });
        }, 0);
      }
      window.setTimeout(() => {
        setShowWelcomeChangelog(true);
      }, 0);
    }

    // Store current version as last seen when user opens the app (first install)
    if (!lastSeenVersion) {
      localStorage.setItem("lastSeenVersion", currentVersion);
    }
  }, [meta?.current_version, meta?.current_version_changelog, meta?.changelog, refreshMeta]);

  // Network status notifications
  useEffect(() => {
    if (!isOnline) {
      push("You are offline. Some features may not work.", "warning");
    }
  }, [isOnline, push]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs
      if (event.target instanceof HTMLInputElement ||
          event.target instanceof HTMLTextAreaElement ||
          event.target instanceof HTMLSelectElement) {
        return;
      }

      const isMod = event.ctrlKey || event.metaKey;

      // Ctrl/Cmd + K - Focus search
      if (isMod && event.key === 'k') {
        event.preventDefault();
        const searchInput = document.querySelector('input[type="text"][placeholder*="Search"]') as HTMLInputElement;
        searchInput?.focus();
        return;
      }

      // ESC - Clear search
      if (event.key === 'Escape') {
        setSearchValue('');
        return;
      }

      // Number keys for visible tab switching
      if (event.key >= "1" && event.key <= "9" && !isMod) {
        event.preventDefault();
        const tabIndex = parseInt(event.key) - 1;
        const tabIds: Tab[] = [
          "processes",
          "logs",
          ...(configuredTabs.radarr ? (["radarr"] as Tab[]) : []),
          ...(configuredTabs.sonarr ? (["sonarr"] as Tab[]) : []),
          ...(configuredTabs.lidarr ? (["lidarr"] as Tab[]) : []),
          ...(configuredTabs.qbittorrent ? (["qbittorrent"] as Tab[]) : []),
          "config",
        ];
        if (tabIndex < tabIds.length) {
          switchTab(tabIds[tabIndex]);
        }
        return;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [setSearchValue, configuredTabs, switchTab]);

  useEffect(() => {
    const onNavigate = (event: Event) => {
      const detail = (event as CustomEvent<NavigateTabDetail>).detail;
      if (!detail?.tab) return;
      const tab = detail.tab as NavigableTab;
      if (
        (tab === "radarr" && !configuredTabs.radarr) ||
        (tab === "sonarr" && !configuredTabs.sonarr) ||
        (tab === "lidarr" && !configuredTabs.lidarr) ||
        (tab === "qbittorrent" && !configuredTabs.qbittorrent)
      ) {
        return;
      }
      switchTab(tab as Tab);
      if (detail.qbitCategory) {
        sessionStorage.setItem("qbitrr:focusQbitCategory", detail.qbitCategory);
      }
    };
    window.addEventListener(NAVIGATE_TAB_EVENT, onNavigate);
    return () => window.removeEventListener(NAVIGATE_TAB_EVENT, onNavigate);
  }, [configuredTabs, switchTab]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void refreshMeta();
    }, 5 * 60 * 1000);
    return () => window.clearInterval(id);
  }, [refreshMeta]);

  const refreshStatus = useCallback(async () => {
    try {
      const status = await getStatus();
      const arrs: ArrInfo[] = Array.isArray(status.arrs) ? status.arrs : [];
      const qbitInstances = status.qbitInstances ?? {};
      const nextTabs = {
        radarr: arrs.some((arr) => arr.type === "radarr"),
        sonarr: arrs.some((arr) => arr.type === "sonarr"),
        lidarr: arrs.some((arr) => arr.type === "lidarr"),
        qbittorrent: Object.keys(qbitInstances).length > 0,
      };
      setConfiguredTabs((prev) =>
        prev.radarr === nextTabs.radarr &&
        prev.sonarr === nextTabs.sonarr &&
        prev.lidarr === nextTabs.lidarr &&
        prev.qbittorrent === nextTabs.qbittorrent
          ? prev
          : nextTabs
      );
    } catch {
      // Silently fail - status is not critical
    }
  }, []);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        // Remount only views that benefit from a hard reset; Arr tabs stay mounted so browse state persists.
        if (
          activeTab === "processes" ||
          activeTab === "logs" ||
          activeTab === "qbittorrent"
        ) {
          setReloadKey((prev) => prev + 1);
        }
        void refreshMeta({ force: true });
        void refreshStatus();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [refreshMeta, refreshStatus, activeTab]);

  useEffect(() => {
    const initialId = window.setTimeout(() => {
      void refreshStatus();
    }, 0);
    const id = window.setInterval(() => {
      void refreshStatus();
    }, 15 * 1000); // Refresh Arr/qBit tab visibility; client TTL covers status overlap
    return () => {
      window.clearTimeout(initialId);
      window.clearInterval(id);
    };
  }, [refreshStatus]);

  useEffect(() => {
    if (!meta?.update_state?.in_progress && !backendRestarting) {
      restartPollCount.current = 0;
      return;
    }
    const id = window.setInterval(async () => {
      try {
        const data = await getMeta({ force: true });
        setMeta(data);
        if (backendRestarting) {
          // Backend came back after restart
          window.location.reload();
        }
        restartPollCount.current = 0;
      } catch {
        restartPollCount.current += 1;
        if (restartPollCount.current > 20) { // 60 seconds
          setBackendRestarting(false);
          restartPollCount.current = 0;
          push("Update completed but backend restart timed out. Please refresh the page manually.", "warning");
          return;
        }
        if (meta?.update_state?.in_progress) {
          // Failed while update in progress, likely restarting
          setBackendRestarting(true);
        }
      }
    }, 3000);
    return () => window.clearInterval(id);
  }, [meta?.update_state?.in_progress, backendRestarting, meta, push]);

  useEffect(() => {
    const state = meta?.update_state;
    if (!state) {
      prevUpdateResult.current = null;
      return;
    }
    const result = state.last_result ?? null;
    if (result && result !== prevUpdateResult.current) {
      if (result === "success") {
        push("Update completed successfully. Restarting...", "success");
        window.setTimeout(() => {
          setBackendRestarting(true);
        }, 0);
        restartPollCount.current = 0;
      } else if (result === "error") {
        push(state.last_error || "Update failed.", "error");
      }
    }
    prevUpdateResult.current = result;
  }, [meta?.update_state, push]);

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    const schedule = (delay: number) => {
      if (backendTimerRef.current !== null) {
        window.clearTimeout(backendTimerRef.current);
      }
      backendTimerRef.current = window.setTimeout(() => {
        void poll();
      }, delay);
    };

    const poll = async () => {
      if (cancelled || backendReadyRef.current) {
        return;
      }
      attempts += 1;
      try {
        const status = await getStatus();
        if (cancelled) {
          return;
        }
        const readyHint =
          status.ready ?? (Array.isArray(status.arrs) && status.arrs.length > 0);
        if (readyHint) {
          backendReadyRef.current = true;
          return;
        }
        if (status.ready === false && attempts >= 3 && !backendWarnedRef.current) {
          backendWarnedRef.current = true;
          push(
            "qBitrr backend is still initialising. Check the logs if this persists.",
            "warning"
          );
        }
      } catch (error) {
        if (!backendWarnedRef.current && attempts >= 3) {
          backendWarnedRef.current = true;
          const detail = error instanceof Error ? error.message : "Unknown backend error";
          push(
            `Unable to confirm qBitrr readiness (${detail}). Please inspect the logs.`,
            "warning"
          );
        }
      } finally {
        if (!cancelled && !backendReadyRef.current) {
          const delay = attempts < 3 ? 3000 : 10000;
          schedule(delay);
        }
      }
    };

    schedule(0);

    return () => {
      cancelled = true;
      if (backendTimerRef.current !== null) {
        window.clearTimeout(backendTimerRef.current);
        backendTimerRef.current = null;
      }
    };
  }, [push]);

  const tabs = useMemo<NavTab[]>(() => {
    const nextTabs: NavTab[] = [
      { id: "processes", label: "Processes", icon: ProcessesIcon },
      { id: "logs", label: "Logs", icon: LogsIcon },
    ];
    if (configuredTabs.radarr) {
      nextTabs.push({ id: "radarr", label: "Radarr", icon: RadarrIcon });
    }
    if (configuredTabs.sonarr) {
      nextTabs.push({ id: "sonarr", label: "Sonarr", icon: SonarrIcon });
    }
    if (configuredTabs.lidarr) {
      nextTabs.push({ id: "lidarr", label: "Lidarr", icon: LidarrIcon });
    }
    if (configuredTabs.qbittorrent) {
      nextTabs.push({ id: "qbittorrent", label: "qBittorrent", icon: QbitIcon });
    }
    nextTabs.push({ id: "config", label: "Config", icon: ConfigIcon });
    return nextTabs;
  }, [configuredTabs]);
  const visibleTabIds = useMemo(() => new Set<Tab>(tabs.map((tab) => tab.id)), [tabs]);

  const repositoryUrl = meta?.repository_url ?? "https://github.com/Feramance/qBitrr";
  const displayVersion = meta?.current_version
    ? formatVersionLabel(meta.current_version)
    : "...";
  const latestVersion = meta?.latest_version ?? null;
  const updateAvailable = Boolean(meta?.update_available);
  const updateState = meta?.update_state;
  const changelogUrl = meta?.changelog_url ?? repositoryUrl;

  const versionTitleParts: string[] = [];
  if (meta?.last_checked) {
    versionTitleParts.push(`Last checked ${new Date(meta.last_checked).toLocaleString()}`);
  }
  if (meta?.error) {
    versionTitleParts.push(`Update check failed: ${meta.error}`);
  }
  const versionTitle = versionTitleParts.length ? versionTitleParts.join(" • ") : undefined;

  // Redirect to processes if active tab is no longer available
  useEffect(() => {
    const tabExists = tabs.some((tab) => tab.id === activeTab);
    if (!tabExists && tabs.length > 0) {
      const id = window.setTimeout(() => {
        startTransition(() => {
          setActiveTab("processes");
          markTabVisited("processes");
        });
      }, 0);
      return () => window.clearTimeout(id);
    }
  }, [tabs, activeTab, markTabVisited]);

  const handleCheckUpdates = useCallback(async () => {
    const data = await refreshMeta({ force: true });
    if (data) {
      if (data.update_available) {
        setShowChangelog(true);
      } else {
        setShowAlreadyUpToDateModal(true);
      }
    }
  }, [refreshMeta]);

  const handleOpenChangelog = useCallback(() => {
    setShowChangelog(true);
    if (!meta?.changelog) {
      void refreshMeta({ force: true, silent: true });
    }
  }, [meta?.changelog, refreshMeta]);

  const handleCloseChangelog = useCallback(() => {
    setShowChangelog(false);
  }, []);

  const handleCloseAlreadyUpToDateModal = useCallback(() => {
    setShowAlreadyUpToDateModal(false);
  }, []);

  const handleCloseWelcomeChangelog = () => {
    setShowWelcomeChangelog(false);
    // Mark this version as seen
    if (meta?.current_version) {
      localStorage.setItem("lastSeenVersion", meta.current_version);
    }
  };

  const handleTriggerUpdate = useCallback(async () => {
    setUpdateBusy(true);
    setBackendRestarting(false);
    restartPollCount.current = 0;
    try {
      await triggerUpdate();
      push("Update started in the background.", "info");
      await refreshMeta({ force: true, silent: true });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to start update";
      push(message, "error");
    } finally {
      setUpdateBusy(false);
    }
  }, [push, refreshMeta]);

  return (
    <div data-density={viewDensity}>
      <header className="appbar">
        <div className="appbar__inner">
          <div className="appbar__title">
            <IconImage src={logoUrl} alt="qBitrr Logo" className="appbar__logo" />
            <h1>qBitrr</h1>
            <span className="appbar__version" title={versionTitle}>
              {displayVersion}
            </span>
            {metaLoading ? <span className="spinner" aria-hidden="true" /> : null}
            {updateState?.in_progress ? (
              <span className="appbar__status text-info">Updating...</span>
            ) : null}
            {updateAvailable ? (
              <button
                type="button"
                className="btn small primary appbar__update"
                onClick={handleOpenChangelog}
                disabled={updateBusy || Boolean(updateState?.in_progress)}
              >
                <span className="appbar__update-indicator" aria-hidden="true" />
                <IconImage src={UpdateIcon} />
                Update available
              </button>
            ) : null}
          </div>
          <div className="appbar__actions">
            {!isOnline && (
              <span className="badge" style={{ background: 'rgba(239, 68, 68, 0.15)', borderColor: 'rgba(239, 68, 68, 0.3)', color: 'var(--danger)' }}>
                Offline
              </span>
            )}
            <div className="view-density-toggle">
              <button
                type="button"
                className={viewDensity === "comfortable" ? "active" : ""}
                onClick={() => setViewDensity("comfortable")}
                title="Comfortable view"
              >
                Comfortable
              </button>
              <button
                type="button"
                className={viewDensity === "compact" ? "active" : ""}
                onClick={() => setViewDensity("compact")}
                title="Compact view"
              >
                Compact
              </button>
            </div>
            <div className="live-switch">
              <span className="live-switch__label" id="live-switch-label">
                Live
              </span>
              <button
                type="button"
                className={`live-switch__control${liveArr ? " live-switch__control--on" : ""}`}
                role="switch"
                aria-checked={liveArr}
                aria-labelledby="live-switch-label"
                title="Live updates for Arr and qBittorrent views"
                aria-label="Live updates for Arr and qBittorrent views"
                onClick={() => setLiveArr(!liveArr)}
              >
                <span className="live-switch__track" aria-hidden="true">
                  <span className="live-switch__thumb" />
                </span>
              </button>
            </div>
            <button
              type="button"
              className="btn small ghost"
              onClick={() => void handleCheckUpdates()}
              disabled={metaLoading}
            >
              <IconImage src={RefreshIcon} />
              {metaLoading ? "Checking..." : "Check Updates"}
            </button>
            <a
              href={repositoryUrl}
              target="_blank"
              rel="noreferrer"
              className="btn small ghost"
            >
              <IconImage src={ExternalIcon} />
              GitHub
            </a>
            <a
              href={webPath("/web/docs")}
              target="_blank"
              rel="noreferrer"
              className="btn small ghost"
              title="Interactive API docs (Swagger UI)"
            >
              <IconImage src={ExternalIcon} />
              OpenAPI
            </a>
            <a
              href="https://feramance.github.io/qBitrr/"
              target="_blank"
              rel="noreferrer"
              className="btn small ghost"
            >
              <IconImage src={ExternalIcon} />
              Docs
            </a>
            {authRequired && (
              <button
                type="button"
                className="btn small ghost"
                onClick={() => void onSignOut()}
              >
                Sign Out
              </button>
            )}
          </div>
        </div>
      </header>
      <main className="container">
        <nav className="nav">
          {tabs.map((tab) => (
            <button
              type="button"
              key={tab.id}
              className={activeTab === tab.id ? "active" : ""}
              onClick={safeClick(() => switchTab(tab.id))}
              onMouseEnter={() => prefetchTab(tab.id)}
              onFocus={() => prefetchTab(tab.id)}
            >
              <IconImage src={tab.icon} />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
        <Suspense fallback={<div className="loading">Loading...</div>}>
          <div className="view-transition">
            {visitedTabs.has("processes") ? (
              <div hidden={activeTab !== "processes"}>
                <ProcessesView
                  key={`processes-${reloadKey}`}
                  active={activeTab === "processes"}
                />
              </div>
            ) : null}
            {visitedTabs.has("logs") ? (
              <div hidden={activeTab !== "logs"}>
                <LogsView key={`logs-${reloadKey}`} active={activeTab === "logs"} />
              </div>
            ) : null}
            {visitedTabs.has("radarr") && visibleTabIds.has("radarr") ? (
              <div hidden={activeTab !== "radarr"}>
                <ArrCatalogView kind="radarr" active={activeTab === "radarr"} />
              </div>
            ) : null}
            {visitedTabs.has("sonarr") && visibleTabIds.has("sonarr") ? (
              <div hidden={activeTab !== "sonarr"}>
                <ArrCatalogView kind="sonarr" active={activeTab === "sonarr"} />
              </div>
            ) : null}
            {visitedTabs.has("lidarr") && visibleTabIds.has("lidarr") ? (
              <div hidden={activeTab !== "lidarr"}>
                <ArrCatalogView kind="lidarr" active={activeTab === "lidarr"} />
              </div>
            ) : null}
            {visitedTabs.has("qbittorrent") && visibleTabIds.has("qbittorrent") ? (
              <div hidden={activeTab !== "qbittorrent"}>
                <QbitCategoriesView
                  key={`qbittorrent-${reloadKey}`}
                  active={activeTab === "qbittorrent"}
                />
              </div>
            ) : null}
            {visitedTabs.has("config") ? (
              <div hidden={activeTab !== "config"}>
                <ConfigView key={`config-${configKey}`} onDirtyChange={setConfigDirty} />
              </div>
            ) : null}
          </div>
        </Suspense>
      </main>
      <Suspense fallback={null}>
        {showChangelog && meta ? (
          <ChangelogModal
            variant="updateAvailable"
            currentVersion={meta.current_version}
            latestVersion={latestVersion}
            changelog={meta.changelog}
            changelogUrl={changelogUrl}
            repositoryUrl={repositoryUrl}
            updateState={updateState}
            updating={updateBusy}
            installationType={meta.installation_type}
            binaryDownloadUrl={meta.binary_download_url}
            binaryDownloadName={meta.binary_download_name}
            binaryDownloadSize={meta.binary_download_size}
            binaryDownloadError={meta.binary_download_error}
            onClose={handleCloseChangelog}
            onUpdate={handleTriggerUpdate}
          />
        ) : null}
        {showWelcomeChangelog && meta ? (
          <ChangelogModal
            variant="welcome"
            currentVersion={meta.current_version}
            changelog={meta.current_version_changelog || meta.changelog}
            changelogUrl={changelogUrl}
            repositoryUrl={repositoryUrl}
            onClose={handleCloseWelcomeChangelog}
          />
        ) : null}
        {showAlreadyUpToDateModal && meta ? (
          <ChangelogModal
            variant="upToDate"
            currentVersion={meta.current_version}
            changelog={meta.current_version_changelog || meta.changelog}
            changelogUrl={changelogUrl}
            repositoryUrl={repositoryUrl}
            onClose={handleCloseAlreadyUpToDateModal}
          />
        ) : null}
      </Suspense>
    </div>
  );
}


export { AppShell };
