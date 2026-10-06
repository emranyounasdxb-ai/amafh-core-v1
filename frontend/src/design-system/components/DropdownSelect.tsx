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
import { Listbox, listboxKeydown, type ListboxMode } from "./Listbox";
import { PositionedOverlay } from "./PositionedOverlay";
import { flattenOptions, optionMatches, type SelectOption } from "./Select";

export type DropdownSelectMode = ListboxMode | "searchable";

export function DropdownSelect({
  id,
  label,
  options,
  value,
  onChange,
  placeholder = "Select",
  compact,
  disabled,
  readOnly,
  invalid,
  required,
  searchable = false,
  mode = "single",
  loading,
  loadingMore,
  unavailable,
  emptyLabel,
  query,
  onQueryChange,
  creatable,
  onCreate,
  clearable = true,
  leading,
}: {
  id: string;
  label?: string;
  options: SelectOption[];
  value: string | string[];
  onChange: (value: string | string[]) => void;
  placeholder?: string;
  compact?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  invalid?: boolean;
  required?: boolean;
  searchable?: boolean;
  mode?: DropdownSelectMode;
  loading?: boolean;
  loadingMore?: boolean;
  unavailable?: boolean;
  emptyLabel?: string;
  query?: string;
  onQueryChange?: (value: string) => void;
  creatable?: boolean;
  onCreate?: (query: string) => void;
  clearable?: boolean;
  leading?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [internalQuery, setInternalQuery] = useState("");
  const [highlighted, setHighlighted] = useState(0);
  const [expandedIds, setExpandedIds] = useState<string[]>([]);
  const [typeahead, setTypeahead] = useState("");
  const anchorRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const wasOpen = useRef(false);
  const search = query ?? internalQuery;
  const setSearch = onQueryChange ?? setInternalQuery;
  const skipFocusOpen = useRef(false);
  const selectedValues = Array.isArray(value) ? value : value ? [value] : [];
  const flat = useMemo(() => flattenOptions(options), [options]);
  const visible = useMemo(
    () =>
      onQueryChange
        ? options
        : options.filter((option) => optionMatches(option, search)),
    [onQueryChange, options, search],
  );
  const visibleFlat = useMemo(() => flattenOptions(visible), [visible]);
  const selected = flat.filter((option) =>
    selectedValues.includes(option.value),
  );
  const listMode: ListboxMode =
    mode === "searchable" ? "single" : mode === "multi" ? "multi" : mode;
  const canOpen = !disabled && !readOnly && !unavailable;
  const closeList = () => {
    skipFocusOpen.current = true;
    setSearch("");
    setOpen(false);
  };

  useEffect(() => {
    if (open) {
      wasOpen.current = true;
      return;
    }
    if (!wasOpen.current) return;
    wasOpen.current = false;
    (searchable ? searchRef.current : triggerRef.current)?.focus();
  }, [open, searchable]);

  useEffect(() => {
    if (!typeahead) return;
    const timer = window.setTimeout(() => setTypeahead(""), 500);
    const match = visibleFlat.findIndex((option) =>
      option.label.toLowerCase().startsWith(typeahead.toLowerCase()),
    );
    if (match >= 0) setHighlighted(match);
    return () => window.clearTimeout(timer);
  }, [typeahead, visibleFlat]);

  const selectValue = (next: string) => {
    if (listMode === "multi" || listMode === "checkbox") {
      const current = selectedValues.includes(next)
        ? selectedValues.filter((item) => item !== next)
        : [...selectedValues, next];
      onChange(current);
      return;
    }
    onChange(next);
    closeList();
  };

  const onKey = (event: KeyboardEvent<HTMLElement>) => {
    if (
      !open &&
      (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ")
    ) {
      event.preventDefault();
      if (canOpen) setOpen(true);
      return;
    }
    if (!open && event.key.length === 1 && !event.ctrlKey && !event.metaKey) {
      setTypeahead((current) => current + event.key);
      if (canOpen) setOpen(true);
      return;
    }
    if (!open) return;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      closeList();
      return;
    }
    if (event.key === " " && searchable) return;
    listboxKeydown(
      event,
      visibleFlat.length,
      highlighted,
      setHighlighted,
      () => {
        const option = visibleFlat[highlighted];
        if (option) selectValue(option.value);
        else if (creatable && search && onCreate) onCreate(search);
      },
      closeList,
    );
  };

  const summary =
    selected.length === 0
      ? placeholder
      : listMode === "multi" || listMode === "checkbox"
        ? `${selected.length} selected`
        : selected[0]?.label;

  return (
    <div className="ds-anchor" ref={anchorRef}>
      <div
        className={cx(
          "ds-combo",
          compact && "ds-combo--compact",
          invalid && "ds-combo--invalid",
          disabled && "ds-combo--disabled",
          readOnly && "ds-combo--readonly",
          unavailable && "ds-combo--unavailable",
        )}
      >
        {leading}
        {searchable ? (
          <input
            ref={searchRef}
            id={id}
            className="ds-combo__input"
            role="combobox"
            aria-expanded={open}
            aria-autocomplete="list"
            aria-invalid={invalid || undefined}
            aria-required={required || undefined}
            aria-label={label}
            disabled={disabled}
            readOnly={readOnly}
            placeholder={placeholder}
            value={open ? search : (selected[0]?.label ?? "")}
            onChange={(event) => {
              setSearch(event.target.value);
              setOpen(true);
              setHighlighted(0);
            }}
            onFocus={() => {
              if (!canOpen) return;
              if (skipFocusOpen.current) {
                skipFocusOpen.current = false;
                return;
              }
              setSearch("");
              setOpen(true);
            }}
            onClick={() => {
              if (!canOpen || open) return;
              setSearch("");
              setOpen(true);
            }}
            onKeyDown={onKey}
          />
        ) : (
          <button
            ref={triggerRef}
            id={id}
            type="button"
            className="ds-combo__input ds-combo__trigger"
            aria-haspopup="listbox"
            aria-expanded={open}
            aria-invalid={invalid || undefined}
            aria-required={required || undefined}
            aria-label={label}
            disabled={disabled || readOnly || unavailable}
            onClick={() => {
              if (!canOpen) return;
              if (open) closeList();
              else setOpen(true);
            }}
            onKeyDown={onKey}
          >
            {listMode === "multi" || listMode === "checkbox" ? (
              selected.length ? (
                <span className="ds-combo__chips">
                  {selected.slice(0, 3).map((option) => (
                    <span key={option.value} className="ds-chip">
                      {option.label}
                    </span>
                  ))}
                  {selected.length > 3 ? (
                    <span className="ds-chip">+{selected.length - 3}</span>
                  ) : null}
                </span>
              ) : (
                <span className="ds-combo__placeholder">{placeholder}</span>
              )
            ) : (
              <span
                className={
                  selected.length ? undefined : "ds-combo__placeholder"
                }
              >
                {summary}
              </span>
            )}
          </button>
        )}
        <span className="ds-combo__actions">
          {clearable && selectedValues.length > 0 && canOpen ? (
            <button
              type="button"
              className="ds-combo__clear"
              aria-label="Clear selection"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() =>
                onChange(
                  listMode === "multi" || listMode === "checkbox" ? [] : "",
                )
              }
            >
              <DsIcon name="close" size={14} />
            </button>
          ) : null}
          <button
            type="button"
            className="ds-combo__chevron"
            tabIndex={-1}
            aria-hidden="true"
            disabled={!canOpen}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => {
              if (!canOpen) return;
              if (open) closeList();
              else setOpen(true);
            }}
          >
            <DsIcon name="expand" size={16} />
          </button>
        </span>
      </div>
      <PositionedOverlay
        open={open && canOpen}
        anchorRef={anchorRef}
        onClose={closeList}
        role="presentation"
        label={label ?? "Options"}
        className="ds-listbox-panel"
        matchAnchorWidth
      >
        {creatable &&
        search &&
        !visibleFlat.some((item) => item.label === search) ? (
          <button
            type="button"
            className="ds-listbox__option"
            onClick={() => onCreate?.(search)}
          >
            Create “{search}”
          </button>
        ) : null}
        <Listbox
          options={onQueryChange ? options : visible}
          value={value}
          highlighted={highlighted}
          onHighlight={setHighlighted}
          onSelect={selectValue}
          query={onQueryChange ? "" : search}
          loading={loading}
          loadingMore={loadingMore}
          emptyLabel={emptyLabel}
          unavailable={unavailable}
          mode={listMode}
          expandedIds={expandedIds}
          onToggleExpand={(id) =>
            setExpandedIds((current) =>
              current.includes(id)
                ? current.filter((item) => item !== id)
                : [...current, id],
            )
          }
          label={label}
        />
      </PositionedOverlay>
    </div>
  );
}

export function Select({
  id,
  options,
  value = "",
  onChange,
  placeholder,
  compact,
  disabled,
  readOnly,
  required,
  invalid,
  label,
  loading,
  unavailable,
  clearable,
}: {
  id: string;
  options: SelectOption[];
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  compact?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  required?: boolean;
  invalid?: boolean;
  label?: string;
  loading?: boolean;
  unavailable?: boolean;
  clearable?: boolean;
}) {
  return (
    <DropdownSelect
      id={id}
      label={label}
      options={options}
      value={value}
      onChange={(next) => onChange?.(String(next))}
      placeholder={placeholder}
      compact={compact}
      disabled={disabled}
      readOnly={readOnly}
      required={required}
      invalid={invalid}
      loading={loading}
      unavailable={unavailable}
      clearable={clearable}
    />
  );
}
