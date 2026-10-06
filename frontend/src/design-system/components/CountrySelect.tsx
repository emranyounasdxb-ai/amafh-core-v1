import type { ComponentType } from "react";
import * as countryFlags from "country-flag-icons/react/3x2";
import { countryOptions, nationalityOptions } from "../data/countries";
import { Combobox } from "./Combobox";
import type { SelectOption } from "./Select";

type FlagSvg = ComponentType<{ className?: string; title?: string }>;

function withFlag(options: SelectOption[]): SelectOption[] {
  const flags = countryFlags as Record<string, FlagSvg | undefined>;
  return options.map((option) => {
    const Flag = flags[option.value];
    return {
      ...option,
      leading: Flag ? (
        <Flag className="ds-flag" title={option.value} />
      ) : (
        <span className="ds-flag-fallback">{option.value}</span>
      ),
    };
  });
}

export function CountrySelect({
  id,
  value,
  onChange,
  compact,
  disabled,
  readOnly,
  invalid,
  required,
  label = "Country",
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  compact?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  invalid?: boolean;
  required?: boolean;
  label?: string;
}) {
  return (
    <Combobox
      id={id}
      label={label}
      value={value}
      onChange={onChange}
      compact={compact}
      disabled={disabled}
      readOnly={readOnly}
      invalid={invalid}
      required={required}
      options={withFlag(countryOptions())}
      placeholder="Search country or ISO code"
    />
  );
}

export function NationalitySelect({
  id,
  value,
  onChange,
  compact,
  disabled,
  readOnly,
  invalid,
  label = "Nationality",
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  compact?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  invalid?: boolean;
  label?: string;
}) {
  return (
    <Combobox
      id={id}
      label={label}
      value={value}
      onChange={onChange}
      compact={compact}
      disabled={disabled}
      readOnly={readOnly}
      invalid={invalid}
      options={withFlag(nationalityOptions())}
      placeholder="Search nationality or ISO code"
    />
  );
}
