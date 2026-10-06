import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Button,
  CompactDateTime,
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
import { canManageTeams, canOpenPage } from "../../../access";
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
import { isUuid } from "../../../app/presentation/labels";
import { namedLabel } from "../../employees/live/employeePresentation";
import { TeamCommandDialog, type TeamCommand } from "./TeamCommandDialog";
import {
  createTeamCommand,
  teamScopeFromList,
  type TeamDetailRecord,
  type TeamListRecord,
} from "./teamCommands";
import styles from "./TeamsPage.module.css";
import { ResponsiveFilterPanel } from "../../../shared/filters/ResponsiveFilterPanel";

type Department = NamedRecord & { branch_id?: string };
type Filters = { status: string; branchId: string; departmentId: string };
type Row = TeamListRecord & {
  branch: string;
  department: string;
  leader: string;
  members: number;
  status: string;
  updated: string;
};

const emptyFilters: Filters = { status: "", branchId: "", departmentId: "" };
const COLUMNS = [
  { key: "name", label: "Team", width: 200 },
  { key: "branch", label: "Branch", width: 140 },
  { key: "department", label: "Department", width: 160 },
  { key: "leader", label: "Team Leader", width: 190 },
  { key: "members", label: "Members", width: 100 },
  { key: "status", label: "Status", width: 110 },
  { key: "updated", label: "Updated", width: 150 },
  { key: "actions", label: "Actions", width: 80, fixed: true },
];
const SORTABLE = new Set([
  "name",
  "branch",
  "department",
  "leader",
  "members",
  "status",
  "updated",
]);
const SOURCE_PATH = "/teams?sort=name&direction=asc";

function readTeams(api: ApiClient, path: string, signal: AbortSignal) {
  return choices<TeamListRecord>(api, path, signal);
}

function readableLabel(value: string | null | undefined) {
  const label = value?.trim();
  return label && !isUuid(label) ? label : "";
}

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

function Text({ value }: { value: string }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

type TeamsListState = {
  filters: Filters;
  search: string;
  page: number;
  pageSize: number;
  sort: TableSort;
};

export function TeamsPage({ open }: { open: (id: string) => void }) {
  const { session } = useSession();
  const [initial] = useState(() =>
    readListState<TeamsListState>(session?.employeeId, "teams"),
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
    saveListState<TeamsListState>(employeeId, "teams", {
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
    team: Row;
    value: TeamCommand;
  } | null>(null);
  const [notice, setNotice] = useState("");
  const layout = useConnectedColumnLayout<Row>("teams-list", COLUMNS);

  const resource = useResource<TeamListRecord[]>(
    SOURCE_PATH,
    refresh,
    readTeams,
    "team-directory",
  );
  const branches = useResource<NamedRecord[]>("/branches");
  const departments = useResource<Department[]>("/departments");
  const teams = useMemo(() => resource.data ?? [], [resource.data]);
  const memberCommandTeam =
    command?.value.kind === "member" ? command.team.id : null;
  const memberCommandDetail = useResource<TeamDetailRecord>(
    memberCommandTeam
      ? `/teams/${encodeURIComponent(memberCommandTeam)}`
      : null,
  );
  const positions = useMemo(
    () => new Map(teams.map((team, index) => [team.id, index])),
    [teams],
  );
  const rows = useMemo<Row[]>(
    () =>
      teams.map((team) => ({
        ...team,
        branch:
          readableLabel(team.branch_name) ||
          namedLabel(branches.data, team.branch_id),
        department:
          readableLabel(team.department_name) ||
          namedLabel(departments.data, team.department_id),
        leader: readableLabel(team.leader_name) || "Assigned employee",
        members: team.member_count,
        status: team.active ? "Active" : "Inactive",
        updated: team.updated_at ?? "",
      })),
    [teams, branches.data, departments.data],
  );
  const filtered = useMemo(
    () =>
      rows.filter(
        (row) =>
          (!filters.status || row.status === filters.status) &&
          (!filters.branchId || row.branch_id === filters.branchId) &&
          (!filters.departmentId ||
            row.department_id === filters.departmentId) &&
          (!query ||
            [row.name, row.branch, row.department, row.leader]
              .filter(Boolean)
              .some((value) => value.toLowerCase().includes(query))),
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
  const teamById = useMemo(
    () => new Map(teams.map((team) => [team.id, team])),
    [teams],
  );
  const selection = useTableSelection<Row>("teams-list", {
    path: SOURCE_PATH,
    page: 1,
    size: Math.max(1, teams.length),
    total: teams.length,
    busy: resource.loading || Boolean(resource.error),
    rowForSelection: (row) => teamById.get(row.id) ?? row,
    positionForRow: (row) => positions.get(row.id) ?? 0,
  });
  const toggleRow = useCallback(
    (key: string) => {
      const index = visible.findIndex((row) => row.id === key);
      if (index >= 0) selection.toggleRow(visible[index], index);
    },
    [selection, visible],
  );

  if (!session) return null;
  const mayWrite = canManageTeams(session);
  const canOpenDetail = canOpenPage(session, "teams");

  const updateFilters = (patch: Partial<Filters>) => {
    setFilters((current) => ({ ...current, ...patch }));
    setPage(1);
  };
  const resetFilters = () => {
    setFilters(emptyFilters);
    setPage(1);
  };
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
  ].filter(Boolean) as AppliedFilter[];

  const actionsFor = (row: Row): MenuItem[] => {
    const items: MenuItem[] = [];
    if (canOpenDetail)
      items.push({
        id: "open",
        label: "View Team",
        onSelect: () => open(row.id),
      });
    if (!row.active) return items;
    items.push(
      {
        id: "member",
        label: "Add member",
        onSelect: () => setCommand({ team: row, value: { kind: "member" } }),
      },
      {
        id: "leader",
        label: "Change Team Leader",
        onSelect: () => setCommand({ team: row, value: { kind: "leader" } }),
      },
      {
        id: "rename",
        label: "Rename Team",
        onSelect: () => setCommand({ team: row, value: { kind: "rename" } }),
      },
      {
        id: "deactivate",
        label: "Deactivate Team",
        danger: true,
        separator: true,
        onSelect: () =>
          setCommand({ team: row, value: { kind: "deactivate" } }),
      },
    );
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
      kind:
        column.key === "members"
          ? "number"
          : column.key === "updated"
            ? "date"
            : undefined,
      render: (row) => {
        switch (column.key) {
          case "name":
            return <Text value={row.name} />;
          case "branch":
            return <Text value={row.branch} />;
          case "department":
            return <Text value={row.department} />;
          case "leader":
            return <Text value={row.leader} />;
          case "members":
            return <span className="ds-numeric">{row.members}</span>;
          case "updated":
            return row.updated ? (
              <CompactDateTime value={row.updated} />
            ) : (
              <EmptyValue />
            );
          case "status":
            return (
              <StatusBadge tone={row.active ? "success" : "neutral"}>
                {row.status}
              </StatusBadge>
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
          title="Teams"
          subtitle="Team leadership, membership, and Branch scope"
        />
        <SearchFilterToolbar
          className={styles.toolbar}
          searchId="team-search"
          searchLabel="Search"
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          searchPlaceholder="Search by Team, Team Leader, Branch or Department"
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
                aria-controls="team-filter-card"
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
                  Add Team
                </Button>
              ) : null}
            </div>
          }
        />

        {filtersOpen ? (
          <ResponsiveFilterPanel
            id="team-filter-card"
            label="Team filters"
            className={styles.filterCard}
            onClose={() => setFiltersOpen(false)}
          >
            <div className={styles.filterGrid}>
              <FormField label="Status" htmlFor="team-status">
                <DropdownSelect
                  id="team-status"
                  compact
                  clearable
                  value={filters.status}
                  placeholder="All statuses"
                  options={[
                    { value: "Active", label: "Active" },
                    { value: "Inactive", label: "Inactive" },
                  ]}
                  onChange={(value) =>
                    updateFilters({
                      status: Array.isArray(value) ? (value[0] ?? "") : value,
                    })
                  }
                />
              </FormField>
              <FormField label="Branch" htmlFor="team-branch">
                <DropdownSelect
                  id="team-branch"
                  compact
                  clearable
                  value={filters.branchId}
                  placeholder="All Branches"
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
              <FormField label="Department" htmlFor="team-department">
                <DropdownSelect
                  id="team-department"
                  compact
                  clearable
                  value={filters.departmentId}
                  placeholder="All Departments"
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
            </div>
          </ResponsiveFilterPanel>
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
          <LoadingState title="Loading Teams" />
        ) : (
          <SectionCard compact className={styles.table}>
            <RecordCount count={filtered.length} />
            {teams.length === 0 ? (
              <EmptyState
                title="No Teams"
                description="There are no Team records in this authorized view."
              />
            ) : filtered.length === 0 ? (
              <NoResultsState
                title="No matching records"
                description="No Teams match the current search and filters."
              />
            ) : (
              <>
                <DataTable
                  ariaLabel="Teams"
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
          command={createTeamCommand()}
          onClose={() => setCreating(false)}
          onSaved={() => saved("Team added.")}
        />
      ) : null}
      {command && memberCommandTeam && memberCommandDetail.error ? (
        <InlineNotice tone="error" title="Team unavailable">
          The Team record could not be loaded for this action.
        </InlineNotice>
      ) : null}
      {command &&
      (!memberCommandTeam ||
        memberCommandDetail.data?.id === memberCommandTeam) ? (
        <TeamCommandDialog
          command={command.value}
          team={{
            ...teamScopeFromList(command.team),
            memberEmployeeIds: memberCommandTeam
              ? memberCommandDetail.data?.memberEmployeeIds
              : undefined,
          }}
          name={command.team.name}
          branch={command.team.branch}
          department={command.team.department}
          leader={command.team.leader}
          onClose={() => setCommand(null)}
          onSaved={saved}
        />
      ) : null}
    </PageContainer>
  );
}
