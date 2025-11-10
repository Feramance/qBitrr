import type {
  ArrListResponse,
  ConfigDocument,
  ConfigResponseWithWarning,
  ConfigUpdatePayload,
  ConfigUpdateResponse,
  MetaResponse,
  LogsListResponse,
  ProcessesResponse,
  RadarrMoviesResponse,
  RestartResponse,
  SonarrSeriesResponse,
  LidarrAlbumsResponse,
  LidarrAlbum,
  StatusResponse,
} from "./types";

const JSON_HEADERS = { "Content-Type": "application/json" } as const;
const TOKEN_STORAGE_KEYS = ["token", "webui-token", "webui_token"] as const;
const MAX_AUTH_RETRIES = 1;

// Request deduplication cache
const inflightRequests = new Map<string, Promise<unknown>>();

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
  };
}

async function fetchWithAuthRetry<T>(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  handler: (response: Response) => Promise<T>,
  retries = MAX_AUTH_RETRIES
): Promise<T> {
  const token = resolveToken();
  const response = await fetch(input, buildInit(init, token));
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
    const existingRequest = inflightRequests.get(key) as Promise<T> | undefined;

    if (existingRequest) {
      return existingRequest;
    }

    const promise = fetchWithAuthRetry<T>(input, init, (response) => handleJson<T>(response))
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
  const query = params?.force ? "?force=1" : "";
  return fetchJson<MetaResponse>(`/web/meta${query}`);
}

export async function getStatus(): Promise<StatusResponse> {
  return fetchJson<StatusResponse>("/web/status");
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

export async function getLogTail(name: string): Promise<string> {
  return fetchTextResponse(`/web/logs/${encodeURIComponent(name)}`);
}

export function getLogDownloadUrl(name: string): string {
  return `/web/logs/${encodeURIComponent(name)}/download`;
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

export async function getLidarrAlbums(
  category: string,
  page: number,
  pageSize: number,
  query?: string
): Promise<LidarrAlbumsResponse> {
  const params = new URLSearchParams();
  params.set("page", page.toString());
  params.set("page_size", pageSize.toString());
  if (query) {
    params.set("q", query);
  }
  // Always include tracks
  params.set("include_tracks", "true");
  return fetchJson<LidarrAlbumsResponse>(
    `/web/lidarr/${encodeURIComponent(category)}/albums?${params}`
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
  const token = resolveToken();
  const response = await fetch("/web/config", buildInit({
    method: "POST",
    body: JSON.stringify(payload),
  }, token));

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      // ignore
    }
    let message = `${response.status} ${response.statusText}`;
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

  // Parse response body with full type information
  const data = await response.json() as ConfigUpdateResponse;
  return data;
}

export async function triggerUpdate(): Promise<void> {
  await fetchJson<void>("/web/update", { method: "POST" });
}
