import { cx } from "../lib/cx";
import { DsIcon } from "../icons";
import {
  addDays,
  addMonths,
  dubaiTodayDateOnly,
  daysInMonth,
  isDateDisabled,
  monthLabel,
  parseDateOnly,
  startOfMonth,
  toDateOnly,
  weekdayMondayIndex,
  type DateOnly,
} from "../lib/dateOnly";
import { IconButton } from "./IconButton";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function Calendar({
  month,
  onMonthChange,
  value,
  rangeStart,
  rangeEnd,
  onSelect,
  min,
  max,
  disabledDates,
  heading,
}: {
  month: DateOnly;
  onMonthChange: (month: DateOnly) => void;
  value?: DateOnly;
  rangeStart?: DateOnly;
  rangeEnd?: DateOnly;
  onSelect: (value: DateOnly) => void;
  min?: DateOnly;
  max?: DateOnly;
  disabledDates?: DateOnly[] | ((date: DateOnly) => boolean);
  heading?: string;
}) {
  const parts = parseDateOnly(startOfMonth(month));
  if (!parts) return null;
  const today = dubaiTodayDateOnly();
  const blanks = weekdayMondayIndex(parts.year, parts.month, 1);
  const days = daysInMonth(parts.year, parts.month);
  const monthStart = toDateOnly(parts.year, parts.month, 1);
  const leading = Array.from({ length: blanks }, (_, index) =>
    addDays(monthStart, index - blanks),
  );
  const current = Array.from({ length: days }, (_, index) =>
    toDateOnly(parts.year, parts.month, index + 1),
  );
  const remainder = (blanks + days) % 7;
  const trailing = Array.from(
    { length: remainder === 0 ? 0 : 7 - remainder },
    (_, index) => addDays(current[current.length - 1]!, index + 1),
  );
  const cells = [
    ...leading.map((date) => ({ date, outside: true })),
    ...current.map((date) => ({ date, outside: false })),
    ...trailing.map((date) => ({ date, outside: true })),
  ];

  return (
    <div className="ds-calendar">
      <div className="ds-calendar__toolbar">
        <IconButton
          label="Previous month"
          variant="ghost"
          size="compact"
          onClick={() => onMonthChange(addMonths(startOfMonth(month), -1))}
        >
          <DsIcon name="previous" size={16} />
        </IconButton>
        <p className="ds-calendar__heading">
          {heading ?? monthLabel(parts.year, parts.month)}
        </p>
        <IconButton
          label="Next month"
          variant="ghost"
          size="compact"
          onClick={() => onMonthChange(addMonths(startOfMonth(month), 1))}
        >
          <DsIcon name="next" size={16} />
        </IconButton>
      </div>
      <div className="ds-calendar__weekdays">
        {WEEKDAYS.map((day) => (
          <span key={day}>{day}</span>
        ))}
      </div>
      <div
        className="ds-calendar__grid"
        role="grid"
        aria-label={monthLabel(parts.year, parts.month)}
      >
        {cells.map(({ date, outside }) => {
          const disabled = isDateDisabled(date, { min, max, disabledDates });
          const isStart = date === rangeStart;
          const isEnd = date === rangeEnd;
          const selected = date === value || isStart || isEnd;
          const inRange = Boolean(
            rangeStart && rangeEnd && date > rangeStart && date < rangeEnd,
          );
          return (
            <button
              key={date}
              type="button"
              className={cx(
                "ds-calendar__day",
                selected && "ds-calendar__day--selected",
                isStart && "ds-calendar__day--range-start",
                isEnd && "ds-calendar__day--range-end",
                inRange && "ds-calendar__day--range",
                date === today && "ds-calendar__day--today",
                outside && "ds-calendar__day--outside",
              )}
              disabled={disabled}
              aria-pressed={selected}
              onClick={() => onSelect(date)}
            >
              {parseDateOnly(date)?.day}
            </button>
          );
        })}
      </div>
    </div>
  );
}
