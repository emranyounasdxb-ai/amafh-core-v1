import { Avatar } from "./Avatar";
import { TruncatedText, EmptyValue } from "./Display";

/** Inline employee identity for tables, compact lists and read-only fields. */
export function PersonValue({
  name,
  code,
  src,
}: {
  name?: string | null;
  code?: string | null;
  src?: string;
}) {
  if (!name) return <EmptyValue />;
  return (
    <span className="ds-person-value">
      <Avatar name={name} src={src} size="sm" />
      <TruncatedText value={code ? `${name} · ${code}` : name} />
    </span>
  );
}
