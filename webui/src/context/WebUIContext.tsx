import { createContext, useCallback, useContext, useEffect, useMemo, useState, type JSX, type ReactNode } from "react";
import { getConfig, updateConfig } from "../api/client";
import { useToast } from "./ToastContext";

type ViewDensity = "comfortable" | "compact";
type Theme = "light" | "dark";

interface WebUISettings {
  liveArr: boolean;
  groupSonarr: boolean;
  groupLidarr: boolean;
  viewDensity: ViewDensity;
  theme: Theme;
}

interface WebUIContextValue {
  liveArr: boolean;
  groupSonarr: boolean;
  groupLidarr: boolean;
  viewDensity: ViewDensity;
  theme: Theme;
  setLiveArr: (value: boolean) => void;
  setGroupSonarr: (value: boolean) => void;
  setGroupLidarr: (value: boolean) => void;
  setViewDensity: (value: ViewDensity) => void;
  setTheme: (value: Theme) => void;
  loading: boolean;
}

const WebUIContext = createContext<WebUIContextValue | null>(null);

export function WebUIProvider({ children }: { children: ReactNode }): JSX.Element {
  const [settings, setSettings] = useState<WebUISettings>({
    liveArr: true,
    groupSonarr: true,
    groupLidarr: true,
    viewDensity: "comfortable",
    theme: "dark",
  });
  const [loading, setLoading] = useState(true);
  const { push } = useToast();

  // Load initial settings
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const config = await getConfig();
        const webui = config?.WebUI as Record<string, unknown> | undefined;

        // Check for config version warning in sessionStorage
        const warningMessage = sessionStorage.getItem("config_version_warning");
        if (warningMessage) {
          // Show error toast with longer duration for config version mismatch
          push(warningMessage, "error");
          // Clear the warning after showing it
          sessionStorage.removeItem("config_version_warning");
        }

        // Load from localStorage as fallback
        const storedDensity = localStorage.getItem("viewDensity") as ViewDensity | null;
        const storedTheme = localStorage.getItem("theme") as Theme | null;

        // Get theme and view density from backend or localStorage
        const backendTheme = webui?.Theme as string | undefined;
        const theme: Theme = storedTheme || (backendTheme?.toLowerCase() as Theme) || "dark";

        const backendDensity = webui?.ViewDensity as string | undefined;
        const viewDensity: ViewDensity = storedDensity || (backendDensity?.toLowerCase() as ViewDensity) || "comfortable";

        setSettings({
          liveArr: webui?.LiveArr === true,
          groupSonarr: webui?.GroupSonarr === true,
          groupLidarr: webui?.GroupLidarr === true,
          viewDensity,
          theme,
        });

        // Apply theme immediately
        document.documentElement.setAttribute('data-theme', theme);
      } catch {
        // settings load failed, defaults will be used
      } finally {
        setLoading(false);
      }
    };

    void loadSettings();
  }, [push]);

  // Auto-save settings to backend
  const saveSettings = useCallback(async (key: string, value: boolean | string) => {
    try {
      await updateConfig({ changes: { [`WebUI.${key}`]: value } });
    } catch {
      // save failed, non-critical
    }
  }, []);

  const setLiveArr = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, liveArr: value }));
    void saveSettings("LiveArr", value);
  }, [saveSettings]);

  const setGroupSonarr = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, groupSonarr: value }));
    void saveSettings("GroupSonarr", value);
  }, [saveSettings]);

  const setGroupLidarr = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, groupLidarr: value }));
    void saveSettings("GroupLidarr", value);
  }, [saveSettings]);

  const setViewDensity = useCallback((value: ViewDensity) => {
    setSettings(prev => ({ ...prev, viewDensity: value }));
    // Store in localStorage for instant application
    localStorage.setItem("viewDensity", value);
    // Save to backend with proper capitalization (Comfortable or Compact)
    const capitalizedDensity = value === "comfortable" ? "Comfortable" : "Compact";
    void saveSettings("ViewDensity", capitalizedDensity);
  }, [saveSettings]);

  const setTheme = useCallback((value: Theme) => {
    setSettings(prev => ({ ...prev, theme: value }));
    // Store in localStorage for instant application
    localStorage.setItem("theme", value);
    // Apply theme immediately to DOM
    document.documentElement.setAttribute('data-theme', value);
    // Save to backend with proper capitalization (Light or Dark)
    const capitalizedTheme = value === "light" ? "Light" : "Dark";
    void saveSettings("Theme", capitalizedTheme);
  }, [saveSettings]);

  const value = useMemo<WebUIContextValue>(() => ({
    liveArr: settings.liveArr,
    groupSonarr: settings.groupSonarr,
    groupLidarr: settings.groupLidarr,
    viewDensity: settings.viewDensity,
    theme: settings.theme,
    setLiveArr,
    setGroupSonarr,
    setGroupLidarr,
    setViewDensity,
    setTheme,
    loading,
  }), [settings, setLiveArr, setGroupSonarr, setGroupLidarr, setViewDensity, setTheme, loading]);

  return <WebUIContext.Provider value={value}>{children}</WebUIContext.Provider>;
}

export function useWebUI(): WebUIContextValue {
  const context = useContext(WebUIContext);
  if (!context) {
    throw new Error("useWebUI must be used within WebUIProvider");
  }
  return context;
}
