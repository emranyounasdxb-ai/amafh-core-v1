import { useState } from "react";
import { download } from "../../app/api/download";
import { useSession } from "../../app/session/useSession";
import { rowFingerprint } from "./rowFingerprint";

export type TableExportSource<T> = {
  path: string;
  page: number;
  size: number;
  total: number;
  busy?: boolean;
  rowForSelection?: (row: T) => Record<string, unknown>;
  positionForRow?: (row: T, index: number) => number;
};

type Entry = { index: number; fingerprint: string };
type Selection = {
  key: string;
  allMatching: boolean;
  entries: Map<number, Entry>;
};

export function useTableSelection<T>(
  tableId: string,
  source?: TableExportSource<T>,
) {
  const { api, session } = useSession();
  const allowed =
    !!source &&
    (session?.designation === "Owner" ||
      session?.designation === "Managing Director");
  const key = `${session?.employeeId || ""}:${tableId}:${source?.path || ""}`;
  const [state, setState] = useState<Selection>({
    key,
    allMatching: false,
    entries: new Map(),
  });
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const selected =
    state.key === key
      ? state
      : { key, allMatching: false, entries: new Map<number, Entry>() };
  const total = source?.total || 0;
  const selectedCount = selected.allMatching
    ? Math.max(0, total - selected.entries.size)
    : selected.entries.size;
  const position = (row: T, index: number) =>
    source?.positionForRow
      ? source.positionForRow(row, index)
      : ((source?.page || 1) - 1) * (source?.size || 25) + index;
  const checked = (row: T, index: number) => {
    const rowIndex = position(row, index);
    return selected.allMatching
      ? !selected.entries.has(rowIndex)
      : selected.entries.has(rowIndex);
  };
  const toggleRow = (row: T, index: number) => {
    const current: Entry = {
      index: position(row, index),
      fingerprint: rowFingerprint(
        source?.rowForSelection
          ? source.rowForSelection(row)
          : (row as Record<string, unknown>),
      ),
    };
    const next = new Map(selected.entries);
    if (next.has(current.index)) next.delete(current.index);
    else next.set(current.index, current);
    setState({ ...selected, entries: next });
  };
  const toggleRows = (rows: T[]) => {
    if (!rows.length) return;
    const allChecked = rows.every((row, index) => checked(row, index));
    const next = new Map(selected.entries);
    rows.forEach((row, index) => {
      const entry: Entry = {
        index: position(row, index),
        fingerprint: rowFingerprint(
          source?.rowForSelection
            ? source.rowForSelection(row)
            : (row as Record<string, unknown>),
        ),
      };
      const include = selected.allMatching ? allChecked : !allChecked;
      if (include) next.set(entry.index, entry);
      else next.delete(entry.index);
    });
    setState({ ...selected, entries: next });
  };
  const toggleAll = () => {
    if (total <= 0) return;
    setState({
      key,
      allMatching: !selected.allMatching && selectedCount !== total,
      entries: new Map(),
    });
  };
  const exportCsv = async () => {
    if (!source || !allowed || !selectedCount) return;
    setWorking(true);
    setError("");
    try {
      await download(api, "/table-exports/csv", {
        method: "POST",
        body: JSON.stringify({
          sourcePath: source.path,
          mode: "selected",
          allMatching: selected.allMatching,
          expectedTotal: total,
          selections: [...selected.entries.values()],
        }),
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "CSV export failed");
    } finally {
      setWorking(false);
    }
  };
  return {
    allowed,
    checked,
    toggleRow,
    toggleRows,
    toggleAll,
    headerChecked: total > 0 && selectedCount === total,
    headerIndeterminate: selectedCount > 0 && selectedCount < total,
    selectedCount,
    working,
    error,
    exportCsv,
  };
}
