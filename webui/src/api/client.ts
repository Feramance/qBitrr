import type {
  ArrListResponse,
  ConfigDocument,
  ConfigResponseWithWarning,
  ConfigUpdatePayload,
  ConfigUpdateResponse,
  LoginRequest,
  MetaResponse,
  LogsListResponse,
  LogSearchResponse,
  LogTailPayload,
  ProcessesResponse,
  QbitCategoriesResponse,
  RadarrMoviesResponse,
  RestartResponse,
  SetPasswordRequest,
  SonarrSeriesResponse,
  LidarrArtistDetailResponse,
  LidarrArtistsResponse,
  StatusResponse,
} from "./types";
import { clearUrlBaseCache, setUrlBaseFromMeta, webPath } from "./urlBase";

export class AuthError extends Error {
  code?: string;
  constructor(message: string, code?: string) {
    super(message);
    this.name = "AuthError";
    this.code = code;
  }
}

const JSON_HEADERS = { "Content-Type": "application/json" } as const;
const TOKEN_STORAGE_KEYS = ["token", "webui-token", "webui_token"] as const;
const MAX_AUTH_RETRIES = 1;

// Request deduplication cache
const inflightRequests = new Map<string, Promise<unknown>>();

/** Short-lived GET response cache (status/config/meta/processes). Arr catalogs use TTL 0. */
interface TtlCacheEntry {
  expiresAt: number;
  value: unknown;
}

const ttlResponseCache = new Map<string, TtlCacheEntry>();

const GET_TTL_MS: ReadonlyArray<{ match: (path: string) => boolean; ttlMs: number }> = [
  { match: (path) => path.includes("/web/status"), ttlMs: 2_000 },
  { match: (path) => path.includes("/web/config"), ttlMs: 30_000 },
  {
    match: (path) => path.includes("/web/meta") && !/[?&]force=1(?:&|$)/.test(path),
    ttlMs: 60_000,
  },
  { match: (path) => path.includes("/web/processes"), ttlMs: 800 },
];

function extractRequestPath(input: RequestInfo | URL): string {
  const raw = input instanceof Request ? input.url : String(input);
  try {
    if (raw.startsWith("http://") || raw.startsWith("https://")) {
      const url = new URL(raw);
      return `${url.pathname}${url.search}`;
    }
  } catch {
    // fall through
  }
  return raw;
}

function resolveGetTtlMs(path: string): number {
  // Arr catalog paged URLs keep their own caches — never TTL here.
  if (
    /\/web\/(?:radarr|sonarr|lidarr)\//.test(path) ||
    /\/web\/arr\//.test(path)
  ) {
    return 0;
  }
  for (const rule of GET_TTL_MS) {
    if (rule.match(path)) {
      return rule.ttlMs;
    }
  }
  return 0;
}

function readTtlCache<T>(key: string): T | undefined {
  const entry = ttlResponseCache.get(key);
  if (!entry) {
    return undefined;
  }
  if (Date.now() > entry.expiresAt) {
    ttlResponseCache.delete(key);
    return undefined;
  }
  return entry.value as T;
}

function writeTtlCache(key: string, value: unknown, ttlMs: number): void {
  if (ttlMs <= 0) {
    return;
  }
  ttlResponseCache.set(key, { value, expiresAt: Date.now() + ttlMs });
}

/** Invalidate TTL entries whose request path matches any of the substrings. */
export function invalidateGetCache(pathSubstrings: readonly string[]): void {
  for (const key of [...ttlResponseCache.keys()]) {
    if (pathSubstrings.some((part) => key.includes(part))) {
      ttlResponseCache.delete(key);
    }
  }
}

function createRequestKey(input: RequestInfo | URL, init?: RequestInit): string {
  const url = input instanceof Request ? input.url : String(input);
  const method = init?.method || "GET";
  const body = init?.body ? String(init.body) : "";
  return `${method}:${url}:${body}`;
}

function resolveToken(): string | null {
  for (const key of TOKEN_STORAGE_KEYS) {
    const value = localStorage.getItem(key) || sessionStorage.getItem(key);
    if (value) {
      if (key !== "token") {
        localStorage.setItem("token", value);
      }
      return value;
    }
  }
  try {
    const params = new URLSearchParams(window.location.search);
    const fromQuery = params.get("token");
    if (fromQuery) {
      localStorage.setItem("token", fromQuery);
      const cleanUrl = new URL(window.location.href);
      cleanUrl.searchParams.delete("token");
      window.history.replaceState({}, "", cleanUrl.toString());
      return fromQuery;
    }
  } catch {
    // ignore
  }
  return null;
}

function clearStoredToken(): void {
  for (const key of TOKEN_STORAGE_KEYS) {
    localStorage.removeItem(key);
  }
  try {
    for (const key of TOKEN_STORAGE_KEYS) {
      sessionStorage.removeItem(key);
    }
  } catch {
    // ignore session storage errors
  }
}

function resolveRequestInput(input: RequestInfo | URL): RequestInfo | URL {
  if (typeof input === "string" && input.startsWith("/")) {
    return webPath(input);
  }
  return input;
}

function buildInit(init: RequestInit | undefined, token: string | null): RequestInit {
  const headers = new Headers(init?.headers || {});
  Object.entries(JSON_HEADERS).forEach(([key, value]) => {
    if (!headers.has(key)) headers.set(key, value);
  });
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return {
    ...init,
    headers,
    credentials: "include",
  };
}

async function fetchWithAuthRetry<T>(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  handler: (response: Response) => Promise<T>,
  retries = MAX_AUTH_RETRIES
): Promise<T> {
  const token = resolveToken();
  const response = await fetch(resolveRequestInput(input), buildInit(init, token));
  if (response.status === 401 && retries > 0 && token) {
    clearStoredToken();
    return fetchWithAuthRetry(input, init, handler, retries - 1);
  }
  return handler(response);
}

async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  // Only deduplicate GET requests (safe to share)
  const method = init?.method || "GET";
  if (method === "GET") {
    const key = createRequestKey(input, init);
    const path = extractRequestPath(input);
    const ttlMs = resolveGetTtlMs(path);

    if (ttlMs > 0) {
      const cached = readTtlCache<T>(key);
      if (cached !== undefined) {
        return cached;
      }
    }

    const existingRequest = inflightRequests.get(key) as Promise<T> | undefined;
    if (existingRequest) {
      return existingRequest;
    }

    const promise = fetchWithAuthRetry<T>(input, init, (response) => handleJson<T>(response))
      .then((value) => {
        writeTtlCache(key, value, ttlMs);
        return value;
      })
      .finally(() => {
        inflightRequests.delete(key);
      });

    inflightRequests.set(key, promise);
    return promise;
  }

  return fetchWithAuthRetry<T>(input, init, (response) => handleJson<T>(response));
}

async function fetchTextResponse(input: RequestInfo | URL, init?: RequestInit): Promise<string> {
  return fetchWithAuthRetry<string>(input, init, (response) => handleText(response));
}

async function handleJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      // ignore
    }
    let message = `${res.status} ${res.statusText}`;
    if (
      detail &&
      typeof detail === "object" &&
      "error" in detail &&
      typeof (detail as Record<string, unknown>).error === "string"
    ) {
      const errorText = (detail as Record<string, unknown>).error as string;
      if (errorText.trim()) {
        message = errorText;
      }
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

async function handleText(res: Response): Promise<string> {
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.text();
}

export async function getMeta(params?: { force?: boolean }): Promise<MetaResponse> {
  if (params?.force) {
    // Forced meta must bypass TTL and drop any soft-cached meta entries.
    invalidateGetCache(["/web/meta"]);
  }
  const query = params?.force ? "?force=1" : "";
  const meta = await fetchJson<MetaResponse>(`/web/meta${query}`);
  setUrlBaseFromMeta(meta.url_base);
  return meta;
}

/** Re-fetch /web/meta and refresh the cached UrlBase prefix (no page reload). */
export async function refreshUrlBaseFromMeta(): Promise<MetaResponse> {
  clearUrlBaseCache();
  return getMeta({ force: true });
}

export async function getStatus(): Promise<StatusResponse> {
  return fetchJson<StatusResponse>("/web/status");
}

export async function getQbitCategories(): Promise<QbitCategoriesResponse> {
  return fetchJson<QbitCategoriesResponse>("/web/qbit/categories");
}

export async function getProcesses(): Promise<ProcessesResponse> {
  return fetchJson<ProcessesResponse>("/web/processes");
}

export async function restartProcess(
  category: string,
  kind: string
): Promise<RestartResponse> {
  const url = `/web/processes/${encodeURIComponent(
    category
  )}/${encodeURIComponent(kind)}/restart`;
  return fetchJson<RestartResponse>(url, { method: "POST" });
}

export async function restartAllProcesses(): Promise<RestartResponse> {
  return fetchJson<RestartResponse>("/web/processes/restart_all", {
    method: "POST",
  });
}

export async function rebuildArrs(): Promise<RestartResponse> {
  return fetchJson<RestartResponse>("/web/arr/rebuild", { method: "POST" });
}

export async function setLogLevel(level: string): Promise<void> {
  await fetchJson<void>("/web/loglevel", {
    method: "POST",
    body: JSON.stringify({ level }),
  });
}

export async function getLogs(): Promise<LogsListResponse> {
  return fetchJson<LogsListResponse>("/web/logs");
}

export async function getLogTail(
  name: string,
  lines?: number,
  offset?: number
): Promise<string> {
  const base = `/web/logs/${encodeURIComponent(name)}`;
  if (lines == null || lines <= 0) {
    return fetchTextResponse(base);
  }
  const params = new URLSearchParams({ lines: String(lines) });
  if (offset != null && offset > 0) {
    params.set("offset", String(offset));
  }
  return fetchTextResponse(`${base}?${params.toString()}`);
}

export interface GetLogTailJsonOptions {
  lines?: number;
  offset?: number;
  sinceBytes?: number;
  inode?: number;
  aroundLine?: number;
}

/** Fetch log content as JSON (initial tail, older window, or byte-offset delta). */
export async function getLogTailJson(
  name: string,
  options: GetLogTailJsonOptions = {}
): Promise<LogTailPayload> {
  const base = `/web/logs/${encodeURIComponent(name)}`;
  const params = new URLSearchParams({ format: "json" });
  if (options.lines != null && options.lines > 0) {
    params.set("lines", String(options.lines));
  }
  if (options.offset != null && options.offset > 0) {
    params.set("offset", String(options.offset));
  }
  if (options.sinceBytes != null) {
    params.set("since_bytes", String(options.sinceBytes));
  }
  if (options.inode != null && options.inode > 0) {
    params.set("inode", String(options.inode));
  }
  if (options.aroundLine != null && options.aroundLine > 0) {
    params.set("around_line", String(options.aroundLine));
  }
  return fetchJson<LogTailPayload>(`${base}?${params.toString()}`);
}

/** Alias for delta polling. */
export async function getLogDelta(
  name: string,
  sinceBytes: number,
  inode?: number,
  lines?: number
): Promise<LogTailPayload> {
  return getLogTailJson(name, { sinceBytes, inode, lines });
}

export interface LogSearchOptions {
  q: string;
  caseSensitive?: boolean;
  regex?: boolean;
  maxMatches?: number;
  context?: number;
  includeRotated?: boolean;
}

export async function searchLogs(
  name: string,
  options: LogSearchOptions
): Promise<LogSearchResponse> {
  const params = new URLSearchParams({ q: options.q });
  if (options.caseSensitive) {
    params.set("case", "1");
  }
  if (options.regex) {
    params.set("regex", "1");
  }
  if (options.maxMatches != null) {
    params.set("max_matches", String(options.maxMatches));
  }
  if (options.context != null) {
    params.set("context", String(options.context));
  }
  if (options.includeRotated === false) {
    params.set("include_rotated", "0");
  }
  return fetchJson<LogSearchResponse>(
    `/web/logs/${encodeURIComponent(name)}/search?${params.toString()}`
  );
}

export function getLogDownloadUrl(name: string): string {
  return webPath(`/web/logs/${encodeURIComponent(name)}/download`);
}

/** Session-cookie EventSource URL for live log SSE (use /web/*, not Bearer). */
export function getLogStreamUrl(
  name: string,
  sinceBytes: number,
  inode?: number,
  lines?: number
): string {
  const params = new URLSearchParams({
    since_bytes: String(sinceBytes),
  });
  if (inode != null && inode > 0) {
    params.set("inode", String(inode));
  }
  if (lines != null && lines > 0) {
    params.set("lines", String(lines));
  }
  return webPath(
    `/web/logs/${encodeURIComponent(name)}/stream?${params.toString()}`
  );
}

export type ArrOpenItemKind = "movie" | "series" | "artist";

export function getArrOpenItemUrl(
  category: string,
  kind: ArrOpenItemKind,
  entryId: number
): string {
  const encodedCategory = encodeURIComponent(category);
  return webPath(`/web/arr/${encodedCategory}/open/${kind}/${entryId}`);
}

export function getRadarrOpenMovieUrl(category: string, movieId: number): string {
  return getArrOpenItemUrl(category, "movie", movieId);
}

export function getSonarrOpenSeriesUrl(category: string, seriesId: number): string {
  return getArrOpenItemUrl(category, "series", seriesId);
}

export function getLidarrOpenArtistUrl(category: string, artistId: number): string {
  return getArrOpenItemUrl(category, "artist", artistId);
}

export async function getArrList(): Promise<ArrListResponse> {
  return fetchJson<ArrListResponse>("/web/arr");
}

export async function getRadarrMovies(
  category: string,
  page: number,
  pageSize: number,
  q: string
): Promise<RadarrMoviesResponse> {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  if (q) params.set("q", q);
  return fetchJson<RadarrMoviesResponse>(
    `/web/radarr/${encodeURIComponent(category)}/movies?${params}`
  );
}

export async function getSonarrSeries(
  category: string,
  page: number,
  pageSize: number,
  q: string,
  options?: { missingOnly?: boolean }
): Promise<SonarrSeriesResponse> {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  if (q) params.set("q", q);
  if (options?.missingOnly) {
    params.set("missing", "1");
  }
  return fetchJson<SonarrSeriesResponse>(
    `/web/sonarr/${encodeURIComponent(category)}/series?${params}`
  );
}

export async function getLidarrArtists(
  category: string,
  page: number,
  pageSize: number,
  query?: string,
  options?: {
    monitored?: boolean | null;
    missingOnly?: boolean;
    reasonFilter?: string | null;
  }
): Promise<LidarrArtistsResponse> {
  const params = new URLSearchParams();
  params.set("page", page.toString());
  params.set("page_size", pageSize.toString());
  if (query) {
    params.set("q", query);
  }
  const mv = options?.monitored;
  if (mv === true || mv === false) {
    params.set("monitored", mv ? "1" : "0");
  }
  if (options?.missingOnly) {
    params.set("missing", "1");
  }
  const reason = options?.reasonFilter;
  if (typeof reason === "string" && reason && reason !== "all") {
    params.set("reason", reason);
  }
  return fetchJson<LidarrArtistsResponse>(
    `/web/lidarr/${encodeURIComponent(category)}/artists?${params}`
  );
}

export async function getLidarrArtistDetail(
  category: string,
  artistId: number
): Promise<LidarrArtistDetailResponse> {
  return fetchJson<LidarrArtistDetailResponse>(
    `/web/lidarr/${encodeURIComponent(category)}/artist/${artistId}`
  );
}

export async function restartArr(category: string): Promise<void> {
  await fetchJson<void>(
    `/web/arr/${encodeURIComponent(category)}/restart`,
    { method: "POST" }
  );
}

export async function getConfig(): Promise<ConfigDocument> {
  // Response might be ConfigDocument OR ConfigResponseWithWarning
  const response = await fetchJson<ConfigDocument | ConfigResponseWithWarning>("/web/config");

  // Check if response contains a warning structure
  if (response && typeof response === "object" && "warning" in response && "config" in response) {
    // Response has warning structure - store warning for display
    const warningResponse = response as ConfigResponseWithWarning;
    if (warningResponse.warning?.message) {
      sessionStorage.setItem("config_version_warning", warningResponse.warning.message);
    }
    // Return the actual config (always present in warning structure)
    return warningResponse.config;
  }

  // Normal response - just a plain config object
  return response as ConfigDocument;
}

export async function updateConfig(
  payload: ConfigUpdatePayload
): Promise<ConfigUpdateResponse> {
  const result = await fetchJson<ConfigUpdateResponse>("/web/config", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  invalidateGetCache(["/web/config", "/web/meta"]);
  return result;
}

export async function triggerUpdate(): Promise<void> {
  await fetchJson<void>("/web/update", { method: "POST" });
}

export interface TestConnectionRequest {
  arrType: "radarr" | "sonarr" | "lidarr";
  /** When present, backend uses stored config for this instance (e.g. when API key is redacted). */
  instanceKey?: string;
  uri?: string;
  apiKey?: string;
}

export interface TestConnectionResponse {
  success: boolean;
  message: string;
  systemInfo?: {
    version: string;
    branch?: string;
  };
  qualityProfiles?: Array<{ id: number; name: string }>;
}

export async function testArrConnection(
  request: TestConnectionRequest
): Promise<TestConnectionResponse> {
  return fetchJson("/web/arr/test-connection", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function login(req: LoginRequest): Promise<{ success: boolean }> {
  const res = await fetch(webPath("/web/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(req),
  });
  const data = await res.json().catch(() => ({})) as Record<string, unknown>;
  if (!res.ok) {
    const code = typeof data.code === "string" ? data.code : undefined;
    const message = typeof data.error === "string" ? data.error : `${res.status} ${res.statusText}`;
    throw new AuthError(message, code);
  }
  return data as { success: boolean };
}

export async function setPassword(req: SetPasswordRequest): Promise<{ success: boolean }> {
  const res = await fetch(webPath("/web/auth/set-password"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(req),
  });
  const data = await res.json().catch(() => ({})) as Record<string, unknown>;
  if (!res.ok) {
    const message = typeof data.error === "string" ? data.error : `${res.status} ${res.statusText}`;
    throw new AuthError(message);
  }
  return data as { success: boolean };
}

export async function logout(): Promise<void> {
  await fetch(webPath("/web/logout"), { method: "POST", credentials: "include" });
  clearStoredToken();
  invalidateGetCache(["/web/config", "/web/meta", "/web/status", "/web/processes"]);
}

export async function fetchWebToken(): Promise<string | null> {
  const res = await fetch(webPath("/web/token"), { credentials: "include" });
  if (!res.ok) return null;
  const data = await res.json().catch(() => ({})) as Record<string, unknown>;
  return typeof data.token === "string" ? data.token : null;
}
