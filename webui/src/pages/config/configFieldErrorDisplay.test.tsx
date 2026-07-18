import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FieldGroup } from "./configFieldComponents";
import type { FieldDefinition, ValidationError } from "./configTypes";

vi.mock("../../context/WebUIContext", () => ({
  useWebUI: () => ({
    liveArr: true,
    viewDensity: "comfortable" as const,
    theme: "dark" as const,
    setLiveArr: () => undefined,
    setViewDensity: () => undefined,
    setTheme: () => undefined,
  }),
}));

function renderFieldGroup(errors: ValidationError[]) {
  const fields: FieldDefinition[] = [
    { label: "URI", path: ["URI"], type: "text" },
    {
      label: "Remove Torrent",
      path: ["Torrent", "SeedingMode", "RemoveTorrent"],
      type: "select",
      options: ["Do not remove (-1)", "On max seeding time (2)"],
    },
  ];
  return render(
    <FieldGroup
      title="Seeding"
      fields={fields}
      state={{ URI: "", Torrent: { SeedingMode: { RemoveTorrent: 2 } } }}
      basePath={[]}
      onChange={() => undefined}
      sectionKey="Lidarr"
      validationErrors={errors}
    />
  );
}

describe("FieldGroup validation highlighting", () => {
  it("highlights invalid fields and shows messages", () => {
    renderFieldGroup([
      { path: ["Lidarr", "URI"], message: "URI must be set" },
      {
        path: ["Lidarr", "Torrent", "SeedingMode", "RemoveTorrent"],
        message: "Remove Torrent is invalid",
      },
    ]);

    expect(screen.getByText("URI must be set")).toBeInTheDocument();
    expect(screen.getByText("Remove Torrent is invalid")).toBeInTheDocument();
    expect(document.querySelector('[data-field-path="Lidarr.URI"]')).toHaveClass(
      "field--invalid"
    );
    expect(
      document.querySelector(
        '[data-field-path="Lidarr.Torrent.SeedingMode.RemoveTorrent"]'
      )
    ).toHaveClass("field--invalid");
  });
});
