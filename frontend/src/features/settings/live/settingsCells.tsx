import {
  EmptyValue,
  StatusBadge,
  TruncatedText,
  formatFullNumber,
} from "../../../design-system";

export function Text({ value }: { value: string | null | undefined }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

export function WholeNumber({
  value,
}: {
  value: number | string | null | undefined;
}) {
  if (value === null || value === undefined || value === "")
    return <EmptyValue />;
  return <span className="ds-numeric">{formatFullNumber(Number(value))}</span>;
}

export function ActiveBadge({ active }: { active: unknown }) {
  return active ? (
    <StatusBadge tone="success">Active</StatusBadge>
  ) : (
    <StatusBadge tone="neutral">Inactive</StatusBadge>
  );
}
