import type { InputHTMLAttributes } from "react";
import { DsIcon } from "../icons";
import { cx } from "../lib/cx";

export type PhonePrefixOption = { value: string; label: string };

export function PhoneInput({
  id,
  prefix,
  prefixOptions,
  onPrefixChange,
  compact,
  invalid,
  className,
  ...props
}: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  prefix: string;
  prefixOptions: PhonePrefixOption[];
  onPrefixChange: (value: string) => void;
  compact?: boolean;
  invalid?: boolean;
}) {
  return (
    <div
      className={cx(
        "ds-phone",
        compact && "ds-phone--compact",
        invalid && "ds-phone--invalid",
        props.disabled && "ds-phone--disabled",
        props.readOnly && "ds-phone--readonly",
        className,
      )}
    >
      <div className="ds-phone__code">
        <select
          className="ds-phone__prefix"
          aria-label="Country calling code"
          value={prefix}
          disabled={props.disabled || props.readOnly}
          onChange={(event) => onPrefixChange(event.target.value)}
        >
          {prefixOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <DsIcon name="expand" size={14} />
      </div>
      <span className="ds-phone__divider" aria-hidden="true" />
      <input
        {...props}
        id={id}
        type="tel"
        inputMode="tel"
        aria-invalid={invalid || undefined}
        className="ds-phone__number"
      />
    </div>
  );
}
