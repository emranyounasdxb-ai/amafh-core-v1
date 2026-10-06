import { cx } from "../lib/cx";

export type SegmentItem = { id: string; label: string; disabled?: boolean };

export function SegmentedControl({
  items,
  value,
  onChange,
  label,
  className,
}: {
  items: SegmentItem[];
  value: string;
  onChange: (id: string) => void;
  label: string;
  className?: string;
}) {
  return (
    <div
      className={cx("ds-segmented", className)}
      role="radiogroup"
      aria-label={label}
    >
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="radio"
          className="ds-segmented__item"
          aria-checked={item.id === value}
          disabled={item.disabled}
          onClick={() => onChange(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
