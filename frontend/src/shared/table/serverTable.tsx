import { useState, type ReactNode } from "react";
import {
  ErrorState,
  LoadingState,
  OfflineState,
  PermissionDeniedState,
  type DataTableColumnKind,
} from "../../design-system";
import type { Page } from "../../app/api/models";
import { useResource } from "../../app/api/useResource";
import { serverSortField } from "./serverSortFields";
import { nextSort, type TableSort } from "./tableSortState";
import { useTableSelection } from "./useTableSelection";

export type ServerColumn<T> = {
  key: string;
  label: string;
  width: number;
  kind?: DataTableColumnKind;
  fixed?: boolean;
  render: (row: T) => ReactNode;
};

export function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

export function resourceFeedback(
  resource: {
    data: unknown;
    error: string;
    denied: boolean;
    loading: boolean;
    reload: () => void;
  },
  loadingTitle: string,
): ReactNode {
  if (resource.denied)
    return (
      <PermissionDeniedState
        title="Record unavailable"
        description="This record is unavailable or outside your authorized scope."
      />
    );
  if (resource.error && !resource.data)
    return isOffline(resource.error) ? (
      <OfflineState />
    ) : (
      <ErrorState description={resource.error} retry={resource.reload} />
    );
  if (!resource.data) return <LoadingState title={loadingTitle} />;
  return null;
}

export function filterQuery(values: Record<string, string>) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values))
    if (value) params.set(key, value);
  return params.toString();
}

export function useServerTable<T extends { id: string }>(
  tableId: string,
  basePath: string,
  query: string,
  refresh: number,
  initial?: { page: number; size: number; sort: TableSort } | null,
) {
  const [paging, setPaging] = useState(() => ({
    query,
    page: initial?.page ?? 1,
    size: initial?.size ?? 25,
  }));
  const [sort, setSort] = useState<TableSort>(initial?.sort ?? null);
  if (paging.query !== query) setPaging({ query, page: 1, size: paging.size });
  const page = paging.query === query ? paging.page : 1;
  const size = paging.size;
  const params = new URLSearchParams(query);
  const sortField = sort ? serverSortField(basePath, sort.key) : undefined;
  if (sort && sortField) {
    params.set("sort", sortField);
    params.set("direction", sort.direction);
  }
  const search = params.toString();
  const sourcePath = search ? `${basePath}?${search}` : basePath;
  const listPath = `${sourcePath}${search ? "&" : "?"}page=${page}&pageSize=${size}`;
  const resource = useResource<Page<T>>(listPath, refresh);
  const rows = resource.data?.items ?? [];
  const total = resource.data?.total ?? 0;
  const selection = useTableSelection<T>(tableId, {
    path: sourcePath,
    page,
    size,
    total,
    busy: resource.loading || Boolean(resource.error),
  });
  return {
    resource,
    rows,
    total,
    page,
    size,
    pageCount: Math.max(1, Math.ceil(total / size)),
    sort,
    selection,
    setPage: (next: number) => setPaging({ query, page: next, size }),
    setSize: (next: number) => setPaging({ query, page: 1, size: next }),
    toggleSort: (key: string) => {
      setSort(nextSort(sort, key));
      setPaging({ query, page: 1, size });
    },
    sortable: (key: string) => Boolean(serverSortField(basePath, key)),
  };
}

export type ServerTable<T extends { id: string }> = ReturnType<
  typeof useServerTable<T>
>;
