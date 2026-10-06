import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function InfoGrid({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className="ds-info-grid-wrap">
      <div className={cx("ds-info-grid", className)}>{children}</div>
    </div>
  );
}
