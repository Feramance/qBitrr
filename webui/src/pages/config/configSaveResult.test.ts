import { describe, expect, it } from "vitest";
import {
  formatConfigSaveMessage,
  shouldRefreshMetaAfterSave,
  shouldReloadPageAfterSave,
  webuiChangeNeedsPageReload,
} from "./configSaveResult";

describe("configSaveResult", () => {
  describe("formatConfigSaveMessage", () => {
    it("describes live reload with and without configReloaded", () => {
      expect(formatConfigSaveMessage("live", true, [], [])).toBe(
        "Configuration saved • Applied live",
      );
      expect(formatConfigSaveMessage("live", false, [], [])).toBe(
        "Configuration saved • Applied without restart",
      );
    });

    it("describes qbit_hot reload", () => {
      expect(formatConfigSaveMessage("qbit_hot", true, [], [])).toBe(
        "Configuration saved • qBittorrent settings reloaded",
      );
      expect(formatConfigSaveMessage("qbit_hot", false, [], [])).toBe(
        "Configuration saved • qBittorrent settings updated",
      );
    });

    it("uses WebUI restart wording only when host or port changed", () => {
      expect(formatConfigSaveMessage("webui", true, [], ["WebUI.UrlBase"])).toBe(
        "Configuration saved • WebUI settings updated",
      );
      expect(formatConfigSaveMessage("webui", true, [], ["WebUI.Host"])).toBe(
        "Configuration saved • WebUI restarting...",
      );
    });

    it("handles unknown reload types defensively", () => {
      expect(formatConfigSaveMessage("future_type", false, [], [])).toBe(
        "Configuration saved • Applied without restart",
      );
    });
  });

  describe("webuiChangeNeedsPageReload", () => {
    it("returns true only for host or port keys", () => {
      expect(webuiChangeNeedsPageReload(["WebUI.UrlBase"])).toBe(false);
      expect(webuiChangeNeedsPageReload(["WebUI.Host"])).toBe(true);
      expect(webuiChangeNeedsPageReload(["WebUI.Port"])).toBe(true);
    });
  });

  describe("shouldRefreshMetaAfterSave", () => {
    it("refreshes meta for live and non-restart webui saves", () => {
      expect(shouldRefreshMetaAfterSave("live", [])).toBe(true);
      expect(shouldRefreshMetaAfterSave("webui", ["WebUI.UrlBase"])).toBe(true);
      expect(shouldRefreshMetaAfterSave("webui", ["WebUI.Host"])).toBe(false);
    });
  });

  describe("shouldReloadPageAfterSave", () => {
    it("reloads page only for webui host/port changes", () => {
      expect(shouldReloadPageAfterSave("webui", ["WebUI.UrlBase"])).toBe(false);
      expect(shouldReloadPageAfterSave("webui", ["WebUI.Port"])).toBe(true);
      expect(shouldReloadPageAfterSave("live", [])).toBe(false);
    });
  });
});
