import type { ReactNode } from "react";
import { DsIcon } from "../icons";
import { Avatar } from "./Avatar";
import { Button } from "./Button";
import { Menu, type MenuItem } from "./Menu";
import { StatusBadge, type StatusTone } from "./StatusBadge";

export function ProfileStatus({
  label,
  tone = "success",
}: {
  label: ReactNode;
  tone?: StatusTone;
}) {
  return <StatusBadge tone={tone}>{label}</StatusBadge>;
}

export function ProfileMetadata({
  items,
}: {
  items: { label: string; value: ReactNode }[];
}) {
  return (
    <dl className="ds-profile-meta">
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function UserIdentity({
  name,
  designation,
  code,
  src,
  size = "md",
}: {
  name: string;
  designation?: ReactNode;
  code?: ReactNode;
  src?: string;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  return (
    <div className="ds-user-identity">
      <Avatar name={name} src={src} size={size === "xl" ? "xl" : size} />
      <div className="ds-user-identity__copy">
        <strong>{name}</strong>
        {designation ? <span>{designation}</span> : null}
        {code ? <em>{code}</em> : null}
      </div>
    </div>
  );
}

export function EmployeeIdentity(props: Parameters<typeof UserIdentity>[0]) {
  return <UserIdentity {...props} />;
}

export function ProfileCard({
  name,
  designation,
  code,
  src,
  status,
  statusTone,
  menu,
  onClick,
}: {
  name: string;
  designation?: ReactNode;
  code?: ReactNode;
  src?: string;
  status?: ReactNode;
  statusTone?: StatusTone;
  menu?: boolean;
  onClick?: () => void;
}) {
  return (
    <button type="button" className="ds-profile-card" onClick={onClick}>
      <UserIdentity
        name={name}
        designation={designation}
        code={code}
        src={src}
        size="sm"
      />
      {status ? <ProfileStatus label={status} tone={statusTone} /> : null}
      {menu ? <DsIcon name="expand" size={16} /> : null}
    </button>
  );
}

export function ProfileMenu({
  name,
  designation,
  src,
  items,
}: {
  name: string;
  designation?: ReactNode;
  src?: string;
  items?: MenuItem[];
}) {
  return (
    <Menu
      label="Account"
      align="bottom-end"
      trigger={
        <ProfileCard name={name} designation={designation} src={src} menu />
      }
      items={
        items ?? [
          {
            id: "profile",
            label: "View profile",
            icon: <DsIcon name="user" size={16} />,
          },
          {
            id: "settings",
            label: "Account settings",
            icon: <DsIcon name="settings" size={16} />,
          },
          {
            id: "out",
            label: "Sign out",
            icon: <DsIcon name="signOut" size={16} />,
            separator: true,
            danger: true,
          },
        ]
      }
    />
  );
}

export function ProfileSummary({
  name,
  designation,
  code,
  src,
  status,
  statusTone,
  branch,
  department,
  manager,
  primaryAction,
  secondaryActions,
}: {
  name: string;
  designation?: ReactNode;
  code?: ReactNode;
  src?: string;
  status?: ReactNode;
  statusTone?: StatusTone;
  branch?: ReactNode;
  department?: ReactNode;
  manager?: ReactNode;
  primaryAction?: ReactNode;
  secondaryActions?: ReactNode;
}) {
  return (
    <section className="ds-profile-summary">
      <div className="ds-profile-summary__identity">
        <UserIdentity
          name={name}
          designation={designation}
          code={code}
          src={src}
          size="xl"
        />
        {status ? <ProfileStatus label={status} tone={statusTone} /> : null}
      </div>
      <ProfileMetadata
        items={[
          { label: "Branch", value: branch ?? "—" },
          { label: "Department", value: department ?? "—" },
          { label: "Reporting manager", value: manager ?? "—" },
        ]}
      />
      {primaryAction || secondaryActions ? (
        <div className="ds-profile-summary__actions">
          {secondaryActions}
          {primaryAction ?? <Button>View profile</Button>}
        </div>
      ) : null}
    </section>
  );
}
