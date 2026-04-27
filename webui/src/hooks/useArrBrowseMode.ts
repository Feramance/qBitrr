import { useCallback, useEffect, useState } from "react";

export type ArrBrowseMode = "list" | "icon";

const defaultMode: ArrBrowseMode = "icon";

function readStored(key: string): ArrBrowseMode {
  try {
    const v = localStorage.getItem(key);
    if (v === "list" || v === "icon") return v;
  } catch {
    // ignore
  }
  return defaultMode;
}

/**
 * List = tabular view without browse thumbnails. Icon = tile grid with posters (default).
 */
export function useArrBrowseMode(appKey: "radarr" | "sonarr" | "lidarr"): {
  mode: ArrBrowseMode;
  setMode: (m: ArrBrowseMode) => void;
} {
  const storageKey = `qbitrr.arrBrowseMode.${appKey}`;
  const [mode, setModeState] = useState<ArrBrowseMode>(() =>
    readStored(storageKey)
  );

  useEffect(() => {
    setModeState(readStored(storageKey));
  }, [storageKey]);

  const setMode = useCallback(
    (m: ArrBrowseMode) => {
      setModeState(m);
      try {
        localStorage.setItem(storageKey, m);
      } catch {
        // ignore
      }
    },
    [storageKey]
  );

  return { mode, setMode };
}
