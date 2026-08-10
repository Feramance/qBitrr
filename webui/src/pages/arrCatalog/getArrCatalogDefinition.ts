import type { AnyArrCatalogDefinition } from "./definition";
import { getLidarrCatalogDefinition } from "./lidarrDefinition";
import { getRadarrCatalogDefinition } from "./radarrDefinition";
import { getReadarrCatalogDefinition } from "./readarrDefinition";
import type { ArrCatalogKind } from "./registry";
import { getSonarrCatalogDefinition } from "./sonarrDefinition";

/** Resolve the catalog definition for an Arr kind. */
export function getArrCatalogDefinition(kind: ArrCatalogKind): AnyArrCatalogDefinition {
  if (kind === "sonarr") return getSonarrCatalogDefinition();
  if (kind === "lidarr") return getLidarrCatalogDefinition();
  if (kind === "readarr") return getReadarrCatalogDefinition();
  return getRadarrCatalogDefinition();
}
