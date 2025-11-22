import { type JSX } from "react";
import { RadarrView } from "./RadarrView";
import { SonarrView } from "./SonarrView";

interface ArrViewProps {
  type: "radarr" | "sonarr";
  active: boolean;
}

export function ArrView({ type, active }: ArrViewProps): JSX.Element {
  if (type === "radarr") {
    return <RadarrView active={active} />;
  }
  return <SonarrView active={active} />;
}
