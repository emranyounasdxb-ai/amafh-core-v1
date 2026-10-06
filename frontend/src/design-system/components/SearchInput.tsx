import { useEffect, useState } from "react";
import { DsIcon } from "../icons";
import { cx } from "../lib/cx";
import { useDebouncedValue } from "../lib/useDebouncedValue";

export function SearchInput({
  id,
  value,
  onChange,
  onDebouncedChange,
  debounce = 0,
  placeholder = "Search",
  compact = true,
  disabled,
  suggestions,
  onSuggestionSelect,
  label = "Search",
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  onDebouncedChange?: (value: string) => void;
  debounce?: number;
  placeholder?: string;
  compact?: boolean;
  disabled?: boolean;
  suggestions?: string[];
  onSuggestionSelect?: (value: string) => void;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const debounced = useDebouncedValue(value, debounce);
  useEffect(() => {
    if (debounce && onDebouncedChange) onDebouncedChange(debounced);
  }, [debounce, debounced, onDebouncedChange]);

  return (
    <div className={cx("ds-search", compact && "ds-search--compact")}>
      <DsIcon name="search" size={16} />
      <input
        id={id}
        type="search"
        className="ds-search__input"
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        aria-label={label}
        autoComplete="off"
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
      />
      {value ? (
        <button
          type="button"
          className="ds-search__clear"
          aria-label="Clear search"
          disabled={disabled}
          onClick={() => onChange("")}
        >
          <DsIcon name="close" size={14} />
        </button>
      ) : null}
      {open && suggestions && suggestions.length > 0 ? (
        <ul
          className="ds-search__suggestions"
          role="listbox"
          aria-label="Suggestions"
        >
          {suggestions.map((item) => (
            <li key={item}>
              <button
                type="button"
                role="option"
                onMouseDown={(event) => {
                  event.preventDefault();
                  onSuggestionSelect?.(item);
                  onChange(item);
                  setOpen(false);
                }}
              >
                {item}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
