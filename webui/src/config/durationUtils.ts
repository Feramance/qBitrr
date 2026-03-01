/**
 * Duration parsing/formatting for config time values.
 * Supports integers (legacy) and suffixed strings (e.g. "1w", "60m").
 * Used by ConfigView duration fields and must match backend (duration_config.py).
 */

export type DurationUnit = "s" | "m" | "h" | "d" | "w" | "M";

const SUFFIX_TO_SECONDS: Record<string, number> = {
  s: 1,
  m: 60,
  h: 3600,
  d: 86400,
  w: 604800,
  M: 2592000, // 30 days
};

const SUFFIX_TO_MINUTES: Record<string, number> = {
  s: 1 / 60,
  m: 1,
  h: 60,
  d: 1440,
  w: 10080,
  M: 43200, // 30 days
};

const DURATION_PATTERN = /^\s*(-?\d+)\s*([smhdwM]?)\s*$/i;

export const DURATION_UNITS: { value: DurationUnit; label: string }[] = [
  { value: "s", label: "seconds" },
  { value: "m", label: "minutes" },
  { value: "h", label: "hours" },
  { value: "d", label: "days" },
  { value: "w", label: "weeks" },
  { value: "M", label: "months" },
];

function parseSuffixed(
  value: unknown,
  toSeconds: boolean,
  fallback: number
): number {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const s = String(value).trim();
  if (!s) return fallback;
  const m = s.match(DURATION_PATTERN);
  if (!m) {
    const n = Number(s);
    return Number.isFinite(n) ? n : fallback;
  }
  const num = parseInt(m[1], 10);
  const rawSuffix = (m[2] || (toSeconds ? "s" : "m")).trim();
  const suffix = rawSuffix === "M" ? "M" : rawSuffix.toLowerCase();
  const mult = toSeconds
    ? SUFFIX_TO_SECONDS[suffix] ?? 1
    : SUFFIX_TO_MINUTES[suffix] ?? 1;
  return num * mult;
}

export function parseDurationToSeconds(value: unknown, fallback = -1): number {
  return parseSuffixed(value, true, fallback);
}

export function parseDurationToMinutes(value: unknown, fallback = -1): number {
  return Math.floor(parseSuffixed(value, false, fallback));
}

function bestUnitForTotal(
  total: number,
  baseUnit: "seconds" | "minutes"
): DurationUnit {
  if (total < 0) return "s";
  const abs = Math.abs(total);
  const inSeconds = baseUnit === "seconds" ? abs : abs * 60;
  if (inSeconds >= 2592000) return "M";
  if (inSeconds >= 604800) return "w";
  if (inSeconds >= 86400) return "d";
  if (inSeconds >= 3600) return "h";
  if (inSeconds >= 60) return "m";
  return "s";
}

function totalToNumberAndUnit(
  total: number,
  baseUnit: "seconds" | "minutes"
): { number: number; unit: DurationUnit } {
  if (total < 0) return { number: -1, unit: "s" };
  const unit = bestUnitForTotal(total, baseUnit);
  const mult =
    baseUnit === "seconds"
      ? SUFFIX_TO_SECONDS[unit]
      : SUFFIX_TO_MINUTES[unit];
  const n = total / mult;
  return { number: Math.round(n * 100) / 100, unit };
}

function numberAndUnitToTotal(
  num: number,
  unit: DurationUnit,
  baseUnit: "seconds" | "minutes"
): number {
  const mult =
    baseUnit === "seconds"
      ? SUFFIX_TO_SECONDS[unit]
      : SUFFIX_TO_MINUTES[unit];
  return num * mult;
}

function toSuffixed(
  total: number,
  baseUnit: "seconds" | "minutes"
): string | number {
  if (total < 0) return -1;
  const unit = bestUnitForTotal(total, baseUnit);
  const mult =
    baseUnit === "seconds"
      ? SUFFIX_TO_SECONDS[unit]
      : SUFFIX_TO_MINUTES[unit];
  const n = Math.round(total / mult);
  if (unit === "s" && baseUnit === "seconds") return n;
  if (unit === "m" && baseUnit === "minutes") return n;
  return `${n}${unit}`;
}

export interface DurationDisplay {
  number: number;
  unit: DurationUnit;
  total: number;
}

export function parseDurationDisplay(
  value: unknown,
  baseUnit: "seconds" | "minutes",
  fallback = -1
): DurationDisplay {
  const total =
    baseUnit === "seconds"
      ? parseDurationToSeconds(value, fallback)
      : parseDurationToMinutes(value, fallback);
  const { number: n, unit } = totalToNumberAndUnit(total, baseUnit);
  return { number: n, unit, total };
}

export function durationDisplayToValue(
  number: number,
  unit: DurationUnit,
  baseUnit: "seconds" | "minutes",
  allowNegative: boolean
): string | number {
  if (allowNegative && number === -1) return -1;
  const total = numberAndUnitToTotal(number, unit, baseUnit);
  const out = toSuffixed(total, baseUnit);
  return typeof out === "number" ? out : out;
}
