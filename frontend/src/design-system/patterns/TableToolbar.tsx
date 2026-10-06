import type { ReactNode } from "react";
import { ActionToolbar } from "../components/ActionToolbar";
import { SectionHeader } from "../components/SectionHeader";

export function TableToolbar({
  title,
  description,
  children,
}: {
  title?: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <SectionHeader
      title={title || undefined}
      description={description}
      actions={children ? <ActionToolbar>{children}</ActionToolbar> : undefined}
    />
  );
}
