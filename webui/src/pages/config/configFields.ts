import {
  parseDurationToSeconds,
} from "../../config/durationUtils";
import { mergeFieldOverlays } from "./configFieldMerge";
import {
  ARR_FIELD_OVERLAYS,
  QBIT_FIELD_OVERLAYS,
  SETTINGS_FIELD_OVERLAYS,
  WEBUI_FIELD_OVERLAYS,
} from "./configFieldOverlays";
import {
  GENERATED_ARR_FIELDS,
  GENERATED_QBIT_FIELDS,
  GENERATED_SETTINGS_FIELDS,
  GENERATED_WEBUI_FIELDS,
} from "./configFields.generated";
import {
  type FieldDefinition,
  SENTENCE_END,
} from "./configTypes";

export function extractTooltipSummary(tooltip?: string): string | undefined {
  if (!tooltip) return undefined;
  const trimmed = tooltip.trim();
  if (!trimmed) return undefined;
  const match = trimmed.match(SENTENCE_END);
  const sentence = match ? match[1] : trimmed;
  return sentence.length > 160 ? `${sentence.slice(0, 157)}…` : sentence;
}

/** Settings fields: registry codegen + FE validator overlays. */
export const SETTINGS_FIELDS: FieldDefinition[] = mergeFieldOverlays(
  GENERATED_SETTINGS_FIELDS,
  SETTINGS_FIELD_OVERLAYS,
);

const WEB_UI_CORE_PATHS = new Set([
  "WebUI.Host",
  "WebUI.Port",
  "WebUI.Token",
  "WebUI.BehindHttpsProxy",
  "WebUI.UrlBase",
]);

/** WebUI connection / proxy fields (layout group). */
export const WEB_SETTINGS_FIELDS: FieldDefinition[] = mergeFieldOverlays(
  GENERATED_WEBUI_FIELDS.filter((f) => WEB_UI_CORE_PATHS.has((f.path ?? []).join("."))),
  WEBUI_FIELD_OVERLAYS,
);

/** Auth / OIDC fields (layout group). */
export const AUTH_SETTINGS_FIELDS: FieldDefinition[] = mergeFieldOverlays(
  GENERATED_WEBUI_FIELDS.filter((f) => !WEB_UI_CORE_PATHS.has((f.path ?? []).join("."))),
  WEBUI_FIELD_OVERLAYS,
);

/** qBit instance fields: Display Name (FE-only) + generated stubs + overlays. */
export const QBIT_FIELDS: FieldDefinition[] = [
  { label: "Display Name", type: "text", placeholder: "qBit-seedbox", sectionName: true },
  ...mergeFieldOverlays(GENERATED_QBIT_FIELDS, QBIT_FIELD_OVERLAYS),
];

const MERGED_ARR_FIELDS: FieldDefinition[] = mergeFieldOverlays(
  GENERATED_ARR_FIELDS,
  ARR_FIELD_OVERLAYS,
);

/** FE-only Arr paths (inventory + UI); not emitted by ``generate_doc``. */
export const ARR_FE_ONLY_FIELDS: FieldDefinition[] = [
  {
    label: "Match subcategories (override)",
    path: ["MatchSubcategories"],
    type: "checkbox",
    description:
      "Optional. When set, overrides the qBit instance MatchSubcategories default for this Arr only (explicit true/false wins; omit to inherit from [qBit] / [qBit-*]).",
  },
];

/** Optional Arr override of qBit MatchSubcategories (not in generate_doc). */
const ARR_MATCH_SUBCATEGORIES_FIELD: FieldDefinition = ARR_FE_ONLY_FIELDS[0];

function isArrGeneralPath(path: string[]): boolean {
  return path.length === 1;
}

function isArrEntryPath(path: string[]): boolean {
  return (
    path[0] === "EntrySearch" &&
    path[1] !== "Ombi" &&
    path[1] !== "Overseerr"
  );
}

function isArrOmbiPath(path: string[]): boolean {
  return path[0] === "EntrySearch" && path[1] === "Ombi";
}

function isArrOverseerrPath(path: string[]): boolean {
  return path[0] === "EntrySearch" && path[1] === "Overseerr";
}

function isArrTorrentPath(path: string[]): boolean {
  return path[0] === "Torrent" && path[1] !== "SeedingMode";
}

function isArrSeedingPath(path: string[]): boolean {
  return path[0] === "Torrent" && path[1] === "SeedingMode";
}

/** Tracker AoT schema (not emitted as FieldDefinition rows by gen_config). */
export const ARR_TRACKER_FIELDS: FieldDefinition[] = [
  { label: "Name", path: ["Name"], type: "text", required: true },
  { label: "URI", path: ["URI"], type: "text", required: true },
  {
    label: "Priority",
    path: ["Priority"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Priority must be a non-negative number.";
      }
      return undefined;
    },
  },
  {
    label: "Sort Torrents by Tracker Priority",
    path: ["SortTorrents"],
    type: "checkbox",
  },
  {
    label: "Maximum ETA",
    path: ["MaximumETA"],
    type: "duration",
    nativeUnit: "seconds",
    allowNegative: true,
    validate: (value) => {
      const total = parseDurationToSeconds(value, -2);
      if (total === -1) return undefined;
      if (!Number.isFinite(total) || total < -1) {
        return "Maximum ETA must be -1 or a non-negative duration.";
      }
      return undefined;
    },
  },
  {
    label: "Download Rate Limit",
    path: ["DownloadRateLimit"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < -1) {
        return "Download Rate Limit must be -1 or greater.";
      }
      return undefined;
    },
  },
  {
    label: "Upload Rate Limit",
    path: ["UploadRateLimit"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < -1) {
        return "Upload Rate Limit must be -1 or greater.";
      }
      return undefined;
    },
  },
  {
    label: "Max Upload Ratio",
    path: ["MaxUploadRatio"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < -1) {
        return "Max Upload Ratio must be -1 or greater.";
      }
      return undefined;
    },
  },
  {
    label: "Max Seeding Time",
    path: ["MaxSeedingTime"],
    type: "duration",
    nativeUnit: "seconds",
    allowNegative: true,
    validate: (value) => {
      const total = parseDurationToSeconds(value, -2);
      if (total === -1) return undefined;
      if (!Number.isFinite(total) || total < -1) {
        return "Max Seeding Time must be -1 or greater.";
      }
      return undefined;
    },
  },
  {
    label: "Add Tracker If Missing",
    path: ["AddTrackerIfMissing"],
    type: "checkbox",
  },
  { label: "Remove If Exists", path: ["RemoveIfExists"], type: "checkbox" },
  { label: "Super Seed Mode", path: ["SuperSeedMode"], type: "checkbox" },
  {
    label: "Add Tags",
    path: ["AddTags"],
    type: "tags",
  },
  {
    label: "Hit and Run Mode",
    path: ["HitAndRunMode"],
    type: "select",
    options: ["and", "or", "disabled"],
    format: (v: unknown) =>
      v === true ? "and" : v === false ? "disabled" : (v as string),
    parse: (v: string | boolean) =>
      typeof v === "string" ? v : v ? "and" : "disabled",
  },
  {
    label: "Min Seed Ratio",
    path: ["MinSeedRatio"],
    type: "number",
    required: false,
    validate: (value) => {
      if (value === null || value === undefined || value === "") return undefined;
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Min Seed Ratio must be 0 or greater.";
      }
      return undefined;
    },
  },
  {
    label: "Min Seeding Time (days)",
    path: ["MinSeedingTimeDays"],
    type: "number",
    required: false,
    validate: (value) => {
      if (value === null || value === undefined || value === "") return undefined;
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Min Seeding Time must be 0 or greater.";
      }
      return undefined;
    },
  },
  {
    label: "Min Download % for HnR",
    path: ["HitAndRunMinimumDownloadPercent"],
    type: "number",
    required: false,
    validate: (value) => {
      if (value === null || value === undefined || value === "") return undefined;
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0 || num > 100) {
        return "Min Download % must be between 0 and 100.";
      }
      return undefined;
    },
  },
  {
    label: "Partial Download Seed Ratio",
    path: ["HitAndRunPartialSeedRatio"],
    type: "number",
    required: false,
    validate: (value) => {
      if (value === null || value === undefined || value === "") return undefined;
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Partial Download Seed Ratio must be 0 or greater.";
      }
      return undefined;
    },
  },
  {
    label: "Tracker Update Buffer",
    path: ["TrackerUpdateBuffer"],
    type: "duration",
    nativeUnit: "seconds",
    required: false,
    validate: (value) => {
      if (value === null || value === undefined || value === "") return undefined;
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Tracker Update Buffer must be 0 or greater.";
      }
      return undefined;
    },
  },
];

export function getArrFieldSets(arrKey: string) {
  const lower = arrKey.toLowerCase();
  const isSonarr = lower.includes("sonarr");
  const isLidarr = lower.includes("lidarr");
  const isReadarr = lower.includes("readarr");

  const generalLeaves = MERGED_ARR_FIELDS.filter(
    (f) => f.path && isArrGeneralPath(f.path),
  );
  const generalFields: FieldDefinition[] = [
    { label: "Display Name", type: "text", placeholder: "Sonarr-TV", sectionName: true },
    ...generalLeaves.slice(0, 4),
    ARR_MATCH_SUBCATEGORIES_FIELD,
    ...generalLeaves.slice(4),
  ];

  const entryFields = MERGED_ARR_FIELDS.filter((field) => {
    if (!field.path || !isArrEntryPath(field.path)) {
      return false;
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
    if (isLidarr && joined === "EntrySearch.SearchByYear") {
      return false;
    }
    return true;
  });

  const entryOmbiFields = isLidarr || isReadarr
    ? []
    : MERGED_ARR_FIELDS.filter((f) => f.path && isArrOmbiPath(f.path));
  const entryOverseerrFields = isLidarr || isReadarr
    ? []
    : MERGED_ARR_FIELDS.filter((f) => f.path && isArrOverseerrPath(f.path));
  const torrentFields = MERGED_ARR_FIELDS.filter(
    (f) => f.path && isArrTorrentPath(f.path),
  );
  const seedingFields = MERGED_ARR_FIELDS.filter(
    (f) => f.path && isArrSeedingPath(f.path),
  );
  const trackerFields = [...ARR_TRACKER_FIELDS];
  return {
    generalFields,
    entryFields,
    entryOmbiFields,
    entryOverseerrFields,
    torrentFields,
    seedingFields,
    trackerFields,
  };
}
