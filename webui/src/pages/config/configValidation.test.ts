import { describe, expect, it } from "vitest";
import type { ConfigDocument } from "../../api/types";
import { AUTH_SETTINGS_FIELDS, ARR_TRACKER_FIELDS, WEB_SETTINGS_FIELDS } from "./configFields";
import {
  basicValidation,
  getChangedSectionKeys,
  isEnabledQbitSection,
  isManagedArrSection,
  validateSection,
  validateSectionsForSave,
} from "./configValidation";
import type { FieldDefinition } from "./configTypes";

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

describe("basicValidation", () => {
  it("requires text fields when marked required", () => {
    const def: FieldDefinition = { label: "Host", type: "text", required: true };
    expect(basicValidation(def, "")).toMatch(/required/i);
    expect(basicValidation(def, "localhost")).toBeUndefined();
  });

  it("validates number finiteness", () => {
    const def: FieldDefinition = { label: "Port", type: "number", required: true };
    expect(basicValidation(def, "abc")).toMatch(/valid number/i);
    expect(basicValidation(def, 6969)).toBeUndefined();
    expect(basicValidation(def, "")).toMatch(/required/i);
  });

  it("validates checkbox booleans", () => {
    const def: FieldDefinition = { label: "Enabled", type: "checkbox", required: true };
    expect(basicValidation(def, "yes")).toMatch(/true or false/i);
    expect(basicValidation(def, true)).toBeUndefined();
  });

  it("validates select options", () => {
    const def: FieldDefinition = {
      label: "Level",
      type: "select",
      options: ["INFO", "DEBUG"],
    };
    expect(basicValidation(def, "TRACE")).toMatch(/must be one of/i);
    expect(basicValidation(def, "INFO")).toBeUndefined();
  });
});

describe("section helpers", () => {
  it("detects managed Arr and enabled qBit sections", () => {
    expect(isManagedArrSection({ Managed: true } as ConfigDocument)).toBe(true);
    expect(isManagedArrSection({ Managed: false } as ConfigDocument)).toBe(false);
    expect(isEnabledQbitSection({ Disabled: false } as ConfigDocument)).toBe(true);
    expect(isEnabledQbitSection({ Disabled: true } as ConfigDocument)).toBe(false);
  });
});

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

  it("skips validation for unmanaged Arr sections", () => {
    const formState: ConfigDocument = {
      Radarr: { Managed: false, URI: "", APIKey: "" },
    };
    expect(validateSection(formState, "Radarr")).toEqual([]);
  });

  it("skips validation for disabled qBit sections", () => {
    const formState: ConfigDocument = {
      "qBit-Movies": { Disabled: true, Host: "" },
    };
    expect(validateSection(formState, "qBit-Movies")).toEqual([]);
  });

  it("validates WebUI port when section saved", () => {
    const formState: ConfigDocument = {
      WebUI: { Host: "", Port: 6969, LocalAuthEnabled: false },
    };
    const errors = validateSection(formState, "WebUI");
    expect(errors.some((e) => e.path.join(".") === "WebUI.Host")).toBe(true);
  });

  it("flags category backslashes in cross-section save", () => {
    const formState: ConfigDocument = {
      Radarr: managedRadarrSection({ Category: "movies\\4k" }),
      "qBit-Movies": {
        Disabled: false,
        ManagedCategories: ["movies/4k"],
      },
    };
    const errors = validateSectionsForSave(formState, ["Radarr"], null, false);
    expect(errors.some((e) => e.message.includes("Backslashes"))).toBe(true);
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

  it("save gate: managed Arr with empty URI blocks section save validation", () => {
    const formState: ConfigDocument = {
      Radarr: managedRadarrSection({ URI: "" }),
    };
    const errors = validateSectionsForSave(formState, ["Radarr"], null, false);
    expect(errors.some((e) => e.path.join(".").includes("URI"))).toBe(true);
  });

  it("save gate: valid managed Arr section passes save validation", () => {
    const formState: ConfigDocument = {
      Radarr: managedRadarrSection(),
    };
    const errors = validateSectionsForSave(formState, ["Radarr"], null, false);
    const uriErrors = errors.filter((e) => e.path.join(".").includes("URI"));
    expect(uriErrors).toHaveLength(0);
  });
});
