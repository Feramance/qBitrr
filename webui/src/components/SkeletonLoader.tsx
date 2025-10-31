import type { JSX } from "react";

interface SkeletonLoaderProps {
  type: "table" | "card" | "text";
  rows?: number;
  columns?: number;
}

export function SkeletonLoader({
  type,
  rows = 5,
  columns = 4,
}: SkeletonLoaderProps): JSX.Element {
  if (type === "table") {
    return (
      <div className="skeleton-table">
        <div className="skeleton-table-header">
          {Array.from({ length: columns }).map((_, i) => (
            <div key={i} className="skeleton skeleton-header" />
          ))}
        </div>
        {Array.from({ length: rows }).map((_, rowIdx) => (
          <div key={rowIdx} className="skeleton-table-row">
            {Array.from({ length: columns }).map((_, colIdx) => (
              <div key={colIdx} className="skeleton skeleton-cell" />
            ))}
          </div>
        ))}
      </div>
    );
  }

  if (type === "card") {
    return (
      <div className="skeleton-card">
        <div className="skeleton skeleton-title" />
        <div className="skeleton skeleton-text" />
        <div className="skeleton skeleton-text" />
        <div className="skeleton skeleton-button" />
      </div>
    );
  }

  // Default: text
  return (
    <div className="skeleton-text-group">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton skeleton-text" />
      ))}
    </div>
  );
}
