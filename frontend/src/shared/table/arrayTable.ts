import { useState } from "react";
import type { ApiClient } from "../../app/api/http";
import type { Page } from "../../app/api/models";
import { useResource } from "../../app/api/useResource";
import type { ServerTable } from "./serverTable";
import { useTableSelection } from "./useTableSelection";

const loadAll = <T>(api: ApiClient, path: string, signal: AbortSignal) =>
  api.request<T[]>(path, { signal }).then(
    (items): Page<T> => ({
      items,
      total: items.length,
      page: 1,
      pageSize: items.length,
    }),
  );

/**
 * Table state for an unpaged list endpoint. Rows keep the server order so the
 * selected-row export positions match the server's full list.
 */
export function useArrayTable<T extends { id: string }>(
  tableId: string,
  basePath: string,
  query: string,
  refresh: number,
): ServerTable<T> {
  const [paging, setPaging] = useState({ query, page: 1, size: 25 });
  if (paging.query !== query) setPaging({ query, page: 1, size: paging.size });
  const page = paging.query === query ? paging.page : 1;
  const size = paging.size;
  const sourcePath = query ? `${basePath}?${query}` : basePath;
  const resource = useResource<Page<T>>(
    sourcePath,
    refresh,
    loadAll<T>,
    "array-table",
  );
  const all = resource.data?.items ?? [];
  const total = all.length;
  const pageCount = Math.max(1, Math.ceil(total / size));
  const current = Math.min(page, pageCount);
  const rows = all.slice((current - 1) * size, current * size);
  const selection = useTableSelection<T>(tableId, {
    path: sourcePath,
    page: current,
    size,
    total,
    busy: resource.loading || Boolean(resource.error),
  });
  return {
    resource,
    rows,
    total,
    page: current,
    size,
    pageCount,
    sort: null,
    selection,
    setPage: (next: number) => setPaging({ query, page: next, size }),
    setSize: (next: number) => setPaging({ query, page: 1, size: next }),
    toggleSort: () => undefined,
    sortable: () => false,
  };
}
