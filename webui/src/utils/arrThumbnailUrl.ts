/**
 * Thumbnail image URLs (token in query for &lt;img src&gt; when not using session cookies).
 */
const TOKEN_KEYS = ["token", "webui-token", "webui_token"] as const;

function resolveTokenFromStorage(): string | null {
  for (const key of TOKEN_KEYS) {
    const v = localStorage.getItem(key) || sessionStorage.getItem(key);
    if (v) return v;
  }
  return null;
}

export function withWebUiToken(relativePath: string): string {
  const t = resolveTokenFromStorage();
  if (!t) return relativePath;
  const [base, q] = relativePath.split("?");
  const params = new URLSearchParams(q || "");
  if (!params.has("token")) {
    params.set("token", t);
  }
  const qstr = params.toString();
  return qstr ? `${base}?${qstr}` : base;
}

export function radarrMovieThumbnailUrl(
  category: string,
  entryId: number
): string {
  const c = encodeURIComponent(category);
  return withWebUiToken(
    `/web/radarr/${c}/movie/${entryId}/thumbnail`
  );
}

export function sonarrSeriesThumbnailUrl(
  category: string,
  entryId: number
): string {
  const c = encodeURIComponent(category);
  return withWebUiToken(
    `/web/sonarr/${c}/series/${entryId}/thumbnail`
  );
}

export function lidarrAlbumThumbnailUrl(
  category: string,
  entryId: number
): string {
  const c = encodeURIComponent(category);
  return withWebUiToken(
    `/web/lidarr/${c}/album/${entryId}/thumbnail`
  );
}
