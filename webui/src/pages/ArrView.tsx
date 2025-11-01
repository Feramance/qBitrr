import { type JSX } from "react";
import { RadarrView } from "./RadarrView";
import { SonarrView } from "./SonarrView";
import { LidarrView } from "./LidarrView";

interface ArrViewProps {
  type: "radarr" | "sonarr" | "lidarr";
  active: boolean;
}

export function ArrView({ type, active }: ArrViewProps): JSX.Element {
  if (type === "radarr") {
    return <RadarrView active={active} />;
  }
  if (type === "lidarr") {
    return <LidarrView active={active} />;
  }
  return <SonarrView active={active} />;
}
