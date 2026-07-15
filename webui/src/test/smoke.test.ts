import { describe, expect, it } from "vitest";

describe("frontend test infrastructure", () => {
  it("runs vitest with jsdom", () => {
    expect(typeof document).toBe("object");
    expect(document.createElement("div").tagName).toBe("DIV");
  });
});
