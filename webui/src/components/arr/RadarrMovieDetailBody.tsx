import type { JSX } from "react";
import { getRadarrOpenMovieUrl } from "../../api/client";
import type { RadarrMovie } from "../../api/types";
import { radarrMovieThumbnailUrl } from "../../utils/arrThumbnailUrl";
import { ArrExternalLink } from "./ArrExternalLink";
import { ArrPosterImage } from "./ArrPosterImage";
import {
  ArrHasFileBadge,
  ArrMonitoredBadge,
  ArrReasonBadge,
} from "./ArrStatusCells";

interface RadarrMovieDetailBodyProps {
  movie: RadarrMovie;
  category: string;
}

export function RadarrMovieDetailBody({
  movie,
  category,
}: RadarrMovieDetailBodyProps): JSX.Element {
  const id = movie.id;
  const openUrl =
    id != null && category ? getRadarrOpenMovieUrl(category, id) : null;
  const poster =
    id != null && category
      ? radarrMovieThumbnailUrl(category, id)
      : null;
  const reason = movie.reason as string | null | undefined;
  return (
    <div className="arr-detail-radarr">
      <ArrExternalLink href={openUrl} arrName="Radarr" />
      {poster ? (
        <div className="arr-detail-radarr__poster">
          <ArrPosterImage src={poster} alt={String(movie.title ?? "")} />
        </div>
      ) : null}
      <dl className="arr-detail-dl">
        <dt>Year</dt>
        <dd>{movie.year ?? "—"}</dd>
        <dt>Monitored</dt>
        <dd>
          <ArrMonitoredBadge monitored={Boolean(movie.monitored)} />
        </dd>
        <dt>Has file</dt>
        <dd>
          <ArrHasFileBadge hasFile={Boolean(movie.hasFile)} />
        </dd>
        <dt>Quality profile</dt>
        <dd>{movie.qualityProfileName ?? "—"}</dd>
        <dt>Reason</dt>
        <dd>
          <ArrReasonBadge reason={reason} />
        </dd>
      </dl>
    </div>
  );
}
