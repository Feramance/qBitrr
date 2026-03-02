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

function formatSeconds(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "disabled";
  if (seconds >= 86400 * 14) return `${Math.round(seconds / 86400)}d`;
  if (seconds >= 86400) return `${Math.round(seconds / 86400)}d`;
  if (seconds >= 3600) return `${Math.round(seconds / 3600)}h`;
  if (seconds >= 60) return `${Math.round(seconds / 60)}m`;
  return `${seconds}s`;
}

function formatMinutes(minutes: number): string {
  if (!Number.isFinite(minutes) || minutes < 0) return "disabled";
  if (minutes >= 1440) return `${Math.round(minutes / 1440)}d`;
  if (minutes >= 60) return `${Math.round(minutes / 60)}h`;
  return `${minutes}m`;
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

  lines.push(
    "Torrent: " +
      (caseSensitive ? "Case-sensitive" : "Case-insensitive") +
      " matches. " +
      (folderExcl || fileExcl
        ? `Folder/file name exclusions (${folderExcl + fileExcl} pattern(s)). `
        : "") +
      (allowlistPreview ? `Extension allowlist (${allowlistPreview}). ` : "") +
      `Auto-delete non-media ${autoDelete ? "on" : "off"}. ` +
      (Number.isFinite(ignoreYounger) && ignoreYounger >= 0
        ? `Ignore torrents younger than ${formatSeconds(ignoreYounger)}. `
        : "") +
      (maxEta >= 0 ? `Max ETA ${formatSeconds(maxEta)}. ` : "Max ETA disabled. ") +
      (Number.isFinite(maxDeletable) && maxDeletable <= 100
        ? `Deletable up to ${maxDeletable}%. `
        : "") +
      `Slow torrents ${doNotRemoveSlow ? "are not removed" : "may be removed"}.`
  );

  if (Number.isFinite(stalledDelayMin) && stalledDelayMin >= 0) {
    lines.push(
      "Stalled: After " +
        formatMinutes(stalledDelayMin) +
        " torrents are treated as stalled; re-search " +
        (reSearchStalled ? "enabled" : "disabled") +
        " before/after removal."
    );
  } else {
    lines.push("Stalled: Stalled handling disabled.");
  }

  const seeding = getVal<Record<string, unknown>>(state, ["Torrent", "SeedingMode"], {});
  const removeTorrent = Number(seeding.RemoveTorrent ?? -1);
  const maxRatio = Number(seeding.MaxUploadRatio ?? -1);
  const maxTimeSec = parseDurationToSeconds(seeding.MaxSeedingTime, -1);
  const removeDead = Boolean(seeding.RemoveDeadTrackers);
  const removeMessages = Array.isArray(seeding.RemoveTrackerWithMessage)
    ? (seeding.RemoveTrackerWithMessage as string[]).length
    : 0;

  lines.push(
    "Seeding: " +
      removeTorrentLabel(removeTorrent) +
      ". " +
      (Number.isFinite(maxRatio) && maxRatio >= 0 ? `Max ratio ${maxRatio}. ` : "") +
      (Number.isFinite(maxTimeSec) && maxTimeSec >= 0
        ? `Max time ${formatSeconds(maxTimeSec)}. `
        : "") +
      (removeDead ? "Dead trackers removed. " : "Dead trackers not removed. ") +
      (removeMessages > 0 ? `Specific tracker messages (${removeMessages}) trigger removal.` : "")
  );

  const hnrMode = resolveHnrMode(seeding.HitAndRunMode);
  const minRatio = Number(seeding.MinSeedRatio ?? 1);
  const minDays = Number(seeding.MinSeedingTimeDays ?? 0);
  lines.push(
    "HnR: " +
      (hnrMode === "disabled"
        ? "Disabled"
        : hnrMode === "and"
          ? "Require both ratio and time"
          : "Either ratio or time clears") +
      " in SeedingMode. Min ratio " +
      (Number.isFinite(minRatio) ? minRatio : "1") +
      ", min time " +
      (Number.isFinite(minDays) ? minDays : 0) +
      " days."
  );

  const trackers = get(state, ["Torrent", "Trackers"]) as ConfigDocument[] | undefined;
  const trackerCount = Array.isArray(trackers) ? trackers.length : 0;
  if (trackerCount === 0) {
    lines.push("Trackers: No per-tracker overrides; using qBit instance defaults.");
  } else {
    const withHnr = Array.isArray(trackers)
      ? trackers.filter((t) => resolveHnrMode((t as Record<string, unknown>).HitAndRunMode) !== "disabled").length
      : 0;
    const names = Array.isArray(trackers)
      ? trackers.map((t) => String((t as Record<string, unknown>).Name ?? "Tracker").trim()).filter(Boolean)
      : [];
    const namePreview = listPreview(names, 2);
    lines.push(
      `Trackers: ${trackerCount} override(s)${namePreview ? ` (e.g. ${namePreview})` : ""}. ` +
        (withHnr > 0 ? `${withHnr} with HnR rules.` : "HnR disabled on all.")
    );
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

  lines.push(
    "Seeding: " +
      removeTorrentLabel(removeTorrent) +
      (removeTorrent !== -1 ? ` (${removeTorrent}).` : ".") +
      " " +
      (Number.isFinite(maxRatio) && maxRatio >= 0 ? `Max ratio ${maxRatio}, ` : "") +
      (Number.isFinite(maxTimeSec) && maxTimeSec >= 0 ? `max time ${formatSeconds(maxTimeSec)}. ` : "") +
      (dlLimit >= 0 || ulLimit >= 0 ? "Rate limits set. " : "No per-torrent rate limits.")
  );

  const stalledDelayMin = parseDurationToMinutes(seeding.StalledDelay, -1);
  const ignoreYounger = parseDurationToSeconds(seeding.IgnoreTorrentsYoungerThan, -1);
  if (Number.isFinite(stalledDelayMin) && stalledDelayMin >= 0) {
    lines.push(
      "Stalled: Stalled downloads in managed categories" +
        (managedPreview ? ` (${managedPreview})` : "") +
        " are removed after " +
        formatMinutes(stalledDelayMin) +
        "; torrents younger than " +
        (Number.isFinite(ignoreYounger) && ignoreYounger >= 0 ? formatSeconds(ignoreYounger) : "—") +
        " are ignored."
    );
  }

  const hnrMode = resolveHnrMode(seeding.HitAndRunMode);
  const minRatio = Number(seeding.MinSeedRatio ?? 1);
  const minDays = Number(seeding.MinSeedingTimeDays ?? 0);
  const minDlPct = Number(seeding.HitAndRunMinimumDownloadPercent ?? 10);
  const partialRatio = Number(seeding.HitAndRunPartialSeedRatio ?? 1);
  lines.push(
    "HnR: " +
      (hnrMode === "disabled"
        ? "Disabled at category level"
        : hnrMode === "and"
          ? "Require both ratio and time"
          : "Either ratio or time clears") +
      ". Min ratio " +
      (Number.isFinite(minRatio) ? minRatio : "1") +
      ", min time " +
      (Number.isFinite(minDays) ? minDays : 0) +
      " days, min download % " +
      (Number.isFinite(minDlPct) ? minDlPct : 10) +
      ", partial ratio " +
      (Number.isFinite(partialRatio) ? partialRatio : "1") +
      "."
  );

  const trackers = get(state, ["Trackers"]) as ConfigDocument[] | undefined;
  const trackerCount = Array.isArray(trackers) ? trackers.length : 0;
  if (trackerCount === 0) {
    lines.push("Trackers: None configured.");
  } else {
    const withHnrAnd = Array.isArray(trackers)
      ? trackers.filter((t) => resolveHnrMode((t as Record<string, unknown>).HitAndRunMode) === "and").length
      : 0;
    const withHnrOr = Array.isArray(trackers)
      ? trackers.filter((t) => resolveHnrMode((t as Record<string, unknown>).HitAndRunMode) === "or").length
      : 0;
    const names = Array.isArray(trackers)
      ? trackers.map((t) => String((t as Record<string, unknown>).Name ?? "Tracker").trim()).filter(Boolean)
      : [];
    const namePreview = listPreview(names, 2);
    let trackerDesc = `${trackerCount} configured${namePreview ? ` (e.g. ${namePreview})` : ""}.`;
    if (withHnrAnd + withHnrOr > 0) {
      const parts: string[] = [];
      if (withHnrAnd) parts.push(`${withHnrAnd} with HnR "and" (ratio and time)`);
      if (withHnrOr) parts.push(`${withHnrOr} with HnR "or"`);
      trackerDesc += " " + parts.join("; ") + "; others with HnR disabled.";
    }
    lines.push("Trackers: " + trackerDesc);
  }

  return lines.join("\n\n");
}
