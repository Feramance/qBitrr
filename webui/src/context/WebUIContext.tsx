import { createContext, useCallback, useContext, useEffect, useState, type JSX, type ReactNode } from "react";
import { getConfig, updateConfig } from "../api/client";

interface WebUISettings {
  liveArr: boolean;
  groupSonarr: boolean;
}

interface WebUIContextValue {
  liveArr: boolean;
  groupSonarr: boolean;
  setLiveArr: (value: boolean) => void;
  setGroupSonarr: (value: boolean) => void;
  loading: boolean;
}

const WebUIContext = createContext<WebUIContextValue | null>(null);

export function WebUIProvider({ children }: { children: ReactNode }): JSX.Element {
  const [settings, setSettings] = useState<WebUISettings>({
    liveArr: true,
    groupSonarr: true,
  });
  const [loading, setLoading] = useState(true);

  // Load initial settings
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const config = await getConfig();
        const webui = config?.WebUI as Record<string, unknown> | undefined;

        setSettings({
          liveArr: webui?.LiveArr === true,
          groupSonarr: webui?.GroupSonarr === true,
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

  const value: WebUIContextValue = {
    liveArr: settings.liveArr,
    groupSonarr: settings.groupSonarr,
    setLiveArr,
    setGroupSonarr,
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
