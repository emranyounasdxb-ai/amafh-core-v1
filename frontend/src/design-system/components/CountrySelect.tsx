import type { ComponentType } from "react";
import * as countryFlags from "country-flag-icons/react/3x2";
import { countryOptions, countryRecords, nationalityOptions } from "../data/countries";
import { Combobox } from "./Combobox";
import { TruncatedText, EmptyValue } from "./Display";
import type { SelectOption } from "./Select";

type FlagSvg = ComponentType<{ className?: string; title?: string }>;

const nationalityRecords = new Map(
  countryRecords.flatMap((record) =>
    [record.code, record.name, record.nationality].map(
      (value) => [value.toLocaleLowerCase("en"), record] as const,
    ),
  ),
);

/** Resolve the actual nationality value, never infer a country from a name. */
export function NationalityValue({ value }: { value?: string | null }) {
  const text = value?.trim();
  if (!text) return <EmptyValue />;
  const record = nationalityRecords.get(text.toLocaleLowerCase("en"));
  const Flag = record
    ? (countryFlags as Record<string, FlagSvg | undefined>)[record.code]
    : undefined;
  return (
    <span className="ds-nationality-value">
      {Flag ? <Flag className="ds-flag" title={record!.name} /> : null}
      <TruncatedText value={record?.nationality ?? text} />
    </span>
  );
}

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
  excludedCodes = [],
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  compact?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  invalid?: boolean;
  label?: string;
  excludedCodes?: readonly string[];
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
      options={withFlag(nationalityOptions().filter((option) => !excludedCodes.includes(option.value)))}
      placeholder="Search country"
    />
  );
}
