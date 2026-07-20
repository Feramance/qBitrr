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

  it("soft-refreshes on visibility without remounting or toasting meta errors", () => {
    expect(source).toMatch(/visibilitychange/);
    expect(source).toMatch(
      /refreshMeta\(\{\s*force:\s*true,\s*silent:\s*true\s*\}\)/,
    );
    expect(source).not.toMatch(/setReloadKey/);
    expect(source).not.toMatch(
      /if \(activeTab === "processes" \|\| activeTab === "logs"\)/,
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

describe("background poll toast silence", () => {
  it("gates Processes / qBit / Arr poll errors on showLoading", () => {
    const processes = readFileSync(
      resolve(__dirname, "pages/ProcessesView.tsx"),
      "utf8",
    );
    const qbit = readFileSync(
      resolve(__dirname, "pages/QbitCategoriesView.tsx"),
      "utf8",
    );
    const instance = readFileSync(
      resolve(__dirname, "pages/arrCatalog/useInstancePagedFetch.ts"),
      "utf8",
    );
    const aggregate = readFileSync(
      resolve(__dirname, "pages/arrCatalog/useAggregateCatalogLoader.ts"),
      "utf8",
    );

    expect(processes).toMatch(/if \(showLoading\) \{\s*push\(/s);
    expect(qbit).toMatch(/if \(showLoading\) \{\s*push\(/s);
    expect(instance).toMatch(/if \(showLoading\) \{\s*pushToast\(/s);
    expect(aggregate).toMatch(/if \(showLoading\) \{\s*pushToast\(/s);
  });

  it("does not toast on Logs delta poll failures", () => {
    const logs = readFileSync(resolve(__dirname, "pages/LogsView.tsx"), "utf8");
    expect(logs).toMatch(/const pollDelta = useCallback/);
    expect(logs).not.toMatch(
      /Failed to poll \$\{selected\}/,
    );
  });
});
