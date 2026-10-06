import { useEffect, useState } from "react";
import type { PageId } from "../../access";
import { parseAppRoute, routePath, type AppRoute } from "./routes";

export type CaseDetailOrigin =
  | "cases"
  | "customers"
  | "my-cases"
  | "my-wallet"
  | "notifications"
  | "tasks";

export type HrPageId =
  | "hr-packages"
  | "hr-documents"
  | "hr-visa"
  | "hr-letters"
  | "hr-certificates"
  | "hr-offboarding";
export type EmployeeSection = "packages" | "documents" | "visa" | "letters";

export type AppNavigationState = {
  performanceDetailOrigin?: "organization" | "performance";
  caseDetailOrigin?: CaseDetailOrigin;
  sessionEmployeeId?: string;
  openTaskId?: string;
  openTaskNonce?: number;
  employeeOrigin?: HrPageId;
  employeeSection?: EmployeeSection;
};

const HR_PAGES: readonly HrPageId[] = [
  "hr-packages",
  "hr-documents",
  "hr-visa",
  "hr-letters",
  "hr-certificates",
  "hr-offboarding",
];
const EMPLOYEE_SECTIONS: readonly EmployeeSection[] = [
  "packages",
  "documents",
  "visa",
  "letters",
];

export function taskNavigation(openTaskId: string): AppNavigationState {
  return { openTaskId, openTaskNonce: Date.now() };
}

export function employeeSectionNavigation(
  origin: HrPageId,
  section?: EmployeeSection,
): AppNavigationState {
  return section
    ? { employeeOrigin: origin, employeeSection: section }
    : { employeeOrigin: origin };
}

export function caseDetailNavigation(
  origin: CaseDetailOrigin,
): AppNavigationState {
  return { caseDetailOrigin: origin };
}

function isCaseDetailOrigin(value: unknown): value is CaseDetailOrigin {
  return (
    value === "cases" ||
    value === "customers" ||
    value === "my-cases" ||
    value === "my-wallet" ||
    value === "notifications" ||
    value === "tasks"
  );
}

function readNavigationState(): AppNavigationState | null {
  const state = window.history.state;
  if (!state || typeof state !== "object") return null;
  const origin = (state as AppNavigationState).performanceDetailOrigin;
  const caseDetailOrigin = (state as AppNavigationState).caseDetailOrigin;
  const sessionEmployeeId = (state as AppNavigationState).sessionEmployeeId;
  const openTaskId = (state as AppNavigationState).openTaskId;
  const openTaskNonce = (state as AppNavigationState).openTaskNonce;
  const employeeOrigin = (state as AppNavigationState).employeeOrigin;
  const employeeSection = (state as AppNavigationState).employeeSection;
  const next: AppNavigationState = {};
  if (employeeOrigin && HR_PAGES.includes(employeeOrigin))
    next.employeeOrigin = employeeOrigin;
  if (employeeSection && EMPLOYEE_SECTIONS.includes(employeeSection))
    next.employeeSection = employeeSection;
  if (origin === "organization" || origin === "performance")
    next.performanceDetailOrigin = origin;
  if (isCaseDetailOrigin(caseDetailOrigin))
    next.caseDetailOrigin = caseDetailOrigin;
  if (typeof sessionEmployeeId === "string")
    next.sessionEmployeeId = sessionEmployeeId;
  if (typeof openTaskId === "string" && openTaskId) next.openTaskId = openTaskId;
  if (typeof openTaskNonce === "number" && Number.isFinite(openTaskNonce))
    next.openTaskNonce = openTaskNonce;
  return Object.keys(next).length ? next : null;
}

export function useAppRoute() {
  const [route, setRoute] = useState<AppRoute | null>(() =>
    parseAppRoute(window.location.pathname),
  );
  const [navigationState, setNavigationState] =
    useState<AppNavigationState | null>(readNavigationState);
  useEffect(() => {
    const onPopState = () => {
      setRoute(parseAppRoute(window.location.pathname));
      setNavigationState(readNavigationState());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  const navigate = (
    page: PageId,
    recordId?: string,
    state: AppNavigationState | null = null,
  ) => {
    const next = { page, recordId };
    window.history.pushState(state, "", routePath(next));
    setRoute(next);
    setNavigationState(state);
  };
  return {
    route,
    navigationState,
    navigate,
    back: () => window.history.back(),
  };
}
