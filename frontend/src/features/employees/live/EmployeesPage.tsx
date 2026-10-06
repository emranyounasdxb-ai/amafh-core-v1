import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Avatar,
  Button,
  CompactDate,
  DataTable,
  DropdownSelect,
  EmptyState,
  EmptyValue,
  ErrorState,
  ExportButton,
  FilterButton,
  FormField,
  InlineNotice,
  LoadingState,
  NoResultsState,
  OfflineState,
  OverflowMenu,
  PageContainer,
  PageHeader,
  Pagination,
  PermissionDeniedState,
  RecordCount,
  SearchFilterToolbar,
  SectionCard,
  StatusBadge,
  TruncatedText,
  type AppliedFilter,
  type DataTableColumn,
  type MenuItem,
} from "../../../design-system";
import { canManageEmployees, canOpenPage } from "../../../access";
import { choices } from "../../../app/api/choices";
import type { ApiClient } from "../../../app/api/http";
import type { NamedRecord } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import {
  readListState,
  saveListState,
} from "../../../app/navigation/listState";
import { CommandFormDialog } from "../../../app/commands/CommandFormDialog";
import { useSession } from "../../../app/session/useSession";
import { useConnectedColumnLayout } from "../../../shared/table/useConnectedColumnLayout";
import { useTableSelection } from "../../../shared/table/useTableSelection";
import {
  nextSort,
  sortCompleteRows,
  type TableSort,
} from "../../../shared/table/tableSortState";
import { createEmployeeCommand } from "../employeeCommands";
import {
  EmployeeCommandDialog,
  type EmployeeCommandKind,
} from "./EmployeeCommandDialog";
import { isUuid } from "../../../app/presentation/labels";
import {
  EMPLOYEE_STATUSES,
  employeeAvatarSrc,
  employeeCode,
  employeeName,
  employeeStatusTone,
  namedLabel,
  type EmployeeDetailRecord,
  type EmployeeListRecord,
} from "./employeePresentation";
import styles from "./EmployeesPage.module.css";
import { ResponsiveFilterPanel } from "../../../shared/filters/ResponsiveFilterPanel";

type Department = NamedRecord & { branch_id?: string };
type Filters = {
  status: string;
  branchId: string;
  departmentId: string;
  designation: string;
  reportingManagerId: string;
};
type Row = EmployeeListRecord & {
  code: string;
  name: string;
  branch: string;
  department: string;
  reportingManager: string;
};

const emptyFilters: Filters = {
  status: "",
  branchId: "",
  departmentId: "",
  designation: "",
  reportingManagerId: "",
};

function readableLabel(value: string | null | undefined) {
  const label = value?.trim();
  return label && !isUuid(label) ? label : "";
}

function managerLabel(row: EmployeeListRecord) {
  if (!row.reportingManagerId) return "";
  return readableLabel(row.reportingManagerName) || "Assigned employee";
}

const COLUMNS = [
  { key: "avatar", label: "Avatar", width: 72, fixed: true },
  { key: "code", label: "Employee code", width: 130 },
  { key: "name", label: "Name", width: 200 },
  { key: "designation", label: "Designation", width: 150 },
  { key: "branch", label: "Branch", width: 130 },
  { key: "department", label: "Department", width: 150 },
  { key: "reportingManager", label: "Reporting Manager", width: 180 },
  { key: "status", label: "Status", width: 120 },
  { key: "dateOfJoining", label: "Join date", width: 110 },
  { key: "actions", label: "Actions", width: 80, fixed: true },
];
const SORTABLE = new Set([
  "code",
  "name",
  "designation",
  "branch",
  "department",
  "status",
]);

function readDirectory(api: ApiClient, path: string, signal: AbortSignal) {
  return choices<EmployeeListRecord>(api, path, signal);
}

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

function Text({ value }: { value: string }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

type EmployeesListState = {
  filters: Filters;
  search: string;
  page: number;
  pageSize: number;
  sort: TableSort;
};

export function EmployeesPage({ open }: { open: (id: string) => void }) {
  const { session } = useSession();
  const [initial] = useState(() =>
    readListState<EmployeesListState>(session?.employeeId, "employees"),
  );
  const [filters, setFilters] = useState<Filters>(
    initial?.filters ?? emptyFilters,
  );
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [search, setSearch] = useState(initial?.search ?? "");
  const query = useDeferredValue(search.trim().toLowerCase());
  const [page, setPage] = useState(initial?.page ?? 1);
  const [pageSize, setPageSize] = useState(initial?.pageSize ?? 25);
  const [sort, setSort] = useState<TableSort>(
    initial ? initial.sort : { key: "name", direction: "asc" },
  );
  const employeeId = session?.employeeId;
  useEffect(() => {
    saveListState<EmployeesListState>(employeeId, "employees", {
      filters,
      search,
      page,
      pageSize,
      sort,
    });
  }, [employeeId, filters, page, pageSize, search, sort]);
  const [refresh, setRefresh] = useState(0);
  const [creating, setCreating] = useState(false);
  const [command, setCommand] = useState<{
    kind: EmployeeCommandKind;
    id: string;
  } | null>(null);
  const [notice, setNotice] = useState("");
  const layout = useConnectedColumnLayout<Row>("employees-list", COLUMNS);

  const statusQuery = filters.status
    ? `status=${encodeURIComponent(filters.status)}&`
    : "";
  const basePath = `/employees?${statusQuery}sort=fullName&direction=asc`;
  const sourcePath = filters.reportingManagerId
    ? `/employees?${statusQuery}reportingManagerId=${encodeURIComponent(filters.reportingManagerId)}&sort=fullName&direction=asc`
    : basePath;
  const base = useResource<EmployeeListRecord[]>(
    basePath,
    refresh,
    readDirectory,
    "employee-directory",
  );
  const managed = useResource<EmployeeListRecord[]>(
    filters.reportingManagerId ? sourcePath : null,
    refresh,
    readDirectory,
    "employee-directory",
  );
  const resource = filters.reportingManagerId ? managed : base;
  const branches = useResource<NamedRecord[]>("/branches");
  const departments = useResource<Department[]>("/departments");
  const designations = useResource<NamedRecord[]>("/designations");
  const commandDetail = useResource<EmployeeDetailRecord>(
    command ? `/employees/${encodeURIComponent(command.id)}` : null,
  );

  const directory = useMemo(() => resource.data ?? [], [resource.data]);
  const positions = useMemo(
    () => new Map(directory.map((row, index) => [row.id, index])),
    [directory],
  );
  const directoryById = useMemo(
    () => new Map(directory.map((row) => [row.id, row])),
    [directory],
  );
  const managerOptions = useMemo(() => {
    const options = new Map<string, { label: string; description?: string }>();
    for (const row of base.data ?? []) {
      const name = readableLabel(row.reportingManagerName);
      if (!row.reportingManagerId || !name) continue;
      options.set(row.reportingManagerId, {
        label: name,
        description: readableLabel(row.reportingManagerCode) || undefined,
      });
    }
    return [...options.entries()]
      .map(([value, option]) => ({ value, ...option }))
      .sort((left, right) => left.label.localeCompare(right.label));
  }, [base.data]);
  const rows = useMemo<Row[]>(
    () =>
      directory.map((row) => ({
        ...row,
        code: employeeCode(row),
        name: employeeName(row),
        branch:
          readableLabel(row.branchName) ||
          namedLabel(branches.data, row.branchId),
        department:
          readableLabel(row.departmentName) ||
          namedLabel(departments.data, row.departmentId),
        reportingManager: managerLabel(row),
      })),
    [directory, branches.data, departments.data],
  );
  const filtered = useMemo(
    () =>
      rows.filter(
        (row) =>
          (!filters.branchId || row.branchId === filters.branchId) &&
          (!filters.departmentId ||
            row.departmentId === filters.departmentId) &&
          (!filters.designation || row.designation === filters.designation) &&
          (!query ||
            [
              row.code,
              row.name,
              row.designation,
              row.branch,
              row.department,
              row.reportingManager,
            ]
              .filter(Boolean)
              .some((value) => String(value).toLowerCase().includes(query))),
      ),
    [rows, filters, query],
  );
  const sorted = useMemo(
    () => sortCompleteRows(filtered, sort),
    [filtered, sort],
  );
  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const visible = sorted.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );

  const selection = useTableSelection<Row>("employees-list", {
    path: sourcePath,
    page: 1,
    size: Math.max(1, directory.length),
    total: directory.length,
    busy: resource.loading || Boolean(resource.error),
    rowForSelection: (row) => directoryById.get(row.id) ?? row,
    positionForRow: (row) => positions.get(row.id) ?? 0,
  });

  const updateFilters = (patch: Partial<Filters>) => {
    setFilters((current) => ({ ...current, ...patch }));
    setPage(1);
  };
  const resetFilters = () => {
    setFilters(emptyFilters);
    setPage(1);
  };
  const toggleRow = useCallback(
    (key: string) => {
      const index = visible.findIndex((row) => row.id === key);
      if (index >= 0) selection.toggleRow(visible[index], index);
    },
    [selection, visible],
  );

  if (!session) return null;
  const mayWrite = canManageEmployees(session);
  const canOpenDetail = canOpenPage(session, "employees");

  const departmentOptions = (departments.data ?? [])
    .filter(
      (department) =>
        !filters.branchId || department.branch_id === filters.branchId,
    )
    .map((department) => ({
      value: department.id,
      label: filters.branchId
        ? department.name
        : `${department.name} · ${namedLabel(branches.data, department.branch_id ?? null)}`,
    }));
  const applied: AppliedFilter[] = [
    filters.status && {
      id: "status",
      label: "Status",
      field: "Status",
      value: filters.status,
      onRemove: () => updateFilters({ status: "" }),
    },
    filters.branchId && {
      id: "branch",
      label: "Branch",
      field: "Branch",
      value: namedLabel(branches.data, filters.branchId),
      onRemove: () => updateFilters({ branchId: "", departmentId: "" }),
    },
    filters.departmentId && {
      id: "department",
      label: "Department",
      field: "Department",
      value:
        departmentOptions.find((item) => item.value === filters.departmentId)
          ?.label || namedLabel(departments.data, filters.departmentId),
      onRemove: () => updateFilters({ departmentId: "" }),
    },
    filters.designation && {
      id: "designation",
      label: "Designation",
      field: "Designation",
      value: filters.designation,
      onRemove: () => updateFilters({ designation: "" }),
    },
    filters.reportingManagerId && {
      id: "reportingManager",
      label: "Reporting Manager",
      field: "Reporting Manager",
      value:
        managerOptions.find(
          (option) => option.value === filters.reportingManagerId,
        )?.label || "Assigned employee",
      onRemove: () => updateFilters({ reportingManagerId: "" }),
    },
  ].filter(Boolean) as AppliedFilter[];

  const actionsFor = (row: Row): MenuItem[] => {
    const items: MenuItem[] = [];
    const canManagePrivileged =
      session.designation === "Owner" ||
      !["Owner", "Managing Director"].includes(row.designation || "");
    if (canOpenDetail)
      items.push({
        id: "open",
        label: "View employee",
        onSelect: () => open(row.id),
      });
    if (canManagePrivileged)
      items.push({
        id: "assignment",
        label: "Change assignment",
        onSelect: () => setCommand({ kind: "assignment", id: row.id }),
      });
    items.push({
      id: "profile",
      label: "Edit profile",
      onSelect: () => setCommand({ kind: "profile", id: row.id }),
    });
    if (canManagePrivileged && row.status === "Pending Setup")
      items.push({
        id: "activate",
        label: "Activate employee",
        onSelect: () => setCommand({ kind: "activate", id: row.id }),
      });
    if (
      canManagePrivileged &&
      row.status !== "Offboarded" &&
      row.designation !== "Owner"
    )
      items.push({
        id: "offboard",
        label: "Offboard employee",
        danger: true,
        separator: true,
        onSelect: () => setCommand({ kind: "offboard", id: row.id }),
      });
    return items;
  };

  const columns: DataTableColumn<Row>[] = layout.columns
    .filter((column) => mayWrite || column.key !== "actions")
    .map((column) => ({
      key: column.key,
      header: column.label,
      width: `${column.width}px`,
      fixed: column.fixed,
      sortable: SORTABLE.has(column.key),
      kind: column.key === "dateOfJoining" ? "date" : undefined,
      render: (row) => {
        switch (column.key) {
          case "avatar":
            return (
              <Avatar name={row.name} src={employeeAvatarSrc(row)} size="sm" />
            );
          case "code":
            return <Text value={row.code} />;
          case "name":
            return <Text value={row.name} />;
          case "designation":
            return <Text value={row.designation || ""} />;
          case "branch":
            return <Text value={row.branch} />;
          case "department":
            return <Text value={row.department} />;
          case "reportingManager":
            return <Text value={row.reportingManager} />;
          case "status":
            return (
              <StatusBadge tone={employeeStatusTone(row.status)}>
                {row.status}
              </StatusBadge>
            );
          case "dateOfJoining":
            return row.dateOfJoining ? (
              <CompactDate value={row.dateOfJoining} />
            ) : (
              <EmptyValue />
            );
          case "actions":
            return (
              <OverflowMenu
                label={`Actions for ${row.name}`}
                items={actionsFor(row)}
              />
            );
          default:
            return <EmptyValue />;
        }
      },
    }));

  const selectedKeys = visible
    .filter((row, index) => selection.checked(row, index))
    .map((row) => row.id);
  const activeCommand =
    command && commandDetail.data?.id === command.id
      ? commandDetail.data
      : undefined;
  const saved = (message: string) => {
    setCommand(null);
    setCreating(false);
    setNotice(message);
    setRefresh((value) => value + 1);
  };

  return (
    <PageContainer>
      <div className={styles.page}>
        <PageHeader
          title="Employees"
          subtitle="Authorized employee records, assignments, and status"
        />
        <SearchFilterToolbar
          className={styles.toolbar}
          searchId="employee-search"
          searchLabel="Search"
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          searchPlaceholder="Search by code, name, designation, Branch or Department"
          applied={applied}
          onClearFilters={applied.length ? resetFilters : undefined}
          disabled={resource.loading && !resource.data}
          loading={resource.loading && !resource.data}
          actions={
            <div className={styles.toolbarActions}>
              <FilterButton
                size="compact"
                count={applied.length}
                aria-expanded={filtersOpen}
                aria-controls="employee-filter-card"
                onClick={() => setFiltersOpen((current) => !current)}
              />
              {selection.allowed ? (
                <ExportButton
                  size="compact"
                  selectedCount={selection.selectedCount}
                  loading={selection.working}
                  disabled={!selection.selectedCount}
                  onClick={() => void selection.exportCsv()}
                />
              ) : null}
              {mayWrite ? (
                <Button size="compact" onClick={() => setCreating(true)}>
                  Add Employee
                </Button>
              ) : null}
            </div>
          }
        />

        {filtersOpen ? (
          <ResponsiveFilterPanel
            id="employee-filter-card"
            label="Employee filters"
            className={styles.filterCard}
            onClose={() => setFiltersOpen(false)}
          >
            <div className={styles.filterGrid}>
              <FormField label="Status" htmlFor="employee-status">
                <DropdownSelect
                  id="employee-status"
                  compact
                  clearable
                  value={filters.status}
                  placeholder="All statuses"
                  options={EMPLOYEE_STATUSES.map((status) => ({
                    value: status,
                    label: status,
                  }))}
                  onChange={(value) =>
                    updateFilters({
                      status: Array.isArray(value) ? (value[0] ?? "") : value,
                    })
                  }
                />
              </FormField>
              <FormField label="Branch" htmlFor="employee-branch">
                <DropdownSelect
                  id="employee-branch"
                  compact
                  clearable
                  value={filters.branchId}
                  placeholder="All Branches"
                  loading={branches.loading && !branches.data}
                  options={(branches.data ?? []).map((branch) => ({
                    value: branch.id,
                    label: branch.name,
                  }))}
                  onChange={(value) => {
                    const next = Array.isArray(value)
                      ? (value[0] ?? "")
                      : value;
                    updateFilters({
                      branchId: next,
                      departmentId:
                        next &&
                        departments.data?.find(
                          (item) => item.id === filters.departmentId,
                        )?.branch_id !== next
                          ? ""
                          : filters.departmentId,
                    });
                  }}
                />
              </FormField>
              <FormField label="Department" htmlFor="employee-department">
                <DropdownSelect
                  id="employee-department"
                  compact
                  clearable
                  value={filters.departmentId}
                  placeholder="All Departments"
                  loading={departments.loading && !departments.data}
                  options={departmentOptions}
                  onChange={(value) =>
                    updateFilters({
                      departmentId: Array.isArray(value)
                        ? (value[0] ?? "")
                        : value,
                    })
                  }
                />
              </FormField>
              <FormField label="Designation" htmlFor="employee-designation">
                <DropdownSelect
                  id="employee-designation"
                  compact
                  clearable
                  value={filters.designation}
                  placeholder="All designations"
                  loading={designations.loading && !designations.data}
                  options={(designations.data ?? []).map((designation) => ({
                    value: designation.name,
                    label: designation.name,
                  }))}
                  onChange={(value) =>
                    updateFilters({
                      designation: Array.isArray(value)
                        ? (value[0] ?? "")
                        : value,
                    })
                  }
                />
              </FormField>
              <FormField
                label="Reporting Manager"
                htmlFor="employee-reporting-manager"
              >
                <DropdownSelect
                  id="employee-reporting-manager"
                  compact
                  clearable
                  searchable
                  value={filters.reportingManagerId}
                  placeholder="All Reporting Managers"
                  loading={base.loading && !base.data}
                  options={managerOptions}
                  onChange={(value) =>
                    updateFilters({
                      reportingManagerId: Array.isArray(value)
                        ? (value[0] ?? "")
                        : value,
                    })
                  }
                />
              </FormField>
            </div>
          </ResponsiveFilterPanel>
        ) : null}
        {command && commandDetail.error ? (
          <InlineNotice tone="error" title="Employee unavailable">
            The Employee record could not be loaded for this action.
          </InlineNotice>
        ) : null}

        {notice ? (
          <InlineNotice tone="success" title="Saved">
            {notice}
          </InlineNotice>
        ) : null}
        {selection.error ? (
          <InlineNotice tone="error" title="Export failed">
            {selection.error}
          </InlineNotice>
        ) : null}

        {resource.denied ? (
          <PermissionDeniedState />
        ) : resource.error && !resource.data ? (
          isOffline(resource.error) ? (
            <OfflineState />
          ) : (
            <ErrorState description={resource.error} retry={resource.reload} />
          )
        ) : resource.loading && !resource.data ? (
          <LoadingState title="Loading Employees" />
        ) : (
          <SectionCard compact className={styles.table}>
            <RecordCount count={filtered.length} />
            {directory.length === 0 ? (
              <EmptyState
                title="No matching authorized records"
                description="There are no Employee records in this authorized view."
              />
            ) : filtered.length === 0 ? (
              <NoResultsState
                title="No matching records"
                description="No employees match the current search and filters."
              />
            ) : (
              <>
                <DataTable
                  ariaLabel="Authorized employees"
                  density="compact"
                  columns={columns}
                  rows={visible}
                  rowKey={(row) => row.id}
                  sort={sort}
                  onSort={(key) => {
                    setSort(nextSort(sort, key));
                    setPage(1);
                  }}
                  selectedKeys={selection.allowed ? selectedKeys : undefined}
                  onToggleRow={selection.allowed ? toggleRow : undefined}
                  onToggleAll={
                    selection.allowed
                      ? () => selection.toggleRows(visible)
                      : undefined
                  }
                  loading={resource.updating}
                  onRowActivate={
                    canOpenDetail ? (row) => open(row.id) : undefined
                  }
                  rowActivateLabel={(row) => `Open ${row.name}`}
                  rowSelectLabel={(row) => `Select ${row.name}`}
                  onColumnResize={layout.resize}
                  onColumnReorder={layout.move}
                />
                <Pagination
                  page={currentPage}
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
          </SectionCard>
        )}
      </div>

      {creating ? (
        <CommandFormDialog
          command={createEmployeeCommand(session.designation === "Owner")}
          onClose={() => setCreating(false)}
          onSaved={() => saved("Employee added.")}
        />
      ) : null}
      {command && activeCommand ? (
        <EmployeeCommandDialog
          kind={command.kind}
          employee={activeCommand}
          branch={namedLabel(branches.data, activeCommand.branchId)}
          department={namedLabel(departments.data, activeCommand.departmentId)}
          onClose={() => setCommand(null)}
          onSaved={saved}
        />
      ) : null}
    </PageContainer>
  );
}
