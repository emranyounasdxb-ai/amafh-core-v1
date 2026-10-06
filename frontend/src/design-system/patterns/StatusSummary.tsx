import { StatusBadge, type StatusTone } from "../components/StatusBadge";

export type StatusCount = { label: string; count: number; tone: StatusTone };

export function StatusSummary({ items }: { items: StatusCount[] }) {
  return (
    <div className="ds-status-summary">
      {items.map((item) => (
        <StatusBadge key={item.label} tone={item.tone}>
          {item.label} {item.count}
        </StatusBadge>
      ))}
    </div>
  );
}
