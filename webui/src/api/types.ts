export type ArrType = "radarr" | "sonarr" | string;

export interface ProcessInfo {
  category: string;
  name: string;
  kind: string;
  pid: number | null;
  alive: boolean;
}

export interface ProcessesResponse {
  processes: ProcessInfo[];
}

export interface ArrInfo {
  category: string;
  name: string;
  type: ArrType;
  alive?: boolean;
}

export interface ArrListResponse {
  arr: ArrInfo[];
}

export interface QbitStatus {
  alive: boolean;
  host: string | null;
  port: number | null;
  version: string | null;
}

export interface StatusResponse {
  qbit: QbitStatus;
  arrs: ArrInfo[];
}

export interface RestartResponse {
  status: string;
  restarted?: string[];
}

export interface LogsListResponse {
  files: string[];
}

export interface RadarrCounts {
  available: number;
  monitored: number;
}

export interface RadarrMovie {
  id?: number;
  title?: string;
  year?: number;
  monitored?: boolean;
  hasFile?: boolean;
  [key: string]: unknown;
}

export interface RadarrMoviesResponse {
  category: string;
  counts: RadarrCounts;
  total: number;
  page: number;
  page_size: number;
  movies: RadarrMovie[];
}

export interface SonarrEpisode {
  id?: number;
  title?: string;
  episodeNumber?: number;
  seasonNumber?: number;
  monitored?: boolean;
  hasFile?: boolean;
  airDateUtc?: string;
  [key: string]: unknown;
}

export interface SonarrSeason {
  monitored: number;
  available: number;
  episodes: SonarrEpisode[];
}

export interface SonarrSeriesEntry {
  series: Record<string, unknown>;
  totals: {
    available: number;
    monitored: number;
  };
  seasons: Record<string, SonarrSeason>;
}

export interface SonarrSeriesResponse {
  category: string;
  total: number;
  page: number;
  page_size: number;
  totals: {
    available: number;
    monitored: number;
  };
  series: SonarrSeriesEntry[];
}

export type ConfigDocument = Record<string, unknown>;

export interface ConfigUpdatePayload {
  changes: Record<string, unknown>;
}
