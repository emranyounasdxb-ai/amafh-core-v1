import type { CaseColumn } from "./CaseColumn";

export const initialCaseColumns: CaseColumn[] = [
  { key: "id", label: "Case ID", width: 150 },
  { key: "customer", label: "Customer", width: 170 },
  { key: "product", label: "Product", width: 100 },
  { key: "bank", label: "Bank", width: 150 },
  { key: "variant", label: "Variant / PF AED", width: 170 },
  { key: "createdBy", label: "Created By", width: 140 },
  { key: "owner", label: "Owner", width: 140 },
  { key: "branch", label: "Branch", width: 140 },
  { key: "status", label: "Case status", width: 190 },
  { key: "bankRef", label: "Bank Case Number", width: 180 },
  { key: "stage", label: "Current stage", width: 170 },
  { key: "date", label: "Created date", width: 150 },
];
