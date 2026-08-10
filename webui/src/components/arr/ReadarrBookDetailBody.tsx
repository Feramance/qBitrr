import type { JSX } from "react";
import type { ReadarrBookEntry } from "../../api/types";
import {
  ArrHasFileBadge,
  ArrMonitoredBadge,
  ArrReasonBadge,
} from "./ArrStatusCells";

type Bookish = ReadarrBookEntry & { __instance?: string };

/** Book metadata block used inside author detail (mirrors Lidarr album detail, without tracks). */
export function ReadarrBookDetailBody({
  entry,
}: {
  entry: Bookish;
}): JSX.Element {
  const book = entry.book as Record<string, unknown>;
  const title = (book?.["title"] as string | undefined) || "—";
  const author = (book?.["authorName"] as string | undefined) || "—";
  const release = book?.["releaseDate"] as string | undefined;
  const monitored = book?.["monitored"] as boolean | undefined;
  const hasFile = book?.["hasFile"] as boolean | undefined;
  const reason = book?.["reason"] as string | null | undefined;
  const qProf = (book?.["qualityProfileName"] as string | null | undefined) ?? "—";
  const totals = entry.totals;

  return (
    <div className="arr-detail-radarr">
      <dl className="arr-detail-dl">
        <dt>Book</dt>
        <dd>{title}</dd>
        <dt>Author</dt>
        <dd>{author}</dd>
        <dt>Release</dt>
        <dd>
          {release ? new Date(release).toLocaleDateString() : "—"}
        </dd>
        <dt>Monitored</dt>
        <dd>
          <ArrMonitoredBadge monitored={Boolean(monitored)} />
        </dd>
        <dt>Has file</dt>
        <dd>
          <ArrHasFileBadge hasFile={Boolean(hasFile)} />
        </dd>
        <dt>Quality profile</dt>
        <dd>{qProf}</dd>
        <dt>Reason</dt>
        <dd>
          <ArrReasonBadge reason={reason} />
        </dd>
        {totals ? (
          <>
            <dt>Totals</dt>
            <dd>
              {totals.available ?? 0} available / {totals.monitored ?? 0} monitored
            </dd>
          </>
        ) : null}
      </dl>
    </div>
  );
}
