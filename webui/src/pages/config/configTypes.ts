import type { ConfigDocument } from "../../api/types";

type FieldType = "text" | "number" | "checkbox" | "password" | "select" | "tags" | "duration";

export interface ValidationContext {
  root: ConfigDocument;
  section?: ConfigDocument | null;
  sectionKey?: string;
}

type FieldValidator = (value: unknown, context: ValidationContext) => string | undefined;

export interface FieldDefinition {
  label: string;
  path?: string[];
  type: FieldType;
  options?: string[];
  placeholder?: string;
  description?: string;
  parse?: (value: string | boolean) => unknown;
  format?: (value: unknown) => string | boolean | string[];
  sectionName?: boolean;
  secure?: boolean;
  required?: boolean;
  validate?: FieldValidator;
  fullWidth?: boolean;
  /** For type "duration": base unit for the config key (seconds or minutes). */
  nativeUnit?: "seconds" | "minutes";
  /** For type "duration: allow -1 (disabled). */
  allowNegative?: boolean;
  /** When true, show hint that the setting applies live without a full restart. */
  applyLive?: boolean;
  /** When true, show hint that saving requires a component or app restart. */
  requiresRestart?: boolean;
}

export interface ValidationError {
  path: string[];
  message: string;
}

export const SERVARR_SECTION_REGEX = /^(radarr|sonarr|lidarr)([.-]|$)/i;
export const QBIT_SECTION_REGEX = /^qBit(-.*)?$/i;
/** Matches backend REDACTED_PLACEHOLDER; when API key equals this, test uses instanceKey. */
export const REDACTED_PLACEHOLDER = "[redacted]";

export const IMPORT_MODE_OPTIONS = ["Move", "Copy", "Auto"];

export const REMOVE_TORRENT_OPTIONS = [
  "Do not remove (-1)",
  "On max upload ratio (1)",
  "On max seeding time (2)",
  "On ratio OR time (3)",
  "On ratio AND time (4)",
];







export const SENTENCE_END = /(.+?[.!?])(\s|$)/;
