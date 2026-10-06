import {
  isDateOnlyField,
  isMoneyField,
  isTimestampField,
  type DataTableColumnKind,
  type SelectOption,
} from "../../design-system";
import type { Designation } from "../../access";
import type { DataRecord, Page } from "../../app/api/models";
import { ASSET_CATEGORIES, ASSET_STATUSES } from "../assets/live/assetCommands";
import { CASE_STATUSES } from "../cases/live/caseListPresentation";
import { EMPLOYEE_STATUSES } from "../employees/live/employeePresentation";
import { productOptions } from "../performance/live/performancePresentation";

export type ReportCatalogItem = {
  report: string;
  title: string;
  columns: { key: string; heading: string }[];
  filters: string[];
};

export type ReportPage = Page<DataRecord> & {
  report: string;
  title: string;
  summary: DataRecord;
  columns: ReportCatalogItem["columns"];
  startDate: string;
  endDate: string;
};

export type ReportPeriod = "today" | "week" | "month" | "year" | "custom";

export const PERIOD_OPTIONS: { value: ReportPeriod; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "week", label: "This week" },
  { value: "month", label: "This month" },
  { value: "year", label: "This year" },
  { value: "custom", label: "Custom range" },
];

export const PRODUCT_OPTIONS: SelectOption[] = productOptions;

export const PANEL_FILTER_ORDER = [
  "branchId",
  "departmentId",
  "teamId",
  "employeeId",
  "designationId",
  "bankId",
  "customerType",
  "status",
  "accessStatus",
  "category",
] as const;

export type PanelFilter = (typeof PANEL_FILTER_ORDER)[number];

export function panelFilters(definition: ReportCatalogItem | undefined) {
  if (!definition) return [];
  return PANEL_FILTER_ORDER.filter((key) => definition.filters.includes(key));
}

export function productRequired(report: string | undefined) {
  return report === "ranking";
}

const EMPLOYEE_COLUMNS = new Set([
  "employeeId",
  "ownerEmployeeId",
  "caseOwnerEmployeeId",
  "currentEmployeeId",
]);

export type ColumnRole =
  | "branch"
  | "department"
  | "bank"
  | "employee"
  | "employee-code"
  | "money"
  | "number"
  | "percent"
  | "achieved"
  | "product"
  | "boolean"
  | "time"
  | "date"
  | "datetime"
  | "status"
  | "text";

const NUMBER_KEYS = new Set([
  "rank",
  "caseCount",
  "createdCaseCount",
  "bookedCaseCount",
  "completedCaseCount",
  "rejectedCaseCount",
  "delayedCaseCount",
  "handledCases",
  "submittedBookedCases",
  "stageUpdatedCases",
  "achievedCCPoints",
  "ccPoints",
]);

export function columnRole(
  report: string,
  key: string,
  keys: string[],
): ColumnRole {
  if (key === "branchId") return "branch";
  if (key === "departmentId") return "department";
  if (key === "bankId") return "bank";
  if (EMPLOYEE_COLUMNS.has(key))
    return key === "employeeId" && keys.includes("employeeName")
      ? "employee-code"
      : "employee";
  if (key === "achievedValue") return "achieved";
  if (key === "achievementPercentage") return "percent";
  if (NUMBER_KEYS.has(key)) return "number";
  if (isMoneyField(key)) return "money";
  if (key === "productCode") return "product";
  if (key === "isLate") return "boolean";
  if (key === "checkInTime" || key === "checkOutTime") return "time";
  if (isDateOnlyField(key)) return "date";
  if (isTimestampField(key)) return "datetime";
  if (key === "status" || key === "accessStatus") return "status";
  void report;
  return "text";
}

export function columnKind(
  role: ColumnRole,
  product: string,
): DataTableColumnKind {
  if (role === "money") return "money";
  if (role === "number" || role === "percent") return "number";
  if (role === "achieved") return product === "PF" ? "money" : "number";
  if (role === "date" || role === "time") return "date";
  if (role === "datetime") return "datetime";
  return "text";
}

export function columnWidth(role: ColumnRole) {
  if (role === "employee") return 200;
  if (role === "employee-code") return 140;
  if (role === "money" || role === "achieved") return 140;
  if (role === "number" || role === "percent") return 130;
  if (role === "datetime") return 150;
  if (role === "date") return 130;
  if (role === "boolean" || role === "time" || role === "product") return 110;
  return 170;
}

export function columnLabel(
  report: string,
  key: string,
  heading: string,
  role: ColumnRole,
  product = "",
) {
  if (role === "achieved" && (product === "CC" || product === "PF"))
    return `${heading} (${product === "CC" ? "Points" : "AED"})`;
  if (role === "branch") return "Branch";
  if (role === "department") return "Department";
  if (role === "bank") return "Bank";
  if (role === "employee-code") return "Employee code";
  if (key === "employeeId")
    return report === "coordinator-workload" ? "Coordinator" : "Employee";
  if (key === "ownerEmployeeId" || key === "caseOwnerEmployeeId")
    return "Case owner";
  if (key === "currentEmployeeId") return "Issued employee";
  if (role === "datetime") return `${heading} (Dubai)`;
  return heading;
}

const SUMMARY_LABELS: Record<string, string> = {
  totalCases: "Total cases",
  pendingApproval: "Pending approval",
  bookedCases: "Booked cases",
  completedCases: "Completed cases",
  rejectedCases: "Rejected cases",
  delayedCases: "Delayed cases",
  delayedMetricState: "Delayed metric",
  totalCustomers: "Total customers",
  newCustomers: "New customers",
  existingWithNewCases: "Existing with new cases",
  individualCustomers: "Individual customers",
  companyCustomers: "Company customers",
  employees: "Employees",
  createdCases: "Created cases",
  achievedCCPoints: "CC points",
  achievedPFAed: "PF AED",
  rankedEmployees: "Ranked employees",
  winnerEmployeeId: "Winner",
  decisionState: "Decision",
  coordinators: "Coordinators",
  recordCount: "Records",
  totalCommissionAed: "Total commission AED",
  totalAmountAed: "Total amount AED",
  totalCCPoints: "Total CC points",
  totalPFAed: "Total PF AED",
  salaryPaidAed: "Salary paid AED",
  commissionPaidAed: "Commission paid AED",
  totalPaidAed: "Total paid AED",
  presentCount: "Present",
  absentCount: "Absent",
  lateCount: "Late",
  availableCount: "Available",
  issuedCount: "Issued",
  maintenanceCount: "Maintenance",
  damagedCount: "Damaged",
  totalEmployees: "Total employees",
  activeEmployees: "Active employees",
  offboardedEmployees: "Offboarded employees",
  assignmentCount: "Assignments",
};

export function summaryLabel(key: string) {
  return (
    SUMMARY_LABELS[key] ??
    key
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .replace(/^./, (character) => character.toUpperCase())
  );
}

export type SummaryRole = "money" | "number" | "employee" | "text";

export function summaryRole(key: string): SummaryRole {
  if (key === "winnerEmployeeId") return "employee";
  if (key === "delayedMetricState" || key === "decisionState") return "text";
  if (isMoneyField(key)) return "money";
  return "number";
}

const ACCESS_STATUSES = ["Not Provisioned", "Active", "Disabled"];
const CUSTOMER_TYPES = ["Individual", "Company"];
const ATTENDANCE_STATUSES = ["Present", "Absent"];

const options = (values: readonly string[]): SelectOption[] =>
  values.map((value) => ({ value, label: value }));

export function fixedOptions(
  report: string,
  key: PanelFilter,
): SelectOption[] | null {
  if (key === "customerType") return options(CUSTOMER_TYPES);
  if (key === "accessStatus") return options(ACCESS_STATUSES);
  if (key === "category") return options(ASSET_CATEGORIES);
  if (key === "status") {
    if (report === "case-pipeline") return options(CASE_STATUSES);
    if (report === "attendance") return options(ATTENDANCE_STATUSES);
    if (report === "assets") return options(ASSET_STATUSES);
    return options(EMPLOYEE_STATUSES);
  }
  return null;
}

export const FILTER_LABEL: Record<PanelFilter | "productCode", string> = {
  branchId: "Branch",
  departmentId: "Department",
  teamId: "Team",
  employeeId: "Employee",
  designationId: "Designation",
  bankId: "Bank",
  productCode: "Product",
  customerType: "Customer type",
  status: "Status",
  accessStatus: "Access status",
  category: "Category",
};

export function filterLabel(report: string, key: PanelFilter) {
  if (key === "employeeId" && report === "assets") return "Issued employee";
  if (
    key === "status" &&
    (report === "hr-employees" || report === "hr-assignments")
  )
    return "Employee status";
  return FILTER_LABEL[key];
}

export function teamChoicePath(role: Designation | undefined) {
  return role === "Sales Manager" || role === "Finance"
    ? "/reports/choices/teams"
    : "/teams";
}
