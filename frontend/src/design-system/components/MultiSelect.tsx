import { DropdownSelect } from "./DropdownSelect";
import type { SelectOption } from "./Select";

export function MultiSelect({
  id,
  label,
  options,
  value,
  onChange,
  placeholder,
  compact,
  disabled,
  readOnly,
  invalid,
  loading,
}: {
  id: string;
  label?: string;
  options: SelectOption[];
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  compact?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  invalid?: boolean;
  loading?: boolean;
}) {
  return (
    <DropdownSelect
      id={id}
      label={label}
      options={options}
      value={value}
      onChange={(next) => onChange(Array.isArray(next) ? next : [next])}
      placeholder={placeholder}
      compact={compact}
      disabled={disabled}
      readOnly={readOnly}
      invalid={invalid}
      searchable
      mode="multi"
      loading={loading}
    />
  );
}
