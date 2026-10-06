import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function StickyActionBar({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx("ds-sticky-bar", className)}
      role="region"
      aria-label="Page actions"
    >
      {children}
    </div>
  );
}
