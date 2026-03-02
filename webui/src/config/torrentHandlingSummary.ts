/**
 * Live summary text for how torrents are handled based on config state.
 * Used by ConfigView Arr and qBit instance modals; updates as the user edits (no save required).
 */

import { get } from "lodash-es";
import { parseDurationToSeconds, parseDurationToMinutes } from "./durationUtils";
import type { ConfigDocument } from "../api/types";

const REMOVE_TORRENT_LABELS: Record<number, string> = {
  [-1]: "Do not remove",
  1: "On max upload ratio",
  2: "On max seeding time",
  3: "On ratio OR time",
  4: "On ratio AND time",
};

function getVal<T = unknown>(state: ConfigDocument | null, path: string[], fallback: T): T {
  if (!state) return fallback;
  const v = get(state, path);
  return (v === undefined || v === null ? fallback : v) as T;
}

function plural(n: number, singular: string, pluralStr: string): string {
  return n === 1 ? singular : pluralStr;
}

function formatSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "disabled";
  if (seconds >= 86400) {
    const days = Math.round(seconds / 86400);
    return `${days} ${plural(days, "day", "days")}`;
  }
  if (seconds >= 3600) {
    const hours = Math.round(seconds / 3600);
    return `${hours} ${plural(hours, "hour", "hours")}`;
  }
  if (seconds >= 60) {
    const minutes = Math.round(seconds / 60);
    return `${minutes} ${plural(minutes, "minute", "minutes")}`;
  }
  const secs = Math.round(seconds);
  return `${secs} ${plural(secs, "second", "seconds")}`;
}

function formatMinutes(minutes: number): string {
  if (!Number.isFinite(minutes) || minutes < 0) return "disabled";
  if (minutes >= 1440) {
    const days = Math.round(minutes / 1440);
    return `${days} ${plural(days, "day", "days")}`;
  }
  if (minutes >= 60) {
    const hours = Math.round(minutes / 60);
    return `${hours} ${plural(hours, "hour", "hours")}`;
  }
  const mins = Math.round(minutes);
  return `${mins} ${plural(mins, "minute", "minutes")}`;
}

function resolveHnrMode(v: unknown): "and" | "or" | "disabled" {
  if (v === true) return "and";
  if (v === false) return "disabled";
  const s = String(v ?? "").toLowerCase();
  if (s === "and" || s === "or") return s;
  return "disabled";
}

function removeTorrentLabel(num: number): string {
  const n = Number(num);
  return REMOVE_TORRENT_LABELS[n] ?? "Do not remove";
}

function listPreview(arr: unknown[], maxItems = 3, suffix = "…"): string {
  if (!Array.isArray(arr) || arr.length === 0) return "";
  const parts = arr.slice(0, maxItems).map((x) => String(x).trim()).filter(Boolean);
  if (parts.length === 0) return "";
  const rest = arr.length > maxItems ? suffix : "";
  return parts.join(", ") + rest;
}

/** Build human-readable summary for an Arr instance section (Torrent, SeedingMode, Trackers). */
export function getArrTorrentHandlingSummary(state: ConfigDocument | null): string {
  if (!state || typeof state !== "object") {
    return "No torrent handling rules configured.";
  }

  const lines: string[] = [];

  const torrent = getVal<Record<string, unknown>>(state, ["Torrent"], {});
  const caseSensitive = Boolean(torrent.CaseSensitiveMatches);
  const folderExcl = Array.isArray(torrent.FolderExclusionRegex)
    ? (torrent.FolderExclusionRegex as string[]).length
    : 0;
  const fileExcl = Array.isArray(torrent.FileNameExclusionRegex)
    ? (torrent.FileNameExclusionRegex as string[]).length
    : 0;
  const allowlist = Array.isArray(torrent.FileExtensionAllowlist)
    ? (torrent.FileExtensionAllowlist as string[])
    : [];
  const allowlistPreview = listPreview(allowlist, 4);
  const autoDelete = Boolean(torrent.AutoDelete);
  const ignoreYounger = parseDurationToSeconds(torrent.IgnoreTorrentsYoungerThan, -1);
  const maxEta = parseDurationToSeconds(torrent.MaximumETA, -1);
  const maxDeletable = Number(torrent.MaximumDeletablePercentage);
  const doNotRemoveSlow = Boolean(torrent.DoNotRemoveSlow);
  const stalledDelayMin = parseDurationToMinutes(torrent.StalledDelay, -1);
  const reSearchStalled = Boolean(torrent.ReSearchStalled);

  // Torrent: 2–3 short lines
  const torrentParts: string[] = [];
  torrentParts.push(
    (caseSensitive ? "Case-sensitive" : "Case-insensitive") +
      (folderExcl || fileExcl ? `, ${folderExcl + fileExcl} exclusion(s)` : "") +
      (allowlistPreview ? `, allowlist ${allowlistPreview}` : ""),
  );
  const torrentOpts: string[] = [];
  torrentOpts.push(autoDelete ? "Auto-delete non-media: yes" : "Auto-delete non-media: no");
  if (Number.isFinite(ignoreYounger) && ignoreYounger >= 0) {
    torrentOpts.push(`Ignore new: ${formatSeconds(ignoreYounger)}`);
  }
  torrentOpts.push(maxEta >= 0 ? `Max ETA: ${formatSeconds(maxEta)}` : "Max ETA: off");
  if (Number.isFinite(maxDeletable) && maxDeletable <= 100) {
    torrentOpts.push(`Deletable up to: ${maxDeletable}%`);
  }
  torrentOpts.push(doNotRemoveSlow ? "Slow: kept" : "Slow: may remove");
  lines.push("Torrent: " + torrentParts.join("") + ".");
  lines.push(torrentOpts.join(". "));

  // Stalled: one short line
  if (!Number.isFinite(stalledDelayMin) || stalledDelayMin < 0) {
    lines.push("Stalled: Not removed.");
  } else if (stalledDelayMin === 0) {
    lines.push("Stalled: Not removed (infinite delay).");
  } else {
    lines.push(
      `Stalled: Removed after ${formatMinutes(stalledDelayMin)}. Re-search before remove: ${reSearchStalled ? "yes" : "no"}.`,
    );
  }

  const seeding = getVal<Record<string, unknown>>(state, ["Torrent", "SeedingMode"], {});
  const removeTorrent = Number(seeding.RemoveTorrent ?? -1);
  const maxRatio = Number(seeding.MaxUploadRatio ?? -1);
  const maxTimeSec = parseDurationToSeconds(seeding.MaxSeedingTime, -1);
  const removeDead = Boolean(seeding.RemoveDeadTrackers);
  const removeMessages = Array.isArray(seeding.RemoveTrackerWithMessage)
    ? (seeding.RemoveTrackerWithMessage as string[]).length
    : 0;

  // Seeding: one short line
  const seedParts: string[] = [removeTorrentLabel(removeTorrent)];
  if (Number.isFinite(maxRatio) && maxRatio >= 0) seedParts.push(`max ratio ${maxRatio}`);
  if (Number.isFinite(maxTimeSec) && maxTimeSec >= 0) {
    seedParts.push(`max time ${formatSeconds(maxTimeSec)}`);
  }
  seedParts.push(removeDead ? "Dead trackers: removed" : "Dead trackers: kept");
  if (removeMessages > 0) seedParts.push(`${removeMessages} message(s) trigger removal`);
  lines.push("Seeding: " + seedParts.join(". ") + ".");

  // HnR: one short line
  const hnrMode = resolveHnrMode(seeding.HitAndRunMode);
  const minRatio = Number(seeding.MinSeedRatio ?? 1);
  const minDays = Number(seeding.MinSeedingTimeDays ?? 0);
  if (hnrMode === "disabled") {
    lines.push("HnR: Off.");
  } else {
    const daysVal = Number.isFinite(minDays) ? minDays : 0;
    const daysLabel = plural(daysVal === 1 ? 1 : Math.max(0, daysVal), "day", "days");
    lines.push(
      `HnR: ${hnrMode} — min ratio ${Number.isFinite(minRatio) ? minRatio : 1}, min time ${daysVal} ${daysLabel}.`,
    );
  }

  const trackers = get(state, ["Torrent", "Trackers"]) as ConfigDocument[] | undefined;
  if (!Array.isArray(trackers) || trackers.length === 0) {
    lines.push("Trackers: No custom rules; using qBit instance defaults.");
  } else {
    lines.push("Trackers:");
    trackers.forEach((raw) => {
      const t = raw as Record<string, unknown>;
      const name = String(t.Name ?? "Tracker").trim() || "Tracker";
      const mode = resolveHnrMode(t.HitAndRunMode);
      const tMinRatio = Number(t.MinSeedRatio ?? 1);
      const tMinDays = Number(t.MinSeedingTimeDays ?? 0);
      const ratioStr = Number.isFinite(tMinRatio) ? tMinRatio : 1;
      const daysVal = Number.isFinite(tMinDays) ? tMinDays : 0;
      const daysLabel = plural(daysVal === 1 ? 1 : Math.max(0, daysVal), "day", "days");
      if (mode === "disabled") {
        lines.push(`  ${name} — HnR off`);
      } else {
        lines.push(`  ${name} — HnR ${mode}: ratio ${ratioStr}, ${daysVal} ${daysLabel}`);
      }
    });
  }

  return lines.join("\n\n");
}

/** Build human-readable summary for a qBit instance section (CategorySeeding, Trackers). */
export function getQbitTorrentHandlingSummary(state: ConfigDocument | null): string {
  if (!state || typeof state !== "object") {
    return "No torrent handling rules configured.";
  }

  const lines: string[] = [];
  const seeding = getVal<Record<string, unknown>>(state, ["CategorySeeding"], {});
  const managedCats = get(state, ["ManagedCategories"]) as string[] | undefined;
  const managedPreview =
    Array.isArray(managedCats) && managedCats.length > 0
      ? managedCats.slice(0, 3).join(", ") + (managedCats.length > 3 ? "…" : "")
      : "";

  const removeTorrent = Number(seeding.RemoveTorrent ?? -1);
  const maxRatio = Number(seeding.MaxUploadRatio ?? -1);
  const maxTimeSec = parseDurationToSeconds(seeding.MaxSeedingTime, -1);
  const dlLimit = Number(seeding.DownloadRateLimitPerTorrent ?? -1);
  const ulLimit = Number(seeding.UploadRateLimitPerTorrent ?? -1);

  // Seeding: one short line
  const seedParts: string[] = [removeTorrentLabel(removeTorrent)];
  if (Number.isFinite(maxRatio) && maxRatio >= 0) seedParts.push(`max ratio ${maxRatio}`);
  if (Number.isFinite(maxTimeSec) && maxTimeSec >= 0) {
    seedParts.push(`max time ${formatSeconds(maxTimeSec)}`);
  }
  seedParts.push(dlLimit >= 0 || ulLimit >= 0 ? "Rate limits: on" : "Rate limits: off");
  lines.push("Seeding: " + seedParts.join(". ") + ".");

  // Stalled: one short line
  const stalledDelayMin = parseDurationToMinutes(seeding.StalledDelay, -1);
  const ignoreYounger = parseDurationToSeconds(seeding.IgnoreTorrentsYoungerThan, -1);
  if (!Number.isFinite(stalledDelayMin) || stalledDelayMin < 0) {
    lines.push("Stalled: Not removed.");
  } else if (stalledDelayMin === 0) {
    let s = "Stalled: Not removed (infinite delay)";
    if (managedPreview) s += ` in ${managedPreview}`;
    if (Number.isFinite(ignoreYounger) && ignoreYounger >= 0) {
      s += `. Ignore new under ${formatSeconds(ignoreYounger)}`;
    }
    lines.push(s + ".");
  } else {
    let s = `Stalled: Removed after ${formatMinutes(stalledDelayMin)}`;
    if (managedPreview) s += ` in ${managedPreview}`;
    if (Number.isFinite(ignoreYounger) && ignoreYounger >= 0) {
      s += `. Ignore new under ${formatSeconds(ignoreYounger)}`;
    }
    lines.push(s + ".");
  }

  // HnR: one short line
  const hnrMode = resolveHnrMode(seeding.HitAndRunMode);
  const minRatio = Number(seeding.MinSeedRatio ?? 1);
  const minDays = Number(seeding.MinSeedingTimeDays ?? 0);
  if (hnrMode === "disabled") {
    lines.push("HnR: Off.");
  } else {
    const daysVal = Number.isFinite(minDays) ? minDays : 0;
    const daysLabel = plural(daysVal === 1 ? 1 : Math.max(0, daysVal), "day", "days");
    lines.push(
      `HnR: ${hnrMode} — min ratio ${Number.isFinite(minRatio) ? minRatio : 1}, min time ${daysVal} ${daysLabel}.`,
    );
  }

  const trackers = get(state, ["Trackers"]) as ConfigDocument[] | undefined;
  if (!Array.isArray(trackers) || trackers.length === 0) {
    lines.push("Trackers: No custom rules configured.");
  } else {
    lines.push("Trackers:");
    trackers.forEach((raw) => {
      const t = raw as Record<string, unknown>;
      const name = String(t.Name ?? "Tracker").trim() || "Tracker";
      const mode = resolveHnrMode(t.HitAndRunMode);
      const tMinRatio = Number(t.MinSeedRatio ?? 1);
      const tMinDays = Number(t.MinSeedingTimeDays ?? 0);
      const ratioStr = Number.isFinite(tMinRatio) ? tMinRatio : 1;
      const daysVal = Number.isFinite(tMinDays) ? tMinDays : 0;
      const daysLabel = plural(daysVal === 1 ? 1 : Math.max(0, daysVal), "day", "days");
      if (mode === "disabled") {
        lines.push(`  ${name} — HnR off`);
      } else {
        lines.push(`  ${name} — HnR ${mode}: ratio ${ratioStr}, ${daysVal} ${daysLabel}`);
      }
    });
  }

  return lines.join("\n\n");
}
