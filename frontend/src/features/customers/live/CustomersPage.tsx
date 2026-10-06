import { useCallback, useEffect, useState, useTransition } from "react";
import {
  Button,
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
  PageContainer,
  PageHeader,
  Pagination,
  PermissionDeniedState,
  RecordCount,
  SearchFilterToolbar,
  SectionCard,
  CompactDateTime,
  TruncatedText,
  type AppliedFilter,
  type DataTableColumn,
} from "../../../design-system";
import { canOpenPage } from "../../../access";
import type { Page } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import {
  readListState,
  saveListState,
} from "../../../app/navigation/listState";
import { useSession } from "../../../app/session/useSession";
import { useConnectedColumnLayout } from "../../../shared/table/useConnectedColumnLayout";
import { useTableSelection } from "../../../shared/table/useTableSelection";
import { nextSort, type TableSort } from "../../../shared/table/tableSortState";
import {
  CUSTOMER_COLUMNS,
  CUSTOMER_COLUMN_SORT,
  CUSTOMER_TYPES,
  activeCustomerFilterCount,
  customerListQuery,
  emptyCustomerFilters,
  identityNumber,
  nationalityLabel,
  type CustomerListFilters,
  type CustomerListRecord,
} from "./customerListPresentation";
import styles from "./CustomersPage.module.css";
import { ResponsiveFilterPanel } from "../../../shared/filters/ResponsiveFilterPanel";

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

type CustomersListState = {
  filters: CustomerListFilters;
  search: string;
  page: number;
  pageSize: number;
  sort: TableSort;
};

export function CustomersPage({ open }: { open: (id: string) => void }) {
  const { session } = useSession();
  const [initial] = useState(() =>
    readListState<CustomersListState>(session?.employeeId, "customers"),
  );
  const [filters, setFilters] = useState<CustomerListFilters>(
    () => initial?.filters ?? emptyCustomerFilters(),
  );
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [search, setSearch] = useState(initial?.search ?? "");
  const [page, setPage] = useState(initial?.page ?? 1);
  const [pageSize, setPageSize] = useState(initial?.pageSize ?? 25);
  const [sort, setSort] = useState<TableSort>(
    initial ? initial.sort : { key: "createdAt", direction: "desc" },
  );
  const [, startTransition] = useTransition();
  const employeeId = session?.employeeId;
  useEffect(() => {
    saveListState<CustomersListState>(employeeId, "customers", {
      filters,
      search,
      page,
      pageSize,
      sort,
    });
  }, [employeeId, filters, page, pageSize, search, sort]);
  const layout = useConnectedColumnLayout("customers-list", [
    ...CUSTOMER_COLUMNS,
  ]);

  const query = customerListQuery(
    filters,
    page,
    pageSize,
    sort?.key ?? null,
    sort?.direction ?? null,
    search,
  );
  const selectionQuery = new URLSearchParams(query);
  selectionQuery.delete("page");
  selectionQuery.delete("pageSize");
  const resource = useResource<Page<CustomerListRecord>>(`/customers?${query}`);
  const rows = resource.data?.items ?? [];
  const visibleRows = rows;
  const selection = useTableSelection<CustomerListRecord>("customers-list", {
    path: `/customers?${selectionQuery}`,
    page,
    size: pageSize,
    total: resource.data?.total || 0,
    busy: resource.loading || Boolean(resource.error),
  });

  const updateFilters = (patch: Partial<CustomerListFilters>) => {
    startTransition(() => {
      setFilters((current) => ({ ...current, ...patch }));
      setPage(1);
    });
  };
  const resetFilters = () => {
    startTransition(() => {
      setFilters(emptyCustomerFilters());
      setPage(1);
    });
  };

  const filterCount = activeCustomerFilterCount(filters);
  const total = resource.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const canOpenDetail = Boolean(session && canOpenPage(session, "customers"));

  const columns: DataTableColumn<CustomerListRecord>[] = layout.columns.map(
    (column) => ({
      key: column.key,
      header: column.label,
      width: `${column.width}px`,
      sortable: Boolean(CUSTOMER_COLUMN_SORT[column.key]),
      kind: column.key === "createdAt" ? "datetime" : undefined,
      render: (row) => {
        switch (column.key) {
          case "customerId":
            return <TruncatedText value={row.customerId} />;
          case "name":
            return <TruncatedText value={row.name || "Unavailable"} />;
          case "type":
            return <TruncatedText value={row.type} />;
          case "nationality":
            return row.type === "Individual" ? (
              nationalityLabel(row.nationality) ? (
                <TruncatedText value={nationalityLabel(row.nationality)} />
              ) : (
                <EmptyValue />
              )
            ) : (
              <EmptyValue />
            );
          case "contactPerson":
            return row.contactPerson ? (
              <TruncatedText value={row.contactPerson} />
            ) : (
              <EmptyValue />
            );
          case "mobile":
            return row.mobile ? (
              <TruncatedText value={row.mobile} />
            ) : (
              <EmptyValue />
            );
          case "email":
            return row.email ? (
              <TruncatedText value={row.email} />
            ) : (
              <EmptyValue />
            );
          case "passportNumber":
            return row.passportNumber ? (
              <TruncatedText value={row.passportNumber} />
            ) : (
              <EmptyValue />
            );
          case "eidOrTl": {
            const value = identityNumber(row);
            return value ? <TruncatedText value={value} /> : <EmptyValue />;
          }
          case "createdAt":
            return row.createdAt ? (
              <CompactDateTime value={row.createdAt} />
            ) : (
              <EmptyValue />
            );
          default:
            return <EmptyValue />;
        }
      },
    }),
  );

  const selectedKeys = visibleRows
    .filter((row, index) => selection.checked(row, index))
    .map((row) => row.customerId);
  const toggleRow = useCallback(
    (key: string) => {
      const index = visibleRows.findIndex((row) => row.customerId === key);
      if (index >= 0) selection.toggleRow(visibleRows[index], index);
    },
    [selection, visibleRows],
  );

  if (!session) return null;

  return (
    <PageContainer>
      <div className={styles.page}>
        <PageHeader
          title="Customers"
          subtitle="Authorized records created or reused through Case applications"
        />
        <SearchFilterToolbar
          className={styles.toolbar}
          searchId="customer-search"
          searchLabel="Search"
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value.slice(0, 128));
            setPage(1);
          }}
          searchPlaceholder="Search by ID, name, nationality, contact or email"
          applied={
            filters.type
              ? [
                  {
                    id: "type",
                    label: "Customer type",
                    field: "Customer type",
                    value: filters.type,
                    onRemove: () => updateFilters({ type: "" }),
                  } satisfies AppliedFilter,
                ]
              : []
          }
          onClearFilters={filterCount > 0 ? resetFilters : undefined}
          disabled={resource.loading && !resource.data}
          loading={resource.loading && !resource.data}
          actions={
            <div className={styles.toolbarActions}>
              <FilterButton
                size="compact"
                count={filterCount}
                aria-expanded={filtersOpen}
                aria-controls="customer-filter-card"
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
            </div>
          }
        />

        {filtersOpen ? (
          <ResponsiveFilterPanel
            id="customer-filter-card"
            label="Customer filters"
            className={styles.filterCard}
            onClose={() => setFiltersOpen(false)}
          >
            <div className={styles.filterGrid}>
              <FormField label="Customer type" htmlFor="customer-type">
                <DropdownSelect
                  id="customer-type"
                  compact
                  clearable
                  value={filters.type}
                  onChange={(value) =>
                    updateFilters({
                      type: Array.isArray(value) ? (value[0] ?? "") : value,
                    })
                  }
                  options={CUSTOMER_TYPES.map((item) => ({
                    value: item,
                    label: item,
                  }))}
                  placeholder="All types"
                />
              </FormField>
            </div>
          </ResponsiveFilterPanel>
        ) : null}

        {selection.error ? (
          <InlineNotice tone="error" title="Export failed">
            {selection.error}
          </InlineNotice>
        ) : null}
        {selection.allowed && selection.selectedCount > 0 ? (
          <div className={styles.selection} role="status">
            <span>{`${selection.selectedCount} selected`}</span>
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
          <LoadingState title="Loading Customers" />
        ) : (
          <SectionCard compact className={styles.table}>
            <RecordCount count={total} />
            {total === 0 ? (
              <EmptyState
                title="No matching authorized records"
                description="There are no Customer records in this authorized view."
              />
            ) : visibleRows.length === 0 ? (
              <NoResultsState
                title="No matching records"
                description="Nothing on this page matches the search."
              />
            ) : (
              <>
                <DataTable
                  ariaLabel="Authorized customers"
                  density="compact"
                  columns={columns}
                  rows={visibleRows}
                  rowKey={(row) => row.customerId}
                  sort={
                    sort
                      ? {
                          key:
                            Object.entries(CUSTOMER_COLUMN_SORT).find(
                              ([, value]) => value === sort.key,
                            )?.[0] ?? sort.key,
                          direction: sort.direction,
                        }
                      : { key: "createdAt", direction: "desc" }
                  }
                  onSort={(key) => {
                    const mapped = CUSTOMER_COLUMN_SORT[key] ?? key;
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
                  rowActivateLabel={(row) =>
                    `Open ${row.name || row.customerId}`
                  }
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
    </PageContainer>
  );
}
