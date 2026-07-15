import React, { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import ReactMarkdown from "react-markdown";
import Select from "react-select";
import type { ConfigDocument } from "../../api/types";
import {
  DURATION_UNITS,
  durationDisplayToValue,
  parseDurationDisplay,
  type DurationUnit,
} from "../../config/durationUtils";
import { getSelectStyles } from "../../config/reactSelectTheme";
import { getTooltip } from "../../config/tooltips";
import {
  getArrTorrentHandlingSummary,
} from "../../config/torrentHandlingSummary";
import { IconImage } from "../../components/IconImage";
import { TagInput } from "../../components/TagInput";
import { useWebUI } from "../../context/WebUIContext";
import AddIcon from "../../icons/plus.svg";
import DeleteIcon from "../../icons/trash.svg";
import RefreshIcon from "../../icons/refresh-arrow.svg";
import VisibilityIcon from "../../icons/visibility.svg";
import { extractTooltipSummary } from "./configFields";
import { getValue } from "./configDocumentUtils";
import {
  QBIT_SECTION_REGEX,
  SERVARR_SECTION_REGEX,
  type FieldDefinition,
} from "./configTypes";

export interface FieldGroupProps {
  title: string | null;
  fields: FieldDefinition[];
  state: ConfigDocument | ConfigDocument[keyof ConfigDocument] | null;
  basePath: string[];
  onChange: (path: string[], def: FieldDefinition, value: unknown) => void;
  onRenameSection?: (oldName: string, newName: string) => void;
  defaultOpen?: boolean;
  qualityProfiles?: Array<{ id: number; name: string }>;
  sectionKey?: string;
  qbitTrackers?: boolean;
}

/** Regex for valid in-progress numeric input: empty, "-", or a valid number string */
const NUMERIC_INPUT_RE = /^-?\d*\.?\d*$/;

export function NumberInput({
  value,
  onChange,
  placeholder,
}: {
  value: unknown;
  onChange: (v: string) => void;
  placeholder?: string;
}): JSX.Element {
  const n = Number(value);
  const externalStr = Number.isFinite(n) ? String(n) : "0";
  const [localValue, setLocalValue] = useState(externalStr);
  const isEditing = useRef(false);

  useEffect(() => {
    if (!isEditing.current) {
      queueMicrotask(() => setLocalValue(externalStr));
    }
  }, [externalStr]);

  return (
    <input
      type="text"
      inputMode="decimal"
      value={localValue}
      onFocus={() => {
        isEditing.current = true;
      }}
      onBlur={() => {
        isEditing.current = false;
        setLocalValue(externalStr);
      }}
      onChange={(e) => {
        const raw = e.target.value;
        // Only allow numeric characters, optional leading minus, optional decimal
        if (raw !== "" && !NUMERIC_INPUT_RE.test(raw)) return;
        setLocalValue(raw);
        onChange(raw);
      }}
      placeholder={placeholder}
    />
  );
}

export function DurationInput({
  value,
  onChange,
  placeholder,
  nativeUnit = "seconds",
  allowNegative = false,
}: {
  value: unknown;
  onChange: (v: string | number) => void;
  placeholder?: string;
  nativeUnit?: "seconds" | "minutes";
  allowNegative?: boolean;
}): JSX.Element {
  const fallback = allowNegative ? -1 : 0;
  const display = parseDurationDisplay(value, nativeUnit, fallback);
  const [num, setNum] = useState(display.number);
  const [unit, setUnit] = useState<DurationUnit>(display.unit);
  const [rawInput, setRawInput] = useState<string | null>(null);
  const isEditing = useRef(false);
  const unitDirty = useRef(false);

  useEffect(() => {
    if (!isEditing.current) {
      const d = parseDurationDisplay(value, nativeUnit, fallback);
      queueMicrotask(() => {
        setNum(d.number);
        if (!unitDirty.current) {
          setUnit(d.unit);
        }
      });
    }
  }, [value, nativeUnit, fallback]);

  const handleNumChange = (raw: string) => {
    if (raw !== "" && !NUMERIC_INPUT_RE.test(raw)) return;
    setRawInput(raw);
    if (raw === "" || raw === "-") return;
    const n = Number(raw);
    if (!Number.isFinite(n)) return;
    setNum(n);
    unitDirty.current = false;
    const out = durationDisplayToValue(n, unit, nativeUnit, allowNegative);
    onChange(out);
  };

  const handleUnitChange = (newUnit: DurationUnit) => {
    setUnit(newUnit);
    unitDirty.current = true;
    if (rawInput === "" || rawInput === "-") {
      return;
    }
    const effectiveNum = rawInput !== null ? Number(rawInput) : num;
    if (!Number.isFinite(effectiveNum)) {
      return;
    }
    setNum(effectiveNum);
    unitDirty.current = false;
    const out = durationDisplayToValue(effectiveNum, newUnit, nativeUnit, allowNegative);
    onChange(out);
  };

  const handleFocus = () => {
    isEditing.current = true;
    unitDirty.current = false;
    setRawInput(num === -1 && allowNegative ? "" : String(num));
  };

  const handleBlur = () => {
    isEditing.current = false;
    const pendingRaw = rawInput;
    setRawInput(null);

    if (pendingRaw === "" && allowNegative) {
      unitDirty.current = false;
      setNum(-1);
      onChange(-1);
      return;
    }

    if (pendingRaw === "" || pendingRaw === "-") {
      const d = parseDurationDisplay(value, nativeUnit, fallback);
      setNum(d.number);
      if (!unitDirty.current) {
        setUnit(d.unit);
      }
      unitDirty.current = false;
      return;
    }

    unitDirty.current = false;
    const d = parseDurationDisplay(value, nativeUnit, fallback);
    setNum(d.number);
    setUnit(d.unit);
  };

  const handleSetDisabled = () => {
    if (!allowNegative) return;
    isEditing.current = false;
    unitDirty.current = false;
    setRawInput(null);
    setNum(-1);
    setUnit("s");
    onChange(-1);
  };

  const isDisabledValue = num === -1 && allowNegative && rawInput === null;
  const displayVal =
    rawInput !== null ? rawInput : isDisabledValue ? "" : String(num);
  const inputPlaceholder =
    allowNegative && (isDisabledValue || rawInput === "")
      ? "Disabled"
      : placeholder;

  return (
    <div className="duration-input">
      <input
        type="text"
        value={displayVal}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onChange={(e) => handleNumChange(e.target.value)}
        placeholder={inputPlaceholder}
      />
      <select
        value={unit}
        onChange={(e) => handleUnitChange(e.target.value as DurationUnit)}
        aria-label="Duration unit"
      >
        {DURATION_UNITS.map((u) => (
          <option key={u.value} value={u.value}>
            {u.label}
          </option>
        ))}
      </select>
      {allowNegative ? (
        <button
          type="button"
          className="btn small ghost duration-input__disabled"
          onClick={handleSetDisabled}
        >
          Use disabled
        </button>
      ) : null}
    </div>
  );
}

export function FieldGroup({
  title,
  fields,
  state,
  basePath,
  onChange,
  onRenameSection,
  defaultOpen = false,
  qualityProfiles = [],
  sectionKey,
  qbitTrackers = false,
}: FieldGroupProps): JSX.Element {
  const { theme } = useWebUI();
  const selectStyles = useMemo(() => getSelectStyles(theme === 'dark'), [theme]);
  const sectionName = sectionKey ?? basePath[0] ?? "";

  if (title === "Quality Profile Mappings") {
    const mappings = (getValue(state as ConfigDocument, ["EntrySearch", "QualityProfileMappings"]) ?? {}) as Record<string, string>;
    const mappingEntries = Object.entries(mappings);

    // Check if credentials exist (URI and APIKey)
    const hasCredentials = Boolean(
      getValue(state as ConfigDocument, ["URI"]) &&
        getValue(state as ConfigDocument, ["APIKey"])
    );
    const hasProfiles = qualityProfiles.length > 0;

    const handleAddMapping = () => {
      const nextMappings = { ...mappings, "": "" };
      onChange([...basePath, "EntrySearch", "QualityProfileMappings"], {} as FieldDefinition, nextMappings);
    };

    const handleUpdateMapping = (oldKey: string, newKey: string, newValue: string) => {
      const nextMappings = { ...mappings };
      if (oldKey !== newKey) {
        delete nextMappings[oldKey];
      }
      if (newKey.trim()) {
        nextMappings[newKey.trim()] = newValue.trim();
      }
      onChange([...basePath, "EntrySearch", "QualityProfileMappings"], {} as FieldDefinition, nextMappings);
    };

    const handleDeleteMapping = (key: string) => {
      const nextMappings = { ...mappings };
      delete nextMappings[key];
      onChange([...basePath, "EntrySearch", "QualityProfileMappings"], {} as FieldDefinition, nextMappings);
    };

    return (
      <details className="config-section" open={defaultOpen}>
        <summary>{title}</summary>
        <div className="config-section__body">
          <div className="field-description" style={{ marginBottom: '1rem' }}>
            Map main quality profile names to temporary profile names. Items will be downgraded to the temp profile when not found, then upgraded back to the main profile when available.
          </div>

          {!hasCredentials ? (
            <div className="alert warning">
              ⚠️ Please configure URI and API Key first, then click "Test Connection" to load quality profiles
            </div>
          ) : !hasProfiles ? (
            <div className="alert info">
              ℹ️ Click "Test Connection" above to load quality profiles from your {sectionName} instance
            </div>
          ) : (
            <>
              <div className="profile-mappings-grid">
                {mappingEntries.map(([mainProfile, tempProfile], index) => (
                  <div key={index} className="profile-mapping-row">
                    <div className="field">
                      <label>Main Profile</label>
                      <Select
                        options={qualityProfiles.map((p) => ({
                          value: p.name,
                          label: p.name,
                        }))}
                        value={
                          mainProfile
                            ? { value: mainProfile, label: mainProfile }
                            : null
                        }
                        onChange={(option) =>
                          handleUpdateMapping(
                            mainProfile,
                            option?.value || "",
                            tempProfile
                          )
                        }
                        placeholder="Select main profile..."
                        isClearable
                        styles={selectStyles}
                        classNamePrefix="react-select"
                      />
                    </div>
                    <div className="field">
                      <label>Temp Profile</label>
                      <Select
                        options={qualityProfiles.map((p) => ({
                          value: p.name,
                          label: p.name,
                        }))}
                        value={
                          tempProfile
                            ? { value: tempProfile, label: tempProfile }
                            : null
                        }
                        onChange={(option) =>
                          handleUpdateMapping(
                            mainProfile,
                            mainProfile,
                            option?.value || ""
                          )
                        }
                        placeholder="Select temp profile..."
                        isClearable
                        styles={selectStyles}
                        classNamePrefix="react-select"
                      />
                    </div>
                    <button
                      className="btn ghost icon-only"
                      type="button"
                      onClick={() => handleDeleteMapping(mainProfile)}
                      title="Delete mapping"
                    >
                      <IconImage src={DeleteIcon} />
                    </button>
                  </div>
                ))}
              </div>
              <div className="config-actions">
                <button className="btn" type="button" onClick={handleAddMapping}>
                  <IconImage src={AddIcon} />
                  Add Profile Mapping
                </button>
              </div>
            </>
          )}
        </div>
      </details>
    );
  }

  if (title === "Trackers") {
    const trackerPath = qbitTrackers ? ["Trackers"] : ["Torrent", "Trackers"];
    const trackers = (getValue(state as ConfigDocument, trackerPath) ?? []) as ConfigDocument[];
    const handleAddTracker = () => {
      const nextTrackers = [
        ...trackers,
        {
          Name: "",
          URI: "",
          Priority: 0,
          SortTorrents: false,
          MaximumETA: -1,
          DownloadRateLimit: -1,
          UploadRateLimit: -1,
          MaxUploadRatio: -1,
          MaxSeedingTime: -1,
          AddTrackerIfMissing: false,
          RemoveIfExists: false,
          SuperSeedMode: false,
          AddTags: [],
          HitAndRunMode: "disabled",
          MinSeedRatio: 1.0,
          MinSeedingTimeDays: 0,
          HitAndRunMinimumDownloadPercent: 10,
          HitAndRunPartialSeedRatio: 1.0,
          TrackerUpdateBuffer: 0,
        },
      ];
      onChange([...basePath, ...trackerPath], {} as FieldDefinition, nextTrackers);
    };
    const handleDeleteTracker = (index: number) => {
      const nextTrackers = [...trackers];
      nextTrackers.splice(index, 1);
      onChange([...basePath, ...trackerPath], {} as FieldDefinition, nextTrackers);
    };
    return (
      <details className="config-section" open={defaultOpen}>
        <summary>{title}</summary>
        <div className="config-section__body">
          {qbitTrackers && (
            <div className="alert info" style={{ marginBottom: '12px' }}>
              Shared tracker configs inherited by all Arr instances on this qBit instance.
            </div>
          )}
          {!qbitTrackers && (
            <div className="alert info" style={{ marginBottom: '12px' }}>
              Trackers inherited from qBit instance. Add here only to override specific settings.
            </div>
          )}
          <div className="tracker-grid">
            {trackers.map((tracker, index) => (
              <TrackerCard
                key={index}
                fields={fields}
                state={tracker}
                basePath={[...basePath, ...trackerPath, String(index)]}
                onChange={onChange}
                onDelete={() => handleDeleteTracker(index)}
              />
            ))}
          </div>
          <div className="config-actions">
            <button className="btn" type="button" onClick={handleAddTracker}>
              <IconImage src={AddIcon} />
              Add Tracker
            </button>
          </div>
        </div>
      </details>
    );
  }

  const renderedFields = fields.map((field) => {
    if (field.sectionName) {
      if (!sectionName) {
        return null;
      }
      const tooltip = getTooltip([sectionName]);

      // Determine expected prefix for Arr instances
      let expectedPrefix: string | undefined;
      if (sectionName.startsWith("Radarr")) {
        expectedPrefix = "Radarr";
      } else if (sectionName.startsWith("Sonarr")) {
        expectedPrefix = "Sonarr";
      } else if (sectionName.startsWith("Lidarr")) {
        expectedPrefix = "Lidarr";
      }

      return (
        <SectionNameField
          key={`${sectionName}.__name`}
          label={field.label}
          tooltip={tooltip}
          currentName={sectionName}
          placeholder={field.placeholder}
          expectedPrefix={expectedPrefix}
          onRename={(newName) => onRenameSection?.(sectionName, newName)}
        />
      );
    }

    const pathSegments = field.path ?? [];
    const path = [...basePath, ...pathSegments];
    const key = path.join('.');
    const rawValue = path.length > 0
      ? getValue(state as ConfigDocument, path)
      : undefined;
    const formatted =
      field.format?.(rawValue) ??
      (field.type === "checkbox" ? Boolean(rawValue) : String(rawValue ?? ""));
    const tooltip = getTooltip(path);
    const description =
      field.description ??
      extractTooltipSummary(tooltip) ??
      (field.type === "checkbox"
        ? `Enable or disable ${field.label}.`
        : `Set the ${field.label} value.`);

    const isArrInstance =
      (basePath.length > 0 && SERVARR_SECTION_REGEX.test(basePath[0] ?? "")) ||
      (!!sectionName && SERVARR_SECTION_REGEX.test(sectionName));
    const isArrApiKey = isArrInstance && (field.path?.[field.path.length - 1] ?? "") === "APIKey";
    const fieldClassName = field.fullWidth ? "field field--full-width" : "field";

    if (field.secure) {
      return (
        <SecureField
          key={key}
          label={field.label}
          tooltip={tooltip}
          description={description}
          value={String(rawValue ?? '')}
          placeholder={field.placeholder}
          canRefresh={!isArrApiKey}
          onChange={(val) => onChange(path, field, val)}
        />
      );
    }



    if (field.type === "checkbox") {
      return (
        <div key={key} className="checkbox-field">
          <label title={tooltip}>
            <input
              type="checkbox"
              checked={Boolean(formatted)}
              onChange={(event) => onChange(path, field, event.target.checked)}
            />
            {field.label}
          </label>
          {description && <div className="field-description">{description}</div>}
        </div>
      );
    }
    if (field.type === "select") {
      // Special handling for Theme field - apply immediately without save
      const isThemeField = field.label === "Theme" && path.join('.') === "WebUI.Theme";

      // Normalize the formatted value for theme field (case-insensitive)
      let displayValue = formatted;
      if (isThemeField && typeof formatted === "string") {
        const normalizedLower = formatted.toLowerCase();
        if (normalizedLower === "light") {
          displayValue = "Light";
        } else if (normalizedLower === "dark") {
          displayValue = "Dark";
        } else {
          // Default to Dark if invalid
          displayValue = "Dark";
        }
      }

      return (
        <div key={key} className={fieldClassName}>
          <label title={tooltip}>{field.label}</label>
          <Select
            options={(field.options ?? []).map(o => ({ value: o, label: o }))}
            value={displayValue ? { value: displayValue, label: displayValue } : null}
            onChange={(option) => {
              const newValue = option?.value || "";
              onChange(path, field, newValue);

              // If this is the theme field, apply immediately
              if (isThemeField && typeof newValue === "string" && newValue) {
                const theme = newValue.toLowerCase() as "light" | "dark";
                document.documentElement.setAttribute('data-theme', theme);
                localStorage.setItem("theme", theme);
              }
            }}
            styles={selectStyles}
          />
          {description && <div className="field-description">{description}</div>}
          {isThemeField && <div className="field-hint">Theme changes apply immediately</div>}
        </div>
      );
    }
    if (field.type === "number") {
      return (
        <div key={key} className={fieldClassName}>
          <label title={tooltip}>{field.label}</label>
          <NumberInput
            value={formatted}
            onChange={(v) => onChange(path, field, v)}
            placeholder={field.placeholder}
          />
          {description && <div className="field-description">{description}</div>}
        </div>
      );
    }
    if (field.type === "duration") {
      return (
        <div key={key} className={fieldClassName}>
          <label title={tooltip}>{field.label}</label>
          <DurationInput
            value={rawValue}
            onChange={(v) => onChange(path, field, v)}
            placeholder={field.placeholder}
            nativeUnit={field.nativeUnit ?? "seconds"}
            allowNegative={field.allowNegative ?? false}
          />
          {description && <div className="field-description">{description}</div>}
        </div>
      );
    }
    if (field.type === "password") {
      return (
        <div key={key} className={fieldClassName}>
          <label title={tooltip}>{field.label}</label>
          <input
            type="password"
            value={String(formatted)}
            onChange={(event) => onChange(path, field, event.target.value)}
            placeholder={field.placeholder}
          />
          {description && <div className="field-description">{description}</div>}
        </div>
      );
    }
    if (field.type === "tags") {
      // Ensure we always have an array
      let tags: string[] = [];

      if (Array.isArray(formatted)) {
        tags = formatted;
      } else if (Array.isArray(rawValue)) {
        tags = rawValue;
      } else if (typeof formatted === "string" && formatted) {
        tags = formatted.split(",").map(s => s.trim()).filter(Boolean);
      } else if (typeof rawValue === "string" && rawValue) {
        tags = rawValue.split(",").map(s => s.trim()).filter(Boolean);
      }

      return (
        <div key={key} className={fieldClassName}>
          <label title={tooltip}>{field.label}</label>
          <TagInput
            value={tags}
            onChange={(newTags) => {
              onChange(path, field, newTags);
            }}
            placeholder={field.placeholder}
          />
          {description && <div className="field-description">{description}</div>}
        </div>
      );
    }
    return (
      <div key={key} className={fieldClassName}>
        <label title={tooltip}>{field.label}</label>
        <input
          type="text"
          value={String(formatted)}
          onChange={(event) => onChange(path, field, event.target.value)}
          placeholder={field.placeholder}
        />
        {description && <div className="field-description">{description}</div>}
      </div>
    );
  });

  if (title) {
    return (
      <details className="config-section" open={defaultOpen}>
        <summary>{title}</summary>
        <div className="config-section__body field-grid">{renderedFields}</div>
      </details>
    );
  }

  return <div className="field-grid">{renderedFields}</div>;
}

export function TrackerCard({
  fields,
  state,
  basePath,
  onChange,
  onDelete,
}: {
  fields: FieldDefinition[];
  state: ConfigDocument | null;
  basePath: string[];
  onChange: (path: string[], def: FieldDefinition, value: unknown) => void;
  onDelete: () => void;
}): JSX.Element {
  const trackerName = (getValue(state, ["Name"]) as string) || "New Tracker";
  // state is the individual tracker object, so read with basePath=[]
  // but onChange needs the full basePath to update the correct location in formState
  const wrappedOnChange = useCallback(
    (path: string[], def: FieldDefinition, value: unknown) => {
      onChange([...basePath, ...path], def, value);
    },
    [basePath, onChange]
  );
  return (
    <details className="card tracker-card" open>
      <summary className="card-header">
        <span>{trackerName}</span>
        <button className="btn danger ghost" type="button" onClick={onDelete}>
          <IconImage src={DeleteIcon} />
        </button>
      </summary>
      <div className="card-body">
        <FieldGroup title={null} fields={fields} state={state} basePath={[]} onChange={wrappedOnChange} />
      </div>
    </details>
  );
}

export interface SectionNameFieldProps {
  label: string;
  currentName: string;
  placeholder?: string;
  tooltip?: string;
  expectedPrefix?: string;
  onRename: (newName: string) => void;
}

export function SectionNameField({
  label,
  currentName,
  placeholder,
  tooltip,
  expectedPrefix,
  onRename,
}: SectionNameFieldProps): JSX.Element {
  const [value, setValue] = useState(currentName);
  const description =
    extractTooltipSummary(tooltip) ?? `Rename the ${currentName} instance.`;

  useEffect(() => {
    const id = window.setTimeout(() => {
      setValue(currentName);
    }, 0);
    return () => window.clearTimeout(id);
  }, [currentName]);

  const commit = () => {
    const trimmed = value.trim();
    if (!trimmed) {
      setValue(currentName);
      return;
    }

    let adjustedName = trimmed;

    // Check if this is a qBit instance
    const isQbitInstance = QBIT_SECTION_REGEX.test(currentName);

    if (isQbitInstance) {
      // qBit instances must follow qBit-NAME format (or just "qBit" for default)
      if (trimmed === "qBit") {
        // Allow default name
        adjustedName = "qBit";
      } else if (!trimmed.startsWith("qBit-")) {
        // If user entered something without the prefix, prepend it
        adjustedName = `qBit-${trimmed}`;
      }

      // Validate format
      if (adjustedName !== "qBit" && !adjustedName.match(/^qBit-.+$/)) {
        alert(`qBit instance name must match format: qBit-NAME\nExample: qBit-seedbox`);
        setValue(currentName);
        return;
      }
    } else {
      // Enforce prefix if specified (for Arr instances)
      if (expectedPrefix && !trimmed.startsWith(expectedPrefix)) {
        // If user entered something without the prefix, prepend it
        adjustedName = expectedPrefix + (trimmed.startsWith("-") ? trimmed : `-${trimmed}`);
      }

      // Enforce format: (Rad|Son|Lid)arr-.+ (prefix-suffix with at least one character after dash)
      const formatRegex = /^(Radarr|Sonarr|Lidarr)-.+$/;
      if (!formatRegex.test(adjustedName)) {
        // Invalid format - show error and reset
        alert(`Instance name must match format: ${expectedPrefix || '(Rad|Son|Lid)arr'}-(name)\nExample: ${expectedPrefix || 'Radarr'}-Movies`);
        setValue(currentName);
        return;
      }
    }

    if (adjustedName !== currentName) {
      onRename(adjustedName);
    } else {
      setValue(currentName); // Reset if no actual change
    }
  };

  return (
    <div className="field">
      <label className="field-label">
        <span>{label}</span>
        {tooltip ? (
          <span className="help-icon" title={tooltip} aria-label={tooltip}>
            ?
          </span>
        ) : null}
      </label>
      {description ? <p className="field-description">{description}</p> : null}
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(event) => setValue(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            commit();
          } else if (event.key === "Escape") {
            event.preventDefault();
            setValue(currentName);
          }
        }}
      />
    </div>
  );
}

export interface SecureFieldProps {
  label: string;
  value: string;
  placeholder?: string;
  tooltip?: string;
  description?: string;
  canRefresh?: boolean;
  onChange: (value: string) => void;
}

export function SecureField({
  label,
  value,
  placeholder,
  tooltip,
  description,
  canRefresh = true,
  onChange,
}: SecureFieldProps): JSX.Element {
  const [showValue, setShowValue] = useState(false);

  const handleRefresh = () => {
    const newKey = (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function")
      ? crypto.randomUUID().replace(/-/g, "")
      : Array.from({ length: 32 }, () =>
          Math.floor(Math.random() * 16).toString(16)
        ).join("");
    onChange(newKey);
  };

  return (
    <div className="field secure-field">
      <label title={tooltip}>{label}</label>
      <div className="secure-field__input-group">
        <input
          type={showValue ? "text" : "password"}
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
        <button type="button" className="btn ghost" onClick={() => setShowValue(!showValue)}>
          <IconImage src={VisibilityIcon} />
        </button>
        {canRefresh && (
          <button type="button" className="btn ghost" onClick={handleRefresh}>
            <IconImage src={RefreshIcon} />
          </button>
        )}
      </div>
      {description && <div className="field-description">{description}</div>}
    </div>
  );
}

export function CategoryOverlapAlert({ messages }: { messages: string[] }): JSX.Element | null {
  if (!messages.length) return null;
  return (
    <div className="alert warning" style={{ marginBottom: 16 }} role="status">
      <strong>Category path overlap</strong>
      <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
        {messages.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </div>
  );
}

export function ArrTorrentSummary({
  state,
}: {
  state: ConfigDocument | ConfigDocument[keyof ConfigDocument] | null;
}): JSX.Element {
  const summary = useMemo(
    () => getArrTorrentHandlingSummary(state as ConfigDocument | null),
    [state]
  );
  return (
    <div className="torrent-handling-summary" aria-live="polite">
      <h3>How torrents are handled</h3>
      <div className="torrent-handling-summary-body markdown-content">
        <ReactMarkdown>{summary}</ReactMarkdown>
      </div>
    </div>
  );
}
