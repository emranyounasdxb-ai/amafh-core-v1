import type { ReactNode } from "react";
import { SectionCard } from "../components/SectionCard";
import {
  FormActions,
  FormLayout,
  type FormColumns,
} from "../components/FormLayout";

export function FormSection({
  title,
  description,
  children,
  columns = 2,
  actions,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  columns?: FormColumns;
  actions?: ReactNode;
}) {
  return (
    <SectionCard title={title} description={description}>
      <div className="ds-form-section">
        <FormLayout columns={columns}>{children}</FormLayout>
        {actions ? <FormActions>{actions}</FormActions> : null}
      </div>
    </SectionCard>
  );
}
