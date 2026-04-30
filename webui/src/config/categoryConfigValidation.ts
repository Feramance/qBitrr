import type { ConfigDocument } from "../api/types";
import {
  categoryHasBackslash,
  findOverlapPairs,
  normalizeCategory,
} from "./categoryPaths";

const SERVARR_SECTION_REGEX = /(rad|son|lid)arr/i;
const QBIT_SECTION_REGEX = /^qBit(-.*)?$/i;

const BACKSLASH_MSG =
  "Backslashes are not qBittorrent subcategory separators; use '/' (forward slash).";

/** Same shape as ConfigView ValidationError for merging into validateFormState. */
export interface CategoryCrossSectionIssue {
  path: string[];
  message: string;
}

function appendUnique(bucket: Map<string, string[]>, normalized: string, sectionKey: string): void {
  if (!normalized) return;
  const arr = bucket.get(normalized);
  if (arr) {
    if (!arr.includes(sectionKey)) arr.push(sectionKey);
  } else {
    bucket.set(normalized, [sectionKey]);
  }
}

/**
 * Blocking validation: Arr-managed ∩ qBit-managed exact conflicts (matches startup rule),
 * and backslashes in category strings that qBit treats literally.
 */
export function getCategoryCrossSectionIssues(formState: ConfigDocument | null): CategoryCrossSectionIssue[] {
  const issues: CategoryCrossSectionIssue[] = [];
  if (!formState || typeof formState !== "object") return issues;

  const settings = formState.Settings as Record<string, unknown> | undefined;
  if (settings && typeof settings === "object") {
    const failed = settings.FailedCategory;
    const recheck = settings.RecheckCategory;
    if (categoryHasBackslash(failed)) {
      issues.push({
        path: ["Settings", "FailedCategory"],
        message: BACKSLASH_MSG,
      });
    }
    if (categoryHasBackslash(recheck)) {
      issues.push({
        path: ["Settings", "RecheckCategory"],
        message: BACKSLASH_MSG,
      });
    }
  }

  const arrByNormalized = new Map<string, string[]>();
  const qbitByNormalized = new Map<string, string[]>();

  for (const [sectionKey, rawSection] of Object.entries(formState)) {
    if (!rawSection || typeof rawSection !== "object") continue;

    if (SERVARR_SECTION_REGEX.test(sectionKey)) {
      const sec = rawSection as Record<string, unknown>;
      if (categoryHasBackslash(sec.Category)) {
        issues.push({
          path: [sectionKey, "Category"],
          message: BACKSLASH_MSG,
        });
      }
      const managed = Boolean(sec.Managed);
      if (managed) {
        const n = normalizeCategory(sec.Category);
        appendUnique(arrByNormalized, n, sectionKey);
      }
    }

    if (QBIT_SECTION_REGEX.test(sectionKey)) {
      const sec = rawSection as Record<string, unknown>;
      const mc = sec.ManagedCategories;
      if (Array.isArray(mc)) {
        const badTags = mc.filter((t) => categoryHasBackslash(t));
        if (badTags.length > 0) {
          issues.push({
            path: [sectionKey, "ManagedCategories"],
            message: `${BACKSLASH_MSG} Problem entries: ${badTags.map(String).join(", ")}.`,
          });
        }
        for (const tag of mc) {
          const n = normalizeCategory(tag);
          appendUnique(qbitByNormalized, n, sectionKey);
        }
      }
    }
  }

  for (const [normalized, arrKeys] of arrByNormalized) {
    const qKeys = qbitByNormalized.get(normalized);
    if (!normalized || !qKeys?.length) continue;
    const msg =
      `Category "${normalized}" cannot be managed by both an Arr instance and a qBit managed category. Assign it to one owner only.`;
    for (const arrKey of arrKeys) {
      issues.push({ path: [arrKey, "Category"], message: msg });
    }
    for (const qKey of qKeys) {
      issues.push({ path: [qKey, "ManagedCategories"], message: msg });
    }
  }

  return issues;
}

/** Non-blocking overlap hints (parent/child configured together); mirrors backend warnings. */
export function getCategoryOverlapWarnings(formState: ConfigDocument | null): string[] {
  if (!formState || typeof formState !== "object") return [];

  const union: string[] = [];

  for (const [sectionKey, rawSection] of Object.entries(formState)) {
    if (!rawSection || typeof rawSection !== "object") continue;

    if (SERVARR_SECTION_REGEX.test(sectionKey)) {
      const sec = rawSection as Record<string, unknown>;
      if (!sec.Managed) continue;
      const n = normalizeCategory(sec.Category);
      if (n) union.push(n);
    }

    if (QBIT_SECTION_REGEX.test(sectionKey)) {
      const sec = rawSection as Record<string, unknown>;
      const mc = sec.ManagedCategories;
      if (!Array.isArray(mc)) continue;
      for (const tag of mc) {
        const n = normalizeCategory(tag);
        if (n) union.push(n);
      }
    }
  }

  const pairs = findOverlapPairs(union);
  const lines = pairs.map(
    ([parent, child]) =>
      `'${child}' is nested under '${parent}'. With MatchSubcategories off, qBittorrent category filters are exact-match only — use full paths or enable prefix matching where appropriate.`
  );
  return [...new Set(lines)];
}
