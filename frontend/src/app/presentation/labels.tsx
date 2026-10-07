import type { ReactNode } from "react";
import {
  CompactDate,
  CompactDateTime,
  isDateOnlyField,
  isMoneyField,
  isTimestampField,
  MonetaryAmount,
  TruncatedText,
} from "../../design-system";
import type { DataRecord } from "../api/models";
import { useResource } from "../api/useResource";
import { useSession } from "../session/useSession";

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isUuid(value: unknown): boolean {
  return typeof value === "string" && uuidPattern.test(value.trim());
}

export function isEmployeeIdKey(key: string) {
  return /EmployeeId$/i.test(key) || key === "employeeId";
}

export function isInternalIdKey(key: string) {
  return (
    isEmployeeIdKey(key) ||
    /^(id|uuid)$/i.test(key) ||
    /(Id|Ids|Uuid|Uuids)$/.test(key)
  );
}

export function readableLabel(
  value: unknown,
  fallback = "Unavailable",
): string {
  const text = String(value ?? "").trim();
  if (!text || isUuid(text)) return fallback;
  return text;
}

function employeeFallback(key?: string) {
  if (key === "actorEmployeeId" || key === "createdByEmployeeId")
    return "Team member";
  if (key === "reportingManagerId" || key === "leaderEmployeeId")
    return "Team member";
  return "Assigned employee";
}

export function EmployeeLabel({
  employeeId,
  fieldKey,
  fallback,
  showCode = false,
  plain = false,
}: {
  employeeId: string;
  fieldKey?: string;
  fallback?: string;
  showCode?: boolean;
  /** Text only, for phrasing-content slots such as a timeline actor paragraph. */
  plain?: boolean;
}) {
  const { session } = useSession();
  const safe = fallback || employeeFallback(fieldKey);
  const self = Boolean(session && session.employeeId === employeeId);
  /** Mirrors the server "own" Employee read scope, which never returns another employee. */
  const ownScope =
    session?.designation === "Sales Executive" ||
    session?.designation === "Coordinator";
  const record = useResource<DataRecord>(
    employeeId && !self && !ownScope ? `/employee-labels/${employeeId}` : null,
  );
  if (!employeeId) return <>{safe}</>;
  if (self) {
    if (plain) return <>{session!.displayName}</>;
    return <EmployeeText name={session!.displayName} />;
  }
  if (ownScope || record.denied || record.error) return <>{safe}</>;
  if (record.loading && !record.data) return <>Loading…</>;
  const name = readableLabel(
    record.data?.fullName || record.data?.name,
    "",
  );
  const code = readableLabel(
    record.data?.employeeCode || record.data?.companyEmployeeCode,
    "",
  );
  if (!name) return <>{safe}</>;
  if (plain) return <>{name}</>;
  return <EmployeeText name={name} code={showCode ? code : ""} />;
}

function EmployeeText({ name, code }: { name: string; code?: string }) {
  return (
    <span className="ds-app-person">
      <TruncatedText value={name} />
      {code ? <small>{code}</small> : null}
    </span>
  );
}

export function labeledRecordValue(
  key: string,
  value: unknown,
): ReactNode | null {
  if (value == null || value === "" || typeof value === "object") return null;
  if (isEmployeeIdKey(key) && typeof value === "string") {
    return (
      <EmployeeLabel employeeId={value} fieldKey={key} showCode={false} />
    );
  }
  if (isInternalIdKey(key) && isUuid(value)) return null;
  if (isMoneyField(key)) return <MonetaryAmount compact={false} value={value} />;
  if (isDateOnlyField(key)) return <CompactDate value={value} />;
  if (isTimestampField(key)) return <CompactDateTime value={value} />;
  return String(value);
}

const preferredRelatedKeys = [
  "fullName",
  "name",
  "title",
  "displayName",
  "companyName",
  "customerName",
  "employeeName",
  "internalCaseId",
  "caseNumber",
  "bankCaseNumber",
  "employeeCode",
  "companyEmployeeCode",
  "status",
  "priority",
  "designation",
  "kind",
];

export function relatedRecordFields(record: DataRecord) {
  const entries: { key: string; label: string; value: ReactNode }[] = [];
  for (const key of preferredRelatedKeys) {
    const value = labeledRecordValue(key, record[key]);
    if (value == null) continue;
    entries.push({
      key,
      label: relatedFieldLabel(key),
      value,
    });
  }
  if (entries.length) return entries;
  return [
    {
      key: "related",
      label: "Record",
      value: "Related record",
    },
  ];
}

function relatedFieldLabel(key: string) {
  if (key === "fullName" || key === "displayName" || key === "name")
    return "Name";
  if (key === "internalCaseId" || key === "caseNumber") return "Case";
  if (key === "employeeCode" || key === "companyEmployeeCode")
    return "Employee code";
  if (key === "companyName") return "Company";
  return key.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/^./, (c) =>
    c.toUpperCase(),
  );
}
