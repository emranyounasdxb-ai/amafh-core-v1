import type { DataRecord } from "../../../app/api/models";
import { nationalityLabel } from "./customerListPresentation";

export type RelatedCaseRecord = {
  id: string;
  internalCaseId?: string;
  product?: string;
  status?: string;
  stage?: string;
  owner?: string;
  createdAt?: string;
};

export type CustomerDetailRecord = {
  id: string;
  customerId: string;
  type: string;
  salaryAed?: string | null;
  identity?: DataRecord;
  cases?: RelatedCaseRecord[];
};

function text(value: unknown) {
  if (value == null) return "";
  const next = String(value).trim();
  return next;
}

export function customerDisplayName(row: CustomerDetailRecord) {
  const identity = row.identity ?? {};
  return (
    text(identity.full_name) ||
    text(identity.company_name) ||
    text(row.customerId) ||
    "Unavailable"
  );
}

export function identityValue(identity: DataRecord | undefined, key: string) {
  return text(identity?.[key]);
}

export function individualNationality(identity: DataRecord | undefined) {
  return nationalityLabel(text(identity?.nationality) || null);
}

export function relatedCaseTitle(item: RelatedCaseRecord) {
  return text(item.internalCaseId) || "Related Case";
}

export function relatedCaseMeta(item: RelatedCaseRecord) {
  return [
    text(item.product),
    text(item.status),
    text(item.stage),
    text(item.owner),
  ]
    .filter(Boolean)
    .join(" · ");
}
