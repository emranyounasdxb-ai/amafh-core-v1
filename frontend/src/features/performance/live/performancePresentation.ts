import {
  addDays,
  dubaiTodayDateOnly,
  formatCompactDateRange,
  type DateOnly,
  type DateRangePreset,
  type PerformanceMetric,
} from "../../../design-system";
import { isUuid } from "../../../app/presentation/labels";
import type { Designation } from "../../../access";

export type PerformanceView =
  | "employees"
  | "rankings"
  | "team"
  | "workload"
  | "comparisons";

export function performanceViews(role: Designation): PerformanceView[] {
  if (role === "Owner" || role === "Managing Director")
    return ["employees", "rankings", "team", "workload", "comparisons"];
  if (role === "Team Leader") return ["employees", "rankings", "team"];
  if (role === "Sales Manager") return ["employees", "rankings"];
  return [];
}

export type OverviewState = {
  view: PerformanceView;
  draft: PerformanceFilters;
  search: string;
  page: number;
  pageSize: number;
  sort: { key: string; direction: "asc" | "desc" } | null;
};

export const productOptions = [
  { value: "CC", label: "Credit Card", description: "CC" },
  { value: "PF", label: "Personal Finance", description: "PF" },
];

export type Product = "CC" | "PF";
export const PRODUCTS: readonly Product[] = ["CC", "PF"];
export const PRODUCT_LABEL: Record<Product, string> = {
  CC: "Credit Card",
  PF: "Personal Finance",
};
export const PRODUCT_COLOR: Record<Product, string> = {
  CC: "var(--ds-chart-1)",
  PF: "var(--ds-chart-5)",
};

export type TargetProgress = {
  state: "Configured" | "No Target";
  achieved: string;
  achievementPercentage: string | null;
  activeOnEndDate?: boolean;
};

export type PerformanceSummaryValues = {
  createdCaseCount: number;
  bookedCaseCount: number;
  completedCaseCount: number;
  rejectedCaseCount: number;
  inProgressCaseCount: number;
  inProgressByStage: Record<string, number>;
  delayedCaseCount: number | null;
  delayedMetricState: "Available" | "Holiday calendar unavailable";
  achievedCCPoints: string;
  achievedPFAed: string;
  targetProgress: Partial<Record<Product, TargetProgress>>;
};

export type EmployeeIdentity = {
  employeeName?: string | null;
  systemEmployeeCode?: string | null;
  companyEmployeeCode?: string | null;
  designation?: string | null;
  branchName?: string | null;
  departmentName?: string | null;
  avatarFileId?: string | null;
};

export type EmployeeMetrics = PerformanceSummaryValues &
  EmployeeIdentity & {
    employeeId: string;
    startDate: DateOnly;
    endDate: DateOnly;
  };

export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
};

export type EmployeePage = Page<EmployeeMetrics> & {
  summary?: PerformanceSummaryValues | null;
};
export type RankingItem = {
  employeeId: string;
  employeeName: string;
  achievementPercentage: string;
  completedCaseCount: number;
  achievedValue: string;
  rank: number;
};
export type RankingPage = Page<RankingItem> & {
  winnerEmployeeId: string | null;
  decisionState:
    | "No eligible employees"
    | "Confirmed"
    | "Owner decision pending"
    | "Automatic";
  tiedCandidateIds: string[];
  confirmedAt: string | null;
};

export type ComparisonItem = PerformanceSummaryValues & {
  id: string;
  name: string;
};
export type ComparisonPage = Page<ComparisonItem> & {
  groupBy: "branch" | "department";
};

export type CoordinatorItem = EmployeeIdentity & {
  employeeId: string;
  handledCases: number;
  submittedBookedCases: number;
  stageUpdatedCases: number;
};

export type TrendValues = {
  createdCaseCount: number;
  bookedCaseCount: number;
  completedCaseCount: number;
  achieved: string;
  achievementPercentage: string | null;
};
export type EmployeeTrend = {
  employeeId: string;
  startDate: DateOnly;
  endDate: DateOnly;
  items: {
    start: DateOnly;
    end: DateOnly;
    label: string;
    CC: TrendValues | null;
    PF: TrendValues | null;
  }[];
};

export type PerformanceFilters = {
  startDate: DateOnly | "";
  endDate: DateOnly | "";
  branchId: string;
  departmentId: string;
  teamId: string;
  designationId: string;
  groupBy: "branch" | "department";
};

export const emptyFilters: PerformanceFilters = {
  startDate: "",
  endDate: "",
  branchId: "",
  departmentId: "",
  teamId: "",
  designationId: "",
  groupBy: "branch",
};

export function amount(value: string | number | null | undefined) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function percentage(value: string | null | undefined) {
  if (value == null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function performanceQuery(
  filters: PerformanceFilters,
  product: Product | "",
  extra: Record<string, string | number | undefined> = {},
  scope: { branch?: boolean; team?: boolean } = {},
) {
  const query = new URLSearchParams();
  if (filters.startDate && filters.endDate) {
    query.set("startDate", filters.startDate);
    query.set("endDate", filters.endDate);
  }
  if (product) query.set("productCode", product);
  if (scope.branch) {
    if (filters.branchId) query.set("branchId", filters.branchId);
    if (filters.departmentId) query.set("departmentId", filters.departmentId);
    if (filters.designationId)
      query.set("designationId", filters.designationId);
  }
  if (scope.team && filters.teamId) query.set("teamId", filters.teamId);
  for (const [key, value] of Object.entries(extra))
    if (value !== undefined && value !== "") query.set(key, String(value));
  return query.toString();
}

export function readable(value: string | null | undefined) {
  const label = value?.trim();
  return label && !isUuid(label) ? label : "";
}

export function personName(identity: EmployeeIdentity) {
  return readable(identity.employeeName) || "Team member";
}

export function personCode(identity: EmployeeIdentity) {
  return (
    readable(identity.companyEmployeeCode) ||
    readable(identity.systemEmployeeCode)
  );
}

export function periodLabel(start?: string, end?: string) {
  return start && end ? formatCompactDateRange(start, end) : "All time";
}

export function datePresets(): DateRangePreset[] {
  const today = dubaiTodayDateOnly();
  return [
    { id: "month", label: "This month", range: { start: `${today.slice(0, 8)}01`, end: today } },
    { id: "30", label: "Last 30 days", range: { start: addDays(today, -29), end: today } },
    { id: "90", label: "Last 90 days", range: { start: addDays(today, -89), end: today } },
    { id: "custom", label: "Custom", range: { start: "", end: "" } },
  ];
}

export function metricCards(
  summary: PerformanceSummaryValues,
  product: Product | "",
): PerformanceMetric[] {
  const scope = product ? PRODUCT_LABEL[product] : "All products";
  const cards: PerformanceMetric[] = [
    {
      id: "created",
      label: "Cases created",
      value: summary.createdCaseCount,
      meta: scope,
    },
    {
      id: "booked",
      label: "Booked",
      value: summary.bookedCaseCount,
      meta: `${summary.inProgressCaseCount} in progress`,
    },
    {
      id: "completed",
      label: "Completed",
      value: summary.completedCaseCount,
      meta: `${summary.rejectedCaseCount} rejected`,
    },
  ];
  if (product !== "PF")
    cards.push({
      id: "cc-points",
      label: "CC points",
      value: amount(summary.achievedCCPoints),
      kind: "points",
      meta: "Credit Card achieved",
    });
  if (product !== "CC")
    cards.push({
      id: "pf-amount",
      label: "PF amount",
      value: amount(summary.achievedPFAed),
      kind: "amount",
      currency: "AED",
      meta: "Personal Finance achieved",
    });
  return cards;
}

export function valuesState<S extends string>(state: S, values: number[]) {
  return state === "ready" && !values.some((value) => value !== 0)
    ? ("empty" as const)
    : state;
}

export function outcomeSeries(summary: PerformanceSummaryValues) {
  return {
    labels: ["Created", "Booked", "Completed", "Rejected", "In progress"],
    values: [
      summary.createdCaseCount,
      summary.bookedCaseCount,
      summary.completedCaseCount,
      summary.rejectedCaseCount,
      summary.inProgressCaseCount,
    ],
  };
}

export function stageSeries(summary: PerformanceSummaryValues) {
  const entries = Object.entries(summary.inProgressByStage ?? {}).filter(
    ([, count]) => count > 0,
  );
  return {
    labels: entries.map(([stage]) => stage),
    values: entries.map(([, count]) => count),
  };
}