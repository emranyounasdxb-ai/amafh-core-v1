import { Avatar } from "./Avatar";
import { Combobox } from "./Combobox";
import type { SelectOption } from "./Select";

export type PersonOption = {
  value: string;
  name: string;
  subtitle?: string;
  disabled?: boolean;
  src?: string;
};

export function PersonSelect({
  id,
  label = "Person",
  people,
  value,
  onChange,
  compact,
  disabled,
  readOnly,
  loading,
}: {
  id: string;
  label?: string;
  people: PersonOption[];
  value: string;
  onChange: (value: string) => void;
  compact?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  loading?: boolean;
}) {
  const options: SelectOption[] = people.map((person) => ({
    value: person.value,
    label: person.name,
    description: person.subtitle,
    disabled: person.disabled,
    keywords: [person.name, person.subtitle ?? ""],
    leading: <Avatar name={person.name} src={person.src} size="sm" />,
  }));
  return (
    <Combobox
      id={id}
      label={label}
      options={options}
      value={value}
      onChange={onChange}
      compact={compact}
      disabled={disabled}
      readOnly={readOnly}
      loading={loading}
      placeholder="Search name or role"
    />
  );
}
