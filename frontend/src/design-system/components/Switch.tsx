import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function Switch({
  id,
  label,
  checked,
  onChange,
  disabled,
  className,
}: {
  id?: string;
  label: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <label className={cx("ds-switch", className)}>
      <input
        id={id}
        type="checkbox"
        role="switch"
        className="ds-switch__input"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="ds-switch__track" aria-hidden="true" />
      <span className="ds-switch__label">{label}</span>
    </label>
  );
}
