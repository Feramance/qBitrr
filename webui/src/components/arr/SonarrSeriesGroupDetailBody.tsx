import { useMemo, type JSX } from "react";

export type SonarrEpisodeRow = {
  __instance: string;
  series: string;
  season: number | string;
  episode: number | string;
  title: string;
  monitored: boolean;
  hasFile: boolean;
  airDate: string;
  reason?: string | null;
};

export type SonarrSeriesGroup = {
  instance: string;
  series: string;
  qualityProfileName?: string | null;
  seriesId?: number;
  episodes: SonarrEpisodeRow[];
};

function sortEpisodes(a: SonarrEpisodeRow, b: SonarrEpisodeRow): number {
  const s = String(a.season).localeCompare(String(b.season), undefined, { numeric: true });
  if (s !== 0) return s;
  const ea = Number(a.episode);
  const eb = Number(b.episode);
  if (Number.isFinite(ea) && Number.isFinite(eb)) return ea - eb;
  return String(a.episode).localeCompare(String(b.episode), undefined, { numeric: true });
}

export function SonarrSeriesGroupDetailBody({
  group,
}: {
  group: SonarrSeriesGroup;
}): JSX.Element {
  const bySeason = useMemo(() => {
    const m = new Map<string, SonarrEpisodeRow[]>();
    for (const e of group.episodes) {
      const sk = String(e.season);
      if (!m.has(sk)) m.set(sk, []);
      m.get(sk)!.push(e);
    }
    for (const arr of m.values()) {
      arr.sort(sortEpisodes);
    }
    return Array.from(m.entries()).sort(([a], [b]) =>
      a.localeCompare(b, undefined, { numeric: true })
    );
  }, [group.episodes]);

  return (
    <div className="stack" style={{ gap: "8px" }}>
      <p className="hint" style={{ margin: 0 }}>
        <strong>Instance:</strong> {group.instance}
        {group.qualityProfileName ? (
          <>
            {" "}
            • <strong>Profile:</strong> {group.qualityProfileName}
          </>
        ) : null}
      </p>
      {bySeason.map(([season, eps]) => (
        <details
          key={season}
          className="arr-series-season"
          open={bySeason.length <= 3}
        >
          <summary style={{ fontWeight: 600, cursor: "pointer" }}>
            Season {season} ({eps.length} episodes)
          </summary>
          <div className="table-wrapper" style={{ marginTop: 8 }}>
            <table className="responsive-table">
              <thead>
                <tr>
                  <th>Ep</th>
                  <th>Title</th>
                  <th>Monitored</th>
                  <th>File</th>
                  <th>Air</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {eps.map((ep) => (
                  <tr
                    key={`${ep.season}-${ep.episode}-${ep.title}`}
                  >
                    <td data-label="Episode">{ep.episode}</td>
                    <td data-label="Title">{ep.title}</td>
                    <td data-label="Monitored">
                      <span
                        className={`track-status ${
                          ep.monitored ? "available" : "missing"
                        }`}
                      >
                        {ep.monitored ? "✓" : "✗"}
                      </span>
                    </td>
                    <td data-label="File">
                      <span
                        className={`track-status ${
                          ep.hasFile ? "available" : "missing"
                        }`}
                      >
                        {ep.hasFile ? "✓" : "✗"}
                      </span>
                    </td>
                    <td data-label="Air">{ep.airDate || "—"}</td>
                    <td data-label="Reason">
                      {ep.reason ? (
                        <span className="table-badge table-badge-reason">
                          {ep.reason}
                        </span>
                      ) : (
                        <span className="table-badge table-badge-reason">
                          Not being searched
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ))}
    </div>
  );
}
