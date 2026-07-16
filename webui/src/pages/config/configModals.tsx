import React, { useEffect, useMemo, useState, type JSX } from "react";
import { createPortal } from "react-dom";
import ReactMarkdown from "react-markdown";
import { get } from "lodash-es";
import {
  testArrConnection,
  setPassword as apiSetPassword,
  type TestConnectionResponse,
} from "../../api/client";
import type { ConfigDocument } from "../../api/types";
import { useToast } from "../../context/ToastContext";
import { useWebUI } from "../../context/WebUIContext";
import {
  getQbitTorrentHandlingSummary,
} from "../../config/torrentHandlingSummary";
import { IconImage } from "../../components/IconImage";
import CloseIcon from "../../icons/close.svg";
import DeleteIcon from "../../icons/trash.svg";
import SaveIcon from "../../icons/check-mark.svg";
import RefreshIcon from "../../icons/refresh-arrow.svg";
import { safeClick } from "../../utils/safeClick";
import {
  ARR_TRACKER_FIELDS,
  getArrFieldSets,
  QBIT_FIELDS,
} from "./configFields";
import {
  ArrTorrentSummary,
  CategoryOverlapAlert,
  FieldGroup,
} from "./configFieldComponents";
import { REDACTED_PLACEHOLDER } from "./configTypes";
import type { FieldDefinition } from "./configTypes";

export function ConfigModalPortal({ children }: { children: React.ReactNode }): JSX.Element {
  return createPortal(children, document.body);
}

export interface ArrInstanceModalProps {
  keyName: string;
  state: ConfigDocument | ConfigDocument[keyof ConfigDocument] | null;
  onChange: (path: string[], def: FieldDefinition, value: unknown) => void;
  onRename: (oldName: string, newName: string) => void;
  onClose: () => void;
  onSave: () => Promise<boolean>;
  onDelete?: () => void;
  overlapWarnings: string[];
}

export function ArrInstanceModal({
  keyName,
  state,
  onChange,
  onRename,
  onClose,
  onSave,
  onDelete,
  overlapWarnings,
}: ArrInstanceModalProps): JSX.Element {
  const { generalFields, entryFields, entryOmbiFields, entryOverseerrFields, torrentFields, seedingFields, trackerFields } =
    getArrFieldSets(keyName);
  const { push } = useToast();

  // State for test connection
  const [testState, setTestState] = useState<{
    testing: boolean;
    result: TestConnectionResponse | null;
  }>({ testing: false, result: null });

  const [qualityProfiles, setQualityProfiles] = useState<
    Array<{ id: number; name: string }>
  >([]);
  const [savingModal, setSavingModal] = useState(false);

  // Helper to get value from state
  const getValue = (path: string[]): unknown => {
    if (!state) return undefined;
    // state is already the Arr instance object, not the full ConfigDocument
    return get(state, path);
  };
  const uriValue = getValue(["URI"]) as string;
  const apiKeyValue = getValue(["APIKey"]) as string;

  // Clear test state when URI or APIKey changes
  useEffect(() => {
    const id = window.setTimeout(() => {
      setTestState({ testing: false, result: null });
      setQualityProfiles([]);
    }, 0);
    return () => window.clearTimeout(id);
  }, [uriValue, apiKeyValue]);

  // Auto-test connection when modal opens if credentials exist
  useEffect(() => {
    const uri = uriValue;
    const apiKey = apiKeyValue;

    if (uri && apiKey && !testState.testing && !testState.result) {
      // Auto-test silently (without toasts)
      handleTestConnection(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run on mount

  // Test connection handler
  async function handleTestConnection(silent = false): Promise<boolean> {
    const uri = getValue(["URI"]) as string;
    const apiKey = getValue(["APIKey"]) as string;
    const isApiKeyRedacted = (apiKey ?? "").trim() === REDACTED_PLACEHOLDER;

    // Determine Arr type from keyName
    const keyLower = keyName.toLowerCase();
    const arrType = keyLower.includes("radarr")
      ? "radarr"
      : keyLower.includes("sonarr")
        ? "sonarr"
        : "lidarr";

    if (!isApiKeyRedacted && (!uri || !apiKey)) {
      if (!silent) {
        push("Please configure URI and API Key first", "error");
      }
      return false;
    }

    setTestState({ testing: true, result: null });

    try {
      const result = await testArrConnection(
        isApiKeyRedacted
          ? { arrType, instanceKey: keyName }
          : { arrType, uri: uri ?? "", apiKey: apiKey ?? "" }
      );
      setTestState({ testing: false, result });

      if (result.success) {
        // Cache quality profiles for dropdown use
        if (result.qualityProfiles) {
          setQualityProfiles(result.qualityProfiles);
        }
        if (!silent) {
          push(`Connected to ${keyName} successfully!`, "success");
        }
        return true;
      } else {
        if (!silent) {
          push(`Connection failed: ${result.message}`, "error");
        }
        return false;
      }
    } catch {
      setTestState({ testing: false, result: null });
      if (!silent) {
        push("Test connection failed", "error");
      }
      return false;
    }
  }

  const handleSave = async () => {
    if (savingModal) return;
    setSavingModal(true);
    try {
      const uri = getValue(["URI"]) as string;
      const apiKey = getValue(["APIKey"]) as string;
      const managed = Boolean(getValue(["Managed"]));

      if (managed && uri && apiKey) {
        const success = await handleTestConnection(false);
        if (!success) {
          return;
        }
      }

      const saved = await onSave();
      if (saved) {
        onClose();
      }
    } finally {
      setSavingModal(false);
    }
  };

  return (
    <ConfigModalPortal>
      <div className="modal-backdrop" role="presentation">
        <div
          className="modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="arr-instance-modal-title"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="modal-header">
            <h2 id="arr-instance-modal-title">
              Configure <code>{keyName}</code>
            </h2>
            <button className="btn ghost" type="button" onClick={safeClick(onClose)}>
              <IconImage src={CloseIcon} />
              Close
            </button>
          </div>
        <div className="modal-body">
          <ArrTorrentSummary state={state} />
          <CategoryOverlapAlert messages={overlapWarnings} />
          <FieldGroup
            title={null}
            fields={generalFields}
            state={state}
            basePath={[]}
            onChange={(path, def, value) => onChange([keyName, ...path], def, value)}
            onRenameSection={onRename}
            sectionKey={keyName}
            defaultOpen
          />
          {testState.result && (
            <div
              className={`alert ${testState.result.success ? "success" : "error"}`}
              style={{ margin: "16px 0" }}
            >
              {testState.result.success ? (
                <>
                  <strong>✓ {testState.result.message}</strong>
                  {testState.result.systemInfo && (
                    <div className="alert-details">
                      Version: {testState.result.systemInfo.version}
                      {testState.result.systemInfo.branch &&
                        ` (${testState.result.systemInfo.branch})`}
                    </div>
                  )}
                  {testState.result.qualityProfiles && (
                    <div className="alert-details">
                      Found {testState.result.qualityProfiles.length} quality
                      profile(s)
                    </div>
                  )}
                </>
              ) : (
                <>
                  <strong>⚠️ Connection Failed</strong>
                  <br />
                  {testState.result.message}
                </>
              )}
            </div>
          )}
          <FieldGroup
            title="Entry Search"
            fields={entryFields}
            state={state}
            basePath={[]}
            onChange={(path, def, value) => onChange([keyName, ...path], def, value)}
            sectionKey={keyName}
            defaultOpen
          />
          <FieldGroup
            title="Quality Profile Mappings"
            fields={[]}
            state={state}
            basePath={[]}
            onChange={(path, def, value) => onChange([keyName, ...path], def, value)}
            sectionKey={keyName}
            defaultOpen
            qualityProfiles={qualityProfiles}
          />
          {entryOmbiFields.length > 0 && (
            <FieldGroup
              title="Ombi Integration"
              fields={entryOmbiFields}
              state={state}
              basePath={[]}
              onChange={(path, def, value) => onChange([keyName, ...path], def, value)}
              sectionKey={keyName}
            />
          )}
          {entryOverseerrFields.length > 0 && (
            <FieldGroup
              title="Overseerr Integration"
              fields={entryOverseerrFields}
              state={state}
              basePath={[]}
              onChange={(path, def, value) => onChange([keyName, ...path], def, value)}
              sectionKey={keyName}
            />
          )}
          <FieldGroup
            title="Torrent Handling"
            fields={torrentFields}
            state={state}
            basePath={[]}
            onChange={(path, def, value) => onChange([keyName, ...path], def, value)}
            sectionKey={keyName}
          />
          <FieldGroup
            title="Seeding"
            fields={seedingFields}
            state={state}
            basePath={[]}
            onChange={(path, def, value) => onChange([keyName, ...path], def, value)}
            sectionKey={keyName}
          />
          <FieldGroup
            title="Trackers"
            fields={trackerFields}
            state={state}
            basePath={[]}
            onChange={(path, def, value) => onChange([keyName, ...path], def, value)}
            sectionKey={keyName}
          />
        </div>
        <div className="modal-footer">
          {onDelete && (
            <button
              className="btn danger"
              type="button"
              onClick={safeClick(() => {
                onDelete();
                onClose();
              })}
            >
              <IconImage src={DeleteIcon} />
              Delete
            </button>
          )}
          <button
            className="btn secondary"
            type="button"
            onClick={() => handleTestConnection(false)}
            disabled={testState.testing}
          >
            {testState.testing ? (
              <>
                <IconImage src={RefreshIcon} />
                Testing...
              </>
            ) : (
              "Test"
            )}
          </button>
          <button
            className="btn primary"
            type="button"
            onClick={() => void handleSave()}
            disabled={savingModal || testState.testing}
          >
            <IconImage src={SaveIcon} />
            {savingModal ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
    </ConfigModalPortal>
  );
}

export function QbitTorrentSummary({
  state,
}: {
  state: ConfigDocument | ConfigDocument[keyof ConfigDocument] | null;
}): JSX.Element {
  const summary = useMemo(
    () => getQbitTorrentHandlingSummary(state as ConfigDocument | null),
    [state]
  );
  return (
    <div className="torrent-handling-summary" aria-live="polite">
      <h3>How torrents are handled</h3>
      <div className="torrent-handling-summary-body markdown-content">
        <ReactMarkdown>{summary}</ReactMarkdown>
      </div>
    </div>
  );
}

export interface QbitInstanceModalProps {
  keyName: string;
  state: ConfigDocument | ConfigDocument[keyof ConfigDocument] | null;
  onChange: (path: string[], def: FieldDefinition, value: unknown) => void;
  onRename: (oldName: string, newName: string) => void;
  onClose: () => void;
  onSave: () => Promise<boolean>;
  onDelete?: () => void;
  overlapWarnings: string[];
}

export function QbitInstanceModal({
  keyName,
  state,
  onChange,
  onRename,
  onClose,
  onSave,
  onDelete,
  overlapWarnings,
}: QbitInstanceModalProps): JSX.Element {
  const [savingModal, setSavingModal] = useState(false);

  const handleDone = async () => {
    if (savingModal) return;
    setSavingModal(true);
    try {
      const saved = await onSave();
      if (saved) {
        onClose();
      }
    } finally {
      setSavingModal(false);
    }
  };

  return (
    <ConfigModalPortal>
      <div className="modal-backdrop" role="presentation">
        <div
          className="modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="qbit-instance-modal-title"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="modal-header">
            <h2 id="qbit-instance-modal-title">
              Configure <code>{keyName}</code>
            </h2>
            <button className="btn ghost" type="button" onClick={safeClick(onClose)}>
              <IconImage src={CloseIcon} />
              Close
            </button>
          </div>
        <div className="modal-body">
          <QbitTorrentSummary state={state} />
          <CategoryOverlapAlert messages={overlapWarnings} />
          <FieldGroup
            title={null}
            fields={QBIT_FIELDS}
            state={state}
            basePath={[]}
            onChange={(path, def, value) => onChange([keyName, ...path], def, value)}
            onRenameSection={onRename}
            sectionKey={keyName}
            defaultOpen
          />
          <FieldGroup
            title="Trackers"
            fields={ARR_TRACKER_FIELDS}
            state={state}
            basePath={[]}
            onChange={(path, def, value) => onChange([keyName, ...path], def, value)}
            defaultOpen={false}
            qbitTrackers
          />
        </div>
        <div className="modal-footer">
          {onDelete && (
            <button
              className="btn danger"
              type="button"
              onClick={safeClick(() => {
                onDelete();
                onClose();
              })}
            >
              <IconImage src={DeleteIcon} />
              Delete
            </button>
          )}
          <button
            className="btn primary"
            type="button"
            onClick={() => void handleDone()}
            disabled={savingModal}
          >
            <IconImage src={SaveIcon} />
            {savingModal ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
    </ConfigModalPortal>
  );
}

export interface SimpleConfigModalProps {
  title: string;
  fields: FieldDefinition[];
  state: ConfigDocument | null;
  basePath: string[];
  onChange: (path: string[], def: FieldDefinition, value: unknown) => void;
  onClose: () => void;
  onSave?: () => Promise<boolean>;
  showLiveSettings?: boolean;
  onSetPassword?: () => void;
}

export function SimpleConfigModal({
  title,
  fields,
  state,
  basePath,
  onChange,
  onClose,
  onSave,
  showLiveSettings = false,
  onSetPassword,
}: SimpleConfigModalProps): JSX.Element | null {
  const webUI = useWebUI();
  const [savingModal, setSavingModal] = useState(false);

  const handleSave = async () => {
    if (!onSave || savingModal) return;
    setSavingModal(true);
    try {
      const saved = await onSave();
      if (saved) {
        onClose();
      }
    } finally {
      setSavingModal(false);
    }
  };

  if (!state) return null;
  return (
    <ConfigModalPortal>
      <div className="modal-backdrop" role="presentation">
        <div
          className="modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby={`${title}-modal-title`}
          onClick={(event) => event.stopPropagation()}
        >
          <div className="modal-header">
            <h2 id={`${title}-modal-title`}>{title}</h2>
            <button className="btn ghost" type="button" onClick={safeClick(onClose)}>
              <IconImage src={CloseIcon} />
              Close
            </button>
          </div>
        <div className="modal-body">
          <FieldGroup
            title={null}
            fields={fields}
            state={state}
            basePath={basePath}
            onChange={onChange}
            defaultOpen
          />
          {showLiveSettings && webUI && (
            <div className="field-group">
              <h3 className="field-group-title">Live Settings</h3>
              <div className="field-group-content">
                <div className="field">
                  <label>
                    <input
                      type="checkbox"
                      checked={webUI.liveArr}
                      onChange={(e) => webUI.setLiveArr(e.target.checked)}
                    />
                    {" "}Live Arr Updates
                  </label>
                  <p className="field-description">Enable real-time updates for Arr views</p>
                </div>
                <div className="field">
                  <label>Theme</label>
                  <select
                    value={webUI.theme}
                    onChange={(e) => webUI.setTheme(e.target.value as "light" | "dark")}
                  >
                    <option value="dark">Dark</option>
                    <option value="light">Light</option>
                  </select>
                  <p className="field-description">WebUI theme (Light or Dark)</p>
                </div>
              </div>
            </div>
          )}
          {onSetPassword && (
            <div className="field-group">
              <h3 className="field-group-title">Password Management</h3>
              <div className="field-group-content">
                <div className="field">
                  <p className="field-description">
                    Set or change the login password for local auth. The password hash is stored
                    securely in config and never exposed via the API.
                  </p>
                  <button className="btn primary" type="button" onClick={onSetPassword}>
                    Set Password
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
        <div className="modal-footer">
          {onSave ? (
            <button
              className="btn primary"
              type="button"
              onClick={() => void handleSave()}
              disabled={savingModal}
            >
              <IconImage src={SaveIcon} />
              {savingModal ? "Saving..." : "Save"}
            </button>
          ) : (
            <button className="btn primary" type="button" onClick={safeClick(onClose)}>
              <IconImage src={SaveIcon} />
              Done
            </button>
          )}
        </div>
      </div>
    </div>
    </ConfigModalPortal>
  );
}

export interface SetPasswordModalProps {
  onClose: () => void;
}

export function SetPasswordModal({ onClose }: SetPasswordModalProps): JSX.Element {
  const [username, setUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [setupToken, setSetupToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const { push } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!username.trim()) {
      setError("Username is required.");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await apiSetPassword({ username: username.trim(), password: newPassword, setupToken: setupToken || undefined });
      setSuccess(true);
      push("Password set successfully.", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to set password.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ConfigModalPortal>
      <div className="modal-backdrop" role="presentation">
        <div
          className="modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="set-password-modal-title"
          onClick={(e) => e.stopPropagation()}
          style={{ maxWidth: 480 }}
        >
          <div className="modal-header">
            <h2 id="set-password-modal-title">Set Password</h2>
            <button className="btn ghost" type="button" onClick={safeClick(onClose)}>
              <IconImage src={CloseIcon} />
              Close
            </button>
          </div>
        <div className="modal-body">
          {success ? (
            <div style={{ padding: "1rem 0", color: "var(--success)" }}>
              Password set successfully. Auth is now enabled with local login.
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <div className="field">
                <label htmlFor="sp-username">Username</label>
                <input
                  id="sp-username"
                  type="text"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="sp-password">New Password</label>
                <input
                  id="sp-password"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  minLength={8}
                  required
                />
                <p className="field-description">Minimum 8 characters.</p>
              </div>
              <div className="field">
                <label htmlFor="sp-confirm">Confirm Password</label>
                <input
                  id="sp-confirm"
                  type="password"
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor="sp-setup-token">Setup Token (optional for signed-in users)</label>
                <input
                  id="sp-setup-token"
                  type="password"
                  autoComplete="off"
                  value={setupToken}
                  onChange={(e) => setSetupToken(e.target.value)}
                  placeholder="QBITRR_SETUP_TOKEN or WebUI.Token"
                />
                <p className="field-description">
                  Signed-in users can change the password without this field. Otherwise provide{" "}
                  <code>QBITRR_SETUP_TOKEN</code> or the <code>WebUI.Token</code> value from{" "}
                  config.toml.
                </p>
              </div>
              {error && <div style={{ color: "var(--danger)", fontSize: "0.875rem" }}>{error}</div>}
              <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                <button
                  className="btn ghost"
                  type="button"
                  onClick={safeClick(onClose)}
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button className="btn primary" type="submit" disabled={submitting}>
                  {submitting ? "Setting…" : "Set Password"}
                </button>
              </div>
            </form>
          )}
        </div>
        {success && (
          <div className="modal-footer">
            <button className="btn primary" type="button" onClick={safeClick(onClose)}>
              Close
            </button>
          </div>
        )}
      </div>
    </div>
    </ConfigModalPortal>
  );
}
