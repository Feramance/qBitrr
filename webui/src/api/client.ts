import type {
  ArrListResponse,
  ConfigDocument,
  ConfigUpdatePayload,
  LogsListResponse,
  ProcessesResponse,
  RadarrMoviesResponse,
  RestartResponse,
  SonarrSeriesResponse,
  StatusResponse,
} from "./types";

const JSON_HEADERS = { "Content-Type": "application/json" };

function buildInit(init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers || {});
  Object.entries(JSON_HEADERS).forEach(([key, value]) => {
    if (!headers.has(key)) headers.set(key, value);
  });
  const token = localStorage.getItem("token");
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return {
    ...init,
    headers,
  };
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

export async function getStatus(): Promise<StatusResponse> {
  return handleJson(await fetch("/web/status"));
}

export async function getProcesses(): Promise<ProcessesResponse> {
  return handleJson(await fetch("/web/processes"));
}

export async function restartProcess(
  category: string,
  kind: string
): Promise<RestartResponse> {
  const res = await fetch(`/web/processes/${category}/${kind}/restart`, {
    method: "POST",
    ...buildInit(),
  });
  return handleJson(res);
}

export async function restartAllProcesses(): Promise<RestartResponse> {
  const res = await fetch("/web/processes/restart_all", {
    method: "POST",
    ...buildInit(),
  });
  return handleJson(res);
}

export async function rebuildArrs(): Promise<RestartResponse> {
  const res = await fetch("/web/arr/rebuild", {
    method: "POST",
    ...buildInit(),
  });
  return handleJson(res);
}

export async function setLogLevel(level: string): Promise<void> {
  const res = await fetch("/web/loglevel", {
    method: "POST",
    ...buildInit({
      body: JSON.stringify({ level }),
    }),
  });
  await handleJson(res);
}

export async function getLogs(): Promise<LogsListResponse> {
  return handleJson(await fetch("/web/logs"));
}

export async function getLogTail(name: string): Promise<string> {
  const res = await fetch(`/web/logs/${encodeURIComponent(name)}`);
  return handleText(res);
}

export function getLogDownloadUrl(name: string): string {
  return `/web/logs/${encodeURIComponent(name)}/download`;
}

export async function getArrList(): Promise<ArrListResponse> {
  return handleJson(await fetch("/web/arr"));
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
  return handleJson(
    await fetch(`/web/radarr/${encodeURIComponent(category)}/movies?${params}`)
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
  return handleJson(
    await fetch(`/web/sonarr/${encodeURIComponent(category)}/series?${params}`)
  );
}

export async function restartArr(category: string): Promise<void> {
  const res = await fetch(`/web/arr/${encodeURIComponent(category)}/restart`, {
    method: "POST",
    ...buildInit(),
  });
  await handleJson(res);
}

export async function getConfig(): Promise<ConfigDocument> {
  return handleJson(await fetch("/web/config"));
}

export async function updateConfig(
  payload: ConfigUpdatePayload
): Promise<void> {
  const res = await fetch("/web/config", {
    method: "POST",
    ...buildInit({
      body: JSON.stringify(payload),
    }),
  });
  await handleJson(res);
}
