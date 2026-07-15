import { describe, expect, it } from "vitest";
import type { ConfigDocument } from "../../api/types";
import { AUTH_SETTINGS_FIELDS, ARR_TRACKER_FIELDS, WEB_SETTINGS_FIELDS } from "./configFields";
import { getChangedSectionKeys, validateSection } from "./configValidation";

function managedRadarrSection(overrides: Record<string, unknown> = {}): ConfigDocument {
  return {
    Managed: true,
    URI: "http://localhost:7878",
    APIKey: "test-key",
    Category: "radarr",
    Trackers: [
      {
        Name: "bad-tracker",
        URI: "udp://tracker.example",
        Priority: -5,
      },
    ],
    ...overrides,
  } as ConfigDocument;
}

describe("validateSection golden-master", () => {
  it("validates Settings required fields", () => {
    const formState: ConfigDocument = {
      Settings: {
        ConsoleLevel: "INFO",
        Logging: true,
        CompletedDownloadFolder: "",
        FreeSpace: "-1",
      },
    };
    const errors = validateSection(formState, "Settings");
    expect(errors.some((e) => e.path.join(".") === "Settings.CompletedDownloadFolder")).toBe(
      true,
    );
  });

  it("gap #14: tracker field validators are not run on Arr section save", () => {
    const formState: ConfigDocument = {
      Radarr: managedRadarrSection(),
    };
    const errors = validateSection(formState, "Radarr");
    const trackerPriorityErrors = errors.filter((e) =>
      e.message.includes("Priority must be a non-negative number"),
    );
    expect(trackerPriorityErrors).toHaveLength(0);
    expect(ARR_TRACKER_FIELDS.some((f) => f.path?.[0] === "Priority" && f.validate)).toBe(true);
  });

  it("gap #15: Authentication branch is dead — auth field changes map to WebUI section", () => {
    const original: ConfigDocument = {
      WebUI: { Host: "0.0.0.0", Port: 6969, LocalAuthEnabled: false },
    };
    const formState: ConfigDocument = {
      WebUI: { Host: "0.0.0.0", Port: 6969, LocalAuthEnabled: true },
    };
    const changed = getChangedSectionKeys(formState, original, new Map());
    expect(changed).toContain("WebUI");
    expect(changed).not.toContain("Authentication");
    // Direct call to the dead branch still runs AUTH validators (paths under WebUI.*).
    const authBranchErrors = validateSection(formState, "Authentication");
    expect(authBranchErrors).toEqual([]);
    expect(AUTH_SETTINGS_FIELDS.every((f) => f.path?.[0] === "WebUI")).toBe(true);
    expect(validateSection(formState, "WebUI").length).toBeGreaterThanOrEqual(0);
  });

  it("gap #16: no field definition uses label Theme at WebUI.Theme path", () => {
    const themeField = WEB_SETTINGS_FIELDS.find(
      (f) => f.label === "Theme" && f.path?.join(".") === "WebUI.Theme",
    );
    expect(themeField).toBeUndefined();
  });
});
