import { useRef, useState } from "react";
import { cx } from "../lib/cx";
import { dubaiTodayDateOnly, parseDateOnly } from "../lib/dateOnly";
import { Button } from "./Button";
import { PositionedOverlay } from "./PositionedOverlay";

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

export function MonthPicker({
  id,
  value,
  onChange,
  disabled,
  readOnly,
  invalid,
  compact,
  monthOnly,
  label: controlLabel,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  readOnly?: boolean;
  invalid?: boolean;
  compact?: boolean;
  monthOnly?: boolean;
  label?: string;
}) {
  const today = parseDateOnly(dubaiTodayDateOnly())!;
  const [year, month] = value
    ? value.split("-").map(Number)
    : [today.year, today.month];
  const [open, setOpen] = useState(false);
  const [viewYear, setViewYear] = useState(year);
  const anchorRef = useRef<HTMLDivElement>(null);
  const label = value
    ? monthOnly
      ? MONTHS[month - 1]
      : new Intl.DateTimeFormat("en-GB", {
          month: "short",
          year: "numeric",
          timeZone: "UTC",
        }).format(new Date(Date.UTC(year, month - 1, 1)))
    : "Select month";

  return (
    <div className="ds-anchor" ref={anchorRef}>
      <button
        id={id}
        type="button"
        className={cx(
          "ds-date-control ds-date-control__button",
          compact && "ds-date-control--compact",
          invalid && "ds-date-control--invalid",
        )}
        disabled={disabled || readOnly}
        aria-expanded={open}
        aria-label={controlLabel ?? "Month"}
        onClick={() => setOpen((current) => !current)}
      >
        {label}
      </button>
      <PositionedOverlay
        open={open && !disabled && !readOnly}
        anchorRef={anchorRef}
        onClose={() => setOpen(false)}
        label="Choose month"
        className="ds-month-panel"
        trapFocus
      >
        <div className="ds-calendar__toolbar">
          <Button
            variant="ghost"
            size="compact"
            aria-label={`Previous year, ${viewYear - 1}`}
            onClick={() => setViewYear((current) => current - 1)}
          >
            {viewYear - 1}
          </Button>
          <strong>{viewYear}</strong>
          <Button
            variant="ghost"
            size="compact"
            aria-label={`Next year, ${viewYear + 1}`}
            onClick={() => setViewYear((current) => current + 1)}
          >
            {viewYear + 1}
          </Button>
        </div>
        <div className="ds-month-grid">
          {MONTHS.map((name, index) => {
            const next = `${viewYear}-${String(index + 1).padStart(2, "0")}`;
            return (
              <button
                key={name}
                type="button"
                className={cx(
                  "ds-month-grid__item",
                  value === next && "ds-month-grid__item--selected",
                )}
                onClick={() => {
                  onChange(next);
                  setOpen(false);
                }}
              >
                {name}
              </button>
            );
          })}
        </div>
      </PositionedOverlay>
    </div>
  );
}

export function YearPicker({
  id,
  value,
  onChange,
  min = 2018,
  max = 2032,
  disabled,
  compact,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  min?: number;
  max?: number;
  disabled?: boolean;
  compact?: boolean;
}) {
  const years = Array.from({ length: max - min + 1 }, (_, index) =>
    String(min + index),
  );
  return (
    <select
      id={id}
      className={cx("ds-select", compact && "ds-select--compact")}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
    >
      {years.map((year) => (
        <option key={year} value={year}>
          {year}
        </option>
      ))}
    </select>
  );
}
