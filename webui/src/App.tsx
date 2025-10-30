import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import { ProcessesView } from "./pages/ProcessesView";
import { LogsView } from "./pages/LogsView";
import { ArrView } from "./pages/ArrView";
import { ConfigView } from "./pages/ConfigView";
import { ToastProvider, ToastViewport, useToast } from "./context/ToastContext";
import { SearchProvider, useSearch } from "./context/SearchContext";
import { getMeta, getStatus, triggerUpdate } from "./api/client";
import type { MetaResponse } from "./api/types";
import { IconImage } from "./components/IconImage";
import CloseIcon from "./icons/close.svg";
import ExternalIcon from "./icons/github.svg";
import RefreshIcon from "./icons/refresh-arrow.svg";
import UpdateIcon from "./icons/up-arrow.svg";
import ProcessesIcon from "./icons/process.svg";
import LogsIcon from "./icons/log.svg";
import RadarrIcon from "./icons/radarr.svg";
import SonarrIcon from "./icons/sonarr.svg";
import ConfigIcon from "./icons/gear.svg";

type Tab = "processes" | "logs" | "radarr" | "sonarr" | "config";

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

interface ChangelogModalProps {
  currentVersion: string;
  latestVersion: string | null;
  changelog: string | null;
  changelogUrl: string | null;
  repositoryUrl: string;
  updateState: MetaResponse["update_state"] | null | undefined;
  updating: boolean;
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
  onClose,
  onUpdate,
}: ChangelogModalProps): JSX.Element {
  const updateDisabled = updating || Boolean(updateState?.in_progress);
  const completedLabel = updateState?.completed_at
    ? new Date(updateState.completed_at).toLocaleString()
    : null;

  let statusClass = "";
  let statusMessage: string | null = null;
  if (updateState?.in_progress) {
    statusClass = "text-info";
    statusMessage = "Update in progress...";
  } else if (updateState?.last_result === "success") {
    statusClass = "text-success";
    statusMessage = "Update completed successfully";
    if (completedLabel) {
      statusMessage = `${statusMessage} (${completedLabel})`;
    }
  } else if (updateState?.last_result === "error") {
    statusClass = "text-danger";
    const detail = updateState.last_error ? updateState.last_error.trim() : "";
    statusMessage = detail ? `Last update failed: ${detail}` : "Last update failed.";
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
          <h2 id="changelog-title">Update Available</h2>
          <button className="btn ghost" type="button" onClick={onClose}>
            <IconImage src={CloseIcon} />
            Close
          </button>
        </div>
        <div className="modal-body changelog-modal__body">
          <div className="changelog-meta">
            <span>
              <strong>Current:</strong> {formatVersionLabel(currentVersion)}
            </span>
            <span>
              <strong>Latest:</strong> {latestVersion ? formatVersionLabel(latestVersion) : "Unknown"}
            </span>
            {statusMessage ? <span className={statusClass}>{statusMessage}</span> : null}
          </div>
          <pre className="changelog-body">
            {changelog?.trim() ? changelog.trim() : "No changelog provided."}
          </pre>
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
            <button className="btn ghost" type="button" onClick={onClose}>
              <IconImage src={CloseIcon} />
              Close
            </button>
            <button
              className="btn primary"
              type="button"
              onClick={onUpdate}
              disabled={updateDisabled}
            >
              <IconImage src={UpdateIcon} />
              {updateDisabled ? "Updating..." : "Update Now"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AppShell(): JSX.Element {
  const [activeTab, setActiveTab] = useState<Tab>("processes");
  const [configDirty, setConfigDirty] = useState(false);
  const { setValue: setSearchValue } = useSearch();
  const { push } = useToast();
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [metaLoading, setMetaLoading] = useState(false);
  const [showChangelog, setShowChangelog] = useState(false);
  const [updateBusy, setUpdateBusy] = useState(false);
  const prevUpdateResult = useRef<string | null>(null);
  const backendReadyRef = useRef(false);
  const backendWarnedRef = useRef(false);
  const backendTimerRef = useRef<number | null>(null);

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

  useEffect(() => {
    const id = window.setInterval(() => {
      void refreshMeta();
    }, 5 * 60 * 1000);
    return () => window.clearInterval(id);
  }, [refreshMeta]);

  useEffect(() => {
    if (!meta?.update_state?.in_progress) {
      return;
    }
    const id = window.setInterval(() => {
      void refreshMeta({ force: true, silent: true });
    }, 3000);
    return () => window.clearInterval(id);
  }, [meta?.update_state?.in_progress, refreshMeta]);

  useEffect(() => {
    const state = meta?.update_state;
    if (!state) {
      prevUpdateResult.current = null;
      return;
    }
    const result = state.last_result ?? null;
    if (result && result !== prevUpdateResult.current) {
      if (result === "success") {
        push("Update completed successfully. A restart may be required.", "success");
      } else if (result === "error") {
        push(state.last_error || "Update failed.", "error");
      }
    }
    prevUpdateResult.current = result;
  }, [meta?.update_state?.last_result, meta?.update_state?.last_error, push]);

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

  const tabs = useMemo<NavTab[]>(
    () => [
      { id: "processes", label: "Processes", icon: ProcessesIcon },
      { id: "logs", label: "Logs", icon: LogsIcon },
      { id: "radarr", label: "Radarr", icon: RadarrIcon },
      { id: "sonarr", label: "Sonarr", icon: SonarrIcon },
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

  const handleTriggerUpdate = useCallback(async () => {
    setUpdateBusy(true);
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
    <>
      <header className="appbar">
        <div className="appbar__inner">
          <div className="appbar__title">
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
        {activeTab === "processes" && <ProcessesView active />}
        {activeTab === "logs" && <LogsView active />}
        {activeTab === "radarr" && <ArrView type="radarr" active />}
        {activeTab === "sonarr" && <ArrView type="sonarr" active />}
        {activeTab === "config" && <ConfigView onDirtyChange={setConfigDirty} />}
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
          onClose={handleCloseChangelog}
          onUpdate={handleTriggerUpdate}
        />
      ) : null}
    </>
  );
}

export default function App(): JSX.Element {
  return (
    <ToastProvider>
      <SearchProvider>
        <AppShell />
        <ToastViewport />
      </SearchProvider>
    </ToastProvider>
  );
}
