import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function SectionHeader({
  title,
  description,
  actions,
  className,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("ds-section-header", className)}>
      <div className="ds-section-header__copy">
        {title ? <h2 className="ds-section-header__title">{title}</h2> : null}
        {description ? (
          <p className="ds-section-header__description">{description}</p>
        ) : null}
      </div>
      {actions}
    </div>
  );
}
