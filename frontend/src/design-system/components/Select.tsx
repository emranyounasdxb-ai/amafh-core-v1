import type { ReactNode } from "react";

export type SelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
  group?: string;
  description?: string;
  keywords?: string[];
  children?: SelectOption[];
  leading?: ReactNode;
};

export function optionMatches(option: SelectOption, query: string) {
  const term = query.trim().toLowerCase();
  if (!term) return true;
  return [
    option.label,
    option.description,
    option.value,
    ...(option.keywords ?? []),
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(term));
}

export function flattenOptions(options: SelectOption[]): SelectOption[] {
  return options.flatMap((option) => [
    option,
    ...(option.children ? flattenOptions(option.children) : []),
  ]);
}
