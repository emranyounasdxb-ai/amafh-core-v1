import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "../lib/cx";
import { Tooltip } from "./Tooltip";

export function IconButton({
  label,
  variant = "secondary",
  size = "standard",
  loading = false,
  children,
  className,
  disabled,
  type = "button",
  tooltip = true,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  variant?: "primary" | "secondary" | "ghost" | "danger" | "success";
  size?: "standard" | "compact" | "large";
  loading?: boolean;
  children: ReactNode;
  tooltip?: boolean;
}) {
  const button = (
    <button
      {...props}
      type={type}
      className={cx(
        "ds-icon-button",
        variant !== "primary" && `ds-icon-button--${variant}`,
        size !== "standard" && `ds-icon-button--${size}`,
        className,
      )}
      aria-label={label}
      title={tooltip ? undefined : label}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading ? <span className="ds-spinner" aria-hidden="true" /> : children}
    </button>
  );
  if (!tooltip) return button;
  return (
    <Tooltip content={label}>
      <span className="ds-icon-hit">{button}</span>
    </Tooltip>
  );
}
