import type { JSX } from "react";

interface ArrExternalLinkProps {
  readonly href: string | null;
  readonly arrName: "Radarr" | "Sonarr" | "Lidarr" | "Readarr";
}

/** Shared "Open in *Arr" action link for detail modals. */
export function ArrExternalLink({ href, arrName }: ArrExternalLinkProps): JSX.Element | null {
  if (!href) {
    return null;
  }
  return (
    <div className="arr-detail-actions">
      <a className="btn small outline" href={href} target="_blank" rel="noreferrer">
        Open in {arrName}
      </a>
    </div>
  );
}

interface ArrInstanceHintProps {
  readonly instanceLabel?: string | null;
  readonly qualityProfileName?: string | null;
}

/** Instance + quality profile hint line (Sonarr series group, Lidarr artist). */
export function ArrInstanceHint({
  instanceLabel,
  qualityProfileName,
}: ArrInstanceHintProps): JSX.Element | null {
  const hintLabel =
    instanceLabel != null && String(instanceLabel).trim() !== ""
      ? String(instanceLabel).trim()
      : null;
  const profileName = qualityProfileName?.trim() ? qualityProfileName.trim() : null;
  if (hintLabel == null && !profileName) {
    return null;
  }
  return (
    <p className="hint" style={{ margin: 0 }}>
      {hintLabel != null ? (
        <>
          <strong>Instance:</strong> {hintLabel}
        </>
      ) : null}
      {hintLabel != null && profileName ? <> • </> : null}
      {profileName ? (
        <>
          <strong>Profile:</strong> {profileName}
        </>
      ) : null}
    </p>
  );
}
