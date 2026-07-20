import { useCallback, useEffect, useState } from "react";

import {
  estimateIconGridColumns,
  roundPageSizeToIconGridRows,
} from "../utils/arrIconGrid";

/**
 * Measure `.arr-icon-grid` width and expose {@link roundPageSizeToIconGridRows} when icon mode
 * is active; otherwise pass through base page sizes unchanged (list/table).
 *
 * Ignores zero-width measures (keep-alive tabs use `display:none` / `hidden`) and remeasures
 * when `panelActive` becomes true so column counts recover after unhide.
 */
export function useArrIconGridPageSize(
  enabled: boolean,
  panelActive: boolean = true,
): {
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
    if (!enabled || !gridEl || !panelActive) {
      return;
    }
    const measure = (width: number) => {
      // Keep-alive inactive panels report 0 width — do not collapse column count.
      if (width <= 0) {
        return;
      }
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
  }, [enabled, gridEl, panelActive]);

  const roundPageSize = useCallback(
    (base: number): number => {
      if (!enabled) {
        return base;
      }
      return roundPageSizeToIconGridRows(base, columnCount);
    },
    [enabled, columnCount],
  );

  return { gridRef, columnCount, roundPageSize };
}
