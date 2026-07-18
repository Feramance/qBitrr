import { describe, expect, it } from "vitest";
import { QBIT_SECTION_REGEX, SERVARR_SECTION_REGEX } from "./configTypes";

describe("SERVARR_SECTION_REGEX", () => {
  it("matches Radarr/Sonarr/Lidarr with hyphen or dotted suffixes", () => {
    expect(SERVARR_SECTION_REGEX.test("Radarr")).toBe(true);
    expect(SERVARR_SECTION_REGEX.test("Sonarr-TV")).toBe(true);
    expect(SERVARR_SECTION_REGEX.test("Radarr.Main")).toBe(true);
    expect(SERVARR_SECTION_REGEX.test("Lidarr-Music")).toBe(true);
  });

  it("rejects Animarr (removed) and non-Arr sections", () => {
    expect(SERVARR_SECTION_REGEX.test("Animarr")).toBe(false);
    expect(SERVARR_SECTION_REGEX.test("Animarr-Extra")).toBe(false);
    expect(SERVARR_SECTION_REGEX.test("Settings")).toBe(false);
    expect(SERVARR_SECTION_REGEX.test("qBit")).toBe(false);
  });
});

describe("QBIT_SECTION_REGEX", () => {
  it("matches primary and named qBit sections", () => {
    expect(QBIT_SECTION_REGEX.test("qBit")).toBe(true);
    expect(QBIT_SECTION_REGEX.test("qBit-Seedbox")).toBe(true);
    expect(QBIT_SECTION_REGEX.test("Radarr")).toBe(false);
  });
});
