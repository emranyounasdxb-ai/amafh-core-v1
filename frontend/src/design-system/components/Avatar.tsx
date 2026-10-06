import { cx } from "../lib/cx";

export type AvatarSize = "sm" | "md" | "lg" | "xl";

export function Avatar({
  name,
  src,
  size = "md",
  className,
}: {
  name: string;
  src?: string;
  size?: AvatarSize;
  className?: string;
}) {
  const initials = name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  return (
    <span
      className={cx("ds-avatar", `ds-avatar--${size}`, className)}
      title={name}
    >
      {src ? <img src={src} alt="" /> : initials || "?"}
    </span>
  );
}

export function AvatarGroup({
  people,
  max = 4,
}: {
  people: { name: string; src?: string }[];
  max?: number;
}) {
  const visible = people.slice(0, max);
  const extra = people.length - visible.length;
  return (
    <div className="ds-avatar-group">
      {visible.map((person) => (
        <Avatar
          key={person.name}
          name={person.name}
          src={person.src}
          size="sm"
        />
      ))}
      {extra > 0 ? (
        <span className="ds-avatar ds-avatar--sm">+{extra}</span>
      ) : null}
    </div>
  );
}
