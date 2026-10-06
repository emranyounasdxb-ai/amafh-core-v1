import type { EmployeeSummary, NamedRecord } from "../../app/api/models";
import type { OrganizationNode } from "./organizationTree";

export type OrganizationTeam = {
  id: string;
  name: string;
  branch_id: string;
  department_id: string;
  leader_employee_id: string;
  active: boolean;
};
export type OrganizationContext = {
  assignments: EmployeeSummary[];
  branches: NamedRecord[];
  departments: NamedRecord[];
  teams: OrganizationTeam[];
};

export function employeeScope(id: string, context: OrganizationContext) {
  const assignment = context.assignments.find((employee) => employee.id === id);
  return {
    branch:
      context.branches.find((branch) => branch.id === assignment?.branchId)
        ?.name || "Branch unavailable",
    department:
      context.departments.find(
        (department) => department.id === assignment?.departmentId,
      )?.name || "Department unavailable",
  };
}

export function orderedSalesManagers(
  nodes: OrganizationNode[],
  context: OrganizationContext,
) {
  const branchOrder = (name: string) => {
    const index = ["Dubai", "Abu Dhabi"].indexOf(name);
    return index < 0 ? 2 : index;
  };
  return nodes
    .filter((node) => node.employee.designation === "Sales Manager")
    .sort((left, right) => {
      const a = employeeScope(left.employee.id, context);
      const b = employeeScope(right.employee.id, context);
      return (
        branchOrder(a.branch) - branchOrder(b.branch) ||
        a.branch.localeCompare(b.branch) ||
        a.department.localeCompare(b.department) ||
        left.employee.fullName.localeCompare(right.employee.fullName) ||
        left.employee.id.localeCompare(right.employee.id)
      );
    });
}

export function leaderTeams(
  leader: OrganizationNode,
  teams: OrganizationTeam[],
) {
  const assigned = teams
    .filter(
      (team) => team.active && team.leader_employee_id === leader.employee.id,
    )
    .sort((a, b) => a.name.localeCompare(b.name));
  // Team membership labels never replace the retained reporting parent.
  const groups = assigned.map((team) => ({
    id: team.id,
    name: team.name,
    members: leader.children.filter(
      (child) => child.employee.teamId === team.id,
    ),
  }));
  const grouped = new Set(
    groups.flatMap((group) => group.members.map((node) => node.employee.id)),
  );
  const other = leader.children.filter(
    (child) => !grouped.has(child.employee.id),
  );
  return { groups, other };
}
