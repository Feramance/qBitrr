import { useCallback, useEffect, useMemo, useRef, useState, type JSX, lazy, Suspense } from "react";
const ProcessesView = lazy(() => import("./pages/ProcessesView").then(module => ({ default: module.ProcessesView })));
const LogsView = lazy(() => import("./pages/LogsView").then(module => ({ default: module.LogsView })));
const ArrView = lazy(() => import("./pages/ArrView").then(module => ({ default: module.ArrView })));
const ConfigView = lazy(() => import("./pages/ConfigView").then(module => ({ default: module.ConfigView })));
import { ToastProvider, ToastViewport, useToast } from "./context/ToastContext";
import { SearchProvider, useSearch } from "./context/SearchContext";
import { WebUIProvider, useWebUI } from "./context/WebUIContext";
import { useNetworkStatus } from "./hooks/useNetworkStatus";
import { getMeta, getStatus, triggerUpdate } from "./api/client";
import type { MetaResponse, StatusResponse } from "./api/types";
import { IconImage } from "./components/IconImage";
import CloseIcon from "./icons/close.svg";
import ExternalIcon from "./icons/github.svg";
import RefreshIcon from "./icons/refresh-arrow.svg";
import UpdateIcon from "./icons/up-arrow.svg";
import DownloadIcon from "./icons/download.svg";
import ProcessesIcon from "./icons/process.svg";
import LogsIcon from "./icons/log.svg";
import RadarrIcon from "./icons/radarr.svg";
import SonarrIcon from "./icons/sonarr.svg";
import LidarrIcon from "./icons/lidarr.svg";
import ConfigIcon from "./icons/gear.svg";
import LogoIcon from "./icons/logo.svg";

type Tab = "processes" | "logs" | "radarr" | "sonarr" | "lidarr" | "config";

interface NavTab {
  id: Tab;
  label: string;
  icon: string;
}

function formatVersionLabel(value: string | null | undefined): string {
  if (!value) {
    return "unknown";
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return "unknown";
  }
  return trimmed[0] === "v" || trimmed[0] === "V" ? trimmed : `v${trimmed}`;
}

interface WelcomeModalProps {
  currentVersion: string;
  changelog: string | null;
  changelogUrl: string | null;
  repositoryUrl: string;
  onClose: () => void;
}

function WelcomeModal({
  currentVersion,
  changelog,
  changelogUrl,
  repositoryUrl,
  onClose,
}: WelcomeModalProps): JSX.Element {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="welcome-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="welcome-title">
            🎉 Welcome to qBitrr {formatVersionLabel(currentVersion)}!
          </h2>
        </div>
        <div className="modal-body changelog-modal__body">
          <div className="changelog-meta">
            <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)' }}>
              You've been updated to version <strong>{formatVersionLabel(currentVersion)}</strong>.
              Here's what's new in this release:
            </p>
          </div>
          <div className="changelog-section">
            <h3>Release Notes</h3>
            <pre className="changelog-body">
              {changelog?.trim() ? changelog.trim() : "No changelog available for this version."}
            </pre>
          </div>
        </div>
        <div className="modal-footer">
          <div className="changelog-links">
            {(changelogUrl || repositoryUrl) && (
              <a
                className="btn ghost small"
                href={changelogUrl ?? repositoryUrl}
                target="_blank"
                rel="noreferrer"
              >
                <IconImage src={ExternalIcon} />
                View Full Release on GitHub
              </a>
            )}
          </div>
          <div className="changelog-buttons">
            <button className="btn primary" type="button" onClick={onClose}>
              Got it!
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

interface ChangelogModalProps {
  currentVersion: string;
  latestVersion: string | null;
  changelog: string | null;
  changelogUrl: string | null;
  repositoryUrl: string;
  updateState: MetaResponse["update_state"] | null | undefined;
  updating: boolean;
  installationType: MetaResponse["installation_type"];
  binaryDownloadUrl: string | null;
  binaryDownloadName: string | null;
  binaryDownloadSize: number | null;
  binaryDownloadError: string | null;
  onClose: () => void;
  onUpdate: () => void;
}

function ChangelogModal({
  currentVersion,
  latestVersion,
  changelog,
  changelogUrl,
  repositoryUrl,
  updateState,
  updating,
  installationType,
  binaryDownloadUrl,
  binaryDownloadName,
  binaryDownloadSize,
  binaryDownloadError,
  onClose,
  onUpdate,
}: ChangelogModalProps): JSX.Element {
  const [countdown, setCountdown] = useState<number | null>(null);
  const updateDisabled = updating || Boolean(updateState?.in_progress);
  const completedLabel = updateState?.completed_at
    ? new Date(updateState.completed_at).toLocaleString()
    : null;
  const isBinaryInstall = installationType === "binary";

  // Start countdown when update completes successfully
  useEffect(() => {
    if (updateState?.last_result === "success" && updateState?.completed_at) {
      let countdown = 10;
      setCountdown(countdown);
      const timer = setInterval(() => {
        countdown -= 1;
        if (countdown <= 0) {
          clearInterval(timer);
          window.location.reload();
        } else {
          setCountdown(countdown);
        }
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [updateState?.last_result, updateState?.completed_at]);

  let statusClass = "";
  let statusMessage: string | null = null;
  if (updateState?.in_progress) {
    statusClass = "text-info";
    statusMessage = "⏳ Update in progress...";
  } else if (updateState?.last_result === "success") {
    statusClass = "text-success";
    if (countdown !== null) {
      statusMessage = `✓ Update completed! Reloading in ${countdown}s...`;
    } else {
      statusMessage = "✓ Update completed successfully";
      if (completedLabel) {
        statusMessage = `${statusMessage} (${completedLabel})`;
      }
    }
  } else if (updateState?.last_result === "error") {
    statusClass = "text-danger";
    const detail = updateState.last_error ? updateState.last_error.trim() : "";
    statusMessage = detail ? `✗ Update failed: ${detail}` : "✗ Update failed";
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="changelog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="changelog-title">
            {updateState?.in_progress ? "⚙️ Updating..." : "🚀 Update Available"}
          </h2>
          <button className="btn ghost" type="button" onClick={onClose} disabled={updateState?.in_progress}>
            <IconImage src={CloseIcon} />
            Close
          </button>
        </div>
        <div className="modal-body changelog-modal__body">
          <div className="changelog-meta">
            <div className="version-comparison">
              <span className="version-item">
                <strong>Current:</strong>{" "}
                <span className="version-badge version-current">{formatVersionLabel(currentVersion)}</span>
              </span>
              <span className="version-arrow">→</span>
              <span className="version-item">
                <strong>Latest:</strong>{" "}
                <span className="version-badge version-latest">
                  {latestVersion ? formatVersionLabel(latestVersion) : "Unknown"}
                </span>
              </span>
            </div>
            {statusMessage ? (
              <div className={`update-status ${statusClass}`}>
                {statusMessage}
              </div>
            ) : null}
          </div>
          <div className="changelog-section">
            <h3>What's New</h3>
            <pre className="changelog-body">
              {changelog?.trim() ? changelog.trim() : "No changelog provided."}
            </pre>
          </div>
        </div>
        <div className="modal-footer">
          <div className="changelog-links">
            {(changelogUrl || repositoryUrl) && (
              <a
                className="btn ghost small"
                href={changelogUrl ?? repositoryUrl}
                target="_blank"
                rel="noreferrer"
              >
                <IconImage src={ExternalIcon} />
                View on GitHub
              </a>
            )}
          </div>
          <div className="changelog-buttons">
            {isBinaryInstall ? (
              binaryDownloadError ? (
                <div className="update-status text-danger" style={{ marginBottom: '0.5rem' }}>
                  {binaryDownloadError}
                </div>
              ) : binaryDownloadUrl ? (
                <>
                  <a
                    className="btn primary"
                    href={`/web/download-update`}
                    download={binaryDownloadName ?? undefined}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <IconImage src={DownloadIcon} />
                    Download Update
                    {binaryDownloadSize && binaryDownloadSize > 0 ? (
                      <span style={{ marginLeft: '0.5rem', opacity: 0.8, fontSize: '0.875rem' }}>
                        ({(binaryDownloadSize / (1024 * 1024)).toFixed(1)} MB)
                      </span>
                    ) : null}
                  </a>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                    Binary installation detected. Download and manually replace the executable.
                  </div>
                </>
              ) : (
                <div className="update-status text-danger">
                  Unable to fetch binary download URL. Please update manually.
                </div>
              )
            ) : (
              <button
                className="btn primary"
                type="button"
                onClick={onUpdate}
                disabled={updateDisabled}
              >
                <IconImage src={UpdateIcon} />
                {updateDisabled ? "Updating..." : "Update Now"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function AppShell(): JSX.Element {
  const [activeTab, setActiveTab] = useState<Tab>("processes");
  const [configDirty, setConfigDirty] = useState(false);
  const { push } = useToast();
  const { setValue: setSearchValue } = useSearch();
  const { viewDensity, setViewDensity } = useWebUI();
  const isOnline = useNetworkStatus();
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [metaLoading, setMetaLoading] = useState(false);
  const [showChangelog, setShowChangelog] = useState(false);
  const [updateBusy, setUpdateBusy] = useState(false);
  const [backendRestarting, setBackendRestarting] = useState(false);
  const restartPollCount = useRef(0);
  const prevUpdateResult = useRef<string | null>(null);
  const backendReadyRef = useRef(false);
  const backendWarnedRef = useRef(false);
  const backendTimerRef = useRef<number | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [statusData, setStatusData] = useState<StatusResponse | null>(null);
  const [showWelcomeChangelog, setShowWelcomeChangelog] = useState(false);

  // Theme is now managed by WebUIContext and applied automatically

  // Clear cache on every page load to ensure fresh content
  useEffect(() => {
    const clearCache = async () => {
      if ('caches' in window) {
        try {
          const cacheNames = await caches.keys();
          await Promise.all(
            cacheNames.map(cacheName => caches.delete(cacheName))
          );
          console.log('Cache cleared on page load');
        } catch (error) {
          console.error('Failed to clear cache:', error);
        }
      }
    };
    clearCache();
  }, []);

  const refreshMeta = useCallback(
    async (options?: { force?: boolean; silent?: boolean }) => {
      const force = options?.force ?? false;
      const silent = options?.silent ?? !force;
      if (!silent) {
        setMetaLoading(true);
      }
      try {
        const data = await getMeta({ force });
        setMeta(data);
      } catch (error) {
        if (!silent) {
          const message =
            error instanceof Error ? error.message : "Failed to fetch version information";
          push(message, "error");
        }
      } finally {
        if (!silent) {
          setMetaLoading(false);
        }
      }
    },
    [push]
  );

  useEffect(() => {
    void refreshMeta({ force: true });
  }, [refreshMeta]);

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
        void refreshMeta({ force: true, silent: true });
      }
      setShowWelcomeChangelog(true);
    }

    // Store current version as last seen when user opens the app (first install)
    if (!lastSeenVersion) {
      localStorage.setItem("lastSeenVersion", currentVersion);
    }
  }, [meta?.current_version, meta?.changelog, refreshMeta]);

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

      // Number keys 1-6 for tab switching
      if (event.key >= '1' && event.key <= '6' && !isMod) {
        event.preventDefault();
        const tabIndex = parseInt(event.key) - 1;
        const tabIds: Tab[] = ['processes', 'logs', 'radarr', 'sonarr', 'lidarr', 'config'];
        if (tabIndex < tabIds.length) {
          setActiveTab(tabIds[tabIndex]);
        }
        return;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [setSearchValue, push]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void refreshMeta();
    }, 5 * 60 * 1000);
    return () => window.clearInterval(id);
  }, [refreshMeta]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        // Force reload all data by incrementing the reload key
        setReloadKey((prev) => prev + 1);
        void refreshMeta({ force: true });
        void refreshStatus();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [refreshMeta]);

  const refreshStatus = useCallback(async () => {
    try {
      const status = await getStatus();
      setStatusData(status);
    } catch {
      // Silently fail - status is not critical
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
    const id = window.setInterval(() => {
      void refreshStatus();
    }, 5 * 1000); // Refresh every 5 seconds for more dynamic tab loading
    return () => window.clearInterval(id);
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
        setBackendRestarting(true);
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
        setStatusData(status);
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

  const tabs = useMemo<NavTab[]>(
    () => [
      { id: "processes", label: "Processes", icon: ProcessesIcon },
      { id: "logs", label: "Logs", icon: LogsIcon },
      { id: "radarr", label: "Radarr", icon: RadarrIcon },
      { id: "sonarr", label: "Sonarr", icon: SonarrIcon },
      { id: "lidarr", label: "Lidarr", icon: LidarrIcon },
      { id: "config", label: "Config", icon: ConfigIcon },
    ],
    []
  );

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
      setActiveTab("processes");
    }
  }, [tabs, activeTab]);

  const handleCheckUpdates = useCallback(() => {
    void refreshMeta({ force: true });
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

  const handleCloseWelcomeChangelog = useCallback(() => {
    setShowWelcomeChangelog(false);
    // Mark this version as seen
    if (meta?.current_version) {
      localStorage.setItem("lastSeenVersion", meta.current_version);
    }
  }, [meta?.current_version]);

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
            <h1>qBitrr</h1>
            <img src={LogoIcon} alt="qBitrr Logo" style={{ width: '32px', height: '32px', marginLeft: '8px' }} />
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
            <button
              type="button"
              className="btn small ghost"
              onClick={handleCheckUpdates}
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
              onClick={() => {
                if (activeTab === "config" && tab.id !== "config" && configDirty) {
                  const shouldLeave = window.confirm(
                    "You have unsaved configuration changes. Leave without saving?"
                  );
                  if (!shouldLeave) {
                    return;
                  }
                }
                setActiveTab(tab.id);
                setSearchValue("");
              }}
            >
              <IconImage src={tab.icon} />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
        <Suspense fallback={<div className="loading">Loading...</div>}>
          {activeTab === "processes" && <ProcessesView key={`processes-${reloadKey}`} active />}
          {activeTab === "logs" && <LogsView key={`logs-${reloadKey}`} active />}
          {activeTab === "radarr" && <ArrView key={`radarr-${reloadKey}`} type="radarr" active />}
          {activeTab === "sonarr" && <ArrView key={`sonarr-${reloadKey}`} type="sonarr" active />}
          {activeTab === "lidarr" && <ArrView key={`lidarr-${reloadKey}`} type="lidarr" active />}
          {activeTab === "config" && <ConfigView key={`config-${reloadKey}`} onDirtyChange={setConfigDirty} />}
        </Suspense>
      </main>
      {showChangelog && meta ? (
        <ChangelogModal
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
        <WelcomeModal
          currentVersion={meta.current_version}
          changelog={meta.current_version_changelog || meta.changelog}
          changelogUrl={changelogUrl}
          repositoryUrl={repositoryUrl}
          onClose={handleCloseWelcomeChangelog}
        />
      ) : null}
    </div>
  );
}

export default function App(): JSX.Element {
  return (
    <ToastProvider>
      <SearchProvider>
        <WebUIProvider>
          <AppShell />
          <ToastViewport />
        </WebUIProvider>
      </SearchProvider>
    </ToastProvider>
  );
}
