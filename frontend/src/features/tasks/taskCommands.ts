import {
  dueField,
  employeeSource,
  reasonField,
  type Command,
  type Field,
} from "../../app/api/commands";
import type { DataRecord } from "../../app/api/models";

export const taskViewOptions = [
  "active",
  "assigned",
  "created",
  "management",
  "overdue",
  "history",
  "archived",
] as const;

export type TaskView = (typeof taskViewOptions)[number];

export const taskPriorities = ["Low", "Normal", "High", "Urgent"] as const;
export const taskStatuses = [
  "Open",
  "In Progress",
  "Completed",
  "Cancelled",
] as const;
export const relatedTypes = [
  "case",
  "customer",
  "employee",
  "asset",
  "attendance",
  "attendance_import",
  "finance_result",
  "clawback",
  "payment",
] as const;

export const relatedTypeLabels: Record<(typeof relatedTypes)[number], string> = {
  case: "Case",
  customer: "Customer",
  employee: "Employee",
  asset: "Asset",
  attendance: "Attendance",
  attendance_import: "Attendance import",
  finance_result: "Finance result",
  clawback: "Clawback",
  payment: "Payment",
};

export function canUseManagementView(designation: string) {
  return [
    "Owner",
    "Managing Director",
    "Sales Manager",
    "Team Leader",
  ].includes(designation);
}

export function assigneeField(employeeId: string, designation: string): Field {
  return {
    key: "assigneeEmployeeId",
    label: "Assignee",
    required: true,
    initial: employeeId,
    source: canUseManagementView(designation)
      ? employeeSource
      : { ...employeeSource, where: { id: employeeId } },
  };
}

export function createTaskCommand(
  employeeId: string,
  designation: string,
): Command {
  const assignee = assigneeField(employeeId, designation);
  return {
    title: "Create Task",
    path: "/tasks",
    idempotent: true,
    fields: [
      { key: "title", label: "Title", required: true, max: 200 },
      {
        key: "description",
        label: "Description",
        type: "textarea",
        max: 5000,
      },
      assignee,
      {
        key: "priority",
        label: "Priority",
        options: [...taskPriorities],
        initial: "Normal",
        required: true,
      },
      dueField,
      {
        key: "relatedType",
        label: "Related record type",
        options: [...relatedTypes],
        optionLabels: relatedTypeLabels,
        clearOnChange: ["relatedId"],
      },
      {
        key: "relatedId",
        label: "Related record",
        show: (values) => Boolean(values.relatedType),
        required: true,
        source: {
          path: "/tasks/related-options",
          queryFrom: { relatedType: "relatedType" },
          label: "label",
          value: "id",
          paged: true,
          search: true,
        },
      },
    ],
  };
}

export function taskCommands(
  row: DataRecord,
  employeeId: string,
  designation: string,
): Command[] {
  if (row.archivedAt) return [];
  const closed = ["Completed", "Cancelled"].includes(String(row.status));
  const manager =
    row.creatorEmployeeId === employeeId || canUseManagementView(designation);
  const assignee = assigneeField(employeeId, designation);
  const commands: Command[] = [];
  if (!closed && row.assigneeEmployeeId === employeeId) {
    commands.push({
      title: "Complete Task",
      path: `/tasks/${row.id}/status`,
      idempotent: true,
      submitLabel: "Complete",
      fields: [
        {
          key: "status",
          label: "Status",
          options: ["Completed"],
          initial: "Completed",
          required: true,
        },
      ],
    });
    commands.push({
      title: "Change status",
      path: `/tasks/${row.id}/status`,
      idempotent: true,
      fields: [
        {
          key: "status",
          label: "Status",
          options: ["Open", "In Progress", "Completed"],
          required: true,
        },
      ],
    });
  }
  if (!manager) return commands;
  if (!closed) {
    commands.push(
      {
        title: "Reassign Task",
        path: `/tasks/${row.id}/reassign`,
        idempotent: true,
        fields: [assignee, reasonField],
      },
      {
        title: "Cancel Task",
        path: `/tasks/${row.id}/cancel`,
        idempotent: true,
        fields: [reasonField],
      },
      {
        title: "Change due time",
        path: `/tasks/${row.id}/due-date`,
        idempotent: true,
        fields: [dueField],
      },
    );
    return commands;
  }
  commands.push(
    {
      title: "Reopen Task",
      path: `/tasks/${row.id}/reopen`,
      idempotent: true,
      fields: [reasonField, dueField],
    },
    {
      title: "Archive Task",
      path: `/tasks/${row.id}/archive`,
      idempotent: true,
      fields: [],
    },
  );
  return commands;
}

export type TaskRecord = {
  id: string;
  title: string;
  description: string | null;
  creatorEmployeeId: string;
  assigneeEmployeeId: string;
  priority: string;
  status: string;
  dueAt: string;
  archivedAt: string | null;
  isOverdue: boolean;
  relatedType: string | null;
  relatedId: string | null;
  relatedUnavailable: boolean;
  createdAt: string;
};

export type TaskHistoryItem = {
  id: string;
  taskId?: string;
  action: string;
  actorEmployeeId: string;
  reason: string | null;
  beforeValues?: Record<string, unknown> | null;
  afterValues?: Record<string, unknown> | null;
  createdAt: string;
};
