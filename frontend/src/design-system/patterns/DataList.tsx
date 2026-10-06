import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function FilterCard({
  id,
  label,
  children,
  className,
}: {
  id?: string;
  label?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      id={id}
      className={cx("ds-filter-card", className)}
      aria-label={label}
    >
      {children}
    </section>
  );
}

export function RecordCount({ count }: { count: number }) {
  return (
    <p className="ds-record-count">{`${count} ${count === 1 ? "record" : "records"}`}</p>
  );
}
