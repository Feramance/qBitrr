import { useMemo, type JSX } from "react";
import { useWebUI } from "../context/WebUIContext";
import { ArrCatalogShell } from "./arrCatalog/ArrCatalogShell";
import "./arrCatalog/radarrDefinition";
import "./arrCatalog/sonarrDefinition";
import "./arrCatalog/lidarrDefinition";
import { getLidarrCatalogDefinition } from "./arrCatalog/lidarrDefinition";
import { getSonarrCatalogDefinition } from "./arrCatalog/sonarrDefinition";
import { ARR_CATALOG_REGISTRY, type ArrCatalogKind } from "./arrCatalog/registry";

export type { ArrCatalogKind } from "./arrCatalog/registry";

/**
 * Thin entry point that picks a per-Arr definition and hands it to the shared
 * [`ArrCatalogShell`](./arrCatalog/ArrCatalogShell.tsx). The shell owns chrome and
 * orchestration; the definition supplies fetch / map / render slots specific to one
 * Arr.
 *
 * Sonarr/Lidarr definitions switch between grouped (series/artist rows + modal) and
 * flat (episode/album rows) based on `WebUI.GroupSonarr` / `WebUI.GroupLidarr`.
 */
export function ArrCatalogView({
  kind,
  active,
}: {
  kind: ArrCatalogKind;
  active: boolean;
}): JSX.Element {
  const { groupSonarr, groupLidarr } = useWebUI();
  const definition = useMemo(() => {
    if (kind === "sonarr") {
      return getSonarrCatalogDefinition(groupSonarr);
    }
    if (kind === "lidarr") {
      return getLidarrCatalogDefinition(groupLidarr);
    }
    return ARR_CATALOG_REGISTRY[kind];
  }, [kind, groupSonarr, groupLidarr]);

  return <ArrCatalogShell definition={definition} active={active} />;
}
