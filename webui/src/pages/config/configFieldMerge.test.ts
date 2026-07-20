import { describe, expect, it } from "vitest";
import { mergeFieldOverlays } from "./configFieldMerge";
import type { FieldDefinition } from "./configTypes";

describe("mergeFieldOverlays", () => {
  it("applies validators from overlays without dropping generated metadata", () => {
    const generated: FieldDefinition[] = [
      {
        label: "Free Space",
        path: ["Settings", "FreeSpace"],
        type: "text",
        required: true,
        applyLive: true,
      },
    ];
    const merged = mergeFieldOverlays(generated, {
      "Settings.FreeSpace": {
        validate: () => "bad",
      },
    });
    expect(merged[0].applyLive).toBe(true);
    expect(merged[0].required).toBe(true);
    expect(merged[0].validate?.(null as never, {} as never)).toBe("bad");
  });
});
