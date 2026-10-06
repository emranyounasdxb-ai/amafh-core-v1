import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function PageActions({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cx("ds-page-actions", className)}>{children}</div>;
}
