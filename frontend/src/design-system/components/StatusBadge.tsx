import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export type StatusTone =
  "success" | "warning" | "danger" | "error" | "info" | "neutral" | "brand";

export function StatusBadge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: StatusTone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cx("ds-status-badge", `ds-status-badge--${tone}`, className)}
    >
      {children}
    </span>
  );
}
