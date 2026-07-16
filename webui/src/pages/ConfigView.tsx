import React, { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { produce } from "immer";
import equal from "fast-deep-equal";
import { getConfig, refreshUrlBaseFromMeta, updateConfig } from "../api/client";
import type { ConfigDocument } from "../api/types";
import { useToast } from "../context/ToastContext";
import {
  getCategoryOverlapWarnings,
} from "../config/categoryConfigValidation";
import { IconImage } from "../components/IconImage";
import ConfigureIcon from "../icons/gear.svg";
import AddIcon from "../icons/plus.svg";
import {
  AUTH_SETTINGS_FIELDS,
  SETTINGS_FIELDS,
  WEB_SETTINGS_FIELDS,
} from "./config/configFields";
import {
  buildSectionChanges,
  ensureArrDefaults,
  flatten,
  formatValidationErrors,
  getValue,
  prunePendingRenames,
  sectionKeysFromChanges,
  setValue,
} from "./config/configDocumentUtils";
import {
  validateSectionsForSave,
} from "./config/configValidation";
import {
  QBIT_SECTION_REGEX,
  SERVARR_SECTION_REGEX,
  type FieldDefinition,
} from "./config/configTypes";
import {
  ArrInstanceModal,
  QbitInstanceModal,
  SetPasswordModal,
  SimpleConfigModal,
} from "./config/configModals";
import {
  formatConfigSaveMessage,
  shouldRefreshMetaAfterSave,
  shouldReloadPageAfterSave,
} from "./config/configSaveResult";

interface ConfigViewProps {
  onDirtyChange?: (dirty: boolean) => void;
}

export function ConfigView(props?: ConfigViewProps): JSX.Element {
  const { onDirtyChange } = props ?? {};
  const { push } = useToast();
  const [originalConfig, setOriginalConfig] = useState<ConfigDocument | null>(
    null
  );
  const [formState, setFormState] = useState<ConfigDocument | null>(null);
  const [loading, setLoading] = useState(false);
  const [, setSavingSection] = useState<string | null>(null);
  const [pendingRenames, setPendingRenames] = useState<Map<string, string>>(new Map());

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const config = await getConfig();
      setOriginalConfig(config);
      // Deep clone config for form state (immer will handle immutability from here)
      setFormState(config ? JSON.parse(JSON.stringify(config)) : null);
      // Clear pending renames when config is loaded
      setPendingRenames(new Map());
    } catch (error) {
      push(
        error instanceof Error
          ? error.message
          : "Failed to load configuration",
        "error"
      );
    } finally {
      setLoading(false);
    }
  }, [push]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void loadConfig();
    }, 0);
    return () => window.clearTimeout(id);
  }, [loadConfig]);

  const handleFieldChange = useCallback(
    (path: string[], def: FieldDefinition, raw: unknown) => {
      if (!formState) return;
      // For tags type, handle arrays directly without parsing
      const parsed =
        def.type === "tags" && Array.isArray(raw)
          ? raw
          : def.parse?.(raw as string | boolean) ??
            (def.type === "number"
              ? (() => { const n = Number(raw); return Number.isFinite(n) ? n : 0; })()
              : def.type === "checkbox"
              ? Boolean(raw)
              : raw);

      setFormState(
        produce(formState, (draft) => {
          setValue(draft, path, parsed);
        })
      );
    },
    [formState]
  );

  const arrSections = useMemo(() => {
    if (!formState) return [] as Array<[string, ConfigDocument]>;
    return Object.entries(formState).filter(([key, value]) =>
      SERVARR_SECTION_REGEX.test(key) && value && typeof value === "object"
    ) as Array<[string, ConfigDocument]>;
  }, [formState]);

  const qbitSections = useMemo(() => {
    if (!formState) return [] as Array<[string, ConfigDocument]>;
    return Object.entries(formState).filter(([key, value]) =>
      QBIT_SECTION_REGEX.test(key) && value && typeof value === "object"
    ) as Array<[string, ConfigDocument]>;
  }, [formState]);
  const categoryOverlapWarnings = useMemo(
    () => getCategoryOverlapWarnings(formState),
    [formState]
  );

  const groupedArrSections = useMemo(() => {
    const groups: Array<{
      label: string;
      type: "radarr" | "sonarr" | "lidarr" | "other";
      items: Array<[string, ConfigDocument]>;
    }> = [];
    const sorted = [...arrSections].sort((a, b) =>
      a[0].localeCompare(b[0], undefined, { numeric: true, sensitivity: "base" })
    );
    const radarr: Array<[string, ConfigDocument]> = [];
    const sonarr: Array<[string, ConfigDocument]> = [];
    const lidarr: Array<[string, ConfigDocument]> = [];
    const others: Array<[string, ConfigDocument]> = [];
    for (const entry of sorted) {
      const [key] = entry;
      const keyLower = key.toLowerCase();
      if (keyLower.startsWith("radarr")) {
        radarr.push(entry);
      } else if (keyLower.startsWith("sonarr")) {
        sonarr.push(entry);
      } else if (keyLower.startsWith("lidarr")) {
        lidarr.push(entry);
      } else {
        others.push(entry);
      }
    }

    groups.push({ label: "Radarr Instances", type: "radarr", items: radarr });
    groups.push({ label: "Sonarr Instances", type: "sonarr", items: sonarr });
    groups.push({ label: "Lidarr Instances", type: "lidarr", items: lidarr });
    if (others.length) {
      groups.push({ label: "Other Instances", type: "other", items: others });
    }
    return groups;
  }, [arrSections]);
  const [activeArrKey, setActiveArrKey] = useState<string | null>(null);
  const [activeQbitKey, setActiveQbitKey] = useState<string | null>(null);
  const [isSettingsOpen, setSettingsOpen] = useState(false);
  const [isWebSettingsOpen, setWebSettingsOpen] = useState(false);
  const [isAuthSettingsOpen, setAuthSettingsOpen] = useState(false);
  const [isSetPasswordOpen, setSetPasswordOpen] = useState(false);
  const [isDirty, setDirty] = useState(false);

  useEffect(() => {
    if (!formState || !originalConfig) {
      const id = window.setTimeout(() => {
        setDirty(false);
      }, 0);
      return () => window.clearTimeout(id);
    }
    const flattenedOriginal = flatten(originalConfig);
    const flattenedCurrent = flatten(formState);

    // Keys that are managed dynamically and should not trigger dirty state
    const liveKeys = new Set([
      "WebUI.LiveArr",
      "WebUI.Theme",
      "WebUI.ViewDensity",
    ]);

    let dirty = false;
    for (const [key, value] of Object.entries(flattenedCurrent)) {
      // Skip live WebUI settings
      if (liveKeys.has(key)) continue;

      const originalValue = flattenedOriginal[key];
      // Use fast-deep-equal for accurate comparison (handles arrays, objects, etc.)
      if (!equal(value, originalValue)) {
        dirty = true;
        break;
      }
    }
    if (!dirty) {
      for (const key of Object.keys(flattenedOriginal)) {
        // Skip live WebUI settings
        if (liveKeys.has(key)) continue;

        if (!(key in flattenedCurrent)) {
          dirty = true;
          break;
        }
      }
    }
    const id = window.setTimeout(() => {
      setDirty(dirty);
    }, 0);
    return () => window.clearTimeout(id);
  }, [formState, originalConfig]);

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  useEffect(() => {
    if (!isDirty) return;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [isDirty]);

  useEffect(() => {
    return () => {
      onDirtyChange?.(false);
    };
  }, [onDirtyChange]);

  useEffect(() => {
    const anyModalOpen = Boolean(activeArrKey || activeQbitKey || isSettingsOpen || isWebSettingsOpen || isAuthSettingsOpen || isSetPasswordOpen);
    if (!anyModalOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        const target = event.target;
        if (
          target instanceof HTMLInputElement ||
          target instanceof HTMLTextAreaElement ||
          target instanceof HTMLSelectElement
        ) {
          return;
        }
        setActiveArrKey(null);
        setActiveQbitKey(null);
        setSettingsOpen(false);
        setWebSettingsOpen(false);
        setAuthSettingsOpen(false);
        setSetPasswordOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    const { style } = document.body;
    const originalOverflow = style.overflow;
    style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      style.overflow = originalOverflow;
    };
  }, [activeArrKey, activeQbitKey, isSettingsOpen, isWebSettingsOpen, isAuthSettingsOpen, isSetPasswordOpen]);

  useEffect(() => {
    if (!activeArrKey) return;
    if (!arrSections.some(([key]) => key === activeArrKey)) {
      const id = window.setTimeout(() => {
        setActiveArrKey(null);
      }, 0);
      return () => window.clearTimeout(id);
    }
  }, [activeArrKey, arrSections]);

  const addArrInstance = useCallback(
    (type: "radarr" | "sonarr" | "lidarr") => {
      if (!formState) return;
      const prefix = type.charAt(0).toUpperCase() + type.slice(1);
      let index = 1;
      let key = `${prefix}-${index}`;
      while (formState[key]) {
        index += 1;
        key = `${prefix}-${index}`;
      }
      const defaults = ensureArrDefaults(type);
      if (defaults && typeof defaults === "object") {
        (defaults as Record<string, unknown>).Name = key;
      }
      setFormState(
        produce(formState, (draft) => {
          draft[key] = defaults;
        })
      );
      // Open modal for immediate configuration
      setActiveArrKey(key);
    },
    [formState]
  );
  const deleteArrInstance = useCallback(
    (key: string) => {
      if (!formState) return;
      const keyLower = key.toLowerCase();
      if (!keyLower.startsWith("radarr") && !keyLower.startsWith("sonarr") && !keyLower.startsWith("lidarr")) {
        return;
      }
      const confirmed = window.confirm(
        `Delete ${key}? This action cannot be undone.`
      );
      if (!confirmed) {
        return;
      }
      if (!(key in formState)) {
        return;
      }
      setFormState(
        produce(formState, (draft) => {
          delete draft[key];
        })
      );
      if (activeArrKey === key) {
        setActiveArrKey(null);
      }
      push(`${key} removed`, "success");
    },
    [formState, activeArrKey, push]
  );

  const addQbitInstance = useCallback(() => {
    if (!formState) return;
    let index = 1;
    let key = `qBit-${index}`;
    while (formState[key]) {
      index += 1;
      key = `qBit-${index}`;
    }
    const defaults: ConfigDocument = {
      Disabled: false,
      Host: "localhost",
      Port: 8080,
      UserName: "",
      Password: "",
      ManagedCategories: [],
      MatchSubcategories: false,
      Trackers: [],
      CategorySeeding: {
        DownloadRateLimitPerTorrent: -1,
        UploadRateLimitPerTorrent: -1,
        MaxUploadRatio: -1,
        MaxSeedingTime: -1,
        RemoveTorrent: -1,
        HitAndRunMode: "disabled",
        MinSeedRatio: 1.0,
        MinSeedingTimeDays: 0,
        HitAndRunMinimumDownloadPercent: 10,
        HitAndRunPartialSeedRatio: 1.0,
        TrackerUpdateBuffer: 0,
        StalledDelay: -1,
        IgnoreTorrentsYoungerThan: 180,
      },
    };
    setFormState(
      produce(formState, (draft) => {
        draft[key] = defaults;
      })
    );
    setActiveQbitKey(key);
  }, [formState]);

  const deleteQbitInstance = useCallback(
    (key: string) => {
      if (!formState) return;
      const confirmed = window.confirm(
        `Remove ${key}? This will remove this qBittorrent instance from the config file.`
      );
      if (!confirmed) {
        return;
      }
      if (!(key in formState)) {
        return;
      }
      setFormState(
        produce(formState, (draft) => {
          delete draft[key];
        })
      );
      if (activeQbitKey === key) {
        setActiveQbitKey(null);
      }
      push(`${key} removed`, "success");
    },
    [formState, activeQbitKey, push]
  );

  const handleRenameSection = useCallback(
    (oldName: string, rawNewName: string) => {
      if (!formState) return;
      const newName = rawNewName.trim();
      if (!newName || newName === oldName) {
        return;
      }
      if (formState[newName]) {
        push(`An instance named "${newName}" already exists`, "error");
        return;
      }
      setFormState(
        produce(formState, (draft) => {
          const section = draft[oldName];
          delete draft[oldName];
          draft[newName] = section;
          if (section && typeof section === "object") {
            (section as Record<string, unknown>).Name = newName;
          }
        })
      );
      // Track this rename to ensure old section is fully deleted on save
      setPendingRenames((prev) => new Map(prev).set(oldName, newName));
      if (activeArrKey === oldName) {
        setActiveArrKey(newName);
      }
    },
    [formState, push, activeArrKey]
  );

  const handleRenameQbitSection = useCallback(
    (oldName: string, rawNewName: string) => {
      if (!formState) return;
      const newName = rawNewName.trim();
      if (!newName || newName === oldName) {
        return;
      }
      if (formState[newName]) {
        push(`An instance named "${newName}" already exists`, "error");
        return;
      }
      setFormState(
        produce(formState, (draft) => {
          const section = draft[oldName];
          delete draft[oldName];
          draft[newName] = section;
        })
      );
      // Track this rename to ensure old section is fully deleted on save
      setPendingRenames((prev) => new Map(prev).set(oldName, newName));
      if (activeQbitKey === oldName) {
        setActiveQbitKey(newName);
      }
    },
    [formState, push, activeQbitKey]
  );

  const applyConfigSaveResult = useCallback(
    async (
      configReloaded: boolean,
      reloadType: string,
      affectedInstances: string[] | undefined,
      savedSectionKeys: Iterable<string> | "all",
      changedKeys: readonly string[] = []
    ) => {
      const message = formatConfigSaveMessage(
        reloadType,
        configReloaded,
        affectedInstances,
        changedKeys
      );
      push(message, "success");

      if (shouldRefreshMetaAfterSave(reloadType, changedKeys)) {
        try {
          await refreshUrlBaseFromMeta();
        } catch {
          // meta refresh failed; config was saved — user can reload manually if needed
        }
      }

      if (shouldReloadPageAfterSave(reloadType, changedKeys)) {
        window.setTimeout(() => window.location.reload(), 500);
      }

      if (configReloaded && "caches" in window) {
        try {
          const cacheNames = await caches.keys();
          await Promise.all(cacheNames.map((cacheName) => caches.delete(cacheName)));
        } catch {
          // cache clear failed, non-critical
        }
      }

      await loadConfig();
      setPendingRenames((prev) => prunePendingRenames(prev, savedSectionKeys));
    },
    [loadConfig, push]
  );

  const saveSection = useCallback(
    async (sectionKey: string): Promise<boolean> => {
      if (!formState) return false;
      setSavingSection(sectionKey);
      try {
        const validationErrors = validateSectionsForSave(
          formState,
          [sectionKey],
          originalConfig,
          false
        );
        if (validationErrors.length) {
          push(formatValidationErrors(validationErrors), "error");
          return false;
        }

        const changes = buildSectionChanges(
          formState,
          originalConfig,
          sectionKey,
          pendingRenames
        );
        if (Object.keys(changes).length === 0) {
          push(`No changes detected for ${sectionKey}`, "info");
          return false;
        }

        const { configReloaded, reloadType, affectedInstances } = await updateConfig({ changes });
        const savedKeys = sectionKeysFromChanges(changes);
        for (const [oldName, newName] of pendingRenames) {
          if (oldName === sectionKey || newName === sectionKey) {
            savedKeys.push(oldName, newName);
          }
        }
        await applyConfigSaveResult(
          configReloaded,
          reloadType,
          affectedInstances,
          savedKeys,
          Object.keys(changes)
        );
        return true;
      } catch (error) {
        push(
          error instanceof Error ? error.message : "Failed to update configuration",
          "error"
        );
        return false;
      } finally {
        setSavingSection(null);
      }
    },
    [formState, originalConfig, pendingRenames, push, applyConfigSaveResult]
  );

  if (loading || !formState) {
    return (
      <section className="card">
        <div className="card-header">Config</div>
        <div className="card-body">
          <div className="loading">
            <span className="spinner" /> Loading configuration…
          </div>
        </div>
      </section>
    );
  }

  return (
    <>
      <section className="card">
        <div className="card-header">Config</div>
        <div className="card-body config-layout">
          <section className="config-arr-group">
            <details className="config-arr-group__details" open>
              <summary>
                <span>Core Configuration</span>
              </summary>
              <div className="config-grid">
                <ConfigSummaryCard
                  title="Settings"
                  description="Core application configuration"
                  onConfigure={() => setSettingsOpen(true)}
                />
                <ConfigSummaryCard
                  title="Web Settings"
                  description="Host, port, and proxy"
                  onConfigure={() => setWebSettingsOpen(true)}
                />
                <ConfigSummaryCard
                  title="Authentication"
                  description="Login, local auth, and OIDC settings"
                  onConfigure={() => setAuthSettingsOpen(true)}
                />
              </div>
            </details>
          </section>
          <section className="config-arr-group">
            <details className="config-arr-group__details" open>
              <summary>
                <span>qBittorrent Instances</span>
                <span className="config-arr-group__count">
                  {qbitSections.length}
                </span>
                <button
                  className="btn small"
                  type="button"
                  onClick={addQbitInstance}
                >
                  <IconImage src={AddIcon} />
                  Add Instance
                </button>
              </summary>
              <div className="config-arr-grid">
                {qbitSections.map(([key, value]) => {
                  const host = getValue(value as ConfigDocument, ["Host"]);
                  const port = getValue(value as ConfigDocument, ["Port"]);
                  const disabled = getValue(value as ConfigDocument, ["Disabled"]);
                  return (
                    <div className="card config-card config-arr-card" key={key}>
                      <div className="card-header">
                        {key}
                      </div>
                      <div className="card-body">
                        <dl className="config-arr-summary">
                          <div className="config-arr-summary__item">
                            <dt>Status</dt>
                            <dd>{disabled ? "Disabled" : "Enabled"}</dd>
                          </div>
                          <div className="config-arr-summary__item">
                            <dt>Host</dt>
                            <dd>{host ? `${String(host)}:${port ?? 8080}` : "-"}</dd>
                          </div>
                        </dl>
                        <div className="config-arr-actions">
                          <button
                            className="btn primary"
                            type="button"
                            onClick={() => setActiveQbitKey(key)}
                          >
                            <IconImage src={ConfigureIcon} />
                            Configure
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </details>
          </section>
          {groupedArrSections.length ? (
            <div className="config-arr-groups">
              {groupedArrSections.map((group) => (
                <section className="config-arr-group" key={group.type}>
                  <details className="config-arr-group__details" open>
                     <summary>
                       <span>{group.label}</span>
                       <span className="config-arr-group__count">
                         {group.items.length}
                       </span>
                        {(group.type === "radarr" || group.type === "sonarr" || group.type === "lidarr") && (
                        <button
                          className="btn small"
                          type="button"
                          onClick={() => addArrInstance(group.type as "radarr" | "sonarr" | "lidarr")}
                        >
                          <IconImage src={AddIcon} />
                          Add Instance
                        </button>
                       )}
                     </summary>
                    <div className="config-arr-grid">
                      {group.items.map(([key, value]) => {
                        const uri = getValue(value as ConfigDocument, ["URI"]);
                        const category = getValue(value as ConfigDocument, ["Category"]);
                        const managed = getValue(value as ConfigDocument, ["Managed"]);
                        return (
                          <div className="card config-card config-arr-card" key={key}>
                            <div className="card-header">{key}</div>
                            <div className="card-body">
                              <dl className="config-arr-summary">
                                <div className="config-arr-summary__item">
                                  <dt>Managed</dt>
                                  <dd>{managed ? "Enabled" : "Disabled"}</dd>
                                </div>
                                <div className="config-arr-summary__item">
                                  <dt>Category</dt>
                                  <dd>{category ? String(category) : "-"}</dd>
                                </div>
                                <div className="config-arr-summary__item">
                                  <dt>URI</dt>
                                  <dd className="config-arr-summary__uri">
                                    {uri ? String(uri) : "-"}
                                  </dd>
                                </div>
                              </dl>
                              <div className="config-arr-actions">
                                <button
                                  className="btn primary"
                                  type="button"
                                  onClick={() => setActiveArrKey(key)}
                                >
                                  <IconImage src={ConfigureIcon} />
                                  Configure
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </details>
                </section>
              ))}
            </div>
          ) : null}
        </div>
      </section>
      {activeArrKey && formState ? (
        <ArrInstanceModal
          keyName={activeArrKey}
          state={(formState[activeArrKey] as ConfigDocument) ?? null}
          onChange={handleFieldChange}
          onRename={handleRenameSection}
          onClose={() => setActiveArrKey(null)}
          onSave={() => saveSection(activeArrKey)}
          onDelete={
            /^(radarr|sonarr|lidarr)/i.test(activeArrKey)
              ? () => deleteArrInstance(activeArrKey)
              : undefined
          }
          overlapWarnings={categoryOverlapWarnings}
        />
      ) : null}
      {isSettingsOpen ? (
        <SimpleConfigModal
          title="Settings"
          fields={SETTINGS_FIELDS}
          state={formState}
          basePath={[]}
          onChange={handleFieldChange}
          onClose={() => setSettingsOpen(false)}
          onSave={() => saveSection("Settings")}
        />
      ) : null}
      {isWebSettingsOpen ? (
        <SimpleConfigModal
          title="Web Settings"
          fields={WEB_SETTINGS_FIELDS}
          state={formState}
          basePath={[]}
          onChange={handleFieldChange}
          onClose={() => setWebSettingsOpen(false)}
          onSave={() => saveSection("WebUI")}
          showLiveSettings={true}
        />
      ) : null}
      {isAuthSettingsOpen ? (
        <SimpleConfigModal
          title="Authentication"
          fields={AUTH_SETTINGS_FIELDS}
          state={formState}
          basePath={[]}
          onChange={handleFieldChange}
          onClose={() => setAuthSettingsOpen(false)}
          onSave={() => saveSection("WebUI")}
          onSetPassword={() => setSetPasswordOpen(true)}
        />
      ) : null}
      {isSetPasswordOpen ? (
        <SetPasswordModal onClose={() => setSetPasswordOpen(false)} />
      ) : null}
      {activeQbitKey && formState ? (
        <QbitInstanceModal
          keyName={activeQbitKey}
          state={(formState[activeQbitKey] as ConfigDocument) ?? null}
          onChange={handleFieldChange}
          onRename={handleRenameQbitSection}
          onClose={() => setActiveQbitKey(null)}
          onSave={() => saveSection(activeQbitKey)}
          onDelete={() => deleteQbitInstance(activeQbitKey)}
          overlapWarnings={categoryOverlapWarnings}
        />
      ) : null}
    </>
  );
}

interface ConfigSummaryCardProps {
  title: string;
  description: string;
  onConfigure: () => void;
}

function ConfigSummaryCard({
  title,
  description,
  onConfigure,
}: ConfigSummaryCardProps): JSX.Element {
  return (
    <div className="card config-card">
      <div className="card-header">{title}</div>
      <div className="card-body config-summary-card">
        <p>{description}</p>
        <div className="config-arr-actions">
          <button className="btn primary" type="button" onClick={onConfigure}>
            <IconImage src={ConfigureIcon} />
            Configure
          </button>
        </div>
      </div>
    </div>
  );
}
