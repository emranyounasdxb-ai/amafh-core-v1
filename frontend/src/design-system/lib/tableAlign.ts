export type TableAlign = "start" | "center" | "end";
export type TableColumnKind =
  | "text"
  | "number"
  | "money"
  | "mixed"
  | "date"
  | "datetime";

export function resolveTableAlign(column: {
  align?: TableAlign;
  kind?: TableColumnKind;
  numeric?: boolean;
}): TableAlign {
  if (column.align) return column.align;
  if (
    column.kind === "number" ||
    column.kind === "money" ||
    (column.numeric &&
      column.kind !== "date" &&
      column.kind !== "datetime" &&
      column.kind !== "mixed")
  ) {
    return "end";
  }
  return "start";
}
