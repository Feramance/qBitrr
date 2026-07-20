import { describe, expect, it } from "vitest";
import {
  buildSectionDeleteChanges,
  fieldErrorDataPath,
  findFieldErrorMessage,
  formatValidationErrors,
  resolveSectionDiskKey,
  validationErrorsFromApi,
} from "./configDocumentUtils";
import type { ValidationError } from "./configTypes";

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
