import type { ReactNode } from "react";
import {
  CompactDate,
  CompactDateTime,
  formatDubaiTimestamp,
  isLikelyDateOnly,
} from "../../design-system";
import { EmployeeLabel, isUuid } from "../../app/presentation/labels";
import type { TaskHistoryItem } from "./taskCommands";

export function formatCompactDubaiTimestamp(value: string): string {
  return formatDubaiTimestamp(value);
}

const titles: Record<string, string> = {
  Created: "Task created",
  Viewed: "Task viewed",
  "Status Changed": "Status changed",
  Completed: "Task completed",
  Reassigned: "Task reassigned",
  Cancelled: "Task cancelled",
  Reopened: "Task reopened",
  "Due Date Changed": "Due date/time changed",
  Archived: "Task archived",
};

function textValue(value: unknown): string {
  if (value == null) return "";
  const text = String(value).trim();
  if (!text || isUuid(text)) return "";
  return text;
}

function asString(record: Record<string, unknown> | null | undefined, key: string) {
  if (!record) return "";
  return textValue(record[key]);
}

function employeeId(record: Record<string, unknown> | null | undefined) {
  const value = record?.assigneeEmployeeId;
  return typeof value === "string" && value ? value : "";
}

function dueLabel(value: unknown) {
  const text = typeof value === "string" ? value : "";
  if (!text || isUuid(text)) return "";
  return formatCompactDubaiTimestamp(text);
}

export function historyEventTitle(action: string) {
  if (titles[action]) return titles[action];
  const text = action.trim();
  if (!text || isUuid(text)) return "Task update";
  if (!/[_-]/.test(text)) return text;
  return text
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

export function historyEventSummary(item: TaskHistoryItem): ReactNode {
  const before = item.beforeValues ?? null;
  const after = item.afterValues ?? null;
  const reason = item.reason?.trim() || "";
  const parts: ReactNode[] = [];
  if (
    item.action === "Status Changed" ||
    item.action === "Completed" ||
    item.action === "Cancelled" ||
    item.action === "Reopened"
  ) {
    const from = asString(before, "status");
    const to = asString(after, "status");
    if (from && to && from !== to) parts.push(`from ${from} to ${to}`);
  }
  if (item.action === "Due Date Changed" || item.action === "Reopened") {
    const from = dueLabel(before?.dueAt);
    const to = dueLabel(after?.dueAt);
    if (from && to && from !== to) {
      parts.push(
        item.action === "Reopened"
          ? `due date/time from ${from} to ${to}`
          : `from ${from} to ${to}`,
      );
    }
  }
  if (item.action === "Reassigned") {
    const fromId = employeeId(before);
    const toId = employeeId(after);
    if (fromId && toId && fromId !== toId) {
      parts.push(
        <>
          from{" "}
          <EmployeeLabel employeeId={fromId} fieldKey="assigneeEmployeeId" /> to{" "}
          <EmployeeLabel employeeId={toId} fieldKey="assigneeEmployeeId" />
        </>,
      );
    }
  }
  if (!parts.length && !reason) return undefined;
  return (
    <>
      {parts.map((part, index) => (
        <span key={index}>
          {index > 0 ? ". " : null}
          {part}
        </span>
      ))}
      {parts.length && reason ? ". " : null}
      {reason || null}
    </>
  );
}

export function historyEventTime(value: string) {
  if (isLikelyDateOnly(value)) return <CompactDate value={value} />;
  return <CompactDateTime value={value} />;
}
