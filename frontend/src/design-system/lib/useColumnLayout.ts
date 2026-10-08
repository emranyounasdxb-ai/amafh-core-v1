import { createContext, useState } from "react";
import {
  boundedWidth,
  moveColumn,
  reconcileColumns,
  type LayoutColumn,
  type SavedColumn,
} from "../../shared/table/columnLayoutState";

/** The application opts into per-user table preferences; nested overlays inherit the scope. */
export const TablePreferenceScope = createContext<string | null>(null);

type LayoutState = { storageKey: string | null; columns: SavedColumn[] };

function readLayout(storageKey: string | null): SavedColumn[] {
  if (!storageKey) return [];
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

export function useColumnLayout<T extends LayoutColumn>(
  storageKey: string | null,
  columns: T[],
) {
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
      if (storageKey)
        window.localStorage.setItem(storageKey, JSON.stringify(entries));
    } catch {
      // The mounted table remains usable when browser storage is unavailable.
    }
  };
  const resize = (key: string, width: number) => {
    update(
      ordered.map((column) =>
        column.key === key && !column.fixed
          ? {
              ...column,
              width: boundedWidth(Math.max(width, column.minWidth ?? 96)),
            }
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
