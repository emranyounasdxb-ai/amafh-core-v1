import type { PageId } from "../../access";

export type AppRoute = { page: PageId; recordId?: string };

const paths: Record<
  Exclude<PageId, "case-detail" | "performance-detail">,
  string
> = {
  dashboard: "/dashboard",
  "my-profile": "/me",
  "my-wallet": "/my-wallet",
  "my-cases": "/my-cases",
  tasks: "/tasks",
  notifications: "/notifications",
  cases: "/cases",
  "bank-stage-updates": "/bank-stage-updates",
  customers: "/customers",
  employees: "/employees",
  "hr-packages": "/hr/packages",
  "hr-documents": "/hr/documents",
  "hr-visa": "/hr/visa",
  "hr-letters": "/hr/letters",
  "hr-certificates": "/hr/certificates",
  "hr-offboarding": "/hr/offboarding",
  organization: "/organization",
  teams: "/teams",
  performance: "/performance",
  attendance: "/attendance",
  assets: "/assets",
  finance: "/finance",
  reports: "/reports",
  settings: "/settings",
};

const recordPages: readonly PageId[] = [
  "bank-stage-updates",
  "customers",
  "employees",
  "teams",
  "attendance",
  "assets",
  "settings",
];

export function routePath(route: AppRoute): string {
  if (route.page === "case-detail")
    return `/cases/${encodeURIComponent(route.recordId ?? "")}`;
  if (route.page === "performance-detail")
    return `/performance/${encodeURIComponent(route.recordId ?? "")}`;
  if (route.recordId && recordPages.includes(route.page))
    return `${paths[route.page as keyof typeof paths]}/${encodeURIComponent(route.recordId)}`;
  return paths[route.page];
}

export function isDesignSystemPath(pathname: string): boolean {
  const path = pathname.replace(/\/+$/, "") || "/";
  return path === "/design-system";
}

export function parseAppRoute(pathname: string): AppRoute | null {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (isDesignSystemPath(path)) return null;
  if (path === "/") return { page: "dashboard" };
  const simple = Object.entries(paths).find(([, value]) => value === path);
  if (simple) return { page: simple[0] as PageId };
  const parts = path.split("/").filter(Boolean);
  if (parts.length !== 2) return null;
  try {
    const recordId = decodeURIComponent(parts[1]);
    if (!recordId) return null;
    if (parts[0] === "cases") return { page: "case-detail", recordId };
    if (parts[0] === "performance")
      return { page: "performance-detail", recordId };
    const detailPage = recordPages.find(
      (page) => paths[page as keyof typeof paths] === `/${parts[0]}`,
    );
    if (detailPage) return { page: detailPage, recordId };
  } catch {
    return null;
  }
  return null;
}
