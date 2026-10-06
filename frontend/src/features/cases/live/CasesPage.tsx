import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useTransition,
} from "react";
import {
  Button,
  DataTable,
  DateRangePicker,
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
  PageContainer,
  PageHeader,
  Pagination,
  PermissionDeniedState,
  PersonSelect,
  RecordCount,
  SearchFilterToolbar,
  SectionCard,
  StatusBadge,
  CompactDateTime,
  MonetaryAmount,
  TruncatedText,
  type AppliedFilter,
  type DataTableColumn,
  type DateRangeValue,
  type PersonOption,
  type SelectOption,
} from "../../../design-system";
import {
  canApproveCases,
  canCreateCase,
  canOpenPage,
  hasPermission,
} from "../../../access";
import { choices } from "../../../app/api/choices";
import type { ApiClient } from "../../../app/api/http";
import type {
  CaseRecord,
  EmployeeSummary,
  NamedRecord,
  Page,
} from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import { useConnectedColumnLayout } from "../../../shared/table/useConnectedColumnLayout";
import { useTableSelection } from "../../../shared/table/useTableSelection";
import { nextSort, type TableSort } from "../../../shared/table/tableSortState";
import { initialCaseColumns } from "../model/initialCaseColumns";
import { CaseApprovalDialog } from "./CaseApprovalDialog";
import { CaseCreateForm } from "./CaseCreateForm";
import {
  CASE_COLUMN_SORT,
  CASE_STATUSES,
  CASE_VIEWS,
  activeCaseFilterCount,
  caseListQuery,
  caseStatusTone,
  emptyCaseFilters,
  initialApprovalColumns,
  viewLabel,
  type CaseListFilters,
} from "./caseListPresentation";
import {
  readListState,
  saveListState,
} from "../../../app/navigation/listState";
import { useCaseLabels } from "./useCaseLabels";
import { ResponsiveFilterPanel } from "../../../shared/filters/ResponsiveFilterPanel";
import styles from "./CasesPage.module.css";

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

function loadNamed(api: ApiClient, path: string, signal: AbortSignal) {
  return choices<NamedRecord>(api, path, signal);
}

function loadEmployees(api: ApiClient, path: string, signal: AbortSignal) {
  return choices<EmployeeSummary>(api, path, signal);
}

function optionLabel(row: NamedRecord, key: keyof NamedRecord) {
  const text = String(row[key] ?? "").trim();
  return text || "Unavailable";
}

type CasesListState = {
  filters: CaseListFilters;
  search: string;
  page: number;
  pageSize: number;
  sort: TableSort;
  queue: boolean;
};

export function CasesPage({
  open,
  mode = "managed",
}: {
  open: (id: string) => void;
  mode?: "managed" | "own";
}) {
  const { session } = useSession();
  const own = mode === "own";
  const listId = own ? "my-cases" : "cases";
  const [initial] = useState(() =>
    readListState<CasesListState>(session?.employeeId, listId),
  );
  const [filters, setFilters] = useState<CaseListFilters>(
    () => initial?.filters ?? emptyCaseFilters(),
  );
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [search, setSearch] = useState(initial?.search ?? "");
  const [page, setPage] = useState(initial?.page ?? 1);
  const [pageSize, setPageSize] = useState(initial?.pageSize ?? 25);
  const [sort, setSort] = useState<TableSort>(initial?.sort ?? null);
  const [queue, setQueue] = useState(!own && (initial?.queue ?? false));
  const [modal, setModal] = useState<"create" | null>(null);
  const [approveItem, setApproveItem] = useState<CaseRecord | null>(null);
  const [approvalSuccess, setApprovalSuccess] = useState("");
  const [createdSuccess, setCreatedSuccess] = useState("");
  const [, startTransition] = useTransition();
  const ownerId = session?.employeeId;
  useEffect(() => {
    saveListState<CasesListState>(ownerId, listId, {
      filters,
      search,
      page,
      pageSize,
      sort,
      queue,
    });
  }, [filters, listId, ownerId, page, pageSize, queue, search, sort]);
  const layoutColumns = useMemo(
    () => (queue ? [...initialApprovalColumns] : initialCaseColumns),
    [queue],
  );
  const layout = useConnectedColumnLayout(
    queue ? "cases-approval" : own ? "my-cases-list" : "cases-list",
    layoutColumns,
  );

  const query = caseListQuery(
    filters,
    page,
    pageSize,
    sort?.key ?? null,
    sort?.direction ?? null,
    queue,
    search,
  );
  const selectionQuery = new URLSearchParams(query);
  selectionQuery.delete("page");
  selectionQuery.delete("pageSize");
  const listPath = `${queue ? "/cases/approval-queue" : own ? "/my-cases" : "/cases"}?${query}`;
  const resource = useResource<Page<CaseRecord>>(listPath);
  const rows = resource.data?.items ?? [];
  const label = useCaseLabels(rows);
  const visibleRows = rows;

  const catalogChoices =
    !own ||
    Boolean(
      session &&
      (canCreateCase(session) ||
        hasPermission(session, "case.read") ||
        hasPermission(session, "pipeline.write")),
    );
  const ownerChoices = !own || session?.designation === "Team Leader";
  const banks = useResource<NamedRecord[]>(
    catalogChoices ? "/catalog/banks" : null,
    0,
    loadNamed,
    "choices",
  );
  const products = useResource<NamedRecord[]>(
    catalogChoices ? "/catalog/product-types" : null,
    0,
    loadNamed,
    "choices",
  );
  const owners = useResource<EmployeeSummary[]>(
    ownerChoices ? "/employees" : null,
    0,
    loadEmployees,
    "choices",
  );

  const selection = useTableSelection<CaseRecord>(
    queue ? "cases-approval" : own ? "my-cases-list" : "cases-list",
    own
      ? undefined
      : {
          path: `${queue ? "/cases/approval-queue" : "/cases"}?${selectionQuery}`,
          page,
          size: pageSize,
          total: resource.data?.total || 0,
          busy: resource.loading || Boolean(resource.error),
        },
  );

  const namedOptions = (
    rows: NamedRecord[] | null,
    loading: boolean,
  ): SelectOption[] =>
    (rows ?? []).map((row) => ({
      value: row.id,
      label: optionLabel(row, "name"),
      disabled: loading,
    }));
  const bankOptions = namedOptions(banks.data, banks.loading);
  const productOptions = namedOptions(products.data, products.loading);
  const ownerPeople: PersonOption[] = (owners.data ?? [])
    .filter(
      (person) =>
        !own ||
        person.id === session?.employeeId ||
        person.designation === "Sales Executive",
    )
    .map((person) => ({
      value: person.id,
      name: person.fullName,
      subtitle: person.employeeCode,
    }));

  const updateFilters = (patch: Partial<CaseListFilters>) => {
    startTransition(() => {
      setFilters((current) => ({ ...current, ...patch }));
      setPage(1);
    });
  };

  const resetFilters = () => {
    startTransition(() => {
      setFilters(emptyCaseFilters());
      setPage(1);
    });
  };

  const createdRange: DateRangeValue = {
    start: filters.createdFrom,
    end: filters.createdTo,
  };
  const filterCount = queue ? 0 : activeCaseFilterCount(filters);

  const columns: DataTableColumn<CaseRecord>[] = layout.columns.map(
    (column) => ({
      key: column.key,
      header: column.label,
      width: `${column.width}px`,
      sortable: Boolean(CASE_COLUMN_SORT[column.key]),
      align: column.key === "variant" ? "start" : undefined,
      kind:
        column.key === "variant"
          ? "mixed"
          : column.key === "date"
            ? "datetime"
            : undefined,
      render: (row) => {
        switch (column.key) {
          case "id":
            return <TruncatedText value={row.internalCaseId} />;
          case "customer":
            return <TruncatedText value={label(row.customerId)} />;
          case "product":
            return <TruncatedText value={label(row.productTypeId)} />;
          case "bank":
            return <TruncatedText value={label(row.bankId)} />;
          case "variant":
            return row.requestedPfAmount ? (
              <MonetaryAmount
                value={row.requestedPfAmount}
                compact={false}
                align="start"
              />
            ) : (
              <TruncatedText
                value={label(row.productVariantId) || "Not recorded"}
              />
            );
          case "createdBy":
            return <TruncatedText value={label(row.createdByEmployeeId)} />;
          case "owner":
            return <TruncatedText value={label(row.ownerEmployeeId)} />;
          case "branch":
            return <TruncatedText value={label(row.branchId)} />;
          case "department":
            return <TruncatedText value={label(row.departmentId)} />;
          case "assignment":
            return (
              <TruncatedText
                value={
                  row.coordinatorEmployeeId
                    ? label(row.coordinatorEmployeeId)
                    : "Not assigned"
                }
              />
            );
          case "status":
            return (
              <StatusBadge
                tone={caseStatusTone(
                  row.status,
                  Boolean(row.administrativelyVoidedAt),
                )}
              >
                {row.administrativelyVoidedAt ? "Archived" : row.status}
              </StatusBadge>
            );
          case "bankRef":
            return (
              <TruncatedText value={row.bankCaseNumber || "Not assigned"} />
            );
          case "stage":
            return <TruncatedText value={row.currentStage || "Not recorded"} />;
          case "date":
            return row.createdAt ? (
              <CompactDateTime value={row.createdAt} />
            ) : (
              "Not recorded"
            );
          case "actions": {
            const canApproveRow =
              Boolean(session && canApproveCases(session)) &&
              row.status === "Pending for Approval" &&
              !row.administrativelyVoidedAt;
            return canApproveRow ? (
              <Button
                size="compact"
                variant="secondary"
                onClick={() => {
                  setApproveItem(row);
                  setApprovalSuccess("");
                }}
              >
                Approve
              </Button>
            ) : (
              <EmptyValue />
            );
          }
          default:
            return null;
        }
      },
    }),
  );

  const selectedKeys = visibleRows
    .filter((row, index) => selection.checked(row, index))
    .map((row) => row.internalCaseId);
  const toggleRow = useCallback(
    (key: string) => {
      const index = visibleRows.findIndex((row) => row.internalCaseId === key);
      if (index >= 0) selection.toggleRow(visibleRows[index], index);
    },
    [selection, visibleRows],
  );

  if (!session) return null;
  const canOpenDetail = canOpenPage(session, "case-detail");
  const total = resource.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const choiceError = banks.error || products.error || owners.error;
  const applied: AppliedFilter[] = [];
  if (!queue) {
    if (filters.status) {
      applied.push({
        id: "status",
        label: "Case status",
        field: "Case status",
        value: filters.status,
        onRemove: () => updateFilters({ status: "" }),
      });
    }
    if (filters.view && filters.view !== "active") {
      applied.push({
        id: "view",
        label: "Visibility",
        field: "Visibility",
        value: viewLabel(filters.view),
        onRemove: () => updateFilters({ view: "active" }),
      });
    }
    if (filters.bankId) {
      applied.push({
        id: "bank",
        label: "Bank",
        field: "Bank",
        value:
          bankOptions.find((option) => option.value === filters.bankId)
            ?.label || "Selected bank",
        onRemove: () => updateFilters({ bankId: "" }),
      });
    }
    if (filters.productTypeId) {
      applied.push({
        id: "product",
        label: "Product",
        field: "Product",
        value:
          productOptions.find(
            (option) => option.value === filters.productTypeId,
          )?.label || "Selected product",
        onRemove: () => updateFilters({ productTypeId: "" }),
      });
    }
    if (filters.ownerEmployeeId) {
      applied.push({
        id: "owner",
        label: "Case Owner",
        field: "Case Owner",
        value:
          ownerPeople.find((person) => person.value === filters.ownerEmployeeId)
            ?.name || "Assigned employee",
        onRemove: () => updateFilters({ ownerEmployeeId: "" }),
      });
    }
    if (filters.createdFrom || filters.createdTo) {
      applied.push({
        id: "created",
        label: "Created date",
        field: "Created date",
        value: [filters.createdFrom, filters.createdTo]
          .filter(Boolean)
          .join(" – "),
        onRemove: () => updateFilters({ createdFrom: "", createdTo: "" }),
      });
    }
  }

  const filterFields = (
    <div className={styles.filterGrid}>
      <FormField label="Case status" htmlFor="case-status">
        <DropdownSelect
          id="case-status"
          compact
          clearable
          value={filters.status}
          onChange={(value) =>
            updateFilters({
              status: Array.isArray(value) ? (value[0] ?? "") : value,
            })
          }
          options={CASE_STATUSES.map((item) => ({
            value: item,
            label: item,
          }))}
          placeholder="All statuses"
        />
      </FormField>
      <FormField label="Visibility" htmlFor="case-view">
        <DropdownSelect
          id="case-view"
          compact
          clearable={filters.view !== "active"}
          value={filters.view}
          onChange={(value) =>
            updateFilters({
              view: (Array.isArray(value) ? value[0] : value) || "active",
            })
          }
          options={CASE_VIEWS.map((item) => ({
            value: item.value,
            label: item.label,
          }))}
        />
      </FormField>
      {catalogChoices ? (
        <>
          <FormField
            label="Bank"
            htmlFor="case-bank"
            error={banks.error || undefined}
          >
            <DropdownSelect
              id="case-bank"
              compact
              clearable
              loading={banks.loading}
              value={filters.bankId}
              onChange={(value) =>
                updateFilters({
                  bankId: Array.isArray(value) ? (value[0] ?? "") : value,
                })
              }
              options={bankOptions}
              placeholder="All banks"
            />
          </FormField>
          <FormField
            label="Product type"
            htmlFor="case-product"
            error={products.error || undefined}
          >
            <DropdownSelect
              id="case-product"
              compact
              clearable
              loading={products.loading}
              value={filters.productTypeId}
              onChange={(value) =>
                updateFilters({
                  productTypeId: Array.isArray(value)
                    ? (value[0] ?? "")
                    : value,
                })
              }
              options={productOptions}
              placeholder="All products"
            />
          </FormField>
        </>
      ) : null}
      {ownerChoices ? (
        <FormField label="Case Owner" htmlFor="case-owner">
          <PersonSelect
            id="case-owner"
            label="Case Owner"
            compact
            loading={owners.loading}
            people={ownerPeople}
            value={filters.ownerEmployeeId}
            onChange={(value) => updateFilters({ ownerEmployeeId: value })}
          />
        </FormField>
      ) : null}
      <FormField
        label="Created date"
        htmlFor="case-created"
        className={styles.createdField}
      >
        <DateRangePicker
          id="case-created"
          compact
          months={1}
          presets={[]}
          compactRangeLabel
          placement="bottom-end"
          className={styles.datePopover}
          value={createdRange}
          onChange={(range) =>
            updateFilters({
              createdFrom: range.start,
              createdTo: range.end,
            })
          }
        />
      </FormField>
    </div>
  );

  return (
    <PageContainer>
      <div className={styles.page}>
        <PageHeader
          title={queue ? "Case Approvals" : own ? "Own Cases" : "Cases"}
          subtitle={
            queue
              ? "Review pending Cases and assign a same-scope Coordinator"
              : own
                ? session.designation === "Team Leader"
                  ? "Cases you own and Cases owned by Sales Executives in your Team"
                  : "Cases you own"
                : "Manage applications, approvals and bank processing"
          }
        />

        <SearchFilterToolbar
          className={styles.toolbar}
          searchId="case-search"
          searchLabel="Search"
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value.slice(0, 128));
            setPage(1);
          }}
          searchPlaceholder={
            queue
              ? "Search by ID, customer, owner, Coordinator or bank"
              : "Search by ID, customer, owner or bank"
          }
          applied={applied}
          onClearFilters={applied.length ? resetFilters : undefined}
          disabled={resource.loading && !resource.data}
          loading={resource.loading && !resource.data}
          actions={
            <div className={styles.toolbarActions}>
              {canCreateCase(session) ? (
                <Button
                  size="compact"
                  onClick={() => {
                    setCreatedSuccess("");
                    setModal("create");
                  }}
                >
                  {own ? "Create Case" : "Add Case"}
                </Button>
              ) : null}
              {!own && canApproveCases(session) ? (
                <Button
                  variant="secondary"
                  size="compact"
                  onClick={() => {
                    setQueue((current) => !current);
                    setFiltersOpen(false);
                    setApproveItem(null);
                    setPage(1);
                  }}
                >
                  {queue ? "All Cases" : "Approvals"}
                </Button>
              ) : null}
              {!queue ? (
                <FilterButton
                  size="compact"
                  count={filterCount}
                  aria-expanded={filtersOpen}
                  aria-controls="case-filter-card"
                  onClick={() => setFiltersOpen((current) => !current)}
                />
              ) : null}
              {selection.allowed ? (
                <ExportButton
                  size="compact"
                  selectedCount={selection.selectedCount}
                  loading={selection.working}
                  disabled={!selection.selectedCount}
                  onClick={() => void selection.exportCsv()}
                />
              ) : null}
            </div>
          }
        />

        {filtersOpen && !queue ? (
          <ResponsiveFilterPanel
            id="case-filter-card"
            label="Case filters"
            onClose={() => setFiltersOpen(false)}
          >
            {filterFields}
          </ResponsiveFilterPanel>
        ) : null}

        {approvalSuccess ? (
          <InlineNotice tone="success" title="Approved">
            {approvalSuccess}
          </InlineNotice>
        ) : null}
        {createdSuccess ? (
          <InlineNotice tone="success" title="Case created">
            {createdSuccess}
          </InlineNotice>
        ) : null}
        {choiceError ? (
          <InlineNotice tone="warning" title="Filter choices unavailable">
            {choiceError}
          </InlineNotice>
        ) : null}
        {selection.error ? (
          <InlineNotice tone="error" title="Export failed">
            {selection.error}
          </InlineNotice>
        ) : null}

        {selection.allowed && selection.selectedCount > 0 ? (
          <div className={styles.selection} role="status">
            <span className={styles.selectionCount}>
              {selection.selectedCount} selected
            </span>
            <Button
              variant="secondary"
              size="compact"
              loading={selection.working}
              onClick={() => void selection.exportCsv()}
            >
              Export selected
            </Button>
          </div>
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
          <LoadingState title="Loading Cases" />
        ) : (
          <SectionCard compact className={styles.table}>
            <RecordCount count={total} />
            {total === 0 ? (
              <EmptyState
                title={
                  queue
                    ? "No Cases awaiting approval"
                    : own
                      ? "No Own Cases"
                      : "No matching authorized Cases"
                }
                description={
                  queue
                    ? "There are no pending Cases in this authorized approval queue."
                    : own
                      ? activeCaseFilterCount(filters) || search.trim()
                        ? "No Own Cases match your search or filters."
                        : session.designation === "Team Leader"
                          ? "Cases you own and Cases owned by Sales Executives in your team appear here."
                          : "Cases you own appear here."
                      : "There are no Cases in this authorized view."
                }
              />
            ) : visibleRows.length === 0 ? (
              <NoResultsState
                title="No matching Cases"
                description="Nothing on this page matches the search."
              />
            ) : (
              <>
                <DataTable
                  ariaLabel={
                    queue
                      ? "Approval queue"
                      : own
                        ? "Own Cases"
                        : "Authorized cases"
                  }
                  density="compact"
                  columns={columns}
                  rows={visibleRows}
                  rowKey={(row) => row.internalCaseId}
                  sort={
                    sort
                      ? {
                          key:
                            Object.entries(CASE_COLUMN_SORT).find(
                              ([, value]) => value === sort.key,
                            )?.[0] ?? sort.key,
                          direction: sort.direction,
                        }
                      : { key: "date", direction: "desc" }
                  }
                  onSort={(key) => {
                    const mapped = CASE_COLUMN_SORT[key] ?? key;
                    setSort(nextSort(sort, mapped));
                    setPage(1);
                  }}
                  selectedKeys={selection.allowed ? selectedKeys : undefined}
                  onToggleRow={selection.allowed ? toggleRow : undefined}
                  onToggleAll={
                    selection.allowed ? selection.toggleAll : undefined
                  }
                  loading={resource.updating}
                  onRowActivate={
                    canOpenDetail ? (row) => open(row.id) : undefined
                  }
                  rowActivateLabel={(row) => `Open Case ${row.internalCaseId}`}
                  onColumnResize={layout.resize}
                  onColumnReorder={layout.move}
                />
                <Pagination
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
          </SectionCard>
        )}
      </div>

      {modal === "create" ? (
        <CaseCreateForm
          personal={own}
          close={() => setModal(null)}
          saved={(item) => {
            setModal(null);
            if (!own) {
              open(item.id);
              return;
            }
            startTransition(() => {
              setFilters(emptyCaseFilters());
              setSearch("");
              setSort(null);
              setPage(1);
            });
            setCreatedSuccess(
              `${item.internalCaseId} is created and pending approval.`,
            );
            resource.reload();
          }}
        />
      ) : null}
      {approveItem ? (
        <CaseApprovalDialog
          item={approveItem}
          people={owners.data ?? []}
          label={label}
          onClose={() => setApproveItem(null)}
          onSaved={() => {
            setApproveItem(null);
            setApprovalSuccess(
              `${approveItem.internalCaseId} is approved and assigned.`,
            );
            resource.reload();
          }}
        />
      ) : null}
    </PageContainer>
  );
}
