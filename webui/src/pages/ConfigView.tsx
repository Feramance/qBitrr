import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import { getConfig, updateConfig } from "../api/client";
import type { ConfigDocument } from "../api/types";
import { useToast } from "../context/ToastContext";
import { getTooltip } from "../config/tooltips";
import { IconImage } from "../components/IconImage";
import ConfigureIcon from "../icons/cockpit.svg";
import ShowIcon from "../icons/motioneye.svg";
import RefreshIcon from "../icons/ddns-updater.svg";
import AddIcon from "../icons/openwebrx-plus.svg";
import SaveIcon from "../icons/healthchecks.svg";
import DeleteIcon from "../icons/immich-power-tools.svg";
import CloseIcon from "../icons/enclosed.svg";

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
}

interface ValidationError {
  path: string[];
  message: string;
}

const SERVARR_SECTION_REGEX = /(rad|son|anim)arr/i;

const parseList = (value: string | boolean): string[] =>
  String(value)
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);

const formatList = (value: unknown): string =>
  Array.isArray(value) ? value.join(", ") : String(value ?? "");

const IMPORT_MODE_OPTIONS = ["Move", "Copy", "Auto"];

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const DAY_NAMES = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

type CronFieldType = "minute" | "hour" | "dayOfMonth" | "month" | "dayOfWeek" | "year";

const CRON_FIELD_LABELS: Record<CronFieldType, { singular: string; plural: string }> = {
  minute: { singular: "minute", plural: "minutes" },
  hour: { singular: "hour", plural: "hours" },
  dayOfMonth: { singular: "day", plural: "days" },
  month: { singular: "month", plural: "months" },
  dayOfWeek: { singular: "day", plural: "days" },
  year: { singular: "year", plural: "years" },
};

const SENTENCE_END = /(.+?[.!?])(\s|$)/;

function extractTooltipSummary(tooltip?: string): string | undefined {
  if (!tooltip) return undefined;
  const trimmed = tooltip.trim();
  if (!trimmed) return undefined;
  const match = trimmed.match(SENTENCE_END);
  const sentence = match ? match[1] : trimmed;
  return sentence.length > 160 ? `${sentence.slice(0, 157)}…` : sentence;
}

function padTwo(value: number): string {
  return value.toString().padStart(2, "0");
}

function isNumeric(value: string): boolean {
  return /^-?\d+$/.test(value);
}

function formatOrdinal(value: string): string {
  if (!isNumeric(value)) return value;
  const num = Number(value);
  const abs = Math.abs(num);
  const mod100 = abs % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${value}th`;
  switch (abs % 10) {
    case 1:
      return `${value}st`;
    case 2:
      return `${value}nd`;
    case 3:
      return `${value}rd`;
    default:
      return `${value}th`;
  }
}

function formatCronToken(token: string, type: CronFieldType): string {
  const trimmed = token.trim();
  if (!trimmed) return "*";
  if (/^[A-Za-z#LW?]+$/.test(trimmed)) return trimmed;
  if (type === "month" && isNumeric(trimmed)) {
    const monthIndex = Number(trimmed);
    if (monthIndex >= 1 && monthIndex <= 12) {
      return MONTH_NAMES[monthIndex - 1];
    }
  }
  if (type === "dayOfWeek" && isNumeric(trimmed)) {
    const dayIndex = Number(trimmed) % 7;
    if (dayIndex >= 0 && dayIndex <= 6) {
      return DAY_NAMES[dayIndex];
    }
  }
  if (type === "dayOfMonth") {
    return formatOrdinal(trimmed);
  }
  return trimmed;
}

function describeCronField(value: string, type: CronFieldType): string {
  const trimmed = value.trim();
  if (!trimmed || trimmed === "*") {
    return `every ${CRON_FIELD_LABELS[type].plural}`;
  }
  if (trimmed === "?") {
    return `any ${CRON_FIELD_LABELS[type].singular}`;
  }
  if (trimmed.startsWith("*/")) {
    const step = trimmed.slice(2);
    return `every ${step} ${Number(step) === 1 ? CRON_FIELD_LABELS[type].singular : CRON_FIELD_LABELS[type].plural}`;
  }
  if (trimmed.includes("/")) {
    const [base, step] = trimmed.split("/");
    const baseDescription =
      !base || base === "*" ? `every ${CRON_FIELD_LABELS[type].plural}` : describeCronField(base, type);
    const stepSize = Number(step);
    const cadence =
      Number.isFinite(stepSize) && stepSize > 0
        ? `every ${step} ${stepSize === 1 ? CRON_FIELD_LABELS[type].singular : CRON_FIELD_LABELS[type].plural}`
        : `every ${step} units`;
    return `${baseDescription} (${cadence})`;
  }
  if (trimmed.includes(",")) {
    return trimmed
      .split(",")
      .map((part) => formatCronToken(part, type))
      .join(", ");
  }
  if (trimmed.includes("-")) {
    const [start, end] = trimmed.split("-");
    return `${formatCronToken(start, type)} to ${formatCronToken(end, type)}`;
  }
  return formatCronToken(trimmed, type);
}

function describeCronTime(minuteField: string, hourField: string): string {
  const minuteTrimmed = minuteField.trim();
  const hourTrimmed = hourField.trim();
  if ((minuteTrimmed === "*" || minuteTrimmed === "*/1") && hourTrimmed === "*") {
    return "Runs every minute";
  }
  if (hourTrimmed === "*" && minuteTrimmed.startsWith("*/")) {
    const step = minuteTrimmed.slice(2);
    return `Runs every ${step} minutes`;
  }
  if (hourTrimmed === "*" && isNumeric(minuteTrimmed)) {
    return `Runs at minute ${Number(minuteTrimmed)} each hour`;
  }
  if (isNumeric(hourTrimmed) && isNumeric(minuteTrimmed)) {
    return `Runs at ${padTwo(Number(hourTrimmed))}:${padTwo(Number(minuteTrimmed))}`;
  }
  const minuteDescription = describeCronField(minuteTrimmed, "minute");
  const hourDescription = describeCronField(hourTrimmed, "hour");
  return `Minutes: ${minuteDescription}; Hours: ${hourDescription}`;
}

function describeCronDay(dayOfMonthField: string, dayOfWeekField: string): string {
  const dom = dayOfMonthField.trim();
  const dow = dayOfWeekField.trim();
  const domWildcard = dom === "*" || dom === "?";
  const dowWildcard = dow === "*" || dow === "?";
  if (domWildcard && dowWildcard) {
    return "Every day";
  }
  const segments: string[] = [];
  if (!domWildcard) {
    segments.push(`Days of month: ${describeCronField(dom, "dayOfMonth")}`);
  }
  if (!dowWildcard) {
    segments.push(`Weekdays: ${describeCronField(dow, "dayOfWeek")}`);
  }
  return segments.join("; ");
}

function describeCron(expression: string): string {
  const parts = expression.trim().split(/\s+/).filter(Boolean);
  if (parts.length < 5 || parts.length > 6) {
    return "Enter 5 or 6 cron fields (minute hour day month weekday [year]).";
  }
  const [minute, hour, dayOfMonth, month, dayOfWeek, year] = [
    parts[0] ?? "*",
    parts[1] ?? "*",
    parts[2] ?? "*",
    parts[3] ?? "*",
    parts[4] ?? "*",
    parts[5],
  ];
  const timeDescription = describeCronTime(minute, hour);
  const dayDescription = describeCronDay(dayOfMonth, dayOfWeek);
  const monthDescription = month.trim() === "*" ? "Every month" : `Months: ${describeCronField(month, "month")}`;
  const pieces = [timeDescription, dayDescription, monthDescription];
  if (year) {
    pieces.push(`Years: ${describeCronField(year, "year")}`);
  }
  return pieces.join(" · ");
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
  {
    label: "WebUI Host",
    path: ["Settings", "WebUIHost"],
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
    path: ["Settings", "WebUIPort"],
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
    path: ["Settings", "WebUIToken"],
    type: "password",
    secure: true,
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
      SERVARR_SECTION_REGEX.test(key) && value && typeof value === "object"
    ) as Array<[string, ConfigDocument]>;
  }, [formState]);
  const groupedArrSections = useMemo(() => {
    const groups: Array<{
      label: string;
      type: "radarr" | "sonarr" | "other";
      items: Array<[string, ConfigDocument]>;
    }> = [];
    const sorted = [...arrSections].sort((a, b) =>
      a[0].localeCompare(b[0], undefined, { numeric: true, sensitivity: "base" })
    );
    const radarr: Array<[string, ConfigDocument]> = [];
    const sonarr: Array<[string, ConfigDocument]> = [];
    const others: Array<[string, ConfigDocument]> = [];
    for (const entry of sorted) {
      const [key] = entry;
      const keyLower = key.toLowerCase();
      if (keyLower.startsWith("radarr")) {
        radarr.push(entry);
      } else if (keyLower.startsWith("sonarr")) {
        sonarr.push(entry);
      } else {
        others.push(entry);
      }
    }
    if (radarr.length) {
      groups.push({ label: "Radarr Instances", type: "radarr", items: radarr });
    }
    if (sonarr.length) {
      groups.push({ label: "Sonarr Instances", type: "sonarr", items: sonarr });
    }
    if (others.length) {
      groups.push({ label: "Other Instances", type: "other", items: others });
    }
    return groups;
  }, [arrSections]);
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
  const deleteArrInstance = useCallback(
    (key: string) => {
      if (!formState) return;
      const keyLower = key.toLowerCase();
      if (!keyLower.startsWith("radarr") && !keyLower.startsWith("sonarr")) {
        return;
      }
      const confirmed = window.confirm(
        `Delete ${key}? This action cannot be undone.`
      );
      if (!confirmed) {
        return;
      }
      const next = cloneConfig(formState) ?? {};
      if (!(key in next)) {
        return;
      }
      delete next[key];
      setFormState(next);
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
                    </summary>
                    <div className="config-arr-grid">
                      {group.items.map(([key, value]) => {
                        const uri = getValue(value as ConfigDocument, ["URI"]);
                        const category = getValue(value as ConfigDocument, ["Category"]);
                        const managed = getValue(value as ConfigDocument, ["Managed"]);
                        const canDelete = group.type === "radarr" || group.type === "sonarr";
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
            <div className="config-actions">
              <button
                className="btn"
                type="button"
                onClick={() => addArrInstance("radarr")}
              >
                <IconImage src={AddIcon} />
                Add Radarr Instance
              </button>
              <button
                className="btn"
                type="button"
                onClick={() => addArrInstance("sonarr")}
              >
                <IconImage src={AddIcon} />
                Add Sonarr Instance
              </button>
            </div>
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

interface CronDescriptorProps {
  expression: string;
}

function CronDescriptor({ expression }: CronDescriptorProps): JSX.Element {
  const readable = useMemo(() => describeCron(expression), [expression]);
  return (
    <p className="field-hint" role="status" aria-live="polite">
      {readable}
    </p>
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
    const key = path.join('.');
    const rawValue = field.path
      ? getValue(state as ConfigDocument, field.path as string[])
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

    const descriptionNode = description ? (
      <p className="field-description">{description}</p>
    ) : null;
    const cronDescriptorNode =
      key === 'Settings.AutoUpdateCron' ? (
        <CronDescriptor expression={String(formatted)} />
      ) : null;

    if (field.type === "checkbox") {
      return (
        <label className="checkbox-field" key={key}>
          <input
            type="checkbox"
            checked={Boolean(formatted)}
            onChange={(event) => onChange(path, field, event.target.checked)}
          />
          <span className="checkbox-field__content">
            <span className="checkbox-field__text">
              {field.label}
              {tooltip ? (
                <span className="help-icon" title={tooltip} aria-label={tooltip}>
                  ?
                </span>
              ) : null}
            </span>
            {description ? (
              <span className="field-description">{description}</span>
            ) : null}
          </span>
        </label>
      );
    }
    if (field.type === "select") {
      return (
        <div className="field" key={key}>
          <label className="field-label">
            <span>{field.label}</span>
            {tooltip ? (
              <span className="help-icon" title={tooltip} aria-label={tooltip}>
                ?
              </span>
            ) : null}
          </label>
          {descriptionNode}
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
          {cronDescriptorNode}
        </div>
      );
    }
    return (
      <div className="field" key={key}>
        <label className="field-label">
          <span>{field.label}</span>
          {tooltip ? (
            <span className="help-icon" title={tooltip} aria-label={tooltip}>
              ?
            </span>
          ) : null}
        </label>
        {descriptionNode}
        <input
          type={field.type === "number" ? "number" : field.type}
          value={String(formatted)}
          placeholder={field.placeholder}
          onChange={(event) => onChange(path, field, event.target.value)}
        />
        {cronDescriptorNode}
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
      {description ? <p className="field-description">{description}</p> : null}
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
            {revealed ? <IconImage src={ShowIcon} className="icon-rotate" /> : <IconImage src={ShowIcon} />}
            <span>{revealed ? "Hide" : "Show"}</span>
          </button>
          {canRefresh ? (
            <button type="button" className="btn ghost" onClick={handleRefresh}>
              <IconImage src={RefreshIcon} />
              Refresh
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

interface ArrInstanceModalProps {
  keyName: string;
  state: ConfigDocument | ConfigDocument[keyof ConfigDocument] | null;
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
            <IconImage src={CloseIcon} />
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
            <IconImage src={SaveIcon} />
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
