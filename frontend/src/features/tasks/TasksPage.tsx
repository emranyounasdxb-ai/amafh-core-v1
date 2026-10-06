import { useState, useTransition } from "react";
import {
  Button,
  DateRangePicker,
  DropdownSelect,
  EmptyState,
  ErrorState,
  FormField,
  LoadingState,
  NoResultsState,
  OfflineState,
  OverflowMenu,
  PageContainer,
  PageHeader,
  PermissionDeniedState,
  RecordCount,
  ResponsiveDataTable,
  SearchFilterToolbar,
  StatusBadge,
  CompactDateTime,
  TruncatedText,
  type AppliedFilter,
  type DataTableColumn,
  type DateRangeValue,
  type StatusTone,
} from "../../design-system";
import { CommandFormDialog } from "../../app/commands/CommandFormDialog";
import type { Command } from "../../app/api/commands";
import type { Page } from "../../app/api/models";
import { useResource } from "../../app/api/useResource";
import { useSession } from "../../app/session/useSession";
import type { PageId } from "../../access";
import { EmployeeLabel } from "../../app/presentation/labels";
import { TaskDetailDrawer } from "./TaskDetailDrawer";
import {
  canUseManagementView,
  createTaskCommand,
  taskCommands,
  taskPriorities,
  taskStatuses,
  taskViewOptions,
  type TaskHistoryItem,
  type TaskRecord,
  type TaskView,
} from "./taskCommands";
import styles from "./TasksPage.module.css";

const viewLabels: Record<TaskView, string> = {
  active: "Active",
  assigned: "Assigned",
  created: "Created",
  management: "Management",
  overdue: "Overdue",
  history: "History",
  archived: "Archived",
};

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

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

export function TasksPage({
  openTaskId,
  openTaskNonce,
  onOpenRecord,
}: {
  openTaskId?: string;
  openTaskNonce?: number;
  onOpenRecord: (page: PageId, recordId?: string) => void;
}) {
  const { session } = useSession();
  const [view, setView] = useState<TaskView>("active");
  const [priority, setPriority] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [sortKey, setSortKey] = useState("dueAt");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [due, setDue] = useState<DateRangeValue>({ start: "", end: "" });
  const [command, setCommand] = useState<Command | null>(null);
  const [selectedId, setSelectedId] = useState<string | undefined>(openTaskId);
  const [seenOpenTask, setSeenOpenTask] = useState(
    () => `${openTaskNonce ?? 0}:${openTaskId ?? ""}`,
  );
  const [refresh, setRefresh] = useState(0);
  const [, startTransition] = useTransition();
  const openTaskKey = `${openTaskNonce ?? 0}:${openTaskId ?? ""}`;
  if (openTaskKey !== seenOpenTask) {
    setSeenOpenTask(openTaskKey);
    if (openTaskId) setSelectedId(openTaskId);
  }
  const management = Boolean(
    session && canUseManagementView(session.designation),
  );
  const views = taskViewOptions.filter(
    (item) => item !== "management" || management,
  );
  const query = new URLSearchParams({
    view,
    page: String(page),
    pageSize: String(pageSize),
    sort: sortKey,
    direction: sortDirection,
  });
  if (priority) query.set("priority", priority);
  if (status) query.set("status", status);
  if (search.trim()) query.set("q", search.trim());
  if (due.start) query.set("dueFrom", `${due.start}T00:00:00+04:00`);
  if (due.end) query.set("dueTo", `${due.end}T23:59:59+04:00`);
  const list = useResource<Page<TaskRecord>>(
    session ? `/tasks?${query}` : null,
    refresh,
  );
  const detail = useResource<TaskRecord>(
    selectedId ? `/tasks/${selectedId}` : null,
    refresh,
  );
  const history = useResource<Page<TaskHistoryItem>>(
    selectedId ? `/tasks/${selectedId}/history?page=1&pageSize=100` : null,
    refresh,
  );
  const items = list.data?.items ?? [];
  const visible = items;
  if (!session) return null;
  const create = createTaskCommand(session.employeeId, session.designation);
  const applied: AppliedFilter[] = [
    ...(priority
      ? [
          {
            id: "priority",
            field: "Priority",
            value: priority,
            label: `Priority: ${priority}`,
            onRemove: () => setPriority(""),
          },
        ]
      : []),
    ...(status
      ? [
          {
            id: "status",
            field: "Status",
            value: status,
            label: `Status: ${status}`,
            onRemove: () => setStatus(""),
          },
        ]
      : []),
    ...(due.start || due.end
      ? [
          {
            id: "due",
            field: "Due",
            value: `${due.start || "…"} – ${due.end || "…"}`,
            label: `Due: ${due.start || "…"} – ${due.end || "…"}`,
            onRemove: () => setDue({ start: "", end: "" }),
          },
        ]
      : []),
  ];
  const columns: DataTableColumn<TaskRecord>[] = [
    {
      key: "title",
      header: "Task",
      width: "22%",
      sortable: true,
      render: (row) => (
        <Button
          variant="ghost"
          size="compact"
          onClick={() => setSelectedId(row.id)}
        >
          <TruncatedText value={row.title} />
        </Button>
      ),
    },
    {
      key: "priority",
      header: "Priority",
      width: "7.5rem",
      sortable: true,
      render: (row) => (
        <StatusBadge tone={priorityTone(row.priority)}>
          {row.priority}
        </StatusBadge>
      ),
    },
    {
      key: "status",
      header: "Status",
      width: "8.5rem",
      sortable: true,
      render: (row) => (
        <StatusBadge tone={statusTone(row.status)}>{row.status}</StatusBadge>
      ),
    },
    {
      key: "dueAt",
      header: "Due date",
      width: "14rem",
      kind: "datetime",
      sortable: true,
      render: (row) => (
        <span className={styles.dueDate}>
          <CompactDateTime value={row.dueAt} />
        </span>
      ),
    },
    {
      key: "assigneeEmployeeId",
      header: "Assignee",
      width: "12rem",
      render: (row) => (
        <EmployeeLabel
          employeeId={row.assigneeEmployeeId}
          fieldKey="assigneeEmployeeId"
        />
      ),
    },
    {
      key: "isOverdue",
      header: "Due status",
      width: "7.5rem",
      sortable: true,
      render: (row) =>
        row.isOverdue ? (
          <StatusBadge tone="danger">Overdue</StatusBadge>
        ) : (
          <StatusBadge tone="neutral">On time</StatusBadge>
        ),
    },
    {
      key: "relatedType",
      header: "Related",
      width: "8rem",
      render: (row) =>
        row.relatedUnavailable ? "Unavailable" : row.relatedType || "None",
    },
    {
      key: "actions",
      header: "Actions",
      width: "3.5rem",
      align: "end",
      render: (row) => {
        const actions = taskCommands(
          row,
          session.employeeId,
          session.designation,
        );
        if (!actions.length) return null;
        return (
          <OverflowMenu
            label={`Actions for ${row.title}`}
            items={actions.map((item) => ({
              id: `${item.path}:${item.title}`,
              label: item.title,
              danger:
                item.title.startsWith("Cancel") ||
                item.title.startsWith("Archive"),
              onSelect: () => setCommand(item),
            }))}
          />
        );
      },
    },
  ];
  const total = list.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const changeView = (value: string) => {
    startTransition(() => {
      setView((value as TaskView) || "active");
      setPage(1);
    });
  };
  return (
    <PageContainer>
      <PageHeader
        title="Tasks"
        subtitle="Authorized work assigned to you or your team"
      />
      <SearchFilterToolbar
        searchId="task-search"
        searchLabel="Search"
        searchValue={search}
        onSearchChange={(value) => {
          setSearch(value.slice(0, 128));
          setPage(1);
        }}
        searchPlaceholder="Search authorized tasks"
        filters={[
          {
            id: "view",
            label: "View",
            value: view,
            options: views.map((item) => ({
              value: item,
              label: viewLabels[item],
            })),
            onChange: changeView,
          },
        ]}
        actions={
          <Button size="compact" onClick={() => setCommand(create)}>
            Create Task
          </Button>
        }
        applied={applied}
        onClearFilters={() => {
          setPriority("");
          setStatus("");
          setDue({ start: "", end: "" });
          setSearch("");
        }}
        sortId="task-sort"
        sortValue={sortKey}
        sortOptions={[
          { value: "dueAt", label: "Due date" },
          { value: "title", label: "Title" },
          { value: "createdAt", label: "Created" },
          { value: "status", label: "Status" },
          { value: "priority", label: "Priority" },
          { value: "isOverdue", label: "Due status" },
        ]}
        onSortChange={(value) => {
          setSortKey(value);
          setPage(1);
        }}
        sortDirection={sortDirection}
        sortLabel="Sort"
        filterPanel={
          <>
            <FormField label="Priority" htmlFor="task-priority">
              <DropdownSelect
                id="task-priority"
                compact
                value={priority}
                onChange={(value) =>
                  setPriority(Array.isArray(value) ? (value[0] ?? "") : value)
                }
                options={taskPriorities.map((item) => ({
                  value: item,
                  label: item,
                }))}
              />
            </FormField>
            <FormField label="Status" htmlFor="task-status">
              <DropdownSelect
                id="task-status"
                compact
                value={status}
                onChange={(value) =>
                  setStatus(Array.isArray(value) ? (value[0] ?? "") : value)
                }
                options={taskStatuses.map((item) => ({
                  value: item,
                  label: item,
                }))}
              />
            </FormField>
            <FormField label="Due date" htmlFor="task-due">
              <DateRangePicker
                id="task-due"
                compact
                value={due}
                onChange={setDue}
              />
            </FormField>
          </>
        }
        onApplyFilters={() => setPage(1)}
        onResetFilters={() => {
          setPriority("");
          setStatus("");
          setDue({ start: "", end: "" });
        }}
      />
      {list.denied ? (
        <PermissionDeniedState title="Tasks are not available to this account" />
      ) : list.error && isOffline(list.error) ? (
        <OfflineState />
      ) : list.error ? (
        <ErrorState
          title="Unable to load tasks"
          description={list.error}
          retry={list.reload}
        />
      ) : list.loading && !list.data ? (
        <LoadingState />
      ) : total === 0 ? (
        <EmptyState
          title="No tasks"
          description="There are no tasks in this view."
        />
      ) : visible.length === 0 ? (
        <NoResultsState
          title="No matching tasks"
          description="Nothing on this page matches the search."
        />
      ) : (
        <>
          <RecordCount count={total} />
          <ResponsiveDataTable
            ariaLabel="Tasks"
            columns={columns}
            rows={visible}
            rowKey={(row) => row.id}
            sort={{ key: sortKey, direction: sortDirection }}
            onSort={(key) => {
              if (sortKey === key)
                setSortDirection((current) =>
                  current === "asc" ? "desc" : "asc",
                );
              else {
                setSortKey(key);
                setSortDirection("asc");
              }
              setPage(1);
            }}
            page={page}
            pageCount={pageCount}
            onPageChange={setPage}
            pageSize={pageSize}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
          />
        </>
      )}
      <TaskDetailDrawer
        open={Boolean(selectedId)}
        task={detail.data}
        loading={detail.loading}
        error={detail.error}
        denied={detail.denied}
        onRetry={detail.reload}
        history={history.data?.items ?? []}
        historyLoading={history.loading && !history.data}
        employeeId={session.employeeId}
        designation={session.designation}
        onClose={() => setSelectedId(undefined)}
        onCommand={setCommand}
        onOpenRecord={onOpenRecord}
        onHistoryRefresh={history.reload}
      />
      {command ? (
        <CommandFormDialog
          key={`${command.path}:${command.title}`}
          command={command}
          record={command.path === "/tasks" ? {} : detail.data || {}}
          onClose={() => setCommand(null)}
          onSaved={() => {
            setCommand(null);
            setRefresh((value) => value + 1);
          }}
        />
      ) : null}
    </PageContainer>
  );
}
