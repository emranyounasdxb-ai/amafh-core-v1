import { useRef, useState } from "react";
import { DsIcon } from "../icons";
import { cx } from "../lib/cx";
import {
  dubaiTodayDateOnly,
  formatDateOnly,
  formatDateOnlyFull,
  startOfMonth,
  type DateOnly,
} from "../lib/dateOnly";
import { Calendar } from "./Calendar";
import { PositionedOverlay } from "./PositionedOverlay";

export function DatePicker({
  id,
  value,
  onChange,
  min,
  max,
  disabledDates,
  disabled,
  readOnly,
  invalid,
  required,
  compact,
  placeholder = "Select date",
}: {
  id?: string;
  value: DateOnly | "";
  onChange: (value: DateOnly | "") => void;
  min?: DateOnly;
  max?: DateOnly;
  disabledDates?: DateOnly[] | ((date: DateOnly) => boolean);
  disabled?: boolean;
  readOnly?: boolean;
  invalid?: boolean;
  required?: boolean;
  compact?: boolean;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(
    startOfMonth(value || dubaiTodayDateOnly()),
  );
  const anchorRef = useRef<HTMLDivElement>(null);
  return (
    <div className="ds-anchor" ref={anchorRef}>
      <div
        className={cx(
          "ds-date-control",
          compact && "ds-date-control--compact",
          invalid && "ds-date-control--invalid",
          disabled && "ds-date-control--disabled",
          readOnly && "ds-date-control--readonly",
        )}
      >
        <button
          id={id}
          type="button"
          className="ds-date-control__button"
          disabled={disabled || readOnly}
          aria-expanded={open}
          aria-haspopup="dialog"
          aria-invalid={invalid || undefined}
          aria-required={required || undefined}
          aria-label={value ? formatDateOnlyFull(value) : undefined}
          onClick={() => setOpen((current) => !current)}
        >
          <DsIcon name="calendar" size={16} />
          <span>{value ? formatDateOnly(value) : placeholder}</span>
        </button>
        {value && !disabled && !readOnly ? (
          <button
            type="button"
            className="ds-combo__clear"
            aria-label="Clear date"
            onClick={() => onChange("")}
          >
            <DsIcon name="close" size={14} />
          </button>
        ) : null}
      </div>
      <PositionedOverlay
        open={open && !disabled && !readOnly}
        anchorRef={anchorRef}
        onClose={() => setOpen(false)}
        label="Choose date"
        trapFocus
        className="ds-date-popover"
      >
        <Calendar
          month={month}
          onMonthChange={setMonth}
          value={value || undefined}
          min={min}
          max={max}
          disabledDates={disabledDates}
          onSelect={(next) => {
            onChange(next);
            setOpen(false);
          }}
        />
      </PositionedOverlay>
    </div>
  );
}

export function DateField({
  id,
  value = "",
  onChange,
  compact,
  disabled,
  readOnly,
  required,
  min,
  max,
  ...props
}: {
  id?: string;
  value?: DateOnly | "";
  onChange?: (value: DateOnly | "") => void;
  compact?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
  required?: boolean;
  min?: DateOnly;
  max?: DateOnly;
  "aria-invalid"?: boolean | "true" | "false";
}) {
  const [internal, setInternal] = useState(value);
  return (
    <DatePicker
      id={id}
      value={onChange ? value : internal}
      onChange={onChange ?? setInternal}
      compact={compact}
      disabled={disabled}
      readOnly={readOnly}
      required={required}
      min={min}
      max={max}
      invalid={
        props["aria-invalid"] === true || props["aria-invalid"] === "true"
      }
    />
  );
}
