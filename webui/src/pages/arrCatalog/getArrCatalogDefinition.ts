import type { AnyArrCatalogDefinition } from "./definition";
import { getLidarrCatalogDefinition } from "./lidarrDefinition";
import { getRadarrCatalogDefinition } from "./radarrDefinition";
import type { ArrCatalogKind } from "./registry";
import { getSonarrCatalogDefinition } from "./sonarrDefinition";

/** Resolve the catalog definition for an Arr kind and grouping prefs. */
export function getArrCatalogDefinition(
  kind: ArrCatalogKind,
  opts: { groupSonarr: boolean; groupLidarr: boolean },
): AnyArrCatalogDefinition {
  if (kind === "sonarr") return getSonarrCatalogDefinition(opts.groupSonarr);
  if (kind === "lidarr") return getLidarrCatalogDefinition(opts.groupLidarr);
  return getRadarrCatalogDefinition();
}
