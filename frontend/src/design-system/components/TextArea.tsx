import type { TextareaHTMLAttributes } from "react";
import { cx } from "../lib/cx";

export function TextArea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx("ds-textarea", className)} />;
}
