import { useCallback, useEffect, useMemo, useRef, useState, type JSX } from "react";
import { getQbitCategories } from "../api/client";
import type { QbitCategory } from "../api/types";
import { useToast } from "../context/ToastContext";
import { useInterval } from "../hooks/useInterval";
import { useWebUI } from "../context/WebUIContext";
import { StableTable } from "../components/StableTable";
import {
  type ColumnDef,
} from "@tanstack/react-table";
import { IconImage } from "../components/IconImage";
import RefreshIcon from "../icons/refresh-arrow.svg";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / k ** i).toFixed(2)} ${sizes[i]}`;
}

function formatTime(seconds: number): string {
  const totalSeconds = Math.round(seconds);
  if (totalSeconds === 0) return "0s";

  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

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
      catA.avgSeedingTime !== catB.avgSeedingTime ||
      catA.managedBy !== catB.managedBy
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

  // Calculate summary stats
  const summary = useMemo(() => {
    const totalTorrents = categories.reduce((sum, cat) => sum + cat.torrentCount, 0);
    const totalSeeding = categories.reduce((sum, cat) => sum + cat.seedingCount, 0);
    const totalSize = categories.reduce((sum, cat) => sum + cat.totalSize, 0);
    const qbitCount = categories.filter((cat) => cat.managedBy === "qbit").length;
    const arrCount = categories.filter((cat) => cat.managedBy === "arr").length;

    return {
      totalTorrents,
      totalSeeding,
      totalSize,
      qbitCount,
      arrCount,
      categoryCount: categories.length,
    };
  }, [categories]);

  // Define table columns
  const columns = useMemo<ColumnDef<QbitCategory>[]>(
    () => [
      {
        accessorKey: "category",
        header: "Category",
        cell: (info) => info.getValue(),
        size: 150,
      },
      {
        accessorKey: "managedBy",
        header: "Managed By",
        cell: (info) => {
          const managedBy = info.getValue() as "qbit" | "arr";
          return managedBy === "qbit" ? (
            <span className="badge badge-qbit">qBit</span>
          ) : (
            <span className="badge badge-arr">Arr</span>
          );
        },
        size: 120,
      },
      {
        accessorKey: "instance",
        header: "Instance",
        cell: (info) => info.getValue(),
        size: 150,
      },
      {
        accessorKey: "torrentCount",
        header: "Torrents",
        cell: (info) => (info.getValue() as number).toLocaleString(),
        size: 100,
      },
      {
        accessorKey: "seedingCount",
        header: "Seeding",
        cell: (info) => (info.getValue() as number).toLocaleString(),
        size: 100,
      },
      {
        accessorKey: "totalSize",
        header: "Total Size",
        cell: (info) => formatBytes(info.getValue() as number),
        size: 120,
      },
      {
        accessorKey: "avgRatio",
        header: "Avg Ratio",
        cell: (info) => (info.getValue() as number).toFixed(2),
        size: 100,
      },
      {
        accessorKey: "avgSeedingTime",
        header: "Avg Seed Time",
        cell: (info) => formatTime(Math.round(info.getValue() as number)),
        size: 140,
      },
      {
        id: "maxRatio",
        header: "Max Ratio",
        accessorFn: (row) => row.seedingConfig.maxRatio,
        cell: (info) => {
          const val = info.getValue() as number;
          return val === -1 ? "Disabled" : val.toFixed(2);
        },
        size: 100,
      },
      {
        id: "maxTime",
        header: "Max Time",
        accessorFn: (row) => row.seedingConfig.maxTime,
        cell: (info) => {
          const val = info.getValue() as number;
          return val === -1 ? "Disabled" : formatTime(val);
        },
        size: 120,
      },
      {
        id: "removeMode",
        header: "Remove Mode",
        accessorFn: (row) => row.seedingConfig.removeMode,
        cell: (info) => getRemoveModeText(info.getValue() as number),
        size: 150,
      },
    ],
    []
  );

  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">
          Category overview across all instances
          <br />
          <strong>Categories:</strong> {summary.categoryCount} •{" "}
          <strong>qBit-managed:</strong> {summary.qbitCount} •{" "}
          <strong>Arr-managed:</strong> {summary.arrCount} •{" "}
          <strong>Total Torrents:</strong>{" "}
          {summary.totalTorrents.toLocaleString()} •{" "}
          <strong>Seeding:</strong> {summary.totalSeeding.toLocaleString()} •{" "}
          <strong>Total Size:</strong> {formatBytes(summary.totalSize)}
        </div>
        <button className="btn ghost" onClick={handleRefresh} disabled={loading}>
          {loading && <span className="spinner" />}
          <IconImage src={RefreshIcon} />
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {loading && categories.length === 0 ? (
        <div className="loading">
          <span className="spinner" /> Loading categories…
        </div>
      ) : categories.length === 0 ? (
        <div className="hint">
          No categories found. Configure ManagedCategories in your qBit config sections or
          add Arr instances to see categories.
        </div>
      ) : (
        <StableTable
          data={categories}
          columns={columns}
          getRowKey={(cat) => `${cat.instance}-${cat.category}-${cat.managedBy}`}
        />
      )}
    </div>
  );
}
