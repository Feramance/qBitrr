import { useCallback, useEffect, useMemo, useState } from "react";

import {
  estimateIconGridColumns,
  roundPageSizeToIconGridRows,
} from "../utils/arrIconGrid";

/**
 * Measure `.arr-icon-grid` width and expose {@link roundPageSizeToIconGridRows} when icon mode
 * is active; otherwise pass through base page sizes unchanged (list/table).
 */
export function useArrIconGridPageSize(enabled: boolean): {
  gridRef: (node: HTMLElement | null) => void;
  columnCount: number;
  roundPageSize: (base: number) => number;
} {
  const [gridEl, setGridEl] = useState<HTMLElement | null>(null);
  const [columnCount, setColumnCount] = useState(() =>
    typeof window !== "undefined"
      ? estimateIconGridColumns(window.innerWidth)
      : estimateIconGridColumns(1200),
  );

  const gridRef = useCallback((node: HTMLElement | null) => {
    setGridEl(node);
  }, []);

  useEffect(() => {
    if (!enabled || !gridEl) {
      return;
    }
    const measure = (width: number) => {
      setColumnCount(estimateIconGridColumns(width));
    };
    measure(gridEl.getBoundingClientRect().width);
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      measure(w);
    });
    ro.observe(gridEl);
    return () => {
      ro.disconnect();
    };
  }, [enabled, gridEl]);

  const roundPageSize = useMemo(() => {
    if (!enabled) {
      return (base: number) => base;
    }
    return (base: number) => roundPageSizeToIconGridRows(base, columnCount);
  }, [enabled, columnCount]);

  return { gridRef, columnCount, roundPageSize };
}
