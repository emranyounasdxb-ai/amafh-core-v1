export type TableSort = { key: string; direction: "asc" | "desc" } | null;

export function nextSort(current: TableSort, key: string): TableSort {
  if (current?.key !== key) return { key, direction: "asc" };
  if (current.direction === "asc") return { key, direction: "desc" };
  return null;
}

export function sortCompleteRows<T extends object>(
  rows: T[],
  sort: TableSort,
): T[] {
  if (!sort) return rows;
  return [...rows].sort((left, right) => {
    const a = (left as Record<string, unknown>)[sort.key];
    const b = (right as Record<string, unknown>)[sort.key];
    if (a === null || a === undefined)
      return b === null || b === undefined ? 0 : 1;
    if (b === null || b === undefined) return -1;
    const result =
      typeof a === "number" && typeof b === "number"
        ? a - b
        : String(a).localeCompare(String(b), undefined, {
            numeric: true,
          });
    return sort.direction === "asc" ? result : -result;
  });
}
