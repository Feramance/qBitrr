import React, { useEffect, useState, type JSX } from "react";
import ReactMarkdown from "react-markdown";
import type { MetaResponse } from "../api/types";
import { webPath } from "../api/urlBase";
import { IconImage } from "./IconImage";
import CloseIcon from "../icons/close.svg";
import ExternalIcon from "../icons/github.svg";
import UpdateIcon from "../icons/up-arrow.svg";
import DownloadIcon from "../icons/download.svg";

export function formatVersionLabel(value: string | null | undefined): string {
  if (!value) {
    return "unknown";
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return "unknown";
  }
  return trimmed[0] === "v" || trimmed[0] === "V" ? trimmed : `v${trimmed}`;
}

export type ChangelogModalVariant = "welcome" | "upToDate" | "updateAvailable";

export interface ChangelogModalProps {
  readonly variant: ChangelogModalVariant;
  readonly currentVersion: string;
  readonly latestVersion?: string | null;
  readonly changelog: string | null;
  readonly changelogUrl: string | null;
  readonly repositoryUrl: string;
  readonly updateState?: MetaResponse["update_state"] | null;
  readonly updating?: boolean;
  readonly installationType?: MetaResponse["installation_type"];
  readonly binaryDownloadUrl?: string | null;
  readonly binaryDownloadName?: string | null;
  readonly binaryDownloadSize?: number | null;
  readonly binaryDownloadError?: string | null;
  readonly onClose: () => void;
  readonly onUpdate?: () => void;
}

function changelogGithubLinkLabel(variant: ChangelogModalVariant): string {
  return variant === "welcome" ? "View Full Release on GitHub" : "View on GitHub";
}

function changelogPrimaryLabel(variant: ChangelogModalVariant): string {
  return variant === "welcome" ? "Got it!" : "Got it";
}

function changelogTitle(
  variant: ChangelogModalVariant,
  currentVersion: string,
  updateInProgress: boolean,
): { readonly id: string; readonly text: string } {
  switch (variant) {
    case "welcome":
      return {
        id: "welcome-title",
        text: `🎉 Welcome to qBitrr ${formatVersionLabel(currentVersion)}!`,
      };
    case "upToDate":
      return { id: "already-up-to-date-title", text: "✓ You're on the latest version" };
    case "updateAvailable":
      return {
        id: "changelog-title",
        text: updateInProgress ? "⚙️ Updating..." : "🚀 Update Available",
      };
  }
}

/** Unified changelog modal shell (welcome, up-to-date, and update-available variants). */
export function ChangelogModal({
  variant,
  currentVersion,
  latestVersion = null,
  changelog,
  changelogUrl,
  repositoryUrl,
  updateState,
  updating = false,
  installationType,
  binaryDownloadUrl = null,
  binaryDownloadName = null,
  binaryDownloadSize = null,
  binaryDownloadError = null,
  onClose,
  onUpdate,
}: ChangelogModalProps): JSX.Element {
  const [countdown, setCountdown] = useState<number | null>(null);
  const updateInProgress = Boolean(updateState?.in_progress);
  const updateDisabled = updating || updateInProgress;
  const completedLabel = updateState?.completed_at
    ? new Date(updateState.completed_at).toLocaleString()
    : null;
  const isBinaryInstall = installationType === "binary";
  const title = changelogTitle(variant, currentVersion, updateInProgress);
  const changelogText = changelog?.trim() ?? "";
  const showReleaseNotes =
    variant === "welcome" ||
    (variant === "upToDate" && Boolean(changelogText)) ||
    variant === "updateAvailable";

  useEffect(() => {
    if (variant !== "updateAvailable") {
      return;
    }
    const isSuccess = updateState?.last_result === "success" && updateState?.completed_at;
    if (!isSuccess) {
      const timeout = setTimeout(() => setCountdown(null), 0);
      return () => clearTimeout(timeout);
    }
    const countdownRef = { current: 11 };
    const timer = setInterval(() => {
      countdownRef.current -= 1;
      if (countdownRef.current <= 0) {
        clearInterval(timer);
        window.location.reload();
      } else {
        setCountdown(countdownRef.current);
      }
    }, 1000);
    const initTimeout = setTimeout(() => setCountdown(10), 0);
    return () => {
      clearInterval(timer);
      clearTimeout(initTimeout);
    };
  }, [variant, updateState?.last_result, updateState?.completed_at]);

  let statusClass = "";
  let statusMessage: string | null = null;
  if (variant === "updateAvailable") {
    if (updateInProgress) {
      statusClass = "text-info";
      statusMessage = "⏳ Update in progress...";
    } else if (updateState?.last_result === "success") {
      statusClass = "text-success";
      statusMessage =
        countdown !== null
          ? `✓ Update completed! Reloading in ${countdown}s...`
          : completedLabel
            ? `✓ Update completed successfully (${completedLabel})`
            : "✓ Update completed successfully";
    } else if (updateState?.last_result === "error") {
      statusClass = "text-danger";
      const detail = updateState.last_error ? updateState.last_error.trim() : "";
      statusMessage = detail ? `✗ Update failed: ${detail}` : "✗ Update failed";
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={title.id}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id={title.id}>{title.text}</h2>
          {variant !== "welcome" ? (
            <button
              className="btn ghost"
              type="button"
              onClick={onClose}
              disabled={variant === "updateAvailable" ? updateInProgress : false}
            >
              <IconImage src={CloseIcon} />
              Close
            </button>
          ) : null}
        </div>
        <div className="modal-body changelog-modal__body">
          <div className="changelog-meta">
            {variant === "updateAvailable" ? (
              <>
                <div className="version-comparison">
                  <span className="version-item">
                    <strong>Current:</strong>{" "}
                    <span className="version-badge version-current">
                      {formatVersionLabel(currentVersion)}
                    </span>
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
                  <div className={`update-status ${statusClass}`}>{statusMessage}</div>
                ) : null}
              </>
            ) : variant === "welcome" ? (
              <p style={{ marginBottom: "1rem", color: "var(--text-secondary)" }}>
                You&apos;ve been updated to version{" "}
                <strong>{formatVersionLabel(currentVersion)}</strong>. Here&apos;s what&apos;s
                new in this release:
              </p>
            ) : (
              <p style={{ marginBottom: "1rem", color: "var(--text-secondary)" }}>
                Current version: <strong>{formatVersionLabel(currentVersion)}</strong>
              </p>
            )}
          </div>
          {showReleaseNotes ? (
            <div className="changelog-section">
              <h3>{variant === "updateAvailable" ? "What's New" : "Release Notes"}</h3>
              <div className="changelog-body markdown-content">
                <ReactMarkdown>
                  {changelogText ||
                    (variant === "updateAvailable"
                      ? "No changelog provided."
                      : "No changelog available for this version.")}
                </ReactMarkdown>
              </div>
            </div>
          ) : null}
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
                {changelogGithubLinkLabel(variant)}
              </a>
            )}
          </div>
          <div className="changelog-buttons">
            {variant === "updateAvailable" ? (
              isBinaryInstall ? (
                binaryDownloadError ? (
                  <div className="update-status text-danger" style={{ marginBottom: "0.5rem" }}>
                    {binaryDownloadError}
                  </div>
                ) : binaryDownloadUrl ? (
                  <>
                    <a
                      className="btn primary"
                      href={webPath("/web/download-update")}
                      download={binaryDownloadName ?? undefined}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <IconImage src={DownloadIcon} />
                      Download Update
                      {binaryDownloadSize && binaryDownloadSize > 0 ? (
                        <span
                          style={{ marginLeft: "0.5rem", opacity: 0.8, fontSize: "0.875rem" }}
                        >
                          ({(binaryDownloadSize / (1024 * 1024)).toFixed(1)} MB)
                        </span>
                      ) : null}
                    </a>
                    <div
                      style={{
                        fontSize: "0.875rem",
                        color: "var(--text-secondary)",
                        marginTop: "0.5rem",
                      }}
                    >
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
              )
            ) : (
              <button className="btn primary" type="button" onClick={onClose}>
                {changelogPrimaryLabel(variant)}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
