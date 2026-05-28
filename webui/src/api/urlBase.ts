/** Public URL path prefix when the WebUI is served under a subpath (e.g. /qbitrr). */
let cachedUrlBaseFromMeta: string | null = null;

/** Derive UrlBase from the current page pathname (e.g. /qbitrr/static/index.html). */
export function pathnameUrlBase(): string {
  const staticMatch = window.location.pathname.match(/^(.*)\/static\/index\.html$/);
  return staticMatch ? staticMatch[1] : "";
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
