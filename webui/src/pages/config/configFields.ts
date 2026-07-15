import type { ConfigDocument } from "../../api/types";
import { getTooltip } from "../../config/tooltips";
import {
  parseDurationToMinutes,
  parseDurationToSeconds,
} from "../../config/durationUtils";
import { getValue, isEmptyValue } from "./configDocumentUtils";
import {
  type FieldDefinition,
  IMPORT_MODE_OPTIONS,
  REMOVE_TORRENT_OPTIONS,
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





export const SETTINGS_FIELDS: FieldDefinition[] = [
  {
    label: "Console Level",
    path: ["Settings", "ConsoleLevel"],
    type: "select",
    options: ["CRITICAL", "ERROR", "WARNING", "NOTICE", "INFO", "DEBUG", "TRACE"],
    required: true,
  },
  { label: "Logging", path: ["Settings", "Logging"], type: "checkbox" },
  {
    label: "Completed Download Folder",
    path: ["Settings", "CompletedDownloadFolder"],
    type: "text",
    required: true,
    validate: (value) => {
      const folder = String(value ?? "").trim();
      if (!folder || folder.toUpperCase() === "CHANGE_ME") {
        return "Completed Download Folder must be set to a valid path.";
      }
      return undefined;
    },
  },
  {
    label: "Free Space",
    path: ["Settings", "FreeSpace"],
    type: "text",
    required: true,
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
  {
    label: "Free Space Folder",
    path: ["Settings", "FreeSpaceFolder"],
    type: "text",
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
  { label: "Auto Pause/Resume", path: ["Settings", "AutoPauseResume"], type: "checkbox" },
  {
    label: "No Internet Sleep",
    path: ["Settings", "NoInternetSleepTimer"],
    type: "duration",
    nativeUnit: "seconds",
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "No Internet Sleep must be a non-negative duration.";
      }
      return undefined;
    },
  },
  {
    label: "Loop Sleep",
    path: ["Settings", "LoopSleepTimer"],
    type: "duration",
    nativeUnit: "seconds",
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Loop Sleep must be a non-negative duration.";
      }
      return undefined;
    },
  },
  {
    label: "Search Loop Delay",
    path: ["Settings", "SearchLoopDelay"],
    type: "duration",
    nativeUnit: "seconds",
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
  { label: "Failed Category", path: ["Settings", "FailedCategory"], type: "text" },
  { label: "Recheck Category", path: ["Settings", "RecheckCategory"], type: "text" },
  { label: "Tagless", path: ["Settings", "Tagless"], type: "checkbox" },
  {
    label: "Ignore Torrents Younger Than",
    path: ["Settings", "IgnoreTorrentsYoungerThan"],
    type: "duration",
    nativeUnit: "seconds",
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Ignore Torrents Younger Than must be a non-negative duration.";
      }
      return undefined;
    },
  },
  {
    label: "Ping URLs",
    path: ["Settings", "PingURLS"],
    type: "tags",
    placeholder: "one.one.one.one",
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
    required: true,
    validate: (value) => {
      const cron = String(value ?? "").trim();
      const parts = cron.split(/\s+/).filter(Boolean);
      if (parts.length < 5 || parts.length > 6) {
        return "Auto Update Cron must contain 5 or 6 space-separated fields.";
      }
      return undefined;
    },
  },
  {
    label: "Auto-Restart Processes",
    path: ["Settings", "AutoRestartProcesses"],
    type: "checkbox",
  },
  {
    label: "Max Process Restarts",
    path: ["Settings", "MaxProcessRestarts"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 1) {
        return "Max Process Restarts must be at least 1.";
      }
      return undefined;
    },
  },
  {
    label: "Process Restart Window",
    path: ["Settings", "ProcessRestartWindow"],
    type: "duration",
    nativeUnit: "seconds",
    validate: (value) => {
      const total = parseDurationToSeconds(value, 0);
      if (!Number.isFinite(total) || total < 1) {
        return "Process Restart Window must be at least 1 second.";
      }
      return undefined;
    },
  },
  {
    label: "Process Restart Delay",
    path: ["Settings", "ProcessRestartDelay"],
    type: "duration",
    nativeUnit: "seconds",
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Process Restart Delay must be a non-negative duration.";
      }
      return undefined;
    },
  },

];

export const WEB_SETTINGS_FIELDS: FieldDefinition[] = [
  {
    label: "WebUI Host",
    path: ["WebUI", "Host"],
    type: "text",
    required: true,
    validate: (value) => {
      if (!String(value ?? "").trim()) {
        return "WebUI Host is required.";
      }
      return undefined;
    },
  },
  {
    label: "WebUI Port",
    path: ["WebUI", "Port"],
    type: "number",
    validate: (value) => {
      const port = typeof value === "number" ? value : Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        return "WebUI Port must be between 1 and 65535.";
      }
      return undefined;
    },
  },
  {
    label: "WebUI Token",
    path: ["WebUI", "Token"],
    type: "password",
    secure: true,
    fullWidth: true,
  },
  {
    label: "Behind HTTPS Proxy",
    path: ["WebUI", "BehindHttpsProxy"],
    type: "checkbox",
    description: "Set when the WebUI is reached over HTTPS (e.g. reverse proxy). Enables Secure cookies.",
  },
  {
    label: "Url Base",
    path: ["WebUI", "UrlBase"],
    type: "text",
    placeholder: "/qbitrr",
    description:
      "Public path prefix when behind a reverse proxy (e.g. /qbitrr). Leave empty for site root.",
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
];

export const AUTH_SETTINGS_FIELDS: FieldDefinition[] = [
  {
    label: "Auth Disabled",
    path: ["WebUI", "AuthDisabled"],
    type: "checkbox",
    description: "Disable login requirement (default: true for backward compatibility)",
  },
  {
    label: "Local Auth Enabled",
    path: ["WebUI", "LocalAuthEnabled"],
    type: "checkbox",
    description: "Enable username/password login",
  },
  {
    label: "OIDC Enabled",
    path: ["WebUI", "OIDCEnabled"],
    type: "checkbox",
    description: "Enable OpenID Connect login",
  },
  {
    label: "Username",
    path: ["WebUI", "Username"],
    type: "text",
    description: "Username for local auth login",
  },
  {
    label: "OIDC Authority",
    path: ["WebUI", "OIDC", "Authority"],
    type: "text",
    placeholder: "https://auth.example.com/application/o/qbitrr",
    description: "OIDC issuer/authority URL",
    fullWidth: true,
  },
  {
    label: "OIDC Client ID",
    path: ["WebUI", "OIDC", "ClientId"],
    type: "text",
    description: "OAuth2 client ID",
  },
  {
    label: "OIDC Client Secret",
    path: ["WebUI", "OIDC", "ClientSecret"],
    type: "password",
    secure: true,
    description: "OAuth2 client secret",
  },
  {
    label: "OIDC Scopes",
    path: ["WebUI", "OIDC", "Scopes"],
    type: "text",
    placeholder: "openid profile",
    description: "Space-separated OIDC scopes",
  },
  {
    label: "OIDC Callback Path",
    path: ["WebUI", "OIDC", "CallbackPath"],
    type: "text",
    placeholder: "/signin-oidc",
    description: "OIDC callback path (must match IdP redirect URI)",
  },
  {
    label: "Require HTTPS Metadata",
    path: ["WebUI", "OIDC", "RequireHttpsMetadata"],
    type: "checkbox",
    description: "Require HTTPS for IdP metadata (set false only for local dev OIDC)",
  },
];

export const QBIT_FIELDS: FieldDefinition[] = [
  { label: "Display Name", type: "text", placeholder: "qBit-seedbox", sectionName: true },
  { label: "Disabled", path: ["Disabled"], type: "checkbox" },
  {
    label: "Host",
    path: ["Host"],
    type: "text",
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
  {
    label: "Port",
    path: ["Port"],
    type: "number",
    validate: (value) => {
      const port = typeof value === "number" ? value : Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        return "qBit Port must be between 1 and 65535.";
      }
      return undefined;
    },
  },
  { label: "UserName", path: ["UserName"], type: "text" },
  { label: "Password", path: ["Password"], type: "password", secure: true },
  {
    label: "Managed Categories",
    path: ["ManagedCategories"],
    type: "tags",
    fullWidth: true,
    placeholder: "Add categories (e.g., prowlarr, downloads)",
    parse: (value: string | boolean) => {
      // When saving, ensure we always save as array
      if (Array.isArray(value)) return value;
      if (typeof value === "string") return value.split(",").map(s => s.trim()).filter(Boolean);
      return [];
    },
    format: (value: unknown) => {
      // When displaying, ensure we always show as array
      if (Array.isArray(value)) return value;
      if (typeof value === "string") return value.split(",").map(s => s.trim()).filter(Boolean);
      return [];
    },
  },
  {
    label: "Match subcategories",
    path: ["MatchSubcategories"],
    type: "checkbox",
    description:
      "When off (default), each managed category must match the qBittorrent category string exactly (use full paths like parent/child). When on, each entry here is a prefix: torrents in child categories (e.g. seed/foo) are included when seed is listed.",
  },
  {
    label: "Max Upload Ratio",
    path: ["CategorySeeding", "MaxUploadRatio"],
    type: "number",
    placeholder: "-1 (disabled), or positive number",
  },
  {
    label: "Max Seeding Time",
    path: ["CategorySeeding", "MaxSeedingTime"],
    type: "duration",
    nativeUnit: "seconds",
    allowNegative: true,
    placeholder: "-1 (disabled), or positive duration",
  },
  {
    label: "Remove Torrent (policy)",
    path: ["CategorySeeding", "RemoveTorrent"],
    type: "select",
    options: REMOVE_TORRENT_OPTIONS,
    parse: (value: string | boolean) => {
      const str = String(value);
      const match = str.match(/\((-?\d+)\)/);
      return match ? Number(match[1]) : -1;
    },
    format: (value: unknown) => {
      const num = typeof value === "number" ? value : Number(value ?? -1);
      return REMOVE_TORRENT_OPTIONS.find(opt => opt.includes(`(${num})`)) || REMOVE_TORRENT_OPTIONS[0];
    },
  },
  {
    label: "Download Rate Limit Per Torrent (KB/s)",
    path: ["CategorySeeding", "DownloadRateLimitPerTorrent"],
    type: "number",
    placeholder: "-1 (unlimited), 0 (disabled), or positive number",
  },
  {
    label: "Upload Rate Limit Per Torrent (KB/s)",
    path: ["CategorySeeding", "UploadRateLimitPerTorrent"],
    type: "number",
    placeholder: "-1 (unlimited), 0 (disabled), or positive number",
  },
  {
    label: "Hit and Run Mode",
    path: ["CategorySeeding", "HitAndRunMode"],
    type: "select",
    options: ["and", "or", "disabled"],
    format: (v: unknown) =>
      v === true ? "and" : v === false ? "disabled" : (v as string),
    parse: (v: string | boolean) =>
      typeof v === "string" ? v : v ? "and" : "disabled",
  },
  {
    label: "Min Seed Ratio",
    path: ["CategorySeeding", "MinSeedRatio"],
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
    path: ["CategorySeeding", "MinSeedingTimeDays"],
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
    path: ["CategorySeeding", "HitAndRunMinimumDownloadPercent"],
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
    path: ["CategorySeeding", "HitAndRunPartialSeedRatio"],
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
    path: ["CategorySeeding", "TrackerUpdateBuffer"],
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
  {
    label: "Stalled Delay",
    path: ["CategorySeeding", "StalledDelay"],
    type: "duration",
    nativeUnit: "minutes",
    allowNegative: true,
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
  {
    label: "Ignore Torrents Younger Than",
    path: ["CategorySeeding", "IgnoreTorrentsYoungerThan"],
    type: "duration",
    nativeUnit: "seconds",
    placeholder: "Seconds; stalled removal also requires last_activity older than this",
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Ignore Torrents Younger Than must be a non-negative duration.";
      }
      return undefined;
    },
  },
];

export const ARR_GENERAL_FIELDS: FieldDefinition[] = [
  { label: "Display Name", type: "text", placeholder: "Sonarr-TV", sectionName: true },
  { label: "Managed", path: ["Managed"], type: "checkbox" },
  {
    label: "URI",
    path: ["URI"],
    type: "text",
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
  {
    label: "API Key",
    path: ["APIKey"],
    type: "password",
    secure: true,
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
  {
    label: "Category",
    path: ["Category"],
    type: "text",
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
  {
    label: "Match subcategories (override)",
    path: ["MatchSubcategories"],
    type: "checkbox",
    description:
      "Optional. When set, overrides the qBit instance MatchSubcategories default for this Arr only (explicit true/false wins; omit to inherit from [qBit] / [qBit-*]).",
  },
  { label: "Re-search", path: ["ReSearch"], type: "checkbox" },
  {
    label: "Import Mode",
    path: ["importMode"],
    type: "select",
    options: IMPORT_MODE_OPTIONS,
    validate: (value, context) => {
      const managed = Boolean(getValue(context.section ?? {}, ["Managed"]));
      if (!managed) {
        return undefined;
      }
      if (isEmptyValue(value)) {
        return "Import Mode is required.";
      }
      return undefined;
    },
  },
  {
    label: "RSS Sync Timer",
    path: ["RssSyncTimer"],
    type: "duration",
    nativeUnit: "minutes",
    validate: (value) => {
      const total = parseDurationToMinutes(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "RSS Sync Timer must be a non-negative duration.";
      }
      return undefined;
    },
  },
  {
    label: "Refresh Downloads Timer",
    path: ["RefreshDownloadsTimer"],
    type: "duration",
    nativeUnit: "minutes",
    validate: (value) => {
      const total = parseDurationToMinutes(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Refresh Downloads Timer must be a non-negative duration.";
      }
      return undefined;
    },
  },
  {
    label: "Arr Error Codes To Blocklist",
    path: ["ArrErrorCodesToBlocklist"],
    type: "tags",
    fullWidth: true,
  },
];

export const ARR_ENTRY_SEARCH_FIELDS: FieldDefinition[] = [
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
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 1) {
        return "Search Limit must be at least 1.";
      }
      return undefined;
    },
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
    label: "Search Requests Every",
    path: ["EntrySearch", "SearchRequestsEvery"],
    type: "duration",
    nativeUnit: "seconds",
    validate: (value) => {
      const total = parseDurationToSeconds(value, 0);
      if (!Number.isFinite(total) || total < 1) {
        return "Search Requests Every must be at least 1 second.";
      }
      return undefined;
    },
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
    label: "Force Reset Temp Profiles",
    path: ["EntrySearch", "ForceResetTempProfiles"],
    type: "checkbox",
    description: "Reset all items using temp profiles to their original main profile on qBitrr startup",
  },
  {
    label: "Temp Profile Reset Timeout",
    path: ["EntrySearch", "TempProfileResetTimeoutMinutes"],
    type: "duration",
    nativeUnit: "minutes",
    description: "Timeout in minutes after which items with temp profiles are automatically reset to main profile (0 = disabled)",
  },
  {
    label: "Profile Switch Retry Attempts",
    path: ["EntrySearch", "ProfileSwitchRetryAttempts"],
    type: "number",
    description: "Number of retry attempts for profile switch API calls (default: 3)",
  },
  {
    label: "Search By Series",
    path: ["EntrySearch", "SearchBySeries"],
    type: "select",
    options: ["smart", "true", "false"],
    description: "smart = auto (series search for multiple episodes, episode search for single), true = always series search, false = always episode search",
    format: (value: unknown) => {
      // Convert boolean or string to string for display
      if (typeof value === "boolean") {
        return value ? "true" : "false";
      }
      return String(value || "smart");
    },
    parse: (value: string | boolean) => {
      // Keep as string for config - backend will handle parsing
      const str = String(value);
      if (str === "true" || str === "false") {
        return str;
      }
      return "smart";
    },
  },
  {
    label: "Prioritize Today's Releases",
    path: ["EntrySearch", "PrioritizeTodaysReleases"],
    type: "checkbox",
  },
];

export const ARR_ENTRY_SEARCH_OMBI_FIELDS: FieldDefinition[] = [
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
];

export const ARR_ENTRY_SEARCH_OVERSEERR_FIELDS: FieldDefinition[] = [
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

export const ARR_TORRENT_FIELDS: FieldDefinition[] = [
  {
    label: "Case Sensitive Matches",
    path: ["Torrent", "CaseSensitiveMatches"],
    type: "checkbox",
  },
  {
    label: "Folder Exclusion Regex",
    path: ["Torrent", "FolderExclusionRegex"],
    type: "tags",
    fullWidth: true,
  },
  {
    label: "File Name Exclusion Regex",
    path: ["Torrent", "FileNameExclusionRegex"],
    type: "tags",
    fullWidth: true,
  },
  {
    label: "File Extension Allowlist",
    path: ["Torrent", "FileExtensionAllowlist"],
    type: "tags",
    fullWidth: true,
  },
  {
    label: "Auto Delete",
    path: ["Torrent", "AutoDelete"],
    type: "checkbox",
  },
  {
    label: "Ignore Torrents Younger Than",
    path: ["Torrent", "IgnoreTorrentsYoungerThan"],
    type: "duration",
    nativeUnit: "seconds",
    validate: (value) => {
      const total = parseDurationToSeconds(value, -1);
      if (!Number.isFinite(total) || total < 0) {
        return "Ignore Torrents Younger Than must be a non-negative duration.";
      }
      return undefined;
    },
  },
  {
    label: "Maximum ETA",
    path: ["Torrent", "MaximumETA"],
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
    label: "Maximum Deletable Percentage",
    path: ["Torrent", "MaximumDeletablePercentage"],
    type: "number",
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
  {
    label: "Do Not Remove Slow",
    path: ["Torrent", "DoNotRemoveSlow"],
    type: "checkbox",
  },
  {
    label: "Stalled Delay",
    path: ["Torrent", "StalledDelay"],
    type: "duration",
    nativeUnit: "minutes",
    allowNegative: true,
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
  {
    label: "Re-search Stalled",
    path: ["Torrent", "ReSearchStalled"],
    type: "checkbox",
  },
];

export const ARR_SEEDING_FIELDS: FieldDefinition[] = [
  {
    label: "Download Rate Limit Per Torrent",
    path: ["Torrent", "SeedingMode", "DownloadRateLimitPerTorrent"],
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
    label: "Upload Rate Limit Per Torrent",
    path: ["Torrent", "SeedingMode", "UploadRateLimitPerTorrent"],
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
    path: ["Torrent", "SeedingMode", "MaxUploadRatio"],
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
    path: ["Torrent", "SeedingMode", "MaxSeedingTime"],
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
    label: "Remove Torrent (policy)",
    path: ["Torrent", "SeedingMode", "RemoveTorrent"],
    type: "select",
    options: REMOVE_TORRENT_OPTIONS,
    parse: (value: string | boolean) => {
      // Extract numeric value from option string like "Do not remove (-1)"
      const str = String(value);
      const match = str.match(/\((-?\d+)\)/);
      return match ? Number(match[1]) : -1;
    },
    format: (value: unknown) => {
      // Convert numeric value to option string
      const num = typeof value === "number" ? value : Number(value ?? -1);
      return REMOVE_TORRENT_OPTIONS.find(opt => opt.includes(`(${num})`)) || REMOVE_TORRENT_OPTIONS[0];
    },
  },
  {
    label: "Remove Dead Trackers",
    path: ["Torrent", "SeedingMode", "RemoveDeadTrackers"],
    type: "checkbox",
  },
  {
    label: "Remove Tracker Messages",
    path: ["Torrent", "SeedingMode", "RemoveTrackerWithMessage"],
    type: "tags",
    fullWidth: true,
  },
];

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
    if (isLidarr) {
      // Lidarr doesn't support SearchByYear (music albums don't have the same year-based search)
      if (joined === "EntrySearch.SearchByYear") {
        return false;
      }
    }
    return true;
  });
  // Ombi and Overseerr don't support music requests, so hide them for Lidarr
  const entryOmbiFields = isLidarr ? [] : [...ARR_ENTRY_SEARCH_OMBI_FIELDS];
  const entryOverseerrFields = isLidarr ? [] : [...ARR_ENTRY_SEARCH_OVERSEERR_FIELDS];
  const torrentFields = [...ARR_TORRENT_FIELDS];
  const seedingFields = [...ARR_SEEDING_FIELDS];
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
