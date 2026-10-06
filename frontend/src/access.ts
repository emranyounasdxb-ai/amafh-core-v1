export type Designation =
  | "Owner"
  | "Managing Director"
  | "Sales Manager"
  | "Coordinator"
  | "Team Leader"
  | "Sales Executive"
  | "Admin Staff"
  | "HR"
  | "Finance";
export type PreviewRole = Designation;
export type PageId =
  | "dashboard"
  | "my-profile"
  | "my-wallet"
  | "my-cases"
  | "tasks"
  | "notifications"
  | "cases"
  | "case-detail"
  | "bank-stage-updates"
  | "customers"
  | "employees"
  | "hr-packages"
  | "hr-documents"
  | "hr-visa"
  | "hr-letters"
  | "hr-certificates"
  | "hr-offboarding"
  | "organization"
  | "teams"
  | "performance"
  | "performance-detail"
  | "attendance"
  | "assets"
  | "finance"
  | "reports"
  | "settings";

export const lockedDesignations: readonly Designation[] = [
  "Owner",
  "Managing Director",
  "Sales Manager",
  "Coordinator",
  "Team Leader",
  "Sales Executive",
  "Admin Staff",
  "HR",
  "Finance",
];

/** The signed-in user's User Type and the effective permissions returned by the server. */
export type AccessSession = {
  designation: Designation;
  permissions: readonly string[];
};

function has(session: AccessSession, permission: string) {
  return session.permissions.includes(permission);
}

// Module entry without a permission key follows the fixed business-role boundary,
// mirroring the server's fixed designation checks for these modules.
const PERFORMANCE_MODULE: readonly Designation[] = [
  "Owner",
  "Managing Director",
  "Sales Manager",
  "Team Leader",
  "Sales Executive",
];
const EMPLOYEE_MODULE: readonly Designation[] = [
  "Owner",
  "Managing Director",
  "HR",
  "Finance",
];
const SETTINGS_MODULE: readonly Designation[] = [
  "Owner",
  "Managing Director",
  "Finance",
];
// Fixed business-role boundary for Case creation; a permission override cannot widen it.
const CASE_CREATORS: readonly Designation[] = [
  "Sales Executive",
  "Team Leader",
  "Sales Manager",
  "Coordinator",
  "Admin Staff",
];
const FINANCE_LEDGERS: readonly Designation[] = [
  "Owner",
  "Managing Director",
  "Finance",
];

// HR & PRO entries open Employee Detail sections, so they also need the Employees module.
function hrEntry(session: AccessSession, permission: string) {
  return (
    has(session, permission) &&
    has(session, "employee.read") &&
    EMPLOYEE_MODULE.includes(session.designation)
  );
}

export function canOpenPage(session: AccessSession, page: PageId) {
  switch (page) {
    case "dashboard":
    case "my-profile":
    case "my-wallet":
    case "my-cases":
    case "case-detail":
    case "tasks":
    case "notifications":
      return true;
    case "cases":
      return has(session, "case.read");
    case "bank-stage-updates":
      return has(session, "case.csv");
    case "customers":
      return has(session, "customer.read");
    case "employees":
      return (
        has(session, "employee.read") &&
        EMPLOYEE_MODULE.includes(session.designation)
      );
    case "hr-packages":
      return hrEntry(session, "package.read");
    case "hr-documents":
      return hrEntry(session, "employee_document.read");
    case "hr-visa":
      return hrEntry(session, "visa.read");
    case "hr-letters":
    case "hr-certificates":
      return hrEntry(session, "hr_letter.read");
    case "hr-offboarding":
      return hrEntry(session, "employee.write");
    case "organization":
      return has(session, "organization.read");
    case "teams":
      return has(session, "team.write");
    case "performance":
    case "performance-detail":
      return PERFORMANCE_MODULE.includes(session.designation);
    case "attendance":
      return has(session, "attendance.write");
    case "assets":
      return has(session, "asset.write");
    case "finance":
      return has(session, "finance.read");
    case "reports":
      return has(session, "report.read");
    case "settings":
      return SETTINGS_MODULE.includes(session.designation);
  }
}
export function canImportBankStages(session: AccessSession) {
  return has(session, "case.csv");
}
export function canCreateCase(session: AccessSession) {
  return (
    has(session, "case.create") &&
    CASE_CREATORS.includes(session.designation)
  );
}
export function canApproveCases(session: AccessSession) {
  return has(session, "case.approve");
}
export function canBookCases(session: AccessSession) {
  return has(session, "case.book");
}
export function canManageEmployees(session: AccessSession) {
  return has(session, "employee.write");
}
export function canManageTeams(session: AccessSession) {
  return has(session, "team.write");
}
export function canManageFinance(session: AccessSession) {
  return has(session, "finance.write");
}
/** Points wallets and financial rules are readable only by the fixed finance roles. */
export function canViewFinanceLedgers(session: AccessSession) {
  return has(session, "finance.read") && FINANCE_LEDGERS.includes(session.designation);
}
export function canManageAssets(session: AccessSession) {
  return has(session, "asset.write");
}
export function canManageAttendance(session: AccessSession) {
  return has(session, "attendance.write");
}
export function canViewAudit(session: AccessSession) {
  return has(session, "audit.read");
}
export function hasPermission(session: AccessSession, permission: string) {
  return has(session, permission);
}
