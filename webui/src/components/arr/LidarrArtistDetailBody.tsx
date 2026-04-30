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
  instanceLabel,
}: {
  category: string;
  artistId: number;
  /** Sidebar label for this Arr instance (matches Sonarr detail hint line). */
  instanceLabel?: string | null;
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
  const profileName = (a?.["qualityProfileName"] as string | null | undefined) ?? null;
  const hintLabel =
    instanceLabel != null && String(instanceLabel).trim() !== ""
      ? String(instanceLabel).trim()
      : null;

  const albums = payload.albums ?? [];

  return (
    <div className="arr-detail-radarr">
      {(hintLabel != null || profileName) ? (
        <p className="hint" style={{ margin: "0 0 8px" }}>
          {hintLabel != null ? (
            <>
              <strong>Instance:</strong> {hintLabel}
            </>
          ) : null}
          {hintLabel != null && profileName ? (
            <>
              {" "}
              •{" "}
            </>
          ) : null}
          {profileName ? (
            <>
              <strong>Profile:</strong> {profileName}
            </>
          ) : null}
        </p>
      ) : null}

      <div
        className="arr-detail-radarr__poster-row"
        style={{ display: "flex", gap: 16, flexWrap: "wrap" }}
      >
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
        </dl>
      </div>

      <h4 style={{ margin: "16px 0 8px" }}>Albums</h4>
      {albums.length === 0 ? (
        <p className="hint">No albums for this artist in the local catalog.</p>
      ) : (
        <div className="stack" style={{ gap: 12 }}>
          {albums.map((albumEntry, idx) => {
            const alb = albumEntry.album as Record<string, unknown>;
            const albTitle = String(alb?.["title"] ?? "Album");
            const trackCount = Array.isArray(albumEntry.tracks)
              ? albumEntry.tracks.length
              : 0;
            return (
              <details
                key={String(alb?.["id"] ?? idx)}
                className="arr-series-season"
                open={albums.length <= 3}
              >
                <summary style={{ fontWeight: 600, cursor: "pointer" }}>
                  {albTitle}
                  {trackCount > 0 ? ` (${trackCount} tracks)` : null}
                </summary>
                <div style={{ marginTop: 8 }}>
                  <LidarrAlbumDetailBody entry={albumEntry} category={category} />
                </div>
              </details>
            );
          })}
        </div>
      )}
    </div>
  );
}
