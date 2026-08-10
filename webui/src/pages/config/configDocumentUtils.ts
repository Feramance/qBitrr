import { get, set } from "lodash-es";
import equal from "fast-deep-equal";
import type { ConfigDocument } from "../../api/types";
import { SERVARR_SECTION_REGEX } from "./configTypes";
import type { ValidationError } from "./configTypes";

export function isEmptyValue(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    (typeof value === "string" && value.trim() === "") ||
    (Array.isArray(value) && value.length === 0)
  );
}

export function buildSectionChanges(
  formState: ConfigDocument,
  originalConfig: ConfigDocument | null,
  sectionKey: string,
  pendingRenames: Map<string, string>
): Record<string, unknown> {
  const flattenedOriginal = flatten(originalConfig ?? {});
  const flattenedCurrent = flatten(formState);
  const changes: Record<string, unknown> = {};
  const prefix = `${sectionKey}.`;

  for (const [key, value] of Object.entries(flattenedCurrent)) {
    if (key !== sectionKey && !key.startsWith(prefix)) {
      continue;
    }
    const originalValue = flattenedOriginal[key];
    if (!equal(value, originalValue)) {
      changes[key] = value;
    }
  }

  for (const key of Object.keys(flattenedOriginal)) {
    if ((key === sectionKey || key.startsWith(prefix)) && !(key in flattenedCurrent)) {
      changes[key] = null;
    }
  }

  for (const [oldName, newName] of pendingRenames) {
    if (oldName !== sectionKey && newName !== sectionKey) {
      continue;
    }
    for (const key of Object.keys(flattenedOriginal)) {
      if (key === oldName || key.startsWith(`${oldName}.`)) {
        if (!(key in changes)) {
          changes[key] = null;
        }
      }
    }
  }

  if (
    !(sectionKey in formState) &&
    SERVARR_SECTION_REGEX.test(sectionKey) &&
    sectionKey in (originalConfig ?? {})
  ) {
    changes[sectionKey] = null;
  }

  return changes;
}

export function prunePendingRenames(
  pendingRenames: Map<string, string>,
  savedSectionKeys: Iterable<string> | "all"
): Map<string, string> {
  if (savedSectionKeys === "all") {
    return new Map();
  }
  const saved = new Set(savedSectionKeys);
  const next = new Map(pendingRenames);
  for (const [oldName, newName] of pendingRenames) {
    if (saved.has(oldName) || saved.has(newName)) {
      next.delete(oldName);
    }
  }
  return next;
}

/**
 * Resolve the on-disk section name for a form section key.
 * When the section was renamed locally but not saved, disk still uses the old name.
 */
export function resolveSectionDiskKey(
  sectionKey: string,
  pendingRenames: Map<string, string>
): string {
  for (const [oldName, newName] of pendingRenames) {
    if (newName === sectionKey) {
      return oldName;
    }
  }
  return sectionKey;
}

/**
 * Build a config API payload that deletes a section from disk.
 * Returns null when the section only exists in local form state (never saved).
 */
export function buildSectionDeleteChanges(
  sectionKey: string,
  originalConfig: ConfigDocument | null,
  pendingRenames: Map<string, string>
): Record<string, null> | null {
  const original = originalConfig ?? {};
  const diskKey = resolveSectionDiskKey(sectionKey, pendingRenames);
  const changes: Record<string, null> = {};
  if (diskKey in original) {
    changes[diskKey] = null;
  }
  if (sectionKey !== diskKey && sectionKey in original) {
    changes[sectionKey] = null;
  }
  return Object.keys(changes).length > 0 ? changes : null;
}

export function sectionKeysFromChanges(changes: Record<string, unknown>): string[] {
  const sections = new Set<string>();
  for (const key of Object.keys(changes)) {
    sections.add(key.split(".")[0] ?? key);
  }
  return [...sections];
}

export function buildAllChanges(
  formState: ConfigDocument,
  originalConfig: ConfigDocument | null,
  pendingRenames: Map<string, string>
): Record<string, unknown> {
  const flattenedOriginal = flatten(originalConfig ?? {});
  const flattenedCurrent = flatten(formState);
  const changes: Record<string, unknown> = {};

  for (const [key, value] of Object.entries(flattenedCurrent)) {
    const originalValue = flattenedOriginal[key];
    if (!equal(value, originalValue)) {
      changes[key] = value;
    }
  }
  for (const key of Object.keys(flattenedOriginal)) {
    if (!(key in flattenedCurrent)) {
      changes[key] = null;
    }
  }
  for (const [key, value] of Object.entries(originalConfig ?? {})) {
    if (
      !(key in formState) &&
      SERVARR_SECTION_REGEX.test(key) &&
      value &&
      typeof value === "object"
    ) {
      changes[key] = null;
    }
  }
  for (const [oldName] of pendingRenames) {
    for (const key of Object.keys(flattenedOriginal)) {
      if (key === oldName || key.startsWith(`${oldName}.`)) {
        if (!(key in changes)) {
          changes[key] = null;
        }
      }
    }
  }

  return changes;
}

export function formatValidationErrors(validationErrors: ValidationError[]): string {
  const formatted = validationErrors
    .map((error) => `${error.path.join(".")}: ${error.message}`)
    .join("\n");
  return validationErrors.length === 1
    ? formatted
    : `Please resolve the following issues:\n${formatted}`;
}

/** Convert API dotted-path validation errors into FE ValidationError[]. */
export function validationErrorsFromApi(
  apiErrors: ReadonlyArray<{ path: string; message: string }>
): ValidationError[] {
  return apiErrors.map((error) => ({
    path: error.path.split(".").filter(Boolean),
    message: error.message,
  }));
}

/** Resolve the message for a field given section/base path conventions used by modals. */
export function findFieldErrorMessage(
  errors: ValidationError[],
  fieldPath: string[],
  options?: { sectionKey?: string; basePath?: string[] }
): string | undefined {
  if (!errors.length || !fieldPath.length) {
    return undefined;
  }
  const basePath = options?.basePath ?? [];
  const sectionKey = options?.sectionKey;
  const candidates = new Set<string>([
    [...basePath, ...fieldPath].join("."),
    fieldPath.join("."),
  ]);
  if (sectionKey) {
    candidates.add([sectionKey, ...fieldPath].join("."));
  }
  const match = errors.find((error) => candidates.has(error.path.join(".")));
  return match?.message;
}

/** Full dotted path used for data-field-path / scroll-into-view. */
export function fieldErrorDataPath(
  fieldPath: string[],
  options?: { sectionKey?: string; basePath?: string[] }
): string {
  const basePath = options?.basePath ?? [];
  if (basePath.length) {
    return [...basePath, ...fieldPath].join(".");
  }
  if (options?.sectionKey) {
    return [options.sectionKey, ...fieldPath].join(".");
  }
  return fieldPath.join(".");
}

export function focusFirstValidationError(errors: ValidationError[]): void {
  if (!errors.length || typeof document === "undefined") {
    return;
  }
  const path = errors[0].path.join(".");
  const el = document.querySelector<HTMLElement>(`[data-field-path="${CSS.escape(path)}"]`);
  el?.scrollIntoView({ behavior: "smooth", block: "center" });
  const focusable = el?.querySelector<HTMLElement>("input, select, textarea, button");
  focusable?.focus({ preventScroll: true });
}

export function getValue(doc: ConfigDocument | null, path: string[]): unknown {
  if (!doc) return undefined;
  return get(doc, path);
}

export function setValue(
  doc: ConfigDocument,
  path: string[],
  value: unknown
): void {
  set(doc, path, value);
}

// Custom flatten to create dot-notation keys (e.g., "Settings.FreeSpace")
// Note: lodash's flatten is for arrays; this is a specialized object flattener
export function flatten(doc: ConfigDocument, prefix: string[] = []): Record<string, unknown> {
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

export function ensureArrDefaults(type: string): ConfigDocument {
  const lowerType = type.toLowerCase();
  const isSonarr = lowerType.includes("sonarr");
  const isRadarr = lowerType.includes("radarr");
  const isLidarr = lowerType.includes("lidarr");
  const isReadarr = lowerType.includes("readarr");

  const arrErrorCodes = isRadarr
    ? [
        "Not a preferred word upgrade for existing movie file(s)",
        "Not an upgrade for existing movie file(s)",
        "Unable to determine if file is a sample",
      ]
    : isLidarr
    ? [
        "Not a preferred word upgrade for existing album file(s)",
        "Not an upgrade for existing album file(s)",
        "Unable to determine if file is a sample",
      ]
    : isReadarr
    ? [
        "Not a preferred word upgrade for existing book file(s)",
        "Not an upgrade for existing book file(s)",
        "Unable to determine if file is a sample",
      ]
    : [
        "Not a preferred word upgrade for existing episode file(s)",
        "Not an upgrade for existing episode file(s)",
        "Unable to determine if file is a sample",
      ];

  const entrySearch: Record<string, unknown> = {
    SearchMissing: true,
    Unmonitored: false,
    SearchLimit: 5,
    SearchInReverse: false,
    SearchRequestsEvery: 300,
    DoUpgradeSearch: false,
    QualityUnmetSearch: false,
    CustomFormatUnmetSearch: false,
    ForceMinimumCustomFormat: false,
    SearchAgainOnSearchCompletion: true,
    UseTempForMissing: false,
    KeepTempProfile: false,
    ForceResetTempProfiles: false,
    TempProfileResetTimeoutMinutes: 0,
    ProfileSwitchRetryAttempts: 3,
    QualityProfileMappings: {},
  };

  // Lidarr omits year search; Readarr keeps it (book release year).
  if (!isLidarr) {
    entrySearch.SearchByYear = true;
  }

  if (isSonarr) {
    entrySearch.AlsoSearchSpecials = false;
    entrySearch.SearchBySeries = "smart";
    entrySearch.PrioritizeTodaysReleases = true;
  }

  // Ombi/Overseerr are Sonarr/Radarr only (not Lidarr or Readarr).
  if (!isLidarr && !isReadarr) {
    entrySearch.Ombi = {
      SearchOmbiRequests: false,
      OmbiURI: "CHANGE_ME",
      OmbiAPIKey: "CHANGE_ME",
      ApprovedOnly: true,
    };
    entrySearch.Overseerr = {
      SearchOverseerrRequests: false,
      OverseerrURI: "CHANGE_ME",
      OverseerrAPIKey: "CHANGE_ME",
      ApprovedOnly: true,
      Is4K: false,
    };
  }

  const torrent: Record<string, unknown> = {
    CaseSensitiveMatches: false,
    FolderExclusionRegex: isLidarr || isReadarr
      ? [
          "\\bextras?\\b",
          "\\bsamples?\\b",
          "\\bscreens?\\b",
        ]
      : [
          "\\bextras?\\b",
          "\\bfeaturettes?\\b",
          "\\bsamples?\\b",
          "\\bscreens?\\b",
          "\\bnc(ed|op)?(\\\\d+)?\\b",
        ],
    FileNameExclusionRegex: isLidarr || isReadarr
      ? [
          "\\bsample\\b",
          "brarbg.com\\b",
          "\\btrailer\\b",
          "comandotorrents.com",
        ]
      : [
          "\\bncop\\\\d+?\\b",
          "\\bnced\\\\d+?\\b",
          "\\bsample\\b",
          "brarbg.com\\b",
          "\\btrailer\\b",
          "music video",
          "comandotorrents.com",
        ],
    FileExtensionAllowlist: isLidarr
      ? [".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".ape", ".wma", ".!qB", ".parts", ".log", ".cue"]
      : isReadarr
        ? [".epub", ".mobi", ".azw", ".azw3", ".pdf", ".cbz", ".cbr", ".!qB", ".parts"]
        : [".mp4", ".mkv", ".sub", ".ass", ".srt", ".!qB", ".parts"],
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
