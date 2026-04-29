import { useEffect, useState } from "react";
import type { JSX } from "react";
import { getLidarrArtistDetail } from "../../api/client";
import type { LidarrArtistDetailResponse } from "../../api/types";
import { lidarrArtistThumbnailUrl } from "../../utils/arrThumbnailUrl";
import { ArrPosterImage } from "./ArrPosterImage";
import { LidarrAlbumDetailBody } from "./LidarrAlbumDetailBody";

export function LidarrArtistDetailBody({
  category,
  artistId,
}: {
  category: string;
  artistId: number;
}): JSX.Element {
  const [payload, setPayload] = useState<LidarrArtistDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getLidarrArtistDetail(category, artistId).then(
      (data) => {
        if (!cancelled) setPayload(data);
      },
      (e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load artist");
        }
      }
    );
    return () => {
      cancelled = true;
    };
  }, [category, artistId]);

  if (error) {
    return <p className="hint">{error}</p>;
  }

  if (!payload) {
    return (
      <div className="loading">
        <span className="spinner" /> Loading artist…
      </div>
    );
  }

  const a = payload.artist;
  const poster =
    typeof a?.["id"] === "number"
      ? lidarrArtistThumbnailUrl(category, artistId)
      : null;

  return (
    <div className="arr-detail-radarr">
      <div className="arr-detail-radarr__poster-row" style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {poster ? (
          <div className="arr-detail-radarr__poster">
            <ArrPosterImage src={poster} alt={(a?.["name"] as string) || ""} />
          </div>
        ) : null}
        <dl className="arr-detail-dl">
          <dt>Artist</dt>
          <dd>{String(a?.["name"] ?? "—")}</dd>
          <dt>Monitored</dt>
          <dd>{a?.["monitored"] ? "Yes" : "No"}</dd>
          <dt>Albums</dt>
          <dd>{Number(a?.["albumCount"] ?? 0).toLocaleString()}</dd>
          <dt>Tracks (total)</dt>
          <dd>{Number(a?.["trackTotalCount"] ?? 0).toLocaleString()}</dd>
          <dt>Quality profile</dt>
          <dd>{(a?.["qualityProfileName"] as string | null | undefined) || "—"}</dd>
        </dl>
      </div>

      <h4 style={{ margin: "16px 0 8px" }}>Albums</h4>
      {(!payload.albums || payload.albums.length === 0) ? (
        <p className="hint">No albums for this artist in the local catalog.</p>
      ) : (
        <div className="stack" style={{ gap: 24 }}>
          {payload.albums.map((albumEntry, idx) => (
            <div
              key={String((albumEntry.album as Record<string, unknown>)?.["id"] ?? idx)}
              className="card"
              style={{ padding: 12 }}
            >
              <LidarrAlbumDetailBody entry={albumEntry} category={category} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
