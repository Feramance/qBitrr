import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { produce } from "immer";
import equal from "fast-deep-equal";
import { get, set } from "lodash-es";
import { getConfig, updateConfig, testArrConnection, type TestConnectionResponse } from "../api/client";
import type { ConfigDocument } from "../api/types";
import { useToast } from "../context/ToastContext";
import { useWebUI } from "../context/WebUIContext";
import { getTooltip } from "../config/tooltips";
import { IconImage } from "../components/IconImage";
import Select from "react-select";
import ConfigureIcon from "../icons/gear.svg";

import RefreshIcon from "../icons/refresh-arrow.svg";
import VisibilityIcon from "../icons/visibility.svg";
import AddIcon from "../icons/plus.svg";
import SaveIcon from "../icons/check-mark.svg";
import DeleteIcon from "../icons/trash.svg";
import CloseIcon from "../icons/close.svg";

type FieldType = "text" | "number" | "checkbox" | "password" | "select";

interface ValidationContext {
  root: ConfigDocument;
  section?: ConfigDocument | null;
  sectionKey?: string;
}

type FieldValidator = (value: unknown, context: ValidationContext) => string | undefined;

interface FieldDefinition {
  label: string;
  path?: string[];
  type: FieldType;
  options?: string[];
  placeholder?: string;
  description?: string;
  parse?: (value: string | boolean) => unknown;
  format?: (value: unknown) => string | boolean;
  sectionName?: boolean;
  secure?: boolean;
  required?: boolean;
  validate?: FieldValidator;
  fullWidth?: boolean;
}

interface ValidationError {
  path: string[];
  message: string;
}

const SERVARR_SECTION_REGEX = /(rad|son|anim|lid)arr/i;

// Helper function for react-select theme-aware styles
const getSelectStyles = () => {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  return {
    control: (base: any) => ({
      ...base,
      background: isDark ? '#0f131a' : '#ffffff',
      color: isDark ? '#eaeef2' : '#1d1d1f',
      borderColor: isDark ? '#2a2f36' : '#d2d2d7',
      minHeight: '38px',
      boxShadow: 'none',
      '&:hover': {
        borderColor: isDark ? '#3a4149' : '#b8b8bd',
      }
    }),
    menu: (base: any) => ({
      ...base,
      background: isDark ? '#0f131a' : '#ffffff',
      borderColor: isDark ? '#2a2f36' : '#d2d2d7',
      border: `1px solid ${isDark ? '#2a2f36' : '#d2d2d7'}`,
    }),
    option: (base: any, state: any) => ({
      ...base,
      background: state.isFocused
        ? (isDark ? 'rgba(122, 162, 247, 0.15)' : 'rgba(0, 113, 227, 0.1)')
        : (isDark ? '#0f131a' : '#ffffff'),
      color: isDark ? '#eaeef2' : '#1d1d1f',
      '&:active': {
        background: isDark ? 'rgba(122, 162, 247, 0.25)' : 'rgba(0, 113, 227, 0.2)',
      }
    }),
    singleValue: (base: any) => ({
      ...base,
      color: isDark ? '#eaeef2' : '#1d1d1f',
    }),
    input: (base: any) => ({
      ...base,
      color: isDark ? '#eaeef2' : '#1d1d1f',
    }),
    placeholder: (base: any) => ({
      ...base,
      color: isDark ? '#9aa3ac' : '#6e6e73',
    }),
    menuList: (base: any) => ({
      ...base,
      padding: '4px',
    }),
  };
};

const parseList = (value: string | boolean): string[] =>
  String(value)
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);

const formatList = (value: unknown): string =>
  Array.isArray(value) ? value.join(", ") : String(value ?? "");

const IMPORT_MODE_OPTIONS = ["Move", "Copy", "Auto"];







const SENTENCE_END = /(.+?[.!?])(\s|$)/;

function extractTooltipSummary(tooltip?: string): string | undefined {
  if (!tooltip) return undefined;
  const trimmed = tooltip.trim();
  if (!trimmed) return undefined;
  const match = trimmed.match(SENTENCE_END);
  const sentence = match ? match[1] : trimmed;
  return sentence.length > 160 ? `${sentence.slice(0, 157)}…` : sentence;
}





const SETTINGS_FIELDS: FieldDefinition[] = [
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
    label: "No Internet Sleep (s)",
    path: ["Settings", "NoInternetSleepTimer"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "No Internet Sleep must be a non-negative number.";
      }
      return undefined;
    },
  },
  {
    label: "Loop Sleep (s)",
    path: ["Settings", "LoopSleepTimer"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Loop Sleep must be a non-negative number.";
      }
      return undefined;
    },
  },
  {
    label: "Search Loop Delay (s)",
    path: ["Settings", "SearchLoopDelay"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Search Loop Delay must be a non-negative number.";
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
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Ignore Torrents Younger Than must be a non-negative number.";
      }
      return undefined;
    },
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

];

const WEB_SETTINGS_FIELDS: FieldDefinition[] = [
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
];

const QBIT_FIELDS: FieldDefinition[] = [
  { label: "Disabled", path: ["qBit", "Disabled"], type: "checkbox" },
  {
    label: "Host",
    path: ["qBit", "Host"],
    type: "text",
    required: true,
    validate: (value) => {
      if (!String(value ?? "").trim()) {
        return "qBit Host is required.";
      }
      return undefined;
    },
  },
  {
    label: "Port",
    path: ["qBit", "Port"],
    type: "number",
    validate: (value) => {
      const port = typeof value === "number" ? value : Number(value);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        return "qBit Port must be between 1 and 65535.";
      }
      return undefined;
    },
  },
  { label: "UserName", path: ["qBit", "UserName"], type: "text" },
  { label: "Password", path: ["qBit", "Password"], type: "password" },
];

const ARR_GENERAL_FIELDS: FieldDefinition[] = [
  { label: "Display Name", type: "text", placeholder: "Sonarr-TV", sectionName: true },
  { label: "Managed", path: ["Managed"], type: "checkbox" },
  {
    label: "URI",
    path: ["URI"],
    type: "text",
    placeholder: "http://host:port",
    required: true,
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
    required: true,
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
    required: true,
    validate: (value) => {
      if (!String(value ?? "").trim()) {
        return "Category is required.";
      }
      return undefined;
    },
  },
  { label: "Re-search", path: ["ReSearch"], type: "checkbox" },
  {
    label: "Import Mode",
    path: ["importMode"],
    type: "select",
    options: IMPORT_MODE_OPTIONS,
    required: true,
  },
  {
    label: "RSS Sync Timer (min)",
    path: ["RssSyncTimer"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "RSS Sync Timer must be a non-negative number.";
      }
      return undefined;
    },
  },
  {
    label: "Refresh Downloads Timer (min)",
    path: ["RefreshDownloadsTimer"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Refresh Downloads Timer must be a non-negative number.";
      }
      return undefined;
    },
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
    label: "Search Requests Every (s)",
    path: ["EntrySearch", "SearchRequestsEvery"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 1) {
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
    label: "Temp Profile Reset Timeout (Minutes)",
    path: ["EntrySearch", "TempProfileResetTimeoutMinutes"],
    type: "number",
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
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Ignore Torrents Younger Than must be a non-negative number.";
      }
      return undefined;
    },
  },
  {
    label: "Maximum ETA (s)",
    path: ["Torrent", "MaximumETA"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < -1) {
        return "Maximum ETA must be -1 or a non-negative number.";
      }
      return undefined;
    },
  },
  {
    label: "Maximum Deletable Percentage",
    path: ["Torrent", "MaximumDeletablePercentage"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0 || num > 100) {
        return "Maximum Deletable Percentage must be between 0 and 100.";
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
    label: "Stalled Delay (min)",
    path: ["Torrent", "StalledDelay"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < 0) {
        return "Stalled Delay must be a non-negative number.";
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

const ARR_SEEDING_FIELDS: FieldDefinition[] = [
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
    label: "Max Seeding Time (s)",
    path: ["Torrent", "SeedingMode", "MaxSeedingTime"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < -1) {
        return "Max Seeding Time must be -1 or greater.";
      }
      return undefined;
    },
  },
  {
    label: "Remove Torrent (policy)",
    path: ["Torrent", "SeedingMode", "RemoveTorrent"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num)) {
        return "Remove Torrent policy must be a number.";
      }
      if (num === -1) {
        return undefined;
      }
      if (![1, 2, 3, 4].includes(num)) {
        return "Remove Torrent policy must be -1, 1, 2, 3, or 4.";
      }
      return undefined;
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
    type: "text",
    parse: parseList,
    format: formatList,
    fullWidth: true,
  },
];

const ARR_TRACKER_FIELDS: FieldDefinition[] = [
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
    label: "Maximum ETA",
    path: ["MaximumETA"],
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < -1) {
        return "Maximum ETA must be -1 or a non-negative number.";
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
    type: "number",
    validate: (value) => {
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num) || num < -1) {
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
    type: "text",
    parse: parseList,
    format: formatList,
  },
];

function getArrFieldSets(arrKey: string) {
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

function isEmptyValue(value: unknown): boolean {
  return (
    value === null ||
    value === undefined ||
    (typeof value === "string" && value.trim() === "") ||
    (Array.isArray(value) && value.length === 0)
  );
}

function basicValidation(def: FieldDefinition, value: unknown): string | undefined {
  const label = def.label;
  const isRequired = def.required ?? (def.type === "number" || def.type === "select");
  switch (def.type) {
    case "text":
    case "password": {
      if (!isRequired) {
        return undefined;
      }
      if (isEmptyValue(value)) {
        return `${label} is required.`;
      }
      return undefined;
    }
    case "number": {
      if (value === null || value === undefined || value === "") {
        return isRequired ? `${label} is required.` : undefined;
      }
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num)) {
        return `${label} must be a valid number.`;
      }
      return undefined;
    }
    case "checkbox": {
      if (value === null || value === undefined) {
        return isRequired ? `${label} is required.` : undefined;
      }
      if (typeof value !== "boolean") {
        return `${label} must be true or false.`;
      }
      return undefined;
    }
    case "select": {
      if (isEmptyValue(value)) {
        return `${label} is required.`;
      }
      if (typeof value !== "string") {
        return `${label} must be selected.`;
      }
      if (def.options && !def.options.includes(value)) {
        return `${label} must be one of ${def.options.join(", ")}.`;
      }
      return undefined;
    }
    default:
      return undefined;
  }
}

function validateFieldGroup(
  errors: ValidationError[],
  fields: FieldDefinition[],
  state: ConfigDocument | null,
  basePath: string[],
  context: ValidationContext
): void {
  if (!state) return;
  for (const field of fields) {
    if (field.sectionName) {
      continue;
    }
    const pathSegments = field.path ?? [];
    const value = pathSegments.length
      ? getValue(state as ConfigDocument, pathSegments)
      : undefined;
    const fullPath = [...basePath, ...pathSegments];
    const baseError = basicValidation(field, value);
    if (baseError) {
      errors.push({ path: fullPath, message: baseError });
      continue;
    }
    if (field.validate) {
      const customError = field.validate(value, context);
      if (customError) {
        errors.push({ path: fullPath, message: customError });
      }
    }
  }
}

function validateFormState(formState: ConfigDocument | null): ValidationError[] {
  if (!formState) return [];
  const errors: ValidationError[] = [];
  const rootContext: ValidationContext = { root: formState };
  validateFieldGroup(errors, SETTINGS_FIELDS, formState, [], rootContext);
  validateFieldGroup(errors, WEB_SETTINGS_FIELDS, formState, [], rootContext);
  validateFieldGroup(errors, QBIT_FIELDS, formState, [], rootContext);
  for (const [key, value] of Object.entries(formState)) {
    if (!SERVARR_SECTION_REGEX.test(key) || !value || typeof value !== "object") {
      continue;
    }
    const section = value as ConfigDocument;
    const sectionContext: ValidationContext = { root: formState, section, sectionKey: key };
    const fieldSets = getArrFieldSets(key);
    validateFieldGroup(errors, fieldSets.generalFields, section, [key], sectionContext);
    validateFieldGroup(errors, fieldSets.entryFields, section, [key], sectionContext);
    validateFieldGroup(errors, fieldSets.entryOmbiFields, section, [key], sectionContext);
    validateFieldGroup(errors, fieldSets.entryOverseerrFields, section, [key], sectionContext);
    validateFieldGroup(errors, fieldSets.torrentFields, section, [key], sectionContext);
    validateFieldGroup(errors, fieldSets.seedingFields, section, [key], sectionContext);
  }
  return errors;
}

// Note: cloneConfig is no longer needed - using immer's produce for immutable updates

// Utility wrappers around lodash for ConfigDocument operations
function getValue(doc: ConfigDocument | null, path: string[]): unknown {
  if (!doc) return undefined;
  return get(doc, path);
}

function setValue(
  doc: ConfigDocument,
  path: string[],
  value: unknown
): void {
  set(doc, path, value);
}

// Custom flatten to create dot-notation keys (e.g., "Settings.FreeSpace")
// Note: lodash's flatten is for arrays; this is a specialized object flattener
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
  const isLidarr = lowerType.includes("lidarr");

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
    : [
        "Not a preferred word upgrade for existing episode file(s)",
        "Not an upgrade for existing episode file(s)",
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
    ForceResetTempProfiles: false,
    TempProfileResetTimeoutMinutes: 0,
    ProfileSwitchRetryAttempts: 3,
    QualityProfileMappings: {},
  };

  if (isSonarr) {
    entrySearch.AlsoSearchSpecials = false;
    entrySearch.SearchBySeries = "smart";
    entrySearch.PrioritizeTodaysReleases = true;
  }

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
    FileExtensionAllowlist: isLidarr
      ? [".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".ape", ".wma", ".!qB", ".parts", ".log", ".cue"]
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
      // Deep clone config for form state (immer will handle immutability from here)
      setFormState(config ? JSON.parse(JSON.stringify(config)) : null);
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
    (path: string[], def: FieldDefinition, raw: unknown) => {
      if (!formState) return;
      const parsed =
        def.parse?.(raw as string | boolean) ??
        (def.type === "number"
          ? Number(raw) || 0
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
    // Always show Radarr, Sonarr, and Lidarr sections even if empty
    groups.push({ label: "Radarr Instances", type: "radarr", items: radarr });
    groups.push({ label: "Sonarr Instances", type: "sonarr", items: sonarr });
    groups.push({ label: "Lidarr Instances", type: "lidarr", items: lidarr });
    if (others.length) {
      groups.push({ label: "Other Instances", type: "other", items: others });
    }
    return groups;
  }, [arrSections]);
  const [activeArrKey, setActiveArrKey] = useState<string | null>(null);
  const [isSettingsOpen, setSettingsOpen] = useState(false);
  const [isWebSettingsOpen, setWebSettingsOpen] = useState(false);
  const [isQbitOpen, setQbitOpen] = useState(false);
  const [isDirty, setDirty] = useState(false);

  useEffect(() => {
    if (!formState || !originalConfig) {
      setDirty(false);
      return;
    }
    const flattenedOriginal = flatten(originalConfig);
    const flattenedCurrent = flatten(formState);

    // Keys that are managed dynamically and should not trigger dirty state
    const liveKeys = new Set([
      "WebUI.LiveArr",
      "WebUI.GroupSonarr",
      "WebUI.GroupLidarr",
      "WebUI.Theme",
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
    const anyModalOpen = Boolean(activeArrKey || isSettingsOpen || isWebSettingsOpen || isQbitOpen);
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
  }, [activeArrKey, isSettingsOpen, isWebSettingsOpen, isQbitOpen]);

  useEffect(() => {
    if (!activeArrKey) return;
    if (!arrSections.some(([key]) => key === activeArrKey)) {
      setActiveArrKey(null);
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
      const validationErrors = validateFormState(formState);
      if (validationErrors.length) {
        const formatted = validationErrors
          .map((error) => `${error.path.join(".")}: ${error.message}`)
          .join("\n");
        const message =
          validationErrors.length === 1
            ? formatted
            : `Please resolve the following issues:\n${formatted}`;
        push(message, "error");
        setSaving(false);
        return;
      }
      const flattenedOriginal = flatten(originalConfig ?? {});
      const flattenedCurrent = flatten(formState);
      const changes: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(flattenedCurrent)) {
        const originalValue = flattenedOriginal[key];
        // Use fast-deep-equal for accurate comparison
        if (!equal(value, originalValue)) {
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
      const { configReloaded, reloadType, affectedInstances } = await updateConfig({ changes });

      // Build appropriate success message
      let message = "Configuration saved";
      if (reloadType === "full") {
        message += " • All instances reloaded";
      } else if (reloadType === "multi_arr" && affectedInstances?.length) {
        message += ` • Reloaded ${affectedInstances.length} instances: ${affectedInstances.join(", ")}`;
      } else if (reloadType === "single_arr" && affectedInstances?.length) {
        message += ` • Reloaded: ${affectedInstances.join(", ")}`;
      } else if (reloadType === "webui") {
        message += " • WebUI restarting...";
      } else if (reloadType === "frontend") {
        message += " • Theme/display settings updated";
      }
      push(message, "success");

      // Only clear browser cache if backend reloaded (non-frontend-only changes)
      if (configReloaded && 'caches' in window) {
        try {
          const cacheNames = await caches.keys();
          await Promise.all(
            cacheNames.map(cacheName => caches.delete(cacheName))
          );
        } catch (error) {
          console.warn('Failed to clear caches:', error);
        }
      }

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
                  description="Web UI configuration"
                  onConfigure={() => setWebSettingsOpen(true)}
                />
                <ConfigSummaryCard
                  title="qBit"
                  description="qBittorrent connection details"
                  onConfigure={() => setQbitOpen(true)}
                />
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
                        const canDelete = group.type === "radarr" || group.type === "sonarr" || group.type === "lidarr";
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
                                {canDelete ? (
                                  <button
                                    className="btn danger"
                                    type="button"
                                    onClick={() => deleteArrInstance(key)}
                                  >
                                    <IconImage src={DeleteIcon} />
                                    Delete
                                  </button>
                                ) : null}
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
          <div className="config-footer">
            <button
              className="btn primary"
              onClick={() => void handleSubmit()}
              disabled={saving}
            >
              <IconImage src={SaveIcon} />
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
      {isWebSettingsOpen ? (
        <SimpleConfigModal
          title="Web Settings"
          fields={WEB_SETTINGS_FIELDS}
          state={formState}
          basePath={[]}
          onChange={handleFieldChange}
          onClose={() => setWebSettingsOpen(false)}
          showLiveSettings={true}
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
            <IconImage src={ConfigureIcon} />
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
  onChange: (path: string[], def: FieldDefinition, value: unknown) => void;
  onRenameSection?: (oldName: string, newName: string) => void;
  defaultOpen?: boolean;
  qualityProfiles?: Array<{ id: number; name: string }>;
}

function FieldGroup({
  title,
  fields,
  state,
  basePath,
  onChange,
  onRenameSection,
  defaultOpen = false,
  qualityProfiles = [],
}: FieldGroupProps): JSX.Element {
  const sectionName = basePath[0] ?? "";

  if (title === "Quality Profile Mappings") {
    const mappings = (getValue(state as ConfigDocument, ["EntrySearch", "QualityProfileMappings"]) ?? {}) as Record<string, string>;
    const mappingEntries = Object.entries(mappings);

    // Check if credentials exist (URI and APIKey)
    const hasCredentials = Boolean(
      getValue(state as ConfigDocument, ["URI"]) &&
        getValue(state as ConfigDocument, ["APIKey"])
    );
    const hasProfiles = qualityProfiles.length > 0;

    const handleAddMapping = () => {
      const nextMappings = { ...mappings, "": "" };
      onChange([...basePath, "EntrySearch", "QualityProfileMappings"], {} as FieldDefinition, nextMappings);
    };

    const handleUpdateMapping = (oldKey: string, newKey: string, newValue: string) => {
      const nextMappings = { ...mappings };
      if (oldKey !== newKey) {
        delete nextMappings[oldKey];
      }
      if (newKey.trim()) {
        nextMappings[newKey.trim()] = newValue.trim();
      }
      onChange([...basePath, "EntrySearch", "QualityProfileMappings"], {} as FieldDefinition, nextMappings);
    };

    const handleDeleteMapping = (key: string) => {
      const nextMappings = { ...mappings };
      delete nextMappings[key];
      onChange([...basePath, "EntrySearch", "QualityProfileMappings"], {} as FieldDefinition, nextMappings);
    };

    return (
      <details className="config-section" open={defaultOpen}>
        <summary>{title}</summary>
        <div className="config-section__body">
          <div className="field-description" style={{ marginBottom: '1rem' }}>
            Map main quality profile names to temporary profile names. Items will be downgraded to the temp profile when not found, then upgraded back to the main profile when available.
          </div>

          {!hasCredentials ? (
            <div className="alert warning">
              ⚠️ Please configure URI and API Key first, then click "Test Connection" to load quality profiles
            </div>
          ) : !hasProfiles ? (
            <div className="alert info">
              ℹ️ Click "Test Connection" above to load quality profiles from your {sectionName} instance
            </div>
          ) : (
            <>
              <div className="profile-mappings-grid">
                {mappingEntries.map(([mainProfile, tempProfile], index) => (
                  <div key={index} className="profile-mapping-row">
                    <div className="field">
                      <label>Main Profile</label>
                      <Select
                        options={qualityProfiles.map((p) => ({
                          value: p.name,
                          label: p.name,
                        }))}
                        value={
                          mainProfile
                            ? { value: mainProfile, label: mainProfile }
                            : null
                        }
                        onChange={(option) =>
                          handleUpdateMapping(
                            mainProfile,
                            option?.value || "",
                            tempProfile
                          )
                        }
                        placeholder="Select main profile..."
                        isClearable
                        styles={getSelectStyles()}
                        classNamePrefix="react-select"
                      />
                    </div>
                    <div className="field">
                      <label>Temp Profile</label>
                      <Select
                        options={qualityProfiles.map((p) => ({
                          value: p.name,
                          label: p.name,
                        }))}
                        value={
                          tempProfile
                            ? { value: tempProfile, label: tempProfile }
                            : null
                        }
                        onChange={(option) =>
                          handleUpdateMapping(
                            mainProfile,
                            mainProfile,
                            option?.value || ""
                          )
                        }
                        placeholder="Select temp profile..."
                        isClearable
                        styles={getSelectStyles()}
                        classNamePrefix="react-select"
                      />
                    </div>
                    <button
                      className="btn ghost icon-only"
                      type="button"
                      onClick={() => handleDeleteMapping(mainProfile)}
                      title="Delete mapping"
                    >
                      <IconImage src={DeleteIcon} />
                    </button>
                  </div>
                ))}
              </div>
              <div className="config-actions">
                <button className="btn" type="button" onClick={handleAddMapping}>
                  <IconImage src={AddIcon} />
                  Add Profile Mapping
                </button>
              </div>
            </>
          )}
        </div>
      </details>
    );
  }

  if (title === "Trackers") {
    const trackers = (getValue(state as ConfigDocument, ["Torrent", "Trackers"]) ?? []) as ConfigDocument[];
    const handleAddTracker = () => {
      const nextTrackers = [
        ...trackers,
        {
          Url: "",
          RemoveIfExists: false,
          SuperSeedMode: false,
          AddTags: [],
        },
      ];
      onChange([...basePath, "Torrent", "Trackers"], {} as FieldDefinition, nextTrackers);
    };
    const handleDeleteTracker = (index: number) => {
      const nextTrackers = [...trackers];
      nextTrackers.splice(index, 1);
      onChange([...basePath, "Torrent", "Trackers"], {} as FieldDefinition, nextTrackers);
    };
    return (
      <details className="config-section" open={defaultOpen}>
        <summary>{title}</summary>
        <div className="config-section__body">
          <div className="tracker-grid">
            {trackers.map((tracker, index) => (
              <TrackerCard
                key={index}
                fields={fields}
                state={tracker}
                basePath={[...basePath, "Torrent", "Trackers", String(index)]}
                onChange={onChange}
                onDelete={() => handleDeleteTracker(index)}
              />
            ))}
          </div>
          <div className="config-actions">
            <button className="btn" type="button" onClick={handleAddTracker}>
              <IconImage src={AddIcon} />
              Add Tracker
            </button>
          </div>
        </div>
      </details>
    );
  }

  const renderedFields = fields.map((field) => {
    if (field.sectionName) {
      if (!sectionName) {
        return null;
      }
      const tooltip = getTooltip([sectionName]);

      // Determine expected prefix for Arr instances
      let expectedPrefix: string | undefined;
      if (sectionName.startsWith("Radarr")) {
        expectedPrefix = "Radarr";
      } else if (sectionName.startsWith("Sonarr")) {
        expectedPrefix = "Sonarr";
      } else if (sectionName.startsWith("Lidarr")) {
        expectedPrefix = "Lidarr";
      }

      return (
        <SectionNameField
          key={`${sectionName}.__name`}
          label={field.label}
          tooltip={tooltip}
          currentName={sectionName}
          placeholder={field.placeholder}
          expectedPrefix={expectedPrefix}
          onRename={(newName) => onRenameSection?.(sectionName, newName)}
        />
      );
    }

    const pathSegments = field.path ?? [];
    const path = [...basePath, ...pathSegments];
    const key = path.join('.');
    const rawValue = path.length > 0
      ? getValue(state as ConfigDocument, path)
      : undefined;
    const formatted =
      field.format?.(rawValue) ??
      (field.type === "checkbox" ? Boolean(rawValue) : String(rawValue ?? ""));
    const tooltip = getTooltip(path);
    const description =
      field.description ??
      extractTooltipSummary(tooltip) ??
      (field.type === "checkbox"
        ? `Enable or disable ${field.label}.`
        : `Set the ${field.label} value.`);

    const isArrInstance = basePath.length > 0 && SERVARR_SECTION_REGEX.test(basePath[0] ?? "");
    const isArrApiKey = isArrInstance && (field.path?.[field.path.length - 1] ?? "") === "APIKey";
    const fieldClassName = field.fullWidth ? "field field--full-width" : "field";

    if (field.secure) {
      return (
        <SecureField
          key={key}
          label={field.label}
          tooltip={tooltip}
          description={description}
          value={String(rawValue ?? '')}
          placeholder={field.placeholder}
          canRefresh={!isArrApiKey}
          onChange={(val) => onChange(path, field, val)}
        />
      );
    }



    if (field.type === "checkbox") {
      return (
        <div key={key} className="checkbox-field">
          <label title={tooltip}>
            <input
              type="checkbox"
              checked={Boolean(formatted)}
              onChange={(event) => onChange(path, field, event.target.checked)}
            />
            {field.label}
          </label>
          {description && <div className="field-description">{description}</div>}
        </div>
      );
    }
    if (field.type === "select") {
      // Special handling for Theme field - apply immediately without save
      const isThemeField = field.label === "Theme" && path.join('.') === "WebUI.Theme";

      // Normalize the formatted value for theme field (case-insensitive)
      let displayValue = formatted;
      if (isThemeField && typeof formatted === "string") {
        const normalizedLower = formatted.toLowerCase();
        if (normalizedLower === "light") {
          displayValue = "Light";
        } else if (normalizedLower === "dark") {
          displayValue = "Dark";
        } else {
          // Default to Dark if invalid
          displayValue = "Dark";
        }
      }

      return (
        <div key={key} className={fieldClassName}>
          <label title={tooltip}>{field.label}</label>
          <Select
            options={(field.options ?? []).map(o => ({ value: o, label: o }))}
            value={displayValue ? { value: displayValue, label: displayValue } : null}
            onChange={(option) => {
              const newValue = option?.value || "";
              onChange(path, field, newValue);

              // If this is the theme field, apply immediately
              if (isThemeField && typeof newValue === "string" && newValue) {
                const theme = newValue.toLowerCase() as "light" | "dark";
                document.documentElement.setAttribute('data-theme', theme);
                localStorage.setItem("theme", theme);
              }
            }}
            styles={getSelectStyles()}
          />
          {description && <div className="field-description">{description}</div>}
          {isThemeField && <div className="field-hint">Theme changes apply immediately</div>}
        </div>
      );
    }
    if (field.type === "number") {
      return (
        <div key={key} className={fieldClassName}>
          <label title={tooltip}>{field.label}</label>
          <input
            type="number"
            value={Number(formatted) || 0}
            onChange={(event) => onChange(path, field, String(event.target.value))}
            placeholder={field.placeholder}
          />
          {description && <div className="field-description">{description}</div>}
        </div>
      );
    }
    if (field.type === "password") {
      return (
        <div key={key} className={fieldClassName}>
          <label title={tooltip}>{field.label}</label>
          <input
            type="password"
            value={String(formatted)}
            onChange={(event) => onChange(path, field, event.target.value)}
            placeholder={field.placeholder}
          />
          {description && <div className="field-description">{description}</div>}
        </div>
      );
    }
    return (
      <div key={key} className={fieldClassName}>
        <label title={tooltip}>{field.label}</label>
        <input
          type="text"
          value={String(formatted)}
          onChange={(event) => onChange(path, field, event.target.value)}
          placeholder={field.placeholder}
        />
        {description && <div className="field-description">{description}</div>}
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

function TrackerCard({
  fields,
  state,
  basePath,
  onChange,
  onDelete,
}: {
  fields: FieldDefinition[];
  state: ConfigDocument | null;
  basePath: string[];
  onChange: (path: string[], def: FieldDefinition, value: unknown) => void;
  onDelete: () => void;
}): JSX.Element {
  const trackerName = (getValue(state, ["Name"]) as string) || "New Tracker";
  return (
    <details className="card tracker-card" open>
      <summary className="card-header">
        <span>{trackerName}</span>
        <button className="btn danger ghost" type="button" onClick={onDelete}>
          <IconImage src={DeleteIcon} />
        </button>
      </summary>
      <div className="card-body">
        <FieldGroup title={null} fields={fields} state={state} basePath={basePath} onChange={onChange} />
      </div>
    </details>
  );
}

interface SectionNameFieldProps {
  label: string;
  currentName: string;
  placeholder?: string;
  tooltip?: string;
  expectedPrefix?: string;
  onRename: (newName: string) => void;
}

function SectionNameField({
  label,
  currentName,
  placeholder,
  tooltip,
  expectedPrefix,
  onRename,
}: SectionNameFieldProps): JSX.Element {
  const [value, setValue] = useState(currentName);
  const description =
    extractTooltipSummary(tooltip) ?? `Rename the ${currentName} instance.`;

  useEffect(() => {
    setValue(currentName);
  }, [currentName]);

  const commit = () => {
    const trimmed = value.trim();
    if (!trimmed) {
      setValue(currentName);
      return;
    }

    let adjustedName = trimmed;

    // Enforce prefix if specified
    if (expectedPrefix && !trimmed.startsWith(expectedPrefix)) {
      // If user entered something without the prefix, prepend it
      adjustedName = expectedPrefix + (trimmed.startsWith("-") ? trimmed : `-${trimmed}`);
    }

    if (adjustedName !== currentName) {
      onRename(adjustedName);
    } else {
      setValue(currentName); // Reset if no actual change
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
      {description ? <p className="field-description">{description}</p> : null}
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
  description?: string;
  canRefresh?: boolean;
  onChange: (value: string) => void;
}

function SecureField({
  label,
  value,
  placeholder,
  tooltip,
  description,
  canRefresh = true,
  onChange,
}: SecureFieldProps): JSX.Element {
  const [showValue, setShowValue] = useState(false);

  const handleRefresh = () => {
    let newKey = "";
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      newKey = crypto.randomUUID().replace(/-/g, "");
    } else {
      newKey = Array.from({ length: 32 }, () =>
        Math.floor(Math.random() * 16).toString(16)
      ).join("");
    }
    onChange(newKey);
  };

  return (
    <div className="field secure-field">
      <label title={tooltip}>{label}</label>
      <div className="secure-field__input-group">
        <input
          type={showValue ? "text" : "password"}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
        <button type="button" className="btn ghost" onClick={() => setShowValue(!showValue)}>
          <IconImage src={VisibilityIcon} />
        </button>
        {canRefresh && (
          <button type="button" className="btn ghost" onClick={handleRefresh}>
            <IconImage src={RefreshIcon} />
          </button>
        )}
      </div>
      {description && <div className="field-description">{description}</div>}
    </div>
  );
}

interface ArrInstanceModalProps {
  keyName: string;
  state: ConfigDocument | ConfigDocument[keyof ConfigDocument] | null;
  onChange: (path: string[], def: FieldDefinition, value: unknown) => void;
  onRename: (oldName: string, newName: string) => void;
  onClose: () => void;
}

function ArrInstanceModal({
  keyName,
  state,
  onChange,
  onRename,
  onClose,
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

  // Helper to get value from state
  const getValue = (path: string[]): unknown => {
    if (!state) return undefined;
    // state is already the Arr instance object, not the full ConfigDocument
    return get(state, path);
  };

  // Clear test state when URI or APIKey changes
  useEffect(() => {
    setTestState({ testing: false, result: null });
    setQualityProfiles([]);
  }, [getValue(["URI"]), getValue(["APIKey"])]);

  // Auto-test connection when modal opens if credentials exist
  useEffect(() => {
    const uri = getValue(["URI"]) as string;
    const apiKey = getValue(["APIKey"]) as string;

    if (uri && apiKey && !testState.testing && !testState.result) {
      // Auto-test silently (without toasts)
      handleTestConnection(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run on mount

  // Test connection handler
  const handleTestConnection = async (silent = false) => {
    const uri = getValue(["URI"]) as string;
    const apiKey = getValue(["APIKey"]) as string;

    // Determine Arr type from keyName
    const keyLower = keyName.toLowerCase();
    const arrType = keyLower.includes("radarr")
      ? "radarr"
      : keyLower.includes("sonarr")
        ? "sonarr"
        : "lidarr";

    if (!uri || !apiKey) {
      if (!silent) {
        push("Please configure URI and API Key first", "error");
      }
      return false;
    }

    setTestState({ testing: true, result: null });

    try {
      const result = await testArrConnection({ arrType, uri, apiKey });
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
  };

  // Handle save with connection test
  const handleSave = async () => {
    const uri = getValue(["URI"]) as string;
    const apiKey = getValue(["APIKey"]) as string;

    // If credentials exist, test connection before saving
    if (uri && apiKey) {
      const success = await handleTestConnection(false);
      if (success) {
        push("Configuration saved successfully", "success");
        onClose();
      }
      // If unsuccessful, stay open so user can fix config
    } else {
      // No credentials to test, just close
      onClose();
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
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
          <button className="btn ghost" type="button" onClick={onClose}>
            <IconImage src={CloseIcon} />
            Close
          </button>
        </div>
        <div className="modal-body">
          <FieldGroup
            title={null}
            fields={generalFields}
            state={state}
            basePath={[keyName]}
            onChange={onChange}
            onRenameSection={onRename}
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
            basePath={[keyName]}
            onChange={onChange}
            defaultOpen
          />
          <FieldGroup
            title="Quality Profile Mappings"
            fields={[]}
            state={state}
            basePath={[keyName]}
            onChange={onChange}
            defaultOpen
            qualityProfiles={qualityProfiles}
          />
          {entryOmbiFields.length > 0 && (
            <FieldGroup
              title="Ombi Integration"
              fields={entryOmbiFields}
              state={state}
              basePath={[keyName]}
              onChange={onChange}
            />
          )}
          {entryOverseerrFields.length > 0 && (
            <FieldGroup
              title="Overseerr Integration"
              fields={entryOverseerrFields}
              state={state}
              basePath={[keyName]}
              onChange={onChange}
            />
          )}
          <FieldGroup
            title="Torrent Handling"
            fields={torrentFields}
            state={state}
            basePath={[keyName]}
            onChange={onChange}
          />
          <FieldGroup
            title="Seeding"
            fields={seedingFields}
            state={state}
            basePath={[keyName]}
            onChange={onChange}
          />
          <FieldGroup
            title="Trackers"
            fields={trackerFields}
            state={state}
            basePath={[keyName]}
            onChange={onChange}
          />
        </div>
        <div className="modal-footer">
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
          <button className="btn primary" type="button" onClick={handleSave}>
            <IconImage src={SaveIcon} />
            Save
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
  onChange: (path: string[], def: FieldDefinition, value: unknown) => void;
  onClose: () => void;
  showLiveSettings?: boolean;
}

function SimpleConfigModal({
  title,
  fields,
  state,
  basePath,
  onChange,
  onClose,
  showLiveSettings = false,
}: SimpleConfigModalProps): JSX.Element | null {
  const webUI = useWebUI();

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
                  <label>
                    <input
                      type="checkbox"
                      checked={webUI.groupSonarr}
                      onChange={(e) => webUI.setGroupSonarr(e.target.checked)}
                    />
                    {" "}Group Sonarr by Series
                  </label>
                  <p className="field-description">Group Sonarr episodes by series in views</p>
                </div>
                <div className="field">
                  <label>
                    <input
                      type="checkbox"
                      checked={webUI.groupLidarr}
                      onChange={(e) => webUI.setGroupLidarr(e.target.checked)}
                    />
                    {" "}Group Lidarr by Artist
                  </label>
                  <p className="field-description">Group Lidarr albums by artist in views</p>
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
        </div>
        <div className="modal-footer">
          <button className="btn primary" type="button" onClick={onClose}>
            <IconImage src={SaveIcon} />
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
