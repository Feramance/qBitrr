/**
 * Thumbnail image URLs.
 *
 * Same-origin ``<img>`` requests authenticate via the session cookie; do not embed
 * ``?token=`` (that splits browser cache keys and leaks into history/proxy logs).
 * Use Bearer / ``?token=`` only for XHR API helpers when needed.
 */
import { webPath } from "../api/urlBase";

export function radarrMovieThumbnailUrl(
  category: string,
  entryId: number
): string {
  const c = encodeURIComponent(category);
  return webPath(`/web/radarr/${c}/movie/${entryId}/thumbnail`);
}

export function sonarrSeriesThumbnailUrl(
  category: string,
  entryId: number
): string {
  const c = encodeURIComponent(category);
  return webPath(`/web/sonarr/${c}/series/${entryId}/thumbnail`);
}

export function lidarrArtistThumbnailUrl(
  category: string,
  artistId: number
): string {
  const c = encodeURIComponent(category);
  return webPath(`/web/lidarr/${c}/artist/${artistId}/thumbnail`);
}

export function readarrAuthorThumbnailUrl(
  category: string,
  authorId: number
): string {
  const c = encodeURIComponent(category);
  return webPath(`/web/readarr/${c}/author/${authorId}/thumbnail`);
}
