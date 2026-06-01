/** Public URL path prefix when the WebUI is served under a subpath (e.g. /qbitrr). */
let cachedUrlBaseFromMeta: string | null = null;

/** App paths that appear after an optional UrlBase prefix in the browser URL. */
const PUBLIC_APP_PATH =
  /^(.*?)(?:\/ui|\/login|\/health|\/sw\.js|\/static\/|\/web\/|\/api\/)(?:\/|$)/;

/**
 * Derive UrlBase from the current page URL.
 * Works for /qbitrr/static/index.html, /qbitrr/ui, /qbitrr/web/docs, etc.
 */
export function pathnameUrlBase(): string {
  const { pathname } = window.location;
  const staticMatch = pathname.match(/^(.*)\/static\/index\.html$/);
  if (staticMatch) {
    return staticMatch[1];
  }
  const appMatch = pathname.match(PUBLIC_APP_PATH);
  if (appMatch && appMatch[1]) {
    return appMatch[1];
  }
  // Bare subpath entry (e.g. /qbitrr) before redirect to /qbitrr/ui
  if (/^\/[^/]+$/.test(pathname)) {
    return pathname;
  }
  return "";
}

/** Return the active UrlBase prefix (pathname first, then meta after load). */
export function getUrlBase(): string {
  if (cachedUrlBaseFromMeta !== null) {
    return cachedUrlBaseFromMeta;
  }
  return pathnameUrlBase();
}

/** Store UrlBase from /web/meta so API calls match the configured prefix. */
export function setUrlBaseFromMeta(base: string | undefined): void {
  if (base !== undefined) {
    cachedUrlBaseFromMeta = base;
  }
}

/** Prefix an app-relative path (must start with /) with the active UrlBase. */
export function webPath(path: string): string {
  if (!path.startsWith("/")) {
    throw new Error("webPath expects a path starting with /");
  }
  const base = getUrlBase();
  return base ? `${base}${path}` : path;
}
