import { describe, expect, it } from "vitest";
import {
  durationDisplayToValue,
  parseDurationToMinutes,
  parseDurationToSeconds,
} from "./durationUtils";

describe("durationDisplayToValue", () => {
  it("preserves fractional units at native-unit precision", () => {
    // Regression: rounding 1.4w to 1w made time-based torrent deletion run 2.8 days early.
    const seconds = durationDisplayToValue(1.4, "w", "seconds", true);
    const minutes = durationDisplayToValue(1.5, "h", "minutes", true);

    expect(seconds).toBe(846720);
    expect(parseDurationToSeconds(seconds)).toBe(846720);
    expect(minutes).toBe(90);
    expect(parseDurationToMinutes(minutes)).toBe(90);
  });

  it("keeps exactly representable durations human-readable", () => {
    expect(durationDisplayToValue(2, "w", "seconds", true)).toBe("2w");
  });
});
