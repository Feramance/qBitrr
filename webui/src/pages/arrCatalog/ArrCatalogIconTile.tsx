import { type JSX, type ReactNode } from "react";
import { ArrPosterImage } from "../../components/arr/ArrPosterImage";

export interface ArrCatalogIconTileProps {
  /** Stable key for React list identity (pass as `key` on this component from the parent map). */
  posterSrc: string;
  onClick: () => void;
  /** Inner content below poster (titles, stats, instance badge, etc.) */
  children: ReactNode;
}

/**
 * Shared catalog tile chrome for Radarr / Sonarr / Lidarr icon browse mode.
 * Per‑Arr views supply only `posterSrc` and `children`.
 */
export function ArrCatalogIconTile({
  posterSrc,
  onClick,
  children,
}: ArrCatalogIconTileProps): JSX.Element {
  return (
    <button
      type="button"
      className="arr-movie-tile card"
      onClick={onClick}
    >
      {posterSrc ? (
        <ArrPosterImage
          className="arr-movie-tile__poster"
          src={posterSrc}
          alt=""
        />
      ) : (
        <div className="arr-movie-tile__poster arr-poster-fallback" aria-hidden />
      )}
      <div className="arr-movie-tile__meta">{children}</div>
    </button>
  );
}
