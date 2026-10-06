import type { ReactNode } from "react";
import {
  DataTable,
  type DataTableColumn,
  type DataTableSort,
} from "../components/DataTable";
import { Pagination } from "../components/Pagination";
import { SectionCard } from "../components/SectionCard";
import { TableToolbar } from "./TableToolbar";

export function ResponsiveDataTable<T>({
  title,
  description,
  actions,
  columns,
  rows,
  rowKey,
  sort,
  onSort,
  selectedKeys,
  onToggleRow,
  onToggleAll,
  page,
  pageCount,
  onPageChange,
  pageSize,
  onPageSizeChange,
  empty,
  loading,
  error,
  ariaLabel,
  onRowActivate,
  rowActivateLabel,
  rowSelectLabel,
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  sort?: DataTableSort | null;
  onSort?: (key: string) => void;
  selectedKeys?: string[];
  onToggleRow?: (key: string) => void;
  onToggleAll?: () => void;
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
  pageSize?: number;
  onPageSizeChange?: (size: number) => void;
  empty?: ReactNode;
  loading?: boolean;
  error?: ReactNode;
  ariaLabel: string;
  onRowActivate?: (row: T) => void;
  rowActivateLabel?: (row: T) => string;
  rowSelectLabel?: (row: T) => string;
}) {
  return (
    <SectionCard compact>
      {title || actions ? (
        <TableToolbar title={title ?? ""} description={description}>
          {actions}
        </TableToolbar>
      ) : null}
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={rowKey}
        sort={sort}
        onSort={onSort}
        selectedKeys={selectedKeys}
        onToggleRow={onToggleRow}
        onToggleAll={onToggleAll}
        empty={empty}
        loading={loading}
        error={error}
        ariaLabel={ariaLabel}
        density="compact"
        onRowActivate={onRowActivate}
        rowActivateLabel={rowActivateLabel}
        rowSelectLabel={rowSelectLabel}
      />
      <Pagination
        page={page}
        pageCount={pageCount}
        onPageChange={onPageChange}
        pageSize={pageSize}
        onPageSizeChange={onPageSizeChange}
      />
    </SectionCard>
  );
}
