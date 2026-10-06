import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import { cx } from "../lib/cx";
import { DsIcon } from "../icons";
import { optionMatches, type SelectOption } from "./Select";

export type ListboxMode = "single" | "multi" | "checkbox" | "radio";

export function Listbox({
  options,
  value,
  highlighted,
  onHighlight,
  onSelect,
  query = "",
  loading = false,
  loadingMore = false,
  emptyLabel = "No matching options",
  unavailable = false,
  unavailableLabel = "Options are unavailable.",
  mode = "single",
  expandedIds = [],
  onToggleExpand,
  label,
}: {
  options: SelectOption[];
  value: string | string[];
  highlighted: number;
  onHighlight: (index: number) => void;
  onSelect: (value: string) => void;
  query?: string;
  loading?: boolean;
  loadingMore?: boolean;
  emptyLabel?: string;
  unavailable?: boolean;
  unavailableLabel?: string;
  mode?: ListboxMode;
  expandedIds?: string[];
  onToggleExpand?: (id: string) => void;
  label?: string;
}) {
  const selected = Array.isArray(value) ? value : value ? [value] : [];
  const rows = useMemo(() => {
    const visible = (
      items: SelectOption[],
      depth = 0,
    ): Array<SelectOption & { depth: number }> =>
      items.flatMap((item) => {
        const kids =
          item.children && expandedIds.includes(item.value)
            ? visible(item.children, depth + 1)
            : [];
        return [{ ...item, depth }, ...kids];
      });
    const tree = options.some((item) => item.children?.length)
      ? visible(options)
      : options.map((item) => ({ ...item, depth: 0 }));
    return tree.filter((item) => optionMatches(item, query));
  }, [expandedIds, options, query]);
  const listRef = useRef<HTMLDivElement>(null);
  const itemHeight = 40;
  const virtual =
    rows.length > 80 &&
    !options.some((item) => item.group || item.children?.length);
  const maxHeight = 280;
  const [scrollTop, setScrollTop] = useState(0);
  const start = virtual
    ? Math.max(0, Math.floor(scrollTop / itemHeight) - 6)
    : 0;
  const end = virtual
    ? Math.min(rows.length, start + Math.ceil(maxHeight / itemHeight) + 12)
    : rows.length;

  useEffect(() => {
    const node = listRef.current?.querySelector<HTMLElement>(
      `[data-index="${highlighted}"]`,
    );
    node?.scrollIntoView({ block: "nearest" });
  }, [highlighted]);

  if (unavailable) {
    return <p className="ds-listbox__empty">{unavailableLabel}</p>;
  }
  if (loading && rows.length === 0) {
    return <p className="ds-listbox__empty">Loading options…</p>;
  }
  if (rows.length === 0) {
    return <p className="ds-listbox__empty">{emptyLabel}</p>;
  }

  const windowed = virtual ? rows.slice(start, end) : rows;
  const groups = new Map<string, typeof rows>();
  windowed.forEach((row) => {
    const key = row.group ?? "";
    groups.set(key, [...(groups.get(key) ?? []), row]);
  });

  const renderRow = (option: (typeof rows)[number], index: number) => {
    const isSelected = selected.includes(option.value);
    const hasChildren = Boolean(option.children?.length);
    return (
      <div
        key={`${option.value}-${index}`}
        className={cx(
          "ds-listbox__option",
          isSelected && "ds-listbox__option--selected",
          index === highlighted && "ds-listbox__option--active",
          option.disabled && "ds-listbox__option--disabled",
        )}
        style={{ paddingInlineStart: 12 + option.depth * 16 }}
        data-index={index}
      >
        {hasChildren ? (
          <button
            type="button"
            className="ds-listbox__branch"
            aria-label={
              expandedIds.includes(option.value)
                ? `Collapse ${option.label}`
                : `Expand ${option.label}`
            }
            onClick={(event) => {
              event.stopPropagation();
              onToggleExpand?.(option.value);
            }}
          >
            <span
              style={{
                display: "inline-flex",
                transform: expandedIds.includes(option.value)
                  ? "rotate(90deg)"
                  : undefined,
              }}
            >
              <DsIcon name="next" size={14} />
            </span>
          </button>
        ) : null}
        <button
          type="button"
          role="option"
          aria-selected={isSelected}
          disabled={option.disabled}
          className="ds-listbox__choice"
          onMouseEnter={() => onHighlight(index)}
          onClick={() => onSelect(option.value)}
        >
          {mode === "checkbox" || mode === "multi" ? (
            <span className={cx("ds-listbox__tick", isSelected && "is-on")} />
          ) : null}
          {mode === "radio" ? (
            <span className={cx("ds-listbox__radio", isSelected && "is-on")} />
          ) : null}
          {option.leading}
          <span className="ds-listbox__copy">
            <strong>{option.label}</strong>
            {option.description ? <em>{option.description}</em> : null}
          </span>
          {mode === "single" && isSelected ? (
            <DsIcon
              name="completed"
              size={14}
              className="ds-listbox__check"
            />
          ) : null}
        </button>
      </div>
    );
  };

  let cursor = virtual ? start - 1 : -1;
  const body: ReactNode[] = [];
  groups.forEach((items, group) => {
    if (group)
      body.push(
        <p key={`g-${group}`} className="ds-listbox__group">
          {group}
        </p>,
      );
    items.forEach((item) => {
      cursor += 1;
      body.push(renderRow(item, cursor));
    });
  });

  return (
    <div
      ref={listRef}
      className="ds-listbox"
      role="listbox"
      aria-label={label}
      aria-multiselectable={mode === "multi" || mode === "checkbox"}
      style={{ maxHeight, overflow: "auto" }}
      onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
    >
      {virtual ? (
        <div style={{ height: rows.length * itemHeight, position: "relative" }}>
          <div style={{ transform: `translateY(${start * itemHeight}px)` }}>
            {body}
          </div>
        </div>
      ) : (
        body
      )}
      {loadingMore ? <p className="ds-listbox__empty">Loading more…</p> : null}
    </div>
  );
}

export function moveHighlight(current: number, delta: number, count: number) {
  if (!count) return 0;
  return (current + delta + count) % count;
}

export function listboxKeydown(
  event: KeyboardEvent<HTMLElement>,
  count: number,
  highlighted: number,
  onHighlight: (index: number) => void,
  onSelect: () => void,
  onClose: () => void,
) {
  if (event.key === "ArrowDown") {
    event.preventDefault();
    onHighlight(moveHighlight(highlighted, 1, count));
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    onHighlight(moveHighlight(highlighted, -1, count));
  } else if (event.key === "Home") {
    event.preventDefault();
    onHighlight(0);
  } else if (event.key === "End") {
    event.preventDefault();
    onHighlight(Math.max(0, count - 1));
  } else if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    onSelect();
  } else if (event.key === "Escape") {
    event.preventDefault();
    onClose();
  }
}
