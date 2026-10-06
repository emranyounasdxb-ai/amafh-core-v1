import { useState, type ReactNode } from "react";
import {
  Button,
  CompactDate,
  CompactDateTime,
  EmptyState,
  EmptyValue,
  ErrorState,
  ExportButton,
  FeedbackState,
  InlineNotice,
  KpiSummary,
  LoadingState,
  MonetaryAmount,
  OfflineState,
  PageContainer,
  PageHeader,
  PermissionDeniedState,
  SectionCard,
  StatusBadge,
  TruncatedText,
  formatCompactDateRange,
  formatFullNumber,
  formatFullPercent,
  type ExportOptionSpec,
  type KpiItem,
  type StatusTone,
} from "../../design-system";
import { download } from "../../app/api/download";
import type { DataRecord } from "../../app/api/models";
import { useResource } from "../../app/api/useResource";
import { readableLabel } from "../../app/presentation/labels";
import { useSession } from "../../app/session/useSession";
import { ServerTableSection } from "../../shared/table/ServerTableSection";
import { isOffline, type ServerColumn } from "../../shared/table/serverTable";
import { nextSort, type TableSort } from "../../shared/table/tableSortState";
import { useTableSelection } from "../../shared/table/useTableSelection";
import { assetStatusTone } from "../assets/live/assetCommands";
import { clockTime } from "../attendance/live/attendancePresentation";
import { caseStatusTone } from "../cases/live/caseListPresentation";
import { employeeStatusTone } from "../employees/live/employeePresentation";
import { personText, type PersonLabel } from "../finance/live/financeLabels";
import {
  PRODUCT_LABEL,
  type Product,
} from "../performance/live/performancePresentation";
import { ReportFilterBar, type PanelValues } from "./ReportFilterBar";
import {
  columnKind,
  columnLabel,
  columnRole,
  columnWidth,
  productRequired,
  summaryLabel,
  summaryRole,
  type ColumnRole,
  type ReportCatalogItem,
  type ReportPage,
  type ReportPeriod,
} from "./reportPresentation";
import { useReportSources, type ReportSources } from "./useReportSources";
import styles from "./ReportsPage.module.css";

type ReportRow = DataRecord & { id: string };
type Filters = {
  report: string;
  period: ReportPeriod;
  startDate: string;
  endDate: string;
  productCode: string;
  panel: PanelValues;
};
type ExportFormat = "csv" | "pdf";
type ExportFailure = { format: ExportFormat; message: string } | null;

const initialFilters = (report: string): Filters => ({
  report,
  period: "month",
  startDate: "",
  endDate: "",
  productCode: "",
  panel: {},
});

function Text({ value }: { value: string }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

function numeric(value: unknown): number | null {
  if (value == null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function NumberText({ value }: { value: unknown }) {
  const number = numeric(value);
  if (number == null) return <EmptyValue />;
  return <span className="ds-numeric">{formatFullNumber(number)}</span>;
}

function statusTone(report: string, key: string, value: string): StatusTone {
  if (key === "accessStatus")
    return value === "Active"
      ? "success"
      : value === "Disabled"
        ? "danger"
        : "neutral";
  if (report === "case-pipeline") return caseStatusTone(value);
  if (report === "assets") return assetStatusTone(value) as StatusTone;
  if (report === "attendance")
    return value === "Present"
      ? "success"
      : value === "Absent"
        ? "danger"
        : "neutral";
  if (report === "hr-employees" || report === "hr-assignments")
    return employeeStatusTone(value);
  return "neutral";
}

function employeeFallback(report: string, key: string) {
  if (key === "ownerEmployeeId" || key === "caseOwnerEmployeeId")
    return "Case owner";
  if (key === "currentEmployeeId") return "Assigned employee";
  if (report === "coordinator-workload") return "Coordinator";
  return "Team member";
}

function renderCell(
  report: string,
  key: string,
  role: ColumnRole,
  product: string,
  row: DataRecord,
  sources: ReportSources,
): ReactNode {
  const value = row[key];
  if (value == null || value === "") return <EmptyValue />;
  switch (role) {
    case "branch":
      return <Text value={sources.branchLabel(value)} />;
    case "department":
      return <Text value={sources.departmentLabel(value)} />;
    case "bank":
      return <Text value={sources.bankLabel(value)} />;
    case "employee":
      return (
        <Text
          value={personText(
            sources.people(String(value), employeeFallback(report, key)),
          )}
        />
      );
    case "employee-code":
      return <Text value={sources.people(String(value), "").code} />;
    case "money":
      return <MonetaryAmount compact={false} value={value} />;
    case "number":
      return <NumberText value={value} />;
    case "percent": {
      const number = numeric(value);
      return number == null ? (
        <EmptyValue />
      ) : (
        <span className="ds-numeric">{formatFullPercent(number)}</span>
      );
    }
    case "achieved":
      return product === "PF" ? (
        <MonetaryAmount compact={false} value={value} />
      ) : (
        <NumberText value={value} />
      );
    case "product":
      return <Text value={PRODUCT_LABEL[value as Product] ?? String(value)} />;
    case "boolean":
      return <Text value={value ? "Yes" : "No"} />;
    case "time":
      return <Text value={clockTime(String(value)) ?? ""} />;
    case "date":
      return <CompactDate value={value} />;
    case "datetime":
      return <CompactDateTime value={value} />;
    case "status":
      return (
        <StatusBadge tone={statusTone(report, key, String(value))}>
          {String(value)}
        </StatusBadge>
      );
    default:
      return <Text value={readableLabel(value, "")} />;
  }
}

function rowLabel(row: DataRecord, index: number) {
  for (const key of [
    "internalCaseId",
    "employeeName",
    "systemEmployeeCode",
    "assetCode",
    "customerId",
  ]) {
    const label = readableLabel(row[key], "");
    if (label) return label;
  }
  return `row ${index + 1}`;
}

function summaryItems(
  summary: DataRecord,
  rows: DataRecord[],
  people: (id: string, fallback?: string) => PersonLabel,
): KpiItem[] {
  return Object.entries(summary).map(([key, value]) => {
    const role = summaryRole(key);
    let shown: ReactNode;
    if (role === "money")
      shown = <MonetaryAmount compact={false} value={value} align="start" />;
    else if (role === "employee") {
      const id = typeof value === "string" ? value : "";
      const fromRows = readableLabel(
        rows.find((row) => row.employeeId === id)?.employeeName,
        "",
      );
      shown = id ? (
        fromRows || personText(people(id, "Team member"))
      ) : (
        <EmptyValue />
      );
    } else if (role === "text")
      shown = readableLabel(value, "") || <EmptyValue />;
    else {
      const number = numeric(value);
      shown = number == null ? "Unavailable" : formatFullNumber(number);
    }
    const label = summaryLabel(key);
    return {
      id: key,
      label: role === "money" ? label.replace(/ AED$/, "") : label,
      value: shown,
      accent: "none",
    };
  });
}

function useReportTable(report: string, path: string | null, query: string) {
  const [paging, setPaging] = useState({
    query: `${report}?${query}`,
    page: 1,
    size: 25,
  });
  const [sortState, setSortState] = useState<{
    report: string;
    sort: TableSort;
  }>({ report, sort: null });
  const sort = sortState.report === report ? sortState.sort : null;
  const pagingKey = `${report}?${query}`;
  if (paging.query !== pagingKey)
    setPaging({ query: pagingKey, page: 1, size: paging.size });
  const page = paging.query === pagingKey ? paging.page : 1;
  const size = paging.size;
  const params = new URLSearchParams(query);
  if (sort) {
    params.set("sort", sort.key);
    params.set("direction", sort.direction);
  }
  const sourcePath = path ? `${path}?${params}` : null;
  const resource = useResource<ReportPage>(
    sourcePath ? `${sourcePath}&page=${page}&pageSize=${size}` : null,
  );
  const current =
    !resource.error &&
    resource.data &&
    resource.dataPath?.split("?")[0] === path
      ? resource.data
      : null;
  const rows: ReportRow[] = (current?.items ?? []).map((item, index) => ({
    ...item,
    id: `${page}:${index}`,
  }));
  const total = current?.total ?? 0;
  const selection = useTableSelection<ReportRow>(
    `report:${report}`,
    sourcePath
      ? {
          path: sourcePath,
          page,
          size,
          total,
          busy: resource.loading || Boolean(resource.error),
          rowForSelection: (row) =>
            Object.fromEntries(
              Object.entries(row).filter(([key]) => key !== "id"),
            ),
        }
      : undefined,
  );
  return {
    report: current,
    table: {
      resource: {
        ...resource,
        data: current ? { ...current, items: rows } : null,
      },
      rows,
      total,
      page,
      size,
      pageCount: Math.max(1, Math.ceil(total / size)),
      sort,
      selection,
      setPage: (next: number) =>
        setPaging({ query: pagingKey, page: next, size }),
      setSize: (next: number) =>
        setPaging({ query: pagingKey, page: 1, size: next }),
      toggleSort: (key: string) => {
        setSortState({ report, sort: nextSort(sort, key) });
        setPaging({ query: pagingKey, page: 1, size });
      },
      sortable: () => true,
    },
  };
}

export function ReportsPage({
  only,
  back,
}: {
  only?: string[];
  back?: () => void;
}) {
  const { api } = useSession();
  const catalog = useResource<ReportCatalogItem[]>("/reports/catalog");
  const available =
    catalog.data?.filter((item) => !only || only.includes(item.report)) ?? [];
  const [selected, setSelected] = useState("");
  const definition =
    available.find((item) => item.report === selected) ?? available[0];
  const report = definition?.report ?? "";
  const [filterState, setFilterState] = useState<Filters>(initialFilters(""));
  const filters =
    filterState.report === report ? filterState : initialFilters(report);
  const update = (patch: Partial<Filters>) =>
    setFilterState({ ...filters, ...patch });
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [exportFailure, setExportFailure] = useState<ExportFailure>(null);

  const rangeMissing =
    filters.period === "custom" && (!filters.startDate || !filters.endDate);
  const productMissing = productRequired(report) && !filters.productCode;
  const ready = Boolean(definition) && !rangeMissing && !productMissing;
  const params = new URLSearchParams({ period: filters.period });
  if (filters.period === "custom") {
    if (filters.startDate) params.set("startDate", filters.startDate);
    if (filters.endDate) params.set("endDate", filters.endDate);
  }
  if (filters.productCode) params.set("productCode", filters.productCode);
  for (const [key, value] of Object.entries(filters.panel))
    if (value) params.set(key, value);
  const query = params.toString();
  const path = ready ? `/reports/${report}` : null;
  const { report: data, table } = useReportTable(report, path, query);
  const sources = useReportSources(
    definition,
    data?.items ?? [],
    data?.summary,
  );

  const runExport = async (format: ExportFormat) => {
    if (!path) return;
    setExporting(format);
    setExportFailure(null);
    try {
      await download(api, `${path}/exports/${format}?${query}`);
    } catch (cause) {
      setExportFailure({
        format,
        message:
          cause instanceof Error
            ? cause.message
            : "The export could not be prepared.",
      });
    } finally {
      setExporting(null);
    }
  };

  const header = (
    <PageHeader
      title="Reports"
      subtitle="Authorized report data and exports"
      onBack={back}
      backLabel="Back to Dashboard"
    />
  );

  if (!definition) {
    let body: ReactNode;
    if (catalog.denied) body = <PermissionDeniedState />;
    else if (catalog.error && !catalog.data)
      body = isOffline(catalog.error) ? (
        <OfflineState />
      ) : (
        <ErrorState description={catalog.error} retry={catalog.reload} />
      );
    else if (!catalog.data) body = <LoadingState title="Loading reports" />;
    else
      body = (
        <EmptyState
          title="No authorized reports"
          description="No reports are available for your role."
        />
      );
    return (
      <PageContainer>
        <div className={styles.page}>
          {header}
          {body}
        </div>
      </PageContainer>
    );
  }

  const product = filters.productCode;
  const keys = definition.columns.map((column) => column.key);
  const columns: ServerColumn<ReportRow>[] = definition.columns.map(
    (column) => {
      const role = columnRole(report, column.key, keys);
      return {
        key: column.key,
        label: columnLabel(report, column.key, column.heading, role, product),
        width: columnWidth(role),
        kind: columnKind(role, product),
        render: (row) =>
          renderCell(report, column.key, role, product, row, sources),
      };
    },
  );
  const exportBlocked =
    !ready || table.resource.loading || Boolean(table.resource.error) || !data;
  const exportOptions: ExportOptionSpec[] = [
    {
      id: "csv",
      format: "csv",
      scope: "filtered",
      label: "CSV",
      description: "Full report for the applied filters",
      disabled: exportBlocked,
    },
    {
      id: "pdf",
      format: "pdf",
      scope: "filtered",
      label: "PDF",
      description: "Full report for the applied filters",
      disabled: exportBlocked,
    },
    ...(table.selection.allowed
      ? [
          {
            id: "selected",
            format: "csv" as const,
            scope: "selected" as const,
            label: `Selected rows CSV (${table.selection.selectedCount})`,
            description: "Only the rows you selected",
            disabled: exportBlocked || !table.selection.selectedCount,
          },
        ]
      : []),
  ];
  const filtered =
    Object.values(filters.panel).some(Boolean) || Boolean(product);

  let body: ReactNode;
  if (rangeMissing) {
    body = (
      <FeedbackState
        kind="validation"
        title="Select a date range"
        description="Select a start date and an end date to generate this report."
      />
    );
  } else if (productMissing) {
    body = (
      <FeedbackState
        kind="validation"
        title="Select a product"
        description="Select a valid Product: Credit Card or Personal Finance."
      />
    );
  } else if (table.resource.error && !table.resource.denied) {
    const retry = (
      <Button
        variant="secondary"
        size="compact"
        onClick={table.resource.reload}
      >
        Retry
      </Button>
    );
    body =
      isOffline(table.resource.error) ||
      /failed to fetch|network/i.test(table.resource.error) ? (
        <FeedbackState
          kind="offline"
          title="Offline"
          description="The report could not be reached. Your selections are kept."
          action={retry}
        />
      ) : (
        <ErrorState
          title="Report unavailable"
          description={table.resource.error}
          retry={table.resource.reload}
        />
      );
  } else {
    body = (
      <>
        {data ? (
          <SectionCard
            compact
            title={definition.title}
            description={`Period ${formatCompactDateRange(data.startDate, data.endDate)}`}
          >
            <KpiSummary
              compact
              items={summaryItems(data.summary, data.items, sources.people)}
            />
          </SectionCard>
        ) : null}
        <ServerTableSection
          table={table}
          tableId={`report:${report}`}
          ariaLabel={definition.title}
          stackOnNarrow={false}
          columns={columns}
          filtered={filtered}
          loadingTitle={`Loading ${definition.title}`}
          emptyTitle="No report records"
          emptyDescription="No authorized records match this report period."
          noResultsDescription="No authorized records match the selected filters."
          rowLabel={(row) => rowLabel(row, table.rows.indexOf(row))}
        />
      </>
    );
  }

  return (
    <PageContainer>
      <div className={styles.page}>
        {header}
        <ReportFilterBar
          reports={available}
          definition={definition}
          onReport={(next) => {
            setSelected(next);
            setExportFailure(null);
          }}
          period={filters.period}
          startDate={filters.startDate}
          endDate={filters.endDate}
          rangeInvalid={
            rangeMissing && Boolean(filters.startDate || filters.endDate)
          }
          onPeriod={(period) => update({ period, startDate: "", endDate: "" })}
          onRange={(startDate, endDate) => update({ startDate, endDate })}
          product={product}
          productInvalid={productMissing}
          onProduct={(productCode) => update({ productCode })}
          applied={filters.panel}
          onApply={(panel) => update({ panel })}
          sources={sources}
          actions={
            <ExportButton
              size="compact"
              label="Export"
              loading={Boolean(exporting) || table.selection.working}
              disabled={exportBlocked}
              options={exportOptions}
              onSelect={(option) =>
                option.scope === "selected"
                  ? void table.selection.exportCsv()
                  : void runExport(option.format)
              }
            />
          }
        />
        {exportFailure ? (
          <InlineNotice tone="error" title="Export failed">
            <span className={styles.noticeBody}>
              {exportFailure.message}
              <Button
                size="compact"
                variant="secondary"
                onClick={() => void runExport(exportFailure.format)}
              >
                Retry {exportFailure.format.toUpperCase()}
              </Button>
            </span>
          </InlineNotice>
        ) : null}
        {body}
      </div>
    </PageContainer>
  );
}
