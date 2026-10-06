import type { ReactNode } from "react";
import { DsIcon, type DsIconName } from "../icons";
import { cx } from "../lib/cx";
import { Avatar } from "./Avatar";
import { Button } from "./Button";
import { IconButton } from "./IconButton";
import { OverflowMenu } from "./SplitButton";
import { StatusBadge, type StatusTone } from "./StatusBadge";
import { TruncatedText } from "./Display";
import type { MenuItem } from "./Menu";
import { ProgressBar } from "./Display";

export function ProfileBannerStatus({
  label,
  tone = "success",
}: {
  label: ReactNode;
  tone?: StatusTone;
}) {
  return (
    <StatusBadge tone={tone} className="ds-profile-banner__status">
      {label}
    </StatusBadge>
  );
}

export function ProfileCoverStatus(props: {
  label: ReactNode;
  tone?: StatusTone;
}) {
  return <ProfileBannerStatus {...props} />;
}

export function ProfileBannerIdentity({
  name,
  designation,
  code,
  src,
  status,
  statusTone,
  completion,
  contextLabel,
  onEditAvatar,
}: {
  name: string;
  designation?: ReactNode;
  code?: ReactNode;
  src?: string;
  status?: ReactNode;
  statusTone?: StatusTone;
  completion?: number;
  contextLabel?: ReactNode;
  onEditAvatar?: () => void;
}) {
  return (
    <div className="ds-profile-banner__identity">
      <div className="ds-profile-banner__avatar">
        <Avatar name={name} src={src} size="xl" />
        {onEditAvatar ? (
          <span className="ds-profile-banner__avatar-edit">
            <IconButton
              label="Edit photo"
              size="compact"
              variant="secondary"
              onClick={onEditAvatar}
            >
              <DsIcon name="edit" size={14} />
            </IconButton>
          </span>
        ) : null}
      </div>
      <div className="ds-profile-banner__who">
        {contextLabel ? (
          <span className="ds-profile-banner__context">{contextLabel}</span>
        ) : null}
        <h2>
          <TruncatedText value={name} />
        </h2>
        {designation ? <p>{designation}</p> : null}
        {code ? <em>{code}</em> : null}
        {status ? (
          <ProfileBannerStatus label={status} tone={statusTone} />
        ) : null}
        {completion != null ? (
          <div className="ds-profile-banner__completion">
            <span>Profile {completion}%</span>
            <ProgressBar
              value={completion}
              label="Profile completion"
              tone="brand"
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function ProfileCoverIdentity(props: Parameters<
  typeof ProfileBannerIdentity
>[0]) {
  return <ProfileBannerIdentity {...props} />;
}

export function ProfileBannerMetadata({
  items,
}: {
  items: {
    id: string;
    label: string;
    value: ReactNode;
    icon?: DsIconName;
  }[];
}) {
  if (!items.length) return null;
  return (
    <dl className="ds-profile-banner__meta">
      {items.map((item) => (
        <div key={item.id}>
          <dt>
            {item.icon ? <DsIcon name={item.icon} size={14} /> : null}
            {item.label}
          </dt>
          <dd>
            {typeof item.value === "string" ? (
              <TruncatedText value={item.value} />
            ) : (
              item.value
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function ProfileCoverMetadata(
  props: Parameters<typeof ProfileBannerMetadata>[0],
) {
  return <ProfileBannerMetadata {...props} />;
}

export function ProfileBannerStats({
  items,
}: {
  items: { id: string; label: string; value: ReactNode }[];
}) {
  if (!items.length) return null;
  return (
    <ul className="ds-profile-banner__stats">
      {items.map((item) => (
        <li key={item.id}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </li>
      ))}
    </ul>
  );
}

export function ProfileBannerActions({
  primary,
  secondary,
  overflow,
  onBack,
}: {
  primary?: ReactNode;
  secondary?: ReactNode;
  overflow?: MenuItem[];
  onBack?: () => void;
}) {
  return (
    <div className="ds-profile-banner__actions">
      {onBack ? (
        <IconButton label="Back" variant="ghost" onClick={onBack}>
          <DsIcon name="back" size={18} />
        </IconButton>
      ) : null}
      {primary}
      {secondary}
      {overflow?.length ? <OverflowMenu items={overflow} /> : null}
    </div>
  );
}

export function ProfileCoverActions(
  props: Parameters<typeof ProfileBannerActions>[0],
) {
  return <ProfileBannerActions {...props} />;
}

export function ProfileCoverBackground() {
  return <div className="ds-profile-cover__bg" aria-hidden="true" />;
}

export function ProfileBanner({
  identity,
  metadata,
  stats,
  actions,
  compact,
  variant = "plain",
  children,
}: {
  identity?: ReactNode;
  metadata?: ReactNode;
  stats?: ReactNode;
  actions?: ReactNode;
  compact?: boolean;
  variant?: "plain" | "cover";
  children?: ReactNode;
}) {
  const main = (
    <div className="ds-profile-banner__main">
      {identity}
      {actions}
    </div>
  );
  return (
    <section
      className={cx(
        "ds-profile-banner",
        compact && "ds-profile-banner--compact",
        variant === "cover" && "ds-profile-banner--cover",
      )}
    >
      {variant === "cover" ? (
        <div className="ds-profile-cover">
          <ProfileCoverBackground />
          {main}
        </div>
      ) : (
        main
      )}
      {metadata}
      {stats}
      {children}
    </section>
  );
}

export function ProfileCoverBanner(
  props: Omit<Parameters<typeof ProfileBanner>[0], "variant">,
) {
  return <ProfileBanner {...props} variant="cover" />;
}

export function ProfileBannerPrimaryAction({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick?: () => void;
}) {
  return <Button onClick={onClick}>{children}</Button>;
}

export function ProfileBannerSecondaryAction({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick?: () => void;
}) {
  return (
    <Button variant="secondary" onClick={onClick}>
      {children}
    </Button>
  );
}
