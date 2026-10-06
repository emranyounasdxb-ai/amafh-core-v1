import type { ReactNode } from "react";
import { FormField } from "./FormField";

export function ReadOnlyField({
  label,
  value,
  hint,
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
}) {
  return (
    <FormField label={label} hint={hint}>
      <div className="ds-readonly">{value}</div>
    </FormField>
  );
}
