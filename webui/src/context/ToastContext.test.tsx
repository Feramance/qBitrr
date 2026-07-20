import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  resetToastDedupeForTests,
  ToastProvider,
  ToastViewport,
  TOAST_DEDUPE_MS,
  useToast,
} from "./ToastContext";

afterEach(() => {
  cleanup();
  resetToastDedupeForTests();
  vi.useRealTimers();
});

beforeEach(() => {
  resetToastDedupeForTests();
});

function Controls(): React.JSX.Element {
  const { push } = useToast();
  return (
    <div>
      <button type="button" onClick={() => push("Failed to fetch", "error")}>
        same
      </button>
      <button type="button" onClick={() => push("Error A", "error")}>
        a
      </button>
      <button type="button" onClick={() => push("Error B", "error")}>
        b
      </button>
    </div>
  );
}

describe("ToastContext dedupe", () => {
  it("suppresses identical message+kind within the dedupe window", () => {
    render(
      <ToastProvider>
        <Controls />
        <ToastViewport />
      </ToastProvider>,
    );

    const button = screen.getByRole("button", { name: "same" });
    act(() => {
      button.click();
      button.click();
      button.click();
    });

    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByRole("alert")).toHaveTextContent("Failed to fetch");
  });

  it("allows the same message again after the dedupe window", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Controls />
        <ToastViewport />
      </ToastProvider>,
    );

    const button = screen.getByRole("button", { name: "same" });
    act(() => {
      button.click();
    });
    expect(screen.getAllByRole("alert")).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(Math.max(TOAST_DEDUPE_MS, 8000) + 50);
    });
    expect(screen.queryByRole("alert")).toBeNull();

    act(() => {
      button.click();
    });
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });

  it("does not dedupe different messages", () => {
    render(
      <ToastProvider>
        <Controls />
        <ToastViewport />
      </ToastProvider>,
    );

    act(() => {
      screen.getByRole("button", { name: "a" }).click();
      screen.getByRole("button", { name: "b" }).click();
    });
    expect(screen.getAllByRole("alert")).toHaveLength(2);
  });
});
