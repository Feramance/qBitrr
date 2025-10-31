import { type JSX, useState, useCallback } from "react";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  loading?: boolean;
  itemsLabel?: string;
}

export function Pagination({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  loading = false,
  itemsLabel = "items",
}: PaginationProps): JSX.Element {
  const [jumpPage, setJumpPage] = useState("");

  const handleJump = useCallback(() => {
    const page = parseInt(jumpPage, 10);
    if (!isNaN(page) && page >= 1 && page <= totalPages) {
      onPageChange(page - 1);
      setJumpPage("");
    }
  }, [jumpPage, totalPages, onPageChange]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        handleJump();
      }
    },
    [handleJump]
  );

  if (totalPages <= 0) {
    return <div />;
  }

  return (
    <div className="pagination">
      <div className="pagination-info">
        Page {currentPage + 1} of {totalPages} ({totalItems.toLocaleString()}{" "}
        {itemsLabel} · page size {pageSize})
      </div>
      <div className="inline">
        <button
          className="btn"
          onClick={() => onPageChange(0)}
          disabled={currentPage === 0 || loading}
          title="First page"
        >
          ««
        </button>
        <button
          className="btn"
          onClick={() => onPageChange(Math.max(0, currentPage - 1))}
          disabled={currentPage === 0 || loading}
          title="Previous page"
        >
          « Prev
        </button>

        <input
          type="number"
          className="pagination-jump"
          placeholder="Page"
          value={jumpPage}
          onChange={(e) => setJumpPage(e.target.value)}
          onKeyDown={handleKeyDown}
          min={1}
          max={totalPages}
          disabled={loading}
        />
        <button
          className="btn"
          onClick={handleJump}
          disabled={loading || !jumpPage}
          title="Jump to page"
        >
          Go
        </button>

        <button
          className="btn"
          onClick={() => onPageChange(Math.min(totalPages - 1, currentPage + 1))}
          disabled={currentPage >= totalPages - 1 || loading}
          title="Next page"
        >
          Next »
        </button>
        <button
          className="btn"
          onClick={() => onPageChange(totalPages - 1)}
          disabled={currentPage >= totalPages - 1 || loading}
          title="Last page"
        >
          »»
        </button>
      </div>
    </div>
  );
}
