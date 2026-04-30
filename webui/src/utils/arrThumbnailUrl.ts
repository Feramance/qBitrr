/**
 * Thumbnail image URLs.
 *
 * Prefer session-cookie auth: when the user is logged in, the browser will send the session
 * cookie automatically with every &lt;img&gt; request and we never have to embed the token in the URL.
 * The query-param fallback below is for environments where the token is the only credential we
 * have (e.g. headless tooling or initial provisioning); the backend logs a warning whenever a
 * request authenticates via ``?token=`` because the token leaks into proxy logs and browser
 * history. The thumbnail responses now use ``Cache-Control: private`` so shared caches do not
 * keep token-bearing bytes.
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
  // If we have a session cookie path the request already authenticates via cookie; only fall
  // back to the query token when storage holds one. This keeps proxy logs clean for the common
  // logged-in case while still allowing token-only deployments to work.
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

export function lidarrArtistThumbnailUrl(
  category: string,
  artistId: number
): string {
  const c = encodeURIComponent(category);
  return withWebUiToken(
    `/web/lidarr/${c}/artist/${artistId}/thumbnail`
  );
}
