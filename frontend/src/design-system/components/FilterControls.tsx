import type { ButtonHTMLAttributes, ReactNode } from "react";
import { DsIcon, type DsIconName } from "../icons";
import { cx } from "../lib/cx";
import { Button, type ButtonSize } from "./Button";
import { DropdownSelect } from "./DropdownSelect";
import { FilterToolbarItem } from "./FilterToolbar";
import { Popover } from "./Popover";

export type AppliedFilter = {
  id: string;
  label: string;
  field?: string;
  value?: string;
  onRemove?: () => void;
};

export function FilterButton({
  count = 0,
  onClick,
  children = "Filters",
  disabled,
  loading,
  size = "compact",
  className,
  ...props
}: {
  count?: number;
  onClick?: () => void;
  children?: ReactNode;
  disabled?: boolean;
  loading?: boolean;
  size?: ButtonSize;
  className?: string;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children">) {
  return (
    <Button
      {...props}
      variant="secondary"
      size={size}
      disabled={disabled}
      loading={loading}
      onClick={onClick}
      className={cx(
        "ds-filter-button",
        count > 0 && "ds-filter-button--active",
        className,
      )}
      aria-pressed={props["aria-pressed"] ?? (count > 0 || undefined)}
    >
      <DsIcon name="filter" size={16} />
      {children}
      {count > 0 ? (
        <span className="ds-filter-count" aria-label={`${count} active filters`}>
          {count}
        </span>
      ) : null}
    </Button>
  );
}

export function FilterPopover({
  count = 0,
  children,
  onApply,
  onReset,
  disabled,
  loading,
}: {
  count?: number;
  children: ReactNode;
  onApply?: () => void;
  onReset?: () => void;
  disabled?: boolean;
  loading?: boolean;
}) {
  if (disabled || loading) {
    return (
      <FilterButton count={count} disabled={disabled} loading={loading} />
    );
  }
  return (
    <Popover
      label="Filters"
      placement="auto"
      className="ds-filter-panel"
      lockHeight={false}
      trigger={<FilterButton count={count} />}
    >
      <div className="ds-filter-popover">
        {children}
        <div className="ds-filter-popover__actions">
          {onReset ? (
            <Button variant="ghost" size="compact" onClick={onReset}>
              Reset
            </Button>
          ) : null}
          {onApply ? (
            <Button size="compact" onClick={onApply}>
              Apply
            </Button>
          ) : null}
        </div>
      </div>
    </Popover>
  );
}

function chipText(item: Pick<AppliedFilter, "label" | "field" | "value">) {
  if (item.field && item.value) return `${item.field}: ${item.value}`;
  return String(item.label);
}

export function FilterChip({
  label,
  field,
  value,
  onRemove,
}: {
  label: ReactNode;
  field?: string;
  value?: string;
  onRemove?: () => void;
}) {
  const text = chipText({ label: String(label), field, value });
  return (
    <span className="ds-chip" title={text}>
      <span className="ds-chip__text">
        {field && value ? (
          <>
            <span className="ds-chip__field">{field}:</span> {value}
          </>
        ) : (
          label
        )}
      </span>
      {onRemove ? (
        <button
          type="button"
          aria-label={`Remove ${text}`}
          onClick={onRemove}
        >
          <DsIcon name="close" size={14} />
        </button>
      ) : null}
    </span>
  );
}

export function FilterChipGroup({
  items,
  className,
}: {
  items: AppliedFilter[];
  className?: string;
}) {
  if (!items.length) return null;
  return (
    <div className={cx("ds-chip-row", className)}>
      {items.map((item) => (
        <FilterChip
          key={item.id}
          label={item.label}
          field={item.field}
          value={item.value}
          onRemove={item.onRemove}
        />
      ))}
    </div>
  );
}

export function AppliedFilterSummary({
  items,
  onClear,
}: {
  items: AppliedFilter[];
  onClear?: () => void;
}) {
  if (!items.length) return null;
  return (
    <div className="ds-filter-summary">
      <FilterChipGroup items={items} />
      {onClear ? (
        <button
          type="button"
          className="ds-filter-summary__clear"
          onClick={onClear}
        >
          Clear all
        </button>
      ) : null}
    </div>
  );
}

export function SortControl({
  id,
  value,
  options,
  onChange,
  label = "Sort",
  direction,
  showIcon = true,
  disabled,
  loading,
  className,
}: {
  id: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  label?: string;
  direction?: "asc" | "desc";
  showIcon?: boolean;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}) {
  const iconName: DsIconName =
    direction === "asc" ? "sortAsc" : direction === "desc" ? "sortDesc" : "sort";
  const selected = options.find((option) => option.value === value)?.label;
  return (
    <FilterToolbarItem
      label={label}
      htmlFor={id}
      className={cx("ds-filter-toolbar__item--sort", className)}
    >
      <div title={selected && selected.length > 18 ? selected : undefined}>
        <DropdownSelect
          id={id}
          label={label}
          compact
          clearable={false}
          value={value}
          options={options}
          disabled={disabled}
          loading={loading}
          onChange={(next) => onChange(String(next))}
          leading={
            showIcon ? (
              <span className="ds-combo__leading" aria-hidden="true">
                <DsIcon name={iconName} size={16} />
              </span>
            ) : undefined
          }
        />
      </div>
    </FilterToolbarItem>
  );
}
