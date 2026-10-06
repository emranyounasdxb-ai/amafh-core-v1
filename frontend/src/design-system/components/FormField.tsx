import type { ReactNode } from "react";
import { cx } from "../lib/cx";

export function FormField({
  label,
  htmlFor,
  required,
  optional,
  hint,
  error,
  span,
  children,
  className,
}: {
  label: ReactNode;
  htmlFor?: string;
  required?: boolean;
  optional?: boolean;
  hint?: ReactNode;
  error?: ReactNode;
  span?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const hintId = htmlFor ? `${htmlFor}-hint` : undefined;
  const errorId = htmlFor ? `${htmlFor}-error` : undefined;
  return (
    <div className={cx("ds-field", span && "ds-field--span", className)}>
      <label className="ds-field__label" htmlFor={htmlFor}>
        {label}
        {required ? (
          <span className="ds-field__required" aria-hidden="true">
            {" "}
            *
          </span>
        ) : optional ? (
          <span className="ds-field__optional"> Optional</span>
        ) : null}
      </label>
      <div className="ds-field__control">{children}</div>
      <div className="ds-field__support">
        {error ? (
          <p className="ds-field__error" id={errorId} role="alert">
            {error}
          </p>
        ) : hint ? (
          <p className="ds-field__hint" id={hintId}>
            {hint}
          </p>
        ) : null}
      </div>
    </div>
  );
}
