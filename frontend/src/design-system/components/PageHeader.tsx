import type { ReactNode } from "react";
import { DsIcon } from "../icons";
import { cx } from "../lib/cx";
import { IconButton } from "./IconButton";
import { PageActions } from "./PageActions";
import { PageTitle } from "./PageTitle";
import { StatusBadge, type StatusTone } from "./StatusBadge";

export function PageHeader({
  title,
  subtitle,
  actions,
  status,
  statusTone = "neutral",
  onBack,
  backLabel = "Back",
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  status?: ReactNode;
  statusTone?: StatusTone;
  onBack?: () => void;
  backLabel?: string;
  className?: string;
}) {
  return (
    <header className={cx("ds-page-header", className)}>
      <div className="ds-page-header__lead">
        {onBack ? (
          <IconButton label={backLabel} variant="ghost" onClick={onBack}>
            <DsIcon name="back" size={16} />
          </IconButton>
        ) : null}
        <PageTitle
          title={title}
          subtitle={
            subtitle || status ? (
              <>
                {subtitle}
                {status ? (
                  <>
                    {subtitle ? " " : null}
                    <StatusBadge tone={statusTone}>{status}</StatusBadge>
                  </>
                ) : null}
              </>
            ) : undefined
          }
        />
      </div>
      {actions ? <PageActions>{actions}</PageActions> : null}
    </header>
  );
}
