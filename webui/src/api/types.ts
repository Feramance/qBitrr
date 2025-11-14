export type ArrType = "radarr" | "sonarr" | "lidarr" | string;

export interface ProcessInfo {
  category: string;
  name: string;
  kind: string;
  pid: number | null;
  alive: boolean;
  rebuilding?: boolean;
  searchSummary?: string;
  searchTimestamp?: string;
  queueCount?: number;
  categoryCount?: number;
  metricType?: string;
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
  counts?: {
    radarr?: RadarrCounts;
    sonarr?: {
      available: number;
      monitored: number;
      missing?: number;
    };
    lidarr?: LidarrCounts;
  };
  ready?: boolean;
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
  ready?: boolean;
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
  reason?: string | null;
  qualityProfileId?: number | null;
  qualityProfileName?: string | null;
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
  reason?: string | null;
  [key: string]: unknown;
}

export interface SonarrSeason {
  monitored: number;
  available: number;
  missing?: number;
  episodes: SonarrEpisode[];
}

export interface SonarrSeriesEntry {
  series: Record<string, unknown> & {
    qualityProfileId?: number | null;
    qualityProfileName?: string | null;
  };
  totals: {
    available: number;
    monitored: number;
    missing?: number;
  };
  seasons: Record<string, SonarrSeason>;
}

export interface SonarrSeriesResponse {
  category: string;
  total: number;
  page: number;
  page_size: number;
  counts: {
    available: number;
    monitored: number;
    missing?: number;
  };
  series: SonarrSeriesEntry[];
}

export interface LidarrCounts {
  available: number;
  monitored: number;
}

export interface LidarrTrack {
  id?: number;
  trackNumber?: number;
  title?: string;
  duration?: number;
  hasFile?: boolean;
  trackFileId?: number | null;
  monitored?: boolean;
  albumId?: number;
  albumTitle?: string;
  artistTitle?: string;
  artistId?: number;
}

export interface LidarrAlbum {
  id?: number;
  title?: string;
  artistId?: number;
  artistName?: string;
  releaseDate?: string;
  monitored?: boolean;
  hasFile?: boolean;
  reason?: string | null;
  tracks?: LidarrTrack[];
  trackCount?: number;
  trackFileCount?: number;
  percentOfTracks?: number;
  qualityProfileId?: number | null;
  qualityProfileName?: string | null;
  [key: string]: unknown;
}

export interface LidarrAlbumEntry {
  album: Record<string, unknown> & {
    qualityProfileId?: number | null;
    qualityProfileName?: string | null;
  };
  totals: {
    available: number;
    monitored: number;
    missing?: number;
  };
  tracks: LidarrTrack[];
  [key: string]: unknown;
}

export interface LidarrAlbumsResponse {
  category: string;
  counts: LidarrCounts;
  total: number;
  page: number;
  page_size: number;
  albums: LidarrAlbumEntry[];
}

export interface LidarrTracksResponse {
  category: string;
  counts: {
    available: number;
    monitored: number;
    missing: number;
  };
  total: number;
  page: number;
  page_size: number;
  tracks: LidarrTrack[];
}

export interface ConfigVersionWarning {
  type: "config_version_mismatch";
  message: string;
  currentVersion: number;
}

export interface ConfigResponseWithWarning {
  config: Record<string, unknown>;
  warning: ConfigVersionWarning;
}

// ConfigDocument is always a plain object with string keys
// The warning structure is handled internally by getConfig()
export type ConfigDocument = Record<string, unknown>;

export interface ConfigUpdatePayload {
  changes: Record<string, unknown>;
}

export interface UpdateState {
  in_progress: boolean;
  last_result: "success" | "error" | null;
  last_error: string | null;
  completed_at: string | null;
}

export interface MetaResponse {
  current_version: string;
  latest_version: string | null;
  update_available: boolean;
  changelog: string | null; // Latest version changelog
  current_version_changelog: string | null; // Current version changelog
  changelog_url: string | null;
  repository_url: string;
  homepage_url: string;
  last_checked: string | null;
  error?: string | null;
  update_state: UpdateState;
  installation_type: "git" | "pip" | "binary" | "unknown";
  binary_download_url: string | null;
  binary_download_name: string | null;
  binary_download_size: number | null;
  binary_download_error: string | null;
}

export interface ConfigUpdateResponse {
  status: string;
  configReloaded: boolean;
  reloadType: "none" | "frontend" | "webui" | "single_arr" | "multi_arr" | "full";
  affectedInstances: string[];
}
