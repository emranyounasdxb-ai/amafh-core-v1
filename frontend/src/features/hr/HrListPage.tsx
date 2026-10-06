import {
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  DataTable,
  DropdownSelect,
  EmptyState,
  EmptyValue,
  ErrorState,
  FilterButton,
  FormField,
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
  TruncatedText,
  type AppliedFilter,
  type DataTableColumn,
  type DataTableColumnKind,
  type MenuItem,
} from "../../design-system";
import { readListState, saveListState } from "../../app/navigation/listState";
import { useSession } from "../../app/session/useSession";
import { useConnectedColumnLayout } from "../../shared/table/useConnectedColumnLayout";
import {
  nextSort,
  sortCompleteRows,
  type TableSort,
} from "../../shared/table/tableSortState";
import styles from "./HrListPage.module.css";
import { ResponsiveFilterPanel } from "../../shared/filters/ResponsiveFilterPanel";

export type HrListColumn<Row> = {
  key: string;
  label: string;
  width: number;
  fixed?: boolean;
  sortable?: boolean;
  kind?: DataTableColumnKind;
  render: (row: Row) => ReactNode;
};

export type HrListFilter<Row> = {
  id: string;
  label: string;
  placeholder: string;
  options: string[];
  matches: (row: Row, value: string) => boolean;
};

export type HrListResource = {
  loading: boolean;
  updating: boolean;
  error: string;
  denied: boolean;
  reload: () => void;
};

type HrListState = {
  values: Record<string, string>;
  search: string;
  page: number;
  pageSize: number;
  sort: TableSort;
};

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

export function HrText({ value }: { value: string | null | undefined }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

export function HrListPage<Row extends object>({
  tableId,
  title,
  subtitle,
  searchPlaceholder,
  rows,
  resource,
  hasData,
  columns,
  filters,
  searchText,
  rowKey,
  rowLabel,
  onOpen,
  rowActions,
  actions,
  notices,
  emptyTitle,
  emptyDescription,
  initialSort,
}: {
  tableId: string;
  title: string;
  subtitle: string;
  searchPlaceholder: string;
  rows: Row[];
  resource: HrListResource;
  hasData: boolean;
  columns: HrListColumn<Row>[];
  filters: HrListFilter<Row>[];
  searchText: (row: Row) => (string | null | undefined)[];
  rowKey: (row: Row) => string;
  rowLabel: (row: Row) => string;
  onOpen?: (row: Row) => void;
  rowActions?: (row: Row) => MenuItem[];
  actions?: ReactNode;
  notices?: ReactNode;
  emptyTitle: string;
  emptyDescription: string;
  initialSort: TableSort;
}) {
  const { session } = useSession();
  const employeeId = session?.employeeId;
  const [initial] = useState(() =>
    readListState<HrListState>(employeeId, tableId),
  );
  const [values, setValues] = useState<Record<string, string>>(
    initial?.values ?? {},
  );
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [search, setSearch] = useState(initial?.search ?? "");
  const query = useDeferredValue(search.trim().toLowerCase());
  const [page, setPage] = useState(initial?.page ?? 1);
  const [pageSize, setPageSize] = useState(initial?.pageSize ?? 25);
  const [sort, setSort] = useState<TableSort>(
    initial ? initial.sort : initialSort,
  );
  useEffect(() => {
    saveListState<HrListState>(employeeId, tableId, {
      values,
      search,
      page,
      pageSize,
      sort,
    });
  }, [employeeId, page, pageSize, search, sort, tableId, values]);
  const layout = useConnectedColumnLayout<Row>(tableId, [
    ...columns,
    ...(rowActions
      ? [{ key: "actions", label: "Actions", width: 80, fixed: true }]
      : []),
  ]);

  const filtered = useMemo(
    () =>
      rows.filter(
        (row) =>
          filters.every(
            (filter) =>
              !values[filter.id] || filter.matches(row, values[filter.id]),
          ) &&
          (!query ||
            searchText(row)
              .filter(Boolean)
              .some((value) => String(value).toLowerCase().includes(query))),
      ),
    [rows, filters, values, query, searchText],
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

  const update = (id: string, value: string) => {
    setValues((current) => ({ ...current, [id]: value }));
    setPage(1);
  };
  const applied: AppliedFilter[] = filters
    .filter((filter) => values[filter.id])
    .map((filter) => ({
      id: filter.id,
      label: filter.label,
      field: filter.label,
      value: values[filter.id],
      onRemove: () => update(filter.id, ""),
    }));
  const byKey = new Map(columns.map((column) => [column.key, column]));
  const tableColumns: DataTableColumn<Row>[] = layout.columns.map((column) => {
    const source = byKey.get(column.key);
    return {
      key: column.key,
      header: column.label,
      width: `${column.width}px`,
      fixed: column.fixed,
      sortable: Boolean(source?.sortable),
      kind: source?.kind,
      render: (row: Row) => {
        if (source) return source.render(row);
        const items = rowActions?.(row) ?? [];
        return items.length ? (
          <OverflowMenu label={`Actions for ${rowLabel(row)}`} items={items} />
        ) : (
          <EmptyValue />
        );
      },
    };
  });
  const firstLoad = resource.loading && !hasData;

  return (
    <PageContainer>
      <div className={styles.page}>
        <PageHeader title={title} subtitle={subtitle} />
        <SearchFilterToolbar
          className={styles.toolbar}
          searchId={`${tableId}-search`}
          searchLabel="Search"
          searchValue={search}
          onSearchChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          searchPlaceholder={searchPlaceholder}
          applied={applied}
          onClearFilters={
            applied.length
              ? () => {
                  setValues({});
                  setPage(1);
                }
              : undefined
          }
          disabled={firstLoad}
          loading={firstLoad}
          actions={
            <div className={styles.toolbarActions}>
              <FilterButton
                size="compact"
                count={applied.length}
                aria-expanded={filtersOpen}
                aria-controls={`${tableId}-filter-card`}
                onClick={() => setFiltersOpen((current) => !current)}
              />
              {actions}
            </div>
          }
        />
        {filtersOpen ? (
          <ResponsiveFilterPanel
            id={`${tableId}-filter-card`}
            label={`${title} filters`}
            className={styles.filterCard}
            onClose={() => setFiltersOpen(false)}
          >
            <div className={styles.filterGrid}>
              {filters.map((filter) => (
                <FormField
                  key={filter.id}
                  label={filter.label}
                  htmlFor={`${tableId}-${filter.id}`}
                >
                  <DropdownSelect
                    id={`${tableId}-${filter.id}`}
                    compact
                    clearable
                    value={values[filter.id] ?? ""}
                    placeholder={filter.placeholder}
                    options={filter.options.map((option) => ({
                      value: option,
                      label: option,
                    }))}
                    onChange={(value) =>
                      update(
                        filter.id,
                        Array.isArray(value) ? (value[0] ?? "") : value,
                      )
                    }
                  />
                </FormField>
              ))}
            </div>
          </ResponsiveFilterPanel>
        ) : null}
        {notices}
        {resource.denied ? (
          <PermissionDeniedState />
        ) : resource.error && !hasData ? (
          isOffline(resource.error) ? (
            <OfflineState />
          ) : (
            <ErrorState description={resource.error} retry={resource.reload} />
          )
        ) : firstLoad ? (
          <LoadingState title={`Loading ${title}`} />
        ) : (
          <SectionCard compact className={styles.table}>
            <RecordCount count={filtered.length} />
            {rows.length === 0 ? (
              <EmptyState title={emptyTitle} description={emptyDescription} />
            ) : filtered.length === 0 ? (
              <NoResultsState
                title="No matching records"
                description="No records match the current search and filters."
              />
            ) : (
              <>
                <DataTable
                  ariaLabel={title}
                  density="compact"
                  columns={tableColumns}
                  rows={visible}
                  rowKey={rowKey}
                  sort={sort}
                  onSort={(key) => {
                    setSort(nextSort(sort, key));
                    setPage(1);
                  }}
                  loading={resource.updating}
                  onRowActivate={onOpen}
                  rowActivateLabel={(row) => `Open ${rowLabel(row)}`}
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
    </PageContainer>
  );
}
