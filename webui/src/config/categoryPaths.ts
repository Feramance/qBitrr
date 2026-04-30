/**
 * Category path helpers aligned with `qBitrr/category_paths.py`.
 * Keep behaviour in sync when changing normalisation or overlap rules.
 */

const CATEGORY_SEPARATOR = "/";

/** Canonical form: trim, collapse repeated `/`, drop empty segments. */
export function normalizeCategory(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  const s = String(value).trim();
  if (!s) {
    return "";
  }
  const parts = s.split(CATEGORY_SEPARATOR).map((seg) => seg.trim()).filter(Boolean);
  return parts.join(CATEGORY_SEPARATOR);
}

function isSubcategoryOf(child: string, parent: string): boolean {
  const c = normalizeCategory(child);
  const p = normalizeCategory(parent);
  if (!c || !p || c === p) {
    return false;
  }
  return c.startsWith(p + CATEGORY_SEPARATOR);
}

/** Pairs `[parent, child]` among distinct normalised paths where child is under parent. */
export function findOverlapPairs(categories: Iterable<string>): Array<[string, string]> {
  const items: string[] = [];
  for (const raw of categories) {
    const n = normalizeCategory(raw);
    if (n && !items.includes(n)) {
      items.push(n);
    }
  }
  const out: Array<[string, string]> = [];
  for (const parent of items) {
    for (const child of items) {
      if (parent === child) continue;
      if (isSubcategoryOf(child, parent)) {
        out.push([parent, child]);
      }
    }
  }
  return out;
}

export function categoryHasBackslash(value: unknown): boolean {
  return String(value ?? "").includes("\\");
}
