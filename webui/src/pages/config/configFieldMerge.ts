/**
 * Merge generated FieldDefinition stubs with FE overlays (validators, parse/format).
 * Overlay keys are dotted paths matching ``field.path.join(".")``.
 */
import type { FieldDefinition } from "./configTypes";

export type FieldOverlay = Partial<
  Omit<FieldDefinition, "path" | "label" | "type">
> & {
  /** Optional label override. */
  label?: string;
  type?: FieldDefinition["type"];
};

export function mergeFieldOverlays(
  generated: ReadonlyArray<FieldDefinition>,
  overlays: Record<string, FieldOverlay>,
): FieldDefinition[] {
  return generated.map((field) => {
    const key = (field.path ?? []).join(".");
    const overlay = overlays[key];
    if (!overlay) {
      return { ...field };
    }
    return { ...field, ...overlay, path: field.path, label: overlay.label ?? field.label };
  });
}
