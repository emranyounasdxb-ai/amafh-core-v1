import type { DataRecord } from "./models";
import type { ImageUpload } from "./recordImages";

export type ChoiceSource = {
  path: string;
  label: string;
  value?: string;
  paged?: boolean;
  search?: boolean;
  where?: Record<string, string>;
  allowed?: Record<string, string[]>;
  queryFrom?: Record<string, string>;
  matchFrom?: Record<string, string>;
  exclude?: string[];
  /** A required parent choice; do not request options until it is present. */
  requires?: { key: string; placeholder: string };
  emptyLabel?: string;
  /** Keep an already saved choice visible when it no longer matches `where`. */
  keepSelected?: boolean;
};
export type Field = {
  key: string;
  label: string;
  type?:
    | "text"
    | "email"
    | "date"
    | "time"
    | "number"
    | "decimal"
    | "textarea"
    | "datetime-local"
    | "checkbox"
    | "month";
  required?: boolean;
  options?: string[];
  optionLabels?: Record<string, string>;
  source?: ChoiceSource;
  max?: number;
  show?: (values: DataRecord) => boolean;
  initial?: unknown;
  initialChoiceLabel?: string;
  choiceLabel?: "departmentWithBranch" | "nameWithCode";
  choiceContextKey?: string;
  /** Copies an attribute of the selected choice into form state (not submitted). */
  choiceContext?: { key: string; from: string };
  clearOnChange?: string[];
  section?: string;
  control?: "nationality";
  hint?: string;
  /** Explicitly clear an optional nullable field instead of omitting it. */
  emptyAsNull?: boolean;
  /** Reject negative input before whole-number rounding. */
  nonNegative?: boolean;
};
export type CommandConfirmation = {
  description: string;
  facts: { label: string; value: string }[];
};
export type Command = {
  title: string;
  path: string;
  method?: "POST" | "PATCH" | "PUT";
  fields: Field[];
  idempotent?: boolean;
  fixed?: DataRecord;
  transform?: (values: DataRecord) => DataRecord;
  confirmation?: CommandConfirmation;
  submitLabel?: string;
  imageUpload?: ImageUpload;
  formClassName?: string;
};
export const employeeSource: ChoiceSource = {
  path: "/employee-labels?status=Active",
  label: "fullName",
  paged: true,
};
export const branchField: Field = {
  key: "branchId",
  label: "Branch",
  required: true,
  source: { path: "/branches", label: "name" },
};
export const departmentField: Field = {
  key: "departmentId",
  label: "Department",
  required: true,
  source: {
    path: "/departments",
    label: "name",
    queryFrom: { branchId: "branchId" },
  },
};
export const designationField: Field = {
  key: "designationId",
  label: "Designation",
  required: true,
  source: { path: "/designations", label: "name" },
};
export const reasonField: Field = {
  key: "reason",
  label: "Reason",
  type: "textarea",
  required: true,
  max: 1000,
};
export const effectiveField: Field = {
  key: "effectiveDate",
  label: "Effective Date",
  type: "date",
  required: true,
};
export const dueField: Field = {
  key: "dueAt",
  label: "Due date and time (Asia/Dubai)",
  type: "datetime-local",
  required: true,
};
export const bankField: Field = {
  key: "bankId",
  label: "Bank",
  required: true,
  source: { path: "/catalog/banks?active=true", label: "name", paged: true },
};
export const productField: Field = {
  key: "productTypeId",
  label: "Product",
  required: true,
  source: {
    path: "/catalog/product-types?active=true",
    label: "name",
    paged: true,
  },
};
/** Products the selected bank offers through an active bank product. */
export const offeredProductField: Field = {
  ...productField,
  source: { ...productField.source!, queryFrom: { bankId: "bankId" } },
};
export const variantField: Field = {
  key: "productVariantId",
  label: "CC Variant (CC rules only)",
  source: {
    path: "/catalog/product-variants?active=true",
    label: "name",
    paged: true,
    queryFrom: { bankId: "bankId", productTypeId: "productTypeId" },
  },
};
