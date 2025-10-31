import { createContext, useCallback, useContext, useEffect, useState, type JSX, type ReactNode } from "react";
import { getConfig, updateConfig } from "../api/client";

type ViewDensity = "comfortable" | "compact";

interface WebUISettings {
  liveArr: boolean;
  groupSonarr: boolean;
  viewDensity: ViewDensity;
}

interface WebUIContextValue {
  liveArr: boolean;
  groupSonarr: boolean;
  viewDensity: ViewDensity;
  setLiveArr: (value: boolean) => void;
  setGroupSonarr: (value: boolean) => void;
  setViewDensity: (value: ViewDensity) => void;
  loading: boolean;
}

const WebUIContext = createContext<WebUIContextValue | null>(null);

export function WebUIProvider({ children }: { children: ReactNode }): JSX.Element {
  const [settings, setSettings] = useState<WebUISettings>({
    liveArr: true,
    groupSonarr: true,
    viewDensity: "comfortable",
  });
  const [loading, setLoading] = useState(true);

  // Load initial settings
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const config = await getConfig();
        const webui = config?.WebUI as Record<string, unknown> | undefined;

        // Load from localStorage as fallback for view density (client-side preference)
        const storedDensity = localStorage.getItem("viewDensity") as ViewDensity | null;

        setSettings({
          liveArr: webui?.LiveArr === true,
          groupSonarr: webui?.GroupSonarr === true,
          viewDensity: storedDensity || "comfortable",
        });
      } catch (error) {
        console.error("Failed to load WebUI settings:", error);
      } finally {
        setLoading(false);
      }
    };

    void loadSettings();
  }, []);

  // Auto-save settings to backend
  const saveSettings = useCallback(async (key: string, value: boolean) => {
    try {
      const changes: Record<string, unknown> = {
        WebUI: {
          [key]: value,
        },
      };
      await updateConfig({ changes });
    } catch (error) {
      console.error(`Failed to save ${key}:`, error);
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

  const setViewDensity = useCallback((value: ViewDensity) => {
    setSettings(prev => ({ ...prev, viewDensity: value }));
    // Store in localStorage (client-side preference, not sent to backend)
    localStorage.setItem("viewDensity", value);
  }, []);

  const value: WebUIContextValue = {
    liveArr: settings.liveArr,
    groupSonarr: settings.groupSonarr,
    viewDensity: settings.viewDensity,
    setLiveArr,
    setGroupSonarr,
    setViewDensity,
    loading,
  };

  return <WebUIContext.Provider value={value}>{children}</WebUIContext.Provider>;
}

export function useWebUI(): WebUIContextValue {
  const context = useContext(WebUIContext);
  if (!context) {
    throw new Error("useWebUI must be used within WebUIProvider");
  }
  return context;
}
