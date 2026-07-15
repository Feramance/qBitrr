/** WebUI keys that bind a new host/port and require a full page reload after save. */
export const WEBUI_PAGE_RELOAD_KEYS = new Set(["WebUI.Host", "WebUI.Port"]);

export function webuiChangeNeedsPageReload(changedKeys: readonly string[]): boolean {
  return changedKeys.some((key) => WEBUI_PAGE_RELOAD_KEYS.has(key));
}

export function formatConfigSaveMessage(
  reloadType: string,
  configReloaded: boolean,
  affectedInstances: string[] | undefined,
  changedKeys: readonly string[],
): string {
  let message = "Configuration saved";
  switch (reloadType) {
    case "full":
      message += " • All instances reloaded";
      break;
    case "multi_arr":
      if (affectedInstances?.length) {
        message += ` • Reloaded ${affectedInstances.length} instances: ${affectedInstances.join(", ")}`;
      }
      break;
    case "single_arr":
      if (affectedInstances?.length) {
        message += ` • Reloaded: ${affectedInstances.join(", ")}`;
      }
      break;
    case "live":
      message += configReloaded ? " • Applied live" : " • Applied without restart";
      break;
    case "qbit_hot":
      message += configReloaded
        ? " • qBittorrent settings reloaded"
        : " • qBittorrent settings updated";
      break;
    case "webui":
      if (webuiChangeNeedsPageReload(changedKeys)) {
        message += " • WebUI restarting...";
      } else {
        message += " • WebUI settings updated";
      }
      break;
    case "frontend":
      message += " • Theme/display settings updated";
      break;
    case "none":
      break;
    default:
      message += configReloaded ? " • Settings reloaded" : " • Applied without restart";
      break;
  }
  return message;
}

export function shouldReloadPageAfterSave(
  reloadType: string,
  changedKeys: readonly string[],
): boolean {
  return reloadType === "webui" && webuiChangeNeedsPageReload(changedKeys);
}

export function shouldRefreshMetaAfterSave(
  reloadType: string,
  changedKeys: readonly string[],
): boolean {
  if (reloadType === "live") {
    return true;
  }
  return reloadType === "webui" && !webuiChangeNeedsPageReload(changedKeys);
}
