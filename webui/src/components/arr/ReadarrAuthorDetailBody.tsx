import { useEffect, useState } from "react";
import type { JSX } from "react";
import { getReadarrOpenAuthorUrl } from "../../api/client";
import { getReadarrAuthorDetail } from "../../api/client";
import type { ReadarrAuthorDetailResponse } from "../../api/types";
import { readarrAuthorThumbnailUrl } from "../../utils/arrThumbnailUrl";
import { ArrExternalLink, ArrInstanceHint } from "./ArrExternalLink";
import { ArrPosterImage } from "./ArrPosterImage";
import { ReadarrBookDetailBody } from "./ReadarrBookDetailBody";
import { ArrMonitoredBadge } from "./ArrStatusCells";

export function ReadarrAuthorDetailBody({
  category,
  authorId,
  instanceLabel,
}: {
  category: string;
  authorId: number;
  /** Sidebar label for this Arr instance (matches Lidarr detail hint line). */
  instanceLabel?: string | null;
}): JSX.Element {
  const [payload, setPayload] = useState<ReadarrAuthorDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getReadarrAuthorDetail(category, authorId).then(
      (data) => {
        if (!cancelled) setPayload(data);
      },
      (e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to load author");
        }
      }
    );
    return () => {
      cancelled = true;
    };
  }, [category, authorId]);

  if (error) {
    return <p className="hint">{error}</p>;
  }

  if (!payload) {
    return (
      <div className="loading">
        <span className="spinner" /> Loading author…
      </div>
    );
  }

  const a = payload.author;
  const poster =
    typeof a?.["id"] === "number"
      ? readarrAuthorThumbnailUrl(category, authorId)
      : null;
  const profileName = (a?.["qualityProfileName"] as string | null | undefined) ?? null;
  const hintLabel =
    instanceLabel != null && String(instanceLabel).trim() !== ""
      ? String(instanceLabel).trim()
      : null;

  const books = payload.books ?? [];
  const openUrl =
    authorId > 0 && category ? getReadarrOpenAuthorUrl(category, authorId) : null;

  return (
    <div className="arr-detail-radarr">
      <ArrExternalLink href={openUrl} arrName="Readarr" />
      <ArrInstanceHint instanceLabel={hintLabel} qualityProfileName={profileName} />

      <div
        className="arr-detail-radarr__poster-row"
        style={{ display: "flex", gap: 16, flexWrap: "wrap" }}
      >
        {poster ? (
          <div className="arr-detail-radarr__poster">
            <ArrPosterImage src={poster} alt={(a?.["name"] as string) || ""} />
          </div>
        ) : null}
        <dl className="arr-detail-dl">
          <dt>Author</dt>
          <dd>{String(a?.["name"] ?? "—")}</dd>
          <dt>Monitored</dt>
          <dd>
            <ArrMonitoredBadge monitored={Boolean(a?.["monitored"])} />
          </dd>
          <dt>Books</dt>
          <dd>{Number(a?.["bookCount"] ?? 0).toLocaleString()}</dd>
        </dl>
      </div>

      <h4 style={{ margin: "16px 0 8px" }}>Books</h4>
      {books.length === 0 ? (
        <p className="hint">No books for this author in the local catalog.</p>
      ) : (
        <div className="stack" style={{ gap: 12 }}>
          {books.map((bookEntry, idx) => {
            const bk = bookEntry.book as Record<string, unknown>;
            const bkTitle = String(bk?.["title"] ?? "Book");
            return (
              <details
                key={String(bk?.["id"] ?? idx)}
                className="arr-series-season"
                open={books.length <= 3}
              >
                <summary style={{ fontWeight: 600, cursor: "pointer" }}>
                  {bkTitle}
                </summary>
                <div style={{ marginTop: 8 }}>
                  <ReadarrBookDetailBody entry={bookEntry} />
                </div>
              </details>
            );
          })}
        </div>
      )}
    </div>
  );
}
