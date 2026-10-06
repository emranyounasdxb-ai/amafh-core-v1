import type { InputHTMLAttributes, ReactNode } from "react";
import { cx } from "../lib/cx";

export function Checkbox({
  label,
  className,
  ...props
}: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: ReactNode;
}) {
  return (
    <label className={cx("ds-check", className)}>
      <input {...props} type="checkbox" className="ds-check__input" />
      <span className="ds-check__label">{label}</span>
    </label>
  );
}

export function CheckboxGroup({
  legend,
  children,
  error,
  layout = "horizontal",
  className,
}: {
  legend: ReactNode;
  children: ReactNode;
  error?: ReactNode;
  layout?: "horizontal" | "vertical";
  className?: string;
}) {
  return (
    <fieldset className={cx("ds-choice-group", className)}>
      <legend>{legend}</legend>
      <div
        className={cx(
          "ds-choice-group__items",
          layout === "horizontal" && "ds-choice-group__items--horizontal",
        )}
      >
        {children}
      </div>
      <div className="ds-field__support">
        {error ? (
          <p className="ds-field__error" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </fieldset>
  );
}
