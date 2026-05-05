/** Must stay aligned with `.arr-icon-grid` in `styles.css`. */
export const ARR_ICON_GRID_MIN_TRACK_PX = 140;
export const ARR_ICON_GRID_GAP_PX = 12;

/**
 * Estimate how many columns `repeat(auto-fill, minmax(140px, 1fr))` fits in ``widthPx``.
 */
export function estimateIconGridColumns(containerWidthPx: number): number {
  const w = Math.max(0, containerWidthPx);
  const minTrack = ARR_ICON_GRID_MIN_TRACK_PX;
  const gap = ARR_ICON_GRID_GAP_PX;
  const stride = minTrack + gap;
  if (stride <= 0) {
    return 1;
  }
  return Math.max(1, Math.floor((w + gap) / stride));
}

/**
 * Round ``desired`` to the nearest multiple of ``columns`` (at least one full row).
 */
export function roundPageSizeToIconGridRows(desired: number, columns: number): number {
  if (!Number.isFinite(desired) || desired < 1 || !Number.isFinite(columns) || columns < 1) {
    return desired;
  }
  const rounded = Math.round(desired / columns) * columns;
  return Math.max(columns, rounded);
}
