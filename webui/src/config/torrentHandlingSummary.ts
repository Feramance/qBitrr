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

  lines.push(
    "Torrent: " +
      (caseSensitive ? "Case-sensitive" : "Case-insensitive") +
      " matches. " +
      (folderExcl || fileExcl
        ? `Folder or file name exclusions (${folderExcl + fileExcl} pattern(s)). `
        : "") +
      (allowlistPreview ? `Allowed file types include ${allowlistPreview}. ` : "") +
      (autoDelete
        ? "Files that are not recognised as media are automatically deleted. "
        : "Files that are not recognised as media are kept. ") +
      (Number.isFinite(ignoreYounger) && ignoreYounger >= 0
        ? `New torrents are ignored for the first ${formatSeconds(ignoreYounger)}. `
        : "") +
      (maxEta >= 0
        ? `Torrents with an estimated time remaining longer than ${formatSeconds(maxEta)} are treated as stuck and may be cleaned up. `
        : "No maximum ETA; torrents are not treated as stuck based on their estimated time remaining. ") +
      (Number.isFinite(maxDeletable) && maxDeletable <= 100
        ? `Torrents may be removed when completion is at or below ${maxDeletable}%. `
        : "") +
      `Slow torrents ${doNotRemoveSlow ? "are not removed" : "may be removed"}.`
  );

  if (!Number.isFinite(stalledDelayMin) || stalledDelayMin < 0) {
    lines.push("Stalled: Stalled handling is disabled.");
  } else if (stalledDelayMin === 0) {
    lines.push(
      "Stalled: Torrents that qBittorrent marks as stalled are not removed automatically (stall delay is infinite)."
    );
  } else {
    lines.push(
      "Stalled: Torrents that qBittorrent has already marked as stalled are allowed to sit for up to " +
        formatMinutes(stalledDelayMin) +
        " before qBitrr removes them. " +
        (reSearchStalled
          ? "qBitrr will search again for a replacement before removing the stalled torrent."
          : "qBitrr will remove stalled torrents without performing a replacement search first.")
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

  lines.push(
    "Seeding: " +
      removeTorrentLabel(removeTorrent) +
      ". " +
      (Number.isFinite(maxRatio) && maxRatio >= 0
        ? `Maximum upload ratio (uploaded ÷ downloaded): ${maxRatio}. `
        : "") +
      (Number.isFinite(maxTimeSec) && maxTimeSec >= 0
        ? `Maximum seeding time: ${formatSeconds(maxTimeSec)}. `
        : "") +
      (removeDead
        ? "Trackers that no longer respond are removed. "
        : "Trackers that no longer respond are not removed. ") +
      (removeMessages > 0
        ? `Removal is triggered when the tracker shows any of ${removeMessages} specific message(s).`
        : "")
  );

  const hnrMode = resolveHnrMode(seeding.HitAndRunMode);
  const minRatio = Number(seeding.MinSeedRatio ?? 1);
  const minDays = Number(seeding.MinSeedingTimeDays ?? 0);
  lines.push(
    "Hit and Run (HnR): " +
      (hnrMode === "disabled"
        ? "Disabled. (No minimum seeding required before removal; torrents are removed based only on seeding limits and stalled/failed checks.)"
        : hnrMode === "and"
          ? "Tracker rules require both a minimum ratio and minimum seeding time before removal is allowed."
          : "Tracker rules allow removal once either the minimum ratio or minimum seeding time is met.") +
      (hnrMode !== "disabled"
        ? ` Minimum ratio: ${Number.isFinite(minRatio) ? minRatio : "1"}. Minimum seeding time: ${Number.isFinite(minDays) ? minDays : 0} ${plural(Number.isFinite(minDays) && minDays === 1 ? 1 : Math.max(0, minDays), "day", "days")}. Torrents will not be removed for seeding limits or stalled status until these HnR thresholds are met (except when the tracker itself bypasses HnR, such as unregistered torrents).`
        : "")
  );

  const trackers = get(state, ["Torrent", "Trackers"]) as ConfigDocument[] | undefined;
  const trackerCount = Array.isArray(trackers) ? trackers.length : 0;
  if (trackerCount === 0) {
    lines.push("Trackers: No custom rules; using qBit instance defaults.");
  } else {
    lines.push("Trackers:");
    (trackers as ConfigDocument[]).forEach((raw) => {
      const t = raw as Record<string, unknown>;
      const nameRaw = String((t as Record<string, unknown>).Name ?? "Tracker").trim();
      const name = nameRaw || "Tracker";
      const mode = resolveHnrMode((t as Record<string, unknown>).HitAndRunMode);
      const tMinRatio = Number((t as Record<string, unknown>).MinSeedRatio ?? 1);
      const tMinDays = Number((t as Record<string, unknown>).MinSeedingTimeDays ?? 0);
      const tMinDlPct = Number(
        (t as Record<string, unknown>).HitAndRunMinimumDownloadPercent ?? 10,
      );
      const tPartialRatio = Number(
        (t as Record<string, unknown>).HitAndRunPartialSeedRatio ?? 1,
      );

      let desc = `- ${name}: `;
      if (mode === "disabled") {
        desc +=
          "HnR disabled; torrents with this tracker can be removed based on seeding limits and stalled/failed checks only.";
      } else if (mode === "and") {
        desc +=
          "HnR enabled; torrents with this tracker will not be removed until both the minimum ratio and minimum seeding time are met, even if they are stalled or hit other remove conditions.";
      } else {
        desc +=
          "HnR enabled; torrents with this tracker will not be removed until either the minimum ratio or minimum seeding time is met, even if they are stalled or hit other remove conditions.";
      }

      if (mode !== "disabled") {
        const ratioStr = Number.isFinite(tMinRatio) ? tMinRatio : 1;
        const daysVal = Number.isFinite(tMinDays) ? tMinDays : 0;
        const daysLabel = plural(
          Number.isFinite(daysVal) && daysVal === 1 ? 1 : Math.max(0, daysVal),
          "day",
          "days",
        );
        const dlPctStr = Number.isFinite(tMinDlPct) ? tMinDlPct : 10;
        const partialStr = Number.isFinite(tPartialRatio) ? tPartialRatio : 1;

        desc += ` Minimum ratio: ${ratioStr}. Minimum seeding time: ${daysVal} ${daysLabel}. Minimum download: ${dlPctStr}%. Partial-download ratio: ${partialStr}.`;
      }

      lines.push(desc);
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

  lines.push(
    "Seeding: " +
      removeTorrentLabel(removeTorrent) +
      ". " +
      (Number.isFinite(maxRatio) && maxRatio >= 0
        ? `Maximum upload ratio (uploaded ÷ downloaded): ${maxRatio}. `
        : "") +
      (Number.isFinite(maxTimeSec) && maxTimeSec >= 0
        ? `Maximum seeding time: ${formatSeconds(maxTimeSec)}. `
        : "") +
      (dlLimit >= 0 || ulLimit >= 0 ? "Rate limits set. " : "No per-torrent rate limits.")
  );

  const stalledDelayMin = parseDurationToMinutes(seeding.StalledDelay, -1);
  const ignoreYounger = parseDurationToSeconds(seeding.IgnoreTorrentsYoungerThan, -1);
  if (!Number.isFinite(stalledDelayMin) || stalledDelayMin < 0) {
    lines.push("Stalled: Stalled download cleanup is disabled for managed categories.");
  } else if (stalledDelayMin === 0) {
    lines.push(
      "Stalled: Downloads that qBittorrent marks as stalled in managed categories" +
        (managedPreview ? ` (${managedPreview})` : "") +
        " are not removed automatically (stall delay is infinite)." +
        (Number.isFinite(ignoreYounger) && ignoreYounger >= 0
          ? ` Torrents younger than ${formatSeconds(ignoreYounger)} are ignored when checking for stalled downloads.`
          : ""),
    );
  } else {
    lines.push(
      "Stalled: Downloads that qBittorrent marks as stalled in managed categories" +
        (managedPreview ? ` (${managedPreview})` : "") +
        " can sit for up to " +
        formatMinutes(stalledDelayMin) +
        " before qBitrr removes them." +
        (Number.isFinite(ignoreYounger) && ignoreYounger >= 0
          ? ` Torrents younger than ${formatSeconds(ignoreYounger)} are ignored when checking for stalled downloads.`
          : ""),
    );
  }

  const hnrMode = resolveHnrMode(seeding.HitAndRunMode);
  const minRatio = Number(seeding.MinSeedRatio ?? 1);
  const minDays = Number(seeding.MinSeedingTimeDays ?? 0);
  const minDlPct = Number(seeding.HitAndRunMinimumDownloadPercent ?? 10);
  const partialRatio = Number(seeding.HitAndRunPartialSeedRatio ?? 1);
  lines.push(
    "Hit and Run (HnR): " +
      (hnrMode === "disabled"
        ? "Disabled at category level. (No minimum seeding required before removal; torrents are removed based only on seeding limits and stalled/failed checks.)"
        : hnrMode === "and"
          ? "Tracker rules require both a minimum ratio and minimum seeding time before removal is allowed."
          : "Tracker rules allow removal once either the minimum ratio or minimum seeding time is met.") +
      (hnrMode !== "disabled"
        ? ` Minimum ratio: ${Number.isFinite(minRatio) ? minRatio : "1"}. Minimum seeding time: ${Number.isFinite(minDays) ? minDays : 0} ${plural(Number.isFinite(minDays) && minDays === 1 ? 1 : Math.max(0, minDays), "day", "days")}. Minimum download: ${Number.isFinite(minDlPct) ? minDlPct : 10}%. Partial-seed ratio: ${Number.isFinite(partialRatio) ? partialRatio : "1"}. Torrents will not be removed for seeding limits or stalled status until these HnR thresholds are met (except when the tracker itself bypasses HnR, such as unregistered torrents).`
        : "")
  );

  const trackers = get(state, ["Trackers"]) as ConfigDocument[] | undefined;
  const trackerCount = Array.isArray(trackers) ? trackers.length : 0;
  if (trackerCount === 0) {
    lines.push("Trackers: No custom rules configured.");
  } else {
    lines.push("Trackers:");
    (trackers as ConfigDocument[]).forEach((raw) => {
      const t = raw as Record<string, unknown>;
      const nameRaw = String((t as Record<string, unknown>).Name ?? "Tracker").trim();
      const name = nameRaw || "Tracker";
      const mode = resolveHnrMode((t as Record<string, unknown>).HitAndRunMode);
      const tMinRatio = Number((t as Record<string, unknown>).MinSeedRatio ?? 1);
      const tMinDays = Number((t as Record<string, unknown>).MinSeedingTimeDays ?? 0);
      const tMinDlPct = Number(
        (t as Record<string, unknown>).HitAndRunMinimumDownloadPercent ?? 10,
      );
      const tPartialRatio = Number(
        (t as Record<string, unknown>).HitAndRunPartialSeedRatio ?? 1,
      );

      let desc = `- ${name}: `;
      if (mode === "disabled") {
        desc +=
          "HnR disabled; torrents with this tracker can be removed based on seeding limits and stalled/failed checks only.";
      } else if (mode === "and") {
        desc +=
          "HnR enabled; torrents with this tracker will not be removed until both the minimum ratio and minimum seeding time are met, even if they are stalled or hit other remove conditions.";
      } else {
        desc +=
          "HnR enabled; torrents with this tracker will not be removed until either the minimum ratio or minimum seeding time is met, even if they are stalled or hit other remove conditions.";
      }

      if (mode !== "disabled") {
        const ratioStr = Number.isFinite(tMinRatio) ? tMinRatio : 1;
        const daysVal = Number.isFinite(tMinDays) ? tMinDays : 0;
        const daysLabel = plural(
          Number.isFinite(daysVal) && daysVal === 1 ? 1 : Math.max(0, daysVal),
          "day",
          "days",
        );
        const dlPctStr = Number.isFinite(tMinDlPct) ? tMinDlPct : 10;
        const partialStr = Number.isFinite(tPartialRatio) ? tPartialRatio : 1;

        desc += ` Minimum ratio: ${ratioStr}. Minimum seeding time: ${daysVal} ${daysLabel}. Minimum download: ${dlPctStr}%. Partial-download ratio: ${partialStr}.`;
      }

      lines.push(desc);
    });
  }

  return lines.join("\n\n");
}
