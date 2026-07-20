import { describe, expect, it } from "vitest";
import { createStandardArrFilters, type StandardArrFilterState } from "./createStandardArrFilters";

interface TestFilters extends StandardArrFilterState {
  onlyMissing: boolean;
  reasonFilter: string;
}

const REASON_VALUES = [
  "all",
  "Not being searched",
  "Missing",
  "Quality",
  "CustomFormat",
  "Upgrade",
] as const;

describe("createStandardArrFilters", () => {
  const filters = createStandardArrFilters<TestFilters>("All Movies");

  it("defines status and reason controls", () => {
    expect(filters).toHaveLength(2);
    expect(filters[0]?.id).toBe("status");
    expect(filters[1]?.id).toBe("reason");
  });

  it("uses the provided all-items label", () => {
    expect(filters[0]?.options[0]?.label).toBe("All Movies");
    expect(createStandardArrFilters<TestFilters>("All Episodes")[0]?.options[0]
      ?.label).toBe("All Episodes");
    expect(createStandardArrFilters<TestFilters>("All Albums")[0]?.options[0]
      ?.label).toBe("All Albums");
  });

  it("maps onlyMissing to status select value", () => {
    const status = filters[0];
    expect(status?.getValue({ onlyMissing: false, reasonFilter: "all" })).toBe(
      "all",
    );
    expect(status?.getValue({ onlyMissing: true, reasonFilter: "all" })).toBe(
      "missing",
    );
    expect(
      status?.setValue(
        { onlyMissing: false, reasonFilter: "all" },
        "missing",
      ),
    ).toEqual({ onlyMissing: true, reasonFilter: "all" });
    expect(
      status?.setValue(
        { onlyMissing: true, reasonFilter: "Quality" },
        "all",
      ),
    ).toEqual({ onlyMissing: false, reasonFilter: "Quality" });
  });

  it("maps reasonFilter to reason select value", () => {
    const reason = filters[1];
    expect(
      reason?.getValue({ onlyMissing: false, reasonFilter: "Quality" }),
    ).toBe("Quality");
    expect(
      reason?.setValue(
        { onlyMissing: false, reasonFilter: "all" },
        "Upgrade",
      ),
    ).toEqual({ onlyMissing: false, reasonFilter: "Upgrade" });
  });

  it.each(REASON_VALUES)("round-trips reason option %s", (value) => {
    const reason = filters[1];
    const state: TestFilters = { onlyMissing: false, reasonFilter: "all" };
    const next = reason?.setValue(state, value);
    expect(reason?.getValue(next!)).toBe(value);
  });

  it("preserves onlyMissing when changing reason", () => {
    const reason = filters[1];
    const prev: TestFilters = { onlyMissing: true, reasonFilter: "all" };
    expect(reason?.setValue(prev, "Missing")).toEqual({
      onlyMissing: true,
      reasonFilter: "Missing",
    });
  });

  it("exposes all standard reason labels", () => {
    const labels = filters[1]?.options.map((o) => o.label) ?? [];
    expect(labels).toEqual([
      "All Reasons",
      "Not Being Searched",
      "Missing",
      "Quality",
      "Custom Format",
      "Upgrade",
    ]);
  });
});
