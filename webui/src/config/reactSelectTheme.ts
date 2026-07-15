import type { CSSObjectWithLabel } from "react-select";

/** Shared react-select style overrides for Config and Logs views. */
export function getSelectStyles(isDark: boolean) {
  return {
    control: (base: CSSObjectWithLabel) => ({
      ...base,
      background: isDark ? "#0f131a" : "#ffffff",
      color: isDark ? "#eaeef2" : "#1d1d1f",
      borderColor: isDark ? "#2a2f36" : "#d2d2d7",
      minHeight: "38px",
      boxShadow: "none",
      "&:hover": {
        borderColor: isDark ? "#3a4149" : "#b8b8bd",
      },
    }),
    menu: (base: CSSObjectWithLabel) => ({
      ...base,
      background: isDark ? "#0f131a" : "#ffffff",
      borderColor: isDark ? "#2a2f36" : "#d2d2d7",
      border: `1px solid ${isDark ? "#2a2f36" : "#d2d2d7"}`,
    }),
    option: (
      base: CSSObjectWithLabel,
      state: { isFocused: boolean },
    ) => ({
      ...base,
      background: state.isFocused
        ? isDark
          ? "rgba(59, 130, 246, 0.15)"
          : "rgba(37, 99, 235, 0.1)"
        : isDark
          ? "#0f131a"
          : "#ffffff",
      color: isDark ? "#eaeef2" : "#1d1d1f",
      "&:active": {
        background: isDark
          ? "rgba(59, 130, 246, 0.25)"
          : "rgba(37, 99, 235, 0.2)",
      },
    }),
    singleValue: (base: CSSObjectWithLabel) => ({
      ...base,
      color: isDark ? "#eaeef2" : "#1d1d1f",
    }),
    input: (base: CSSObjectWithLabel) => ({
      ...base,
      color: isDark ? "#eaeef2" : "#1d1d1f",
    }),
    placeholder: (base: CSSObjectWithLabel) => ({
      ...base,
      color: isDark ? "#9aa3ac" : "#6e6e73",
    }),
    menuList: (base: CSSObjectWithLabel) => ({
      ...base,
      padding: "4px",
    }),
  };
}
