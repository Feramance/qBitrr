import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChangelogModal, type ChangelogModalProps } from "./ChangelogModal";
import type { MetaResponse } from "../api/types";

vi.mock("./IconImage", () => ({
  IconImage: () => <span data-testid="icon" />,
}));

function updateState(
  partial: Partial<MetaResponse["update_state"]>,
): MetaResponse["update_state"] {
  return {
    in_progress: false,
    last_result: null,
    last_error: null,
    completed_at: null,
    ...partial,
  };
}

afterEach(() => {
  cleanup();
});

function baseProps(overrides: Partial<ChangelogModalProps> = {}): ChangelogModalProps {
  return {
    variant: "welcome",
    currentVersion: "5.9.0",
    changelog: "## New features",
    changelogUrl: "https://github.com/example/releases/tag/v5.9.0",
    repositoryUrl: "https://github.com/example/qBitrr",
    onClose: vi.fn(),
    ...overrides,
  };
}

describe("ChangelogModal variants", () => {
  it("welcome: shows welcome title, release notes, and Got it!", async () => {
    const onClose = vi.fn();
    render(<ChangelogModal {...baseProps({ onClose })} />);

    expect(screen.getByRole("dialog", { name: /Welcome to qBitrr v5\.9\.0/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Release Notes/i })).toBeInTheDocument();
    expect(screen.getByText(/New features/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /View Full Release on GitHub/i })).toHaveAttribute(
      "href",
      "https://github.com/example/releases/tag/v5.9.0",
    );
    expect(screen.queryByRole("button", { name: /Close/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Got it!/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("upToDate: shows latest-version copy and hides release notes when changelog empty", () => {
    render(
      <ChangelogModal
        {...baseProps({
          variant: "upToDate",
          changelog: "   ",
        })}
      />,
    );

    expect(screen.getByRole("dialog", { name: /latest version/i })).toBeInTheDocument();
    expect(screen.getByText(/Current version:/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Release Notes/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Close/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Got it/i })).toBeInTheDocument();
  });

  it("upToDate: shows release notes when changelog has content", () => {
    render(
      <ChangelogModal
        {...baseProps({
          variant: "upToDate",
          changelog: "Patch notes",
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: /Release Notes/i })).toBeInTheDocument();
    expect(screen.getByText(/Patch notes/)).toBeInTheDocument();
  });

  it("updateAvailable: shows version comparison and update button", async () => {
    const onUpdate = vi.fn();
    render(
      <ChangelogModal
        {...baseProps({
          variant: "updateAvailable",
          latestVersion: "6.0.0",
          onUpdate,
        })}
      />,
    );

    expect(screen.getByRole("dialog", { name: /Update Available/i })).toBeInTheDocument();
    expect(screen.getByText(/Current:/i)).toBeInTheDocument();
    expect(screen.getByText(/Latest:/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /What's New/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Update Now/i }));
    expect(onUpdate).toHaveBeenCalledTimes(1);
  });

  it("updateAvailable: shows in-progress status and disables close/update", () => {
    render(
      <ChangelogModal
        {...baseProps({
          variant: "updateAvailable",
          latestVersion: "6.0.0",
          updating: true,
          updateState: updateState({ in_progress: true }),
        })}
      />,
    );

    expect(screen.getByRole("dialog", { name: /Updating/i })).toBeInTheDocument();
    expect(screen.getByText(/Update in progress/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Close/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Updating\.\.\./i })).toBeDisabled();
  });

  it("updateAvailable: shows error status from updateState", () => {
    render(
      <ChangelogModal
        {...baseProps({
          variant: "updateAvailable",
          latestVersion: "6.0.0",
          updateState: updateState({ last_result: "error", last_error: "network timeout" }),
        })}
      />,
    );

    expect(screen.getByText(/Update failed: network timeout/i)).toBeInTheDocument();
  });

  it("updateAvailable: binary install shows download link with size", () => {
    render(
      <ChangelogModal
        {...baseProps({
          variant: "updateAvailable",
          latestVersion: "6.0.0",
          installationType: "binary",
          binaryDownloadUrl: "https://example.com/qbitrr.bin",
          binaryDownloadName: "qbitrr.bin",
          binaryDownloadSize: 2 * 1024 * 1024,
        })}
      />,
    );

    const download = screen.getByRole("link", { name: /Download Update/i });
    expect(download).toHaveAttribute("href", "/web/download-update");
    expect(download).toHaveAttribute("download", "qbitrr.bin");
    expect(screen.getByText(/\(2\.0 MB\)/i)).toBeInTheDocument();
  });

  it("updateAvailable: binary install shows error when download URL missing", () => {
    render(
      <ChangelogModal
        {...baseProps({
          variant: "updateAvailable",
          latestVersion: "6.0.0",
          installationType: "binary",
          binaryDownloadError: "CDN unreachable",
        })}
      />,
    );

    expect(screen.getByText(/CDN unreachable/i)).toBeInTheDocument();
  });
});
