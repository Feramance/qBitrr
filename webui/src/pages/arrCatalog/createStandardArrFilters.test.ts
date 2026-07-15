import { describe, expect, it } from "vitest";
import { createStandardArrFilters, type StandardArrFilterState } from "./createStandardArrFilters";

interface TestFilters extends StandardArrFilterState {
  onlyMissing: boolean;
  reasonFilter: string;
}

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
});
