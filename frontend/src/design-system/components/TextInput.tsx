import type { InputHTMLAttributes, ReactNode } from "react";
import { cx } from "../lib/cx";

export function TextInput({
  compact,
  prefix,
  suffix,
  invalid,
  className,
  ...props
}: Omit<InputHTMLAttributes<HTMLInputElement>, "prefix"> & {
  compact?: boolean;
  prefix?: ReactNode;
  suffix?: ReactNode;
  invalid?: boolean;
}) {
  const input = (
    <input
      {...props}
      aria-invalid={invalid || props["aria-invalid"]}
      className={cx(
        "ds-input",
        compact && "ds-input--compact",
        Boolean(prefix || suffix) && "ds-input--bare",
        className,
      )}
    />
  );
  if (!prefix && !suffix) return input;
  return (
    <div
      className={cx(
        "ds-input-affix",
        compact && "ds-input-affix--compact",
        (invalid || props["aria-invalid"]) && "ds-input-affix--invalid",
        props.disabled && "ds-input-affix--disabled",
        props.readOnly && "ds-input-affix--readonly",
      )}
    >
      {prefix ? <span className="ds-input-affix__addon">{prefix}</span> : null}
      {input}
      {suffix ? <span className="ds-input-affix__addon">{suffix}</span> : null}
    </div>
  );
}
