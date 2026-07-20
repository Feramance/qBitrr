import type { ConfigDocument } from "../../api/types";
import { getCategoryCrossSectionIssues } from "../../config/categoryConfigValidation";
import equal from "fast-deep-equal";
import {
  AUTH_SETTINGS_FIELDS,
  getArrFieldSets,
  QBIT_FIELDS,
  SETTINGS_FIELDS,
  WEB_SETTINGS_FIELDS,
} from "./configFields";
import { flatten, getValue, isEmptyValue } from "./configDocumentUtils";
import {
  QBIT_SECTION_REGEX,
  SERVARR_SECTION_REGEX,
  type FieldDefinition,
  type ValidationContext,
  type ValidationError,
} from "./configTypes";

export function basicValidation(def: FieldDefinition, value: unknown): string | undefined {
  const label = def.label;
  const isRequired = def.required ?? (def.type === "number" || def.type === "select");
  switch (def.type) {
    case "text":
    case "password": {
      if (!isRequired) {
        return undefined;
      }
      if (isEmptyValue(value)) {
        return `${label} is required.`;
      }
      return undefined;
    }
    case "number": {
      if (value === null || value === undefined || value === "") {
        return isRequired ? `${label} is required.` : undefined;
      }
      const num = typeof value === "number" ? value : Number(value);
      if (!Number.isFinite(num)) {
        return `${label} must be a valid number.`;
      }
      return undefined;
    }
    case "checkbox": {
      if (value === null || value === undefined) {
        return isRequired ? `${label} is required.` : undefined;
      }
      if (typeof value !== "boolean") {
        return `${label} must be true or false.`;
      }
      return undefined;
    }
    case "select": {
      if (isEmptyValue(value)) {
        return `${label} is required.`;
      }
      if (typeof value !== "string") {
        return `${label} must be selected.`;
      }
      if (def.options && !def.options.includes(value)) {
        return `${label} must be one of ${def.options.join(", ")}.`;
      }
      return undefined;
    }
    default:
      return undefined;
  }
}

export function validateFieldGroup(
  errors: ValidationError[],
  fields: FieldDefinition[],
  state: ConfigDocument | null,
  basePath: string[],
  context: ValidationContext
): void {
  if (!state) return;
  for (const field of fields) {
    if (field.sectionName) {
      continue;
    }
    const pathSegments = field.path ?? [];
    const rawValue = pathSegments.length
      ? getValue(state as ConfigDocument, pathSegments)
      : undefined;
    // When field has both format and parse, validate the stored (raw) value; otherwise use formatted value.
    // For type "select", use formatted value for basicValidation so stored numbers (e.g. RemoveTorrent -1..4) pass.
    const value =
      field.type === "select" && field.format
        ? field.format(rawValue)
        : field.format && field.parse
          ? rawValue
          : field.format
            ? field.format(rawValue)
            : rawValue;
    const fullPath = [...basePath, ...pathSegments];
    const baseError = basicValidation(field, value);
    if (baseError) {
      errors.push({ path: fullPath, message: baseError });
      continue;
    }
    if (field.validate) {
      const customError = field.validate(value, context);
      if (customError) {
        errors.push({ path: fullPath, message: customError });
      }
    }
  }
}

export function isManagedArrSection(section: ConfigDocument | null): boolean {
  return Boolean(getValue(section, ["Managed"]));
}

export function isEnabledQbitSection(section: ConfigDocument | null): boolean {
  return !getValue(section, ["Disabled"]);
}

export function validateSection(
  formState: ConfigDocument | null,
  sectionKey: string
): ValidationError[] {
  if (!formState) return [];
  const value = formState[sectionKey];
  if (!value || typeof value !== "object") {
    return [];
  }
  const section = value as ConfigDocument;
  const errors: ValidationError[] = [];
  const sectionContext: ValidationContext = { root: formState, section, sectionKey };

  if (QBIT_SECTION_REGEX.test(sectionKey)) {
    if (!isEnabledQbitSection(section)) {
      return [];
    }
    validateFieldGroup(errors, QBIT_FIELDS, section, [sectionKey], sectionContext);
    return errors;
  }

  if (SERVARR_SECTION_REGEX.test(sectionKey)) {
    if (!isManagedArrSection(section)) {
      return [];
    }
    const fieldSets = getArrFieldSets(sectionKey);
    validateFieldGroup(errors, fieldSets.generalFields, section, [sectionKey], sectionContext);
    validateFieldGroup(errors, fieldSets.entryFields, section, [sectionKey], sectionContext);
    validateFieldGroup(errors, fieldSets.entryOmbiFields, section, [sectionKey], sectionContext);
    validateFieldGroup(errors, fieldSets.entryOverseerrFields, section, [sectionKey], sectionContext);
    validateFieldGroup(errors, fieldSets.torrentFields, section, [sectionKey], sectionContext);
    validateFieldGroup(errors, fieldSets.seedingFields, section, [sectionKey], sectionContext);
    return errors;
  }

  if (sectionKey === "Settings") {
    validateFieldGroup(errors, SETTINGS_FIELDS, formState, [], { root: formState });
  } else if (sectionKey === "WebUI") {
    validateFieldGroup(errors, WEB_SETTINGS_FIELDS, formState, [], { root: formState });
    validateFieldGroup(errors, AUTH_SETTINGS_FIELDS, formState, [], { root: formState });
  } else if (sectionKey === "Authentication") {
    validateFieldGroup(errors, AUTH_SETTINGS_FIELDS, formState, [], { root: formState });
  }

  return errors;
}

export function sectionHasCategoryChanges(
  sectionKey: string,
  formState: ConfigDocument,
  originalConfig: ConfigDocument | null
): boolean {
  const categoryPath = `${sectionKey}.Category`;
  const flattenedOriginal = flatten(originalConfig ?? {});
  const flattenedCurrent = flatten(formState);
  return !equal(flattenedCurrent[categoryPath], flattenedOriginal[categoryPath]);
}

export function validateSectionsForSave(
  formState: ConfigDocument | null,
  sectionKeys: string[],
  originalConfig: ConfigDocument | null,
  includeCategoryCrossCheck: boolean
): ValidationError[] {
  if (!formState) return [];
  const errors: ValidationError[] = [];
  for (const sectionKey of sectionKeys) {
    errors.push(...validateSection(formState, sectionKey));
  }
  if (includeCategoryCrossCheck) {
    for (const issue of getCategoryCrossSectionIssues(formState)) {
      errors.push(issue);
    }
  } else {
    const categoryTouched = sectionKeys.some((key) =>
      sectionHasCategoryChanges(key, formState, originalConfig)
    );
    if (categoryTouched) {
      for (const issue of getCategoryCrossSectionIssues(formState)) {
        errors.push(issue);
      }
    }
  }
  return errors;
}

export function getChangedSectionKeys(
  formState: ConfigDocument,
  originalConfig: ConfigDocument | null,
  pendingRenames: Map<string, string>
): string[] {
  const flattenedOriginal = flatten(originalConfig ?? {});
  const flattenedCurrent = flatten(formState);
  const sections = new Set<string>();

  for (const [key, value] of Object.entries(flattenedCurrent)) {
    if (!equal(value, flattenedOriginal[key])) {
      sections.add(key.split(".")[0] ?? key);
    }
  }
  for (const key of Object.keys(flattenedOriginal)) {
    if (!(key in flattenedCurrent)) {
      sections.add(key.split(".")[0] ?? key);
    }
  }
  for (const [oldName] of pendingRenames) {
    sections.add(oldName);
    const newName = pendingRenames.get(oldName);
    if (newName) {
      sections.add(newName);
    }
  }
  for (const [key, value] of Object.entries(originalConfig ?? {})) {
    if (
      !(key in formState) &&
      SERVARR_SECTION_REGEX.test(key) &&
      value &&
      typeof value === "object"
    ) {
      sections.add(key);
    }
  }

  return [...sections];
}
