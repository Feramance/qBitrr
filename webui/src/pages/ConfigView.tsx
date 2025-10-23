import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { getConfig, updateConfig } from "../api/client";
import type { ConfigDocument } from "../api/types";
import { useToast } from "../context/ToastContext";

type FieldType = "text" | "number" | "checkbox" | "password" | "select";

interface FieldDefinition {
  label: string;
  path: string[];
  type: FieldType;
  options?: string[];
  placeholder?: string;
  parse?: (value: string | boolean) => unknown;
  format?: (value: unknown) => string | boolean;
}

const SETTINGS_FIELDS: FieldDefinition[] = [
  {
    label: "Console Level",
    path: ["Settings", "ConsoleLevel"],
    type: "select",
    options: ["CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"],
  },
  { label: "Logging", path: ["Settings", "Logging"], type: "checkbox" },
  {
    label: "Completed Download Folder",
    path: ["Settings", "CompletedDownloadFolder"],
    type: "text",
  },
  { label: "Free Space", path: ["Settings", "FreeSpace"], type: "text" },
  {
    label: "Free Space Folder",
    path: ["Settings", "FreeSpaceFolder"],
    type: "text",
  },
  { label: "Auto Pause/Resume", path: ["Settings", "AutoPauseResume"], type: "checkbox" },
  {
    label: "No Internet Sleep (s)",
    path: ["Settings", "NoInternetSleepTimer"],
    type: "number",
  },
  {
    label: "Loop Sleep (s)",
    path: ["Settings", "LoopSleepTimer"],
    type: "number",
  },
  {
    label: "Search Loop Delay (s)",
    path: ["Settings", "SearchLoopDelay"],
    type: "number",
  },
  { label: "Failed Category", path: ["Settings", "FailedCategory"], type: "text" },
  { label: "Recheck Category", path: ["Settings", "RecheckCategory"], type: "text" },
  { label: "Tagless", path: ["Settings", "Tagless"], type: "checkbox" },
  {
    label: "Ignore Torrents Younger Than",
    path: ["Settings", "IgnoreTorrentsYoungerThan"],
    type: "number",
  },
  { label: "WebUI Host", path: ["Settings", "WebUIHost"], type: "text" },
  {
    label: "WebUI Port",
    path: ["Settings", "WebUIPort"],
    type: "number",
  },
  { label: "WebUI Token", path: ["Settings", "WebUIToken"], type: "text" },
];

const QBIT_FIELDS: FieldDefinition[] = [
  { label: "Disabled", path: ["qBit", "Disabled"], type: "checkbox" },
  { label: "Host", path: ["qBit", "Host"], type: "text" },
  { label: "Port", path: ["qBit", "Port"], type: "number" },
  { label: "UserName", path: ["qBit", "UserName"], type: "text" },
  { label: "Password", path: ["qBit", "Password"], type: "password" },
];

const ARR_GENERAL_FIELDS: FieldDefinition[] = [
  { label: "Managed", path: ["Managed"], type: "checkbox" },
  { label: "URI", path: ["URI"], type: "text", placeholder: "http://host:port" },
  { label: "API Key", path: ["APIKey"], type: "password", placeholder: "apikey" },
  { label: "Category", path: ["Category"], type: "text" },
];

const ARR_ENTRY_SEARCH_FIELDS: FieldDefinition[] = [
  {
    label: "Search Missing",
    path: ["EntrySearch", "SearchMissing"],
    type: "checkbox",
  },
  {
    label: "Do Upgrade Search",
    path: ["EntrySearch", "DoUpgradeSearch"],
    type: "checkbox",
  },
  {
    label: "Quality Unmet Search",
    path: ["EntrySearch", "QualityUnmetSearch"],
    type: "checkbox",
  },
  {
    label: "Custom Format Unmet Search",
    path: ["EntrySearch", "CustomFormatUnmetSearch"],
    type: "checkbox",
  },
  {
    label: "Force Minimum Custom Format",
    path: ["EntrySearch", "ForceMinimumCustomFormat"],
    type: "checkbox",
  },
  {
    label: "Search Limit",
    path: ["EntrySearch", "SearchLimit"],
    type: "number",
  },
  {
    label: "Prioritize Today's Releases",
    path: ["EntrySearch", "PrioritizeTodaysReleases"],
    type: "checkbox",
  },
];

const ARR_TORRENT_FIELDS: FieldDefinition[] = [
  {
    label: "Ignore Torrents Younger Than (s)",
    path: ["Torrent", "IgnoreTorrentsYoungerThan"],
    type: "number",
  },
  {
    label: "Maximum ETA (s)",
    path: ["Torrent", "MaximumETA"],
    type: "number",
  },
  {
    label: "Maximum Deletable Percentage",
    path: ["Torrent", "MaximumDeletablePercentage"],
    type: "number",
  },
  {
    label: "Do Not Remove Slow",
    path: ["Torrent", "DoNotRemoveSlow"],
    type: "checkbox",
  },
  {
    label: "Stalled Delay (min)",
    path: ["Torrent", "StalledDelay"],
    type: "number",
  },
  {
    label: "Re-Search Stalled",
    path: ["Torrent", "ReSearchStalled"],
    type: "checkbox",
  },
  {
    label: "File Extension Allowlist (comma separated)",
    path: ["Torrent", "FileExtensionAllowlist"],
    type: "text",
    parse: (value) =>
      String(value)
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean),
    format: (value) => (Array.isArray(value) ? value.join(",") : String(value ?? "")),
  },
];

const ARR_SEEDING_FIELDS: FieldDefinition[] = [
  {
    label: "Max Upload Ratio",
    path: ["Torrent", "SeedingMode", "MaxUploadRatio"],
    type: "number",
  },
  {
    label: "Max Seeding Time (s)",
    path: ["Torrent", "SeedingMode", "MaxSeedingTime"],
    type: "number",
  },
  {
    label: "Remove Torrent (policy)",
    path: ["Torrent", "SeedingMode", "RemoveTorrent"],
    type: "number",
  },
];

function cloneConfig(config: ConfigDocument | null): ConfigDocument | null {
  return config ? JSON.parse(JSON.stringify(config)) : null;
}

function getValue(doc: ConfigDocument | null, path: string[]): unknown {
  if (!doc) return undefined;
  let cur: unknown = doc;
  for (const key of path) {
    if (cur == null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[key];
  }
  return cur;
}

function setValue(
  doc: ConfigDocument,
  path: string[],
  value: unknown
): void {
  let cur: Record<string, unknown> = doc;
  path.forEach((key, idx) => {
    if (idx === path.length - 1) {
      cur[key] = value;
    } else {
      if (typeof cur[key] !== "object" || cur[key] === null) {
        cur[key] = {};
      }
      cur = cur[key] as Record<string, unknown>;
    }
  });
}

function flatten(doc: ConfigDocument, prefix: string[] = []): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(doc)) {
    const nextPath = [...prefix, key];
    if (value && typeof value === "object" && !Array.isArray(value)) {
      Object.assign(result, flatten(value as ConfigDocument, nextPath));
    } else {
      result[nextPath.join(".")] = value;
    }
  }
  return result;
}

function ensureArrDefaults(type: string): ConfigDocument {
  return {
    Managed: true,
    URI: "",
    APIKey: "",
    Category: type,
    EntrySearch: {
      SearchMissing: false,
      DoUpgradeSearch: false,
      QualityUnmetSearch: false,
      CustomFormatUnmetSearch: false,
      ForceMinimumCustomFormat: false,
      SearchLimit: 0,
      PrioritizeTodaysReleases: false,
    },
    Torrent: {
      IgnoreTorrentsYoungerThan: 0,
      MaximumETA: 0,
      MaximumDeletablePercentage: 0,
      DoNotRemoveSlow: false,
      StalledDelay: 0,
      ReSearchStalled: false,
      FileExtensionAllowlist: [],
      SeedingMode: {
        MaxUploadRatio: 0,
        MaxSeedingTime: 0,
        RemoveTorrent: 0,
      },
    },
  };
}

export function ConfigView(): JSX.Element {
  const { push } = useToast();
  const [originalConfig, setOriginalConfig] = useState<ConfigDocument | null>(
    null
  );
  const [formState, setFormState] = useState<ConfigDocument | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const config = await getConfig();
      setOriginalConfig(config);
      setFormState(cloneConfig(config));
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
    void loadConfig();
  }, [loadConfig]);

  const handleFieldChange = useCallback(
    (path: string[], def: FieldDefinition, raw: string | boolean) => {
      if (!formState) return;
      const next = cloneConfig(formState) ?? {};
      const parsed =
        def.parse?.(raw) ??
        (def.type === "number"
          ? Number(raw) || 0
          : def.type === "checkbox"
          ? Boolean(raw)
          : raw);
      setValue(next, path, parsed);
      setFormState(next);
    },
    [formState]
  );

  const arrSections = useMemo(() => {
    if (!formState) return [] as Array<[string, ConfigDocument]>;
    return Object.entries(formState).filter(([key, value]) =>
      /(rad|son|anim)arr/i.test(key) && value && typeof value === "object"
    ) as Array<[string, ConfigDocument]>;
  }, [formState]);

  const addArrInstance = useCallback(
    (type: "radarr" | "sonarr") => {
      if (!formState) return;
      const prefix = type.charAt(0).toUpperCase() + type.slice(1);
      let index = 1;
      let key = `${prefix}-${index}`;
      while (formState[key]) {
        index += 1;
        key = `${prefix}-${index}`;
      }
      const next = cloneConfig(formState) ?? {};
      next[key] = ensureArrDefaults(type);
      setFormState(next);
    },
    [formState]
  );

  const handleSubmit = useCallback(async () => {
    if (!formState) return;
    setSaving(true);
    try {
      const flattenedOriginal = flatten(originalConfig ?? {});
      const flattenedCurrent = flatten(formState);
      const changes: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(flattenedCurrent)) {
        const originalValue = flattenedOriginal[key];
        const changed =
          Array.isArray(value) || Array.isArray(originalValue)
            ? JSON.stringify(value ?? []) !==
              JSON.stringify(originalValue ?? [])
            : value !== originalValue;
        if (changed) {
          changes[key] = value;
        }
      }
      if (Object.keys(changes).length === 0) {
        push("No changes detected", "info");
        setSaving(false);
        return;
      }
      await updateConfig({ changes });
      push("Configuration saved", "success");
      await loadConfig();
    } catch (error) {
      push(
        error instanceof Error
          ? error.message
          : "Failed to update configuration",
        "error"
      );
    } finally {
      setSaving(false);
    }
  }, [formState, originalConfig, loadConfig, push]);

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
    <section className="card">
      <div className="card-header">Config</div>
      <div className="card-body stack">
        <button className="btn" onClick={() => addArrInstance("radarr")}>
          Add Radarr Instance
        </button>
        <button className="btn" onClick={() => addArrInstance("sonarr")}>
          Add Sonarr Instance
        </button>
        <ConfigCard
          title="Settings"
          fields={SETTINGS_FIELDS}
          state={formState}
          onChange={handleFieldChange}
        />
        <ConfigCard
          title="qBit"
          fields={QBIT_FIELDS}
          state={formState}
          onChange={handleFieldChange}
        />
        {arrSections.map(([key, value]) => (
          <details className="card config-card" key={key} open>
            <summary>{key}</summary>
            <div className="card-body stack">
              <FieldGroup
                title="General"
                fields={ARR_GENERAL_FIELDS}
                state={value}
                basePath={[key]}
                onChange={handleFieldChange}
              />
              <FieldGroup
                title="Entry Search"
                fields={ARR_ENTRY_SEARCH_FIELDS}
                state={value}
                basePath={[key]}
                onChange={handleFieldChange}
              />
              <FieldGroup
                title="Torrent"
                fields={ARR_TORRENT_FIELDS}
                state={value}
                basePath={[key]}
                onChange={handleFieldChange}
              />
              <FieldGroup
                title="Seeding Mode"
                fields={ARR_SEEDING_FIELDS}
                state={value}
                basePath={[key]}
                onChange={handleFieldChange}
              />
            </div>
          </details>
        ))}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button
            className="btn primary"
            onClick={() => void handleSubmit()}
            disabled={saving}
          >
            Save + Live Reload
          </button>
        </div>
      </div>
    </section>
  );
}

interface ConfigCardProps {
  title: string;
  fields: FieldDefinition[];
  state: ConfigDocument | null;
  onChange: (path: string[], def: FieldDefinition, value: string | boolean) => void;
}

function ConfigCard({ title, fields, state, onChange }: ConfigCardProps): JSX.Element {
  return (
    <details className="card config-card" open>
      <summary>{title}</summary>
      <div className="card-body">
        <FieldGroup
          title={null}
          fields={fields}
          state={state}
          basePath={[]}
          onChange={onChange}
        />
      </div>
    </details>
  );
}

interface FieldGroupProps {
  title: string | null;
  fields: FieldDefinition[];
  state: ConfigDocument | ConfigDocument[keyof ConfigDocument] | null;
  basePath: string[];
  onChange: (path: string[], def: FieldDefinition, value: string | boolean) => void;
}

function FieldGroup({
  title,
  fields,
  state,
  basePath,
  onChange,
}: FieldGroupProps): JSX.Element {
  const renderedFields = fields.map((field) => {
    const path = [...basePath, ...field.path];
    const rawValue = getValue(state as ConfigDocument, field.path);
    const formatted =
      field.format?.(rawValue) ??
      (field.type === "checkbox" ? Boolean(rawValue) : String(rawValue ?? ""));
    if (field.type === "checkbox") {
      return (
        <label className="hint inline" key={path.join(".")}>
          <input
            type="checkbox"
            checked={Boolean(formatted)}
            onChange={(event) =>
              onChange(path, field, event.target.checked)
            }
          />
          {field.label}
        </label>
      );
    }
    if (field.type === "select") {
      return (
        <div className="field" key={path.join(".")}>
          <label>{field.label}</label>
          <select
            value={String(formatted)}
            onChange={(event) => onChange(path, field, event.target.value)}
          >
            {(field.options ?? []).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      );
    }
    return (
      <div className="field" key={path.join(".")}>
        <label>{field.label}</label>
        <input
          type={field.type === "number" ? "number" : field.type}
          value={String(formatted)}
          placeholder={field.placeholder}
          onChange={(event) => onChange(path, field, event.target.value)}
        />
      </div>
    );
  });

  if (title) {
    return (
      <details className="config-section" open>
        <summary>{title}</summary>
        <div className="config-section__body stack">{renderedFields}</div>
      </details>
    );
  }

  return <div className="stack">{renderedFields}</div>;
}
