import { describe, expect, it } from "vitest";
import {
  fieldErrorDataPath,
  findFieldErrorMessage,
  formatValidationErrors,
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
