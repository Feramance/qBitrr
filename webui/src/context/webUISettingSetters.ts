import type { Dispatch, SetStateAction } from "react";

type SaveSettings = (key: string, value: boolean | string) => Promise<void>;

/** Factory for WebUI boolean settings that persist to config via `WebUI.*` keys. */
export function createPersistedBooleanSetter<
  TSettings,
  K extends keyof TSettings,
>(
  setSettings: Dispatch<SetStateAction<TSettings>>,
  saveSettings: SaveSettings,
  stateKey: K,
  configKey: string,
): (value: boolean) => void {
  return (value: boolean) => {
    setSettings((prev) => ({ ...prev, [stateKey]: value }));
    void saveSettings(configKey, value);
  };
}
