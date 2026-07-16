import { useMemo, type JSX } from "react";
import { ArrCatalogShell } from "./arrCatalog/ArrCatalogShell";
import "./arrCatalog/radarrDefinition";
import "./arrCatalog/sonarrDefinition";
import "./arrCatalog/lidarrDefinition";
import { getArrCatalogDefinition } from "./arrCatalog/getArrCatalogDefinition";
import type { ArrCatalogKind } from "./arrCatalog/registry";

export type { ArrCatalogKind } from "./arrCatalog/registry";

/**
 * Thin entry point that picks a per-Arr definition and hands it to the shared
 * [`ArrCatalogShell`](./arrCatalog/ArrCatalogShell.tsx). The shell owns chrome and
 * orchestration; the definition supplies fetch / map / render slots specific to one
 * Arr.
 *
 * Sonarr/Lidarr browse always uses series/artist rows with seasons/episodes or
 * albums/tracks in the detail modal.
 */
export function ArrCatalogView({
  kind,
  active,
}: {
  kind: ArrCatalogKind;
  active: boolean;
}): JSX.Element {
  const definition = useMemo(() => getArrCatalogDefinition(kind), [kind]);

  return <ArrCatalogShell definition={definition} active={active} />;
}
