import {
  DataTable,
  EmptyState,
  ErrorState,
  InlineNotice,
  LoadingState,
  NoResultsState,
  OfflineState,
  Pagination,
  PermissionDeniedState,
  RecordCount,
  SectionCard,
  type DataTableColumn,
} from "../../design-system";
import { isOffline, type ServerColumn, type ServerTable } from "./serverTable";
import { useConnectedColumnLayout } from "./useConnectedColumnLayout";
import styles from "./ServerTableSection.module.css";

export function ServerTableSection<T extends { id: string }>({
  table,
  tableId,
  ariaLabel,
  columns,
  filtered,
  emptyTitle,
  emptyDescription,
  noResultsDescription = "No records match the current filters.",
  loadingTitle,
  onRowActivate,
  rowLabel,
  stackOnNarrow,
}: {
  table: ServerTable<T>;
  tableId: string;
  ariaLabel: string;
  columns: ServerColumn<T>[];
  filtered: boolean;
  emptyTitle: string;
  emptyDescription: string;
  noResultsDescription?: string;
  loadingTitle: string;
  onRowActivate?: (row: T) => void;
  rowLabel: (row: T) => string;
  stackOnNarrow?: boolean;
}) {
  const layout = useConnectedColumnLayout<T>(
    tableId,
    columns.map(({ key, label, width, fixed }) => ({
      key,
      label,
      width,
      fixed,
    })),
  );
  const { resource, rows, selection } = table;
  const definitions = new Map(columns.map((column) => [column.key, column]));
  const tableColumns: DataTableColumn<T>[] = layout.columns.flatMap(
    (column) => {
      const definition = definitions.get(column.key);
      if (!definition) return [];
      return [
        {
          key: column.key,
          header: definition.label,
          width: `${column.width}px`,
          fixed: definition.fixed,
          kind: definition.kind,
          sortable: table.sortable(column.key),
          render: definition.render,
        },
      ];
    },
  );

  if (resource.denied) return <PermissionDeniedState />;
  if (resource.error && !resource.data)
    return isOffline(resource.error) ? (
      <OfflineState />
    ) : (
      <ErrorState description={resource.error} retry={resource.reload} />
    );
  if (resource.loading && !resource.data)
    return <LoadingState title={loadingTitle} />;

  const selectedKeys = rows
    .filter((row, index) => selection.checked(row, index))
    .map((row) => row.id);
  return (
    <>
      {selection.error ? (
        <InlineNotice tone="error" title="Export failed">
          {selection.error}
        </InlineNotice>
      ) : null}
      <SectionCard compact className={styles.table}>
        <RecordCount count={table.total} />
        {table.total === 0 ? (
          filtered ? (
            <NoResultsState
              title="No matching records"
              description={noResultsDescription}
            />
          ) : (
            <EmptyState title={emptyTitle} description={emptyDescription} />
          )
        ) : (
          <>
            <DataTable
              ariaLabel={ariaLabel}
              density="compact"
              stackOnNarrow={stackOnNarrow}
              columns={tableColumns}
              rows={rows}
              rowKey={(row) => row.id}
              sort={table.sort}
              onSort={table.toggleSort}
              selectedKeys={selection.allowed ? selectedKeys : undefined}
              onToggleRow={
                selection.allowed
                  ? (key) => {
                      const index = rows.findIndex((row) => row.id === key);
                      if (index >= 0) selection.toggleRow(rows[index], index);
                    }
                  : undefined
              }
              onToggleAll={selection.allowed ? selection.toggleAll : undefined}
              loading={resource.updating}
              onRowActivate={onRowActivate}
              rowActivateLabel={(row) => `Open ${rowLabel(row)}`}
              rowSelectLabel={(row) => `Select ${rowLabel(row)}`}
              onColumnResize={layout.resize}
              onColumnReorder={layout.move}
            />
            <Pagination
              page={table.page}
              pageCount={table.pageCount}
              onPageChange={table.setPage}
              pageSize={table.size}
              onPageSizeChange={table.setSize}
            />
          </>
        )}
      </SectionCard>
    </>
  );
}
