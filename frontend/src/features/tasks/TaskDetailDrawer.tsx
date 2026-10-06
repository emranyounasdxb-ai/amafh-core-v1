import { useEffect, type ReactNode } from "react";
import {
  ActionToolbar,
  ActivityTimeline,
  Button,
  Drawer,
  ErrorState,
  InfoField,
  InfoGrid,
  LoadingState,
  OverflowMenu,
  PermissionDeniedState,
  StatusBadge,
  CompactDate,
  CompactDateTime,
  isLikelyDateOnly,
  type MenuItem,
  type StatusTone,
} from "../../design-system";
import type { Command } from "../../app/api/commands";
import type { PageId } from "../../access";
import { EmployeeLabel } from "../../app/presentation/labels";
import { useSession } from "../../app/session/useSession";
import { RelatedDestination } from "../notifications/RelatedDestination";
import {
  taskCommands,
  type TaskHistoryItem,
  type TaskRecord,
} from "./taskCommands";
import {
  historyEventSummary,
  historyEventTime,
  historyEventTitle,
} from "./taskHistoryPresentation";
import styles from "./TaskDetailDrawer.module.css";

const actionLabels: Record<string, string> = {
  "Complete Task": "Complete task",
  "Change status": "Change status",
  "Reassign Task": "Reassign task",
  "Change due time": "Change due time",
  "Reopen Task": "Reopen task",
  "Archive Task": "Archive task",
  "Cancel Task": "Cancel task",
};

const overflowOrder = [
  "Reassign Task",
  "Change due time",
  "Reopen Task",
  "Archive Task",
  "Cancel Task",
];

function statusTone(status: string): StatusTone {
  if (status === "Completed") return "success";
  if (status === "Cancelled") return "neutral";
  if (status === "In Progress") return "brand";
  return "info";
}

function priorityTone(priority: string): StatusTone {
  if (priority === "Urgent") return "danger";
  if (priority === "High") return "warning";
  if (priority === "Low") return "neutral";
  return "info";
}

function emptyValue(text: string) {
  return <span className="ds-empty-value">{text}</span>;
}

function relatedTypeLabel(type: string) {
  return type
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function relatedRecordValue(task: TaskRecord): ReactNode {
  if (task.relatedUnavailable) return "Unavailable";
  if (!task.relatedType) return emptyValue("Not linked");
  return relatedTypeLabel(task.relatedType);
}

function formatDue(value: string) {
  if (isLikelyDateOnly(value)) return <CompactDate value={value} />;
  return <CompactDateTime value={value} />;
}

function visibleLabel(command: Command) {
  return actionLabels[command.title] || command.title;
}

function isDangerAction(title: string) {
  return title.startsWith("Cancel") || title.startsWith("Archive");
}

function TaskActions({
  commands,
  onCommand,
}: {
  commands: Command[];
  onCommand: (command: Command) => void;
}) {
  const complete = commands.find((item) => item.title === "Complete Task");
  const changeStatus = commands.find((item) => item.title === "Change status");
  const overflowItems: MenuItem[] = [];
  for (const title of overflowOrder) {
    const command = commands.find((item) => item.title === title);
    if (!command) continue;
    overflowItems.push({
      id: `${command.path}:${command.title}`,
      label: visibleLabel(command),
      danger: isDangerAction(command.title),
      separator: command.title === "Cancel Task" && overflowItems.length > 0,
      onSelect: () => onCommand(command),
    });
  }
  if (!complete && !changeStatus && !overflowItems.length) return null;
  return (
    <div className={styles.actions}>
      <ActionToolbar>
        {complete ? (
          <Button onClick={() => onCommand(complete)}>
            {visibleLabel(complete)}
          </Button>
        ) : null}
        {changeStatus ? (
          <Button
            variant="secondary"
            onClick={() => onCommand(changeStatus)}
          >
            {visibleLabel(changeStatus)}
          </Button>
        ) : null}
        {overflowItems.length ? (
          <OverflowMenu label="More actions" items={overflowItems} />
        ) : null}
      </ActionToolbar>
    </div>
  );
}

export function TaskDetailDrawer({
  open,
  task,
  loading,
  error,
  denied,
  onRetry,
  history,
  historyLoading,
  employeeId,
  designation,
  onClose,
  onCommand,
  onOpenRecord,
  onHistoryRefresh,
}: {
  open: boolean;
  task: TaskRecord | null;
  loading: boolean;
  error: string;
  denied: boolean;
  onRetry: () => void;
  history: TaskHistoryItem[];
  historyLoading: boolean;
  employeeId: string;
  designation: string;
  onClose: () => void;
  onCommand: (command: Command) => void;
  onOpenRecord: (page: PageId, recordId?: string) => void;
  onHistoryRefresh: () => void;
}) {
  const { api } = useSession();
  const commands = task ? taskCommands(task, employeeId, designation) : [];
  const description = task?.description?.trim() || "";
  const taskId = task?.id;
  const assigneeId = task?.assigneeEmployeeId;
  useEffect(() => {
    if (!open || !taskId || !assigneeId || denied || error) return;
    if (assigneeId !== employeeId) return;
    let cancelled = false;
    const key = `task-view-${taskId}-${assigneeId}`;
    void api
      .request(`/tasks/${taskId}/view`, {
        method: "POST",
        body: "{}",
        headers: { "Idempotency-Key": key },
      })
      .then(() => {
        if (!cancelled) onHistoryRefresh();
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [
    api,
    assigneeId,
    denied,
    employeeId,
    error,
    onHistoryRefresh,
    open,
    taskId,
  ]);
  return (
    <Drawer
      open={open}
      title={task?.title || "Task"}
      description={
        task ? (
          <span className={styles.headerMeta}>
            <StatusBadge tone={statusTone(task.status)}>
              {task.status}
            </StatusBadge>
          </span>
        ) : undefined
      }
      onClose={onClose}
      size="wide"
    >
      {denied ? (
        <PermissionDeniedState />
      ) : error ? (
        <ErrorState description={error} retry={onRetry} />
      ) : loading && !task ? (
        <LoadingState />
      ) : task ? (
        <div className={styles.body}>
          <div className={styles.summary}>
            <InfoGrid>
              <InfoField
                label="Priority"
                value={
                  <StatusBadge tone={priorityTone(task.priority)}>
                    {task.priority}
                  </StatusBadge>
                }
              />
              <InfoField
                label="Assignee"
                value={
                  <EmployeeLabel
                    employeeId={task.assigneeEmployeeId}
                    fieldKey="assigneeEmployeeId"
                  />
                }
              />
              <InfoField label="Due date/time" value={formatDue(task.dueAt)} />
              <InfoField
                label="Due status"
                value={
                  task.isOverdue ? (
                    <StatusBadge tone="danger">Overdue</StatusBadge>
                  ) : (
                    <StatusBadge tone="neutral">On time</StatusBadge>
                  )
                }
              />
              <InfoField label="Related record" value={relatedRecordValue(task)} />
              <InfoField
                label="Description"
                value={
                  description
                    ? description
                    : emptyValue("No description provided")
                }
              />
            </InfoGrid>
            {task.relatedType ? (
              <div className={styles.related}>
                <RelatedDestination
                  key={task.id}
                  endpoint={`/tasks/${task.id}/related`}
                  onOpen={onOpenRecord}
                />
              </div>
            ) : null}
          </div>
          {commands.length ? (
            <TaskActions commands={commands} onCommand={onCommand} />
          ) : null}
          <div className={styles.history}>
            {historyLoading ? (
              <LoadingState title="Loading task history" />
            ) : (
              <ActivityTimeline
                title="Task history"
                compact
                items={history.map((item, index) => ({
                  id: item.id,
                  title:
                    item.action === "Viewed" ? (
                      <>
                        Viewed by{" "}
                        <EmployeeLabel
                          employeeId={item.actorEmployeeId}
                          fieldKey="actorEmployeeId"
                          plain
                        />
                      </>
                    ) : (
                      historyEventTitle(item.action)
                    ),
                  time: historyEventTime(item.createdAt),
                  description: historyEventSummary(item),
                  actor: item.actorEmployeeId ? (
                    <EmployeeLabel
                      employeeId={item.actorEmployeeId}
                      fieldKey="actorEmployeeId"
                      plain
                    />
                  ) : undefined,
                  tone: index === 0 ? "brand" : "neutral",
                }))}
              />
            )}
          </div>
        </div>
      ) : null}
    </Drawer>
  );
}
