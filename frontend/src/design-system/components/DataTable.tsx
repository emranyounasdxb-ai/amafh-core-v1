import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type MouseEvent,
  type PointerEvent,
  type ReactNode,
} from "react";
import { cx } from "../lib/cx";
import {
  resolveTableAlign,
  type TableAlign,
  type TableColumnKind,
} from "../lib/tableAlign";
import {
  isInteractiveRowTarget,
  shouldIgnoreRowActivation,
} from "../lib/rowActivation";
import { EmptyState } from "./EmptyState";
import { LoadingState } from "./LoadingState";
import { CheckboxDropdown } from "./TreeSelect";

export type DataTableAlign = TableAlign;
export type DataTableColumnKind = TableColumnKind;
export { resolveTableAlign };

export type DataTableColumn<T> = {
  key: string;
  header: string;
  align?: DataTableAlign;
  kind?: DataTableColumnKind;
  numeric?: boolean;
  width?: string;
  sortable?: boolean;
  fixed?: boolean;
  render?: (row: T) => ReactNode;
};

function kindMinWidth(kind?: DataTableColumnKind) {
  if (kind === "datetime") return 140;
  if (kind === "date") return 96;
  return 0;
}

export type DataTableSort = { key: string; direction: "asc" | "desc" };

type HeaderPointer = {
  key: string;
  x: number;
  width: number;
  mode: "pending" | "resize" | "reorder";
};

function columnWidthPx(width?: string, kind?: DataTableColumnKind): number {
  const parsed = Number.parseInt(width ?? "", 10);
  const base = Number.isFinite(parsed) ? parsed : 160;
  return Math.max(kindMinWidth(kind), base);
}

function columnKeyFromPoint(x: number, y: number): string | null {
  const header = document
    .elementFromPoint(x, y)
    ?.closest("[data-column-key]");
  return header?.getAttribute("data-column-key") ?? null;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  sort,
  onSort,
  selectedKeys,
  onToggleRow,
  onToggleAll,
  empty,
  error,
  loading,
  density = "compact",
  stackOnNarrow = true,
  ariaLabel,
  className,
  onRowActivate,
  rowActivateLabel,
  rowSelectLabel,
  onColumnResize,
  onColumnReorder,
}: {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  sort?: DataTableSort | null;
  onSort?: (key: string) => void;
  selectedKeys?: string[];
  onToggleRow?: (key: string) => void;
  onToggleAll?: () => void;
  empty?: ReactNode;
  error?: ReactNode;
  loading?: boolean;
  density?: "standard" | "compact";
  stackOnNarrow?: boolean;
  ariaLabel: string;
  className?: string;
  onRowActivate?: (row: T) => void;
  rowActivateLabel?: (row: T) => string;
  rowSelectLabel?: (row: T) => string;
  onColumnResize?: (key: string, width: number) => void;
  onColumnReorder?: (fromKey: string, toKey: string) => void;
}) {
  const headerPointer = useRef<HeaderPointer | null>(null);
  const ignoreSortClick = useRef(false);
  const textSelection = useRef("");
  const [dragged, setDragged] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const layoutEnabled = Boolean(onColumnResize || onColumnReorder);

  useEffect(
    () => () => {
      if (headerPointer.current)
        document.body.style.userSelect = textSelection.current;
    },
    [],
  );

  if (error) {
    return <div className={cx("ds-table-wrap", className)}>{error}</div>;
  }
  if (loading && !rows.length) {
    return (
      <div className={cx("ds-table-wrap", className)}>
        <LoadingState />
      </div>
    );
  }
  const selectable = Boolean(onToggleRow);
  const keys = rows.map(rowKey);
  const allSelected =
    keys.length > 0 && keys.every((key) => selectedKeys?.includes(key));
  const someSelected =
    !allSelected && keys.some((key) => selectedKeys?.includes(key));
  const selectionWidth = selectable ? 36 : 0;
  const totalWidth =
    selectionWidth +
    columns.reduce(
      (sum, column) => sum + columnWidthPx(column.width, column.kind),
      0,
    );

  const finishHeaderPointer = (event: PointerEvent<HTMLElement>) => {
    const pointer = headerPointer.current;
    headerPointer.current = null;
    document.body.style.userSelect = textSelection.current;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (pointer?.mode === "resize") {
      setAnnouncement("Column resize complete");
      event.stopPropagation();
      return;
    }
    if (pointer?.mode === "reorder") {
      const target = columnKeyFromPoint(event.clientX, event.clientY);
      if (target && target !== pointer.key) {
        ignoreSortClick.current = true;
        onColumnReorder?.(pointer.key, target);
        const label =
          columns.find((column) => column.key === pointer.key)?.header ??
          pointer.key;
        setAnnouncement(`${label} column moved`);
      }
    }
    setDragged(null);
    setDropTarget(null);
  };

  return (
    <div
      className={cx(
        "ds-table-wrap",
        density === "compact" && "ds-table-wrap--compact",
        stackOnNarrow && "ds-table-wrap--stack",
        className,
      )}
    >
      {layoutEnabled ? (
        <span className="ds-table__live" aria-live="polite">
          {announcement}
        </span>
      ) : null}
      <table
        className="ds-table"
        aria-label={ariaLabel}
        aria-busy={loading}
        data-column-layout={layoutEnabled || undefined}
        style={
          layoutEnabled
            ? ({
                "--ds-table-layout-width": `${totalWidth}px`,
              } as CSSProperties)
            : undefined
        }
      >
        {layoutEnabled ? (
          <colgroup>
            {selectable ? <col style={{ width: selectionWidth }} /> : null}
            {columns.map((column) => (
              <col
                key={column.key}
                style={{ width: columnWidthPx(column.width, column.kind) }}
              />
            ))}
          </colgroup>
        ) : null}
        <thead>
          <tr>
            {selectable ? (
              <th className="ds-table__check">
                <input
                  ref={(node) => {
                    if (node) node.indeterminate = someSelected;
                  }}
                  type="checkbox"
                  checked={allSelected}
                  aria-checked={someSelected ? "mixed" : allSelected}
                  aria-label="Select all rows in the current view"
                  onChange={onToggleAll}
                />
              </th>
            ) : null}
            {columns.map((column) => {
              const width = columnWidthPx(column.width, column.kind);
              const align = resolveTableAlign(column);
              const canResize = Boolean(onColumnResize) && !column.fixed;
              const canReorder = Boolean(onColumnReorder) && !column.fixed;
              const canSort = Boolean(column.sortable && onSort);
              return (
                <th
                  key={column.key}
                  data-align={align}
                  data-kind={column.kind}
                  data-column-key={column.key}
                  data-dragging={dragged === column.key || undefined}
                  data-drop-target={dropTarget === column.key || undefined}
                  className={cx(layoutEnabled && "ds-table__th--layout")}
                  style={
                    !layoutEnabled && column.width
                      ? { width: column.width }
                      : undefined
                  }
                  aria-sort={
                    canSort
                      ? sort?.key === column.key
                        ? sort.direction === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                      : undefined
                  }
                  onPointerDown={
                    canReorder
                      ? (event) => {
                          if (
                            event.button !== 0 ||
                            (event.target instanceof Element &&
                              event.target.closest(".ds-table__resize"))
                          ) {
                            return;
                          }
                          headerPointer.current = {
                            key: column.key,
                            x: event.clientX,
                            width,
                            mode: "pending",
                          };
                        }
                      : undefined
                  }
                  onPointerMove={
                    canReorder
                      ? (event) => {
                          const pointer = headerPointer.current;
                          if (!pointer || pointer.key !== column.key) return;
                          if (
                            pointer.mode === "pending" &&
                            Math.abs(event.clientX - pointer.x) >= 6
                          ) {
                            pointer.mode = "reorder";
                            textSelection.current =
                              document.body.style.userSelect;
                            document.body.style.userSelect = "none";
                            event.currentTarget.setPointerCapture(
                              event.pointerId,
                            );
                            setDragged(column.key);
                          }
                          if (pointer.mode === "reorder") {
                            const target = columnKeyFromPoint(
                              event.clientX,
                              event.clientY,
                            );
                            setDropTarget(
                              target && target !== column.key ? target : null,
                            );
                          }
                        }
                      : undefined
                  }
                  onPointerUp={canReorder ? finishHeaderPointer : undefined}
                  onPointerCancel={canReorder ? finishHeaderPointer : undefined}
                >
                  {canSort ? (
                    <button
                      type="button"
                      className="ds-table__sort"
                      onPointerDown={() => {
                        ignoreSortClick.current = false;
                      }}
                      onClick={() => {
                        if (ignoreSortClick.current) {
                          ignoreSortClick.current = false;
                          return;
                        }
                        if (headerPointer.current?.mode === "reorder") return;
                        onSort?.(column.key);
                      }}
                    >
                      {column.header}
                      <span aria-hidden="true">
                        {sort?.key === column.key
                          ? sort.direction === "asc"
                            ? "↑"
                            : "↓"
                          : "↕"}
                      </span>
                    </button>
                  ) : (
                    <span className="ds-table__heading">{column.header}</span>
                  )}
                  {canResize ? (
                    <span
                      className="ds-table__resize"
                      role="separator"
                      tabIndex={0}
                      data-ds-row-interactive
                      aria-orientation="vertical"
                      aria-label={`Resize ${column.header} column`}
                      aria-valuemin={96}
                      aria-valuenow={width}
                      onPointerDown={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        textSelection.current = document.body.style.userSelect;
                        document.body.style.userSelect = "none";
                        headerPointer.current = {
                          key: column.key,
                          x: event.clientX,
                          width,
                          mode: "resize",
                        };
                        event.currentTarget.setPointerCapture(event.pointerId);
                      }}
                      onPointerMove={(event) => {
                        const pointer = headerPointer.current;
                        if (
                          pointer?.mode !== "resize" ||
                          pointer.key !== column.key
                        ) {
                          return;
                        }
                        event.stopPropagation();
                        onColumnResize?.(
                          column.key,
                          pointer.width + event.clientX - pointer.x,
                        );
                      }}
                      onPointerUp={finishHeaderPointer}
                      onPointerCancel={finishHeaderPointer}
                      onKeyDown={(event) => {
                        if (
                          event.key !== "ArrowLeft" &&
                          event.key !== "ArrowRight"
                        ) {
                          return;
                        }
                        event.preventDefault();
                        event.stopPropagation();
                        onColumnResize?.(
                          column.key,
                          width +
                            (event.key === "ArrowRight" ? 1 : -1) *
                              (event.shiftKey ? 24 : 12),
                        );
                        setAnnouncement(`${column.header} column resized`);
                      }}
                    />
                  ) : null}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const key = rowKey(row);
            const selected = selectedKeys?.includes(key);
            const activatable = Boolean(onRowActivate);
            const activateRow = () => onRowActivate?.(row);
            const handleActivateClick = (
              event: MouseEvent<HTMLTableRowElement>,
            ) => {
              if (shouldIgnoreRowActivation(event, event)) return;
              activateRow();
            };
            const handleActivateKeyDown = (
              event: KeyboardEvent<HTMLTableRowElement>,
            ) => {
              if (event.key !== "Enter" && event.key !== " ") return;
              if (isInteractiveRowTarget(event.target, event.currentTarget)) {
                return;
              }
              event.preventDefault();
              activateRow();
            };
            return (
              <tr
                key={key}
                data-selected={selected || undefined}
                data-interactive={activatable || undefined}
                tabIndex={activatable ? 0 : undefined}
                aria-label={
                  activatable
                    ? (rowActivateLabel?.(row) ?? "Open record")
                    : undefined
                }
                onClick={activatable ? handleActivateClick : undefined}
                onKeyDown={activatable ? handleActivateKeyDown : undefined}
              >
                {selectable ? (
                  <td className="ds-table__check" data-label="Select">
                    <input
                      type="checkbox"
                      checked={Boolean(selected)}
                      aria-label={rowSelectLabel?.(row) ?? "Select row"}
                      onClick={(event) => event.stopPropagation()}
                      onChange={() => onToggleRow?.(key)}
                    />
                  </td>
                ) : null}
                {columns.map((column) => (
                  <td
                    key={column.key}
                    data-label={column.header}
                    data-align={resolveTableAlign(column)}
                    data-kind={column.kind}
                    className={
                      column.numeric ||
                      column.kind === "number" ||
                      column.kind === "money"
                        ? "ds-numeric"
                        : undefined
                    }
                  >
                    {column.render
                      ? column.render(row)
                      : String(
                          (row as Record<string, unknown>)[column.key] ?? "",
                        )}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {!rows.length && !loading
        ? (empty ?? (
            <EmptyState
              title="No records"
              description="No authorized rows match the current filters."
            />
          ))
        : null}
    </div>
  );
}

export function ColumnVisibilityMenu({
  id = "column-visibility",
  columns,
  visibleKeys,
  onChange,
}: {
  id?: string;
  columns: { key: string; label: string }[];
  visibleKeys: string[];
  onChange: (keys: string[]) => void;
}) {
  return (
    <CheckboxDropdown
      id={id}
      label="Visible columns"
      options={columns.map((column) => ({
        value: column.key,
        label: column.label,
      }))}
      value={visibleKeys}
      onChange={onChange}
      compact
    />
  );
}
