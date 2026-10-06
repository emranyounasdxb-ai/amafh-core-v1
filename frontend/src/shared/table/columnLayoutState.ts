export type SavedColumn = { key: string; width: number; manual?: boolean };
export type LayoutColumn = { key: string; width?: number; fixed?: boolean };

export const MIN_WIDTH = 96;
export const MAX_WIDTH = 480;
const DEFAULT_WIDTH = 160;

export function boundedWidth(value: number): number {
  return Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Math.round(value)));
}

export function renderedColumnWidths(
  preferredWidths: number[],
  availableWidth: number,
  fixed: boolean[] = [],
): number[] {
  const preferredTotal = preferredWidths.reduce((sum, width) => sum + width, 0);
  if (!preferredTotal || availableWidth <= preferredTotal)
    return [...preferredWidths];

  const flexibleTotal = preferredWidths.reduce(
    (sum, width, index) => sum + (fixed[index] ? 0 : width),
    0,
  );
  // A restored layout can have a manual preference for every column.
  // Preserve their proportions while filling the table when none can flex.
  if (!flexibleTotal)
    return renderedColumnWidths(preferredWidths, availableWidth);
  const extra = availableWidth - preferredTotal;
  let remaining = extra;
  let lastFlexible = -1;
  preferredWidths.forEach((_, index) => {
    if (!fixed[index]) lastFlexible = index;
  });
  return preferredWidths.map((width, index) => {
    if (fixed[index]) return width;
    const added =
      index === lastFlexible ? remaining : (extra * width) / flexibleTotal;
    remaining -= added;
    return width + added;
  });
}

export function reconcileColumns<T extends LayoutColumn>(
  columns: T[],
  saved: SavedColumn[],
): (T & { width: number })[] {
  const allowed = new Map(columns.map((column) => [column.key, column]));
  const seen = new Set<string>();
  const movable = [
    ...saved
      .filter((entry) => {
        const column = allowed.get(entry.key);
        if (!column || column.fixed || seen.has(entry.key)) return false;
        seen.add(entry.key);
        return true;
      })
      .map((entry) => ({
        ...allowed.get(entry.key)!,
        width: boundedWidth(entry.width),
      })),
    ...columns
      .filter((column) => !column.fixed && !seen.has(column.key))
      .map((column) => ({
        ...column,
        width: boundedWidth(column.width ?? DEFAULT_WIDTH),
      })),
  ];
  return columns.map((column) =>
    column.fixed
      ? { ...column, width: boundedWidth(column.width ?? DEFAULT_WIDTH) }
      : movable.shift()!,
  );
}

export function moveColumn<T extends LayoutColumn>(
  columns: T[],
  key: string,
  target: string,
): T[] {
  const from = columns.findIndex((column) => column.key === key);
  const to = columns.findIndex((column) => column.key === target);
  if (
    from < 0 ||
    to < 0 ||
    from === to ||
    columns[from].fixed ||
    columns[to].fixed ||
    columns
      .slice(Math.min(from, to), Math.max(from, to) + 1)
      .some((column) => column.fixed)
  )
    return columns;
  const next = [...columns];
  next.splice(to, 0, next.splice(from, 1)[0]);
  return next;
}
