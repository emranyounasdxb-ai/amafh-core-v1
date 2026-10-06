import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function KpiCard({
  label,
  value,
  meta,
  accent = "brand",
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  meta?: ReactNode;
  accent?: "brand" | "pink" | "none";
  className?: string;
}) {
  return (
    <article
      className={cx(
        "ds-kpi-card",
        accent !== "none" && "ds-kpi-card--accent",
        className,
      )}
    >
      {accent !== "none" ? (
        <span
          className={cx(
            "ds-kpi-card__mark",
            accent === "pink" && "ds-kpi-card__mark--pink",
          )}
          aria-hidden="true"
        />
      ) : null}
      <div className="ds-kpi-card__label">{label}</div>
      <div className="ds-kpi-card__value ds-numeric">{value}</div>
      {meta ? <div className="ds-kpi-card__meta">{meta}</div> : null}
    </article>
  );
}
