import type { ReactNode } from "react";
import { DsIcon, type DsIconName } from "../icons";
import { cx } from "../lib/cx";
import { Button } from "./Button";

export type FeedbackKind =
  | "loading"
  | "empty"
  | "no-results"
  | "validation"
  | "error"
  | "permission"
  | "not-found"
  | "offline"
  | "retry"
  | "unavailable";

const ICONS: Record<Exclude<FeedbackKind, "loading">, DsIconName> = {
  empty: "search",
  "no-results": "search",
  validation: "alert",
  error: "warning",
  permission: "noAccess",
  "not-found": "notFound",
  offline: "offline",
  retry: "refresh",
  unavailable: "unavailable",
};

export function FeedbackState({
  kind,
  title,
  description,
  action,
  secondary,
  className,
}: {
  kind: FeedbackKind;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  secondary?: ReactNode;
  className?: string;
}) {
  const Icon = kind === "loading" ? null : ICONS[kind];
  const alert = kind === "error" || kind === "validation" || kind === "offline";
  return (
    <div
      className={cx("ds-state", `ds-state--${kind}`, className)}
      role={alert ? "alert" : "status"}
      aria-busy={kind === "loading" || undefined}
    >
      <span className="ds-state__icon" aria-hidden="true">
        {kind === "loading" ? (
          <span className="ds-spinner" />
        ) : Icon ? (
          <DsIcon name={Icon} size={24} />
        ) : null}
      </span>
      <h2 className="ds-state__title">{title}</h2>
      {description ? <p className="ds-state__copy">{description}</p> : null}
      {action || secondary ? (
        <div className="ds-state__actions">
          {action}
          {secondary}
        </div>
      ) : null}
    </div>
  );
}

export function LoadingState({
  title = "Loading",
  description = "Retrieving authorized results…",
  className,
}: {
  title?: ReactNode;
  description?: ReactNode;
  className?: string;
}) {
  return (
    <FeedbackState
      kind="loading"
      title={title}
      description={description}
      className={className}
    />
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  if (icon) {
    return (
      <div className={cx("ds-state", className)} role="status">
        <span className="ds-state__icon" aria-hidden="true">
          {icon}
        </span>
        <h2 className="ds-state__title">{title}</h2>
        {description ? <p className="ds-state__copy">{description}</p> : null}
        {action ? <div className="ds-state__actions">{action}</div> : null}
      </div>
    );
  }
  return (
    <FeedbackState
      kind="empty"
      title={title}
      description={description}
      action={action}
      className={className}
    />
  );
}

export function NoResultsState({
  title = "No matching results",
  description = "Try a different search or clear filters.",
  action,
}: {
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <FeedbackState
      kind="no-results"
      title={title}
      description={description}
      action={action}
    />
  );
}

export function ErrorState({
  title = "Unable to load",
  description,
  retry,
  className,
}: {
  title?: ReactNode;
  description?: ReactNode;
  retry?: () => void;
  className?: string;
}) {
  return (
    <FeedbackState
      kind="error"
      title={title}
      description={description}
      className={className}
      action={
        retry ? (
          <Button variant="secondary" size="compact" onClick={retry}>
            Retry
          </Button>
        ) : undefined
      }
    />
  );
}

export function PermissionDeniedState({
  title = "Permission denied",
  description = "This view is outside the current authorized scope.",
}: {
  title?: ReactNode;
  description?: ReactNode;
}) {
  return (
    <FeedbackState kind="permission" title={title} description={description} />
  );
}

export function NotFoundState({
  title = "Not found",
  description = "The requested record is not available in this view.",
  action,
}: {
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <FeedbackState
      kind="not-found"
      title={title}
      description={description}
      action={action}
    />
  );
}

export function OfflineState({
  title = "Offline",
  description = "This view cannot refresh until the network is available.",
}: {
  title?: ReactNode;
  description?: ReactNode;
}) {
  return (
    <FeedbackState kind="offline" title={title} description={description} />
  );
}

export function RetryState({
  title = "Safe to retry",
  description = "Retrying will not create a duplicate command or financial effect.",
  retry,
  secondary,
}: {
  title?: ReactNode;
  description?: ReactNode;
  retry?: () => void;
  secondary?: ReactNode;
}) {
  return (
    <FeedbackState
      kind="retry"
      title={title}
      description={description}
      action={
        retry ? (
          <Button size="compact" onClick={retry}>
            Retry
          </Button>
        ) : undefined
      }
      secondary={secondary}
    />
  );
}

export function UnavailableState({
  title = "Unavailable",
  description = "This content cannot be shown with the current prerequisites.",
  action,
}: {
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <FeedbackState
      kind="unavailable"
      title={title}
      description={description}
      action={action}
    />
  );
}
