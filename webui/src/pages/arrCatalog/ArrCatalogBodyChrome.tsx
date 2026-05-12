import { type JSX, type ReactNode } from "react";
import { IconImage } from "../../components/IconImage";
import RefreshIcon from "../../icons/refresh-arrow.svg";

interface ArrCatalogBodyChromeProps {
  /** Top-row hint / counts — already includes "(updated …)" tail when relevant. */
  readonly summaryLine: ReactNode;
  /** Refresh handler wired to the toolbar button. */
  readonly onRefresh: () => void;
  /** True while a load is in flight (disables the refresh button). */
  readonly loading: boolean;
  /** Loading spinner copy (e.g. `"Loading Radarr library…"`). */
  readonly loadingHint: string;
  /** Body content: list table, icon grid, or empty-state copy. */
  readonly children: ReactNode;
  /** Optional pagination footer below the body. */
  readonly footer?: ReactNode;
}

/**
 * Shared "body chrome" — the summary header row + refresh button + spinner + body
 * slot used by all three Arrs.  Keeps the per-Arr render slot focused on the parts
 * that genuinely differ (counts copy, columns, tile content).
 */
export function ArrCatalogBodyChrome({
  summaryLine,
  onRefresh,
  loading,
  loadingHint,
  children,
  footer,
}: ArrCatalogBodyChromeProps): JSX.Element {
  return (
    <div className="stack animate-fade-in">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="hint">{summaryLine}</div>
        <button
          className="btn ghost"
          type="button"
          onClick={onRefresh}
          disabled={loading}
        >
          <IconImage src={RefreshIcon} />
          Refresh
        </button>
      </div>
      {loading ? (
        <div className="loading">
          <span className="spinner" /> {loadingHint}
        </div>
      ) : (
        children
      )}
      {footer}
    </div>
  );
}

interface ArrCatalogPaginationProps {
  readonly page: number;
  readonly totalPages: number;
  readonly total: number;
  readonly itemNoun: string;
  readonly pageSize: number;
  readonly loading: boolean;
  readonly onPageChange: (page: number) => void;
}

/**
 * Shared pagination footer with Prev / Next buttons + "Page X of Y (N items · page size Z)".
 */
export function ArrCatalogPagination({
  page,
  totalPages,
  total,
  itemNoun,
  pageSize,
  loading,
  onPageChange,
}: ArrCatalogPaginationProps): JSX.Element {
  return (
    <div className="pagination">
      <div>
        Page {page + 1} of {totalPages} ({total.toLocaleString()} {itemNoun} ·
        page size {pageSize})
      </div>
      <div className="inline">
        <button
          className="btn"
          type="button"
          onClick={() => onPageChange(Math.max(0, page - 1))}
          disabled={page === 0 || loading}
        >
          Prev
        </button>
        <button
          className="btn"
          type="button"
          onClick={() =>
            onPageChange(Math.min(totalPages - 1, page + 1))
          }
          disabled={page >= totalPages - 1 || loading}
        >
          Next
        </button>
      </div>
    </div>
  );
}
