import { useEffect, useState, type JSX } from "react";
import { ArrCatalogShell } from "./arrCatalog/ArrCatalogShell";
import type { AnyArrCatalogDefinition } from "./arrCatalog/definition";
import type { ArrCatalogKind } from "./arrCatalog/registry";

export type { ArrCatalogKind } from "./arrCatalog/registry";

async function loadArrCatalogDefinition(
  kind: ArrCatalogKind,
): Promise<AnyArrCatalogDefinition> {
  if (kind === "sonarr") {
    const mod = await import("./arrCatalog/sonarrDefinition");
    return mod.getSonarrCatalogDefinition();
  }
  if (kind === "lidarr") {
    const mod = await import("./arrCatalog/lidarrDefinition");
    return mod.getLidarrCatalogDefinition();
  }
  if (kind === "readarr") {
    const mod = await import("./arrCatalog/readarrDefinition");
    return mod.getReadarrCatalogDefinition();
  }
  const mod = await import("./arrCatalog/radarrDefinition");
  return mod.getRadarrCatalogDefinition();
}

/**
 * Thin entry point that picks a per-Arr definition and hands it to the shared
 * [`ArrCatalogShell`](./arrCatalog/ArrCatalogShell.tsx). The shell owns chrome and
 * orchestration; the definition supplies fetch / map / render slots specific to one
 * Arr.
 *
 * Only the definition module for `kind` is loaded (dynamic import) so visiting one
 * Arr tab does not pull the other Arr definition chunks.
 *
 * Sonarr/Lidarr/Readarr browse always uses series/artist/author rows with
 * seasons/episodes, albums/tracks, or books in the detail modal.
 */
export function ArrCatalogView({
  kind,
  active,
}: {
  kind: ArrCatalogKind;
  active: boolean;
}): JSX.Element {
  const [loaded, setLoaded] = useState<{
    kind: ArrCatalogKind;
    definition: AnyArrCatalogDefinition;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    void loadArrCatalogDefinition(kind).then((def) => {
      if (!cancelled) {
        setLoaded({ kind, definition: def });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [kind]);

  if (!loaded || loaded.kind !== kind) {
    return <div className="hint">Loading catalog…</div>;
  }

  return <ArrCatalogShell definition={loaded.definition} active={active} />;
}
