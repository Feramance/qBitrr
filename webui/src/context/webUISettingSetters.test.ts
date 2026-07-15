import { describe, expect, it, vi } from "vitest";
import { createPersistedBooleanSetter } from "./webUISettingSetters";

describe("createPersistedBooleanSetter", () => {
  it("updates local state and persists to config", () => {
    const setSettings = vi.fn();
    const saveSettings = vi.fn().mockResolvedValue(undefined);
    const setter = createPersistedBooleanSetter(
      setSettings,
      saveSettings,
      "liveArr",
      "LiveArr",
    );

    setter(true);

    expect(setSettings).toHaveBeenCalledTimes(1);
    expect(saveSettings).toHaveBeenCalledWith("LiveArr", true);
  });
});
