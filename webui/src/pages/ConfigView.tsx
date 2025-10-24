import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { getConfig, updateConfig } from "../api/client";
import type { ConfigDocument } from "../api/types";
import { useToast } from "../context/ToastContext";
import { getTooltip } from "../config/tooltips";

type FieldType = "text" | "number" | "checkbox" | "password" | "select";

interface FieldDefinition {
  label: string;
  path?: string[];
  type: FieldType;
  options?: string[];
  placeholder?: string;
  parse?: (value: string | boolean) => unknown;
  format?: (value: unknown) => string | boolean;
  sectionName?: boolean;
  secure?: boolean;
}

const parseList = (value: string | boolean): string[] =>
  String(value)
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);

const formatList = (value: unknown): string =>
  Array.isArray(value) ? value.join(", ") : String(value ?? "");

const IMPORT_MODE_OPTIONS = ["Move", "Copy", "Auto"];

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
  {
    label: "Ping URLs",
    path: ["Settings", "PingURLS"],
    type: "text",
    parse: parseList,
    format: formatList,
    placeholder: "one.one.one.one, dns.google.com",
  },
  {
    label: "FFprobe Auto Update",
    path: ["Settings", "FFprobeAutoUpdate"],
    type: "checkbox",
  },
  {
    label: "Auto Update Enabled",
    path: ["Settings", "AutoUpdateEnabled"],
    type: "checkbox",
  },
  {
    label: "Auto Update Cron",
    path: ["Settings", "AutoUpdateCron"],
    type: "text",
    placeholder: "0 3 * * 0",
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
  { label: "Display Name", type: "text", placeholder: "Sonarr-TV", sectionName: true },
  { label: "Managed", path: ["Managed"], type: "checkbox" },
  { label: "URI", path: ["URI"], type: "text", placeholder: "http://host:port" },
  { label: "API Key", path: ["APIKey"], type: "password", secure: true },
  { label: "Category", path: ["Category"], type: "text" },
  { label: "Re-search", path: ["ReSearch"], type: "checkbox" },
  {
    label: "Import Mode",
    path: ["importMode"],
    type: "select",
    options: IMPORT_MODE_OPTIONS,
  },
  {
    label: "RSS Sync Timer (min)",
    path: ["RssSyncTimer"],
    type: "number",
  },
  {
    label: "Refresh Downloads Timer (min)",
    path: ["RefreshDownloadsTimer"],
    type: "number",
  },
  {
    label: "Arr Error Codes To Blocklist",
    path: ["ArrErrorCodesToBlocklist"],
    type: "text",
    parse: parseList,
    format: formatList,
  },
];

const ARR_ENTRY_SEARCH_FIELDS: FieldDefinition[] = [
  {
    label: "Search Missing",
    path: ["EntrySearch", "SearchMissing"],
    type: "checkbox",
  },
  {
    label: "Also Search Specials",
    path: ["EntrySearch", "AlsoSearchSpecials"],
    type: "checkbox",
  },
  {
    label: "Unmonitored",
    path: ["EntrySearch", "Unmonitored"],
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
    label: "Search By Year",
    path: ["EntrySearch", "SearchByYear"],
    type: "checkbox",
  },
  {
    label: "Search In Reverse",
    path: ["EntrySearch", "SearchInReverse"],
    type: "checkbox",
  },
  {
    label: "Search Requests Every (s)",
    path: ["EntrySearch", "SearchRequestsEvery"],
    type: "number",
  },
  {
    label: "Search Again On Completion",
    path: ["EntrySearch", "SearchAgainOnSearchCompletion"],
    type: "checkbox",
  },
  {
    label: "Use Temp Profile For Missing",
    path: ["EntrySearch", "UseTempForMissing"],
    type: "checkbox",
  },
  {
    label: "Keep Temp Profile",
    path: ["EntrySearch", "KeepTempProfile"],
    type: "checkbox",
  },
  {
    label: "Main Quality Profile",
    path: ["EntrySearch", "MainQualityProfile"],
    type: "text",
    parse: parseList,
    format: formatList,
  },
  {
    label: "Temp Quality Profile",
    path: ["EntrySearch", "TempQualityProfile"],
    type: "text",
    parse: parseList,
    format: formatList,
  },
  {
    label: "Search By Series",
    path: ["EntrySearch", "SearchBySeries"],
    type: "checkbox",
  },
  {
    label: "Prioritize Today's Releases",
    path: ["EntrySearch", "PrioritizeTodaysReleases"],
    type: "checkbox",
  },
];

const ARR_ENTRY_SEARCH_OMBI_FIELDS: FieldDefinition[] = [
  {
    label: "Search Ombi Requests",
    path: ["EntrySearch", "Ombi", "SearchOmbiRequests"],
    type: "checkbox",
  },
  {
    label: "Ombi URI",
    path: ["EntrySearch", "Ombi", "OmbiURI"],
    type: "text",
    placeholder: "http://host:port",
  },
  {
    label: "Ombi API Key",
    path: ["EntrySearch", "Ombi", "OmbiAPIKey"],
    type: "password",
  },
  {
    label: "Approved Only",
    path: ["EntrySearch", "Ombi", "ApprovedOnly"],
    type: "checkbox",
  },
  {
    label: "Is 4K Instance",
    path: ["EntrySearch", "Ombi", "Is4K"],
    type: "checkbox",
  },
];

const ARR_ENTRY_SEARCH_OVERSEERR_FIELDS: FieldDefinition[] = [
  {
    label: "Search Overseerr Requests",
    path: ["EntrySearch", "Overseerr", "SearchOverseerrRequests"],
    type: "checkbox",
  },
  {
    label: "Overseerr URI",
    path: ["EntrySearch", "Overseerr", "OverseerrURI"],
    type: "text",
    placeholder: "http://host:port",
  },
  {
    label: "Overseerr API Key",
    path: ["EntrySearch", "Overseerr", "OverseerrAPIKey"],
    type: "password",
  },
  {
    label: "Approved Only",
    path: ["EntrySearch", "Overseerr", "ApprovedOnly"],
    type: "checkbox",
  },
  {
    label: "Is 4K Instance",
    path: ["EntrySearch", "Overseerr", "Is4K"],
    type: "checkbox",
  },
];

const ARR_TORRENT_FIELDS: FieldDefinition[] = [
  {
    label: "Case Sensitive Matches",
    path: ["Torrent", "CaseSensitiveMatches"],
    type: "checkbox",
  },
  {
    label: "Folder Exclusion Regex",
    path: ["Torrent", "FolderExclusionRegex"],
    type: "text",
    parse: parseList,
    format: formatList,
  },
  {
    label: "File Name Exclusion Regex",
    path: ["Torrent", "FileNameExclusionRegex"],
    type: "text",
    parse: parseList,
    format: formatList,
  },
  {
    label: "File Extension Allowlist",
    path: ["Torrent", "FileExtensionAllowlist"],
    type: "text",
    parse: parseList,
    format: formatList,
  },
  {
    label: "Auto Delete",
    path: ["Torrent", "AutoDelete"],
    type: "checkbox",
  },
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
    label: "Re-search Stalled",
    path: ["Torrent", "ReSearchStalled"],
    type: "checkbox",
  },
  {
    label: "Remove Dead Trackers",
    path: ["Torrent", "RemoveDeadTrackers"],
    type: "checkbox",
  },
  {
    label: "Remove Tracker Messages",
    path: ["Torrent", "RemoveTrackerWithMessage"],
    type: "text",
    parse: parseList,
    format: formatList,
  },
];

const ARR_SEEDING_FIELDS: FieldDefinition[] = [
  {
    label: "Download Rate Limit Per Torrent",
    path: ["Torrent", "SeedingMode", "DownloadRateLimitPerTorrent"],
    type: "number",
  },
  {
    label: "Upload Rate Limit Per Torrent",
    path: ["Torrent", "SeedingMode", "UploadRateLimitPerTorrent"],
    type: "number",
  },
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

function getArrFieldSets(arrKey: string) {
  const lower = arrKey.toLowerCase();
  const isSonarr = lower.includes("sonarr");
  const generalFields = [...ARR_GENERAL_FIELDS];
  const entryFields = ARR_ENTRY_SEARCH_FIELDS.filter((field) => {
    if (!field.path) {
      return true;
    }
    const joined = field.path.join(".");
    if (!isSonarr) {
      if (
        joined === "EntrySearch.AlsoSearchSpecials" ||
        joined === "EntrySearch.SearchBySeries" ||
        joined === "EntrySearch.PrioritizeTodaysReleases"
      ) {
        return false;
      }
    }
    return true;
  });
  const entryOmbiFields = [...ARR_ENTRY_SEARCH_OMBI_FIELDS];
  const entryOverseerrFields = [...ARR_ENTRY_SEARCH_OVERSEERR_FIELDS];
  const torrentFields = [...ARR_TORRENT_FIELDS];
  const seedingFields = [...ARR_SEEDING_FIELDS];
  return {
    generalFields,
    entryFields,
    entryOmbiFields,
    entryOverseerrFields,
    torrentFields,
    seedingFields,
  };
}

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
  const lowerType = type.toLowerCase();
  const isSonarr = lowerType.includes("sonarr");
  const isRadarr = lowerType.includes("radarr");
  const is4k = lowerType.includes("4k");
  const arrErrorCodes = isRadarr
    ? [
        "Not an upgrade for existing movie file(s)",
        "Not a preferred word upgrade for existing movie file(s)",
        "Unable to determine if file is a sample",
      ]
    : [
        "Not an upgrade for existing episode file(s)",
        "Not a preferred word upgrade for existing episode file(s)",
        "Unable to determine if file is a sample",
      ];

  const entrySearch: Record<string, unknown> = {
    SearchMissing: true,
    Unmonitored: false,
    SearchLimit: 5,
    SearchByYear: true,
    SearchInReverse: false,
    SearchRequestsEvery: 300,
    DoUpgradeSearch: false,
    QualityUnmetSearch: false,
    CustomFormatUnmetSearch: false,
    ForceMinimumCustomFormat: false,
    SearchAgainOnSearchCompletion: true,
    UseTempForMissing: false,
    KeepTempProfile: false,
    MainQualityProfile: [],
    TempQualityProfile: [],
  };

  if (isSonarr) {
    entrySearch.AlsoSearchSpecials = false;
    entrySearch.SearchBySeries = true;
    entrySearch.PrioritizeTodaysReleases = true;
  }

  entrySearch.Ombi = {
    SearchOmbiRequests: false,
    OmbiURI: "CHANGE_ME",
    OmbiAPIKey: "CHANGE_ME",
    ApprovedOnly: true,
    Is4K: is4k,
  };
  entrySearch.Overseerr = {
    SearchOverseerrRequests: false,
    OverseerrURI: "CHANGE_ME",
    OverseerrAPIKey: "CHANGE_ME",
    ApprovedOnly: true,
    Is4K: is4k,
  };

  const torrent: Record<string, unknown> = {
    CaseSensitiveMatches: false,
    FolderExclusionRegex: [
      "\\bextras?\\b",
      "\\bfeaturettes?\\b",
      "\\bsamples?\\b",
      "\\bscreens?\\b",
      "\\bnc(ed|op)?(\\\\d+)?\\b",
    ],
    FileNameExclusionRegex: [
      "\\bncop\\\\d+?\\b",
      "\\bnced\\\\d+?\\b",
      "\\bsample\\b",
      "brarbg.com\\b",
      "\\btrailer\\b",
      "music video",
      "comandotorrents.com",
    ],
    FileExtensionAllowlist: [".mp4", ".mkv", ".sub", ".ass", ".srt", ".!qB", ".parts"],
    AutoDelete: false,
    IgnoreTorrentsYoungerThan: 600,
    MaximumETA: 604800,
    MaximumDeletablePercentage: 0.99,
    DoNotRemoveSlow: true,
    StalledDelay: 15,
    ReSearchStalled: false,
    RemoveDeadTrackers: false,
    RemoveTrackerWithMessage: [
      "skipping tracker announce (unreachable)",
      "No such host is known",
      "unsupported URL protocol",
      "info hash is not authorized with this tracker",
    ],
    SeedingMode: {
      DownloadRateLimitPerTorrent: -1,
      UploadRateLimitPerTorrent: -1,
      MaxUploadRatio: -1,
      MaxSeedingTime: -1,
      RemoveTorrent: -1,
    },
  };

  return {
    Managed: true,
    URI: "CHANGE_ME",
    APIKey: "CHANGE_ME",
    Category: type,
    ReSearch: true,
    importMode: "Auto",
    RssSyncTimer: 5,
    RefreshDownloadsTimer: 5,
    ArrErrorCodesToBlocklist: arrErrorCodes,
    EntrySearch: entrySearch as ConfigDocument,
    Torrent: torrent as ConfigDocument,
  } as ConfigDocument;
}

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
  const [activeArrKey, setActiveArrKey] = useState<string | null>(null);
  const [isSettingsOpen, setSettingsOpen] = useState(false);
  const [isQbitOpen, setQbitOpen] = useState(false);
  const [isDirty, setDirty] = useState(false);

  useEffect(() => {
    if (!formState || !originalConfig) {
      setDirty(false);
      return;
    }
    const flattenedOriginal = flatten(originalConfig);
    const flattenedCurrent = flatten(formState);

    let dirty = false;
    for (const [key, value] of Object.entries(flattenedCurrent)) {
      const originalValue = flattenedOriginal[key];
      const changed =
        Array.isArray(value) || Array.isArray(originalValue)
          ? JSON.stringify(value ?? []) !== JSON.stringify(originalValue ?? [])
          : value !== originalValue;
      if (changed) {
        dirty = true;
        break;
      }
    }
    if (!dirty) {
      for (const key of Object.keys(flattenedOriginal)) {
        if (!(key in flattenedCurrent)) {
          dirty = true;
          break;
        }
      }
    }
    setDirty(dirty);
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
    const anyModalOpen = Boolean(activeArrKey || isSettingsOpen || isQbitOpen);
    if (!anyModalOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setActiveArrKey(null);
        setSettingsOpen(false);
        setQbitOpen(false);
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
  }, [activeArrKey, isSettingsOpen, isQbitOpen]);

  useEffect(() => {
    if (!activeArrKey) return;
    if (!arrSections.some(([key]) => key === activeArrKey)) {
      setActiveArrKey(null);
    }
  }, [activeArrKey, arrSections]);

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
      const defaults = ensureArrDefaults(type);
      if (defaults && typeof defaults === "object") {
        (defaults as Record<string, unknown>).Name = key;
      }
      next[key] = defaults;
      setFormState(next);
    },
    [formState]
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
      const next = cloneConfig(formState) ?? {};
      const section = next[oldName];
      delete next[oldName];
      next[newName] = section;
      if (section && typeof section === "object") {
        (section as Record<string, unknown>).Name = newName;
      }
      setFormState(next);
      if (activeArrKey === oldName) {
        setActiveArrKey(newName);
      }
    },
    [formState, push, activeArrKey]
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
      for (const key of Object.keys(flattenedOriginal)) {
        if (!(key in flattenedCurrent)) {
          changes[key] = null;
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
    <>
      <section className="card">
        <div className="card-header">Config</div>
        <div className="card-body config-layout">
          <div className="config-grid">
            <ConfigSummaryCard
              title="Settings"
              description="Core application configuration"
              onConfigure={() => setSettingsOpen(true)}
            />
            <ConfigSummaryCard
              title="qBit"
              description="qBittorrent connection details"
              onConfigure={() => setQbitOpen(true)}
            />
          </div>
          {arrSections.length ? (
            <div className="config-arr-grid">
              {arrSections.map(([key, value]) => {
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
                          Configure
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}
          <div className="config-footer">
            <div className="config-actions">
              <button
                className="btn"
                type="button"
                onClick={() => addArrInstance("radarr")}
              >
                Add Radarr Instance
              </button>
              <button
                className="btn"
                type="button"
                onClick={() => addArrInstance("sonarr")}
              >
                Add Sonarr Instance
              </button>
            </div>
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
      {activeArrKey && formState ? (
        <ArrInstanceModal
          keyName={activeArrKey}
          state={(formState[activeArrKey] as ConfigDocument) ?? null}
          onChange={handleFieldChange}
          onRename={handleRenameSection}
          onClose={() => setActiveArrKey(null)}
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
        />
      ) : null}
      {isQbitOpen ? (
        <SimpleConfigModal
          title="qBit"
          fields={QBIT_FIELDS}
          state={formState}
          basePath={[]}
          onChange={handleFieldChange}
          onClose={() => setQbitOpen(false)}
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
            Configure
          </button>
        </div>
      </div>
    </div>
  );
}

interface FieldGroupProps {
  title: string | null;
  fields: FieldDefinition[];
  state: ConfigDocument | ConfigDocument[keyof ConfigDocument] | null;
  basePath: string[];
  onChange: (path: string[], def: FieldDefinition, value: string | boolean) => void;
  onRenameSection?: (oldName: string, newName: string) => void;
  defaultOpen?: boolean;
}

function FieldGroup({
  title,
  fields,
  state,
  basePath,
  onChange,
  onRenameSection,
  defaultOpen = false,
}: FieldGroupProps): JSX.Element {
  const sectionName = basePath[0] ?? "";
  const renderedFields = fields.map((field) => {
    if (field.sectionName) {
      if (!sectionName) {
        return null;
      }
      const tooltip = getTooltip([sectionName]);
      return (
        <SectionNameField
          key={`${sectionName}.__name`}
          label={field.label}
          tooltip={tooltip}
          currentName={sectionName}
          placeholder={field.placeholder}
          onRename={(newName) => onRenameSection?.(sectionName, newName)}
        />
      );
    }

    const pathSegments = field.path ?? [];
    const path = [...basePath, ...pathSegments];
    const rawValue = field.path
      ? getValue(state as ConfigDocument, field.path as string[])
      : undefined;
    const formatted =
      field.format?.(rawValue) ??
      (field.type === "checkbox" ? Boolean(rawValue) : String(rawValue ?? ""));
    const tooltip = getTooltip(path);

    if (field.secure) {
      return (
        <SecureField
          key={path.join('.')}
          label={field.label}
          tooltip={tooltip}
          value={String(rawValue ?? '')}
          placeholder={field.placeholder}
          onChange={(val) => onChange(path, field, val)}
        />
      );
    }

    if (field.type === "checkbox") {
      return (
        <label className="checkbox-field" key={path.join('.')}>
          <input
            type="checkbox"
            checked={Boolean(formatted)}
            onChange={(event) => onChange(path, field, event.target.checked)}
          />
          <span className="checkbox-field__text">
            {field.label}
            {tooltip ? (
              <span className="help-icon" title={tooltip} aria-label={tooltip}>
                ?
              </span>
            ) : null}
          </span>
        </label>
      );
    }
    if (field.type === "select") {
      return (
        <div className="field" key={path.join('.')}>
          <label className="field-label">
            <span>{field.label}</span>
            {tooltip ? (
              <span className="help-icon" title={tooltip} aria-label={tooltip}>
                ?
              </span>
            ) : null}
          </label>
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
      <div className="field" key={path.join('.')}>
        <label className="field-label">
          <span>{field.label}</span>
          {tooltip ? (
            <span className="help-icon" title={tooltip} aria-label={tooltip}>
              ?
            </span>
          ) : null}
        </label>
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
      <details className="config-section" open={defaultOpen}>
        <summary>{title}</summary>
        <div className="config-section__body field-grid">{renderedFields}</div>
      </details>
    );
  }

  return <div className="field-grid">{renderedFields}</div>;
}

interface SectionNameFieldProps {
  label: string;
  currentName: string;
  placeholder?: string;
  tooltip?: string;
  onRename: (newName: string) => void;
}

function SectionNameField({
  label,
  currentName,
  placeholder,
  tooltip,
  onRename,
}: SectionNameFieldProps): JSX.Element {
  const [value, setValue] = useState(currentName);

  useEffect(() => {
    setValue(currentName);
  }, [currentName]);

  const commit = () => {
    const trimmed = value.trim();
    if (!trimmed) {
      setValue(currentName);
      return;
    }
    if (trimmed !== currentName) {
      onRename(trimmed);
    }
  };

  return (
    <div className="field">
      <label className="field-label">
        <span>{label}</span>
        {tooltip ? (
          <span className="help-icon" title={tooltip} aria-label={tooltip}>
            ?
          </span>
        ) : null}
      </label>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(event) => setValue(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            commit();
          } else if (event.key === "Escape") {
            event.preventDefault();
            setValue(currentName);
          }
        }}
      />
    </div>
  );
}

interface SecureFieldProps {
  label: string;
  value: string;
  placeholder?: string;
  tooltip?: string;
  onChange: (value: string) => void;
}

function SecureField({
  label,
  value,
  placeholder,
  tooltip,
  onChange,
}: SecureFieldProps): JSX.Element {
  const [revealed, setRevealed] = useState(false);

  const maskedValue =
    value && !revealed
      ? "*".repeat(Math.min(Math.max(value.length, 8), 16))
      : "";
  const displayValue = revealed ? value : value ? maskedValue : "";

  const handleRefresh = () => {
    let newKey = "";
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      newKey = crypto.randomUUID().replace(/-/g, "");
    } else {
      newKey = Array.from({ length: 32 }, () =>
        Math.floor(Math.random() * 16).toString(16)
      ).join("");
    }
    setRevealed(true);
    onChange(newKey);
  };

  return (
    <div className="field secure-field">
      <label className="field-label">
        <span>{label}</span>
        {tooltip ? (
          <span className="help-icon" title={tooltip} aria-label={tooltip}>
            ?
          </span>
        ) : null}
      </label>
      <div className="secure-field__input-group">
        <input
          type={revealed ? "text" : "password"}
          value={revealed ? value : displayValue}
          placeholder={placeholder}
          readOnly={!revealed}
          onChange={(event) => onChange(event.target.value)}
        />
        <div className="secure-field__controls">
          <button
            type="button"
            className="btn ghost"
            onClick={() => setRevealed((prev) => !prev)}
          >
            {revealed ? "Hide" : "Show"}
          </button>
          <button type="button" className="btn ghost" onClick={handleRefresh}>
            Refresh
          </button>
        </div>
      </div>
    </div>
  );
}

interface ArrInstanceModalProps {
  keyName: string;
  state: ConfigDocument | null;
  onChange: (path: string[], def: FieldDefinition, value: string | boolean) => void;
  onRename: (oldName: string, newName: string) => void;
  onClose: () => void;
}

function ArrInstanceModal({
  keyName,
  state,
  onChange,
  onRename,
  onClose,
}: ArrInstanceModalProps): JSX.Element | null {
  if (!state) return null;
  const fieldSets = getArrFieldSets(keyName);

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="arr-config-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="arr-config-title">Configure {keyName}</h2>
          <button className="btn ghost" type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-body">
          <FieldGroup
            title="General"
            fields={fieldSets.generalFields}
            state={state}
            basePath={[keyName]}
            onChange={onChange}
            onRenameSection={onRename}
            defaultOpen
          />
          <FieldGroup
            title="Entry Search"
            fields={fieldSets.entryFields}
            state={state}
            basePath={[keyName]}
            onChange={onChange}
            defaultOpen
          />
          {fieldSets.entryOmbiFields.length ? (
            <FieldGroup
              title="Entry Search - Ombi"
              fields={fieldSets.entryOmbiFields}
              state={state}
              basePath={[keyName]}
              onChange={onChange}
              defaultOpen
            />
          ) : null}
          {fieldSets.entryOverseerrFields.length ? (
            <FieldGroup
              title="Entry Search - Overseerr"
              fields={fieldSets.entryOverseerrFields}
              state={state}
              basePath={[keyName]}
              onChange={onChange}
              defaultOpen
            />
          ) : null}
          <FieldGroup
            title="Torrent"
            fields={fieldSets.torrentFields}
            state={state}
            basePath={[keyName]}
            onChange={onChange}
            defaultOpen
          />
          <FieldGroup
            title="Seeding Mode"
            fields={fieldSets.seedingFields}
            state={state}
            basePath={[keyName]}
            onChange={onChange}
            defaultOpen
          />
        </div>
        <div className="modal-footer">
          <button className="btn primary" type="button" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

interface SimpleConfigModalProps {
  title: string;
  fields: FieldDefinition[];
  state: ConfigDocument | null;
  basePath: string[];
  onChange: (path: string[], def: FieldDefinition, value: string | boolean) => void;
  onClose: () => void;
}

function SimpleConfigModal({
  title,
  fields,
  state,
  basePath,
  onChange,
  onClose,
}: SimpleConfigModalProps): JSX.Element | null {
  if (!state) return null;
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${title}-modal-title`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id={`${title}-modal-title`}>{title}</h2>
          <button className="btn ghost" type="button" onClick={onClose}>
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
        </div>
        <div className="modal-footer">
          <button className="btn primary" type="button" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
