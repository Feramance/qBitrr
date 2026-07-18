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

  it("documents Arr tabs staying mounted across visibility changes", () => {
    expect(source).toMatch(/Arr tabs stay mounted|visibilitychange/i);
  });
});
