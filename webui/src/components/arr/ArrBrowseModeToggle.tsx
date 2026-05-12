import type { JSX } from "react";
import type { ArrBrowseMode } from "../../hooks/useArrBrowseMode";

interface ArrBrowseModeToggleProps {
  mode: ArrBrowseMode;
  onChange: (mode: ArrBrowseMode) => void;
  idPrefix: string;
}

export function ArrBrowseModeToggle({
  mode,
  onChange,
  idPrefix,
}: ArrBrowseModeToggleProps): JSX.Element {
  return (
    <div
      className="inline"
      style={{ gap: 6 }}
      role="group"
      aria-label="Browse layout"
    >
      <button
        type="button"
        className={`btn text-sm ${mode === "list" ? "active" : "ghost"}`}
        onClick={() => onChange("list")}
        id={`${idPrefix}-browse-list`}
      >
        List
      </button>
      <button
        type="button"
        className={`btn text-sm ${mode === "icon" ? "active" : "ghost"}`}
        onClick={() => onChange("icon")}
        id={`${idPrefix}-browse-icon`}
      >
        Icon
      </button>
    </div>
  );
}
