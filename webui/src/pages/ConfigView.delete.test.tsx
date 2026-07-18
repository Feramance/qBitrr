import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../context/ToastContext";
import { ConfigView } from "./ConfigView";

const getConfig = vi.fn();
const updateConfig = vi.fn();

vi.mock("../api/client", () => ({
  ConfigApiError: class ConfigApiError extends Error {
    validationErrors: Array<{ path: string; message: string }>;
    constructor(
      message: string,
      validationErrors: Array<{ path: string; message: string }> = []
    ) {
      super(message);
      this.validationErrors = validationErrors;
    }
  },
  getConfig: (...args: unknown[]) => getConfig(...args),
  updateConfig: (...args: unknown[]) => updateConfig(...args),
  refreshUrlBaseFromMeta: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../components/IconImage", () => ({
  IconImage: () => <span data-testid="icon" />,
}));

vi.mock("../context/WebUIContext", () => ({
  useWebUI: () => ({
    liveArr: true,
    viewDensity: "comfortable" as const,
    theme: "dark" as const,
    setLiveArr: () => undefined,
    setViewDensity: () => undefined,
    setTheme: () => undefined,
  }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function qbitSection(host = "bad.example") {
  return {
    Disabled: false,
    Host: host,
    Port: 1,
    UserName: "",
    Password: "",
    ManagedCategories: [],
    MatchSubcategories: false,
    Trackers: [],
    CategorySeeding: {
      DownloadRateLimitPerTorrent: -1,
      UploadRateLimitPerTorrent: -1,
      MaxUploadRatio: -1,
      MaxSeedingTime: -1,
      RemoveTorrent: -1,
      HitAndRunMode: "disabled",
      MinSeedRatio: 1,
      MinSeedingTimeDays: 0,
      HitAndRunMinimumDownloadPercent: 10,
      HitAndRunPartialSeedRatio: 1,
      TrackerUpdateBuffer: 0,
      StalledDelay: -1,
      IgnoreTorrentsYoungerThan: 180,
    },
  };
}

function renderConfig() {
  return render(
    <ToastProvider>
      <ConfigView />
    </ToastProvider>
  );
}

async function openQbitModal(user: ReturnType<typeof userEvent.setup>, key: string) {
  const header = await screen.findByText(key);
  const card = header.closest(".config-arr-card");
  expect(card).toBeTruthy();
  await user.click(within(card as HTMLElement).getByRole("button", { name: /Configure/i }));
  await screen.findByRole("dialog", { name: new RegExp(`Configure ${key}`, "i") });
}

describe("ConfigView instance delete persist", () => {
  beforeEach(() => {
    getConfig.mockResolvedValue({
      Settings: { LoopSleepTimer: 60, ConsoleLevel: "INFO" },
      WebUI: { Host: "0.0.0.0", Port: 6969 },
      "qBit-Bad": qbitSection(),
    });
    updateConfig.mockResolvedValue({
      configReloaded: true,
      reloadType: "full",
      affectedInstances: [],
    });
  });

  it("persists an existing qBit delete after confirm", async () => {
    const user = userEvent.setup();
    renderConfig();

    await openQbitModal(user, "qBit-Bad");
    await user.click(screen.getByRole("button", { name: /^Delete$/i }));
    const confirm = await screen.findByRole("dialog", { name: /Remove qBit-Bad/i });
    expect(
      within(confirm).getByText(/removes qBit-Bad from the config file/i)
    ).toBeInTheDocument();

    await user.click(within(confirm).getByRole("button", { name: /^Remove$/i }));

    await waitFor(() => {
      expect(updateConfig).toHaveBeenCalledWith({
        changes: { "qBit-Bad": null },
      });
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /Configure qBit-Bad/i })).not.toBeInTheDocument();
    });
  });

  it("does not call updateConfig when confirm is cancelled", async () => {
    const user = userEvent.setup();
    renderConfig();

    await openQbitModal(user, "qBit-Bad");
    await user.click(screen.getByRole("button", { name: /^Delete$/i }));
    const confirm = await screen.findByRole("dialog", { name: /Remove qBit-Bad/i });
    await user.click(within(confirm).getByRole("button", { name: /Cancel/i }));

    expect(updateConfig).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: /Configure qBit-Bad/i })).toBeInTheDocument();
  });

  it("removes an unsaved new qBit locally without updateConfig", async () => {
    const user = userEvent.setup();
    renderConfig();

    await screen.findByText("qBit-Bad");
    const qbitGroup = screen.getByText("qBittorrent Instances").closest("details");
    expect(qbitGroup).toBeTruthy();
    await user.click(
      within(qbitGroup as HTMLElement).getByRole("button", { name: /Add Instance/i })
    );
    await screen.findByRole("dialog", { name: /Configure qBit-1/i });

    await user.click(screen.getByRole("button", { name: /^Delete$/i }));
    const confirm = await screen.findByRole("dialog", { name: /Remove qBit-1/i });
    await user.click(within(confirm).getByRole("button", { name: /^Remove$/i }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: /Configure qBit-1/i })).not.toBeInTheDocument();
    });
    expect(updateConfig).not.toHaveBeenCalled();
  });

  it("deletes a renamed qBit using the old disk section key", async () => {
    const user = userEvent.setup();
    renderConfig();

    await openQbitModal(user, "qBit-Bad");

    const nameInput = screen.getByPlaceholderText("qBit-seedbox");
    await user.clear(nameInput);
    await user.type(nameInput, "qBit-General");
    await user.tab();

    await waitFor(() => {
      expect(screen.getByRole("dialog", { name: /Configure qBit-General/i })).toBeInTheDocument();
    });

    getConfig.mockResolvedValueOnce({
      Settings: { LoopSleepTimer: 60, ConsoleLevel: "INFO" },
      WebUI: { Host: "0.0.0.0", Port: 6969 },
    });

    await user.click(screen.getByRole("button", { name: /^Delete$/i }));
    const confirm = await screen.findByRole("dialog", { name: /Remove qBit-General/i });
    await user.click(within(confirm).getByRole("button", { name: /^Remove$/i }));

    await waitFor(() => {
      expect(updateConfig).toHaveBeenCalledWith({
        changes: { "qBit-Bad": null },
      });
    });
  });
});
