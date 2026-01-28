import { useCallback, useEffect, useRef, useState, type JSX } from "react";
import { getQbitCategories } from "../api/client";
import type { QbitCategory } from "../api/types";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";
import { useWebUI } from "../context/WebUIContext";
import RefreshIcon from "../icons/refresh-arrow.svg";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / k ** i).toFixed(2)} ${sizes[i]}`;
}

function formatTime(seconds: number): string {
  if (seconds === 0) return "0s";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);

  return parts.join(" ");
}

function getRemoveModeText(mode: number): string {
  switch (mode) {
    case -1:
      return "Never";
    case 1:
      return "On Ratio";
    case 2:
      return "On Time";
    case 3:
      return "Ratio OR Time";
    case 4:
      return "Ratio AND Time";
    default:
      return "Unknown";
  }
}

function areCategoriesEqual(a: QbitCategory[], b: QbitCategory[]): boolean {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    const catA = a[i];
    const catB = b[i];
    if (
      catA.category !== catB.category ||
      catA.instance !== catB.instance ||
      catA.torrentCount !== catB.torrentCount ||
      catA.seedingCount !== catB.seedingCount ||
      catA.totalSize !== catB.totalSize ||
      catA.avgRatio !== catB.avgRatio ||
      catA.avgSeedingTime !== catB.avgSeedingTime
    ) {
      return false;
    }
  }
  return true;
}

interface QbitCategoriesViewProps {
  active: boolean;
}

export function QbitCategoriesView({ active }: QbitCategoriesViewProps): JSX.Element {
  const [categories, setCategories] = useState<QbitCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const { push } = useToast();
  const { liveArr } = useWebUI();
  const isFetching = useRef(false);

  const load = useCallback(
    async (showLoading = true) => {
      if (isFetching.current) {
        return;
      }
      isFetching.current = true;
      if (showLoading) {
        setLoading(true);
      }
      try {
        const data = await getQbitCategories();
        setCategories((prev) =>
          areCategoriesEqual(prev, data.categories) ? prev : data.categories
        );
      } catch (error) {
        push(
          error instanceof Error
            ? error.message
            : "Failed to load qBit categories",
          "error"
        );
      } finally {
        isFetching.current = false;
        if (showLoading) {
          setLoading(false);
        }
      }
    },
    [push]
  );

  useEffect(() => {
    if (active) {
      void load();
    }
  }, [active, load]);

  useInterval(
    () => {
      void load(false);
    },
    liveArr ? 1000 : null
  );

  const handleRefresh = useCallback(() => {
    void load();
  }, [load]);

  return (
    <div className="qbit-categories-view">
      <div className="qbit-categories-header">
        <h2>qBit-Managed Categories</h2>
        <button
          type="button"
          className="btn btn-refresh"
          onClick={handleRefresh}
          disabled={loading}
        >
          <img src={RefreshIcon} alt="Refresh" className="icon-sm" />
          Refresh
        </button>
      </div>

      {loading && categories.length === 0 ? (
        <div className="loading-state">Loading qBit categories...</div>
      ) : categories.length === 0 ? (
        <div className="empty-state">
          <p>No qBit-managed categories configured.</p>
          <p className="text-muted">
            Configure ManagedCategories in your qBit config sections to see categories here.
          </p>
        </div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Instance</th>
                <th>Torrents</th>
                <th>Seeding</th>
                <th>Total Size</th>
                <th>Avg Ratio</th>
                <th>Avg Seed Time</th>
                <th>Max Ratio</th>
                <th>Max Time</th>
                <th>Remove Mode</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((cat) => (
                <tr key={`${cat.instance}-${cat.category}`}>
                  <td className="category-name">{cat.category}</td>
                  <td className="instance-name">{cat.instance}</td>
                  <td className="torrent-count">{cat.torrentCount}</td>
                  <td className="seeding-count">{cat.seedingCount}</td>
                  <td className="total-size">{formatBytes(cat.totalSize)}</td>
                  <td className="avg-ratio">{cat.avgRatio.toFixed(2)}</td>
                  <td className="avg-seed-time">
                    {formatTime(cat.avgSeedingTime)}
                  </td>
                  <td className="max-ratio">
                    {cat.seedingConfig.maxRatio === -1
                      ? "Disabled"
                      : cat.seedingConfig.maxRatio.toFixed(2)}
                  </td>
                  <td className="max-time">
                    {cat.seedingConfig.maxTime === -1
                      ? "Disabled"
                      : formatTime(cat.seedingConfig.maxTime)}
                  </td>
                  <td className="remove-mode">
                    {getRemoveModeText(cat.seedingConfig.removeMode)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
