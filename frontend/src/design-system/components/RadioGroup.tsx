import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export type RadioOption = {
  value: string;
  label: ReactNode;
  disabled?: boolean;
};

export function RadioGroup({
  legend,
  name,
  value,
  options,
  onChange,
  error,
  disabled,
  layout = "horizontal",
  className,
}: {
  legend: ReactNode;
  name: string;
  value: string;
  options: RadioOption[];
  onChange: (value: string) => void;
  error?: ReactNode;
  disabled?: boolean;
  layout?: "horizontal" | "vertical";
  className?: string;
}) {
  return (
    <fieldset className={cx("ds-choice-group", className)} disabled={disabled}>
      <legend>{legend}</legend>
      <div
        className={cx(
          "ds-choice-group__items",
          layout === "horizontal" && "ds-choice-group__items--horizontal",
        )}
      >
        {options.map((option) => (
          <label key={option.value} className="ds-check">
            <input
              type="radio"
              className="ds-check__input"
              name={name}
              value={option.value}
              checked={value === option.value}
              disabled={option.disabled}
              onChange={() => onChange(option.value)}
            />
            <span className="ds-check__label">{option.label}</span>
          </label>
        ))}
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
