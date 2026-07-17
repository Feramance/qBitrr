/**
 * FE-only overlays for registry-generated config fields (validators / parse / UX).
 * Boring labels/kinds/reload hints come from codegen (configFields.generated.ts).
 */
import {
  parseDurationToMinutes,
  parseDurationToSeconds,
} from "../../config/durationUtils";
import { getValue } from "./configDocumentUtils";
import type { FieldOverlay } from "./configFieldMerge";
import { IMPORT_MODE_OPTIONS, REMOVE_TORRENT_OPTIONS } from "./configTypes";

export const SETTINGS_FIELD_OVERLAYS: Record<string, FieldOverlay> = {
  "Settings.CompletedDownloadFolder": {
    validate: (value) => {
      const folder = String(value ?? "").trim();
      if (!folder || folder.toUpperCase() === "CHANGE_ME") {
        return "Completed Download Folder must be set to a valid path.";
      }
      return undefined;
    },
  },
  "Settings.FreeSpace": {
    validate: (value) => {
      const raw = String(value ?? "").trim();
      if (!raw) {
        return "Free Space must be provided.";
      }
      if (raw === "-1") {
        return undefined;
      }
      if (!/^-?\d+(\.\d+)?[KMGTP]?$/i.test(raw)) {
        return "Free Space must be -1 or a number optionally suffixed with K, M, G, T, or P.";
      }
      return undefined;
    },
  },
  "Settings.FreeSpaceFolder": {
    validate: (value, context) => {
      const freeSpace = getValue(context.root, ["Settings", "FreeSpace"]);
      const requiresFolder = String(freeSpace ?? "").trim() !== "-1";
      if (!requiresFolder) {
        return undefined;
      }
      const folder = String(value ?? "").trim();
      if (!folder || folder.toUpperCase() === "CHANGE_ME") {
        return "Free Space Folder is required when Free Space monitoring is enabled.";
      }
      return undefined;
    },
  },
  "Settings.NoInternetSleepTimer": {
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "No Internet Sleep must be a non-negative duration.";
      }
      return undefined;
    },
  },
  "Settings.LoopSleepTimer": {
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Loop Sleep must be a non-negative duration.";
      }
      return undefined;
    },
  },
  "Settings.SearchLoopDelay": {
    allowNegative: true,
    validate: (value) => {
      const total = parseDurationToSeconds(value, -2);
      if (total === -1) return undefined;
      if (!Number.isFinite(total) || total < 0) {
        return "Search Loop Delay must be -1 (disabled) or a non-negative duration.";
      }
      return undefined;
    },
  },
  "Settings.IgnoreTorrentsYoungerThan": {
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Ignore Torrents Younger Than must be a non-negative duration.";
      }
      return undefined;
    },
  },
  "Settings.AutoUpdateCron": {
    validate: (value) => {
      const cron = String(value ?? "").trim();
      const parts = cron.split(/\s+/).filter(Boolean);
      if (parts.length < 5 || parts.length > 6) {
        return "Auto Update Cron must contain 5 or 6 space-separated fields.";
      }
      return undefined;
    },
  },
  "Settings.MaxProcessRestarts": {
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 1) {
        return "Max Process Restarts must be at least 1.";
      }
      return undefined;
    },
  },
  "Settings.ProcessRestartWindow": {
    validate: (value) => {
      const total = parseDurationToSeconds(value, 0);
      if (!Number.isFinite(total) || total < 1) {
        return "Process Restart Window must be at least 1 second.";
      }
      return undefined;
    },
  },
  "Settings.ProcessRestartDelay": {
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Process Restart Delay must be a non-negative duration.";
      }
      return undefined;
    },
  },
};

export const WEBUI_FIELD_OVERLAYS: Record<string, FieldOverlay> = {
  "WebUI.Host": {
    validate: (value) => {
      if (!String(value ?? "").trim()) {
        return "WebUI Host is required.";
      }
      return undefined;
    },
  },
  "WebUI.Port": {
    validate: (value) => {
      const port = typeof value === "number" ? value : Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        return "WebUI Port must be between 1 and 65535.";
      }
      return undefined;
    },
  },
  "WebUI.Token": {
    fullWidth: true,
  },
  "WebUI.UrlBase": {
    validate: (value) => {
      const raw = String(value ?? "").trim();
      if (!raw) {
        return undefined;
      }
      if (!raw.startsWith("/")) {
        return "UrlBase must start with / (e.g. /qbitrr).";
      }
      if (raw.endsWith("/")) {
        return "UrlBase must not end with a trailing slash.";
      }
      if (raw.includes("//")) {
        return "UrlBase is invalid.";
      }
      return undefined;
    },
  },
  "WebUI.OIDC.Authority": {
    placeholder: "https://auth.example.com/application/o/qbitrr",
    fullWidth: true,
    description: "OIDC issuer/authority URL",
  },
  "WebUI.OIDC.Scopes": {
    placeholder: "openid profile",
    description: "Space-separated OIDC scopes",
  },
  "WebUI.OIDC.CallbackPath": {
    placeholder: "/signin-oidc",
    description: "OIDC callback path (must match IdP redirect URI)",
  },
  "WebUI.OIDC.RequireHttpsMetadata": {
    label: "Require HTTPS Metadata",
    description: "Require HTTPS for IdP metadata (set false only for local dev OIDC)",
  },
};

export const QBIT_FIELD_OVERLAYS: Record<string, FieldOverlay> = {
  Host: {
    validate: (value, context) => {
      const disabled = Boolean(getValue(context.section ?? {}, ["Disabled"]));
      if (disabled) {
        return undefined;
      }
      if (!String(value ?? "").trim()) {
        return "qBit Host is required.";
      }
      return undefined;
    },
  },
  Port: {
    validate: (value) => {
      const port = typeof value === "number" ? value : Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        return "qBit Port must be between 1 and 65535.";
      }
      return undefined;
    },
  },
  ManagedCategories: {
    fullWidth: true,
    placeholder: "Add categories (e.g., prowlarr, downloads)",
    parse: (value: string | boolean) => {
      if (Array.isArray(value)) return value;
      if (typeof value === "string") return value.split(",").map((s) => s.trim()).filter(Boolean);
      return [];
    },
    format: (value: unknown) => {
      if (Array.isArray(value)) return value;
      if (typeof value === "string") return value.split(",").map((s) => s.trim()).filter(Boolean);
      return [];
    },
  },
  MatchSubcategories: {
    label: "Match subcategories",
    description:
      "When off (default), each managed category must match the qBittorrent category string exactly (use full paths like parent/child). When on, each entry here is a prefix: torrents in child categories (e.g. seed/foo) are included when seed is listed.",
  },
  "CategorySeeding.MaxUploadRatio": {
    placeholder: "-1 (disabled), or positive number",
  },
  "CategorySeeding.MaxSeedingTime": {
    placeholder: "-1 (disabled), or positive duration",
  },
  "CategorySeeding.RemoveTorrent": {
    label: "Remove Torrent (policy)",
    options: REMOVE_TORRENT_OPTIONS,
    parse: (value: string | boolean) => {
      const str = String(value);
      const match = str.match(/\((-?\d+)\)/);
      return match ? Number(match[1]) : -1;
    },
    format: (value: unknown) => {
      const num = typeof value === "number" ? value : Number(value ?? -1);
      return REMOVE_TORRENT_OPTIONS.find((opt) => opt.includes(`(${num})`)) || REMOVE_TORRENT_OPTIONS[0];
    },
  },
  "CategorySeeding.DownloadRateLimitPerTorrent": {
    label: "Download Rate Limit Per Torrent (KB/s)",
    placeholder: "-1 (unlimited), 0 (disabled), or positive number",
  },
  "CategorySeeding.UploadRateLimitPerTorrent": {
    label: "Upload Rate Limit Per Torrent (KB/s)",
    placeholder: "-1 (unlimited), 0 (disabled), or positive number",
  },
  "CategorySeeding.HitAndRunMode": {
    options: ["and", "or", "disabled"],
    format: (v: unknown) =>
      v === true ? "and" : v === false ? "disabled" : (v as string),
    parse: (v: string | boolean) =>
      typeof v === "string" ? v : v ? "and" : "disabled",
  },
  "CategorySeeding.MinSeedRatio": {
    label: "Min Seed Ratio",
    validate: (value) => {
      if (value === null || value === undefined || value === "") return undefined;
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Min Seed Ratio must be 0 or greater.";
      }
      return undefined;
    },
  },
  "CategorySeeding.MinSeedingTimeDays": {
    label: "Min Seeding Time (days)",
    validate: (value) => {
      if (value === null || value === undefined || value === "") return undefined;
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Min Seeding Time must be 0 or greater.";
      }
      return undefined;
    },
  },
  "CategorySeeding.HitAndRunMinimumDownloadPercent": {
    label: "Min Download % for HnR",
    validate: (value) => {
      if (value === null || value === undefined || value === "") return undefined;
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0 || num > 100) {
        return "Min Download % must be between 0 and 100.";
      }
      return undefined;
    },
  },
  "CategorySeeding.HitAndRunPartialSeedRatio": {
    label: "Partial Download Seed Ratio",
    validate: (value) => {
      if (value === null || value === undefined || value === "") return undefined;
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Partial Download Seed Ratio must be 0 or greater.";
      }
      return undefined;
    },
  },
  "CategorySeeding.TrackerUpdateBuffer": {
    validate: (value) => {
      if (value === null || value === undefined || value === "") return undefined;
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Tracker Update Buffer must be 0 or greater.";
      }
      return undefined;
    },
  },
  "CategorySeeding.StalledDelay": {
    placeholder: "-1 (disabled), 0 (infinite), or minutes before removing stalled downloads",
    validate: (value) => {
      const total = parseDurationToMinutes(value, -2);
      if (total === -1) return undefined;
      if (!Number.isFinite(total) || total < -1) {
        return "Stalled Delay must be -1 or greater.";
      }
      return undefined;
    },
  },
  "CategorySeeding.IgnoreTorrentsYoungerThan": {
    placeholder: "Seconds; stalled removal also requires last_activity older than this",
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Ignore Torrents Younger Than must be a non-negative duration.";
      }
      return undefined;
    },
  },
};

export const ARR_FIELD_OVERLAYS: Record<string, FieldOverlay> = {
  URI: {
    placeholder: "http://host:port",
    validate: (value, context) => {
      const uri = String(value ?? "").trim();
      const managed = Boolean(getValue(context.section ?? {}, ["Managed"]));
      if (!managed) {
        return undefined;
      }
      if (!uri || uri.toUpperCase() === "CHANGE_ME") {
        return "URI must be set to a valid URL when the instance is managed.";
      }
      return undefined;
    },
  },
  APIKey: {
    validate: (value, context) => {
      const apiKey = String(value ?? "").trim();
      const managed = Boolean(getValue(context.section ?? {}, ["Managed"]));
      if (!managed) {
        return undefined;
      }
      if (!apiKey || apiKey.toUpperCase() === "CHANGE_ME") {
        return "API Key must be provided when the instance is managed.";
      }
      return undefined;
    },
  },
  Category: {
    validate: (value, context) => {
      const managed = Boolean(getValue(context.section ?? {}, ["Managed"]));
      if (!managed) {
        return undefined;
      }
      if (!String(value ?? "").trim()) {
        return "Category is required.";
      }
      return undefined;
    },
  },
  importMode: {
    options: IMPORT_MODE_OPTIONS,
    validate: (value, context) => {
      const managed = Boolean(getValue(context.section ?? {}, ["Managed"]));
      if (!managed) {
        return undefined;
      }
      if (value === null || value === undefined || value === "") {
        return "Import Mode is required.";
      }
      return undefined;
    },
  },
  RssSyncTimer: {
    validate: (value) => {
      const total = parseDurationToMinutes(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "RSS Sync Timer must be a non-negative duration.";
      }
      return undefined;
    },
  },
  RefreshDownloadsTimer: {
    validate: (value) => {
      const total = parseDurationToMinutes(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Refresh Downloads Timer must be a non-negative duration.";
      }
      return undefined;
    },
  },
  ArrErrorCodesToBlocklist: {
    fullWidth: true,
  },
  "EntrySearch.SearchLimit": {
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 1) {
        return "Search Limit must be at least 1.";
      }
      return undefined;
    },
  },
  "EntrySearch.SearchRequestsEvery": {
    validate: (value) => {
      const total = parseDurationToSeconds(value, 0);
      if (!Number.isFinite(total) || total < 1) {
        return "Search Requests Every must be at least 1 second.";
      }
      return undefined;
    },
  },
  "EntrySearch.SearchAgainOnSearchCompletion": {
    label: "Search Again On Completion",
  },
  "EntrySearch.UseTempForMissing": {
    label: "Use Temp Profile For Missing",
  },
  "EntrySearch.ForceResetTempProfiles": {
    description:
      "Reset all items using temp profiles to their original main profile on qBitrr startup",
  },
  "EntrySearch.TempProfileResetTimeoutMinutes": {
    label: "Temp Profile Reset Timeout",
    type: "duration",
    nativeUnit: "minutes",
    description:
      "Timeout in minutes after which items with temp profiles are automatically reset to main profile (0 = disabled)",
  },
  "EntrySearch.ProfileSwitchRetryAttempts": {
    description: "Number of retry attempts for profile switch API calls (default: 3)",
  },
  "EntrySearch.SearchBySeries": {
    description:
      "smart = auto (series search for multiple episodes, episode search for single), true = always series search, false = always episode search",
    format: (value: unknown) => {
      if (typeof value === "boolean") {
        return value ? "true" : "false";
      }
      return String(value || "smart");
    },
    parse: (value: string | boolean) => {
      const str = String(value);
      if (str === "true" || str === "false") {
        return str;
      }
      return "smart";
    },
  },
  "EntrySearch.PrioritizeTodaysReleases": {
    label: "Prioritize Today's Releases",
  },
  "EntrySearch.Ombi.OmbiURI": {
    placeholder: "http://host:port",
  },
  "EntrySearch.Ombi.ApprovedOnly": {
    label: "Approved Only",
  },
  "EntrySearch.Overseerr.OverseerrURI": {
    placeholder: "http://host:port",
  },
  "EntrySearch.Overseerr.ApprovedOnly": {
    label: "Approved Only",
  },
  "EntrySearch.Overseerr.Is4K": {
    label: "Is 4K Instance",
  },
  "Torrent.FolderExclusionRegex": {
    fullWidth: true,
  },
  "Torrent.FileNameExclusionRegex": {
    fullWidth: true,
  },
  "Torrent.FileExtensionAllowlist": {
    fullWidth: true,
  },
  "Torrent.IgnoreTorrentsYoungerThan": {
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Ignore Torrents Younger Than must be a non-negative duration.";
      }
      return undefined;
    },
  },
  "Torrent.MaximumETA": {
    validate: (value) => {
      const total = parseDurationToSeconds(value, -2);
      if (total === -1) return undefined;
      if (!Number.isFinite(total) || total < -1) {
        return "Maximum ETA must be -1 or a non-negative duration.";
      }
      return undefined;
    },
  },
  "Torrent.MaximumDeletablePercentage": {
    placeholder: "0–100 (e.g. 99 = 99%)",
    format: (value: unknown) => {
      const n = typeof value === "number" ? value : Number(value ?? 0.99);
      return Number.isFinite(n) ? String(Math.round(n * 10000) / 100) : "99";
    },
    parse: (value: string | boolean) => {
      const n = Number(value);
      return Number.isFinite(n) ? n / 100 : 0.99;
    },
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0 || num > 1) {
        return "Maximum Deletable Percentage must be between 0 and 100 (e.g. 99 = 99%).";
      }
      return undefined;
    },
  },
  "Torrent.StalledDelay": {
    placeholder: "-1 (disabled), 0 (infinite), or minutes before removing stalled downloads",
    validate: (value) => {
      const total = parseDurationToMinutes(value, -2);
      if (total === -1) return undefined;
      if (!Number.isFinite(total) || total < -1) {
        return "Stalled Delay must be -1 (disabled), 0 (infinite), or a positive duration.";
      }
      return undefined;
    },
  },
  "Torrent.ReSearchStalled": {
    label: "Re-search Stalled",
  },
  "Torrent.SeedingMode.DownloadRateLimitPerTorrent": {
    label: "Download Rate Limit Per Torrent",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < -1) {
        return "Download Rate Limit must be -1 or greater.";
      }
      return undefined;
    },
  },
  "Torrent.SeedingMode.UploadRateLimitPerTorrent": {
    label: "Upload Rate Limit Per Torrent",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < -1) {
        return "Upload Rate Limit must be -1 or greater.";
      }
      return undefined;
    },
  },
  "Torrent.SeedingMode.MaxUploadRatio": {
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < -1) {
        return "Max Upload Ratio must be -1 or greater.";
      }
      return undefined;
    },
  },
  "Torrent.SeedingMode.MaxSeedingTime": {
    validate: (value) => {
      const total = parseDurationToSeconds(value, -2);
      if (total === -1) return undefined;
      if (!Number.isFinite(total) || total < -1) {
        return "Max Seeding Time must be -1 or greater.";
      }
      return undefined;
    },
  },
  "Torrent.SeedingMode.RemoveTorrent": {
    label: "Remove Torrent (policy)",
    options: REMOVE_TORRENT_OPTIONS,
    parse: (value: string | boolean) => {
      const str = String(value);
      const match = str.match(/\((-?\d+)\)/);
      return match ? Number(match[1]) : -1;
    },
    format: (value: unknown) => {
      const num = typeof value === "number" ? value : Number(value ?? -1);
      return REMOVE_TORRENT_OPTIONS.find((opt) => opt.includes(`(${num})`)) || REMOVE_TORRENT_OPTIONS[0];
    },
  },
  "Torrent.SeedingMode.RemoveTrackerWithMessage": {
    label: "Remove Tracker Messages",
    fullWidth: true,
  },
};
