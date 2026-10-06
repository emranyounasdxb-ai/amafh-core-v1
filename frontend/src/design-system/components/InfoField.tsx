import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function InfoField({
  label,
  value,
  numeric = false,
  className,
}: {
  label: ReactNode;
  value: ReactNode;
  numeric?: boolean;
  className?: string;
}) {
  return (
    <div className={cx("ds-info-field", className)}>
      <div className="ds-info-field__label">{label}</div>
      <div className={cx("ds-info-field__value", numeric && "ds-numeric")}>
        {value}
      </div>
    </div>
  );
}
