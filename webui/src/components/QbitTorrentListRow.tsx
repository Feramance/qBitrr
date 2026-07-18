import type { JSX, ReactNode } from "react";
import type { QbitTorrentOverview } from "../api/types";
import {
  formatTorrentStateLabel,
  torrentStateFamily,
} from "../utils/qbitTorrentDisplay";

const INFINITE_ETA = 8640000;

function formatBytes(bytes: number): { value: string; unit: string } {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return { value: "0", unit: "B" };
  }
  const k = 1024;
  const sizes = ["B", "KiB", "MiB", "GiB", "TiB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1);
  return { value: (bytes / k ** i).toFixed(i === 0 ? 0 : 2), unit: sizes[i]! };
}

function formatSpeed(bytesPerSec: number): { value: string; unit: string } {
  const { value, unit } = formatBytes(bytesPerSec);
  return { value, unit: `${unit}/s` };
}

function formatEta(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0 || seconds >= INFINITE_ETA) {
    return "∞";
  }
  const total = Math.round(seconds);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
  return parts.join(" ");
}

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "0s";
  }
  return formatEta(seconds);
}

function formatAddedOn(unixSeconds: number): string {
  if (!unixSeconds) {
    return "—";
  }
  try {
    return new Date(unixSeconds * 1000).toLocaleString();
  } catch {
    return "—";
  }
}

function ratioClass(ratio: number): string {
  if (ratio < 0.5) return "qbit-ratio--bad";
  if (ratio < 1) return "qbit-ratio--almost";
  if (ratio < 5) return "qbit-ratio--good";
  return "qbit-ratio--best";
}

interface MetricProps {
  label: string;
  children: ReactNode;
}

function Metric({ label, children }: MetricProps): JSX.Element {
  return (
    <div className="qbit-torrent-metric">
      <div className="qbit-torrent-metric__label">{label}</div>
      <div className="qbit-torrent-metric__value">{children}</div>
    </div>
  );
}

interface DataMetricProps {
  label: string;
  bytes: number;
}

function DataMetric({ label, bytes }: DataMetricProps): JSX.Element {
  const { value, unit } = formatBytes(bytes);
  return (
    <Metric label={label}>
      {value} <span className="qbit-torrent-metric__unit">{unit}</span>
    </Metric>
  );
}

interface SpeedMetricProps {
  label: string;
  bytesPerSec: number;
}

function SpeedMetric({ label, bytesPerSec }: SpeedMetricProps): JSX.Element {
  const { value, unit } = formatSpeed(bytesPerSec);
  return (
    <Metric label={label}>
      {value} <span className="qbit-torrent-metric__unit">{unit}</span>
    </Metric>
  );
}

interface QbitTorrentListRowProps {
  torrent: QbitTorrentOverview;
}

export function QbitTorrentListRow({ torrent }: QbitTorrentListRowProps): JSX.Element {
  const family = torrentStateFamily(torrent.state);
  const done = torrent.progress >= 1;
  const progressPct = Math.min(100, Math.max(0, torrent.progress * 100));

  return (
    <article className={`qbit-torrent-row qbit-torrent-row--${family}`}>
      <div className="qbit-torrent-row__title" title={torrent.name}>
        {torrent.name}
      </div>
      <div className="qbit-torrent-metrics">
        <DataMetric label="Size" bytes={torrent.size} />
        <Metric label="Progress">
          <div
            className={`qbit-torrent-progress qbit-torrent-progress--${family}`}
            role="progressbar"
            aria-valuenow={Math.round(progressPct)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="qbit-torrent-progress__bar"
              style={{ width: `${progressPct}%` }}
            />
            <span className="qbit-torrent-progress__text">
              {progressPct.toFixed(1)}%
            </span>
          </div>
        </Metric>
        {!done && <SpeedMetric label="Download" bytesPerSec={torrent.dlspeed} />}
        <SpeedMetric label="Upload" bytesPerSec={torrent.upspeed} />
        <DataMetric label="Downloaded" bytes={torrent.downloaded} />
        <DataMetric label="Uploaded" bytes={torrent.uploaded} />
        {!done && <Metric label="ETA">{formatEta(torrent.eta)}</Metric>}
        {done && torrent.seedingTime > 0 && (
          <Metric label="Seeding time">{formatDuration(torrent.seedingTime)}</Metric>
        )}
        <Metric label="Peers">
          {torrent.numLeechs}
          <span className="qbit-torrent-metric__unit">
            {" "}
            / {torrent.numIncomplete}
          </span>
        </Metric>
        <Metric label="Seeds">
          {torrent.numSeeds}
          <span className="qbit-torrent-metric__unit">
            {" "}
            / {torrent.numComplete}
          </span>
        </Metric>
        <Metric label="State">
          <span className={`badge qbit-state-badge qbit-state-badge--${family}`}>
            {formatTorrentStateLabel(torrent.state)}
          </span>
        </Metric>
        <Metric label="Ratio">
          <span className={ratioClass(torrent.ratio)}>
            {torrent.ratio.toFixed(2)}
          </span>
        </Metric>
        <Metric label="Availability">
          {torrent.availability.toFixed(2)}
        </Metric>
        <Metric label="Added on">{formatAddedOn(torrent.addedOn)}</Metric>
        {torrent.tags.length > 0 && (
          <Metric label="Tags">
            <div className="qbit-torrent-tags">
              {torrent.tags.map((tag) => (
                <span key={tag} className="badge">
                  {tag}
                </span>
              ))}
            </div>
          </Metric>
        )}
      </div>
    </article>
  );
}
