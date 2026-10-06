// Kept in memory only, per signed-in employee and list, so Back from a detail page restores the list.
const saved = new Map<string, unknown>();

const storeKey = (employeeId: string, listId: string) =>
  `${employeeId}:${listId}`;

export function readListState<T>(
  employeeId: string | null | undefined,
  listId: string,
): T | null {
  if (!employeeId) return null;
  return (saved.get(storeKey(employeeId, listId)) as T | undefined) ?? null;
}

export function saveListState<T>(
  employeeId: string | null | undefined,
  listId: string,
  state: T,
) {
  if (employeeId) saved.set(storeKey(employeeId, listId), state);
}
