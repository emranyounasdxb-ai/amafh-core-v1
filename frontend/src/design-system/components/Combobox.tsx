import { DropdownSelect } from "./DropdownSelect";
import type { SelectOption } from "./Select";

export function Combobox({
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
  unavailable,
  emptyLabel,
  query,
  onQueryChange,
  creatable,
  onCreate,
  required,
}: {
  id: string;
  label?: string;
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  compact?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  invalid?: boolean;
  loading?: boolean;
  unavailable?: boolean;
  emptyLabel?: string;
  query?: string;
  onQueryChange?: (value: string) => void;
  creatable?: boolean;
  onCreate?: (query: string) => void;
  required?: boolean;
}) {
  return (
    <DropdownSelect
      id={id}
      label={label}
      options={options}
      value={value}
      onChange={(next) => onChange(String(next))}
      placeholder={placeholder}
      compact={compact}
      disabled={disabled}
      readOnly={readOnly}
      invalid={invalid}
      searchable
      loading={loading}
      unavailable={unavailable}
      emptyLabel={emptyLabel}
      query={query}
      onQueryChange={onQueryChange}
      creatable={creatable}
      onCreate={onCreate}
      required={required}
    />
  );
}
