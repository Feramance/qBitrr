import { describe, expect, it } from "vitest";
import type { ConfigDocument } from "../../api/types";
import { QBIT_FIELD_OVERLAYS } from "./configFieldOverlays";

const ctx = { root: {} as ConfigDocument };

describe("CategorySeeding rate/ratio overlays", () => {
  it("accepts documented -1 disabled values", () => {
    const download = QBIT_FIELD_OVERLAYS["CategorySeeding.DownloadRateLimitPerTorrent"];
    const upload = QBIT_FIELD_OVERLAYS["CategorySeeding.UploadRateLimitPerTorrent"];
    const ratio = QBIT_FIELD_OVERLAYS["CategorySeeding.MaxUploadRatio"];

    expect(download.allowNegative).toBe(true);
    expect(upload.allowNegative).toBe(true);
    expect(ratio.allowNegative).toBe(true);
    expect(download.validate?.(-1, ctx)).toBeUndefined();
    expect(upload.validate?.(-1, ctx)).toBeUndefined();
    expect(ratio.validate?.(-1, ctx)).toBeUndefined();
    expect(download.placeholder).toContain("-1 (disabled)");
    expect(upload.placeholder).toContain("-1 (disabled)");
  });

  it("rejects values below -1", () => {
    const download = QBIT_FIELD_OVERLAYS["CategorySeeding.DownloadRateLimitPerTorrent"];
    expect(download.validate?.(-2, ctx)).toMatch(/-1 or greater/);
  });
});
