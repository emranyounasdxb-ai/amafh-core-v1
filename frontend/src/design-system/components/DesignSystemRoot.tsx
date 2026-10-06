import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function DesignSystemRoot({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cx("ds-root", className)}>{children}</div>;
}
