import { choices } from "../../app/api/choices";
import type { ApiClient } from "../../app/api/http";
import type { EmployeeSummary, NamedRecord } from "../../app/api/models";
import type {
  OrganizationContext,
  OrganizationTeam,
} from "./organizationLayout";
import type { OrganizationEmployee } from "./organizationTree";

export type OrganizationChart = OrganizationContext & {
  employees: OrganizationEmployee[];
};

export async function readOrganizationChart(
  api: ApiClient,
  path: string,
  signal: AbortSignal,
): Promise<OrganizationChart> {
  const [hierarchy, assignments, branches, departments, teams] =
    await Promise.all([
      api.request<{ employees: OrganizationEmployee[] }>(path, { signal }),
      choices<EmployeeSummary>(api, "/employees?status=Active", signal),
      api.request<NamedRecord[]>("/branches", { signal }),
      api.request<NamedRecord[]>("/departments", { signal }),
      choices<OrganizationTeam>(api, "/teams", signal),
    ]);
  return { ...hierarchy, assignments, branches, departments, teams };
}
