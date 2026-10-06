import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export type FormColumns = 1 | 2 | 3;

export function FormLayout({
  columns = 2,
  children,
  className,
}: {
  columns?: FormColumns;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className="ds-form-layout-wrap">
      <div
        className={cx("ds-form-layout", `ds-form-layout--${columns}`, className)}
      >
        {children}
      </div>
    </div>
  );
}

export function FormRow({
  columns,
  children,
  className,
}: {
  columns?: FormColumns;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className="ds-form-layout-wrap">
      <div
        className={cx(
          "ds-form-row",
          columns && `ds-form-row--${columns}`,
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
}

export function FormActions({
  children,
  sticky = false,
  align = "end",
  className,
}: {
  children: ReactNode;
  sticky?: boolean;
  align?: "start" | "end";
  className?: string;
}) {
  return (
    <div
      className={cx(
        "ds-form-actions",
        sticky && "ds-form-actions--sticky",
        align === "start" && "ds-form-actions--start",
        className,
      )}
    >
      {children}
    </div>
  );
}
