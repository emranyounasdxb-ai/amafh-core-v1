import { useMemo, useRef, useState } from "react";
import { DsIcon } from "../icons";
import { cx } from "../lib/cx";
import {
  addMonths,
  dubaiTodayDateOnly,
  formatCompactDateRange,
  formatDateOnly,
  formatDateOnlyFull,
  lastDaysRange,
  startOfMonth,
  thisMonthRange,
  type DateOnly,
} from "../lib/dateOnly";
import { Button } from "./Button";
import { Calendar } from "./Calendar";
import type { OverlayPlacement } from "../lib/positionOverlay";
import { PositionedOverlay } from "./PositionedOverlay";

export type DateRangeValue = { start: DateOnly | ""; end: DateOnly | "" };

export type DateRangePreset = {
  id: string;
  label: string;
  range: DateRangeValue;
};

const defaultPresets = (today = dubaiTodayDateOnly()): DateRangePreset[] => [
  { id: "today", label: "Today", range: { start: today, end: today } },
  { id: "month", label: "This month", range: thisMonthRange(today) },
  { id: "30", label: "Last 30 days", range: lastDaysRange(30, today) },
  { id: "custom", label: "Custom", range: { start: "", end: "" } },
];

export function DateRangePicker({
  id,
  value,
  onChange,
  min,
  max,
  disabledDates,
  disabled,
  readOnly,
  invalid,
  compact,
  presets,
  months = 2,
  className,
  placement = "auto",
  compactRangeLabel = false,
}: {
  id?: string;
  value: DateRangeValue;
  onChange: (value: DateRangeValue) => void;
  min?: DateOnly;
  max?: DateOnly;
  disabledDates?: DateOnly[] | ((date: DateOnly) => boolean);
  disabled?: boolean;
  readOnly?: boolean;
  invalid?: boolean;
  compact?: boolean;
  presets?: DateRangePreset[];
  months?: 1 | 2;
  className?: string;
  placement?: OverlayPlacement;
  compactRangeLabel?: boolean;
}) {
  const today = dubaiTodayDateOnly();
  const presetItems = presets ?? defaultPresets(today);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(value);
  const [preset, setPreset] = useState("custom");
  const [leftMonth, setLeftMonth] = useState(
    startOfMonth(value.start || today),
  );
  const anchorRef = useRef<HTMLDivElement>(null);
  const rightMonth = addMonths(leftMonth, 1);
  const label = useMemo(() => {
    if (value.start && value.end) {
      return compactRangeLabel
        ? formatCompactDateRange(value.start, value.end)
        : `${formatDateOnly(value.start)} – ${formatDateOnly(value.end)}`;
    }
    if (value.start) return `${formatDateOnly(value.start)} – End`;
    return "Select date range";
  }, [compactRangeLabel, value.end, value.start]);
  const fullLabel = useMemo(() => {
    if (value.start && value.end) {
      return `${formatDateOnlyFull(value.start)} – ${formatDateOnlyFull(value.end)}`;
    }
    if (value.start) return `${formatDateOnlyFull(value.start)} – End`;
    return "Select date range";
  }, [value.end, value.start]);

  const selectDay = (next: DateOnly) => {
    setPreset("custom");
    if (!draft.start || (draft.start && draft.end)) {
      setDraft({ start: next, end: "" });
      return;
    }
    if (next < draft.start) {
      setDraft({ start: next, end: draft.start });
      return;
    }
    setDraft({ start: draft.start, end: next });
  };

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
          aria-label={fullLabel}
          onClick={() => {
            setDraft(value);
            setOpen((current) => !current);
          }}
        >
          <DsIcon name="calendar" size={16} />
          <span>{label}</span>
        </button>
        {value.start && !disabled && !readOnly ? (
          <button
            type="button"
            className="ds-combo__clear"
            aria-label="Clear date range"
            onClick={() => onChange({ start: "", end: "" })}
          >
            <DsIcon name="close" size={14} />
          </button>
        ) : null}
      </div>
      <PositionedOverlay
        open={open && !disabled && !readOnly}
        anchorRef={anchorRef}
        onClose={() => setOpen(false)}
        label="Choose date range"
        trapFocus
        placement={placement}
        className={cx(
          "ds-date-popover ds-date-popover--range",
          compact && "ds-date-popover--compact",
          className,
        )}
        lockHeight={!compact}
      >
        <div
          className={cx("ds-date-range", compact && "ds-date-range--compact")}
        >
          {presetItems.length > 0 ? (
            <div className="ds-date-range__presets" role="list">
              {presetItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={cx(
                    "ds-date-range__preset",
                    preset === item.id && "ds-date-range__preset--active",
                  )}
                  onClick={() => {
                    setPreset(item.id);
                    if (item.id !== "custom") setDraft(item.range);
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ) : null}
          <div
            className={cx(
              "ds-date-range__calendars",
              months === 1 && "ds-date-range__calendars--single",
            )}
          >
            <Calendar
              month={leftMonth}
              onMonthChange={setLeftMonth}
              rangeStart={draft.start || undefined}
              rangeEnd={draft.end || undefined}
              min={min}
              max={max}
              disabledDates={disabledDates}
              onSelect={selectDay}
            />
            {months === 2 ? (
              <Calendar
                month={rightMonth}
                onMonthChange={(next) => setLeftMonth(addMonths(next, -1))}
                rangeStart={draft.start || undefined}
                rangeEnd={draft.end || undefined}
                min={min}
                max={max}
                disabledDates={disabledDates}
                onSelect={selectDay}
              />
            ) : null}
          </div>
          <div className="ds-date-range__footer">
            <Button
              variant="ghost"
              size="compact"
              onClick={() => {
                setDraft({ start: "", end: "" });
                onChange({ start: "", end: "" });
              }}
            >
              Clear
            </Button>
            <Button
              size="compact"
              disabled={!draft.start || !draft.end}
              onClick={() => {
                onChange(draft);
                setOpen(false);
              }}
            >
              Apply
            </Button>
          </div>
        </div>
      </PositionedOverlay>
    </div>
  );
}
