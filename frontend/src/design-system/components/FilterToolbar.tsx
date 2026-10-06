import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function FilterToolbar({
  children,
  className,
  label,
}: {
  children: ReactNode;
  className?: string;
  label?: string;
}) {
  return (
    <div
      className={cx("ds-filter-toolbar", className)}
      role="search"
      aria-label={label}
    >
      {children}
    </div>
  );
}

export function FilterToolbarItem({
  label,
  htmlFor,
  children,
  className,
  labeled = true,
}: {
  label?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
  className?: string;
  labeled?: boolean;
}) {
  return (
    <div className={cx("ds-filter-toolbar__item", className)}>
      {labeled && label ? (
        <label className="ds-field__label" htmlFor={htmlFor}>
          {label}
        </label>
      ) : (
        <span className="ds-field__label" aria-hidden="true">
          {"\u00a0"}
        </span>
      )}
      <div className="ds-filter-toolbar__control">{children}</div>
    </div>
  );
}
