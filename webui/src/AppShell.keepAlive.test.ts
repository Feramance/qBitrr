import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * AppShell keep-alive policy is hard to RTL-test without mounting the full shell.
 * Characterize the intentional policy in source so regressions are obvious in review/CI.
 */
describe("AppShell keep-alive policy", () => {
  const source = readFileSync(resolve(__dirname, "AppShell.tsx"), "utf8");

  it("keeps visited tabs mounted via hidden toggles", () => {
    expect(source).toContain("visitedTabs");
    expect(source).toMatch(/hidden=\{activeTab !== "radarr"\}/);
    expect(source).toMatch(/hidden=\{activeTab !== "processes"\}/);
  });

  it("documents Arr/qBit tabs staying mounted across visibility changes", () => {
    expect(source).toMatch(/Arr\/qBit tabs stay mounted|visibilitychange/i);
    expect(source).toMatch(
      /if \(activeTab === "processes" \|\| activeTab === "logs"\)/,
    );
    expect(source).not.toMatch(
      /activeTab === "qbittorrent"[\s\S]{0,80}setReloadKey/,
    );
  });

  it("shows Arr and qBittorrent nav tabs only when configured", () => {
    expect(source).toMatch(/configuredTabs\.radarr/);
    expect(source).toMatch(/configuredTabs\.sonarr/);
    expect(source).toMatch(/configuredTabs\.lidarr/);
    expect(source).toMatch(/configuredTabs\.qbittorrent/);
    expect(source).toMatch(
      /qbittorrent:\s*Object\.keys\(qbitInstances\)\.length\s*>\s*0/,
    );
    expect(source).toMatch(
      /visitedTabs\.has\("qbittorrent"\)\s*&&\s*visibleTabIds\.has\("qbittorrent"\)/,
    );
  });
});
