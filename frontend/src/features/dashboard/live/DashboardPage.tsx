import { useState, type ReactNode } from "react";
import {
  BarChart,
  Button,
  ChartCard,
  ChartGrid,
  DataTable,
  DsIcon,
  DropdownSelect,
  ErrorState,
  ExportButton,
  FilterToolbar,
  FilterToolbarItem,
  InlineNotice,
  KpiSummary,
  LineChart,
  LoadingState,
  MonetaryAmount,
  PageContainer,
  PageHeader,
  PermissionDeniedState,
  SectionCard,
  StatusSummary,
  formatCompactDateRange,
  formatFullNumber,
  formatMonthYear,
  type DataTableColumn,
  type KpiItem,
} from "../../../design-system";
import type { Designation } from "../../../access";
import { choices } from "../../../app/api/choices";
import type { ApiClient } from "../../../app/api/http";
import type { NamedRecord } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import { useTableSelection } from "../../../shared/table/useTableSelection";
import { namedLabel } from "../../employees/live/employeePresentation";
import { ReportsPage } from "../../reports/ReportsPage";
import {
  PRODUCTS,
  PRODUCT_COLOR,
  PRODUCT_LABEL,
  amount,
  productOptions,
  readable,
  valuesState,
  type ComparisonItem,
  type Product,
  type RankingPage,
} from "../../performance/live/performancePresentation";
import styles from "./DashboardPage.module.css";

type Period = "today" | "week" | "month" | "year";
type Scope = {
  branchId: string;
  departmentId: string;
  bankId: string;
  productCode: Product | "";
};
type Numeric = number | string | null | undefined;
type Summary = Record<string, Numeric>;
type DashboardData = {
  startDate: string;
  endDate: string;
  openTaskCount: number;
  unreadNotificationCount: number;
  performance?: Summary;
  teamPerformance?: Summary;
  attendance?: Summary;
  assets?: Summary;
  employees?: Summary;
  bookedCases?: Partial<Record<Product, number>>;
  ranking?: Partial<
    Record<Product, { employeeOfMonth: RankingPage; highestPerformer: RankingPage }>
  >;
  branchComparison?: Partial<Record<Product, ComparisonItem[]>>;
  charts?: { caseActivity?: Record<string, number> };
};
type MonthItem = {
  start: string;
  end: string;
  label: string;
  cc: number | null;
  pf: number | null;
  pfAed: string | null;
};
type Monthly = { startDate: string; endDate: string; items: MonthItem[] };
type Department = NamedRecord & { branch_id?: string };

const PERIODS: { value: Period; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "week", label: "This week" },
  { value: "month", label: "This month" },
  { value: "year", label: "This year" },
];
const SCOPE_ROLES: Designation[] = [
  "Owner",
  "Managing Director",
  "Sales Manager",
  "Finance",
];
const CHART_ROLES: Designation[] = [
  ...SCOPE_ROLES,
  "Coordinator",
  "Team Leader",
  "Sales Executive",
];
const emptyScope: Scope = {
  branchId: "",
  departmentId: "",
  bankId: "",
  productCode: "",
};

function loadBanks(api: ApiClient, path: string, signal: AbortSignal) {
  return choices<NamedRecord>(api, path, signal);
}

function count(value: Numeric) {
  return formatFullNumber(amount(value));
}

function rankingWinner(page: RankingPage | undefined) {
  if (!page) return "Unavailable";
  const winner = page.items.find(
    (item) => item.employeeId === page.winnerEmployeeId,
  );
  return readable(winner?.employeeName) || page.decisionState;
}

function roleKpis(
  role: Designation,
  data: DashboardData,
  product: Product | "",
): KpiItem[] {
  const perf = data.performance ?? {};
  const showCC = product !== "PF";
  const showPF = product !== "CC";
  if (role === "Owner" || role === "Managing Director") {
    const items: KpiItem[] = [
      { id: "created", label: "Total cases", value: count(perf.createdCases) },
      ...PRODUCTS.filter((code) => !product || code === product).map(
        (code): KpiItem => ({
          id: `booked-${code}`,
          label: `${code} booked`,
          value: count(data.bookedCases?.[code]),
          meta: PRODUCT_LABEL[code],
        }),
      ),
      { id: "completed", label: "Completed", value: count(perf.completedCases) },
    ];
    if (product) {
      const ranking = data.ranking?.[product];
      items.push(
        {
          id: "month-winner",
          label: "Employee of the month",
          value: <span className={styles.person}>{rankingWinner(ranking?.employeeOfMonth)}</span>,
          meta: PRODUCT_LABEL[product],
        },
        {
          id: "top-performer",
          label: "Top performer",
          value: <span className={styles.person}>{rankingWinner(ranking?.highestPerformer)}</span>,
          meta: PRODUCT_LABEL[product],
        },
      );
    }
    return items;
  }
  if (role === "Sales Manager" || role === "Finance") {
    return [
      { id: "employees", label: "Employees", value: count(perf.employees) },
      { id: "created", label: "Created", value: count(perf.createdCases) },
      { id: "booked", label: "Booked", value: count(perf.bookedCases) },
      { id: "completed", label: "Completed", value: count(perf.completedCases) },
      ...(showCC
        ? [{ id: "cc", label: "CC points", value: count(perf.achievedCCPoints) }]
        : []),
      ...(showPF
        ? [
            {
              id: "pf",
              label: "PF amount",
              value: <MonetaryAmount compact={false} value={perf.achievedPFAed} align="start" />,
            },
          ]
        : []),
    ];
  }
  if (role === "Team Leader" || role === "Sales Executive") {
    return [
      { id: "created", label: "Created", value: count(perf.createdCaseCount) },
      { id: "booked", label: "Booked", value: count(perf.bookedCaseCount) },
      { id: "completed", label: "Completed", value: count(perf.completedCaseCount) },
      { id: "cc", label: "CC points", value: count(perf.achievedCCPoints) },
      {
        id: "pf",
        label: "PF amount",
        value: <MonetaryAmount compact={false} value={perf.achievedPFAed} align="start" />,
      },
    ];
  }
  if (role === "Coordinator") {
    return [
      { id: "created", label: "Created", value: count(perf.createdCaseCount) },
      { id: "booked", label: "Booked", value: count(perf.bookedCaseCount) },
      { id: "completed", label: "Completed", value: count(perf.completedCaseCount) },
      { id: "rejected", label: "Rejected", value: count(perf.rejectedCaseCount) },
    ];
  }
  if (role === "Admin Staff") {
    const attendance = data.attendance;
    const assets = data.assets;
    return [
      ...(attendance
        ? [
            { id: "present", label: "Present", value: count(attendance.presentCount) },
            { id: "late", label: "Late", value: count(attendance.lateCount) },
            { id: "absent", label: "Absent", value: count(attendance.absentCount) },
          ]
        : []),
      ...(assets
        ? [
            { id: "available", label: "Available assets", value: count(assets.availableCount) },
            { id: "issued", label: "Issued assets", value: count(assets.issuedCount) },
          ]
        : []),
    ];
  }
  const people = data.employees ?? {};
  return [
    { id: "total", label: "Total employees", value: count(people.totalEmployees) },
    { id: "active", label: "Active", value: count(people.activeEmployees) },
    { id: "offboarded", label: "Offboarded", value: count(people.offboardedEmployees) },
  ];
}

export function DashboardPage({
  openTasks,
  openNotifications,
}: {
  openTasks: () => void;
  openNotifications: () => void;
}) {
  const { session } = useSession();
  const [period, setPeriod] = useState<Period>("month");
  const [scope, setScope] = useState<Scope>(emptyScope);
  const [reports, setReports] = useState(false);
  const [monthlyOpen, setMonthlyOpen] = useState(false);
  const role = session?.designation;
  const scoped = Boolean(role && SCOPE_ROLES.includes(role));
  const charted = Boolean(role && CHART_ROLES.includes(role));

  const query = new URLSearchParams({ period });
  if (scoped)
    for (const [key, value] of Object.entries(scope))
      if (value) query.set(key, value);
  const dashboard = useResource<DashboardData>(
    session ? `/dashboard?${query}` : null,
  );
  const monthlyPath = `/dashboard/monthly-activity?${query}`;
  const monthly = useResource<Monthly>(session && charted ? monthlyPath : null);
  const branches = useResource<NamedRecord[]>(scoped ? "/branches" : null);
  const departments = useResource<Department[]>(scoped ? "/departments" : null);
  const banks = useResource<NamedRecord[]>(
    scoped ? "/catalog/banks" : null,
    0,
    loadBanks,
    "choices",
  );
  const months = monthly.data?.items ?? [];
  const selection = useTableSelection<MonthItem>("dashboard-monthly-activity", {
    path: monthlyPath,
    page: 1,
    size: Math.max(1, months.length),
    total: months.length,
    busy: monthly.loading || Boolean(monthly.error),
    rowForSelection: (item) => item,
    positionForRow: (item) => months.indexOf(item),
  });

  if (!session || !role) return null;
  if (reports)
    return (
      <ReportsPage
        back={() => setReports(false)}
        only={role === "HR" ? ["hr-employees"] : ["attendance", "assets"]}
      />
    );

  const data = dashboard.data;
  const product = scoped ? scope.productCode : "";
  const coordinator = role === "Coordinator";
  const products = product ? [product] : PRODUCTS;
  const departmentOptions = (departments.data ?? [])
    .filter((item) => !scope.branchId || item.branch_id === scope.branchId)
    .map((item) => ({
      value: item.id,
      label: item.name,
      description: namedLabel(branches.data, item.branch_id ?? null),
    }));
  const pick = (value: string | string[]) =>
    Array.isArray(value) ? (value[0] ?? "") : value;

  const filters = (
    <FilterToolbar label="Dashboard filters" className={styles.filters}>
      <div className={styles.filterGroup}>
        <FilterToolbarItem label="Period" htmlFor="dashboard-period">
          <DropdownSelect
            id="dashboard-period"
            compact
            clearable={false}
            value={period}
            options={PERIODS}
            onChange={(value) => setPeriod((pick(value) as Period) || "month")}
          />
        </FilterToolbarItem>
        {scoped ? (
          <>
            <FilterToolbarItem label="Branch" htmlFor="dashboard-branch">
              <DropdownSelect
                id="dashboard-branch"
                compact
                clearable
                searchable
                placeholder="All Branches"
                value={scope.branchId}
                loading={branches.loading && !branches.data}
                options={(branches.data ?? []).map((item) => ({
                  value: item.id,
                  label: item.name,
                }))}
                onChange={(value) => {
                  const branchId = pick(value);
                  const department = departments.data?.find(
                    (item) => item.id === scope.departmentId,
                  );
                  setScope({
                    ...scope,
                    branchId,
                    departmentId:
                      branchId && department?.branch_id !== branchId
                        ? ""
                        : scope.departmentId,
                  });
                }}
              />
            </FilterToolbarItem>
            <FilterToolbarItem
              label="Department"
              htmlFor="dashboard-department"
            >
              <DropdownSelect
                id="dashboard-department"
                compact
                clearable
                searchable
                placeholder="All Departments"
                value={scope.departmentId}
                loading={departments.loading && !departments.data}
                options={departmentOptions}
                onChange={(value) =>
                  setScope({ ...scope, departmentId: pick(value) })
                }
              />
            </FilterToolbarItem>
            <FilterToolbarItem label="Bank" htmlFor="dashboard-bank">
              <DropdownSelect
                id="dashboard-bank"
                compact
                clearable
                searchable
                placeholder="All Banks"
                value={scope.bankId}
                loading={banks.loading && !banks.data}
                options={(banks.data ?? []).map((item) => ({
                  value: item.id,
                  label: item.name,
                }))}
                onChange={(value) =>
                  setScope({ ...scope, bankId: pick(value) })
                }
              />
            </FilterToolbarItem>
            <FilterToolbarItem label="Product" htmlFor="dashboard-product">
              <DropdownSelect
                id="dashboard-product"
                compact
                clearable
                placeholder="All products"
                value={scope.productCode}
                options={productOptions}
                onChange={(value) => {
                  const next = pick(value);
                  setScope({
                    ...scope,
                    productCode: next === "CC" || next === "PF" ? next : "",
                  });
                }}
              />
            </FilterToolbarItem>
          </>
        ) : null}
      </div>
      <div className={styles.filterActions}>
        <Button size="compact" onClick={openTasks}>
          <DsIcon name="tasks" size={16} />
          Tasks
        </Button>
      </div>
    </FilterToolbar>
  );

  const header = (
    <PageHeader
      title="Dashboard"
      subtitle={`${readable(session.displayName) || "Welcome"} · ${role}${
        data ? ` · ${formatCompactDateRange(data.startDate, data.endDate)}` : ""
      }`}
      actions={
        <div className={styles.headerActions}>
          {role === "HR" || role === "Admin Staff" ? (
            <Button
              variant="secondary"
              size="compact"
              onClick={() => setReports(true)}
            >
              <DsIcon name="reports" size={16} />
              Reports
            </Button>
          ) : null}
        </div>
      }
    />
  );

  let body: ReactNode;
  if (dashboard.denied) {
    body = (
      <PermissionDeniedState description="The Dashboard is outside your authorized scope." />
    );
  } else if (!data) {
    body = dashboard.error ? (
      <ErrorState
        description="The Dashboard could not be loaded for the selected period."
        retry={dashboard.reload}
      />
    ) : (
      <LoadingState
        title="Loading Dashboard"
        description="Retrieving your authorized summary…"
      />
    );
  } else {
    const monthLabels = months.map((item) => formatMonthYear(item.label));
    const monthlyState = monthly.denied
      ? "permission"
      : monthly.error && !monthly.data
        ? "error"
        : !monthly.data
          ? "loading"
          : months.length
            ? "ready"
            : "empty";
    const showAmount = !coordinator && products.includes("PF");
    const monthColumns: DataTableColumn<MonthItem>[] = [
      {
        key: "month",
        header: "Month",
        width: "110px",
        render: (item) => formatMonthYear(item.label),
      },
      ...products.map((code): DataTableColumn<MonthItem> => ({
        key: code,
        header: `${code} cases`,
        width: "110px",
        kind: "number",
        render: (item) => {
          const value = code === "CC" ? item.cc : item.pf;
          return value == null ? "—" : formatFullNumber(value);
        },
      })),
      ...(showAmount
        ? [
            {
              key: "pfAed",
              header: "PF amount",
              width: "130px",
              kind: "money" as const,
              render: (item: MonthItem) => (
                <MonetaryAmount compact={false} value={item.pfAed} />
              ),
            },
          ]
        : []),
    ];
    const activity = data.charts?.caseActivity;
    const activityKeys = activity ? Object.keys(activity) : [];
    const activityLabel: Record<string, string> = {
      createdCases: "Created",
      bookedCases: "Booked",
      completedCases: "Completed",
      rejectedCases: "Rejected",
    };
    const kpis = roleKpis(role, data, product);

    body = (
      <>
        {dashboard.updating ? (
          <InlineNotice tone="info" title="Refreshing">
            Updating the Dashboard. Current values stay visible until the update
            completes.
          </InlineNotice>
        ) : null}
        {dashboard.error ? (
          <InlineNotice tone="warning" title="Not updated">
            The latest selection could not be loaded. The values shown are from
            the previous selection.
          </InlineNotice>
        ) : null}
        <div className={styles.content}>
          <div className={styles.main}>
            {kpis.length ? <KpiSummary compact items={kpis} /> : null}

            {charted ? (
              <ChartGrid>
                <ChartCard
                  emptyMessage="No activity for the selected period."
                  title={coordinator ? "Handled Case trend" : "Case activity"}
                  description={`${coordinator ? "Handled" : "Created"} cases by month`}
                  legend={products.map((code) => ({
                    id: code,
                    label: PRODUCT_LABEL[code],
                    color: PRODUCT_COLOR[code],
                  }))}
                  state={valuesState(
                    monthlyState,
                    months.flatMap((item) => [
                      amount(item.cc),
                      amount(item.pf),
                    ]),
                  )}
                  retry={monthly.reload}
                >
                  <BarChart
                    grouped
                    labels={monthLabels}
                    series={products.map((code) => ({
                      id: code,
                      label: PRODUCT_LABEL[code],
                      color: PRODUCT_COLOR[code],
                      values: months.map((item) =>
                        amount(code === "CC" ? item.cc : item.pf),
                      ),
                    }))}
                  />
                </ChartCard>
                {showAmount ? (
                  <ChartCard
                    emptyMessage="No activity for the selected period."
                    title="PF amount by month"
                    description="Personal Finance amount achieved"
                    state={valuesState(
                      monthlyState,
                      months.map((item) => amount(item.pfAed)),
                    )}
                    retry={monthly.reload}
                  >
                    <LineChart
                      labels={monthLabels}
                      kind="currency"
                      series={[
                        {
                          id: "pf",
                          label: "PF amount",
                          color: PRODUCT_COLOR.PF,
                          values: months.map((item) => amount(item.pfAed)),
                        },
                      ]}
                    />
                  </ChartCard>
                ) : null}
              </ChartGrid>
            ) : null}

            {activity || data.branchComparison ? (
              <div className={styles.comparisonCharts}>
                {activity ? (
                  <ChartCard
                    emptyMessage="No activity for the selected period."
                    title="Selected-period activity"
                    description="Case outcomes in the authorized scope"
                    state={
                      activityKeys.some((key) => activity[key])
                        ? "ready"
                        : "empty"
                    }
                  >
                    <BarChart
                      labels={activityKeys.map(
                        (key) => activityLabel[key] ?? key,
                      )}
                      series={[
                        {
                          id: "cases",
                          label: "Cases",
                          values: activityKeys.map((key) =>
                            amount(activity[key]),
                          ),
                        },
                      ]}
                    />
                  </ChartCard>
                ) : null}
                {products.map((code) => {
                  const rows = data.branchComparison?.[code];
                  if (!rows) return null;
                  return (
                    <ChartCard
                      emptyMessage="No activity for the selected period."
                      key={code}
                      title={
                        code === "CC"
                          ? "Branch comparison · CC points"
                          : "Branch comparison · PF amount"
                      }
                      description={`${PRODUCT_LABEL[code]} achieved by Branch`}
                      state={valuesState(
                        "ready",
                        rows.map((row) =>
                          amount(
                            code === "CC"
                              ? row.achievedCCPoints
                              : row.achievedPFAed,
                          ),
                        ),
                      )}
                    >
                      <BarChart
                        labels={rows.map(
                          (row) => readable(row.name) || "Unavailable",
                        )}
                        kind={code === "CC" ? "points" : "currency"}
                        series={[
                          {
                            id: code,
                            label: code === "CC" ? "CC points" : "PF amount",
                            color: PRODUCT_COLOR[code],
                            values: rows.map((row) =>
                              amount(
                                code === "CC"
                                  ? row.achievedCCPoints
                                  : row.achievedPFAed,
                              ),
                            ),
                          },
                        ]}
                      />
                    </ChartCard>
                  );
                })}
              </div>
            ) : null}
            {data.teamPerformance || data.assets ? (
              <div className={styles.panels}>
                {data.teamPerformance ? (
                  <SectionCard compact title="Team performance">
                    <StatusSummary
                      items={[
                        {
                          label: "Created",
                          count: amount(data.teamPerformance.createdCaseCount),
                          tone: "neutral",
                        },
                        {
                          label: "Booked",
                          count: amount(data.teamPerformance.bookedCaseCount),
                          tone: "info",
                        },
                        {
                          label: "Completed",
                          count: amount(data.teamPerformance.completedCaseCount),
                          tone: "success",
                        },
                      ]}
                    />
                    <dl className={styles.facts}>
                      <div>
                        <dt>CC points</dt>
                        <dd>{count(data.teamPerformance.achievedCCPoints)}</dd>
                      </div>
                      <div>
                        <dt>PF amount</dt>
                        <dd>
                          <MonetaryAmount
                            compact={false}
                            value={data.teamPerformance.achievedPFAed}
                            align="start"
                          />
                        </dd>
                      </div>
                    </dl>
                  </SectionCard>
                ) : null}

                {data.assets ? (
                  <SectionCard
                    compact
                    title="Assets"
                    description="Authorized Branch inventory"
                  >
                    <StatusSummary
                      items={[
                        {
                          label: "Available",
                          count: amount(data.assets.availableCount),
                          tone: "success",
                        },
                        {
                          label: "Issued",
                          count: amount(data.assets.issuedCount),
                          tone: "info",
                        },
                        {
                          label: "Maintenance",
                          count: amount(data.assets.maintenanceCount),
                          tone: "warning",
                        },
                        {
                          label: "Damaged",
                          count: amount(data.assets.damagedCount),
                          tone: "danger",
                        },
                      ]}
                    />
                  </SectionCard>
                ) : null}
              </div>
            ) : null}
          </div>
          <div className={styles.secondary}>
            {data.ranking ? (
              <SectionCard
                compact
                title="Employee performance"
                description="Monthly and selected-period leaders"
              >
                <dl className={styles.performanceProducts}>
                  {products.map((code) => (
                    <div key={code} className={styles.performanceProduct}>
                      <dt>{PRODUCT_LABEL[code]}</dt>
                      <dd>
                        <span>
                          Employee of the month:{" "}
                          <strong>
                            {rankingWinner(
                              data.ranking?.[code]?.employeeOfMonth,
                            )}
                          </strong>
                        </span>
                        <span>
                          Top performer:{" "}
                          <strong>
                            {rankingWinner(
                              data.ranking?.[code]?.highestPerformer,
                            )}
                          </strong>
                        </span>
                      </dd>
                    </div>
                  ))}
                </dl>
              </SectionCard>
            ) : null}
            {charted && monthly.data && months.length ? (
              <SectionCard
                compact
                className={styles.monthly}
                title={
                  <button
                    type="button"
                    className={styles.monthlyToggle}
                    aria-expanded={monthlyOpen}
                    aria-controls="dashboard-monthly-values"
                    onClick={() => setMonthlyOpen((open) => !open)}
                  >
                    Monthly values{" "}
                    <DsIcon
                      name={monthlyOpen ? "collapse" : "expand"}
                      size={16}
                    />
                  </button>
                }
                actions={
                  selection.allowed ? (
                    <ExportButton
                      size="compact"
                      selectedCount={selection.selectedCount}
                      loading={selection.working}
                      disabled={!selection.selectedCount}
                      onClick={() => void selection.exportCsv()}
                    />
                  ) : undefined
                }
              >
                <div id="dashboard-monthly-values" hidden={!monthlyOpen}>
                  <DataTable
                    ariaLabel="Monthly activity values"
                    density="compact"
                    columns={monthColumns}
                    rows={months}
                    rowKey={(item) => item.start}
                    selectedKeys={
                      selection.allowed
                        ? months
                            .filter((item, index) =>
                              selection.checked(item, index),
                            )
                            .map((item) => item.start)
                        : undefined
                    }
                    onToggleRow={
                      selection.allowed
                        ? (key) => {
                            const index = months.findIndex(
                              (item) => item.start === key,
                            );
                            if (index >= 0)
                              selection.toggleRow(months[index], index);
                          }
                        : undefined
                    }
                    onToggleAll={
                      selection.allowed ? selection.toggleAll : undefined
                    }
                  />
                </div>
                {selection.error ? (
                  <p className={styles.support} role="alert">
                    The CSV export could not be completed. Try again.
                  </p>
                ) : null}
              </SectionCard>
            ) : null}

            <SectionCard compact title="Work shortcuts">
              <div className={styles.shortcuts}>
                <Button variant="secondary" size="compact" onClick={openTasks}>
                  <DsIcon name="tasks" size={16} />
                  Open Tasks
                  <strong className="ds-numeric">
                    {formatFullNumber(data.openTaskCount)}
                  </strong>
                </Button>
                <Button
                  variant="secondary"
                  size="compact"
                  onClick={openNotifications}
                >
                  <DsIcon name="notification" size={16} />
                  Unread Notifications
                  <strong className="ds-numeric">
                    {formatFullNumber(data.unreadNotificationCount)}
                  </strong>
                </Button>
              </div>
            </SectionCard>
          </div>
        </div>
      </>
    );
  }

  return (
    <PageContainer className={styles.container}>
      <div className={styles.page}>
        {header}
        {filters}
        {body}
      </div>
    </PageContainer>
  );
}
