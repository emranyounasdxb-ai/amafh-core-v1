import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "../lib/cx";

export type ButtonVariant =
  "primary" | "secondary" | "subtle" | "ghost" | "danger" | "success";
export type ButtonSize = "standard" | "compact" | "large";

export function Button({
  variant = "primary",
  size = "standard",
  loading = false,
  children,
  className,
  disabled,
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      {...props}
      type={type}
      className={cx(
        "ds-button",
        variant !== "primary" && `ds-button--${variant}`,
        size !== "standard" && `ds-button--${size}`,
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading ? <span className="ds-spinner" aria-hidden="true" /> : null}
      <span className="ds-button__label">{children}</span>
    </button>
  );
}
