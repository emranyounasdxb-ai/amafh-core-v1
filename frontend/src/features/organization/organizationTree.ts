import type { Designation } from "../../access";

export type OrganizationEmployee = {
  id: string;
  fullName: string;
  designation: Designation;
  reportingManagerId: string | null;
  avatarFileId: string | null;
  teamId: string | null;
  teamLeaderId: string | null;
};

export type OrganizationNode = {
  employee: OrganizationEmployee;
  relationship: "reports" | "team" | null;
  children: OrganizationNode[];
};

const displayedRoles = new Set<Designation>([
  "Managing Director",
  "Sales Manager",
  "Coordinator",
  "Admin Staff",
  "Team Leader",
  "Sales Executive",
  "Finance",
]);

const roleOrder: Partial<Record<Designation, number>> = {
  "Managing Director": 0,
  "Sales Manager": 1,
  Coordinator: 2,
  "Admin Staff": 3,
  "Team Leader": 4,
  "Sales Executive": 5,
  Finance: 6,
};

function compare(left: OrganizationNode, right: OrganizationNode) {
  return (
    (roleOrder[left.employee.designation] ?? 99) -
      (roleOrder[right.employee.designation] ?? 99) ||
    left.employee.fullName.localeCompare(right.employee.fullName) ||
    left.employee.id.localeCompare(right.employee.id)
  );
}

export function buildOrganizationTree(employees: OrganizationEmployee[]) {
  const nodes = new Map(
    employees
      .filter((employee) => displayedRoles.has(employee.designation))
      .map((employee) => [
        employee.id,
        { employee, relationship: null, children: [] } as OrganizationNode,
      ]),
  );
  const parents = new Map<
    string,
    { id: string; relationship: "reports" | "team" }
  >();
  for (const node of nodes.values()) {
    const employee = node.employee;
    if (employee.reportingManagerId && nodes.has(employee.reportingManagerId)) {
      parents.set(employee.id, {
        id: employee.reportingManagerId,
        relationship: "reports",
      });
    } else if (
      !employee.reportingManagerId &&
      employee.designation === "Sales Executive" &&
      employee.teamLeaderId &&
      nodes.get(employee.teamLeaderId)?.employee.designation === "Team Leader"
    ) {
      parents.set(employee.id, {
        id: employee.teamLeaderId,
        relationship: "team",
      });
    }
  }

  const roots: OrganizationNode[] = [];
  for (const node of nodes.values()) {
    const parent = parents.get(node.employee.id);
    const seen = new Set([node.employee.id]);
    let ancestor = parent?.id;
    while (ancestor && !seen.has(ancestor)) {
      seen.add(ancestor);
      ancestor = parents.get(ancestor)?.id;
    }
    if (!parent || ancestor) {
      roots.push(node);
      continue;
    }
    node.relationship = parent.relationship;
    nodes.get(parent.id)!.children.push(node);
  }
  const sortChildren = (node: OrganizationNode) => {
    node.children.sort(compare);
    node.children.forEach(sortChildren);
  };
  roots.sort(compare).forEach(sortChildren);
  return roots;
}

export function organizationCounts(employees: OrganizationEmployee[]) {
  const count = (designation: Designation) =>
    employees.filter((employee) => employee.designation === designation).length;
  return [
    { label: "Managers", count: count("Sales Manager") },
    { label: "Team Leaders", count: count("Team Leader") },
    { label: "Coordinators", count: count("Coordinator") },
    { label: "Admin Staff", count: count("Admin Staff") },
    { label: "Sales Executives", count: count("Sales Executive") },
  ];
}
