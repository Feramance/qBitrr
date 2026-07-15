import { describe, expect, it } from "vitest";
import { normalizeNumericId } from "./normalizeNumericId";

describe("normalizeNumericId", () => {
  it("returns finite numbers unchanged", () => {
    expect(normalizeNumericId(42)).toBe(42);
    expect(normalizeNumericId(0)).toBe(0);
  });

  it("parses numeric strings", () => {
    expect(normalizeNumericId("123")).toBe(123);
    expect(normalizeNumericId(" 7 ")).toBe(7);
  });

  it("returns undefined for invalid values", () => {
    expect(normalizeNumericId(undefined)).toBeUndefined();
    expect(normalizeNumericId(null)).toBeUndefined();
    expect(normalizeNumericId("")).toBeUndefined();
    expect(normalizeNumericId("   ")).toBeUndefined();
    expect(normalizeNumericId("abc")).toBeUndefined();
    expect(normalizeNumericId(NaN)).toBeUndefined();
    expect(normalizeNumericId(Infinity)).toBeUndefined();
  });
});
