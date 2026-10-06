import type { HierarchyNodeData } from "../../design-system";
import {
  employeeScope,
  leaderTeams,
  orderedSalesManagers,
  type OrganizationContext,
} from "./organizationLayout";
import {
  buildOrganizationTree,
  type OrganizationEmployee,
  type OrganizationNode,
} from "./organizationTree";

export type Expansion = {
  rootClosed: boolean;
  financeClosed: boolean;
  branchId: string | null;
  managerId: string | null;
  teams: boolean;
  leaderId: string | null;
};

export const collapsed: Expansion = {
  rootClosed: false,
  financeClosed: false,
  branchId: null,
  managerId: null,
  teams: false,
  leaderId: null,
};

function avatarSrc(employee: OrganizationEmployee) {
  return employee.avatarFileId
    ? `/api/v1/employees/${encodeURIComponent(employee.id)}/media/avatar?v=${encodeURIComponent(employee.avatarFileId)}`
    : undefined;
}

function person(
  prefix: "root" | "person" | "manager" | "leader",
  node: OrganizationNode,
  extra: Partial<HierarchyNodeData> = {},
): HierarchyNodeData {
  const { employee } = node;
  const expandable = Boolean(extra.children?.length);
  return {
    id: `${prefix}:${employee.id}`,
    name: employee.fullName,
    subtitle: employee.designation,
    kind: "person",
    avatarSrc: avatarSrc(employee),
    activateLabel: expandable
      ? `${employee.fullName} hierarchy`
      : `Open ${employee.fullName} Performance detail`,
    actionLabel: expandable
      ? `View Performance for ${employee.fullName}`
      : undefined,
    actionIcon: "performance",
    ...extra,
  };
}

function branchesFor(
  director: OrganizationNode,
  managers: OrganizationNode[],
  context: OrganizationContext,
) {
  const order = (name: string) =>
    name === "Dubai" ? 0 : name === "Abu Dhabi" ? 1 : 2;
  const managerBranch = (manager: OrganizationNode) =>
    context.assignments.find((item) => item.id === manager.employee.id)
      ?.branchId;
  return context.branches
    .filter((branch) =>
      managers.some((manager) => managerBranch(manager) === branch.id),
    )
    .sort(
      (left, right) =>
        order(left.name) - order(right.name) ||
        left.name.localeCompare(right.name),
    )
    .map((branch) => ({
      key: `${director.employee.id}:${branch.id}`,
      name: branch.name,
      managers: managers.filter(
        (manager) => managerBranch(manager) === branch.id,
      ),
    }));
}

function leaderNode(leader: OrganizationNode, context: OrganizationContext) {
  const { groups, other } = leaderTeams(leader, context.teams);
  const members = [
    ...groups.flatMap((team) =>
      team.members.map((member) =>
        person("person", member, { status: team.name }),
      ),
    ),
    ...other.map((member) => person("person", member)),
  ];
  return person("leader", leader, {
    status: groups.map((team) => team.name).join(", ") || undefined,
    children: members,
  });
}

function managerNode(manager: OrganizationNode, context: OrganizationContext) {
  const staff = manager.children.filter((node) =>
    ["Coordinator", "Admin Staff"].includes(node.employee.designation),
  );
  const leaders = manager.children.filter(
    (node) => node.employee.designation === "Team Leader",
  );
  const scope = employeeScope(manager.employee.id, context);
  const children: HierarchyNodeData[] = staff.map((node) =>
    person("person", node),
  );
  if (leaders.length)
    children.push({
      id: `teams:${manager.employee.id}`,
      name: "Teams",
      kind: "group",
      count: leaders.length,
      activateLabel: `${manager.employee.fullName} Teams`,
      children: leaders.map((leader) => leaderNode(leader, context)),
    });
  return person("manager", manager, {
    subtitle: `${manager.employee.designation} · ${scope.department}`,
    children,
  });
}

export function organizationHierarchy(
  employees: OrganizationEmployee[],
  context: OrganizationContext,
): HierarchyNodeData[] {
  return buildOrganizationTree(employees)
    .filter((node) => node.employee.designation === "Managing Director")
    .map((director) => {
      const finance = director.children.filter(
        (node) => node.employee.designation === "Finance",
      );
      const managers = orderedSalesManagers(director.children, context);
      const children: HierarchyNodeData[] = [];
      if (finance.length)
        children.push({
          id: `finance:${director.employee.id}`,
          name: "Finance Manager",
          kind: "group",
          count: finance.length,
          activateLabel: "Finance Manager",
          children: finance.map((node) => person("person", node)),
        });
      for (const branch of branchesFor(director, managers, context))
        children.push({
          id: `branch:${branch.key}`,
          name: `${branch.name} Branch`,
          kind: "group",
          count: branch.managers.length,
          activateLabel: `${branch.name} Branch hierarchy`,
          children: branch.managers.map((manager) =>
            managerNode(manager, context),
          ),
        });
      return person("root", director, { root: true, children });
    });
}

export function expandedIds(nodes: HierarchyNodeData[], expansion: Expansion) {
  const ids: string[] = [];
  for (const root of nodes) {
    if (!expansion.rootClosed) ids.push(root.id);
    const directorId = root.id.slice("root:".length);
    if (!expansion.financeClosed) ids.push(`finance:${directorId}`);
  }
  if (expansion.branchId) ids.push(`branch:${expansion.branchId}`);
  if (expansion.managerId) {
    ids.push(`manager:${expansion.managerId}`);
    if (expansion.teams) ids.push(`teams:${expansion.managerId}`);
  }
  if (expansion.leaderId) ids.push(`leader:${expansion.leaderId}`);
  return ids;
}

export function toggleExpansion(current: Expansion, id: string): Expansion {
  const [kind, ...rest] = id.split(":");
  const value = rest.join(":");
  switch (kind) {
    case "root":
      return { ...current, rootClosed: !current.rootClosed };
    case "finance":
      return { ...current, financeClosed: !current.financeClosed };
    case "branch":
      return {
        ...collapsed,
        rootClosed: current.rootClosed,
        financeClosed: current.financeClosed,
        branchId: current.branchId === value ? null : value,
      };
    case "manager":
      return {
        ...current,
        managerId: current.managerId === value ? null : value,
        teams: false,
        leaderId: null,
      };
    case "teams":
      return { ...current, teams: !current.teams, leaderId: null };
    case "leader":
      return {
        ...current,
        leaderId: current.leaderId === value ? null : value,
      };
    default:
      return current;
  }
}

export function hierarchyEmployeeId(id: string) {
  const [kind, ...rest] = id.split(":");
  return ["root", "person", "manager", "leader"].includes(kind)
    ? rest.join(":")
    : null;
}

export function activeContextId(expansion: Expansion) {
  if (expansion.leaderId) return `leader:${expansion.leaderId}`;
  if (expansion.managerId)
    return expansion.teams
      ? `teams:${expansion.managerId}`
      : `manager:${expansion.managerId}`;
  return expansion.branchId ? `branch:${expansion.branchId}` : null;
}
