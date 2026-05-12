import { type JSX } from "react";
import { ArrCatalogView } from "./ArrCatalogView";

interface ArrViewProps {
  type: "radarr" | "sonarr" | "lidarr";
  active: boolean;
}

export function ArrView({ type, active }: ArrViewProps): JSX.Element {
  return <ArrCatalogView kind={type} active={active} />;
}
