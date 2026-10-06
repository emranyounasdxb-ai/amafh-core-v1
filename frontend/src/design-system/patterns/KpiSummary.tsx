import type { ReactNode } from "react";
import { KpiCard } from "../components/KpiCard";

export type KpiItem = {
  id: string;
  label: string;
  value: ReactNode;
  meta?: string;
  accent?: "brand" | "pink" | "none";
};

export function KpiSummary({
  items,
  compact,
}: {
  items: KpiItem[];
  compact?: boolean;
}) {
  return (
    <div className="ds-kpi-summary-wrap">
      <div
        className={
          compact ? "ds-kpi-summary ds-kpi-summary--compact" : "ds-kpi-summary"
        }
      >
        {items.map((item) => (
          <KpiCard
            key={item.id}
            label={item.label}
            value={item.value}
            meta={item.meta}
            accent={item.accent}
          />
        ))}
      </div>
    </div>
  );
}
