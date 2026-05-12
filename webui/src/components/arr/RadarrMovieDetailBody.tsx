import type { JSX } from "react";
import type { RadarrMovie } from "../../api/types";
import { radarrMovieThumbnailUrl } from "../../utils/arrThumbnailUrl";
import { ArrPosterImage } from "./ArrPosterImage";

interface RadarrMovieDetailBodyProps {
  movie: RadarrMovie;
  category: string;
}

export function RadarrMovieDetailBody({
  movie,
  category,
}: RadarrMovieDetailBodyProps): JSX.Element {
  const id = movie.id;
  const poster =
    id != null && category
      ? radarrMovieThumbnailUrl(category, id)
      : null;
  const reason = movie.reason as string | null | undefined;
  return (
    <div className="arr-detail-radarr">
      {poster ? (
        <div className="arr-detail-radarr__poster">
          <ArrPosterImage src={poster} alt={String(movie.title ?? "")} />
        </div>
      ) : null}
      <dl className="arr-detail-dl">
        <dt>Year</dt>
        <dd>{movie.year ?? "—"}</dd>
        <dt>Monitored</dt>
        <dd>{movie.monitored ? "Yes" : "No"}</dd>
        <dt>Has file</dt>
        <dd>{movie.hasFile ? "Yes" : "No"}</dd>
        <dt>Quality profile</dt>
        <dd>{movie.qualityProfileName ?? "—"}</dd>
        <dt>Reason</dt>
        <dd>
          {reason ? (
            <span className="table-badge table-badge-reason">{reason}</span>
          ) : (
            <span className="table-badge table-badge-reason">Not being searched</span>
          )}
        </dd>
      </dl>
    </div>
  );
}
