import { useMemo, useState, type JSX } from "react";
import { ProcessesView } from "./pages/ProcessesView";
import { LogsView } from "./pages/LogsView";
import { ArrView } from "./pages/ArrView";
import { ConfigView } from "./pages/ConfigView";
import { ToastProvider, ToastViewport } from "./context/ToastContext";
import { SearchProvider, useSearch } from "./context/SearchContext";

type Tab = "processes" | "logs" | "radarr" | "sonarr" | "config";

interface NavTab {
  id: Tab;
  label: string;
}

function AppShell(): JSX.Element {
  const [activeTab, setActiveTab] = useState<Tab>("processes");
  const [configDirty, setConfigDirty] = useState(false);
  const { setValue: setSearchValue } = useSearch();

  const tabs = useMemo<NavTab[]>(
    () => [
      { id: "processes", label: "Processes" },
      { id: "logs", label: "Logs" },
      { id: "radarr", label: "Radarr" },
      { id: "sonarr", label: "Sonarr" },
      { id: "config", label: "Config" },
    ],
    []
  );

  return (
    <>
      <header className="appbar">
        <div>
          <h1>qBitrr WebUI</h1>
        </div>
      </header>
      <main className="container">
        <nav className="nav">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={activeTab === tab.id ? "active" : ""}
              onClick={() => {
                if (activeTab === "config" && tab.id !== "config" && configDirty) {
                  const shouldLeave = window.confirm(
                    "You have unsaved configuration changes. Leave without saving?"
                  );
                  if (!shouldLeave) {
                    return;
                  }
                }
                setActiveTab(tab.id);
                setSearchValue("");
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        {activeTab === "processes" && <ProcessesView active />}
        {activeTab === "logs" && <LogsView active />}
        {activeTab === "radarr" && <ArrView type="radarr" active />}
        {activeTab === "sonarr" && <ArrView type="sonarr" active />}
        {activeTab === "config" && <ConfigView onDirtyChange={setConfigDirty} />}
      </main>
    </>
  );
}

export default function App(): JSX.Element {
  return (
    <ToastProvider>
      <SearchProvider>
        <AppShell />
        <ToastViewport />
      </SearchProvider>
    </ToastProvider>
  );
}
