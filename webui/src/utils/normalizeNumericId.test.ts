import { describe, expect, it } from "vitest";
import { normalizeNumericId } from "./normalizeNumericId";

describe("normalizeNumericId", () => {
  it("returns finite numbers unchanged", () => {
    expect(normalizeNumericId(42)).toBe(42);
    expect(normalizeNumericId(0)).toBe(0);
    expect(normalizeNumericId(-3)).toBe(-3);
  });

  it("parses numeric strings including decimals coerced by Number()", () => {
    expect(normalizeNumericId("123")).toBe(123);
    expect(normalizeNumericId(" 7 ")).toBe(7);
    expect(normalizeNumericId("3.14")).toBe(3.14);
    expect(normalizeNumericId("-1")).toBe(-1);
  });

  it("returns undefined for invalid values", () => {
    expect(normalizeNumericId(undefined)).toBeUndefined();
    expect(normalizeNumericId(null)).toBeUndefined();
    expect(normalizeNumericId("")).toBeUndefined();
    expect(normalizeNumericId("   ")).toBeUndefined();
    expect(normalizeNumericId("abc")).toBeUndefined();
    expect(normalizeNumericId("12abc")).toBeUndefined();
    expect(normalizeNumericId(NaN)).toBeUndefined();
    expect(normalizeNumericId(Infinity)).toBeUndefined();
    expect(normalizeNumericId(-Infinity)).toBeUndefined();
  });

  it("rejects non-numeric types", () => {
    expect(normalizeNumericId(true)).toBeUndefined();
    expect(normalizeNumericId(false)).toBeUndefined();
    expect(normalizeNumericId({ id: 1 })).toBeUndefined();
    expect(normalizeNumericId([1])).toBeUndefined();
  });
});
