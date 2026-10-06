import { cx } from "../lib/cx";
import { Button } from "./Button";

export function Pagination({
  page,
  pageCount,
  onPageChange,
  pageSize,
  pageSizeOptions = [25, 50, 100],
  onPageSizeChange,
  className,
}: {
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
  pageSize?: number;
  pageSizeOptions?: number[];
  onPageSizeChange?: (size: number) => void;
  className?: string;
}) {
  const pages = Array.from({ length: pageCount }, (_, index) => index + 1);
  return (
    <div className={cx("ds-pagination", className)}>
      <div className="ds-pagination__pages">
        <Button
          variant="ghost"
          size="compact"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </Button>
        {pages.map((item) => (
          <button
            key={item}
            type="button"
            className="ds-pagination__page"
            aria-current={item === page ? "page" : undefined}
            onClick={() => onPageChange(item)}
          >
            {item}
          </button>
        ))}
        <Button
          variant="ghost"
          size="compact"
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
      {onPageSizeChange && pageSize ? (
        <label className="ds-cluster">
          <span className="ds-field__label">Rows</span>
          <select
            className="ds-select ds-select--compact"
            value={pageSize}
            aria-label="Rows per page"
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </div>
  );
}
