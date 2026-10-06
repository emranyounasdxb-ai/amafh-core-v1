import { useCallback, useState, type ReactNode } from "react";
import {
  Avatar,
  BarChart,
  Button,
  ChartCard,
  ChartGrid,
  DataTable,
  DateRangePicker,
  Dialog,
  DropdownSelect,
  DsIcon,
  EmptyState,
  EmptyValue,
  ErrorState,
  ExportButton,
  FormField,
  InlineNotice,
  MonetaryAmount,
  NoResultsState,
  PageContainer,
  PageHeader,
  Pagination,
  PerformanceSummary,
  PermissionDeniedState,
  RadioGroup,
  RecordCount,
  SearchFilterToolbar,
  StatusBadge,
  Tabs,
  TruncatedText,
  dubaiTodayDateOnly,
  formatDubaiTimestamp,
  formatFullNumber,
  formatFullPercent,
  useDebouncedValue,
  type AppliedFilter,
  type DataTableColumn,
  type DsIconName,
} from "../../../design-system";
import { choices } from "../../../app/api/choices";
import { ApiFailure, type ApiClient } from "../../../app/api/http";
import type { NamedRecord } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import { useTableSelection } from "../../../shared/table/useTableSelection";
import {
  departmentLabel,
  employeeAvatarSrc,
  namedLabel,
} from "../../employees/live/employeePresentation";
import {
  PRODUCTS,
  performanceViews,
  productOptions,
  type OverviewState,
  type PerformanceView,
  PRODUCT_COLOR,
  PRODUCT_LABEL,
  amount,
  datePresets,
  emptyFilters,
  metricCards,
  outcomeSeries,
  percentage,
  performanceQuery,
  periodLabel,
  personCode,
  personName,
  readable,
  stageSeries,
  valuesState,
  type ComparisonItem,
  type ComparisonPage,
  type CoordinatorItem,
  type EmployeeMetrics,
  type EmployeePage,
  type Page,
  type PerformanceFilters,
  type PerformanceSummaryValues,
  type Product,
  type RankingItem,
  type RankingPage,
} from "./performancePresentation";
import styles from "./PerformancePage.module.css";

type Department = NamedRecord & { branch_id?: string };
type Team = NamedRecord & { branch_id?: string; department_id?: string };

const VIEW_LABEL: Record<PerformanceView, string> = {
  employees: "Employees",
  rankings: "Rankings",
  team: "Team",
  workload: "Coordinator workload",
  comparisons: "Comparisons",
};

const SORT_KEYS: Record<PerformanceView, Record<string, string>> = {
  employees: {
    name: "employeeName",
    created: "createdCaseCount",
    booked: "bookedCaseCount",
    completed: "completedCaseCount",
    ccPoints: "achievedCCPoints",
    pfAmount: "achievedPFAed",
  },
  team: {
    name: "employeeName",
    created: "createdCaseCount",
    booked: "bookedCaseCount",
    completed: "completedCaseCount",
    ccPoints: "achievedCCPoints",
    pfAmount: "achievedPFAed",
  },
  rankings: {
    rank: "rank",
    name: "employeeName",
    achievement: "achievementPercentage",
    completed: "completedCaseCount",
  },
  workload: {
    name: "employeeName",
    handled: "handledCases",
    booked: "submittedBookedCases",
    stages: "stageUpdatedCases",
  },
  comparisons: {
    name: "name",
    created: "createdCaseCount",
    booked: "bookedCaseCount",
    completed: "completedCaseCount",
    ccPoints: "achievedCCPoints",
    pfAmount: "achievedPFAed",
  },
};

function loadTeams(api: ApiClient, path: string, signal: AbortSignal) {
  return choices<Team>(api, path, signal);
}

function Text({ value }: { value: string }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

function Points({ value }: { value: string | number }) {
  return <span className="ds-numeric">{formatFullNumber(amount(value))}</span>;
}

function Achievement({
  row,
  product,
}: {
  row: PerformanceSummaryValues;
  product: Product | "";
}) {
  const products = product ? [product] : PRODUCTS;
  const text = products
    .map((code) => {
      const progress = row.targetProgress[code];
      const value = percentage(progress?.achievementPercentage);
      const shown =
        !progress || progress.state === "No Target"
          ? "No target"
          : value == null
            ? "Unavailable"
            : formatFullPercent(value);
      return product ? shown : `${code} ${shown}`;
    })
    .join(" · ");
  return <TruncatedText value={text} />;
}

function Person({ row }: { row: EmployeeMetrics | CoordinatorItem }) {
  const name = personName(row);
  return (
    <span className={styles.person}>
      <Avatar
        name={name}
        size="sm"
        src={employeeAvatarSrc({ id: row.employeeId, avatarFileId: row.avatarFileId })}
      />
      <TruncatedText value={name} />
    </span>
  );
}

function confirmMessage(failure: unknown) {
  const code = failure instanceof ApiFailure ? failure.code : "";
  switch (code) {
    case "RANKING_ALREADY_CONFIRMED":
      return "This ranking winner has already been confirmed.";
    case "RANKING_SELECTION_INVALID":
      return "The selected employee is not part of the final tie. Refresh the ranking and try again.";
    case "RANKING_CONFLICT":
      return "The ranking changed while it was being confirmed. Refresh and try again.";
    case "FORBIDDEN":
      return "You are not authorized to confirm this ranking.";
    default:
      return "The ranking winner could not be confirmed. Try again.";
  }
}

export function PerformanceOverview({
  state,
  update,
  filters,
  applyFilters,
  product,
  setProduct,
  open,
}: {
  state: OverviewState;
  update: (patch: Partial<OverviewState>) => void;
  filters: PerformanceFilters;
  applyFilters: (filters: PerformanceFilters) => void;
  product: Product | "";
  setProduct: (product: Product | "") => void;
  open: (id: string) => void;
}) {
  const { session, api } = useSession();
  const { view, draft, search, page, pageSize, sort } = state;
  const debouncedSearch = useDebouncedValue(search.trim(), 300);
  const [refresh, setRefresh] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [candidate, setCandidate] = useState("");
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [confirmError, setConfirmError] = useState("");
  const [notice, setNotice] = useState("");

  const role = session?.designation;
  const management = role === "Owner" || role === "Managing Director";
  const views = role ? performanceViews(role) : [];
  const activeView = views.includes(view) ? view : "employees";
  const teamScoped = role === "Team Leader";

  const branches = useResource<NamedRecord[]>(management ? "/branches" : null);
  const departments = useResource<Department[]>(
    management ? "/departments" : null,
  );
  const designations = useResource<NamedRecord[]>(
    management ? "/designations" : null,
  );
  const teams = useResource<Team[]>(
    management ? "/teams" : null,
    0,
    loadTeams,
    "choices",
  );

  const teamId = teamScoped ? (session?.teamId ?? "") : filters.teamId;
  const datesSet = Boolean(filters.startDate && filters.endDate);
  const sortKey = sort ? SORT_KEYS[activeView][sort.key] : undefined;
  const paging = {
    page,
    pageSize,
    sort: sortKey,
    direction: sortKey ? sort?.direction : undefined,
  };

  let blocked: { title: string; description: string; icon: DsIconName } | null =
    null;
  let path: string | null = null;
  if (activeView === "employees") {
    path = `/performance/employees?${performanceQuery(
      filters,
      product,
      { ...paging, search: debouncedSearch || undefined },
      { branch: management },
    )}`;
  } else if (activeView === "team") {
    if (!teamId)
      blocked = {
        title: "Select a Team",
        description: teamScoped
          ? "No active Team is assigned to you."
          : "Choose a Team in Filters to view its performance.",
        icon: "team",
      };
    else
      path = `/performance/teams/${encodeURIComponent(teamId)}?${performanceQuery(
        filters,
        product,
        paging,
      )}`;
  } else if (activeView === "rankings") {
    if (!product || !datesSet)
      blocked = {
        title: "Select a Product and period",
        description:
          "Rankings need Credit Card or Personal Finance and a complete date range.",
        icon: "performance",
      };
    else {
      const extra: Record<string, string | number | undefined> = { ...paging };
      if (role === "Sales Manager") {
        extra.branchId = session?.branchId ?? undefined;
        extra.departmentId = session?.departmentId ?? undefined;
      }
      if (teamScoped) extra.teamId = session?.teamId ?? undefined;
      path = `/performance/rankings?${performanceQuery(filters, product, extra, {
        branch: management,
        team: management,
      })}`;
    }
  } else if (activeView === "workload") {
    path = `/performance/coordinator-workload?${performanceQuery(
      filters,
      "",
      paging,
      { branch: management },
    )}`;
  } else if (!product) {
    blocked = {
      title: "Select a Product",
      description:
        "Comparisons need Credit Card or Personal Finance before they can be calculated.",
      icon: "performance",
    };
  } else {
    path = `/performance/comparisons?${performanceQuery(
      filters,
      product,
      { ...paging, groupBy: filters.groupBy },
      { branch: management },
    )}`;
  }

  const resource = useResource<
    EmployeePage | RankingPage | ComparisonPage | Page<CoordinatorItem>
  >(path, refresh);
  const sameView = Boolean(
    resource.dataPath &&
      path &&
      resource.dataPath.split("?")[0] === path.split("?")[0],
  );
  const pageData = sameView ? resource.data : null;
  const pageItems: unknown[] = pageData?.items ?? [];
  const total = pageData?.total ?? 0;
  const exportQuery = new URLSearchParams(path?.split("?")[1] ?? "");
  exportQuery.delete("page");
  exportQuery.delete("pageSize");
  const selection = useTableSelection<unknown>(
    `performance-${activeView}`,
    path && pageData
      ? {
          path: `${path.split("?")[0]}?${exportQuery}`,
          page,
          size: pageSize,
          total,
          busy: resource.loading || Boolean(resource.error),
          positionForRow: (row) => (page - 1) * pageSize + pageItems.indexOf(row),
        }
      : undefined,
  );

  const switchView = useCallback(
    (next: string) => {
      update({ view: next as PerformanceView, page: 1, sort: null });
      setNotice("");
    },
    [update],
  );

  if (!session || !role) return null;

  const draftRangePartial = Boolean(draft.startDate) !== Boolean(draft.endDate);
  const draftValid =
    !draftRangePartial &&
    (activeView !== "rankings" || Boolean(draft.startDate && draft.endDate)) &&
    (activeView !== "team" || teamScoped || Boolean(draft.teamId));

  const departmentOptions = (departments.data ?? [])
    .filter((item) => !draft.branchId || item.branch_id === draft.branchId)
    .map((item) => ({
      value: item.id,
      label: item.name,
      description: namedLabel(branches.data, item.branch_id ?? null),
    }));
  const teamOptions = (teams.data ?? [])
    .filter(
      (team) =>
        (!draft.branchId || team.branch_id === draft.branchId) &&
        (!draft.departmentId || team.department_id === draft.departmentId),
    )
    .map((team) => ({
      value: team.id,
      label: team.name,
      description: departmentLabel(
        departments.data,
        branches.data,
        team.department_id ?? null,
      ),
    }));

  const setDraft = (patch: Partial<PerformanceFilters>) =>
    update({ draft: { ...draft, ...patch } });
  const changeBranch = (branchId: string) => {
    const department = departments.data?.find(
      (item) => item.id === draft.departmentId,
    );
    const team = teams.data?.find((item) => item.id === draft.teamId);
    const departmentId =
      branchId && department?.branch_id !== branchId ? "" : draft.departmentId;
    setDraft({
      branchId,
      departmentId,
      teamId:
        branchId && team?.branch_id !== branchId ? "" : draft.teamId,
    });
  };
  const changeDepartment = (departmentId: string) => {
    const team = teams.data?.find((item) => item.id === draft.teamId);
    setDraft({
      departmentId,
      teamId:
        departmentId && team?.department_id !== departmentId
          ? ""
          : draft.teamId,
    });
  };
  const remove = (patch: Partial<PerformanceFilters>) =>
    applyFilters({ ...filters, ...patch });

  const applied = [
    datesSet && {
      id: "period",
      label: "Period",
      field: "Period",
      value: periodLabel(filters.startDate, filters.endDate),
      onRemove: () => remove({ startDate: "", endDate: "" }),
    },
    management &&
      filters.branchId && {
        id: "branch",
        label: "Branch",
        field: "Branch",
        value: namedLabel(branches.data, filters.branchId),
        onRemove: () =>
          remove({ branchId: "", departmentId: "", teamId: "" }),
      },
    management &&
      filters.departmentId && {
        id: "department",
        label: "Department",
        field: "Department",
        value: departmentLabel(
          departments.data,
          branches.data,
          filters.departmentId,
        ),
        onRemove: () => remove({ departmentId: "", teamId: "" }),
      },
    management &&
      filters.designationId && {
        id: "designation",
        label: "Designation",
        field: "Designation",
        value: namedLabel(designations.data, filters.designationId),
        onRemove: () => remove({ designationId: "" }),
      },
    management &&
      filters.teamId &&
      (activeView === "team" || activeView === "rankings") && {
        id: "team",
        label: "Team",
        field: "Team",
        value: namedLabel(teams.data, filters.teamId),
        onRemove: () => remove({ teamId: "" }),
      },
    management &&
      activeView === "comparisons" &&
      filters.groupBy === "department" && {
        id: "groupBy",
        label: "Group by",
        field: "Group by",
        value: "Department",
        onRemove: () => remove({ groupBy: "branch" }),
      },
  ].filter(Boolean) as AppliedFilter[];

  const showScope = management;
  const showTeam =
    management && (activeView === "team" || activeView === "rankings");
  const filterPanel = (
    <div className={styles.filterPanel}>
      <FormField label="Period" htmlFor="performance-period">
        <DateRangePicker
          id="performance-period"
          compact
          compactRangeLabel
          max={dubaiTodayDateOnly()}
          presets={datePresets()}
          invalid={!draftValid && draftRangePartial}
          value={{ start: draft.startDate, end: draft.endDate }}
          onChange={(range) =>
            setDraft({ startDate: range.start, endDate: range.end })
          }
        />
      </FormField>
      {showScope ? (
        <>
          <FormField label="Branch" htmlFor="performance-branch">
            <DropdownSelect
              id="performance-branch"
              compact
              clearable
              searchable
              placeholder="All Branches"
              value={draft.branchId}
              loading={branches.loading && !branches.data}
              options={(branches.data ?? []).map((item) => ({
                value: item.id,
                label: item.name,
              }))}
              onChange={(value) =>
                changeBranch(Array.isArray(value) ? (value[0] ?? "") : value)
              }
            />
          </FormField>
          <FormField label="Department" htmlFor="performance-department">
            <DropdownSelect
              id="performance-department"
              compact
              clearable
              searchable
              placeholder="All Departments"
              value={draft.departmentId}
              loading={departments.loading && !departments.data}
              options={departmentOptions}
              onChange={(value) =>
                changeDepartment(
                  Array.isArray(value) ? (value[0] ?? "") : value,
                )
              }
            />
          </FormField>
          <FormField label="Designation" htmlFor="performance-designation">
            <DropdownSelect
              id="performance-designation"
              compact
              clearable
              placeholder="All designations"
              value={draft.designationId}
              loading={designations.loading && !designations.data}
              options={(designations.data ?? []).map((item) => ({
                value: item.id,
                label: item.name,
              }))}
              onChange={(value) =>
                setDraft({
                  designationId: Array.isArray(value)
                    ? (value[0] ?? "")
                    : value,
                })
              }
            />
          </FormField>
        </>
      ) : null}
      {showTeam ? (
        <FormField label="Team" htmlFor="performance-team">
          <DropdownSelect
            id="performance-team"
            compact
            clearable
            searchable
            placeholder={activeView === "team" ? "Select a Team" : "All Teams"}
            value={draft.teamId}
            loading={teams.loading && !teams.data}
            options={teamOptions}
            onChange={(value) =>
              setDraft({
                teamId: Array.isArray(value) ? (value[0] ?? "") : value,
              })
            }
          />
        </FormField>
      ) : null}
      {management && activeView === "comparisons" ? (
        <FormField label="Group by" htmlFor="performance-group">
          <DropdownSelect
            id="performance-group"
            compact
            clearable={false}
            value={draft.groupBy}
            options={[
              { value: "branch", label: "Branch" },
              { value: "department", label: "Department" },
            ]}
            onChange={(value) => {
              const next = Array.isArray(value) ? value[0] : value;
              setDraft({ groupBy: next === "department" ? "department" : "branch" });
            }}
          />
        </FormField>
      ) : null}
      {!draftValid ? (
        <p className={styles.panelHint} role="status">
          {draftRangePartial
            ? "Select both a start date and an end date."
            : activeView === "rankings"
              ? "Rankings need a complete date range."
              : "Select a Team to apply."}
        </p>
      ) : null}
    </div>
  );

  const ranking = activeView === "rankings" ? (pageData as RankingPage | null) : null;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const toggleSort = (key: string) =>
    update({
      sort:
        sort?.key === key
          ? { key, direction: sort.direction === "asc" ? "desc" : "asc" }
          : { key, direction: "asc" },
      page: 1,
    });

  const localQuery = activeView === "employees" ? "" : search.trim().toLowerCase();
  const matches = (values: (string | null | undefined)[]) =>
    !localQuery ||
    values.some((value) => value?.toLowerCase().includes(localQuery));
  const selectable = <T,>(rows: T[], key: (row: T) => string) =>
    selection.allowed
      ? {
          selectedKeys: rows
            .filter((row, index) => selection.checked(row, index))
            .map(key),
          onToggleRow: (value: string) => {
            const index = rows.findIndex((row) => key(row) === value);
            if (index >= 0) selection.toggleRow(rows[index], index);
          },
          onToggleAll: localQuery
            ? () => selection.toggleRows(rows)
            : selection.toggleAll,
        }
      : {};

  const confirmRanking = async () => {
    if (!ranking || !candidate || !path) return;
    setConfirmBusy(true);
    setConfirmError("");
    const query = new URLSearchParams(path.split("?")[1]);
    for (const key of ["page", "pageSize", "sort", "direction"]) query.delete(key);
    try {
      await api.request(`/performance/rankings/confirm?${query}`, {
        method: "POST",
        body: JSON.stringify({ selectedEmployeeId: candidate }),
      });
      setConfirming(false);
      setNotice("Ranking winner confirmed.");
      setRefresh((value) => value + 1);
    } catch (failure) {
      setConfirmError(confirmMessage(failure));
    } finally {
      setConfirmBusy(false);
    }
  };

  const summary =
    activeView === "employees" || activeView === "team"
      ? ((pageData as EmployeePage | null)?.summary ?? null)
      : null;

  let table: ReactNode = null;
  let charts: ReactNode = null;
  let visibleCount = 0;

  if (pageData && (activeView === "employees" || activeView === "team")) {
    const rows = (pageData as EmployeePage).items.filter((row) =>
      matches([row.employeeName, row.systemEmployeeCode, row.companyEmployeeCode]),
    );
    visibleCount = rows.length;
    const columns: DataTableColumn<EmployeeMetrics>[] = [
      { key: "name", header: "Employee", width: "220px", sortable: true, render: (row) => <Person row={row} /> },
      { key: "code", header: "Employee code", width: "130px", render: (row) => <Text value={personCode(row)} /> },
      { key: "designation", header: "Designation", width: "150px", render: (row) => <Text value={readable(row.designation)} /> },
      { key: "branch", header: "Branch", width: "130px", render: (row) => <Text value={readable(row.branchName)} /> },
      { key: "department", header: "Department", width: "150px", render: (row) => <Text value={readable(row.departmentName)} /> },
      { key: "created", header: "Created", width: "100px", kind: "number", sortable: true, render: (row) => row.createdCaseCount },
      { key: "booked", header: "Booked", width: "100px", kind: "number", sortable: true, render: (row) => row.bookedCaseCount },
      { key: "completed", header: "Completed", width: "110px", kind: "number", sortable: true, render: (row) => row.completedCaseCount },
      ...(product !== "PF"
        ? [{ key: "ccPoints", header: "CC points", width: "110px", kind: "number" as const, sortable: true, render: (row: EmployeeMetrics) => <Points value={row.achievedCCPoints} /> }]
        : []),
      ...(product !== "CC"
        ? [{ key: "pfAmount", header: "PF amount", width: "120px", kind: "money" as const, sortable: true, render: (row: EmployeeMetrics) => <MonetaryAmount compact={false} value={row.achievedPFAed} /> }]
        : []),
      { key: "achievement", header: "Achievement", width: product ? "120px" : "190px", render: (row) => <Achievement row={row} product={product} /> },
    ];
    table = (
      <DataTable
        ariaLabel={`${VIEW_LABEL[activeView]} performance`}
        density="compact"
        columns={columns}
        rows={rows}
        rowKey={(row) => row.employeeId}
        {...selectable(rows, (row) => row.employeeId)}
        sort={sort}
        onSort={toggleSort}
        loading={resource.loading && !pageData}
        onRowActivate={(row) => open(row.employeeId)}
        rowActivateLabel={(row) => `Open performance for ${personName(row)}`}
        empty={
          localQuery || debouncedSearch ? (
            <NoResultsState />
          ) : (
            <EmptyState
              title="No performance records"
              description="No authorized employees match the selected scope."
            />
          )
        }
      />
    );
    charts = summary ? (
      <ChartGrid>
        <OutcomeChart summary={summary} refreshing={resource.updating} />
        <StageChart summary={summary} refreshing={resource.updating} />
      </ChartGrid>
    ) : null;
  } else if (ranking) {
    const rows = ranking.items.filter((row) => matches([row.employeeName]));
    visibleCount = rows.length;
    const columns: DataTableColumn<RankingItem>[] = [
      { key: "rank", header: "Rank", width: "80px", kind: "number", sortable: true, render: (row) => row.rank },
      { key: "name", header: "Employee", width: "220px", sortable: true, render: (row) => <Text value={readable(row.employeeName) || "Team member"} /> },
      { key: "achievement", header: "Achievement", width: "130px", kind: "number", sortable: true, render: (row) => formatFullPercent(amount(row.achievementPercentage)) },
      { key: "completed", header: "Completed", width: "120px", kind: "number", sortable: true, render: (row) => row.completedCaseCount },
      {
        key: "achieved",
        header: product === "PF" ? "PF amount" : "CC points",
        width: "130px",
        kind: product === "PF" ? "money" : "number",
        render: (row) =>
          product === "PF" ? <MonetaryAmount compact={false} value={row.achievedValue} /> : <Points value={row.achievedValue} />,
      },
      {
        key: "status",
        header: "Status",
        width: "130px",
        render: (row) =>
          row.employeeId === ranking.winnerEmployeeId ? (
            <StatusBadge tone="success">Winner</StatusBadge>
          ) : ranking.tiedCandidateIds.includes(row.employeeId) ? (
            <StatusBadge tone="warning">Tied</StatusBadge>
          ) : (
            <EmptyValue />
          ),
      },
    ];
    table = (
      <DataTable
        ariaLabel="Performance rankings"
        density="compact"
        columns={columns}
        rows={rows}
        rowKey={(row) => row.employeeId}
        {...selectable(rows, (row) => row.employeeId)}
        sort={sort}
        onSort={toggleSort}
        onRowActivate={(row) => open(row.employeeId)}
        rowActivateLabel={(row) => `Open performance for ${readable(row.employeeName) || "Team member"}`}
        empty={localQuery ? <NoResultsState /> : <EmptyState title="No eligible employees" description="No employees are eligible for this ranking period." />}
      />
    );
  } else if (pageData && activeView === "workload") {
    const rows = (pageData as Page<CoordinatorItem>).items.filter((row) =>
      matches([row.employeeName, row.systemEmployeeCode, row.companyEmployeeCode]),
    );
    visibleCount = rows.length;
    const columns: DataTableColumn<CoordinatorItem>[] = [
      { key: "name", header: "Coordinator", width: "220px", sortable: true, render: (row) => <Person row={row} /> },
      { key: "code", header: "Employee code", width: "130px", render: (row) => <Text value={personCode(row)} /> },
      { key: "branch", header: "Branch", width: "130px", render: (row) => <Text value={readable(row.branchName)} /> },
      { key: "handled", header: "Handled cases", width: "130px", kind: "number", sortable: true, render: (row) => row.handledCases },
      { key: "booked", header: "Booked submissions", width: "160px", kind: "number", sortable: true, render: (row) => row.submittedBookedCases },
      { key: "stages", header: "Stage updates", width: "130px", kind: "number", sortable: true, render: (row) => row.stageUpdatedCases },
    ];
    table = (
      <DataTable
        ariaLabel="Coordinator workload"
        density="compact"
        columns={columns}
        rows={rows}
        rowKey={(row) => row.employeeId}
        {...selectable(rows, (row) => row.employeeId)}
        sort={sort}
        onSort={toggleSort}
        empty={localQuery ? <NoResultsState /> : <EmptyState title="No Coordinator workload" description="No authorized Coordinators have workload in this scope." />}
      />
    );
    charts = (
      <ChartGrid>
        <ChartCard
          title="Coordinator workload"
          description="Coordinators shown on this page"
          actions={resource.updating ? <Refreshing /> : undefined}
          state={rows.length ? "ready" : "empty"}
        >
          <BarChart
            grouped
            labels={rows.slice(0, 8).map((row) => personName(row))}
            series={[
              { id: "handled", label: "Handled cases", values: rows.slice(0, 8).map((row) => row.handledCases) },
              { id: "booked", label: "Booked submissions", values: rows.slice(0, 8).map((row) => row.submittedBookedCases) },
              { id: "stages", label: "Stage updates", values: rows.slice(0, 8).map((row) => row.stageUpdatedCases) },
            ]}
          />
        </ChartCard>
      </ChartGrid>
    );
  } else if (pageData && activeView === "comparisons" && product) {
    const comparison = pageData as ComparisonPage;
    const groupLabel = (row: ComparisonItem) =>
      comparison.groupBy === "department"
        ? departmentLabel(departments.data, branches.data, row.id) === "Unavailable"
          ? readable(row.name) || "Unavailable"
          : departmentLabel(departments.data, branches.data, row.id)
        : readable(row.name) || "Unavailable";
    const rows = comparison.items.filter((row) => matches([groupLabel(row)]));
    visibleCount = rows.length;
    const columns: DataTableColumn<ComparisonItem>[] = [
      { key: "name", header: comparison.groupBy === "department" ? "Department" : "Branch", width: "220px", sortable: true, render: (row) => <Text value={groupLabel(row)} /> },
      { key: "created", header: "Created", width: "100px", kind: "number", sortable: true, render: (row) => row.createdCaseCount },
      { key: "booked", header: "Booked", width: "100px", kind: "number", sortable: true, render: (row) => row.bookedCaseCount },
      { key: "completed", header: "Completed", width: "110px", kind: "number", sortable: true, render: (row) => row.completedCaseCount },
      product === "CC"
        ? { key: "ccPoints", header: "CC points", width: "120px", kind: "number", sortable: true, render: (row) => <Points value={row.achievedCCPoints} /> }
        : { key: "pfAmount", header: "PF amount", width: "120px", kind: "money", sortable: true, render: (row) => <MonetaryAmount compact={false} value={row.achievedPFAed} /> },
      { key: "achievement", header: "Achievement", width: "120px", render: (row) => <Achievement row={row} product={product} /> },
    ];
    table = (
      <DataTable
        ariaLabel="Performance comparison"
        density="compact"
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        {...selectable(rows, (row) => row.id)}
        sort={sort}
        onSort={toggleSort}
        empty={localQuery ? <NoResultsState /> : <EmptyState title="No comparison results" description="No authorized groups have results for this scope." />}
      />
    );
    const chartRows = rows.slice(0, 8);
    charts = (
      <ChartGrid>
        <ChartCard
          title="Case outcomes by group"
          description={`${PRODUCT_LABEL[product]} booked and completed cases`}
          actions={resource.updating ? <Refreshing /> : undefined}
          state={chartRows.length ? "ready" : "empty"}
        >
          <BarChart
            grouped
            labels={chartRows.map(groupLabel)}
            series={[
              { id: "booked", label: "Booked", color: PRODUCT_COLOR[product], values: chartRows.map((row) => row.bookedCaseCount) },
              { id: "completed", label: "Completed", color: "var(--ds-chart-2)", values: chartRows.map((row) => row.completedCaseCount) },
            ]}
          />
        </ChartCard>
        <ChartCard
          title={product === "CC" ? "CC points by group" : "PF amount by group"}
          description={`${PRODUCT_LABEL[product]} achieved`}
          actions={resource.updating ? <Refreshing /> : undefined}
          state={valuesState(
            "ready",
            chartRows.map((row) =>
              amount(product === "CC" ? row.achievedCCPoints : row.achievedPFAed),
            ),
          )}
        >
          <BarChart
            labels={chartRows.map(groupLabel)}
            kind={product === "CC" ? "points" : "currency"}
            series={[
              {
                id: "achieved",
                label: product === "CC" ? "CC points" : "PF amount",
                color: PRODUCT_COLOR[product],
                values: chartRows.map((row) =>
                  amount(product === "CC" ? row.achievedCCPoints : row.achievedPFAed),
                ),
              },
            ]}
          />
        </ChartCard>
      </ChartGrid>
    );
  }

  const tiedOptions = (ranking?.tiedCandidateIds ?? []).map((employeeId, index) => ({
    value: employeeId,
    label:
      readable(ranking?.items.find((item) => item.employeeId === employeeId)?.employeeName) ||
      `Tied candidate ${index + 1}`,
  }));

  let body: ReactNode;
  if (blocked) {
    body = (
      <EmptyState
        title={blocked.title}
        description={blocked.description}
        icon={<DsIcon name={blocked.icon} size={24} />}
      />
    );
  } else if (resource.denied) {
    body = (
      <PermissionDeniedState description="This performance scope is outside your authorized access." />
    );
  } else if (!pageData && resource.error) {
    body = (
      <ErrorState
        description="Performance could not be loaded for the selected scope."
        retry={resource.reload}
      />
    );
  } else {
    body = (
      <>
        {resource.error ? (
          <InlineNotice tone="warning" title="Not updated">
            The latest selection could not be loaded. The values shown are from
            the previous selection.
          </InlineNotice>
        ) : null}
        {summary ? (
          <PerformanceSummary metrics={metricCards(summary, product)} />
        ) : null}
        {ranking && ranking.decisionState !== "No eligible employees" ? (
          <RankingDecision
            ranking={ranking}
            canConfirm={role === "Owner"}
            busy={resource.updating}
            onConfirm={() => {
              setCandidate("");
              setConfirmError("");
              setConfirming(true);
            }}
          />
        ) : null}
        {charts}
        <div className={styles.tableBlock}>
          {pageData ? (
            <RecordCount count={localQuery ? visibleCount : total} />
          ) : null}
          {table ?? (
            <DataTable
              ariaLabel={`${VIEW_LABEL[activeView]} performance`}
              density="compact"
              columns={[]}
              rows={[]}
              rowKey={() => ""}
              loading
            />
          )}
          {total > pageSize || pageSize !== 25 ? (
            <Pagination
              page={Math.min(page, pageCount)}
              pageCount={pageCount}
              onPageChange={(next) => update({ page: next })}
              pageSize={pageSize}
              onPageSizeChange={(size) => update({ pageSize: size, page: 1 })}
            />
          ) : null}
        </div>
      </>
    );
  }

  return (
    <PageContainer>
      <div className={styles.page}>
        <PageHeader
          title="Performance"
          subtitle="Server-calculated achievements within your authorized scope"
        />
        {views.length > 1 ? (
          <Tabs
            label="Performance views"
            value={activeView}
            onChange={switchView}
            items={views.map((item) => ({ id: item, label: VIEW_LABEL[item] }))}
          />
        ) : null}
        <SearchFilterToolbar
          searchId="performance-search"
          searchLabel="Search"
          searchValue={search}
          onSearchChange={(value) => update({ search: value, page: activeView === "employees" ? 1 : page })}
          searchPlaceholder={
            activeView === "employees"
              ? "Search by employee name or code"
              : activeView === "comparisons"
                ? "Search groups on this page"
                : "Search employees on this page"
          }
          filters={
            activeView === "workload"
              ? undefined
              : [
                  {
                    id: "performance-product",
                    label: "Product",
                    value: product || "all",
                    options: [
                      ...(activeView === "rankings" || activeView === "comparisons"
                        ? []
                        : [{ value: "all", label: "All products" }]),
                      ...productOptions.map(({ value, label }) => ({ value, label })),
                    ],
                    onChange: (value) =>
                      setProduct(value === "CC" || value === "PF" ? value : ""),
                  },
                ]
          }
          applied={applied}
          onClearFilters={
            applied.length
              ? () => applyFilters({ ...emptyFilters, groupBy: filters.groupBy })
              : undefined
          }
          filterPanel={filterPanel}
          onApplyFilters={draftValid ? () => applyFilters(draft) : undefined}
          onResetFilters={() => update({ draft: emptyFilters })}
          actions={
            selection.allowed && !blocked ? (
              <ExportButton
                size="compact"
                selectedCount={selection.selectedCount}
                loading={selection.working}
                disabled={!selection.selectedCount}
                onClick={() => void selection.exportCsv()}
              />
            ) : undefined
          }
        />
        {selection.error ? (
          <InlineNotice tone="error" title="Export failed">
            The CSV export could not be completed. Refresh and try again.
          </InlineNotice>
        ) : null}
        {notice ? (
          <InlineNotice tone="success" title="Confirmed">
            {notice}
          </InlineNotice>
        ) : null}
        {body}
      </div>

      <Dialog
        open={confirming}
        title="Confirm ranking winner"
        description="Select the winner from the employees tied for first place."
        size="sm"
        busy={confirmBusy}
        onClose={() => {
          if (!confirmBusy) setConfirming(false);
        }}
        footer={
          <>
            <Button
              variant="secondary"
              disabled={confirmBusy}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </Button>
            <Button
              loading={confirmBusy}
              disabled={!candidate}
              onClick={() => void confirmRanking()}
            >
              Confirm winner
            </Button>
          </>
        }
      >
        <RadioGroup
          legend="Tied candidates"
          name="ranking-candidate"
          layout="vertical"
          value={candidate}
          options={tiedOptions}
          onChange={setCandidate}
          error={confirmError || undefined}
          disabled={confirmBusy}
        />
      </Dialog>
    </PageContainer>
  );
}

function Refreshing() {
  return <span className={styles.refreshing}>Refreshing…</span>;
}

function OutcomeChart({
  summary,
  refreshing,
}: {
  summary: PerformanceSummaryValues;
  refreshing: boolean;
}) {
  const outcomes = outcomeSeries(summary);
  return (
    <ChartCard
      title="Case outcomes"
      description="Created, booked, completed, rejected and in-progress cases"
      actions={refreshing ? <Refreshing /> : undefined}
      state={outcomes.values.some(Boolean) ? "ready" : "empty"}
    >
      <BarChart
        labels={outcomes.labels}
        series={[{ id: "cases", label: "Cases", values: outcomes.values }]}
      />
    </ChartCard>
  );
}

function StageChart({
  summary,
  refreshing,
}: {
  summary: PerformanceSummaryValues;
  refreshing: boolean;
}) {
  const stages = stageSeries(summary);
  return (
    <ChartCard
      title="In progress by stage"
      description="Open cases at each current stage"
      actions={refreshing ? <Refreshing /> : undefined}
      state={stages.labels.length ? "ready" : "empty"}
    >
      <BarChart
        labels={stages.labels}
        series={[{ id: "stage", label: "Cases", values: stages.values }]}
      />
    </ChartCard>
  );
}

function RankingDecision({
  ranking,
  canConfirm,
  busy,
  onConfirm,
}: {
  ranking: RankingPage;
  canConfirm: boolean;
  busy: boolean;
  onConfirm: () => void;
}) {
  const winner = ranking.items.find(
    (item) => item.employeeId === ranking.winnerEmployeeId,
  );
  const pending = ranking.decisionState === "Owner decision pending";
  return (
    <InlineNotice
      tone={pending ? "warning" : "info"}
      title={ranking.decisionState}
    >
      <span className={styles.decision}>
        <span>
          {winner
            ? `Winner: ${readable(winner.employeeName) || "Team member"}`
            : pending
              ? `${ranking.tiedCandidateIds.length} employees are tied for first place.`
              : ranking.decisionState === "No eligible employees"
                ? "No employees are eligible for this period."
                : "The winner is outside the current page."}
          {ranking.confirmedAt
            ? ` · Confirmed ${formatDubaiTimestamp(ranking.confirmedAt)}`
            : ""}
        </span>
        {pending && canConfirm ? (
          <Button size="compact" disabled={busy} onClick={onConfirm}>
            Confirm winner
          </Button>
        ) : null}
      </span>
    </InlineNotice>
  );
}
