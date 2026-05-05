import { type JSX } from "react";
import { ArrCatalogShell } from "./arrCatalog/ArrCatalogShell";
import "./arrCatalog/radarrDefinition";
import "./arrCatalog/sonarrDefinition";
import "./arrCatalog/lidarrDefinition";
import { ARR_CATALOG_REGISTRY, type ArrCatalogKind } from "./arrCatalog/registry";

export type { ArrCatalogKind } from "./arrCatalog/registry";

/**
 * Thin entry point that picks a per-Arr definition and hands it to the shared
 * [`ArrCatalogShell`](./arrCatalog/ArrCatalogShell.tsx). The shell owns chrome and
 * orchestration; the definition supplies fetch / map / render slots specific to one
 * Arr.
 */
export function ArrCatalogView({
  kind,
  active,
}: {
  kind: ArrCatalogKind;
  active: boolean;
}): JSX.Element {
  const definition = ARR_CATALOG_REGISTRY[kind];
  return <ArrCatalogShell definition={definition} active={active} />;
}
