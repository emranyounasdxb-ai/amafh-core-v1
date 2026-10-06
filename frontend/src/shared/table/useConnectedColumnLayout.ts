import { useState, type ReactNode } from "react";
import { useSession } from "../../app/session/useSession";
import {
  boundedWidth,
  moveColumn,
  reconcileColumns,
  type SavedColumn,
} from "./columnLayoutState";

export type ConnectedColumn<T> = {
  key: string;
  label: string;
  render?: (row: T) => ReactNode;
  sortKey?: string;
  width?: number;
  fixed?: boolean;
};

type LayoutState = { storageKey: string; columns: SavedColumn[] };

function readLayout(storageKey: string): SavedColumn[] {
  try {
    const raw = JSON.parse(window.localStorage.getItem(storageKey) || "null");
    if (!Array.isArray(raw)) return [];
    return raw.filter(
      (entry): entry is SavedColumn =>
        entry !== null &&
        typeof entry === "object" &&
        typeof entry.key === "string" &&
        typeof entry.width === "number" &&
        Number.isFinite(entry.width),
    );
  } catch {
    return [];
  }
}

export function useConnectedColumnLayout<T>(
  tableId: string,
  columns: ConnectedColumn<T>[],
) {
  const { session } = useSession();
  const storageKey = `amafh:table-layout:v1:${session?.employeeId || "signed-out"}:${tableId}`;
  const [state, setState] = useState<LayoutState>(() => ({
    storageKey,
    columns: readLayout(storageKey),
  }));
  const saved =
    state.storageKey === storageKey ? state.columns : readLayout(storageKey);
  const savedWidthKeys = new Set(
    saved
      .filter((column) => column.manual !== false)
      .map((column) => column.key),
  );
  const ordered = reconcileColumns(columns, saved);
  const update = (next: typeof ordered, resizedKey?: string) => {
    const entries = next.map(({ key, width }) => ({
      key,
      width,
      manual: key === resizedKey || savedWidthKeys.has(key),
    }));
    setState({ storageKey, columns: entries });
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(entries));
    } catch {
      // The mounted table remains usable when browser storage is unavailable.
    }
  };
  const resize = (key: string, width: number) => {
    update(
      ordered.map((column) =>
        column.key === key && !column.fixed
          ? { ...column, width: boundedWidth(width) }
          : column,
      ),
      key,
    );
  };
  const move = (key: string, target: string) => {
    update(moveColumn(ordered, key, target));
  };
  return { columns: ordered, savedWidthKeys, resize, move };
}
