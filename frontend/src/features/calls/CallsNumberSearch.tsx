import { useEffect, useRef, useState } from "react";
import { DsIcon } from "../../design-system";
import { useSession } from "../../app/session/useSession";
import {
  NUMBER_SUGGESTION_DELAY_MS,
  numberSuggestionPrefix,
} from "./numberLookup";

export function CallsNumberSearch({
  month,
  value,
  disabled,
  onChange,
  onSelect,
}: {
  month: string;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
  onSelect: (value: string) => void;
}) {
  const { api, session } = useSession();
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(-1);
  const prefix = numberSuggestionPrefix(value);
  const [lookup, setLookup] = useState<{
    owner: typeof session;
    month: string;
    prefix: string;
    numbers: string[];
    loading: boolean;
    failed: boolean;
  } | null>(null);
  const eligible = open && !disabled && !!session && !!month && prefix !== null;
  const current =
    eligible &&
    lookup?.owner === session &&
    lookup.month === month &&
    lookup.prefix === prefix
      ? lookup
      : null;
  const items = current?.numbers ?? [];
  const listVisible = eligible && items.length > 0;
  const active =
    listVisible && highlighted >= 0 && highlighted < items.length
      ? highlighted
      : -1;

  useEffect(() => {
    if (!eligible || prefix === null) return;
    const controller = new AbortController();
    let live = true;
    const timer = setTimeout(() => {
      setLookup({
        owner: session,
        month,
        prefix,
        numbers: [],
        loading: true,
        failed: false,
      });
      api
        .request<{ month: string; prefix: string; numbers: string[] }>(
          "/calls/number-suggestions",
          {
            method: "POST",
            body: JSON.stringify({ month, prefix }),
            signal: controller.signal,
          },
        )
        .then((payload) => {
          if (
            !live ||
            controller.signal.aborted ||
            payload.month !== month ||
            payload.prefix !== prefix
          )
            return;
          setLookup({
            owner: session,
            month,
            prefix,
            numbers: payload.numbers,
            loading: false,
            failed: false,
          });
        })
        .catch(() => {
          if (live && !controller.signal.aborted) {
            setLookup({
              owner: session,
              month,
              prefix,
              numbers: [],
              loading: false,
              failed: true,
            });
          }
        });
    }, NUMBER_SUGGESTION_DELAY_MS);
    return () => {
      live = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [api, session, month, prefix, eligible]);

  function choose(number: string) {
    setOpen(false);
    setHighlighted(-1);
    onChange(number);
    onSelect(number);
  }

  return (
    <div
      className="calls-number-search"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null))
          setOpen(false);
      }}
    >
      <label className="ds-field__label" htmlFor="calls-customer-number">
        Phone number or extension
      </label>
      <div className="ds-search ds-search--compact">
        <DsIcon name="search" size={16} />
        <input
          ref={inputRef}
          id="calls-customer-number"
          className="ds-search__input"
          type="text"
          inputMode="numeric"
          maxLength={80}
          autoComplete="off"
          spellCheck={false}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={listVisible}
          aria-controls={listVisible ? "calls-number-suggestions" : undefined}
          aria-activedescendant={
            active >= 0 ? `calls-number-option-${active}` : undefined
          }
          aria-describedby="calls-number-hint"
          placeholder="Start typing a phone number or extension"
          value={value}
          disabled={disabled || !session}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            onChange(event.target.value);
            setOpen(true);
            setHighlighted(-1);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" && items.length) {
              event.preventDefault();
              setHighlighted((current) => (current + 1) % items.length);
            } else if (event.key === "ArrowUp" && items.length) {
              event.preventDefault();
              setHighlighted((current) =>
                current <= 0 ? items.length - 1 : current - 1,
              );
            } else if (event.key === "Enter" && active >= 0) {
              event.preventDefault();
              choose(items[active]);
            } else if (event.key === "Enter") {
              setOpen(false);
            } else if (event.key === "Escape") {
              event.preventDefault();
              setOpen(false);
              setHighlighted(-1);
            }
          }}
        />
        {value ? (
          <button
            className="ds-search__clear"
            type="button"
            aria-label="Clear search"
            disabled={disabled}
            onClick={() => {
              onChange("");
              setOpen(false);
              setHighlighted(-1);
              inputRef.current?.focus();
            }}
          >
            <DsIcon name="close" size={14} />
          </button>
        ) : null}
      </div>
      <p id="calls-number-hint" className="calls-field-hint">
        Type 3 or more digits for suggestions in the selected month.
      </p>
      {eligible &&
      (listVisible ||
        current?.loading ||
        current?.failed ||
        (current && !current.numbers.length)) ? (
        <div className="calls-suggestion-popover">
          <div className="calls-suggestion-heading">Matching numbers</div>
          {listVisible ? (
            <ul
              role="listbox"
              id="calls-number-suggestions"
              aria-label="Matching numbers"
            >
              {items.map((number, index) => (
                <li
                  key={number}
                  id={`calls-number-option-${index}`}
                  role="option"
                  aria-selected={active === index}
                  className={active === index ? "is-active" : undefined}
                  onMouseEnter={() => setHighlighted(index)}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => choose(number)}
                >
                  <DsIcon name="phone" size={16} />
                  <span>{number}</span>
                  <DsIcon name="forward" size={14} />
                </li>
              ))}
            </ul>
          ) : (
            <p role="status">
              {current?.loading
                ? "Finding matching numbers…"
                : current?.failed
                  ? "Suggestions unavailable. Use Search for an exact number."
                  : "No matching numbers in this month."}
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
