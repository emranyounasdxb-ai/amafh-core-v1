import type { PageId } from "../../access";
import type { DsIconName } from "../../design-system";

export type ProductionNavItem = {
  id: PageId;
  label: string;
  icon: DsIconName;
};

export type ProductionNavGroup = {
  id: string;
  label: string;
  items: ProductionNavItem[];
};

export const sidebarGroups: ProductionNavGroup[] = [
  {
    id: "main",
    label: "Main",
    items: [
      { id: "dashboard", label: "Dashboard", icon: "dashboard" },
      { id: "tasks", label: "Tasks", icon: "tasks" },
      { id: "my-cases", label: "Own Cases", icon: "cases" },
      { id: "my-wallet", label: "My Wallet", icon: "finance" },
    ],
  },
  {
    id: "sales",
    label: "Sales",
    items: [
      { id: "cases", label: "Cases", icon: "cases" },
      { id: "bank-stage-updates", label: "Bank Stage Updates", icon: "csv" },
      { id: "customers", label: "Customers", icon: "customers" },
    ],
  },
  {
    id: "hr",
    label: "HR & PRO",
    items: [
      { id: "employees", label: "Employees", icon: "employees" },
      { id: "hr-packages", label: "Packages", icon: "finance" },
      { id: "hr-documents", label: "Documents", icon: "pdf" },
      { id: "hr-visa", label: "Visa / PRO", icon: "administration" },
      { id: "hr-letters", label: "Letters", icon: "mail" },
      { id: "hr-certificates", label: "Certificates", icon: "audit" },
      { id: "hr-offboarding", label: "Offboarding", icon: "signOut" },
    ],
  },
  {
    id: "administration",
    label: "Administration",
    items: [
      { id: "organization", label: "Organization", icon: "organization" },
      { id: "teams", label: "Teams", icon: "team" },
      { id: "attendance", label: "Attendance", icon: "attendance" },
      { id: "assets", label: "Assets", icon: "assets" },
    ],
  },
  {
    id: "performance",
    label: "Performance",
    items: [{ id: "performance", label: "Performance", icon: "performance" }],
  },
  {
    id: "finance",
    label: "Finance",
    items: [{ id: "finance", label: "Finance", icon: "finance" }],
  },
  {
    id: "reports",
    label: "Reports",
    items: [{ id: "reports", label: "Reports", icon: "reports" }],
  },
  {
    id: "settings",
    label: "Settings",
    items: [{ id: "settings", label: "Settings", icon: "settings" }],
  },
];

export const pageTitles: Record<PageId, string> = {
  dashboard: "Dashboard",
  "my-profile": "My profile",
  "my-wallet": "My Wallet",
  "my-cases": "Own Cases",
  tasks: "Tasks",
  notifications: "Notifications",
  cases: "Cases",
  "case-detail": "Case",
  "bank-stage-updates": "Bank Stage Updates",
  customers: "Customers",
  employees: "Employees",
  "hr-packages": "Packages",
  "hr-documents": "Documents",
  "hr-visa": "Visa / PRO",
  "hr-letters": "Letters",
  "hr-certificates": "Certificates",
  "hr-offboarding": "Offboarding",
  organization: "Organization",
  teams: "Teams",
  performance: "Performance",
  "performance-detail": "Performance",
  attendance: "Attendance",
  assets: "Assets",
  finance: "Finance",
  reports: "Reports",
  settings: "Settings",
};

export function sidebarActiveId(
  page: PageId,
  employeeOrigin?: PageId,
  caseDetailOrigin?: PageId,
): string {
  if (page === "case-detail")
    return caseDetailOrigin === "my-cases" ? "my-cases" : "cases";
  if (page === "performance-detail") return "performance";
  if (page === "employees" && employeeOrigin) return employeeOrigin;
  return page;
}
