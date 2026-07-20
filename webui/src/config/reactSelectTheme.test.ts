import { describe, expect, it } from "vitest";
import { getSelectStyles } from "./reactSelectTheme";

describe("getSelectStyles", () => {
  it("returns dark-theme control colors", () => {
    const styles = getSelectStyles(true);
    const control = styles.control({ background: "base" } as never);
    expect(control.background).toBe("#0f131a");
    expect(control.color).toBe("#eaeef2");
    expect(control.borderColor).toBe("#2a2f36");
  });

  it("returns light-theme control colors", () => {
    const styles = getSelectStyles(false);
    const control = styles.control({ background: "base" } as never);
    expect(control.background).toBe("#ffffff");
    expect(control.color).toBe("#1d1d1f");
    expect(control.borderColor).toBe("#d2d2d7");
  });

  it("highlights focused options in dark mode", () => {
    const styles = getSelectStyles(true);
    const focused = styles.option({} as never, { isFocused: true });
    const idle = styles.option({} as never, { isFocused: false });
    expect(focused.background).toBe("rgba(59, 130, 246, 0.15)");
    expect(idle.background).toBe("#0f131a");
  });
});
