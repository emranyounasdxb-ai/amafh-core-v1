import type { InputHTMLAttributes, ReactNode } from "react";
import { TextInput } from "./TextInput";
import { UaeDirhamSymbol } from "./UaeDirhamSymbol";

export function NumberInput({
  prefix,
  suffix,
  ...props
}: Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "prefix"> & {
  compact?: boolean;
  prefix?: ReactNode;
  suffix?: ReactNode;
  invalid?: boolean;
}) {
  return (
    <TextInput
      {...props}
      type="text"
      inputMode="decimal"
      prefix={prefix}
      suffix={suffix}
    />
  );
}

export function CurrencyInput({
  currency = "AED",
  ...props
}: Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "prefix"> & {
  compact?: boolean;
  currency?: string;
  invalid?: boolean;
}) {
  return (
    <NumberInput
      {...props}
      prefix={currency === "AED" ? <UaeDirhamSymbol /> : currency}
      aria-label={props["aria-label"] ?? `Amount in ${currency}`}
    />
  );
}
