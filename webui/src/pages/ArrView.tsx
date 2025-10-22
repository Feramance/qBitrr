import { useCallback, useEffect, useMemo, useState, type JSX } from "react";
import {
  getArrList,
  getRadarrMovies,
  getSonarrSeries,
  restartArr,
} from "../api/client";
import type {
  ArrInfo,
  RadarrMovie,
  RadarrMoviesResponse,
  SonarrEpisode,
  SonarrSeriesEntry,
  SonarrSeriesResponse,
} from "../api/types";
import { useToast } from "../context/ToastContext";
import { useSearch } from "../context/SearchContext";
import { useInterval } from "../hooks/useInterval";

interface ArrViewProps {
  type: "radarr" | "sonarr";
  active: boolean;
}

interface RadarrAggRow extends RadarrMovie {
  __instance: string;
}

interface SonarrAggRow {
  __instance: string;
  series: string;
  season: number | string;
  episode: number | string;
  title: string;
  monitored: boolean;
  hasFile: boolean;
  airDate: string;
}

const RADARR_PAGE_SIZE = 50;
const RADARR_AGG_PAGE_SIZE = 50;
const RADARR_AGG_FETCH_SIZE = 500;
const SONARR_PAGE_SIZE = 25;
const SONARR_AGG_PAGE_SIZE = 50;
const SONARR_AGG_FETCH_SIZE = 200;

export function ArrView({ type, active }: ArrViewProps): JSX.Element {
  if (type === "radarr") {
    return <RadarrView active={active} />;
  }
  return <SonarrView active={active} />;
}

function RadarrView({ active }: { active: boolean }): JSX.Element {
  const { push } = useToast();
  const {
    value: globalSearch,
    setValue: setGlobalSearch,
    register,
    clearHandler,
  } = useSearch();

  const [instances, setInstances] = useState<ArrInfo[]>([]);
  const [selection, setSelection] = useState<string | "aggregate">("");
  const [instanceData, setInstanceData] = useState<RadarrMoviesResponse | null>(
    null
  );
  const [instancePage, setInstancePage] = useState(0);
  const [instanceQuery, setInstanceQuery] = useState("");
  const [instanceLoading, setInstanceLoading] = useState(false);
  const [live, setLive] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const [aggRows, setAggRows] = useState<RadarrAggRow[]>([]);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggPage, setAggPage] = useState(0);
  const [aggFilter, setAggFilter] = useState("");
  const [aggUpdated, setAggUpdated] = useState<string | null>(null);

  const loadInstances = useCallback(async () => {
    try {
      const data = await getArrList();
      const filtered = (data.arr || []).filter((arr) => arr.type === "radarr");
      setInstances(filtered);
      if (!filtered.length) {
        setSelection("");
        setInstanceData(null);
        setAggRows([]);
        return;
      }
      if (
        !selection ||
        (selection !== "aggregate" &&
          !filtered.some((arr) => arr.category === selection))
      ) {
        setSelection(filtered[0].category);
      }
    } catch (error) {
      push(
        error instanceof Error
          ? error.message
          : "Unable to load Radarr instances",
        "error"
      );
    }
  }, [push, selection]);

  const fetchInstance = useCallback(
    async (category: string, page: number, query: string) => {
      setInstanceLoading(true);
      try {
        const response = await getRadarrMovies(
          category,
          page,
          RADARR_PAGE_SIZE,
          query
        );
        setInstanceData(response);
        setInstancePage(response.page ?? page);
        setInstanceQuery(query);
        setLastUpdated(new Date().toLocaleTimeString());
      } catch (error) {
        push(
          error instanceof Error
            ? error.message
            : `Failed to load ${category} movies`,
          "error"
        );
      } finally {
        setInstanceLoading(false);
      }
    },
    [push]
  );

  const loadAggregate = useCallback(async () => {
    if (!instances.length) return;
    setAggLoading(true);
    try {
      const aggregated: RadarrAggRow[] = [];
      for (const inst of instances) {
        let page = 0;
        const label = inst.name || inst.category;
        while (page < 100) {
          const res = await getRadarrMovies(
            inst.category,
            page,
            RADARR_AGG_FETCH_SIZE,
            ""
          );
          const movies = res.movies ?? [];
          movies.forEach((movie) => {
            aggregated.push({ ...movie, __instance: label });
          });
          if (!movies.length || movies.length < RADARR_AGG_FETCH_SIZE) break;
          page += 1;
        }
      }
      setAggRows(aggregated);
      setAggPage(0);
      setAggFilter(globalSearch);
      setAggUpdated(new Date().toLocaleTimeString());
    } catch (error) {
      push(
        error instanceof Error
          ? error.message
          : "Failed to load aggregated Radarr data",
        "error"
      );
    } finally {
      setAggLoading(false);
    }
  }, [instances, globalSearch, push]);

  useEffect(() => {
    if (!active) return;
    void loadInstances();
  }, [active, loadInstances]);

  useEffect(() => {
    if (!active) return;
    if (!selection || selection === "aggregate") return;
    void fetchInstance(selection, instancePage, globalSearch);
  }, [active, selection, instancePage, globalSearch, fetchInstance]);

  useEffect(() => {
    if (!active) return;
    if (selection !== "aggregate") return;
    void loadAggregate();
  }, [active, selection, loadAggregate]);

  useEffect(() => {
    if (!active) return;
    const handler = (term: string) => {
      if (selection === "aggregate") {
        setAggFilter(term);
        setAggPage(0);
      } else if (selection) {
        setInstancePage(0);
        void fetchInstance(selection, 0, term);
      }
    };
    register(handler);
    return () => {
      clearHandler(handler);
    };
  }, [active, selection, register, clearHandler, fetchInstance]);

  useInterval(
    () => {
      if (selection && selection !== "aggregate") {
        void fetchInstance(selection, instancePage, instanceQuery);
      }
    },
    active && selection && selection !== "aggregate" && live ? 1000 : null
  );

  useEffect(() => {
    if (selection === "aggregate") {
      setAggFilter(globalSearch);
    }
  }, [selection, globalSearch]);

  const filteredAggRows = useMemo(() => {
    if (!aggFilter) return aggRows;
    const q = aggFilter.toLowerCase();
    return aggRows.filter((row) => {
      const title = (row.title ?? "").toString().toLowerCase();
      const instance = (row.__instance ?? "").toLowerCase();
      return title.includes(q) || instance.includes(q);
    });
  }, [aggRows, aggFilter]);

  const aggPages = Math.max(
    1,
    Math.ceil(filteredAggRows.length / RADARR_AGG_PAGE_SIZE)
  );
  const aggPageRows = filteredAggRows.slice(
    aggPage * RADARR_AGG_PAGE_SIZE,
    aggPage * RADARR_AGG_PAGE_SIZE + RADARR_AGG_PAGE_SIZE
  );

  const totalInstancePages = Math.max(
    1,
    instanceData
      ? Math.ceil((instanceData.total ?? 0) / (instanceData.page_size ?? RADARR_PAGE_SIZE))
      : 1
  );

  const handleRestart = useCallback(async () => {
    if (!selection || selection === "aggregate") return;
    try {
      await restartArr(selection);
      push(`Restarted ${selection}`, "success");
    } catch (error) {
      push(
        error instanceof Error ? error.message : `Failed to restart ${selection}`,
        "error"
      );
    }
  }, [selection, push]);

  const isAggregate = selection === "aggregate";

  return (
    <section className="card">
      <div className="card-header">Radarr</div>
      <div className="card-body">
        <div className="split">
          <aside className="pane sidebar">
            <button
              className={`btn ${isAggregate ? "active" : ""}`}
              onClick={() => setSelection("aggregate")}
            >
              All Radarr
            </button>
            {instances.map((inst) => (
              <button
                key={inst.category}
                className={`btn ghost ${
                  selection === inst.category ? "active" : ""
                }`}
                onClick={() => {
                  setSelection(inst.category);
                  setGlobalSearch("");
                }}
              >
                {inst.name || inst.category}
              </button>
            ))}
          </aside>
          <div className="pane">
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div className="col field">
                <label>Search</label>
                <input
                  placeholder="Filter movies"
                  value={globalSearch}
                  onChange={(event) => setGlobalSearch(event.target.value)}
                />
              </div>
              {!isAggregate && (
                <label className="hint inline" style={{ marginBottom: 8 }}>
                  <input
                    type="checkbox"
                    checked={live}
                    onChange={(event) => setLive(event.target.checked)}
                  />
                  Live
                </label>
              )}
            </div>

            {isAggregate ? (
              <RadarrAggregateView
                loading={aggLoading}
                rows={aggPageRows}
                total={filteredAggRows.length}
                page={aggPage}
                totalPages={aggPages}
                onPageChange={setAggPage}
                onRefresh={() => void loadAggregate()}
                lastUpdated={aggUpdated}
              />
            ) : (
              <RadarrInstanceView
                loading={instanceLoading}
                data={instanceData}
                page={instancePage}
                totalPages={totalInstancePages}
                onPageChange={(page) => {
                  setInstancePage(page);
                  void fetchInstance(selection as string, page, instanceQuery);
                }}
                onRestart={() => void handleRestart()}
                lastUpdated={lastUpdated}
              />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

interface RadarrAggregateViewProps {
  loading: boolean;
  rows: RadarrAggRow[];
  total: number;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  lastUpdated: string | null;
}

function RadarrAggregateView({
  loading,
  rows,
  total,
  page,
  totalPages,
  onPageChange,
  onRefresh,
  lastUpdated,
}: RadarrAggregateViewProps): JSX.Element {
  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          Aggregated movies across all instances{" "}
          {lastUpdated ? `(updated ${lastUpdated})` : ""}
        </div>
        <button className="btn ghost" onClick={onRefresh} disabled={loading}>
          Refresh
        </button>
      </div>
      {loading ? (
        <div className="loading">
          <span className="spinner" /> Loading Radarr library…
        </div>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>Instance</th>
                <th>Title</th>
                <th>Year</th>
                <th>Monitored</th>
                <th>Has File</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={`${row.__instance}-${row.id ?? idx}`}>
                  <td>{row.__instance}</td>
                  <td>{row.title ?? ""}</td>
                  <td>{row.year ?? ""}</td>
                  <td>{row.monitored ? "Yes" : "No"}</td>
                  <td>{row.hasFile ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pagination">
            <div>
              Page {page + 1} of {totalPages} ({total} items)
            </div>
            <div className="inline">
              <button
                className="btn"
                onClick={() => onPageChange(Math.max(0, page - 1))}
                disabled={page === 0}
              >
                Prev
              </button>
              <button
                className="btn"
                onClick={() =>
                  onPageChange(Math.min(totalPages - 1, page + 1))
                }
                disabled={page >= totalPages - 1}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

interface RadarrInstanceViewProps {
  loading: boolean;
  data: RadarrMoviesResponse | null;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRestart: () => void;
  lastUpdated: string | null;
}

function RadarrInstanceView({
  loading,
  data,
  page,
  totalPages,
  onPageChange,
  onRestart,
  lastUpdated,
}: RadarrInstanceViewProps): JSX.Element {
  const counts = data?.counts;
  const movies = data?.movies ?? [];
  const showInitialLoading = loading && movies.length === 0;
  const refreshLabel = lastUpdated ? `Last updated ${lastUpdated}` : null;

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="inline hint">
          <span className="badge">
            Available: {counts?.available ?? 0} / Monitored:{" "}
            {counts?.monitored ?? 0}
          </span>
          {refreshLabel ? <span>{refreshLabel}</span> : null}
        </div>
        <button className="btn ghost" onClick={onRestart}>
          Restart Instance
        </button>
      </div>
      {showInitialLoading && (
        <div className="loading">
          <span className="spinner" /> Updating…
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Year</th>
            <th>Monitored</th>
            <th>Has File</th>
          </tr>
        </thead>
        <tbody>
          {movies.map((movie) => (
            <tr key={movie.id ?? `${movie.title}-${movie.year}`}>
              <td>{movie.title ?? ""}</td>
              <td>{movie.year ?? ""}</td>
              <td>{movie.monitored ? "Yes" : "No"}</td>
              <td>{movie.hasFile ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pagination">
        <div>
          Page {page + 1} of {totalPages} ({data?.total ?? movies.length} items)
        </div>
        <div className="inline">
          <button
            className="btn"
            onClick={() => onPageChange(Math.max(0, page - 1))}
            disabled={page === 0 || loading}
          >
            Prev
          </button>
          <button
            className="btn"
            onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
            disabled={page >= totalPages - 1 || loading}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

function SonarrView({ active }: { active: boolean }): JSX.Element {
  const { push } = useToast();
  const {
    value: globalSearch,
    setValue: setGlobalSearch,
    register,
    clearHandler,
  } = useSearch();

  const [instances, setInstances] = useState<ArrInfo[]>([]);
  const [selection, setSelection] = useState<string | "aggregate">("");
  const [instanceData, setInstanceData] =
    useState<SonarrSeriesResponse | null>(null);
  const [instancePage, setInstancePage] = useState(0);
  const [instanceQuery, setInstanceQuery] = useState("");
  const [instanceLoading, setInstanceLoading] = useState(false);
  const [live, setLive] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const [aggRows, setAggRows] = useState<SonarrAggRow[]>([]);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggPage, setAggPage] = useState(0);
  const [aggFilter, setAggFilter] = useState("");
  const [aggUpdated, setAggUpdated] = useState<string | null>(null);

  const loadInstances = useCallback(async () => {
    try {
      const data = await getArrList();
      const filtered = (data.arr || []).filter((arr) => arr.type === "sonarr");
      setInstances(filtered);
      if (!filtered.length) {
        setSelection("");
        setInstanceData(null);
        setAggRows([]);
        return;
      }
      if (
        !selection ||
        (selection !== "aggregate" &&
          !filtered.some((arr) => arr.category === selection))
      ) {
        setSelection(filtered[0].category);
      }
    } catch (error) {
      push(
        error instanceof Error
          ? error.message
          : "Unable to load Sonarr instances",
        "error"
      );
    }
  }, [push, selection]);

  const fetchInstance = useCallback(
    async (category: string, page: number, query: string) => {
      setInstanceLoading(true);
      try {
        const response = await getSonarrSeries(
          category,
          page,
          SONARR_PAGE_SIZE,
          query
        );
        setInstanceData(response);
        setInstancePage(response.page ?? page);
        setInstanceQuery(query);
        setLastUpdated(new Date().toLocaleTimeString());
      } catch (error) {
        push(
          error instanceof Error
            ? error.message
            : `Failed to load ${category} series`,
          "error"
        );
      } finally {
        setInstanceLoading(false);
      }
    },
    [push]
  );

  const loadAggregate = useCallback(async () => {
    if (!instances.length) return;
    setAggLoading(true);
    try {
      const aggregated: SonarrAggRow[] = [];
      for (const inst of instances) {
        let page = 0;
        const label = inst.name || inst.category;
        while (page < 200) {
          const res = await getSonarrSeries(
            inst.category,
            page,
            SONARR_AGG_FETCH_SIZE,
            ""
          );
          const series = res.series ?? [];
          series.forEach((entry: SonarrSeriesEntry) => {
            const title =
              (entry.series?.["title"] as string | undefined) || "";
            Object.entries(entry.seasons ?? {}).forEach(
              ([seasonNumber, season]) => {
                (season.episodes ?? []).forEach((episode: SonarrEpisode) => {
                  aggregated.push({
                    __instance: label,
                    series: title,
                    season: seasonNumber,
                    episode: episode.episodeNumber ?? "",
                    title: episode.title ?? "",
                    monitored: !!episode.monitored,
                    hasFile: !!episode.hasFile,
                    airDate: episode.airDateUtc ?? "",
                  });
                });
              }
            );
          });
          if (!series.length || series.length < SONARR_AGG_FETCH_SIZE) break;
          page += 1;
        }
      }
      setAggRows(aggregated);
      setAggPage(0);
      setAggFilter(globalSearch);
      setAggUpdated(new Date().toLocaleTimeString());
    } catch (error) {
      push(
        error instanceof Error
          ? error.message
          : "Failed to load aggregated Sonarr data",
        "error"
      );
    } finally {
      setAggLoading(false);
    }
  }, [instances, globalSearch, push]);

  useEffect(() => {
    if (!active) return;
    void loadInstances();
  }, [active, loadInstances]);

  useEffect(() => {
    if (!active) return;
    if (!selection || selection === "aggregate") return;
    void fetchInstance(selection, instancePage, globalSearch);
  }, [active, selection, instancePage, globalSearch, fetchInstance]);

  useEffect(() => {
    if (!active) return;
    if (selection !== "aggregate") return;
    void loadAggregate();
  }, [active, selection, loadAggregate]);

  useEffect(() => {
    if (!active) return;
    const handler = (term: string) => {
      if (selection === "aggregate") {
        setAggFilter(term);
        setAggPage(0);
      } else if (selection) {
        setInstancePage(0);
        void fetchInstance(selection, 0, term);
      }
    };
    register(handler);
    return () => clearHandler(handler);
  }, [active, selection, register, clearHandler, fetchInstance]);

  useInterval(
    () => {
      if (selection && selection !== "aggregate") {
        void fetchInstance(selection, instancePage, instanceQuery);
      }
    },
    active && selection && selection !== "aggregate" && live ? 1000 : null
  );

  useEffect(() => {
    if (selection === "aggregate") {
      setAggFilter(globalSearch);
    }
  }, [selection, globalSearch]);

  const filteredAggRows = useMemo(() => {
    if (!aggFilter) return aggRows;
    const q = aggFilter.toLowerCase();
    return aggRows.filter((row) => {
      return (
        row.series.toLowerCase().includes(q) ||
        row.title.toLowerCase().includes(q) ||
        row.__instance.toLowerCase().includes(q)
      );
    });
  }, [aggRows, aggFilter]);

  const aggPages = Math.max(
    1,
    Math.ceil(filteredAggRows.length / SONARR_AGG_PAGE_SIZE)
  );
  const aggPageRows = filteredAggRows.slice(
    aggPage * SONARR_AGG_PAGE_SIZE,
    aggPage * SONARR_AGG_PAGE_SIZE + SONARR_AGG_PAGE_SIZE
  );

  const totalInstancePages = Math.max(
    1,
    instanceData
      ? Math.ceil((instanceData.total ?? 0) / (instanceData.page_size ?? SONARR_PAGE_SIZE))
      : 1
  );

  const handleRestart = useCallback(async () => {
    if (!selection || selection === "aggregate") return;
    try {
      await restartArr(selection);
      push(`Restarted ${selection}`, "success");
    } catch (error) {
      push(
        error instanceof Error ? error.message : `Failed to restart ${selection}`,
        "error"
      );
    }
  }, [selection, push]);

  const isAggregate = selection === "aggregate";

  return (
    <section className="card">
      <div className="card-header">Sonarr</div>
      <div className="card-body">
        <div className="split">
          <aside className="pane sidebar">
            <button
              className={`btn ${isAggregate ? "active" : ""}`}
              onClick={() => setSelection("aggregate")}
            >
              All Sonarr
            </button>
            {instances.map((inst) => (
              <button
                key={inst.category}
                className={`btn ghost ${
                  selection === inst.category ? "active" : ""
                }`}
                onClick={() => {
                  setSelection(inst.category);
                  setGlobalSearch("");
                }}
              >
                {inst.name || inst.category}
              </button>
            ))}
          </aside>
          <div className="pane">
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div className="col field">
                <label>Search</label>
                <input
                  placeholder="Filter series or episodes"
                  value={globalSearch}
                  onChange={(event) => setGlobalSearch(event.target.value)}
                />
              </div>
              {!isAggregate && (
                <label className="hint inline" style={{ marginBottom: 8 }}>
                  <input
                    type="checkbox"
                    checked={live}
                    onChange={(event) => setLive(event.target.checked)}
                  />
                  Live
                </label>
              )}
            </div>

            {isAggregate ? (
              <SonarrAggregateView
                loading={aggLoading}
                rows={aggPageRows}
                total={filteredAggRows.length}
                page={aggPage}
                totalPages={aggPages}
                onPageChange={setAggPage}
                onRefresh={() => void loadAggregate()}
                lastUpdated={aggUpdated}
              />
            ) : (
              <SonarrInstanceView
                loading={instanceLoading}
                data={instanceData}
                page={instancePage}
                totalPages={totalInstancePages}
                onPageChange={(page) => {
                  setInstancePage(page);
                  void fetchInstance(selection as string, page, instanceQuery);
                }}
                onRestart={() => void handleRestart()}
                lastUpdated={lastUpdated}
              />
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

interface SonarrAggregateViewProps {
  loading: boolean;
  rows: SonarrAggRow[];
  total: number;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  lastUpdated: string | null;
}

function SonarrAggregateView({
  loading,
  rows,
  total,
  page,
  totalPages,
  onPageChange,
  onRefresh,
  lastUpdated,
}: SonarrAggregateViewProps): JSX.Element {
  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          Aggregated monitored episodes {lastUpdated ? `(updated ${lastUpdated})` : ""}
        </div>
        <button className="btn ghost" onClick={onRefresh} disabled={loading}>
          Refresh
        </button>
      </div>
      {loading ? (
        <div className="loading">
          <span className="spinner" /> Loading Sonarr library…
        </div>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>Instance</th>
                <th>Series</th>
                <th>Season</th>
                <th>Episode</th>
                <th>Title</th>
                <th>Monitored</th>
                <th>Has File</th>
                <th>Air Date</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={`${row.__instance}-${idx}`}>
                  <td>{row.__instance}</td>
                  <td>{row.series}</td>
                  <td>{row.season}</td>
                  <td>{row.episode}</td>
                  <td>{row.title}</td>
                  <td>{row.monitored ? "Yes" : "No"}</td>
                  <td>{row.hasFile ? "Yes" : "No"}</td>
                  <td>{row.airDate}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pagination">
            <div>
              Page {page + 1} of {totalPages} ({total} items)
            </div>
            <div className="inline">
              <button
                className="btn"
                onClick={() => onPageChange(Math.max(0, page - 1))}
                disabled={page === 0}
              >
                Prev
              </button>
              <button
                className="btn"
                onClick={() =>
                  onPageChange(Math.min(totalPages - 1, page + 1))
                }
                disabled={page >= totalPages - 1}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

interface SonarrInstanceViewProps {
  loading: boolean;
  data: SonarrSeriesResponse | null;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRestart: () => void;
  lastUpdated: string | null;
}

function SonarrInstanceView({
  loading,
  data,
  page,
  totalPages,
  onPageChange,
  onRestart,
  lastUpdated,
}: SonarrInstanceViewProps): JSX.Element {
  const series = data?.series ?? [];
  const counts = data?.counts;
  const showInitialLoading = loading && series.length === 0;
  const refreshLabel = lastUpdated ? `Last updated ${lastUpdated}` : null;
  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="inline hint">
          <span className="badge">
            Available: {counts?.available ?? 0} / Monitored:{" "}
            {counts?.monitored ?? 0}
          </span>
          {refreshLabel ? <span>{refreshLabel}</span> : null}
        </div>
        <button className="btn ghost" onClick={onRestart}>
          Restart Instance
        </button>
      </div>
      {showInitialLoading && (
        <div className="loading">
          <span className="spinner" /> Updating…
        </div>
      )}
      <div className="stack">
        {series.map((entry, idx) => {
          const title =
            (entry.series?.["title"] as string | undefined) || `Series ${idx + 1}`;
          return (
            <details key={idx} open>
              <summary>
                {title}{" "}
                <span className="hint">
                  (Monitored {entry.totals?.monitored ?? 0} / Available{" "}
                  {entry.totals?.available ?? 0})
                </span>
              </summary>
              {Object.entries(entry.seasons ?? {}).map(
                ([seasonNumber, season]) => (
                  <details key={seasonNumber}>
                    <summary>
                      Season {seasonNumber}{" "}
                      <span className="hint">
                        (Monitored {season.monitored} / Available{" "}
                        {season.available})
                      </span>
                    </summary>
                    <table>
                      <thead>
                        <tr>
                          <th>Episode</th>
                          <th>Title</th>
                          <th>Monitored</th>
                          <th>Has File</th>
                          <th>Air Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(season.episodes ?? []).map((ep, epIdx) => (
                          <tr key={ep.id ?? epIdx}>
                            <td>{ep.episodeNumber ?? ""}</td>
                            <td>{ep.title ?? ""}</td>
                            <td>{ep.monitored ? "Yes" : "No"}</td>
                            <td>{ep.hasFile ? "Yes" : "No"}</td>
                            <td>{ep.airDateUtc ?? ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </details>
                )
              )}
            </details>
          );
        })}
      </div>
      <div className="pagination">
        <div>
          Page {page + 1} of {totalPages} ({data?.total ?? series.length} items)
        </div>
        <div className="inline">
          <button
            className="btn"
            onClick={() => onPageChange(Math.max(0, page - 1))}
            disabled={page === 0 || loading}
          >
            Prev
          </button>
          <button
            className="btn"
            onClick={() => onPageChange(Math.min(totalPages - 1, page + 1))}
            disabled={page >= totalPages - 1 || loading}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
