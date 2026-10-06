import { DropdownSelect } from "./DropdownSelect";
import type { SelectOption } from "./Select";

export function TreeSelect({
  id,
  label,
  options,
  value,
  onChange,
  compact,
  disabled,
  invalid,
}: {
  id: string;
  label?: string;
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  compact?: boolean;
  disabled?: boolean;
  invalid?: boolean;
}) {
  return (
    <DropdownSelect
      id={id}
      label={label}
      options={options}
      value={value}
      onChange={(next) => onChange(String(next))}
      compact={compact}
      disabled={disabled}
      invalid={invalid}
      searchable
      placeholder="Search hierarchy"
    />
  );
}

export function CheckboxDropdown({
  id,
  label,
  options,
  value,
  onChange,
  compact,
}: {
  id: string;
  label?: string;
  options: SelectOption[];
  value: string[];
  onChange: (value: string[]) => void;
  compact?: boolean;
}) {
  return (
    <DropdownSelect
      id={id}
      label={label}
      options={options}
      value={value}
      onChange={(next) => onChange(Array.isArray(next) ? next : [next])}
      compact={compact}
      mode="checkbox"
    />
  );
}

export function RadioDropdown({
  id,
  label,
  options,
  value,
  onChange,
  compact,
}: {
  id: string;
  label?: string;
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  compact?: boolean;
}) {
  return (
    <DropdownSelect
      id={id}
      label={label}
      options={options}
      value={value}
      onChange={(next) => onChange(String(next))}
      compact={compact}
      mode="radio"
    />
  );
}
