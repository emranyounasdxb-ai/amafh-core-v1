import type { CaseRecord } from "../../../app/api/models";
import { caseStatusTone } from "./caseDetailPresentation";

export { caseStatusTone };

export const CASE_STATUSES = [
  "Pending for Approval",
  "Approved",
  "Booked",
  "Completed",
  "Rejected",
  "Case Reopened by Owner",
] as const;

export const CASE_VIEWS = [
  { value: "active", label: "Active" },
  { value: "archived", label: "Archived" },
  { value: "all", label: "All retained Cases" },
] as const;

export const initialApprovalColumns = [
  { key: "id", label: "Case ID", width: 150 },
  { key: "customer", label: "Customer", width: 170 },
  { key: "product", label: "Product", width: 100 },
  { key: "bank", label: "Bank", width: 150 },
  { key: "branch", label: "Branch", width: 140 },
  { key: "department", label: "Department", width: 140 },
  { key: "owner", label: "Case Owner", width: 140 },
  { key: "assignment", label: "Coordinator", width: 160 },
  { key: "stage", label: "Current stage", width: 150 },
  { key: "status", label: "Current status", width: 190 },
  { key: "date", label: "Created date", width: 150 },
  { key: "actions", label: "Actions", width: 150 },
] as const;

export const CASE_COLUMN_SORT: Record<string, string> = {
  id: "internalCaseId",
  customer: "customerName",
  product: "productName",
  bank: "bankName",
  variant: "variantOrPfAmount",
  createdBy: "createdByName",
  owner: "ownerName",
  branch: "branchName",
  status: "status",
  bankRef: "bankCaseNumber",
  stage: "currentStage",
  date: "createdAt",
};

export type CaseListFilters = {
  status: string;
  view: string;
  bankId: string;
  productTypeId: string;
  ownerEmployeeId: string;
  createdFrom: string;
  createdTo: string;
};

export const emptyCaseFilters = (): CaseListFilters => ({
  status: "",
  view: "active",
  bankId: "",
  productTypeId: "",
  ownerEmployeeId: "",
  createdFrom: "",
  createdTo: "",
});

export function caseListQuery(
  filters: CaseListFilters,
  page: number,
  pageSize: number,
  sortKey: string | null,
  sortDirection: "asc" | "desc" | null,
  queue: boolean,
  search = "",
) {
  const query = new URLSearchParams({
    page: String(page),
    pageSize: String(pageSize),
  });
  if (!queue) {
    if (filters.status) query.set("status", filters.status);
    query.set("view", filters.view || "active");
    if (filters.bankId) query.set("bankId", filters.bankId);
    if (filters.productTypeId)
      query.set("productTypeId", filters.productTypeId);
    if (filters.ownerEmployeeId)
      query.set("ownerEmployeeId", filters.ownerEmployeeId);
    if (filters.createdFrom) query.set("createdFrom", filters.createdFrom);
    if (filters.createdTo) query.set("createdTo", filters.createdTo);
  }
  if (sortKey && sortDirection) {
    query.set("sort", sortKey);
    query.set("direction", sortDirection);
  }
  if (search.trim()) query.set("q", search.trim());
  return query;
}

export function matchesCaseSearch(
  row: CaseRecord,
  term: string,
  label: (id: string | null) => string,
) {
  const needle = term.trim().toLowerCase();
  if (!needle) return true;
  const haystack = [
    row.internalCaseId,
    label(row.customerId),
    label(row.productTypeId),
    label(row.bankId),
    row.requestedPfAmount || label(row.productVariantId),
    label(row.createdByEmployeeId),
    label(row.ownerEmployeeId),
    label(row.branchId),
    label(row.departmentId),
    label(row.coordinatorEmployeeId),
    row.status,
    row.bankCaseNumber,
    row.currentStage,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(needle);
}

export function viewLabel(view: string) {
  return CASE_VIEWS.find((item) => item.value === view)?.label ?? view;
}

export function activeCaseFilterCount(filters: CaseListFilters) {
  return [
    Boolean(filters.status),
    Boolean(filters.view && filters.view !== "active"),
    Boolean(filters.bankId),
    Boolean(filters.productTypeId),
    Boolean(filters.ownerEmployeeId),
    Boolean(filters.createdFrom || filters.createdTo),
  ].filter(Boolean).length;
}
