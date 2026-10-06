import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function PageTitle({
  title,
  subtitle,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("ds-page-title", className)}>
      <h1 className="ds-page-title__heading">{title}</h1>
      {subtitle ? <p className="ds-page-title__subtitle">{subtitle}</p> : null}
    </div>
  );
}
