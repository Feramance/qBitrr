import { describe, expect, it } from "vitest";
import {
  formatTorrentStateLabel,
  isSeedingState,
  SEEDING_STATES,
  torrentStateFamily,
} from "./qbitTorrentDisplay";

describe("isSeedingState", () => {
  it("counts uploading, stalledUP, forcedUP, and queuedUP as seeding", () => {
    expect(SEEDING_STATES).toEqual([
      "uploading",
      "stalledUP",
      "forcedUP",
      "queuedUP",
    ]);
    for (const state of SEEDING_STATES) {
      expect(isSeedingState(state)).toBe(true);
    }
  });

  it("excludes paused/stopped/checking upload states from seeding counts", () => {
    expect(isSeedingState("pausedUP")).toBe(false);
    expect(isSeedingState("stoppedUP")).toBe(false);
    expect(isSeedingState("checkingUP")).toBe(false);
    expect(isSeedingState("downloading")).toBe(false);
  });
});

describe("torrentStateFamily", () => {
  it("maps forcedUP and queuedUP into uploading family for badges", () => {
    expect(torrentStateFamily("forcedUP")).toBe("uploading");
    expect(torrentStateFamily("queuedUP")).toBe("uploading");
    expect(torrentStateFamily("stalledUP")).toBe("stalled");
  });
});

describe("formatTorrentStateLabel", () => {
  it("labels forced upload states", () => {
    expect(formatTorrentStateLabel("forcedUP")).toBe("Forced UP");
    expect(formatTorrentStateLabel("queuedUP")).toBe("Queued UP");
  });
});
