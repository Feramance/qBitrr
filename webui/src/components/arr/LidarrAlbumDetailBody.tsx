import type { JSX } from "react";
import type { LidarrAlbumEntry, LidarrTrack } from "../../api/types";

type Albumish = LidarrAlbumEntry & { __instance?: string };

/** Format duration stored as seconds; divide large legacy millisecond values for display. */
function formatTrackDurationSeconds(seconds: number): string {
  let sec = Math.round(seconds);
  if (sec > 7200) {
    sec = Math.floor(sec / 1000);
  }
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

export function LidarrAlbumDetailBody({
  entry,
}: {
  entry: Albumish;
  category: string;
}): JSX.Element {
  const album = entry.album as Record<string, unknown>;
  const albumId = album?.["id"] as number | undefined;
  const title = (album?.["title"] as string | undefined) || "—";
  const artist = (album?.["artistName"] as string | undefined) || "—";
  const release = album?.["releaseDate"] as string | undefined;
  const monitored = album?.["monitored"] as boolean | undefined;
  const hasFile = album?.["hasFile"] as boolean | undefined;
  const reason = album?.["reason"] as string | null | undefined;
  const qProf = (album?.["qualityProfileName"] as string | null | undefined) ?? "—";
  const tracks: LidarrTrack[] = entry.tracks || [];
  const totals = entry.totals;

  return (
    <div className="arr-detail-radarr">
      <dl className="arr-detail-dl">
        <dt>Album</dt>
        <dd>{title}</dd>
        <dt>Artist</dt>
        <dd>{artist}</dd>
        <dt>Release</dt>
        <dd>
          {release ? new Date(release).toLocaleDateString() : "—"}
        </dd>
        <dt>Monitored</dt>
        <dd>{monitored ? "Yes" : "No"}</dd>
        <dt>Has file</dt>
        <dd>{hasFile ? "Yes" : "No"}</dd>
        <dt>Quality profile</dt>
        <dd>{qProf}</dd>
        <dt>Reason</dt>
        <dd>
          {reason ? (
            <span className="table-badge table-badge-reason">{reason}</span>
          ) : (
            <span className="table-badge table-badge-reason">Not being searched</span>
          )}
        </dd>
        {totals ? (
          <>
            <dt>Track totals</dt>
            <dd>
              {totals.available ?? 0} available / {totals.monitored ?? 0} monitored
            </dd>
          </>
        ) : null}
      </dl>
      {tracks.length > 0 ? (
        <div className="table-wrapper" style={{ marginTop: 12 }}>
          <table className="tracks-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Title</th>
                <th>Duration</th>
                <th>Has File</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {tracks.map((track) => (
                <tr
                  key={`${albumId ?? "a"}-${track.id ?? track.trackNumber}-${track.title}`}
                  className={track.hasFile ? "track-available" : "track-missing"}
                >
                  <td data-label="#">{track.trackNumber ?? "—"}</td>
                  <td data-label="Title">{track.title ?? "—"}</td>
                  <td data-label="Duration">
                    {track.duration != null && Number.isFinite(Number(track.duration))
                      ? formatTrackDurationSeconds(Number(track.duration))
                      : "—"}
                  </td>
                  <td data-label="Has File">
                    <span
                      className={`track-status ${
                        track.hasFile ? "available" : "missing"
                      }`}
                    >
                      {track.hasFile ? "✓" : "✗"}
                    </span>
                  </td>
                  <td data-label="Reason">
                    {reason ? (
                      <span className="table-badge table-badge-reason">
                        {reason}
                      </span>
                    ) : (
                      <span className="table-badge table-badge-reason">
                        Not being searched
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="hint" style={{ marginTop: 8 }}>
          No track list in the current response.
        </p>
      )}
    </div>
  );
}
