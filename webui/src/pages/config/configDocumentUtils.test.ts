import { describe, expect, it } from "vitest";
import {
  buildSectionDeleteChanges,
  createDefaultTrackerEntry,
  ensureArrDefaults,
  fieldErrorDataPath,
  findFieldErrorMessage,
  formatValidationErrors,
  resolveSectionDiskKey,
  validationErrorsFromApi,
} from "./configDocumentUtils";
import type { ValidationError } from "./configTypes";

describe("createDefaultTrackerEntry", () => {
  it("omits seeding/ETA limit keys so parent limits are inherited", () => {
    const tracker = createDefaultTrackerEntry();
    expect(tracker).not.toHaveProperty("MaxSeedingTime");
    expect(tracker).not.toHaveProperty("MaxUploadRatio");
    expect(tracker).not.toHaveProperty("MaximumETA");
    expect(tracker.DownloadRateLimit).toBe(-1);
    expect(tracker.UploadRateLimit).toBe(-1);
  });
});

describe("configDocumentUtils validation helpers", () => {
  it("formatValidationErrors lists every path and message", () => {
    const errors: ValidationError[] = [
      { path: ["Lidarr", "URI"], message: "URI is required" },
      {
        path: ["Lidarr", "Torrent", "SeedingMode", "RemoveTorrent"],
        message: "Invalid value",
      },
    ];
    const text = formatValidationErrors(errors);
    expect(text).toContain("Please resolve the following issues:");
    expect(text).toContain("Lidarr.URI: URI is required");
    expect(text).toContain("Lidarr.Torrent.SeedingMode.RemoveTorrent: Invalid value");
  });

  it("validationErrorsFromApi splits dotted paths", () => {
    expect(
      validationErrorsFromApi([
        { path: "Lidarr.Torrent.SeedingMode.RemoveTorrent", message: "bad" },
      ])
    ).toEqual([
      {
        path: ["Lidarr", "Torrent", "SeedingMode", "RemoveTorrent"],
        message: "bad",
      },
    ]);
  });

  it("findFieldErrorMessage matches Arr sectionKey + relative field path", () => {
    const errors: ValidationError[] = [
      {
        path: ["Lidarr", "Torrent", "SeedingMode", "RemoveTorrent"],
        message: "Remove Torrent is invalid",
      },
    ];
    expect(
      findFieldErrorMessage(errors, ["Torrent", "SeedingMode", "RemoveTorrent"], {
        sectionKey: "Lidarr",
        basePath: [],
      })
    ).toBe("Remove Torrent is invalid");
  });

  it("findFieldErrorMessage matches Settings absolute field paths", () => {
    const errors: ValidationError[] = [
      { path: ["Settings", "FreeSpace"], message: "FreeSpace is invalid" },
    ];
    expect(
      findFieldErrorMessage(errors, ["Settings", "FreeSpace"], { basePath: [] })
    ).toBe("FreeSpace is invalid");
  });

  it("fieldErrorDataPath prefers sectionKey for Arr relative paths", () => {
    expect(
      fieldErrorDataPath(["URI"], { sectionKey: "Lidarr-Music", basePath: [] })
    ).toBe("Lidarr-Music.URI");
  });
});

describe("buildSectionDeleteChanges", () => {
  it("returns section null for an existing qBit instance", () => {
    const original = {
      "qBit-Bad": { Host: "localhost", Port: 8080 },
      Settings: { LoopSleepTimer: 60 },
    };
    expect(buildSectionDeleteChanges("qBit-Bad", original, new Map())).toEqual({
      "qBit-Bad": null,
    });
  });

  it("returns null for an unsaved new section", () => {
    const original = { Settings: { LoopSleepTimer: 60 } };
    expect(buildSectionDeleteChanges("qBit-2", original, new Map())).toBeNull();
  });

  it("uses the old disk key after a pending rename", () => {
    const original = {
      qBit: { Host: "localhost", Port: 8080 },
    };
    const pending = new Map([["qBit", "qBit-General"]]);
    expect(resolveSectionDiskKey("qBit-General", pending)).toBe("qBit");
    expect(buildSectionDeleteChanges("qBit-General", original, pending)).toEqual({
      qBit: null,
    });
  });

  it("nulls both keys when rename target also exists on disk", () => {
    const original = {
      qBit: { Host: "a" },
      "qBit-General": { Host: "b" },
    };
    const pending = new Map([["qBit", "qBit-General"]]);
    expect(buildSectionDeleteChanges("qBit-General", original, pending)).toEqual({
      qBit: null,
      "qBit-General": null,
    });
  });
});

describe("ensureArrDefaults", () => {
  it("omits SearchByYear and Ombi/Overseerr for Lidarr", () => {
    const doc = ensureArrDefaults("Lidarr");
    const entry = doc.EntrySearch as Record<string, unknown>;
    expect(entry.SearchByYear).toBeUndefined();
    expect(entry.Ombi).toBeUndefined();
    expect(entry.Overseerr).toBeUndefined();
  });

  it("includes SearchByYear but omits Ombi/Overseerr for Readarr", () => {
    const doc = ensureArrDefaults("Readarr");
    const entry = doc.EntrySearch as Record<string, unknown>;
    expect(entry.SearchByYear).toBe(true);
    expect(entry.Ombi).toBeUndefined();
    expect(entry.Overseerr).toBeUndefined();
  });

  it("includes SearchByYear and Ombi/Overseerr for Radarr", () => {
    const doc = ensureArrDefaults("Radarr");
    const entry = doc.EntrySearch as Record<string, unknown>;
    expect(entry.SearchByYear).toBe(true);
    expect(entry.Ombi).toBeTruthy();
    expect(entry.Overseerr).toBeTruthy();
  });
});
