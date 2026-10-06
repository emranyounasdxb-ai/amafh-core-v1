import {
  branchField,
  departmentField,
  effectiveField,
  employeeSource,
  type Command,
  type Field,
} from "../../../app/api/commands";
import { dubaiTodayDateOnly } from "../../../design-system";

export type TeamListRecord = {
  id: string;
  name: string;
  branch_id: string;
  department_id: string;
  leader_employee_id: string;
  active: boolean;
  updated_at: string | null;
  branch_name: string | null;
  department_name: string | null;
  leader_name: string | null;
  leader_code: string | null;
  leader_avatar_file_id: string | null;
  member_count: number;
};

export type TeamDetailRecord = {
  id: string;
  name: string;
  branchId: string;
  departmentId: string;
  leaderEmployeeId: string;
  active: boolean;
  memberEmployeeIds: string[];
};

export type TeamScope = {
  id: string;
  branchId: string;
  departmentId: string;
  leaderEmployeeId: string;
  memberEmployeeIds?: string[];
};

const nameField: Field = { key: "name", label: "Team name", required: true };

export function createTeamCommand(): Command {
  return {
    title: "Add Team",
    path: "/teams",
    submitLabel: "Add Team",
    fields: [
      nameField,
      { ...branchField, clearOnChange: ["departmentId", "leaderEmployeeId"] },
      {
        ...departmentField,
        choiceLabel: "departmentWithBranch",
        clearOnChange: ["leaderEmployeeId"],
      },
      {
        key: "leaderEmployeeId",
        label: "Team Leader",
        required: true,
        source: {
          ...employeeSource,
          where: { designation: "Team Leader" },
          matchFrom: { branchId: "branchId", departmentId: "departmentId" },
        },
      },
    ],
  };
}

export function renameTeamCommand(team: TeamScope): Command {
  return {
    title: "Rename Team",
    path: `/teams/${team.id}`,
    method: "PATCH",
    submitLabel: "Save name",
    fields: [nameField],
  };
}

export function reassignLeaderCommand(team: TeamScope): Command {
  return {
    title: "Change Team Leader",
    path: `/teams/${team.id}/reassign-leader`,
    submitLabel: "Change Team Leader",
    fields: [
      {
        key: "leaderEmployeeId",
        label: "Team Leader",
        required: true,
        source: {
          ...employeeSource,
          where: {
            designation: "Team Leader",
            branchId: team.branchId,
            departmentId: team.departmentId,
          },
          exclude: [team.leaderEmployeeId],
        },
      },
      { ...effectiveField, initial: dubaiTodayDateOnly() },
    ],
  };
}

export function addMemberCommand(team: TeamScope): Command {
  return {
    title: "Add member",
    path: `/teams/${team.id}/members`,
    submitLabel: "Add member",
    fields: [
      {
        key: "employeeId",
        label: "Sales Executive",
        required: true,
        source: {
          ...employeeSource,
          where: {
            designation: "Sales Executive",
            branchId: team.branchId,
            departmentId: team.departmentId,
          },
          exclude: team.memberEmployeeIds ?? [],
        },
      },
      {
        key: "startDate",
        label: "Start date",
        type: "date",
        required: true,
        initial: dubaiTodayDateOnly(),
      },
    ],
  };
}

export function teamScopeFromList(team: TeamListRecord): TeamScope {
  return {
    id: team.id,
    branchId: team.branch_id,
    departmentId: team.department_id,
    leaderEmployeeId: team.leader_employee_id,
  };
}

export function teamScopeFromDetail(team: TeamDetailRecord): TeamScope {
  return {
    id: team.id,
    branchId: team.branchId,
    departmentId: team.departmentId,
    leaderEmployeeId: team.leaderEmployeeId,
    memberEmployeeIds: team.memberEmployeeIds,
  };
}
