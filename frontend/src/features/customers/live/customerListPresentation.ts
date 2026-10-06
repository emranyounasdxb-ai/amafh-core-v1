import { nationalityOptions } from "../../../design-system";

export type CustomerListRecord = {
  id: string;
  customerId: string;
  type: string;
  name: string | null;
  nationality: string | null;
  emiratesId: string | null;
  passportNumber: string | null;
  employer: string | null;
  tradeLicense: string | null;
  contactPerson: string | null;
  mobile: string | null;
  email: string | null;
  createdAt: string;
};

export type CustomerListFilters = {
  type: string;
};

export const emptyCustomerFilters = (): CustomerListFilters => ({
  type: "",
});

export const CUSTOMER_TYPES = ["Individual", "Company"] as const;

export const CUSTOMER_COLUMNS = [
  { key: "customerId", label: "Customer ID", width: 140 },
  { key: "name", label: "Name", width: 180 },
  { key: "type", label: "Customer type", width: 130 },
  { key: "nationality", label: "Nationality", width: 150 },
  { key: "contactPerson", label: "Contact person", width: 160 },
  { key: "mobile", label: "Mobile", width: 140 },
  { key: "email", label: "Email", width: 180 },
  { key: "passportNumber", label: "Passport", width: 140 },
  { key: "eidOrTl", label: "EID / Trade licence", width: 170 },
  { key: "createdAt", label: "Created", width: 150 },
] as const;

export const CUSTOMER_COLUMN_SORT: Record<string, string> = {
  customerId: "customerId",
  name: "name",
  type: "type",
  nationality: "nationality",
  contactPerson: "contactPerson",
  mobile: "mobile",
  email: "email",
  passportNumber: "passportNumber",
  eidOrTl: "eidOrTl",
  createdAt: "createdAt",
};

export function customerListQuery(
  filters: CustomerListFilters,
  page: number,
  pageSize: number,
  sortKey: string | null,
  sortDirection: "asc" | "desc" | null,
  search = "",
) {
  const query = new URLSearchParams({
    page: String(page),
    pageSize: String(pageSize),
  });
  if (filters.type) query.set("type", filters.type);
  if (search.trim()) query.set("q", search.trim());
  if (sortKey && sortDirection) {
    query.set("sort", sortKey);
    query.set("direction", sortDirection);
  }
  return query;
}

export function activeCustomerFilterCount(filters: CustomerListFilters) {
  return Number(Boolean(filters.type));
}

export function matchesCustomerSearch(row: CustomerListRecord, term: string) {
  const needle = term.trim().toLowerCase();
  if (!needle) return true;
  return [
    row.customerId,
    row.name,
    row.type,
    nationalityLabel(row.nationality),
    row.contactPerson,
    row.mobile,
    row.email,
    row.passportNumber,
    row.emiratesId,
    row.tradeLicense,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
    .includes(needle);
}

export function nationalityLabel(code: string | null | undefined) {
  if (!code) return "";
  return (
    nationalityOptions().find((option) => option.value === code)?.label || ""
  );
}

export function identityNumber(row: CustomerListRecord) {
  return row.type === "Individual" ? row.emiratesId : row.tradeLicense;
}
