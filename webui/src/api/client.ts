import type {
  ArrListResponse,
  ConfigDocument,
  ConfigUpdatePayload,
  MetaResponse,
  LogsListResponse,
  ProcessesResponse,
  RadarrMoviesResponse,
  RestartResponse,
  SonarrSeriesResponse,
  StatusResponse,
} from "./types";

const JSON_HEADERS = { "Content-Type": "application/json" } as const;
const TOKEN_STORAGE_KEYS = ["token", "webui-token", "webui_token"] as const;

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

function buildInit(init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers || {});
  Object.entries(JSON_HEADERS).forEach(([key, value]) => {
    if (!headers.has(key)) headers.set(key, value);
  });
  const token = resolveToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return {
    ...init,
    headers,
  };
}

async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  return handleJson<T>(await fetch(input, buildInit(init)));
}

async function fetchTextResponse(input: RequestInfo | URL, init?: RequestInit): Promise<string> {
  return handleText(await fetch(input, buildInit(init)));
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
  q: string
): Promise<SonarrSeriesResponse> {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  if (q) params.set("q", q);
  return fetchJson<SonarrSeriesResponse>(
    `/web/sonarr/${encodeURIComponent(category)}/series?${params}`
  );
}

export async function restartArr(category: string): Promise<void> {
  await fetchJson<void>(
    `/web/arr/${encodeURIComponent(category)}/restart`,
    { method: "POST" }
  );
}

export async function getConfig(): Promise<ConfigDocument> {
  return fetchJson<ConfigDocument>("/web/config");
}

export async function updateConfig(
  payload: ConfigUpdatePayload
): Promise<void> {
  await fetchJson<void>("/web/config", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function triggerUpdate(): Promise<void> {
  await fetchJson<void>("/web/update", { method: "POST" });
}
