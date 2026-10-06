import type { ReactNode } from "react";
import { PageHeader } from "../components/PageHeader";
import type { StatusTone } from "../components/StatusBadge";

export function RecordDetailHeader({
  title,
  subtitle,
  status,
  statusTone = "neutral",
  actions,
  onBack,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  status?: ReactNode;
  statusTone?: StatusTone;
  actions?: ReactNode;
  onBack?: () => void;
}) {
  return (
    <PageHeader
      title={title}
      subtitle={subtitle}
      status={status}
      statusTone={statusTone}
      actions={actions}
      onBack={onBack}
    />
  );
}
