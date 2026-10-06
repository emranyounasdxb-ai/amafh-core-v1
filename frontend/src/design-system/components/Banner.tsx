import type { ReactNode } from "react";
import { DsIcon, type DsIconName } from "../icons";
import { cx } from "../lib/cx";
import { IconButton } from "./IconButton";

export type BannerTone =
  | "info"
  | "success"
  | "warning"
  | "error"
  | "permission"
  | "maintenance"
  | "announcement"
  | "contextual";

export type BannerLevel = "global" | "page" | "inline";

const icons: Record<BannerTone, DsIconName> = {
  info: "information",
  success: "success",
  warning: "warning",
  error: "alert",
  permission: "noAccessBanner",
  maintenance: "maintenance",
  announcement: "information",
  contextual: "information",
};

export function Banner({
  tone = "info",
  level = "page",
  title,
  children,
  actions,
  onDismiss,
  compact = true,
  className,
}: {
  tone?: BannerTone;
  level?: BannerLevel;
  title?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  onDismiss?: () => void;
  compact?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "ds-banner",
        `ds-banner--${tone}`,
        `ds-banner--${level}`,
        compact && "ds-banner--compact",
        className,
      )}
      role={tone === "error" ? "alert" : "status"}
    >
      <span className="ds-banner__icon" aria-hidden="true">
        <DsIcon name={icons[tone]} size={16} />
      </span>
      <div className="ds-banner__copy">
        {title ? <strong>{title}</strong> : null}
        {children ? <p>{children}</p> : null}
      </div>
      {actions ? <div className="ds-banner__actions">{actions}</div> : null}
      {onDismiss ? (
        <IconButton
          label="Dismiss banner"
          variant="ghost"
          size="compact"
          onClick={onDismiss}
        >
          <DsIcon name="close" size={16} />
        </IconButton>
      ) : null}
    </div>
  );
}
