import type { ReactNode } from "react";
import { cx } from "../lib/cx";
import { SectionHeader } from "./SectionHeader";

export function SectionCard({
  title,
  description,
  actions,
  children,
  className,
  id,
  compact = false,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
  compact?: boolean;
}) {
  return (
    <section
      id={id}
      className={cx(
        "ds-section-card",
        compact && "ds-section-card--compact",
        className,
      )}
    >
      {title ? (
        <SectionHeader
          title={title}
          description={description}
          actions={actions}
        />
      ) : null}
      {children}
    </section>
  );
}
