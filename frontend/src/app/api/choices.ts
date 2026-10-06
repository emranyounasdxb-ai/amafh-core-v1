import type { ApiClient } from "./http";
import type { Page } from "./models";

// Choice lists use the same scoped pages as the server; no browser-side scope expansion.
export async function choices<T>(
  api: ApiClient,
  path: string,
  signal?: AbortSignal,
): Promise<T[]> {
  const result: T[] = [];
  for (let page = 1; ; page++) {
    const response = await api.request<Page<T>>(
      `${path}${path.includes("?") ? "&" : "?"}page=${page}&pageSize=100`,
      { signal },
    );
    result.push(...response.items);
    if (result.length >= response.total || !response.items.length)
      return result;
  }
}
