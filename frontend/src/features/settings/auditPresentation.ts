import { isEmployeeIdKey } from "../../app/presentation/labels";
import {
  PRODUCT_LABEL,
  type Product,
} from "../performance/live/performancePresentation";

export type AuditEvent = {
  id: string;
  actorEmployeeId: string | null;
  action: string;
  module: string;
  entityType: string | null;
  entityId: string | null;
  occurredAt: string;
  context: unknown;
  before: unknown;
  after: unknown;
};

export type RecordKind =
  | "person"
  | "case"
  | "customer"
  | "asset"
  | "team"
  | "branch"
  | "department"
  | "designation"
  | "banks"
  | "product-types"
  | "product-variants";

const ACRONYMS = new Set(["csv", "pdf", "aed", "cc", "pf", "hr", "md"]);

function sentence(value: string) {
  const text = value
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[._-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase()
    .split(" ")
    .map((word) => (ACRONYMS.has(word) ? word.toUpperCase() : word))
    .join(" ");
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
}

export function eventLabel(action: string | null | undefined) {
  return sentence(action ?? "") || "Recorded event";
}

export function moduleLabel(module: string | null | undefined) {
  return sentence(module ?? "");
}

export function recordTypeLabel(entityType: string | null | undefined) {
  return sentence(entityType ?? "");
}

const CODE_FIELDS = new Set(["report", "table", "mode", "relatedType"]);
const PRODUCT_FIELDS = new Set(["product", "productCode"]);

export function codeLabel(key: string, text: string) {
  if (key === "format") return text.toUpperCase();
  if (PRODUCT_FIELDS.has(key) && text in PRODUCT_LABEL)
    return PRODUCT_LABEL[text as Product];
  if (CODE_FIELDS.has(key) || /^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$/.test(text))
    return sentence(text);
  return null;
}

export function fieldLabel(key: string) {
  if (key === "id") return "Record";
  const trimmed = key.replace(/_?(ids|Ids)$/, "s").replace(/_?(id|Id)$/, "");
  return sentence(trimmed) || "Record";
}

const KEY_KINDS: Record<string, RecordKind> = {
  branchId: "branch",
  branch_id: "branch",
  departmentId: "department",
  department_id: "department",
  designationId: "designation",
  designation_id: "designation",
  bankId: "banks",
  bank_id: "banks",
  productTypeId: "product-types",
  product_type_id: "product-types",
  productVariantId: "product-variants",
  product_variant_id: "product-variants",
  caseId: "case",
  customerId: "customer",
  teamId: "team",
};

export function keyKind(key: string): RecordKind | null {
  if (isEmployeeIdKey(key)) return "person";
  return KEY_KINDS[key] ?? null;
}

const ENTITY_KINDS: Record<string, RecordKind> = {
  case: "case",
  employee: "person",
  asset: "asset",
  team: "team",
  banks: "banks",
  product_variants: "product-variants",
  departments: "department",
};

export function entityKind(entityType: string | null | undefined) {
  return entityType ? (ENTITY_KINDS[entityType] ?? null) : null;
}

export function isTechnicalKey(key: string) {
  return /Hash$/i.test(key);
}

export function payloadEntries(value: unknown): [string, unknown][] {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return Object.entries(value as Record<string, unknown>).filter(
    ([key]) => !isTechnicalKey(key),
  );
}

export const AUDIT_EMPTY = {
  actorId: "",
  module: "",
  action: "",
  entityId: "",
  fromDate: "",
  fromTime: "",
  toDate: "",
  toTime: "",
};

export type AuditFilters = typeof AUDIT_EMPTY;

export function auditQuery(filters: AuditFilters) {
  const params = new URLSearchParams();
  if (filters.actorId) params.set("actorId", filters.actorId);
  if (filters.module.trim()) params.set("module", filters.module.trim());
  if (filters.action.trim()) params.set("action", filters.action.trim());
  if (filters.entityId.trim()) params.set("entityId", filters.entityId.trim());
  if (filters.fromDate)
    params.set(
      "fromTime",
      `${filters.fromDate}T${filters.fromTime || "00:00"}:00+04:00`,
    );
  if (filters.toDate)
    params.set(
      "toTime",
      `${filters.toDate}T${filters.toTime || "23:59"}:${filters.toTime ? "00" : "59"}+04:00`,
    );
  return params.toString();
}

export function rangeInvalid(filters: AuditFilters) {
  if (!filters.fromDate || !filters.toDate) return false;
  const from = `${filters.fromDate}T${filters.fromTime || "00:00"}`;
  const to = `${filters.toDate}T${filters.toTime || "23:59"}`;
  return from > to;
}
