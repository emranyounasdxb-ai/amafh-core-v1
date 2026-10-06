import type { AccessSession, PageId } from "../../access";
import { canOpenPage } from "../../access";

const destinationResources: Record<string, PageId> = {
  cases: "case-detail",
  tasks: "tasks",
  employees: "employees",
  teams: "teams",
  customers: "customers",
  assets: "assets",
  attendance: "attendance",
};

export function apiPathFromDestination(path: string) {
  if (!path.startsWith("/api/v1/")) return "";
  return path.slice("/api/v1".length);
}

export function destinationPageForResource(resource: string): PageId | null {
  return destinationResources[resource] ?? null;
}

export function routeFromApiPath(
  path: string,
  session: AccessSession,
): { page: PageId; recordId?: string } | null {
  const relative = apiPathFromDestination(path);
  if (!relative) return null;
  const parts = relative.split("/").filter(Boolean);
  if (
    parts[0] === "case-imports" &&
    parts[1] === "bank-stage" &&
    parts[2] &&
    canOpenPage(session, "bank-stage-updates")
  ) {
    return { page: "bank-stage-updates", recordId: parts[2] };
  }
  const page = destinationPageForResource(parts[0] ?? "");
  if (!page || !parts[1] || !canOpenPage(session, page)) return null;
  return { page, recordId: parts[1] };
}
