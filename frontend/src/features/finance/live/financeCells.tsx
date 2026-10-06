import {
  DateRangePicker,
  DropdownSelect,
  EmptyValue,
  FilterToolbarItem,
  MonetaryAmount,
  TruncatedText,
  formatFullNumber,
  type SelectOption,
} from "../../../design-system";
import styles from "./FinancePage.module.css";

export function Text({ value }: { value: string | null | undefined }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

export function Points({ value }: { value: number | null | undefined }) {
  return typeof value === "number" ? (
    <span className="ds-numeric">{formatFullNumber(value)}</span>
  ) : (
    <EmptyValue />
  );
}

export function PfSlab({
  min,
  max,
}: {
  min: string | null | undefined;
  max: string | null | undefined;
}) {
  if (min == null && max == null) return <EmptyValue />;
  return (
    <span className={styles.slab}>
      <MonetaryAmount compact={false} value={min} align="start" />
      <span aria-hidden="true">–</span>
      <MonetaryAmount compact={false} value={max} align="start" />
    </span>
  );
}

export function SelectFilter({
  id,
  label,
  placeholder,
  value,
  options,
  loading,
  onChange,
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  options: SelectOption[];
  loading?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <FilterToolbarItem
      label={label}
      htmlFor={id}
      className="ds-filter-toolbar__item--quick"
    >
      <DropdownSelect
        id={id}
        label={label}
        compact
        clearable
        placeholder={placeholder}
        value={value}
        options={options}
        loading={loading}
        onChange={(next) =>
          onChange(Array.isArray(next) ? (next[0] ?? "") : next)
        }
      />
    </FilterToolbarItem>
  );
}

export function RangeFilter({
  id,
  label,
  start,
  end,
  onChange,
}: {
  id: string;
  label: string;
  start: string;
  end: string;
  onChange: (start: string, end: string) => void;
}) {
  return (
    <FilterToolbarItem label={label} htmlFor={id} className={styles.rangeControl}>
      <DateRangePicker
        id={id}
        compact
        compactRangeLabel
        value={{ start, end }}
        onChange={(next) => onChange(next.start, next.end)}
      />
    </FilterToolbarItem>
  );
}