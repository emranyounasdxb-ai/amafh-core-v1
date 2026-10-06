import { cx } from "../lib/cx";

export type TabItem = {
  id: string;
  label: string;
  disabled?: boolean;
};

export function Tabs({
  items,
  value,
  onChange,
  className,
  label,
}: {
  items: TabItem[];
  value: string;
  onChange: (id: string) => void;
  className?: string;
  label: string;
}) {
  return (
    <div className={cx("ds-tabs", className)} role="tablist" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          className="ds-tabs__tab"
          aria-selected={item.id === value}
          disabled={item.disabled}
          onClick={() => onChange(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
